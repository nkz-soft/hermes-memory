# Quickstart: validating the ChatGPT export source

Everything here runs on synthesized exports. Nothing needs network access, Hindsight or a real
export.

## Prerequisites

```bash
uv sync
```

## 1. The contract suite passes, nothing skipped (SC-002)

```bash
uv run pytest tests/contracts/test_chatgpt_source_passes_the_contract.py -v -rs
```

Expected: 7 passed, 0 skipped.

## 2. The parser's own behaviour (FR-023)

```bash
uv run pytest tests/unit -k chatgpt -v
```

Expected, among the rest: a plain thread, a branched thread, an empty conversation, a missing
title, a message with no timestamp, a hidden node, tool calls with and without results, non-text
parts, an unrecognized content type, a malformed conversation, and the accounting invariant — all
passing.

## 3. Memory stays flat as the export grows (SC-007)

```bash
uv run pytest tests/unit/test_chatgpt_streaming.py -v
```

Expected: the peak traced allocation for a synthesized export of many conversations is within a
fixed factor of the peak for an export with far fewer.

## 4. The whole suite, lint, and the boundary checks

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

Expected: all pass. The structure tests confirm that `ingestion` imports no Hindsight, HTTP or
storage module.

## 5. By hand, against a local export (optional, never committed)

Put a real export under `data/`, which git ignores, and read it without printing content:

```bash
uv run python -c "from pathlib import Path; from hermes_memory.ingestion.chatgpt import ChatGPTExportSource as S; print(sum(1 for _ in S(Path('data/chatgpt-export.zip')).read()))"
```

Expected: a count, plus one `chatgpt.conversation.read` log event per conversation that holds
counts only. If a conversation fails, the command stops with that `SourceFormatError`. This is a
smoke check, not the pipeline, which is #19.
