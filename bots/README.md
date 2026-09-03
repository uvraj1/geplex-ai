# GepLex Automation & Management Bots

This directory houses all automated control, diagnostic, and startup bots for the **GepLex AI Workspace**.

---

## Bots Overview

### 1. Fast 1-Click Startup Bot (`start_bot_headless.py`)
- **Purpose**: Autonomous, console-based launcher.
- **Features**:
  - Automatically checks port availability (`7000` default).
  - Starts the backend FastAPI server (`app:app`) via Uvicorn.
  - Actively polls the `/api/health` endpoint until the server is fully ready.
  - Automatically launches your default web browser to `http://localhost:7000`.
  - Handles clean graceful shutdown on `Ctrl+C`.

### 2. Desktop Control Center GUI (`start_bot_gui.py`)
- **Purpose**: Visual Tkinter dashboard with a modern dark theme.
- **Features**:
  - Real-time server status indicator (ONLINE / STARTING / STOPPED).
  - 1-Click Start / Stop server button with live log streaming.
  - "Open Web Interface" shortcut button.
  - "Create Desktop Shortcut" button (places a Windows Desktop `.lnk` shortcut).
  - Automated dependency verification.

### 3. Backend Control & Live Test Diagnostic Bot (`backend_control_bot.py`)
- **Purpose**: Interactive CLI tool for testing, diagnostics, and management.
- **Features**:
  - Start, Stop, and Restart backend server with automatic port cleanup.
  - Run full automated test suite:
    1. Server liveness check (`/api/health`)
    2. Authentication system status (`/api/auth/status`)
    3. Login screen HTML rendering check
    4. Auth database integrity verification (`data/auth.json`)
    5. Live simulation: account signup -> login -> session verification -> logout -> test cleanup
  - User management menu (add user, toggle open registration, change admin rights).
  - Real-time backend log viewer.

---

## How to Run
- Run `START_BOT.bat` to launch the AI workspace or open the GUI.
- Run `BACKEND_BOT.bat` to open the interactive test & diagnostic menu.
- Or run via Python:
  ```bash
  python bots/start_bot_headless.py
  python bots/start_bot_gui.py
  python bots/backend_control_bot.py
  ```
