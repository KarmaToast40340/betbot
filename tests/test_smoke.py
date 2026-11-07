"""Step 1 smoke tests: the light modules import without side effects, and the
parser runs end to end on a fixture. The real test suite comes in step 3."""
from pathlib import Path


def test_config_import_has_no_side_effect(tmp_path, monkeypatch):
    import importlib

    import config

    monkeypatch.setenv("BETBOT_INPUT_DIR", str(tmp_path / "in"))
    monkeypatch.setenv("BETBOT_OUTPUT_DIR", str(tmp_path / "out"))
    importlib.reload(config)
    assert not (tmp_path / "in").exists()
    config.ensure_dirs()
    assert (tmp_path / "in").is_dir() and (tmp_path / "out").is_dir()


def test_capture_region_from_env(monkeypatch):
    import importlib

    import config

    monkeypatch.setenv("BETBOT_CAPTURE_REGION", "10,20,110,220")
    importlib.reload(config)
    assert config.MONITOR == {"left": 10, "top": 20, "width": 100, "height": 200}


def test_ocr_engine_imports_without_paddleocr():
    import ocr_engine

    assert ocr_engine._pipeline is None  # nothing built until first predict


def test_parser_on_fixture(ocr_text):
    from parser import parse_ocr_document

    states = parse_ocr_document(ocr_text("preflop_fold"), Path("capture_zone.png"))
    assert len(states) == 1
    state = states[0]
    assert state["hand_id"] == "4938973414124683265-10-1784135602"
    assert state["hero"]["hole_cards_raw"] == ["Q", "J"]
    assert state["blinds"] == {"sb": 0.5, "bb": 1.0}
    assert state["timestamp_utc"].endswith("Z")
    assert [a["action"] for a in state["actions"]] == ["post_small_blind", "post_big_blind", "raises", "folds"]
