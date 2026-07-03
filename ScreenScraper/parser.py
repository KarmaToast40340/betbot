import re
from datetime import datetime
from pathlib import Path
from typing import Any

from config import STREETS, SUIT_MAP

SUIT_CHARS = "♥♦♣♠♡♢hdcs"
STREET_NAMES = {"PRE-FLOP", "FLOP", "TURN", "RIVER", "SHOWDOWN"}
NON_ACTION_EVENTS = {
    "cards_dealt",
    "flop_start",
    "turn_start",
    "river_start",
    "showdown_start",
    "hero_cards",
}

HAND_LINE_RE = re.compile(r"^\s*Hand\s+(.+)$", re.IGNORECASE)
AMOUNT_BB_RE = re.compile(r"\(?\s*([0-9]+(?:\.[0-9]+)?)\s*BB\s*\)?", re.IGNORECASE)
CARD_WITH_SUIT_RE = re.compile(rf"(?:10|[2-9AKQJT])(?:\s*[{SUIT_CHARS}])", re.IGNORECASE)
RANK_ONLY_RE = re.compile(r"\b(10|[2-9AKQJT])\b", re.IGNORECASE)
COMPACT_RANK_SEQ_RE = re.compile(r"(?<![A-Za-z0-9_])(10|[2-9AKQJT])(?=(10|[2-9AKQJT]))", re.IGNORECASE)
CARDS_DEALT_INLINE_RE = re.compile(r"^CARDS DEALT\s+(.+)$", re.IGNORECASE)
SHOWDOWN_INLINE_RE = re.compile(r"^SHOWDOWN\s+(.+)$", re.IGNORECASE)
BOARD_VALUE_RE = re.compile(r"^(?:\s*(?:10|[2-9AKQJT])\s*){3,5}$", re.IGNORECASE)

ACTION_PATTERNS = [
    ("post_small_blind", re.compile(r"\bPost small blind\b(?:\s*\(?\s*([0-9]+(?:\.[0-9]+)?)\s*(?:BB)?\s*\)?)?", re.IGNORECASE)),
    ("post_big_blind", re.compile(r"\bPost big blind\b(?:\s*\(?\s*([0-9]+(?:\.[0-9]+)?)\s*(?:BB)?\s*\)?)?", re.IGNORECASE)),
    ("raise_to", re.compile(r"\bRaises to\s+([0-9]+(?:\.[0-9]+)?)(?:\s*BB\b)?", re.IGNORECASE)),
    ("bet", re.compile(r"\bBets\s+([0-9]+(?:\.[0-9]+)?)(?:\s*BB\b)?", re.IGNORECASE)),
    ("call", re.compile(r"\bCalls\s+([0-9]+(?:\.[0-9]+)?)(?:\s*BB\b)?", re.IGNORECASE)),
    ("check", re.compile(r"\bCheck\b", re.IGNORECASE)),
    ("fold", re.compile(r"\bFold\b", re.IGNORECASE)),
    ("mucks", re.compile(r"\bMucks\b", re.IGNORECASE)),
    ("wins", re.compile(r"\bWINS?\s+([0-9]+(?:\.[0-9]+)?)(?:\s*BB\b)?", re.IGNORECASE)),
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

STRUCTURAL_MARKERS = {
    "CARDS DEALT": ("preflop", "cards_dealt"),
    "FLOP": ("flop", "flop_start"),
    "TURN": ("turn", "turn_start"),
    "RIVER": ("river", "river_start"),
    "SHOWDOWN": ("showdown", "showdown_start"),
}

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


def split_lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def strip_heading_prefix(line: str) -> str:
    return re.sub(r"^#+\s*", "", (line or "").strip()).strip()


def normalize_rank(rank: str) -> str:
    rank = rank.upper()
    return "T" if rank == "10" else rank


def normalize_suit(suit: str) -> str:
    return SUIT_MAP.get(suit.lower(), suit.lower())


def normalize_card(token: str) -> str:
    token = token.strip()
    match = re.match(rf"(10|[2-9AKQJT])\s*([{SUIT_CHARS}])", token, flags=re.IGNORECASE)
    if not match:
        return normalize_rank(token)
    return f"{normalize_rank(match.group(1))}{normalize_suit(match.group(2))}"


def space_compact_cards(text: str) -> str:
    if not text:
        return text
    text = COMPACT_RANK_SEQ_RE.sub(r"\1 ", text)
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip()


def extract_cards_with_suits(text: str) -> list[str]:
    suited = [normalize_card(token) for token in CARD_WITH_SUIT_RE.findall(text)]
    if suited:
        return suited
    return extract_rank_only_cards(text)


def extract_rank_only_cards(text: str) -> list[str]:
    text = space_compact_cards(text)
    return [normalize_rank(token) for token in RANK_ONLY_RE.findall(text)]


def extract_cards_dealt_blocks(raw_text: str) -> list[str]:
    text = (raw_text or "").replace("\r", "\n")
    pattern = re.compile(
        r"CARDS DEALT(.*?)(?:\n\s*#*\s*PRE-FLOP\b|\n\s*#*\s*FLOP\b|\n\s*#*\s*TURN\b|\n\s*#*\s*RIVER\b|\n\s*#*\s*SHOWDOWN\b|\n\s*Hand\b|\Z)",
        re.IGNORECASE | re.DOTALL,
    )
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


def split_hand_blocks(raw_text: str) -> list[str]:
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
        chunk = lines[start_idx:end_idx]
        if chunk:
            blocks.append("\n\n".join(chunk))
    return blocks


def parse_hand_id(lines: list[str]) -> str | None:
    for line in lines:
        match = HAND_LINE_RE.match(line)
        if match:
            return match.group(1).strip()
    return None


def parse_blinds(text: str) -> dict[str, float | None]:
    match_sb = re.search(r"Post small blind.*?([0-9]+(?:\.[0-9]+)?)\s*(?:BB\b|\)|$)", text, flags=re.IGNORECASE | re.DOTALL)
    match_bb = re.search(r"Post big blind.*?([0-9]+(?:\.[0-9]+)?)\s*(?:BB\b|\)|$)", text, flags=re.IGNORECASE | re.DOTALL)
    return {
        "sb": float(match_sb.group(1)) if match_sb else None,
        "bb": float(match_bb.group(1)) if match_bb else None,
    }


def parse_hero_cards(lines: list[str], raw_text: str | None = None) -> list[str]:
    if raw_text:
        for block in extract_cards_dealt_blocks(raw_text):
            ranks = extract_rank_only_cards(block)
            if len(ranks) >= 2:
                return ranks[:2]

    for i, line in enumerate(lines):
        cleaned = strip_heading_prefix(line)
        match_inline = CARDS_DEALT_INLINE_RE.match(cleaned)
        if match_inline:
            inline_ranks = extract_rank_only_cards(match_inline.group(1).strip())
            if len(inline_ranks) >= 2:
                return inline_ranks[:2]

        if cleaned.upper() == "CARDS DEALT":
            ranks: list[str] = []
            for probe in lines[i + 1 : i + 8]:
                probe_upper = strip_heading_prefix(probe).upper()
                if probe_upper in STREET_NAMES:
                    break
                if probe_upper.startswith("CARDS DEALT"):
                    continue
                ranks.extend(extract_rank_only_cards(probe))
                if len(ranks) >= 2:
                    return ranks[:2]

        match_receives = re.search(r"\bRECEIVES\s*:\s*(.+)$", line, flags=re.IGNORECASE)
        if match_receives:
            ranks = extract_rank_only_cards(match_receives.group(1))
            if len(ranks) >= 2:
                return ranks[:2]
    return []


def parse_board(lines: list[str]) -> dict[str, Any]:
    board = {"flop": [], "turn": None, "river": None, "all_cards": []}
    for i, line in enumerate(lines):
        cleaned = strip_heading_prefix(line)
        upper = cleaned.upper()
        if upper.startswith("FLOP"):
            payload = cleaned[4:].strip()
            cards = extract_cards_with_suits(payload) if payload else []
            if len(cards) < 3 and i + 1 < len(lines):
                cards = extract_cards_with_suits(lines[i + 1])
            if len(cards) >= 3:
                board["flop"] = cards[:3]
        elif upper.startswith("TURN"):
            payload = cleaned[4:].strip()
            cards = extract_cards_with_suits(payload) if payload else []
            if not cards and i + 1 < len(lines):
                cards = extract_cards_with_suits(lines[i + 1])
            if len(cards) >= 4:
                board["turn"] = cards[3]
            elif cards:
                board["turn"] = cards[-1]
        elif upper.startswith("RIVER"):
            payload = cleaned[5:].strip()
            cards = extract_cards_with_suits(payload) if payload else []
            if not cards and i + 1 < len(lines):
                cards = extract_cards_with_suits(lines[i + 1])
            if len(cards) >= 5:
                board["river"] = cards[4]
            elif cards:
                board["river"] = cards[-1]

    board["all_cards"] = board["flop"][:]
    if board["turn"]:
        board["all_cards"].append(board["turn"])
    if board["river"]:
        board["all_cards"].append(board["river"])
    return board


def contains_action_words(line: str) -> bool:
    lowered = strip_heading_prefix(line).lower()
    return any(token.lower() in lowered for token in ACTION_START_TOKENS)


def is_probable_player_name(line: str) -> bool:
    if not line:
        return False
    line = strip_heading_prefix(line)
    upper = line.upper()
    if not line:
        return False
    if upper in BANNED_NAME_TOKENS or upper in STREETS:
        return False
    if upper.startswith("CARDS DEALT") or upper.startswith("SHOWDOWN"):
        return False
    if HAND_LINE_RE.match(line):
        return False
    if contains_action_words(line):
        return False
    if re.search(r"\b(BB|SB)\b", upper):
        return False
    if re.fullmatch(rf"[AKQJT2-9\s{SUIT_CHARS}()\.#:-]+", line, flags=re.IGNORECASE):
        return False
    if BOARD_VALUE_RE.fullmatch(line):
        return False
    compact = space_compact_cards(line)
    ranks = extract_rank_only_cards(line)
    if len(ranks) >= 2 and compact.replace(" ", "") == line.replace(" ", ""):
        return False
    if ":" in line:
        return False
    if len(line) > 40:
        return False
    return bool(re.search(r"[A-Za-z]", line))


def collect_player_names(lines: list[str]) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for line in lines:
        cleaned = strip_heading_prefix(line)
        if cleaned.upper() in STRUCTURAL_MARKERS or cleaned.upper() in STREET_NAMES:
            continue
        if is_probable_player_name(cleaned):
            key = cleaned.lower()
            if key not in seen:
                seen.add(key)
                names.append(cleaned)
    return names


def canonicalize_name(name: str | None, players: list[str]) -> str | None:
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


def extract_inline_actor(line: str) -> tuple[str, str] | None:
    cleaned = strip_heading_prefix(line)
    for token in ACTION_START_TOKENS:
        idx = cleaned.lower().find(token.lower())
        if idx > 0:
            prefix = cleaned[:idx].strip()
            if prefix:
                return prefix, cleaned[idx:].strip()
    return None


def enrich_players_from_actions(lines: list[str], players: list[str]) -> list[str]:
    seen = {p.lower() for p in players}
    enriched = list(players)
    for line in lines:
        cleaned = strip_heading_prefix(line)
        showdown_inline = SHOWDOWN_INLINE_RE.match(cleaned)
        if showdown_inline:
            actor = showdown_inline.group(1).strip()
            if actor and actor.lower() not in seen and len(extract_rank_only_cards(actor)) < 2:
                seen.add(actor.lower())
                enriched.append(actor)
            continue
        inline = extract_inline_actor(cleaned)
        if not inline:
            continue
        actor, _ = inline
        if actor and actor.lower() not in seen and len(extract_rank_only_cards(actor)) < 2 and not actor.upper().startswith("CARDS DEALT"):
            seen.add(actor.lower())
            enriched.append(actor)
    return enriched


def infer_hero_name(players: list[str], lines: list[str]) -> str | None:
    preferred = ["Karmatoast40"]
    for player in preferred:
        if player in players:
            return player
    for line in lines:
        match = re.match(r"([A-Za-z0-9_]+)\s+RECEIVES\s*:", line, flags=re.IGNORECASE)
        if match:
            return canonicalize_name(match.group(1), players)
    return None


def split_inline_name_action(line: str, players: list[str]) -> tuple[str | None, str] | None:
    inline = extract_inline_actor(line)
    if not inline:
        return None
    actor, segment = inline
    return canonicalize_name(actor, players), segment


def iter_action_matches(segment: str) -> list[tuple[int, int, dict[str, Any]]]:
    segment = strip_heading_prefix(segment).strip()
    if not segment:
        return []
    matches: list[tuple[int, int, dict[str, Any]]] = []
    for action_name, pattern in ACTION_PATTERNS:
        for match in pattern.finditer(segment):
            amount = None
            cards = None
            if action_name == "receives":
                ranks = extract_rank_only_cards(match.group(1))
                if len(ranks) >= 2:
                    cards = ranks[:2]
            elif match.groups():
                raw_amount = match.group(1)
                if raw_amount not in (None, ""):
                    try:
                        amount = float(raw_amount)
                    except (ValueError, TypeError):
                        amount = None
            action = {
                "action": action_name,
                "amount_bb": amount,
                "raw": segment,
            }
            if cards:
                action["cards"] = cards
            matches.append((match.start(), match.end(), action))
    matches.sort(key=lambda item: (item[0], item[1]))
    return matches


def parse_action_segment(segment: str, player: str | None, street: str) -> dict[str, Any] | None:
    matches = iter_action_matches(segment)
    if not matches:
        return None
    action = dict(matches[0][2])
    action["street"] = street
    action["player"] = player
    return action


def assign_blind_owners(actions: list[dict[str, Any]], players: list[str], hero_name: str | None):
    sb_actions = [a for a in actions if a["action"] == "post_small_blind"]
    bb_actions = [a for a in actions if a["action"] == "post_big_blind"]
    if len(players) >= 2 and len(sb_actions) == 1 and len(bb_actions) == 1:
        p1, p2 = players[0], players[1]
        if sb_actions[0].get("player") and not bb_actions[0].get("player"):
            bb_actions[0]["player"] = p1 if sb_actions[0]["player"] == p2 else p2
        elif bb_actions[0].get("player") and not sb_actions[0].get("player"):
            sb_actions[0]["player"] = p1 if bb_actions[0]["player"] == p2 else p2
        elif not sb_actions[0].get("player") and not bb_actions[0].get("player") and hero_name in players:
            villain = next((p for p in players if p != hero_name), None)
            sb_actions[0]["player"] = hero_name
            bb_actions[0]["player"] = villain
    return actions


def extract_structural_actions(lines: list[str], board: dict[str, Any], showdown_present: bool) -> list[dict[str, Any]]:
    actions = []
    seen = set()
    for line in lines:
        cleaned = strip_heading_prefix(line)
        upper = cleaned.upper()
        marker = upper if upper in STRUCTURAL_MARKERS else ("SHOWDOWN" if upper.startswith("SHOWDOWN") else None)
        if marker not in STRUCTURAL_MARKERS:
            continue
        street, action_name = STRUCTURAL_MARKERS[marker]
        action = {
            "street": street,
            "player": None,
            "action": action_name,
            "amount_bb": None,
            "raw": marker,
        }
        if action_name == "flop_start":
            action["cards"] = board.get("flop", [])
        elif action_name == "turn_start":
            action["cards"] = [board["turn"]] if board.get("turn") else []
        elif action_name == "river_start":
            action["cards"] = [board["river"]] if board.get("river") else []
        elif action_name == "showdown_start":
            action["showdown_present"] = showdown_present
        key = (action["street"], action["action"], tuple(action.get("cards", [])), action.get("showdown_present"))
        if key in seen:
            continue
        seen.add(key)
        actions.append(action)
    return actions


def parse_actions(
    lines: list[str],
    players: list[str],
    hero_name: str | None = None,
    hero_cards: list[str] | None = None,
    board: dict[str, Any] | None = None,
    showdown_present: bool = False,
) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    current_street = "preflop"
    pending_player = None
    i = 0

    while i < len(lines):
        line = lines[i]
        cleaned = strip_heading_prefix(line)
        upper = cleaned.upper()

        if upper in STREETS or upper.startswith("SHOWDOWN"):
            current_street = "showdown" if upper.startswith("SHOWDOWN") else upper.lower().replace("-", "")
            showdown_inline = SHOWDOWN_INLINE_RE.match(cleaned)
            pending_player = canonicalize_name(showdown_inline.group(1), players) if showdown_inline else None
            i += 1
            continue

        inline = split_inline_name_action(cleaned, players)
        if inline:
            player, segment = inline
            for _, _, base_action in iter_action_matches(segment):
                action = dict(base_action)
                action["street"] = current_street
                action["player"] = player
                actions.append(action)
            i += 1
            continue

        if is_probable_player_name(cleaned):
            pending_player = canonicalize_name(cleaned, players)
            i += 1
            continue

        if contains_action_words(cleaned):
            combined = cleaned
            next_line = strip_heading_prefix(lines[i + 1]) if i + 1 < len(lines) else ""
            if next_line and AMOUNT_BB_RE.fullmatch(next_line):
                combined = f"{combined} {next_line}"
                i += 1
            for _, _, base_action in iter_action_matches(combined):
                action = dict(base_action)
                action["street"] = current_street
                action["player"] = pending_player
                actions.append(action)
            pending_player = None
            i += 1
            continue

        i += 1

    if hero_name and hero_cards:
        actions.insert(
            0,
            {
                "street": "preflop",
                "player": hero_name,
                "action": "hero_cards",
                "amount_bb": None,
                "raw": "CARDS DEALT",
                "cards": hero_cards,
            },
        )

    board = board or {"flop": [], "turn": None, "river": None}
    actions = extract_structural_actions(lines, board, showdown_present) + actions
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
            action.get("showdown_present"),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(action)
    return deduped


def parse_showdown(lines: list[str], players: list[str]) -> dict[str, Any] | None:
    idx = None
    current_player = None
    for i, line in enumerate(lines):
        cleaned = strip_heading_prefix(line)
        upper = cleaned.upper()
        if upper == "SHOWDOWN" or upper.startswith("SHOWDOWN "):
            idx = i
            inline = SHOWDOWN_INLINE_RE.match(cleaned)
            if inline:
                current_player = canonicalize_name(inline.group(1).strip(), players)
            break
    if idx is None:
        return None

    showdown = {"players": [], "winners": []}
    seen_players = set()
    seen_winners = set()

    def ensure_player(name: str | None):
        if name and name not in seen_players:
            showdown["players"].append({"name": name, "hole_cards": []})
            seen_players.add(name)

    ensure_player(current_player)

    for line in lines[idx + 1 :]:
        cleaned = strip_heading_prefix(line)
        upper = cleaned.upper()
        if upper in STREETS and not upper.startswith("SHOWDOWN") and upper != "SHOWDOWN":
            break

        inline = split_inline_name_action(cleaned, players)
        if inline:
            player, segment = inline
            ensure_player(player)
            for _, _, base_action in iter_action_matches(segment):
                if base_action["action"] == "wins":
                    key = (player, base_action.get("amount_bb"))
                    if key not in seen_winners:
                        seen_winners.add(key)
                        showdown["winners"].append({"player": player, "amount_bb": base_action.get("amount_bb")})
            current_player = player
            continue

        ranks = extract_rank_only_cards(cleaned)
        if current_player and len(ranks) >= 2 and not cleaned.lower().startswith("pair:"):
            for player_entry in showdown["players"]:
                if player_entry["name"] == current_player and not player_entry.get("hole_cards"):
                    player_entry["hole_cards"] = ranks[:2]
                    break
            continue

        if current_player and ":" in cleaned and "receives" not in cleaned.lower():
            for player_entry in showdown["players"]:
                if player_entry["name"] == current_player:
                    player_entry["made_hand"] = cleaned
                    break
            continue

        if is_probable_player_name(cleaned):
            current_player = canonicalize_name(cleaned, players)
            ensure_player(current_player)
            continue

    for player_entry in showdown["players"]:
        player_entry.setdefault("hole_cards", [])

    if not showdown["players"] and not showdown["winners"]:
        return None
    return showdown


def infer_current_street(board: dict[str, Any], showdown: dict[str, Any] | None, actions: list[dict[str, Any]]) -> str:
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


def build_events(state: dict[str, Any]) -> list[dict[str, Any]]:
    events = []
    seq = 1
    hand_id = state.get("hand_id")

    def push(event_type: str, street: str | None = None, **payload: Any):
        nonlocal seq
        events.append({"seq": seq, "hand_id": hand_id, "street": street, "event": event_type, **payload})
        seq += 1

    if hand_id:
        push("hand_start", street="preflop")

    for action in state.get("actions", []):
        action_name = action["action"]
        if action_name in NON_ACTION_EVENTS:
            payload = {"player": action.get("player"), "amount_bb": action.get("amount_bb")}
            if "cards" in action:
                payload["cards"] = action["cards"]
            if "showdown_present" in action:
                payload["showdown_present"] = action["showdown_present"]
            push(action_name, street=action.get("street"), **payload)
            continue
        payload = {
            "player": action.get("player"),
            "amount_bb": action.get("amount_bb"),
            "action_name": action_name,
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


def parse_poker_ocr_text(raw_text: str, image_path: Path) -> dict[str, Any]:
    raw_text = clean_text(raw_text)
    lines = split_lines(raw_text)
    players = collect_player_names(lines)
    players = enrich_players_from_actions(lines, players)
    hero_name = infer_hero_name(players, lines)
    if hero_name and hero_name not in players:
        players = [hero_name] + players

    hero_cards = parse_hero_cards(lines, raw_text=raw_text)
    board = parse_board(lines)
    showdown = parse_showdown(lines, players)
    actions = parse_actions(
        lines,
        players,
        hero_name=hero_name,
        hero_cards=hero_cards,
        board=board,
        showdown_present=showdown is not None,
    )

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


def parse_ocr_document(raw_text: str, image_path: Path) -> list[dict[str, Any]]:
    states = []
    for block in split_hand_blocks(raw_text):
        state = parse_poker_ocr_text(block, image_path)
        if state.get("hand_id") or state.get("actions") or state.get("hero", {}).get("hole_cards_raw"):
            states.append(state)
    return states