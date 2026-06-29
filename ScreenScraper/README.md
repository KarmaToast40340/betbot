# Poker OCR modulaire

Fichiers :
- `config.py` : chemins, zone de capture, regex, config serveur
- `capture.py` : capture écran de la zone poker
- `parser.py` : transforme le texte OCR en état poker structuré
- `ocr_engine.py` : appel PaddleOCR-VL + sauvegarde JSON/Markdown
- `state_manager.py` : fingerprint image + signature d'état + JSONL
- `main.py` : boucle continue de monitoring

## Lancement

```bash
python main.py
```

## Dépendances

- `paddleocr`
- `opencv-python`
- `mss`
- serveur PaddleOCR-VL accessible via `PADDLEOCR_VL_SERVER_URL`

## Sorties

- `data/input/capture_zone.png`
- `data/output/latest_ocr.txt`
- `data/output/latest_state.json`
- `data/output/poker_states.jsonl`
- `data/output/ocr_vl_000.json`
- `data/output/ocr_vl_000.md`
