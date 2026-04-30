import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from brain.loop import AgentLoop, BrainLoop
from brain.prompt import PromptBuilder, PetIdentity
from brain.memory import ShortTermMemory
from brain.providers.base import Provider


class MockProvider(Provider):
    def __init__(self, response: str = '```json\n{"actions": [], "mood": "neutral", "memory": "idle"}\n```'):
        self.response = response
        self.calls: list[tuple[str, str]] = []

    def complete(self, system: str, user: str) -> str:
        self.calls.append((system, user))
        return self.response


class MockSimulatorClient:
    def __init__(self):
        self.moves: list[str] = []
        self.speeches: list[str] = []
        self.moods: list[str] = []
        self._state = {
            "config": {"width": 20, "height": 15},
            "pet": {"x": 10, "y": 7, "facing": "right", "mood": "neutral"},
            "tick": 0,
        }

    async def get_state(self): return self._state
    async def move(self, direction: str): self.moves.append(direction)
    async def speak(self, text: str): self.speeches.append(text)
    async def set_mood(self, mood: str): self.moods.append(mood)
    async def get_last_frame(self): return None
    async def get_last_transcript(self): return None
    async def set_activity(self, activity: str): pass


def make_loop(provider_response=None):
    identity = PetIdentity(name="Pepper", purpose="A curious pet.", hard_rules=["Be safe."])
    provider = MockProvider(provider_response) if provider_response else MockProvider()
    sim = MockSimulatorClient()
    loop = BrainLoop(
        provider=provider,
        simulator=sim,
        prompt_builder=PromptBuilder(identity),
        memory=ShortTermMemory(),
        heartbeat=0,
    )
    return loop, provider, sim


@pytest.mark.asyncio
async def test_tick_calls_provider_once():
    loop, provider, _ = make_loop()
    await loop.tick()
    assert len(provider.calls) == 1


@pytest.mark.asyncio
async def test_tick_system_contains_identity():
    loop, provider, _ = make_loop()
    await loop.tick()
    system, _ = provider.calls[0]
    assert "Pepper" in system


@pytest.mark.asyncio
async def test_tick_dispatches_move():
    loop, _, sim = make_loop('```json\n{"actions": [{"skill": "move", "direction": "up"}], "mood": "curious"}\n```')
    await loop.tick()
    assert sim.moves == ["up"]


@pytest.mark.asyncio
async def test_tick_dispatches_speak():
    loop, _, sim = make_loop('```json\n{"actions": [{"skill": "speak", "text": "hello"}], "mood": "happy"}\n```')
    await loop.tick()
    assert sim.speeches == ["hello"]


@pytest.mark.asyncio
async def test_tick_dispatches_mood():
    loop, _, sim = make_loop('```json\n{"actions": [], "mood": "happy"}\n```')
    await loop.tick()
    assert sim.moods == ["happy"]


@pytest.mark.asyncio
async def test_tick_dispatches_multiple_actions():
    resp = '```json\n{"actions": [{"skill": "move", "direction": "left"}, {"skill": "speak", "text": "hi"}], "mood": "curious"}\n```'
    loop, _, sim = make_loop(resp)
    await loop.tick()
    assert sim.moves == ["left"]
    assert sim.speeches == ["hi"]


@pytest.mark.asyncio
async def test_tick_stores_to_memory():
    loop, _, _ = make_loop()
    await loop.tick()
    assert len(loop.memory) == 1


@pytest.mark.asyncio
async def test_tick_accumulates_memory_across_ticks():
    loop, _, _ = make_loop()
    await loop.tick()
    await loop.tick()
    assert len(loop.memory) == 2


@pytest.mark.asyncio
async def test_tick_handles_empty_actions():
    loop, _, sim = make_loop('```json\n{"actions": []}\n```')
    await loop.tick()
    assert sim.moves == []
    assert sim.speeches == []


@pytest.mark.asyncio
async def test_tick_handles_no_json_in_response():
    loop, _, sim = make_loop("I have no idea what to do.")
    await loop.tick()
    assert sim.moves == []
    assert sim.speeches == []


# --- AgentLoop browse tests ---

def make_agent_loop():
    from pathlib import Path
    import tempfile
    tmp = Path(tempfile.mkdtemp()) / "memory.md"
    sim = MockSimulatorClient()
    return AgentLoop(
        provider="openai",
        model="gpt-4o",
        simulator=sim,
        system_prompt="You are Pepper.",
        memory_file=tmp,
        heartbeat=0,
    ), sim


@pytest.mark.asyncio
async def test_browse_returns_content():
    loop, _ = make_agent_loop()
    fake_proc = AsyncMock()
    fake_proc.communicate = AsyncMock(return_value=(b"Hello from the web!", b""))
    with patch("asyncio.create_subprocess_exec", return_value=fake_proc):
        result = await loop._browse("http://example.com")
    assert result["url"] == "http://example.com"
    assert "Hello from the web!" in result["content"]
    assert result["truncated"] is False


@pytest.mark.asyncio
async def test_browse_truncates_long_content():
    loop, _ = make_agent_loop()
    long_text = b"x" * 5000
    fake_proc = AsyncMock()
    fake_proc.communicate = AsyncMock(return_value=(long_text, b""))
    with patch("asyncio.create_subprocess_exec", return_value=fake_proc):
        result = await loop._browse("http://example.com")
    assert len(result["content"]) == 3000
    assert result["truncated"] is True


@pytest.mark.asyncio
async def test_browse_records_action():
    loop, _ = make_agent_loop()
    fake_proc = AsyncMock()
    fake_proc.communicate = AsyncMock(return_value=(b"content", b""))
    with patch("asyncio.create_subprocess_exec", return_value=fake_proc):
        await loop._browse("http://example.com")
    assert any("browsed" in a for a in loop._cur_actions)


@pytest.mark.asyncio
async def test_browse_blocks_js_heavy_domains():
    loop, _ = make_agent_loop()
    for url in ["https://marketwatch.com/q", "https://www.bloomberg.com/q", "https://finance.yahoo.com/quote/INTC"]:
        result = await loop._browse(url)
        assert "error" in result
        assert "search()" in result["error"]


@pytest.mark.asyncio
async def test_search_returns_results():
    loop, _ = make_agent_loop()
    fake_proc = AsyncMock()
    fake_proc.communicate = AsyncMock(return_value=(b"1. Result one\n2. Result two", b""))
    with patch("asyncio.create_subprocess_exec", return_value=fake_proc):
        result = await loop._search("INTC stock price")
    assert result["query"] == "INTC stock price"
    assert "Result one" in result["results"]


@pytest.mark.asyncio
async def test_search_records_action():
    loop, _ = make_agent_loop()
    fake_proc = AsyncMock()
    fake_proc.communicate = AsyncMock(return_value=(b"results", b""))
    with patch("asyncio.create_subprocess_exec", return_value=fake_proc):
        await loop._search("test query")
    assert any("searched" in a for a in loop._cur_actions)


@pytest.mark.asyncio
async def test_stock_price_returns_data():
    loop, _ = make_agent_loop()
    fake_response = AsyncMock()
    fake_response.json = lambda: {
        "chart": {"result": [{"meta": {
            "regularMarketPrice": 87.94,
            "chartPreviousClose": 84.55,
            "regularMarketDayHigh": 88.14,
            "regularMarketDayLow": 86.11,
            "regularMarketVolume": 14000000,
            "currency": "USD",
        }}]}
    }
    with patch.object(loop._http, "get", return_value=fake_response):
        result = await loop._stock_price("INTC")
    assert result["ticker"] == "INTC"
    assert result["price"] == 87.94
    assert result["currency"] == "USD"
