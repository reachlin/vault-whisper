import pytest
from brain.longterm_memory import LongTermMemory


@pytest.fixture
def mem(tmp_path):
    return LongTermMemory(tmp_path / "memory.md")


def test_creates_file_on_init(tmp_path):
    LongTermMemory(tmp_path / "memory.md")
    assert (tmp_path / "memory.md").exists()


def test_new_file_starts_with_header(tmp_path):
    LongTermMemory(tmp_path / "memory.md")
    content = (tmp_path / "memory.md").read_text()
    assert content.startswith("# Pepper's Memory")


def test_recent_empty_on_new_file(mem):
    assert mem.recent() == []


def test_save_entry_appears_in_recent(mem):
    mem.save("spotted a cat")
    assert any("spotted a cat" in e for e in mem.recent())


def test_newest_entry_is_first(mem):
    mem.save("first note")
    mem.save("second note")
    entries = mem.recent()
    assert "second note" in entries[0]
    assert "first note" in entries[1]


def test_recent_caps_at_n(mem):
    for i in range(10):
        mem.save(f"note {i}")
    assert len(mem.recent(n=3)) == 3


def test_recent_returns_all_when_fewer_than_n(mem):
    mem.save("only one")
    assert len(mem.recent(n=10)) == 1


def test_file_is_valid_markdown(mem):
    mem.save("test note", position=(5, 3), mood="curious")
    content = (mem.path).read_text()
    assert content.startswith("# Pepper's Memory")
    assert "---" in content
    assert "test note" in content


def test_entry_includes_timestamp(mem):
    mem.save("note")
    assert "UTC" in mem.path.read_text()


def test_entry_includes_position(mem):
    mem.save("note", position=(7, 3))
    assert "(7, 3)" in mem.path.read_text()


def test_entry_includes_mood(mem):
    mem.save("note", mood="happy")
    assert "happy" in mem.path.read_text()


def test_multiple_saves_all_readable(mem):
    for i in range(5):
        mem.save(f"note {i}", position=(i, i), mood="neutral")
    entries = mem.recent()
    assert len(entries) == 5


def test_creates_parent_dirs(tmp_path):
    m = LongTermMemory(tmp_path / "sub" / "deep" / "memory.md")
    m.save("deep note")
    assert any("deep note" in e for e in m.recent())
