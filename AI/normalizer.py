#!/usr/bin/env python3
import json
import sys
from pathlib import Path

ACTION_MAP = {
    "raises": "raise",
    "raise": "raise",
    "bets": "bet",
    "bet": "bet",
    "calls": "call",
    "call": "call",
    "checks": "check",
    "check": "check",
    "folds": "fold",
    "fold": "fold",
    "all-in": "all_in",
    "all_in": "all_in",
    "post_small_blind": "post_sb",
    "post_big_blind": "post_bb",
}

VALID_STREETS = {"preflop", "flop", "turn", "river"}

def normalize_action_name(name):
    if not name:
        return None
    return ACTION_MAP.get(name.strip().lower(), name.strip().lower())

def normalize_cards(cards):
    if not cards:
        return []
    return [str(c).strip() for c in cards if c is not None and str(c).strip()]

def normalize_board(board):
    board = board or {}
    flop = normalize_cards(board.get("flop", []))[:3]
    turn = board.get("turn")
    river = board.get("river")
    turn = str(turn).strip() if turn not in (None, "") else None
    river = str(river).strip() if river not in (None, "") else None
    return {
        "flop": flop,
        "turn": turn,
        "river": river,
    }

def extract_cards_dealt(record):
    hero = record.get("hero", {}) or {}
    cards = hero.get("hole_cards_raw", []) or []
    return normalize_cards(cards)[:2]

def normalize_actions(actions):
    out = {
        "preflop": [],
        "flop": [],
        "turn": [],
        "river": [],
    }

    for a in actions or []:
        street = (a.get("street") or "").strip().lower()
        if street not in VALID_STREETS:
            continue

        action = normalize_action_name(a.get("action"))
        if action in (None, "wins"):
            continue

        amount = a.get("amount_bb")
        try:
            amount = float(amount) if amount is not None else None
        except (TypeError, ValueError):
            amount = None

        out[street].append({
            "player": a.get("player"),
            "action": action,
            "amount_bb": amount,
        })

    return out

def standardize_record(record):
    players = record.get("players", []) or []
    hero = record.get("hero", {}) or {}

    return {
        "source": "ocr",
        "hand_id": record.get("hand_id"),
        "num_players": len(players),
        "blinds": {
            "sb": float(record.get("blinds", {}).get("sb")) if record.get("blinds", {}).get("sb") is not None else None,
            "bb": float(record.get("blinds", {}).get("bb")) if record.get("blinds", {}).get("bb") is not None else None,
        },
        "hero": {
            "name": hero.get("name"),
            "cards_dealt": extract_cards_dealt(record),
        },
        "board": normalize_board(record.get("board")),
        "actions": normalize_actions(record.get("actions", [])),
    }

def convert_jsonl(input_path, output_path):
    count_in = 0
    count_out = 0

    with open(input_path, "r", encoding="utf-8") as fin, open(output_path, "w", encoding="utf-8") as fout:
        for line in fin:
            line = line.strip()
            if not line:
                continue

            count_in += 1
            try:
                record = json.loads(line)
                normalized = standardize_record(record)
                fout.write(json.dumps(normalized, ensure_ascii=False) + "\n")
                count_out += 1
            except Exception as e:
                print(f"[WARN] line {count_in}: {e}", file=sys.stderr)

    print(f"Done. Read {count_in} records, wrote {count_out} records.")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python normalize_ocr_jsonl.py input.jsonl output.jsonl")
        sys.exit(1)

    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])
    convert_jsonl(input_path, output_path)