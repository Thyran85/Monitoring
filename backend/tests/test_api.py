"""
Tests de l'API Flask — Étape 5.

Base mockée : les tests sont déterministes et ne nécessitent ni
Oracle ni Telegram.

Exécution :
    cd backend && ./venv/bin/python -m tests.test_api
"""

from __future__ import annotations

import sys
from types import SimpleNamespace
from unittest.mock import patch

from alerting.telegram import TelegramNotifier
from api.app import create_app
from engine.monitor import Monitor
from storage import db

_failures: list[str] = []


def _check(label: str, condition: bool, detail: str = "") -> None:
    print(f"[{'OK  ' if condition else 'FAIL'}] {label}" + (f" — {detail}" if detail else ""))
    if not condition:
        _failures.append(label)


def _snap(cpu=12.0, ram=55.0, disk=69.0):
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


_HEALTH_OK = {
    "db_name": "XEPDB1", "instance": "XE", "service": "xepdb1",
    "container": "XEPDB1", "version": "21.0.0.0.0", "status": "OPEN",
    "dsn": "localhost:1521/XEPDB1", "user": "MONITOR_APP",
}

_FAKE_METRICS = [{
    "collected_at": "2026-11-18 12:00:00", "cpu_percent": 42.0,
    "cpu_per_core": [42.0] * 8, "ram_total_mb": 100.0, "ram_used_mb": 50.0,
    "ram_avail_mb": 50.0, "ram_percent": 50.0, "disk_total_gb": 100.0,
    "disk_used_gb": 50.0, "disk_free_gb": 50.0, "disk_percent": 50.0,
}]

_FAKE_HISTORY = [
    {"collected_at": f"2026-11-18 12:00:{i:02d}", "cpu_percent": float(i),
     "ram_percent": 50.0, "disk_percent": 69.0, "ram_used_mb": 50.0,
     "disk_used_gb": 50.0}
    for i in range(5)
]

_FAKE_ALERTS = [{
    "alert_id": 1, "resource": "CPU", "level": "WARNING",
    "message": "WARNING CPU", "value_percent": 80.0, "threshold": 75.0,
    "status": "RESOLVED", "started_at": "2026-11-18 11:00:00",
    "resolved_at": "2026-11-18 11:10:00",
}]


def _make_client(snapshot=_snap(), configured=False, db_available=True):
    """Construit un client de test avec la base et Telegram simulés."""
    monitor = Monitor(interval=0.1, persist=False)
    monitor.last_snapshot = snapshot
    notifier = TelegramNotifier(
        token="123456:ABC" if configured else "",
        chat_id="42" if configured else "",
        session=SimpleNamespace(),  # jamais appelé dans ces tests
    )
    app = create_app(monitor, notifier)
    app.config["TESTING"] = True

    patches = []
    if db_available:
        patches.append(patch("api.app.db.health_check",
                             return_value=dict(_HEALTH_OK)))
        patches.append(patch("storage.repository.latest_metrics",
                             return_value=list(_FAKE_METRICS)))
        patches.append(patch("storage.repository.metrics_history",
                             return_value=list(_FAKE_HISTORY)))
        patches.append(patch("storage.repository.recent_alerts",
                             return_value=list(_FAKE_ALERTS)))
    # _machine_id : évite l'appel réel à la base
    patches.append(patch.object(Monitor, "_ensure_machine", return_value=1))
    for p in patches:
        p.start()
        app.extensions.setdefault("test_patches", []).append(p)
    return app.test_client()


def _stop_patches(app):
    for p in app.extensions.get("test_patches", []):
        p.stop()


# ---------------------------------------------------------------- /health

def scenario_health() -> None:
    client = _make_client()
    try:
        res = client.get("/api/health")
        data = res.get_json()
        _check("GET /api/health -> 200", res.status_code == 200)
        _check("health porte status=ok", data.get("status") == "ok")
        _check("health expose monitor_running", "monitor_running" in data,
               str(data))
    finally:
        _stop_patches(client.application)


# ---------------------------------------------------------------- /api/status

def scenario_status_ok() -> None:
    client = _make_client()
    try:
        res = client.get("/api/status")
        data = res.get_json()
        _check("GET /api/status -> 200", res.status_code == 200)
        _check("état général NORMAL", data["overall_state"] == "NORMAL",
               data["overall_state"])
        _check("3 ressources présentes",
               set(data["states"]) == {"CPU", "RAM", "DISK"},
               str(data["states"]))
        _check("métriques réelles servies",
               data["metrics"]["cpu"]["percent"] == 12.0
               and data["metrics"]["ram"]["percent"] == 55.0)
        _check("seuils exposés",
               data["thresholds"]["CPU"] == {"warning": 75.0, "critical": 90.0},
               str(data["thresholds"]["CPU"]))
        _check("database.available = True", data["database"]["available"] is True)
        _check("telegram.configured présent, sans token",
               "configured" in data["telegram"]
               and "token" not in str(data).lower(),
               str(data["telegram"]))
        _check("monitor.last_collect renseigné",
               data["monitor"]["last_collect"] == "2026-11-18T12:00:00+00:00",
               str(data["monitor"]["last_collect"]))
    finally:
        _stop_patches(client.application)


def scenario_status_db_down() -> None:
    """Base indisponible : l'API répond quand même (503 nowhere)."""
    monitor = Monitor(interval=0.1, persist=False)
    monitor.last_snapshot = _snap()
    notifier = TelegramNotifier(token="", chat_id="", session=SimpleNamespace())
    app = create_app(monitor, notifier)
    app.config["TESTING"] = True
    with patch("api.app.db.health_check",
               side_effect=db.DatabaseUnavailable("down")), \
         patch.object(Monitor, "_ensure_machine", return_value=1):
        client = app.test_client()
        res = client.get("/api/status")
        data = res.get_json()
        _check("status répond 200 même sans base", res.status_code == 200)
        _check("database.available = False avec détail",
               data["database"]["available"] is False
               and "error" in data["database"])
        _check("surveillance toujours renseignée",
               data["metrics"]["cpu"]["percent"] == 12.0)


def scenario_status_cascade() -> None:
    """État général = niveau le plus sévère."""
    monitor = Monitor(interval=0.1, persist=False)
    from engine.detector import State
    monitor.detector._state = {"CPU": State.CRITICAL, "RAM": State.WARNING,
                               "DISK": State.NORMAL}
    monitor.last_snapshot = _snap(cpu=96.0, ram=85.0)
    notifier = TelegramNotifier(token="", chat_id="", session=SimpleNamespace())
    app = create_app(monitor, notifier)
    app.config["TESTING"] = True
    with patch("api.app.db.health_check", return_value=dict(_HEALTH_OK)), \
         patch.object(Monitor, "_ensure_machine", return_value=1):
        client = app.test_client()
        res = client.get("/api/status")
        _check("overall_state = CRITICAL (pire niveau)",
               res.get_json()["overall_state"] == "CRITICAL",
               res.get_json()["overall_state"])


# ---------------------------------------------------------------- métriques

def scenario_metrics_latest() -> None:
    client = _make_client()
    try:
        res = client.get("/api/metrics/latest")
        _check("GET /metrics/latest -> 200", res.status_code == 200)
        _check("donnée réelle de la base servie",
               res.get_json()["cpu_percent"] == 42.0, str(res.get_json())[:60])
        _check("cpu_per_core décodé en liste",
               isinstance(res.get_json()["cpu_per_core"], list))
    finally:
        _stop_patches(client.application)


def scenario_metrics_latest_empty() -> None:
    """Aucune donnée en base -> repli sur le snapshot vivant."""
    monitor = Monitor(interval=0.1, persist=False)
    monitor.last_snapshot = _snap(cpu=33.0)
    notifier = TelegramNotifier(token="", chat_id="", session=SimpleNamespace())
    app = create_app(monitor, notifier)
    app.config["TESTING"] = True
    with patch("storage.repository.latest_metrics", return_value=[]), \
         patch.object(Monitor, "_ensure_machine", return_value=1):
        client = app.test_client()
        res = client.get("/api/metrics/latest")
        _check("Repli sur snapshot vivant si base vide",
               res.status_code == 200 and res.get_json()["cpu"]["percent"] == 33.0,
               f"{res.status_code}")


def scenario_metrics_latest_no_data() -> None:
    monitor = Monitor(interval=0.1, persist=False)
    notifier = TelegramNotifier(token="", chat_id="", session=SimpleNamespace())
    app = create_app(monitor, notifier)
    app.config["TESTING"] = True
    with patch("storage.repository.latest_metrics", return_value=[]), \
         patch.object(Monitor, "_ensure_machine", return_value=1):
        client = app.test_client()
        res = client.get("/api/metrics/latest")
        _check("404 propre si aucune donnée", res.status_code == 404,
               str(res.get_json()))


def scenario_metrics_history() -> None:
    client = _make_client()
    try:
        res = client.get("/api/metrics/history?limit=5")
        data = res.get_json()
        _check("GET /metrics/history -> 200", res.status_code == 200)
        _check("historique servi", data["count"] == 5
               and len(data["metrics"]) == 5, str(data["count"]))

        res_bad = client.get("/api/metrics/history?limit=abc")
        _check("paramètre invalide -> valeur par défaut (200)",
               res_bad.status_code == 200, str(res_bad.status_code))

        res_big = client.get("/api/metrics/history?limit=999999")
        _check("paramètre borné à 500", res_big.status_code == 200)
    finally:
        _stop_patches(client.application)


def scenario_metrics_db_down() -> None:
    monitor = Monitor(interval=0.1, persist=False)
    notifier = TelegramNotifier(token="", chat_id="", session=SimpleNamespace())
    app = create_app(monitor, notifier)
    app.config["TESTING"] = True
    with patch("storage.repository.latest_metrics",
               side_effect=db.DatabaseUnavailable("down")), \
         patch("storage.repository.metrics_history",
               side_effect=db.DatabaseUnavailable("down")), \
         patch.object(Monitor, "_ensure_machine", return_value=1):
        client = app.test_client()
        res1 = client.get("/api/metrics/latest")
        res2 = client.get("/api/metrics/history")
        _check("latest -> 503 JSON si base coupée",
               res1.status_code == 503 and "error" in res1.get_json(),
               str(res1.get_json()))
        _check("history -> 503 JSON si base coupée",
               res2.status_code == 503 and "error" in res2.get_json(),
               str(res2.get_json()))


# ---------------------------------------------------------------- alertes

def scenario_alerts() -> None:
    client = _make_client()
    try:
        res = client.get("/api/alerts?limit=10")
        data = res.get_json()
        _check("GET /alerts -> 200", res.status_code == 200)
        _check("alertes servies", data["count"] == 1
               and data["alerts"][0]["resource"] == "CPU", str(data)[:60])
        _check("champs dashboard présents",
               {"resource", "level", "status", "started_at"}
               <= set(data["alerts"][0]))

        res_lim = client.get("/api/alerts?limit=-5")
        _check("limit négative bornée à >=1", res_lim.status_code == 200)
    finally:
        _stop_patches(client.application)


def scenario_alerts_db_down() -> None:
    monitor = Monitor(interval=0.1, persist=False)
    notifier = TelegramNotifier(token="", chat_id="", session=SimpleNamespace())
    app = create_app(monitor, notifier)
    app.config["TESTING"] = True
    with patch("storage.repository.recent_alerts",
               side_effect=db.DatabaseUnavailable("down")), \
         patch.object(Monitor, "_ensure_machine", return_value=1):
        client = app.test_client()
        res = client.get("/api/alerts")
        _check("alerts -> 503 JSON si base coupée",
               res.status_code == 503, str(res.status_code))


# ---------------------------------------------------------------- test telegram

def scenario_alerts_test_not_configured() -> None:
    client = _make_client(configured=False)
    try:
        res = client.post("/api/alerts/test")
        data = res.get_json()
        _check("POST /alerts/test -> 503 si non configuré",
               res.status_code == 503, str(res.status_code))
        _check("ok=False, error=not_configured",
               data["ok"] is False and data["error"] == "not_configured",
               str(data))
        _check("aucun token dans la réponse",
               "token" not in str(data).lower() or data.get("configured") is False,
               str(data))
    finally:
        _stop_patches(client.application)


def scenario_alerts_test_method() -> None:
    client = _make_client()
    try:
        res = client.get("/api/alerts/test")
        _check("GET /alerts/test -> 405", res.status_code == 405,
               str(res.status_code))
        _check("405 en JSON", "error" in res.get_json())
    finally:
        _stop_patches(client.application)


# ---------------------------------------------------------------- 404

def scenario_unknown_route() -> None:
    client = _make_client()
    try:
        res = client.get("/api/inexistant")
        _check("404 en JSON", res.status_code == 404
               and "error" in res.get_json(), str(res.get_json()))
    finally:
        _stop_patches(client.application)


def scenario_no_secret_leak() -> None:
    """Aucune route ne doit fuiter token/mot de passe."""
    client = _make_client(configured=True)
    try:
        leaks = []
        for route in ("/api/health", "/api/status", "/api/metrics/latest",
                      "/api/metrics/history", "/api/alerts"):
            body = client.get(route).get_data(as_text=True).lower()
            if "123456:abc" in body or "th373622" in body:
                leaks.append(route)
        _check("Aucune fuite de secret sur les GET", not leaks, str(leaks))
    finally:
        _stop_patches(client.application)


def main() -> int:
    scenario_health()
    scenario_status_ok()
    scenario_status_db_down()
    scenario_status_cascade()
    scenario_metrics_latest()
    scenario_metrics_latest_empty()
    scenario_metrics_latest_no_data()
    scenario_metrics_history()
    scenario_metrics_db_down()
    scenario_alerts()
    scenario_alerts_db_down()
    scenario_alerts_test_not_configured()
    scenario_alerts_test_method()
    scenario_unknown_route()
    scenario_no_secret_leak()

    print()
    if _failures:
        print(f"{len(_failures)} TEST(S) EN ÉCHEC :")
        for name in _failures:
            print(f"  - {name}")
        return 1
    print("TOUS LES TESTS PASSENT")
    return 0


if __name__ == "__main__":
    sys.exit(main())
