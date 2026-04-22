import httpx


class SimulatorClient:
    def __init__(self, base_url: str):
        self._http = httpx.Client(base_url=base_url, timeout=10.0)

    def get_status(self) -> dict:
        state = self._http.get("/state").raise_for_status().json()
        frame = self._http.get("/hardware/last-frame").raise_for_status().json()["frame"]
        transcript = self._http.get("/hardware/last-transcript").raise_for_status().json()["transcript"]
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
        state = self._http.post("/move", json={"direction": direction}).raise_for_status().json()
        return {"position": {"x": state["pet"]["x"], "y": state["pet"]["y"]}, "tick": state["tick"]}

    def speak(self, text: str) -> dict:
        self._http.post("/speak", json={"text": text}).raise_for_status()
        return {"spoken": text}

    def get_last_frame(self) -> str | None:
        return self._http.get("/hardware/last-frame").raise_for_status().json()["frame"]

    def set_mood(self, mood: str) -> dict:
        self._http.post("/mood", json={"mood": mood}).raise_for_status()
        return {"mood": mood}

    def close(self) -> None:
        self._http.close()
