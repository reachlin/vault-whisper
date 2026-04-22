from datetime import datetime, timezone
from pathlib import Path

HEADER = "# Pepper's Memory\n"


class LongTermMemory:
    def __init__(self, path: Path | str = "data/memory.md"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text(HEADER)

    def save(
        self,
        note: str,
        position: tuple[int, int] | None = None,
        mood: str | None = None,
    ) -> None:
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        meta_parts = [f"**{timestamp}**"]
        if position is not None:
            meta_parts.append(str(position))
        if mood:
            meta_parts.append(mood)
        meta = " · ".join(meta_parts)

        entry = f"\n---\n{meta}\n{note.strip()}\n"

        content = self.path.read_text()
        # prepend after the title line so newest entry is always first
        first_newline = content.index("\n") if "\n" in content else len(content)
        self.path.write_text(content[: first_newline + 1] + entry + content[first_newline + 1 :])

    def recent(self, n: int = 10) -> list[str]:
        content = self.path.read_text()
        parts = content.split("\n---\n")
        entries = [p.strip() for p in parts[1:] if p.strip()]
        return entries[:n]

    def all_text(self) -> str:
        return self.path.read_text()
