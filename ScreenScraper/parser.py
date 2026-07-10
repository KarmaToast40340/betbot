import re
from collections import deque
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from config import STREETS, STRUCTURAL_MARKERS

HERO_NAME = "Karmatoast40"
STREET_NAMES = set(STREETS)
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
CARD_RANK_RE = re.compile(r"\b(10|[2-9AKQJT])\b", re.IGNORECASE)
COMPACT_CARD_SEQ_RE = re.compile(r"(?<![A-Za-z0-9])((?:10|[2-9AKQJT]){2,5})(?![A-Za-z0-9])", re.IGNORECASE)
CARDS_DEALT_INLINE_RE = re.compile(r"^CARDS\s+DEALT\s*(.*)$", re.IGNORECASE)
SHOWDOWN_INLINE_RE = re.compile(r"^SHOWDOWN\s+(.+)$", re.IGNORECASE)
BOARD_LINE_RE = re.compile(r"^\s*(?:10|[2-9AKQJT])(?:\s+(?:10|[2-9AKQJT])){0,4}\s*$", re.IGNORECASE)
MADE_HAND_RE = re.compile(
    r"\b(PAIR|TWO PAIR|TRIPS|THREE OF A KIND|STRAIGHT|FLUSH|FULL HOUSE|QUADS|FOUR OF A KIND|STRAIGHT FLUSH)\b",
    re.IGNORECASE,
)

ACTION_PATTERNS = [
    ("post_small_blind", re.compile(r"\bPost\s+small\s+blind(?:\s*\(?\s*([0-9]+(?:\.[0-9]+)?)\s*BB\s*\)?)?", re.IGNORECASE)),
    ("post_big_blind", re.compile(r"\bPost\s+big\s+blind(?:\s*\(?\s*([0-9]+(?:\.[0-9]+)?)\s*BB\s*\)?)?", re.IGNORECASE)),
    ("raise_to", re.compile(r"\bRaises\s+to\s+([0-9]+(?:\.[0-9]+)?)\s*BB\b", re.IGNORECASE)),
    ("bet", re.compile(r"\bBets\s+([0-9]+(?:\.[0-9]+)?)\s*BB\b", re.IGNORECASE)),
    ("call", re.compile(r"\bCalls\s+([0-9]+(?:\.[0-9]+)?)\s*BB\b", re.IGNORECASE)),
    ("check", re.compile(r"\bChecks?\b", re.IGNORECASE)),
    ("fold", re.compile(r"\bFolds?\b", re.IGNORECASE)),
    ("mucks", re.compile(r"\bMucks?\b", re.IGNORECASE)),
    ("wins", re.compile(r"\bWINS\s+([0-9]+(?:\.[0-9]+)?)\s*BB\b", re.IGNORECASE)),
    ("receives", re.compile(r"\bRECEIVES\s*:\s*(.+)$", re.IGNORECASE)),
]
ACTION_START_TOKENS = [
    "Post small blind",
    "Post big blind",
    "Raises to",
    "Bets",
    "Calls",
    "Checks",
    "Check",
    "Folds",
    "Fold",
    "Mucks",
    "Muck",
    "WINS",
    "RECEIVES",
]
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
    text = text.replace("♣", " ").replace("♠", " ").replace("♦", " ").replace("♥", " ")
    text = text.replace("♡", " ").replace("♢", " ")
    text = re.sub(r"&nbsp;", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"[ 	]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def split_lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def strip_heading_prefix(line: str) -> str:
    return re.sub(r"^#+\s*", "", (line or "").strip()).strip()


def normalize_rank(rank: str) -> str:
    rank = rank.upper()
    return "T" if rank == "10" else rank


def normalize_player_token(name: str) -> str:
    name = (name or "").strip()
    name = re.sub(r"[^A-Za-z0-9_]", "", name)
    return name.lower()


def space_compact_cards(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        chunk = match.group(1)
        tokens = re.findall(r"10|[2-9AKQJT]", chunk, flags=re.IGNORECASE)
        return " ".join(tokens)
    return COMPACT_CARD_SEQ_RE.sub(repl, text or "")


def extract_rank_only_cards(text: str) -> list[str]:
    text = space_compact_cards(text or "")
    return [normalize_rank(token) for token in CARD_RANK_RE.findall(text)]


def extract_strict_cards(text: str, expected: int | None = None) -> list[str]:
    if not text:
        return []
    cards = extract_rank_only_cards(text)
    if expected is None:
        return cards
    if len(cards) < expected:
        return []
    return cards[:expected]


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
    for i, line in enumerate(lines):
        cleaned = strip_heading_prefix(line)
        inline = CARDS_DEALT_INLINE_RE.match(cleaned)
        if inline:
            cards = extract_strict_cards(inline.group(1), expected=2)
            if cards:
                return cards
        if cleaned.upper() == "CARDS DEALT":
            for probe in lines[i + 1 : i + 6]:
                probe_clean = strip_heading_prefix(probe)
                probe_upper = probe_clean.upper()
                if probe_upper in STREET_NAMES:
                    break
                cards = extract_strict_cards(probe_clean, expected=2)
                if cards:
                    return cards
    return []


def parse_board(lines: list[str]) -> dict[str, Any]:
    board = {"flop": [], "turn": None, "river": None, "all_cards": []}
    for i, line in enumerate(lines):
        cleaned = strip_heading_prefix(line)
        upper = cleaned.upper()
        if upper.startswith("FLOP"):
            payload = cleaned[4:].strip()
            cards = extract_strict_cards(payload, expected=3)
            if not cards and i + 1 < len(lines):
                cards = extract_strict_cards(strip_heading_prefix(lines[i + 1]), expected=3)
            if cards:
                board["flop"] = cards[:3]
        elif upper.startswith("TURN"):
            payload = cleaned[4:].strip()
            cards = extract_strict_cards(payload, expected=4)
            if not cards and i + 1 < len(lines):
                cards = extract_strict_cards(strip_heading_prefix(lines[i + 1]), expected=4)
            if cards:
                board["turn"] = cards[3]
        elif upper.startswith("RIVER"):
            payload = cleaned[5:].strip()
            cards = extract_strict_cards(payload, expected=5)
            if not cards and i + 1 < len(lines):
                cards = extract_strict_cards(strip_heading_prefix(lines[i + 1]), expected=5)
            if cards:
                board["river"] = cards[4]
    board["all_cards"] = board["flop"][:]
    if board["turn"]:
        board["all_cards"].append(board["turn"])
    if board["river"]:
        board["all_cards"].append(board["river"])
    return board


def contains_action_words(line: str) -> bool:
    lowered = strip_heading_prefix(line).lower()
    return any(token.lower() in lowered for token in ACTION_START_TOKENS)


def is_board_line(line: str) -> bool:
    return bool(BOARD_LINE_RE.fullmatch(space_compact_cards(strip_heading_prefix(line))))


def is_probable_player_name(line: str) -> bool:
    if not line:
        return False
    line = strip_heading_prefix(line)
    upper = line.upper()
    if not line or upper in BANNED_NAME_TOKENS or upper in STREET_NAMES:
        return False
    if upper.startswith("CARDS DEALT") or upper.startswith("SHOWDOWN"):
        return False
    if HAND_LINE_RE.match(line):
        return False
    if contains_action_words(line):
        return False
    if MADE_HAND_RE.search(line):
        return False
    if is_board_line(line):
        return False
    if re.search(r"\b(BB|SB)\b", upper):
        return False
    if ":" in line:
        return False
    if len(line) > 32:
        return False
    return bool(re.search(r"[A-Za-z]", line))


def names_look_like_same_player(left: str, right: str) -> bool:
    a = normalize_player_token(left)
    b = normalize_player_token(right)
    if not a or not b:
        return False
    if a == b:
        return True
    if a == normalize_player_token(HERO_NAME) or b == normalize_player_token(HERO_NAME):
        return a == b
    digits_a = "".join(ch for ch in a if ch.isdigit())
    digits_b = "".join(ch for ch in b if ch.isdigit())
    if digits_a and digits_b and digits_a != digits_b:
        return False
    ratio = SequenceMatcher(None, a, b).ratio()
    return ratio >= 0.86


def choose_canonical_name(existing: str, candidate: str) -> str:
    if normalize_player_token(candidate) == normalize_player_token(HERO_NAME):
        return HERO_NAME
    score_existing = (sum(ch.isdigit() for ch in existing), len(existing))
    score_candidate = (sum(ch.isdigit() for ch in candidate), len(candidate))
    return candidate if score_candidate > score_existing else existing


def merge_player_name(candidate: str, canonicals: list[str]) -> str:
    if normalize_player_token(candidate) == normalize_player_token(HERO_NAME):
        return HERO_NAME
    for idx, existing in enumerate(canonicals):
        if names_look_like_same_player(existing, candidate):
            better = choose_canonical_name(existing, candidate)
            canonicals[idx] = better
            return better
    canonicals.append(candidate)
    return candidate


def collect_raw_player_names(lines: list[str]) -> list[str]:
    raw_names = []
    seen = set()
    for line in lines:
        cleaned = strip_heading_prefix(line)
        if is_probable_player_name(cleaned):
            key = cleaned.lower()
            if key not in seen:
                seen.add(key)
                raw_names.append(cleaned)
        inline = extract_inline_actor(cleaned)
        if inline:
            actor, _ = inline
            if is_probable_player_name(actor):
                key = actor.lower()
                if key not in seen:
                    seen.add(key)
                    raw_names.append(actor)
        showdown_inline = SHOWDOWN_INLINE_RE.match(cleaned)
        if showdown_inline:
            actor = showdown_inline.group(1).strip()
            if is_probable_player_name(actor):
                key = actor.lower()
                if key not in seen:
                    seen.add(key)
                    raw_names.append(actor)
    return raw_names


def canonicalize_players(raw_names: list[str]) -> tuple[list[str], dict[str, str]]:
    canonical_players = [HERO_NAME]
    alias_map = {normalize_player_token(HERO_NAME): HERO_NAME}
    for raw in raw_names:
        canonical = merge_player_name(raw, canonical_players)
        alias_map[normalize_player_token(raw)] = canonical
    deduped = []
    seen = set()
    for player in canonical_players:
        key = normalize_player_token(player)
        if key not in seen:
            seen.add(key)
            deduped.append(HERO_NAME if key == normalize_player_token(HERO_NAME) else player)
    if HERO_NAME not in deduped:
        deduped.insert(0, HERO_NAME)
    for player in deduped:
        alias_map[normalize_player_token(player)] = player
    return deduped, alias_map


def canonicalize_name(name: str | None, players: list[str], alias_map: dict[str, str]) -> str | None:
    if not name:
        return None
    token = normalize_player_token(name)
    if token == normalize_player_token(HERO_NAME):
        return HERO_NAME
    if token in alias_map:
        return alias_map[token]
    for player in players:
        if names_look_like_same_player(player, name):
            alias_map[token] = player
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


def iter_action_matches(segment: str) -> list[tuple[int, int, dict[str, Any]]]:
    segment = strip_heading_prefix(segment).strip()
    if not segment:
        return []
    matches = []
    for action_name, pattern in ACTION_PATTERNS:
        for match in pattern.finditer(segment):
            amount = None
            cards = None
            if action_name == "receives":
                cards = extract_strict_cards(match.group(1), expected=2)
            elif match.groups():
                raw_amount = match.group(1)
                if raw_amount not in (None, ""):
                    try:
                        amount = float(raw_amount)
                    except (ValueError, TypeError):
                        amount = None
            action = {"action": action_name, "amount_bb": amount, "raw": segment}
            if cards:
                action["cards"] = cards
            matches.append((match.start(), match.end(), action))
    matches.sort(key=lambda item: (item[0], item[1]))
    return matches


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
        action = {"street": street, "player": None, "action": action_name, "amount_bb": None, "raw": marker}
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


def normalize_street_name(upper: str) -> str:
    if upper == "PRE-FLOP":
        return "preflop"
    if upper == "FLOP":
        return "flop"
    if upper == "TURN":
        return "turn"
    if upper == "RIVER":
        return "river"
    return "showdown"


def infer_initial_order(street: str, players: list[str], hero_name: str | None) -> list[str]:
    if len(players) != 2:
        return players[:]
    hero = hero_name if hero_name in players else players[0]
    villain = players[1] if players[0] == hero else players[0]
    if street == "preflop":
        return [hero, villain]
    return [villain, hero]


def rebuild_queue_from_context(context_names: list[str], players: list[str], street: str, hero_name: str | None) -> deque[str]:
    base_order = infer_initial_order(street, players, hero_name)
    if len(players) != 2:
        ordered = []
        seen = set()
        for name in context_names:
            if name in players and name not in seen:
                ordered.append(name)
                seen.add(name)
        for name in players:
            if name not in seen:
                ordered.append(name)
        return deque(ordered)
    if len(context_names) >= 2:
        return deque(context_names[:2])
    if len(context_names) == 1:
        first = context_names[0]
        second = next((p for p in base_order if p != first), None)
        return deque([n for n in [first, second] if n])
    return deque(base_order)


def consume_implicit_actor(turn_queue: deque[str], fallback_order: list[str]) -> str | None:
    if turn_queue:
        actor = turn_queue.popleft()
        turn_queue.append(actor)
        return actor
    return fallback_order[0] if fallback_order else None


def rotate_from_explicit(turn_queue: deque[str], actor: str | None, fallback_order: list[str]):
    if not actor:
        return
    if actor in turn_queue:
        while turn_queue and turn_queue[0] != actor:
            turn_queue.rotate(-1)
        if turn_queue:
            turn_queue.popleft()
            turn_queue.append(actor)
            turn_queue.rotate(-1)
        return
    if len(fallback_order) == 2 and actor in fallback_order:
        other = fallback_order[1] if fallback_order[0] == actor else fallback_order[0]
        turn_queue.clear()
        turn_queue.extend([other, actor])


def reconcile_showdown_winner(actions: list[dict[str, Any]], showdown: dict[str, Any] | None):
    if not showdown or not showdown.get("winners"):
        return actions
    winner = showdown["winners"][0].get("player")
    amount = showdown["winners"][0].get("amount_bb")
    for action in actions:
        if action.get("street") == "showdown" and action.get("action") == "wins":
            action["player"] = winner
            if amount is not None:
                action["amount_bb"] = amount
    return actions


def iter_action_matches(line):
    # Ajout de "post small/big blind" au pattern
    # On capture l'action, et on cherche le montant si présent
    pattern = r"(?P<action>calls|raises|bets|folds|checks|post\s+small\s+blind|post\s+big\s+blind)(?:\s+(?:to|an)?\s*(?P<amount>[\d\.]+))?"
    matches = list(re.finditer(pattern, line, re.IGNORECASE))
    
    results = []
    for m in matches:
        act = m.group("action").lower().replace(" ", "_")
        data = {"action": act}
        if m.group("amount"):
            data["amount_bb"] = float(m.group("amount"))
        results.append(data)
    return results

from collections import deque
import re

def parse_actions(lines, players, alias_map, hero_name=None, hero_cards=None, board=None, showdown_present=False, showdown=None):
    actions = []
    player_queue = deque()
    action_queue = deque()
    
    current_street = "blinds"
    
    for line in lines:
        line_clean = line.strip()
        upper = line_clean.upper()
        if not line_clean: 
            continue

        # 1. Gestion des changements de street
        if upper in STREET_NAMES or upper.startswith("SHOWDOWN"):
            current_street = normalize_street_name(upper if upper in STREET_NAMES else "SHOWDOWN")
            # On vide les files au changement de street pour éviter les couplages aberrants
            player_queue.clear()
            action_queue.clear()
            continue
            
        # 2. Détection
        detected_actions = iter_action_matches(line_clean)
        is_player = is_probable_player_name(line_clean)
        
        # Logique : Si on trouve un joueur, on l'ajoute.
        # Si on trouve une action, on l'ajoute.
        # Le couplage FIFO se chargera de les associer intelligemment.
        if is_player:
            player_queue.append(canonicalize_name(line_clean, players, alias_map))
            
        if detected_actions:
            for act in detected_actions:
                action_queue.append(act)
        
        # 3. Moteur de couplage (FIFO)
        # On tente de coupler tant qu'on a les deux éléments
        while action_queue and player_queue:
            action_data = action_queue.popleft()
            player = player_queue.popleft()
            
            action_entry = {
                "seq": len(actions),
                "street": current_street,
                "player": player,
                "action": action_data["action"]
            }
            if "amount_bb" in action_data and action_data["amount_bb"] is not None:
                action_entry["amount_bb"] = action_data["amount_bb"]
            
            actions.append(action_entry)

    # --- Post-traitement ---
    if hero_name and hero_cards:
        actions.insert(0, {"seq": 0, "street": "preflop", "player": hero_name, "action": "hero_cards", "cards": hero_cards})
    
    structural = extract_structural_actions(lines, board or {}, showdown_present)
    
    deduped = []
    seen = set()
    for a in structural + actions:
        # On définit une clé unique pour éviter les doublons structurels
        key = (a.get("street"), a.get("player"), a.get("action"), a.get("amount_bb"))
        if a.get("player") is None:
            if key not in seen:
                deduped.append(a)
                seen.add(key)
        else:
            deduped.append(a)
            
    final_actions = assign_blind_owners(deduped, players, hero_name)
    final_actions = reconcile_showdown_winner(final_actions, showdown)
    
    return final_actions

def parse_showdown(lines, players, alias_map, hero_cards, board):
    idx = None
    current_player = None
    for i, line in enumerate(lines):
        cleaned = strip_heading_prefix(line)
        upper = cleaned.upper()
        if upper == "SHOWDOWN" or upper.startswith("SHOWDOWN "):
            idx = i
            inline = SHOWDOWN_INLINE_RE.match(cleaned)
            if inline:
                current_player = canonicalize_name(inline.group(1).strip(), players, alias_map)
            break
    if idx is None:
        return None
    showdown = {"players": [], "winners": []}
    seen_players = set()
    seen_winners = set()

    def ensure_player(name):
        if name and name not in seen_players:
            showdown["players"].append({"name": name, "hole_cards": []})
            seen_players.add(name)

    ensure_player(current_player)
    for line in lines[idx + 1:]:
        cleaned = strip_heading_prefix(line)
        upper = cleaned.upper()
        if upper in STREET_NAMES and upper != "SHOWDOWN":
            break
        inline = extract_inline_actor(cleaned)
        if inline:
            actor, segment = inline
            player = canonicalize_name(actor, players, alias_map)
            ensure_player(player)
            for _, _, base_action in iter_action_matches(segment):
                if base_action["action"] == "wins":
                    key = (player, base_action.get("amount_bb"))
                    if key not in seen_winners:
                        seen_winners.add(key)
                        showdown["winners"].append({"player": player, "amount_bb": base_action.get("amount_bb")})
                    current_player = player
            continue
        if is_probable_player_name(cleaned):
            current_player = canonicalize_name(cleaned, players, alias_map)
            ensure_player(current_player)
            continue
        if current_player and MADE_HAND_RE.search(cleaned):
            for entry in showdown["players"]:
                if entry["name"] == current_player:
                    entry["made_hand"] = cleaned
                    break
            continue
        cards = extract_strict_cards(cleaned, expected=2)
        if current_player and cards:
            if current_player == HERO_NAME and hero_cards and cards == hero_cards:
                for entry in showdown["players"]:
                    if entry["name"] == current_player and not entry.get("hole_cards"):
                        entry["hole_cards"] = hero_cards[:2]
                        break
                continue
            if cards == board.get("flop", [])[:2]:
                continue
            for entry in showdown["players"]:
                if entry["name"] == current_player and not entry.get("hole_cards"):
                    entry["hole_cards"] = cards[:2]
                    break
            continue
        win_match = re.search(r"\bWINS\s+([0-9]+(?:\.[0-9]+)?)\s*BB\b", cleaned, flags=re.IGNORECASE)
        if current_player and win_match:
            amount = float(win_match.group(1))
            key = (current_player, amount)
            if key not in seen_winners:
                seen_winners.add(key)
                showdown["winners"].append({"player": current_player, "amount_bb": amount})
    for entry in showdown["players"]:
        entry.setdefault("hole_cards", [])
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
    raw_players = collect_raw_player_names(lines)
    players, alias_map = canonicalize_players(raw_players)
    hero_name = HERO_NAME
    hero_cards = parse_hero_cards(lines, raw_text=raw_text)
    board = parse_board(lines)
    showdown = parse_showdown(lines, players, alias_map, hero_cards, board)
    actions = parse_actions(
        lines,
        players,
        alias_map,
        hero_name=hero_name,
        hero_cards=hero_cards,
        board=board,
        showdown_present=showdown is not None,
        showdown=showdown,
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