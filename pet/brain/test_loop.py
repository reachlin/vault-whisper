import pytest
from brain.loop import BrainLoop
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
