# Test fixtures

- `ocr_text/*.txt`: raw OCR text of one or more hands, copied from the
  `raw_text` field of `data/output/poker_states.jsonl` (anonymise opponents).
  Each `foo.txt` can come with a `foo.expected.json` holding the checked
  output of `parse_ocr_document` (without `timestamp_utc`) for golden tests.
- `images/*.png`: a few `capture_zone.png` screenshots for OCR tests
  (marked `gpu`, not run in CI).
