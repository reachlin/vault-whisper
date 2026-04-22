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

## Phase 3 — Real Hardware

- Raspberry Pi GPIO drivers for LEDs, motors, servos
- Camera capture via picamera2 or OpenCV
- Mic via pyaudio + VAD
- IMU via smbus2

---

## Phase 4 — Extras

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
