#!/usr/bin/env python3
"""Minimal one-click startup helper for the GepLex AI assistant."""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import sys
import time
import webbrowser


def banner() -> None:
    print("")
    print("  ____   ____   _____  _  _   _")
    print(" |  _ \\ / ___| | ____|| || | | |")
    print(" | |_) | |     |  _|  | || |_| |")
    print(" |  __/| |___  | |___ |__   _| |")
    print(" |_|    \\_____| |_____|   |_|   ")
    print("\n  GepLex one-click startup bot\n")


def open_browser(url: str) -> None:
    try:
        time.sleep(2.5)
        webbrowser.open(url, new=2)
    except Exception:
        pass


def _port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except OSError:
        return False


def start_local_chroma() -> None:
    """Start the local vector service when Docker/another instance is absent."""
    if os.getenv("CHROMADB_HOST", "localhost").lower() not in {"localhost", "127.0.0.1"}:
        return
    host = os.getenv("CHROMADB_HOST", "127.0.0.1")
    port = int(os.getenv("CHROMADB_PORT", "8100"))
    if _port_open(host, port):
        print(f"ChromaDB already running at {host}:{port}")
        return

    chroma = shutil.which("chroma")
    if not chroma:
        candidate = os.path.join(os.path.dirname(sys.executable), "chroma.exe")
        if os.path.exists(candidate):
            chroma = candidate
    if not chroma:
        print("ChromaDB server command not found; vector features will use fallback memory.")
        return

    data_dir = os.path.join(os.path.dirname(__file__), "data", "chroma-server")
    os.makedirs(data_dir, exist_ok=True)
    subprocess.Popen(
        [chroma, "run", "--path", data_dir, "--host", host, "--port", str(port)],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    for _ in range(20):
        if _port_open(host, port):
            print(f"Started local ChromaDB at {host}:{port}")
            return
        time.sleep(0.25)
    print("ChromaDB did not become ready; vector features will use fallback memory.")


def main() -> int:
    banner()
    host = os.getenv("APP_BIND", "127.0.0.1")
    port = os.getenv("APP_PORT", "7000")
    url = f"http://{host}:{port}"
    print(f"Starting GepLex on {url}")
    print("The browser will open automatically when the app is ready.\n")
    start_local_chroma()

    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "app:app",
        "--host",
        host,
        "--port",
        port,
    ]
    try:
        subprocess.Popen(cmd)
        open_browser(url)
        print("GepLex started in the background.")
        print("Press Ctrl+C in this terminal to stop it.\n")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nGepLex shutdown requested.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
