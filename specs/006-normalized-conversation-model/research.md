# Phase 0 — Research: Normalized conversation model

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

No `[NEEDS CLARIFICATION]` marker survived the specification, so nothing is carried in as an open
question. What follows is the design work the specification deliberately deferred: the shape of the
canonical form, the hash over it, how the typed vocabularies are expressed, and how the boundary of
Principle IV is made to fail a test rather than a review.

Every decision below was checked against the constitution and against ARCHITECTURE.md §§3.3, 6, 7,
8, 9, 10, 11, 17 and ADR-006. Where a check was run rather than reasoned, the command and its result
are stated.

---

## R1 — The canonical form is built explicitly, not dumped from the model

**Decision.** The canonical representation is assembled by a dedicated function that names each
field it includes, and is not derived from a serialization of the model.

**Rationale.** ADR-006 decision 4 fixes what the hash covers: the messages, their order and their
timestamps, excluding the title and importer-produced metadata. If the canonical form were
`model_dump()` minus a deny-list, then every field a later feature adds to `Conversation` would join
the hash silently — and a field joining the hash silently is every stored hash invalidated and every
conversation re-extracted, discovered on a refresh months later. Naming the included fields inverts
that: a new field is outside the hash until someone writes it in, in a commit that has to say why.

The same argument in reverse is why a deny-list is not enough for the title. Excluding the title by
name works today; it works only by accident once a `subtitle` or a `source_label` exists.

**Alternatives considered.**

* *`model_dump(exclude={"title", ...})` with a deny-list.* Rejected above: silent inclusion is the
  expensive failure, and this makes inclusion the default.
* *A `hashed=True` marker in each field's metadata.* Keeps one list, but scatters the ADR-006
  decision across twenty field declarations, where no reviewer reads it as a whole. The function
  body is the readable form of a decision that is about the set, not about each member.

## R2 — JSON with sorted keys and no spaces, UTF-8, as the canonical bytes

**Decision.** The canonical form is serialized with
`json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)` and encoded UTF-8.
The payload contains only `None`, `str`, `int`, `bool`, `list` and `dict`.

**Rationale.** FR-011 requires identity across processes and runs under any key ordering or hash
seed, which `sort_keys=True` delivers and a plain dict iteration order does not guarantee across
future changes in construction order. Fixed separators remove whitespace as a degree of freedom.
`ensure_ascii=False` keeps the text as text: with `ensure_ascii=True` the same string escapes
differently depending on nothing the content controls, and the corpus is substantially non-ASCII —
this is Russian-language engineering history.

JSON rather than a bespoke encoding because the canonical bytes are also what a human debugging a
"why did this re-extract" question will read, and because the round-trip form (R3) is JSON already;
one format, two uses, no second parser.

**Alternatives considered.**

* *A length-prefixed binary encoding.* Immune to the escaping questions above and unreadable by
  anyone. Rejected: the ambiguities JSON leaves are closed by three keyword arguments.
* *Canonical JSON per RFC 8785 (JCS).* Solves the same problem with an external dependency and a
  float-formatting apparatus this payload has no floats to need. Rejected: a dependency has to
  displace something or earn a record (constitution, Technology Stack), and this one would earn
  neither.
* *Unicode normalization (NFC) before hashing.* Rejected. Two byte-different strings that render
  alike are two different contents, and the parser must not decide otherwise on the model's behalf.
  Recorded here because it is a real fork: if a source is ever found to re-encode text between
  exports, normalization becomes a parser concern, not a hash concern.

## R3 — SHA-256, hex, over those bytes

**Decision.** `hashlib.sha256(canonical_bytes).hexdigest()`.

**Rationale.** The hash is an identity check, not a security primitive, but it is stored in the
import state and compared for years, so the boring, universally recognizable choice wins. It is in
the standard library, so no dependency and no ADR-004 question. 64 hex characters fit any column
anyone later chooses.

Nothing depends on the algorithm staying fixed *today*: no importer has run, so no stored hash
exists to stay compatible with. The first import is what makes this decision expensive to revisit,
and the plan notes that so a later change is made knowingly.

**Alternatives considered.** BLAKE2b — faster, also stdlib, and the speed is irrelevant at a few
megabytes of text per import. `md5` — rejected on recognizability grounds alone; a reviewer reading
`md5` in a memory system spends time deciding whether it matters.

## R4 — Timestamps are normalized to UTC and rendered at fixed precision

**Decision.** In the canonical form, an aware datetime is converted with `astimezone(UTC)` and
rendered `%Y-%m-%dT%H:%M:%S.%fZ`. An absent time renders as JSON `null`.

**Rationale.** `2026-01-01T12:00:00+03:00` and `2026-01-01T09:00:00Z` are the same instant, and
`datetime.__eq__` agrees — confirmed by probe (`instant equal: True`, `models equal: True`). If the
canonical form kept the offset, two conversations equal in every respect would hash differently
because an export was taken in another timezone. Converting first removes that.

Fixed `%f` precision matters for the same reason at a smaller scale: `datetime.isoformat()` omits
the microseconds when they are zero, so a timestamp that happens to land on a whole second renders
in a different shape from one that does not. That is a formatting accident inside a value the hash
depends on.

`null` for an absent time, rather than a sentinel or an omitted key, because FR-007 forbids
substituting any clock for a missing timestamp and the canonical form has to render the absence as
itself.

## R5 — Naive datetimes are rejected at construction

**Decision.** Every datetime field is `AwareDatetime`. A naive value fails validation.

**Rationale.** A time without an offset is a time whose instant depends on where the code ran, and
R4 turns instants into hash input. Rejecting at construction (FR-008, FR-020) keeps the invalid
value out of the archive rather than out of the hash only.

Confirmed by probe: `M(at=datetime(2026, 1, 1))` raises with error type `timezone_aware`.

**Alternative considered.** Coercing a naive value to UTC. Rejected — it is a guess about the
source's intent, made silently, at the one place where a wrong guess is unrecoverable because the
original offset is gone.

## R6 — Message order is list position, with no separate index field

**Decision.** Messages are an ordered `tuple` on the conversation. There is no `position` or
`sequence` field on the message.

**Rationale.** FR-003 requires order to be explicit and never derived from timestamps — both because
a ChatGPT export omits some message times and because two messages can share one. A tuple is
explicit: it *is* the order, and the canonical form's JSON array preserves it.

A separate index field would be a second source of truth for the same fact, able to disagree with
the list it annotates. The pipeline sanitizes and re-builds conversations (§7), so that disagreement
would arrive eventually and would be invisible until a conversation came back from the archive in
the wrong order.

## R7 — Immutable models, tuples for sequences

**Decision.** Every model is `frozen=True, extra="forbid"`, and every sequence field is a `tuple`.

**Rationale.** Three things fall out of it. A conversation's content hash cannot go stale in the
hand of a caller who mutated a message after computing it. The pipeline stages of §7 become what
Principle IV calls composable — each returns a new conversation rather than editing its argument,
so the sanitizer cannot leave a half-redacted object behind on failure. And `extra="forbid"` turns
a misspelled field in an archived record into a loud parse failure (FR-015) instead of a silently
dropped value.

Confirmed by probe: a frozen model with a tuple field round-trips through
`model_dump_json` / `model_validate_json` equal to the original, and the list in the JSON comes
back as a `tuple`.

## R8 — Provenance is a separate value, paired with the conversation by an enrichment record

**Decision.** `Provenance` is its own model carrying the §3.3 fields. A third model pairs a
conversation with its provenance and its tags — the output of §7's enrich stage — and that is what
the memory store and the archive accept.

**Rationale.** §7 puts classification between normalization and enrichment, and provenance carries
the project that classification determines. Baking provenance into `Conversation` would mean either
constructing it with a placeholder project and rewriting it later — mutation, against R7 — or
delaying the conversation's existence until after classification, which leaves the parser with
nothing to return.

The pairing record is not invented to satisfy a template: SC-001 requires the six boundaries of §8
to be declarable without inventing a type, and the memory store's input is exactly
conversation + provenance + tags. Defining it here is what stops #9 from defining it three times.

**Alternative considered.** Passing the three values as separate parameters across every boundary.
Rejected: the archive, the memory store and the import state would each have to re-state the same
triple, and the first one to reorder its parameters would be caught by nothing.

## R9 — Tags are one typed value per namespace, rendering to the §6 strings

**Decision.** A frozen `Tag` base with a closed `namespace` and a validated `value`, and four
concrete forms — source, project, type, user. Source and type take closed vocabularies; project and
user take a validated slug. Each renders to exactly `namespace:value`.

**Rationale.** §6 calls the convention "part of the architecture", and it is the only scoping
mechanism there is: a typo in a project tag does not fail, it silently files a conversation where
nobody will look for it. Typing the namespace closes the first half; validating the slug
(`[a-z0-9]` then `[a-z0-9._-]*`) closes the second. `project:unknown` (§15) is an ordinary value of
the project tag and needs no special case.

Rendering through one method keeps the string form in one place, so the memory store's serialization
is a call rather than an f-string repeated per call site.

**Alternative considered.** A single `Tag(str)` subclass validating against a regex of the whole
convention. Simpler to write and it loses the thing worth having: with a typed namespace, a function
that needs the project tag can say so in its signature.

## R10 — `document_id` is derived, and the native id is opaque

**Decision.** `document_id` is a read-only derivation, `f"{source}:{source_id}"` (§10). The model
offers no way to set it. The native id is validated non-empty and free of whitespace and control
characters, and is otherwise opaque — a colon inside it is permitted.

**Rationale.** Principle II forbids a generated identifier, and the way to forbid it in code is to
leave no parameter that could carry one. Opacity is the other half: nothing in this system splits a
document id back into its parts, so a colon inside the native id is harmless, and writing a rule
against it would be inventing a constraint on a source's identifiers that the source does not owe
us. What is *not* harmless is whitespace or a control character, which would make the id unreadable
in a log and unstable across any transport that trims.

## R11 — Tool activity and non-text parts are inside the hash

**Decision.** The canonical form includes each message's role, text, timestamp, tool activity and
the record of any non-text parts. It excludes the conversation's title, its source, its native id,
and everything on `Provenance`.

**Rationale.** ADR-006 decision 4 says the hash covers "the messages, their order and the timestamps
of the messages", and excludes "the title and any metadata the importer itself produces". Tool
activity is part of a message, not metadata about it — §7 exists partly to preserve the chain
command → error → investigation → solution — so a tool result that changed is content that changed.
The same holds for the record that an image was present.

Source and native id are excluded for a different reason: they are the *key* the import state looks
the hash up by (§17), not part of what is being compared. Including them would make the hash of a
conversation depend on the identity it is already filed under, which changes nothing and hides the
distinction.

## R12 — The boundary of Principle IV is enforced twice, statically and at runtime

**Decision.** Two tests. A static one parses every source file under `normalization/` and asserts
that its imports fall inside a named allowlist. A runtime one imports the package in a subprocess
and asserts that no forbidden module appears in that process's `sys.modules`.

**Rationale.** Each catches what the other misses. The static check is readable and names the
allowlist, but it sees only this module's own import statements — a helper imported from elsewhere
in the package could drag in `httpx` and pass. The runtime check sees the true transitive closure
and cannot be argued with, but it reports a module that arrived rather than the line that asked for
it. Together they fail on both the direct violation and the laundered one.

Confirmed viable: a subprocess importing `hermes_memory.normalization` today returns 52 entries in
`sys.modules` and the package `__init__` is a bare docstring, so the measurement is not swamped by
the package itself.

**Alternatives considered.** `import-linter` — the right tool and a new dependency; the constitution
requires a record for a dependency that displaces one, and adding one that displaces nothing still
has to earn its place against thirty lines of `ast` and `subprocess`. If a second or third module
ever needs the same guard, that is the moment to reconsider — noted rather than pre-empted.
Vendoring a check into CI only — rejected, because a guard that does not run in `pytest` does not
run for the person about to break it.

## R13 — `FILLED_BOUNDARIES` gains `normalization`, deliberately

**Decision.** `tests/structure/test_module_layout.py::FILLED_BOUNDARIES` gains `"normalization"`,
with a comment naming this feature, in this feature's own commit.

**Rationale.** That guard holds every recorded boundary to containing nothing but a docstring until
a feature fills it, and its own docstring says filling one "is a deliberate edit in the commit that
fills it". This is such a commit. The edit is a task in `tasks.md`, not a surprise discovered when
the suite goes red, and the accompanying comment records what filled it — matching the entries
already there for `observability` and `cli`.

## R14 — File layout inside the module

**Decision.**

```text
src/hermes_memory/normalization/
├── __init__.py       # the module's public surface, re-exporting the names below
├── base.py           # the frozen value base and the two validated string types
├── conversation.py   # Conversation, Message, ToolActivity, NonTextPart, Role, Source
├── provenance.py     # Provenance, and the enrichment record pairing it with a conversation
├── tags.py           # Tag and its four namespaces
└── canonical.py      # the canonical form and the content hash
```

**`base.py` was added during implementation, and the addition is recorded here rather than only in
a commit message** — the constitution requires a deviation from a committed plan to be justified in
writing. The plan listed four files; the frozen model configuration, the opaque-identifier type and
the slug type are needed by `conversation.py`, `provenance.py` and `tags.py` alike, and putting
them in any one of the three would have made the other two import it for a reason unrelated to what
that file is about — the exact coupling this split exists to avoid. It changes no decision above:
the axes of change are unaltered, and a reviewer checking the hash against ADR-006 still reads one
file.

**Rationale.** Four files rather than one because the four have different reasons to change — a new
source touches `conversation.py`, a new tag namespace touches `tags.py`, and ADR-006 governs
`canonical.py` alone — and because a reviewer asked to check the hash against ADR-006 should have
one file to read. `__init__.py` re-exports so that consumers import from the boundary rather than
from its internals, which is what lets the internals move.

Tests mirror it: one unit test file per source file, plus the boundary tests under
`tests/structure/`, matching the existing split where `tests/structure/` holds the checks about the
shape of the repository and `tests/unit/` holds the checks about behaviour.

## R15 — What is deliberately not built

* **No parser.** Mapping a ChatGPT export into this model is #10. This feature's fixtures are
  synthesized conversations, never real history (CLAUDE.md).
* **No archive format.** §14 leaves the on-disk layout to #13. This feature defines the
  serialization that layout will carry, and chooses no directory, no filename and no compression.
* **No boundary interfaces.** Declaring the six protocols is #9, which this blocks. The enrichment
  record of R8 is a data shape the boundaries will name, not a protocol.
* **No tag assignment.** Which tags a conversation gets is the enrich stage's decision. This defines
  what a tag *is*.
* **No `type:` classification.** The `type:` vocabulary is typed here because §6 fixes it; choosing
  between `conversation` and `troubleshooting` for a given conversation is nobody's job yet.
