# Implementation Plan

## Phase 1 — Core Brain (mock hardware, no real device needed)

### Step 1: Config & Identity
- `config/identity.yaml` — name, purpose, hard rules
- `config/providers.yaml` — AI backend selection
- Loader in `brain/config.py`

### Step 2: Hardware Abstraction
- `hardware/sensors.py` — SensorReading dataclass + MockSensors (random plausible values)
- `hardware/actuators.py` — ActuatorCommand + MockActuators (print to console)
- Real drivers added later as subclasses; selected by `--mock` flag

### Step 3: Memory System
- `brain/memory.py`
  - `ShortTermMemory` — ring buffer (last N rounds), in-memory
  - `LongTermMemory` — SQLite, stores (timestamp, summary, embedding_stub)
  - `remember(text)` / `recall(query, k=5)` API

### Step 4: Prompt Builder
- `brain/prompt.py`
  - Injects hard rules as immutable system block
  - Appends sensory snapshot as user message
  - Appends memory context
  - Returns (system_prompt, user_message) tuple

### Step 5: AI Provider Adapters
- `brain/providers/base.py` — `Provider.complete(system, user) -> str`
- `brain/providers/claude.py` — Anthropic SDK, with prompt caching on system block
- `brain/providers/openai.py` — OpenAI SDK (also covers openai_compatible)

### Step 6: Action Parser
- `brain/parser.py`
  - Extracts JSON block from AI response
  - Validates against action schema
  - Returns list of `Action(skill, kwargs)`

### Step 7: Skill System
- `skills/base.py` — `Skill` base class with `name` and `run(**kwargs)`
- `skills/speak.py`, `move.py`, `express.py`, `rest.py`
- `skills/registry.py` — auto-discovers all Skill subclasses in `skills/`

### Step 8: Brain Loop
- `brain/loop.py` — ties everything together
  - `BrainLoop.run()` — infinite loop with configurable heartbeat
  - Graceful shutdown on SIGINT
  - Per-round logging

### Step 9: Entry Point
- `main.py` — CLI with `--mock`, `--heartbeat`, `--provider` flags

---

## Phase 2 — MCP Server

### Step 10: FastMCP Server
- `mcp_server/server.py` — FastMCP app
- Tools: `pet_status`, `pet_command`, `pet_memory_search`, `pet_identity`
- Reads shared state from brain via a lightweight IPC (file or socket)

---

## Phase 3 — M5Stack Physical Body (in progress)

### Done
- [x] M5Stack StickC Plus firmware — animated face ball + activity ring, BLE Nordic UART
- [x] BLE bridge (`ble_bridge/bridge.py`) — simulator WebSocket → M5Stack display
- [x] Activity ring: 6 animated states (idle, thinking, received, browsing, talking, moving)
- [x] Speech screen on button press
- [x] Hat SPK2 speaker — BLE PCM audio streaming, macOS TTS + OpenAI TTS fallback
- [x] Pip-Boy 3000 face aesthetic — phosphor green, CRT scan lines, block-pixel eyes/mouth
- [x] Robco terminal sleep screen — shown when BLE disconnects; speaker silenced via `i2s_zero_dma_buffer`
- [x] Browser mute button — silences computer TTS when M5Stack speaker is active
- [x] Multilingual voice — `language` field in `identity.yaml`; SAY_VOICE env for macOS voices (Meijia, Tingting, Thomas…); OpenAI TTS auto-detects language
- [x] Camera vision — Pepper receives webcam frame every tick and actively reacts to what she sees

### Done — Speaker (Hat SPK2)

**Hardware:** M5Stack Hat SPK2 (MAX98357 I2S DAC), stacked on StickC Plus HAT port
- BCLK=GPIO26, LRCLK=GPIO0, DIN=GPIO25 — 8kHz 16-bit left-channel I2S

**BLE audio protocol:** binary frames on NUS RX channel
- `0xAA + uint16_le_size + int16_le_pcm_data` — audio frame (signed 16-bit LE)
- `0xAA + 0x00 0x00` — end-of-audio sentinel (silences DMA buffer)
- Paced at 85% of playback rate so DMA buffer stays full
- **16kHz failed on ESP32 (BLE 4.2)** — write-without-response drops frames silently above ~16KB/s; 8kHz 16-bit (~16KB/s) is the ceiling
- **Fix: upgrade to StickC S3** — BLE 5.0 doubles PHY to 2 Mbps, making 16kHz 16-bit (~32KB/s) viable; update `afconvert` target rate and `AUDIO_RATE` constant

**TTS pipeline (macOS):**
- `say -v <voice>` → AIFF → `afconvert -d LEI16@8000 -q 127` → raw int16_le bytes over BLE
- 3× volume boost applied before streaming
- OpenAI `tts-1-hd` with voice `alloy` also implemented (set `OPENAI_API_KEY` to activate)
  — confirmed to fit Pip-Boy aesthetic; auto-detects language; disabled by default to save tokens

### Recommended Upgrade — Face/Brain (M5Stack StickC S3, ~$20–25)

Drop-in replacement for StickC Plus. Same 135×240 display and Hat port, Hat SPK2 still fits.

| | StickC Plus | StickC S3 |
|---|---|---|
| Chip | ESP32-PICO-D4 | ESP32-S3 |
| BLE | 4.2 (1 Mbps) | 5.0 (2 Mbps) |
| PSRAM | ~520 KB | 8 MB |

**Firmware migration:** `platformio.ini` board → `m5stick-cs3`, `#include <M5StickCPlus.h>` → `#include <M5StickCS3.h>`. Audio: change `AUDIO_RATE` to `16000` and update `afconvert` pipeline from `LEI16@8000` to `LEI16@16000`.

### Next — Camera / Eyes (needs hardware: AtomS3R CAM, ~$15–20)

Unit CamS3 (5MP) is hard to source. **AtomS3R CAM** is the recommended alternative — ESP32-S3, WiFi, MJPEG over HTTP, compact Atom form factor (~24×24mm), easy to mount.

**Integration plan:**
1. AtomS3R CAM streams MJPEG at `http://<cam-ip>/stream`
2. Add `camera_bridge/bridge.py` on host: pulls MJPEG frames, POSTs JPEG to simulator
   `/camera` endpoint (same path the browser WebRTC already uses)
3. Brain loop already reads frames via `get_last_frame()` — no brain changes needed
4. Pepper sees through the physical camera instead of (or alongside) the browser webcam

**Wiring note:** AtomS3R CAM is WiFi-only; no Grove connection to StickC needed.
Both devices connect independently to the same LAN.

### Future — Wheels / Legs

**RoverC Pro** (M5Stack snap-on chassis) was the ideal fit for StickC but is currently out of stock / discontinued everywhere.

**Recommended alternative: separate ESP32 motor controller over WiFi**

```
Mac brain ──BLE──► StickC S3  (face + speech)
Mac brain ──WiFi──► ESP32 motor node  (wheels / legs)
```

Parts (~$15–20 total):
- ESP32 DevKit (~$5)
- DRV8833 dual motor driver (~$3) — or L298N if higher current needed
- 2× TT geared DC motors + wheels (~$8) — standard 1:48 yellow motors

Brain sends movement commands via WiFi HTTP to motor node independently from BLE face channel. Motor node exposes `POST /move` with `{direction, speed, duration_ms}`.

**Legs (future, harder):** PCA9685 I2C servo driver + 4× SG90 servos + 3D-printed chassis. Requires gait programming — not a first build.

---

## Phase 4 — Minecraft Integration (in progress)

### Architecture

```
Minecraft Java Server
        │
        │ Mineflayer protocol
        ▼
minecraft/bridge.js  (Node.js, port 18090, runs on host)
        │                               ▲
        │ POST /mc/state (5s push)       │ GET /state, POST /chat,
        │                               │ POST /move, POST /mine,
        ▼                               │ POST /attack
simulator/server.py  ◄──────────────── brain/loop.py
  (stores MC state,                     (MC_BRIDGE_URL → host:18090)
   WS-broadcasts mc_state)
```

### Done
- [x] Mineflayer bridge (`minecraft/bridge.js`) — HTTP API wrapping Mineflayer bot
  - Endpoints: `POST /join`, `POST /leave`, `GET /state`, `POST /chat`, `POST /move`, `POST /mine`, `POST /place`, `POST /attack`
  - Pushes game state to simulator every 5s
  - Forwards in-game chat to simulator as transcript
- [x] Simulator `/mc/state` endpoint — receives bridge push, stores snapshot, WS-broadcasts
- [x] Simulator `/minecraft/join|leave|status` — browser UI join/leave controls
- [x] Browser "Join Minecraft" button with WS sync
- [x] Brain MC tool specs: `mc_state`, `mc_chat`, `mc_move`, `mc_mine`, `mc_attack`
- [x] Brain MC tool handlers wired in `_execute` + `_mc_http` helper
- [x] `MC_BRIDGE_URL` env var in docker-compose brain service
- [x] System prompt updated: Pepper knows to use MC tools when `mc_state` shows connected

### To Do / Test
- [ ] `cd minecraft && npm install` — install Mineflayer deps (package.json ready)
- [ ] Verify Mineflayer supports Minecraft 26.1.x (new Mojang versioning) — may need `--version` pin
- [ ] Start a local Minecraft Java server, connect from bridge, verify Pepper navigates
- [ ] Update `/pepper` skill to include MC bridge startup step
- [ ] Add `mc_place` tool to brain (bridge already has `/place`)

### Startup (manual, bridge runs on host outside Docker)
```bash
cd minecraft && npm install && node bridge.js
# then from browser: click "Join Minecraft", enter server address
# brain auto-detects connected=true via mc_state()
```

---

## Phase 5 — Extras

- Emotion state machine (mood persists across rounds, decays over time)
- Web dashboard (FastAPI + HTMX, shows live brain state)
- Wake-word detection (porcupine or vosk)
- Multi-pet chat via vault-whisper

---

## Dependencies (Phase 1+2)

```
anthropic>=0.40
openai>=1.0
fastmcp>=0.4
pydantic>=2.0
pyyaml>=6.0
```
