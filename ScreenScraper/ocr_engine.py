import json
import re
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageEnhance, ImageFilter, ImageOps
from paddleocr import PaddleOCRVL

from config import DEBUG_OCR_PATH, RAW_OCR_PATH, SERVER_URL

pipeline = PaddleOCRVL(
    vl_rec_backend="vllm-server",
    vl_rec_server_url=SERVER_URL,
    use_ocr_for_image_block=True,
    format_block_content=True,
)

NULL_TOKEN = "NULL"
MIN_LOGICAL_LINES = 3
CARD_HEADER_RE = re.compile(r"^CARDS DEALT$", re.IGNORECASE)
HTML_TAG_RE = re.compile(r"<[^>]+>")
CARD_SUIT_RE = re.compile(r"[♥♦♣♠♡♢]", re.IGNORECASE)
CARD_BODY_SECTION_RE = re.compile(
    r"(CARDS DEALT)(.*?)(?=(?:\n\s*(?:PRE-FLOP|FLOP|TURN|RIVER|SHOWDOWN|Hand\s+.+))|\Z)",
    re.IGNORECASE | re.DOTALL,
)
OCR_NOISE_RE = re.compile(r"\b(?:paragraph_title|title|subtitle|heading)\b", re.IGNORECASE)


def _load_json(path: Path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _load_markdown_raw(path: Path):
    if not path.exists():
        return None
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return None


def _clean_basic_text(text: str) -> str:
    text = text.replace("\r", "\n")
    text = re.sub(r"&nbsp;", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def _strip_markup(text: str) -> str:
    text = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", text)
    text = re.sub(r"<img.*?>", "", text, flags=re.IGNORECASE)
    text = HTML_TAG_RE.sub(" ", text)
    return _clean_basic_text(text)


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
    for key in ("block_content", "text", "transcription", "content", "value", "label"):
        value = node.get(key)
        if isinstance(value, str):
            value = _clean_basic_text(value)
            if value:
                return value
    return None


def _extract_bbox(node):
    if not isinstance(node, dict):
        return None
    for key in ("block_bbox", "coordinate"):
        value = node.get(key)
        if isinstance(value, list) and len(value) == 4:
            try:
                x1, y1, x2, y2 = map(float, value)
                return [x1, y1, x2, y2]
            except Exception:
                pass
        if isinstance(value, str):
            nums = re.findall(r"-?\d+(?:\.\d+)?", value)
            if len(nums) >= 4:
                try:
                    x1, y1, x2, y2 = map(float, nums[:4])
                    return [x1, y1, x2, y2]
                except Exception:
                    pass
    return None


def _extract_label(node):
    if not isinstance(node, dict):
        return ""
    return str(node.get("block_label") or node.get("label") or "").strip().lower()


def _text_from_json(payload):
    rows = []
    for node in _iter_nodes(payload):
        text = _extract_text(node)
        bbox = _extract_bbox(node)
        if not text or not bbox:
            continue
        rows.append((bbox[1], bbox[0], text))
    if not rows:
        return None
    rows.sort(key=lambda item: (item[0], item[1]))
    return "\n".join(text for _, _, text in rows).strip() or None


def _is_poor_text(text: str) -> bool:
    if not text or text == NULL_TOKEN:
        return True
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return len(lines) < MIN_LOGICAL_LINES


def _normalize_rank_char(token: str) -> str:
    token = token.upper().strip()
    if token == "10":
        return "T"
    if token in {"0", "O"}:
        return "Q"
    return token


def _extract_cardish_tokens(text: str) -> list[str]:
    text = text or ""
    text = text.replace("\n", " ")
    text = OCR_NOISE_RE.sub(" ", text)
    text = re.sub(r"^\s*#+\s*", "", text)
    text = re.sub(r"[|/\\,_;:]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    pattern = re.compile(r"(10|[2-9AKQJT0O])(?:\s*([♥♦♣♠♡♢]))?", re.IGNORECASE)
    tokens = []
    for match in pattern.finditer(text):
        rank = _normalize_rank_char(match.group(1))
        suit = match.group(2) or ""
        if suit:
            tokens.append(f"{rank}{suit}")
        else:
            tokens.append(rank)
    return tokens


def _count_card_tokens(text: str) -> int:
    return len(_extract_cardish_tokens(text))


def _clean_cards_dealt_text(text: str) -> str:
    tokens = _extract_cardish_tokens(text)
    if not tokens:
        return ""
    return " ".join(tokens[:2]).strip()


def _score_card_candidate(text: str):
    cleaned = _clean_cards_dealt_text(text)
    ranks = len(_extract_cardish_tokens(cleaned))
    suits = len(CARD_SUIT_RE.findall(cleaned))
    noise = 1 if re.search(r"\b(PRE-FLOP|SHOWDOWN|FOLD|WINS|HAND|BB|BLIND|MUCKS)\b", text, re.IGNORECASE) else 0
    q_bonus = 1 if re.search(r"\b[QO0]\b", text, re.IGNORECASE) else 0
    return (ranks >= 2, ranks, suits, q_bonus, -noise, -abs(len(cleaned) - 5))


def _collect_layout_items(payload) -> list[dict]:
    items = []
    if not payload:
        return items
    for node in _iter_nodes(payload):
        label = _extract_label(node)
        text = _extract_text(node)
        bbox = _extract_bbox(node)
        if not bbox:
            continue
        items.append({"label": label, "text": text or "", "bbox": bbox})
    return items


def _find_cards_headers(items: list[dict]) -> list[dict]:
    headers = []
    for item in items:
        if item["label"] == "text" and CARD_HEADER_RE.match(item["text"] or ""):
            headers.append(item)
    headers.sort(key=lambda it: (it["bbox"][1], it["bbox"][0]))
    return headers


def _find_image_blocks(items: list[dict]) -> list[dict]:
    images = []
    for item in items:
        if item["label"] == "image":
            images.append(item)
    images.sort(key=lambda it: (it["bbox"][1], it["bbox"][0]))
    return images


def _associate_known_card_images(headers: list[dict], images: list[dict]) -> tuple[list[dict], list[dict]]:
    paired = []
    missing = []
    used_image_ids = set()
    for header in headers:
        hx1, hy1, _, _ = header["bbox"]
        best = None
        best_idx = None
        best_score = None
        for idx, image in enumerate(images):
            if idx in used_image_ids:
                continue
            ix1, iy1, ix2, iy2 = image["bbox"]
            dy = iy1 - hy1
            dx = ix1 - hx1
            if not (-10 <= dy <= 25):
                continue
            if dx < 40:
                continue
            score = (abs(dy), abs(dx - 98))
            if best is None or score < best_score:
                best = image
                best_idx = idx
                best_score = score
        if best is not None:
            used_image_ids.add(best_idx)
            paired.append({"header": header, "image": best})
        else:
            missing.append(header)
    return paired, missing


def _learn_offset_and_size(paired: list[dict]):
    if not paired:
        return {"dx": 98, "dy": 2, "w": 50, "h": 33}
    dxs, dys, ws, hs = [], [], [], []
    for pair in paired:
        hx1, hy1, _, _ = pair["header"]["bbox"]
        ix1, iy1, ix2, iy2 = pair["image"]["bbox"]
        dxs.append(ix1 - hx1)
        dys.append(iy1 - hy1)
        ws.append(ix2 - ix1)
        hs.append(iy2 - iy1)
    return {
        "dx": sum(dxs) / len(dxs),
        "dy": sum(dys) / len(dys),
        "w": sum(ws) / len(ws),
        "h": sum(hs) / len(hs),
    }


def _safe_predict(path: Path):
    try:
        return pipeline.predict(str(path))
    except Exception:
        return []


def _collect_prediction_texts(results: Iterable) -> list[str]:
    texts = []
    for res in results or []:
        text = None
        for attr in ("res", "result", "text"):
            value = getattr(res, attr, None)
            if isinstance(value, str) and value.strip():
                text = value.strip()
                break
        if not text and hasattr(res, "json"):
            try:
                payload = res.json if not callable(res.json) else res.json()
                if isinstance(payload, dict):
                    text = _text_from_json(payload)
            except Exception:
                pass
        if text:
            texts.append(_clean_basic_text(text.replace("\n", " ")))
    return texts


def _build_variants(crop: Image.Image, stem: str):
    variants = []
    for scale in (2, 3, 4):
        scaled = crop.resize((max(1, crop.width * scale), max(1, crop.height * scale)), Image.Resampling.LANCZOS)
        variants.append((f"{stem}_s{scale}_base", scaled))
        variants.append((f"{stem}_s{scale}_gray", ImageOps.grayscale(scaled).convert("RGB")))
        variants.append((f"{stem}_s{scale}_contrast", ImageEnhance.Contrast(scaled).enhance(2.0)))
        variants.append((f"{stem}_s{scale}_sharp", scaled.filter(ImageFilter.SHARPEN)))
        bw = ImageEnhance.Contrast(ImageOps.grayscale(scaled)).enhance(2.5).point(lambda p: 255 if p > 160 else 0).convert("RGB")
        variants.append((f"{stem}_s{scale}_binary", bw))
        pad = ImageOps.expand(scaled, border=16, fill="white")
        variants.append((f"{stem}_s{scale}_pad", pad))
    return variants


def _ocr_crop(base_image: Image.Image, crop_box, temp_dir: Path, stem: str, debug_rows: list[dict]) -> str | None:
    x1, y1, x2, y2 = map(int, crop_box)
    crop = base_image.crop((x1, y1, x2, y2))
    variants = _build_variants(crop, stem)

    candidates = []
    temp_paths = []
    try:
        for name, image in variants:
            tmp = temp_dir / f"{name}.png"
            image.save(tmp)
            temp_paths.append(tmp)
            results = _safe_predict(tmp)
            for raw_text in _collect_prediction_texts(results):
                cleaned = _clean_cards_dealt_text(raw_text)
                if not cleaned:
                    continue
                candidates.append(cleaned)
                debug_rows.append({
                    "variant": name,
                    "crop_box": [x1, y1, x2, y2],
                    "raw_text": raw_text,
                    "cleaned_text": cleaned,
                    "score": _score_card_candidate(raw_text),
                })
    finally:
        for tmp in temp_paths:
            try:
                tmp.unlink(missing_ok=True)
            except Exception:
                pass

    if not candidates:
        return None
    candidates = sorted(set(candidates), key=_score_card_candidate, reverse=True)
    best = candidates[0]
    return best if _count_card_tokens(best) >= 2 else None


def _repair_cards_dealt_from_layout(json_payload, markdown_raw: str, source_image_path: Path, debug_rows: list[dict]) -> str | None:
    if not markdown_raw:
        return None

    items = _collect_layout_items(json_payload)
    headers = _find_cards_headers(items)
    images = _find_image_blocks(items)
    paired, missing = _associate_known_card_images(headers, images)
    learned = _learn_offset_and_size(paired)

    debug_rows.append({
        "learned": learned,
        "headers": [h["bbox"] for h in headers],
        "known_pairs": [
            {"header": p["header"]["bbox"], "image": p["image"]["bbox"]}
            for p in paired
        ],
        "missing_headers": [h["bbox"] for h in missing],
    })

    sections = []
    for idx, match in enumerate(CARD_BODY_SECTION_RE.finditer(markdown_raw)):
        body = match.group(2) or ""
        body_text = _strip_markup(body)
        sections.append({
            "index": idx,
            "body_text": body_text,
            "full_match": match.group(0),
            "span": match.span(),
        })

    if not sections:
        return _strip_markup(markdown_raw)

    try:
        base_image = Image.open(source_image_path).convert("RGB")
    except Exception:
        return _strip_markup(markdown_raw)

    width, height = base_image.size
    rebuilt = markdown_raw
    offset = 0

    for idx, section in enumerate(sections):
        existing_clean = _clean_cards_dealt_text(section["body_text"])
        if _count_card_tokens(existing_clean) >= 2:
            debug_rows.append({"section": idx, "status": "already_ok", "text": existing_clean})
            continue
        if idx >= len(headers):
            debug_rows.append({"section": idx, "status": "no_header_match"})
            continue

        hx1, hy1, _, _ = headers[idx]["bbox"]
        x1 = max(0, int(round(hx1 + learned["dx"] - 4)))
        y1 = max(0, int(round(hy1 + learned["dy"] - 4)))
        x2 = min(width, int(round(x1 + learned["w"] + 8)))
        y2 = min(height, int(round(y1 + learned["h"] + 8)))

        candidate_boxes = [
            (x1, y1, x2, y2),
            (max(0, x1 - 4), max(0, y1 - 4), min(width, x2 + 4), min(height, y2 + 4)),
            (max(0, x1 - 8), max(0, y1 - 6), min(width, x2 + 8), min(height, y2 + 6)),
        ]

        recovered = None
        for box_id, box in enumerate(candidate_boxes):
            recovered = _ocr_crop(base_image, box, source_image_path.parent, f"cards_{idx}_{box_id}", debug_rows)
            if recovered:
                break

        debug_rows.append({
            "section": idx,
            "status": "recovered" if recovered else "failed",
            "header_bbox": headers[idx]["bbox"],
            "candidate_boxes": [list(b) for b in candidate_boxes],
            "replacement": recovered,
        })

        if not recovered:
            continue

        replacement = f"CARDS DEALT\n\n{recovered}\n"
        start, end = section["span"]
        start += offset
        end += offset
        rebuilt = rebuilt[:start] + replacement + rebuilt[end:]
        offset += len(replacement) - (end - start)

    return _strip_markup(rebuilt) or None


def extract_text_from_result(json_path: Path, md_path: Path, source_image_path: Path):
    debug_rows = []
    payload = _load_json(json_path)
    markdown_raw = _load_markdown_raw(md_path)
    markdown_text = _repair_cards_dealt_from_layout(payload, markdown_raw, source_image_path, debug_rows) if markdown_raw else None
    json_text = _text_from_json(payload) if payload else None

    if markdown_text and not _is_poor_text(markdown_text):
        chosen = markdown_text
    elif json_text and not _is_poor_text(json_text):
        # Reached only when markdown_text is missing/poor — must prefer the
        # known-good json_text here. The previous `markdown_text or json_text`
        # re-checked markdown_text first and picked it whenever merely
        # non-empty, silently defeating the poor-quality check above.
        chosen = json_text
    else:
        chosen = markdown_text or json_text or NULL_TOKEN

    try:
        RAW_OCR_PATH.write_text(chosen, encoding="utf-8")
    except Exception:
        pass
    try:
        DEBUG_OCR_PATH.write_text(json.dumps(debug_rows, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass
    return chosen


def run_ocr(image_path, output_dir):
    source_image_path = Path(image_path)
    output = pipeline.predict(str(source_image_path))
    texts = []
    artifacts = []
    for i, res in enumerate(output):
        json_path = output_dir / f"ocr_vl_{i:03d}.json"
        md_path = output_dir / f"ocr_vl_{i:03d}.md"
        if hasattr(res, "save_to_json"):
            res.save_to_json(save_path=str(json_path))
        if hasattr(res, "save_to_markdown"):
            res.save_to_markdown(save_path=str(md_path))
        text = extract_text_from_result(json_path, md_path, source_image_path)
        texts.append(text)
        artifacts.append({
            "json_path": str(json_path),
            "md_path": str(md_path),
            "text": text,
        })
    full_text = "\n\n".join(text for text in texts if text).strip() or NULL_TOKEN
    return full_text, artifacts