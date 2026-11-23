"""
Connexion Oracle Database (python-oracledb, mode Thin).

Responsabilités :
  - créer/réutiliser un pool de connexions vers l'instance existante
    (localhost:1521/XEPDB1) ;
  - bootstrap : créer l'utilisateur applicatif MONITOR_APP avec des
    privilèges minimaux si nécessaire (via SYS, une seule fois) ;
  - appliquer le schéma MVP (schema.sql) de façon idempotente.

Aucune autre couche du projet ne parle SQL directement en dehors
de ce module et de ses requêtes paramétrées.
"""

from __future__ import annotations

from pathlib import Path

import oracledb

from config import (
    ORACLE_DSN,
    ORACLE_PASSWORD,
    ORACLE_USER,
    SYS_PASSWORD,
    SYS_USER,
)

SCHEMA_FILE = Path(__file__).with_name("schema.sql")

_pool: oracledb.Pool | None = None

# Privilèges minimaux de l'utilisateur applicatif.
# Note : CREATE INDEX n'existe pas comme privilège système distinct en
# Oracle ; la création d'index est couverte par CREATE TABLE.
_APP_GRANTS = (
    "CREATE SESSION",
    "CREATE TABLE",
    "CREATE SEQUENCE",
)


class DatabaseUnavailable(RuntimeError):
    """Oracle n'est pas joignable (conteneur arrêté, mauvais DSN, ...)."""


def _connect_sys() -> oracledb.Connection:
    """Connexion bootstrap en SYSDBA (création de l'utilisateur uniquement)."""
    if not SYS_PASSWORD:
        raise DatabaseUnavailable("SYS_PASSWORD manquant dans le fichier .env")
    try:
        return oracledb.connect(
            user=SYS_USER,
            password=SYS_PASSWORD,
            dsn=ORACLE_DSN,
            mode=oracledb.AUTH_MODE_SYSDBA,
        )
    except oracledb.Error as exc:
        raise DatabaseUnavailable(f"Connexion SYS impossible : {exc}") from exc


def ensure_app_user() -> None:
    """Crée MONITOR_APP s'il n'existe pas (privilèges minimaux)."""
    with _connect_sys() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*) FROM dba_users
                WHERE username = UPPER(:u)
                """,
                u=ORACLE_USER,
            )
            exists = cur.fetchone()[0]
            if not exists:
                # Nom d'utilisateur et mot de passe en constantes littérales :
                # DDL non paramétrable, valeurs issues de la config uniquement.
                cur.execute(f'CREATE USER {ORACLE_USER} IDENTIFIED BY "{ORACLE_PASSWORD}"')
            # Les GRANT sont idempotents : on les rejoue toujours pour
            # garantir l'état complet (y après un run interrompu).
            for grant in _APP_GRANTS:
                cur.execute(f"GRANT {grant} TO {ORACLE_USER}")
            cur.execute(f"GRANT UNLIMITED TABLESPACE TO {ORACLE_USER}")


def get_pool() -> oracledb.Pool:
    """Pool de connexions applicatives (créé à la première utilisation)."""
    global _pool
    if _pool is None:
        try:
            _pool = oracledb.create_pool(
                user=ORACLE_USER,
                password=ORACLE_PASSWORD,
                dsn=ORACLE_DSN,
                min=1,
                max=4,
                increment=1,
            )
        except oracledb.Error as exc:
            raise DatabaseUnavailable(f"Connexion à {ORACLE_DSN} impossible : {exc}") from exc
    return _pool


def acquire() -> oracledb.Connection:
    """Borne une connexion du pool, en convertissant toute erreur
    réseau en DatabaseUnavailable (le pool peut être créé en différé
    par python-oracledb : c'est à l'acquisition que l'échec arrive)."""
    try:
        return get_pool().acquire()
    except oracledb.Error as exc:
        # On purge le pool défaillant : le prochain appel retentera.
        close_pool()
        raise DatabaseUnavailable(
            f"Acquisition de connexion impossible ({ORACLE_DSN}) : {exc}"
        ) from exc


def ensure_schema() -> None:
    """Applique schema.sql (idempotent) dans le schéma applicatif.

    Le fichier contient un unique bloc PL/SQL (les ';' internes sont
    ceux du bloc) : on l'exécute en une seule fois, après retrait des
    commentaires et du '/' final de terminaison SQL*Plus.
    """
    lines = []
    for line in SCHEMA_FILE.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("--") or stripped == "/":
            continue
        lines.append(line)
    sql = "\n".join(lines).strip()
    if not sql:
        return
    with acquire() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)


def health_check() -> dict:
    """Vérifie la disponibilité de l'instance et renvoie ses infos.

    Utilise uniquement des vues publiques (SYS_CONTEXT,
    PRODUCT_COMPONENT_VERSION) : l'utilisateur applicatif a des
    privilèges minimaux et n'a pas accès aux vues V$.
    """
    with acquire() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT version FROM product_component_version
                WHERE product LIKE 'Oracle%'
                """
            )
            row = cur.fetchone()
            version = row[0] if row else None
            cur.execute(
                """
                SELECT SYS_CONTEXT('USERENV', 'DB_NAME'),
                       SYS_CONTEXT('USERENV', 'INSTANCE_NAME'),
                       SYS_CONTEXT('USERENV', 'SERVICE_NAME'),
                       SYS_CONTEXT('USERENV', 'CON_NAME')
                FROM dual
                """
            )
            db_name, instance, service, con_name = cur.fetchone()
    return {
        "db_name": db_name,
        "instance": instance,
        "service": service,
        "container": con_name,
        "version": version,
        "status": "OPEN",
        "dsn": ORACLE_DSN,
        "user": ORACLE_USER,
    }


def close_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.close(force=True)
        _pool = None
