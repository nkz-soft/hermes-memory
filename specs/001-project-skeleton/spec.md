# Feature Specification: Project Skeleton

**Feature Branch**: `001-project-skeleton`

**Created**: 2026-09-13

**Status**: Draft

**Input**: GitHub issue #4 — "Bootstrap the Python project skeleton". Phase 1, wave 1. Blocks #5,
#6, #7, #8.

## User Scenarios & Testing *(mandatory)*

The users of this feature are the contributors to this repository — including the agent-driven
workflow described in `CLAUDE.md`. The value delivered is that the next piece of work has a place
to put its code, its tests and its checks, and cannot invent a different one.

### User Story 1 - A contributor gets a working environment from a clean clone (Priority: P1)

Someone clones the repository for the first time and wants to run the project's checks. They run
one documented setup command, and from that point the test command and the lint command both work.
Nothing about the environment has to be reconstructed from prose in the architecture document.

**Why this priority**: without a reproducible environment, no other story can even be attempted,
and every later contributor pays the setup cost again. This is the smallest slice that already
delivers value on its own.

**Independent Test**: clone the repository into a fresh directory, run the documented setup
command, then the test command. Both succeed without further steps.

**Acceptance Scenarios**:

1. **Given** a clean clone with no pre-existing environment, **When** the contributor runs the
   documented setup command, **Then** the environment resolves and installs from a committed,
   pinned lock file without network prompts for undeclared dependencies.
2. **Given** the environment is installed, **When** the contributor runs the test command,
   **Then** the suite executes and reports success with zero failures and zero errors.
3. **Given** the environment is installed, **When** the contributor runs the lint and format
   checks, **Then** both report no violations against the committed sources.
4. **Given** the runtime version pinned by the project is not present, **When** the contributor
   runs the setup command, **Then** the required version is stated explicitly rather than the
   setup silently proceeding on a different one.

---

### User Story 2 - The module boundaries exist before anything fills them (Priority: P1)

A contributor starting the first ingestion feature needs to know where a parser, a sanitizer, an
interface or a memory-store implementation belongs. They read the source tree, find every module
named by the recorded architecture already present, and add their code inside one of them rather
than beside them.

**Why this priority**: this is the reason the issue exists. The layout is a decision already
recorded (ARCHITECTURE.md §20, ADR-004, and the constitution's Technology Stack section); leaving
it to the first feature is how the boundaries of Principle IV drift apart.

**Independent Test**: compare the source tree against the module list in the recorded architecture;
every listed module is present and importable, and no module outside the list has been introduced.

**Acceptance Scenarios**:

1. **Given** the repository at this feature's completion, **When** the source tree is compared to
   the module list recorded in the architecture, **Then** every listed module exists, with the
   listed nesting, and none is missing.
2. **Given** the module tree exists, **When** a contributor imports any of the modules, **Then**
   the import succeeds and the module is empty of behaviour.
3. **Given** the module tree exists, **When** the architecture's module list is later amended,
   **Then** an automated check fails until the tree is brought back into agreement.

---

### User Story 3 - Every pull request is checked automatically (Priority: P2)

A contributor opens a pull request. Continuous integration installs the environment, runs the lint
and format checks and the test suite, and reports the outcome on the pull request before a human
looks at it.

**Why this priority**: the checks exist and are runnable after Story 1; automating them is what
makes them binding rather than optional. Valuable, but the repository is already usable without it.

**Independent Test**: open a pull request against the default branch and observe the checks report
a result on it.

**Acceptance Scenarios**:

1. **Given** a pull request targeting the default branch, **When** it is opened or updated,
   **Then** the checks run automatically and their pass/fail result is visible on the pull request.
2. **Given** a pull request that introduces a lint violation or a failing test, **When** the checks
   run, **Then** they report failure rather than success.
3. **Given** the checks run, **When** they install the environment, **Then** they use the same
   pinned lock file and runtime version as a local contributor, so a local pass and a CI pass mean
   the same thing.

---

### Edge Cases

- The contributor's machine has a different runtime version than the one the project pins — setup
  must say so rather than proceed on the wrong one.
- The lock file and the dependency declaration disagree — the checks must fail rather than silently
  resolve something new.
- An empty test suite: the test command must report success, not error out for having collected
  nothing.
- A module in the recorded layout is renamed or removed in a later change without amending the
  architecture — the boundary check must catch the divergence in both directions.
- CI runs on a pull request from a fork, where repository secrets are unavailable — the checks in
  this feature need no secrets and must still run.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The repository MUST declare its dependencies and its required runtime version in
  committed project metadata, and MUST commit a lock file that pins every resolved dependency to an
  exact version.
- **FR-002**: A single documented command MUST install the complete development environment from
  that lock file on a clean clone.
- **FR-003**: The source tree MUST contain every module named in the recorded module layout, with
  the recorded nesting, and MUST NOT introduce modules outside it.
- **FR-004**: Every module created by this feature MUST be free of behaviour — it establishes the
  boundary and nothing else.
- **FR-005**: An automated check MUST verify that the module tree agrees with the recorded module
  layout, and MUST fail when a module is missing or an unrecorded one is present.
- **FR-006**: A single documented command MUST run the test suite, and MUST report success on a
  suite that contains no failing tests.
- **FR-007**: A single documented command MUST run the lint and formatting checks over the
  repository's own sources and report violations without modifying files.
- **FR-008**: Continuous integration MUST run the environment installation, the lint and format
  checks and the test suite on every pull request targeting the default branch, and report the
  outcome on the pull request.
- **FR-009**: Continuous integration MUST install from the same committed lock file and the same
  pinned runtime version used locally.
- **FR-010**: The repository MUST document, in a place a first-time contributor will find, the
  setup command, the test command and the lint command.
- **FR-011**: This feature MUST NOT add runtime behaviour, configuration for external services, or
  credentials of any kind.

### Key Entities

- **Project metadata**: the committed declaration of the project's name, its required runtime
  version, its dependencies and its development dependencies.
- **Lock file**: the committed, exact resolution of that declaration, shared by contributors and
  by continuous integration.
- **Module**: a named boundary in the source tree, corresponding one-to-one with an entry in the
  recorded module layout.
- **Check**: a command with a pass/fail outcome — environment installation, lint, format, module
  layout, tests — runnable locally and in continuous integration.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: From a clean clone on a machine with the pinned runtime available, a contributor
  reaches a state where the test command passes using only commands written in the repository's
  documentation, with no undocumented step.
- **SC-002**: The test command exits successfully on the committed tree, reporting zero failures
  and zero errors.
- **SC-003**: The lint and format checks exit successfully on the committed tree, reporting zero
  violations.
- **SC-004**: 100% of the modules in the recorded layout are present in the source tree, and 0
  modules outside it exist; a deliberate deviation introduced in a scratch commit makes the layout
  check fail.
- **SC-005**: A pull request opened against the default branch shows a completed pass/fail result
  for the checks without anyone triggering them by hand.
- **SC-006**: A pull request that deliberately introduces a lint violation, and one that
  deliberately introduces a failing test, are each reported as failing.
- **SC-007**: No module added by this feature contains executable behaviour beyond what a module
  declaration requires.

## Assumptions

- The technology choices are not open questions here: the runtime, the dependency manager and the
  test framework are fixed by the constitution's Technology Stack section and ADR-004. This
  specification treats them as given constraints rather than decisions to make, and states the
  requirements in terms of outcomes so that the checks remain verifiable.
- The linter and formatter are not named in ADR-004. Selecting them is a planning decision within
  the stack already fixed, not a change to it, and therefore needs no new decision record. The
  requirement here is only that both a lint check and a format check exist, run over the
  repository's own sources, and fail on violation.
- Continuous integration runs on GitHub Actions, because that is where this repository already
  hosts its issues, pull requests and workflow.
- The test suite starts empty of feature tests. The tests this feature itself owns are the ones
  that verify its own deliverable — chiefly the module-layout check — written test-first per
  Principle III.
- The default branch is `main`.
- No history data, credentials, external service or Hindsight instance is involved. Nothing in this
  feature touches the archive, the pipeline or the memory store beyond creating their empty
  boundaries.
- Container packaging, the HTTP surface and the metadata database are out of scope for this
  feature; ADR-004 names them, but the issue's deliverable is the skeleton, and each arrives with
  the work that needs it.
