# AI Pet — Pepper

A simulated AI pet that lives in a 2D grid, sees through your webcam, hears through your microphone, speaks via text-to-speech, and thinks using Claude Code as her brain.

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
```

---

## Prerequisites

| Tool | Install |
|------|---------|
| Docker + Docker Compose | https://docs.docker.com/get-docker/ |
| Claude Code | https://claude.ai/code |
| Miniconda or Conda | https://docs.conda.io/en/latest/miniconda.html |
| Chrome or Edge | for camera, mic, and Web Speech API |

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

This environment is used by Claude Code to run the MCP server. It must be active (or the full path used) when Claude Code spawns it.

### 3. Configure environment

```bash
cp .env.example .env
# edit .env — at minimum set:
#   PET_MEMORY_FILE=data/memory.md   (or a path in another git repo / cloud folder)
```

No API key needed for Claude Code integration — Claude Code handles auth.

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

This runs `claude mcp add ai-pet` pointing at `mcp_server/server.py` in the conda env.  
Restart Claude Code, then verify:

```bash
claude mcp list
# ai-pet   ✔ connected
```

---

## Usage

### Start Pepper's brain

In Claude Code, run `/loop` with a personality prompt:

**Basic** — just explore:
```
/loop You are Pepper, an AI pet in a 2D grid. Each round: call pet_status, then move, speak, or change mood based on your situation. Be curious and expressive.
```

**Full senses** — camera + mic:
```
/loop You are Pepper. Each round: call pet_status and pet_camera_frame to see your environment. If you hear something (last_transcript), respond to it. Describe what you see, react to people, and express authentic emotions. Call pet_remember when something meaningful happens.
```

**With memory** — remembers across sessions:
```
/loop You are Pepper. Start by calling pet_recall to remember past interactions. Each round: call pet_status and pet_camera_frame. React to what you see and hear. Move purposefully — avoid pacing. When something meaningful happens, call pet_remember. Speak occasionally, change mood to match your feelings.
```

### Enable hardware in the browser

| Feature | How |
|---------|-----|
| Camera | Click **Enable Camera** — Pepper sees through your webcam |
| Microphone | Click **Enable Mic** — speak to Pepper; transcript appears in HUD |
| Speaker | Always on — Pepper speaks via Web Speech API TTS |

### Stop the loop

Press **Escape** in Claude Code to interrupt the current round and stop the loop.

---

## MCP Tools

Claude Code has access to these tools each loop round:

| Tool | Description |
|------|-------------|
| `pet_status` | Position, facing, mood, tick, grid size, camera availability, last heard |
| `pet_camera_frame` | Live camera image — Claude sees what Pepper sees |
| `pet_move(direction)` | Move one cell: `up`, `down`, `left`, `right` |
| `pet_speak(text)` | Say something — shown on screen and spoken aloud |
| `pet_set_mood(mood)` | Change mood: `neutral`, `happy`, `curious`, `tired`, `scared` |
| `pet_remember(note, mood)` | Save a memory to `data/memory.md` |
| `pet_recall(n)` | Read the last `n` memories (default 10) |

---

## Memory

Pepper's long-term memory lives in a markdown file — human-readable, versionable, and syncable anywhere.

**Default location:** `data/memory.md` (inside the `pet/` folder)

**Format:**
```markdown
# Pepper's Memory

---
**2026-04-22 17:30 UTC** · (19, 0) · happy
Spotted a human with glasses staring through the camera. Lost my mind with excitement!

---
**2026-04-22 17:20 UTC** · (5, 3) · curious
Explored the top-left quadrant. Quiet and empty there.
```

**To sync via GitHub** — commit `data/memory.md` to any repo:
```bash
# point PET_MEMORY_FILE at a file in another repo
PET_MEMORY_FILE=/path/to/my-pet-memories/pepper.md
```

**To sync via cloud** — point `PET_MEMORY_FILE` at a Dropbox/iCloud/Google Drive path:
```bash
PET_MEMORY_FILE=~/Dropbox/pepper-memory.md
```

Memory is written by the host-side MCP server, not Docker, so it's always accessible.

---

## Directory Layout

```
pet/
├── brain/
│   ├── loop.py              # Headless brain loop (API mode, no Claude Code needed)
│   ├── prompt.py            # Prompt builder (identity + rules + state + memory)
│   ├── parser.py            # Extracts JSON actions from AI response
│   ├── memory.py            # Short-term ring buffer (in-session)
│   ├── longterm_memory.py   # Long-term markdown file memory
│   └── providers/           # claude.py, openai.py (for headless API mode)
├── mcp_server/
│   ├── server.py            # FastMCP stdio server — Claude Code's interface to Pepper
│   └── client.py            # HTTP client for the simulator
├── simulator/
│   ├── server.py            # FastAPI: grid state, hardware endpoints, WebSocket
│   ├── grid.py              # 2D grid logic, pet movement, boundaries
│   └── static/              # Browser UI (Canvas, WebRTC camera, Web Speech)
├── config/
│   └── identity.yaml        # Pepper's name, purpose, hard rules
├── data/
│   └── memory.md            # Pepper's long-term memory (commit this to GitHub)
├── docker/
│   ├── simulator.Dockerfile
│   ├── brain.Dockerfile     # For headless API mode
│   └── test.Dockerfile
├── scripts/
│   └── install-mcp.sh       # Registers MCP server with Claude Code
├── docker-compose.yml
├── Makefile
└── .env.example
```

---

## Development

```bash
make test        # run all 112 tests in Docker
make simulator   # start simulator (http://localhost:18080)
make shell       # open a shell in the test container
make logs        # tail simulator logs
make down        # stop all containers
```

Tests live next to source (`simulator/test_*.py`, `brain/test_*.py`, `mcp_server/test_*.py`) and run fully in Docker — no real hardware or API keys needed.

---

## Headless Mode (API without Claude Code)

If you want Pepper to run autonomously without Claude Code, use the brain loop directly:

```bash
conda activate ai-pet
cp .env.example .env
# set ANTHROPIC_API_KEY or OPENAI_API_KEY in .env

# start simulator + brain loop together
docker compose up
```

The brain loop calls the AI API directly every `PET_HEARTBEAT_SECS` seconds (default 10).

---

## Roadmap

- [x] 2D grid simulator with WebSocket live updates
- [x] Camera (WebRTC → simulator → MCP)
- [x] Microphone (Web Speech API → simulator)
- [x] Text-to-speech output
- [x] Claude Code integration via MCP + `/loop`
- [x] Long-term markdown memory (GitHub/cloud syncable)
- [ ] Emotion decay over time
- [ ] Obstacles and furniture in the grid
- [ ] Wake-word detection ("Hey Pepper")
- [ ] Multi-pet coordination via vault-whisper chat
- [ ] Real hardware drivers (Raspberry Pi)
