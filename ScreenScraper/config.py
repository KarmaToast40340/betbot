import os
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

SERVER_URL = os.environ.get(
    "PADDLEOCR_VL_SERVER_URL",
    "http://host.docker.internal:8118/v1"
)

MONITOR = {
    "left": 3768,
    "top": 498,
    "width": 3992 - 3768,
    "height": 1080 - 498,
}

STREETS = ["PRE-FLOP", "FLOP", "TURN", "RIVER", "SHOWDOWN"]
ACTION_PATTERNS = [
    ("raise_to", r"Raises to\s+([0-9]+(?:\.[0-9]+)?)\s*BB"),
    ("bet", r"Bets\s+([0-9]+(?:\.[0-9]+)?)\s*BB"),
    ("call", r"Calls\s+([0-9]+(?:\.[0-9]+)?)\s*BB"),
    ("post_small_blind", r"Post small blind.*?([0-9]+(?:\.[0-9]+)?)\s*BB"),
    ("post_big_blind", r"Post big blind.*?([0-9]+(?:\.[0-9]+)?)\s*BB"),
    ("check", r"^Check$"),
    ("fold", r"^Fold$")
]

SUIT_MAP = {
    "♥": "h",
    "♡": "h",
    "♦": "d",
    "♢": "d",
    "♣": "c",
    "♠": "s",
}
