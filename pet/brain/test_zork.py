"""Tests for ZorkSession — mocks pexpect, never touches real dfrotz."""
import pytest
from unittest.mock import patch, MagicMock
from brain.zork import ZorkSession


class MockChild:
    """Minimal pexpect child stub. Each expect() call pops the next canned response."""

    def __init__(self, responses: list[str]):
        self._responses = iter(responses)
        self.before = ""
        self._alive = True

    def expect(self, *args, **kwargs):
        self.before = next(self._responses, "")
        return 0

    def sendline(self, text: str):
        pass

    def isalive(self) -> bool:
        return self._alive

    def terminate(self, force: bool = False):
        self._alive = False


def _spawn(responses: list[str], save_exists: bool = False):
    """Return a (session, mock_child) pair with pexpect.spawn patched."""
    child = MockChild(responses)
    with patch("pexpect.spawn", return_value=child), \
         patch("pathlib.Path.exists", return_value=save_exists):
        s = ZorkSession("/fake/zork1.dat", "/fake/save.qzl")
        s.start()
    return s, child


def test_start_returns_intro():
    intro = "West of House\nYou are standing in an open field."
    s, _ = _spawn([intro])
    assert "West of House" in s.last_output


def test_command_sends_and_returns_output():
    s, child = _spawn(["West of House"])
    child._alive = True
    with patch("pexpect.spawn", return_value=child):
        child._responses = iter(["You are in a twisty maze."])
        out = s.command("go north")
    assert "maze" in out


def test_turn_counter_increments():
    child = MockChild(["West of House", "room A", "room B"])
    child._alive = True
    with patch("pexpect.spawn", return_value=child), \
         patch("pathlib.Path.exists", return_value=False):
        s = ZorkSession("/fake/zork1.dat", "/fake/save.qzl")
        s.start()
        s.command("go north")
        s.command("go south")
    assert s.turn == 2


def test_score_parsed_from_output():
    child = MockChild(["West of House  Score: 0", "Score: 10  Moves: 3"])
    child._alive = True
    with patch("pexpect.spawn", return_value=child), \
         patch("pathlib.Path.exists", return_value=False):
        s = ZorkSession("/fake/zork1.dat", "/fake/save.qzl")
        s.start()
        s.command("take lamp")
    assert s.score == 10


def test_is_alive_reflects_process_state():
    child = MockChild(["intro"])
    with patch("pexpect.spawn", return_value=child), \
         patch("pathlib.Path.exists", return_value=False):
        s = ZorkSession("/fake/zork1.dat", "/fake/save.qzl")
        s.start()
    assert s.is_alive
    child._alive = False
    assert not s.is_alive


def test_command_when_not_running_returns_error():
    child = MockChild(["intro"])
    child._alive = False
    with patch("pexpect.spawn", return_value=child), \
         patch("pathlib.Path.exists", return_value=False):
        s = ZorkSession("/fake/zork1.dat", "/fake/save.qzl")
        s.start()
    out = s.command("go north")
    assert "not running" in out


def test_save_triggered_every_10_turns():
    responses = ["intro"] + [f"room {i}" for i in range(10)]
    child = MockChild(responses)
    child._alive = True
    saved = []

    original_save = ZorkSession.save

    def spy_save(self):
        saved.append(True)
        return True

    with patch("pexpect.spawn", return_value=child), \
         patch("pathlib.Path.exists", return_value=False), \
         patch.object(ZorkSession, "save", spy_save):
        s = ZorkSession("/fake/zork1.dat", "/fake/save.qzl")
        s.start()
        for i in range(10):
            child._responses = iter([f"room {i}"])
            s.command(f"cmd {i}")

    assert len(saved) == 1  # exactly one auto-save at turn 10


def test_restore_called_when_save_exists():
    child = MockChild(["intro", "Restored."])
    child._alive = True
    sent = []
    original_sendline = child.sendline
    child.sendline = lambda t: sent.append(t)

    with patch("pexpect.spawn", return_value=child), \
         patch("pathlib.Path.exists", return_value=True):
        s = ZorkSession("/fake/zork1.dat", "/fake/save.qzl")
        s.start()

    assert any("restore" in c.lower() for c in sent)
