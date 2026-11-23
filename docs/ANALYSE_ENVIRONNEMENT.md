# Analyse d'environnement — Projet System Monitoring

Date : 18/11/2026 — Phase 1, étape 0.

## Machine

| Élément | Constat |
|---|---|
| OS | Fedora 44 (kernel 7.3.3-200.fc44.x86_64) |
| CPU | 8 cœurs |
| RAM | 15 GiB (≈ 10 GiB disponibles) |
| Swap | 8 GiB (inutilisé) |
| Disque `/` et `/home` | 128 Go, 89 Go utilisés (70 %), 39 Go libres |
| Conclusion | Ressources suffisantes pour Flask + React + Oracle |

## Outils

| Outil | Version | Statut |
|---|---|---|
| Python | 3.14.10 | ✅ venv disponible |
| Node.js | v22.23.1 | ✅ |
| npm | 9.0.8 | ✅ registre npm joignable |
| psutil | 7.2.2 | ✅ système |
| Flask, oracledb, requests, dotenv | installés dans `backend/venv` | ✅ |
| Ports 5000 / 5173 | libres | ✅ |

## Oracle Database — instance existante (utilisée telle quelle)

- Image : `oracle/database:21.3.0-xe` → Oracle Database XE 21c
- Conteneur Docker `oracle-pfe` (préexistant, **non recréé**), démarré
  manuellement pour les vérifications : `docker start oracle-pfe`
- Instance `XE` 21.3.0.0.0, statut OPEN
- Connexion : TCP `localhost:1521`, service **XEPDB1** (READ WRITE)
- Credentials initiaux du conteneur : SYS / `th373622`
- Schemas existants (exercices PFE) : intacts, non modifiés

## python-oracledb — mode Thin validé

Test réel sous Python 3.14 avec oracledb 26.1.0 : connexion OK,
aucun client Oracle Instant Client requis.

> Note : le nom PyPI installable est `oracledb` (le projet s'appelle
> « python-oracledb » mais `python-oracledb` n'existe pas comme nom de
> distribution sur PyPI).

## Utilisateur applicatif créé

- `MONITOR_APP` avec privilèges minimaux : CREATE SESSION, CREATE TABLE,
  CREATE SEQUENCE, UNLIMITED TABLESPACE.
- Bootstrap via SYS dans `storage/db.py` (`ensure_app_user`, idempotent).
- Mot de passe : celui fourni dans `.env` (jamais dans le code).

## Points d'attention

1. Le conteneur Oracle n'est pas auto-démarré : l'application doit
   signaler proprement l'indisponibilité (exception
   `DatabaseUnavailable`), jamais planter.
2. L'utilisateur applicatif n'a pas accès aux vues `V$` : le health check
   utilise `SYS_CONTEXT` et `PRODUCT_COMPONENT_VERSION`.
3. Oracle réservé : les colonnes `level` et `resource` sont des mots
   réservés — renommées `alert_level` et `alert_resource` dans le schéma.
4. L'application est lancée nativement (pas de Docker) ; seul Oracle
   existant tourne dans son conteneur.
