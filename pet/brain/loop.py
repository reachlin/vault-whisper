import asyncio
import logging

import httpx

from brain.memory import ShortTermMemory
from brain.parser import BrainResponse, parse_response
from brain.prompt import PromptBuilder
from brain.providers.base import Provider

log = logging.getLogger(__name__)


class SimulatorClient:
    def __init__(self, base_url: str):
        self._http = httpx.AsyncClient(base_url=base_url, timeout=10.0)

    async def get_state(self) -> dict:
        r = await self._http.get("/state")
        r.raise_for_status()
        return r.json()

    async def move(self, direction: str) -> None:
        await self._http.post("/move", json={"direction": direction})

    async def speak(self, text: str) -> None:
        await self._http.post("/speak", json={"text": text})

    async def set_mood(self, mood: str) -> None:
        await self._http.post("/mood", json={"mood": mood})

    async def get_last_frame(self) -> str | None:
        r = await self._http.get("/hardware/last-frame")
        return r.json().get("frame")

    async def get_last_transcript(self) -> str | None:
        r = await self._http.get("/hardware/last-transcript")
        return r.json().get("transcript")

    async def close(self) -> None:
        await self._http.aclose()


class BrainLoop:
    def __init__(
        self,
        provider: Provider,
        simulator: SimulatorClient,
        prompt_builder: PromptBuilder,
        memory: ShortTermMemory,
        heartbeat: float = 10.0,
    ):
        self.provider = provider
        self.simulator = simulator
        self.prompt = prompt_builder
        self.memory = memory
        self.heartbeat = heartbeat

    async def tick(self) -> BrainResponse:
        state = await self.simulator.get_state()
        frame = await self.simulator.get_last_frame()
        transcript = await self.simulator.get_last_transcript()

        system = self.prompt.build_system()
        user = self.prompt.build_user(state, frame, transcript, self.memory.recent())

        raw = self.provider.complete(system, user)
        response = parse_response(raw)

        await self._act(response)
        self.memory.store(state, response)
        return response

    async def _act(self, response: BrainResponse) -> None:
        if response.mood:
            await self.simulator.set_mood(response.mood)
        for action in response.actions:
            skill = action.get("skill")
            if skill == "move":
                await self.simulator.move(action["direction"])
            elif skill == "speak":
                await self.simulator.speak(action["text"])

    async def run(self) -> None:
        log.info("brain loop started  heartbeat=%.1fs", self.heartbeat)
        while True:
            try:
                result = await self.tick()
                log.info("tick done  actions=%d mood=%s memory=%s",
                         len(result.actions), result.mood, result.memory)
            except Exception as exc:
                log.error("tick error: %s", exc)
            await asyncio.sleep(self.heartbeat)
