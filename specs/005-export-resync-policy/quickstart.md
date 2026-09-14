# Quickstart: verifying the export resynchronization policy

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Date**: 2026-09-14

This feature ships prose, so "running it" means reading it. The checks below are what a reviewer
performs to close the issue; each maps to a success criterion in the specification.

## Prerequisites

The branch `005-export-resync-policy` checked out, and ARCHITECTURE.md as amended.

## 1. The diff is confined (SC-004)

```bash
git diff --stat origin/main...HEAD
```

Expected: `ARCHITECTURE.md` plus files under `specs/005-export-resync-policy/`, and nothing else.
No file under `src/` or `tests/` appears.

```bash
git diff origin/main...HEAD -- ARCHITECTURE.md
```

Expected: two hunks — a cross-reference at the end of §17, and a new `### ADR-006` subsection in
§23 following ADR-005. A hunk anywhere else is a defect.

## 2. The four questions are answered (SC-001)

Read ARCHITECTURE.md alone — not this specification, not issue #39 — and answer:

| Question | Expected answer in the document |
|---|---|
| How does history stay current? | A fresh full export, imported incrementally; the manual export request is a property of the source |
| A conversation gained messages — what happens on re-import? | Replaced in full under `replace`; `append` stays reserved for its §9 purpose |
| A conversation is missing from a newer export — what happens? | Nothing. It stays in the archive and in the bank; removals are never derived from an export |
| Does renaming a conversation cost a re-extraction? | No. The hash covers messages, order and timestamps, not the title or importer-produced metadata |

Then search the document for anything that contradicts those four answers:

```bash
grep -n "append\|delete\|deletion\|remove\|hash" ARCHITECTURE.md
```

Expected: every hit is consistent with the table above. §9's description of `append` as the
mechanism for oversized documents is consistent — the record narrows its use, it does not
redefine it.

## 3. §17 reaches the policy in one hop (SC-002)

```bash
sed -n '/^## 17\./,/^## 18\./p' ARCHITECTURE.md
```

Expected: the section names ADR-006 explicitly, so a reader who arrives asking about idempotency
does not have to already know the record exists.

## 4. The prohibition is quotable (SC-005)

```bash
grep -n "MUST NOT" ARCHITECTURE.md
```

Expected: a single sentence forbidding both diffing the raw archive against an export and deriving
removals from one — usable verbatim in a code review, without surrounding context.

## 5. The downstream issues are unblocked (SC-003)

For each of #8, #14 and #21, check that the consequence it needs is stated in the record rather
than left to that issue to decide:

* **#8** — the canonical hash excludes the title and importer-produced metadata.
* **#14** — the import state never derives removals from an export; the skip is by source id plus
  content hash.
* **#21** — `status` reports the age of the last import, which is what makes the refresh cadence
  visible.

## 6. Nothing else broke

```bash
uv run ruff check . && uv run ruff format --check . && uv run pytest
```

Expected: green. This proves only that the documentation change disturbed nothing in the codebase
— no check in this repository inspects Markdown, so CI cannot verify the content of the record.
Sections 1 through 5 are the verification; this is the guard rail.

## What is deliberately not verified here

The behavioural test named in issue #39 — import an export from which a previously imported
conversation is missing, then assert it survives in the raw archive and in the bank — **cannot run
in this feature**. There is no importer, no archive and no memory store yet. It is inherited by
#14, which delivers the import state, and is recorded in the specification's Assumptions so that
the inheritance is visible rather than lost.
