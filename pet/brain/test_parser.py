from brain.parser import parse_response


def test_parses_fenced_json_block():
    text = '```json\n{"actions": [{"skill": "move", "direction": "right"}], "mood": "curious", "memory": "moved right"}\n```'
    r = parse_response(text)
    assert len(r.actions) == 1
    assert r.actions[0]["skill"] == "move"
    assert r.actions[0]["direction"] == "right"
    assert r.mood == "curious"
    assert r.memory == "moved right"


def test_parses_bare_json_at_end():
    text = 'I will speak. {"actions": [{"skill": "speak", "text": "hi"}], "mood": "happy", "memory": null}'
    r = parse_response(text)
    assert len(r.actions) == 1
    assert r.actions[0]["text"] == "hi"


def test_parses_multiple_actions():
    text = '```json\n{"actions": [{"skill": "move", "direction": "up"}, {"skill": "speak", "text": "hello"}], "mood": "happy"}\n```'
    r = parse_response(text)
    assert len(r.actions) == 2


def test_parses_empty_actions():
    text = '```json\n{"actions": [], "mood": "tired"}\n```'
    r = parse_response(text)
    assert r.actions == []
    assert r.mood == "tired"


def test_returns_empty_on_no_json():
    r = parse_response("I have no idea what to do.")
    assert r.actions == []
    assert r.mood is None
    assert r.memory is None


def test_returns_empty_on_malformed_json():
    r = parse_response("```json\n{broken json here\n```")
    assert r.actions == []


def test_mood_is_none_when_absent():
    text = '```json\n{"actions": []}\n```'
    r = parse_response(text)
    assert r.mood is None


def test_memory_is_none_when_null():
    text = '```json\n{"actions": [], "memory": null}\n```'
    r = parse_response(text)
    assert r.memory is None


def test_fenced_block_takes_priority_over_bare():
    text = 'Bare: {"actions": [], "mood": "sad"}\n```json\n{"actions": [], "mood": "happy"}\n```'
    r = parse_response(text)
    assert r.mood == "happy"
