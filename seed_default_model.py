#!/usr/bin/env python3
"""Seed the workspace default AI model and endpoint configuration."""

import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from src.settings import ensure_default_model_seed


def main() -> None:
    settings = ensure_default_model_seed()
    print(f"Default model seeded: {settings.get('default_model')} ({settings.get('default_endpoint_id')})")


if __name__ == "__main__":
    main()
