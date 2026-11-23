"""
Tests du module Telegram — Étape 4 (aucun token réel requis : HTTP mocké).

Exécution :
    cd backend && ./venv/bin/python -m tests.test_telegram
"""

from __future__ import annotations

import sys
from types import SimpleNamespace

from alerting.telegram import (
    TelegramNotifier,
    _mask,
    format_transition,
)
from engine.detector import State, Transition

_failures: list[str] = []


def _check(label: str, condition: bool, detail: str = "") -> None:
    print(f"[{'OK  ' if condition else 'FAIL'}] {label}" + (f" — {detail}" if detail else ""))
    if not condition:
        _failures.append(label)


class FakeResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload if payload is not None else {"ok": True}

    def json(self):
        return self._payload


class FakeSession:
    """Remplace requests : enregistre les appels, renvoie des réponses prédéfinies."""

    def __init__(self, post_response=None, get_response=None, raise_on=None):
        self.post_calls = []
        self.get_calls = []
        self.post_response = post_response or FakeResponse()
        self.get_response = get_response or FakeResponse()
        self.raise_on = raise_on  # "post" | "get" | None

    def post(self, url, json=None, timeout=None):
        self.post_calls.append({"url": url, "json": json, "timeout": timeout})
        if self.raise_on == "post":
            import requests
            raise requests.ConnectionError("boom")
        return self.post_response

    def get(self, url, timeout=None):
        self.get_calls.append({"url": url, "timeout": timeout})
        if self.raise_on == "get":
            import requests
            raise requests.Timeout("boom")
        return self.get_response


def _transition(current: State, previous: State = State.NORMAL) -> Transition:
    return Transition(resource="CPU", previous=previous, current=current,
                      value=85.0, threshold=75.0)


# --- Sécurité du token -------------------------------------------------------

def scenario_mask() -> None:
    token = "1234567890:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw"
    masked = _mask(token)
    _check("Token masqué", "…" in masked and token not in masked, masked)
    _check("Masque court sans crash", _mask("abc") == "***")
    _check("Masque vide", _mask("") == "***")


def scenario_repr_no_secret() -> None:
    token = "1234567890:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw"
    n = TelegramNotifier(token=token, chat_id="42", session=FakeSession())
    r = repr(n)
    _check("repr ne contient pas le token complet", token not in r, r[:70])
    _check("repr signale la configuration", "configured=True" in r)


# --- Non configuré -----------------------------------------------------------

def scenario_not_configured() -> None:
    n = TelegramNotifier(token="", chat_id="", session=FakeSession())
    _check("is_configured faux sans config", not n.is_configured)
    res = n.send_text("test")
    _check("Envoi refusé proprement", not res.ok and res.error == "not_configured",
           res.detail)
    res2 = n.test()
    _check("test() signale le token absent",
           not res2.ok and res2.error == "not_configured", res2.detail)


# --- Envoi -------------------------------------------------------------------

def scenario_send_ok() -> None:
    session = FakeSession(post_response=FakeResponse(200, {"ok": True}))
    n = TelegramNotifier(token="123456:ABC", chat_id="42", session=session)
    res = n.send_text("bonjour")
    _check("Envoi réussi", res.ok, res.detail)
    _check("POST vers l'API officielle",
           len(session.post_calls) == 1
           and session.post_calls[0]["url"].startswith("https://api.telegram.org/bot"),
           session.post_calls[0]["url"][:45] + "…")
    _check("chat_id et text présents",
           session.post_calls[0]["json"]["chat_id"] == "42"
           and session.post_calls[0]["json"]["text"] == "bonjour")
    _check("Timeout imposé", session.post_calls[0]["timeout"] > 0)


def scenario_send_api_error() -> None:
    session = FakeSession(post_response=FakeResponse(400, {"ok": False}))
    n = TelegramNotifier(token="123456:ABC", chat_id="42", session=session)
    res = n.send_text("x")
    _check("Erreur API détectée", not res.ok and res.error == "api_error",
           res.detail)


def scenario_send_network_error() -> None:
    session = FakeSession(raise_on="post")
    n = TelegramNotifier(token="123456:ABC", chat_id="42", session=session)
    res = n.send_text("x")
    _check("Erreur réseau absorbée (pas de crash)",
           not res.ok and res.error == "ConnectionError", res.detail)


# --- Test de configuration ----------------------------------------------------

def scenario_test_success() -> None:
    session = FakeSession(
        get_response=FakeResponse(200, {"ok": True, "result": {"username": "mon_bot"}}),
        post_response=FakeResponse(200, {"ok": True}),
    )
    n = TelegramNotifier(token="123456:ABC", chat_id="42", session=session)
    res = n.test()
    _check("test() complet réussi", res.ok, res.detail)
    _check("getMe appelé", len(session.get_calls) == 1)
    _check("Message de test envoyé", len(session.post_calls) == 1)
    _check("Message contient le nom du bot", "mon_bot" in session.post_calls[0]["json"]["text"])


def scenario_test_bad_token() -> None:
    session = FakeSession(get_response=FakeResponse(200, {"ok": False}))
    n = TelegramNotifier(token="123456:ABC", chat_id="42", session=session)
    res = n.test()
    _check("Token invalide détecté", not res.ok and res.error == "bad_token",
           res.detail)


def scenario_test_no_chat_id() -> None:
    session = FakeSession(
        get_response=FakeResponse(200, {"ok": True, "result": {"username": "b"}}))
    n = TelegramNotifier(token="123456:ABC", chat_id="", session=session)
    res = n.test()
    _check("chat_id manquant signalé",
           not res.ok and res.error == "no_chat_id", res.detail)


# --- Formats de messages -------------------------------------------------------

def scenario_formats() -> None:
    warn = format_transition(_transition(State.WARNING))
    _check("Message WARNING contient niveau et ressource",
           "WARNING" in warn and "CPU" in warn and "85.0" in warn)
    crit = format_transition(_transition(State.CRITICAL, State.WARNING))
    _check("Message CRITICAL/escalade explicite",
           "CRITICAL" in crit and "Escalade" in crit)
    rec = format_transition(
        Transition("RAM", State.CRITICAL, State.NORMAL, 40.0, 80.0))
    _check("Message rétablissement explicite",
           "rétabli" in rec.lower() and "RAM" in rec and "40.0" in rec)
    _check("Aucun token dans les messages",
           "123456" not in warn + crit + rec)


# --- Intégration notifier <-> moniteur -----------------------------------------

def scenario_monitor_notify_marks_notified() -> None:
    """Le moniteur appelle le notifier avec l'alert_id et ne marque
    `notified` que si l'envoi a réussi. Test déterministe : la base est
    remplacée par des stubs (aucune dépendance à Oracle)."""
    from engine import monitor as monitor_mod
    from engine.monitor import Monitor

    def _snap(cpu):
        return {
            "collected_at": "2026-11-18T12:00:00+00:00",
            "cpu": {"percent": cpu, "per_core": [cpu] * 8, "core_count": 8},
            "ram": {"percent": 50.0, "total_mb": 100, "used_mb": 50,
                    "available_mb": 50},
            "disk": {"percent": 50.0, "path": "/", "total_gb": 100,
                     "used_gb": 50, "free_gb": 50},
        }

    def _run(notifier, alert_id_stub):
        """Exécute 3 cycles WARNING avec persistance stubée."""
        calls = []
        m = Monitor(interval=0.1, notifier=notifier)
        m._persist = lambda snap: None                      # pas de metrics
        m._persist_alert = lambda t: alert_id_stub          # alert_id simulé
        trans = []
        for _ in range(3):
            trans += m.run_cycle(_snap(cpu=85.0))
        return trans, calls

    # 1. Le notifier reçoit bien (transition, alert_id)
    received = []
    ok_notifier = lambda t, a: received.append((t, a)) or SimpleNamespace(ok=True)
    trans, _ = _run(ok_notifier, 42)
    _check("Notifier appelé exactement 1 fois sur transition",
           len(trans) == 1 and len(received) == 1,
           f"{len(trans)} transition(s), {len(received)} appel(s)")
    _check("Notifier reçoit l'alert_id persisté",
           received and received[0][1] == 42,
           str(received[0][1]) if received else "aucun appel")

    # 2. send ok -> mark_notified(42) appelé
    marked = []
    original_mark = monitor_mod.repository.mark_notified
    monitor_mod.repository.mark_notified = lambda alert_id: marked.append(alert_id)
    try:
        _run(lambda t, a: SimpleNamespace(ok=True), 42)
        _check("Envoi réussi -> mark_notified appelé", marked == [42], str(marked))

        # 3. send échoué -> mark_notified JAMAIS appelé
        marked.clear()
        _run(lambda t, a: SimpleNamespace(ok=False), 43)
        _check("Envoi échoué -> mark_notified non appelé", not marked,
               str(marked))
    finally:
        monitor_mod.repository.mark_notified = original_mark

    # 4. Une exception du notifier ne casse pas la boucle
    def boom(transition, alert_id):
        raise RuntimeError("telegram down")

    try:
        trans, _ = _run(boom, None)
        _check("Exception notifier absorbée", len(trans) == 1)
    except Exception as exc:  # noqa: BLE001
        _check("Exception notifier absorbée", False, str(exc))

    # 5. Sans persistance (alert_id=None) : pas de mark_notified, pas de crash
    marked.clear()
    monitor_mod.repository.mark_notified = lambda alert_id: marked.append(alert_id)
    try:
        trans, _ = _run(lambda t, a: SimpleNamespace(ok=True), None)
        _check("alert_id=None -> pas de mark_notified (pas d'erreur)",
               len(trans) == 1 and not marked, str(marked))
    finally:
        monitor_mod.repository.mark_notified = original_mark


def scenario_run_py_notify_adapter() -> None:
    """L'adaptateur de run.py : bon format, token absent = pas de bruit."""
    import run as run_mod
    from engine.detector import State, Transition

    # Non configuré : pas d'envoi, mais retour exploitable et non crashant
    unconf = run_mod._make_notify_fn(
        TelegramNotifier(token="", chat_id="", session=FakeSession()))
    res = unconf(_transition(State.WARNING), 1)
    _check("Adaptateur : non configuré -> ok=False propre",
           not res.ok and res.error == "not_configured", res.detail)

    # Configuré et envoyé : affiche la confirmation d'envoi
    session = FakeSession(post_response=FakeResponse(200, {"ok": True}))
    conf = run_mod._make_notify_fn(
        TelegramNotifier(token="123456:ABC", chat_id="42", session=session))
    res2 = conf(
        Transition("CPU", State.CRITICAL, State.NORMAL, 30.0, 75.0), 7)
    _check("Adaptateur : envoi OK retourné au moniteur", res2.ok)
    _check("Adaptateur : 1 POST effectué", len(session.post_calls) == 1)
    _check("Adaptateur : message de rétablissement envoyé",
           "rétabli" in session.post_calls[0]["json"]["text"].lower())


def main() -> int:
    scenario_mask()
    scenario_repr_no_secret()
    scenario_not_configured()
    scenario_send_ok()
    scenario_send_api_error()
    scenario_send_network_error()
    scenario_test_success()
    scenario_test_bad_token()
    scenario_test_no_chat_id()
    scenario_formats()
    scenario_monitor_notify_marks_notified()
    scenario_run_py_notify_adapter()

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
