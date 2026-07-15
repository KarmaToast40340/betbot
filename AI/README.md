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

## Vocabulaire d'action (baseline V1)

Le modèle V1 prédit uniquement le type d'action (classification à 6 classes) ; `amount_bb` n'est pas encore prédit.

| action | id |
|---|---|
| fold | 0 |
| check | 1 |
| call | 2 |
| bet | 3 |
| raise | 4 |
| all_in | 5 |

## Pipeline PokerBench (baseline supervisé)

Le service `betbot-agent` a `profiles: ["train"]` dans `docker-compose.yml` : il ne démarre jamais avec un simple `docker compose up`, il faut l'invoquer explicitement.

```bash
# 1. Télécharger les 4 CSV officiels de RZ412/PokerBench
docker compose --profile train run --rm betbot-agent \
  python /workspace/AI/Training/download_pokerbench.py \
  --output-dir /workspace/AI/Training/data/raw

# 2. Convertir chaque CSV vers le JSONL standardisé (une commande par fichier)
docker compose --profile train run --rm betbot-agent \
  python /workspace/AI/Training/pokerbench_to_json.py \
  /workspace/AI/Training/data/raw/preflop_60k_train_set_game_scenario_information.csv \
  /workspace/AI/Training/data/interim/preflop_train.jsonl preflop

docker compose --profile train run --rm betbot-agent \
  python /workspace/AI/Training/pokerbench_to_json.py \
  /workspace/AI/Training/data/raw/preflop_1k_test_set_game_scenario_information.csv \
  /workspace/AI/Training/data/interim/preflop_test.jsonl preflop

docker compose --profile train run --rm betbot-agent \
  python /workspace/AI/Training/pokerbench_to_json.py \
  /workspace/AI/Training/data/raw/postflop_500k_train_set_game_scenario_information.csv \
  /workspace/AI/Training/data/interim/postflop_train.jsonl postflop

docker compose --profile train run --rm betbot-agent \
  python /workspace/AI/Training/pokerbench_to_json.py \
  /workspace/AI/Training/data/raw/postflop_10k_test_set_game_scenario_information.csv \
  /workspace/AI/Training/data/interim/postflop_test.jsonl postflop

# 3. Split train/val (preflop+postflop unifiés) ; le split *_test officiel est conservé tel quel comme test set
docker compose --profile train run --rm betbot-agent \
  python /workspace/AI/Training/split_dataset.py \
  --interim-dir /workspace/AI/Training/data/interim \
  --output-dir /workspace/AI/Training/data/processed \
  --val-fraction 0.1 --seed 42

# 4. Entraîner (utilise la commande par défaut du service, ou surcharge les arguments)
docker compose --profile train run --rm betbot-agent \
  python /workspace/AI/train/train.py --epochs 5 --batch-size 64
```

Checkpoints écrits dans `AI/train/checkpoints/` (`last.pt` à chaque epoch, `best.pt` sur amélioration de la val accuracy). Chaque checkpoint embarque ses hyperparamètres et un snapshot du vocabulaire (`AI/train/vocab.py`), donc une future inférence peut le recharger sans dépendre du code d'entraînement.

## GPU (AMD RX 7700 XT / ROCm)

`Dockerfile.ia` part de l'image officielle `rocm/pytorch:latest` (torch déjà compilé pour ROCm), et `docker-compose.yml` passe `/dev/kfd`+`/dev/dri` au conteneur `betbot-agent`. La RX 7700 XT (gfx1101) n'est pas officiellement supportée par ROCm — `HSA_OVERRIDE_GFX_VERSION=11.0.0` (déjà dans le compose) la fait s'identifier comme une 7900 (gfx1100, supportée). `AI/train/train.py` détecte automatiquement le GPU via `torch.cuda.is_available()` (ROCm expose la même API) et l'affiche au démarrage (`Using device: cuda` ou `cpu`).

Après `docker compose --profile train build betbot-agent`, vérifier que le GPU est bien détecté avant de lancer un entraînement complet :

```bash
docker compose --profile train run --rm betbot-agent \
  python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else None)"
```

Si ça affiche `False`, le passthrough ou l'override GFX ne fonctionne pas sur cette machine — retomber sur `--device cpu` en attendant.

**Note permissions** : les conteneurs Docker tournent en root ; si `sudo docker compose` a déjà écrit dans `AI/Training/data/` ou `AI/train/checkpoints/`, ces fichiers appartiennent à root et ne sont plus modifiables par les scripts lancés en dehors de Docker (hors sudo). `sudo chown -R $USER:$USER AI/Training/data AI/train/checkpoints` si besoin de repasser en local.
