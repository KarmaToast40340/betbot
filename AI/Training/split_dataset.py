#!/usr/bin/env python3
"""Split standardized PokerBench JSONL into train/val/test.

Reads standardized JSONL produced by pokerbench_to_json.py from --interim-dir
(expected naming convention: preflop_train.jsonl, postflop_train.jsonl,
preflop_test.jsonl, postflop_test.jsonl), concatenates preflop+postflop into
a single unified pool (one model, not two), splits the *_train pool into
train/val, and copies the *_test pool through untouched as the held-out test
set (PokerBench's own official split, never re-split, comparable to the
paper's eval protocol).

Usage:
    python split_dataset.py [--interim-dir DIR] [--output-dir DIR]
                             [--val-fraction 0.1] [--seed 42] [--max-total-rows N]
"""
import argparse
import json
import os
import random
import sys
from collections import Counter
from glob import glob
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "train"))
import vocab  # noqa: E402


def load_jsonl(path):
    records = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def is_valid_record(record):
    label = (record.get("label") or {}).get("action")
    if label not in vocab.LABEL2ID:
        return False
    cards = (record.get("hero") or {}).get("cards_dealt") or []
    return len(cards) == 2


def concat_and_filter(paths):
    out = []
    for path in paths:
        records = load_jsonl(path)
        kept = [r for r in records if is_valid_record(r)]
        out.extend(kept)
        print(f"{os.path.basename(path)}: kept {len(kept)}/{len(records)}")
    return out


def split_train_val(records, val_fraction, seed):
    shuffled = list(records)
    random.Random(seed).shuffle(shuffled)
    split_idx = int(len(shuffled) * (1 - val_fraction))
    return shuffled[:split_idx], shuffled[split_idx:]


def write_jsonl(path, records):
    with open(path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def print_label_distribution(name, records):
    counts = Counter(r["label"]["action"] for r in records)
    total = max(len(records), 1)
    print(f"{name} ({len(records)} rows):")
    for action, count in sorted(counts.items(), key=lambda kv: -kv[1]):
        print(f"  {action}: {count} ({100 * count / total:.1f}%)")


def main():
    default_ai_dir = os.environ.get("BETBOT_AI_DIR", "AI")

    parser = argparse.ArgumentParser(description="Split standardized PokerBench JSONL into train/val/test")
    parser.add_argument("--interim-dir", default=os.path.join(default_ai_dir, "Training", "data", "interim"))
    parser.add_argument("--train-glob", default="*_train.jsonl")
    parser.add_argument("--test-glob", default="*_test.jsonl")
    parser.add_argument("--output-dir", default=os.path.join(default_ai_dir, "Training", "data", "processed"))
    parser.add_argument("--val-fraction", type=float, default=0.1)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-total-rows", type=int, default=None)
    args = parser.parse_args()

    train_paths = sorted(glob(os.path.join(args.interim_dir, args.train_glob)))
    test_paths = sorted(glob(os.path.join(args.interim_dir, args.test_glob)))

    if not train_paths:
        print(f"No files matched {args.train_glob!r} in {args.interim_dir}", file=sys.stderr)
        sys.exit(1)

    train_pool = concat_and_filter(train_paths)
    test_pool = concat_and_filter(test_paths) if test_paths else []

    random.Random(args.seed).shuffle(train_pool)
    if args.max_total_rows is not None:
        train_pool = train_pool[: args.max_total_rows]

    train_records, val_records = split_train_val(train_pool, args.val_fraction, args.seed)

    os.makedirs(args.output_dir, exist_ok=True)
    write_jsonl(os.path.join(args.output_dir, "train.jsonl"), train_records)
    write_jsonl(os.path.join(args.output_dir, "val.jsonl"), val_records)
    write_jsonl(os.path.join(args.output_dir, "test.jsonl"), test_pool)

    print_label_distribution("train", train_records)
    print_label_distribution("val", val_records)
    if test_pool:
        print_label_distribution("test", test_pool)
    else:
        print("test: no *_test.jsonl files found, test.jsonl written empty")


if __name__ == "__main__":
    main()
