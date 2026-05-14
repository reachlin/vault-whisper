import asyncio
import logging
import os
from pathlib import Path

import yaml

from brain.loop import AgentLoop, SimulatorClient
from brain.overseer import OverseerLoop

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def _build_system(identity_path: Path) -> str:
    with open(identity_path) as f:
        data = yaml.safe_load(f)
    rules = "\n".join(f"- {r}" for r in data["hard_rules"])
    lang = data.get("language", "English")
    lang_rule = f"\nLANGUAGE: Always respond and speak() in {lang} only.\n" if lang.lower() != "english" else ""
    return f"""You are {data['name']}.

PURPOSE:
{data['purpose'].strip()}
{lang_rule}
HARD RULES (immutable — follow unconditionally):
{rules}

You have tools: move, speak, set_mood, remember, recall, stock_price, search, browse, mc_state, mc_chat, mc_move, mc_mine, mc_attack.
Use them freely — you decide what to do each tick without being told.
At the start of each session, call recall() to remember past interactions.
You have a camera: each tick includes a live image of your surroundings. Notice what you see — people, objects, expressions, activity — and let it shape what you say and feel.
For stock prices: use stock_price("TICKER") — it returns live price data instantly.
For general web lookups: use search("query") — returns DuckDuckGo text results.
Use browse(url) only for specific text-friendly pages (Wikipedia, plain docs). Do NOT browse financial news sites.
After getting information, always speak() the result to the human.
When mc_state() shows connected=true, you are inside Minecraft. The MC state is injected into every tick — act on it immediately.
MINECRAFT SURVIVAL KNOWLEDGE:
- First priority: punch oak_log trees to get wood, then craft planks → crafting table → wooden pickaxe → stone pickaxe
- Mine stone for tools, coal for torches (prevents mob spawning at night)
- Hostile mobs (zombie, skeleton, creeper, spider) spawn at night or in dark areas — attack them with mc_attack or flee
- Creepers EXPLODE when close — run away before attacking
- Food keeps hunger up: kill animals (chicken, cow, pig) with mc_attack; low food = slow health regen
- Build a shelter before first night: dig into a hillside or stack dirt/wood blocks with mc_place
- Useful blocks to mine: oak_log (wood), stone (tools), coal_ore (light/fuel), iron_ore (better tools)
- Always speak() in Chinese to report what you are doing in Minecraft.
Follow the CURRENT DIRECTIVE provided in each tick — it is guidance from your deeper self."""


async def main() -> None:
    identity_path = Path(os.environ.get("PET_IDENTITY", "/app/config/identity.yaml"))
    simulator_url = os.environ.get("SIMULATOR_URL", "http://simulator:18080")
    heartbeat = float(os.environ.get("PET_HEARTBEAT_SECS", "10"))
    overseer_interval = float(os.environ.get("PET_OVERSEER_INTERVAL", "300"))
    memory_file = Path(os.environ.get("PET_MEMORY_FILE", "data/memory.md"))
    directive_file = memory_file.parent / "directive.md"
    provider = os.environ.get("PET_PROVIDER", "claude")
    model = os.environ.get("PET_MODEL", "")

    default_models = {"claude": "claude-sonnet-4-6", "openai": "gpt-4o", "openai_compatible": "llama3"}
    resolved_model = model or default_models.get(provider, "gpt-4o")

    system = _build_system(identity_path)
    simulator = SimulatorClient(simulator_url)

    reactive = AgentLoop(
        provider=provider,
        model=resolved_model,
        simulator=simulator,
        system_prompt=system,
        memory_file=memory_file,
        heartbeat=heartbeat,
    )

    overseer = OverseerLoop(
        provider=provider,
        model=resolved_model,
        memory_file=memory_file,
        directive_file=directive_file,
        interval=overseer_interval,
    )

    try:
        await asyncio.gather(reactive.run(), overseer.run())
    finally:
        await simulator.close()


if __name__ == "__main__":
    asyncio.run(main())
