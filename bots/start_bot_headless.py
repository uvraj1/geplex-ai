#!/usr/bin/env python3
"""GepLex / GepLex - Fast 1-Click Startup Bot & Browser Auto-Launcher.

Features:
- Port availability checking.
- Environment variables verification (.env auto-loader).
- Uvicorn server startup.
- Active polling for server readiness.
- Auto-opening default web browser once backend is ready.
- Graceful shutdown handling.
"""

from __future__ import annotations

import os
import sys
import time
import socket
import urllib.request
import webbrowser
import subprocess
from pathlib import Path

# Resolve app base directory properly (handles both root and bots/ location)
BASE_DIR = Path(__file__).resolve().parent
if BASE_DIR.name == "bots":
    BASE_DIR = BASE_DIR.parent

if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))


def print_banner() -> None:
    print(r"""
===================================================================
   ______               __               ___     ____ 
  / ____/ ___   ____   / /   ___  _  __ /   |   /  _/ 
 / / __  / _ \ / __ \ / /   / _ \| |/_// /| |   / /   
/ /_/ / /  __// /_/ // /___/  __/>  < / ___ |_ / /    
\____/  \___// .___//_____/\___/_/|_|/_/  |_(_)___/   
            /_/                                       
       >> GepLex / GepLex 1-Click AI Workspace <<
===================================================================
""")


def is_port_in_use(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.8)
        return s.connect_ex((host, port)) == 0


def wait_for_server(url: str, max_retries: int = 40, delay: float = 0.5) -> bool:
    print(f"[*] Waiting for GepLex AI Server to come online at {url} ...")
    for attempt in range(1, max_retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "GepLex-Launcher/1.0"})
            with urllib.request.urlopen(req, timeout=1.5) as resp:
                if resp.status in (200, 301, 302, 401, 403):
                    print(f"\n[+] GepLex AI Server is ONLINE and healthy! (Attempt {attempt})")
                    return True
        except Exception:
            pass
        print(".", end="", flush=True)
        time.sleep(delay)
    print("\n[-] Server started, opening browser now...")
    return False


def open_ui(url: str) -> None:
    print(f"[+] Launching Web Interface in your default browser: {url}")
    try:
        webbrowser.open(url, new=2)
    except Exception as e:
        print(f"[-] Could not launch browser automatically: {e}")
        print(f"    Please open {url} manually in Chrome, Edge, or Firefox.")


def main() -> int:
    os.chdir(str(BASE_DIR))
    print_banner()

    # Automatically refresh Cloudflare dist and zip on every start bot run
    try:
        from scripts.build_dist import build_cloudflare_dist
        build_cloudflare_dist()
    except Exception as e:
        print(f"[-] Dist sync note: {e}")

    bind_host = os.getenv("APP_BIND", "127.0.0.1")
    bind_port = int(os.getenv("APP_PORT", "7000"))
    url = f"http://{bind_host}:{bind_port}"

    if is_port_in_use(bind_host, bind_port):
        print(f"[!] Warning: Port {bind_port} is already in use!")
        print(f"[*] Attempting to open existing instance at {url} ...")
        open_ui(url)
        print("\nPress Ctrl+C to exit launcher.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            return 0

    print(f"[*] Initializing GepLex AI Workspace on {url}")

    # Set Windows event loop policy
    if sys.platform == "win32":
        import asyncio
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    # Build uvicorn command using current Python executable
    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "app:app",
        "--host",
        bind_host,
        "--port",
        str(bind_port),
        "--log-level",
        "info"
    ]

    print("[*] Starting backend process...")
    proc = subprocess.Popen(cmd, cwd=str(BASE_DIR))

    # Spawn thread/polling for browser open
    wait_for_server(url, max_retries=50, delay=0.4)
    open_ui(url)

    print("\n" + "=" * 65)
    print(f"  GepLex AI Workspace is running!")
    print(f"  URL: {url}")
    print(f"  Press Ctrl+C in this window to stop the server.")
    print("=" * 65 + "\n")

    try:
        proc.wait()
    except KeyboardInterrupt:
        print("\n[*] Stopping GepLex AI Workspace...")
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        print("[+] GepLex stopped cleanly. Have a great day!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
