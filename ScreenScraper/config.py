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

SERVER_URL = os.environ.get(
    "PADDLEOCR_VL_SERVER_URL",
    "http://host.docker.internal:8118/v1",
)

x1, y1 = 3745, 215
x2, y2 = 3970, 821
MONITOR = {"left": x1, "top": y1, "width": x2 - x1, "height": y2 - y1}

STREETS = ["PRE-FLOP", "FLOP", "TURN", "RIVER", "SHOWDOWN"]
ACTION_PATTERNS = [
    ("raise_to", r"Raises to\s+([0-9]+(?:\.[0-9]+)?)\s*BB"),
    ("bet", r"Bets\s+([0-9]+(?:\.[0-9]+)?)\s*BB"),
    ("call", r"Calls\s+([0-9]+(?:\.[0-9]+)?)\s*BB"),
    ("post_small_blind", r"Post small blind.*?([0-9]+(?:\.[0-9]+)?)\s*BB"),
    ("post_big_blind", r"Post big blind.*?([0-9]+(?:\.[0-9]+)?)\s*BB"),
    ("check", r"^Check$"),
    ("fold", r"^Fold$"),
]

SUIT_MAP = {
    "♥": "h",
    "♡": "h",
    "♦": "d",
    "♢": "d",
    "♣": "c",
    "♠": "s",
}

CARD_RANK_RE = re.compile(r"\b(10|[2-9AKQJT])\b", re.IGNORECASE)
CARD_SUIT_RE = re.compile(r"[♥♦♣♠♡♢]", re.IGNORECASE)
CARD_LIKE_RE = re.compile(r"\b(?:10|[2-9AKQJT])(?:\s*[♥♦♣♠♡♢])?\b", re.IGNORECASE)
CARD_SECTION_RE = re.compile(
    r"(CARDS DEALT)(.*?)(?=(?:\n\s*(?:PRE-FLOP|FLOP|TURN|RIVER|SHOWDOWN|Hand\s+.+))|\Z)",
    re.IGNORECASE | re.DOTALL,
)

EXPECTED_HERO_CARD_COUNT = 2
ROI_UPSCALE_FACTORS = [2, 3, 4]
ROI_VARIANTS = ["base", "gray", "contrast", "sharp", "binary", "pad"]


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