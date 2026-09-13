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


def test_no_runtime_dependencies() -> None:
    """The skeleton adds no runtime dependency (FR-011).

    This passes on an empty declaration and is meant to: its value is as a guard, so that the
    first feature to add a runtime dependency has to change this test on purpose rather than
    slipping one in. The stack table fixes which tool is used when one is needed; it does not
    mean all of them are pinned on day one.
    """
    dependencies = _pyproject()["project"].get("dependencies", [])

    assert dependencies == [], (
        f"The project skeleton declares runtime dependencies {dependencies!r}. "
        "Adding one is a deliberate change — update this test in the same commit."
    )
