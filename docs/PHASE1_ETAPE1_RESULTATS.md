# Résultats — Étape 1 : socle projet + connexion Oracle

Date : 18/11/2026 — Phase 1.

## Réalisé

- Arborescence du projet créée (`backend/`, `frontend/`, `docs/`).
- `.env` (réel, non versionné) et `.env.example` (modèle).
- `.gitignore` (exclut `.env`, `venv/`, `node_modules/`).
- `backend/config.py` : chargement centralisé de la config et des seuils.
- `backend/requirements.txt` : flask, psutil, oracledb, requests, dotenv.
- `backend/venv/` : environnement virtuel installé.
- `backend/storage/db.py` : pool de connexions Thin, bootstrap
  `MONITOR_APP`, health check, exception `DatabaseUnavailable`.
- `backend/storage/schema.sql` : 3 tables + index, idempotent.
- `backend/run.py` : point d'entrée de vérification (`python run.py`).

## Tests effectués

| # | Test | Résultat |
|---|---|---|
| 1 | `python run.py` (création utilisateur + schéma) | ✅ OK |
| 2 | Relance de `run.py` (idempotence) | ✅ OK, aucune erreur |
| 3 | Tables créées : MACHINES, METRICS, ALERTS | ✅ |
| 4 | Index créés : 4 index + contraintes + unique hostname | ✅ |
| 5 | INSERT machines / metrics / alerts (requêtes paramétrées) | ✅ |
| 6 | SELECT avec JOIN machines↔alerts | ✅ |
| 7 | Nettoyage des données de test | ✅ (0 metrics, 0 alerts restants) |
| 8 | Base indisponible → `DatabaseUnavailable` propre | ✅ |

## Corrections apportées pendant les tests

1. **`python-oracledb` introuvable sur PyPI** → nom correct : `oracledb`.
2. **`GRANT CREATE INDEX` invalide (ORA-00990)** → CREATE INDEX est inclus
   dans CREATE TABLE en Oracle ; retiré des grants.
3. **Split du schema.sql sur `;` cassait le bloc PL/SQL** → exécution du
   bloc entier après retrait des commentaires et du `/` final.
4. **`level` mot réservé (ORA-00904)** → colonne renommée `alert_level`.
5. **`resource` mot réservé (ORA-00904)** → colonne renommée
   `alert_resource`.
6. **`V$INSTANCE` inaccessible pour MONITOR_APP** → health check basé sur
   `SYS_CONTEXT` + `PRODUCT_COMPONENT_VERSION`.

## État

- Base cible : `localhost:1521/XEPDB1`, utilisateur `MONITOR_APP`
- Instance : XE 21.3.0.0.0, container XEPDB1 OPEN
- Machine locale enregistrée : `fedora` (id 1)

## En attente

Validation de l'étape 1 avant de passer à l'étape 2 (collecte des
métriques avec psutil).
