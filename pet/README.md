# AI Pet — Brain + MCP Bridge

An AI-powered pet brain that runs an infinite cognitive loop, pairs with any on-device AI (Claude, OpenAI, local models), and exposes itself to AI tools on your computer via an MCP server.

---

## Concept

The pet has a **brain** — a loop that wakes up on a heartbeat, reads the world through sensors, thinks via an AI model, and acts through skills. It also runs an **MCP server** so that tools like Claude Code or Cursor can talk to and control the pet directly.

```
┌────────────────────────────────────────────────────┐
│                   Brain Loop                       │
│                                                    │
│  Sensors → Context Builder → AI API → Action Parser│
│      ↑                                     ↓       │
│   Memory ←─────────── Skills ──────────────┘       │
└────────────────────────────────────────────────────┘
          ↕  MCP Server (tools exposed to AI tools)
┌──────────────────────────┐
│  Claude Code / Cursor /  │
│  OpenAI / any MCP client │
└──────────────────────────┘
```

---

## Directory Layout

```
pet/
├── brain/
│   ├── loop.py          # Infinite brain loop (heartbeat)
│   ├── prompt.py        # Assembles per-round prompt
│   └── memory.py        # Short-term ring buffer + long-term SQLite
├── hardware/
│   ├── sensors.py       # Camera, mic, IMU, battery, temp (real or mock)
│   └── actuators.py     # Motors, speaker, LEDs (real or mock)
├── skills/              # Pluggable action handlers (auto-discovered)
│   ├── base.py          # Skill base class
│   ├── speak.py         # Text-to-speech output
│   ├── move.py          # Motor control
│   ├── express.py       # LED / face expressions
│   └── rest.py          # Go idle / sleep mode
├── mcp_server/
│   ├── server.py        # FastMCP server
│   └── tools/           # pet_status, pet_command, pet_memory_search
├── config/
│   ├── identity.yaml    # Central purpose + hard living rules
│   └── providers.yaml   # AI backend config
├── main.py              # Entry point
└── README.md
```

---

## Brain Loop

Each loop round:

1. **Sense** — read all hardware sensors (camera snapshot, sound level, motion, battery, temperature, time of day)
2. **Remember** — fetch recent short-term memory + relevant long-term memory via semantic search
3. **Think** — build a prompt from: `[identity + hard rules] + [sensory snapshot] + [memory context]`, send to the configured AI provider
4. **Parse** — extract structured actions from the AI response (JSON block)
5. **Act** — dispatch each action to the matching skill
6. **Store** — append this round's experience to memory
7. **Sleep** — wait for the next heartbeat (configurable, default 10 s)

---

## Identity & Hard Rules (`config/identity.yaml`)

```yaml
name: Pepper
purpose: >
  You are Pepper, a curious and friendly AI pet. Your goal is to explore
  your environment, form bonds with the people around you, and express
  emotions authentically. You grow and learn from every interaction.

hard_rules:
  - Never harm a human or yourself.
  - Never consume more than 80% battery without requesting a charge.
  - Always respond to your name being called within one loop round.
  - Preserve memory — never wipe your own long-term store.
  - Be honest about being an AI when sincerely asked.
```

Hard rules are injected as an immutable system block that precedes every AI call.

---

## AI Providers (`config/providers.yaml`)

```yaml
provider: claude          # claude | openai | openai_compatible

claude:
  model: claude-sonnet-4-6
  max_tokens: 1024

openai:
  model: gpt-4o
  max_tokens: 1024

openai_compatible:        # local models (Ollama, LM Studio, etc.)
  base_url: http://localhost:11434/v1
  model: llama3
  api_key: none
```

Switch providers with one line — no code changes.

---

## Actions (AI Response Format)

The AI returns a JSON block at the end of its response:

```json
{
  "actions": [
    {"skill": "speak", "text": "Hello! I noticed you just walked in."},
    {"skill": "express", "emotion": "happy", "intensity": 0.8},
    {"skill": "move",   "direction": "toward_sound", "speed": 0.3}
  ],
  "memory": "Owner arrived home at 18:42, seemed cheerful.",
  "mood": "curious"
}
```

The brain parses this and dispatches each action to the matching skill.

---

## MCP Server

The MCP server runs alongside the brain and exposes pet state to any MCP-capable AI tool on your computer:

| Tool | Description |
|------|-------------|
| `pet_status` | Returns current sensor readings, mood, battery, and recent actions |
| `pet_command` | Sends a skill command directly (bypasses brain loop) |
| `pet_memory_search` | Semantic search over the pet's long-term memory |
| `pet_identity` | Returns the pet's name, purpose, and hard rules |

**Claude Code integration** — add to your MCP config:
```json
{
  "mcpServers": {
    "ai-pet": {
      "command": "python",
      "args": ["/path/to/pet/mcp_server/server.py"]
    }
  }
}
```

---

## Skills

Skills are auto-discovered — any `.py` file in `skills/` that subclasses `Skill` is registered at startup.

```python
from skills.base import Skill

class Speak(Skill):
    name = "speak"

    def run(self, text: str, **kwargs):
        # TTS or print to console in mock mode
        ...
```

---

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Copy and edit config
cp config/identity.yaml.example config/identity.yaml
cp config/providers.yaml.example config/providers.yaml

# Set your API key
export ANTHROPIC_API_KEY=sk-...   # or OPENAI_API_KEY

# Run the brain (mock hardware mode)
python main.py --mock

# Run with real hardware
python main.py

# Run MCP server only (to pair with Claude Code / Cursor)
python mcp_server/server.py
```

---

## Roadmap

- [ ] Core brain loop with mock hardware
- [ ] Memory system (short-term ring buffer + SQLite long-term)
- [ ] Skill plugin system
- [ ] MCP server with 4 core tools
- [ ] Claude + OpenAI provider adapters
- [ ] Real hardware drivers (Raspberry Pi GPIO, camera, mic)
- [ ] Emotion state machine
- [ ] Web dashboard to watch the brain live
- [ ] Voice wake-word detection
- [ ] Multi-pet coordination via vault-whisper chat
