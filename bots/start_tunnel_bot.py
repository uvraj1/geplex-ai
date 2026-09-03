"""start_tunnel_bot.py — 1-Click Cloudflare Tunnel & GepLex Backend Connector.

Starts the local backend and creates a secure Cloudflare Tunnel, automatically
connecting https://geplex.pages.dev to the local AI assistant.
"""

import os
import sys
import time
import re
import subprocess
import urllib.request

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLOUDFLARED_BIN = os.path.join(REPO_ROOT, "bots", "cloudflared.exe")

def is_backend_running(port=7000):
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1.5)
        return True
    except Exception:
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=1.5)
            return True
        except Exception:
            return False

def start_backend():
    print("[1/3] Checking GepLex local backend...")
    if is_backend_running():
        print("  -> Backend is already running on http://127.0.0.1:7000")
        return None
    
    print("  -> Starting backend server on http://127.0.0.1:7000...")
    python_exe = os.path.join(REPO_ROOT, "venv", "Scripts", "python.exe")
    if not os.path.exists(python_exe):
        python_exe = sys.executable
    
    proc = subprocess.Popen(
        [python_exe, "app.py"],
        cwd=REPO_ROOT,
        creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == "win32" else 0
    )
    for _ in range(30):
        if is_backend_running():
            print("  -> Backend started successfully!")
            return proc
        time.sleep(1)
    print("  -> Warning: Backend took long to respond, proceeding with tunnel.")
    return proc

def start_tunnel():
    print("\n[2/3] Starting Cloudflare Tunnel...")
    if not os.path.exists(CLOUDFLARED_BIN):
        print(f"Error: {CLOUDFLARED_BIN} not found.")
        return None, None
    
    proc = subprocess.Popen(
        [CLOUDFLARED_BIN, "tunnel", "--url", "http://127.0.0.1:7000"],
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
        bufsize=1
    )
    
    tunnel_url = None
    url_regex = re.compile(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com")
    
    print("  -> Establishing secure public HTTPS tunnel...")
    start_time = time.time()
    while time.time() - start_time < 30:
        line = proc.stderr.readline()
        if not line and proc.poll() is not None:
            break
        if line:
            match = url_regex.search(line)
            if match:
                tunnel_url = match.group(0)
                break
    
    if not tunnel_url:
        print("  -> Failed to obtain trycloudflare.com URL automatically.")
        return proc, None
    
    print(f"  -> Secure Tunnel URL: {tunnel_url}")
    return proc, tunnel_url

def update_cloud_deployment(tunnel_url):
    print(f"\n[3/3] Synchronizing Cloudflare Pages with Backend Tunnel ({tunnel_url})...")
    os.environ["GEPLEX_API_URL"] = tunnel_url
    token_file = os.path.join(REPO_ROOT, ".cloudflare_token")
    if os.path.exists(token_file):
        with open(token_file, "r", encoding="utf-8") as f:
            for line in f:
                if "=" in line:
                    k, v = line.strip().split("=", 1)
                    os.environ[k] = v
    
    build_script = os.path.join(REPO_ROOT, "scripts", "build-cloudflare-dist.ps1")
    subprocess.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", build_script], cwd=REPO_ROOT)
    
    wrangler_bin = os.path.join(REPO_ROOT, "node_modules", ".bin", "wrangler.cmd")
    subprocess.run([wrangler_bin, "pages", "deploy", "dist", "--project-name", "geplex", "--commit-dirty=true"], cwd=REPO_ROOT)
    
    print("\n" + "="*60)
    print("🎉 GEPLEX AI ASSISTANT IS 100% CONNECTED & LIVE!")
    print("="*60)
    print(f"Live Web App:      https://geplex.pages.dev")
    print(f"Connected Backend: {tunnel_url}")
    print("="*60)
    print("\nKeep this window open to maintain the live connection.")

def main():
    backend_proc = start_backend()
    tunnel_proc, tunnel_url = start_tunnel()
    if tunnel_url:
        update_cloud_deployment(tunnel_url)
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nShutting down tunnel...")
            if tunnel_proc:
                tunnel_proc.terminate()
            if backend_proc:
                backend_proc.terminate()

if __name__ == "__main__":
    main()
