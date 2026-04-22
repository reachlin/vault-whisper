import pytest
from brain.prompt import PromptBuilder, PetIdentity
from brain.memory import MemoryEntry


def make_builder():
    return PromptBuilder(PetIdentity(
        name="Pepper",
        purpose="A curious AI pet.",
        hard_rules=["Never harm anyone.", "Be honest."],
    ))


def make_state(x=5, y=3, mood="neutral", tick=0):
    return {
        "config": {"width": 20, "height": 15},
        "pet": {"x": x, "y": y, "facing": "right", "mood": mood},
        "tick": tick,
    }


def test_system_contains_name():
    assert "Pepper" in make_builder().build_system()


def test_system_contains_purpose():
    assert "curious AI pet" in make_builder().build_system()


def test_system_contains_all_hard_rules():
    system = make_builder().build_system()
    assert "Never harm anyone." in system
    assert "Be honest." in system


def test_system_contains_response_format():
    system = make_builder().build_system()
    assert "actions" in system
    assert "json" in system


def test_user_contains_position():
    msg = make_builder().build_user(make_state(x=5, y=3), None, None, [])
    assert "(5, 3)" in msg


def test_user_contains_grid_dimensions():
    msg = make_builder().build_user(make_state(), None, None, [])
    assert "20" in msg and "15" in msg


def test_user_contains_tick():
    msg = make_builder().build_user(make_state(tick=42), None, None, [])
    assert "42" in msg


def test_user_shows_no_frame_when_none():
    msg = make_builder().build_user(make_state(), None, None, [])
    assert "no frame" in msg


def test_user_shows_frame_available():
    msg = make_builder().build_user(make_state(), "data:image/jpeg;base64,abc", None, [])
    assert "frame available" in msg


def test_user_shows_transcript():
    msg = make_builder().build_user(make_state(), None, "hello there", [])
    assert "hello there" in msg


def test_user_shows_no_transcript_when_none():
    msg = make_builder().build_user(make_state(), None, None, [])
    assert "nothing" in msg


def test_user_includes_memory_note():
    entry = MemoryEntry(
        timestamp="2026-04-22T10:00:00",
        position=(3, 3),
        mood="happy",
        actions_taken=[],
        note="explored north wall",
    )
    msg = make_builder().build_user(make_state(), None, None, [entry])
    assert "explored north wall" in msg


def test_user_shows_empty_memory_label():
    msg = make_builder().build_user(make_state(), None, None, [])
    assert "none yet" in msg.lower() or "RECENT MEMORY" in msg
