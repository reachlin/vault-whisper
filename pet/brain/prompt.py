from dataclasses import dataclass
from brain.memory import MemoryEntry


@dataclass
class PetIdentity:
    name: str
    purpose: str
    hard_rules: list[str]


class PromptBuilder:
    def __init__(self, identity: PetIdentity):
        self.identity = identity

    def build_system(self) -> str:
        rules = "\n".join(f"- {r}" for r in self.identity.hard_rules)
        return f"""You are {self.identity.name}.

PURPOSE:
{self.identity.purpose.strip()}

HARD RULES (immutable — follow unconditionally):
{rules}

RESPONSE FORMAT:
Think briefly, then end your response with exactly one JSON block:
```json
{{
  "actions": [
    {{"skill": "move", "direction": "up|down|left|right"}},
    {{"skill": "speak", "text": "..."}}
  ],
  "mood": "neutral|happy|curious|tired|scared",
  "memory": "one sentence summary of this moment"
}}
```
Include 0 or more actions. Valid skills: move, speak."""

    def build_user(
        self,
        state: dict,
        frame: str | None,
        transcript: str | None,
        recent: list[MemoryEntry],
    ) -> str:
        pet = state["pet"]
        cfg = state["config"]
        camera = "frame available (vision not yet wired)" if frame else "no frame"
        heard = f'"{transcript}"' if transcript else "nothing"

        if recent:
            mem_lines = "\n".join(
                f"  [{e.timestamp[:19]}] at {e.position}, mood={e.mood}, note={e.note or '—'}"
                for e in recent
            )
        else:
            mem_lines = "  (none yet)"

        return f"""CURRENT STATE (tick {state['tick']}):
- Position: ({pet['x']}, {pet['y']}) in a {cfg['width']}×{cfg['height']} grid
- Facing: {pet['facing']}
- Mood: {pet['mood']}
- Camera: {camera}
- Last heard: {heard}

RECENT MEMORY:
{mem_lines}

What do you do next?"""
