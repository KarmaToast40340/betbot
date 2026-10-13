# The normalizer is not yet tested, but its purpose is to read hands from the JSONL in `data` and transform them into a standardized hand format such as:

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

### TRAINING IS CURRENTLY DONE WITHOUT SUIT DETECTION

## `label` field (PokerBench data only)

`AI/Training/pokerbench_to_json.py` adds a `label` field to standardized hands, which is absent from `source: "ocr"` hands:

```json
{
  "source": "pokerbench",
  "...": "...",
  "label": { "player": "BTN", "action": "raise", "amount_bb": 12.0 }
}
```

`label.action` is the correct decision (computed by a solver) that the hero should have taken. It is the training target of the V1 baseline.

## `pot_bb` field (PokerBench data only)

`pokerbench_to_json.py` also extracts `pot_bb` (the `pot_size` CSV column, in bb) at the root of the standardized hand:

```json
{ "source": "pokerbench", "...": "...", "pot_bb": 21.0 }
```

This is encoded as input via a dedicated bucket (`<POT_BUCKET_X>`, same bands as bet amounts but in a separate token namespace) immediately after the hero position in the sequence — see `...`.

## Action + sizing vocabulary (V2)

The model predicts the action type (6-way classification), and when the predicted action is `bet` / `raise`, it also predicts the bet size through a second classification head on 10 buckets defined by amount ranges.

| action | id |
|---|---|
| fold | 0 |
| check | 1 |
| call | 2 |
| bet | 3 |
| raise | 4 |
| all_in | 5 |

The sizing loss is computed only on rows where `label.action` is `bet` / `raise` (masked otherwise), weighted by `--amount-loss-weight` (default `1.0`) in `train.py`.

## PokerBench pipeline (supervised baseline)

The `betbot-agent` service has `profiles: ["train"]` in `docker-compose.yml`: it never starts with a plain `docker compose up`; it must be invoked explicitly.

```bash
# 1. Download the 4 official RZ412/PokerBench CSV files
sudo docker compose --profile train run --rm betbot-agent \
  python /workspace/AI/Training/download_pokerbench.py \
  --output-dir /workspace/AI/Training/data/raw

# 2. Convert each CSV to standardized JSONL (one command per file)
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

# 3. Split train/val (preflop + postflop unified); the official *_test split is kept as-is as the test set
sudo docker compose --profile train run --rm betbot-agent \
  python /workspace/AI/Training/split_dataset.py \
  --interim-dir /workspace/AI/Training/data/interim \
  --output-dir /workspace/AI/Training/data/processed \
  --val-fraction 0.1 --seed 42

# 4. Train (uses the service default command, or override arguments)
sudo docker compose --profile train run --rm betbot-agent \
  python /workspace/AI/train/train.py --epochs 5 --batch-size 64
```

Checkpoints are written to `AI/train/checkpoints/` (`last.pt` every epoch, `best.pt` on validation accuracy improvement). Each checkpoint includes its hyperparameters and a vocabulary snapshot.

## Inference (`AI/train/infer.py`)

Standalone script: loads a checkpoint and runs the model on a single standardized hand (JSON), prints the predicted action (+ its probabilities), and if the predicted action is `bet` / `raise`, also prints the predicted size bucket.

```bash
# from a file
python AI/train/infer.py --checkpoint AI/train/checkpoints/best.pt --input my_hand.json

# from stdin
head -1 AI/Training/data/processed/test.jsonl | python AI/train/infer.py --checkpoint AI/train/checkpoints/best.pt --input -

# via docker
docker compose --profile train run --rm betbot-agent \
  python /workspace/AI/train/infer.py --checkpoint /workspace/AI/train/checkpoints/best.pt --input -
```

The checkpoint carries its own config and vocabulary snapshot; `infer.py` remains independent of `train.py` / the training loop and compares the checkpoint snapshot to the current runtime config.

## Turn detection (`ScreenScraper/turn_detector.py`)

The "Check" button changes color (blue → red) when it is the hero's turn — a direct visual signal, much faster and more reliable than inferring "it's my turn" from OCR text.

**Calibration required**: the red/blue classification thresholds (`BETBOT_TURN_MIN_RED=110`, `BETBOT_TURN_RED_MARGIN=25` by default in `ScreenScraper/turn_detector.py`) are an important tuning point and may need adjustment depending on the poker client or display settings.

## Live inference (`AI/train/watch_and_infer.py` + `agent-serve` service)

It watches `data/output/turn_signal.json` and triggers a prediction as soon as it becomes `true`, using the latest known hero hand state from `data/output/poker_states.jsonl` to feed the model.

The `agent-serve` service (`profiles: ["serve"]`, `restart: unless-stopped`) reuses the `Dockerfile.ia` image already built for training, but runs on CPU (a single prediction is enough for a normal live session).

**Preferred usage**: one terminal per service, each showing live raw logs (`Ctrl+C` to stop that specific service):

```bash
# Terminal 1
sudo docker compose up paddleocr-vlm-server

# Terminal 2
sudo docker compose up screenscraper

# Terminal 3
sudo docker compose --profile serve up agent-serve
```

Once ready to play, in a 4th terminal (the other three are occupied by logs):

```bash
sudo docker compose --profile serve exec agent-serve touch /workspace/data/output/start_serving.flag
```

Alternative all-in-one (fewer terminals, mixed logs):

```bash
sudo docker compose --profile serve up -d
sudo docker compose --profile serve logs -f agent-serve
```

The `screenscraper` container is untouched (no torch in it): `agent-serve` reads only `poker_states.jsonl`, with no direct coupling between the two services. Every trigger creates a fresh inference request based on the latest hand state.

### Startup cleanup

`agent-serve` completely clears `data/output/` as soon as it starts (even before loading the model), so it always begins from a clean state at each session. This is what prevents stale detection artifacts from previous runs.

⚠️ **Important**: `agent-serve` has `restart: unless-stopped`. If it crashes and restarts automatically during a session, it will also erase the hands captured since the last restart.

### On-demand startup

`agent-serve` loads the model when the container starts and then waits for an explicit signal before starting to monitor, so it does not trigger before the game begins. This is the intended behavior.

```bash
sudo docker compose --profile serve exec agent-serve touch /workspace/data/output/start_serving.flag
```

The signal is consumed (the file is deleted) as soon as it is seen, so every container restart requires a new signal — there is no need to remove it manually between sessions. This ensures the agent starts only when explicitly requested.

## GPU (AMD RX 7700 XT / ROCm)

`Dockerfile.ia` is based on the official `rocm/pytorch:latest` image (torch already compiled for ROCm), and `docker-compose.yml` passes `/dev/kfd` + `/dev/dri` to the `betbot-agent` container. The RX 7700 XT is the expected target GPU.

After `docker compose --profile train build betbot-agent`, verify that the GPU is detected before launching a full training run:

```bash
docker compose --profile train run --rm betbot-agent \
  python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else None)"
```

If it prints `False`, the passthrough or GFX override is not working on this machine — fall back to `--device cpu` until fixed.

**Permission note**: Docker containers run as root; if `sudo docker compose` has already written into `AI/Training/data/` or `AI/train/checkpoints/`, those files belong to root and may cause permission issues for the host user.

