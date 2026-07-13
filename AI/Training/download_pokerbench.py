#!/usr/bin/env python3
"""Download the official PokerBench CSVs from the HuggingFace Hub.

Usage:
    python download_pokerbench.py [--output-dir DIR] [--files f1 f2 ...]
                                   [--sample-rows N] [--hf-token TOKEN]
"""
import argparse
import csv
import os
import shutil
import sys
from pathlib import Path

from huggingface_hub import hf_hub_download

REPO_ID = "RZ412/PokerBench"
REPO_TYPE = "dataset"

KNOWN_FILES = [
    "preflop_60k_train_set_game_scenario_information.csv",
    "preflop_1k_test_set_game_scenario_information.csv",
    "postflop_500k_train_set_game_scenario_information.csv",
    "postflop_10k_test_set_game_scenario_information.csv",
]


def download_file(filename, token):
    return Path(hf_hub_download(repo_id=REPO_ID, repo_type=REPO_TYPE, filename=filename, token=token))


def write_output(cached_path, dst_path, sample_rows):
    if sample_rows is None:
        shutil.copyfile(cached_path, dst_path)
        with open(dst_path, "r", encoding="utf-8", newline="") as f:
            return sum(1 for _ in f) - 1

    with open(cached_path, "r", encoding="utf-8", newline="") as fin, \
            open(dst_path, "w", encoding="utf-8", newline="") as fout:
        reader = csv.reader(fin)
        writer = csv.writer(fout)
        writer.writerow(next(reader))
        count = 0
        for row in reader:
            if count >= sample_rows:
                break
            writer.writerow(row)
            count += 1
        return count


def main():
    default_ai_dir = os.environ.get("BETBOT_AI_DIR", "AI")

    parser = argparse.ArgumentParser(description="Download PokerBench CSVs from HuggingFace")
    parser.add_argument("--output-dir", default=os.path.join(default_ai_dir, "Training", "data", "raw"))
    parser.add_argument("--files", nargs="*", default=KNOWN_FILES, choices=KNOWN_FILES)
    parser.add_argument("--sample-rows", type=int, default=None)
    parser.add_argument("--hf-token", default=os.environ.get("HF_TOKEN"))
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    total = 0
    for filename in args.files:
        try:
            cached_path = download_file(filename, args.hf_token)
        except Exception as e:
            print(f"[ERROR] failed to download {filename}: {e}", file=sys.stderr)
            continue

        dst_path = os.path.join(args.output_dir, filename)
        rows = write_output(cached_path, dst_path, args.sample_rows)
        total += rows
        print(f"{filename} -> {rows} rows written")

    print(f"Done. Total rows written across {len(args.files)} file(s): {total}")


if __name__ == "__main__":
    main()
