"""The six interface modules reach neither Hindsight, nor the network, nor storage.

Principle IV confines Hindsight to `memory/hindsight`, and these are the modules every other module
depends on: if one of them reached the engine, every consumer would reach it transitively and the
exit strategy of ADR-001 would be gone without a single line admitting it.

Three checks, because each catches what the others miss:

* **Static imports** — parses each interface module and holds it to an allowlist. Names the
  offending line; sees only direct imports.
* **Runtime imports** — imports each module in a subprocess and inspects `sys.modules`. Sees the
  true transitive closure; names the module that arrived rather than who asked for it.
* **Vocabulary** — no public name is a Hindsight term. A method called `retain_items` imports
  nothing forbidden and still binds every caller to the engine, which is what ADR-001 is written
  against. `retain` and `recall` themselves are kept: they are §16's words, and the architecture's.

Plus one that is about the taxonomy rather than the boundary: every error a boundary declares
derives from `TransientBoundaryError` or `PermanentBoundaryError`, so a new failure cannot enter
without answering §18's only question.

This is the sibling of `test_normalization_boundary.py`, and follows its shape deliberately.
"""

from __future__ import annotations

import ast
import inspect
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

import hermes_memory.archive as archive
import hermes_memory.classification as classification
import hermes_memory.ingestion as ingestion
import hermes_memory.memory.interface as memory_interface
import hermes_memory.sanitization as sanitization
from hermes_memory.errors import BoundaryError, PermanentBoundaryError, TransientBoundaryError

REPO_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_ROOT = REPO_ROOT / "src" / "hermes_memory"

INTERFACE_SOURCES = (
    "errors.py",
    "ingestion/source.py",
    "ingestion/state.py",
    "sanitization/sanitizer.py",
    "classification/classifier.py",
    "archive/interface.py",
    "memory/interface/store.py",
)
"""The files this feature adds to `src/`. Every one of them is an interface or the taxonomy."""

INTERFACE_MODULES = (
    "hermes_memory.errors",
    "hermes_memory.ingestion",
    "hermes_memory.sanitization",
    "hermes_memory.classification",
    "hermes_memory.archive",
    "hermes_memory.memory.interface",
)

BOUNDARY_PACKAGES = (
    ingestion,
    sanitization,
    classification,
    archive,
    memory_interface,
)

ALLOWED_THIRD_PARTY = frozenset({"pydantic"})
"""Pydantic only — the "Models and contracts" row of the stack table (ADR-004)."""

ALLOWED_INTERNAL = (
    "hermes_memory.errors",
    "hermes_memory.normalization",
    "hermes_memory.archive",
)
"""What an interface module may import from inside the package.

`hermes_memory.archive` is here for one reason, and it is worth stating rather than leaving to be
puzzled over: `ingestion/source.py` names `OriginalPayload`, because a source yields a conversation
together with the bytes it was read from and the archive is what those bytes are for (Principle I).
One interface naming another interface's value type is the dependency Principle IV wants — on the
declaration, never on an implementation.
"""

FORBIDDEN_AT_RUNTIME = (
    "hermes_memory.memory.hindsight",
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
"""`hermes_memory.memory.hindsight` rather than `hermes_memory.memory`: the interface lives under
that package, and forbidding the parent would forbid the module being checked."""

HINDSIGHT_TERMS = ("bank", "hindsight", "update_mode", "operation_id", "endpoint", "mission")
"""Terms that belong to the engine.

`retain` and `recall` are deliberately absent: ARCHITECTURE.md §16 uses both as the architecture's
own words for what a memory store does, and FR-009 keeps them. The rest name Hindsight's request
shape, and a public name carrying one would make #16's replacement a rewrite of its callers.
"""


def imported_roots(source: Path) -> set[str]:
    roots: set[str] = set()
    for node in ast.walk(ast.parse(source.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            roots.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            roots.add(node.module or "")
    return roots


def is_forbidden(imported: str) -> bool:
    return any(
        imported == forbidden or imported.startswith(f"{forbidden}.")
        for forbidden in FORBIDDEN_AT_RUNTIME
    )


def is_allowed(imported: str) -> bool:
    """The forbidden list is consulted first, because `sqlite3` and `urllib.request` are stdlib."""
    if is_forbidden(imported):
        return False

    root = imported.split(".")[0]
    return (
        root in sys.stdlib_module_names
        or root in ALLOWED_THIRD_PARTY
        or any(
            imported == allowed or imported.startswith(f"{allowed}.")
            for allowed in ALLOWED_INTERNAL
        )
    )


def interface_sources() -> list[Path]:
    return [PACKAGE_ROOT / relative for relative in INTERFACE_SOURCES]


def test_every_interface_source_exists() -> None:
    """A guard that found no files would report green while enforcing nothing."""
    missing = [str(source) for source in interface_sources() if not source.exists()]

    assert not missing, f"These interface sources are missing: {missing}."


def test_no_interface_imports_outside_the_allowlist() -> None:
    """FR-026, Principle IV. The static half."""
    offenders = [
        f"{source.relative_to(REPO_ROOT).as_posix()}: {imported}"
        for source in interface_sources()
        for imported in sorted(imported_roots(source))
        if not is_allowed(imported)
    ]

    assert not offenders, (
        f"These imports are outside the allowlist: {offenders}. An interface reaches neither "
        "Hindsight, nor the network, nor storage (ARCHITECTURE.md §8, Principle IV)."
    )


def test_the_static_guard_still_bites(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The guard fails on the case it exists for, watched rather than assumed."""
    fake_root = tmp_path / "hermes_memory"
    (fake_root / "archive").mkdir(parents=True)
    (fake_root / "archive" / "interface.py").write_text(
        "import httpx\nimport sqlite3\nfrom hermes_memory.memory.hindsight import Client\n",
        encoding="utf-8",
    )
    (fake_root / "errors.py").write_text("from pydantic import BaseModel\n", encoding="utf-8")

    monkeypatch.setattr("tests.structure.test_boundary_interfaces.PACKAGE_ROOT", fake_root)
    monkeypatch.setattr("tests.structure.test_boundary_interfaces.REPO_ROOT", tmp_path)
    monkeypatch.setattr(
        "tests.structure.test_boundary_interfaces.INTERFACE_SOURCES",
        ("errors.py", "archive/interface.py"),
    )

    with pytest.raises(AssertionError) as failure:
        test_no_interface_imports_outside_the_allowlist()

    reported = str(failure.value)
    assert "archive/interface.py: httpx" in reported
    assert "archive/interface.py: hermes_memory.memory.hindsight" in reported
    assert "archive/interface.py: sqlite3" in reported
    assert "errors.py" not in reported


@pytest.mark.parametrize("module", INTERFACE_MODULES)
def test_importing_an_interface_pulls_in_nothing_forbidden(module: str) -> None:
    """FR-026. The runtime half: the true transitive closure, in a fresh interpreter."""
    script = f"import {module}, sys; print('\\n'.join(sorted(sys.modules)))"
    finished = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, check=True
    )

    offenders = [
        name
        for name in finished.stdout.split()
        for forbidden in FORBIDDEN_AT_RUNTIME
        if name == forbidden or name.startswith(f"{forbidden}.")
    ]

    assert not offenders, (
        f"Importing {module} loaded {offenders}. Something it depends on reaches Hindsight, the "
        "network or storage, even if no source names it directly."
    )


@pytest.mark.parametrize("package", BOUNDARY_PACKAGES, ids=lambda package: package.__name__)
def test_no_exported_name_is_a_hindsight_term(package) -> None:
    """FR-009, MS-10. The vocabulary is the architecture's, so the engine stays replaceable."""
    offenders = sorted(
        name for name in package.__all__ for term in HINDSIGHT_TERMS if term in name.lower()
    )

    assert not offenders, (
        f"{package.__name__} exports Hindsight vocabulary: {offenders}. Only memory/hindsight "
        "speaks the engine's words (ADR-001, FR-009)."
    )


@pytest.mark.parametrize("package", BOUNDARY_PACKAGES, ids=lambda package: package.__name__)
def test_no_public_method_is_a_hindsight_term(package) -> None:
    """The same rule one level down: a method name binds a caller as firmly as a class name."""
    offenders = sorted(
        f"{name}.{attribute}"
        for name in package.__all__
        if inspect.isclass(getattr(package, name))
        for attribute in vars(getattr(package, name))
        if not attribute.startswith("_")
        for term in HINDSIGHT_TERMS
        if term in attribute.lower()
    )

    assert not offenders, (
        f"{package.__name__} has Hindsight vocabulary in its methods: {offenders}."
    )


@pytest.mark.parametrize(
    "package",
    # The classifier is absent on purpose: it declares no error, which
    # `test_the_classifier_declares_no_error_at_all` below is what holds it to (E8).
    [package for package in BOUNDARY_PACKAGES if package is not classification],
    ids=lambda package: package.__name__,
)
def test_every_declared_error_answers_the_retry_question(package) -> None:
    """E1, E2 — a boundary's failures live inside the taxonomy, or #20 cannot read them (§18)."""
    errors = [
        getattr(package, name)
        for name in package.__all__
        if inspect.isclass(getattr(package, name)) and issubclass(getattr(package, name), Exception)
    ]

    assert errors, f"{package.__name__} declares no errors; the list below would be vacuous."

    outside = [
        error.__name__
        for error in errors
        if not issubclass(error, TransientBoundaryError | PermanentBoundaryError)
    ]

    assert not outside, (
        f"{package.__name__} declares {outside} outside the taxonomy. Every boundary failure says "
        "whether retrying could succeed, by deriving from one of the two branches (E2, E3)."
    )


def test_the_classifier_declares_no_error_at_all() -> None:
    """E8 — §15 makes the unresolved project ordinary, so there is nothing here to fail."""
    errors = [
        name
        for name in classification.__all__
        if inspect.isclass(getattr(classification, name))
        and issubclass(getattr(classification, name), BoundaryError)
    ]

    assert not errors, (
        f"The classifier declares {errors}. §15 makes an unresolved project an ordinary answer — "
        "`project:unknown` — so an error type here is an invitation to make the common case "
        "exceptional (contracts/errors.md E8)."
    )


def test_the_vocabulary_guard_still_bites() -> None:
    """A name that would pass every import check and still bind its callers to the engine."""

    class BankConfig:
        pass

    named_boundary = SimpleNamespace(
        __name__="hermes_memory.pretend", __all__=["BankConfig"], BankConfig=BankConfig
    )

    with pytest.raises(AssertionError, match="BankConfig"):
        test_no_exported_name_is_a_hindsight_term(named_boundary)

    class Store:
        """Named innocently at the top level, with the engine's word on a method."""

        def mission_for_bank(self) -> None: ...

    method_boundary = SimpleNamespace(
        __name__="hermes_memory.pretend", __all__=["Store"], Store=Store
    )

    with pytest.raises(AssertionError, match="mission_for_bank"):
        test_no_public_method_is_a_hindsight_term(method_boundary)


def test_the_taxonomy_guard_still_bites() -> None:
    """An error outside the taxonomy answers §18's only question with silence."""

    class RawFailure(Exception):
        """What a boundary raises the day somebody forgets the two branches exist."""

    pretend_boundary = SimpleNamespace(
        __name__="hermes_memory.pretend", __all__=["RawFailure"], RawFailure=RawFailure
    )

    with pytest.raises(AssertionError, match="RawFailure"):
        test_every_declared_error_answers_the_retry_question(pretend_boundary)
