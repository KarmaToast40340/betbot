import os
from pathlib import Path

import pytest

# Keep tests deterministic whatever the developer's shell exports.
os.environ.setdefault("BETBOT_HERO_NAME", "Karmatoast40")

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES_DIR


@pytest.fixture
def ocr_text(fixtures_dir):
    """Load an OCR text fixture by name: ocr_text("preflop_fold")."""

    def _load(name: str) -> str:
        return (fixtures_dir / "ocr_text" / f"{name}.txt").read_text(encoding="utf-8")

    return _load
