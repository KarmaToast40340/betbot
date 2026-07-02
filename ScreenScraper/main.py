import hashlib
import json
import time
from datetime import datetime

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


def append_jsonl(path, obj):
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(obj, ensure_ascii=False) + "\n")


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


def monitor_loop(interval_sec=1.0):
    print(f"Monitoring region: {MONITOR}")
    print(f"Server URL: {SERVER_URL}")

    last_image_hash = None
    seen_signatures = set()

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

        new_count = 0
        for state in states:
            signature = state_signature(state)
            if signature in seen_signatures:
                continue
            seen_signatures.add(signature)
            append_jsonl(STATE_LOG_PATH, state)
            new_count += 1

        print(
            f"{new_count} nouvel(x) état(s) sauvegardé(s), "
            f"latest hand_id={latest_state.get('hand_id')} street={latest_state.get('current_street')}"
        )
        time.sleep(interval_sec)


if __name__ == "__main__":
    monitor_loop(interval_sec=1.0)