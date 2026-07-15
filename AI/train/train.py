#!/usr/bin/env python3
"""Training entrypoint for the PokerBench action-type baseline.

Matches the docker-compose `betbot-agent` service command:
    python /workspace/AI/train/train.py
"""
import argparse
import os
import random

import torch
import torch.nn as nn
from tqdm import tqdm

import dataset
import vocab
from model import PokerTransformerClassifier

# ROCm-built torch exposes the GPU through the same torch.cuda API as CUDA,
# so this picks up the AMD GPU automatically inside the ROCm container and
# falls back to CPU for local (non-Docker) dev.
DEFAULT_DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

AI_DIR = os.environ.get("BETBOT_AI_DIR", "AI")
DEFAULT_TRAIN_PATH = os.path.join(AI_DIR, "Training", "data", "processed", "train.jsonl")
DEFAULT_VAL_PATH = os.path.join(AI_DIR, "Training", "data", "processed", "val.jsonl")
DEFAULT_TEST_PATH = os.path.join(AI_DIR, "Training", "data", "processed", "test.jsonl")
DEFAULT_CHECKPOINT_DIR = os.path.join(AI_DIR, "train", "checkpoints")


def parse_args():
    parser = argparse.ArgumentParser(description="Train the PokerBench action-type baseline")
    parser.add_argument("--train-path", default=DEFAULT_TRAIN_PATH)
    parser.add_argument("--val-path", default=DEFAULT_VAL_PATH)
    parser.add_argument("--test-path", default=DEFAULT_TEST_PATH)
    parser.add_argument("--epochs", type=int, default=5)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--lr", type=float, default=3e-4)
    parser.add_argument("--max-train-samples", type=int, default=None)
    parser.add_argument("--max-val-samples", type=int, default=None)
    parser.add_argument("--checkpoint-dir", default=DEFAULT_CHECKPOINT_DIR)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--device", default=DEFAULT_DEVICE)
    parser.add_argument("--num-workers", type=int, default=0)
    return parser.parse_args()


def set_seed(seed):
    random.seed(seed)
    torch.manual_seed(seed)


def compute_majority_baseline(loader):
    counts = {}
    for batch in loader:
        for label_id in batch["labels"].tolist():
            counts[label_id] = counts.get(label_id, 0) + 1
    total = sum(counts.values())
    if total == 0:
        return None, 0.0
    majority_id = max(counts, key=counts.get)
    return vocab.ID2LABEL[majority_id], counts[majority_id] / total


def evaluate(model, loader, device, loss_fn, desc="eval"):
    model.eval()
    total_loss = 0.0
    total_correct = 0
    total_count = 0
    num_classes = len(vocab.LABEL2ID)
    confusion = [[0] * num_classes for _ in range(num_classes)]

    with torch.no_grad():
        for batch in tqdm(loader, desc=desc, unit="batch", leave=False):
            input_ids = batch["input_ids"].to(device)
            attention_mask = batch["attention_mask"].to(device)
            labels = batch["labels"].to(device)

            logits = model(input_ids, attention_mask)
            loss = loss_fn(logits, labels)
            total_loss += loss.item() * labels.size(0)

            preds = logits.argmax(dim=-1)
            total_correct += (preds == labels).sum().item()
            total_count += labels.size(0)

            for true_id, pred_id in zip(labels.tolist(), preds.tolist()):
                confusion[true_id][pred_id] += 1

    return {
        "loss": total_loss / max(total_count, 1),
        "accuracy": total_correct / max(total_count, 1),
        "confusion": confusion,
    }


def print_confusion(confusion):
    names = [vocab.ID2LABEL[i] for i in range(len(confusion))]
    header = "true\\pred".ljust(10) + "".join(n.rjust(8) for n in names)
    print(header)
    for i, row in enumerate(confusion):
        print(names[i].ljust(10) + "".join(str(v).rjust(8) for v in row))


def main():
    args = parse_args()
    set_seed(args.seed)
    print(f"Using device: {args.device}")

    train_loader = dataset.make_dataloader(
        args.train_path, args.batch_size, shuffle=True,
        max_samples=args.max_train_samples, num_workers=args.num_workers,
    )
    val_loader = dataset.make_dataloader(
        args.val_path, args.batch_size, shuffle=False,
        max_samples=args.max_val_samples, num_workers=args.num_workers,
    )

    model_config = {
        "vocab_size": vocab.VOCAB_SIZE,
        "num_classes": len(vocab.LABEL2ID),
        "d_model": 128,
        "nhead": 4,
        "num_layers": 2,
        "dim_feedforward": 256,
        "dropout": 0.1,
        "max_len": vocab.MAX_SEQ_LEN,
        "pad_id": vocab.TOKEN_TO_ID[vocab.PAD],
    }
    model = PokerTransformerClassifier(**model_config).to(args.device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr)
    loss_fn = nn.CrossEntropyLoss()

    maj_label, maj_acc = compute_majority_baseline(val_loader)
    print(f"Majority-class baseline on val: predict '{maj_label}' always -> accuracy={maj_acc:.4f}")

    os.makedirs(args.checkpoint_dir, exist_ok=True)
    best_val_acc = -1.0

    for epoch in range(1, args.epochs + 1):
        model.train()
        running_loss = 0.0
        pbar = tqdm(train_loader, desc=f"epoch {epoch}/{args.epochs}", unit="batch")
        for step, batch in enumerate(pbar, start=1):
            optimizer.zero_grad()
            logits = model(batch["input_ids"].to(args.device), batch["attention_mask"].to(args.device))
            loss = loss_fn(logits, batch["labels"].to(args.device))
            loss.backward()
            optimizer.step()
            running_loss += loss.item()
            pbar.set_postfix(loss=f"{running_loss / step:.4f}")

        val_metrics = evaluate(model, val_loader, args.device, loss_fn, desc=f"epoch {epoch} val")
        print(
            f"epoch {epoch} DONE train_loss={running_loss / max(len(train_loader), 1):.4f} "
            f"val_loss={val_metrics['loss']:.4f} val_acc={val_metrics['accuracy']:.4f} "
            f"(majority_baseline={maj_acc:.4f})"
        )
        print_confusion(val_metrics["confusion"])

        checkpoint = {
            "model_state_dict": model.state_dict(),
            "config": model_config,
            "vocab": vocab.export_snapshot(),
            "epoch": epoch,
            "val_accuracy": val_metrics["accuracy"],
        }
        torch.save(checkpoint, os.path.join(args.checkpoint_dir, "last.pt"))
        if val_metrics["accuracy"] > best_val_acc:
            best_val_acc = val_metrics["accuracy"]
            torch.save(checkpoint, os.path.join(args.checkpoint_dir, "best.pt"))
            print(f"  -> new best checkpoint saved (val_acc={best_val_acc:.4f})")

    if args.test_path and os.path.exists(args.test_path):
        test_loader = dataset.make_dataloader(
            args.test_path, args.batch_size, shuffle=False, num_workers=args.num_workers,
        )
        test_metrics = evaluate(model, test_loader, args.device, loss_fn, desc="final test")
        _, maj_acc_test = compute_majority_baseline(test_loader)
        print(f"FINAL TEST: acc={test_metrics['accuracy']:.4f} (majority_baseline={maj_acc_test:.4f})")
    else:
        print(f"No test set found at {args.test_path}, skipping final test evaluation.")


if __name__ == "__main__":
    main()
