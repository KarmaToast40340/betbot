import re
from datetime import datetime
from pathlib import Path

from config import ACTION_PATTERNS, STREETS, SUIT_MAP


RANK_PATTERN = r"(10|[2-9AKQJT])"
CARD_TOKEN_PATTERN = r"(?:10|[2-9AKQJT])(?:\s*[♥♦♣♠♡♢hdcs])?"
AMOUNT_PATTERN = r"([0-9]+(?:\.[0-9]+)?)\s*BB"

PLAYER_TOKEN_BLACKLIST = {
    "CARDS DEALT",
    "PRE-FLOP",
    "FLOP",
    "TURN",
    "RIVER",
    "SHOWDOWN",
    "CHECK",
    "FOLD",
    "CALL",
    "CALLS",
    "BET",
    "BETS",
    "RAISE",
    "RAISES",
    "WINS",
    "WINS",
    "MUCKS",
    "NULL",
}

ACTION_MAP = [
    ("raise_to", r"Raises to\s+([0-9]+(?:\.[0-9]+)?)\s*BB"),
    ("bet", r"Bets\s+([0-9]+(?:\.[0-9]+)?)\s*BB"),
    ("call", r"Calls\s+([0-9]+(?:\.[0-9]+)?)\s*BB"),
    ("post_small_blind", r"Post small blind.*?\(?([0-9]+(?:\.[0-9]+)?)\s*BB\)?"),
    ("post_big_blind", r"Post big blind.*?\(?([0-9]+(?:\.[0-9]+)?)\s*BB\)?"),
    ("check", r"\bCheck\b"),
    ("fold", r"\bFold\b"),
    ("mucks", r"\bMucks\b"),
    ("wins", r"\bWINS?\s+([0-9]+(?:\.[0-9]+)?)\s*BB\b"),
    ("receives", r"\bRECEIVES\s*:\s*"),
]


def clean_text(text: str) -> str:
    text = text or ""
    text = text.replace("\r", "\n")
    text = re.sub(r"<div.*?</div>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<img.*?>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", text)
    text = re.sub(r"&nbsp;", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def split_lines(text: str):
    return [line.strip() for line in text.splitlines() if line.strip()]


def normalize_rank(rank: str) -> str:
    rank = rank.upper()
    return "T" if rank == "10" else rank


def normalize_card_token(raw: str) -> str:
    raw = raw.strip()
    m = re.match(r"(10|[2-9AKQJT])(?:\s*([♥♦♣♠♡♢hdcs]))?$", raw, flags=re.IGNORECASE)
    if not m:
        return raw.upper()

    rank = normalize_rank(m.group(1))
    suit = m.group(2)
    if not suit:
        return rank

    suit = SUIT_MAP.get(suit.lower(), suit.lower())
    return f"{rank}{suit}"


def extract_card_tokens_with_suits(line: str):
    tokens = re.findall(CARD_TOKEN_PATTERN, line, flags=re.IGNORECASE)
    return [normalize_card_token(token) for token in tokens]


def extract_ranks_only(line: str):
    tokens = re.findall(RANK_PATTERN, line, flags=re.IGNORECASE)
    return [normalize_rank(token) for token in tokens]


def parse_hand_id(lines):
    for line in lines:
        m = re.match(r"Hand\s+(.+)", line, flags=re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return None


def parse_blinds(text: str):
    sb = None
    bb = None

    m_sb = re.search(
        r"Post small blind.*?\(?([0-9]+(?:\.[0-9]+)?)\s*BB\)?",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if m_sb:
        sb = float(m_sb.group(1))

    m_bb = re.search(
        r"Post big blind.*?\(?([0-9]+(?:\.[0-9]+)?)\s*BB\)?",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if m_bb:
        bb = float(m_bb.group(1))

    return {"sb": sb, "bb": bb}


def parse_hero_cards(lines):
    for i, line in enumerate(lines):
        upper = line.upper()

        if upper == "CARDS DEALT":
            cards = []
            for probe in lines[i + 1:i + 6]:
                cards.extend(extract_ranks_only(probe))
                if len(cards) >= 2:
                    return cards[:2]

        m = re.search(r"\bRECEIVES\s*:\s*(.+)$", line, flags=re.IGNORECASE)
        if m:
            cards = extract_ranks_only(m.group(1))
            if len(cards) >= 2:
                return cards[:2]

    return []


def parse_board(lines):
    board = {
        "flop": [],
        "turn": None,
        "river": None,
        "all_cards": [],
    }

    for i, line in enumerate(lines):
        upper = line.upper()

        if upper == "FLOP" and i + 1 < len(lines):
            cards = extract_card_tokens_with_suits(lines[i + 1])
            board["flop"] = cards[:3]

        elif upper == "TURN" and i + 1 < len(lines):
            cards = extract_card_tokens_with_suits(lines[i + 1])
            if len(cards) >= 4:
                board["turn"] = cards[3]

        elif upper == "RIVER" and i + 1 < len(lines):
            cards = extract_card_tokens_with_suits(lines[i + 1])
            if len(cards) >= 5:
                board["river"] = cards[4]

    board["all_cards"] = board["flop"][:]
    if board["turn"]:
        board["all_cards"].append(board["turn"])
    if board["river"]:
        board["all_cards"].append(board["river"])

    return board


def is_probable_player_name(line: str):
    if not line:
        return False

    line = line.strip()
    upper = line.upper()

    if upper in PLAYER_TOKEN_BLACKLIST:
        return False
    if upper in STREETS:
        return False
    if re.search(r"\b(BB|SB)\b", upper):
        return False
    if re.search(r"^Hand\s+", line, flags=re.IGNORECASE):
        return False
    if re.search(
        r"\b(POST|CALLS|BETS|RAISES|CHECK|FOLD|TRIPS|PAIR|STRAIGHT|FLUSH|FULL HOUSE|MUCKS|WINS|RECEIVES)\b",
        line,
        flags=re.IGNORECASE,
    ):
        return False
    if re.fullmatch(r"[AKQJT2-9\s♥♦♣♠♡♢hdcs]+", line, flags=re.IGNORECASE):
        return False
    if "{" in line or "}" in line or "[" in line or "]" in line:
        return False
    if len(line) > 40:
        return False

    return bool(re.search(r"[A-Za-z]", line))


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
    if not name:
        return None

    n = name.lower().strip()

    for p in known_players:
        if p.lower() == n:
            return p

    for p in known_players:
        if p.lower().replace("0", "o") == n.replace("0", "o"):
            return p

    return name.strip()


def parse_action_from_segment(segment, player, street):
    segment = segment.strip()
    actions = []

    for action_name, pattern in ACTION_MAP:
        m = re.search(pattern, segment, flags=re.IGNORECASE)
        if not m:
            continue

        amount = None
        if m.groups():
            try:
                amount = float(m.group(1))
            except (ValueError, TypeError):
                amount = None

        action = {
            "street": street,
            "player": player,
            "action": action_name,
            "amount_bb": amount,
            "raw": segment,
        }

        if action_name == "receives":
            cards = extract_ranks_only(segment)
            if len(cards) >= 2:
                action["cards"] = cards[:2]

        actions.append(action)
        break

    return actions


def parse_inline_player_action_segments(line, players, current_street):
    if not players:
        return []

    escaped_players = [re.escape(p) for p in sorted(players, key=len, reverse=True)]
    player_union = "|".join(escaped_players)
    matches = list(re.finditer(player_union, line, flags=re.IGNORECASE))

    if not matches:
        return []

    actions = []

    for idx, match in enumerate(matches):
        player_raw = match.group(0)
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(line)
        segment = line[start:end].strip(" -–:|")

        if not segment:
            continue

        player = canonicalize_name(player_raw, players)
        actions.extend(parse_action_from_segment(segment, player, current_street))

    return actions


def parse_actions(lines, players):
    actions = []
    current_street = "preflop"
    last_player = None

    for line in lines:
        upper = line.upper()

        if upper in STREETS:
            current_street = upper.lower().replace("-", "")
            continue

        inline_actions = parse_inline_player_action_segments(line, players, current_street)
        if inline_actions:
            actions.extend(inline_actions)
            continue

        if is_probable_player_name(line):
            last_player = canonicalize_name(line, players)
            continue

        if last_player:
            actions.extend(parse_action_from_segment(line, last_player, current_street))

    return actions


def parse_showdown(lines, players):
    try:
        idx = lines.index("SHOWDOWN")
    except ValueError:
        return None

    showdown = {
        "players": [],
        "winners": [],
    }

    current_player = None
    block = lines[idx + 1:]

    winner_pattern = None
    if players:
        winner_pattern = r"(" + "|".join(re.escape(p) for p in players) + r")\s+WINS?\s+([0-9]+(?:\.[0-9]+)?)\s*BB"

    for line in block:
        upper = line.upper()

        if upper in STREETS and upper != "SHOWDOWN":
            break

        if is_probable_player_name(line):
            current_player = canonicalize_name(line, players)
            if current_player and not any(p["name"] == current_player for p in showdown["players"]):
                showdown["players"].append({"name": current_player})
            continue

        if current_player:
            if ":" in line and not re.search(r"\bRECEIVES\b", line, flags=re.IGNORECASE):
                for player in showdown["players"]:
                    if player["name"] == current_player:
                        player["made_hand"] = line
                        break

            cards = extract_card_tokens_with_suits(line)
            if 1 <= len(cards) <= 2:
                for player in showdown["players"]:
                    if player["name"] == current_player:
                        player["hole_cards"] = cards[:2]
                        break

        if winner_pattern:
            for m in re.finditer(winner_pattern, line, flags=re.IGNORECASE):
                showdown["winners"].append({
                    "player": canonicalize_name(m.group(1), players),
                    "amount_bb": float(m.group(2)),
                })

    if not showdown["players"] and not showdown["winners"]:
        return None

    return showdown


def infer_current_street(board, showdown):
    if showdown and (showdown.get("players") or showdown.get("winners")):
        return "showdown"
    if board.get("river"):
        return "river"
    if board.get("turn"):
        return "turn"
    if board.get("flop"):
        return "flop"
    return "preflop"


def infer_hero_name(players, lines):
    preferred_names = ["Karmatoast40"]
    for name in preferred_names:
        if name in players:
            return name

    for line in lines:
        m = re.match(r"([A-Za-z0-9_]+)\s+RECEIVES\s*:", line, flags=re.IGNORECASE)
        if m:
            return canonicalize_name(m.group(1), players) if players else m.group(1)

    return None


def build_events(state):
    events = []
    seq = 1
    hand_id = state.get("hand_id")

    def push(event_type, street=None, **payload):
        nonlocal seq
        events.append({
            "seq": seq,
            "hand_id": hand_id,
            "street": street,
            "event": event_type,
            **payload,
        })
        seq += 1

    if hand_id:
        push("hand_start", street="preflop")

    hero = state.get("hero", {})
    actions = state.get("actions", [])

    for action in actions:
        if action["action"] == "post_small_blind":
            push("post_small_blind", street="preflop", player=action["player"], amount_bb=action["amount_bb"])
        elif action["action"] == "post_big_blind":
            push("post_big_blind", street="preflop", player=action["player"], amount_bb=action["amount_bb"])

    if hero.get("name") and hero.get("hole_cards_raw"):
        push("hero_cards", street="preflop", player=hero["name"], cards=hero["hole_cards_raw"])

    for action in actions:
        if action["action"] in {"post_small_blind", "post_big_blind"}:
            continue

        payload = {
            "player": action.get("player"),
            "action_name": action.get("action"),
            "amount_bb": action.get("amount_bb"),
            "raw": action.get("raw"),
        }
        if "cards" in action:
            payload["cards"] = action["cards"]

        push("action", street=action.get("street"), **payload)

    board = state.get("board", {})
    if board.get("flop"):
        push("flop_reveal", street="flop", cards=board["flop"])
    if board.get("turn"):
        push("turn_reveal", street="turn", card=board["turn"])
    if board.get("river"):
        push("river_reveal", street="river", card=board["river"])

    showdown = state.get("showdown")
    if showdown:
        push("showdown", street="showdown", data=showdown)

    return events


def parse_poker_ocr_text(raw_text: str, image_path: Path):
    raw_text = clean_text(raw_text)
    lines = split_lines(raw_text)

    players = collect_player_names(lines)
    board = parse_board(lines)
    showdown = parse_showdown(lines, players)
    actions = parse_actions(lines, players)
    hero_name = infer_hero_name(players, lines)
    hero_cards = parse_hero_cards(lines)

    state = {
        "timestamp_utc": datetime.utcnow().isoformat() + "Z",
        "source_image": image_path.name,
        "hand_id": parse_hand_id(lines),
        "blinds": parse_blinds(raw_text),
        "hero": {
            "name": hero_name,
            "hole_cards_raw": hero_cards,
        },
        "players": [{"name": p} for p in players],
        "board": board,
        "current_street": infer_current_street(board, showdown),
        "actions": actions,
        "showdown": showdown,
        "raw_text": raw_text,
    }

    state["events"] = build_events(state)
    return state