"""
Tests unitaires du moteur de détection — Étape 3.

Exécution :
    cd backend && ./venv/bin/python -m tests.test_detector
"""

from __future__ import annotations

import sys

from config import THRESHOLDS
from engine.detector import Detector, State

N = 3  # CONFIRM_SAMPLES par défaut

_failures: list[str] = []


def _check(label: str, condition: bool, detail: str = "") -> None:
    print(f"[{'OK  ' if condition else 'FAIL'}] {label}" + (f" — {detail}" if detail else ""))
    if not condition:
        _failures.append(label)


def _feed(det: Detector, resource: str, values: list[float]) -> list:
    """Nourrit le détecteur et collecte les transitions émises."""
    return [t for v in values if (t := det.update(resource, v))]


def scenario_pic_isole() -> None:
    """Un pic court (< N mesures) ne déclenche AUCUNE alerte."""
    det = Detector(THRESHOLDS, N)
    # 2 mesures à 95 % puis retour normal : jamais confirmé
    tr = _feed(det, "CPU", [95.0, 96.0, 10.0])
    _check("Pic isolé ignoré (aucune transition)", not tr,
           f"{len(tr)} transition(s)")
    _check("État toujours NORMAL", det.state_of("CPU") is State.NORMAL)


def scenario_confirmation_warning() -> None:
    """3 mesures consécutives >= 75 % -> confirmation WARNING."""
    det = Detector(THRESHOLDS, N)
    tr = _feed(det, "CPU", [80.0, 80.0, 80.0])
    _check("WARNING confirmé après 3 mesures",
           len(tr) == 1 and tr[0].current is State.WARNING,
           f"{len(tr)} transition(s)")
    _check("Valeur et seuil portés par la transition",
           tr and tr[0].value == 80.0 and tr[0].threshold == 75.0)


def scenario_confirmation_critical() -> None:
    """3 mesures consécutives >= 90 % -> confirmation CRITICAL direct."""
    det = Detector(THRESHOLDS, N)
    tr = _feed(det, "CPU", [95.0, 96.0, 97.0])
    _check("CRITICAL confirmé après 3 mesures",
           len(tr) == 1 and tr[0].current is State.CRITICAL
           and tr[0].threshold == 90.0,
           f"{len(tr)} transition(s)")


def scenario_dedoublonnage() -> None:
    """Rester en WARNING ne renvoie AUCUNE nouvelle alerte."""
    det = Detector(THRESHOLDS, N)
    _feed(det, "CPU", [80.0, 80.0, 80.0])   # -> WARNING (1 transition)
    tr = _feed(det, "CPU", [80.0, 85.0, 82.0, 88.0, 90.0, 81.0] * 3)
    _check("Aucun renvoi en boucle en état stable", not tr,
           f"{len(tr)} transition(s) supplémentaire(s)")
    _check("État conservé WARNING", det.state_of("CPU") is State.WARNING)


def scenario_escalade() -> None:
    """WARNING -> CRITICAL, avec confirmation du palier critique."""
    det = Detector(THRESHOLDS, N)
    _feed(det, "CPU", [80.0] * 3)             # -> WARNING
    tr = _feed(det, "CPU", [95.0] * 3)         # 3 CRITICAL consécutifs
    _check("Escalade WARNING -> CRITICAL",
           len(tr) == 1 and tr[0].previous is State.WARNING
           and tr[0].current is State.CRITICAL and tr[0].is_escalation,
           f"{len(tr)} transition(s)")


def scenario_retablissement() -> None:
    """Retour à NORMAL confirmé après N mesures saines."""
    det = Detector(THRESHOLDS, N)
    _feed(det, "RAM", [96.0] * 3)              # -> CRITICAL
    # 1 mesure saine isolée : fenêtre mixte -> pas de rétablissement
    tr = _feed(det, "RAM", [50.0])
    _check("Creux isolé ne rétablit pas", not tr,
           f"{len(tr)} transition(s)")
    # Puis 3 mesures saines consécutives -> rétablissement confirmé
    tr2 = _feed(det, "RAM", [50.0, 50.0, 50.0])
    _check("Rétablissement confirmé",
           len(tr2) == 1 and tr2[0].current is State.NORMAL
           and tr2[0].is_recovery,
           f"{len(tr2)} transition(s)")
    _check("Seuil WARNING reporté sur la transition de rétablissement",
           tr2 and tr2[0].threshold == 80.0)


def scenario_fenetre_incomplete() -> None:
    """Jamais de confirmation sur une fenêtre non remplie."""
    det = Detector(THRESHOLDS, 5)
    tr = _feed(det, "DISK", [99.0] * 4)
    _check("Fenêtre incomplète (4/5) : aucune alerte", not tr,
           f"{len(tr)} transition(s)")
    tr2 = _feed(det, "DISK", [99.0])           # 5e mesure
    _check("Confirmation dès la 5e mesure",
           len(tr2) == 1 and tr2[0].current is State.CRITICAL)


def scenario_ressource_inconnue() -> None:
    det = Detector(THRESHOLDS, N)
    try:
        det.update("GPU", 50.0)
        _check("Ressource inconnue rejetée", False)
    except KeyError:
        _check("Ressource inconnue rejetée", True)


def scenario_multiple() -> None:
    """Indépendance des états entre ressources."""
    det = Detector(THRESHOLDS, N)
    _feed(det, "CPU", [95.0] * 3)     # CRITICAL
    _feed(det, "RAM", [30.0] * 3)     # NORMAL
    snap = det.snapshot()
    _check("États indépendants par ressource",
           snap.get("CPU") is State.CRITICAL and snap.get("RAM") is State.NORMAL,
           str({k: v.value for k, v in snap.items()}))


def main() -> int:
    scenario_pic_isole()
    scenario_confirmation_warning()
    scenario_confirmation_critical()
    scenario_dedoublonnage()
    scenario_escalade()
    scenario_retablissement()
    scenario_fenetre_incomplete()
    scenario_ressource_inconnue()
    scenario_multiple()

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
