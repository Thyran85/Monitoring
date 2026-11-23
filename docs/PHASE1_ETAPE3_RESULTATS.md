# Résultats — Étape 3 : moteur de détection + boucle de surveillance

Date : 18/11/2026 — Phase 1.

## Réalisé

| Composant | Fichier | Rôle |
|---|---|---|
| Moteur de détection | `engine/detector.py` | états, seuils, fenêtre glissante, transitions |
| Boucle autonome | `engine/monitor.py` | cycle 10 s en thread, indépendante du frontend |
| Persistance | `storage/repository.py` | requêtes paramétrées (machines, metrics, alerts) |
| Point d'entrée | `run.py` | `--once`, `--status`, `--no-db`, boucle interactive |
| Tests unitaires | `tests/test_detector.py` | 15 assertions |
| Tests intégration | `tests/test_monitor.py` | 17 assertions (avec Oracle) |

## Règles du moteur (conformes au cahier des charges)

- **Seuils** : CPU 75/90 %, RAM 80/95 %, Disque 80/95 % (configurables
  dans `.env`).
- **Fenêtre glissante** : un état anormal n'est confirmé qu'après
  **3 mesures consécutives** (N configurable). Une fenêtre incomplète
  ne conclut jamais.
- **Symétrie** : le rétablissement exige lui aussi 3 mesures saines
  consécutives — un creux isolé en pleine alerte ne provoque pas de
  faux rétablissement.
- **Fenêtre mixte** (mesures contradictoires) : l'état confirmé est
  conservé.
- **Anti-dédoublonnage** : une alerte n'est émise qu'à chaque
  *changement* d'état — rester en WARNING ne renvoie rien.
- **Transitions suivies** : NORMAL→WARNING, NORMAL→CRITICAL,
  WARNING→CRITICAL (escalade), WARNING/CRITICAL→NORMAL
  (`is_recovery` pour la notification de rétablissement, étape 4).

## Tests — 15/15 unitaires + 17/17 intégration

**`tests/test_detector.py`** (pur, sans base) :
pic isolé ignoré · confirmation WARNING · confirmation CRITICAL directe ·
dédoublonnage · escalade · rétablissement (creux isolé ignoré) ·
fenêtre incomplète (4/5 sans effet, 5/5 confirmée) · ressource
inconnue rejetée · indépendance des ressources.

**`tests/test_monitor.py`** (avec Oracle) :
scénario complet NORMAL→WARNING→CRITICAL→rétablissement avec
vérification en base : 5 alertes créées, 0 OPEN après rétablissement,
résolutions horodatées, `alert_resource` correct, et **résilience** :
le cycle survit à l'indisponibilité de la base (collecte et détection
poursuivent, la persistance retente au cycle suivant).

Les données synthétiques du test sont purgées en fin d'exécution.

## Vérifications manuelles

- `python run.py --once` : cycle réel, persistance OK, 3 états NORMAL.
- Boucle observée 25 s : 5 cycles, arrêt propre (`Ctrl+C`).
- État de la base après recette : 3 tables, 3 machines... 1 machine
  (`fedora`), 7 métriques réelles, 0 alerte.

## Corrections apportées pendant les tests

1. **`MERGE ... RETURNING INTO` non supporté** (ORA-00933) → séparation
   MERGE puis SELECT de l'id.
2. **`ORA-01745` sur les binds `:level` / `:resource`** → mots réservés
   interdits comme noms de variable de liaison, renommés `:lvl` / `:res`.
3. **CLOB lue comme objet LOB** → `.read()` avant `json.loads()`.
4. **Échec réseau parfois à `pool.acquire()` et non à `create_pool`**
   (pool créé en différé) → `db.acquire()` convertit toute erreur en
   `DatabaseUnavailable` et purge le pool défaillant.
5. **`PythonFinalizationError` en fin d'interpréteur** → fermeture
   explicite du pool (`db.close_pool()`) à l'arrêt.
6. **Faute de frappe `help(...)`** → `help=` dans argparse.

## En attente

Validation de l'étape 3 avant de passer à l'étape 4 (notifications
Telegram : WARNING, CRITICAL, rétablissement, test — nécessitera le
bot token et le chat id).
