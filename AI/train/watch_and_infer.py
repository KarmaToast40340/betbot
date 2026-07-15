#!/usr/bin/env python3
"""Watch data/output/turn_signal.json (a color-based "is it hero's turn"
signal written continuously by the screenscraper service, see
ScreenScraper/turn_detector.py) and, when it fires, run the trained model
on the latest known hand state from data/output/poker_states.jsonl —
printing the suggestion and writing it to data/output/latest_prediction.json.

turn_signal.json is a direct visual signal (the Check button's color) and
much faster/more reliable than inferring "hero's turn" from the parsed
hand-history text (that text-log heuristic used to be the primary trigger
here; kept below only as a defensive guard against acting on a stale/
misfired color signal after hero has already folded or the hand ended).

On startup, data/output/ is wiped clean by default (see clear_output_dir) so
no hand from a previous session can ever resurface — pass --keep-output to
disable this.

Usage (normally via the `agent-serve` docker-compose service):
    python watch_and_infer.py [--checkpoint PATH] [--device cpu] [--poll-interval 1.0]
"""
import argparse
import json
import os
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import normalizer  # noqa: E402

from infer import load_model, predict  # noqa: E402

AI_DIR = os.environ.get("BETBOT_AI_DIR", "AI")
DATA_DIR = os.environ.get("BETBOT_DATA_DIR", os.path.join(AI_DIR, "..", "data"))
DEFAULT_OUTPUT_DIR = os.path.join(DATA_DIR, "output")
DEFAULT_STATE_LOG_PATH = os.path.join(DATA_DIR, "output", "poker_states.jsonl")
DEFAULT_TURN_SIGNAL_PATH = os.path.join(DATA_DIR, "output", "turn_signal.json")
DEFAULT_PREDICTION_PATH = os.path.join(DATA_DIR, "output", "latest_prediction.json")
DEFAULT_START_SIGNAL_PATH = os.path.join(DATA_DIR, "output", "start_serving.flag")
DEFAULT_CHECKPOINT_PATH = os.path.join(AI_DIR, "train", "checkpoints", "best.pt")
DEFAULT_HERO_NAME = os.environ.get("BETBOT_HERO_NAME", "Karmatoast40")


def clear_output_dir(output_dir):
    # Wipes data/output/ at startup so a leftover hand from a previous,
    # long-abandoned session can never resurface (this is exactly what
    # caused the earlier stale-hand bug — find_latest_hand only fixes it
    # while poker_states.jsonl exists across restarts; starting from a
    # clean slate removes the failure mode entirely). Only screenscraper
    # and agent-serve write here, and both regenerate everything they need
    # from scratch, so nothing of lasting value lives in this directory.
    if not os.path.isdir(output_dir):
        return
    for name in os.listdir(output_dir):
        path = os.path.join(output_dir, name)
        try:
            if os.path.isdir(path):
                shutil.rmtree(path)
            else:
                os.remove(path)
        except OSError as e:
            print(f"[cleanup] failed to remove {path}: {e}")
    print(f"Cleared {output_dir}")


def parse_args():
    parser = argparse.ArgumentParser(description="Live inference watcher, gated on the turn-signal color check")
    parser.add_argument("--state-log", default=DEFAULT_STATE_LOG_PATH)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--turn-signal-path", default=DEFAULT_TURN_SIGNAL_PATH)
    parser.add_argument("--prediction-path", default=DEFAULT_PREDICTION_PATH)
    parser.add_argument("--start-signal-path", default=DEFAULT_START_SIGNAL_PATH)
    parser.add_argument("--checkpoint", default=DEFAULT_CHECKPOINT_PATH)
    parser.add_argument("--hero-name", default=DEFAULT_HERO_NAME)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--poll-interval", type=float, default=1.0)
    parser.add_argument("--keep-output", action="store_true",
                         help="Don't clear data/output/ on startup (it's cleared by default)")
    parser.add_argument("--auto-start", action="store_true",
                         help="Skip waiting for the start-signal file (useful for testing)")
    return parser.parse_args()


def wait_for_start_signal(path, poll_interval):
    # Consume-once: delete the flag after seeing it, so every fresh
    # container start (docker compose up/restart) requires a new explicit
    # "ready" signal rather than remembering it was already armed once.
    if os.path.exists(path):
        os.remove(path)
        return
    print(f"Waiting for start signal — run this when you're ready to begin watching:")
    print(f"  docker compose --profile serve exec agent-serve touch {path}")
    while not os.path.exists(path):
        time.sleep(poll_interval)
    try:
        os.remove(path)
    except FileNotFoundError:
        pass
    print("Start signal received, watching now.")


def load_jsonl(path):
    if not os.path.exists(path):
        return []
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def load_turn_signal(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"hero_turn": False}


def hero_already_out(state, hero_name):
    # Guard against acting on a stale/misfired color signal: skip if the
    # hand is resolved or hero has already folded, per the parsed text log.
    if state.get("current_street") == "showdown":
        return True
    actions = state.get("actions") or []
    return any(a.get("player") == hero_name and a.get("action") == "fold" for a in actions)


def find_latest_hand(states, hero_name):
    candidates = [s for s in states if hero_name in {p.get("name") for p in s.get("players") or []}]
    if not candidates:
        return None
    candidates.sort(key=lambda s: s.get("timestamp_utc") or "")
    return candidates[-1]


def decision_signature(state):
    return (state.get("hand_id"), state.get("current_street"), len(state.get("actions") or []))


def format_summary(active, result):
    line = f"[{active.get('hand_id')}] {active.get('current_street')} -> {result['action']}"
    prob = result["action_probabilities"].get(result["action"])
    if prob is not None:
        line += f" ({prob:.2f})"
    if "amount_bb_estimate" in result:
        line += f", size~{result['amount_bb_estimate']}bb ({result['amount_bb_range']})"
    return line


def main():
    args = parse_args()

    if not args.keep_output:
        clear_output_dir(args.output_dir)

    model, checkpoint = load_model(args.checkpoint, device=args.device)
    print(f"Loaded checkpoint epoch={checkpoint.get('epoch')} val_accuracy={checkpoint.get('val_accuracy')}")

    if not args.auto_start:
        wait_for_start_signal(args.start_signal_path, args.poll_interval)

    print(f"Watching {args.turn_signal_path} (poll every {args.poll_interval}s)...")

    last_signature = None

    while True:
        turn_signal = load_turn_signal(args.turn_signal_path)
        if turn_signal.get("hero_turn"):
            states = load_jsonl(args.state_log)
            active = find_latest_hand(states, args.hero_name)

            if active is not None and not hero_already_out(active, args.hero_name):
                sig = decision_signature(active)
                if sig != last_signature:
                    hero_cards = (active.get("hero") or {}).get("hole_cards_raw") or []
                    if len(hero_cards) < 2:
                        # Deliberately don't update last_signature here: the
                        # signature (hand_id/street/action count) may not
                        # change between "cards not captured yet" and "cards
                        # now captured" for the same decision point, so keep
                        # retrying each tick rather than getting stuck.
                        print(f"[{active.get('hand_id')}] {active.get('current_street')} "
                              f"-> hero's turn but hole cards not captured yet, skipping")
                    else:
                        last_signature = sig
                        standardized = normalizer.standardize_record(active)
                        result = predict(model, standardized, device=args.device)
                        result["hand_id"] = active.get("hand_id")
                        result["street"] = active.get("current_street")
                        print(format_summary(active, result))
                        with open(args.prediction_path, "w", encoding="utf-8") as f:
                            json.dump(result, f, ensure_ascii=False, indent=2)

        time.sleep(args.poll_interval)


if __name__ == "__main__":
    main()
