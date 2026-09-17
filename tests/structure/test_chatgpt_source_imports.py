"""The ChatGPT source reaches neither Hindsight, nor the network, nor storage (Principle IV).

It is an implementation, not an interface, so it may use more than an interface may: the logging
boundary, and its own sibling modules. What it may not use is the same list that holds the
interfaces — and it is not re-exported by `hermes_memory.ingestion`, so importing the interface
never loads an implementation (specs/008-chatgpt-export-source/tasks.md T002).
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

from tests.structure.test_boundary_interfaces import FORBIDDEN_AT_RUNTIME, imported_roots

REPO_ROOT = Path(__file__).resolve().parents[2]
PACKAGE = REPO_ROOT / "src" / "hermes_memory" / "ingestion" / "chatgpt"
INGESTION_INIT = REPO_ROOT / "src" / "hermes_memory" / "ingestion" / "__init__.py"

ALLOWED_THIRD_PARTY = frozenset({"pydantic"})

ALLOWED_INTERNAL = (
    "hermes_memory.errors",
    "hermes_memory.normalization",
    "hermes_memory.archive.interface",
    "hermes_memory.archive",
    "hermes_memory.ingestion.source",
    "hermes_memory.ingestion.chatgpt",
    "hermes_memory.observability",
)


def _is_forbidden(imported: str) -> bool:
    return any(
        imported == forbidden or imported.startswith(f"{forbidden}.")
        for forbidden in FORBIDDEN_AT_RUNTIME
    )


def _is_allowed(imported: str) -> bool:
    if _is_forbidden(imported):
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


def _offenders(package: Path) -> list[str]:
    return [
        f"{source.name}: {imported}"
        for source in sorted(package.rglob("*.py"))
        for imported in sorted(imported_roots(source))
        if not _is_allowed(imported)
    ]


def test_the_chatgpt_source_imports_only_what_it_may() -> None:
    offenders = _offenders(PACKAGE)

    assert not offenders, (
        f"These imports are outside the allowlist: {offenders}. A source reads an export; it "
        "reaches neither Hindsight, nor the network, nor storage (Principle IV)."
    )


def test_the_guard_still_bites(tmp_path: Path) -> None:
    (tmp_path / "leak.py").write_text("import httpx\nimport sqlite3\n", encoding="utf-8")

    assert _offenders(tmp_path) == ["leak.py: httpx", "leak.py: sqlite3"]


def test_the_interface_package_does_not_load_the_implementation() -> None:
    tree = ast.parse(INGESTION_INIT.read_text(encoding="utf-8"))
    imported = {
        node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
    } | {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }

    assert not [name for name in imported if "chatgpt" in name]


@pytest.mark.parametrize("name", ["hermes_memory.ingestion.chatgpt"])
def test_the_package_exposes_only_the_source(name: str) -> None:
    module = __import__(name, fromlist=["__all__"])

    assert getattr(module, "__all__", ()) == ["ChatGPTExportSource"]
