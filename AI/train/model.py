#!/usr/bin/env python3
"""Small Transformer encoder classifier for the 6-way action-type baseline."""
import torch
import torch.nn as nn


class PokerTransformerClassifier(nn.Module):
    def __init__(
        self,
        vocab_size,
        num_classes=6,
        num_amount_buckets=10,
        d_model=128,
        nhead=4,
        num_layers=2,
        dim_feedforward=256,
        dropout=0.1,
        max_len=64,
        pad_id=0,
    ):
        super().__init__()
        self.pad_id = pad_id
        self.token_embedding = nn.Embedding(vocab_size, d_model, padding_idx=pad_id)
        self.pos_embedding = nn.Embedding(max_len, d_model)
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=d_model,
            nhead=nhead,
            dim_feedforward=dim_feedforward,
            dropout=dropout,
            activation="gelu",
            batch_first=True,
        )
        self.encoder = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)
        self.dropout = nn.Dropout(dropout)
        self.classifier = nn.Linear(d_model, num_classes)
        # Only supervised on bet/raise rows (see vocab.SIZING_ACTIONS) — the
        # network still produces this head for every input, the masking
        # happens in the training loss, not here.
        self.amount_classifier = nn.Linear(d_model, num_amount_buckets)

    def forward(self, input_ids, attention_mask):
        # input_ids: (B, L), attention_mask: (B, L) with 1=real token, 0=pad
        batch_size, seq_len = input_ids.shape
        positions = torch.arange(seq_len, device=input_ids.device).unsqueeze(0).expand(batch_size, seq_len)
        x = self.token_embedding(input_ids) + self.pos_embedding(positions)

        key_padding_mask = attention_mask == 0  # True = pad position
        encoded = self.encoder(x, src_key_padding_mask=key_padding_mask)

        mask_f = attention_mask.unsqueeze(-1).float()
        pooled = (encoded * mask_f).sum(dim=1) / mask_f.sum(dim=1).clamp(min=1)
        pooled = self.dropout(pooled)
        return self.classifier(pooled), self.amount_classifier(pooled)
