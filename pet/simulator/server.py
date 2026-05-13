from contextlib import asynccontextmanager
from pathlib import Path
import json

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from simulator.grid import Grid, Direction

grid = Grid()
last_frame: str | None = None
last_transcript: str | None = None
pet_activity: str = "idle"
connections: list[WebSocket] = []
minecraft_server: str | None = None   # "host:port" when connected, None otherwise
minecraft_state: dict = {}            # last state snapshot pushed from Mineflayer bridge

_static = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(title="AI Pet Simulator", lifespan=lifespan)

if _static.exists():
    app.mount("/static", StaticFiles(directory=str(_static)), name="static")


# --- models ---

class MoveRequest(BaseModel):
    direction: Direction


class CameraFrameRequest(BaseModel):
    frame: str  # base64 data URL


class SpeakRequest(BaseModel):
    text: str


class AudioChunkRequest(BaseModel):
    audio: str  # base64 audio blob


class TranscriptRequest(BaseModel):
    text: str


class MoodRequest(BaseModel):
    mood: str


class ActivityRequest(BaseModel):
    activity: str


class MinecraftJoinRequest(BaseModel):
    host: str = "localhost"
    port: int = 25565


class MinecraftStateRequest(BaseModel):
    connected: bool = False
    username: str | None = None
    position: dict | None = None
    health: int | None = None
    food: int | None = None
    game_mode: str | None = None
    time_of_day: int | None = None
    nearby_entities: list | None = None
    nearby_blocks: dict | None = None
    inventory: list | None = None


# --- helpers ---

async def broadcast(data: dict) -> None:
    dead = []
    for ws in connections:
        try:
            await ws.send_text(json.dumps(data))
        except Exception:
            dead.append(ws)
    for ws in dead:
        connections.remove(ws)


# --- routes ---

_NO_CACHE = {"Cache-Control": "no-store"}


@app.get("/")
def serve_index():
    return FileResponse(str(_static / "index.html"), headers=_NO_CACHE)


@app.get("/state")
def get_state():
    return grid.state.model_dump()


@app.post("/move")
async def move_pet(req: MoveRequest):
    state = grid.move(req.direction)
    await broadcast({"type": "state", "data": state.model_dump()})
    return state.model_dump()


@app.get("/hardware/last-frame")
def get_last_frame():
    return {"frame": last_frame}


@app.post("/hardware/camera-frame")
async def receive_camera_frame(req: CameraFrameRequest):
    global last_frame
    last_frame = req.frame
    return {"ok": True}


@app.get("/hardware/last-transcript")
def get_last_transcript():
    return {"transcript": last_transcript}


@app.post("/hardware/audio-chunk")
async def receive_audio(req: AudioChunkRequest):
    # Whisper STT integration point — stub until brain loop is wired
    return {"ok": True}


@app.post("/hardware/transcript")
async def receive_transcript(req: TranscriptRequest):
    global last_transcript
    if not req.text.strip():
        return {"ok": True}
    last_transcript = req.text.strip()
    await broadcast({"type": "transcript", "text": last_transcript})
    return {"ok": True}


@app.post("/mood")
async def set_mood(req: MoodRequest):
    state = grid.set_mood(req.mood)
    await broadcast({"type": "state", "data": state.model_dump()})
    return state.model_dump()


@app.post("/pet-activity")
async def set_pet_activity(req: ActivityRequest):
    global pet_activity
    pet_activity = req.activity
    await broadcast({"type": "activity", "activity": pet_activity})
    return {"ok": True}


@app.post("/speak")
async def speak(req: SpeakRequest):
    await broadcast({"type": "speak", "text": req.text})
    return {"text": req.text}


@app.get("/minecraft/status")
def minecraft_status():
    return {"connected": minecraft_server is not None, "server": minecraft_server}


@app.post("/minecraft/join")
async def minecraft_join(req: MinecraftJoinRequest):
    global minecraft_server
    minecraft_server = f"{req.host}:{req.port}"
    await broadcast({"type": "minecraft", "connected": True, "server": minecraft_server})
    return {"ok": True, "server": minecraft_server}


@app.post("/minecraft/leave")
async def minecraft_leave():
    global minecraft_server
    minecraft_server = None
    await broadcast({"type": "minecraft", "connected": False, "server": None})
    return {"ok": True}


@app.get("/mc/state")
def get_mc_state():
    return minecraft_state


@app.post("/mc/state")
async def receive_mc_state(req: MinecraftStateRequest):
    global minecraft_state, minecraft_server
    minecraft_state = req.model_dump()
    if req.connected and minecraft_server is None and req.username:
        minecraft_server = "bridge"
    elif not req.connected:
        minecraft_server = None
    await broadcast({"type": "mc_state", "data": minecraft_state})
    return {"ok": True}


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    connections.append(ws)
    await ws.send_text(json.dumps({"type": "state", "data": grid.state.model_dump()}))
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        if ws in connections:
            connections.remove(ws)
