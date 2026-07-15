#!/usr/bin/env python3
"""Standalone inference: load a checkpoint, feed it one standardized hand
record, print the predicted action (and sizing bucket for bet/raise).

Usage:
    python infer.py --checkpoint AI/train/checkpoints/best.pt --input record.json
    cat record.json | python infer.py --checkpoint AI/train/checkpoints/best.pt --input -
"""
import argparse
import json
import sys

import torch

import vocab
from model import PokerTransformerClassifier


def load_model(checkpoint_path, device="cpu"):
    checkpoint = torch.load(checkpoint_path, map_location=device, weights_only=False)

    # The checkpoint carries its own vocab snapshot so it's self-describing,
    # but this script still imports the live vocab.py to encode the input
    # record. Warn if they've drifted apart instead of silently mispredicting.
    if checkpoint.get("vocab", {}).get("token_to_id") != vocab.TOKEN_TO_ID:
        print(
            "[WARN] checkpoint vocab snapshot doesn't match the current vocab.py — "
            "predictions may be unreliable.",
            file=sys.stderr,
        )

    model = PokerTransformerClassifier(**checkpoint["config"])
    model.load_state_dict(checkpoint["model_state_dict"])
    model.to(device)
    model.eval()
    return model, checkpoint


def predict(model, record, device="cpu"):
    token_ids = vocab.encode_record(record)
    input_ids = torch.tensor([token_ids], dtype=torch.long, device=device)
    attention_mask = torch.ones_like(input_ids)

    with torch.no_grad():
        action_logits, amount_logits = model(input_ids, attention_mask)
        action_probs = torch.softmax(action_logits, dim=-1)[0]
        amount_probs = torch.softmax(amount_logits, dim=-1)[0]

    action_id = int(action_probs.argmax())
    action_name = vocab.ID2LABEL[action_id]

    result = {
        "action": action_name,
        "action_probabilities": {
            vocab.ID2LABEL[i]: round(float(p), 4) for i, p in enumerate(action_probs)
        },
    }

    if action_name in vocab.SIZING_ACTIONS:
        bucket_id = int(amount_probs.argmax())
        range_str, point_estimate = vocab.format_amount_bucket(bucket_id)
        result["amount_bb_range"] = range_str
        result["amount_bb_estimate"] = round(point_estimate, 2)

    return result


def main():
    parser = argparse.ArgumentParser(description="Run the trained baseline on a standardized hand record")
    parser.add_argument("--checkpoint", default="AI/train/checkpoints/best.pt")
    parser.add_argument("--input", default="-", help="Path to a standardized hand JSON, or '-' for stdin")
    parser.add_argument("--device", default="cpu")
    args = parser.parse_args()

    if args.input == "-":
        record = json.load(sys.stdin)
    else:
        with open(args.input, "r", encoding="utf-8") as f:
            record = json.load(f)

    model, checkpoint = load_model(args.checkpoint, device=args.device)
    result = predict(model, record, device=args.device)
    result["checkpoint_epoch"] = checkpoint.get("epoch")
    result["checkpoint_val_accuracy"] = checkpoint.get("val_accuracy")
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
