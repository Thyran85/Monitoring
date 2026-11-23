# Résultats — Étape 5 : API Flask

Date : 18/11/2026 — Phase 1.

## Réalisé

| Composant | Fichier | Rôle |
|---|---|---|
| API Flask | `api/app.py` | 6 routes JSON, gestion d'erreurs |
| Historique | `storage/repository.py` | `metrics_history()` (courbes Recharts) |
| Point d'entrée | `run.py` | assemble moniteur (thread) + serveur, `--no-api`, `--host`, `--port` |
| Persistance pilotable | `engine/monitor.py` | drapeau `persist` (mode `--no-db` réel) |
| Tests | `tests/test_api.py` | 40 assertions, base et Telegram mockés |

## Endpoints

| Méthode | Route | Description | Réponse |
|---|---|---|---|
| GET | `/api/health` | battement de cœur (sans base) | 200 |
| GET | `/api/status` | état général + 3 états + seuils + métriques + bannières db/telegram | 200 |
| GET | `/api/metrics/latest` | dernière métrique persistée | 200 / 404 / 503 |
| GET | `/api/metrics/history?limit=` | historique (borné 1..500) | 200 / 503 |
| GET | `/api/alerts?limit=` | dernières alertes (borné 1..100) | 200 / 503 |
| POST | `/api/alerts/test` | test config Telegram | 200 / 503 |
| — | 404 / 405 / 500 | erreurs systématiquement en JSON | |

### `GET /api/status` (extrait réel)
```json
{
  "overall_state": "NORMAL",
  "states": {"CPU": "NORMAL", "RAM": "NORMAL", "DISK": "NORMAL"},
  "metrics": {"cpu": {...}, "ram": {...}, "disk": {...}},
  "thresholds": {"CPU": {"warning": 75.0, "critical": 90.0}, ...},
  "monitor": {"running": true, "interval_seconds": 10.0, "cycles": 3, ...},
  "telegram": {"configured": false},
  "database": {"available": true, "instance": "XE", ...}
}
```

## Comportements clés (testés)

- **Base coupée** : `/api/status` reste en **200** avec
  `database.available=false` (le dashboard s'affiche) ; les routes de
  données répondent **503 JSON** (pas de page d'erreur HTML).
- **Sans aucune mesure** : `metrics` peut être `null`, l'état général
  reste renseigné.
- **État général** = niveau le plus sévère des 3 ressources (testé
  CRITICAL/WARNING/NORMAL).
- **Repli** : `/metrics/latest` sert le snapshot vivant si la base est
  vide, 404 si rien n'existe.
- **Paramètres contraints** : `limit=abc` → défaut, `limit=999999` →
  500, `limit=-5` → 1.
- **Aucune fuite de secret** : testé sur les 5 GET avec un notifier
  configuré → ni token, ni mot de passe Oracle dans les réponses.
  Telegram n'est exposé que par le booléen `configured`.

## Tests — 40/40 OK

Couverture : health · status (normal / base coupée / cascade de
sévérité) · latest (base / repli snapshot / 404 / base coupée) ·
history (ok / paramètre invalide / borné / 503) · alerts (ok / borné /
503) · test Telegram non configuré / méthode 405 · route inconnue 404 ·
**audit de fuite de secrets**.

## Corrections apportées pendant les tests

1. **`detector.snapshot()` vide avant la première mesure** → les états
   des 3 ressources sont maintenant pré-initialisés à NORMAL : le
   dashboard a toujours les 3 entrées dès le démarrage.
2. **`--no-db` ne désactivait pas la persistance** (le moniteur écrivait
   quand même en base, seul l'affichage disait « désactivée ») →
   drapeau `Monitor(persist=...)`, vérifié en l'absence totale de
   nouvelles lignes.
3. Deux fragments erronés laissés dans `tests/test_api.py` (expression
   `:=` parasite, branche morte) nettoyés avant exécution.

## Recette réelle (serveur lancé)

```
GET  /api/health              -> {"status":"ok","monitor_running":true,"cycles":1}
GET  /api/status              -> overall NORMAL, 3 états, db XE 21c OPEN, telegram false
GET  /api/metrics/latest      -> cpu 18.18% / ram 58.5% / disk 69.4% (réel)
GET  /api/metrics/history     -> 3 points espacés de 10 s
GET  /api/alerts              -> count 0 (données de test purgées)
POST /api/alerts/test         -> 503 {"ok":false,"error":"not_configured"} (env vide)
GET  /api/inexistant          -> 404 JSON
```
5 suites de tests : **toutes OK**. Base finale : 1 machine, 16 métriques
réelles, 0 alerte résiduelle.

## En attente

Validation de l'étape 5 avant de passer à l'étape 6 (dashboard React :
état général, cartes CPU/RAM/Disque, badges, dernières alertes,
auto-refresh 5 s).

Rappel : vos `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` restent à
mettre dans `.env` (étape 4 déjà livrée, test réel à faire avec
`run.py --test-telegram`).
