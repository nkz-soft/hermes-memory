"""The module tree on disk agrees with the module tree the constitution records.

The list this check *enforces* is not written down here. It is parsed out of
`.specify/memory/constitution.md`, so the constitution stays the single record of that decision
and amending it is what moves this check (research.md R3, FR-005).

There is a literal list of the fifteen modules further down, in
`test_constitution_tree_parses_to_the_recorded_modules`. It exists to pin the *parser*, not to
enforce the layout — nothing else compares against it — so that a parser bug cannot quietly
turn the real check into a weaker one. Amending the constitution's tree means updating that
test in the same commit, deliberately.

The invariant runs in both directions: a recorded module that is missing fails, and a package on
disk that nothing recorded fails too.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
CONSTITUTION = REPO_ROOT / ".specify" / "memory" / "constitution.md"
PACKAGE_ROOT = REPO_ROOT / "src" / "hermes_memory"

_FENCE = re.compile(r"^```text\n(.*?)^```", re.MULTILINE | re.DOTALL)
_BRANCH = re.compile(r"^((?:│   |    )*)(?:├── |└── )(\S+)$")
_INDENT = 4


class ModuleTreeError(AssertionError):
    """The recorded tree could not be located or read.

    Deliberately an AssertionError: an unreadable record must fail the suite, never let it pass
    on an empty set. A check that cannot find what it checks against is worse than no check.
    """


def recorded_modules() -> frozenset[str]:
    """Parse the module tree out of the constitution into dotted module paths.

    Returns paths relative to the package root, e.g. ``ingestion.chatgpt``. The tree's own root
    line is a label for the system, not a package, and is discarded.
    """
    if not CONSTITUTION.exists():
        raise ModuleTreeError(f"The constitution is missing at {CONSTITUTION}.")

    text = CONSTITUTION.read_text(encoding="utf-8")
    # Match on the connector's trailing "── " rather than on "├── " specifically: a tree with a
    # single child at every level would use only "└── " and would otherwise go unrecognised.
    candidates = [block for block in _FENCE.findall(text) if "── " in block]

    if len(candidates) != 1:
        raise ModuleTreeError(
            f"Expected exactly one fenced module tree in {CONSTITUTION.name}, "
            f"found {len(candidates)}. The parser cannot tell which one records the layout."
        )

    lines = [line for line in candidates[0].splitlines() if line.strip()]
    if not lines:
        raise ModuleTreeError("The fenced module tree is empty.")

    modules: set[str] = set()
    ancestors: list[str] = []

    for line in lines[1:]:  # lines[0] is the tree's root label, not a package
        match = _BRANCH.match(line)
        if match is None:
            raise ModuleTreeError(
                f"Could not parse this line of the recorded module tree: {line!r}. "
                "The parser must not guess — fix the tree or fix the parser."
            )

        indent, name = match.groups()
        depth = len(indent) // _INDENT

        if depth > len(ancestors):
            raise ModuleTreeError(f"The recorded tree skips an indentation level at: {line!r}")

        ancestors = ancestors[:depth]
        modules.add(".".join([*ancestors, name]))
        ancestors.append(name)

    return frozenset(modules)


def present_modules() -> frozenset[str]:
    """Every module directory under the package root, as dotted paths relative to it.

    Found by looking for directories containing *any* Python file, not by looking for
    ``__init__.py``. A directory without one is still importable as an implicit namespace
    package, so keying on ``__init__.py`` would let an unrecorded module — with behaviour in
    it — sit under the package root unseen. ``test_every_module_is_a_real_package`` then
    insists each one has its ``__init__.py``.
    """
    return frozenset(
        source.parent.relative_to(PACKAGE_ROOT).as_posix().replace("/", ".")
        for source in PACKAGE_ROOT.rglob("*.py")
        if source.parent != PACKAGE_ROOT
    )


def test_constitution_tree_parses_to_the_recorded_modules() -> None:
    """Pin the parser itself, so a parser bug cannot quietly weaken the layout check."""
    expected = {
        "api",
        "cli",
        "ingestion",
        "ingestion.chatgpt",
        "ingestion.claude_code",
        "ingestion.codex",
        "normalization",
        "sanitization",
        "classification",
        "archive",
        "memory",
        "memory.interface",
        "memory.hindsight",
        "evaluation",
        "observability",
    }

    assert recorded_modules() == expected, (
        "The parser no longer reads the constitution's module tree as expected. "
        "Either the tree was amended — in which case update this test in the same commit — "
        "or the parser is wrong."
    )


def test_an_unreadable_record_fails_loudly(tmp_path, monkeypatch) -> None:
    """A record the parser cannot read must fail, never yield an empty set.

    This is the failure mode that matters: an empty recorded set would make
    ``test_every_recorded_module_exists`` pass on any tree at all, and the check would go on
    reporting green while enforcing nothing.
    """
    # The dotted target below assumes pytest's default "prepend" import mode, under which this
    # file is importable as tests.structure.test_module_layout. Switching to importmode=importlib
    # would break these three lines — loudly, which is the acceptable kind.
    missing = tmp_path / "gone.md"
    monkeypatch.setattr("tests.structure.test_module_layout.CONSTITUTION", missing)
    with pytest.raises(ModuleTreeError):
        recorded_modules()

    no_fence = tmp_path / "no-fence.md"
    no_fence.write_text("# A constitution with no module tree\n", encoding="utf-8")
    monkeypatch.setattr("tests.structure.test_module_layout.CONSTITUTION", no_fence)
    with pytest.raises(ModuleTreeError):
        recorded_modules()

    unparsable = tmp_path / "unparsable.md"
    unparsable.write_text(
        "```text\nroot\n├── api\n  wat\n```\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("tests.structure.test_module_layout.CONSTITUTION", unparsable)
    with pytest.raises(ModuleTreeError):
        recorded_modules()


def test_every_recorded_module_exists() -> None:
    """Every module the constitution records is present on disk (FR-003)."""
    missing = sorted(recorded_modules() - present_modules())

    assert not missing, (
        f"Recorded in the constitution but missing under src/hermes_memory/: {missing}. "
        "The boundaries of ADR-004 exist before anything fills them, not after."
    )


def test_no_unrecorded_modules_exist() -> None:
    """No package exists that the constitution does not record (FR-003, FR-005).

    This is the direction that keeps the layout from growing by accident. Adding a module is
    an amendment to the constitution first, and a directory second.
    """
    surplus = sorted(present_modules() - recorded_modules())

    assert not surplus, (
        f"Present under src/hermes_memory/ but recorded nowhere: {surplus}. "
        "Amend the constitution's module tree, or remove the package."
    )


def test_every_module_is_a_real_package() -> None:
    """No module relies on being an implicit namespace package (research.md R4).

    A directory of Python files without an ``__init__.py`` still imports, but it has nowhere to
    state what boundary it is, and it makes packaging mistakes quieter rather than louder.
    """
    not_packages = sorted(
        module
        for module in present_modules()
        if not (PACKAGE_ROOT / Path(module.replace(".", "/")) / "__init__.py").exists()
    )

    assert not not_packages, (
        f"These directories hold Python files but no __init__.py: {not_packages}. "
        "Add one with a docstring naming the boundary, or remove the directory."
    )


def test_modules_carry_no_behaviour() -> None:
    """Each module is a boundary and nothing else (FR-004, SC-007).

    A docstring is not behaviour; an import, a class, a function or an assignment is. This is
    what keeps the skeleton from quietly becoming an implementation.

    Every ``.py`` file under the package root is inspected, not only ``__init__.py``: the guard
    is worth nothing if behaviour can be added in a sibling module. The first feature to write
    real code changes this test on purpose — the same deliberate-change guard that
    ``test_no_runtime_dependencies`` uses.
    """
    offenders: list[str] = []

    for source in sorted(PACKAGE_ROOT.rglob("*.py")):
        body = ast.parse(source.read_text(encoding="utf-8")).body
        docstring_only = len(body) <= 1 and (not body or ast.get_docstring(ast.Module(body, [])))

        if not docstring_only:
            offenders.append(source.relative_to(REPO_ROOT).as_posix())

    assert not offenders, (
        f"These modules contain more than a docstring: {offenders}. "
        "The skeleton establishes boundaries; behaviour arrives with the feature that needs it."
    )
