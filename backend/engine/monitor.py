"""
Boucle de surveillance autonome — indépendante du frontend.

Responsabilités :
  1. collecter les métriques (collector.metrics) ;
  2. faire passer chaque métrique au détecteur (engine.detector) ;
  3. persister les métriques et les alertes (storage.repository) ;
  4. remettre les transitions dans une file pour les notifications
     (l'envoi Telegram réel sera branché à l'étape 4).

La boucle tourne dans un thread séparé : le dashboard n'est qu'un
consommateur de l'API, jamais un pilote de la surveillance.

Résilience : si Oracle est indisponible (conteneur arrêté), la boucle
journalise l'erreur et continue — elle retentera au cycle suivant.
"""

from __future__ import annotations

import logging
import queue
import threading
import time
from datetime import datetime, timezone

from collector import metrics as collector
from config import (
    COLLECT_INTERVAL_SECONDS,
    CONFIRM_SAMPLES,
    DISK_PATH,
    THRESHOLDS,
)
from engine.detector import Detector, Transition
from storage import db, repository

log = logging.getLogger("monitor")


class Monitor:
    """Cycle de surveillance : collecte -> détection -> persistance.

    Parameters
    ----------
    interval : durée entre deux cycles (secondes).
    notifier : callable(transition, alert_id) optionnel, appelé pour
        chaque transition (branché par l'étape 4 pour Telegram). Son
        attribut `ok` permet de marquer l'alerte comme notifiée.
    persist : si False, aucune écriture Oracle (mode --no-db) ; la
        collecte et la détection restent actives.
    """

    def __init__(
        self,
        interval: float = COLLECT_INTERVAL_SECONDS,
        confirm_samples: int = CONFIRM_SAMPLES,
        notifier=None,
        persist: bool = True,
    ) -> None:
        self.interval = interval
        self.detector = Detector(THRESHOLDS, confirm_samples)
        self.notifier = notifier
        self.persist = persist
        self.machine_id: int | None = None
        self.transitions: "queue.Queue[Transition]" = queue.Queue()
        self.last_snapshot: dict | None = None
        self.cycles = 0
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    # --- Un cycle complet ----------------------------------------------------

    def run_cycle(self, snapshot: dict | None = None) -> list[Transition]:
        """Un cycle : collecte, détection, persistance.

        `snapshot` permet d'injecter des valeurs (tests) ; par défaut
        les métriques sont collectées réellement via psutil.
        Retourne les transitions confirmées de ce cycle.
        """
        if snapshot is None:
            snapshot = collector.collect_all(DISK_PATH)
        self.last_snapshot = snapshot
        self.cycles += 1

        try:
            self._persist(snapshot)
        except db.DatabaseUnavailable as exc:
            # Base arrêtée : on garde les états en mémoire et on
            # retentera au cycle suivant. Aucune perte de surveillance.
            log.warning("Oracle indisponible, cycle poursuivi sans "
                        "persistance : %s", exc)

        transitions: list[Transition] = []
        for resource, value in self._iter_values(snapshot):
            transition = self.detector.update(resource, value)
            if transition is None:
                continue
            transitions.append(transition)
            self.transitions.put(transition)
            log.info(
                "Transition %s : %s -> %s (%.2f%%)",
                transition.resource,
                transition.previous.value,
                transition.current.value,
                transition.value,
            )
            alert_id = self._persist_alert(transition)
            if self.notifier is not None:
                self._notify(transition, alert_id)
        return transitions

    # --- Boucle (thread) -----------------------------------------------------

    def start(self) -> None:
        """Démarre la boucle en arrière-plan (une seule fois)."""
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._loop, name="monitor-loop", daemon=True
        )
        self._thread.start()
        log.info("Boucle de surveillance démarrée (intervalle = %.0fs)",
                 self.interval)

    def stop(self, timeout: float = 5.0) -> None:
        """Arrête proprement la boucle."""
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=timeout)

    @property
    def running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def _loop(self) -> None:
        while not self._stop.is_set():
            started = time.monotonic()
            try:
                self.run_cycle()
            except Exception:  # la boucle ne doit jamais mourir
                log.exception("Cycle en erreur")
            elapsed = time.monotonic() - started
            self._stop.wait(max(0.0, self.interval - elapsed))

    # --- Internes ------------------------------------------------------------

    @staticmethod
    def _iter_values(snapshot: dict):
        """Extrait les 3 métriques surveillées du snapshot."""
        yield "CPU", snapshot["cpu"]["percent"]
        yield "RAM", snapshot["ram"]["percent"]
        yield "DISK", snapshot["disk"]["percent"]

    def _ensure_machine(self) -> int:
        if self.machine_id is None:
            self.machine_id = repository.register_machine(
                collector.collect_machine()
            )
            log.info("Machine enregistrée (id=%s)", self.machine_id)
        return self.machine_id

    def _persist(self, snapshot: dict) -> None:
        if not self.persist:
            return
        machine_id = self._ensure_machine()
        repository.insert_metric(machine_id, snapshot)

    def _persist_alert(self, transition: Transition) -> int | None:
        """Persiste la transition ; renvoie l'alert_id ou None si la
        base est indisponible (la notification partira quand même)."""
        if not self.persist:
            return None
        try:
            machine_id = self._ensure_machine()
            return repository.insert_alert(machine_id, transition)
        except db.DatabaseUnavailable as exc:
            log.warning("Alerte non persistée (Oracle indisponible) : %s", exc)
            return None

    def _notify(self, transition: Transition, alert_id: int | None) -> None:
        """Notifie la transition ; marque `notified` si l'envoi réussit.

        Le notifier renvoie un objet avec un attribut `ok` (SendResult).
        Toute exception est absorbée : une panne Telegram ne casse
        jamais la boucle de surveillance.
        """
        try:
            result = self.notifier(transition, alert_id)
        except Exception:  # noqa: BLE001 — panne de notification
            log.exception("Échec de la notification pour %s",
                          transition.resource)
            return

        ok = getattr(result, "ok", None)
        if ok and alert_id is not None:
            try:
                repository.mark_notified(alert_id)
            except db.DatabaseUnavailable:
                log.warning("Impossible de marquer notified=%s (base "
                            "indisponible)", alert_id)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
