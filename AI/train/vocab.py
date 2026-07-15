#!/usr/bin/env python3
"""Static token vocabulary + record -> token id sequence encoding.

Token/label ids are fixed and enumerated in this file. A snapshot of the
mappings is embedded in every training checkpoint (see export_snapshot)
so a future standalone inference script never needs to import this module.
"""
import bisect

PAD = "<PAD>"
UNK = "<UNK>"
HOLE = "<HOLE>"
BOARD = "<BOARD>"

STREET_PREFLOP = "<STREET_PREFLOP>"
STREET_FLOP = "<STREET_FLOP>"
STREET_TURN = "<STREET_TURN>"
STREET_RIVER = "<STREET_RIVER>"

HERO = "<HERO>"
OPP = "<OPP>"

NUM_PLAYERS_MIN = 2
NUM_PLAYERS_MAX = 9
NUM_PLAYERS_UNK = "<NUM_PLAYERS_UNK>"

# PokerBench's preflop CSV gives hero_pos as a concrete position (BB/SB/BTN/
# HJ/CO/UTG...); its postflop CSV (heads-up only) instead gives hero_position
# as always "IP" or "OOP" (verified against the real dataset), and
# postflop_action player tokens use that same IP/OOP labeling. Both are kept
# as valid hero-position tokens so postflop in-position/out-of-position
# information isn't thrown away as UNK.
HERO_POSITIONS = ["UTG", "UTG+1", "UTG+2", "LJ", "HJ", "CO", "BTN", "SB", "BB", "IP", "OOP"]
HERO_POS_UNK = "<HERO_POS_UNK>"

RANK_ORDER = "23456789TJQKA"

ACTION_NAMES = ["fold", "check", "call", "bet", "raise", "all_in"]
ACTION_TOKEN_MAP = {
    "fold": "<ACT_FOLD>",
    "check": "<ACT_CHECK>",
    "call": "<ACT_CALL>",
    "bet": "<ACT_BET>",
    "raise": "<ACT_RAISE>",
    "all_in": "<ACT_ALLIN>",
    # Never emitted by PokerBench, but already produced by AI/normalizer.py
    # on the OCR side. Reserved now to avoid a vocab migration later.
    "post_sb": "<ACT_POST_SB>",
    "post_bb": "<ACT_POST_BB>",
}

AMOUNT_BUCKET_EDGES = [1, 2, 4, 7, 12, 20, 35, 60, 100]
NUM_AMOUNT_BUCKETS = len(AMOUNT_BUCKET_EDGES) + 1

# Pot size reuses the same bucket edges as bet/raise amounts (same unit, bb) —
# a distinct token namespace so the model can tell "this is the pot" apart
# from "this is a bet size" even though the underlying buckets are identical.
POT_UNK = "<POT_UNK>"

MAX_SEQ_LEN = 64

LABEL2ID = {name: i for i, name in enumerate(ACTION_NAMES)}
ID2LABEL = {i: name for name, i in LABEL2ID.items()}


def _build_vocab():
    tokens = [PAD, UNK, HOLE, BOARD]
    tokens += [STREET_PREFLOP, STREET_FLOP, STREET_TURN, STREET_RIVER]
    tokens += [HERO, OPP]
    tokens += [f"<NUM_PLAYERS_{n}>" for n in range(NUM_PLAYERS_MIN, NUM_PLAYERS_MAX + 1)]
    tokens += [NUM_PLAYERS_UNK]
    tokens += [f"<HERO_POS_{pos}>" for pos in HERO_POSITIONS]
    tokens += [HERO_POS_UNK]
    tokens += [f"<RANK_{r}>" for r in RANK_ORDER]
    tokens += list(ACTION_TOKEN_MAP.values())
    tokens += [f"<AMT_BUCKET_{i}>" for i in range(NUM_AMOUNT_BUCKETS)]
    tokens += [f"<POT_BUCKET_{i}>" for i in range(NUM_AMOUNT_BUCKETS)]
    tokens += [POT_UNK]
    return tokens


_ALL_TOKENS = _build_vocab()
TOKEN_TO_ID = {t: i for i, t in enumerate(_ALL_TOKENS)}
ID_TO_TOKEN = {i: t for t, i in TOKEN_TO_ID.items()}
VOCAB_SIZE = len(_ALL_TOKENS)

_NUM_PLAYERS_TOKEN_ID = {
    n: TOKEN_TO_ID[f"<NUM_PLAYERS_{n}>"] for n in range(NUM_PLAYERS_MIN, NUM_PLAYERS_MAX + 1)
}
_HERO_POS_TOKEN_ID = {pos: TOKEN_TO_ID[f"<HERO_POS_{pos}>"] for pos in HERO_POSITIONS}
_RANK_TOKEN_ID = {r: TOKEN_TO_ID[f"<RANK_{r}>"] for r in RANK_ORDER}
_ACTION_TOKEN_ID = {name: TOKEN_TO_ID[tok] for name, tok in ACTION_TOKEN_MAP.items()}
_AMOUNT_BUCKET_TOKEN_ID = [TOKEN_TO_ID[f"<AMT_BUCKET_{i}>"] for i in range(NUM_AMOUNT_BUCKETS)]
_POT_BUCKET_TOKEN_ID = [TOKEN_TO_ID[f"<POT_BUCKET_{i}>"] for i in range(NUM_AMOUNT_BUCKETS)]


def bucket_amount(amount_bb):
    return bisect.bisect_right(AMOUNT_BUCKET_EDGES, amount_bb)


def pot_bucket_token(pot_bb):
    if pot_bb is None:
        return TOKEN_TO_ID[POT_UNK]
    return _POT_BUCKET_TOKEN_ID[bucket_amount(pot_bb)]


def num_players_token(num_players):
    return _NUM_PLAYERS_TOKEN_ID.get(num_players, TOKEN_TO_ID[NUM_PLAYERS_UNK])


def hero_position_token(hero_name):
    return _HERO_POS_TOKEN_ID.get(hero_name, TOKEN_TO_ID[HERO_POS_UNK])


def rank_token(rank):
    return _RANK_TOKEN_ID.get(rank, TOKEN_TO_ID[UNK])


def encode_action(action, hero_name):
    # Preflop actions use concrete positions (matching hero.name directly);
    # postflop actions use IP/OOP labels, which is also what hero.name is set
    # to for postflop records — so plain equality resolves both correctly.
    # The one known gap: preflop-history actions embedded inside a postflop
    # record still use concrete positions while hero.name is IP/OOP there,
    # so those specific actions fall back to OPP even when they were the
    # hero's own. Not resolvable without the aggressor_position column,
    # which pokerbench_to_json.py doesn't carry through (out of scope here).
    role = TOKEN_TO_ID[HERO] if action.get("player") == hero_name else TOKEN_TO_ID[OPP]

    act_token = _ACTION_TOKEN_ID.get(action.get("action"), TOKEN_TO_ID[UNK])
    out = [role, act_token]

    amount = action.get("amount_bb")
    if amount is not None:
        out.append(_AMOUNT_BUCKET_TOKEN_ID[bucket_amount(amount)])
    return out


def encode_record(record):
    hero = record.get("hero") or {}
    hero_name = hero.get("name")
    actions = record.get("actions") or {}
    board = record.get("board") or {}

    tokens = [
        num_players_token(record.get("num_players")),
        hero_position_token(hero_name),
        pot_bucket_token(record.get("pot_bb")),
        TOKEN_TO_ID[HOLE],
    ]
    for r in (hero.get("cards_dealt") or [])[:2]:
        tokens.append(rank_token(r))

    tokens.append(TOKEN_TO_ID[STREET_PREFLOP])
    for a in actions.get("preflop") or []:
        tokens.extend(encode_action(a, hero_name))

    flop = board.get("flop") or []
    if flop:
        tokens.append(TOKEN_TO_ID[STREET_FLOP])
        tokens.append(TOKEN_TO_ID[BOARD])
        for r in flop[:3]:
            tokens.append(rank_token(r))
        for a in actions.get("flop") or []:
            tokens.extend(encode_action(a, hero_name))

    turn = board.get("turn")
    if turn:
        tokens.append(TOKEN_TO_ID[STREET_TURN])
        tokens.append(TOKEN_TO_ID[BOARD])
        tokens.append(rank_token(turn))
        for a in actions.get("turn") or []:
            tokens.extend(encode_action(a, hero_name))

    river = board.get("river")
    if river:
        tokens.append(TOKEN_TO_ID[STREET_RIVER])
        tokens.append(TOKEN_TO_ID[BOARD])
        tokens.append(rank_token(river))
        for a in actions.get("river") or []:
            tokens.extend(encode_action(a, hero_name))

    return tokens[:MAX_SEQ_LEN]


def encode_label(record):
    return LABEL2ID[record["label"]["action"]]


# Only bet/raise carry a meaningful sizing decision — all_in is implicitly
# "whatever's left in the stack", fold/check/call have no amount at all.
SIZING_ACTIONS = {"bet", "raise"}


def needs_amount_label(record):
    return (record.get("label") or {}).get("action") in SIZING_ACTIONS


def encode_amount_label(record):
    amount = (record.get("label") or {}).get("amount_bb")
    if amount is None:
        return 0
    return bucket_amount(amount)


def format_amount_bucket(bucket_id):
    edges = AMOUNT_BUCKET_EDGES
    if bucket_id == 0:
        return f"<{edges[0]}bb", edges[0] / 2
    if bucket_id >= len(edges):
        return f">={edges[-1]}bb", float(edges[-1])
    lo, hi = edges[bucket_id - 1], edges[bucket_id]
    return f"{lo}-{hi}bb", (lo + hi) / 2


def export_snapshot():
    return {
        "token_to_id": TOKEN_TO_ID,
        "amount_bucket_edges": AMOUNT_BUCKET_EDGES,
        "num_amount_buckets": NUM_AMOUNT_BUCKETS,
        "rank_order": RANK_ORDER,
        "label_to_id": LABEL2ID,
        "max_seq_len": MAX_SEQ_LEN,
    }
