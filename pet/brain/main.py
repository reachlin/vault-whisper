import asyncio
import logging
import os
from pathlib import Path

import yaml

from brain.loop import BrainLoop, SimulatorClient
from brain.memory import ShortTermMemory
from brain.prompt import PetIdentity, PromptBuilder

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def _load_identity(path: Path) -> PetIdentity:
    with open(path) as f:
        data = yaml.safe_load(f)
    return PetIdentity(name=data["name"], purpose=data["purpose"], hard_rules=data["hard_rules"])


def _make_provider():
    name = os.environ.get("PET_PROVIDER", "claude")
    model = os.environ.get("PET_MODEL", "")
    if name == "claude":
        from brain.providers.claude import ClaudeProvider
        return ClaudeProvider(model=model or "claude-sonnet-4-6")
    if name == "openai":
        from brain.providers.openai import OpenAIProvider
        return OpenAIProvider(model=model or "gpt-4o")
    if name == "openai_compatible":
        from brain.providers.openai import OpenAIProvider
        return OpenAIProvider(
            model=model or "llama3",
            base_url=os.environ.get("PET_BASE_URL", "http://localhost:11434/v1"),
        )
    raise ValueError(f"Unknown PET_PROVIDER: {name}")


async def main() -> None:
    identity_path = Path(os.environ.get("PET_IDENTITY", "/app/config/identity.yaml"))
    identity = _load_identity(identity_path)
    simulator_url = os.environ.get("SIMULATOR_URL", "http://simulator:18080")
    heartbeat = float(os.environ.get("PET_HEARTBEAT_SECS", "10"))

    provider = _make_provider()
    simulator = SimulatorClient(simulator_url)
    loop = BrainLoop(
        provider=provider,
        simulator=simulator,
        prompt_builder=PromptBuilder(identity),
        memory=ShortTermMemory(max_size=20),
        heartbeat=heartbeat,
    )
    try:
        await loop.run()
    finally:
        await simulator.close()


if __name__ == "__main__":
    asyncio.run(main())
