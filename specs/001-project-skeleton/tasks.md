---

description: "Task list for the project skeleton"
---

# Tasks: Project Skeleton

**Input**: Design documents from `/specs/001-project-skeleton/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md),
[data-model.md](data-model.md), [contracts/checks.md](contracts/checks.md),
[quickstart.md](quickstart.md)

**Tests**: Required. Principle III of the constitution is non-negotiable — every test below is
written and **observed to fail** before the code that satisfies it exists. A task that creates
the thing before its test has failed is not done.

**Organization**: grouped by user story, in the priority order of `spec.md`.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1, US2, US3 — maps to the user stories in `spec.md`
- Every task names the exact file it touches

## Path Conventions

Single Python project, `src/` layout (plan.md → Structure Decision). Package root is
`src/hermes_memory/`; tests live in `tests/` at the repository root. Paths below are relative to
the repository root, which for this work is the worktree `../hermes-memory-4`.

---

## Phase 1: Setup — a harness that can run a failing test

**Purpose**: the chicken-and-egg problem of this feature. A test cannot be *observed* to fail
before there is anything to run it with, so this phase creates the minimum needed to execute
`pytest` and nothing more.

**⚠️ Deliberately incomplete.** What this phase writes is a harness, not the deliverable. It
declares no `requires-python` pin, no `.python-version`, no `src/` package discovery, no Ruff
configuration and no README section — precisely so that the tests in Phase 3 fail for real
reasons rather than passing by accident. Completing the metadata is US1's job, in Phase 3.

- [ ] T001 Create a minimal `pyproject.toml` at the repository root: `[project]` with `name =
  "hermes-memory"` and `version = "0.1.0"` only, plus a `dev` dependency group containing `pytest`
  and `ruff`. No `requires-python`, no build backend, no tool configuration — those are T009–T011.
- [ ] T002 Run `uv sync` to generate `uv.lock`, and confirm `uv run pytest --version` executes.
- [ ] T003 [P] Create `tests/__init__.py` and `tests/structure/__init__.py`, both empty.
- [ ] T004 [P] Add `.venv/`, `__pycache__/`, `*.egg-info/`, `.pytest_cache/` and `.ruff_cache/` to
  `.gitignore` if not already ignored. Confirm `data/` is still ignored and untouched.

**Checkpoint**: `uv run pytest` executes and exits 5 (no tests collected). That is the expected
state — see research.md R6 — and the next phase is what makes it collect something.

---

## Phase 2: Foundational

**Purpose**: none. There is no shared infrastructure between the stories of this feature beyond
the harness above, and inventing a foundational layer for fifteen empty packages would be the
kind of structure the issue exists to prevent.

This phase is intentionally empty. User story work begins immediately after Phase 1.

---

## Phase 3: User Story 1 — A contributor gets a working environment from a clean clone (Priority: P1) 🎯 MVP

**Goal**: one documented setup command takes a clean clone to a state where the test command and
the lint command both work, from a committed lock file on the pinned runtime.

**Independent Test**: clone into a fresh directory, run the documented setup command, then the
test command. Both succeed with no further steps (quickstart.md Scenario 1).

### Tests for User Story 1 ⚠️ WRITE FIRST, OBSERVE FAILING

- [ ] T005 [P] [US1] Write `tests/structure/test_packaging.py::test_requires_python_pins_313`:
  reads `pyproject.toml` and asserts `project.requires-python` is exactly `==3.13.*`, the value
  fixed by the constitution's Technology Stack table. **Run it. It must fail** — T001 declared no
  `requires-python`.
- [ ] T006 [P] [US1] Add `test_python_version_file_agrees_with_metadata` to
  `tests/structure/test_packaging.py`: asserts `.python-version` exists, contains exactly `3.13`
  (stripped), and that the version it names satisfies `project.requires-python`. **Run it. It must
  fail** — there is no `.python-version` yet. This is the assertion behind FR-009.
- [ ] T007 [P] [US1] Add `test_package_is_importable_from_src_layout` to
  `tests/structure/test_packaging.py`: asserts `hermes_memory` imports, and that its resolved
  `__file__` lies under a `src/` directory — proving the installed package, not the working
  directory, is what is under test (research.md R1). **Run it. It must fail** — no package exists.
- [ ] T008 [P] [US1] Add `test_no_runtime_dependencies` to `tests/structure/test_packaging.py`:
  asserts `project.dependencies` is absent or empty, enforcing FR-011 — the skeleton adds no
  runtime dependency, and a later feature that adds one must change this test deliberately. **Run
  it. It must fail or error** on the current metadata; if it passes trivially, note that in the
  commit and keep it, since its value is as a guard against a future addition.

### Implementation for User Story 1

- [ ] T009 [US1] Complete `pyproject.toml`: add `requires-python = "==3.13.*"`, a build backend
  with `src/` package discovery for `hermes_memory`, and an explicitly empty
  `dependencies = []`. Satisfies T005, T007 (in part) and T008.
- [ ] T010 [US1] Create `.python-version` containing `3.13`. Satisfies T006.
- [ ] T011 [P] [US1] Add `[tool.ruff]` to `pyproject.toml` — target version `py313`, a line length,
  and an explicit rule selection — and `[tool.pytest.ini_options]` with `testpaths = ["tests"]`,
  `--strict-markers` and `--strict-config`, so a mistyped marker or option is an error rather than
  a silent no-op (data-model.md → Project metadata).
- [ ] T012 [US1] Create `src/hermes_memory/__init__.py` with a one-line docstring naming the
  distribution. Satisfies T007. **Run the packaging tests. All four must now pass.**
- [ ] T013 [US1] Re-run `uv sync` so `uv.lock` reflects the completed metadata, and verify
  `uv sync --locked` exits 0 — check C1 of [contracts/checks.md](contracts/checks.md).
- [ ] T014 [US1] Add a "Development" section to `README.md` with the required Python version and
  the three commands verbatim: `uv sync`, `uv run pytest`, `uv run ruff check . && uv run ruff
  format --check .` (FR-010, research.md R7).
- [ ] T015 [US1] Run `uv run ruff check .` and `uv run ruff format --check .` over the tree and fix
  what they report — checks C2 and C3.

**Checkpoint**: a clean clone reaches a green suite using only the README's commands. US1 is
independently done, and quickstart.md Scenario 1 passes.

---

## Phase 4: User Story 2 — The module boundaries exist before anything fills them (Priority: P1)

**Goal**: every module in the recorded layout is present and importable, no module outside it
exists, and an automated check enforces both directions.

**Independent Test**: `uv run pytest -k layout` passes on the committed tree, and can be *made* to
fail by adding an unrecorded package or renaming a recorded one (quickstart.md Scenario 2).

### Tests for User Story 2 ⚠️ WRITE FIRST, OBSERVE FAILING

- [ ] T016 [US2] Write the parser in `tests/structure/test_module_layout.py`: a helper that reads
  `.specify/memory/constitution.md`, locates the single fenced `text` block containing the module
  tree, and parses its `├── / └── / │` ASCII tree by indentation depth into a set of dotted module
  paths. **It must raise rather than return an empty set** when the fence cannot be found or a line
  cannot be resolved (research.md R3) — a check that passes vacuously is worse than none.
- [ ] T017 [US2] Add `test_constitution_tree_parses_to_the_recorded_modules`: asserts the parser
  returns exactly the fifteen paths recorded in [data-model.md](data-model.md) → Module — `api`,
  `cli`, `ingestion`, `ingestion.chatgpt`, `ingestion.claude_code`, `ingestion.codex`,
  `normalization`, `sanitization`, `classification`, `archive`, `memory`, `memory.interface`,
  `memory.hindsight`, `evaluation`, `observability`. This pins the parser itself, so a parser bug
  cannot silently weaken the layout check. **Run it. It must fail** — no parser exists yet.
- [ ] T018 [US2] Add `test_every_recorded_module_exists`: for each parsed path, asserts the
  corresponding directory under `src/hermes_memory/` exists and contains an `__init__.py`. The
  failure message names the missing modules. **Run it. It must fail** — only the package root
  exists.
- [ ] T019 [US2] Add `test_no_unrecorded_modules_exist`: walks the packages under
  `src/hermes_memory/`, and asserts every one appears in the parsed set. The failure message names
  the surplus packages. This is the second direction of the FR-005 invariant. **Run it.** It may
  pass trivially on an empty tree; T023 is where it is proven capable of failing.
- [ ] T020 [US2] Add `test_modules_carry_no_behaviour`: asserts every `__init__.py` under
  `src/hermes_memory/` contains nothing but a module docstring — no import, no class, no function,
  no assignment (FR-004, SC-007, research.md R4). **Run it. It must fail or pass vacuously**; it
  becomes meaningful in T022.

### Implementation for User Story 2

- [ ] T021 [US2] Create the fifteen module directories under `src/hermes_memory/` exactly as
  recorded: `api/`, `cli/`, `ingestion/{chatgpt,claude_code,codex}/`, `normalization/`,
  `sanitization/`, `classification/`, `archive/`, `memory/{interface,hindsight}/`, `evaluation/`,
  `observability/`. Create no other package — in particular, do not add one for the import-state
  boundary of ARCHITECTURE.md §8, which the recorded layout does not carry (plan.md → Principle IV).
- [ ] T022 [US2] Give each new `__init__.py` a single one-line docstring naming that boundary's
  responsibility, taken from ARCHITECTURE.md §8 where §8 names it. Nothing else in the file.
  **Run the layout tests. All five must now pass.**
- [ ] T023 [US2] Prove the check can fail, per quickstart.md Scenario 2: temporarily add
  `src/hermes_memory/unrecorded/__init__.py` and confirm T019 fails naming it; remove it. Then
  temporarily rename `src/hermes_memory/archive/` and confirm T018 fails naming it; rename it back.
  Record both observed failures in the commit message. Leave the tree clean.

**Checkpoint**: the module tree matches the constitution and is enforced in both directions.
SC-004 and SC-007 hold.

---

## Phase 5: User Story 3 — Every pull request is checked automatically (Priority: P2)

**Goal**: CI installs the environment from the same lock file and the same runtime as a
contributor, runs all four checks, and reports the outcome on every pull request.

**Independent Test**: open the pull request for this branch and observe a completed pass/fail
result appear without anyone triggering it (quickstart.md Scenario 4).

### Tests for User Story 3 ⚠️ WRITE FIRST, OBSERVE FAILING

CI cannot be unit-tested — the only honest proof is a pull request that runs it, which is T027.
What *can* be asserted locally is that the workflow keeps the promises the contract makes about it,
and those assertions are worth having because they are what silently rot.

- [ ] T024 [P] [US3] Write `tests/structure/test_ci_workflow.py`: parses
  `.github/workflows/ci.yml` and asserts it triggers on `pull_request` against `main`; runs all
  four commands of [contracts/checks.md](contracts/checks.md), with `uv sync` carrying `--locked`;
  declares `permissions: contents: read`; and references no `secrets.` expression, which is what
  lets it run on fork pull requests (plan.md → Principle V). **Run it. It must fail** — no workflow
  file exists.

### Implementation for User Story 3

- [ ] T025 [US3] Create `.github/workflows/ci.yml` per research.md R5: triggers on `pull_request`
  targeting `main` and `push` to `main`; one job on `ubuntu-latest`; a concurrency group keyed on
  the ref that cancels superseded runs; `permissions: contents: read`; steps — checkout, install
  `uv` at a pinned action version, install the Python version from `.python-version`,
  `uv sync --locked`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run pytest`.
  **Run T024. It must now pass.**
- [ ] T026 [US3] Run every one of the four checks locally in the workflow's order and confirm each
  exits 0, so that what CI will run has already been run by hand.

**Checkpoint**: the workflow exists and its promises are asserted. Confirmation that it *reports*
comes from the pull request itself.

---

## Phase 6: Polish & verification

- [ ] T027 Open the pull request (this is also step 5 of the `issue-to-pr` workflow) and confirm
  the checks appear and complete on it — SC-005.
- [ ] T028 Verify SC-006 by making each check fail on purpose and reverting: push a scratch commit
  with an unused import in one module and confirm C2 turns the pull request red; push one with a
  deliberately false assertion and confirm C4 does. Revert both. Quote the observed failures in the
  pull request's verification section rather than claiming the checks work.
- [ ] T029 [P] Verify the lock file is binding (quickstart.md Scenario 3): add a dependency line to
  `pyproject.toml` without regenerating the lock, confirm `uv sync --locked` fails rather than
  re-resolving, then restore the file.
- [ ] T030 [P] Run `find src/hermes_memory -name '__init__.py' -size +200c` and confirm no output,
  the independent check on SC-007.
- [ ] T031 Correct `plan.md` → Technical Context → Scale/Scope: it says "14 module packages"; the
  recorded layout has fifteen. Fix the number rather than leaving the plan disagreeing with what
  was built.
- [ ] T032 Walk [quickstart.md](quickstart.md) end to end from a fresh clone and confirm every
  expected outcome, including that no step outside the README was needed — SC-001.
- [ ] T033 Request a code review of the finished branch and address what it finds before a human
  sees it.

---

## Dependencies & Execution Order

### Phase dependencies

- **Phase 1 (Setup)**: no dependencies. Everything else needs it, because nothing can run a test
  before it.
- **Phase 2 (Foundational)**: empty. Blocks nothing.
- **Phase 3 (US1)**: after Phase 1.
- **Phase 4 (US2)**: after Phase 3 — the layout test needs the package root and the pytest
  configuration that T009–T012 create. This is a harness dependency, not a story dependency: US2
  delivers value on its own once US1 has run.
- **Phase 5 (US3)**: after Phases 3 and 4, because the workflow runs the checks those produce.
- **Phase 6 (Polish)**: after all three stories.

### Within each story

Tests first, observed failing, then the implementation that makes them pass. No exceptions — the
`⚠️` markers above are where that is checked.

### Parallel opportunities

- T003 and T004 in Setup.
- T005–T008 in US1: four independent assertions, all added to the same file, so run them together
  but write them in one sitting to avoid an edit conflict.
- T011 is parallel to T009 and T010 — different sections of `pyproject.toml`, different concerns.
- T029 and T030 in Polish.
- Nothing in US2 is parallel: T016 builds the parser every later test in the phase depends on.

---

## Implementation Strategy

### MVP

US1 alone is a coherent increment: a repository someone can clone, install and test. It delivers
value without US2 or US3, which is why it is first.

But this feature's *point* is US2 — the boundaries. US1 is the ground it stands on. Both are P1
and both ship in this pull request; the sequencing above is about which failing test comes first,
not about which could be dropped.

### Incremental delivery

1. Phase 1 → a harness that runs tests.
2. Phase 3 → clean clone to green suite. Stop and validate against quickstart Scenario 1.
3. Phase 4 → the module tree, enforced. Stop and validate against Scenario 2, including the
   proof that the check fails (T023).
4. Phase 5 → CI. Validate against Scenario 4 once the pull request exists.
5. Phase 6 → prove the checks can fail, then finish.

### Notes

- Commit after each phase, or after each logical group within one.
- The `⚠️` blocks are not decoration. Run the test, read the failure, then write the code.
- Nothing in this feature reads a credential, contacts Hindsight, or touches `data/`. If a task
  seems to need one of those, it has drifted out of scope.
