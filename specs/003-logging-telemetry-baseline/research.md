# Research: Logging and Telemetry Baseline

Phase 0 output for [plan.md](plan.md). Each item is a decision, why it was taken, and what was
rejected. The technology is fixed by the constitution's Technology Stack table — structlog for
logging, OpenTelemetry for telemetry — so nothing here re-opens that; what is open is how the
guarantees of ARCHITECTURE.md §18 and Principle V become properties of the pipeline rather than
rules a caller has to remember.

## R1 — Where the baseline lives

**Decision**: inside the existing `observability` package, as
`src/hermes_memory/observability/`, with the public surface re-exported from its `__init__.py`:

```text
observability/
├── __init__.py      # configure(), get_logger(), get_tracer(), ingestion_operation(), the markers
├── logging.py       # the structlog pipeline and stdlib interoperability
├── redaction.py     # the redaction processor and the two rosters
├── operations.py    # the §18 record and the context manager that emits it
└── tracing.py       # the tracer provider and the log/trace correlation processor
```

**Rationale**: `observability` is one of the fifteen boundaries the constitution's module tree
records; this is the feature that fills it. No module is added, so no amendment is implied — which
matches the issue's "None of the above" governance answer.

A file named `logging.py` inside a package does not shadow the standard library: implicit relative
imports do not exist in Python 3, so `import logging` from any sibling resolves to the standard
module. It is named for what it is rather than renamed to avoid a hazard that Python removed in
2008.

**Alternatives considered**: a single `observability.py` module — rejected because the redaction
roster is the part a reviewer will want to read on its own, and burying it in a 500-line module
makes the security-relevant code the hardest to find. A top-level module next to `settings.py`, as
002 chose for configuration — rejected because, unlike configuration, observability *is* one of the
recorded boundaries.

## R2 — Shape of the structlog pipeline

**Decision**: one processor chain, configured once, rendering JSON to standard error:

```text
merge_contextvars → add_log_level → TimeStamper(iso, utc) → StackInfoRenderer
  → format_exc_info → correlate_with_span → redact → JSONRenderer
```

Two positions in that order carry the guarantees and are not free to move:

* **`format_exc_info` before `redact`.** structlog renders `exc_info` into a plain string under the
  `exception` key. Placed after redaction, that string would be assembled out of exception
  arguments and traceback frames *after* the only step that inspects values — and an exception
  carrying a token in its message is an ordinary thing (FR-016).
* **`redact` immediately before the renderer.** Every other processor has finished contributing
  keys by then, so nothing can add a field behind redaction's back. A processor added later in this
  project's life is inserted before it, never after.

**Rationale**: this is the one ordering under which "no credential in a record" is a property of
the pipeline. Any other placement makes it a property of which processors happen to be installed.

**Alternatives considered**: redaction as the first processor — rejected, it would run before
exception rendering and before context merging, missing both. Redaction inside a custom renderer —
rejected, it couples the guarantee to the output format, so a later human-readable renderer would
silently ship without it.

## R3 — The pipeline must protect lines emitted before it is configured

**Decision**: `observability/__init__.py` installs the chain at import time, as a module-level call
taking no arguments and reading nothing. `configure(settings)` later refines the level and the
content flag by reconfiguring the same chain.

**Rationale**: FR-024. structlog's default configuration renders to the console through
`ConsoleRenderer` with no redaction, so a component that logs before `configure()` runs — an
import-time warning, a failure while loading the settings themselves — would emit unredacted. The
default has to be the safe one, because the unsafe default only shows itself in the incident.

Import time is safe to do this in because the call reads no environment, opens no file and makes no
network connection: the settings object is consulted only by `configure()`, so FR-021 holds and
importing the package stays free of side effects beyond installing a formatter.

**Alternatives considered**: lazy configuration on the first `get_logger()` call — rejected because
a library logging through the standard library never calls it. Requiring `configure()` before any
logging and failing loudly otherwise — rejected: the moment it is most likely to be violated is
while reporting a failure, which is the worst time to raise a second one.

## R4 — Idempotent initialisation

**Decision**: `configure()` is safe to call repeatedly. `structlog.configure()` replaces the
configuration wholesale rather than appending, so structlog needs nothing; the two things that do
are the standard-library handler and the OpenTelemetry tracer provider. The handler we install is
tagged with an attribute and any previously tagged handler is removed before the new one is added.
The tracer provider is set once per process, guarded by a module-level flag, because
`trace.set_tracer_provider` ignores a second call and logs a warning.

A test asserts that configuring twice and logging once yields exactly one line (FR-023).

**Rationale**: a duplicated handler is the classic way structured logs become double-counted, and
it is invisible in any test that only asserts a line *is* present.

**Alternatives considered**: refusing a second call — rejected, tests configure per case, and a CLI
that configures at startup and again after reading a `--verbose` flag is an ordinary shape.

## R5 — Standard-library interoperability

**Decision**: route the standard library's records through the same chain using
`structlog.stdlib.ProcessorFormatter` with a `foreign_pre_chain`, attached to the root logger on a
single handler writing to standard error.

**Rationale**: FR-001 says every component uses one surface, and the components this project will
actually depend on — httpx, the OpenTelemetry SDK, urllib3 underneath them — log through the
standard library and will never call ours. Left alone, those lines arrive unstructured *and*
unredacted, and httpx logging a request URL with credentials in it is the exact leak Principle V
forbids. Sharing the chain makes the guarantee cover them.

**Alternatives considered**: leaving foreign logs alone — rejected for the reason above. Silencing
third-party loggers entirely — rejected: it hides the retry and connection detail that §18's error
reporting will need, and a silenced logger is a leak waiting for someone to re-enable it.

## R6 — What "sensitive field name" means, exactly

**Decision**: a key is sensitive when its name, lowercased and split on non-alphanumeric
characters, contains one of a documented roster of segments, or an adjacent pair from a small
roster of pairs. Both rosters live in `redaction.py` and are reproduced in
[contracts/observability.md](contracts/observability.md).

* Segments: `token`, `secret`, `password`, `passwd`, `credential`, `credentials`, `authorization`,
  `cookie`, `cookies`, `jwt`, `bearer`, `apikey`.
* Pairs: `api`+`key`, `access`+`key`, `private`+`key`, `secret`+`key`, `auth`+`header`,
  `auth`+`token`.

**Rationale**: substring matching over the whole key is the obvious implementation and it is wrong
in a way that matters here. `auth` as a substring redacts `author`, and this project's domain is
conversations that have authors; a redaction rule that eats a legitimate field teaches contributors
to work around the redactor, which is a worse outcome than the field it protected. Segment matching
catches `hindsight_token`, `HTTP_AUTHORIZATION` and `llm.api_key` while leaving `author` and
`document_id` alone.

`key` alone is deliberately not a segment: `bank_key`, `sort_key` and `idempotency_key` are all
plausible in this project and none is a credential, so `key` is matched only in a pair.

**Alternatives considered**: an allow-list of permitted field names — rejected as unworkable
against a field set that grows with every feature, and it fails open in the direction that matters
least. Regular expressions per key — rejected: the same result, less readable, and each addition
becomes a small puzzle.

## R7 — The credential-shape roster, and where it stops

**Decision**: a small roster of unmistakable shapes, matched against string values whatever the key
is called, replacing the matched span and leaving the surrounding text intact:

* an `Authorization`-style prefix followed by a token — `Bearer …`, `Basic …`;
* a JSON web token — three base64url segments separated by dots, first segment beginning `eyJ`;
* a conventionally prefixed API key — `sk-`, `sk-ant-`, `ghp_`, `gho_`, `ghs_` and the like,
  followed by a long enough run of key characters;
* credentials embedded in a URL's userinfo — `scheme://user:password@host`.

**Rationale**: FR-011 and the acceptance criterion in the issue, which logs a token-shaped value
and expects it not to appear. Replacing the span rather than the field mirrors Principle V's rule
for sanitization — "replace the secret value while preserving the surrounding context rather than
dropping the enclosing text" — so a log line stays readable around the hole.

**This is explicitly not a secret scanner.** ARCHITECTURE.md §13's sanitizer is separate work with
its own specification, operating on conversation content bound for the memory engine, where a
missed secret is replicated into facts and the graph. The roster here is the last line of defence
for a log line under an innocuous key name. The distinction is recorded because the failure mode is
someone later assuming the log redactor is the sanitizer, and shipping without §13.

**Alternatives considered**: high-entropy string detection — rejected: it fires on base64 payloads,
hashes and document ids, which this project logs by design, and a redactor that eats real fields
gets disabled. Reusing a scanner such as detect-secrets or Gitleaks in the logging path — rejected:
a dependency the stack table does not fix, added to run on every log line, to do a job §13 will do
properly elsewhere.

## R8 — Marking conversation content

**Decision**: a caller marks content by wrapping it: `ConversationContent(text)`, a frozen wrapper
whose `__repr__` and `__str__` do not reveal the text. The redactor emits the text only when the
content flag is on, and truncates it to a documented cap with an explicit marker when it does.

**Rationale**: FR-014 needs a way to tell a conversation body from any other string, and inferring
it from field names would be guesswork that fails open. A wrapper makes it the caller's explicit
act, and gives the same defence in depth `SecretStr` gives credentials: even a stray
`f"{content}"` at a call site outside the logging path reveals nothing. The truncation cap answers
the edge case of an enabled flag turning a 2 MB conversation into a single log line.

**Alternatives considered**: a roster of content field names — rejected, it fails open for the next
field someone invents. A plain string plus a per-call keyword — rejected, the protection then
depends on the caller passing the keyword, which is the discipline FR-008 exists to remove.

## R9 — Descending into structures, and failing closed

**Decision**: the redactor walks mappings and sequences to a depth of 6. At the limit it replaces
the value with the marker rather than emitting it unexamined. Anything that is not a mapping,
sequence, string, number, boolean or `None` is rendered with `repr()` and the shape roster is
applied to the result. Every per-value step runs inside a guard: an exception anywhere in
inspection replaces that value with the marker and the record is still emitted (FR-017).

**Rationale**: FR-012 and FR-017, and the direction of failure is the whole point — a redactor that
raises takes down the caller, and a redactor that gives up and emits has leaked. Six levels is
deeper than any record this project plausibly emits and finite, so a cyclic structure terminates
without needing a separate visited-set.

`repr()` on an unknown object is the risky-looking half: an object holding a token may put it in
its `repr`. That is precisely why the shape roster runs over the result rather than the value being
passed to the JSON renderer's fallback, which would emit it untouched.

**Alternatives considered**: no depth limit plus cycle detection — rejected, more machinery for a
case the limit already covers. Dropping non-primitive values entirely — rejected, it removes the
diagnostic value of logging an object at all.

## R10 — Correlating logs with spans

**Decision**: a processor asks OpenTelemetry for the current span and, when its context is valid,
adds `trace_id` and `span_id` as the conventional lowercase hexadecimal strings. When no span is
active it adds nothing (FR-020).

**Rationale**: correlation has to be automatic to be worth anything — a caller who has to pass the
ids will not — and adding empty ids to every line outside a span would double the noise for no
information.

**Alternatives considered**: `opentelemetry-instrumentation-logging` — rejected: a third
dependency, outside the stack table, to add two fields we can add in six lines.

## R11 — How much OpenTelemetry to take, and what is not configured

**Decision**: `opentelemetry-api` and `opentelemetry-sdk`, and nothing else. `configure()`
constructs a `TracerProvider` with an explicit `Resource` naming the service and version, installs
no span processor and no exporter, and this feature adds **no** trace-destination setting.

**Rationale**: the issue asks for a tracer "so a later span around retain has somewhere to attach",
which is the provider. An exporter means at least one more distribution and a wire protocol, in
service of a setting nothing in the repository would exercise — a seam whose only implementation is
unreachable rots, and the first feature to actually export will want to choose its exporter against
a real collector. With no span processor installed, starting and ending a span costs an allocation
and exports nothing, which is FR-019 by construction rather than by configuration.

**A note a reviewer should not have to discover**: the OpenTelemetry SDK reads its own `OTEL_*`
environment variables — `OTEL_SDK_DISABLED`, `OTEL_SERVICE_NAME` and others — when it builds a
provider. That is the SDK's published contract with operators, the same way httpx honours
`HTTP_PROXY`, and it is not this project reading configuration outside `settings.py`: every value
*this* project reads still comes through the settings object (FR-021), and the resource attributes
we care about are passed explicitly so they do not depend on the ambient environment. SC-008's
check inspects this repository's own sources, and remains true.

**Alternatives considered**: adding the OTLP exporter and an endpoint setting now — rejected above.
Skipping the SDK and using the API's no-op provider — rejected: a no-op provider produces invalid
span contexts, so R10's correlation could never be tested, and the next feature would have to
introduce the SDK anyway.

## R12 — Settings this feature adds

**Decision**: one nested group, `LoggingSettings`, defaulted so that absent configuration is valid:

| Variable | Type | Default |
|---|---|---|
| `HERMES_LOGGING__LEVEL` | one of the standard level names | `INFO` |
| `HERMES_LOGGING__INCLUDE_CONVERSATION_CONTENT` | boolean | `false` |

Both are added to `.env.example`, which 002's check compares against the declared settings in both
directions, so omitting them fails the suite (FR-022).

**Rationale**: this is the shape 002 established, and its `_declared_variables` walk already
descends into nested groups, so the roster and the credential detection extend to the new group
with no change to `settings.py` beyond the group itself. The group needs no entry in
`_always_descend_into_the_groups`, because every field has a default and an absent group is
therefore valid — unlike `hindsight` and `llm`, where the descent exists to name a missing leaf.

**Alternatives considered**: a `HERMES_LOG_LEVEL` flat variable — rejected, it breaks the grouping
convention 002 set. Naming the flag `DEBUG` — rejected: it reads as a level and would be set by
someone wanting verbosity, not by someone consenting to conversation text in their terminal. The
name has to say what it does.

## R13 — Capturing output in tests, and one trap

**Decision**: tests assert over rendered output, captured by configuring the pipeline to write to
an in-memory stream and parsing the JSON lines back. A fixture does the configuring and restores
the previous configuration afterwards.

**`structlog.testing.capture_logs` must not be used for the redaction tests.** It replaces the
processor chain with a capturing one, so it hands back the event dictionary *as the caller built
it* — credential intact. A redaction test written against it passes while proving nothing, and it
is the most natural thing for a contributor to reach for. It is called out here, in the contract,
and in a comment on the fixture, because this is the test that would fail open.

**Rationale**: SC-002 is stated over "the captured output" for this reason. What must be true is
that the bytes leaving the process carry no credential; only the rendered form is those bytes.

**Alternatives considered**: `caplog` — same trap, one layer lower: it captures standard-library
records before our formatter runs. It is fine for asserting that a third-party line was *emitted*,
never for asserting what it contained.

## R14 — The two existing structure tests this feature changes

**Decision**: both change on purpose, in the commit that requires them.

* `tests/structure/test_packaging.py::test_runtime_dependencies_are_exactly_the_declared_set`
  currently expects exactly `pydantic` and `pydantic-settings`. It gains `structlog`,
  `opentelemetry-api` and `opentelemetry-sdk` — all three fixed by the stack table's Logging and
  Telemetry rows, so no decision record is required and the docstring says which row permits each.
* `tests/structure/test_module_layout.py::test_recorded_modules_carry_no_behaviour` asserts that
  every recorded boundary holds nothing but docstrings. `observability` stops being one. Rather
  than deleting the check or widening it, the module gains an explicit set of boundaries that have
  been filled — `{"observability"}` — so the other fourteen are still guarded, and filling one is
  an edit to that set in the feature's own commit. Its companion
  `test_the_behaviour_guard_still_bites` builds its fixture out of `archive/`, so it keeps proving
  the narrowed guard still fails on the case it exists for.

**Rationale**: 002 established this pattern and the reason for it — a reviewer who sees a weakened
assertion should be able to find the sentence that authorised it. Both remain guards afterwards.

**Alternatives considered**: exempting any module that happens to contain more than a docstring —
rejected, that is the check deleting itself. Moving the implementation outside `observability/` to
keep the check green — rejected, it would put the boundary's code outside the boundary to satisfy a
test, which is the tail wagging the dog.
