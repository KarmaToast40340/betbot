import os
import re
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
DATA_DIR = PROJECT_ROOT / "data"
INPUT_DIR = DATA_DIR / "input"
OUTPUT_DIR = DATA_DIR / "output"

INPUT_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

INPUT_PATH = INPUT_DIR / "capture_zone.png"
STATE_LOG_PATH = OUTPUT_DIR / "poker_states.jsonl"
LATEST_STATE_PATH = OUTPUT_DIR / "latest_state.json"
RAW_OCR_PATH = OUTPUT_DIR / "latest_ocr.txt"
DEBUG_OCR_PATH = OUTPUT_DIR / "latest_ocr_debug.json"

SERVER_URL = os.environ.get("PADDLEOCR_VL_SERVER_URL", "http://host.docker.internal:8118/v1")

x1, y1 = 3745, 215
x2, y2 = 3970, 821
MONITOR = {"left": x1, "top": y1, "width": x2 - x1, "height": y2 - y1}

STREETS = ["PRE-FLOP", "FLOP", "TURN", "RIVER", "SHOWDOWN"]
STRUCTURAL_MARKERS = {
    "CARDS DEALT": ("preflop", "cards_dealt"),
    "FLOP": ("flop", "flop_start"),
    "TURN": ("turn", "turn_start"),
    "RIVER": ("river", "river_start"),
    "SHOWDOWN": ("showdown", "showdown_start"),
}

SUIT_MAP = {
    "♥": "h",
    "♡": "h",
    "♦": "d",
    "♢": "d",
    "♣": "c",
    "♠": "s",
    "h": "h",
    "d": "d",
    "c": "c",
    "s": "s",
}

CARD_RANK_RE = re.compile(r"\b(10|[2-9AKQJT])\b", re.IGNORECASE)
CARD_SUIT_RE = re.compile(r"[♥♦♣♠♡♢]", re.IGNORECASE)
CARD_LIKE_RE = re.compile(r"(?:10|[2-9AKQJT])(?:\s*[♥♦♣♠♡♢hdcs])?", re.IGNORECASE)
CARD_ONLY_LINE_RE = re.compile(r"^\s*(?:(?:10|[2-9AKQJT])(?:\s*[♥♦♣♠♡♢hdcs])?\s*){1,5}$", re.IGNORECASE)
COMPACT_TWO_CARD_RE = re.compile(r"^\s*(10|[2-9AKQJT])\s*(10|[2-9AKQJT])\s*$", re.IGNORECASE)
MADE_HAND_RE = re.compile(
    r"\b(PAIR|TWO PAIR|TRIPS|THREE OF A KIND|STRAIGHT|FLUSH|FULL HOUSE|QUADS|FOUR OF A KIND|STRAIGHT FLUSH)\b",
    re.IGNORECASE,
)
SECTION_KEYWORD_RE = re.compile(r"\b(CARDS DEALT|PRE-FLOP|FLOP|TURN|RIVER|SHOWDOWN)\b", re.IGNORECASE)

EXPECTED_CARD_COUNTS = {
    "CARDS DEALT": 2,
    "FLOP": 3,
    "TURN": 4,
    "RIVER": 5,
}

ROI_UPSCALE_FACTORS = [2, 3, 4]
ROI_VARIANTS = ["base", "gray", "contrast", "sharp", "binary", "pad"]
ROI_ANCHOR_PRESETS = {
    "CARDS DEALT": {
        "anchor_text": "CARDS DEALT",
        "relative": True,
        "offset": {"dx": 97.0, "dy": 2.0},
        "size": {"w": 50.0, "h": 32.0},
        "expand": [
            {"left": 4, "top": 4, "right": 4, "bottom": 4},
            {"left": 8, "top": 6, "right": 8, "bottom": 6},
        ],
    },
    "FLOP": {
        "anchor_text": "FLOP",
        "relative": True,
        "offset": {"dx": 96.0, "dy": -20.0},
        "size": {"w": 113.0, "h": 15.0},
        "expand": [
            {"left": 4, "top": 4, "right": 4, "bottom": 4},
            {"left": 8, "top": 6, "right": 8, "bottom": 6},
        ],
    },
    "TURN": {
        "anchor_text": "TURN",
        "relative": True,
        "offset": {"dx": 96.0, "dy": -62.0},
        "size": {"w": 113.0, "h": 15.0},
        "expand": [
            {"left": 4, "top": 4, "right": 4, "bottom": 4},
            {"left": 8, "top": 6, "right": 8, "bottom": 6},
        ],
    },
    "RIVER": {
        "anchor_text": "RIVER",
        "relative": True,
        "offset": {"dx": 96.0, "dy": 58.0},
        "size": {"w": 68.0, "h": 13.0},
        "expand": [
            {"left": 4, "top": 4, "right": 4, "bottom": 4},
            {"left": 8, "top": 6, "right": 8, "bottom": 6},
        ],
    },
}


def count_rank_tokens(text: str) -> int:
    if not text:
        return 0
    return len(CARD_RANK_RE.findall(text))


def count_suit_tokens(text: str) -> int:
    if not text:
        return 0
    return len(CARD_SUIT_RE.findall(text))


def extract_rank_tokens(text: str) -> list[str]:
    if not text:
        return []
    tokens = [m.upper() for m in CARD_RANK_RE.findall(text)]
    return ["T" if t == "10" else t for t in tokens]


def normalize_cardish_text(text: str) -> str:
    if not text:
        return ""
    text = text.replace("\n", " ")
    text = re.sub(r"[|/\\,_;]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def score_card_text(text: str) -> tuple:
    cleaned = normalize_cardish_text(text)
    ranks = count_rank_tokens(cleaned)
    suits = count_suit_tokens(cleaned)
    penalty = 0
    if re.search(r"\b(?:PRE-FLOP|SHOWDOWN|FOLD|WINS|BLIND|HAND|MUCKS)\b", cleaned, re.IGNORECASE):
        penalty += 3
    if len(cleaned) > 24:
        penalty += 1
    return (ranks >= 2, ranks, suits, -penalty, -abs(len(cleaned) - 5))