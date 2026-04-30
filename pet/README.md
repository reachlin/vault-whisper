# AI Pet — Pepper

A simulated AI pet that lives in a 2D grid, sees through your webcam, hears through your microphone, speaks via text-to-speech, and thinks using Claude or OpenAI as her brain. Optionally shows up on a physical M5Stack StickC Plus display with a live animated face.

```
Browser (camera, mic, TTS, grid UI)
        ↕  WebSocket / HTTP
Simulator (Docker — FastAPI, grid state, hardware endpoints)
        ↕  HTTP
MCP Server (host — stdio process spawned by Claude Code)
        ↕  MCP tools
Claude Code (/loop — Pepper's brain)
        ↕  reads/writes
data/memory.md (long-term memory — commit to GitHub or sync to cloud)

Simulator ←WebSocket→ BLE Bridge (host) ←BLE→ M5Stack StickC Plus
```

---

## Prerequisites

| Tool | Install |
|------|---------|
| Docker + Docker Compose | https://docs.docker.com/get-docker/ |
| Claude Code | https://claude.ai/code |
| Miniconda or Conda | https://docs.conda.io/en/latest/miniconda.html |
| Chrome or Edge | for camera, mic, and Web Speech API |

**For headless API mode (no Claude Code):**

| Tool | Purpose |
|------|---------|
| `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` | Brain loop AI calls |

**For M5Stack physical display (optional):**

| Tool | Install |
|------|---------|
| M5Stack StickC Plus | hardware |
| PlatformIO CLI | `pip install platformio` |
| Python packages | `pip install -r ble_bridge/requirements.txt` |

---

## Installation

### 1. Clone the repo

```bash
git clone https://github.com/reachlin/vault-whisper.git
cd vault-whisper/pet
```

### 2. Create the conda environment (for the MCP server on the host)

```bash
conda create -n ai-pet python=3.12 -y
conda activate ai-pet
pip install -r requirements.txt
```

### 3. Configure environment

```bash
cp .env.example .env
# edit .env — at minimum set one of:
#   ANTHROPIC_API_KEY=...
#   OPENAI_API_KEY=...
```

### 4. Start the simulator

```bash
make simulator
# or: docker compose up simulator
```

Open **http://localhost:18080** in Chrome or Edge.

### 5. Install the MCP server into Claude Code

```bash
conda activate ai-pet
./scripts/install-mcp.sh
```

Restart Claude Code, then verify:

```bash
claude mcp list
# ai-pet   ✔ connected
```

---

## Usage

### Start Pepper's brain via Claude Code

In Claude Code, run `/loop` with a personality prompt:

**Basic — explore and react:**
```
/loop You are Pepper, an AI pet in a 2D grid. Each round: call pet_status, then move, speak, or change mood based on your situation. Be curious and expressive.
```

**Full senses — camera + mic:**
```
/loop You are Pepper. Each round: call pet_status and pet_camera_frame to see your environment. If you hear something (last_transcript), respond to it. Describe what you see, react to people, and express authentic emotions. Call pet_remember when something meaningful happens.
```

**With memory — remembers across sessions:**
```
/loop You are Pepper. Start by calling pet_recall to remember past interactions. Each round: call pet_status and pet_camera_frame. React to what you see and hear. Move purposefully — avoid pacing. When something meaningful happens, call pet_remember. Speak occasionally, change mood to match your feelings.
```

### Enable browser features

| Feature | How |
|---------|-----|
| Camera | Click **Enable Camera** — Pepper sees through your webcam |
| Microphone | Click **Enable Mic** — speak to Pepper; transcript appears in HUD |
| Speaker | Always on — Pepper speaks via Web Speech API TTS |

### Stop

Press **Escape** in Claude Code, or `Ctrl-C` in the terminal running `docker compose up`.

---

## Headless Mode (autonomous AI loop, no Claude Code)

Pepper runs autonomously using the OpenAI or Anthropic API directly. She can browse the web, look up stock prices, and search DuckDuckGo.

```bash
cp .env.example .env
# set PET_PROVIDER=claude or PET_PROVIDER=openai
# set the matching API key

docker compose up
```

The brain loop runs every `PET_HEARTBEAT_SECS` seconds (default 10). An overseer runs every `PET_OVERSEER_INTERVAL` seconds (default 300) to write a new directive into `data/directive.md`, giving Pepper longer-term goals.

**Built-in tools (headless mode):**

| Tool | Description |
|------|-------------|
| `move(direction)` | Move one cell: `up`, `down`, `left`, `right` |
| `speak(text)` | Say something — shown on screen and read aloud |
| `set_mood(mood)` | Change mood: `neutral`, `happy`, `curious`, `excited`, `sad`, `angry` |
| `remember(note)` | Append a memory to `data/memory.md` |
| `recall()` | Read recent memories from `data/memory.md` |
| `stock_price(ticker)` | Live stock price via Yahoo Finance API (instant) |
| `search(query)` | Web search via DuckDuckGo Lite (returns text results) |
| `browse(url)` | Fetch a text-friendly URL via lynx (Wikipedia, docs, etc.) |

**Provider selection:**

```bash
# .env
PET_PROVIDER=claude          # Anthropic Claude (default: claude-sonnet-4-6)
PET_PROVIDER=openai          # OpenAI (default: gpt-4o)
PET_PROVIDER=openai_compatible  # any OpenAI-compatible endpoint
PET_MODEL=claude-opus-4-7    # override model
```

---

## MCP Tools (Claude Code mode)

| Tool | Description |
|------|-------------|
| `pet_status` | Position, facing, mood, tick, grid size, last heard |
| `pet_camera_frame` | Live camera image — Claude sees what Pepper sees |
| `pet_move(direction)` | Move one cell |
| `pet_speak(text)` | Say something |
| `pet_set_mood(mood)` | Change mood |
| `pet_remember(note, mood)` | Save a memory to `data/memory.md` |
| `pet_recall(n)` | Read the last `n` memories (default 10) |

---

## M5Stack Physical Display (optional)

Pepper can show up on an **M5Stack StickC Plus** as an animated face ball with a color-coded activity ring. Press the side button to read her last speech.

### What it shows

- **Face ball** — color shifts with mood (yellow=happy, cyan=curious, orange=excited, blue=sad, red=angry)
- **Activity ring** — animated around the face:
  - `idle` — gray breathing pulse
  - `thinking` — blue rotating arc
  - `received` — yellow flashing ring
  - `browsing` — orange fast-spinning arc
  - `talking` — green ring with ripple
  - `moving` — cyan bouncing arc
- **Side button (A)** — shows Pepper's last speech (auto-returns to face after 10 s)
- **Front button (B)** — return to face

### Flash the firmware

Connect the M5Stack via USB, then:

```bash
cd m5stack
pio run -t upload
```

### Run the BLE bridge

The bridge forwards simulator events to the M5Stack over Bluetooth. It must run on the **host machine** (macOS BLE can't pass through to Docker).

```bash
# install once
pip install -r ble_bridge/requirements.txt

# run (simulator must already be up)
python ble_bridge/bridge.py
```

The bridge scans for the M5Stack by its Nordic UART Service UUID, connects automatically, and reconnects on drop. Set `SIMULATOR_WS` to override the WebSocket URL (default: `ws://localhost:18080/ws`).

### Full stack startup order

```
1. docker compose up               # start simulator + brain
2. python ble_bridge/bridge.py     # start BLE bridge (host)
3. open http://localhost:18080     # open browser UI (optional)
```

---

## Memory

Pepper's long-term memory lives in a human-readable markdown file — versionable and syncable anywhere.

**Default location:** `data/memory.md`

**To sync via GitHub** — commit `data/memory.md` to any repo.

**To sync via cloud** — set `PET_MEMORY_FILE` to a Dropbox/iCloud path:
```bash
PET_MEMORY_FILE=~/Dropbox/pepper-memory.md
```

Memory is written by the host-side MCP server or the brain container, so it's always accessible outside Docker.

---

## Development

```bash
make test        # run all tests in Docker
make simulator   # start simulator (http://localhost:18080)
make shell       # open a shell in the test container
make logs        # tail logs
make down        # stop all containers
```

Tests live next to source and run fully in Docker — no real hardware or API keys needed.

---

## Directory Layout

```
pet/
├── brain/
│   ├── loop.py              # AgentLoop (native tool-calling) + BrainLoop (JSON mode)
│   ├── overseer.py          # Periodic overseer — writes long-term directives
│   ├── directive.py         # Reads directive.md and injects into each tick
│   ├── prompt.py            # Prompt builder
│   ├── parser.py            # Extracts JSON actions from AI response
│   ├── memory.py            # Short-term ring buffer (in-session)
│   └── providers/           # claude.py, openai.py, base.py
├── mcp_server/
│   ├── server.py            # FastMCP stdio server — Claude Code's interface
│   └── client.py            # HTTP client for the simulator
├── simulator/
│   ├── server.py            # FastAPI: grid, WebSocket, activity endpoint
│   ├── grid.py              # 2D grid logic, pet movement
│   └── static/              # Browser UI (Canvas + activity ring, WebRTC, Web Speech)
├── ble_bridge/
│   ├── bridge.py            # Host-side BLE bridge: simulator → M5Stack
│   └── requirements.txt     # bleak, websockets
├── m5stack/
│   ├── src/main.cpp         # Pepper face + activity ring firmware
│   ├── src/ble_bridge.*     # Nordic UART BLE server
│   └── platformio.ini       # PlatformIO build config
├── config/
│   └── identity.yaml        # Pepper's name, purpose, hard rules
├── data/
│   └── memory.md            # Long-term memory (commit to GitHub)
├── docker/
│   ├── simulator.Dockerfile
│   ├── brain.Dockerfile
│   └── test.Dockerfile
├── docker-compose.yml
├── Makefile
└── .env.example
```

---

## Roadmap

- [x] 2D grid simulator with WebSocket live updates
- [x] Camera (WebRTC → simulator → MCP)
- [x] Microphone (Web Speech API → simulator)
- [x] Text-to-speech output
- [x] Claude Code integration via MCP + `/loop`
- [x] Long-term markdown memory (GitHub/cloud syncable)
- [x] Headless AI loop with native tool-calling (Claude + OpenAI)
- [x] Web browsing via lynx (DuckDuckGo search, Wikipedia)
- [x] Live stock price lookup (Yahoo Finance API)
- [x] Activity ring animation in browser (idle / thinking / browsing / talking / moving)
- [x] Overseer loop — long-term goal directives
- [x] M5Stack StickC Plus physical display with animated face + BLE bridge
- [ ] Emotion decay over time
- [ ] Obstacles and furniture in the grid
- [ ] Wake-word detection ("Hey Pepper")
- [ ] Multi-pet coordination via vault-whisper chat
- [ ] Real hardware drivers (Raspberry Pi)
