#!/usr/bin/env python3
"""GepLex / GepLex Workspace - Desktop Start Bot & Control Panel.

A standalone, dark-themed visual controller GUI built with pure Python / Tkinter.
No third-party GUI dependencies required.
"""

from __future__ import annotations

import os
import sys
import time
import socket
import threading
import subprocess
import urllib.request
import webbrowser
from pathlib import Path

try:
    import tkinter as tk
    from tkinter import ttk, messagebox, scrolledtext
except ImportError:
    print("Tkinter is required for the GUI Start Bot. Please run start_bot_headless.py instead.")
    sys.exit(1)

# Resolve app base directory properly (handles both root and bots/ location)
BASE_DIR = Path(__file__).resolve().parent
if BASE_DIR.name == "bots":
    BASE_DIR = BASE_DIR.parent

if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# Color Palette (Modern Dark Cyberpunk/Indigo)
BG_DARK = "#0f172a"       # Slate 900
BG_CARD = "#1e293b"       # Slate 800
BG_CARD_LIGHT = "#334155" # Slate 700
ACCENT_PURPLE = "#8b5cf6" # Violet 500
ACCENT_CYAN = "#06b6d4"   # Cyan 500
TEXT_WHITE = "#f8fafc"    # Slate 50
TEXT_MUTED = "#94a3b8"    # Slate 400
STATUS_GREEN = "#10b981"  # Emerald 500
STATUS_RED = "#ef4444"    # Red 500
STATUS_YELLOW = "#f59e0b" # Amber 500


class GepLexBotApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("GepLex AI - 1-Click Start Bot")
        self.root.geometry("680x620")
        self.root.minsize(580, 520)
        self.root.configure(bg=BG_DARK)

        self.server_proc: subprocess.Popen | None = None
        self.is_running = False
        self.host = os.getenv("APP_BIND", "127.0.0.1")
        self.port = int(os.getenv("APP_PORT", "7000"))
        self.url = f"http://{self.host}:{self.port}"

        self._build_ui()
        self._check_initial_status()

    def _build_ui(self):
        # Header Frame
        header = tk.Frame(self.root, bg=BG_CARD, height=90, padx=20, pady=15)
        header.pack(fill="x", padx=16, pady=(16, 10))

        # Title & Subtitle
        title_frame = tk.Frame(header, bg=BG_CARD)
        title_frame.pack(side="left", fill="y")

        title_lbl = tk.Label(
            title_frame,
            text="⚡ GepLex AI Workspace",
            font=("Segoe UI", 16, "bold"),
            fg=TEXT_WHITE,
            bg=BG_CARD,
        )
        title_lbl.pack(anchor="w")

        sub_lbl = tk.Label(
            title_frame,
            text="Autonomous Agent & Self-Hosted AI Control Center",
            font=("Segoe UI", 9),
            fg=ACCENT_CYAN,
            bg=BG_CARD,
        )
        sub_lbl.pack(anchor="w", pady=(2, 0))

        # Status Badge Frame
        status_box = tk.Frame(header, bg=BG_CARD_LIGHT, padx=12, pady=6)
        status_box.pack(side="right")

        self.status_dot = tk.Label(
            status_box,
            text="●",
            font=("Segoe UI", 13, "bold"),
            fg=STATUS_RED,
            bg=BG_CARD_LIGHT,
        )
        self.status_dot.pack(side="left", padx=(0, 6))

        self.status_lbl = tk.Label(
            status_box,
            text="STOPPED",
            font=("Segoe UI", 10, "bold"),
            fg=TEXT_WHITE,
            bg=BG_CARD_LIGHT,
        )
        self.status_lbl.pack(side="left")

        # Action Cards Frame
        actions_frame = tk.Frame(self.root, bg=BG_DARK)
        actions_frame.pack(fill="x", padx=16, pady=8)

        # Main Start/Stop Button
        self.btn_toggle = tk.Button(
            actions_frame,
            text="🚀 START AI WORKSPACE (1-Click)",
            font=("Segoe UI", 11, "bold"),
            bg=ACCENT_PURPLE,
            fg="#ffffff",
            activebackground="#7c3aed",
            activeforeground="#ffffff",
            relief="flat",
            cursor="hand2",
            padx=16,
            pady=10,
            command=self.toggle_server,
        )
        self.btn_toggle.pack(fill="x", pady=(0, 8))

        # Secondary Button Bar
        btn_bar = tk.Frame(actions_frame, bg=BG_DARK)
        btn_bar.pack(fill="x")

        self.btn_browser = tk.Button(
            btn_bar,
            text="🌐 Open Web Interface",
            font=("Segoe UI", 9, "bold"),
            bg=BG_CARD,
            fg=ACCENT_CYAN,
            activebackground=BG_CARD_LIGHT,
            activeforeground=ACCENT_CYAN,
            relief="flat",
            cursor="hand2",
            padx=12,
            pady=8,
            command=self.open_browser,
        )
        self.btn_browser.pack(side="left", fill="x", expand=True, padx=(0, 4))

        self.btn_shortcut = tk.Button(
            btn_bar,
            text="🖥️ Create Desktop Shortcut",
            font=("Segoe UI", 9, "bold"),
            bg=BG_CARD,
            fg=TEXT_WHITE,
            activebackground=BG_CARD_LIGHT,
            activeforeground=TEXT_WHITE,
            relief="flat",
            cursor="hand2",
            padx=12,
            pady=8,
            command=self.create_desktop_shortcut,
        )
        self.btn_shortcut.pack(side="left", fill="x", expand=True, padx=4)

        self.btn_setup = tk.Button(
            btn_bar,
            text="⚙️ Setup / Fix Dependencies",
            font=("Segoe UI", 9, "bold"),
            bg=BG_CARD,
            fg=TEXT_MUTED,
            activebackground=BG_CARD_LIGHT,
            activeforeground=TEXT_WHITE,
            relief="flat",
            cursor="hand2",
            padx=12,
            pady=8,
            command=self.run_setup_thread,
        )
        self.btn_setup.pack(side="left", fill="x", expand=True, padx=(4, 0))

        # Console / Logs Frame
        log_frame = tk.Frame(self.root, bg=BG_CARD, padx=12, pady=12)
        log_frame.pack(fill="both", expand=True, padx=16, pady=(8, 16))

        log_header = tk.Frame(log_frame, bg=BG_CARD)
        log_header.pack(fill="x", pady=(0, 6))

        log_title = tk.Label(
            log_header,
            text="📋 Live Server Console & Logs",
            font=("Segoe UI", 9, "bold"),
            fg=TEXT_MUTED,
            bg=BG_CARD,
        )
        log_title.pack(side="left")

        btn_clear = tk.Button(
            log_header,
            text="Clear",
            font=("Segoe UI", 8),
            bg=BG_CARD_LIGHT,
            fg=TEXT_WHITE,
            relief="flat",
            padx=8,
            pady=2,
            command=self.clear_logs,
        )
        btn_clear.pack(side="right")

        self.log_text = scrolledtext.ScrolledText(
            log_frame,
            wrap=tk.WORD,
            bg="#0b0f19",
            fg="#e2e8f0",
            insertbackground="#ffffff",
            font=("Consolas", 9),
            relief="flat",
            padx=8,
            pady=8,
        )
        self.log_text.pack(fill="both", expand=True)

        # Footer info
        footer = tk.Frame(self.root, bg=BG_DARK)
        footer.pack(fill="x", padx=16, pady=(0, 10))

        self.url_lbl = tk.Label(
            footer,
            text=f"Address: {self.url} (Click Open Web Interface to use)",
            font=("Segoe UI", 8),
            fg=TEXT_MUTED,
            bg=BG_DARK,
        )
        self.url_lbl.pack(side="left")

        ver_lbl = tk.Label(
            footer,
            text="GepLex v1.0.3",
            font=("Segoe UI", 8),
            fg=TEXT_MUTED,
            bg=BG_DARK,
        )
        ver_lbl.pack(side="right")

        self.log("[System] Bot initialized. Click 'START AI WORKSPACE' to launch.")

    def log(self, message: str):
        def _append():
            self.log_text.insert(tk.END, message + "\n")
            self.log_text.see(tk.END)
        self.root.after(0, _append)

    def clear_logs(self):
        self.log_text.delete("1.0", tk.END)

    def update_status(self, state: str):
        def _update():
            if state == "RUNNING":
                self.status_dot.config(fg=STATUS_GREEN)
                self.status_lbl.config(text=f"RUNNING (:{self.port})", fg=STATUS_GREEN)
                self.btn_toggle.config(
                    text="⏹️ STOP AI WORKSPACE",
                    bg=STATUS_RED,
                    activebackground="#dc2626",
                )
                self.is_running = True
            elif state == "STARTING":
                self.status_dot.config(fg=STATUS_YELLOW)
                self.status_lbl.config(text="STARTING...", fg=STATUS_YELLOW)
                self.btn_toggle.config(text="⏳ STARTING...", state="disabled")
            else:
                self.status_dot.config(fg=STATUS_RED)
                self.status_lbl.config(text="STOPPED", fg=TEXT_WHITE)
                self.btn_toggle.config(
                    text="🚀 START AI WORKSPACE (1-Click)",
                    bg=ACCENT_PURPLE,
                    activebackground="#7c3aed",
                    state="normal",
                )
                self.is_running = False
        self.root.after(0, _update)

    def _check_initial_status(self):
        def _check():
            if self._is_port_open():
                self.log(f"[Status] Existing server detected on port {self.port}!")
                self.update_status("RUNNING")
        threading.Thread(target=_check, daemon=True).start()

    def _is_port_open(self) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.6)
            return s.connect_ex((self.host, self.port)) == 0

    def toggle_server(self):
        if self.is_running:
            self.stop_server()
        else:
            self.start_server()

    def start_server(self):
        self.update_status("STARTING")
        self.log(f"[Action] Starting GepLex AI server on {self.url} ...")

        def _worker():
            try:
                try:
                    from scripts.build_dist import build_cloudflare_dist
                    self.log("[Build] Updating Cloudflare dist & geplex-cloudflare-upload.zip...")
                    build_cloudflare_dist()
                    self.log("[Build] Cloudflare zip & dist updated!")
                except Exception as b_err:
                    self.log(f"[Build] Note: {b_err}")

                # Set environment for Windows Proactor loop & Python
                env = os.environ.copy()
                env["PYTHONUNBUFFERED"] = "1"

                venv_py = BASE_DIR / "venv" / "Scripts" / "python.exe"
                py_exec = str(venv_py) if venv_py.exists() else sys.executable

                cmd = [
                    py_exec,
                    "-m",
                    "uvicorn",
                    "app:app",
                    "--host",
                    self.host,
                    "--port",
                    str(self.port),
                ]

                # Run process with redirected pipes
                self.server_proc = subprocess.Popen(
                    cmd,
                    cwd=str(BASE_DIR),
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
                )

                # Thread to stream server logs into GUI text box
                def _stream_logs():
                    if self.server_proc and self.server_proc.stdout:
                        for line in iter(self.server_proc.stdout.readline, ""):
                            if line:
                                self.log(line.rstrip())
                    self.log("[Backend] Process terminated.")
                    self.update_status("STOPPED")

                threading.Thread(target=_stream_logs, daemon=True).start()

                # Poll until port is live
                connected = False
                for _ in range(40):
                    time.sleep(0.4)
                    if self._is_port_open():
                        connected = True
                        break

                if connected:
                    self.log(f"[+] GepLex is live! Opening browser at {self.url}")
                    self.update_status("RUNNING")
                    self.open_browser()
                else:
                    self.log("[-] Server took longer than expected to bind port. Check logs above.")
                    self.update_status("RUNNING" if self._is_port_open() else "STOPPED")

            except Exception as e:
                self.log(f"[Error] Failed to start server: {e}")
                self.update_status("STOPPED")

        threading.Thread(target=_worker, daemon=True).start()

    def stop_server(self):
        self.log("[Action] Stopping server...")
        if self.server_proc:
            try:
                self.server_proc.terminate()
                self.server_proc.wait(timeout=3)
            except Exception:
                try:
                    self.server_proc.kill()
                except Exception:
                    pass
            self.server_proc = None
        self.update_status("STOPPED")
        self.log("[+] Server stopped.")

    def open_browser(self):
        try:
            webbrowser.open(self.url, new=2)
        except Exception as e:
            self.log(f"[-] Could not launch browser: {e}")

    def create_desktop_shortcut(self):
        try:
            from create_shortcut import create_shortcut, get_windows_desktop_path
            success = create_shortcut()
            if success:
                desktop = get_windows_desktop_path()
                shortcut_path = desktop / "GepLex AI Bot.lnk"
                self.log(f"[+] Desktop shortcut created: {shortcut_path}")
                messagebox.showinfo(
                    "Shortcut Created",
                    f"✅ 'GepLex AI Bot' shortcut successfully placed on your Desktop!\n\nLocation:\n{shortcut_path}\n\nYou can now start the AI workspace directly from your Desktop with 1 click."
                )
            else:
                self.log("[-] Failed to create shortcut.")
                messagebox.showerror("Shortcut Error", "Could not create desktop shortcut. Check console logs.")
        except Exception as e:
            self.log(f"[-] Error creating shortcut: {e}")
            messagebox.showerror("Shortcut Error", f"Could not create shortcut: {e}")

    def run_setup_thread(self):
        self.log("[Setup] Running environment verification & setup...")
        def _worker():
            venv_py = BASE_DIR / "venv" / "Scripts" / "python.exe"
            py_exec = str(venv_py) if venv_py.exists() else sys.executable

            setup_script = BASE_DIR / "setup.py"
            if setup_script.exists():
                proc = subprocess.Popen(
                    [py_exec, str(setup_script)],
                    cwd=str(BASE_DIR),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                )
                if proc.stdout:
                    for line in iter(proc.stdout.readline, ""):
                        self.log(line.rstrip())
                proc.wait()
                self.log("[Setup] Environment & database setup completed.")
            else:
                self.log("[-] setup.py not found.")
        threading.Thread(target=_worker, daemon=True).start()


def main():
    root = tk.Tk()
    app = GepLexBotApp(root)
    root.protocol("WM_DELETE_WINDOW", lambda: (app.stop_server() if app.is_running else None, root.destroy()))
    root.mainloop()


if __name__ == "__main__":
    main()
