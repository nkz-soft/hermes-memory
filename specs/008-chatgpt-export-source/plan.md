# Implementation Plan: ChatGPT export source

**Branch**: `008-chatgpt-export-source` | **Date**: 2026-09-17 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/008-chatgpt-export-source/spec.md` (issue #10)

## Summary

Implement `ChatGPTExportSource`, the first real conversation source behind #9's boundary. It opens a
ChatGPT export (an archive, a directory or a conversations file) and streams its conversation
records one at a time with a standard-library incremental scanner, keeping each record's exact
bytes as the original. For each record it validates the message graph and reconstructs the thread
from the root to the current node, falling back to the last-listed child at every fork. It then maps
turns into #8's model, folding each tool call and its result into a `ToolActivity` and every
non-text part into a marker, and accounts for every node it did not turn into a turn in one
content-free log event per conversation. Per-conversation failures leave the iterator usable, and
export-level failures end it. The source is proved by #9's contract suite, run against synthesized
exports written by a test-only writer, and by unit tests for each branch of the format.

## Technical Context

**Language/Version**: Python 3.13

**Primary Dependencies**: Pydantic v2 (#8's model), structlog through `hermes_memory.observability`
(#6). Standard library `json`, `zipfile`, `io`, `datetime`. **No new dependency** (research R3).

**Storage**: None written. Reads the export read-only, as a `.zip` in place or as a directory.

**Testing**: pytest. The contract suite `tests/contracts/source.py` (#9); unit tests over exports
synthesized into `tmp_path`; `tracemalloc` for the memory bound.

**Target Platform**: The developer machine and the container image (#7), Linux and Windows.

**Project Type**: A module of the modular monolith — `hermes_memory.ingestion.chatgpt`.

**Performance Goals**: Reads a synthesized 10,000-conversation export in one pass. No latency
target: a person runs an import rarely (ADR-006), and extraction dominates the pipeline's cost.

**Constraints**: Peak memory is bounded by the largest single conversation, not by the export
(SC-007). No clock is read (§11). No conversation content in logs or errors (Principle V). No
Hindsight, HTTP or storage import (Principle IV).

**Scale/Scope**: A year or more of personal history: thousands to tens of thousands of
conversations, and a conversations file that can exceed a gigabyte.

No item is left as NEEDS CLARIFICATION. research.md settles each choice.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | How this plan complies |
|---|---|
| **I. Raw archive is the source of truth** | Every yielded conversation carries its original, the record's **exact bytes** rather than a re-serialization (R8). A unit test proves the original alone re-parses to an equal conversation, so a replay from the archive (#13) can re-run a fixed parser. This feature writes no archive itself — that is #13. |
| **II. Provenance and stable identity** | `source_id` is the export's native `conversation_id`, so `document_id` is `chatgpt:{id}`, stable across runs, and derived by #8's model rather than supplied (CG-4). Times are the export's own, and no clock is read. A test controls the clock to prove it (R7, SC-006). A duplicate id within one export fails rather than letting two conversations share an identity. |
| **III. Test-first** | Every rule in contracts/chatgpt-source.md gets a test written and observed failing before its code. The constitution's minimum for a source parser is met by unit tests over realistic synthesized fixtures, and #9's contract suite runs with nothing skipped. |
| **IV. Replaceable boundaries** | The source implements `ConversationSource` and nothing else. Callers see only `SourceConversation` and #9's errors, and no library exception crosses (CS-7, R10). Parsing and thread reconstruction are separate functions, testable without files. No Hindsight vocabulary appears, and the existing structure tests enforce that. |
| **V. Secrets never reach the memory engine** | The source does not sanitize: that is #11, which runs downstream before Hindsight. What this feature owns is not leaking in its own output. Logs carry counts and type names only (R9), and error messages carry rule descriptions, never record values. A `ValidationError` is rendered from types and locations, because its default rendering includes the input (R10). |

**Stack.** Only fixed-stack tools and the standard library are used. No dependency is added, so no
decision record is required.

**Governance impact.** None. This is not a new source (§2 already names ChatGPT as the MVP source),
and the issue ticks "None of the above".

**Gate result: PASS.** No deviation to justify.

**Re-check after Phase 1 design: PASS.** The design adds no boundary type and no field to #9's
`SourceConversation`. The omission record goes through #6's logging instead (R9), so the boundary
stays source-independent. One consequence is recorded rather than hidden: a pipeline that wants
the omission counts in its run summary (#19) has to either read the log or amend the boundary, and
that is #19's decision.

## Alternatives considered

- **The export's own linear rendering, where one exists** (from issue #10). Rejected: not present in
  every export version, and the graph is the authoritative structure (R1).
- **Loading the whole conversations file with `json.load`.** Rejected: memory grows with the export
  (R3).
- **A streaming JSON library such as `ijson`.** Rejected: it adds a dependency outside the stack
  table, and it cannot return a record's exact bytes, which Principle I is better served by (R3).
- **Importing every branch of a conversation.** Rejected: it puts abandoned answers into memory as
  if they had been accepted (spec assumptions).
- **Tool results as separate `TOOL` turns only.** Rejected: it loses the pairing with the call and
  duplicates the result when combined with `ToolActivity` (R6).
- **Adding an omission report to `SourceConversation`.** Rejected for now: it changes a boundary
  shared by every source in order to serve one (R9).

## Project Structure

### Documentation (this feature)

```text
specs/008-chatgpt-export-source/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── chatgpt-source.md
├── checklists/
│   └── requirements.md
└── tasks.md             # /speckit-tasks, after the gate
```

### Source Code (repository root)

```text
src/hermes_memory/ingestion/chatgpt/
├── __init__.py          # public surface: ChatGPTExportSource only
├── export.py            # locate conversation files in an archive/directory/file; open as text streams (R2)
├── records.py           # incremental array scanner → ExportRecord with exact raw slice (R3)
├── thread.py            # graph validation, leaf choice, walk, ThreadAccount (R4)
├── content.py           # content types → text + markers; tool-call folding (R5, R6)
├── conversation.py      # record → Conversation + ThreadAccount; times (R7); error rendering (R10)
└── source.py            # ChatGPTExportSource and its resumable iterator; log event (R9)

tests/
├── synthetic/
│   ├── __init__.py
│   └── chatgpt_export.py        # test-only writer: build records, branches, hidden/tool nodes; write zip/dir
├── contracts/
│   └── test_chatgpt_source_passes_the_contract.py   # CS-1..CS-7 against the real parser (R11)
└── unit/
    ├── test_chatgpt_records.py      # scanner: chunk boundaries, BOM, split files, invalid JSON
    ├── test_chatgpt_export.py       # zip / directory / file; missing; both forms; no conversation file
    ├── test_chatgpt_thread.py       # plain, branched, fallback, cycle, dangling, accounting invariant
    ├── test_chatgpt_content.py      # every content type row; attachments; unknown type; tool folding
    ├── test_chatgpt_conversation.py # id, title, times, empty conversation, no timestamp, original re-parse
    ├── test_chatgpt_source.py       # per-conversation failure continues, duplicate id, log event, no content in errors/logs
    └── test_chatgpt_streaming.py    # tracemalloc bound (SC-007)
```

**Structure Decision**: The code lives in the existing `ingestion/chatgpt` package that the
constitution's module layout reserves for it. One module per research decision keeps the parts that
can be tested without files (`thread`, `content`, `conversation`) apart from the parts that do I/O
(`export`, `records`, `source`). The test-only export writer lives in `tests/synthetic/` because it
is neither a fake nor a contract. It builds inputs, and both the contract harness and the unit tests
need it.

## Complexity Tracking

No constitution violations; nothing to justify.
