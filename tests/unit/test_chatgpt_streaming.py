"""Memory does not grow with the number of conversations read (SC-007, CG-14, research R3).

Measured rather than argued: `tracemalloc` records the peak while a synthesized export is read in
full, for an export ten times the size of another. A reader that held the export — `json.load`, or
a list of conversations — grows with it; a streaming one stays within a constant factor.
"""

from __future__ import annotations

import tracemalloc
from pathlib import Path

from hermes_memory.ingestion.chatgpt import ChatGPTExportSource
from tests.synthetic import chatgpt_export as synth

PARAGRAPH = "A synthesized paragraph about retry policies and idempotency keys. " * 30


def _export(path: Path, count: int) -> Path:
    records = [
        synth.linear_record(
            f"conv-{i}",
            synth.message("user", PARAGRAPH),
            synth.message("assistant", PARAGRAPH),
        )
        for i in range(count)
    ]
    return synth.write_directory(path, records)


def _peak_while_reading(path: Path) -> int:
    source = ChatGPTExportSource(path)
    tracemalloc.start()
    try:
        for _ in source.read():
            pass
        return tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()


def test_peak_memory_does_not_grow_with_the_export(tmp_path: Path) -> None:
    small = _export(tmp_path / "small", 200)
    large = _export(tmp_path / "large", 2_000)
    _peak_while_reading(small)  # warm imports and caches, so they do not count against the first

    small_peak = _peak_while_reading(small)
    large_peak = _peak_while_reading(large)

    assert large_peak < 3 * small_peak, (small_peak, large_peak)
