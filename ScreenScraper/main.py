import hashlib
import json
import time
from datetime import datetime
from pathlib import Path

from capture import capture_region_to_png
from config import INPUT_PATH, MONITOR, OUTPUT_DIR, STATE_LOG_PATH, TURN_SIGNAL_PATH
from ocr_engine import run_ocr
from parser import parse_ocr_document
from turn_detector import is_hero_turn

# Définition de l'ordre des streets pour la progression
STREET_ORDER = {"blinds": 0, "preflop": 1, "flop": 2, "turn": 3, "river": 4, "showdown": 5}

class HandStateManager:
    def __init__(self):
        self.active_hands = {}

    def merge_actions_by_street(self, old_actions, new_actions):
        # Identifie les streets contenues dans la nouvelle capture
        new_streets = {a.get("street") for a in new_actions}
        # Garde les anciennes actions uniquement pour les streets non présentes dans la nouvelle capture
        filtered_old = [a for a in old_actions if a.get("street") not in new_streets]
        return filtered_old + new_actions

    def process_new_capture(self, new_data):
        h_id = new_data.get("hand_id")
        
        if h_id not in self.active_hands:
            self.active_hands[h_id] = new_data
            return new_data

        existing = self.active_hands[h_id]
        
        # Fusion des actions par remplacement sélectif (écrase la street courante)
        existing["actions"] = self.merge_actions_by_street(
            existing.get("actions", []), 
            new_data.get("actions", [])
        )
        
        # Mise à jour des données structurelles : ne jamais régresser sur un
        # street déjà connu si une capture bruitée relit une street plus
        # ancienne (STREET_ORDER existait déjà mais n'était utilisé nulle
        # part avant ce correctif).
        new_street = new_data.get("current_street")
        existing_street = existing.get("current_street")
        if STREET_ORDER.get(new_street, -1) >= STREET_ORDER.get(existing_street, -1):
            existing["current_street"] = new_street
            existing["board"] = new_data.get("board", existing["board"])
        existing["showdown"] = new_data.get("showdown") or existing.get("showdown")
        existing["raw_text"] = new_data.get("raw_text", existing["raw_text"])
        
        self.active_hands[h_id] = existing
        return existing

manager = HandStateManager()

def image_fingerprint(img):
    import cv2
    ok, encoded = cv2.imencode(".png", img)
    if not ok: return None
    return hashlib.sha256(encoded.tobytes()).hexdigest()

def read_jsonl(path: Path):
    if not path.exists(): return []
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip(): rows.append(json.loads(line))
    return rows

def write_jsonl(path: Path, rows):
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

def get_canonical_hand_id(h_id):
    h_id = str(h_id or "")
    # Real hand ids look like "{session_id}-{hand_number}-{timestamp}", e.g.
    # "4938973414124683265-10-1784135602". The trailing timestamp segment is
    # frequently missing/truncated in early captures of a hand (OCR reads it
    # before the full id has rendered) — "last N digits of everything" is
    # NOT stable under that truncation (the last digits come from a
    # different segment depending on whether the suffix is present), so the
    # same real hand was ending up as two separate rows. The hand-sequence
    # segment (index 1) stays present and identical across partial/complete
    # captures of the same hand, so key on session_id + hand_number instead.
    parts = h_id.split("-")
    if len(parts) >= 2 and parts[0] and parts[1].isdigit():
        return f"{parts[0]}-{parts[1]}"
    digits = "".join(filter(str.isdigit, h_id))
    return digits[-5:] if len(digits) >= 5 else digits

def upsert_states_preserve_history(path: Path, new_states):
    rows = read_jsonl(path)
    # Mapping des index par hand_id
    index_by_hand_id = {row.get("hand_id"): i for i, row in enumerate(rows) if row.get("hand_id")}

    for state in new_states:
        h_id = state.get("hand_id")
        if h_id in index_by_hand_id:
            # Mise à jour de la ligne existante
            rows[index_by_hand_id[h_id]] = state
        else:
            # Nouvelle main
            rows.append(state)
            index_by_hand_id[h_id] = len(rows) - 1

    write_jsonl(path, rows)

def write_turn_signal(hero_turn: bool):
    payload = {"hero_turn": hero_turn, "timestamp_utc": datetime.utcnow().isoformat() + "Z"}
    TURN_SIGNAL_PATH.write_text(json.dumps(payload), encoding="utf-8")

def monitor_loop(interval_sec=1.0):
    print(f"Monitoring: {MONITOR}")
    last_image_hash = None
    last_hero_turn = None

    while True:
        # Cheap color check on the Check button, done every tick regardless
        # of the OCR image-hash dedup below — the OCR analysis only runs
        # every ~10s in practice (full hand-history zone + OCR round-trip),
        # far too slow to catch "it's your turn" reliably. This is a direct
        # visual signal, no OCR needed, so it can run every interval_sec.
        try:
            hero_turn = is_hero_turn()
        except Exception as e:
            print(f"[turn_detector] error: {e}")
            hero_turn = False
        if hero_turn != last_hero_turn:
            last_hero_turn = hero_turn
            write_turn_signal(hero_turn)

        img = capture_region_to_png(INPUT_PATH)
        if img is None:
            time.sleep(interval_sec)
            continue

        current_image_hash = image_fingerprint(img)
        if current_image_hash == last_image_hash:
            time.sleep(interval_sec)
            continue

        print(f"[{datetime.now().isoformat(timespec='seconds')}] Analyse OCR...")

        # A transient failure here (e.g. paddleocr-vlm-server still loading
        # its model at startup — depends_on only waits for the container to
        # start, not for the server inside it to be ready) used to crash the
        # whole process (restart: "no" means no auto-recovery). Log and
        # retry instead: last_image_hash is only advanced on success, so
        # this same frame gets retried next tick rather than silently lost.
        try:
            raw_text, _ = run_ocr(INPUT_PATH, OUTPUT_DIR)
            states = parse_ocr_document(raw_text, INPUT_PATH)
        except Exception as e:
            print(f"[ocr] error: {e} — will retry this frame next tick")
            time.sleep(interval_sec)
            continue

        last_image_hash = current_image_hash

        merged_states = []
        for state_data in states:
            state_data["hand_id"] = get_canonical_hand_id(state_data.get("hand_id", ""))
            latest_state = manager.process_new_capture(state_data)
            merged_states.append(latest_state)
            print(f"Main {latest_state.get('hand_id')} | Street: {latest_state.get('current_street')}")

        if merged_states:
            upsert_states_preserve_history(STATE_LOG_PATH, merged_states)
            
        time.sleep(interval_sec)

if __name__ == "__main__":
    monitor_loop()