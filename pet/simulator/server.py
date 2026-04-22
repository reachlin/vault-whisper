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
connections: list[WebSocket] = []

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

@app.get("/")
def serve_index():
    return FileResponse(str(_static / "index.html"))


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


@app.post("/speak")
async def speak(req: SpeakRequest):
    await broadcast({"type": "speak", "text": req.text})
    return {"text": req.text}


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
