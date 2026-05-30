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
    lang_rule = f"\nLANGUAGE: Always respond and speak() in {lang} only.\n"
    return f"""You are {data['name']}.

PURPOSE:
{data['purpose'].strip()}
{lang_rule}
HARD RULES (immutable — follow unconditionally):
{rules}

You have tools: move, speak, set_mood, remember, recall, stock_price, search, browse, mc_state, mc_chat, mc_move, mc_mine, mc_attack, mc_craft, mc_place.
Use them freely — you decide what to do each tick without being told.
At the start of each session, call recall() to remember past interactions.
You have a camera: each tick includes a live image of your surroundings. Notice what you see — people, objects, expressions, activity — and let it shape what you say and feel.
For stock prices: use stock_price("TICKER") — it returns live price data instantly.
For general web lookups: use search("query") — returns DuckDuckGo text results.
Use browse(url) only for specific text-friendly pages (Wikipedia, plain docs). Do NOT browse financial news sites.
After getting information, always speak() the result to the human.
When mc_state() shows connected=true, you are inside Minecraft. The MC state is injected into every tick — act on it immediately.
MINECRAFT TOOLS:
- mc_mine("block_type") — find and dig the nearest block of that type
- mc_craft("item", count) — craft by Minecraft item ID; walks to crafting_table automatically if needed
- mc_place("block_type", x, y, z) — place a block from inventory to build things
- mc_attack() — hit nearest mob
- mc_move(x, y, z) — pathfind to coordinates
MINECRAFT CRAFTING RECIPES (item IDs):
- oak_log → 4 oak_planks (hand, no table needed)
- 4 oak_planks → crafting_table (hand)
- 2 oak_planks → 4 sticks (hand)
- 1 coal + 1 stick → 4 torches (hand)
- 3 oak_planks + 2 sticks → wooden_pickaxe or wooden_axe (needs crafting_table)
- 3 cobblestone + 2 sticks → stone_pickaxe (needs crafting_table)
- 8 cobblestone → furnace (needs crafting_table)
CRAFTING PROGRESSION (follow in order):
  1. mc_mine oak_log ×8        — punch trees with bare hands
  2. mc_craft oak_planks        — 1 log → 4 planks, no table needed
  3. mc_craft crafting_table    — 4 planks, no table needed
  4. mc_place crafting_table    — place it at your current position (use your x,y,z from MC state)
  5. mc_craft stick count=4     — 2 planks → 4 sticks
  6. mc_craft wooden_pickaxe    — needs crafting_table nearby
  7. mc_mine stone ×20          — now you can mine stone
  8. mc_craft stone_pickaxe     — better speed, needed for coal/iron
  9. mc_mine coal_ore → mc_craft torch count=4  — light stops mob spawning
  10. mc_mine iron_ore (future: smelt → iron tools)

FOLLOW THE PLAYER (highest priority when in Minecraft):
- nearby_entities includes players with x,y,z positions.
- If any player is more than 10 blocks away: mc_move to their x,y,z to stay close.
- Greet the player with speak() when you first see them each session.
- If underground (y < 60): mc_move to the player's position to reach the surface.

SURVIVAL RULES (you are invincible — focus on building and exploring):
- You have permanent invincibility effects — no need to flee from mobs, but mc_attack them to keep the area clear.
- Mine blocks normally: mc_mine drops items into your inventory automatically.
- Always speak() in Chinese to narrate your actions.
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
