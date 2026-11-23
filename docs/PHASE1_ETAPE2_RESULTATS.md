# Résultats — Étape 2 : collecte des métriques (psutil)

Date : 18/11/2026 — Phase 1.

## Réalisé

- `backend/collector/metrics.py` :
  - `collect_cpu()` : pourcentage global + par cœur + nombre de cœurs
  - `collect_ram()` : total / utilisé / disponible (Mo) + pourcentage
  - `collect_disk(path)` : total / utilisé / libre (Go) + pourcentage
  - `collect_machine()` : hostname, IP, OS, cores, RAM totale (statique)
  - `collect_all()` : snapshot complet horodaté (UTC, ISO 8601)
  - `cpu_cores_json()` : sérialisation pour la colonne CLOB Oracle
- `backend/tests/test_collector.py` : 18 assertions de validité.

## Tests unitaires — 18/18 OK

Exécution : `cd backend && ./venv/bin/python -m tests.test_collector`

Couverture : bornes 0-100 sur tous les pourcentages, cohérence
used+available≈total, utilisé+libre≈total, horodatage UTC, présence
des clés, IP valide, JSON du CLOB.

## Vérification croisée avec les outils système

| Métrique | psutil | Référence système | Écart |
|---|---|---|---|
| RAM totale | 15853.7 Mo | `free -m` : 15853 Mo | ✅ 0.7 Mo |
| RAM utilisée | 9148.5 Mo | `free -m` : 9153 Mo | ✅ 4.5 Mo (instantanés décalés) |
| RAM disponible | 6705.2 Mo | `free -m` : 6699 Mo | ✅ 6 Mo |
| Disque total | 128.0 Go | `df -B1` : 128.0 Go | ✅ |
| Disque utilisé | 88.34 Go | `df -B1` : 88.3 Go | ✅ |
| Disque libre | 38.9 Go | `df -B1` : 38.9 Go | ✅ |
| CPU global | 8.54 % | `vmstat 1 3` (100-id) : 10.7 % | ✅ 2.1 pts (fenêtres non synchrone, charge variable) |

## Défaut détecté et corrigé pendant les tests

**Faux 0 % CPU au premier appel** : `psutil.cpu_percent(interval=None)`
renvoie 0.0 tant qu'aucun échantillon préalable n'existe dans le
processus. Corrections :
1. amorçage des bases de comparaison (global + par cœur) au premier
   appel, avec 1 s d'échantillonnage réel ;
2. le pourcentage global est calculé comme la moyenne des cœurs, sur
   la même fenêtre de mesure (sinon la fenêtre entre les deux appels
   serait quasi nulle et fausserait le résultat).

Note comportementale : deux appels quasi instantanés donnent 0 % car la
fenêtre de mesure est nulle — normal en mode non bloquant ; dans la
boucle de surveillance (étape 3), les appels sont espacés de 10 s.

## En attente

Validation de l'étape 2 avant de passer à l'étape 3 (moteur de
détection : seuils, fenêtre glissante, transitions d'état).
