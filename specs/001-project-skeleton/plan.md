# Implementation Plan: Project Skeleton

**Branch**: `001-project-skeleton` | **Date**: 2026-09-13 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/001-project-skeleton/spec.md`, derived from GitHub
issue #4 (Phase 1, wave 1; blocks #5, #6, #7, #8).

## Summary

Create the Python project skeleton so that the boundaries of ADR-004 exist before any code fills
them: `uv` with a committed lock file on Python 3.13, the recorded module tree under
`src/hermes_memory/`, Ruff as linter and formatter, pytest, and one GitHub Actions workflow running
all of it on every pull request.

The approach has one idea in it beyond the obvious. The module layout is not re-typed into a test —
the test parses it out of the constitution's own fenced tree, so the constitution stays the single
record of the decision and an amendment to it is what moves the check. Everything else is
assembly: no runtime dependency, no behaviour, no configuration for any external service.

## Technical Context

**Language/Version**: Python 3.13, pinned by `.python-version` and `requires-python == 3.13.*`
(constitution, Technology Stack).

**Primary Dependencies**: none at runtime. Development only: `pytest` (fixed by ADR-004), `ruff`
(selected in [research.md](research.md) R2 — ADR-004 names no linter, so this displaces nothing).

**Storage**: N/A. No persistence in this feature.

**Testing**: pytest, invoked as `uv run pytest`.

**Target Platform**: developer machines (Windows, macOS, Linux) and `ubuntu-latest` in CI. The
checks are platform-independent; the layout test uses `pathlib`, not shell.

**Project Type**: single Python package, `src/` layout, modular monolith per ADR-004.

**Performance Goals**: N/A — no code path to measure. The relevant budget is contributor time: the
full check set should finish in well under a minute on a warm environment.

**Constraints**: no runtime dependency added; no credential, secret or external service touched; no
behaviour in any module (FR-004, FR-011). CI must run on fork pull requests, so it reads no secret.

**Scale/Scope**: 14 module packages, 4 checks, ~10 committed files. No feature code.

## Constitution Check

*GATE: passed before Phase 0 research; re-evaluated after Phase 1 design — see below.*

The feature adds no behaviour, so several principles are satisfied by construction rather than by
argument. Stating each anyway, because the constitution requires the plan to.

| Principle | Compliance |
|---|---|
| **I — Raw Archive Is the Source of Truth** | Not engaged: no ingestion, no archive, no `retain`. The `archive` module is created empty. Nothing here creates a second record of history, because it records no history. The spirit of the principle *is* applied to the module layout (R3): one record of the decision, in the constitution, read rather than copied. |
| **II — Provenance and Stable Identity** | Not engaged: no retained item, no `document_id`, no timestamp. Nothing in this feature can generate an identifier, stable or otherwise. |
| **III — Test-First (NON-NEGOTIABLE)** | Engaged, and governs the task order. The module-layout test and the packaging-metadata test are written first and observed to fail — the layout test against an empty `src/`, the metadata test before `pyproject.toml` exists — before the tree and the metadata are created. The task list orders it that way explicitly; a task that creates a module before its test fails is not done. The principle's *minimum coverage* clause names parser, sanitizer, contract and end-to-end tests as prerequisites for a pipeline stage being done — this feature completes no pipeline stage, so that clause does not bind it, and each named test arrives with the stage it covers. |
| **IV — Replaceable Boundaries** | Engaged, and this is the feature's purpose. Every boundary of §8 gets its module before anything imports across one. No module imports another — no module imports anything at all — so no dependency direction is established that a later feature would have to undo. `memory/hindsight` and `memory/interface` exist as separate packages from the first commit, so the one place permitted to know about Hindsight is already fenced off. The import-state boundary of §8 has no module in the recorded layout and is deliberately not invented here; adding one would be an unrecorded module and the layout test would reject it. Enforcing the dependency *directions* automatically (import-linter) is deferred to the first feature that writes an import — see R3. |
| **V — Secrets Never Reach the Memory Engine** | Engaged negatively and satisfied: no content leaves the process, no credential is read, and no file in this feature holds one. The CI workflow declares `permissions: contents: read` and consumes no repository secret, which is also what lets it run on fork pull requests. `data/` remains ignored and untouched. Gitleaks, named in the stack table, is a scanning tool rather than a skeleton component; wiring it in is a separate change and is called out under Deferred below. |

**Technology Stack compliance**: every fixed entry this feature touches is used as fixed — Python
3.13, `uv`, pytest. It adds one tool the table does not name (Ruff) and displaces none, so the
"changing any entry, or adding a dependency that displaces one" clause is not triggered and no new
decision record is required. This matches the issue's Governance impact: "None of the above". FastAPI,
Typer, Pydantic, httpx, SQLAlchemy, Tenacity, structlog, OpenTelemetry, testcontainers and Docker
are all deliberately absent — the stack table fixes *which* tool is used when one is needed, not
that all of them are installed on day one, and each arrives with the feature that needs it. Adding
them now would put unused pins in the lock file and make `uv sync` slower for no benefit.

**Branch naming**: `001-project-skeleton`, matching the feature directory, per the Development
Workflow section. Created by hand because the `before_specify` hook is not installed here.

**Post-design re-evaluation**: unchanged. Phase 1 introduced no dependency, no interface and no
behaviour beyond what is listed above. The one design decision with any weight — parsing the
constitution rather than copying its list — moved the design *towards* Principle I's reasoning
rather than away from it. No violations; the Complexity Tracking table below stays empty.

## Alternatives Considered

The issue records one rejected alternative, and the research phase produced several more. The full
reasoning is in [research.md](research.md); the summary:

| Alternative | Rejected because |
|---|---|
| **Let the first feature create whatever structure it needs** (the issue's alternative) | The layout is a decision already recorded in ADR-004. Re-deriving it per feature is how a module ends up importing Hindsight from the wrong side of Principle IV — and by the time that shows up, three features have each built half a layout and the cost of reconciling them is paid in rewrites rather than in one afternoon of scaffolding. |
| `engineering_memory` as the import package name (R1) | A third name for one system, for the sake of a label in a diagram that was never a package name. |
| Flat layout instead of `src/` (R1) | Makes `import hermes_memory` succeed regardless of whether packaging is correct, so the first packaging defect surfaces in Docker instead of in CI. |
| Black + Flake8 + isort instead of Ruff (R2) | Three dependencies and three configurations where one suffices, and slower on every run. |
| Adding a type checker now (R2) | ADR-004 states maximum static typing is explicitly not the target. A later decision with its own justification, not a silent addition. |
| Hard-coding the expected module list in the test (R3) | A second source of truth for a decision the constitution already records; the check would only prove the two copies matched each other. |
| An import-linter contract for Principle IV's directions now (R3) | The right tool, but there is no import yet for it to constrain. It belongs to the feature that writes the first one. |
| A placeholder `test_nothing` to keep an empty suite green (R6) | Would make the suite pass while proving nothing, and would outlive everyone's memory of why it exists. The suite is not empty: this feature is written test-first. |
| A Python version matrix in CI (R5) | The constitution fixes exactly one runtime; testing unsupported releases reports failures nobody will act on. |
| Pre-commit framework instead of direct commands (R5) | A second place where the check commands are written down. |

## Project Structure

### Documentation (this feature)

```text
specs/001-project-skeleton/
├── spec.md              # Feature specification
├── plan.md              # This file
├── research.md          # Phase 0 output — R1..R7
├── data-model.md        # Phase 1 output — the feature's own artifacts
├── quickstart.md        # Phase 1 output — how to validate the deliverable
├── contracts/
│   └── checks.md        # Phase 1 output — the four checks and their guarantees
├── checklists/
│   └── requirements.md  # Specification quality checklist
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
pyproject.toml               # Project metadata, Ruff and pytest configuration
uv.lock                      # Committed, exact resolution
.python-version              # 3.13

src/
└── hermes_memory/
    ├── __init__.py
    ├── api/
    ├── cli/
    ├── ingestion/
    │   ├── chatgpt/
    │   ├── claude_code/
    │   └── codex/
    ├── normalization/
    ├── sanitization/
    ├── classification/
    ├── archive/
    ├── memory/
    │   ├── interface/
    │   └── hindsight/
    ├── evaluation/
    └── observability/

tests/
├── __init__.py
└── structure/
    ├── test_module_layout.py    # Parses the constitution's tree, compares to src/
    └── test_packaging.py        # Metadata is installed and importable, version pins agree

.github/workflows/ci.yml     # uv sync --locked → ruff check → ruff format --check → pytest
README.md                    # Development section: the three commands and the Python version
```

**Structure Decision**: single Python package under `src/`, named `hermes_memory` after the
repository (R1). Its subpackages are exactly the module tree recorded in the constitution's
Technology Stack section and ADR-004 — no more, no fewer — and the layout test enforces both
directions. Tests live in a top-level `tests/` outside the package, grouped by what they are about;
`tests/structure/` holds the checks that this feature owns, and later features add siblings
(`tests/unit/`, `tests/contract/`, `tests/integration/`) as the constitution's minimum-coverage
clause requires them.

## Deferred, deliberately

Named here so that a reviewer can see these were considered and left out rather than forgotten:

- **Gitleaks in CI.** Named in the stack table as secret scanning. It is a real requirement for a
  public repository handling private history, but it is a check about content, not about the
  skeleton, and it belongs in a change that says so — the contract in `contracts/checks.md` is
  written to be additive precisely so that adding it later is a normal change.
- **Import-linter contracts** enforcing Principle IV's dependency directions (R3).
- **A type checker** (R2).
- **Docker packaging**, the FastAPI surface, and the metadata database — ADR-004 names them; each
  arrives with the work that needs it.

## Complexity Tracking

> Fill ONLY if Constitution Check has violations that must be justified

No violations. No deviation from the constitution is taken, and no entry in the fixed technology
stack is changed, displaced or added to in a way that requires a decision record.
