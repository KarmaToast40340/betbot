import re
from datetime import datetime
from pathlib import Path

from config import STREETS, SUIT_MAP


HAND_LINE_RE = re.compile(r"^\s*Hand\s+(.+)$", re.IGNORECASE)
AMOUNT_BB_RE = re.compile(r"\(?\s*([0-9]+(?:\.[0-9]+)?)\s*BB\s*\)?", re.IGNORECASE)
CARD_WITH_SUIT_RE = re.compile(r"(?:10|[2-9AKQJT])(?:\s*[♥♦♣♠♡♢hdcs])", re.IGNORECASE)
RANK_ONLY_RE = re.compile(r"\b(10|[2-9AKQJT])\b", re.IGNORECASE)

ACTION_PATTERNS = [
    ("post_small_blind", re.compile(r"\bPost small blind\b.*?([0-9]+(?:\.[0-9]+)?)\s*BB", re.IGNORECASE)),
    ("post_big_blind", re.compile(r"\bPost big blind\b.*?([0-9]+(?:\.[0-9]+)?)\s*BB", re.IGNORECASE)),
    ("raise_to", re.compile(r"\bRaises to\s+([0-9]+(?:\.[0-9]+)?)\s*BB", re.IGNORECASE)),
    ("bet", re.compile(r"\bBets\s+([0-9]+(?:\.[0-9]+)?)\s*BB", re.IGNORECASE)),
    ("call", re.compile(r"\bCalls\s+([0-9]+(?:\.[0-9]+)?)\s*BB", re.IGNORECASE)),
    ("check", re.compile(r"\bCheck\b", re.IGNORECASE)),
    ("fold", re.compile(r"\bFold\b", re.IGNORECASE)),
    ("mucks", re.compile(r"\bMucks\b", re.IGNORECASE)),
    ("wins", re.compile(r"\bWINS?\s+([0-9]+(?:\.[0-9]+)?)\s*BB\b", re.IGNORECASE)),
    ("receives", re.compile(r"\bRECEIVES\s*:\s*(.+)$", re.IGNORECASE)),
]

ACTION_START_TOKENS = (
    "Post small blind",
    "Post big blind",
    "Raises to",
    "Bets",
    "Calls",
    "Check",
    "Fold",
    "Mucks",
    "WINS",
    "RECEIVES",
)

BANNED_NAME_TOKENS = {
    "CARDS DEALT",
    "PRE-FLOP",
    "FLOP",
    "TURN",
    "RIVER",
    "SHOWDOWN",
    "NULL",
}


def clean_text(text: str) -> str:
    text = text or ""
    text = text.replace("\r", "\n")
    text = re.sub(r"&nbsp;", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def split_lines(text: str):
    return [line.strip() for line in text.splitlines() if line.strip()]


def normalize_rank(rank: str) -> str:
    rank = rank.upper()
    return "T" if rank == "10" else rank


def normalize_suit(suit: str) -> str:
    return SUIT_MAP.get(suit.lower(), suit.lower())


def normalize_card(token: str) -> str:
    token = token.strip()
    match = re.match(r"(10|[2-9AKQJT])\s*([♥♦♣♠♡♢hdcs])", token, flags=re.IGNORECASE)
    if not match:
        return token.upper()
    return f"{normalize_rank(match.group(1))}{normalize_suit(match.group(2))}"


def extract_cards_with_suits(text: str):
    return [normalize_card(token) for token in CARD_WITH_SUIT_RE.findall(text)]


def extract_rank_only_cards(text: str):
    return [normalize_rank(token) for token in RANK_ONLY_RE.findall(text)]


def extract_cards_dealt_blocks(raw_text: str):
    text = raw_text or ""
    text = text.replace("\r", "\n")
    pattern = re.compile(r"CARDS DEALT(.*?)(?:\n\s*PRE-FLOP\b|\n\s*FLOP\b|\n\s*TURN\b|\n\s*RIVER\b|\n\s*SHOWDOWN\b|\n\s*Hand\b|\Z)", re.IGNORECASE | re.DOTALL)
    blocks = []
    for match in pattern.finditer(text):
        block = match.group(1)
        block = re.sub(r"<img.*?>", " ", block, flags=re.IGNORECASE)
        block = re.sub(r"<[^>]+>", " ", block)
        block = re.sub(r"!\[[^\]]*\]\([^)]+\)", " ", block)
        block = re.sub(r"[ \t]+", " ", block)
        block = re.sub(r"\n{2,}", "\n", block)
        blocks.append(block.strip())
    return blocks


def split_hand_blocks(raw_text: str):
    text = clean_text(raw_text)
    if not text:
        return []
    lines = split_lines(text)
    hand_start_indexes = [idx for idx, line in enumerate(lines) if HAND_LINE_RE.match(line)]
    if not hand_start_indexes:
        return [text]
    blocks = []
    for i, start_idx in enumerate(hand_start_indexes):
        end_idx = hand_start_indexes[i + 1] if i + 1 < len(hand_start_indexes) else len(lines)
        block_lines = lines[start_idx:end_idx]
        if block_lines:
            blocks.append("\n\n".join(block_lines))
    return blocks


def parse_hand_id(lines):
    for line in lines:
        match = HAND_LINE_RE.match(line)
        if match:
            return match.group(1).strip()
    return None


def parse_blinds(text: str):
    sb = None
    bb = None
    match_sb = re.search(r"Post small blind.*?([0-9]+(?:\.[0-9]+)?)\s*BB", text, flags=re.IGNORECASE | re.DOTALL)
    match_bb = re.search(r"Post big blind.*?([0-9]+(?:\.[0-9]+)?)\s*BB", text, flags=re.IGNORECASE | re.DOTALL)
    if match_sb:
        sb = float(match_sb.group(1))
    if match_bb:
        bb = float(match_bb.group(1))
    return {"sb": sb, "bb": bb}


def parse_hero_cards(lines, raw_text=None):
    for i, line in enumerate(lines):
        if line.upper() == "CARDS DEALT":
            ranks = []
            for probe in lines[i + 1:i + 8]:
                ranks.extend(extract_rank_only_cards(probe))
                if len(ranks) >= 2:
                    return ranks[:2]
        match = re.search(r"\bRECEIVES\s*:\s*(.+)$", line, flags=re.IGNORECASE)
        if match:
            ranks = extract_rank_only_cards(match.group(1))
            if len(ranks) >= 2:
                return ranks[:2]

    if raw_text:
        for block in extract_cards_dealt_blocks(raw_text):
            ranks = extract_rank_only_cards(block)
            if len(ranks) >= 2:
                return ranks[:2]

    return []


def parse_board(lines):
    board = {"flop": [], "turn": None, "river": None, "all_cards": []}
    for i, line in enumerate(lines):
        upper = line.upper()
        if upper == "FLOP" and i + 1 < len(lines):
            board["flop"] = extract_cards_with_suits(lines[i + 1])[:3]
        elif upper == "TURN" and i + 1 < len(lines):
            cards = extract_cards_with_suits(lines[i + 1])
            if len(cards) >= 4:
                board["turn"] = cards[3]
        elif upper == "RIVER" and i + 1 < len(lines):
            cards = extract_cards_with_suits(lines[i + 1])
            if len(cards) >= 5:
                board["river"] = cards[4]
    board["all_cards"] = board["flop"][:]
    if board["turn"]:
        board["all_cards"].append(board["turn"])
    if board["river"]:
        board["all_cards"].append(board["river"])
    return board


def contains_action_words(line: str) -> bool:
    lowered = line.lower()
    return any(token.lower() in lowered for token in ACTION_START_TOKENS)


def is_probable_player_name(line: str) -> bool:
    if not line:
        return False
    line = line.strip()
    upper = line.upper()
    if upper in BANNED_NAME_TOKENS or upper in STREETS:
        return False
    if HAND_LINE_RE.match(line):
        return False
    if contains_action_words(line):
        return False
    if re.search(r"\b(BB|SB)\b", upper):
        return False
    if re.fullmatch(r"[AKQJT2-9\s♥♦♣♠♡♢hdcs()\.]+", line, flags=re.IGNORECASE):
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


def canonicalize_name(name, players):
    if not name:
        return None
    normalized = name.lower().strip()
    for player in players:
        if player.lower() == normalized:
            return player
    for player in players:
        if player.lower().replace("0", "o") == normalized.replace("0", "o"):
            return player
    return name.strip()


def extract_inline_actor(line: str):
    for token in ACTION_START_TOKENS:
        idx = line.lower().find(token.lower())
        if idx > 0:
            prefix = line[:idx].strip()
            if prefix and " " not in prefix:
                return prefix, line[idx:].strip()
    return None


def enrich_players_from_actions(lines, players):
    seen = {p.lower() for p in players}
    enriched = list(players)
    for line in lines:
        inline = extract_inline_actor(line)
        if not inline:
            continue
        actor, _ = inline
        if actor.lower() not in seen:
            seen.add(actor.lower())
            enriched.append(actor)
    return enriched


def infer_hero_name(players, lines):
    preferred = ["Karmatoast40"]
    for player in preferred:
        if player in players:
            return player
    for line in lines:
        match = re.match(r"([A-Za-z0-9_]+)\s+RECEIVES\s*:", line, flags=re.IGNORECASE)
        if match:
            return canonicalize_name(match.group(1), players)
    return None


def split_inline_name_action(line: str, players):
    inline = extract_inline_actor(line)
    if not inline:
        return None
    actor, segment = inline
    return canonicalize_name(actor, players), segment


def parse_action_segment(segment: str, player: str, street: str):
    segment = segment.strip()
    for action_name, pattern in ACTION_PATTERNS:
        match = pattern.search(segment)
        if not match:
            continue
        amount = None
        cards = None
        if action_name == "receives":
            ranks = extract_rank_only_cards(match.group(1))
            if len(ranks) >= 2:
                cards = ranks[:2]
        elif match.groups():
            try:
                amount = float(match.group(1))
            except (ValueError, TypeError):
                amount = None
        action = {
            "street": street,
            "player": player,
            "action": action_name,
            "amount_bb": amount,
            "raw": segment,
        }
        if cards:
            action["cards"] = cards
        return action
    return None


def assign_blind_owners(actions, players, hero_name):
    sb_actions = [a for a in actions if a["action"] == "post_small_blind"]
    bb_actions = [a for a in actions if a["action"] == "post_big_blind"]
    if len(players) == 2 and len(sb_actions) == 1 and len(bb_actions) == 1:
        p1, p2 = players[0], players[1]
        if sb_actions[0].get("player") and not bb_actions[0].get("player"):
            bb_actions[0]["player"] = p1 if sb_actions[0]["player"] == p2 else p2
        elif bb_actions[0].get("player") and not sb_actions[0].get("player"):
            sb_actions[0]["player"] = p1 if bb_actions[0]["player"] == p2 else p2
        elif not sb_actions[0].get("player") and not bb_actions[0].get("player") and hero_name in players:
            villain = p1 if p2 == hero_name else p2
            sb_actions[0]["player"] = hero_name
            bb_actions[0]["player"] = villain
    return actions


def parse_actions(lines, players, hero_name=None, hero_cards=None):
    actions = []
    current_street = "preflop"
    pending_player = None
    i = 0

    while i < len(lines):
        line = lines[i]
        upper = line.upper()

        if upper in STREETS:
            current_street = upper.lower().replace("-", "")
            pending_player = None
            i += 1
            continue

        inline = split_inline_name_action(line, players)
        if inline:
            player, segment = inline
            action = parse_action_segment(segment, player, current_street)
            if action:
                actions.append(action)
                i += 1
                continue

        if is_probable_player_name(line):
            pending_player = canonicalize_name(line, players)
            i += 1
            continue

        if contains_action_words(line):
            combined = line
            if i + 1 < len(lines) and AMOUNT_BB_RE.fullmatch(lines[i + 1]):
                combined = f"{combined} {lines[i + 1]}"
                i += 1
            actor = pending_player
            action = parse_action_segment(combined, actor, current_street)
            if action:
                actions.append(action)
                pending_player = None
                i += 1
                continue

        i += 1

    if hero_name and hero_cards:
        actions.insert(0, {
            "street": "preflop",
            "player": hero_name,
            "action": "hero_cards",
            "amount_bb": None,
            "raw": "CARDS DEALT",
            "cards": hero_cards,
        })

    actions = assign_blind_owners(actions, players, hero_name)

    deduped = []
    seen = set()
    for action in actions:
        key = (
            action.get("street"),
            action.get("player"),
            action.get("action"),
            action.get("amount_bb"),
            tuple(action.get("cards", [])),
            action.get("raw"),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(action)
    return deduped


def parse_showdown(lines, players):
    try:
        idx = lines.index("SHOWDOWN")
    except ValueError:
        return None
    showdown = {"players": [], "winners": []}
    seen_players = set()
    seen_winners = set()
    current_player = None
    for line in lines[idx + 1:]:
        upper = line.upper()
        if upper in STREETS and upper != "SHOWDOWN":
            break
        inline = split_inline_name_action(line, players)
        if inline:
            player, segment = inline
            if player and player not in seen_players:
                showdown["players"].append({"name": player})
                seen_players.add(player)
            action = parse_action_segment(segment, player, "showdown")
            if action and action["action"] == "wins":
                key = (player, action.get("amount_bb"))
                if key not in seen_winners:
                    seen_winners.add(key)
                    showdown["winners"].append({"player": player, "amount_bb": action.get("amount_bb")})
            current_player = player
            continue
        if is_probable_player_name(line):
            current_player = canonicalize_name(line, players)
            if current_player and current_player not in seen_players:
                showdown["players"].append({"name": current_player})
                seen_players.add(current_player)
            continue
        if current_player and ":" in line and "receives" not in line.lower():
            for player_entry in showdown["players"]:
                if player_entry["name"] == current_player:
                    player_entry["made_hand"] = line
                    break
    if not showdown["players"] and not showdown["winners"]:
        return None
    return showdown


def infer_current_street(board, showdown, actions):
    if showdown and (showdown.get("players") or showdown.get("winners")):
        return "showdown"
    if any(action.get("street") == "river" for action in actions):
        return "river"
    if any(action.get("street") == "turn" for action in actions):
        return "turn"
    if any(action.get("street") == "flop" for action in actions):
        return "flop"
    if board.get("river"):
        return "river"
    if board.get("turn"):
        return "turn"
    if board.get("flop"):
        return "flop"
    return "preflop"


def build_events(state):
    events = []
    seq = 1
    hand_id = state.get("hand_id")

    def push(event_type, street=None, **payload):
        nonlocal seq
        events.append({"seq": seq, "hand_id": hand_id, "street": street, "event": event_type, **payload})
        seq += 1

    if hand_id:
        push("hand_start", street="preflop")

    for action in state.get("actions", []):
        if action["action"] in {"post_small_blind", "post_big_blind", "hero_cards"}:
            payload = {"player": action.get("player"), "amount_bb": action.get("amount_bb")}
            if "cards" in action:
                payload["cards"] = action["cards"]
            push(action["action"], street=action.get("street"), **payload)
            continue

        payload = {
            "player": action.get("player"),
            "amount_bb": action.get("amount_bb"),
            "action_name": action.get("action"),
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
    players = enrich_players_from_actions(lines, players)
    hero_name = infer_hero_name(players, lines)
    if hero_name and hero_name not in players:
        players = [hero_name] + players
    hero_cards = parse_hero_cards(lines, raw_text=raw_text)
    actions = parse_actions(lines, players, hero_name=hero_name, hero_cards=hero_cards)
    board = parse_board(lines)
    showdown = parse_showdown(lines, players)
    state = {
        "timestamp_utc": datetime.utcnow().isoformat() + "Z",
        "source_image": image_path.name,
        "hand_id": parse_hand_id(lines),
        "blinds": parse_blinds(raw_text),
        "hero": {"name": hero_name, "hole_cards_raw": hero_cards},
        "players": [{"name": player} for player in players],
        "board": board,
        "current_street": infer_current_street(board, showdown, actions),
        "actions": actions,
        "showdown": showdown,
        "raw_text": raw_text,
    }
    state["events"] = build_events(state)
    return state


def parse_ocr_document(raw_text: str, image_path: Path):
    states = []
    for block in split_hand_blocks(raw_text):
        state = parse_poker_ocr_text(block, image_path)
        if state.get("hand_id") or state.get("actions") or state.get("hero", {}).get("hole_cards_raw"):
            states.append(state)
    return states