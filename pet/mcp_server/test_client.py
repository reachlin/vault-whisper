import httpx
import pytest
import respx

from mcp_server.client import SimulatorClient

BASE = "http://localhost:18080"


def make_state(x=5, y=3, facing="left", mood="curious", tick=10):
    return {
        "config": {"width": 20, "height": 15},
        "pet": {"x": x, "y": y, "facing": facing, "mood": mood},
        "tick": tick,
    }


def test_get_status_position():
    with respx.mock() as mock:
        mock.get(f"{BASE}/state").mock(return_value=httpx.Response(200, json=make_state()))
        mock.get(f"{BASE}/hardware/last-frame").mock(return_value=httpx.Response(200, json={"frame": None}))
        mock.get(f"{BASE}/hardware/last-transcript").mock(return_value=httpx.Response(200, json={"transcript": "hello"}))

        status = SimulatorClient(BASE).get_status()

    assert status["position"] == {"x": 5, "y": 3}
    assert status["facing"] == "left"
    assert status["mood"] == "curious"
    assert status["tick"] == 10
    assert status["grid"] == {"width": 20, "height": 15}


def test_get_status_no_camera():
    with respx.mock() as mock:
        mock.get(f"{BASE}/state").mock(return_value=httpx.Response(200, json=make_state()))
        mock.get(f"{BASE}/hardware/last-frame").mock(return_value=httpx.Response(200, json={"frame": None}))
        mock.get(f"{BASE}/hardware/last-transcript").mock(return_value=httpx.Response(200, json={"transcript": None}))

        status = SimulatorClient(BASE).get_status()

    assert status["camera_frame_available"] is False
    assert status["last_transcript"] is None


def test_get_status_camera_available():
    with respx.mock() as mock:
        mock.get(f"{BASE}/state").mock(return_value=httpx.Response(200, json=make_state()))
        mock.get(f"{BASE}/hardware/last-frame").mock(return_value=httpx.Response(200, json={"frame": "data:image/jpeg;base64,abc"}))
        mock.get(f"{BASE}/hardware/last-transcript").mock(return_value=httpx.Response(200, json={"transcript": None}))

        status = SimulatorClient(BASE).get_status()

    assert status["camera_frame_available"] is True


def test_move_sends_direction():
    with respx.mock() as mock:
        route = mock.post(f"{BASE}/move").mock(return_value=httpx.Response(200, json=make_state(x=6, tick=1)))

        result = SimulatorClient(BASE).move("right")

    assert route.called
    assert result["position"]["x"] == 6
    assert result["tick"] == 1


def test_speak_sends_text():
    with respx.mock() as mock:
        route = mock.post(f"{BASE}/speak").mock(return_value=httpx.Response(200, json={"text": "hello"}))

        result = SimulatorClient(BASE).speak("hello")

    assert route.called
    assert result["spoken"] == "hello"


def test_get_last_frame_returns_none_when_empty():
    with respx.mock() as mock:
        mock.get(f"{BASE}/hardware/last-frame").mock(return_value=httpx.Response(200, json={"frame": None}))
        assert SimulatorClient(BASE).get_last_frame() is None


def test_get_last_frame_returns_data_url():
    frame = "data:image/jpeg;base64,/9j/abc123"
    with respx.mock() as mock:
        mock.get(f"{BASE}/hardware/last-frame").mock(return_value=httpx.Response(200, json={"frame": frame}))
        assert SimulatorClient(BASE).get_last_frame() == frame


def test_set_mood_sends_mood():
    with respx.mock() as mock:
        route = mock.post(f"{BASE}/mood").mock(return_value=httpx.Response(200, json=make_state(mood="happy")))

        result = SimulatorClient(BASE).set_mood("happy")

    assert route.called
    assert result["mood"] == "happy"
