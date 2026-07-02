import json
import re
import statistics
from collections import defaultdict
from pathlib import Path

ANCHORS = ["CARDS DEALT", "FLOP", "TURN", "RIVER"]
TEXT_KEYS = ("block_content", "text", "transcription", "content", "value", "label")
BBOX_KEYS = ("block_bbox", "coordinate")
CARDISH_RE = re.compile(r"(10|[2-9AKQJT0O])(?:\s*[♥♦♣♠♡♢hdcs])?", re.IGNORECASE)


def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def iter_nodes(obj):
    if isinstance(obj, dict):
        yield obj
        for value in obj.values():
            yield from iter_nodes(value)
    elif isinstance(obj, list):
        for item in obj:
            yield from iter_nodes(item)


def extract_text(node):
    if not isinstance(node, dict):
        return None
    for key in TEXT_KEYS:
        value = node.get(key)
        if isinstance(value, str):
            value = value.strip()
            if value:
                return value
    return None


def extract_label(node):
    if not isinstance(node, dict):
        return ""
    return str(node.get("block_label") or node.get("label") or "").strip().lower()


def extract_bbox(node):
    if not isinstance(node, dict):
        return None
    for key in BBOX_KEYS:
        value = node.get(key)
        if isinstance(value, list) and len(value) >= 4:
            try:
                return [float(value[0]), float(value[1]), float(value[2]), float(value[3])]
            except Exception:
                pass
        if isinstance(value, str):
            nums = re.findall(r"-?\d+(?:\.\d+)?", value)
            if len(nums) >= 4:
                try:
                    return [float(nums[0]), float(nums[1]), float(nums[2]), float(nums[3])]
                except Exception:
                    pass
    return None


def collect_items(payload):
    items = []
    for node in iter_nodes(payload):
        bbox = extract_bbox(node)
        if not bbox:
            continue
        items.append({
            "label": extract_label(node),
            "text": extract_text(node) or "",
            "bbox": bbox,
        })
    items.sort(key=lambda item: (item["bbox"][1], item["bbox"][0]))
    return items


def normalize_anchor(text: str):
    clean = re.sub(r"\s+", " ", (text or "").strip()).upper()
    return clean if clean in ANCHORS else None


def looks_like_card_target(item: dict) -> bool:
    text = item["text"] or ""
    label = item["label"]
    if label == "image":
        return True
    if "img_in_image_box" in text.lower():
        return True
    return bool(CARDISH_RE.search(text))


def find_target(anchor_item: dict, items: list[dict], max_local_y=80):
    ax1, ay1, ax2, ay2 = anchor_item["bbox"]
    best = None
    best_score = None
    for item in items:
        if item is anchor_item:
            continue
        if not looks_like_card_target(item):
            continue
        ix1, iy1, ix2, iy2 = item["bbox"]
        dx = ix1 - ax1
        dy = iy1 - ay1
        if dx < 20:
            continue
        if abs(dy) > max_local_y:
            continue
        score = (
            0 if item["label"] == "image" else 1,
            abs(dx - 97),
            abs(dy - 2),
            abs((ix2 - ix1) - 50),
        )
        if best is None or score < best_score:
            best = item
            best_score = score
    return best


def summarize(values):
    if not values:
        return None
    return {
        "count": len(values),
        "min": round(min(values), 2),
        "max": round(max(values), 2),
        "mean": round(sum(values) / len(values), 2),
        "median": round(statistics.median(values), 2),
    }


def build_config_block(stats: dict) -> str:
    lines = ["ROI_ANCHOR_PRESETS = {"]
    for anchor in ANCHORS:
        entry = stats.get(anchor, {})
        dx = entry.get("dx", {}).get("median", 0) if entry.get("dx") else 0
        dy = entry.get("dy", {}).get("median", 0) if entry.get("dy") else 0
        w = entry.get("w", {}).get("median", 0) if entry.get("w") else 0
        h = entry.get("h", {}).get("median", 0) if entry.get("h") else 0
        lines.append(f'    "{anchor}": {{')
        lines.append(f'        "anchor_text": "{anchor}",')
        lines.append('        "relative": True,')
        lines.append(f'        "offset": {{"dx": {dx}, "dy": {dy}}},')
        lines.append(f'        "size": {{"w": {w}, "h": {h}}},')
        lines.append('        "expand": [')
        lines.append('            {"left": 4, "top": 4, "right": 4, "bottom": 4},')
        lines.append('            {"left": 8, "top": 6, "right": 8, "bottom": 6},')
        lines.append('        ],')
        lines.append('    },')
    lines.append('}')
    return "\n".join(lines)


def main():
    base = Path.cwd()
    json_files = sorted(base.rglob("ocr_vl_*.json"))
    if not json_files:
        print("No ocr_vl_*.json files found.")
        return

    stats_rows = defaultdict(list)
    report = []

    for json_file in json_files:
        payload = load_json(json_file)
        if not payload:
            continue
        items = collect_items(payload)
        anchors_in_file = []
        for item in items:
            anchor_name = normalize_anchor(item["text"])
            if not anchor_name:
                continue
            target = find_target(item, items)
            row = {
                "anchor": anchor_name,
                "anchor_bbox": item["bbox"],
                "target_bbox": target["bbox"] if target else None,
                "target_label": target["label"] if target else None,
                "target_text": target["text"] if target else None,
            }
            anchors_in_file.append(row)
            if target:
                ax1, ay1, _, _ = item["bbox"]
                tx1, ty1, tx2, ty2 = target["bbox"]
                stats_rows[anchor_name].append({
                    "dx": round(tx1 - ax1, 2),
                    "dy": round(ty1 - ay1, 2),
                    "w": round(tx2 - tx1, 2),
                    "h": round(ty2 - ty1, 2),
                    "source": str(json_file),
                })
        if anchors_in_file:
            report.append({"file": str(json_file), "anchors": anchors_in_file})

    stats = {}
    for anchor in ANCHORS:
        rows = stats_rows.get(anchor, [])
        stats[anchor] = {
            "dx": summarize([row["dx"] for row in rows]),
            "dy": summarize([row["dy"] for row in rows]),
            "w": summarize([row["w"] for row in rows]),
            "h": summarize([row["h"] for row in rows]),
            "samples": rows,
        }

    result = {
        "report": report,
        "stats": stats,
        "config_block": build_config_block(stats),
    }
    out_path = base / "anchor_probe_output.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Saved: {out_path}")
    print()
    print(build_config_block(stats))


if __name__ == "__main__":
    main()
