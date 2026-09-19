# Implementation Plan: Secret sanitizer

**Branch**: `009-secret-sanitizer` | **Date**: 2026-09-18 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/009-secret-sanitizer/spec.md` (issue #11)

## Summary

Implement `PatternSecretSanitizer`, the first and only implementation of the `SecretSanitizer`
boundary #9 declared. It holds one ordered table of deterministic patterns covering the thirteen
categories of ARCHITECTURE.md §13, in three shapes: value-shaped for credentials recognizable by
their own prefix and alphabet, keyed for the ones that have no shape of their own — a password, an
AWS secret access key, a `.env` value — where only the value is replaced and the key it sits under
is kept, and a delimited block for a PEM private key, where the body goes and the markers stay.
Scanning a string collects spans rather than substituting in place, so overlapping matches are
redacted once and counted once under the more specific category, and the rebuild is a single pass.
The rewriter visits the named text-bearing fields of #8's model — title, message text, tool name,
request and result, attachment name — returning a new conversation with identity untouched, plus a
report of counts by category and nothing else. It is proved by #9's contract suite, by a fixture per
category, by a false-positive suite of ordinary engineering code and prose, and by a guard in the
integration pipeline that fails if a conversation can reach the memory store unsanitized.

## Technical Context

**Language/Version**: Python 3.13

**Primary Dependencies**: Pydantic v2 (#8's model and #9's report). Standard library `re`.
**No new dependency** (research R2).

**Storage**: None. The sanitizer reads a conversation and returns one; the unredacted original
stays in the raw archive (§14, Principle I).

**Testing**: pytest. The contract suite `tests/contracts/sanitizer.py` (#9); unit tests per category
and a false-positive suite in `tests/unit/`; the composed guard in
`tests/integration/test_pipeline_from_fakes.py` over the harness `tests/integration/pipeline.py`.

**Target Platform**: The developer machine and the container image (#7), Linux and Windows.

**Project Type**: A module of the modular monolith — `hermes_memory.sanitization`.

**Performance Goals**: Linear in the text, patterns compiled once (R12). A large tool result —
hundreds of kilobytes of manifest — is sanitized within a bounded time asserted by a test. No
latency target: extraction dominates an import, which a person runs rarely (ADR-006).

**Constraints**: Deterministic, offline, no clock, no network, no model (FR-011, Principle V). No
log event of any kind from the boundary (R8). No conversation content in an error message. Every
quantifier bounded, none nested, with an adversarial-input test (R2).

**Scale/Scope**: Thirteen categories, a table of roughly twenty patterns, run over every message of
a decade of personal history.

No item is left as NEEDS CLARIFICATION. research.md settles each choice.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | How this plan complies |
|---|---|
| **I. Raw archive is the source of truth** | The sanitizer guards the path to the memory engine and nothing else: it neither reads nor writes the archive, and the archive keeps the conversation as it arrived (§14). That is what makes a replay meaningful — a pattern fixed later is re-applied to the original, exactly the case Principle I's rationale names ("the redaction rules … can change later without losing history"). Idempotence (FR-012) is what makes re-sanitizing an already sanitized replay harmless. |
| **II. Provenance and stable identity** | Identity is out of the rewriter's reach by construction: `source`, `source_id`, `started_at` and `last_activity_at` are copied, never scanned, so no pattern can touch the value `document_id` is derived from (R1). Message count and order are preserved, and SS-2 asserts all of it. No clock is read. |
| **III. Test-first** | The constitution names unit tests for the secret sanitizer against realistic fixtures as the minimum before this stage is done. Every rule in contracts/redaction-rules.md gets its test written and observed failing first: thirteen category fixtures, the false-positive suite, the overlap and idempotence rules, #9's contract suite, and the pipeline guard — which is written together with its "guard bites" twin, so the guard is proved able to fail. |
| **IV. Replaceable boundaries** | The implementation satisfies `SecretSanitizer` and adds nothing to the boundary: no new type crosses it, no signature changes, `sanitizer.py` is not edited. It imports the normalized model and `re`; it does not import Hindsight, HTTP, storage or the pipeline, and the existing structure tests enforce that. The patterns live behind the interface, so a different sanitizer — a stricter one, or one backed by a scanner — replaces this one by passing the same contract suite. Sanitization stays one stage, run conversation by conversation, so one failure cannot abort a run (§18). |
| **V. Secrets never reach the memory engine** | This feature *is* Principle V's enforcement. The minimum categories of §13 are covered, a redaction replaces the value and keeps the enclosing text rather than dropping it, the report carries counts and cannot carry a value or a position (#9, R6 of that feature), the boundary logs nothing (R8), and the pipeline guard makes the ordering constraint executable (FR-017). Fixtures are synthesized, so no credential enters this public repository (R11). |

**Stack.** `re` is the standard library; Pydantic and pytest are already in the stack table. No
dependency is added, so no decision record is required.

**Governance impact.** None. Issue #11 ticks "None of the above": no principle changes, the stack
is untouched, the Hindsight contract, the bank strategy and the tag convention are not involved, and
no history source is added. The §13 category vocabulary is consumed as #9 fixed it, not amended.

**Gate result: PASS.** No deviation to justify; Complexity Tracking is therefore empty and omitted.

**Re-check after Phase 1 design: PASS.** The design adds four modules inside `sanitization` and no
public type beyond `PatternSecretSanitizer`. Two consequences are recorded rather than hidden.
First, R7's known limit: a Kubernetes `data:` block quoted without its `kind: Secret` line and with
neutral key names is not recognized, and no pattern can tell it from a ConfigMap. Second, R1's
trade: identity fields are deliberately not scanned, so a credential pasted into a conversation *id*
by the source service would survive — an impossibility for a ChatGPT id, and a leak that redacting
would trade for a broken `document_id` on every conversation.

## Alternatives considered

- **Dropping the message or tool output that matched** (named in issue #11, rejected by §13). The
  simplest implementation that satisfies Principle V, and it destroys the corpus: §13's own example
  is a tool output whose value is the sentence around the token. Rejected explicitly by the
  architecture, and by User Story 2.
- **A per-category marker such as `[REDACTED:aws-key]`.** Rejected: the marker would tell a reader
  of the text what kind of credential was there — a hint the report deliberately withholds — and the
  issue fixes the literal `[REDACTED]` (R3).
- **A recursive walk redacting every string in the model.** Rejected: it would redact `source_id`
  and so change `document_id`, trading Principle II's stable identity for a hypothetical future
  field. A structure test over the model's fields covers that field instead (R1).
- **Entropy scoring, or a model-based detector.** Rejected: entropy redacts SHAs, UUIDs and base64
  payloads and cannot be pinned by a fixture; a model sends content out of the process, which
  Principle V forbids, and makes sanitization non-deterministic (R2, R5).
- **Matching AWS secret access keys by shape.** Rejected: forty characters of base64 alphabet is
  also what a hash and half the quoted payloads look like. Keyed matching catches them where they
  actually occur (R6).
- **`regex` with a timeout.** Rejected: a dependency outside the stack table for a problem bounded
  quantifiers already solve (R2).
- **Logging one content-free event per conversation from the sanitizer.** Rejected: it duplicates
  the report at the boundary least able to afford a mistake about what is in scope (R8).

## Project Structure

### Documentation (this feature)

```text
specs/009-secret-sanitizer/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── redaction-rules.md
├── checklists/
│   └── requirements.md
└── tasks.md             # /speckit-tasks, after the gate
```

### Source Code (repository root)

```text
src/hermes_memory/sanitization/
├── __init__.py            # public surface: #9's boundary types plus PatternSecretSanitizer
├── sanitizer.py           # #9's protocol, report and error — UNCHANGED by this feature
├── patterns.py            # the ordered table: category, expression, value group, precedence; placeholder rejection (R3, R5)
├── scanner.py             # spans over one string: find, resolve overlaps, rebuild, count (R4)
└── pattern_sanitizer.py   # PatternSecretSanitizer: the conversation traversal (R1)

tests/
├── unit/
│   ├── test_redaction_patterns.py      # a fixture per §13 category (SC-001)
│   ├── test_redaction_false_positives.py  # ordinary code and prose (SC-002)
│   ├── test_redaction_scanner.py       # overlap, repeats, idempotence, adversarial input (R2, R4)
│   └── test_pattern_sanitizer.py       # the conversation traversal, identity, report
├── structure/
│   └── test_sanitizer_covers_the_model.py  # every text-bearing field of #8 is visited (R1)
├── contracts/
│   └── test_pattern_sanitizer_passes_the_contract.py  # #9's SS-1..SS-8
├── synthetic/
│   └── secrets.py                      # synthesized samples per category (R11)
└── integration/
    └── test_pipeline_from_fakes.py     # extended: the guard and its bite (FR-017, R10)
```

**Structure Decision**: the constitution's module tree fixes `sanitization`; this feature fills it.
The split inside the module follows what is separately testable — whether a string matches
(`patterns`, `scanner`) and whether a conversation is rewritten correctly (`pattern_sanitizer`) —
and leaves #9's declaration in `sanitizer.py` untouched, so the boundary stays readable as a
boundary rather than as the first implementation of one.
