"""
Persistance des données de surveillance (requêtes paramétrées).

Toutes les requêtes sont paramétrées (:name) — aucune concaténation
de valeurs utilisateur dans le SQL. Seul le module `storage/db.py`
gère la connexion ; ce fichier ne gère que les requêtes.
"""

from __future__ import annotations

import json

from engine.detector import State, Transition
from config import CONFIRM_SAMPLES
from storage import db


def register_machine(info: dict) -> int:
    """Enregistre la machine (idempotent par hostname) et renvoie son id.

    Requête MERGE : la machine locale est déclarée une seule fois,
    les champs statiques sont rafraîchis à chaque démarrage.
    """
    sql = """
        MERGE INTO machines m
        USING (SELECT :hostname AS hostname FROM dual) src
        ON (m.hostname = src.hostname)
        WHEN NOT MATCHED THEN
            INSERT (hostname, ip_address, os_info, cpu_cores, total_ram_mb, is_local)
            VALUES (:hostname, :ip, :os, :cores, :ram, 1)
        WHEN MATCHED THEN
            UPDATE SET ip_address = :ip, os_info = :os,
                       cpu_cores = :cores, total_ram_mb = :ram
    """
    with db.acquire() as conn:
        with conn.cursor() as cur:
            # MERGE ne supporte pas RETURNING INTO en Oracle :
            # on fusionne puis on relit l'identifiant.
            cur.execute(
                sql,
                hostname=info["hostname"],
                ip=info["ip_address"],
                os=info["os_info"],
                cores=info["cpu_cores"],
                ram=info["total_ram_mb"],
            )
            cur.execute(
                "SELECT machine_id FROM machines WHERE hostname = :h",
                h=info["hostname"],
            )
            machine_id = cur.fetchone()[0]
        conn.commit()
    return int(machine_id)


def insert_metric(machine_id: int, snapshot: dict) -> None:
    """Persiste un snapshot de métriques complet."""
    cpu, ram, disk = snapshot["cpu"], snapshot["ram"], snapshot["disk"]
    sql = """
        INSERT INTO metrics (
            machine_id, collected_at, cpu_percent, cpu_per_core,
            ram_total_mb, ram_used_mb, ram_avail_mb, ram_percent,
            disk_total_gb, disk_used_gb, disk_free_gb, disk_percent
        ) VALUES (
            :machine_id, TO_TIMESTAMP(:collected_at, 'YYYY-MM-DD"T"HH24:MI:SS'),
            :cpu_percent, :cpu_per_core,
            :ram_total, :ram_used, :ram_avail, :ram_percent,
            :disk_total, :disk_used, :disk_free, :disk_percent
        )
    """
    # collected_at est un ISO 8601 ('...+00:00') : on tronque le fuseau
    # et laissons Oracle interpréter en fuseau de la base.
    ts = snapshot["collected_at"][:19]
    with db.acquire() as conn:
        with conn.cursor() as cur:
            cur.execute(
                sql,
                machine_id=machine_id,
                collected_at=ts,
                cpu_percent=cpu["percent"],
                cpu_per_core=json.dumps(cpu["per_core"]),
                ram_total=ram["total_mb"],
                ram_used=ram["used_mb"],
                ram_avail=ram["available_mb"],
                ram_percent=ram["percent"],
                disk_total=disk["total_gb"],
                disk_used=disk["used_gb"],
                disk_free=disk["free_gb"],
                disk_percent=disk["percent"],
            )
        conn.commit()


def insert_alert(machine_id: int, transition: Transition) -> int:
    """Persiste une alerte issue d'un changement d'état confirmé.

    - transition vers WARNING/CRITICAL -> alerte OPEN ;
    - transition vers NORMAL -> résolution des alertes encore ouvertes
      de cette ressource + journal du rétablissement (alert_level NORMAL).
    """
    with db.acquire() as conn:
        with conn.cursor() as cur:
            if transition.is_recovery:
                cur.execute(
                    """
                    UPDATE alerts
                    SET status = 'RESOLVED', resolved_at = CURRENT_TIMESTAMP
                    WHERE machine_id = :m
                      AND alert_resource = :r
                      AND status = 'OPEN'
                    """,
                    m=machine_id,
                    r=transition.resource,
                )
                resolved = cur.rowcount
            else:
                resolved = 0

            message = _message(transition, resolved)
            # NB : les noms de bind :level et :resource sont refusés par
            # Oracle (mots réservés) — on utilise lvl / res.
            cur.execute(
                """
                INSERT INTO alerts (
                    machine_id, alert_resource, alert_level, message,
                    value_percent, threshold, status, notified
                ) VALUES (
                    :m, :res, :lvl, :msg, :value, :threshold, :status, 0
                )
                RETURNING alert_id INTO :id
                """,
                m=machine_id,
                res=transition.resource,
                lvl=transition.current.value,
                msg=message,
                value=transition.value,
                threshold=transition.threshold,
                status="RESOLVED" if transition.is_recovery else "OPEN",
                id=(alert_id := cur.var(int)),
            )
            alert_id_value = int(alert_id.getvalue()[0])
        conn.commit()
    return alert_id_value


def _message(transition: Transition, resolved_count: int) -> str:
    """Message d'alerte lisible, en français, destiné à Telegram/UI."""
    res = transition.resource
    if transition.is_recovery:
        base = f"✅ {res} rétabli : {transition.value}% (seuil {transition.threshold}%)"
        if resolved_count:
            base += f" — {resolved_count} alerte(s) fermée(s)"
        return base
    verb = "montée en sévérité" if transition.is_escalation else "détecté"
    return (
        f"{transition.current.value} {res} {verb} : {transition.value}% "
        f"(seuil {transition.threshold}%) — confirmé sur "
        f"{CONFIRM_SAMPLES} mesures"
    )


def latest_metrics(machine_id: int, limit: int = 1) -> list[dict]:
    """Dernières métriques d'une machine (pour l'API, étape 5)."""
    sql = """
        SELECT collected_at, cpu_percent, cpu_per_core,
               ram_total_mb, ram_used_mb, ram_avail_mb, ram_percent,
               disk_total_gb, disk_used_gb, disk_free_gb, disk_percent
        FROM (
            SELECT * FROM metrics
            WHERE machine_id = :m
            ORDER BY collected_at DESC
        )
        FETCH FIRST :lim ROWS ONLY
    """
    rows: list[dict] = []
    with db.acquire() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, m=machine_id, lim=limit)
            for row in cur:
                rows.append({
                    "collected_at": str(row[0]),
                    "cpu_percent": row[1],
                    # cpu_per_core est une CLOB : python-oracledb renvoie
                    # un objet LOB qu'il faut lire avant JSON.loads().
                    "cpu_per_core": json.loads(row[2].read()) if row[2] else [],
                    "ram_total_mb": row[3],
                    "ram_used_mb": row[4],
                    "ram_avail_mb": row[5],
                    "ram_percent": row[6],
                    "disk_total_gb": row[7],
                    "disk_used_gb": row[8],
                    "disk_free_gb": row[9],
                    "disk_percent": row[10],
                })
    return rows


def metrics_history(machine_id: int, limit: int = 60) -> list[dict]:
    """Historique des métriques (les plus récentes en premier).

    Alimente les courbes du dashboard (Recharts) : le frontend inverse
    l'ordre s'il a besoin d'une progression temporelle croissante.
    """
    sql = """
        SELECT collected_at, cpu_percent, ram_percent,
               disk_percent, ram_used_mb, disk_used_gb
        FROM (
            SELECT * FROM metrics
            WHERE machine_id = :m
            ORDER BY collected_at DESC
        )
        FETCH FIRST :lim ROWS ONLY
    """
    rows: list[dict] = []
    with db.acquire() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, m=machine_id, lim=limit)
            for row in cur:
                rows.append({
                    "collected_at": str(row[0]),
                    "cpu_percent": row[1],
                    "ram_percent": row[2],
                    "disk_percent": row[3],
                    "ram_used_mb": row[4],
                    "disk_used_gb": row[5],
                })
    return rows


def recent_alerts(machine_id: int, limit: int = 10) -> list[dict]:
    """Dernières alertes d'une machine (pour l'API / le dashboard)."""
    sql = """
        SELECT alert_id, alert_resource, alert_level, message,
               value_percent, threshold, status,
               started_at, resolved_at
        FROM (
            SELECT * FROM alerts
            WHERE machine_id = :m
            ORDER BY started_at DESC, alert_id DESC
        )
        FETCH FIRST :lim ROWS ONLY
    """
    rows: list[dict] = []
    with db.acquire() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, m=machine_id, lim=limit)
            for row in cur:
                rows.append({
                    "alert_id": row[0],
                    "resource": row[1],
                    "level": row[2],
                    "message": row[3],
                    "value_percent": row[4],
                    "threshold": row[5],
                    "status": row[6],
                    "started_at": str(row[7]),
                    "resolved_at": str(row[8]) if row[8] else None,
                })
    return rows


def mark_notified(alert_id: int) -> None:
    """Marque une alerte comme notifiée sur Telegram (étape 4)."""
    with db.acquire() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE alerts SET notified = 1 WHERE alert_id = :id",
                id=alert_id,
            )
        conn.commit()
