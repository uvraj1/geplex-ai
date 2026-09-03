"""Export persisted conversations into a safe chat fine-tuning JSONL dataset.

Usage:
    python scripts/export_training_data.py
    python scripts/export_training_data.py --input data/conversation_memory.jsonl --output data/geplex-training.jsonl
"""

import argparse
import json
import re
from pathlib import Path

SYSTEM_PROMPT = (
    "You are GepLex Local AI. Match the user's language and formality; use natural "
    "Hinglish for Roman Hindi. Identify the user's goal, ask one focused clarification "
    "question only when needed, and answer clearly and respectfully. Be concise by "
    "default, use steps/examples when useful, never invent facts or completed actions, "
    "state uncertainty, protect privacy, and adapt when the user corrects you. For "
    "concrete tasks, plan briefly, select the smallest relevant tool sequence, execute "
    "and verify each step, then report only confirmed results. Use existing tools and "
    "approval gates; never bypass safety checks, fabricate integrations, or claim an "
    "action succeeded without observable confirmation. Handle failures explicitly and "
    "ask one concise clarification only when ambiguity materially changes the outcome."
    " For coding requests, inspect the relevant project and tests first, reuse existing "
    "patterns, make precise safe edits, preserve unrelated work, and verify with the "
    "smallest relevant existing test/build/lint/type-check command before reporting."
)
SECRET_PATTERN = re.compile(
    r"(?i)(api[_ -]?key|token|password|secret|bearer)\s*[:=]\s*\S+"
)


def _clean(value: object) -> str:
    text = str(value or "").strip()
    return SECRET_PATTERN.sub(r"\1: [REDACTED]", text)


def export(input_path: Path, output_path: Path) -> int:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with input_path.open(encoding="utf-8") as source, output_path.open("w", encoding="utf-8") as target:
        for line in source:
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            messages = record.get("messages")
            if not isinstance(messages, list):
                continue
            cleaned = [
                {"role": item["role"], "content": _clean(item.get("content"))}
                for item in messages
                if isinstance(item, dict)
                and item.get("role") in {"user", "assistant"}
                and _clean(item.get("content"))
            ]
            if not any(item["role"] == "user" for item in cleaned):
                continue
            if cleaned and cleaned[0]["role"] != "system":
                cleaned.insert(0, {"role": "system", "content": SYSTEM_PROMPT})
            target.write(json.dumps({"messages": cleaned}, ensure_ascii=False) + "\n")
            written += 1
    return written


def main() -> None:
    parser = argparse.ArgumentParser(description="Export GepLex conversations for chat fine-tuning.")
    parser.add_argument("--input", type=Path, default=Path("data/conversation_memory.jsonl"))
    parser.add_argument("--output", type=Path, default=Path("data/geplex-training.jsonl"))
    args = parser.parse_args()
    print(f"Exported {export(args.input, args.output)} conversations to {args.output}")


if __name__ == "__main__":
    main()
