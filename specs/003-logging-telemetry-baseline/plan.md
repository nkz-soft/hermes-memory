# Implementation Plan: Logging and Telemetry Baseline

**Branch**: `003-logging-telemetry-baseline` | **Date**: 2026-09-14 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/003-logging-telemetry-baseline/spec.md`, derived from
GitHub issue #6 (Phase 1, wave 2; depends on #4, merged as PR #33).

## Summary

Fill the `observability` boundary with the pipeline that makes ARCHITECTURE.md §18 and Principle V
true by construction: a structlog chain rendering one JSON object per record to standard error, a
context manager that binds the §18 field set and emits exactly one record per ingestion operation
with a duration it measured itself, a redaction processor sitting immediately before the renderer,
and an OpenTelemetry tracer provider for a later span around `retain` to attach to.

Three ideas in it beyond the obvious assembly.

First, **the redaction step is a processor, not a convention**. It runs after every other processor
has contributed its keys and after the traceback has been rendered to a string, so there is no
position from which a field can reach the renderer unexamined ([research.md](research.md) R2). The
constitution's "credentials, tokens and authorization headers are never logged" stops being a rule
each future call site must remember, which is exactly what the issue asks for.

Second, **the pipeline is installed at import, not at `configure()`** (R3). The moment a leak is
most likely is while reporting a failure — including a failure to load the settings that
`configure()` needs — so the unconfigured default has to be the safe one.

Third, **the name roster matches segments rather than substrings** (R6). A redactor that eats
`author` in a project about conversations is a redactor contributors route around, and a
security control that gets worked around protects nothing.

## Technical Context

**Language/Version**: Python 3.13, as pinned by the skeleton.

**Primary Dependencies**: `structlog`, `opentelemetry-api`, `opentelemetry-sdk` — three runtime
dependencies added, all three fixed by the constitution's Technology Stack table (Logging,
Telemetry). `pydantic` and `pydantic-settings` unchanged from 002. No new development dependency.

**Storage**: none. Records go to standard error; nothing is written to disk.

**Testing**: pytest. New suites under `tests/unit/` for the pipeline, the redaction rosters, the
operation record and the tracer; `tests/structure/` gains the invariant that nothing outside
`observability/` configures logging. Tests assert over **rendered** output, never over
`structlog.testing.capture_logs`, which bypasses the processors and would make every redaction test
pass vacuously (R13).

**Target Platform**: developer machines (Windows, macOS, Linux) and `ubuntu-latest` in CI.

**Project Type**: single Python package, `src/` layout, unchanged.

**Performance Goals**: none stated, and the honest reason is that the record rate is bounded by the
import rate — one record per conversation, against a pipeline that is doing network I/O and LLM
extraction per conversation. The redactor's walk is bounded by depth 6 and by the size of a record,
so it cannot become the thing that is slow.

**Constraints**: no network call, no file created (FR-019, contract). No credential and no
conversation body in any record (Principle V). Nothing outside `settings.py` reads the environment
(FR-021) — with the OpenTelemetry SDK's own `OTEL_*` contract noted below. CI must keep running on
fork pull requests, so every credential in the new tests is a literal invented in the test.

**Scale/Scope**: 5 modules in one boundary, 2 settings, 12 name-roster entries and 4 shape-roster
entries, 34 contract checks, 3 runtime dependencies, 2 existing tests changed on purpose.

## Constitution Check

*GATE: passed before Phase 0 research; re-evaluated after Phase 1 design — see below.*

| Principle | Compliance |
|---|---|
| **I — Raw Archive Is the Source of Truth** | Not engaged. Nothing here reads, writes or derives history, and a log record is not an archive: it is not re-runnable input and nothing may ever reconstruct a conversation from one. The content flag makes that tempting to forget, which is why it is default-off, capped and marked — a truncated body in a debugging session is diagnostic output, never a second copy of the source of truth. |
| **II — Provenance and Stable Identity** | Engaged as a consumer, not as an author. The §18 record carries `source`, `source_id` and `document_id` because those are the provenance facts the principle fixes, and it carries them as the caller derived them — this feature derives no identifier and invents no timestamp. `start_time` is the operation's, explicitly a measurement of the import run and never a substitute for the conversation's real time, which this feature never touches. |
| **III — Test-First (NON-NEGOTIABLE)** | Engaged, and it orders the work. Every one of the 34 checks in [contracts/observability.md](contracts/observability.md) is written before the code and observed to fail. The order that matters most is the redaction block: the name roster, the shape roster and the nesting cases are written against a processor that does not exist, so the first run proves the assertion can fail — which for a redaction test is the only thing that distinguishes it from a test that would pass on an empty pipeline. R13's trap is the same concern one level down, and the fixture that captures rendered output carries a comment saying so. |
| **IV — Replaceable Boundaries** | Engaged. `observability` is one of the §8 boundaries, and [contracts/observability.md](contracts/observability.md) states what consumers may rely on so that later features depend on the contract rather than on structlog. No Hindsight type, endpoint or vocabulary appears: `bank` is a string the caller passes, which is what a replacement memory engine would also call it. The dependency direction is one-way — `observability` imports `settings` and nothing else of ours — so no other boundary is constrained by this one's internals. |
| **V — Secrets Never Reach the Memory Engine** | Engaged, and this is the feature's purpose for the log surface specifically. The two clauses the issue quotes — conversation contents not logged by default, credentials and tokens never — become properties of the pipeline (FR-008 through FR-016). The redaction that this principle's *first* sentence is about, sanitizing content before it leaves the process for Hindsight, is ARCHITECTURE.md §13's sanitizer and is separate work; R7 records the boundary explicitly, because the failure mode is someone later mistaking this for that and shipping without §13. Redaction replaces the matched span rather than dropping the enclosing text, which is the form this principle requires. |

**Technology Stack compliance**: structlog is the fixed entry for Logging and OpenTelemetry for
Telemetry, and this feature uses both as fixed. `opentelemetry-api` and `opentelemetry-sdk` are the
two distributions that OpenTelemetry-for-Python is packaged as — the API for callers, the SDK for
the process that configures a provider — not two choices. Nothing is displaced and no competing
library is introduced, so the constitution's "changing any entry, or adding a dependency that
displaces one" clause is not triggered and no decision record is required. This matches the issue's
governance answer of "None of the above". No exporter distribution is added (R11).

**The OpenTelemetry SDK reads its own `OTEL_*` environment variables.** Recorded here rather than
left for a reviewer to discover: building a tracer provider consults `OTEL_SDK_DISABLED`,
`OTEL_SERVICE_NAME` and others. That is the SDK's published contract with operators — the same kind
of thing as httpx honouring `HTTP_PROXY` — and not this project reading configuration outside
`settings.py`. Every value *this project* reads still arrives on the settings object (FR-021), the
resource attributes are passed explicitly so they do not depend on the ambient environment, and
SC-008's check, which inspects this repository's own sources, stays true.

**Two existing tests change on purpose, in the commits that require them** (R14):

- `tests/structure/test_packaging.py::test_runtime_dependencies_are_exactly_the_declared_set`
  expects exactly `pydantic` and `pydantic-settings`. It gains the three above, with the stack-table
  row that permits each named in its docstring. Still a guard, now over five.
- `tests/structure/test_module_layout.py::test_recorded_modules_carry_no_behaviour` asserts that
  every recorded boundary holds nothing but docstrings. `observability` stops being one. The module
  gains an explicit set of boundaries that have been filled — `{"observability"}` — so the other
  fourteen stay guarded and filling one is a deliberate edit in the feature's own commit. Its
  companion `test_the_behaviour_guard_still_bites` builds its fixture from `archive/`, so it keeps
  proving the narrowed guard still fails on the case it exists for.

Both are called out because a reviewer seeing a weakened assertion should be able to find the
sentence that authorised it.

**The §8 / module-tree conflict raised by 001 is untouched.** 001 noted that §8 lists an *Import
state* boundary the constitution's module tree has no module for. This feature neither stores
import state nor needs that boundary, so the conflict still awaits the feature that does.

**Branch naming**: `003-logging-telemetry-baseline`, matching the feature directory, per the
Development Workflow section. Created by hand because the `before_specify` hook is not installed
here.

**Post-design re-evaluation**: unchanged, no violations. Phase 1 added one boundary contract, one
data model and no behaviour beyond what the Constitution Check above describes. The design decision
with the most weight — putting redaction in the pipeline rather than at call sites — moves towards
Principle V rather than away from it, and the second-heaviest — declining to add an exporter and
its setting — removes an untested seam rather than adding one. The Complexity Tracking table below
stays empty.

## Alternatives Considered

The issue records one rejected alternative; research produced the rest. Full reasoning in
[research.md](research.md).

| Alternative | Rejected because |
|---|---|
| **Plain `logging` with a documented convention** (the issue's alternative) | The constraint is enforceable only if redaction lives in the pipeline. A convention holds where someone remembered it, and the places that will log have not been written yet. |
| Redaction as the first processor, or inside the renderer (R2) | First: it runs before exception rendering and context merging and misses both. Inside the renderer: the guarantee becomes a property of the output format, so a later human-readable renderer ships without it. |
| Lazy configuration on first use, or requiring `configure()` first (R3) | A third-party library logging through the standard library never calls our surface; and failing loudly on an unconfigured log is a second failure raised at the worst moment — while reporting the first. |
| Leaving standard-library logs alone, or silencing them (R5) | httpx logging a URL with credentials in it is precisely the leak Principle V forbids; silencing hides the retry and connection detail §18's error reporting needs. |
| Substring matching on field names (R6) | `auth` matches `author`, and this project's domain has authors. A redactor that eats real fields gets worked around. |
| An allow-list of permitted field names (R6) | Unworkable against a field set that grows with every feature. |
| High-entropy detection, or a secret scanner in the log path (R7) | Fires on hashes, base64 payloads and document ids, which this project logs by design; or adds an unfixed dependency to every log line to do §13's job badly. |
| A roster of conversation-content field names (R8) | Fails open for the next field someone invents. The wrapper makes it the caller's explicit act and protects the value everywhere, not only in the log. |
| No depth limit plus cycle detection (R9) | More machinery for a case a finite limit already covers. |
| Dropping unknown objects instead of `repr()` + shape scan (R9) | Removes the diagnostic value of logging an object at all; the shape roster is what makes the `repr` safe. |
| `opentelemetry-instrumentation-logging` (R10) | A third distribution, outside the stack table, to add two fields we add in six lines. |
| Adding the OTLP exporter and an endpoint setting now (R11) | A seam whose only implementation is unreachable rots, and the feature that actually exports will want to choose its exporter against a real collector. |
| The API's no-op provider instead of the SDK (R11) | It produces invalid span contexts, so correlation could never be tested, and the next feature would introduce the SDK anyway. |
| `structlog.testing.capture_logs` in the redaction tests (R13) | It hands back the event dictionary as the caller built it, credential intact. The test would pass while proving nothing — the one failure mode these tests exist to prevent. |

## Project Structure

### Documentation (this feature)

```text
specs/003-logging-telemetry-baseline/
├── spec.md                    # Feature specification
├── plan.md                    # This file
├── research.md                # Phase 0 output — R1..R14
├── data-model.md              # Phase 1 output — the record, the markers, the rosters
├── quickstart.md              # Phase 1 output — validating the deliverable by hand
├── contracts/
│   └── observability.md       # Phase 1 output — the boundary, and its 34 checks
├── checklists/
│   └── requirements.md        # Specification quality checklist
└── tasks.md                   # Phase 2 output (/speckit-tasks — NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
.env.example                            # + HERMES_LOGGING__LEVEL, __INCLUDE_CONVERSATION_CONTENT
pyproject.toml                          # + structlog, opentelemetry-api, opentelemetry-sdk
uv.lock                                 # Re-resolved, committed
README.md                               # + a short Logging section

src/
└── hermes_memory/
    ├── settings.py                     # CHANGED: + LoggingSettings group
    └── observability/
        ├── __init__.py                 # CHANGED: the public surface; installs the pipeline
        ├── logging.py                  # NEW: the processor chain, stdlib bridge, get_logger
        ├── redaction.py                # NEW: the processor and the two rosters
        ├── operations.py               # NEW: the §18 record and ingestion_operation
        └── tracing.py                  # NEW: the provider, get_tracer, span correlation

tests/
├── structure/
│   ├── test_packaging.py               # CHANGED: guards five runtime dependencies
│   ├── test_module_layout.py           # CHANGED: observability recorded as filled
│   └── test_logging_surface.py         # NEW: nothing outside observability/ configures logging
└── unit/
    ├── conftest.py                     # CHANGED: + the rendered-output capture fixture
    ├── test_redaction_names.py         # NEW: checks 8-10
    ├── test_redaction_values.py        # NEW: checks 11-18
    ├── test_conversation_content.py    # NEW: checks 19-24
    ├── test_operation_record.py        # NEW: checks 1-7
    ├── test_logging_configuration.py   # NEW: checks 25-28
    └── test_tracing.py                 # NEW: checks 30-32
```

**Structure Decision**: five modules inside the existing `observability` package (R1). The boundary
is one the constitution already records, so nothing is added to the module tree and no amendment is
implied. Splitting redaction into its own module is deliberate: it is the part a reviewer will want
to read on its own, and the part whose rosters change over time.

A file named `logging.py` inside a package does not shadow the standard library — implicit relative
imports do not exist in Python 3 — so the module is named for what it holds rather than renamed
around a hazard the language removed.

## Deferred, deliberately

Named so a reviewer can see these were considered rather than forgotten:

- **Any exporter, and any trace destination setting** (R11). The provider is the seam; the feature
  that has spans to export chooses the exporter against a real collector.
- **Metrics.** §18 asks for logs per operation; the issue asks for the tracer. A metrics pipeline
  before anything is measured is configuration with no reader.
- **The span around `retain`.** It belongs to the feature that makes the call — this baseline
  exists so that it has somewhere to attach.
- **Actually logging from anywhere.** No other module calls `get_logger` in this feature. The
  pipeline and the CLI wire it in when they exist; doing it now creates dependency directions with
  nothing at the other end, exactly as 002 declined to do for `settings`.
- **A human-readable console renderer.** The guarantees are stated over the machine-readable form,
  and a second renderer is a second thing to prove redaction for. It is a convenience, and it can
  arrive behind the same processor chain when someone wants it.
- **Sampling, log rotation, a file destination.** Standard error is the destination; whatever runs
  the process decides where that goes.
- **ARCHITECTURE.md §13's sanitizer, and Gitleaks.** Still separate work. R7 records why this
  feature must not be mistaken for either.

## Complexity Tracking

> Fill ONLY if Constitution Check has violations that must be justified

No violations. No deviation from the constitution is taken, and no entry in the fixed technology
stack is changed, displaced or added to in a way that requires a decision record. The two existing
tests that change do so under sentences their own authors wrote for that purpose, and both remain
guards afterwards.
