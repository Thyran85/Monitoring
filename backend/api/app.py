"""
API Flask du System Monitoring — couche lecture pour le dashboard.

Endpoints :
    GET  /api/health              petit battement de cœur (sans base)
    GET  /api/status              état général + états des 3 ressources
    GET  /api/metrics/latest      dernière métrique persistée
    GET  /api/metrics/history     historique (courbes Recharts)
    GET  /api/alerts              dernières alertes
    POST /api/alerts/test         test de la configuration Telegram

Principes :
  - AUCUN secret exposé (pas de token, pas de mot de passe) : on ne
    renvoie que des booléens du type "telegram.configured" ;
  - réponses JSON systématiques, y compris en cas d'erreur ;
  - base indisponible -> HTTP 503 JSON (le frontend peut afficher
    "Oracle hors ligne" sans casser) ;
  - le monitor tourne dans son propre thread : l'API est un simple
    consommateur de son état en mémoire et de la base.
"""

from __future__ import annotations

from flask import Flask, Response, jsonify, request

from alerting.telegram import TelegramNotifier
from config import (
    COLLECT_INTERVAL_SECONDS,
    CONFIRM_SAMPLES,
    DISK_PATH,
    THRESHOLDS,
)
from engine.monitor import Monitor
from storage import db, repository

MAX_HISTORY = 500
MAX_ALERTS = 100


def _json(data, status: int = 200) -> tuple[Response, int]:
    return jsonify(data), status


def _clamp(value: str | None, default: int, minimum: int, maximum: int) -> int:
    """Convertit un paramètre query en entier contraint."""
    try:
        parsed = int(value) if value is not None else default
    except (TypeError, ValueError):
        return default
    return max(minimum, min(parsed, maximum))


def create_app(monitor: Monitor, notifier: TelegramNotifier) -> Flask:
    """Fabrique l'application Flask.

    `monitor` : instance partagée avec la boucle de surveillance
        (peut être non démarrée dans les tests).
    `notifier` : client Telegram utilisé par /api/alerts/test.
    """
    app = Flask(__name__)
    app.config["JSON_SORT_KEYS"] = False

    # ------------------------------------------------------------------
    # États & monitoring
    # ------------------------------------------------------------------

    @app.get("/api/health")
    def health():
        return _json({
            "status": "ok",
            "monitor_running": monitor.running,
            "cycles": monitor.cycles,
        })

    @app.get("/api/status")
    def status():
        """État général du système + état de chaque ressource."""
        snapshot = monitor.last_snapshot
        states = {name: state.value
                  for name, state in monitor.detector.snapshot().items()}

        # État général = niveau le plus sévère parmi les ressources
        severity = {"NORMAL": 0, "WARNING": 1, "CRITICAL": 2}
        overall = max(states.values(), key=lambda s: severity[s]) \
            if states else "NORMAL"

        payload = {
            "overall_state": overall,
            "states": states,
            "thresholds": THRESHOLDS,
            "monitor": {
                "running": monitor.running,
                "interval_seconds": COLLECT_INTERVAL_SECONDS,
                "confirm_samples": CONFIRM_SAMPLES,
                "cycles": monitor.cycles,
                "last_collect": snapshot["collected_at"] if snapshot else None,
                "disk_path": DISK_PATH,
            },
            "telegram": {"configured": notifier.is_configured},
            "database": {"available": False},
        }

        # Valeurs courantes : privilégiées en mémoire (vivantes),
        # retomber sur la base si le moniteur n'a pas encore tourné.
        if snapshot:
            payload["metrics"] = {
                "cpu": snapshot["cpu"],
                "ram": snapshot["ram"],
                "disk": snapshot["disk"],
            }
        else:
            payload["metrics"] = None

        try:
            payload["database"] = {"available": True, **db.health_check()}
        except db.DatabaseUnavailable as exc:
            payload["database"] = {"available": False, "error": str(exc)[:200]}

        return _json(payload)

    # ------------------------------------------------------------------
    # Métriques
    # ------------------------------------------------------------------

    @app.get("/api/metrics/latest")
    def metrics_latest():
        try:
            machine_id = _machine_id()
            rows = repository.latest_metrics(machine_id, limit=1)
        except db.DatabaseUnavailable as exc:
            return _json({"error": "base indisponible", "detail": str(exc)[:200]},
                         503)
        if not rows:
            # Pas encore de donnée persistée : on sert le snapshot vivant.
            if monitor.last_snapshot:
                return _json(monitor.last_snapshot)
            return _json({"error": "aucune métrique"}, 404)
        return _json(rows[0])

    @app.get("/api/metrics/history")
    def metrics_history():
        """Historique pour les courbes (Recharts). ?limit= paramètre."""
        limit = _clamp(request.args.get("limit"), 60, 1, MAX_HISTORY)
        try:
            machine_id = _machine_id()
            rows = repository.metrics_history(machine_id, limit=limit)
        except db.DatabaseUnavailable as exc:
            return _json({"error": "base indisponible", "detail": str(exc)[:200]},
                         503)
        return _json({"count": len(rows), "metrics": rows})

    # ------------------------------------------------------------------
    # Alertes
    # ------------------------------------------------------------------

    @app.get("/api/alerts")
    def alerts():
        limit = _clamp(request.args.get("limit"), 20, 1, MAX_ALERTS)
        try:
            machine_id = _machine_id()
            rows = repository.recent_alerts(machine_id, limit=limit)
        except db.DatabaseUnavailable as exc:
            return _json({"error": "base indisponible", "detail": str(exc)[:200]},
                         503)
        return _json({"count": len(rows), "alerts": rows})

    @app.post("/api/alerts/test")
    def alerts_test():
        """Teste la config Telegram (jamais de token en retour)."""
        result = notifier.test()
        return _json({
            "ok": result.ok,
            "detail": result.detail,
            "error": result.error,
            "configured": notifier.is_configured,
        }, 200 if result.ok else 503)

    # ------------------------------------------------------------------
    # Gestion d'erreurs
    # ------------------------------------------------------------------

    @app.errorhandler(db.DatabaseUnavailable)
    def _handle_db_error(exc) -> tuple[Response, int]:
        return _json({"error": "base indisponible", "detail": str(exc)[:200]}, 503)

    @app.errorhandler(404)
    def _handle_404(_exc) -> tuple[Response, int]:
        return _json({"error": "route inconnue"}, 404)

    @app.errorhandler(405)
    def _handle_405(_exc) -> tuple[Response, int]:
        return _json({"error": "méthode non autorisée"}, 405)

    @app.errorhandler(500)
    def _handle_500(_exc) -> tuple[Response, int]:
        return _json({"error": "erreur interne"}, 500)

    def _machine_id() -> int:
        """Id de la machine locale (mémoire, sinon lecture en base)."""
        if monitor.machine_id is not None:
            return monitor.machine_id
        return monitor._ensure_machine()

    return app
