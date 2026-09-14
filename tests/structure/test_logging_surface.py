"""One module configures logging, and one module writes to a stream (FR-001, SC-010).

The companion of `test_environment_files.py`, which keeps configuration to one source. The same
argument applies here: the guarantees of ARCHITECTURE.md §18 and Principle V are properties of one
pipeline, and a component that installs its own handler or writes to standard error directly is
outside all of them — its output is neither structured nor redacted, and nothing about the log
says so.

Asserted against the committed tree by parsing the sources, not by grepping them: a comment
mentioning `basicConfig` must not fail this, and `logging  .  basicConfig()` must not pass it.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_ROOT = REPO_ROOT / "src" / "hermes_memory"
OBSERVABILITY = PACKAGE_ROOT / "observability"

FORBIDDEN_CALLS = {
    ("logging", "basicConfig"),
    ("logging", "config"),
    ("structlog", "configure"),
    ("structlog", "configure_once"),
}
"""Configuring the logging system. Permitted inside `observability/` and nowhere else."""

FORBIDDEN_ATTRIBUTES = {
    ("sys", "stdout"),
    ("sys", "stderr"),
}
"""Writing where records go. A module reaching for the stream is a module rendering its own
output, which by definition has not been through the redactor."""

FORBIDDEN_METHODS = {"addHandler", "setFormatter"}
"""Installing a handler anywhere but in the one place that owns the root logger."""


def _modules_outside_observability() -> list[Path]:
    return sorted(
        source
        for source in PACKAGE_ROOT.rglob("*.py")
        if OBSERVABILITY not in source.parents and source != OBSERVABILITY
    )


def _offences(source: Path) -> list[str]:
    """Every place in one module that steps outside the logging boundary."""
    tree = ast.parse(source.read_text(encoding="utf-8"))
    found: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            pair = (node.value.id, node.attr)
            if pair in FORBIDDEN_CALLS or pair in FORBIDDEN_ATTRIBUTES:
                found.append(f"line {node.lineno}: {pair[0]}.{pair[1]}")
        if isinstance(node, ast.Call):
            function = node.func
            if isinstance(function, ast.Attribute) and function.attr in FORBIDDEN_METHODS:
                found.append(f"line {function.lineno}: .{function.attr}()")

    return found


def test_nothing_outside_observability_configures_logging() -> None:
    """SC-010 — zero components outside the boundary configure logging or write records."""
    offences = {
        source.relative_to(REPO_ROOT).as_posix(): found
        for source in _modules_outside_observability()
        if (found := _offences(source))
    }

    assert not offences, (
        f"These modules reach around the logging boundary: {offences}. "
        "Use hermes_memory.observability.get_logger(); a record that does not pass through the "
        "pipeline is neither structured nor redacted."
    )


def test_the_check_would_notice_a_violation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A structure check nobody has seen fail is a structure check nobody can trust.

    Builds a package root holding one offending module outside `observability/` and insists it is
    reported — the same pattern `test_module_layout.py` uses for its behaviour guard.
    """
    fake_root = tmp_path / "hermes_memory"
    (fake_root / "ingestion").mkdir(parents=True)
    (fake_root / "ingestion" / "chatgpt.py").write_text(
        "import logging\n\n\ndef setup():\n    logging.basicConfig()\n",
        encoding="utf-8",
    )

    monkeypatch.setattr("tests.structure.test_logging_surface.PACKAGE_ROOT", fake_root)
    monkeypatch.setattr("tests.structure.test_logging_surface.OBSERVABILITY", fake_root / "obs")
    monkeypatch.setattr("tests.structure.test_logging_surface.REPO_ROOT", tmp_path)

    with pytest.raises(AssertionError, match="basicConfig"):
        test_nothing_outside_observability_configures_logging()
