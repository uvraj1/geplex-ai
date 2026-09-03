"""Fine-tune a causal language model on a conversational JSONL dataset.

Each JSONL line must contain a ``messages`` list:

    {"messages": [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi! How can I help?"}
    ]}

Install dependencies in the environment used for training:
    pip install torch transformers

Example:
    python scripts/finetune_conversational_model.py \
        --dataset data/conversations.jsonl \
        --model sshleifer/tiny-gpt2 \
        --output-dir models/conversation-model \
        --epochs 3
"""

from __future__ import annotations

import argparse
import json
import math
import random
from pathlib import Path
from typing import Any

import torch
from torch.utils.data import DataLoader, Dataset
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    get_linear_schedule_with_warmup,
)


VALID_ROLES = {"system", "user", "assistant"}


def load_conversations(path: Path) -> list[list[dict[str, str]]]:
    """Load and validate conversations from JSONL."""
    conversations: list[list[dict[str, str]]] = []
    with path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            if not line.strip():
                continue
            try:
                record: Any = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(f"Invalid JSON on line {line_number}: {error}") from error

            messages = record.get("messages") if isinstance(record, dict) else record
            if not isinstance(messages, list) or not messages:
                raise ValueError(f"Line {line_number} must contain a non-empty messages list.")

            normalized: list[dict[str, str]] = []
            for message in messages:
                if not isinstance(message, dict):
                    raise ValueError(f"Line {line_number} contains a non-object message.")
                role = message.get("role")
                content = message.get("content")
                if role not in VALID_ROLES or not isinstance(content, str) or not content.strip():
                    raise ValueError(
                        f"Line {line_number} has a message with an invalid role or content."
                    )
                normalized.append({"role": role, "content": content.strip()})
            conversations.append(normalized)

    if not conversations:
        raise ValueError(f"No conversations found in {path}.")
    return conversations


def format_conversation(tokenizer: Any, messages: list[dict[str, str]]) -> str:
    """Render messages using the model's chat template or a portable fallback."""
    if getattr(tokenizer, "chat_template", None):
        return tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=False
        )
    return "\n".join(
        f"{message['role'].capitalize()}: {message['content']}" for message in messages
    ) + "\n"


class ConversationDataset(Dataset[dict[str, torch.Tensor]]):
    """Tokenized conversations with padded labels masked from the loss."""

    def __init__(
        self,
        conversations: list[list[dict[str, str]]],
        tokenizer: Any,
        max_length: int,
    ) -> None:
        self.examples: list[dict[str, torch.Tensor]] = []
        for messages in conversations:
            encoded = tokenizer(
                format_conversation(tokenizer, messages),
                truncation=True,
                max_length=max_length,
                add_special_tokens=True,
            )
            input_ids = torch.tensor(encoded["input_ids"], dtype=torch.long)
            attention_mask = torch.tensor(encoded["attention_mask"], dtype=torch.long)
            self.examples.append(
                {
                    "input_ids": input_ids,
                    "attention_mask": attention_mask,
                    "labels": input_ids.clone(),
                }
            )

    def __len__(self) -> int:
        return len(self.examples)

    def __getitem__(self, index: int) -> dict[str, torch.Tensor]:
        return self.examples[index]


def collate_batch(
    examples: list[dict[str, torch.Tensor]], pad_token_id: int
) -> dict[str, torch.Tensor]:
    """Pad a batch and ignore padding positions in the causal-LM loss."""
    input_ids = torch.nn.utils.rnn.pad_sequence(
        [example["input_ids"] for example in examples],
        batch_first=True,
        padding_value=pad_token_id,
    )
    attention_mask = torch.nn.utils.rnn.pad_sequence(
        [example["attention_mask"] for example in examples],
        batch_first=True,
        padding_value=0,
    )
    labels = input_ids.clone()
    labels[attention_mask == 0] = -100
    return {"input_ids": input_ids, "attention_mask": attention_mask, "labels": labels}


def evaluate(
    model: torch.nn.Module,
    loader: DataLoader[dict[str, torch.Tensor]],
    device: torch.device,
) -> float:
    """Return average validation loss."""
    model.eval()
    total_loss = 0.0
    batches = 0
    with torch.no_grad():
        for batch in loader:
            outputs = model(**{key: value.to(device) for key, value in batch.items()})
            total_loss += float(outputs.loss)
            batches += 1
    model.train()
    return total_loss / max(batches, 1)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True, help="Conversational JSONL file.")
    parser.add_argument("--model", default="sshleifer/tiny-gpt2", help="Hugging Face model ID.")
    parser.add_argument("--output-dir", type=Path, default=Path("fine-tuned-model"))
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=2)
    parser.add_argument("--learning-rate", type=float, default=5e-5)
    parser.add_argument("--max-length", type=int, default=512)
    parser.add_argument("--gradient-accumulation-steps", type=int, default=1)
    parser.add_argument("--validation-split", type=float, default=0.1)
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.epochs < 1 or args.batch_size < 1 or args.max_length < 2:
        raise ValueError("epochs, batch-size, and max-length must be positive.")
    if not 0 <= args.validation_split < 1:
        raise ValueError("validation-split must be between 0 (inclusive) and 1 (exclusive).")

    random.seed(args.seed)
    torch.manual_seed(args.seed)
    conversations = load_conversations(args.dataset)
    random.Random(args.seed).shuffle(conversations)
    validation_count = (
        max(1, math.ceil(len(conversations) * args.validation_split))
        if len(conversations) > 1 and args.validation_split
        else 0
    )
    validation = conversations[:validation_count]
    training = conversations[validation_count:] or conversations

    tokenizer = AutoTokenizer.from_pretrained(args.model)
    if tokenizer.pad_token_id is None:
        if tokenizer.eos_token_id is None:
            raise ValueError("Tokenizer has neither a pad token nor an EOS token.")
        tokenizer.pad_token = tokenizer.eos_token
    model = AutoModelForCausalLM.from_pretrained(args.model)

    train_dataset = ConversationDataset(training, tokenizer, args.max_length)
    validation_dataset = ConversationDataset(validation, tokenizer, args.max_length)
    collate = lambda examples: collate_batch(examples, tokenizer.pad_token_id)
    train_loader = DataLoader(train_dataset, batch_size=args.batch_size, shuffle=True, collate_fn=collate)
    validation_loader = (
        DataLoader(
            validation_dataset,
            batch_size=args.batch_size,
            shuffle=False,
            collate_fn=collate,
        )
        if validation
        else None
    )

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.learning_rate)
    updates_per_epoch = math.ceil(len(train_loader) / args.gradient_accumulation_steps)
    scheduler = get_linear_schedule_with_warmup(
        optimizer, num_warmup_steps=0, num_training_steps=updates_per_epoch * args.epochs
    )
    use_amp = device.type == "cuda"
    scaler = torch.amp.GradScaler("cuda", enabled=use_amp)

    for epoch in range(args.epochs):
        model.train()
        optimizer.zero_grad(set_to_none=True)
        running_loss = 0.0
        for step, batch in enumerate(train_loader, start=1):
            batch = {key: value.to(device) for key, value in batch.items()}
            with torch.autocast(device_type="cuda", enabled=use_amp):
                loss = model(**batch).loss / args.gradient_accumulation_steps
            scaler.scale(loss).backward()
            if step % args.gradient_accumulation_steps == 0 or step == len(train_loader):
                scaler.step(optimizer)
                scaler.update()
                scheduler.step()
                optimizer.zero_grad(set_to_none=True)
            running_loss += float(loss) * args.gradient_accumulation_steps

        message = f"epoch {epoch + 1}/{args.epochs} - train loss: {running_loss / len(train_loader):.4f}"
        if validation_loader is not None:
            message += f" - validation loss: {evaluate(model, validation_loader, device):.4f}"
        print(message)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(args.output_dir)
    tokenizer.save_pretrained(args.output_dir)
    print(f"Saved fine-tuned model to {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
