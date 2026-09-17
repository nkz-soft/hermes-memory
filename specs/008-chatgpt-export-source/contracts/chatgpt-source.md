# Contract: `ChatGPTExportSource`

The public surface this feature adds, and the behaviour it promises beyond #9's CS-1 to CS-7.

## Surface

```python
from hermes_memory.ingestion.chatgpt import ChatGPTExportSource

source = ChatGPTExportSource(path)  # a .zip archive, a directory, or a conversations JSON file
source.source  # Source.CHATGPT
source.read()  # Iterator[SourceConversation]
```

The constructor does no I/O: it cannot fail on a missing path. Each call to `read()` opens the export
afresh, which is why reading twice yields equal results (CS-4). Nothing else in
`hermes_memory.ingestion.chatgpt` is public.

## Rules

| Id | Rule | Spec |
|---|---|---|
| CG-1 | Satisfies CS-1 to CS-7; none skipped | FR-001, FR-024 |
| CG-2 | The turns are the branch root → `current_node`; with no valid current node, the last-listed child at every fork, recorded | FR-005, FR-006 |
| CG-3 | Turn order is graph order and never derived from times | FR-007 |
| CG-4 | `document_id == "chatgpt:" + conversation_id` | FR-009 |
| CG-5 | Times are the export's, as UTC instants, or absent; no clock is read | FR-010 |
| CG-6 | Title is the export's or absent | FR-011 |
| CG-7 | A tool call becomes a `ToolActivity`; an immediately following matching tool node is folded in as its result | FR-014 |
| CG-8 | Image, audio, file and unrecognized parts become non-text markers; an unrecognized type never fails a conversation | FR-015 |
| CG-9 | Every node of the mapping is accounted for, in one log event per conversation, which contains no title and no text | FR-016, FR-017, SC-005 |
| CG-10 | `original.content` is the record's exact bytes, and parsing it alone yields an equal conversation | FR-018 |
| CG-11 | A per-conversation failure is `SourceFormatError` with `subject` when an id exists, and iteration continues | FR-019 |
| CG-12 | An unreachable export is `SourceUnavailable`; an unrecognizable one is `SourceFormatError` without subject | FR-020, FR-021 |
| CG-13 | No error message contains a value from the record | FR-022 |
| CG-14 | Peak memory does not grow with the number of conversations read | FR-003, SC-007 |

## Log event

`chatgpt.conversation.read`, at `info`, one per yielded conversation:

```text
source_id, nodes, turns, folded_tool_results, structural, hidden, hidden_reasoning, abandoned_branch,
fallback_branch, start_from_messages, inconsistent_times, unrecognized_content_types
```

No field holds conversation content. `unrecognized_content_types` is omitted when it is empty.
