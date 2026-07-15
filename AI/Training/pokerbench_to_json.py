#!/usr/bin/env python3
import csv
import json
import re
import sys
from pathlib import Path

POSITIONS = {"UTG", "UTG+1", "UTG+2", "LJ", "HJ", "CO", "BTN", "SB", "BB", "OOP", "IP"}
RANKS = set("23456789TJQKA")


def to_float_or_none(value):
    try:
        return float(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def normalize_action_name(name):
    name = (name or "").strip().lower()
    mapping = {
        "fold": "fold",
        "call": "call",
        "check": "check",
        "allin": "all_in",
        "all-in": "all_in",
        "all_in": "all_in",
        "bet": "bet",
        "raise": "raise",
    }
    return mapping.get(name, name)


def extract_rank(token):
    if token is None:
        return None
    s = str(token).strip().upper()
    if not s:
        return None
    s = s.replace("♠", "").replace("♥", "").replace("♦", "").replace("♣", "")
    if len(s) >= 2 and s[:2] == "10":
        return "T"
    ch = s[0]
    return ch if ch in RANKS else None


def split_hole_cards_rank_only(s):
    s = (s or "").strip()
    parts = re.findall(r"10|[2-9TJQKA][shdc♠♥♦♣]?", s, flags=re.IGNORECASE)
    ranks = []
    for p in parts:
        r = extract_rank(p)
        if r:
            ranks.append(r)
    return ranks[:2]


def split_flop_rank_only(s):
    s = (s or "").strip()
    parts = re.findall(r"10|[2-9TJQKA][shdc♠♥♦♣]?", s, flags=re.IGNORECASE)
    ranks = []
    for p in parts:
        r = extract_rank(p)
        if r:
            ranks.append(r)
    return ranks[:3]


def parse_bb_token(token):
    token = (token or "").strip().lower()
    if token.endswith("bb"):
        try:
            return float(token[:-2])
        except ValueError:
            return None
    return None


def parse_action_with_optional_amount(raw):
    raw = (raw or "").strip()
    if not raw:
        return None, None
    m = re.match(r"(?i)^(fold|call|check|allin|all-in|all_in|bet|raise)\s*(\d+(?:\.\d+)?)?$", raw)
    if m:
        action = normalize_action_name(m.group(1))
        amount = to_float_or_none(m.group(2))
        return action, amount
    # PokerBench encodes preflop raises as a bare size with no keyword, e.g.
    # "3.0bb" instead of "raise 3.0bb" — treat any bare "X.Xbb" as a raise.
    bare_amount = parse_bb_token(raw)
    if bare_amount is not None:
        return "raise", bare_amount
    return normalize_action_name(raw.split()[0]), to_float_or_none(raw.split()[1]) if len(raw.split()) > 1 else None


def parse_preflop_line(prev_line):
    tokens = [t.strip() for t in (prev_line or "").split("/") if t.strip()]
    actions = []
    i = 0
    while i < len(tokens) - 1:
        player = tokens[i]
        nxt = tokens[i + 1]
        if player not in POSITIONS:
            i += 1
            continue
        amt = parse_bb_token(nxt)
        if amt is not None:
            actions.append({"player": player, "action": "raise", "amount_bb": amt})
            i += 2
            continue
        low = nxt.lower()
        if low in {"fold", "call", "check", "allin", "all-in", "all_in"}:
            actions.append({"player": player, "action": normalize_action_name(low), "amount_bb": None})
            i += 2
            continue
        i += 1
    return actions


def parse_postflop_line(line):
    actions = []
    parts = [p.strip() for p in (line or "").split("/") if p.strip()]
    for part in parts:
        sub = [x.strip() for x in part.split("_") if x.strip()]
        if len(sub) < 2:
            continue
        player = sub[0]
        action_raw = sub[1]
        amount = None
        if len(sub) >= 3:
            amount = to_float_or_none(sub[2])
        actions.append({
            "player": player,
            "action": normalize_action_name(action_raw),
            "amount_bb": amount,
        })
    return actions


def make_empty_actions():
    return {"preflop": [], "flop": [], "turn": [], "river": []}


def detect_preflop_columns(fieldnames):
    fields = set(fieldnames or [])
    return {"prev_line", "hero_pos", "hero_holding"}.issubset(fields)


def detect_postflop_columns(fieldnames):
    fields = set(fieldnames or [])
    return {"holding", "postflop_action"}.issubset(fields)


def convert_preflop_row(row, idx):
    hero_pos = (row.get("hero_pos") or row.get("hero_position") or "hero").strip()
    hero_holding = row.get("hero_holding") or row.get("holding") or ""
    correct_decision = (row.get("correct_decision") or row.get("output") or "").strip()
    label_action, label_amount = parse_action_with_optional_amount(correct_decision)

    return {
        "source": "pokerbench",
        "hand_id": row.get("hand_id") or f"pokerbench_preflop_{idx}",
        "num_players": int(row["num_players"]) if row.get("num_players") not in (None, "") else None,
        "blinds": {"sb": None, "bb": 1.0},
        "pot_bb": to_float_or_none(row.get("pot_size")),
        "hero": {
            "name": hero_pos,
            "cards_dealt": split_hole_cards_rank_only(hero_holding),
        },
        "board": {"flop": [], "turn": None, "river": None},
        "actions": {
            "preflop": parse_preflop_line(row.get("prev_line") or row.get("preflop_action")),
            "flop": [],
            "turn": [],
            "river": [],
        },
        "label": {
            "player": hero_pos,
            "action": label_action,
            "amount_bb": label_amount,
        },
    }


def convert_postflop_row(row, idx):
    street = (row.get("evaluation_at") or row.get("street") or "flop").strip().lower()
    hero_pos = (row.get("hero_position") or row.get("hero_pos") or "hero").strip()
    holding = row.get("holding") or row.get("hero_holding") or ""
    correct_decision = (row.get("correct_decision") or row.get("output") or "").strip()
    label_action, label_amount = parse_action_with_optional_amount(correct_decision)

    record = {
        "source": "pokerbench",
        "hand_id": row.get("hand_id") or f"pokerbench_postflop_{idx}",
        "num_players": int(row["num_players"]) if row.get("num_players") not in (None, "") else 2,
        "blinds": {"sb": None, "bb": 1.0},
        "pot_bb": to_float_or_none(row.get("pot_size")),
        "hero": {
            "name": hero_pos,
            "cards_dealt": split_hole_cards_rank_only(holding),
        },
        "board": {
            "flop": split_flop_rank_only(row.get("board_flop")),
            "turn": extract_rank(row.get("board_turn")),
            "river": extract_rank(row.get("board_river")),
        },
        "actions": make_empty_actions(),
        "label": {
            "player": hero_pos,
            "action": label_action,
            "amount_bb": label_amount,
        },
    }

    record["actions"]["preflop"] = parse_preflop_line(row.get("preflop_action"))
    parsed_post = parse_postflop_line(row.get("postflop_action"))

    if street == "flop":
        record["actions"]["flop"] = parsed_post
    elif street == "turn":
        record["actions"]["turn"] = parsed_post
    elif street == "river":
        record["actions"]["river"] = parsed_post
    else:
        record["actions"]["flop"] = parsed_post

    return record


def convert_csv(input_csv, output_jsonl, mode="auto"):
    count = 0
    Path(output_jsonl).parent.mkdir(parents=True, exist_ok=True)
    with open(input_csv, "r", encoding="utf-8") as fin, open(output_jsonl, "w", encoding="utf-8") as fout:
        reader = csv.DictReader(fin)
        fieldnames = reader.fieldnames or []
        inferred_mode = mode
        if mode == "auto":
            if detect_preflop_columns(fieldnames):
                inferred_mode = "preflop"
            elif detect_postflop_columns(fieldnames):
                inferred_mode = "postflop"
            else:
                raise ValueError(f"Unable to infer mode from columns: {fieldnames}")

        for idx, row in enumerate(reader, start=1):
            if inferred_mode == "preflop":
                record = convert_preflop_row(row, idx)
            elif inferred_mode == "postflop":
                record = convert_postflop_row(row, idx)
            else:
                raise ValueError("mode must be auto, preflop, or postflop")
            fout.write(json.dumps(record, ensure_ascii=False) + "\n")
            count += 1
    print(f"Done. Mode={inferred_mode}. Wrote {count} records.")


if __name__ == "__main__":
    if len(sys.argv) not in {3, 4}:
        print("Usage: python pokerbench_to_standard_jsonl_rank_only.py <input.csv> <output.jsonl> [auto|preflop|postflop]")
        sys.exit(1)
    input_csv = Path(sys.argv[1])
    output_jsonl = Path(sys.argv[2])
    mode = sys.argv[3] if len(sys.argv) == 4 else "auto"
    convert_csv(input_csv, output_jsonl, mode=mode)