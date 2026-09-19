"""The sanitizer reaches neither Hindsight, nor the network, nor storage (Principle IV).

`sanitization` is the one package that holds both an interface and its implementation: #9 declared
the boundary in `sanitizer.py`, and #11 fills the rest of the package with the patterns behind it.
So the allowlist here is the interface's, widened by nothing at all — a sanitizer needs the model it
rewrites, the error taxonomy, `re`, and its own siblings.

It is deliberately narrower than the ChatGPT source's sibling guard: this package does not log
(specs/009-secret-sanitizer/research.md R8), so `hermes_memory.observability` is absent from the
list, and an import of it fails this test rather than passing unnoticed.
"""

from __future__ import annotations

import sys
from pathlib import Path

from tests.structure.test_boundary_interfaces import FORBIDDEN_AT_RUNTIME, imported_roots

REPO_ROOT = Path(__file__).resolve().parents[2]
PACKAGE = REPO_ROOT / "src" / "hermes_memory" / "sanitization"

ALLOWED_THIRD_PARTY = frozenset({"pydantic"})

ALLOWED_INTERNAL = (
    "hermes_memory.errors",
    "hermes_memory.normalization",
    "hermes_memory.sanitization",
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


def test_the_sanitizer_imports_only_what_it_may() -> None:
    offenders = _offenders(PACKAGE)

    assert not offenders, (
        f"These imports are outside the allowlist: {offenders}. A sanitizer rewrites a "
        "conversation in memory; it reaches neither Hindsight, nor the network, nor storage "
        "(Principle IV), and it does not log (research R8)."
    )


def test_the_guard_still_bites(tmp_path: Path) -> None:
    (tmp_path / "leak.py").write_text(
        "import httpx\nimport hermes_memory.observability\n", encoding="utf-8"
    )

    assert _offenders(tmp_path) == [
        "leak.py: hermes_memory.observability",
        "leak.py: httpx",
    ]
