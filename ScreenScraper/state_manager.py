import hashlib
import json


def image_fingerprint(img, hash_size=8):
    import cv2
    import numpy as np

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    small = cv2.resize(gray, (hash_size, hash_size))
    avg = small.mean()
    bits = (small > avg).astype(np.uint8).flatten()
    return "".join(map(str, bits.tolist()))


def state_signature(state):
    compact = {
        "hand_id": state.get("hand_id"),
        "street": state.get("current_street"),
        "hero": state.get("hero", {}).get("name"),
        "hero_cards": state.get("hero", {}).get("hole_cards_raw"),
        "board": state.get("board", {}).get("all_cards"),
        "actions": [
            {
                "street": a.get("street"),
                "player": a.get("player"),
                "action": a.get("action"),
                "amount_bb": a.get("amount_bb"),
            }
            for a in state.get("actions", [])
        ],
        "showdown": state.get("showdown"),
    }
    payload = json.dumps(compact, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def append_jsonl(path, obj: dict):
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")
