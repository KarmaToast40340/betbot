import hashlib
import json
import time
from datetime import datetime
from pathlib import Path

from capture import capture_region_to_png
from config import INPUT_PATH, LATEST_STATE_PATH, MONITOR, OUTPUT_DIR, RAW_OCR_PATH, SERVER_URL, STATE_LOG_PATH
from ocr_engine import run_ocr
from parser import parse_ocr_document


def image_fingerprint(img):
    import cv2

    ok, encoded = cv2.imencode(".png", img)
    if not ok:
        return None
    return hashlib.sha256(encoded.tobytes()).hexdigest()


def read_jsonl(path: Path):
    if not path.exists():
        return []
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def write_jsonl(path: Path, rows):
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def state_signature(state):
    compact = {
        "hand_id": state.get("hand_id"),
        "hero": state.get("hero", {}).get("name"),
        "hero_cards": state.get("hero", {}).get("hole_cards_raw"),
        "board": state.get("board", {}).get("all_cards"),
        "current_street": state.get("current_street"),
        "actions": [
            {
                "street": action.get("street"),
                "player": action.get("player"),
                "action": action.get("action"),
                "amount_bb": action.get("amount_bb"),
                "cards": action.get("cards"),
            }
            for action in state.get("actions", [])
        ],
        "showdown": state.get("showdown"),
    }
    payload = json.dumps(compact, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def merge_unique_actions(old_actions, new_actions):
    merged = []
    seen = set()
    
    # On itère sur la liste combinée
    for action in (old_actions or []) + (new_actions or []):
        # Clé composée ultra-spécifique pour éviter les collisions
        key = (
            action.get("street"),
            action.get("player"),
            action.get("action"),
            action.get("amount_bb"),
            # On transforme les listes en tuples pour qu'ils soient hashables
            tuple(sorted(action.get("cards", []) or [])),
            action.get("showdown_present")
        )
        
        if key in seen:
            continue
            
        seen.add(key)
        merged.append(action)
    return merged


def merge_unique_players(old_players, new_players):
    merged = []
    seen = set()
    for player in (old_players or []) + (new_players or []):
        name = player.get("name") if isinstance(player, dict) else None
        if not name:
            continue
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        merged.append({"name": name})
    return merged


def merge_showdown(old_showdown, new_showdown):
    if not old_showdown:
        return new_showdown
    if not new_showdown:
        return old_showdown

    players = []
    seen_players = set()
    for entry in (old_showdown.get("players") or []) + (new_showdown.get("players") or []):
        name = entry.get("name")
        if not name:
            continue
        key = name.lower()
        existing = next((p for p in players if p["name"].lower() == key), None)
        if existing:
            if not existing.get("hole_cards") and entry.get("hole_cards"):
                existing["hole_cards"] = entry.get("hole_cards")
            if not existing.get("made_hand") and entry.get("made_hand"):
                existing["made_hand"] = entry.get("made_hand")
            continue
        seen_players.add(key)
        players.append(
            {
                "name": name,
                "hole_cards": entry.get("hole_cards", []),
                **({"made_hand": entry["made_hand"]} if entry.get("made_hand") else {}),
            }
        )

    winners = []
    seen_winners = set()
    for winner in (old_showdown.get("winners") or []) + (new_showdown.get("winners") or []):
        key = (winner.get("player"), winner.get("amount_bb"))
        if key in seen_winners:
            continue
        seen_winners.add(key)
        winners.append(winner)

    return {"players": players, "winners": winners}


def choose_value(old_value, new_value):
    if new_value not in (None, "", [], {}):
        return new_value
    return old_value


def merge_state(existing, incoming):
    merged = dict(existing)
    merged["timestamp_utc"] = incoming.get("timestamp_utc", existing.get("timestamp_utc"))
    merged["source_image"] = choose_value(existing.get("source_image"), incoming.get("source_image"))
    merged["hand_id"] = choose_value(existing.get("hand_id"), incoming.get("hand_id"))

    existing_blinds = existing.get("blinds", {}) or {}
    incoming_blinds = incoming.get("blinds", {}) or {}
    merged["blinds"] = {
        "sb": choose_value(existing_blinds.get("sb"), incoming_blinds.get("sb")),
        "bb": choose_value(existing_blinds.get("bb"), incoming_blinds.get("bb")),
    }

    existing_hero = existing.get("hero", {}) or {}
    incoming_hero = incoming.get("hero", {}) or {}
    merged["hero"] = {
        "name": choose_value(existing_hero.get("name"), incoming_hero.get("name")),
        "hole_cards_raw": choose_value(existing_hero.get("hole_cards_raw"), incoming_hero.get("hole_cards_raw")) or [],
    }

    merged["players"] = merge_unique_players(existing.get("players"), incoming.get("players"))

    existing_board = existing.get("board", {}) or {}
    incoming_board = incoming.get("board", {}) or {}
    merged_board = {
        "flop": choose_value(existing_board.get("flop"), incoming_board.get("flop")) or [],
        "turn": choose_value(existing_board.get("turn"), incoming_board.get("turn")),
        "river": choose_value(existing_board.get("river"), incoming_board.get("river")),
        "all_cards": choose_value(existing_board.get("all_cards"), incoming_board.get("all_cards")) or [],
    }
    merged["board"] = merged_board

    existing_street = existing.get("current_street")
    incoming_street = incoming.get("current_street")
    merged["current_street"] = incoming_street or existing_street
    merged["actions"] = merge_unique_actions(existing.get("actions"), incoming.get("actions"))
    merged["showdown"] = merge_showdown(existing.get("showdown"), incoming.get("showdown"))
    merged["raw_text"] = choose_value(existing.get("raw_text"), incoming.get("raw_text"))
    merged["events"] = incoming.get("events") or existing.get("events") or []
    return merged


def upsert_states_preserve_history(path: Path, new_states):
    rows = read_jsonl(path)
    index_by_hand_id = {}
    signatures = set()

    for idx, row in enumerate(rows):
        hand_id = row.get("hand_id")
        if hand_id and hand_id not in index_by_hand_id:
            index_by_hand_id[hand_id] = idx
        signatures.add(state_signature(row))

    inserted = 0
    updated = 0
    skipped = 0

    for state in new_states:
        signature = state_signature(state)
        if signature in signatures:
            skipped += 1
            continue

        hand_id = state.get("hand_id")
        if hand_id and hand_id in index_by_hand_id:
            idx = index_by_hand_id[hand_id]
            merged = merge_state(rows[idx], state)
            merged_signature = state_signature(merged)
            if merged_signature != state_signature(rows[idx]):
                rows[idx] = merged
                signatures.add(merged_signature)
                updated += 1
            else:
                skipped += 1
            signatures.add(signature)
            continue

        rows.append(state)
        if hand_id and hand_id not in index_by_hand_id:
            index_by_hand_id[hand_id] = len(rows) - 1
        signatures.add(signature)
        inserted += 1

    write_jsonl(path, rows)
    return inserted, updated, skipped


def monitor_loop(interval_sec=1.0):
    print(f"Monitoring region: {MONITOR}")
    print(f"Server URL: {SERVER_URL}")

    last_image_hash = None

    while True:
        img = capture_region_to_png(INPUT_PATH)
        if img is None:
            print("Capture échouée.")
            time.sleep(interval_sec)
            continue

        current_image_hash = image_fingerprint(img)
        if current_image_hash == last_image_hash:
            time.sleep(interval_sec)
            continue

        last_image_hash = current_image_hash
        print(f"\n[{datetime.now().isoformat(timespec='seconds')}] Changement visuel détecté, OCR...")

        raw_text, _artifacts = run_ocr(INPUT_PATH, OUTPUT_DIR)
        RAW_OCR_PATH.write_text(raw_text, encoding="utf-8")

        states = parse_ocr_document(raw_text, INPUT_PATH)
        if not states:
            time.sleep(interval_sec)
            continue

        latest_state = states[-1]
        LATEST_STATE_PATH.write_text(json.dumps(latest_state, ensure_ascii=False, indent=2), encoding="utf-8")

        inserted, updated, skipped = upsert_states_preserve_history(STATE_LOG_PATH, states)

        print(
            f"{inserted} nouvelle(s) main(s), {updated} main(s) mise(s) à jour, {skipped} état(s) ignoré(s), "
            f"latest hand_id={latest_state.get('hand_id')} street={latest_state.get('current_street')}"
        )
        time.sleep(interval_sec)


if __name__ == "__main__":
    monitor_loop(interval_sec=1.0)
