"""
Tests d'intégration du moniteur — Étape 3.

Exécution (Oracle doit être démarré) :
    cd backend && ./venv/bin/python -m tests.test_monitor

Scénario simulé (snapshots injectés, pas de charge réelle) :
    NORMAL -> WARNING confirmé -> CRITICAL confirmé -> rétablissement

Vérifie : détection, persistance des alertes en Oracle, résolution,
absence de renvoi en boucle, et tolérance à une base indisponible.
"""

from __future__ import annotations

import sys

from engine.monitor import Monitor
from storage import db, repository

_failures: list[str] = []


def _check(label: str, condition: bool, detail: str = "") -> None:
    print(f"[{'OK  ' if condition else 'FAIL'}] {label}" + (f" — {detail}" if detail else ""))
    if not condition:
        _failures.append(label)


def _snap(cpu: float, ram: float, disk: float) -> dict:
    """Snapshot synthétique aux valeurs de CPU/RAM/DISCO données (%)."""
    return {
        "collected_at": "2026-11-18T12:00:00+00:00",
        "cpu": {"percent": cpu, "per_core": [cpu] * 8, "core_count": 8},
        "ram": {"percent": ram, "total_mb": 15853.7,
                "used_mb": round(15853.7 * ram / 100, 2),
                "available_mb": round(15853.7 * (100 - ram) / 100, 2)},
        "disk": {"percent": disk, "path": "/", "total_gb": 128.0,
                 "used_gb": round(128.0 * disk / 100, 2),
                 "free_gb": round(128.0 * (100 - disk) / 100, 2)},
    }


def _counts(machine_id: int) -> tuple[int, int]:
    with db.acquire() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM alerts WHERE machine_id = :m",
                        m=machine_id)
            total = cur.fetchone()[0]
            cur.execute(
                "SELECT COUNT(*) FROM alerts WHERE machine_id = :m "
                "AND status = 'OPEN'", m=machine_id)
            open_ = cur.fetchone()[0]
    return total, open_


def main() -> int:
    # --- Connexion requise pour ce test ---
    try:
        db.health_check()
    except db.DatabaseUnavailable as exc:
        print(f"SKIP : Oracle indisponible ({exc})")
        return 1

    monitor = Monitor(interval=0.1)
    machine_id = monitor._ensure_machine()
    print(f"Machine de test : id={machine_id}\n")

    baseline_alerts, _ = _counts(machine_id)
    # Ids max au départ : sert à purger les données synthétiques du test
    # à la fin (le dashboard affiche les "dernières alertes" : elles
    # doivent être de vraies données).
    with db.acquire() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT (SELECT NVL(MAX(alert_id), 0) FROM alerts), "
                "       (SELECT NVL(MAX(metric_id), 0) FROM metrics) "
                "FROM dual")
            start_alert_id, start_metric_id = cur.fetchone()

    # --- 1. Pic isolé : 2 mesures CPU à 96 % puis retour ---
    print("--- Scénario 1 : pic isolé (aucune alerte) ---")
    for _ in range(2):
        monitor.run_cycle(_snap(cpu=96.0, ram=50.0, disk=69.0))
    monitor.run_cycle(_snap(cpu=20.0, ram=50.0, disk=69.0))
    total, _ = _counts(machine_id)
    _check("Pic isolé : aucune alerte persistée", total == baseline_alerts,
           f"{total - baseline_alerts} alerte(s)")
    _check("État CPU NORMAL après pic",
           monitor.detector.snapshot()["CPU"].value == "NORMAL")

    # --- 2. WARNING confirmé (3 mesures >= 75 %) ---
    print("\n--- Scénario 2 : confirmation WARNING ---")
    trans = []
    for _ in range(3):
        trans += monitor.run_cycle(_snap(cpu=80.0, ram=50.0, disk=69.0))
    _check("Exactement 1 transition WARNING",
           len(trans) == 1 and trans[0].current.value == "WARNING",
           f"{len(trans)} transition(s)")
    # Encore 3 cycles identiques : pas de renvoi
    trans2 = []
    for _ in range(3):
        trans2 += monitor.run_cycle(_snap(cpu=82.0, ram=50.0, disk=69.0))
    _check("Pas de renvoi en état stable", not trans2,
           f"{len(trans2)} transition(s) supplémentaire(s)")

    # --- 3. RAM en WARNING en parallèle (indépendance) ---
    print("\n--- Scénario 3 : RAM WARNING indépendant ---")
    trans3 = []
    for _ in range(3):
        trans3 += monitor.run_cycle(_snap(cpu=82.0, ram=85.0, disk=69.0))
    _check("Transition RAM isolée sans perturber CPU",
           len(trans3) == 1 and trans3[0].resource == "RAM",
           f"{len(trans3)} transition(s) : {[t.resource for t in trans3]}")

    # --- 4. Escalade CRITICAL ---
    print("\n--- Scénario 4 : escalade CPU -> CRITICAL ---")
    trans4 = []
    for _ in range(3):
        trans4 += monitor.run_cycle(_snap(cpu=96.0, ram=85.0, disk=69.0))
    _check("1 escalade CRITICAL (CPU)",
           len(trans4) == 1 and trans4[0].resource == "CPU"
           and trans4[0].current.value == "CRITICAL"
           and trans4[0].previous.value == "WARNING",
           f"{len(trans4)} : {[(t.resource, t.current.value) for t in trans4]}")

    # --- 5. Rétablissement complet ---
    print("\n--- Scénario 5 : rétablissement ---")
    trans5 = []
    for _ in range(4):
        trans5 += monitor.run_cycle(_snap(cpu=30.0, ram=40.0, disk=69.0))
    recovered = {t.resource for t in trans5 if t.is_recovery}
    _check("CPU et RAM rétablis", recovered == {"CPU", "RAM"},
           f"rétablis = {recovered}, transitions = {len(trans5)}")

    # --- 6. Persistance : alertes + résolutions ---
    print("\n--- Scénario 6 : persistance Oracle ---")
    total, open_ = _counts(machine_id)
    _check("5 alertes persistées (CPU WARNING + RAM WARNING + CPU "
           "CRITICAL + 2 rétablissements)",
           total - baseline_alerts == 5,
           f"{total - baseline_alerts} alerte(s) créée(s)")
    _check("Plus aucune alerte OPEN (tout résolu)", open_ == 0,
           f"{open_} OPEN")
    alerts = repository.recent_alerts(machine_id, limit=10)
    _check("Alertes relatables via repository", len(alerts) >= 4,
           f"{len(alerts)} ligne(s)")
    _check("Résolutions horodatées",
           all(a["resolved_at"] or a["status"] == "RESOLVED" for a in alerts
               if a["level"] != "NORMAL"))
    _check("Champ alert_resource correct",
           {a["resource"] for a in alerts} >= {"CPU", "RAM"},
           str({a["resource"] for a in alerts}))

    # --- 7. Tolérance base indisponible ---
    print("\n--- Scénario 7 : résilience (métriques toujours collectées) ---")
    saved_dsn = db.ORACLE_DSN
    db.ORACLE_DSN = "localhost:1/INVALID"
    db.close_pool()  # force la reconnexion sur le faux DSN
    try:
        snap = _snap(cpu=10.0, ram=10.0, disk=69.0)
        trans7 = monitor.run_cycle(snap)   # ne doit pas lever d'exception
        _check("Cycle survit à l'indisponibilité Oracle", True)
        _check("Collecte et détection toujours actives",
               monitor.last_snapshot["cpu"]["percent"] == 10.0)
    except Exception as exc:  # noqa: BLE001
        _check("Cycle survit à l'indisponibilité Oracle", False,
               f"{type(exc).__name__}: {exc}")
    finally:
        db.ORACLE_DSN = saved_dsn
        db.close_pool()

    print()
    # Purge des données synthétiques du test (conserve le historique réel)
    with db.acquire() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM alerts WHERE alert_id > :a",
                        a=start_alert_id)
            deleted_alerts = cur.rowcount
            cur.execute("DELETE FROM metrics WHERE metric_id > :m",
                        m=start_metric_id)
            deleted_metrics = cur.rowcount
        conn.commit()
    print(f"Purge du test : {deleted_alerts} alerte(s), "
          f"{deleted_metrics} métrique(s) synthétique(s) supprimée(s)")
    db.close_pool()  # fermeture propre en fin de test
    if _failures:
        print(f"{len(_failures)} TEST(S) EN ÉCHEC :")
        for name in _failures:
            print(f"  - {name}")
        return 1
    print("TOUS LES TESTS PASSENT")
    return 0


if __name__ == "__main__":
    sys.exit(main())
