"""
Collecte des métriques système via psutil.

Module pur : aucune persistance, aucune notification, aucune
dépendance au frontend. Le moteur de surveillance (étape 3) consomme
les dictionnaires renvoyés par `collect_all()`.

Unités conventionnelles :
  - pourcentages : float 0-100
  - mémoire : mégaoctets (Mo)
  - disque : gigaoctets (Go), arrondi à 2 décimales
"""

from __future__ import annotations

import json
import platform
import socket
import time
from datetime import datetime, timezone

import psutil

from config import DISK_PATH

# psutil.cpu_percent(interval=None) renvoie 0.0 tant qu'aucun échantillon
# préalable n'existe dans le processus : on force un premier échantillonnage
# réel (une seule fois) pour éviter un faux 0 % au démarrage.
_cpu_warmup_done = False


def collect_cpu() -> dict:
    """CPU global (%) et utilisation de chaque cœur (%).

    Une seule mesure est effectuée (par cœur, sur la fenêtre depuis le
    dernier appel) ; le pourcentage global est la moyenne des cœurs,
    ce qui garantit une fenêtre identique pour les deux valeurs.

    Le premier appel du processus effectue un amorçage avec une seconde
    d'échantillonnage pour éviter un faux 0 % au démarrage.
    """
    global _cpu_warmup_done
    if not _cpu_warmup_done:
        # Amorçage des deux bases de comparaison (global et par cœur)
        psutil.cpu_percent(interval=None)
        psutil.cpu_percent(percpu=True)
        time.sleep(1.0)
        _cpu_warmup_done = True

    per_core = [round(value, 2) for value in psutil.cpu_percent(percpu=True)]
    global_percent = round(sum(per_core) / len(per_core), 2) if per_core else 0.0
    return {
        "percent": global_percent,
        "per_core": per_core,
        "core_count": psutil.cpu_count(logical=True),
    }


def collect_ram() -> dict:
    """Mémoire vive : totale, utilisée, disponible (Mo) et pourcentage."""
    vm = psutil.virtual_memory()
    to_mb = lambda n: round(n / (1024 * 1024), 2)
    return {
        "total_mb": to_mb(vm.total),
        "used_mb": to_mb(vm.used),
        "available_mb": to_mb(vm.available),
        "percent": round(float(vm.percent), 2),
    }


def collect_disk(path: str = DISK_PATH) -> dict:
    """Espace disque du point de montage `path` : totale, utilisé, libre (Go)."""
    usage = psutil.disk_usage(path)
    to_gb = lambda n: round(n / (1024 ** 3), 2)
    return {
        "path": path,
        "total_gb": to_gb(usage.total),
        "used_gb": to_gb(usage.used),
        "free_gb": to_gb(usage.free),
        "percent": round(float(usage.percent), 2),
    }


def collect_machine() -> dict:
    """Informations statiques de la machine (enregistrées une fois)."""
    vm = psutil.virtual_memory()
    return {
        "hostname": socket.gethostname(),
        "ip_address": _local_ip(),
        "os_info": f"{platform.system()} {platform.release()} ({platform.machine()})",
        "cpu_cores": psutil.cpu_count(logical=True),
        "total_ram_mb": round(vm.total / (1024 * 1024), 2),
    }


def collect_all(path: str = DISK_PATH) -> dict:
    """Snapshot complet des métriques, horodaté en UTC (ISO 8601)."""
    return {
        "collected_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "cpu": collect_cpu(),
        "ram": collect_ram(),
        "disk": collect_disk(path),
    }


def cpu_cores_json(cpu: dict) -> str:
    """Sérialise l'utilisation par cœur pour la colonne CLOB (Oracle)."""
    return json.dumps(cpu["per_core"])


def _local_ip() -> str:
    """Adresse IP locale (meilleur effort, sans paquet réseau externe)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))
            return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
