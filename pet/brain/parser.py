import json
import re
from pydantic import BaseModel


class BrainResponse(BaseModel):
    actions: list[dict] = []
    mood: str | None = None
    memory: str | None = None


def parse_response(text: str) -> BrainResponse:
    # fenced ```json ... ``` block takes priority
    m = re.search(r'```json\s*(\{.*?\})\s*```', text, re.DOTALL)
    if m:
        try:
            return BrainResponse(**json.loads(m.group(1)))
        except Exception:
            return BrainResponse()

    # fall back: find the last JSON object containing "actions"
    for match in reversed(list(re.finditer(r'\{', text))):
        try:
            obj = json.loads(text[match.start():])
            if "actions" in obj:
                return BrainResponse(**obj)
        except json.JSONDecodeError:
            continue

    return BrainResponse()
