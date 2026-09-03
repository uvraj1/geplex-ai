<p align="center">
  <img src="assets/branding/geplex-wordmark.svg" alt="GepLex" width="320">
</p>

<p align="center">
  GepLex is a self-hosted AI workspace for chat, agents, research, documents, email, notes, calendar, and local model workflows.
</p>

<p align="center">
  <a href="#quick-start">Quick Start</a> ·
  <a href="website/setup.md">Setup Guide</a> ·
  <a href="CONTRIBUTING.md">Contributing</a> ·
  <a href="ROADMAP.md">Roadmap</a>
</p>

<p align="center">
  <a href="https://repology.org/project/geplex/versions"><img src="https://repology.org/badge/vertical-allrepos/geplex.svg" alt="Packaging status"></a>
</p>

<p align="center">
  <img src="assets/branding/geplex-browser.jpg" alt="GepLex interface">
</p>

---

## Quick Start

> `dev` is the default branch and gets the newest changes first. Use [`main`](https://github.com/geplex-dev/geplex/tree/main) if you want the more curated branch.

```bash
git clone https://github.com/geplex-dev/geplex.git
cd geplex
cp .env.example .env
docker compose up -d --build
```

Open `http://localhost:7000` when the containers are healthy. The first admin password is printed in `docker compose logs geplex`.

Native installs, GPU notes, Windows/macOS instructions, HTTPS, and configuration live in the [setup guide](website/setup.md).

### Chat backend

GepLex now seeds a protected, in-process local chat backend by default, so the
chat UI works on a fresh install without an external API key or model server.
For full model quality, configure an Ollama, LM Studio, or other
OpenAI-compatible endpoint in Settings; the local backend remains a usable
offline fallback.

The built-in backend appends conversation history to
`data/conversation_memory.jsonl` and reuses relevant prior turns as context.
This is persistent memory, not model-weight training: an actual local model is
still required for independent, high-quality answers.

To prepare saved conversations for LoRA/fine-tuning after installing a
compatible ML stack, run:

```powershell
.\venv\Scripts\python.exe scripts\export_training_data.py
```

The exporter adds GepLex communication rules and redacts common secret formats.
Review the generated `data/geplex-training.jsonl` before training; memory should
not automatically become model weights without human/teacher verification.

## Features

- **Chat + Agents** — local/API models, tools, MCP, files, shell, skills, and memory.
- **Cookbook** — hardware-aware model recommendations, downloads, and serving.
- **Deep Research** — multi-step web research with source reading and report generation.
- **Compare** — blind side-by-side model testing and synthesis.
- **Documents** — writing-first editor with AI edits, suggestions, Markdown, HTML, CSV, and syntax highlighting.
- **Email** — IMAP/SMTP inbox with triage, tags, summaries, reminders, and reply drafts.
- **Notes, Tasks + Calendar** — reminders, todos, scheduled agent tasks, and CalDAV sync.
- **Extras** — gallery/image editor, themes, uploads, web search, presets, sessions, and 2FA.

## Demo

A full hover-to-play tour lives on the [GepLex landing page](https://geplex-dev.github.io/geplex/). Its source lives under [`website/`](website/).

## Contributing

Help is welcome. The best entry points are fresh-install testing, provider setup bugs, mobile/editor polish, docs, and small focused refactors. See [CONTRIBUTING.md](CONTRIBUTING.md) and [ROADMAP.md](ROADMAP.md).

## Security

GepLex is a self-hosted workspace with powerful local tools. Keep auth enabled, keep private data out of Git, and do not expose raw model/service ports publicly.

- Keep `AUTH_ENABLED=true` for any network-accessible deployment.
- Keep `LOCALHOST_BYPASS=false` outside local development.

Deployment details are in the [setup guide](website/setup.md#security-notes).

## Star History

<a href="https://star-history.dera.page/#geplex-dev/geplex&type=date&legend=top-left">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://star-history.dera.page/svg?repos=geplex-dev/geplex&type=date&theme=dark&legend=top-left" />
   <source media="(prefers-color-scheme: light)" srcset="https://star-history.dera.page/svg?repos=geplex-dev/geplex&type=date&legend=top-left" />
   <img alt="Star History Chart" src="https://star-history.dera.page/svg?repos=geplex-dev/geplex&type=date&legend=top-left" />
 </picture>
</a>

## License

AGPL-3.0-or-later -- see [LICENSE](LICENSE) and [ACKNOWLEDGMENTS.md](ACKNOWLEDGMENTS.md).
