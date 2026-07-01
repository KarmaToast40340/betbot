import json
import re
from pathlib import Path

from paddleocr import PaddleOCRVL

from config import SERVER_URL
from parser import parse_poker_ocr_text


pipeline = PaddleOCRVL(
    vl_rec_backend="vllm-server",
    vl_rec_server_url=SERVER_URL,
    use_ocr_for_image_block=True,
    format_block_content=True,
)

NULL_TOKEN = "NULL"
MIN_LOGICAL_LINES = 3


def _load_json(path: Path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _load_markdown_as_text(path: Path):
    if not path.exists():
        return None

    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return None

    text = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", text)
    text = re.sub(r"<img.*?>", "", text, flags=re.IGNORECASE)
    text = text.replace("\r", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = text.strip()

    return text or None


def _iter_nodes(obj):
    if isinstance(obj, dict):
        yield obj
        for value in obj.values():
            yield from _iter_nodes(value)
    elif isinstance(obj, list):
        for item in obj:
            yield from _iter_nodes(item)


def _extract_text(node):
    if not isinstance(node, dict):
        return None

    for key in ("text", "transcription", "content", "value"):
        value = node.get(key)
        if isinstance(value, str):
            value = re.sub(r"\s+", " ", value).strip()
            if value:
                return value

    return None


def _extract_order(node):
    if not isinstance(node, dict):
        return None
    value = node.get("order")
    if isinstance(value, int):
        return value
    return None


def _extract_bbox(node):
    if not isinstance(node, dict):
        return None

    coord = node.get("coordinate")
    if isinstance(coord, list) and len(coord) == 4:
        try:
            x1, y1, x2, y2 = map(float, coord)
            return (x1, y1, x2, y2)
        except Exception:
            return None

    return None


def _is_noise_node(node):
    if not isinstance(node, dict):
        return True

    label = str(node.get("label", "")).lower()
    if label in {"image", "figure"}:
        return True

    if any(k in node for k in ("doc_preprocessor_res", "layout_det_res")):
        return True

    return False


def _build_text_from_json(payload):
    rows = []

    for node in _iter_nodes(payload):
        if _is_noise_node(node):
            continue

        text = _extract_text(node)
        if not text:
            continue

        bbox = _extract_bbox(node)
        order = _extract_order(node)

        rows.append({
            "text": text,
            "order": order if order is not None else 10**9,
            "y": bbox[1] if bbox else 10**9,
            "x": bbox[0] if bbox else 10**9,
        })

    if not rows:
        return None

    rows.sort(key=lambda r: (r["order"], r["y"], r["x"]))
    text = "\n".join(row["text"] for row in rows if row["text"].strip())
    text = re.sub(r"\n{3,}", "\n\n", text).strip()

    return text or None


def _is_poor_text(text: str) -> bool:
    if not text or text == NULL_TOKEN:
        return True
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return len(lines) < MIN_LOGICAL_LINES


def extract_text_from_result(json_path: Path, md_path: Path):
    markdown_text = _load_markdown_as_text(md_path)
    if markdown_text and not _is_poor_text(markdown_text):
        return markdown_text

    payload = _load_json(json_path)
    json_text = _build_text_from_json(payload) if payload else None
    if json_text and not _is_poor_text(json_text):
        return json_text

    return markdown_text or json_text or NULL_TOKEN


def run_ocr_and_parse(image_path, output_dir):
    output = pipeline.predict(str(image_path))
    texts = []
    parsed_results = []

    for i, res in enumerate(output):
        json_path = output_dir / f"ocr_vl_{i:03d}.json"
        md_path = output_dir / f"ocr_vl_{i:03d}.md"

        if hasattr(res, "save_to_json"):
            res.save_to_json(save_path=str(json_path))

        if hasattr(res, "save_to_markdown"):
            res.save_to_markdown(save_path=str(md_path))

        result_text = extract_text_from_result(json_path, md_path)
        texts.append(result_text)
        parsed_results.append(parse_poker_ocr_text(result_text, Path(image_path)))

    return "\n\n".join(texts), parsed_results