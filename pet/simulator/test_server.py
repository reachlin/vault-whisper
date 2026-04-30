import pytest
from fastapi.testclient import TestClient
import simulator.server as srv
from simulator.grid import Grid
from simulator.server import app


@pytest.fixture(autouse=True)
def reset_state():
    srv.grid = Grid()
    srv.last_frame = None
    srv.last_transcript = None
    srv.pet_activity = "idle"
    srv.connections.clear()


@pytest.fixture
def client():
    return TestClient(app)


# --- state ---

def test_get_state_shape(client):
    r = client.get("/state")
    assert r.status_code == 200
    data = r.json()
    assert {"pet", "config", "tick"} <= data.keys()


def test_state_pet_starts_at_center(client):
    data = client.get("/state").json()
    assert data["pet"]["x"] == data["config"]["width"] // 2
    assert data["pet"]["y"] == data["config"]["height"] // 2


# --- move ---

def test_move_up(client):
    initial_y = client.get("/state").json()["pet"]["y"]
    r = client.post("/move", json={"direction": "up"})
    assert r.status_code == 200
    assert r.json()["pet"]["y"] == initial_y - 1


def test_move_right(client):
    initial_x = client.get("/state").json()["pet"]["x"]
    r = client.post("/move", json={"direction": "right"})
    assert r.status_code == 200
    assert r.json()["pet"]["x"] == initial_x + 1


def test_move_updates_facing(client):
    r = client.post("/move", json={"direction": "left"})
    assert r.json()["pet"]["facing"] == "left"


def test_move_invalid_direction_rejected(client):
    r = client.post("/move", json={"direction": "diagonal"})
    assert r.status_code == 422


# --- camera ---

def test_last_frame_empty_on_start(client):
    r = client.get("/hardware/last-frame")
    assert r.status_code == 200
    assert r.json()["frame"] is None


def test_receive_and_retrieve_camera_frame(client):
    frame = "data:image/jpeg;base64,/9j/abc123"
    client.post("/hardware/camera-frame", json={"frame": frame})
    saved = client.get("/hardware/last-frame").json()
    assert saved["frame"] == frame


# --- transcript ---

def test_last_transcript_empty_on_start(client):
    r = client.get("/hardware/last-transcript")
    assert r.status_code == 200
    assert r.json()["transcript"] is None


def test_receive_text_transcript(client):
    r = client.post("/hardware/transcript", json={"text": "hello pepper"})
    assert r.status_code == 200
    assert client.get("/hardware/last-transcript").json()["transcript"] == "hello pepper"


def test_empty_transcript_ignored(client):
    client.post("/hardware/transcript", json={"text": ""})
    assert client.get("/hardware/last-transcript").json()["transcript"] is None


def test_transcript_broadcast_via_websocket(client):
    with client.websocket_connect("/ws") as ws:
        ws.receive_json()  # initial state
        client.post("/hardware/transcript", json={"text": "hi there"})
        msg = ws.receive_json()
        assert msg["type"] == "transcript"
        assert msg["text"] == "hi there"


# --- speak ---

def test_speak_returns_text(client):
    r = client.post("/speak", json={"text": "Hello world"})
    assert r.status_code == 200
    assert r.json()["text"] == "Hello world"


# --- mood ---

def test_set_mood(client):
    r = client.post("/mood", json={"mood": "happy"})
    assert r.status_code == 200
    assert r.json()["pet"]["mood"] == "happy"


def test_set_mood_reflects_in_state(client):
    client.post("/mood", json={"mood": "tired"})
    assert client.get("/state").json()["pet"]["mood"] == "tired"


# --- websocket ---

def test_websocket_sends_initial_state(client):
    with client.websocket_connect("/ws") as ws:
        msg = ws.receive_json()
        assert msg["type"] == "state"
        assert "pet" in msg["data"]
        assert "config" in msg["data"]
