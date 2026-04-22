import base64
import os
import sys
from pathlib import Path

# ensure the pet/ root is on sys.path when run as a standalone script
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastmcp import FastMCP
from fastmcp.utilities.types import Image
from mcp_server.client import SimulatorClient
from brain.longterm_memory import LongTermMemory

SIMULATOR_URL = os.environ.get("SIMULATOR_URL", "http://localhost:18080")

mcp = FastMCP(
    "AI Pet — Pepper",
    instructions="You are controlling Pepper, an AI pet living in a 2D grid. "
                 "Use pet_status to read her current state, then decide actions. "
                 "Move her around to explore, speak to interact, and set her mood to reflect her feelings.",
)

_sim = SimulatorClient(SIMULATOR_URL)

_memory_file = Path(os.environ.get("PET_MEMORY_FILE", "data/memory.md"))
_mem = LongTermMemory(_memory_file)


@mcp.tool()
def pet_status() -> dict:
    """Get Pepper's current status: position, facing direction, mood, tick count,
    grid dimensions, whether a camera frame is available, and the last heard transcript."""
    return _sim.get_status()


@mcp.tool()
def pet_move(direction: str) -> dict:
    """Move Pepper one cell in the grid.

    Args:
        direction: One of 'up', 'down', 'left', 'right'.

    Returns the new position and tick count. Moves blocked at grid boundaries.
    """
    return _sim.move(direction)


@mcp.tool()
def pet_speak(text: str) -> dict:
    """Make Pepper say something out loud in the simulator (displayed on screen and spoken via TTS).

    Args:
        text: What Pepper should say.
    """
    return _sim.speak(text)


@mcp.tool()
def pet_camera_frame() -> Image | dict:
    """Get the latest camera frame from Pepper's environment as an image.
    Returns the actual image so you can see what Pepper sees.
    Returns an error dict if no frame is available (camera not enabled in browser).
    """
    frame = _sim.get_last_frame()
    if not frame:
        return {"error": "no camera frame available — enable camera in the simulator browser tab"}
    # frame is a data URL: "data:image/jpeg;base64,<data>"
    raw = frame.split(",", 1)[1] if "," in frame else frame
    return Image(data=base64.b64decode(raw), format="jpeg")


@mcp.tool()
def pet_remember(note: str, mood: str | None = None) -> dict:
    """Save a note to Pepper's long-term memory (a markdown file).
    Call this to record meaningful moments — people met, feelings, discoveries.
    The memory persists across sessions and can be stored in GitHub or cloud.

    Args:
        note: What to remember — one or two sentences about this moment.
        mood: Optional mood override; defaults to Pepper's current mood.
    """
    status = _sim.get_status()
    position = (status["position"]["x"], status["position"]["y"])
    _mem.save(note, position=position, mood=mood or status["mood"])
    return {"saved": True, "note": note}


@mcp.tool()
def pet_recall(n: int = 10) -> dict:
    """Read Pepper's recent long-term memories from the markdown file.
    Call this at the start of each session to remember past interactions and context.

    Args:
        n: How many recent memories to retrieve (default 10).
    """
    entries = _mem.recent(n=n)
    return {"memories": entries, "count": len(entries)}


@mcp.tool()
def pet_set_mood(mood: str) -> dict:
    """Set Pepper's current mood, which changes her colour in the simulator.

    Args:
        mood: One of 'neutral', 'happy', 'curious', 'tired', 'scared'.
    """
    return _sim.set_mood(mood)


if __name__ == "__main__":
    mcp.run()
