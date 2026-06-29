import json
import time
from datetime import datetime

from capture import capture_region_to_png
from config import INPUT_PATH, LATEST_STATE_PATH, OUTPUT_DIR, RAW_OCR_PATH, SERVER_URL, STATE_LOG_PATH, MONITOR
from ocr_engine import run_ocr_and_parse
from state_manager import append_jsonl, image_fingerprint, state_signature


def monitor_loop(interval_sec=1.0):
    print(f"Monitoring region: {MONITOR}")
    print(f"Server URL: {SERVER_URL}")

    last_image_hash = None
    last_state_hash = None

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

        raw_text, parsed_results = run_ocr_and_parse(INPUT_PATH, OUTPUT_DIR)
        RAW_OCR_PATH.write_text(raw_text, encoding="utf-8")

        if not parsed_results:
            time.sleep(interval_sec)
            continue

        state = parsed_results[0]
        sig = state_signature(state)

        if sig == last_state_hash:
            print("État OCR identique au précédent, ignoré.")
            time.sleep(interval_sec)
            continue

        last_state_hash = sig
        state["state_signature"] = sig
        LATEST_STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        append_jsonl(STATE_LOG_PATH, state)
        print(f"Nouvel état sauvegardé: street={state.get('current_street')} hand_id={state.get('hand_id')}")

        time.sleep(interval_sec)


if __name__ == "__main__":
    monitor_loop(interval_sec=1.0)
