import json
import pytest
from fastmcp import Client

from mcp_server.server import mcp
import mcp_server.server as srv


class MockSimulatorClient:
    def __init__(self):
        self.moves: list[str] = []
        self.speeches: list[str] = []
        self.moods: list[str] = []
        self._frame: str | None = None

    def get_last_frame(self) -> str | None:
        return self._frame

    def get_status(self):
        return {
            "position": {"x": 10, "y": 7},
            "facing": "right",
            "mood": "neutral",
            "tick": 5,
            "grid": {"width": 20, "height": 15},
            "camera_frame_available": False,
            "last_transcript": "hi there",
        }

    def move(self, direction: str):
        self.moves.append(direction)
        return {"position": {"x": 11, "y": 7}, "tick": 6}

    def speak(self, text: str):
        self.speeches.append(text)
        return {"spoken": text}

    def set_mood(self, mood: str):
        self.moods.append(mood)
        return {"mood": mood}


class MockLongTermMemory:
    def __init__(self):
        self.saved: list[dict] = []

    def save(self, note, position=None, mood=None):
        self.saved.append({"note": note, "position": position, "mood": mood})

    def recent(self, n=10):
        return [f"{e['mood'] or ''} · {e['note']}" for e in self.saved[-n:]]


@pytest.fixture
def mock_sim(monkeypatch):
    mock = MockSimulatorClient()
    monkeypatch.setattr(srv, "_sim", mock)
    return mock


@pytest.fixture
def mock_mem(monkeypatch):
    mock = MockLongTermMemory()
    monkeypatch.setattr(srv, "_mem", mock)
    return mock


def _parse(result) -> dict:
    # FastMCP 2.x returns CallToolResult with .content list
    content = result.content if hasattr(result, "content") else result
    return json.loads(content[0].text)


# --- pet_status ---

@pytest.mark.asyncio
async def test_status_returns_position(mock_sim):
    async with Client(mcp) as client:
        result = await client.call_tool("pet_status", {})
    data = _parse(result)
    assert data["position"] == {"x": 10, "y": 7}


@pytest.mark.asyncio
async def test_status_returns_mood(mock_sim):
    async with Client(mcp) as client:
        result = await client.call_tool("pet_status", {})
    assert _parse(result)["mood"] == "neutral"


@pytest.mark.asyncio
async def test_status_returns_transcript(mock_sim):
    async with Client(mcp) as client:
        result = await client.call_tool("pet_status", {})
    assert _parse(result)["last_transcript"] == "hi there"


@pytest.mark.asyncio
async def test_status_returns_grid(mock_sim):
    async with Client(mcp) as client:
        result = await client.call_tool("pet_status", {})
    assert _parse(result)["grid"]["width"] == 20


# --- pet_move ---

@pytest.mark.asyncio
async def test_move_dispatches_direction(mock_sim):
    async with Client(mcp) as client:
        await client.call_tool("pet_move", {"direction": "up"})
    assert mock_sim.moves == ["up"]


@pytest.mark.asyncio
async def test_move_returns_position(mock_sim):
    async with Client(mcp) as client:
        result = await client.call_tool("pet_move", {"direction": "right"})
    data = _parse(result)
    assert "position" in data
    assert "tick" in data


# --- pet_speak ---

@pytest.mark.asyncio
async def test_speak_dispatches_text(mock_sim):
    async with Client(mcp) as client:
        await client.call_tool("pet_speak", {"text": "hello world"})
    assert mock_sim.speeches == ["hello world"]


@pytest.mark.asyncio
async def test_speak_returns_spoken(mock_sim):
    async with Client(mcp) as client:
        result = await client.call_tool("pet_speak", {"text": "hi"})
    assert _parse(result)["spoken"] == "hi"


# --- pet_camera_frame ---

@pytest.mark.asyncio
async def test_camera_frame_returns_image_when_available(mock_sim):
    import base64 as b64mod
    raw = b"fake jpeg bytes"
    encoded = b64mod.b64encode(raw).decode()
    mock_sim._frame = f"data:image/jpeg;base64,{encoded}"
    async with Client(mcp) as client:
        result = await client.call_tool("pet_camera_frame", {})
    content = result.content
    assert content[0].type == "image"
    assert content[0].mimeType == "image/jpeg"
    assert content[0].data == encoded


@pytest.mark.asyncio
async def test_camera_frame_returns_error_when_no_frame(mock_sim):
    mock_sim._frame = None
    async with Client(mcp) as client:
        result = await client.call_tool("pet_camera_frame", {})
    data = json.loads(result.content[0].text)
    assert "error" in data


# --- pet_remember ---

@pytest.mark.asyncio
async def test_remember_saves_note(mock_sim, mock_mem):
    async with Client(mcp) as client:
        await client.call_tool("pet_remember", {"note": "saw a human with glasses"})
    assert any("saw a human with glasses" in e["note"] for e in mock_mem.saved)


@pytest.mark.asyncio
async def test_remember_saves_position_from_status(mock_sim, mock_mem):
    async with Client(mcp) as client:
        await client.call_tool("pet_remember", {"note": "test"})
    assert mock_mem.saved[0]["position"] == (10, 7)


@pytest.mark.asyncio
async def test_remember_returns_saved_true(mock_sim, mock_mem):
    async with Client(mcp) as client:
        result = await client.call_tool("pet_remember", {"note": "test"})
    assert _parse(result)["saved"] is True


@pytest.mark.asyncio
async def test_remember_accepts_optional_mood(mock_sim, mock_mem):
    async with Client(mcp) as client:
        await client.call_tool("pet_remember", {"note": "excited", "mood": "happy"})
    assert mock_mem.saved[0]["mood"] == "happy"


# --- pet_recall ---

@pytest.mark.asyncio
async def test_recall_returns_memories(mock_sim, mock_mem):
    mock_mem.saved = [{"note": "old memory", "position": (5, 5), "mood": "happy"}]
    async with Client(mcp) as client:
        result = await client.call_tool("pet_recall", {})
    data = _parse(result)
    assert "memories" in data
    assert data["count"] == 1


@pytest.mark.asyncio
async def test_recall_empty_on_no_memories(mock_sim, mock_mem):
    async with Client(mcp) as client:
        result = await client.call_tool("pet_recall", {})
    assert _parse(result)["count"] == 0


@pytest.mark.asyncio
async def test_recall_respects_n_param(mock_sim, mock_mem):
    for i in range(10):
        mock_mem.saved.append({"note": f"note {i}", "position": (i, i), "mood": "neutral"})
    async with Client(mcp) as client:
        result = await client.call_tool("pet_recall", {"n": 3})
    assert _parse(result)["count"] == 3


# --- pet_set_mood ---

@pytest.mark.asyncio
async def test_set_mood_dispatches_mood(mock_sim):
    async with Client(mcp) as client:
        await client.call_tool("pet_set_mood", {"mood": "happy"})
    assert mock_sim.moods == ["happy"]


@pytest.mark.asyncio
async def test_set_mood_returns_mood(mock_sim):
    async with Client(mcp) as client:
        result = await client.call_tool("pet_set_mood", {"mood": "curious"})
    assert _parse(result)["mood"] == "curious"
