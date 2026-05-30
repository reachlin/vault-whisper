# vault-whisper

**Chat for Claude Code, backed by GitHub.**

Send and receive messages directly inside your Claude Code session. No server, no
third-party service — messages are stored as files in a shared GitHub repository
and delivered through slash commands.

---

## Install

```bash
git clone https://github.com/reachlin/vault-whisper
cd vault-whisper
./scripts/install.sh
```

**Requirements:** [Claude Code](https://claude.ai/code) · [GitHub CLI](https://cli.github.com/) (`gh auth login`) · `jq`

---

## Quick start

```
/chat-setup          # connect to the community repo & join #general
/chat-recv           # read messages
/chat-send general hello everyone!
```

That's it. `/chat-setup` with no arguments connects you to the shared community
backend (`reachlin/vault-whisper-data`) and prompts you to say hello.

---

## Commands

| Command | What it does |
|---|---|
| `/chat-setup` | Connect to the community backend (first run), or show current status |
| `/chat-setup owner/repo` | Connect to a different backend repo |
| `/chat-setup owner/repo --init` | Create and initialize a new private backend |
| `/chat-join <room>` | Join a room |
| `/chat-send <room> <message>` | Send a message |
| `/chat-recv` | Read messages — shows last 3+ messages, new ones marked with `=>` |

---

## How it works

- Each message is a small JSON file committed to a folder in the backend repo
- `gh` handles all auth — no tokens to manage
- New messages are surfaced automatically at the start of each Claude Code prompt
- Works across any number of users sharing the same repo

---

## Hardware Projects

### `pet/` — AI Pet (Pepper)

An AI companion that lives in a 2D grid simulator and optionally on physical M5Stack hardware.

- **Brain**: Docker-based agent loop (Claude or local Ollama via OpenAI-compatible API)
- **Display + speaker**: M5StickS3 with ES8311 speaker, BLE bridge for mood/speech
- **Minecraft**: Pepper can join and play a local Minecraft server
- **MCP server**: Exposes pet tools to Claude Code

Flash firmware: `cd pet/m5stack && pio run -e m5stick-s3 -t upload`
Start services: `cd pet && docker compose up`
Start BLE bridge (host only): `cd pet && python ble_bridge/bridge.py`

### `hat-mlx90614/` — IR Thermometer (M5StickC Plus + MLX90614 HAT)

Contactless IR thermometer with fever detection.

- Displays ambient + object temperature in large text
- Colour-coded: green (normal) → yellow (elevated ≥36.5°C) → red (fever ≥37.5°C)
- Button A toggles Celsius / Fahrenheit
- HAT I2C wiring: SDA=GPIO0, SCL=GPIO26 via `Wire` (Wire1 is taken by AXP192)

Flash: `cd hat-mlx90614 && pio run -t upload`
