# GepLex Main Source Code Architecture Hub

Welcome to the **Main Source Code** boundary for the GepLex AI Workspace.

---

## 🏛️ System Architecture & Directory Map

The editable core source code is structured as follows:

```
odysseus-dev/
├── app.py                   <-- Main FastAPI ASGI orchestrator & server lifecycle
│
├── core/                    <-- System Foundational Layer
│   ├── auth.py              <-- Session & JWT authentication management
│   ├── database.py          <-- SQLAlchemy SQLite database engine & schema definitions
│   ├── middleware.py        <-- Security headers, CORS, request tracing
│   ├── constants.py         <-- System-wide constants & directory anchors
│   └── exceptions.py        <-- Custom business logic & runtime error classes
│
├── src/                     <-- Core AI & Autonomous Agent Runtime
│   ├── llm_core.py          <-- Multi-provider unified LLM connector (OpenAI, Anthropic, Gemini, DeepSeek, Grok, Ollama)
│   ├── agent_loop.py        <-- Autonomous tool loop, reasoning engine, & multi-turn execution
│   ├── endpoint_resolver.py <-- Model endpoint routing, cost attribution, & URL normalization
│   ├── memory.py            <-- Vector memory, session history, & semantic retrieval
│   ├── preset_manager.py    <-- AI personas & instruction presets
│   ├── tools/               <-- Built-in tools (web search, files, shell, code, email, calendar)
│   └── task_scheduler.py    <-- Background automated jobs & recurring tasks
│
├── routes/                  <-- REST & WebSocket API Routers
│   ├── chat_routes.py       <-- Real-time streaming chat endpoints
│   ├── auth_routes.py       <-- Login, registration, token verification
│   ├── model_routes.py      <-- Model discovery & endpoint configuration
│   ├── skills_routes.py     <-- Dynamic skill registration & execution
│   └── ...                  <-- Additional domain routers (email, calendar, notes, etc.)
│
├── services/                <-- Supporting Backend Services
│   ├── hwfit/               <-- Hardware-fit benchmarking & model recommendations
│   └── ...                  <-- Additional background processors
│
├── static/                  <-- Web Interface & Single-Page Application
│   ├── index.html           <-- Main UI application shell
│   ├── js/                  <-- Modular JavaScript front-end components
│   └── css/                 <-- UI styling & themes
│
├── config/                  <-- Service configurations (SearXNG, etc.)
│
├── bots/                    <-- Dedicated Automation & Management Bots
│   ├── start_bot_headless.py<-- 1-Click fast startup & auto-browser launcher
│   ├── start_bot_gui.py     <-- Visual Tkinter dark dashboard
│   ├── backend_control_bot.py<-- Interactive diagnostics & test suite
│   └── README.md            <-- Bot guide & usage
│
└── applications/            <-- Built Client Applications
    ├── desktop/             <-- Standalone Windows application (PyInstaller)
    └── android/             <-- Android mobile package (Capacitor)
```

---

## 🚀 Running the Core Server
The application is run using `uvicorn`:
```bash
uvicorn app:app --host 127.0.0.1 --port 7000 --reload
```
Or with 1-click via `START_BOT.bat` from the root directory or `bots/START_BOT.bat`.
