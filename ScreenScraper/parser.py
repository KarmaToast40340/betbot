import re
from datetime import datetime
from pathlib import Path

from config import ACTION_PATTERNS, STREETS, SUIT_MAP


def clean_text(text: str) -> str:
    text = text.replace("\r", "\n")
    text = re.sub(r"<div.*?</div>", "", text, flags=re.DOTALL)
    text = re.sub(r"<img.*?>", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def split_lines(text: str):
    return [line.strip() for line in text.splitlines() if line.strip()]


def parse_hand_id(lines):
    for line in lines:
        m = re.match(r"Hand\s+(.+)", line, flags=re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return None


def parse_blinds(text: str):
    sb = None
    bb = None
    m_sb = re.search(r"Post small blind.*?\(?([0-9]+(?:\.[0-9]+)?)\s*BB\)?", text, flags=re.IGNORECASE | re.DOTALL)
    if m_sb:
        sb = float(m_sb.group(1))
    m_bb = re.search(r"Post big blind.*?\(?([0-9]+(?:\.[0-9]+)?)\s*BB\)?", text, flags=re.IGNORECASE | re.DOTALL)
    if m_bb:
        bb = float(m_bb.group(1))
    return {"sb": sb, "bb": bb}


def parse_hero_cards(lines):
    if "CARDS DEALT" in lines:
        idx = lines.index("CARDS DEALT")
        cards = []
        for line in lines[idx + 1: idx + 6]:
            tokens = re.findall(r"\b([AKQJT2-9]|10)\b", line.upper())
            cards.extend(tokens)
            if len(cards) >= 2:
                break
        return [c.replace("10", "T") for c in cards[:2]]
    return []


def parse_board(lines):
    board = {"flop": [], "turn": None, "river": None, "all_cards": []}
    for i, line in enumerate(lines):
        if line == "FLOP" and i + 1 < len(lines):
            flop_cards = re.findall(r"[AKQJT2-9]|10", lines[i + 1].upper().replace(" ", ""))
            board["flop"] = [c.replace("10", "T") for c in flop_cards[:3]]
        elif line == "TURN" and i + 1 < len(lines):
            tokens = re.findall(r"[AKQJT2-9]|10", lines[i + 1].upper())
            tokens = [c.replace("10", "T") for c in tokens]
            if len(tokens) >= 4:
                board["turn"] = tokens[3]
        elif line == "RIVER" and i + 1 < len(lines):
            raw = lines[i + 1]
            ranks = re.findall(r"[AKQJT2-9]|10", raw.upper())
            ranks = [c.replace("10", "T") for c in ranks]
            suit = None
            for k, v in SUIT_MAP.items():
                if k in raw:
                    suit = v
            if len(ranks) >= 5:
                board["river"] = ranks[4] + (suit or "")
    board["all_cards"] = board["flop"][:]
    if board["turn"]:
        board["all_cards"].append(board["turn"])
    if board["river"]:
        board["all_cards"].append(board["river"])
    return board


def is_probable_player_name(line: str):
    if not line:
        return False
    banned = {"CARDS DEALT", "PRE-FLOP", "FLOP", "TURN", "RIVER", "SHOWDOWN", "CHECK", "FOLD"}
    if line.upper() in banned:
        return False
    if re.search(r"\b(BB|SB)\b", line.upper()):
        return False
    if re.search(r"POST|CALLS|BETS|RAISES|TRIPS", line.upper()):
        return False
    if re.fullmatch(r"[AKQJT2-9\s♥♦♣♠]+", line.upper()):
        return False
    return True


def collect_player_names(lines):
    names = []
    seen = set()
    for line in lines:
        if is_probable_player_name(line):
            key = line.lower()
            if key not in seen:
                seen.add(key)
                names.append(line)
    return names


def canonicalize_name(name, known_players):
    n = name.lower()
    for p in known_players:
        if p.lower() == n:
            return p
    for p in known_players:
        if p.lower().replace("0", "o") == n.replace("0", "o"):
            return p
    return name


def parse_actions(lines, players):
    actions = []
    current_street = None
    last_player = None
    for line in lines:
        upper = line.upper()
        if upper in STREETS:
            current_street = upper.lower().replace("-", "")
            continue
        if is_probable_player_name(line):
            last_player = canonicalize_name(line, players)
            continue
        for action_name, pattern in ACTION_PATTERNS:
            m = re.search(pattern, line, flags=re.IGNORECASE)
            if m:
                amount = 0.0
                if m.groups():
                    try:
                        amount = float(m.group(1))
                    except ValueError:
                        amount = 0.0
                actions.append({
                    "street": current_street,
                    "player": last_player,
                    "action": action_name,
                    "amount_bb": amount,
                    "raw": line,
                })
                break
    return actions


def parse_showdown(lines, players):
    if "SHOWDOWN" not in lines:
        return None
    idx = lines.index("SHOWDOWN")
    block = lines[idx + 1: idx + 8]
    player = None
    made_hand = None
    for line in block:
        if is_probable_player_name(line):
            player = canonicalize_name(line, players)
        elif ":" in line:
            made_hand = line
    return {"player": player, "made_hand": made_hand}


def infer_current_street(board, showdown):
    if showdown and showdown.get("made_hand"):
        return "showdown"
    if board.get("river"):
        return "river"
    if board.get("turn"):
        return "turn"
    if board.get("flop"):
        return "flop"
    return "preflop"


def parse_poker_ocr_text(raw_text: str, image_path: Path):
    raw_text = clean_text(raw_text)
    lines = split_lines(raw_text)
    players = collect_player_names(lines)
    hero_name = "Karmatoast40" if "Karmatoast40" in players else None
    board = parse_board(lines)
    showdown = parse_showdown(lines, players)
    actions = parse_actions(lines, players)
    return {
        "timestamp_utc": datetime.utcnow().isoformat() + "Z",
        "source_image": image_path.name,
        "hand_id": parse_hand_id(lines),
        "blinds": parse_blinds(raw_text),
        "hero": {"name": hero_name, "hole_cards_raw": parse_hero_cards(lines)},
        "players": [{"name": p} for p in players],
        "board": board,
        "current_street": infer_current_street(board, showdown),
        "actions": actions,
        "showdown": showdown,
        "raw_text": raw_text,
    }
