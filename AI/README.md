Le normaliser n'est pas encore testé mais son but est de récupérer les mains du jsonl dans data et de le transformer en main standardisée du type :

```json
{
  "source": "ocr",
  "hand_id": "4928089271211917313-1-1783781173",
  "num_players": 3,
  "blinds": { "sb": 0.5, "bb": 1.0 },
  "hero": {
    "name": "Karmatoast40",
    "cards_dealt": ["Q", "J"]
  },
  "board": {
    "flop": [],
    "turn": null,
    "river": null
  },
  "actions": {
    "preflop": [
      { "player": "Moi54350", "action": "raise", "amount_bb": 15.0 },
      { "player": "Karmatoast40", "action": "fold", "amount_bb": null },
      { "player": "Petunija", "action": "fold", "amount_bb": null }
    ],
    "flop": [],
    "turn": [],
    "river": []
  }
}
```


### L'ENTRAINEMENT EST POUR LE MOMENT FAIT SANS DETECTION DES COULEURS

## Champ `label` (données PokerBench uniquement)

`AI/Training/pokerbench_to_json.py` ajoute un champ `label` aux mains standardisées, absent des mains `source: "ocr"` :

```json
{
  "source": "pokerbench",
  "...": "...",
  "label": { "player": "BTN", "action": "raise", "amount_bb": 12.0 }
}
```

`label.action` est la décision correcte (calculée par un solveur) que le héros aurait dû prendre. C'est la cible d'entraînement du baseline V1.

## Champ `pot_bb` (données PokerBench uniquement)

`pokerbench_to_json.py` extrait aussi `pot_bb` (colonne `pot_size` du CSV, en bb) au niveau racine de la main standardisée :

```json
{ "source": "pokerbench", "...": "...", "pot_bb": 21.0 }
```

Encodé en entrée via un bucket dédié (`<POT_BUCKET_X>`, mêmes tranches que les montants de mise mais namespace de token séparé) juste après la position du héros dans la séquence — voir `AI/train/vocab.py`. Absent des mains `source: "ocr"` (le pipeline OCR n'extrait pas la taille du pot) ; retombe sur `<POT_UNK>` si absent.

## Vocabulaire d'action + sizing (V2)

Le modèle prédit le type d'action (classification à 6 classes) et, quand l'action prédite est `bet`/`raise`, une taille de mise via une deuxième tête de classification sur les 10 buckets déjà utilisés pour encoder les montants en entrée (`AI/train/vocab.py`, `AMOUNT_BUCKET_EDGES = [1, 2, 4, 7, 12, 20, 35, 60, 100]`). Pas de régression continue : classification sur buckets, plus stable et cohérent avec le reste du vocabulaire. `all_in` n'a pas de tête de sizing (le montant est implicitement tout le stack).

| action | id |
|---|---|
| fold | 0 |
| check | 1 |
| call | 2 |
| bet | 3 |
| raise | 4 |
| all_in | 5 |

La loss de sizing n'est calculée que sur les lignes où `label.action` est `bet`/`raise` (masquée pour les autres), pondérée par `--amount-loss-weight` (défaut `1.0`) dans `train.py`.

## Pipeline PokerBench (baseline supervisé)

Le service `betbot-agent` a `profiles: ["train"]` dans `docker-compose.yml` : il ne démarre jamais avec un simple `docker compose up`, il faut l'invoquer explicitement.

```bash
# 1. Télécharger les 4 CSV officiels de RZ412/PokerBench
sudo docker compose --profile train run --rm betbot-agent \
  python /workspace/AI/Training/download_pokerbench.py \
  --output-dir /workspace/AI/Training/data/raw

# 2. Convertir chaque CSV vers le JSONL standardisé (une commande par fichier)
sudo docker compose --profile train run --rm betbot-agent \
  python /workspace/AI/Training/pokerbench_to_json.py \
  /workspace/AI/Training/data/raw/preflop_60k_train_set_game_scenario_information.csv \
  /workspace/AI/Training/data/interim/preflop_train.jsonl preflop

sudo docker compose --profile train run --rm betbot-agent \
  python /workspace/AI/Training/pokerbench_to_json.py \
  /workspace/AI/Training/data/raw/preflop_1k_test_set_game_scenario_information.csv \
  /workspace/AI/Training/data/interim/preflop_test.jsonl preflop

sudo docker compose --profile train run --rm betbot-agent \
  python /workspace/AI/Training/pokerbench_to_json.py \
  /workspace/AI/Training/data/raw/postflop_500k_train_set_game_scenario_information.csv \
  /workspace/AI/Training/data/interim/postflop_train.jsonl postflop

sudo docker compose --profile train run --rm betbot-agent \
  python /workspace/AI/Training/pokerbench_to_json.py \
  /workspace/AI/Training/data/raw/postflop_10k_test_set_game_scenario_information.csv \
  /workspace/AI/Training/data/interim/postflop_test.jsonl postflop

# 3. Split train/val (preflop+postflop unifiés) ; le split *_test officiel est conservé tel quel comme test set
sudo docker compose --profile train run --rm betbot-agent \
  python /workspace/AI/Training/split_dataset.py \
  --interim-dir /workspace/AI/Training/data/interim \
  --output-dir /workspace/AI/Training/data/processed \
  --val-fraction 0.1 --seed 42

# 4. Entraîner (utilise la commande par défaut du service, ou surcharge les arguments)
sudo docker compose --profile train run --rm betbot-agent \
  python /workspace/AI/train/train.py --epochs 5 --batch-size 64
```

Checkpoints écrits dans `AI/train/checkpoints/` (`last.pt` à chaque epoch, `best.pt` sur amélioration de la val accuracy). Chaque checkpoint embarque ses hyperparamètres et un snapshot du vocabulaire (`AI/train/vocab.py`), donc une future inférence peut le recharger sans dépendre du code d'entraînement.

## Inférence (`AI/train/infer.py`)

Script autonome : charge un checkpoint et fait tourner le modèle sur une seule main standardisée (JSON), affiche l'action prédite (+ ses probabilités) et, si l'action prédite est `bet`/`raise`, la tranche de taille prédite (`amount_bb_range`, `amount_bb_estimate` = milieu de la tranche).

```bash
# depuis un fichier
python AI/train/infer.py --checkpoint AI/train/checkpoints/best.pt --input ma_main.json

# depuis stdin
head -1 AI/Training/data/processed/test.jsonl | python AI/train/infer.py --checkpoint AI/train/checkpoints/best.pt --input -

# via docker
docker compose --profile train run --rm betbot-agent \
  python /workspace/AI/train/infer.py --checkpoint /workspace/AI/train/checkpoints/best.pt --input -
```

Le checkpoint embarque sa propre config et son propre snapshot de vocabulaire ; `infer.py` reste indépendant de `train.py`/de la boucle d'entraînement, et compare le snapshot du checkpoint au `vocab.py` courant pour avertir en cas de désynchronisation (ex. checkpoint entraîné avant l'ajout de la tête de sizing).

## Détection du tour (`ScreenScraper/turn_detector.py`)

Le bouton "Check" change de couleur (bleuté → rouge) quand c'est le tour du héros — un signal visuel direct, bien plus rapide et fiable que déduire "c'est mon tour" depuis le texte OCR de l'historique de main (qui ne se met à jour qu'environ toutes les 10s). `main.py` échantillonne la couleur moyenne de cette zone (`config.CHECK_BUTTON_ROI`) à chaque tick de sa boucle (pas besoin d'OCR pour ça, juste un `mss.grab` + moyenne de pixels) et écrit `data/output/turn_signal.json` (`{"hero_turn": bool, "timestamp_utc": ...}`) dès que l'état change.

**Calibration nécessaire** : les seuils de classification rouge/bleu (`BETBOT_TURN_MIN_RED=110`, `BETBOT_TURN_RED_MARGIN=25` par défaut dans `ScreenScraper/turn_detector.py`) sont un point de départ raisonnable, pas calibré sur le vrai jeu. `ScreenScraper/misc/mouse_coords.py` affiche maintenant aussi la couleur RGB sous le curseur — survole le bouton dans les deux états (pas ton tour / ton tour) pour lire les vraies valeurs, puis ajuste les deux variables d'environnement dans `docker-compose.yml` (service `screenscraper`) si la détection ne colle pas.

## Inférence live (`AI/train/watch_and_infer.py` + service `agent-serve`)

Surveille `data/output/turn_signal.json` et lance une prédiction dès qu'il passe à `true`, en utilisant le dernier état connu de la main du héros dans `data/output/poker_states.jsonl` pour construire l'entrée du modèle. La logique texte précédente ("le héros n'a pas encore agi sur la street en cours") reste en place uniquement comme garde-fou (ne pas agir si le héros a déjà foldé ou si la main est au showdown d'après le journal, au cas où le signal couleur se déclenche à tort sur un état périmé).

Le service `agent-serve` (`profiles: ["serve"]`, `restart: unless-stopped`) réutilise l'image `Dockerfile.ia` déjà construite pour l'entraînement, mais tourne en CPU (une seule prédiction sur ce petit modèle est instantanée, pas besoin du GPU) — donc pas de passthrough `/dev/kfd`/`/dev/dri` pour ce service.

**Usage préféré : un terminal par service**, chacun avec ses logs bruts en direct (`Ctrl+C` pour arrêter ce service précis) :

```bash
# Terminal 1
sudo docker compose up paddleocr-vlm-server

# Terminal 2
sudo docker compose up screenscraper

# Terminal 3
sudo docker compose --profile serve up agent-serve
```

Une fois prêt à jouer, dans un 4e terminal (les trois autres sont occupés par les logs) :

```bash
sudo docker compose --profile serve exec agent-serve touch /workspace/data/output/start_serving.flag
```

Alternative tout-en-un (moins de terminaux, logs entremêlés) :

```bash
sudo docker compose --profile serve up -d
sudo docker compose --profile serve logs -f agent-serve
```

Le conteneur `screenscraper` n'a pas été touché (pas de torch dedans) : `agent-serve` lit uniquement `poker_states.jsonl`, aucun couplage direct entre les deux services. À chaque déclenchement, la prédiction est affichée dans les logs et écrite dans `data/output/latest_prediction.json`. Si les cartes du héros n'ont pas encore été captées par l'OCR à ce moment-là, le tour est signalé mais aucune prédiction n'est faite (prédire sans connaître sa main n'est pas fiable). Un décompte simple (hand_id + street + nombre d'actions) évite de re-prédire en boucle tant que rien n'a changé.

### Nettoyage au démarrage

`agent-serve` **vide entièrement `data/output/`** dès son lancement (avant même de charger le modèle), pour repartir sur une base saine à chaque session — c'est ce qui évite définitivement le bug de main périmée d'une session précédente (`screenscraper` régénère tout ce dont il a besoin depuis zéro, rien d'important n'est perdu). Désactivable avec `--keep-output` si besoin.

⚠️ **Point d'attention** : `agent-serve` a `restart: unless-stopped` — s'il plante et redémarre automatiquement *en cours de session*, ça effacera aussi les mains capturées depuis le début de cette session. Peu probable (la boucle est simple), mais à savoir.

### Démarrage à la demande

`agent-serve` charge le modèle au lancement du conteneur puis **attend un signal explicite** avant de commencer à surveiller — pour ne pas se déclencher avant que la partie ne commence. Une fois `agent-serve` démarré (et donc en attente), lance ça quand tu es prêt :

```bash
sudo docker compose --profile serve exec agent-serve touch /workspace/data/output/start_serving.flag
```

Le signal est consommé (fichier supprimé) dès qu'il est vu, donc chaque redémarrage du conteneur redemande un nouveau signal — pas besoin de le supprimer manuellement entre deux sessions. Pour désactiver l'attente (tests, debug) : ajouter `--auto-start` à la commande dans `docker-compose.yml`.

## GPU (AMD RX 7700 XT / ROCm)

`Dockerfile.ia` part de l'image officielle `rocm/pytorch:latest` (torch déjà compilé pour ROCm), et `docker-compose.yml` passe `/dev/kfd`+`/dev/dri` au conteneur `betbot-agent`. La RX 7700 XT (gfx1101) n'est pas officiellement supportée par ROCm — `HSA_OVERRIDE_GFX_VERSION=11.0.0` (déjà dans le compose) la fait s'identifier comme une 7900 (gfx1100, supportée). `AI/train/train.py` détecte automatiquement le GPU via `torch.cuda.is_available()` (ROCm expose la même API) et l'affiche au démarrage (`Using device: cuda` ou `cpu`).

Après `docker compose --profile train build betbot-agent`, vérifier que le GPU est bien détecté avant de lancer un entraînement complet :

```bash
docker compose --profile train run --rm betbot-agent \
  python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else None)"
```

Si ça affiche `False`, le passthrough ou l'override GFX ne fonctionne pas sur cette machine — retomber sur `--device cpu` en attendant.

**Note permissions** : les conteneurs Docker tournent en root ; si `sudo docker compose` a déjà écrit dans `AI/Training/data/` ou `AI/train/checkpoints/`, ces fichiers appartiennent à root et ne sont plus modifiables par les scripts lancés en dehors de Docker (hors sudo). `sudo chown -R $USER:$USER AI/Training/data AI/train/checkpoints` si besoin de repasser en local.
