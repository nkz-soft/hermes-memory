# Phase 0 — Research: Boundary interfaces and their contract tests

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

No `[NEEDS CLARIFICATION]` marker survived the specification, so nothing here answers an open
question from it. What is here is the design the specification deferred: where the interfaces live,
what shape they take, what an error is, and how a contract suite is run against something.

Four claims were checked by running them rather than reasoning about them (R2, R3, R15). Their
output is quoted where it is used.

---

## R1 — `typing.Protocol`, not an abstract base class

**Decision.** Each boundary is a `Protocol`. Implementations do not inherit from it; they match it
structurally. `@runtime_checkable` is applied only where a test wants to state the intent, and is
never the thing a contract suite relies on.

**Rationale.** ADR-004 chose a stack where contract validation sits at the boundaries rather than in
a compiler, and accepted "less type safety at compile time, which Principle III compensates for by
requiring tests first". A protocol matches that trade exactly: an implementation in `memory/hindsight`
does not import anything from the interface module in order to satisfy it, which is the strongest
possible statement of the dependency direction Principle IV wants. An ABC would invert it — every
implementation would import its boundary to inherit from it, and a shared base class accumulates
helper methods until it is a partial implementation with an interface attached.

`@runtime_checkable` is deliberately not load-bearing: `isinstance` against a protocol checks that
attribute names exist, not that they take the right arguments or behave. A suite that relied on it
would report green for a class with six correctly-named methods that all raise. The contract suite
is the check; the protocol is the declaration.

**Alternatives considered.** ABCs with `@abstractmethod` — rejected above. `zope.interface` or
another declaration library — rejected: a dependency ADR-004 does not list, for something the
standard library does.

---

## R2 — Where each interface lives: the module that owns the responsibility

**Decision.**

| Boundary (§8) | Module | Name |
|---|---|---|
| Conversation source | `ingestion/source.py` | `ConversationSource` |
| Secret sanitizer | `sanitization/sanitizer.py` | `SecretSanitizer` |
| Project classifier | `classification/classifier.py` | `ProjectClassifier` |
| Raw archive | `archive/interface.py` | `RawArchive` |
| Memory store | `memory/interface/store.py` | `MemoryStore` |
| Import state | `ingestion/state.py` | `ImportState` |

No new package is created.

**Rationale.** The constitution fixes the module tree, and `tests/structure/test_module_layout.py`
enforces it in both directions: a recorded module missing from disk fails, and a package on disk
recorded nowhere fails too. A `boundaries/` package would therefore be a constitution amendment —
governance work the issue explicitly ticks "None of the above" against. Every boundary except the
import state has an obvious recorded home, and the constitution already names the memory one: "
`memory/interface` is what every other module depends on".

The import state has no recorded module, and it does not need one. §17 calls it the *importer* side
of idempotency, so it is a file inside `ingestion/`, alongside the source interface. A file is not a
module: the layout check derives packages from directories.

**Checked by running it.** A file placed directly inside a recorded package satisfies the layout
checks but trips the behaviour guard:

```text
$ printf 'VALUE = 1\n' > src/hermes_memory/ingestion/state.py && uv run pytest tests/structure/test_module_layout.py -q
FAILED tests/structure/test_module_layout.py::test_recorded_modules_carry_no_behaviour
AssertionError: These modules contain more than a docstring:
['src/hermes_memory/ingestion/state.py']
1 failed, 6 passed
```

Six passed — including `test_no_unrecorded_modules_exist`, which is the one that would have caught a
new package. The single failure is the guard doing its job, and R15 is how this feature answers it.

**Alternatives considered.** One `boundaries.py` holding all six — rejected: it makes every
implementation module import a file that also declares five boundaries it has nothing to do with,
and it dissolves the mapping the constitution draws between §8's rows and the module tree. All six
in `memory/interface` — rejected: it would make the sanitizer depend on a memory module to know what
a sanitizer is, which is the dependency Principle IV exists to prevent.

---

## R3 — The shared error taxonomy is a top-level module, owned by no boundary

**Decision.** `src/hermes_memory/errors.py` holds `BoundaryError`, `TransientBoundaryError` and
`PermanentBoundaryError`. Each boundary declares its own specific errors in its own module, deriving
from one of the two.

**Rationale.** The taxonomy is consumed by all six boundaries and by the retry policy of #20, and
owned by none of them. That is the same shape as `settings.py`, and this repository has already
settled where such a thing goes: the behaviour guard's own docstring records that `settings.py` is
"configuration, consumed by every boundary and owned by none", placed at the package root rather than
inside a boundary. Putting the base errors inside any one boundary would make the other five import
that boundary to catch a failure.

**Checked by running it.** The top-level placement is invisible to the layout checks — the guard
walks only recorded module directories, and `present_modules()` derives packages from directories
containing Python files, so `src/hermes_memory/errors.py` is neither a module nor guarded behaviour.
That is the precedent `settings.py` already relies on; both layout tests pass over it today
(677 passed on the branch point).

**Alternatives considered.** A single `BoundaryError` per boundary module with no shared base —
rejected: #20 must be able to write one retry policy, and without a shared base it would enumerate
six exception types and be edited by every future boundary. Reusing built-in exceptions (`OSError`,
`ValueError`) — rejected: they are raised by the libraries underneath, so a caller could not tell a
boundary's declared failure from a leak through it, which is exactly the distinction FR-013 exists
for.

---

## R4 — Retryability is structural, not a constructor argument

**Decision.**

```python
class BoundaryError(Exception):
    retryable: ClassVar[bool]


class TransientBoundaryError(BoundaryError):
    retryable: ClassVar[bool] = True


class PermanentBoundaryError(BoundaryError):
    retryable: ClassVar[bool] = False
```

An error declares retryability by which base it derives from. No constructor takes a `retryable`
flag, and the attribute is not writable per instance.

**Rationale.** FR-014 requires that §18's never-retryable conditions — a rejected or unauthorized
request, invalid input — *cannot be expressed* as retryable. A constructor flag makes that a
convention someone has to keep; a class hierarchy makes it a thing the type will not do, which is the
same move #8 made when it gave `document_id` no setter. It also gives #20 the cheapest possible
policy: `except TransientBoundaryError` and nothing else.

`retryable` remains readable as a property so a caller can report it without matching on a class.

**Alternatives considered.** A flag on the instance — rejected above. An enum of failure kinds —
rejected: it is the same information with an extra lookup, and `except` clauses are how Python
callers already branch on failure.

---

## R5 — What an error carries, and what it must never carry

**Decision.** Every `BoundaryError` carries the boundary it came from, the `source_id` or
`document_id` it concerned when there is one, and a human-readable message. It may carry an
underlying exception as `__cause__`. It carries no conversation content, no credential, no token,
no authorization header, and no request or response body.

**Rationale.** §18 requires each failure to be recorded with its source id, its error and its time,
and §19 plus Principle V forbid conversation content and credentials in logs. An error object is
the thing that gets logged and reported, so the constraint belongs on it and not on each call site
that formats one. The time is the reporter's — an error that timestamps itself would invite the
§11 mistake of a captured clock standing in for a real one.

A caution that is worth writing down rather than discovering: `__cause__` can carry a secret that
the boundary error itself does not. A rejected HTTP request whose URL holds a token is the obvious
case. The memory store's errors therefore state, in their own documentation, that the chained
exception is not safe to render, and the failure report of §18 renders the boundary error alone.

**Alternatives considered.** Carrying the full underlying response for diagnosis — rejected: it is
the fastest path to a token in a log file, and it is not needed for §18's report.

---

## R6 — The sanitizer reports categories from §13, with counts

**Decision.** `RedactionCategory` is a `StrEnum` seeded with the minimum categories §13 lists.
`RedactionReport` carries a count per category and nothing else; an empty report is a report with no
counts, distinct from `None`.

**Rationale.** §13 fixes the minimum list, so it is architecture, not a guess about what #11 will
find. A closed vocabulary is also what keeps a report comparable across runs: free strings would give
`aws_key`, `aws-key` and `AWS key` for one thing, and the report exists to be read by a human deciding
whether redaction is working.

Counts without values is the whole point (FR-004): the report is what gets logged, and a report
carrying the secret it redacted is Principle V defeated by the mechanism that serves it.

**Alternatives considered.** Positions or spans of each redaction — rejected: an offset into the
text plus the archived original reconstructs the secret, which makes the report as dangerous as the
value. Leaving the categories to #11 — rejected: #11 adds *patterns*, and a pattern for a category
§13 already names is not a vocabulary change. #11 may extend the enum; that is expected.

---

## R7 — The classifier returns a project tag, and `unknown` is a value

**Decision.** `classify(conversation) -> ProjectTag`. `classification` exposes
`UNKNOWN_PROJECT: ProjectTag` for the §15 answer. The classifier never raises to mean "no project".

**Rationale.** §6's `project:` tag is the scoping value that reaches the memory store, and #8 already
models it; returning the tag means the enrich stage attaches what classification decided rather than
re-deriving it. `Provenance.project` is the same value's slug, and deriving a slug from a tag is
lossless in the direction that matters.

§15 states plainly that a substantial share of conversations will not resolve, that they are still
imported, and that they stay retrievable because of the shared bank (ADR-002). A boundary that
raised for the ordinary case would make the pipeline's failure path the common path, which FR-017
forbids.

**Alternatives considered.** Returning `Slug` — rejected: the tag is the thing §6 defines and the
thing that is sent. Returning `ProjectTag | None` — rejected: `None` and `unknown` would be two
spellings of one answer, and the second one is the architecture's.

---

## R8 — The archive stores the original alongside the normalized form

**Decision.** `RawArchive` accepts an `EnrichedConversation` together with an `OriginalPayload` —
the bytes the source was read from and their media type — and returns each of them by document id.
`store` is idempotent: storing the same document id twice leaves one document. `load` raises a
declared `ArchiveDocumentNotFound` (permanent) when the document is not held, which is distinct from
an `ArchiveUnavailable` (transient).

**Rationale.** §8's row says "Persist originals and normalized forms" and Principle I requires both,
because the reason to keep an archive is to re-run ingestion after the *parser* changed — and a
re-run from the normalized form alone would replay the old parser's mistakes. If the interface took
only the normalized conversation, Principle I would be unmet by construction and no later feature
could fix it without changing every caller.

What the payload *is* — a file, a slice of a JSON export, a directory layout — is #13's to settle;
the interface carries bytes and a media type so that #13 can choose.

**Alternatives considered.** Normalized form only — rejected above. Two separate interfaces, one per
form — rejected: §8 lists one boundary, and splitting it invites an archive holding one without the
other, which is the failure Principle I is about.

---

## R9 — The memory store's own read side is how idempotence is proved

**Decision.** `MemoryStore` declares exactly `retain(enriched) -> None` and
`recall(query, tags=(), limit=None) -> tuple[RecallResult, ...]`. `RecallResult` carries the content,
the provenance the item was retained with, and an optional score. The contract suite proves FR-010 —
retaining twice creates no duplicate — by recalling, not by inspecting the implementation.

**Rationale.** FR-009 forbids a Hindsight term anywhere in this interface, and the instinctive way
to test "no duplicate" is to expose a count of stored documents, which is a Hindsight-shaped hole in
the abstraction: no memory engine owes us a document count, and a suite that demanded one would fail
against a legitimate implementation. `recall` is the interface's own read side and every
implementation has it.

`score` is optional and generic — every retrieval system ranks — and #23 and #31 will want it. It is
declared as "whatever the implementation means by relevance, comparable only within one result set",
because promising more would be promising something about Hindsight.

**Alternatives considered.** `reflect` alongside `recall` — rejected: §16 uses it in #31 against
accumulated memory, and a method with no caller is a contract nobody has tested. A retain that
returns a receipt — rejected: the receipt would carry the engine's identifiers, which is FR-009
again.

---

## R10 — The skip rule lives in the domain, not in each import-state implementation

**Decision.** `ImportState` declares `record(ImportRecord) -> None` and
`find(source_id) -> ImportRecord | None`. Whether a conversation may be skipped is a function of the
record and the current content hash, defined once in `ingestion/state.py` and not by each store.
`ImportRecord` carries source id, content hash, document id, time and `ImportStatus`
(`imported` / `skipped` / `failed`, §18).

**Rationale.** If each implementation answered "may I skip this?" itself, the SQLite store of #14 and
any later PostgreSQL store could disagree about what counts as unchanged — and the disagreement
would be invisible, because both would pass a suite that asked them the question their own way. A
single domain function means the stores answer only "what do you remember about this source id",
which is the part that genuinely differs between SQLite and anything else.

It also keeps FR-012 true by construction: the decision is local, and no other boundary is consulted.

A failed import is recorded, not omitted (§18, and the spec's edge case about a crash between the
archive write and the retain call): "no record" and "a record saying it failed" must be
distinguishable, or a resume cannot tell a conversation it never reached from one that broke.

**Alternatives considered.** A `seen(source_id, content_hash) -> bool` method — rejected above; it is
the shape that lets two stores define "seen" differently. Recording only successes — rejected: it
makes every failure look like a conversation never attempted.

---

## R11 — A contract suite is a base class the implementation's test subclasses

**Decision.** Each boundary gets a class in `tests/contracts/` — `ConversationSourceContract`,
`SecretSanitizerContract`, and so on — holding the boundary's rules as test methods and one abstract
factory the subclass supplies. An implementation's own test module subclasses it:

```python
class TestInMemoryArchive(RawArchiveContract):
    def make_archive(self) -> RawArchive:
        return InMemoryRawArchive()
```

The base class name deliberately does not start with `Test`, so pytest collects the subclass and not
the abstract base.

**Rationale.** Subclassing is how pytest reuses a suite without a plugin, an entry point or a
conftest that every future feature has to remember to edit. #13 and #16 import one class and get the
whole contract; the suite belongs to the boundary and the implementation supplies itself to it,
which is FR-018 stated in code.

**Alternatives considered.** A parametrized fixture enumerating every implementation — rejected: the
list of implementations would live in this feature, so #13 would have to come back and edit #9's
test file to be tested, and a forgotten edit is a silently untested implementation. A pytest plugin —
rejected: machinery for six classes.

---

## R12 — Fakes live in the test tree, not in the package

**Decision.** `tests/fakes/` holds one in-memory implementation per boundary, plus the deliberately
broken ones R13 needs. Nothing fake ships in `src/`.

**Rationale.** FR-027 says this feature implements no boundary for real, and a fake in the
distribution is an invitation to import it from production code "just for now". The fakes are test
support for #10 through #19, and the test tree is already importable across test modules — `tests/`
is a package with `__init__.py`, and pytest's default prepend import mode makes `tests.fakes.archive`
an ordinary import, which `tests/structure/test_module_layout.py` already relies on for its own
monkeypatching.

**Alternatives considered.** Shipping the in-memory archive in `archive/` as a real MVP
implementation — rejected: #13 specifies the archive, and an in-memory one would be a second
implementation nobody asked for and a tempting default that loses history on exit.

---

## R13 — Every suite is shown to fail

**Decision.** For each boundary, a broken fake violates exactly one rule — an archive that drops a
field, a sanitizer that reports a redaction it did not make, an import state that forgets failures —
and a test asserts the suite fails on it, by calling the contract method directly inside
`pytest.raises(AssertionError)`.

**Rationale.** FR-020, and the precedent this repository already set: `test_the_behaviour_guard_still_bites`
exists because "a weakened assertion that nobody has seen fail is a weakened assertion nobody knows
about". A contract suite is the same risk in a more expensive place — six implementations will be
declared correct by it.

Calling the method directly rather than running a nested pytest session keeps the check cheap and
readable; the repository has done it this way before.

**Alternatives considered.** `pytester` sub-sessions — rejected: slower, and it tests pytest as much
as it tests the suite. Mutation testing — rejected: a tool ADR-004 does not list, for a job six
hand-written breakages do precisely.

---

## R14 — The pipeline harness proves "no I/O" rather than asserting it in prose

**Decision.** `tests/integration/test_pipeline_from_fakes.py` composes the six fakes into §7's
sequence and imports a synthesized conversation. Network is blocked by monkeypatching
`socket.socket` to raise; filesystem writes are blocked by monkeypatching `builtins.open`,
`pathlib.Path.open`, `Path.write_text` and `Path.write_bytes` to raise on any write mode.

**Rationale.** SC-004 is the issue's own acceptance statement, and a test that merely *doesn't*
perform I/O passes equally well on the day someone adds some. Blocking makes the claim falsifiable.

The limit is stated rather than hidden: a determined implementation could reach the filesystem
through `os.open` or a C extension and slip past these guards. They are here to catch the realistic
mistake — a fake that quietly writes a temp file, a source that opens a fixture — not to sandbox a
hostile implementation, and Phase 1's quickstart says so.

**Alternatives considered.** Running the suite in a network namespace or a container — rejected:
infrastructure for an assertion, and not portable to a developer's machine, which is where this
suite has to be cheap enough to run on every change (NFR-003).

---

## R15 — The behaviour guard is narrowed by prefix, and gains a second bite

**Decision.** `FILLED_BOUNDARIES` gains `ingestion`, `sanitization`, `classification`, `archive`
and the dotted `memory.interface`. The guard's filter changes from comparing `module.split(".")[0]`
to matching a recorded module against the filled set by dotted prefix, so that filling
`memory.interface` does not exempt `memory.hindsight`. A new test asserts the sibling case: code
placed in `memory/hindsight/` is still caught while `memory/interface/` is filled.

**Rationale.** As written, the filter takes the first segment only, so adding `memory` to the set
would exempt every module under it — including `memory/hindsight`, the one module the constitution's
merge gate cares most about keeping honest. Filling five boundaries is exactly the moment to notice
that, and the repository's own convention is that narrowing a guard is a deliberate edit in the
commit that needs it, accompanied by proof the narrowed version still bites.

**Alternatives considered.** Adding `memory` and accepting the exemption — rejected: it would
silently remove the guard from `memory/hindsight` in the feature whose entire subject is keeping
Hindsight in one place. Leaving the guard alone and placing the interfaces elsewhere — rejected: it
would let a test's convenience choose the module layout.

---

## R16 — No dependency is added

**Decision.** Nothing enters `pyproject.toml`. The feature uses `typing`, `dataclasses` or Pydantic
for the small value types it owns, `pytest` for the suites, and nothing else.

**Rationale.** ADR-004 fixes the stack and the constitution requires a decision record to change it.
Every type this feature adds is either a protocol or a small immutable value, and #8's `FrozenModel`
already provides the second: reusing it keeps validation-on-construction true of the report, the
record and the payload, and avoids two spellings of "immutable value" in one codebase.

---

## R17 — What this feature deliberately does not build

* **No retry policy.** #20 reads the distinction R4 declares; backoff, jitter and the idempotency
  key are its work.
* **No `reflect`.** R9.
* **No asynchrony.** The MVP is a local command importing one conversation at a time; an async
  interface adopted without a caller that needs it would be a shape invented wrongly, and #8 said the
  same about modelling non-text content.
* **No pipeline.** #19 composes the real one. What this feature assembles is a harness that proves
  the interfaces compose.
* **No real implementation of any boundary** — FR-027. The temptation is the in-memory archive,
  which is thirty lines and would make #13 look half-done; R12 is why it stays in the test tree.
