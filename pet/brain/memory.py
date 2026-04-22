from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass
class MemoryEntry:
    timestamp: str
    position: tuple[int, int]
    mood: str
    actions_taken: list[dict]
    note: str | None


class ShortTermMemory:
    def __init__(self, max_size: int = 20):
        self._entries: deque[MemoryEntry] = deque(maxlen=max_size)
        self.max_size = max_size

    def store(self, state: dict, response) -> None:
        pet = state["pet"]
        self._entries.append(MemoryEntry(
            timestamp=datetime.now(timezone.utc).isoformat(),
            position=(pet["x"], pet["y"]),
            mood=pet["mood"],
            actions_taken=list(response.actions),
            note=response.memory,
        ))

    def recent(self, n: int = 5) -> list[MemoryEntry]:
        entries = list(self._entries)
        return entries[-n:]

    def __len__(self) -> int:
        return len(self._entries)
