# Résultats — Étape 4 : notifications Telegram

Date : 18/11/2026 — Phase 1.

## Réalisé

| Composant | Fichier | Rôle |
|---|---|---|
| Client Telegram | `alerting/telegram.py` | WARNING, CRITICAL, rétablissement, test |
| Branche­ment moniteur | `engine/monitor.py` | passage de l'`alert_id`, marquage `notified` |
| Point d'entrée | `run.py` | `--test-telegram`, adaptateur `_make_notify_fn()` |
| Tests | `tests/test_telegram.py` | 34 assertions, HTTP mocké (pas de token requis) |

## Fonctionnalités

- **Alertes WARNING / CRITICAL** : messages HTML avec emoji de niveau,
  valeur, seuil, mention « confirmé sur plusieurs mesures ».
- **Notification de rétablissement** : message `✅` distinct quand la
  ressource retourne à NORMAL (sévérité WARNING/CRITICAL → NORMAL).
- **Test Telegram** : `python run.py --test-telegram`
  1. `getMe` vérifie le token (détecte token invalide/révoqué) ;
  2. signale un `chat_id` manquant ;
  3. envoie un message d'essai réel.
- **Marquage `notified`** : la colonne `alerts.notified` passe à 1
  uniquement si l'envoi a réellement réussi (vérifié en base).

## Sécurité du token

- Lecture **uniquement** depuis `.env` ; aucune valeur en dur.
- Le token est **masqué** dans tous les logs et `repr()`
  (`123456…Dsaw`), y compris dans les exceptions réseau (l'URL
  contenant le token n'est jamais journalisée).
- Aucun code du frontend n'a accès au token (aucune route ne l'expose).

## Comportement dégradé (testé)

| Situation | Comportement |
|---|---|
| `.env` vide | avertissement unique, surveillance normale, `not_configured` |
| Réseau en échec | `ConnectionError` absorbée, `ok=False`, pas de crash |
| Telegram refuse (HTTP 4xx/5xx) | log masqué, pas de renvoi en boucle |
| Exception dans le notifier | absorbée par le moniteur, la boucle continue |
| Oracle indisponible + envoi OK | `alert_id=None` → pas de marquage, pas d'erreur |

## Tests — 34/34 OK (sans token réel)

Couverture : masquage du token · `repr()` sans secret · non configuré ·
envoi OK/erreur API/erreur réseau · `test()` succès / token invalide /
chat_id manquant · formats des 3 types de message · absence de token
dans les messages · intégration moniteur : notifier reçoit l'`alert_id`,
`mark_notified` appelé **seulement** si `ok=True`, exceptions absorbées ·
adaptateur `run.py`.

## Recette effectuée

- `run.py --test-telegram` avec `.env` vide → dégradation propre,
  message d'aide, code retour 1.
- `run.py --once` → Telegram détecté comme non configuré, cycle normal.
- Intégration réelle (persistance + notifier simulé) : alerte WARNING
  créée, notifier appelée avec `alert_id=43`, **`notified=1`** en base.
- 4 suites de tests : toutes OK. Données synthétiques purgées.

## En attente

1. **Votre validation** de l'étape 4.
2. **Vos valeurs** : `TELEGRAM_BOT_TOKEN` et `TELEGRAM_CHAT_ID` dans
   `.env` → puis `python run.py --test-telegram` pour la vérification
   réelle (l'étape 5 pourra de toute façon démarrer sans elles).

## Étape suivante

Étape 5 — API Flask : `/api/status`, `/api/metrics/latest`,
`/api/metrics/history`, `/api/alerts`, `POST /api/alerts/test`.
