"""Block the network and the filesystem for the pipeline tests (PL-5).

A test that merely *does not* perform I/O passes equally well on the day someone adds some. Blocking
makes the claim falsifiable, which is the difference between an assertion and a habit.

**What this does not cover**, stated rather than implied: `os.open`, `os.write`, a C extension
reaching the filesystem directly, or a socket obtained by any route other than `socket.socket`. The
guard exists to catch the realistic mistake — a fake that quietly writes a temporary file, a source
that opens a fixture — not to sandbox a hostile implementation
(specs/007-boundary-interfaces/research.md R14).
"""

from __future__ import annotations

import builtins
import socket
from pathlib import Path
from typing import Any

import pytest

_WRITING = frozenset("wxa+")


class ForbiddenIO(AssertionError):
    """The pipeline reached for the network or the filesystem. It is assembled from fakes."""


@pytest.fixture
def no_io(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make network and filesystem writes raise for the duration of a test."""

    def refuse_socket(*args: Any, **kwargs: Any) -> Any:
        raise ForbiddenIO("the pipeline opened a socket; it is assembled entirely from fakes")

    def refuse_write(path: Any, mode: str = "r", *args: Any, **kwargs: Any) -> Any:
        if _WRITING & set(mode):
            raise ForbiddenIO(f"the pipeline opened {path!r} for writing (mode {mode!r})")
        return _real_open(path, mode, *args, **kwargs)

    def refuse_path_open(self: Path, mode: str = "r", *args: Any, **kwargs: Any) -> Any:
        if _WRITING & set(mode):
            raise ForbiddenIO(f"the pipeline opened {self} for writing (mode {mode!r})")
        return _real_path_open(self, mode, *args, **kwargs)

    def refuse_path_write(self: Path, *args: Any, **kwargs: Any) -> Any:
        raise ForbiddenIO(f"the pipeline wrote to {self}")

    _real_open = builtins.open
    _real_path_open = Path.open

    monkeypatch.setattr(socket, "socket", refuse_socket)
    monkeypatch.setattr(builtins, "open", refuse_write)
    monkeypatch.setattr(Path, "open", refuse_path_open)
    monkeypatch.setattr(Path, "write_text", refuse_path_write)
    monkeypatch.setattr(Path, "write_bytes", refuse_path_write)
