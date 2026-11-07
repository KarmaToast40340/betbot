"""Shared JSONL helpers for the AI scripts (dataset, live inference, split)."""
import json
import os


def load_jsonl(path, missing_ok=False):
    """Read a JSONL file into a list of dicts, skipping blank lines.

    With missing_ok=True a missing file returns [] instead of raising
    (used by the live watcher, which may start before the first hand is logged).
    """
    if missing_ok and not os.path.exists(path):
        return []
    records = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def write_jsonl(path, records):
    with open(path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
