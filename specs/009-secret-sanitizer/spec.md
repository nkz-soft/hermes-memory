# Feature Specification: Secret sanitizer

**Feature Branch**: `009-secret-sanitizer`

**Created**: 2026-09-18

**Status**: Draft

**Input**: Issue #11 — "Redact secrets while preserving surrounding context"

## User Scenarios & Testing *(mandatory)*

The sanitizer is the one stage of §7 whose failure is invisible and permanent. A parser that drops
a field produces a thin memory; a sanitizer that misses a token publishes a live credential into a
store built to replicate it across facts and a graph, and the archive it came from is years of
history written before anyone was being careful.

Its users are the person importing their own history, who is trusting the run not to leak what they
wrote years ago; the person recalling a fact afterwards, who needs the sentence around the
credential to still mean something; and the reviewer whom the constitution's merge gate obliges to
reject an unsanitized path to Hindsight.

Every story is testable with no export file, no network and no Hindsight instance in reach: the
input is a conversation in the normalized model of #8, and the fixtures are synthesized —
CLAUDE.md forbids real credentials in the repository, and a synthesized token proves a pattern just
as well.

### User Story 1 - A credential in the history never reaches the memory engine (Priority: P1)

Someone imports an export that contains, somewhere in a hundred thousand messages, a GitLab token
pasted into a `curl`, an AWS key in a tool result, and a `.env` file quoted in full. They cannot
read the corpus first — reading it is the thing they are automating. They need the guarantee to
hold without their attention: every category §13 names is recognized, and it is recognized wherever
a conversation can carry text, not only in the body of a message.

**Why this priority**: Principle V is absolute and this is its only enforcement. Nothing else in
the pipeline inspects content for credentials, and the categories of §13 are the minimum the
constitution requires before a stage is considered done.

**Independent Test**: Feed a conversation carrying a synthesized secret of each category in its
title, message text, tool request, tool result and attachment name, and assert the value does not
appear anywhere in the conversation that leaves the sanitizer.

**Acceptance Scenarios**:

1. **Given** a conversation whose message text contains a GitLab personal access token, **When** it
   is sanitized, **Then** the token is replaced by `[REDACTED]` and no substring of it survives.
2. **Given** a conversation carrying the same token in its title, in a tool request, in a tool
   result and in an attachment name, **When** it is sanitized, **Then** the token is gone from all
   five places.
3. **Given** a conversation with a secret of every category §13 names, **When** it is sanitized,
   **Then** every one of them is gone.
4. **Given** the same conversation, **When** it is sanitized, **Then** the conversation handed in is
   unchanged — the redacted conversation is a new value.

---

### User Story 2 - The knowledge around the secret survives (Priority: P1)

The reason to import the history at all is the sentence the credential sits in: that a 401 came
from a token missing a scope, that a connection string pointed at the wrong host, that an
expired key surfaced as an unhelpful error. §13 fixes the standard with its own example, and
rejects the easy implementation — dropping the message or the tool output — because it throws away
the knowledge along with the credential.

**Why this priority**: It is what distinguishes this feature from deleting the content. A sanitizer
that redacts by truncation satisfies Principle V and destroys the corpus, and both halves are part
of what the issue asks for.

**Independent Test**: Sanitize §13's own example and assert the result reads
`GitLab request using token [REDACTED] returned HTTP 401 Unauthorized` — the words on both sides
intact, in order, with the value replaced in place.

**Acceptance Scenarios**:

1. **Given** a message reading `GitLab request using token <token> returned HTTP 401 Unauthorized`,
   **When** it is sanitized, **Then** it reads `GitLab request using token [REDACTED] returned HTTP
   401 Unauthorized`.
2. **Given** a `.env` line `DATABASE_PASSWORD=<value>`, **When** it is sanitized, **Then** the key
   `DATABASE_PASSWORD` is still readable and only the value is replaced.
3. **Given** a PEM private key block, **When** it is sanitized, **Then** the key material is gone
   and the surrounding prose — including the fact that a private key was present — still reads.
4. **Given** a message that carried text and a secret, **When** it is sanitized, **Then** it still
   carries text, and the message is still in its original position in the conversation.

---

### User Story 3 - A run can be audited without logging its content (Priority: P2)

Someone who has just imported a decade of history wants one question answered: did redaction do
anything, and of what kind. They must be able to answer it from the run's output alone. What they
must never be handed — and what a well-meaning implementation reaches for first — is the value, an
offset into the text, or the line it sat on: with the archived original of §14 beside it, any of
those reconstructs the secret and defeats Principle V through the mechanism meant to serve it.

**Why this priority**: The issue asks for it explicitly, and the report's shape is already fixed by
the boundary declared in #9; what this feature adds is a truthful population of it. It is P2 rather
than P1 because a leak is a breach and a missing count is an inconvenience.

**Independent Test**: Sanitize a conversation containing two tokens of one category and one of
another, and assert the report names both categories with counts 2 and 1, and that neither value
appears in the report rendered in full.

**Acceptance Scenarios**:

1. **Given** a conversation containing three secrets of two categories, **When** it is sanitized,
   **Then** the report gives a count per category summing to three.
2. **Given** a conversation containing no secrets, **When** it is sanitized, **Then** the report is
   empty rather than absent, and the conversation is returned unchanged.
3. **Given** any sanitized conversation, **When** the report is rendered in full, **Then** it
   contains no secret value, no position and no surrounding text.

---

### User Story 4 - Ordinary code and prose are left alone (Priority: P2)

The corpus is mostly engineering conversation: hex digests, UUIDs, base64 payloads, `password` as a
word in a sentence, `Authorization: Bearer $TOKEN` written as an example, a placeholder
`<your-api-key>` in documentation. A sanitizer tuned only for recall redacts these too, and the
result is a corpus of `[REDACTED]` where the knowledge used to be — a quieter version of the
failure §13 rejects.

**Why this priority**: The issue names a false-positive suite as an acceptance criterion. It is P2
because over-redaction degrades the corpus rather than breaching it.

**Independent Test**: Run the sanitizer over a fixture of ordinary engineering prose and code
containing near-miss shapes, and assert the conversation comes back byte-identical with an empty
report.

**Acceptance Scenarios**:

1. **Given** a message containing a git commit SHA, a UUID and a base64-encoded image fragment,
   **When** it is sanitized, **Then** nothing is redacted.
2. **Given** a message containing the word `password` in a sentence, or `PASSWORD=$DB_PASSWORD`, or
   `<your-api-key>`, **When** it is sanitized, **Then** nothing is redacted.
3. **Given** a conversation in which nothing matched, **When** it is sanitized, **Then** the value
   returned is equal to the one handed in.

---

### User Story 5 - Nothing reaches the memory store without passing through first (Priority: P3)

A boundary that works is not the same as a boundary that is used. The path this feature guards is
the one the constitution's merge gate names — an unsanitized path to Hindsight — and it is composed
in #19, not here. What this feature can do is leave a test standing that #19 must keep passing.

**Why this priority**: It is a guard on work not yet written, and it is P3 because the composition
it constrains does not exist yet. The issue asks for it, and it is cheap to state now and expensive
to retrofit after the pipeline is written around it.

**Independent Test**: Compose the in-memory fakes of #9 — source, sanitizer, memory store — into
the order of §7, feed a conversation carrying a secret, and assert the store never saw the secret.

**Acceptance Scenarios**:

1. **Given** a source yielding a conversation with a secret and a memory store recording what it
   was handed, **When** the stages are composed in the order of §7, **Then** what the store
   received carries no secret.
2. **Given** the same composition with sanitization omitted, **When** the test runs, **Then** it
   fails — the guard detects the path it exists to forbid.

---

### Edge Cases

- **A secret spanning a line break**, as a PEM block does: the whole block is key material, and
  redacting it line by line would leave most of it intact.
- **Two secrets in one string, and one secret twice**: every occurrence is replaced, and the count
  is of occurrences replaced, not of distinct values.
- **Overlapping patterns** — a JWT presented as a bearer token, an AWS key inside a connection
  string: the region is redacted once and counted once, under the more specific category.
- **A conversation already sanitized**, re-imported from the archive: `[REDACTED]` is not itself a
  secret, sanitizing twice changes nothing, and the second run reports nothing.
- **A message that was nothing but a secret**: the text becomes `[REDACTED]`, the message stays in
  the conversation, and its position is unchanged — an empty turn still holds the order (#8).
- **A secret in an attachment name**, which is not prose and has no surrounding words to keep.
- **A very long tool result**, such as a dumped Kubernetes manifest: sanitization is proportional to
  the text and does not degrade the run.
- **A secret in the title**, which travels to the memory store as provenance rather than as content.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST provide a secret sanitizer satisfying the boundary declared in #9 —
  handed a normalized conversation, returning a redacted conversation and a report of what was
  redacted.
- **FR-002**: The sanitizer MUST recognize every category ARCHITECTURE.md §13 names as the minimum:
  API keys, bearer tokens, JWTs, GitHub and GitLab personal access tokens, Anthropic and OpenAI
  keys, AWS access keys, private keys, passwords, connection strings, `.env` values and Kubernetes
  secrets.
- **FR-003**: A recognized value MUST be replaced with the literal `[REDACTED]`, in place, leaving
  the text before and after it unchanged.
- **FR-004**: The sanitizer MUST NOT drop a message, a tool activity or any other part of the
  conversation because it matched.
- **FR-005**: Redaction MUST reach every field of the conversation that can carry text — the title,
  each message's text, each tool activity's name, request and result, and each non-text part's name.
- **FR-006**: The conversation handed to the sanitizer MUST NOT be modified; the redacted
  conversation MUST be a new value, and no partially redacted value may escape on a failure.
- **FR-007**: The conversation's identity MUST survive redaction — source, native identifier,
  derived document id, message count and message order are those of the input.
- **FR-008**: The report MUST give, per category, how many redactions were made, and MUST NOT carry
  the value, its position, its length, or the text around it.
- **FR-009**: When nothing matched, the sanitizer MUST return the conversation unchanged together
  with an empty report, and MUST NOT signal "nothing found" by any other means.
- **FR-010**: A conversation that cannot be rewritten MUST be reported by raising the boundary's
  permanent error, never by returning the input unchanged.
- **FR-011**: Sanitization MUST be deterministic: the same text sanitizes to the same result, with
  no dependence on a network call, a model, or the order conversations are processed in.
- **FR-012**: Sanitization MUST be idempotent — sanitizing an already sanitized conversation changes
  nothing and reports nothing.
- **FR-013**: Every occurrence of a recognized value MUST be replaced, including repeats of the same
  value and multiple secrets within one field.
- **FR-014**: Where two patterns match overlapping text, the region MUST be redacted once and
  counted once, under the more specific category.
- **FR-015**: The sanitizer MUST leave ordinary engineering content untouched: identifiers, digests,
  UUIDs, variable references such as `$TOKEN` or `${VAR}`, documentation placeholders, and the word
  `password` used as a word.
- **FR-016**: The sanitizer MUST NOT log conversation content, and MUST NOT log a redacted value in
  any form; what it may emit is the report.
- **FR-017**: A test MUST stand that composes the pipeline stages in the order of §7 and fails if a
  conversation can reach the memory store without passing through the sanitizer.
- **FR-018**: The implementation MUST pass the contract suite of #9 unchanged, as any sanitizer must.

### Key Entities

- **Sanitized conversation**: the normalized conversation of #8 with recognized values replaced,
  identical to its input in identity, structure and surrounding text. It is what continues down the
  pipeline; the unredacted original stays in the raw archive (§14, Principle I).
- **Redaction report**: counts by §13 category for one conversation. It is what is logged, shown and
  aggregated across a run, and its value lies as much in what it cannot carry as in what it does.
- **Redaction category**: the closed vocabulary of §13, fixed by #9, so that reports are comparable
  across runs.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For each of the thirteen categories of §13, a fixture proves the secret is gone from
  the sanitized conversation and the words around it are still there — thirteen for thirteen, none
  skipped.
- **SC-002**: Across the false-positive suite of ordinary engineering code and prose, zero
  redactions are made.
- **SC-003**: A conversation carrying a secret in its title, message text, tool request, tool result
  and attachment name comes back with the secret in none of the five.
- **SC-004**: The report accounts for every redaction made — the sum of its counts equals the number
  of replacements — and contains no value, position or surrounding text.
- **SC-005**: Sanitizing an already sanitized conversation produces an unchanged conversation and an
  empty report.
- **SC-006**: Removing the sanitizer from the composed pipeline makes a test fail.
- **SC-007**: The implementation passes the contract suite of #9 without a change to the suite.

## Assumptions

- **The archive keeps the original.** Sanitization guards the path to the memory engine; Principle I
  requires the raw archive to hold the conversation as it arrived. This feature does not sanitize
  what is archived, and does not change §14.
- **Detection is pattern-based.** Recognition is by deterministic patterns over text — structural
  shapes for the vendor-prefixed keys, keyed patterns such as `password=` for the value categories,
  delimiters for PEM blocks. Entropy scoring and model-based detection are not used: both introduce
  a false-positive rate that is untestable as a fixture and, in the case of a model, send the
  content out of the process, which Principle V forbids.
- **Where recall and precision conflict, recall wins.** A redaction that should not have happened
  loses a phrase; a miss publishes a credential. The false-positive suite bounds the cost by naming
  the shapes that must survive, rather than by a tolerance.
- **Patterns are not configurable in this feature.** The set is fixed in code and changes by a
  commit with a test. A user-supplied pattern list is a separate feature and is not needed for the
  MVP.
- **The pipeline guard is written against the fakes of #9.** #19 composes the real pipeline; until
  it exists, the guard composes the in-memory fakes in the order of §7. #19 inherits the test and
  the obligation to keep it passing.
- **Vendor key shapes are those published today.** A prefix scheme changing later is an ordinary
  edit — a pattern added or widened with a fixture beside it — not a change to this specification.
- **Fixtures are synthesized.** No real credential enters the repository, per CLAUDE.md; synthesized
  values of the right shape prove the patterns, and the suite asserts they are of the right shape.
- **The sanitizer works on one conversation at a time**, as the boundary requires, so that one
  failure cannot abort a run (Principle IV, §18).

## Dependencies

- **#9 — boundary interfaces** (merged): declares `SecretSanitizer`, `RedactionCategory`,
  `RedactionReport` and `SanitizationError`, the contract suite SS-1 to SS-8, and the fakes this
  feature composes in its pipeline guard.
- **#8 — normalized conversation model** (merged): the conversation this feature rewrites, and the
  text-bearing fields FR-005 enumerates.
- **Blocks #19 — the ingestion pipeline**, which composes this stage between normalization and the
  memory store.
