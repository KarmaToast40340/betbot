#!/usr/bin/env python3
"""PyTorch Dataset/DataLoader for standardized+labeled PokerBench JSONL records."""
import json

import torch
from torch.utils.data import DataLoader, Dataset

import vocab


def load_jsonl(path):
    records = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


class PokerBenchDataset(Dataset):
    def __init__(self, jsonl_path, max_samples=None):
        records = load_jsonl(jsonl_path)
        if max_samples is not None:
            records = records[:max_samples]
        self.examples = [
            (
                vocab.encode_record(r),
                vocab.encode_label(r),
                vocab.encode_amount_label(r),
                vocab.needs_amount_label(r),
            )
            for r in records
        ]

    def __len__(self):
        return len(self.examples)

    def __getitem__(self, idx):
        token_ids, label, amount_label, amount_valid = self.examples[idx]
        return {
            "token_ids": token_ids,
            "label": label,
            "amount_label": amount_label,
            "amount_valid": amount_valid,
        }


def collate_batch(batch):
    max_len = max(len(ex["token_ids"]) for ex in batch)
    pad_id = vocab.TOKEN_TO_ID[vocab.PAD]

    input_ids = torch.full((len(batch), max_len), pad_id, dtype=torch.long)
    attention_mask = torch.zeros((len(batch), max_len), dtype=torch.long)
    labels = torch.empty(len(batch), dtype=torch.long)
    amount_labels = torch.empty(len(batch), dtype=torch.long)
    amount_valid = torch.zeros(len(batch), dtype=torch.bool)

    for i, ex in enumerate(batch):
        ids = ex["token_ids"]
        input_ids[i, : len(ids)] = torch.tensor(ids, dtype=torch.long)
        attention_mask[i, : len(ids)] = 1
        labels[i] = ex["label"]
        amount_labels[i] = ex["amount_label"]
        amount_valid[i] = ex["amount_valid"]

    return {
        "input_ids": input_ids,
        "attention_mask": attention_mask,
        "labels": labels,
        "amount_labels": amount_labels,
        "amount_valid": amount_valid,
    }


def make_dataloader(jsonl_path, batch_size, shuffle, max_samples=None, num_workers=0):
    ds = PokerBenchDataset(jsonl_path, max_samples=max_samples)
    return DataLoader(
        ds,
        batch_size=batch_size,
        shuffle=shuffle,
        collate_fn=collate_batch,
        num_workers=num_workers,
    )
