"""Small command-line chatbot that keeps multi-turn conversation history.

Usage:
    set OPENAI_API_KEY=your-key
    python scripts/multiturn_chatbot.py

The script uses any OpenAI-compatible chat-completions endpoint. Configure a
different provider with OPENAI_BASE_URL and OPENAI_MODEL.
"""

from __future__ import annotations

import os
import sys
from typing import Any

import httpx
from dotenv import load_dotenv


DEFAULT_BASE_URL = "https://api.openai.com/v1"
DEFAULT_MODEL = "gpt-4o-mini"
SYSTEM_PROMPT = "You are a helpful, concise assistant."


def create_client() -> tuple[httpx.Client, str]:
    """Create an HTTP client and return it with the selected model."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Add it to your environment or .env file."
        )

    base_url = os.getenv("OPENAI_BASE_URL", DEFAULT_BASE_URL).rstrip("/")
    model = os.getenv("OPENAI_MODEL", DEFAULT_MODEL)
    client = httpx.Client(
        base_url=base_url,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        timeout=60.0,
    )
    return client, model


def ask_model(
    client: httpx.Client, model: str, messages: list[dict[str, str]]
) -> str:
    """Send the complete conversation and return the assistant's response."""
    response = client.post(
        "/chat/completions",
        json={
            "model": model,
            "messages": messages,
            "temperature": 0.7,
        },
    )
    response.raise_for_status()

    payload: Any = response.json()
    if not isinstance(payload, dict):
        raise RuntimeError("The LLM response was not a JSON object.")
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise RuntimeError("The LLM response did not contain any choices.")

    message = choices[0].get("message")
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError("The LLM response did not contain text content.")
    return content.strip()


def print_history(messages: list[dict[str, str]]) -> None:
    """Print user and assistant turns, excluding the system prompt."""
    for message in messages[1:]:
        role = "You" if message["role"] == "user" else "Assistant"
        print(f"{role}: {message['content']}")


def main() -> int:
    """Run the interactive chatbot until the user exits."""
    load_dotenv()

    try:
        client, model = create_client()
    except RuntimeError as error:
        print(f"Configuration error: {error}", file=sys.stderr)
        return 2

    messages: list[dict[str, str]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
    ]

    print(f"Chatbot ready ({model}). Type /reset, /history, or /quit.")
    try:
        with client:
            while True:
                try:
                    user_input = input("You: ").strip()
                except EOFError:
                    print()
                    break

                if not user_input:
                    continue
                if user_input.lower() in {"/quit", "/exit"}:
                    break
                if user_input.lower() == "/reset":
                    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
                    print("Conversation history cleared.")
                    continue
                if user_input.lower() == "/history":
                    print_history(messages)
                    continue

                messages.append({"role": "user", "content": user_input})
                try:
                    answer = ask_model(client, model, messages)
                except (httpx.HTTPError, RuntimeError) as error:
                    messages.pop()
                    print(f"Request failed: {error}", file=sys.stderr)
                    continue

                messages.append({"role": "assistant", "content": answer})
                print(f"Assistant: {answer}")
    except KeyboardInterrupt:
        print("\nGoodbye.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
