# Research: Project Skeleton

**Feature**: `specs/001-project-skeleton` | **Date**: 2026-09-13

The stack is fixed by the constitution's Technology Stack section and ADR-004, so this phase
resolves only what those leave open. Each item below is a choice *within* the fixed stack, not a
change to it; none displaces an entry in the ADR-004 table, so none requires a new decision record.

---

## R1 — Name of the top-level Python package

**Decision**: distribution name `hermes-memory`, import package `hermes_memory`, laid out under
`src/`, so every module of ADR-004 is `src/hermes_memory/<module>/`.

**Rationale**: the constitution's tree is drawn with the root label `engineering-memory`, which is
the name of the *system* in ARCHITECTURE.md §1, not of a Python package — the tree's purpose there
is the module list and its nesting, and ADR-004 restates the same list with no root at all. The
repository, the GitHub project and the eventual distribution are all `hermes-memory`, and having
the import name disagree with all three buys nothing. Naming the package after the repository keeps
one name for one thing.

The `src/` layout is chosen because it is the arrangement that makes the installed package, rather
than the working directory, the thing under test: without it, `import hermes_memory` succeeds from
the repository root whether or not the packaging metadata is correct, and the first packaging
defect surfaces only in Docker. It also keeps `specs/`, `docs/` and `.specify/` from sitting as
siblings of importable code.

**Alternatives considered**:

- `engineering_memory` as the import name, matching the tree's root label literally. Rejected: it
  introduces a third name for one system and makes the repository harder to navigate, for the sake
  of a label that was never a package name.
- A flat layout with `hermes_memory/` at the repository root. Rejected for the reasons above; the
  saving is one directory level.

## R2 — Linter and formatter

**Decision**: Ruff, used both as the linter (`ruff check`) and the formatter (`ruff format
--check`), configured in `pyproject.toml`.

**Rationale**: ADR-004 names no linter and no formatter, so this displaces no fixed entry — it
fills a gap the record left open, which is a planning decision and not a stack change. Ruff covers
both roles in one dependency, which suits a constitution that optimises for time-to-experiment over
enterprise-platform consistency, and it comes from the same toolchain as `uv`, already fixed by
ADR-004, so the two are installed and pinned by the same mechanism.

**Alternatives considered**:

- Black plus Flake8 plus isort. Rejected: three dependencies, three configurations and three
  failure modes where one suffices, and it is slower on every run and in every CI job.
- A formatter only, with no linter. Rejected: FR-007 requires both, and the checks the constitution
  cares about (unused imports, an accidental cross-module dependency) are lint findings, not
  formatting ones.

**Deliberately not decided here**: a type checker. ADR-004 says maximum static typing is explicitly
not the optimisation target, and Principle III puts the weight on tests instead. Adding one is a
later decision with its own justification, not a silent addition to the skeleton.

## R3 — How the module layout is enforced

**Decision**: a test reads the fenced module tree out of `.specify/memory/constitution.md`, parses
it into a set of module paths, and compares that set against the packages actually present under
`src/hermes_memory/`. It fails on a module that is recorded but missing, and on a package that is
present but unrecorded. If the fence cannot be located or parsed, the test fails rather than
passing vacuously.

**Rationale**: FR-005 asks for agreement between the tree and "the recorded module layout". If the
test carried its own copy of the list, the repository would hold two records of one decision and
the check would only prove they matched each other. Reading the constitution makes it the single
source of truth, which is the same reasoning Principle I applies to the archive, and it means an
amendment to the constitution is what moves the check — exactly the behaviour the third acceptance
scenario of User Story 2 asks for.

**Alternatives considered**:

- The expected list hard-coded in the test. Rejected: a second source of truth for a decision the
  constitution already records, and it drifts silently.
- An import-linter contract enforcing the dependency directions of Principle IV as well. Not
  rejected on merit — it is the right tool for "only `memory/hindsight` knows about Hindsight" —
  but there is no code yet for it to constrain. It belongs to the feature that first writes an
  import, not to the skeleton.

**Parsing note**: the fence is an ASCII tree using `├──`, `└──` and `│` at two-space-per-level
indentation. Parsing is by indentation depth and connector, and unresolved lines make the test
fail; the tree is committed content that changes only by amendment, so this is deterministic.

## R4 — What "an empty module" contains

**Decision**: each module is a package directory with an `__init__.py` holding a one-line docstring
naming the boundary's responsibility, taken from ARCHITECTURE.md §8 where §8 names it. No imports,
no classes, no functions, no `__all__`.

**Rationale**: FR-004 forbids behaviour, and a docstring is not behaviour. It is also what makes
the boundary self-describing at the point where someone is about to add code to it, which is the
whole point of creating the modules early. `__init__.py` is required in any case for the package to
be importable and for the layout test to see it.

**Alternatives considered**: namespace packages with no `__init__.py`. Rejected: the module would
have nowhere to state what it is for, and implicit namespace packages make packaging errors quieter
rather than louder.

## R5 — Continuous integration shape

**Decision**: one GitHub Actions workflow, triggered on `pull_request` against `main` and on
`push` to `main`, running on `ubuntu-latest`: install `uv` at a pinned action version, install the
Python version from `.python-version`, `uv sync --locked`, then `ruff check`, `ruff format
--check`, and `pytest`. `permissions: contents: read`, and a concurrency group that cancels
superseded runs on the same ref.

**Rationale**: `--locked` is the load-bearing flag — it fails when `uv.lock` disagrees with
`pyproject.toml` instead of quietly re-resolving, which is what makes FR-009 true and what makes a
local pass and a CI pass mean the same thing. Pinning the Python version through `.python-version`
rather than a matrix keeps one runtime, as the constitution fixes exactly one. The workflow reads
no secrets, so it runs unchanged on pull requests from forks, per the spec's edge case.

**Alternatives considered**:

- A version matrix across several Python releases. Rejected: the constitution fixes 3.13; testing
  releases the project does not support reports failures nobody will act on.
- Separate workflows for lint and for tests. Rejected: two jobs would each pay the install cost,
  and the pull request gains two checks where one answers the question.
- Running the checks from a pre-commit framework instead. Rejected for now: it adds a dependency
  and a second place where the check commands are written down. The commands live in
  `pyproject.toml` and the workflow calls them.

## R6 — pytest on a suite with no tests

**Finding**: `pytest` exits with code 5 ("no tests collected") on a genuinely empty suite, which CI
reads as failure. The spec's "green on an empty suite" (FR-006) therefore needs care.

**Decision**: the suite is not empty — this feature is written test-first per Principle III, and its
own tests (the module-layout check of R3, and a check that the packaging metadata resolves) are
real tests that exist before the code they describe. No `--exitfirst`-style workaround and no
placeholder test is introduced.

**Rationale**: a placeholder `test_nothing` that asserts `True` would make the suite pass while
proving nothing, and would still be in the repository years later. The honest reading of FR-006 is
that the test command must succeed on the committed tree, which it does because the tree carries
tests worth running.

## R7 — Where the commands are written down

**Decision**: `README.md` gains a short "Development" section with the three commands — `uv sync`,
`uv run pytest`, `uv run ruff check . && uv run ruff format --check .` — and the required Python
version. `CLAUDE.md` is not the place: it holds working agreements, and a first-time human
contributor reads the README.

**Rationale**: FR-010 asks for "a place a first-time contributor will find". That is the README.
