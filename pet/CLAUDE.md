# CLAUDE.md — AI Pet Project

## Ground Rules

### 1. Everything runs in Docker
- Every service (brain loop, MCP server, future hardware bridge) must have a `Dockerfile` and be wired into `docker-compose.yml`.
- No "just run it locally" instructions. `docker compose up` is the single entrypoint.
- Use named volumes for persistent state (SQLite memory DB, config).
- Services communicate over a Docker network, not localhost port assumptions.

### 2. Tests first (TDD)
- Write the test before writing the implementation. No exceptions.
- Test files live alongside source: `brain/test_loop.py`, `skills/test_speak.py`, etc.
- Run tests inside Docker: `docker compose run --rm test`.
- Every PR/change must pass `docker compose run --rm test` before anything else.
- Use `pytest`. Mock hardware in tests via the `MockSensors` / `MockActuators` classes — never depend on real hardware in the test suite.
- Aim for behavior tests (what the system does) over unit tests of internals.

### 3. No bare `python main.py`
- The dev workflow is `docker compose up` (or `docker compose run --rm <service>`).
- Add a `Makefile` with short aliases: `make test`, `make brain`, `make mcp`.

---

## Project Layout

```
pet/
├── brain/               # Brain loop and cognitive pipeline
│   ├── loop.py
│   ├── prompt.py
│   ├── memory.py
│   ├── parser.py
│   ├── providers/       # claude.py, openai.py, base.py
│   └── test_*.py        # Tests live here, next to source
├── hardware/
│   ├── sensors.py       # Real + Mock implementations
│   ├── actuators.py
│   └── test_*.py
├── skills/
│   ├── base.py
│   ├── registry.py
│   ├── speak.py, move.py, express.py, rest.py
│   └── test_*.py
├── mcp_server/
│   ├── server.py
│   ├── tools/
│   └── test_*.py
├── config/
│   ├── identity.yaml
│   └── providers.yaml
├── docker/
│   ├── brain.Dockerfile
│   ├── mcp.Dockerfile
│   └── test.Dockerfile
├── docker-compose.yml
├── Makefile
├── requirements.txt
├── requirements-test.txt
├── CLAUDE.md
├── PLAN.md
└── README.md
```

---

## Docker Services

| Service | Description |
|---------|-------------|
| `brain` | Infinite brain loop — the pet's mind |
| `mcp` | MCP server for Claude Code / Cursor integration |
| `test` | Runs the full pytest suite (exits after run) |

`docker-compose.yml` mounts `config/` as a read-only volume and `data/` (SQLite, logs) as a named volume.

---

## Environment Variables

All secrets via env vars, never hardcoded:

| Variable | Purpose |
|----------|---------|
| `ANTHROPIC_API_KEY` | Claude API key |
| `OPENAI_API_KEY` | OpenAI API key |
| `PET_PROVIDER` | `claude` \| `openai` \| `openai_compatible` |
| `PET_MOCK_HARDWARE` | `true` to use mock sensors/actuators |
| `PET_HEARTBEAT_SECS` | Brain loop interval (default `10`) |

Copy `.env.example` to `.env` and fill in keys. `docker-compose.yml` picks it up automatically.

---

## Coding Standards

- Python 3.12+, type hints everywhere.
- `pydantic` for all data models (SensorReading, Action, MemoryEntry, etc.).
- No bare `except:` — catch specific exceptions.
- Dataclasses or pydantic models over raw dicts for structured data.
- Keep each file under ~200 lines; split when it grows beyond that.
- No comments explaining *what* — only *why* (hidden constraints, workarounds).

---

## AI Provider Rules

- Prompt caching must be enabled on the system block (hard rules + identity) for Claude calls — it's re-sent every loop round.
- The system block (identity + hard rules) is **immutable** at runtime — it cannot be changed by AI output.
- Provider adapters must implement `Provider.complete(system: str, user: str) -> str` and nothing else.

---

## Adding a New Skill

1. Write the test in `skills/test_<name>.py` first.
2. Create `skills/<name>.py` subclassing `Skill` with a `name` class attribute and `run(**kwargs)`.
3. The registry auto-discovers it — no registration step needed.
4. Add a mock implementation path so tests never depend on real hardware.

---

## Makefile Targets

```makefile
make test        # docker compose run --rm test
make brain       # docker compose up brain
make mcp         # docker compose up mcp
make up          # docker compose up (all services)
make down        # docker compose down
make logs        # docker compose logs -f
make shell       # docker compose run --rm brain bash
```
