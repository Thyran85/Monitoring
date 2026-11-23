"""
Configuration centrale du backend.

Charge le fichier .env (jamais versionné) et expose les paramètres
Oracle, Telegram et les seuils de surveillance sous forme de
constantes. Aucun secret n'est écrit en dur dans le code.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR.parent / ".env")


def _env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


def _env_float(key: str, default: float) -> float:
    raw = _env(key, str(default))
    try:
        return float(raw)
    except ValueError:
        return default


def _env_int(key: str, default: int) -> int:
    raw = _env(key, str(default))
    try:
        return int(raw)
    except ValueError:
        return default


# --- Oracle Database ---------------------------------------------------------
ORACLE_USER = _env("ORACLE_USER", "MONITOR_APP")
ORACLE_PASSWORD = _env("ORACLE_PASSWORD")
ORACLE_DSN = _env("ORACLE_DSN", "localhost:1521/XEPDB1")

# Bootstrap (création de l'utilisateur applicatif uniquement)
SYS_USER = _env("SYS_USER", "SYS")
SYS_PASSWORD = _env("SYS_PASSWORD")

# --- Telegram ----------------------------------------------------------------
TELEGRAM_BOT_TOKEN = _env("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = _env("TELEGRAM_CHAT_ID")

# --- Surveillance ------------------------------------------------------------
COLLECT_INTERVAL_SECONDS = _env_float("COLLECT_INTERVAL_SECONDS", 10.0)
CONFIRM_SAMPLES = _env_int("CONFIRM_SAMPLES", 3)
DISK_PATH = _env("DISK_PATH", "/")

# Seuils en pourcentages : {ressource: {"warning": x, "critical": y}}
THRESHOLDS: dict[str, dict[str, float]] = {
    "CPU": {
        "warning": _env_float("THRESHOLD_CPU_WARNING", 75.0),
        "critical": _env_float("THRESHOLD_CPU_CRITICAL", 90.0),
    },
    "RAM": {
        "warning": _env_float("THRESHOLD_RAM_WARNING", 80.0),
        "critical": _env_float("THRESHOLD_RAM_CRITICAL", 95.0),
    },
    "DISK": {
        "warning": _env_float("THRESHOLD_DISK_WARNING", 80.0),
        "critical": _env_float("THRESHOLD_DISK_CRITICAL", 95.0),
    },
}
