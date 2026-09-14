---

description: "Task list for 004-ci-scanning-packaging"
---

# Tasks: Secret Scanning and Image Packaging in CI

**Input**: Design documents from `/specs/004-ci-scanning-packaging/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md),
[data-model.md](data-model.md), [contracts/checks.md](contracts/checks.md)

**Tests**: Required, not optional. Constitution Principle III is non-negotiable: every check in
[contracts/checks.md](contracts/checks.md) is written first and **observed to fail** before the file
it constrains exists. A task that skips the red step is not done.

**Organization**: Tasks are grouped by user story. One deviation from the spec's priority order is
deliberate and explained under Dependencies: **US3 is implemented first**, because the repository
cannot produce a green scan until the existing deliberate fixtures are exempted, and a story that
cannot be observed passing cannot be observed failing either.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: US1–US4 as numbered in [spec.md](spec.md)
- Paths are repository-root relative, inside the worktree `.claude/worktrees/7`

## Path Conventions

Single project: `src/hermes_memory/`, `tests/` at repository root, per
[plan.md](plan.md) § Project Structure.

---

## Phase 1: Setup

**Purpose**: establish the baseline that later red/green transitions are measured against.

- [ ] T001 Run the four existing checks and record the result, so any later failure is attributable
      to this feature: `uv sync --locked && uv run ruff check . && uv run ruff format --check . && uv run pytest`
- [ ] T002 Run the default-configuration history scan and record its output — the command is in
      [quickstart.md](quickstart.md) § C5, expected `leaks found: 10`. This is the **red** state the
      exemptions of Phase 3 turn green, and it must be observed before they are written

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: the shared declarations and test scaffolding that every story's checks read.

**⚠️ CRITICAL**: no story work begins until this phase is complete.

- [ ] T003 Amend the checks table in `specs/001-project-skeleton/contracts/checks.md` with C5, C6
      and C7 exactly as specified in [contracts/checks.md](contracts/checks.md) § "The commands
      added", including the container-runtime prerequisite paragraph (FR-023)
- [ ] T004 Extend the helpers in `tests/structure/test_ci_workflow.py` so a single job's steps and a
      step's parsed `with:` mapping can be addressed by job name — required by S1–S4, S9 and I7–I9.
      Existing tests must still pass unchanged after this refactor

**Checkpoint**: the contract names three new commands and the workflow test can address a named job.

---

## Phase 3: User Story 3 - A deliberate fixture is not mistaken for a leak (Priority: P2) 🎯 first by dependency

**Goal**: the repository's existing credential-shaped test fixtures are exempted, narrowly, so that
the scan can report zero findings on a clean tree.

**Independent Test**: run the history scan over the repository with the committed configuration and
observe zero findings, having observed ten without it (T002).

### Tests for User Story 3 ⚠️ write first, observe failing

- [ ] T005 [P] [US3] Write check S5 in `tests/structure/test_secret_scanning_config.py`:
      `.gitleaks.toml` exists, parses with `tomllib`, and sets `[extend] useDefault = true`
- [ ] T006 [P] [US3] Write check S6 in `tests/structure/test_secret_scanning_config.py`: every
      `[[allowlists]]` entry sets `condition = "AND"` — the default is OR, under which `paths` alone
      exempts a whole file for that rule
- [ ] T007 [P] [US3] Write check S7 in `tests/structure/test_secret_scanning_config.py`: every entry
      declares a non-empty `targetRules`, a non-empty `paths` and a non-empty `regexes`, and a
      non-empty `description`
- [ ] T008 [P] [US3] Write check S8 in `tests/structure/test_secret_scanning_config.py`: every
      `paths` pattern is anchored with `^` and `$` and ends in a file extension — no entry may name
      a directory (FR-008)
- [ ] T009 [US3] Run the new module and confirm all four checks fail because `.gitleaks.toml` does
      not exist. Red observed, per Principle III

### Implementation for User Story 3

- [ ] T010 [US3] Create `.gitleaks.toml` with `[extend] useDefault = true` and four
      `[[allowlists]]` entries — one per location measured in [research.md](research.md) R4:
      `github-pat` in `tests/unit/test_redaction_canary.py`, `jwt` in
      `tests/unit/test_redaction_values.py`, and `generic-api-key` in
      `tests/unit/test_redaction_names.py` and
      `specs/003-logging-telemetry-baseline/quickstart.md`. Each entry carries `description`,
      `condition = "AND"`, `targetRules`, anchored per-file `paths` and `regexes` matching the
      specific literal, per [data-model.md](data-model.md) § Exemption
- [ ] T011 [US3] Run `uv run pytest tests/structure/test_secret_scanning_config.py` and confirm
      S5–S8 now pass
- [ ] T012 [US3] Run the history scan with the committed configuration and confirm `no leaks found`
      with exit status 0 (SC-002, SC-003)

**Checkpoint**: the repository scans clean, and the exemptions' shape is enforced by tests.

---

## Phase 4: User Stories 1 and 2 - A credential cannot be merged, and history is proven clean (Priority: P1)

**Goal**: the scan runs in CI over the full history on every pull request, findings fail the build,
and the check is demonstrated capable of failing.

**Independent Test**: scan the committed negative-control fixture directly and observe a non-zero
exit naming the file, line and rule; confirm the workflow runs the same scanner over the history
with `fetch-depth: 0`.

### Tests for User Stories 1 and 2 ⚠️ write first, observe failing

- [ ] T013 [P] [US1] Write check S1 in `tests/structure/test_ci_workflow.py`: a job named `scan`
      runs the scanner as a `run:` command, asserted against parsed YAML rather than file text
- [ ] T014 [P] [US1] Write check S2 in `tests/structure/test_ci_workflow.py`: the scanner reference
      is pinned to an exact `vX.Y.Z` tag — `latest` or a bare major fails (FR-006)
- [ ] T015 [P] [US1] Write check S3 in `tests/structure/test_ci_workflow.py`: the invocation carries
      both `-v` and `--redact` (FR-004, research R6)
- [ ] T016 [P] [US2] Write check S4 in `tests/structure/test_ci_workflow.py`: the `scan` job's
      checkout step sets `fetch-depth: 0`, asserted against that step's parsed `with:` mapping.
      Without it the history scan passes vacuously over one commit (FR-002)
- [ ] T017 [P] [US1] Write check S9 in `tests/structure/test_ci_workflow.py`: the workflow runs the
      negative control against `tests/fixtures/secret_scanning/` and requires a non-zero exit
- [ ] T018 [US1] Confirm check S10 — the existing `test_needs_no_secrets_so_forks_can_run_it` —
      still passes unchanged once the new jobs exist (FR-005)
- [ ] T019 [US1] Run the workflow test module and confirm S1–S4 and S9 fail against the current
      `ci.yml`. Red observed

### Implementation for User Stories 1 and 2

- [ ] T020 [P] [US1] Create `tests/fixtures/secret_scanning/leaky_config.ini` containing a fake AWS
      key whose sixteen-character tail lies in the base32 alphabet `[A-Z2-7]` — no `0`, `1`, `8` or
      `9`, per [research.md](research.md) R7 — with a comment beside it stating that constraint and
      that the literal may not be edited casually
- [ ] T021 [US1] Add the fifth `[[allowlists]]` entry to `.gitleaks.toml`, scoped to
      `aws-access-token`, that one path and that one literal, so the repository scan stays green
      while the negative control still fires when scanned directly
- [ ] T022 [US1] Add the `scan` job to `.github/workflows/ci.yml`: `actions/checkout@v5` with
      `fetch-depth: 0`, then the pinned history scan, then the negative-control scan asserting a
      non-zero exit. The invocations are the ones in [quickstart.md](quickstart.md), including the
      `GIT_CONFIG_*` trio of research R3 — without it the scanner can report zero findings on a
      repository it never read
- [ ] T023 [US1] Extend `test_runs_every_check_in_the_contract` with C5 (check X1, FR-024)
- [ ] T024 [US1] Run `uv run pytest tests/structure/` and confirm S1–S4, S9, S10 and X1 pass
- [ ] T025 [US1] Run the negative control locally and confirm exit status 1 with a finding naming
      the file, the line and `aws-access-token` (SC-001); run the repository scan and confirm it is
      still `no leaks found` (SC-002)

**Checkpoint**: the scan runs in CI, fails on a finding, and has been observed failing.

---

## Phase 5: User Story 4 - The container is proven to build and run (Priority: P2)

**Goal**: the packaging target of ADR-004 is exercised on every pull request rather than assumed.

**Independent Test**: build the image and run it with no arguments; usage text is printed and the
container exits 0.

### Tests for User Story 4 ⚠️ write first, observe failing

- [ ] T026 [P] [US4] Write check P1 in `tests/structure/test_packaging.py`: `pyproject.toml`
      declares the console script `hermes-memory` pointing into `hermes_memory.cli`
- [ ] T027 [P] [US4] Write checks P2 and P3 in `tests/unit/test_cli.py`: invoking the application
      with `--help` exits 0 and prints usage text naming the application; and the application
      registers **no** behavioural command — the command list is empty (FR-022)
- [ ] T028 [P] [US4] Write checks I1, I2, I3, I4, I5 in `tests/structure/test_image_definition.py`:
      a `Dockerfile` exists; its runtime base interpreter agrees with `.python-version`; the build
      installs with `uv sync` carrying both `--locked` and `--no-dev`; `ENTRYPOINT` is the exec form
      naming the console script and `CMD` is `["--help"]`; a `USER` directive selects a non-root
      user and no later instruction returns to root
- [ ] T029 [P] [US4] Write check I6 in `tests/structure/test_image_definition.py`: `.dockerignore`
      excludes at minimum `.git`, `tests/`, `specs/` and `data/`
- [ ] T030 [P] [US4] Write checks I7, I8, I9 in `tests/structure/test_ci_workflow.py`: a job named
      `image` builds the image as a `run:` command; the workflow asserts on the **content** of the
      container's output rather than its exit status alone; and the job contains no registry login
      and no push (FR-017)
- [ ] T031 [US4] Run the new and changed modules and confirm P1–P3 and I1–I9 fail. Red observed

### Implementation for User Story 4

- [ ] T032 [US4] Add `typer` to the runtime dependencies in `pyproject.toml`, declare
      `[project.scripts] hermes-memory = "hermes_memory.cli:main"`, and re-resolve `uv.lock` with
      `uv lock`
- [ ] T033 [US4] Update `test_runtime_dependencies_are_exactly_the_declared_set` in
      `tests/structure/test_packaging.py` to guard six dependencies, naming the stack table's CLI
      row in the docstring as the authority for `typer` (check P4, research R14)
- [ ] T034 [US4] Record `cli` in `FILLED_BOUNDARIES` in `tests/structure/test_module_layout.py`,
      with the one-line note naming this feature, so the remaining boundaries stay guarded
- [ ] T035 [US4] Implement the Typer application in `src/hermes_memory/cli/__init__.py`: an app with
      a help description, a `--version` option and `main()` as the console-script target. No
      behavioural command — FR-022, enforced by check P3
- [ ] T036 [P] [US4] Create `.dockerignore` excluding `.git`, `tests/`, `specs/`, `data/`,
      `.claude/`, and the usual build detritus
- [ ] T037 [US4] Create `Dockerfile`: a builder stage running
      `uv sync --locked --no-dev --no-editable`, and a `python:3.13-slim-bookworm` runtime stage
      copying the virtual environment, creating and switching to a non-root user, with
      `ENTRYPOINT ["hermes-memory"]` and `CMD ["--help"]` (research R9, R10)
- [ ] T038 [US4] Add the `image` job to `.github/workflows/ci.yml`: build, then run the image and
      assert the usage text appears in its output. No registry login, no push
- [ ] T039 [US4] Extend `test_runs_every_check_in_the_contract` with C6 and C7 (check X1)
- [ ] T040 [US4] Run `uv run pytest` and confirm P1–P4 and I1–I9 pass
- [ ] T041 [US4] Build and run the image locally and confirm usage text with exit status 0 (SC-006),
      then confirm the image carries no tests, no development dependencies and a non-root user, per
      [quickstart.md](quickstart.md) § "Confirming what the image does not contain" (SC-007, SC-008)

**Checkpoint**: all four stories are independently functional.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [ ] T042 [P] Document the two new checks in `README.md`: how to run them, the container-runtime
      prerequisite, how to tell a real finding from a deliberate fixture, and that a real finding
      means the credential is revoked rather than merely deleted from the diff (FR-011)
- [ ] T043 Walk [quickstart.md](quickstart.md) end to end and correct anything that does not match
      what the commands now do
- [ ] T044 Run the full local suite — `uv sync --locked && uv run ruff check . && uv run ruff format --check . && uv run pytest` — plus C5, C6, C7, and quote the output rather than claiming a pass
      (superpowers:verification-before-completion)
- [ ] T045 Request code review on the finished branch and address what it finds before a reviewer
      sees it (superpowers:requesting-code-review)
- [ ] T046 Open the pull request, composing the body from
      `.github/pull_request_template.md` by hand, with `Closes #7`, and move the issue's labels from
      `in-progress` to `in-review`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies. T002's red observation is a prerequisite of Phase 3's
  green claim and cannot be reconstructed afterwards
- **Foundational (Phase 2)**: depends on Setup. Blocks all stories
- **US3 (Phase 3)**: depends on Foundational
- **US1 + US2 (Phase 4)**: depend on US3. See below
- **US4 (Phase 5)**: depends on Foundational only — independent of the scanning stories and could
  be built in parallel by a second person
- **Polish (Phase 6)**: depends on all stories

### Why US3 precedes the P1 stories

The spec ranks US3 below US1 and US2 by *value*, and that ranking stands: US3 protects the check,
while US1 and US2 protect the repository. Implementation order is a different question. Measured in
[research.md](research.md) R4, the repository's history carries ten findings in five deliberate
fixtures, so a scanning job added before the exemptions exist is a job that cannot pass — and a
check that has never been green tells you nothing when it goes red. US3 first is the order in which
each story's transition is observable.

### Within each story

- Checks are written first and observed to fail (T009, T019, T031 are the explicit red gates)
- Configuration before the workflow that invokes it
- The application before the image that packages it
- The negative control before any claim that the scan works

### Parallel Opportunities

- T005–T008 are four checks in one new file with no dependency between them
- T013–T017 likewise, across the workflow test
- T026–T030 likewise, across three files
- **Phase 5 is independent of Phases 3 and 4 in full.** Two people could take the scanning half and
  the packaging half simultaneously; they meet only in `ci.yml`, T023 and T039

---

## Parallel Example: User Story 4

```bash
# The image and CLI checks touch three different files and can be written together:
Task: "P1 in tests/structure/test_packaging.py"
Task: "P2, P3 in tests/unit/test_cli.py"
Task: "I1..I5 in tests/structure/test_image_definition.py"
Task: "I6 in tests/structure/test_image_definition.py"
Task: "I7..I9 in tests/structure/test_ci_workflow.py"
```

---

## Implementation Strategy

### MVP

The scanning half — Phases 1 through 4 — is the MVP, and it is what should ship if only one half
can. A leaked credential costs a credential; an unexercised packaging target costs time. The plan's
summary says the same thing in one sentence.

### Incremental Delivery

1. Setup + Foundational → the contract names the new commands
2. US3 → the repository scans clean, exemption shape enforced
3. US1 + US2 → the scan runs in CI, and has been seen to fail **(MVP)**
4. US4 → the image builds, runs, and is proven to carry neither tests nor root
5. Polish → documentation, verification, review, pull request

---

## Notes

- Commit after each story phase, not after each task; the red gates (T009, T019, T031) are worth a
  commit of their own where the failing output is quoted in the message
- Every claim of a pass carries the command and its output. "Tests pass" without the command is not
  verification
- Avoid: widening an exemption to make a build green. That is the one change this feature exists to
  make visible
