---

description: "Task list for environment configuration"
---

# Tasks: Environment Configuration

**Input**: Design documents from `/specs/002-environment-configuration/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md),
[data-model.md](data-model.md), [contracts/settings.md](contracts/settings.md),
[quickstart.md](quickstart.md)

**Tests**: Required. Principle III of the constitution is non-negotiable — every test below is
written and **observed to fail** before the code that satisfies it exists. A task that writes the
code before its test has failed is not done.

**Organization**: grouped by user story, in the priority order of `spec.md`.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1–US4 — maps to the user stories in `spec.md`
- Every task names the exact file it touches

## Path Conventions

Single Python project, `src/` layout (plan.md → Structure Decision). Package root is
`src/hermes_memory/`; tests live in `tests/` at the repository root. Paths below are relative to
the repository root, which for this work is the worktree `../hermes-memory-5`.

---

## Phase 1: Setup — the first runtime dependency

**Purpose**: `pydantic` and `pydantic-settings` have to exist in the environment before a test can
import them. The skeleton's guard test forbids exactly that, and changing it is the deliberate act
the guard was written to force (plan.md → Constitution Check).

The order is test-first in the only sense available for a guard: the assertion is moved to its new
truth and **observed to fail** against the current empty dependency list, and only then is the list
changed.

- [x] T001 [US1] In `tests/structure/test_packaging.py`, change `test_no_runtime_dependencies` to
  assert the declared runtime dependencies are exactly `pydantic` and `pydantic-settings`, and
  rename it to say what it now guards. Run it and observe it **fail** against the empty list.
- [x] T002 [US1] Add `pydantic>=2` and `pydantic-settings>=2` to `[project] dependencies` in
  `pyproject.toml`, run `uv sync`, commit the re-resolved `uv.lock`. Observe T001 pass.
- [x] T003 [P] [US1] Create `tests/unit/__init__.py`, empty, so the new suites are collected under
  the same prepend import mode the existing ones rely on.

**Checkpoint**: `uv run pytest` passes on the unchanged tree with the dependencies declared and
nothing importing them yet.

---

## Phase 2: Foundational

**Purpose**: none. Every story below is independently testable against the same module, and no
shared scaffolding is needed beyond Phase 1. Stated explicitly so its absence is a decision rather
than an omission.

---

## Phase 3: US1 — configure without touching a repository file (P1)

**Goal**: values arrive from the environment and from an optional untracked `.env`, with defined
precedence.

**Independent test**: with the required values in the environment, settings load and every value
reads back as supplied.

- [x] T004 [US1] Write `tests/unit/test_settings_loading.py` covering
  [contracts/settings.md](contracts/settings.md): load from environment only; load from `.env`
  only; environment beats `.env`; `.env` beats a default; a missing `.env` loads normally; unrelated
  environment variables are ignored; the loaded object is immutable. Run and observe it **fail** —
  `hermes_memory.settings` does not exist.
- [x] T005 [US1] Create `src/hermes_memory/settings.py` with `HindsightSettings`, `LlmSettings`,
  `Settings` and `load_settings()` per [data-model.md](data-model.md): `HERMES_` prefix, `__`
  nesting delimiter, the defaults of research.md R6. Observe T004 pass.
- [x] T006 [US1] `test_modules_carry_no_behaviour` in `tests/structure/test_module_layout.py` now
  fails — observe it first. Then narrow it to the recorded module tree, so the boundaries it was
  written to keep empty are still guarded, and add a test proving the narrowed guard still catches
  behaviour placed inside a recorded module. Observe both pass.
- [x] T007 [P] [US1] Create `.env.example` at the repository root: every declared variable by name,
  a comment per group, required ones marked, no assigned credential value.

**Checkpoint**: US1 is demonstrable by hand — quickstart steps 1, 2 and 4.

---

## Phase 4: US2 — fail at startup, not mid-import (P1)

**Goal**: a missing, empty or malformed setting stops the run immediately, naming every fault.

**Independent test**: remove one required value from a complete environment; loading fails naming
it.

- [x] T008 [US2] Write `tests/unit/test_settings_failures.py`: each required setting removed on its
  own (parametrized over the required set, so the coverage is total rather than a sample per
  SC-002); empty string; whitespace only; a URL with no scheme or host; an empty bank id; several
  faults at once reported together. Run and observe it **fail**.
- [x] T009 [US2] Add the validation constraints to `src/hermes_memory/settings.py` that make T008
  pass — stripped minimum length on required strings, URL shape, non-empty bank id — without
  changing what US1 already proves.

**Checkpoint**: quickstart step 3 behaves as written.

---

## Phase 5: US3 — a credential cannot leak (P1)

**Goal**: a secret's value is absent from every rendering a program produces by default.

**Independent test**: construct settings with a known secret, render them four ways, find the value
in none.

- [x] T010 [US3] Write `tests/unit/test_settings_secrets.py` asserting the literal secret is absent
  from `repr()`, `str()`, `model_dump()`, `model_dump_json()` and the rendered text of a load
  failure, and that `get_secret_value()` returns it. Run and observe it **fail**.
- [x] T011 [US3] Make T010 pass. **This is the task research.md R3 could not settle from
  documentation**: run the validation-failure assertion first and record what it reports. If
  `SecretStr` alone covers it, the test stays as the regression that notices a future Pydantic
  release changing its mind; if it does not, add the explicit guard here and say so in the task
  notes.

**Checkpoint**: quickstart step 2 shows no token in the printed settings.

---

## Phase 6: Paths (US1, FR-013)

- [x] T012 [US1] Write `tests/unit/test_settings_paths.py`: a relative configured path resolves to
  the same absolute path from any working directory; an absolute one is preserved; loading creates
  no file or directory. Observe **fail**, then make it pass in `src/hermes_memory/settings.py`.

---

## Phase 7: US4 — the example file cannot drift (P2)

**Goal**: `.env.example` and the declared settings name the same set, enforced in both directions.

**Independent test**: add a setting without updating the file; the check fails naming it.

- [x] T013 [US4] Write `tests/unit/test_settings_example.py`: the names derived from the settings
  class equal the names parsed from `.env.example`, in both directions; a missing or empty
  `.env.example` raises loudly rather than comparing empty sets; no secret variable in the file
  carries a usable value (SC-006). Observe **fail**, then make it pass — deriving both sides rather
  than re-typing either (research.md R5).
- [x] T014 [P] [US4] Write `tests/structure/test_environment_files.py`: version control ignores
  `.env` and tracks `.env.example` (FR-011), asserted against the repository rather than trusted
  from `.gitignore`'s text.

---

## Phase 8: Invariant, documentation and polish

- [x] T015 Write the FR-001 / SC-008 invariant check in `tests/structure/test_environment_files.py`:
  no module outside `settings.py` reads the environment, asserted over the committed tree by parsing
  the sources rather than by grep.
- [x] T016 [P] Add a Configuration section to `README.md`: copy `.env.example` to `.env`, the two
  required variables, and the fact that `.env` is never committed. Keep the four commands
  `tests/structure/test_documented_commands.py` asserts and the Python version.
- [x] T017 Run the full check set — `uv sync --locked`, `uv run ruff check .`,
  `uv run ruff format --check .`, `uv run pytest` — and walk [quickstart.md](quickstart.md)
  end to end, including step 7, which proves the drift check bites.

---

## Dependencies

```text
T001 → T002 → T003
              ↓
        T004 → T005 → T006, T007
                      ↓
                T008 → T009
                      ↓
               T010 → T011
                      ↓
                     T012
                      ↓
               T013, T014 → T015 → T016 → T017
```

US1 (T004–T007) is the only story the others build on, because it creates the module. US2, US3 and
US4 each add checks to it and are independently testable once it exists.

## What "done" means

Every row of the check table in [contracts/settings.md](contracts/settings.md) has a test, each was
observed to fail before its code existed, and the four commands of T017 pass on the committed tree.
