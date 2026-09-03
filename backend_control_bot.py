#!/usr/bin/env python3
"""Shim forwarder for bots/backend_control_bot.py."""
import sys
import runpy
from pathlib import Path

target = Path(__file__).resolve().parent / "bots" / "backend_control_bot.py"
if __name__ == "__main__":
    runpy.run_path(str(target), run_name="__main__")
