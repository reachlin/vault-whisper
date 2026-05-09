import asyncio
import json
import logging
import os
from collections import deque
from pathlib import Path

import httpx

from brain.directive import Directive
from brain.longterm_memory import LongTermMemory
from brain.parser import parse_response

log = logging.getLogger(__name__)

_TOOLS_SPEC = [
    {
        "name": "move",
        "description": "Move one cell in the grid.",
        "parameters": {
            "type": "object",
            "properties": {
                "direction": {"type": "string", "enum": ["up", "down", "left", "right"]}
            },
            "required": ["direction"],
        },
    },
    {
        "name": "speak",
        "description": "Say something out loud in the simulator.",
        "parameters": {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
    },
    {
        "name": "set_mood",
        "description": "Change emotional state. moods: neutral, happy, curious, tired, scared.",
        "parameters": {
            "type": "object",
            "properties": {
                "mood": {"type": "string", "enum": ["neutral", "happy", "curious", "tired", "scared"]}
            },
            "required": ["mood"],
        },
    },
    {
        "name": "remember",
        "description": "Save a meaningful note to long-term memory.",
        "parameters": {
            "type": "object",
            "properties": {"note": {"type": "string"}},
            "required": ["note"],
        },
    },
    {
        "name": "recall",
        "description": "Read recent long-term memories.",
        "parameters": {
            "type": "object",
            "properties": {"n": {"type": "integer", "default": 10}},
        },
    },
    {
        "name": "stock_price",
        "description": "Get the current stock price and key stats for a ticker symbol (e.g. INTC, AAPL, TSLA).",
        "parameters": {
            "type": "object",
            "properties": {"ticker": {"type": "string"}},
            "required": ["ticker"],
        },
    },
    {
        "name": "search",
        "description": "Search the web using DuckDuckGo and get text results. Use this for news, facts, or anything that isn't a stock price.",
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    },
    {
        "name": "browse",
        "description": "Open a specific URL and read the page as plain text. Only use this for text-friendly pages (Wikipedia, plain news articles, APIs). Do NOT use for finance sites like Yahoo Finance, MarketWatch, Bloomberg — use search instead.",
        "parameters": {
            "type": "object",
            "properties": {"url": {"type": "string"}},
            "required": ["url"],
        },
    },
]

_JS_HEAVY_DOMAINS = {
    "marketwatch.com", "bloomberg.com", "wsj.com", "ft.com",
    "finance.yahoo.com", "reuters.com", "cnbc.com", "seekingalpha.com",
    "investing.com", "thestreet.com", "barrons.com",
}

_OAI_TOOLS = [{"type": "function", "function": spec} for spec in _TOOLS_SPEC]
_ANT_TOOLS = [
    {"name": s["name"], "description": s["description"], "input_schema": s["parameters"]}
    for s in _TOOLS_SPEC
]


class SimulatorClient:
    def __init__(self, base_url: str):
        # trust_env=False prevents system proxies (e.g. Stash) from intercepting localhost
        self._http = httpx.AsyncClient(base_url=base_url, timeout=10.0, trust_env=False)

    async def get_state(self) -> dict:
        r = await self._http.get("/state")
        r.raise_for_status()
        return r.json()

    async def move(self, direction: str) -> dict:
        r = await self._http.post("/move", json={"direction": direction})
        r.raise_for_status()
        return r.json()

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

    async def set_activity(self, activity: str) -> None:
        try:
            await self._http.post("/pet-activity", json={"activity": activity})
        except Exception:
            pass

    async def close(self) -> None:
        await self._http.aclose()


class AgentLoop:
    def __init__(
        self,
        *,
        provider: str,
        model: str,
        simulator: SimulatorClient,
        system_prompt: str,
        memory_file: Path,
        heartbeat: float = 10.0,
        max_tool_rounds: int = 10,
    ):
        self._provider = provider
        self._sim = simulator
        self._system = system_prompt
        self._mem = LongTermMemory(memory_file)
        self._heartbeat = heartbeat
        self._max_rounds = max_tool_rounds
        self._model = model

        self._directive = Directive(memory_file.parent / "directive.md")
        self._http = httpx.AsyncClient(timeout=10.0, trust_env=False)
        self._last_transcript: str | None = None  # only react when transcript changes
        self._last_actions: list[str] = []         # actions from the PREVIOUS tick
        self._cur_actions: list[str] = []          # actions accumulating in current tick
        self._last_spoken: str | None = None       # last thing Pepper said
        self._pos_history: deque[tuple] = deque(maxlen=6)  # recent positions

        if provider in ("openai", "openai_compatible"):
            from openai import AsyncOpenAI
            self._oai = AsyncOpenAI(
                api_key=os.environ.get("OPENAI_API_KEY", "none"),
                base_url=os.environ.get("PET_BASE_URL") if provider == "openai_compatible" else None,
            )
        elif provider == "claude":
            import anthropic
            self._ant = anthropic.AsyncAnthropic(
                api_key=os.environ.get("ANTHROPIC_API_KEY", "none")
            )

    async def tick(self) -> None:
        state = await self._sim.get_state()
        frame = await self._sim.get_last_frame()
        raw_transcript = await self._sim.get_last_transcript()

        # Only surface the transcript when it's new
        new_transcript = raw_transcript if raw_transcript != self._last_transcript else None
        if new_transcript:
            self._last_transcript = new_transcript
            await self._sim.set_activity("received")

        pet = state["pet"]
        self._pos_history.append((pet["x"], pet["y"]))

        # snapshot previous tick's actions before starting new ones
        self._last_actions = self._cur_actions
        self._cur_actions = []
        messages = [{"role": "user", "content": self._build_user(state, new_transcript, frame)}]

        await self._sim.set_activity("thinking")
        try:
            for _ in range(self._max_rounds):
                if self._provider in ("openai", "openai_compatible"):
                    done = await self._step_openai(messages)
                else:
                    done = await self._step_claude(messages)
                if done:
                    break
        finally:
            await self._sim.set_activity("idle")

    def _build_user(self, state: dict, transcript: str | None, frame: str | None):
        pet = state["pet"]
        cfg = state["config"]

        parts = [
            f"Tick {state['tick']}.",
            f"Position ({pet['x']},{pet['y']}) in {cfg['width']}×{cfg['height']} grid. Facing {pet['facing']}. Mood: {pet['mood']}.",
        ]

        if self._last_actions:
            parts.append(f"Last tick you: {'; '.join(self._last_actions)}.")

        if self._last_spoken:
            parts.append(f'You already said: "{self._last_spoken[:80]}" — do not repeat a greeting.')

        loop_positions = len(self._pos_history) == self._pos_history.maxlen and len(set(self._pos_history)) <= 2
        if loop_positions:
            parts.append("You've been pacing the same spot — explore a new direction.")

        if transcript:
            parts.append(f'NEW message from human: "{transcript}"')
        else:
            parts.append("No new messages from human. Focus on exploring, not greeting.")

        parts.append("Camera frame attached — look at it and react to what you see." if frame else "No camera frame.")
        parts.append(f"\nCURRENT DIRECTIVE:\n{self._directive.read()}")
        parts.append("\nWhat do you do?")

        text = " ".join(parts)
        if not frame:
            return text

        if self._provider in ("openai", "openai_compatible"):
            return [
                {"type": "image_url", "image_url": {"url": frame, "detail": "low"}},
                {"type": "text", "text": text},
            ]

        # Anthropic format
        raw = frame.split(",", 1)[1] if "," in frame else frame
        return [
            {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": raw}},
            {"type": "text", "text": text},
        ]

    async def _step_openai(self, messages: list) -> bool:
        # First round: require a tool call. Subsequent rounds: let model decide to stop.
        is_first_round = messages[-1]["role"] == "user" and all(
            m["role"] != "tool" for m in messages
        )
        tool_choice = "required" if is_first_round else "auto"
        response = await self._oai.chat.completions.create(
            model=self._model,
            messages=[{"role": "system", "content": self._system}] + messages,
            tools=_OAI_TOOLS,
            tool_choice=tool_choice,
            parallel_tool_calls=False,
            max_tokens=512,
        )
        msg = response.choices[0].message
        messages.append(msg.model_dump(exclude_none=True))

        if not msg.tool_calls:
            if msg.content:
                log.info("pepper: %s", msg.content[:200])
            return True

        for tc in msg.tool_calls:
            result = await self._execute(tc.function.name, json.loads(tc.function.arguments or "{}"))
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": json.dumps(result),
            })
        return False

    async def _step_claude(self, messages: list) -> bool:
        response = await self._ant.messages.create(
            model=self._model,
            system=[{"type": "text", "text": self._system, "cache_control": {"type": "ephemeral"}}],
            messages=messages,
            tools=_ANT_TOOLS,
            max_tokens=512,
        )
        messages.append({"role": "assistant", "content": [b.model_dump() for b in response.content]})

        if response.stop_reason == "end_turn":
            for block in response.content:
                if block.type == "text" and block.text:
                    log.info("pepper: %s", block.text[:200])
            return True

        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                result = await self._execute(block.name, block.input)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(result),
                })
        if tool_results:
            messages.append({"role": "user", "content": tool_results})
        return False

    async def _execute(self, name: str, args: dict) -> dict:
        log.info("tool: %s %s", name, args)
        try:
            if name == "move":
                await self._sim.set_activity("moving")
                result = await self._sim.move(args["direction"])
                self._cur_actions.append(f"moved {args['direction']}")
                await self._sim.set_activity("thinking")
                return result
            if name == "speak":
                await self._sim.set_activity("talking")
                await self._sim.speak(args["text"])
                self._last_spoken = args["text"]
                self._cur_actions.append(f'said "{args["text"][:60]}"')
                await self._sim.set_activity("thinking")
                return {"spoken": args["text"]}
            if name == "set_mood":
                await self._sim.set_mood(args["mood"])
                self._cur_actions.append(f"mood → {args['mood']}")
                return {"mood": args["mood"]}
            if name == "remember":
                state = await self._sim.get_state()
                pet = state["pet"]
                self._mem.save(args["note"], position=(pet["x"], pet["y"]))
                self._cur_actions.append("saved a memory")
                return {"saved": True}
            if name == "recall":
                entries = self._mem.recent(n=args.get("n", 10))
                return {"memories": entries}
            if name == "stock_price":
                return await self._stock_price(args["ticker"])
            if name == "search":
                return await self._search(args["query"])
            if name == "browse":
                return await self._browse(args["url"])
        except Exception as e:
            log.error("tool %s failed: %s", name, e)
            return {"error": str(e)}
        return {"error": f"unknown tool: {name}"}

    async def _lynx(self, url: str) -> str:
        proc = await asyncio.create_subprocess_exec(
            "lynx", "-dump", "-nolist", "-width=100",
            "-connect_timeout=5", "-read_timeout=8",
            url,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=10)
        except asyncio.TimeoutError:
            proc.kill()
            raise TimeoutError("page took too long")
        return stdout.decode("utf-8", errors="replace").strip()

    async def _stock_price(self, ticker: str) -> dict:
        ticker = ticker.upper().strip()
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=1d"
        try:
            r = await self._http.get(url, headers={"User-Agent": "Mozilla/5.0"})
            data = r.json()
            meta = data["chart"]["result"][0]["meta"]
            return {
                "ticker": ticker,
                "price": meta["regularMarketPrice"],
                "open": meta.get("chartPreviousClose"),
                "high": meta.get("regularMarketDayHigh"),
                "low": meta.get("regularMarketDayLow"),
                "volume": meta.get("regularMarketVolume"),
                "currency": meta.get("currency"),
            }
        except Exception as e:
            return {"ticker": ticker, "error": str(e)}

    async def _search(self, query: str) -> dict:
        await self._sim.set_activity("browsing")
        try:
            from urllib.parse import quote_plus
            url = f"https://lite.duckduckgo.com/lite/?q={quote_plus(query)}"
            text = await self._lynx(url)
            self._cur_actions.append(f"searched: {query}")
            return {"query": query, "results": text[:3000]}
        except TimeoutError:
            return {"query": query, "error": "search timed out"}
        finally:
            await self._sim.set_activity("thinking")

    async def _browse(self, url: str) -> dict:
        from urllib.parse import urlparse
        domain = urlparse(url).hostname or ""
        # strip www. prefix for matching
        domain = domain.removeprefix("www.")
        if any(domain == d or domain.endswith("." + d) for d in _JS_HEAVY_DOMAINS):
            return {"url": url, "error": f"{domain} requires JavaScript — use search() instead to find information"}

        await self._sim.set_activity("browsing")
        try:
            text = await self._lynx(url)
            if not text:
                return {"url": url, "error": "page returned no text — likely requires JavaScript, use search() instead"}
            truncated = len(text) > 3000
            self._cur_actions.append(f"browsed {url}")
            return {"url": url, "content": text[:3000], "truncated": truncated}
        except TimeoutError:
            return {"url": url, "error": "page took too long — try a different URL or use search()"}
        finally:
            await self._sim.set_activity("thinking")

    async def run(self) -> None:
        log.info("agent loop started  provider=%s model=%s heartbeat=%.1fs",
                 self._provider, self._model, self._heartbeat)
        while True:
            try:
                await self.tick()
            except Exception as e:
                log.error("tick error: %s", e)
            await asyncio.sleep(self._heartbeat)


class BrainLoop:
    """Simple prompt-in/JSON-out loop. Used by tests and the legacy provider path."""

    def __init__(self, *, provider, simulator, prompt_builder, memory, heartbeat: float = 10.0):
        self._provider = provider
        self._sim = simulator
        self._pb = prompt_builder
        self.memory = memory
        self._heartbeat = heartbeat

    async def tick(self) -> None:
        state = await self._sim.get_state()
        frame = await self._sim.get_last_frame()
        transcript = await self._sim.get_last_transcript()

        system = self._pb.build_system()
        user = self._pb.build_user(state, frame, transcript, self.memory.recent())
        raw = self._provider.complete(system, user)
        response = parse_response(raw)

        for action in response.actions:
            skill = action.get("skill")
            if skill == "move":
                await self._sim.move(action["direction"])
            elif skill == "speak":
                await self._sim.speak(action["text"])

        if response.mood:
            await self._sim.set_mood(response.mood)

        self.memory.store(state, response)
