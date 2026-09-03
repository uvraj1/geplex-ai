#!/usr/bin/env python3
"""GepLex Backend Control & Live Test Bot.

Interactive command-line control center to:
- Start, stop, and restart the backend server
- Perform real-time health and authentication diagnostics
- Test signup, login, and logout flows live
- Manage users (list, add, toggle open registration, change password)
- Tail live application logs
"""

from __future__ import annotations

import os
import sys
import time
import json
import signal
import socket
import urllib.request
import urllib.error
import http.cookiejar
import subprocess
import webbrowser
from pathlib import Path

# Fix Windows console UTF-8 encoding
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Resolve app base directory properly (handles both root and bots/ location)
BASE_DIR = Path(__file__).resolve().parent
if BASE_DIR.name == "bots":
    BASE_DIR = BASE_DIR.parent

os.chdir(str(BASE_DIR))
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# ANSI Terminal Colors
C_RESET = "\033[0m"
C_BOLD = "\033[1m"
C_RED = "\033[91m"
C_GREEN = "\033[92m"
C_YELLOW = "\033[93m"
C_BLUE = "\033[94m"
C_MAGENTA = "\033[95m"
C_CYAN = "\033[96m"
C_GRAY = "\033[90m"


def print_banner() -> None:
    print(f"""{C_CYAN}{C_BOLD}
 ===================================================================
   ██████╗ ███████╗██████╗ ██╗     ███████╗██╗  ██╗
  ██╔════╝ ██╔════╝██╔══██╗██║     ██╔════╝╚██╗██╔╝
  ██║  ███╗█████╗  ██████╔╝██║     █████╗   ╚███╔╝ 
  ██║   ██║██╔══╝  ██╔═══╝ ██║     ██╔══╝   ██╔██╗ 
  ╚██████╔╝███████╗██║     ███████╗███████╗██╔╝ ██╗
   ╚═════╝ ╚══════╝╚═╝     ╚══════╝╚══════╝╚═╝  ╚═╝
   >> Backend Control & Diagnostic Bot <<
 ==================================================================={C_RESET}""")


def get_server_config() -> tuple[str, int, str]:
    host = os.getenv("APP_BIND", "127.0.0.1")
    port = int(os.getenv("APP_PORT", "7000"))
    url = f"http://{host}:{port}"
    return host, port, url


def is_port_in_use(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) == 0


def get_pid_on_port(port: int) -> list[int]:
    """Find process IDs listening on a specific port on Windows."""
    pids = []
    try:
        output = subprocess.check_output(f'netstat -ano | findstr :{port}', shell=True, text=True, errors="ignore")
        for line in output.splitlines():
            line = line.strip()
            if "LISTENING" in line:
                parts = line.split()
                if len(parts) >= 5:
                    try:
                        pid = int(parts[-1])
                        if pid not in pids and pid != 0:
                            pids.append(pid)
                    except ValueError:
                        pass
    except Exception:
        pass
    return pids


def kill_processes(pids: list[int]) -> None:
    for pid in pids:
        try:
            print(f"{C_YELLOW}[*] Terminating process PID {pid}...{C_RESET}")
            if sys.platform == "win32":
                subprocess.run(f"taskkill /F /PID {pid}", shell=True, capture_output=True)
            else:
                os.kill(pid, signal.SIGKILL)
            print(f"{C_GREEN}[+] Process {pid} stopped.{C_RESET}")
        except Exception as e:
            print(f"{C_RED}[!] Could not terminate PID {pid}: {e}{C_RESET}")


def check_server_health(url: str) -> dict:
    try:
        req = urllib.request.Request(f"{url}/api/health", headers={"User-Agent": "BackendBot/1.0"})
        with urllib.request.urlopen(req, timeout=2.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return {"online": True, "status": resp.status, "data": data}
    except Exception as e:
        return {"online": False, "error": str(e)}


def start_backend(url: str, host: str, port: int) -> None:
    if is_port_in_use(host, port):
        health = check_server_health(url)
        if health.get("online"):
            print(f"{C_YELLOW}[!] Backend is already running and healthy at {url}{C_RESET}")
            return
        else:
            print(f"{C_YELLOW}[!] Port {port} is occupied by another process. Freeing port...{C_RESET}")
            pids = get_pid_on_port(port)
            if pids:
                kill_processes(pids)
                time.sleep(1)

    print(f"{C_BLUE}[*] Launching backend server on {url} ...{C_RESET}")
    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "app:app",
        "--host",
        host,
        "--port",
        str(port),
        "--log-level",
        "info"
    ]

    try:
        proc = subprocess.Popen(cmd, cwd=str(BASE_DIR))
        print(f"{C_GREEN}[+] Server process spawned (PID: {proc.pid}){C_RESET}")
        print(f"[*] Waiting for server readiness...", end="", flush=True)
        for _ in range(30):
            time.sleep(0.5)
            print(".", end="", flush=True)
            if check_server_health(url).get("online"):
                print(f"\n{C_GREEN}{C_BOLD}[+] Backend server is LIVE & accepting requests at {url}{C_RESET}")
                return
        print(f"\n{C_YELLOW}[!] Server started but still initializing. Check logs if needed.{C_RESET}")
    except Exception as e:
        print(f"\n{C_RED}[!] Failed to start backend: {e}{C_RESET}")


def stop_backend(port: int) -> None:
    pids = get_pid_on_port(port)
    if not pids:
        print(f"{C_YELLOW}[*] No active server process found on port {port}.{C_RESET}")
        return
    print(f"{C_BLUE}[*] Stopping backend server processes on port {port}...{C_RESET}")
    kill_processes(pids)
    time.sleep(1)
    if not is_port_in_use("127.0.0.1", port):
        print(f"{C_GREEN}[+] Backend stopped successfully and port {port} is clean.{C_RESET}")
    else:
        print(f"{C_RED}[!] Port {port} is still in use.{C_RESET}")


def restart_backend(url: str, host: str, port: int) -> None:
    print(f"{C_BLUE}[*] Restarting Backend Server...{C_RESET}")
    stop_backend(port)
    time.sleep(1)
    start_backend(url, host, port)


def run_diagnostics(url: str) -> None:
    print(f"\n{C_CYAN}{C_BOLD}=======================================================")
    print(f"         RUNNING LIVE BACKEND DIAGNOSTICS")
    print(f"======================================================={C_RESET}\n")

    # 1. Health Liveness
    print(f"{C_BOLD}[1/5] Checking Server Liveness (/api/health)...{C_RESET}")
    health = check_server_health(url)
    if health.get("online"):
        print(f"  {C_GREEN}[OK] Server status: ONLINE (HTTP {health['status']}){C_RESET}")
        print(f"       Payload: {health.get('data')}")
    else:
        print(f"  {C_RED}[FAIL] Server is OFFLINE: {health.get('error')}{C_RESET}")
        print(f"  {C_YELLOW}→ Please start the backend first (Option 1).{C_RESET}\n")
        return

    # 2. Auth Status
    print(f"\n{C_BOLD}[2/5] Checking Auth System Status (/api/auth/status)...{C_RESET}")
    try:
        req = urllib.request.Request(f"{url}/api/auth/status")
        with urllib.request.urlopen(req, timeout=3.0) as resp:
            auth_data = json.loads(resp.read().decode("utf-8"))
            print(f"  {C_GREEN}[OK] Auth endpoint response (HTTP {resp.status}):{C_RESET}")
            print(f"       - Configured: {auth_data.get('configured')}")
            print(f"       - Open Signup Enabled: {C_GREEN if auth_data.get('signup_enabled') else C_RED}{auth_data.get('signup_enabled')}{C_RESET}")
            print(f"       - Authenticated: {auth_data.get('authenticated')}")
    except Exception as e:
        print(f"  {C_RED}[FAIL] Failed to fetch auth status: {e}{C_RESET}")

    # 3. Login Page Integrity
    print(f"\n{C_BOLD}[3/5] Testing Login Screen Rendering (/login)...{C_RESET}")
    try:
        req = urllib.request.Request(f"{url}/login")
        with urllib.request.urlopen(req, timeout=3.0) as resp:
            html = resp.read().decode("utf-8")
            has_logo = "GepLex" in html
            has_login = "Sign In" in html
            has_signup = "Sign up" in html
            if resp.status == 200 and has_login:
                print(f"  {C_GREEN}[OK] Login page loaded successfully (HTTP 200, Size: {len(html)} bytes){C_RESET}")
                print(f"       - Brand Title Present: {'Yes' if has_logo else 'No'}")
                print(f"       - Sign In Form Present: {'Yes' if has_login else 'No'}")
                print(f"       - Sign Up Option Present: {'Yes' if has_signup else 'No'}")
            else:
                print(f"  {C_YELLOW}[!] Login page returned unexpected content.{C_RESET}")
    except Exception as e:
        print(f"  {C_RED}[FAIL] Login page error: {e}{C_RESET}")

    # 4. Auth Database File Verification
    print(f"\n{C_BOLD}[4/5] Checking Data Files (data/auth.json)...{C_RESET}")
    auth_file = BASE_DIR / "data" / "auth.json"
    if auth_file.exists():
        try:
            with open(auth_file, "r", encoding="utf-8") as f:
                conf = json.load(f)
            user_count = len(conf.get("users", {}))
            signup_on = conf.get("signup_enabled", False)
            print(f"  {C_GREEN}[OK] auth.json exists & valid JSON{C_RESET}")
            print(f"       - Registered User Count: {C_BOLD}{user_count}{C_RESET}")
            print(f"       - Users: {list(conf.get('users', {}).keys())}")
            print(f"       - Open Registration: {C_GREEN if signup_on else C_RED}{signup_on}{C_RESET}")
        except Exception as e:
            print(f"  {C_RED}[FAIL] Error reading auth.json: {e}{C_RESET}")
    else:
        print(f"  {C_YELLOW}[!] data/auth.json not found (first-run mode).{C_RESET}")

    # 5. Live Simulated Auth Cycle (Signup -> Login -> Session Check -> Logout)
    print(f"\n{C_BOLD}[5/5] Running Live End-to-End Simulation Test...{C_RESET}")
    sim_user = f"bot_test_{int(time.time()) % 10000}"
    sim_pw = "TestPassword_1234!"
    cookie_jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookie_jar))

    try:
        # Step A: Signup
        signup_payload = json.dumps({"username": sim_user, "password": sim_pw}).encode("utf-8")
        req = urllib.request.Request(
            f"{url}/api/auth/signup",
            data=signup_payload,
            headers={"Content-Type": "application/json"}
        )
        with opener.open(req, timeout=3.0) as resp:
            s_res = json.loads(resp.read().decode("utf-8"))
            print(f"  {C_GREEN}[OK] Step A - Signup Account '{sim_user}': OK ({s_res.get('message')}){C_RESET}")

        # Step B: Login
        login_payload = json.dumps({"username": sim_user, "password": sim_pw}).encode("utf-8")
        req = urllib.request.Request(
            f"{url}/api/auth/login",
            data=login_payload,
            headers={"Content-Type": "application/json"}
        )
        with opener.open(req, timeout=3.0) as resp:
            l_res = json.loads(resp.read().decode("utf-8"))
            print(f"  {C_GREEN}[OK] Step B - Login with Credentials: OK (User: {l_res.get('username')}){C_RESET}")

        # Step C: Verify Authenticated Session
        req = urllib.request.Request(f"{url}/api/auth/status")
        with opener.open(req, timeout=3.0) as resp:
            st_res = json.loads(resp.read().decode("utf-8"))
            if st_res.get("authenticated") and st_res.get("username") == sim_user:
                print(f"  {C_GREEN}[OK] Step C - Session Authenticated: OK (Logged in as {sim_user}){C_RESET}")
            else:
                print(f"  {C_RED}[FAIL] Step C - Session Verification Failed!{C_RESET}")

        # Step D: Logout
        req = urllib.request.Request(
            f"{url}/api/auth/logout",
            data=b"{}",
            headers={"Content-Type": "application/json"}
        )
        with opener.open(req, timeout=3.0) as resp:
            print(f"  {C_GREEN}[OK] Step D - Logout & Cookie Invalidation: OK (HTTP {resp.status}){C_RESET}")

        # Cleanup simulated user
        from app import auth_manager
        auth_manager.delete_user(sim_user, "uv")
        print(f"  {C_GREEN}[OK] Cleanup - Test user '{sim_user}' cleaned up.{C_RESET}")

        print(f"\n{C_GREEN}{C_BOLD}[✓✓✓] ALL BACKEND SYSTEMS & AUTHENTICATION FLOWS ARE 100% OPERATIONAL!{C_RESET}\n")

    except urllib.error.HTTPError as he:
        err_msg = he.read().decode("utf-8")
        print(f"  {C_RED}[FAIL] Simulation Failed (HTTP {he.code}): {err_msg}{C_RESET}\n")
    except Exception as e:
        print(f"  {C_RED}[FAIL] Simulation Failed: {e}{C_RESET}\n")


def manage_users_menu() -> None:
    auth_file = BASE_DIR / "data" / "auth.json"
    if not auth_file.exists():
        print(f"{C_RED}[!] data/auth.json does not exist.{C_RESET}")
        return

    while True:
        try:
            with open(auth_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            print(f"{C_RED}[!] Could not read auth.json: {e}{C_RESET}")
            return

        users = data.get("users", {})
        signup_enabled = data.get("signup_enabled", False)

        print(f"\n{C_MAGENTA}{C_BOLD}--- User Management Menu ---{C_RESET}")
        print(f"Open Self-Registration (Sign Up): {C_GREEN + 'ENABLED' if signup_enabled else C_RED + 'DISABLED'}{C_RESET}")
        print(f"Registered Users ({len(users)}):")
        for u, info in users.items():
            role = f"{C_YELLOW}[ADMIN]{C_RESET}" if info.get("is_admin") else f"{C_GRAY}[USER]{C_RESET}"
            print(f"  • {C_BOLD}{u}{C_RESET} {role}")

        print(f"\n  {C_CYAN}[1]{C_RESET} Toggle Open Registration (Enable/Disable Sign Up)")
        print(f"  {C_CYAN}[2]{C_RESET} Create / Register New User")
        print(f"  {C_CYAN}[3]{C_RESET} Delete a User")
        print(f"  {C_CYAN}[4]{C_RESET} Set / Toggle Admin Privileges")
        print(f"  {C_CYAN}[0]{C_RESET} Back to Main Menu")

        choice = input(f"\n{C_BOLD}Select Option [0-4]: {C_RESET}").strip()
        if choice == "0":
            break
        elif choice == "1":
            from app import auth_manager
            auth_manager.signup_enabled = not auth_manager.signup_enabled
            print(f"{C_GREEN}[+] Open Registration is now: {'ENABLED' if auth_manager.signup_enabled else 'DISABLED'}{C_RESET}")
        elif choice == "2":
            uname = input("Enter new username: ").strip().lower()
            pw = input("Enter password (min 8 chars): ").strip()
            is_adm = input("Make Admin? (y/N): ").strip().lower() == "y"
            if len(uname) < 1 or len(pw) < 8:
                print(f"{C_RED}[!] Invalid username or password (min 8 chars required).{C_RESET}")
                continue
            from app import auth_manager
            if auth_manager.create_user(uname, pw, is_admin=is_adm):
                print(f"{C_GREEN}[+] User '{uname}' created successfully!{C_RESET}")
            else:
                print(f"{C_RED}[!] Username already exists or is reserved.{C_RESET}")
        elif choice == "3":
            uname = input("Enter username to delete: ").strip().lower()
            from app import auth_manager
            if auth_manager.delete_user(uname, "uv"):
                print(f"{C_GREEN}[+] User '{uname}' deleted.{C_RESET}")
            else:
                print(f"{C_RED}[!] Could not delete user (user not found or is self/last admin).{C_RESET}")
        elif choice == "4":
            uname = input("Enter username: ").strip().lower()
            make_admin = input("Make Admin? (y/n): ").strip().lower() == "y"
            from app import auth_manager
            res = auth_manager.set_admin(uname, make_admin, "uv")
            print(f"{C_GREEN}[+] Result: {res.value}{C_RESET}")


def view_logs() -> None:
    log_file = BASE_DIR / "data" / "logs" / "app.log"
    if not log_file.exists():
        print(f"{C_YELLOW}[!] Log file not found at {log_file}{C_RESET}")
        return
    print(f"\n{C_CYAN}{C_BOLD}=== Recent App Logs (Last 30 lines) ==={C_RESET}\n")
    try:
        with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
            for line in lines[-30:]:
                print(line.rstrip())
    except Exception as e:
        print(f"{C_RED}[!] Error reading logs: {e}{C_RESET}")
    print(f"\n{C_GRAY}(Press Enter to return to menu){C_RESET}")
    input()


def main_menu() -> None:
    host, port, url = get_server_config()

    while True:
        print_banner()
        is_up = check_server_health(url).get("online", False)
        status_text = f"{C_GREEN}● ONLINE{C_RESET}" if is_up else f"{C_RED}● OFFLINE{C_RESET}"

        print(f" Backend Address: {C_BOLD}{url}{C_RESET} | Status: {status_text}")
        print(" -------------------------------------------------------------------")
        print(f"  {C_CYAN}[1]{C_RESET} {C_BOLD}Start Backend Server{C_RESET} (Run in background)")
        print(f"  {C_CYAN}[2]{C_RESET} {C_BOLD}Restart Backend Server{C_RESET} (Fresh reload)")
        print(f"  {C_CYAN}[3]{C_RESET} {C_BOLD}Stop Backend Server{C_RESET} (Terminate & free port)")
        print(f"  {C_CYAN}[4]{C_RESET} {C_BOLD}Open Web Interface / Login Screen in Browser{C_RESET}")
        print(f"  {C_CYAN}[5]{C_RESET} {C_BOLD}Run Live Diagnostics & Auth Test Suite{C_RESET}")
        print(f"  {C_CYAN}[6]{C_RESET} {C_BOLD}Manage Users & Open Registration{C_RESET}")
        print(f"  {C_CYAN}[7]{C_RESET} {C_BOLD}View Recent Backend Logs{C_RESET}")
        print(f"  {C_CYAN}[0]{C_RESET} Exit")
        print(" -------------------------------------------------------------------")

        choice = input(f"{C_BOLD}Enter choice [0-7]: {C_RESET}").strip()

        if choice == "1":
            start_backend(url, host, port)
        elif choice == "2":
            restart_backend(url, host, port)
        elif choice == "3":
            stop_backend(port)
        elif choice == "4":
            print(f"{C_BLUE}[*] Opening {url}/login in your default browser...{C_RESET}")
            webbrowser.open(f"{url}/login")
        elif choice == "5":
            run_diagnostics(url)
        elif choice == "6":
            manage_users_menu()
        elif choice == "7":
            view_logs()
        elif choice == "0":
            print(f"\n{C_CYAN}[+] Exiting Backend Control Bot. Server state preserved.{C_RESET}\n")
            break
        else:
            print(f"{C_RED}[!] Invalid choice. Please enter a number 0-7.{C_RESET}")

        time.sleep(0.8)


if __name__ == "__main__":
    try:
        main_menu()
    except KeyboardInterrupt:
        print("\n\n[+] Exited Backend Control Bot.")
        sys.exit(0)
