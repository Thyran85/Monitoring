"""
Point d'entrée du backend.

Usage :
    python run.py                    # surveillance + API Flask (:5000)
    python run.py --once             # un seul cycle (test rapide)
    python run.py --status           # état de la base uniquement
    python run.py --no-db            # surveillance sans persistance
    python run.py --no-api           # surveillance seule, sans serveur
    python run.py --test-telegram    # teste la config Telegram (.env)

La boucle de surveillance tourne dans un thread séparé de l'API :
elle continue même si le serveur HTTP s'arrête, et réciproquement.
"""

from __future__ import annotations

import argparse
import atexit
import logging
import sys
import time

from alerting.telegram import TelegramNotifier
from api.app import create_app
from config import COLLECT_INTERVAL_SECONDS, THRESHOLDS
from engine.monitor import Monitor
from storage import db


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="System Monitoring - backend")
    parser.add_argument("--once", action="store_true",
                        help="exécute un seul cycle puis quitte")
    parser.add_argument("--status", action="store_true",
                        help="affiche l'état de la base puis quitte")
    parser.add_argument("--no-db", action="store_true",
                        help="désactive la persistance Oracle")
    parser.add_argument("--no-api", action="store_true",
                        help="ne démarre pas le serveur Flask")
    parser.add_argument("--test-telegram", action="store_true",
                        help="teste la configuration Telegram puis quitte")
    parser.add_argument("--host", default="127.0.0.1",
                        help="adresse d'écoute de l'API (défaut: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=5000,
                        help="port de l'API (défaut: 5000)")
    return parser


def _test_telegram() -> int:
    """Teste token + chat_id (étape 4) sans lancer la surveillance."""
    notifier = TelegramNotifier()
    print(f"Configuration : {notifier!r}")
    result = notifier.test()
    prefixe = "✅" if result.ok else "❌"
    print(f"{prefixe} {result.detail}")
    if result.error and not result.ok:
        print(f"   (code : {result.error})")
        print("   Renseigner TELEGRAM_BOT_TOKEN et TELEGRAM_CHAT_ID "
              "dans .env, puis relancer.")
    return 0 if result.ok else 1


def _check_db() -> bool:
    """Vérifie la base ; renvoie False si indisponible (non bloquant)."""
    print(f"Base cible : {db.ORACLE_DSN} (utilisateur : {db.ORACLE_USER})")
    try:
        info = db.health_check()
    except db.DatabaseUnavailable as exc:
        print(f"  ⚠ Oracle indisponible : {exc}")
        print("  ⚠ Surveillance poursuivie SANS persistance.")
        return False
    print("  Connexion OK")
    for key, value in info.items():
        print(f"    - {key} : {value}")
    return True


def _make_notify_fn(notifier: TelegramNotifier):
    """Adaptateur attendu par Monitor : callable(transition, alert_id).

    Sépare la logique de branchement du corps de main() pour la rendre
    testable. Une panne d'envoi est signalée mais n'interrompt rien.
    """
    def _notify(transition, alert_id):
        result = notifier.send_transition(transition)
        if result.ok:
            kind = "rétablissement" if transition.is_recovery else "alerte"
            print(f"  📨 Telegram ({kind} {transition.resource}) : envoyé")
        elif result.error != "not_configured":
            print(f"  ⚠ Telegram : {result.detail}")
        return result
    return _notify


def main() -> int:
    args = _build_parser().parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s : %(message)s",
        datefmt="%H:%M:%S",
    )

    if args.status:
        return 0 if _check_db() else 1

    if args.test_telegram:
        return _test_telegram()

    print("Seuils :")
    for resource, th in THRESHOLDS.items():
        print(f"  - {resource:<5} WARNING > {th['warning']:.0f}%  "
              f"CRITICAL > {th['critical']:.0f}%")

    db_ok = False if args.no_db else _check_db()

    # --- Notifications Telegram (étape 4) -----------------------------------
    notifier = TelegramNotifier()
    print(f"Telegram : {notifier!r}")
    if not notifier.is_configured:
        print("  ⚠ Non configuré — les alertes seront journalisées mais "
              "non envoyées (remplir .env puis: run.py --test-telegram)")

    monitor = Monitor(interval=COLLECT_INTERVAL_SECONDS,
                      notifier=_make_notify_fn(notifier),
                      persist=db_ok)

    if args.once:
        transitions = monitor.run_cycle()
        snap = monitor.last_snapshot
        print("\n--- Cycle unique ---")
        print(f"  CPU  : {snap['cpu']['percent']}% "
              f"(par cœur : {snap['cpu']['per_core']})")
        print(f"  RAM  : {snap['ram']['percent']}% "
              f"({snap['ram']['used_mb']} / {snap['ram']['total_mb']} Mo)")
        print(f"  DISK : {snap['disk']['percent']}% "
              f"({snap['disk']['used_gb']} / {snap['disk']['total_gb']} Go)")
        print(f"  États : { {k: v.value for k, v in monitor.detector.snapshot().items()} }")
        print(f"  Transitions : {len(transitions)}")
        print(f"  Persistance : {'OK' if db_ok else 'désactivée'}")
        db.close_pool()
        return 0

    print(f"\nDémarrage de la surveillance (intervalle "
          f"{COLLECT_INTERVAL_SECONDS:.0f}s)...")
    monitor.start()
    # Fermeture garantie du pool quelle que soit la fin de processus.
    atexit.register(db.close_pool)

    if args.no_api:
        print("API désactivée (--no-api). Ctrl+C pour arrêter.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nArrêt en cours...")
            monitor.stop()
            print("Arrêté proprement.")
        return 0

    app = create_app(monitor, notifier)
    print(f"API Flask : http://{args.host}:{args.port}/api/health")
    print("Ctrl+C pour arrêter.\n")
    try:
        # threaded=True : le serveur reste réactif pendant que le
        # moniteur tourne dans son propre thread.
        app.run(host=args.host, port=args.port, threaded=True,
                use_reloader=False)
    except KeyboardInterrupt:
        print("\nArrêt en cours...")
    finally:
        monitor.stop()
        print("Arrêté proprement.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
