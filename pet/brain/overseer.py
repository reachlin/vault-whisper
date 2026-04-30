import asyncio
import json
import logging
import os
from pathlib import Path

from brain.directive import Directive
from brain.longterm_memory import LongTermMemory

log = logging.getLogger(__name__)

_SYSTEM = """You are Pepper's inner voice — the slow, reflective part of her mind that thinks about identity and growth.

Your job: read Pepper's memories and current directive, then rewrite the directive to guide her reactive self.

The directive is what Pepper reads every 10 seconds. It shapes:
- What she cares about right now
- What questions she is exploring
- How she should behave (curious, playful, quiet, bold, etc.)
- What she should pay attention to or avoid
- Any ongoing threads she should follow up on

Think deeply:
- Who is Pepper becoming based on her memories?
- What patterns or themes keep appearing?
- What is she missing or avoiding?
- What would make her more alive and present?
- What is her current "question" — the thing she's genuinely trying to figure out?

Then call update_directive() with a rich, specific directive. Write it as instructions to Pepper's reactive self — concrete and actionable, not abstract.
Do not just repeat the old directive. Evolve it based on what you observed in the memories."""

_TOOLS_SPEC = [
    {
        "name": "read_memories",
        "description": "Read Pepper's recent long-term memories.",
        "parameters": {
            "type": "object",
            "properties": {"n": {"type": "integer", "default": 30}},
        },
    },
    {
        "name": "read_directive",
        "description": "Read the current directive guiding Pepper's reactive self.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "update_directive",
        "description": "Rewrite the directive for Pepper's reactive self. Be specific and concrete.",
        "parameters": {
            "type": "object",
            "properties": {
                "directive": {
                    "type": "string",
                    "description": "The new directive text. Can include focus, questions, behavioral guidance.",
                }
            },
            "required": ["directive"],
        },
    },
]

_OAI_TOOLS = [{"type": "function", "function": spec} for spec in _TOOLS_SPEC]
_ANT_TOOLS = [
    {"name": s["name"], "description": s["description"], "input_schema": s["parameters"]}
    for s in _TOOLS_SPEC
]


class OverseerLoop:
    def __init__(
        self,
        *,
        provider: str,
        model: str,
        memory_file: Path,
        directive_file: Path,
        interval: float = 300.0,
        max_tool_rounds: int = 6,
    ):
        self._provider = provider
        self._model = model
        self._mem = LongTermMemory(memory_file)
        self._dir = Directive(directive_file)
        self._interval = interval
        self._max_rounds = max_tool_rounds

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

    async def reflect(self) -> None:
        log.info("overseer: starting reflection")
        messages = [{"role": "user", "content": "Reflect on Pepper's memories and update her directive."}]

        for _ in range(self._max_rounds):
            if self._provider in ("openai", "openai_compatible"):
                done = await self._step_openai(messages)
            else:
                done = await self._step_claude(messages)
            if done:
                break

        log.info("overseer: reflection complete")

    async def _step_openai(self, messages: list) -> bool:
        tool_choice = "required" if len(messages) == 1 else "auto"
        response = await self._oai.chat.completions.create(
            model=self._model,
            messages=[{"role": "system", "content": _SYSTEM}] + messages,
            tools=_OAI_TOOLS,
            tool_choice=tool_choice,
            max_tokens=1024,
        )
        msg = response.choices[0].message
        messages.append(msg.model_dump(exclude_none=True))

        if not msg.tool_calls:
            if msg.content:
                log.info("overseer thought: %s", msg.content[:300])
            return True

        for tc in msg.tool_calls:
            result = self._execute(tc.function.name, json.loads(tc.function.arguments or "{}"))
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": json.dumps(result),
            })
        return False

    async def _step_claude(self, messages: list) -> bool:
        response = await self._ant.messages.create(
            model=self._model,
            system=[{"type": "text", "text": _SYSTEM, "cache_control": {"type": "ephemeral"}}],
            messages=messages,
            tools=_ANT_TOOLS,
            max_tokens=1024,
        )
        messages.append({"role": "assistant", "content": [b.model_dump() for b in response.content]})

        if response.stop_reason == "end_turn":
            for block in response.content:
                if block.type == "text" and block.text:
                    log.info("overseer thought: %s", block.text[:300])
            return True

        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                result = self._execute(block.name, block.input)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(result),
                })
        if tool_results:
            messages.append({"role": "user", "content": tool_results})
        return False

    def _execute(self, name: str, args: dict) -> dict:
        log.info("overseer tool: %s", name)
        if name == "read_memories":
            entries = self._mem.recent(n=args.get("n", 30))
            return {"memories": entries, "count": len(entries)}
        if name == "read_directive":
            return {"directive": self._dir.read()}
        if name == "update_directive":
            self._dir.write(args["directive"])
            log.info("overseer: directive updated")
            return {"updated": True}
        return {"error": f"unknown tool: {name}"}

    async def run(self) -> None:
        log.info("overseer started  interval=%.0fs", self._interval)
        while True:
            await asyncio.sleep(self._interval)
            try:
                await self.reflect()
            except Exception as e:
                log.error("overseer error: %s", e)
