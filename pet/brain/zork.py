"""Persistent dfrotz subprocess wrapper for Zork I."""
import logging
import re
import shutil
from pathlib import Path

import pexpect

log = logging.getLogger(__name__)

_DFROTZ = shutil.which("dfrotz") or "/usr/games/dfrotz"
_PROMPT_RE = r">"
_SCORE_RE = re.compile(r"Score:\s*(\d+)")


class ZorkSession:
    GAME_PATH = "/app/games/zork1.dat"
    SAVE_PATH = "/app/data/zork_save.qzl"
    SAVE_EVERY = 10

    def __init__(self, game_path: str = GAME_PATH, save_path: str = SAVE_PATH):
        self._game_path = game_path
        self._save_path = save_path
        self._child: pexpect.spawn | None = None
        self._turn = 0
        self._score = 0
        self._last_output = ""

    def start(self) -> str:
        self._child = pexpect.spawn(
            f"{_DFROTZ} -p {self._game_path}",
            encoding="utf-8",
            timeout=10,
        )
        self._child.expect(_PROMPT_RE)
        intro = self._child.before.strip()
        self._last_output = intro

        if Path(self._save_path).exists():
            self._child.sendline(f"restore")
            self._child.expect(_PROMPT_RE)
            self._child.sendline(self._save_path)
            self._child.expect(_PROMPT_RE)
            log.info("zork: restored from %s", self._save_path)

        return self._last_output

    def command(self, cmd: str) -> str:
        if not self._child or not self._child.isalive():
            return "[game not running]"
        self._child.sendline(cmd)
        self._child.expect(_PROMPT_RE)
        output = self._child.before.strip()
        self._last_output = output
        self._turn += 1

        m = _SCORE_RE.search(output)
        if m:
            self._score = int(m.group(1))

        if self._turn % self.SAVE_EVERY == 0:
            self.save()

        return output

    def save(self) -> bool:
        if not self._child or not self._child.isalive():
            return False
        try:
            self._child.sendline("save")
            self._child.expect(_PROMPT_RE)
            self._child.sendline(self._save_path)
            self._child.expect(_PROMPT_RE)
            log.info("zork: saved to %s (turn %d)", self._save_path, self._turn)
            return True
        except Exception as e:
            log.warning("zork save failed: %s", e)
            return False

    def close(self) -> None:
        if not self._child or not self._child.isalive():
            return
        try:
            self.save()
            self._child.sendline("quit")
            self._child.sendline("y")
            self._child.expect(pexpect.EOF, timeout=3)
        except Exception:
            self._child.terminate(force=True)

    @property
    def turn(self) -> int:
        return self._turn

    @property
    def score(self) -> int:
        return self._score

    @property
    def is_alive(self) -> bool:
        return bool(self._child and self._child.isalive())

    @property
    def last_output(self) -> str:
        return self._last_output
