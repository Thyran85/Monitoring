"""
Moteur de détection d'anomalies — états NORMAL / WARNING / CRITICAL.

Principes (MVP) :
  - Seuils par ressource (WARNING / CRITICAL), configurables via .env.
  - Fenêtre glissante : un état anormal n'est CONFIRMÉ qu'après
    `confirm_samples` mesures consécutives au niveau suffisant.
    Un pic isolé ne déclenche donc aucune alerte.
  - Anti-dédoublonnage : une alerte n'est émise qu'à chaque CHANGEMENT
    d'état confirmé ; rester en WARNING ne renvoie rien.
  - Détection des transitions, y compris le rétablissement (retour à
    NORMAL), qui devra déclencher une notification (étape 4).

Module pur : aucune persistance, aucun envoi réseau — le moniteur
(engine/monitor.py) consomme les transitions renvoyées par update().
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class State(str, Enum):
    """État confirmé d'une ressource."""

    NORMAL = "NORMAL"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"

    @property
    def severity(self) -> int:
        return {"NORMAL": 0, "WARNING": 1, "CRITICAL": 2}[self.value]


@dataclass(frozen=True)
class Transition:
    """Changement d'état confirmé sur une ressource."""

    resource: str
    previous: State
    current: State
    value: float
    threshold: float  # seuil correspondant à l'état atteint

    @property
    def is_recovery(self) -> bool:
        """Vrai lorsque la situation redevient normale."""
        return self.current is State.NORMAL

    @property
    def is_escalation(self) -> bool:
        """Vrai lors d'une montée en sévérité WARNING -> CRITICAL."""
        return self.current.severity > self.previous.severity


class Detector:
    """Détecteur multi-ressources avec fenêtre glissante.

    Parameters
    ----------
    thresholds : {"CPU": {"warning": 75, "critical": 90}, ...}
    confirm_samples : nombre de mesures consécutives requises (>= 1).
    """

    def __init__(self, thresholds: dict[str, dict[str, float]],
                 confirm_samples: int = 3) -> None:
        if confirm_samples < 1:
            raise ValueError("confirm_samples doit être >= 1")
        self.thresholds = thresholds
        self.confirm_samples = confirm_samples
        self._history: dict[str, list[State]] = {}
        # Les états sont pré-initialisés à NORMAL pour toutes les
        # ressources configurées : le dashboard a toujours les 3
        # entrées, même avant la première mesure.
        self._state: dict[str, State] = {name: State.NORMAL
                                         for name in thresholds}

    # --- API publique --------------------------------------------------------

    def update(self, resource: str, value: float) -> Transition | None:
        """Informe le détecteur d'une nouvelle mesure.

        Retourne une Transition si l'état CONFIRMÉ change, sinon None.
        """
        thresholds = self.thresholds.get(resource)
        if thresholds is None:
            raise KeyError(f"Ressource inconnue : {resource}")

        level = self._level_for(value, thresholds)
        history = self._history.setdefault(resource, [])
        history.append(level)
        if len(history) > self.confirm_samples:
            del history[: len(history) - self.confirm_samples]

        previous = self._state.get(resource, State.NORMAL)
        confirmed = self._confirm(history, previous)

        self._state[resource] = confirmed
        if confirmed is previous:
            return None

        # Seuil associé à l'état atteint ; pour un retour à NORMAL, on
        # reporte le seuil WARNING (celui dont on sort).
        if confirmed is State.NORMAL:
            threshold = thresholds["warning"]
        else:
            threshold = thresholds[confirmed.value.lower()]

        return Transition(
            resource=resource,
            previous=previous,
            current=confirmed,
            value=round(value, 2),
            threshold=threshold,
        )

    def state_of(self, resource: str) -> State:
        """État actuel confirmé d'une ressource (NORMAL par défaut)."""
        return self._state.get(resource, State.NORMAL)

    def snapshot(self) -> dict[str, State]:
        """Tous les états confirmés (pour l'API / le dashboard)."""
        return dict(self._state)

    # --- Logique interne -----------------------------------------------------

    @staticmethod
    def _level_for(value: float, thresholds: dict[str, float]) -> State:
        """Niveau IMMÉDIAT d'une valeur (sans fenêtre)."""
        if value >= thresholds["critical"]:
            return State.CRITICAL
        if value >= thresholds["warning"]:
            return State.WARNING
        return State.NORMAL

    def _confirm(self, history: list[State], previous: State) -> State:
        """ÉTAT CONFIRMÉ à partir de la fenêtre glissante.

        Règles (symétriques pour l'entrée en anomalie et le
        rétablissement, afin d'éviter les allers-retours) :
          - fenêtre incomplète -> jamais confirmé (reste NORMAL) ;
          - fenêtre unanime CRITICAL -> CRITICAL ;
          - fenêtre entièrement >= WARNING -> WARNING ;
          - fenêtre entièrement NORMAL -> NORMAL (rétablissement confirmé) ;
          - fenêtre MIXTE -> l'état précédent est conservé : une mesure
            isolée dans l'autre sens ne change pas l'état confirmé.
        """
        if len(history) < self.confirm_samples:
            return State.NORMAL
        if all(s is State.CRITICAL for s in history):
            return State.CRITICAL
        if all(s.severity >= State.WARNING.severity for s in history):
            return State.WARNING
        if all(s is State.NORMAL for s in history):
            return State.NORMAL
        # Fenêtre mixte : aucun changement d'état confirmé.
        return previous
