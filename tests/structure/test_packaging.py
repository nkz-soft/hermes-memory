"""The project's packaging metadata says what the constitution says it must.

These assertions exist because the alternative is prose. The runtime version is fixed by the
constitution's Technology Stack table, and a pin that drifts from it is invisible until someone
runs on the wrong interpreter and gets a different answer than CI did.
"""

from __future__ import annotations

import tomllib
from importlib.util import find_spec
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PYPROJECT = REPO_ROOT / "pyproject.toml"
PYTHON_VERSION_FILE = REPO_ROOT / ".python-version"

REQUIRED_PYTHON = "==3.13.*"
"""Fixed by .specify/memory/constitution.md, Technology Stack: Runtime | Python 3.13."""


def _pyproject() -> dict:
    return tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))


def _distribution_name(requirement: str) -> str:
    """The distribution name out of a PEP 508 requirement string.

    Deliberately small: the declarations here are plain ``name>=version`` strings, and pulling in
    a full requirement parser to split on the first specifier character would be a dependency
    added to check the dependency list.
    """
    for separator in ("[", "<", ">", "=", "!", "~", ";", " "):
        requirement = requirement.split(separator, 1)[0]
    return requirement.strip().lower().replace("_", "-")


def test_requires_python_pins_313() -> None:
    """The metadata pins exactly the one runtime the constitution fixes."""
    requires_python = _pyproject()["project"].get("requires-python")

    assert requires_python == REQUIRED_PYTHON, (
        f"pyproject.toml declares requires-python = {requires_python!r}, "
        f"but the constitution fixes Python 3.13, which is {REQUIRED_PYTHON!r}."
    )


def test_python_version_file_agrees_with_metadata() -> None:
    """`.python-version` and `requires-python` name the same interpreter.

    They are read by different things — the version file by `uv` and by the CI setup step, the
    metadata by the build — so agreement between them is what makes a local pass and a CI pass
    mean the same thing (FR-009).
    """
    assert PYTHON_VERSION_FILE.exists(), (
        ".python-version is missing; uv and CI would each choose their own interpreter."
    )

    pinned = PYTHON_VERSION_FILE.read_text(encoding="utf-8").strip()

    assert pinned == "3.13", f".python-version names {pinned!r}, expected '3.13'."

    major_minor = REQUIRED_PYTHON.removeprefix("==").removesuffix(".*")
    assert pinned == major_minor, (
        f".python-version ({pinned}) and requires-python ({REQUIRED_PYTHON}) disagree."
    )


def test_package_is_importable_from_src_layout() -> None:
    """The installed package, not the working directory, is what the suite imports.

    Under a flat layout this passes whether or not the packaging metadata is correct, and the
    first packaging defect surfaces in Docker instead of here (research.md R1).
    """
    spec = find_spec("hermes_memory")

    assert spec is not None, (
        "hermes_memory is not importable; the package is not installed into the environment."
    )
    assert spec.origin is not None, "hermes_memory resolved to a namespace package, not a package."

    origin = Path(spec.origin).resolve()
    assert "src" in origin.parts, (
        f"hermes_memory resolved to {origin}, which is not under a src/ directory."
    )


EXPECTED_RUNTIME_DEPENDENCIES = frozenset({"pydantic", "pydantic-settings"})
"""Every runtime dependency the project is allowed to declare, by distribution name.

The skeleton declared none, and this test asserted that. 002-environment-configuration is the
feature that added the first two, under the sentence the previous version of this docstring wrote
for exactly that purpose. Both are the Pydantic v2 entry the constitution's Technology Stack table
already fixes — `pydantic-settings` is the part of it carrying `BaseSettings`, separated at the
v1→v2 split for packaging reasons (specs/002-environment-configuration/research.md R2).
"""


def test_runtime_dependencies_are_exactly_the_declared_set() -> None:
    """The runtime dependency list holds what the plans say it holds, and nothing else.

    Still a guard, now with something to guard. Its value is unchanged: a dependency that
    displaces a fixed stack entry, or that arrives with no decision behind it, has to change this
    test on purpose rather than slipping into the lock file where nobody reads it.
    """
    declared = _pyproject()["project"].get("dependencies", [])
    names = frozenset(_distribution_name(requirement) for requirement in declared)

    assert names == EXPECTED_RUNTIME_DEPENDENCIES, (
        f"Runtime dependencies are {sorted(names)}, expected "
        f"{sorted(EXPECTED_RUNTIME_DEPENDENCIES)}. Adding or removing one is a deliberate change "
        "— update this test in the same commit, and say in the pull request which decision "
        "record permits it."
    )
