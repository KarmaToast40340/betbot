import hashlib
import json
import time
from datetime import datetime
from pathlib import Path

from capture import capture_region_to_png
from config import INPUT_PATH, MONITOR, OUTPUT_DIR, STATE_LOG_PATH
from ocr_engine import run_ocr
from parser import parse_ocr_document

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
        
        # Mise à jour des données structurelles
        existing["current_street"] = new_data.get("current_street", existing["current_street"])
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
    digits = "".join(filter(str.isdigit, str(h_id)))
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

def monitor_loop(interval_sec=1.0):
    print(f"Monitoring: {MONITOR}")
    last_image_hash = None

    while True:
        img = capture_region_to_png(INPUT_PATH)
        if img is None:
            time.sleep(interval_sec)
            continue

        current_image_hash = image_fingerprint(img)
        if current_image_hash == last_image_hash:
            time.sleep(interval_sec)
            continue

        last_image_hash = current_image_hash
        print(f"[{datetime.now().isoformat(timespec='seconds')}] Analyse OCR...")

        raw_text, _ = run_ocr(INPUT_PATH, OUTPUT_DIR)
        states = parse_ocr_document(raw_text, INPUT_PATH)
        
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