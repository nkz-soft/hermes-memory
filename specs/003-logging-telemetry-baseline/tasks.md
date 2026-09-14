---

description: "Task list for 003-logging-telemetry-baseline"
---

# Tasks: Logging and Telemetry Baseline

**Input**: Design documents from `/specs/003-logging-telemetry-baseline/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md),
[data-model.md](data-model.md), [contracts/observability.md](contracts/observability.md)

**Tests**: mandatory. Principle III of the constitution is non-negotiable — every test below is
written first and observed to fail before the code that satisfies it exists. The check numbers in
parentheses are the roster in [contracts/observability.md](contracts/observability.md).

**Organization**: grouped by the user stories of [spec.md](spec.md), so each is implementable and
testable on its own.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1–US4, mapping to the user stories in spec.md
- File paths are exact and relative to the repository root

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: take the three runtime dependencies the stack table fixes, through the guard that
exists to make that deliberate.

- [X] T001 Change `EXPECTED_RUNTIME_DEPENDENCIES` in `tests/structure/test_packaging.py` to
  `{"pydantic", "pydantic-settings", "structlog", "opentelemetry-api", "opentelemetry-sdk"}` and
  rewrite its docstring to name the stack-table row permitting each addition (Logging → structlog;
  Telemetry → the two OpenTelemetry distributions), per research.md R14. Run
  `uv run pytest tests/structure/test_packaging.py` and **observe it fail** — the dependencies are
  not declared yet (check 34).
- [X] T002 Add the three dependencies with
  `uv add structlog opentelemetry-api opentelemetry-sdk`, committing the resulting `pyproject.toml`
  and `uv.lock`. Re-run the same command and observe it pass.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: the settings group, the capture fixture and the pipeline itself. Every user story
below emits through what this phase builds.

**⚠️ CRITICAL**: no user story work begins until this phase is complete.

- [X] T003 [P] Write `tests/unit/test_settings_logging.py`: `HERMES_LOGGING__LEVEL` defaults to
  `"INFO"`; it accepts each of `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` case-insensitively;
  any other value fails at load naming the variable and withholding the value (check 28);
  `HERMES_LOGGING__INCLUDE_CONVERSATION_CONTENT` defaults to `False` and parses `true`/`false`; an
  absent `HERMES_LOGGING__*` environment is valid because every field has a default. Observe it
  fail.
- [X] T004 Add the `LoggingSettings` group to `src/hermes_memory/settings.py` per data-model.md:
  a `_Frozen` subclass with `level` (closed set of the five standard names, default `INFO`,
  matched case-insensitively) and `include_conversation_content` (bool, default `False`), attached
  to `Settings` as `logging: LoggingSettings` with `default_factory=LoggingSettings` so an absent
  group is valid. Do **not** add it to `_always_descend_into_the_groups` — research.md R12 says
  why. Observe T003 pass.
- [X] T005 Add `HERMES_LOGGING__LEVEL` and `HERMES_LOGGING__INCLUDE_CONVERSATION_CONTENT` to
  `.env.example`, commented out with their defaults and, for the flag, a line stating that setting
  it puts conversation text in the log. 002's existing
  `tests/unit/test_settings_example.py` goes red at T004 and green here (check 29).
- [X] T006 Add a `rendered_records` fixture to `tests/unit/conftest.py`: configures the pipeline to
  write to an in-memory stream, yields a callable returning the parsed JSON lines, and restores the
  previous configuration afterwards. Its docstring **must** state that
  `structlog.testing.capture_logs` is forbidden in this suite because it bypasses the processors
  and would make every redaction test pass vacuously (research.md R13).
- [X] T007 [P] Write `tests/unit/test_logging_configuration.py` for the pipeline's own behaviour:
  a record parses as one JSON object per line (check 2); a record emitted with no `configure()`
  call at all is still structured (check 26); `configure()` twice then one log emits exactly one
  line (check 25); `configure()` performs no network call and creates no file (check 27). Observe
  it fail.
- [X] T008 Create `src/hermes_memory/observability/logging.py`: the processor chain of research.md
  R2 in the fixed order — `merge_contextvars`, `add_log_level`, `TimeStamper(fmt="iso", utc=True)`,
  `StackInfoRenderer`, `format_exc_info`, then the correlation and redaction slots, then
  `JSONRenderer` — writing to standard error, with `get_logger(name=None)` and a `configure`
  applying the level. Leave the correlation and redaction slots as no-op placeholders; US2 and US4
  fill them.
- [X] T009 Rewrite `src/hermes_memory/observability/__init__.py` as the public surface of
  contracts/observability.md, installing the default pipeline at import time (research.md R3) with
  a call that reads no environment, opens no file and makes no network connection.
- [X] T010 Run `uv run pytest tests/structure/test_module_layout.py` and **observe
  `test_recorded_modules_carry_no_behaviour` fail** on the new files — then narrow it per research
  R14: add an explicit set of boundaries that have been filled, `{"observability"}`, excluded from
  the docstring-only assertion, with a docstring saying which feature filled it and that the other
  fourteen are still guarded. Leave `test_the_behaviour_guard_still_bites` untouched: its fixture
  is built from `archive/`, so it keeps proving the narrowed guard bites.
- [X] T011 Complete `configure(settings)` in `src/hermes_memory/observability/logging.py`: install
  the standard-library bridge through `structlog.stdlib.ProcessorFormatter` with a
  `foreign_pre_chain` sharing the chain (research.md R5), on a single handler tagged with an
  attribute so a previous one is removed rather than stacked (research.md R4), and set
  `cache_logger_on_first_use=False` so reconfiguration is visible to loggers already obtained.
  Observe T007 pass.

**Checkpoint**: records are structured and the surface exists. Nothing is redacted yet — no user
story is complete.

---

## Phase 3: User Story 1 — An operator can tell what an import did (Priority: P1) 🎯 MVP

**Goal**: exactly one record per ingestion operation, carrying the §18 field set, with a duration
the surface measured itself.

**Independent Test**: run an ingestion operation through the surface, parse the captured output,
and assert all ten fields are present with the intended values.

### Tests for User Story 1 ⚠️

> Write these first; observe them fail.

- [X] T012 [P] [US1] Write `tests/unit/test_operation_record.py` covering checks 1–5: one record
  per operation carrying **all ten** fields of data-model.md — `event` (fixed
  `"ingestion.operation"`), `source`, `source_id`, `project` (nullable), `bank`, `document_id`
  (nullable), `start_time` (ISO 8601, UTC, with offset), `duration_ms` (numeric, never accepted
  from the caller), `status`, `error` (null unless failed); `status` is `imported` on a clean exit,
  `skipped` when the body says so, `failed` on an exception; on an exception the record is emitted,
  `error` is non-null **and the exception reaches the caller**.
- [X] T013 [P] [US1] Add checks 6–7 to the same file: context bound for an operation appears on
  other records emitted inside it and on none emitted after it ends; two operations in sequence on
  one thread do not share context.

### Implementation for User Story 1

- [X] T014 [US1] Create `src/hermes_memory/observability/operations.py`: `OperationStatus` as a
  closed enumeration of exactly `imported`, `skipped`, `failed`; the `ingestion_operation`
  context manager binding the §18 context through `structlog.contextvars`, timing the body with a
  monotonic clock for `duration_ms` and `datetime.now(UTC)` for `start_time`, emitting one terminal
  record, re-raising every exception unchanged, and unbinding the context on every exit path.
- [X] T015 [US1] Export `ingestion_operation` and `OperationStatus` from
  `src/hermes_memory/observability/__init__.py`. Observe T012 and T013 pass.

**Checkpoint**: §18's record exists and is honest about failure. Credentials are **not** yet
redacted, so this is not shippable on its own — see the MVP note at the end.

---

## Phase 4: User Story 2 — A credential cannot reach the log (Priority: P1) 🎯 MVP

**Goal**: redaction as a property of the pipeline, covering names, secret types, value shapes,
nesting and tracebacks.

**Independent Test**: emit a record carrying a credential-shaped value, capture the rendered
output, and assert the literal appears nowhere in it.

### Tests for User Story 2 ⚠️

> Write these first; observe them fail. These are the tests that would pass vacuously if written
> against `capture_logs` — they assert over rendered output only.

- [X] T016 [P] [US2] Write `tests/unit/test_redaction_names.py` covering checks 8–10:
  parametrised over **each** of the twelve name segments (`token`, `secret`, `password`, `passwd`,
  `credential`, `credentials`, `authorization`, `cookie`, `cookies`, `jwt`, `bearer`, `apikey`) and
  **each** of the six pairs (`api`+`key`, `access`+`key`, `private`+`key`, `secret`+`key`,
  `auth`+`header`, `auth`+`token`), the value never appears; and `author`, `idempotency_key`,
  `document_id` and `bank` are **not** redacted.
- [X] T017 [P] [US2] Write `tests/unit/test_redaction_values.py` covering checks 11–18: a
  `SecretStr` is withheld whatever the field name; **each** of the four shapes on the shape roster
  is redacted span-wise with the surrounding text surviving; a credential nested mapping-in-list-in-
  mapping does not appear; a value at depth 7 is withheld rather than emitted unexamined; a
  credential in an exception's message does not appear in the rendered record; a withheld value is
  present as the marker rather than missing; a value whose inspection raises is withheld while the
  record is still emitted and the logging call does not raise; a cyclic structure terminates.

### Implementation for User Story 2

- [X] T018 [US2] Create `src/hermes_memory/observability/redaction.py`: the two rosters exactly as
  contracts/observability.md lists them, `REDACTED = "[redacted]"`, name matching by lowercasing
  and splitting on runs of non-alphanumeric characters and testing segments and adjacent pairs —
  never substrings (research.md R6) — and shape matching by compiled patterns replacing only the
  matched span.
- [X] T019 [US2] Add the walker to the same module: mappings and sequences to a maximum depth of 6,
  the value replaced by the marker at the limit; anything not a mapping, sequence, string, number,
  boolean or `None` rendered with `repr()` and then shape-scanned; every per-value step inside a
  guard so that an exception withholds that value and the record is still emitted (research.md R9).
- [X] T020 [US2] Wire the processor into the redaction slot of
  `src/hermes_memory/observability/logging.py` — immediately before `JSONRenderer` and after
  `format_exc_info`, which is the ordering the guarantee depends on (research.md R2) — including in
  the import-time default configuration and in the `foreign_pre_chain` for standard-library
  records. Export `REDACTED` from `__init__.py`. Observe T016 and T017 pass.

**Checkpoint**: Principle V holds for the log surface. With Phase 3, this is the shippable
increment.

---

## Phase 5: User Story 3 — Content on, deliberately, for one session (Priority: P2)

**Goal**: conversation bodies absent by default, present behind one explicit flag that can never
expose a credential.

**Independent Test**: emit a body with the flag unset and observe it absent; set the flag, emit the
same body, observe it present.

### Tests for User Story 3 ⚠️

- [X] T021 [P] [US3] Write `tests/unit/test_conversation_content.py` covering checks 19–24: with no
  configuration at all a `ConversationContent` does not appear; with the flag off, the same; with
  the flag on it appears; with the flag on a credential in the same record is still withheld;
  content beyond the cap is truncated and marked with `…[truncated]`; `ConversationContent`'s own
  `__repr__` and `__str__` do not reveal the text.

### Implementation for User Story 3

- [X] T022 [US3] Add `ConversationContent` to `src/hermes_memory/observability/redaction.py`: a
  frozen wrapper rendering as `[redacted:content]` unless the flag is on, with `__repr__` and
  `__str__` withholding the text (research.md R8), and a documented truncation cap applied when the
  flag is on.
- [X] T023 [US3] Have `configure()` pass `settings.logging.include_conversation_content` into the
  processor, defaulting to off when `configure()` has not run, and export `ConversationContent`
  from `__init__.py`. Observe T021 pass.

**Checkpoint**: the escape hatch exists and cannot be turned into a credential leak.

---

## Phase 6: User Story 4 — A later span has somewhere to attach (Priority: P2)

**Goal**: a tracer provider this project owns, and automatic log/trace correlation.

**Independent Test**: request a span, emit a record inside it, and assert the record carries the
identifiers tying it to that span.

### Tests for User Story 4 ⚠️

- [X] T024 [P] [US4] Write `tests/unit/test_tracing.py` covering checks 30–32: a span can be
  started and ended and no network call is made; a record emitted inside a span carries `trace_id`
  and `span_id`; a record emitted outside a span carries neither.

### Implementation for User Story 4

- [X] T025 [US4] Create `src/hermes_memory/observability/tracing.py`: a `TracerProvider` built with
  an explicit `Resource` of `service.name = "hermes-memory"` and `service.version` from the
  installed distribution, with **no** span processor and **no** exporter (research.md R11), set
  once per process behind a module-level flag; plus `get_tracer(name)` and the correlation
  processor adding `trace_id` and `span_id` as lowercase hexadecimal only when the current span
  context is valid.
- [X] T026 [US4] Wire the correlation processor into its slot in
  `src/hermes_memory/observability/logging.py` — before redaction, so the ids pass through it like
  any other field — construct the provider in `configure()`, and export `get_tracer` from
  `__init__.py`. Observe T024 pass.

**Checkpoint**: all four stories are independently functional.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [X] T027 [P] Write `tests/structure/test_logging_surface.py` (check 33): parse the committed
  sources and assert that no module outside `src/hermes_memory/observability/` calls
  `logging.basicConfig`, adds a handler, calls `structlog.configure`, or writes to `sys.stdout` or
  `sys.stderr` — asked of the parsed tree rather than by grepping, as
  `tests/structure/test_environment_files.py` does for the environment.
- [X] T028 [P] Add a short Logging section to `README.md`: the two variables, what the flag does and
  what it does not do, and that records are JSON on standard error.
- [X] T029 Run every step of [quickstart.md](quickstart.md) by hand and confirm each expected
  outcome, including step 4's `author` field surviving and step 5's token staying redacted with the
  flag on.
- [X] T030 Run `uv run pytest`, `uv run ruff check .` and `uv run ruff format --check .`; quote the
  output in the pull request's verification section rather than asserting that they passed.

---

## Dependencies & Execution Order

### Phase dependencies

- **Setup (Phase 1)**: no dependencies.
- **Foundational (Phase 2)**: needs Phase 1 — blocks every user story.
- **US1 (Phase 3)** and **US2 (Phase 4)**: both need Phase 2; independent of each other
  (`operations.py` and `redaction.py` are different files).
- **US3 (Phase 5)**: needs US2 — it extends the redaction processor.
- **US4 (Phase 6)**: needs Phase 2 only; independent of US1–US3.
- **Polish (Phase 7)**: needs everything it documents.

### Within each story

Tests are written and observed to fail before the implementation. No exceptions: a task that skips
it is not done (Principle III).

### Parallel opportunities

- T012 and T013 (US1 tests) with T016 and T017 (US2 tests) — different files, different stories.
- T024 (US4 tests) at any point after Phase 2.
- T027 and T028 in Polish.
- US1 and US4 can be worked by different people simultaneously once Phase 2 lands.

---

## Implementation Strategy

**The MVP is US1 *and* US2, not US1 alone.** The template's usual advice is to ship the first P1
story; here that would mean a log surface that reports operations and leaks credentials, which
Principle V forbids outright. US1 is the first increment to build, US2 is the one that makes the
increment shippable, and they are listed separately because they are testable separately — not
because either ships without the other.

After that, US3 and US4 are genuine increments: each adds value and neither is load-bearing for
the two before it.
