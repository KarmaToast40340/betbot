# Modular Poker OCR

Files:
- `config.py`: paths, capture area, regexes, server config
- `capture.py`: screen capture of the poker table area
- `parser.py`: transforms OCR text into a structured poker state
- `ocr_engine.py`: calls PaddleOCR-VL and saves JSON/Markdown output
- `state_manager.py`: image fingerprint, state signature, and JSONL logging
- `main.py`: continuous monitoring loop

## Launch

```bash
python main.py
```

## Dependencies

- `paddleocr`
- `opencv-python`
- `mss`
- PaddleOCR-VL server available via `PADDLEOCR_VL_SERVER_URL`

## Output

- `data/input/capture_zone.png`
- `data/output/latest_ocr.txt`
- `data/output/latest_state.json`
- `data/output/poker_states.jsonl`
- `data/output/ocr_vl_000.json`
- `data/output/ocr_vl_000.md`


## Configuration (environment variables)

- `BETBOT_CAPTURE_REGION="x1,y1,x2,y2"`: hand-history zone to capture (default: original multi-monitor setup)
- `BETBOT_CHECK_BUTTON_REGION="x1,y1,x2,y2"`: Check button zone used for turn detection
- `BETBOT_HERO_NAME`: your in-game name (default `Karmatoast40`)
- `BETBOT_INPUT_DIR` / `BETBOT_OUTPUT_DIR`: where captures and OCR outputs are written

## Tests

```bash
pip install -r requirements-dev.txt
pytest            # from the repo root; paddleocr/GPU not needed
```
