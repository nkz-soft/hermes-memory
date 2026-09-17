# Data Model: ChatGPT export source

This feature adds no entity to the normalized model. It produces #8's `Conversation`, paired with
an `OriginalPayload` as #9's `SourceConversation`. The types below are internal to
`hermes_memory.ingestion.chatgpt` and do not cross the boundary. The one exception is the log event
of R9.

## Output (existing, unchanged)

| Type | From | Filled by this feature as |
|---|---|---|
| `SourceConversation` | #9 | `conversation` + `original` |
| `Conversation` | #8 | `source=CHATGPT`, `source_id`, `title`, `started_at`, `last_activity_at`, `messages` (research R4–R7) |
| `Message` | #8 | one per thread turn; `role`, `text`, `sent_at`, `tool_activity`, `non_text_parts` |
| `ToolActivity` | #8 | one per tool call (R6) |
| `NonTextPart` | #8 | one per image, audio, file or unrecognized part (R5) |
| `OriginalPayload` | #9 | exact record bytes, `application/json` (R8) |

## Internal types

### `ExportRecord`

One conversation record as the scanner found it.

| Field | Type | Rule |
|---|---|---|
| `raw` | `str` | the exact decoded text slice |
| `value` | `object` | the decoded JSON value. Not yet known to be an object |

### `ThreadAccount`

What reconstruction did with every node of one conversation (FR-016, SC-005). Frozen.

| Field | Type | Rule |
|---|---|---|
| `source_id` | `str` | the conversation's native id |
| `turns` | `int` ≥ 0 | nodes that became a `Message` |
| `folded_tool_results` | `int` ≥ 0 | tool nodes folded into a call's `ToolActivity` (R6) |
| `structural` | `int` ≥ 0 | nodes with no message |
| `hidden` | `int` ≥ 0 | nodes marked hidden from the conversation |
| `hidden_reasoning` | `int` ≥ 0 | reasoning nodes (R5) |
| `abandoned_branch` | `int` ≥ 0 | nodes off the chosen thread |
| `fallback_branch` | `bool` | the current node was missing or invalid (R4) |
| `start_from_messages` | `bool` | `started_at` came from the earliest message time (R7) |
| `inconsistent_times` | `bool` | `update_time` preceded the start and was dropped (R7) |
| `unrecognized_content_types` | `tuple[str, ...]` | sorted, distinct type names (R5) |

**Invariant.** `turns + folded_tool_results + structural + hidden + hidden_reasoning +
abandoned_branch == len(mapping)`. It is checked when the value is constructed, so an accounting
bug fails loudly in tests instead of producing a record that does not add up.

`ThreadAccount` contains no title and no text. It is safe to log (Principle V).

### `ReadConversation`

The result of parsing one record: `conversation: Conversation`, `account: ThreadAccount`. The
source turns it into a `SourceConversation` and a log event.

## State: one `read()`

```text
open export ──(OSError)──────────────────────► SourceUnavailable, iterator ends
   │
   ├──(not an export)────────────────────────► SourceFormatError (no subject), iterator ends
   ▼
next record ──(end of array, last file)──────► StopIteration
   │
   ├──(invalid JSON)─────────────────────────► SourceFormatError (no subject), iterator ends
   ├──(unreadable conversation / duplicate id)► SourceFormatError (subject), continue
   ▼
yield SourceConversation, log chatgpt.conversation.read, continue
```

The iterator keeps position across a per-conversation failure (CS-5). It is a class, not a
generator. The set of identifiers seen is kept for the duplicate rule. Its memory grows with the
number of conversations, but it holds identifiers only.
