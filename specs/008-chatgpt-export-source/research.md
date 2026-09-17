# Research: ChatGPT export source

Decisions taken before design. Each resolves an unknown in the plan's technical context or a choice
the specification left to planning. Fixture shapes below are described, never copied from a real
export (CLAUDE.md).

## R1 — What the export contains, as far as this feature reads it

**Decision.** The source reads the conversation files of the export and nothing else. A conversation
file is a JSON array of conversation records. The fields read are:

| Level | Field | Use |
|---|---|---|
| conversation | `conversation_id`, falling back to `id` | native identifier (FR-009) |
| conversation | `title` | title, absent when null or missing (FR-011) |
| conversation | `create_time`, `update_time` | seconds since the epoch, as floats or null (FR-010) |
| conversation | `mapping` | node id → node |
| conversation | `current_node` | the node the interface displayed last (FR-005) |
| node | `parent`, `children` | the graph |
| node | `message` | null for structural nodes such as the root (FR-008) |
| message | `author.role`, `author.name` | role; the tool's name for tool nodes |
| message | `create_time` | the turn's time, or null |
| message | `recipient` | `all` for an ordinary turn; a tool's name for a tool call (R6) |
| message | `content.content_type` and its payload | R5 |
| message | `metadata.is_visually_hidden_from_conversation` | hidden node (FR-008) |
| message | `metadata.attachments[].name` | file markers (FR-015) |

Every other field is ignored without a record. Ignoring a *field* loses no turn. What must be recorded
is a *node* or a *content part* that was left out, and R4 and R5 cover those.

**Rationale.** The graph and these fields are what the export has carried across the versions it has
shipped. The rest — moderation results, model slugs, plugin and gizmo ids, safe URLs — is
presentation or service metadata with no place in the normalized model (#8).

**Alternatives considered.** Taking the export's own linear rendering, where one exists (issue #10).
Rejected: it is not present in every export version, and the graph is the authoritative structure.
The HTML page in the archive renders the same graph and adds nothing to it.

## R2 — Accepting the export: an archive or a directory, one or several conversation files

**Decision.** `ChatGPTExportSource(path)` accepts either a `.zip` archive or a directory. Its
conversation files are `conversations.json`, or, when the export is split, every file matching
`conversations-<digits>.json`, read in numeric order. They are looked for at the top level of the
archive or directory. No conversation file is a permanent export-level failure, and so is a
directory or archive holding both the single and the split form, because the reader cannot tell
which one is authoritative.

The standard library's `zipfile` opens members as streams, so an archive is read without being
extracted to disk.

**Rationale.** FR-002: the export in the form the person downloads it. Reading the archive in place
also means no extracted copy of private history is left behind in a temporary directory.

**Alternatives considered.** Requiring the person to extract `conversations.json` first. Rejected:
it is one more manual step in a refresh that ADR-006 already makes manual, and it leaves copies of
the export around. Accepting a single JSON file path as well is harmless and is allowed. It is the
directory case with the location already resolved.

## R3 — Streaming the conversation array without a new dependency

**Decision.** Records are read one at a time by an incremental scanner over the standard library's
`json.JSONDecoder.raw_decode`. The scanner:

1. reads the text stream in fixed-size chunks (UTF-8, `﻿` tolerated at the start);
2. consumes the opening `[`, then repeatedly skips whitespace and a separating `,`, and calls
   `raw_decode` at the current position;
3. when decoding fails and the stream is not at its end, reads more and tries again — the buffer
   size at least doubles between attempts, so a large record costs O(n) rather than O(n²) decodes;
4. on success, keeps **the exact text slice** that was decoded as the record's original (R8), drops
   the consumed prefix from the buffer, and yields the decoded object;
5. stops at the closing `]`.

Peak memory is bounded by the largest single record plus one chunk, not by the export.

Three refinements came out of review, each with a test:

- A decode is also not trusted when it ends in a number that the next character could extend.
  `raw_decode` takes `1500` out of `1500.0`.
- Only a decode error within a few characters of the buffer's end, or an unterminated string, is
  read as truncation. Any other error fails at once, so garbage is not buffered to the end of the
  file first.
- Some failures are not `JSONDecodeError`: an integer past the interpreter's digit limit, nesting
  past the recursion limit, invalid UTF-8, or a compressed member that fails to inflate. These are
  export-level `SourceFormatError`s too.

A zip member's CRC is checked only once the member has been read to its end. A corrupted archive
can therefore yield its early conversations before it fails, which streaming makes unavoidable.
Text after the closing `]` is refused, so two concatenated arrays do not pass silently as one.

A record that is valid JSON but not a readable conversation is a **per-conversation** failure
(FR-019), and iteration continues. Text that is not valid JSON at all cannot be resynchronized:
a scanner cannot find where the broken record ends. So it is an **export-level** permanent failure.
Every record before it has already been yielded, and the iterator ends after raising.

**Rationale.** CS-2 and SC-007 require streaming. A year of history in a single JSON array is the
ordinary case, and `json.load` would hold all of it, plus its Python objects, several times over.
The constitution fixes the stack, and nothing in it parses JSON incrementally. The standard library
is enough, and a second parser would be a dependency with no stack row.

**Alternatives considered.**
- `json.load` of the whole file. Rejected: memory grows with the export (SC-007).
- `ijson`. It streams well, but it adds a dependency and, more to the point, does not give back the
  exact bytes of each record. The original would then have to be re-serialized, which is weaker
  evidence for Principle I than the bytes themselves.
- Splitting the file on a textual pattern. Rejected: record boundaries cannot be found reliably
  without parsing strings, and conversation text is full of braces.

## R4 — Reconstructing the thread

**Decision.** For each conversation:

1. **Validate the graph.** Every `parent` and `children` entry names a node in `mapping`, and
   parent and children agree. Exactly one node has no parent. Walking parents from any node reaches
   the root without revisiting a node. Any violation is a per-conversation failure (spec edge case:
   cycle or dangling parent).
2. **Choose the leaf.** It is `current_node` when that names a node in the mapping. Otherwise, from
   the root, follow the **last-listed child** at every fork until a node with no children, and record
   `fallback_branch`.
3. **Walk** from the leaf to the root through `parent`, then reverse. This is the thread. The order
   of turns is this order and nothing else (FR-007).
4. **Account for every node** (SC-005). Nodes on the thread become turns, are folded into a tool
   activity (R6), or are omitted as `structural` (no message) or `hidden` (R5). Nodes off the thread
   are counted as `abandoned_branch`. The four counts plus the turns plus the folded nodes equal the
   size of the mapping. A unit test asserts this for every fixture.

**Rationale.** The spec's assumption: the current node marks what the interface displayed, and
regenerations and edits are appended after the child they replace, so the last child is the latest.
The fallback uses no times, which may be absent. Walking up from the leaf rather than down from the
root is what makes the choice unambiguous at every fork.

**Alternatives considered.** Choosing the branch by the latest `create_time`. Rejected: message
times are sometimes null, and ties are possible. Importing every branch was rejected for the reason
in the spec's assumptions.

## R5 — Content types

**Decision.** A message's content becomes text, non-text markers and, for hidden kinds, an
omission:

| `content_type` | Becomes |
|---|---|
| `text` | text: the string `parts`, joined with `\n` |
| `multimodal_text` | text from string parts; `image_asset_pointer` → `IMAGE` marker; `audio_asset_pointer`, `real_time_user_audio_video_asset_pointer` → `AUDIO` marker; `audio_transcription` → its `text` joined into the text; any other part type → `OTHER` marker named after that part type |
| `code` | text: `text` (usually a tool call — R6) |
| `execution_output` | text: `text` (usually a tool result — R6) |
| `tether_quote` | text: `text`, preceded by `title` and `url` where present |
| `tether_browsing_display` | text: `result`, followed by `summary` where present |
| `system_error` | text: `name: text` |
| `thoughts`, `reasoning_recap` | omitted as `hidden_reasoning` (spec assumption) |
| `user_editable_context`, `model_editable_context` | omitted as `hidden` when the node is marked hidden. Otherwise text from their string fields, in field-name order |
| anything else | the message is kept with empty text and an `OTHER` marker named after the content type, and the type name is counted under `unrecognized_content_type` |

`metadata.attachments` adds a `FILE` marker per attachment, carrying the attachment's `name`. A
node whose `metadata.is_visually_hidden_from_conversation` is true is omitted as `hidden`,
whatever its content type.

**Rationale.** FR-013 and FR-015: text comes through unaltered beyond joining; everything else
leaves a marker. The table covers the types the export is known to carry. The final row is what
keeps an unknown future type from failing a conversation or disappearing (User Story 3, scenario 3).
A type name is format vocabulary, not conversation content, so it may appear in the record.

**Alternatives considered.** Failing a conversation that contains an unknown type. Rejected: a
format change on the service side would then fail every conversation that uses the new type, and
the spec says the conversation is not failed.

## R6 — Tool calls and their results

**Decision.** On the thread, an assistant message whose `recipient` is not `all` is a **tool call**
to the tool named by `recipient`. It becomes an assistant turn with empty text and one
`ToolActivity(name=recipient, request=<its text>)`. Nodes omitted under R5 (hidden, hidden
reasoning, structural) are transparent to adjacency, because folding runs over the turns that
remain. If the **next** remaining turn is a message
with role `tool` and `author.name` equal to that recipient, that node's text becomes the activity's
`result`. The tool node is then **folded** into the call and does not become a turn of its own. A
call not followed by such a node keeps `result` absent (FR-014). A tool message that answers no
immediately preceding call stays a `TOOL` turn with its text.

**Rationale.** #8's `ToolActivity` is modelled at the level this export carries: a name, a request,
a result. Folding keeps the result from appearing twice — once in the activity and once as a turn —
which would double it in extraction. The call → result chain stays inside the conversation, as §7
intends.

**Alternatives considered.** Keeping every tool node as a `TOOL` turn and emitting no `ToolActivity`.
Rejected: the call and its result would lose their pairing, and the model's field for this would go
unused by the one source it was designed for.

## R7 — Times

**Decision.** An epoch float becomes `datetime.fromtimestamp(value, UTC)`. The conversation's
`started_at` is its `create_time`; if that is absent, it is the earliest message time on the
thread, and `start_from_messages` is recorded. If no time exists, the conversation fails. A value
that is not a finite number within the range `datetime` accepts also fails the conversation.
`last_activity_at` is `update_time`. When `update_time` precedes `started_at`, it is dropped and
`inconsistent_times` is recorded. The model would otherwise refuse the conversation, and a real
time is not to be invented in its place (§11). Nothing reads a clock. A unit test controls the clock
and asserts that no yielded time equals it (SC-006).

**Rationale.** FR-010 and the spec's edge cases.

## R8 — The original

**Decision.** `OriginalPayload(content=<the exact decoded text slice, encoded as UTF-8>,
media_type="application/json")`. It is the conversation's record exactly as the export spelled it.
Parsing that payload alone yields an equal conversation, and a unit test asserts this for every
fixture (User Story 5, scenario 2). Re-reading the export yields the same bytes, so CS-4 holds for
originals too.

**Rationale.** Principle I, and #9's reasoning for `SourceConversation`: the archive holds the
original so that a fixed parser can be re-run. The exact bytes are stronger than a re-serialization,
because a re-serialization is itself output of the code under suspicion.

## R9 — Where the omission record goes

**Decision.** Each conversation's `ThreadAccount` (data-model.md) is emitted as one structured log
event, `chatgpt.conversation.read`, through `hermes_memory.observability.get_logger`. The event
carries the source id, the number of turns, the number of folded tool nodes, and the omission counts
by reason. Unrecognized type names are included only when that count is non-zero. No title and no
text are included. A conversation with nothing omitted still emits the event, with every omission
count at zero (FR-017), so the log accounts for every conversation read. The same value is
reachable by calling the thread reconstruction directly, and that is how unit tests assert it
without parsing logs.

**Rationale.** `SourceConversation` is a frozen boundary type with `extra="forbid"`, so a report
cannot be attached to it without changing #9's contract for one source. The logging baseline of #6
is where §18 already expects per-operation records. Counts and type names are not conversation
content, so Principle V is not engaged.

**Alternatives considered.** Adding a report field to `SourceConversation`. Rejected: it changes a
boundary type for all sources in order to serve one, and it is not needed until #19's run summary
asks for it. If #19 does ask, amending the boundary is its decision.

## R10 — Failure translation

**Decision.**

| Condition | Raised |
|---|---|
| path missing; `PermissionError`, `OSError` while opening or reading | `SourceUnavailable` (retryable) |
| not a zip and not a directory or JSON file; `zipfile.BadZipFile`; no conversation file; both single and split forms present; top level not an array; invalid JSON that cannot be resynchronized; not UTF-8 | `SourceFormatError`, no subject: export-level, permanent. The iterator then ends |
| record not an object; no identifier; bad graph; no time anywhere; time out of range; a model `ValidationError`; identifier already seen in this read | `SourceFormatError(subject=<id or None>)`: per conversation. Iteration continues |

Every underlying exception is chained with `raise ... from`. The message states the rule broken
("mapping has two roots", "no creation time and no message time"), never a value from the record.
A `pydantic.ValidationError` is rendered from its error **types and locations only**, because its
default string includes the offending input, which is conversation content (Principle V).

**Rationale.** #9's error contract (E1, E5) and CS-5 to CS-7. The one subtle row is the validation
error: its obvious rendering leaks.

## R11 — The contract suite against the real parser

**Decision.** `tests/contracts/test_chatgpt_source_passes_the_contract.py` subclasses
`ConversationSourceContract`. `make_source` writes the suite's conversations into a synthesized
export directory (`tmp_path`) through a test-only writer, `tests/synthetic/chatgpt_export.py`, and
returns `ChatGPTExportSource` over it. `make_source_with_one_unreadable` writes the second record
with a dangling parent, so the failure comes from the real graph validation, not from a switch.
`make_unreachable_source` points at a path that does not exist. The same writer builds the unit
fixtures, with explicit control over branches, hidden nodes, tool calls and missing fields.

**Rationale.** SC-002 with nothing skipped, and a harness that proves the parser rather than a
pass-through (spec assumption). The suite's `make_source` has no `tmp_path` parameter, so the
subclass takes it from an autouse fixture.
