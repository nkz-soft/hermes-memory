"""The normalization module reaches neither Hindsight, nor the network, nor storage.

Principle IV confines Hindsight to `memory/hindsight`, and the constitution's merge gate obliges a
reviewer to reject a Hindsight reference outside the memory store. A reviewer needs a failing test
for that, not an argument — and ADR-001's exit strategy is worth only as much as the boundary that
keeps it possible.

Two checks, because each catches what the other misses:

* **Static** — parses this module's own imports and holds them to an allowlist. Readable, and it
  names the offending line; but it sees only what this module asks for directly, so a helper
  imported from elsewhere in the package could launder `httpx` past it.
* **Runtime** — imports the package in a subprocess and inspects that process's `sys.modules`. Sees
  the true transitive closure and cannot be argued with; but it reports a module that arrived
  rather than the line that asked for it.

`test_the_static_guard_still_bites` proves the first one fails when it should, because a guard
nobody has watched fail is a guard nobody knows is working.
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

import pytest

import hermes_memory.normalization as normalization

REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_ROOT = REPO_ROOT / "src" / "hermes_memory" / "normalization"

ALLOWED_THIRD_PARTY = frozenset({"pydantic"})
"""Everything outside the standard library this module may import.

Pydantic is the "Models and contracts" row of the stack table. Adding a second entry here is a
change to what the domain model depends on, which the constitution makes a decision rather than a
commit.
"""

INTERNAL_PREFIX = "hermes_memory.normalization"

FORBIDDEN_AT_RUNTIME = (
    "hermes_memory.memory",
    "hermes_memory.settings",
    "httpx",
    "requests",
    "urllib.request",
    "urllib3",
    "aiohttp",
    "socket",
    "http.client",
    "sqlalchemy",
    "sqlite3",
    "shelve",
    "dbm",
    "boto3",
)
"""Named explicitly because these are the ones that would actually be reached for.

`hermes_memory.memory` — Principle IV: only the memory store knows Hindsight. The HTTP clients and
`urllib.request` — §8: the domain model makes no calls. The storage libraries — §8: it persists
nothing. `hermes_memory.settings` — FR-018: a model that reads configuration is a model that cannot
be constructed in a test.
"""

HINDSIGHT_TERMS = ("bank", "retain", "recall", "hindsight", "update_mode", "item")
"""Vocabulary that would bind the domain to the engine even with every import check passing.

A model called `RetainItem` imports nothing forbidden and still makes replacing Hindsight a
rewrite of the pipeline, which is exactly what ADR-001's exit strategy is written against.
"""


def imported_roots(source: Path) -> set[str]:
    """The root module of every import in one file.

    A relative import is internal to this module by construction, so it is reported as the internal
    prefix rather than skipped — skipping is how a check quietly stops seeing a category.
    """
    roots: set[str] = set()

    for node in ast.walk(ast.parse(source.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            roots.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            roots.add(INTERNAL_PREFIX if node.level else (node.module or ""))

    return roots


def is_forbidden(imported: str) -> bool:
    return any(
        imported == forbidden or imported.startswith(f"{forbidden}.")
        for forbidden in FORBIDDEN_AT_RUNTIME
    )


def is_allowed(imported: str) -> bool:
    """Whether one import is permitted here.

    The forbidden list is consulted *first*, and that ordering is the point. `sqlite3` and
    `urllib.request` are standard library, so a check that asked only "is this stdlib?" would wave
    through the two most likely ways for storage and the network to enter the domain model — which
    is exactly what happened when this guard was first watched against a real violation: the
    runtime half reported `sqlite3` and the static half said nothing.
    """
    if is_forbidden(imported):
        return False

    root = imported.split(".")[0]
    return (
        root in sys.stdlib_module_names
        or root in ALLOWED_THIRD_PARTY
        or imported == INTERNAL_PREFIX
        or imported.startswith(f"{INTERNAL_PREFIX}.")
    )


def module_sources(root: Path) -> list[Path]:
    return sorted(root.rglob("*.py"))


def test_the_module_has_sources_to_check() -> None:
    """A guard that found no files would report green while enforcing nothing."""
    assert module_sources(MODULE_ROOT), f"No Python sources found under {MODULE_ROOT}."


def test_no_source_imports_outside_the_allowlist() -> None:
    """FR-016, Principle IV. The static half."""
    offenders = [
        f"{source.relative_to(REPO_ROOT).as_posix()}: {imported}"
        for source in module_sources(MODULE_ROOT)
        for imported in sorted(imported_roots(source))
        if not is_allowed(imported)
    ]

    assert not offenders, (
        f"These imports are outside the allowlist: {offenders}. The domain model reaches neither "
        "Hindsight, nor the network, nor storage (ARCHITECTURE.md §8, Principle IV)."
    )


def test_the_static_guard_still_bites(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The guard fails on the case it exists for, watched rather than assumed.

    Follows the precedent of `test_the_behaviour_guard_still_bites` in `test_module_layout.py`:
    the check passes the moment it is written, because the module is clean, so the only way to
    know it works is to build the violation and see it reported.
    """
    fake_root = tmp_path / "normalization"
    fake_root.mkdir()
    (fake_root / "clean.py").write_text("from pydantic import BaseModel\n", encoding="utf-8")
    (fake_root / "leaky.py").write_text(
        "import httpx\nimport sqlite3\nfrom hermes_memory.memory.hindsight import Client\n",
        encoding="utf-8",
    )

    monkeypatch.setattr("tests.structure.test_normalization_boundary.MODULE_ROOT", fake_root)
    monkeypatch.setattr("tests.structure.test_normalization_boundary.REPO_ROOT", tmp_path)

    with pytest.raises(AssertionError) as failure:
        test_no_source_imports_outside_the_allowlist()

    reported = str(failure.value)
    assert "leaky.py: httpx" in reported
    assert "leaky.py: hermes_memory.memory.hindsight" in reported
    # Standard library, and still forbidden: storage reaches the domain model through `sqlite3`
    # long before it reaches it through anything exotic.
    assert "leaky.py: sqlite3" in reported
    assert "clean.py" not in reported


def test_importing_the_module_pulls_in_nothing_forbidden() -> None:
    """FR-016, FR-018. The runtime half: the true transitive closure, in a fresh interpreter."""
    script = "import hermes_memory.normalization, sys; print('\\n'.join(sorted(sys.modules)))"
    finished = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, check=True
    )
    loaded = finished.stdout.split()

    offenders = [
        name
        for name in loaded
        for forbidden in FORBIDDEN_AT_RUNTIME
        if name == forbidden or name.startswith(f"{forbidden}.")
    ]

    assert not offenders, (
        f"Importing hermes_memory.normalization loaded {offenders}. Something it depends on "
        "reaches Hindsight, the network or storage, even if no source here names it directly."
    )


def test_the_module_imports_without_configuration() -> None:
    """FR-018. No environment variable, no file, no service — or it cannot be used in a test.

    Run with an emptied environment rather than the ambient one, so a value that happens to be set
    on this machine cannot make a configuration dependency look absent.
    """
    finished = subprocess.run(
        [sys.executable, "-c", "import hermes_memory.normalization"],
        capture_output=True,
        text=True,
        env={"PATH": "", "SYSTEMROOT": ""},
    )

    assert finished.returncode == 0, finished.stderr


def public_names() -> set[str]:
    return {name for name in vars(normalization) if not name.startswith("_")}


def test_every_exported_name_exists() -> None:
    """An `__all__` entry with nothing behind it fails at the boundary, not at a call site."""
    missing = sorted(set(normalization.__all__) - public_names())

    assert not missing, f"Named in __all__ but not present: {missing}."


def test_every_public_name_is_exported() -> None:
    """The other direction: a name added to the module without being exported.

    Submodules are excluded — importing `normalization.canonical` binds `canonical` as an attribute
    of the package, and that is Python's doing rather than a public name this module chose.
    """
    submodules = {"base", "canonical", "conversation", "provenance", "tags"}
    unexported = sorted(public_names() - set(normalization.__all__) - submodules)

    assert not unexported, (
        f"Public but not in __all__: {unexported}. The module's surface is what it exports; "
        "a name that drifts in is a name no consumer was promised."
    )


def test_no_exported_name_is_a_hindsight_term() -> None:
    """FR-017. The vocabulary is the architecture's, so the engine stays replaceable."""
    offenders = sorted(
        name for name in normalization.__all__ for term in HINDSIGHT_TERMS if term in name.lower()
    )

    assert not offenders, (
        f"These exported names carry Hindsight vocabulary: {offenders}. The domain model speaks "
        "the architecture's words; only memory/hindsight speaks the engine's (ADR-001)."
    )
