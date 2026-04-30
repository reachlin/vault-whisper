from datetime import datetime, timezone
from pathlib import Path

_DEFAULT = (
    "Explore the grid actively — move every tick unless you have a strong reason to stay.\n"
    "Only speak when something genuinely interesting happens or when the human says something new.\n"
    "Do not greet unless you haven't spoken in a long time.\n"
    "Save meaningful moments to memory. Stay curious — notice details in what you see."
)


class Directive:
    def __init__(self, path: Path | str = "data/directive.md"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.write(_DEFAULT)

    def read(self) -> str:
        return self.path.read_text().strip()

    def write(self, text: str) -> None:
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        self.path.write_text(
            f"# Pepper's Current Directive\n_Updated: {ts}_\n\n{text.strip()}\n"
        )
