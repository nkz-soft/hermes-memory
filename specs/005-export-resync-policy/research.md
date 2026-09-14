# Research: Export resynchronization policy (ADR-006)

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Date**: 2026-09-14

No NEEDS CLARIFICATION markers survived the specification, so nothing here resolves an open
question. What follows is the material behind each of the four decisions: what was weighed, what
was rejected, and what each answer costs. It is written down before the record so that the ADR's
Rationale and Consequences sections are reported rather than improvised.

## 1. How history stays current

**Decision.** Periodic full re-export, imported incrementally. A refresh is a fresh export placed
under `data/` and a re-run of the import; the skip by source id plus content hash (§17) confines
the cost to what is new or changed.

**Rationale.** Each export carries the account's history in full rather than the changes since the
last one, so there is no merge to perform and no window to track. "Full" is not "superset": the one
way a later export holds less than an earlier one is a conversation deleted in the source, which is
what decision 3 governs — so the two decisions describe the same input rather than contradicting
each other. The expensive
part of an import is not reading the file, it is LLM extraction per conversation, and §17's skip
already removes that cost for everything unchanged. The refresh therefore needs no new mechanism;
it needs to be named, so that nobody builds one.

The manual step is a property of the source. There is no supported interface that yields an
account's conversation history: the archive is requested by a person and arrives as a download.
Recording that as a constraint rather than as a gap matters, because the alternative reading — "the
automation is missing" — invites the rejected approach below.

**Alternatives considered.**

*Drive an authenticated session against the service's internal endpoints and pull conversations
directly.* Rejected. It is automated access outside the terms that govern the account; it requires
holding live credentials in a project whose Principle V exists because credentials in this corpus
are hazardous; and it fails by returning a partial history, which is the single input this system
is least able to distinguish from a legitimate one — see decision 3.

*Track a high-water mark and import only conversations newer than the last run.* Rejected as
redundant and less safe. The content hash already achieves the skip, and it also catches a
conversation that was edited in place — which a timestamp cursor misses.

**Consequences.** Memory ages between refreshes, and nothing forces one. The visibility of that
decay is what #21's `status` command provides by reporting the age of the last import; the cost of
reversing it is what this decision keeps low.

**Deliberately left out.** How the archive reaches `data/`. Acquisition is a replaceable component
behind its own boundary — manual placement in the MVP, an automated watcher later (#40, with
ADR-007). None of the four decisions changes when it is automated, and stating that keeps the
record from being reopened by an issue that only changes the delivery of a file.

## 2. A conversation that continued

**Decision.** Replace it in full. `update_mode: "replace"` stays the default for re-import;
`append` remains reserved for its §9 purpose — delivering one oversized document as several items
within a single operation.

**Rationale.** Two properties are worth more than the extraction saved. First, idempotency:
`replace` keyed by a stable `document_id` yields the same bank whether a conversation is imported
once or five times, which is what Principle II's no-duplicates requirement rests on. Second,
context: §7 sends a conversation as one logical document precisely so extraction sees the whole
thing, and a decision made in message 4 and revised in message 40 is only legible to an extractor
holding both.

**Alternatives considered.**

*Append only the new tail.* Cheaper per refresh and incompatible with Principle I. `append` is not
idempotent, so a replay from the raw archive — which the principle requires to remain possible —
would append the tail a second time and corrupt the document from the inside, silently. Extraction
would also see a fragment with no preceding context, which is the failure §7 is written to avoid.

*Split long-running conversations into per-session documents at import time.* Rejected as a change
to document identity (§10) dressed up as an optimisation, and out of scope for a record about
refresh policy.

**Consequences.** A conversation that keeps growing is re-extracted in full on every refresh in
which it grew, and a very long one is the most expensive thing in the corpus. Accepted: growing
conversations are a minority, and the alternative trades a recurring cost for a correctness risk.

## 3. A conversation that disappeared

**Decision.** It stays — in the raw archive and in the bank. The importer MUST NOT diff the archive
against an export, and MUST NOT derive removals from one. An absence may be logged as an
observation; nothing may act on it.

**Rationale.** Absence is not evidence of deletion. A truncated download, a partial or filtered
export, a parser that lost a branch, an export taken from a different account — each produces
exactly the same input as a deliberate deletion, and none of them means the knowledge should go.
There is no signal to tell them apart, so acting on any of them means acting on all of them.

The risk is asymmetric, which settles it even where the ambiguity does not. A conversation wrongly
kept costs some noise in recall. A conversation wrongly removed is unrecoverable: it is gone from
the source too, which is why the archive exists.

And the architectural point: if an absence in a later export can empty our archive, the source
service holds a remote delete on a store whose entire purpose (Principle I, ADR-001 exit strategy)
is independence from it.

**Alternatives considered.**

*Treat absence as deletion and remove the document.* Rejected above.

*Treat absence as deletion only when the export is otherwise complete — same conversation count
give or take, same date range.* Rejected as a heuristic guarding an irreversible action. It
converts "we cannot tell" into "we usually can", and the case it fails on is the one it was built
for: a partial export that happens to look plausible.

*Tombstone the document — keep it, mark it absent, let recall deprioritise it.* Rejected for the
MVP as a mechanism serving a signal we just established is untrustworthy. It is the natural design
*if* a source ever reports deletions explicitly, and nothing here forecloses it.

**Consequences.** A conversation deleted in the source remains retrievable through memory. For
history that is correct — a decision discussed in March happened, whether or not the thread was
tidied away in April. For content that must not be retained, the answer is a different operation:
deliberate forgetting, human-initiated, on a named `document_id`, out of scope for the MVP and
absent from every import path. Until it exists, the only remedy for a secret the sanitizer missed
is rebuilding the bank, and the record says so rather than implying a capability that is not there.

**Scope.** The rule binds sources whose export cannot distinguish absence from deletion. A future
source that carries an explicit deletion event is a different case, decided in that source's own
record (§2).

## 4. What the content hash covers

**Decision.** Messages, their order and their timestamps. Not the title, and not metadata the
importer itself produces.

**Rationale.** The hash exists to answer one question — has anything changed that would change what
extraction produces — and the answer is driven by conversation content. Including the title means a
rename in the source costs a full re-extraction of an otherwise identical conversation. Including
importer-produced metadata is worse: the importer's own version bump would invalidate the entire
corpus at once, turning a routine release into a full re-extraction of everything.

**Alternatives considered.**

*Hash the whole normalized record, title and metadata included.* Rejected for the two costs above.

*Hash content, and separately detect a title change to update metadata without re-extracting.*
Attractive and deferred. It is a second comparison and a partial-update path in the memory store,
which is #14 and #16's design space rather than a policy question. The record states the
consequence so that whoever wants it has the reason written down.

**Consequences.** A renamed conversation is skipped, so the title travelling with the document as
metadata goes stale until some other change re-imports it. Accepted: titles are metadata, not the
retrieval surface, and paying for full re-extraction to correct one is the worse trade.

## Sources

* ARCHITECTURE.md — §2, §7, §9, §10, §11, §14, §17, §21, §23 (ADR-001, ADR-002)
* `.specify/memory/constitution.md` — Principles I, II, III, IV, V
* Issue #39 (this feature), issue #40 (acquisition boundary), issues #8, #14, #21 (blocked)
