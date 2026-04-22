from brain.memory import ShortTermMemory
from brain.parser import BrainResponse


def make_state(x=5, y=5, mood="neutral"):
    return {
        "config": {"width": 20, "height": 15},
        "pet": {"x": x, "y": y, "facing": "right", "mood": mood},
        "tick": 0,
    }


def make_response(note=None, mood=None):
    return BrainResponse(actions=[], mood=mood, memory=note)


def test_starts_empty():
    assert len(ShortTermMemory()) == 0


def test_store_adds_entry():
    m = ShortTermMemory()
    m.store(make_state(), make_response())
    assert len(m) == 1


def test_recent_returns_all_when_under_limit():
    m = ShortTermMemory()
    m.store(make_state(x=1), make_response("first"))
    m.store(make_state(x=2), make_response("second"))
    recent = m.recent()
    assert len(recent) == 2


def test_recent_returns_latest_last():
    m = ShortTermMemory()
    m.store(make_state(), make_response("first"))
    m.store(make_state(), make_response("second"))
    assert m.recent()[-1].note == "second"


def test_recent_caps_at_n():
    m = ShortTermMemory()
    for i in range(10):
        m.store(make_state(), make_response(f"entry {i}"))
    assert len(m.recent(n=3)) == 3


def test_ring_buffer_drops_oldest():
    m = ShortTermMemory(max_size=3)
    for i in range(5):
        m.store(make_state(x=i), make_response(f"entry {i}"))
    assert len(m) == 3
    notes = [e.note for e in m.recent()]
    assert "entry 0" not in notes
    assert "entry 4" in notes


def test_stores_position():
    m = ShortTermMemory()
    m.store(make_state(x=7, y=3), make_response())
    assert m.recent()[0].position == (7, 3)


def test_stores_mood_from_state():
    m = ShortTermMemory()
    m.store(make_state(mood="happy"), make_response())
    assert m.recent()[0].mood == "happy"


def test_stores_note_from_response():
    m = ShortTermMemory()
    m.store(make_state(), make_response(note="interesting corner"))
    assert m.recent()[0].note == "interesting corner"


def test_stores_actions():
    m = ShortTermMemory()
    actions = [{"skill": "move", "direction": "up"}]
    m.store(make_state(), BrainResponse(actions=actions, mood=None, memory=None))
    assert m.recent()[0].actions_taken == actions
