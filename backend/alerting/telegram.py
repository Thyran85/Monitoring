"""
Intégration Telegram (Bot API officielle).

Responsabilités :
  - formater et envoyer les alertes WARNING / CRITICAL ;
  - envoyer la notification de rétablissement (retour à NORMAL) ;
  - fournir une fonction de TEST du paramétrage (token + chat_id).

Sécurité :
  - le token et le chat_id sont lus UNIQUEMENT depuis `.env`
    (jamais dans le code, jamais exposés au frontend) ;
  - le token n'est jamais journalisé (masqué en permanence).

Comportement dégradé : si Telegram n'est pas configuré ou si
l'envoi échoue, on journalise et on n'interrompt jamais la
surveillance. Chaque envoi est indépendant (une notification
échouée n'est pas réessayée en boucle : l'anti-dédoublonnage
est assuré par le moteur de détection).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import requests

from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from engine.detector import State, Transition

log = logging.getLogger("telegram")

API_BASE = "https://api.telegram.org"
TIMEOUT_SECONDS = 10.0

# Emojis de niveau (affichage Telegram)
_LEVEL_EMOJI = {
    State.WARNING: "⚠️",
    State.CRITICAL: "🚨",
    State.NORMAL: "✅",
}


def _mask(token: str) -> str:
    """Masque un token pour tout affichage/journalisation sûr."""
    if not token or len(token) < 12:
        return "***"
    return f"{token[:6]}…{token[-4:]}"


@dataclass(frozen=True)
class SendResult:
    """Résultat d'un envoi, exploitable par les tests et l'API."""

    ok: bool
    detail: str
    error: str | None = None


class TelegramNotifier:
    """Envoi de messages vers un chat Telegram.

    Parameters
    ----------
    token / chat_id : valeur explicite, ou None pour lire la config
        (.env) au moment de l'instanciation.
    session : objet compatible `requests.post` (permet le mock en test).
    """

    def __init__(
        self,
        token: str | None = None,
        chat_id: str | None = None,
        session=None,
    ) -> None:
        self.token = (TELEGRAM_BOT_TOKEN if token is None else token) or ""
        self.chat_id = (TELEGRAM_CHAT_ID if chat_id is None else chat_id) or ""
        self._session = session or requests

    # --- État ---------------------------------------------------------------

    @property
    def is_configured(self) -> bool:
        """Vrai si token et chat_id sont présents dans la config."""
        return bool(self.token) and bool(self.chat_id)

    def __repr__(self) -> str:  # jamais de token en clair
        return (f"TelegramNotifier(configured={self.is_configured}, "
                f"token={_mask(self.token)}, chat_id={'oui' if self.chat_id else 'non'})")

    # --- Envoi ---------------------------------------------------------------

    def send_text(self, text: str) -> SendResult:
        """Envoie un message texte brut au chat configuré."""
        if not self.is_configured:
            msg = ("Telegram non configuré : renseigner TELEGRAM_BOT_TOKEN "
                   "et TELEGRAM_CHAT_ID dans .env")
            log.warning(msg)
            return SendResult(ok=False, detail=msg, error="not_configured")

        url = f"{API_BASE}/bot{self.token}/sendMessage"
        try:
            response = self._session.post(
                url,
                json={
                    "chat_id": self.chat_id,
                    "text": text,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": True,
                },
                timeout=TIMEOUT_SECONDS,
            )
        except requests.RequestException as exc:
            # Remarque : l'exception peut contenir l'URL avec token —
            # on ne la journalise pas telle quelle.
            log.warning("Envoi Telegram impossible : %s", type(exc).__name__)
            return SendResult(ok=False, detail="erreur réseau",
                              error=type(exc).__name__)

        if response.status_code == 200 and response.json().get("ok"):
            return SendResult(ok=True, detail="message envoyé")

        # Réponse d'erreur du serveur Telegram : on masque le token.
        detail = f"HTTP {response.status_code}"
        log.warning("Telegram a refusé le message (%s) — token=%s",
                    detail, _mask(self.token))
        return SendResult(ok=False, detail=detail, error="api_error")

    def send_transition(self, transition: Transition) -> SendResult:
        """Envoie l'alerte correspondant à un changement d'état."""
        return self.send_text(format_transition(transition))

    # --- Test ----------------------------------------------------------------

    def test(self) -> SendResult:
        """Test complet : vérifie le token puis envoie un message d'essai."""
        if not self.token:
            return SendResult(ok=False,
                              detail="TELEGRAM_BOT_TOKEN absent de .env",
                              error="not_configured")
        # 1. Le token est-il valide ? (getMe)
        try:
            response = self._session.get(
                f"{API_BASE}/bot{self.token}/getMe",
                timeout=TIMEOUT_SECONDS,
            )
            payload = response.json()
        except requests.RequestException as exc:
            return SendResult(ok=False, detail="erreur réseau sur getMe",
                              error=type(exc).__name__)
        if not payload.get("ok"):
            return SendResult(ok=False, detail="token invalide ou révoqué",
                              error="bad_token")
        bot = payload.get("result", {})
        bot_name = bot.get("username", "?")

        if not self.chat_id:
            return SendResult(
                ok=False,
                detail=f"bot @{bot_name} OK mais TELEGRAM_CHAT_ID absent "
                       "de .env",
                error="no_chat_id",
            )

        # 2. Message d'essai
        return self.send_text(
            f"✅ <b>System Monitoring — test réussi</b>\n"
            f"Bot : @{bot_name}\n"
            f"La surveillance enverra ici les alertes WARNING, CRITICAL "
            f"et les rétablissements."
        )


def format_transition(transition: Transition) -> str:
    """Formate une transition en message HTML Telegram."""
    emoji = _LEVEL_EMOJI.get(transition.current, "ℹ️")
    resource = transition.resource
    level = transition.current.value

    if transition.is_recovery:
        return (
            f"{emoji} <b>Rétablissement — {resource}</b>\n"
            f"Situation revenue à la normale : <b>{transition.value}%</b>\n"
            f"Seuil de sortie : {transition.threshold}%"
        )

    if transition.is_escalation:
        title = f"Escalade — {resource} passe en CRITICAL"
    else:
        title = f"Alerte {level} — {resource}"

    return (
        f"{emoji} <b>{title}</b>\n"
        f"Valeur : <b>{transition.value}%</b>\n"
        f"Seuil {level} : {transition.threshold}%\n"
        f"Confirmé sur plusieurs mesures consécutives."
    )
