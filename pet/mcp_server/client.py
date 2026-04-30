import httpx


class SimulatorClient:
    def __init__(self, base_url: str):
        self._base_url = base_url.rstrip("/")
        # trust_env=False prevents system proxies (e.g. Stash) from intercepting localhost
        self._client = httpx.Client(trust_env=False, timeout=10.0)

    def _get(self, path: str) -> httpx.Response:
        return self._client.get(f"{self._base_url}{path}")

    def _post(self, path: str, **kwargs) -> httpx.Response:
        return self._client.post(f"{self._base_url}{path}", **kwargs)

    def get_status(self) -> dict:
        state = self._get("/state").raise_for_status().json()
        frame = self._get("/hardware/last-frame").raise_for_status().json()["frame"]
        transcript = self._get("/hardware/last-transcript").raise_for_status().json()["transcript"]
        pet = state["pet"]
        return {
            "position": {"x": pet["x"], "y": pet["y"]},
            "facing": pet["facing"],
            "mood": pet["mood"],
            "tick": state["tick"],
            "grid": {"width": state["config"]["width"], "height": state["config"]["height"]},
            "camera_frame_available": frame is not None,
            "last_transcript": transcript,
        }

    def move(self, direction: str) -> dict:
        state = self._post("/move", json={"direction": direction}).raise_for_status().json()
        return {"position": {"x": state["pet"]["x"], "y": state["pet"]["y"]}, "tick": state["tick"]}

    def speak(self, text: str) -> dict:
        self._post("/speak", json={"text": text}).raise_for_status()
        return {"spoken": text}

    def get_last_frame(self) -> str | None:
        return self._get("/hardware/last-frame").raise_for_status().json()["frame"]

    def set_mood(self, mood: str) -> dict:
        self._post("/mood", json={"mood": mood}).raise_for_status()
        return {"mood": mood}

    def close(self) -> None:
        pass
