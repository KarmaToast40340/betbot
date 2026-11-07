import os
import re
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
DATA_DIR = PROJECT_ROOT / "data"
INPUT_DIR = Path(os.environ.get("BETBOT_INPUT_DIR", DATA_DIR / "input"))
OUTPUT_DIR = Path(os.environ.get("BETBOT_OUTPUT_DIR", DATA_DIR / "output"))


def ensure_dirs() -> None:
    """Create the input/output folders. Called by main.py at startup, never at
    import time, so that importing config (e.g. from tests) has no side effect."""
    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def _region_from_env(name: str, default: tuple[int, int, int, int]) -> dict[str, int]:
    """Read a screen region "x1,y1,x2,y2" from env var `name` (falls back to
    `default`) and return it in mss format {left, top, width, height}."""
    raw = os.environ.get(name)
    if raw:
        parts = [int(v) for v in raw.replace(" ", "").split(",")]
        if len(parts) != 4:
            raise ValueError(f"{name} must be 'x1,y1,x2,y2', got {raw!r}")
        x1, y1, x2, y2 = parts
    else:
        x1, y1, x2, y2 = default
    if x2 <= x1 or y2 <= y1:
        raise ValueError(f"{name}: empty region ({x1},{y1},{x2},{y2})")
    return {"left": x1, "top": y1, "width": x2 - x1, "height": y2 - y1}

INPUT_PATH = INPUT_DIR / "capture_zone.png"
TURN_BUTTON_DEBUG_PATH = INPUT_DIR / "turn_button_zone.png"
STATE_LOG_PATH = OUTPUT_DIR / "poker_states.jsonl"
LATEST_STATE_PATH = OUTPUT_DIR / "latest_state.json"
RAW_OCR_PATH = OUTPUT_DIR / "latest_ocr.txt"
DEBUG_OCR_PATH = OUTPUT_DIR / "latest_ocr_debug.json"
TURN_SIGNAL_PATH = OUTPUT_DIR / "turn_signal.json"

SERVER_URL = os.environ.get("PADDLEOCR_VL_SERVER_URL", "http://host.docker.internal:8118/v1")

# Hand-history zone of the poker client. Defaults match the original
# multi-monitor setup; override with BETBOT_CAPTURE_REGION="x1,y1,x2,y2".
MONITOR = _region_from_env("BETBOT_CAPTURE_REGION", (3745, 215, 3970, 821))

# The Check button: bluish when it's not hero's turn, red when it is. Much
# cheaper and more reliable than inferring "hero's turn" from the parsed
# hand-history text (see ScreenScraper/turn_detector.py) — no OCR needed,
# just a color sample. Coordinates found + refined via
# ScreenScraper/misc/mouse_coords.py; user-measured red-state samples were
# ~(219,80,80) and ~(229,53,53) (there's white text in the middle of the
# button that dilutes the region average, but the red/blue gap survives it).
# Override with BETBOT_CHECK_BUTTON_REGION="x1,y1,x2,y2".
CHECK_BUTTON_ROI = _region_from_env("BETBOT_CHECK_BUTTON_REGION", (3096, 997, 3186, 1026))

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
    # PAIRS? (not just PAIR): Winamax renders two pair as "2 pairs: 9-4"
    # (plural) — "\bPAIR\b" doesn't match "pairs" (the trailing "s" breaks
    # the word boundary), so that line used to fall through the made-hand
    # check entirely and get misparsed as hole cards by the generic
    # card-extraction fallback in parser.py.
    r"\b(PAIRS?|TWO PAIR|TRIPS|THREE OF A KIND|STRAIGHT|FLUSH|FULL HOUSE|QUADS|FOUR OF A KIND|STRAIGHT FLUSH)\b",
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