# Quickstart — verifying the normalized conversation model

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

How a reviewer confirms this feature does what it claims. Every step is a command with an expected
outcome; no step is "read it and agree".

## Prerequisites

```bash
uv sync --all-extras
```

Nothing else. The module reads no configuration and requires no service — that is FR-018, and step
5 below is what proves it.

## 1. The suite is green

```bash
uv run pytest
```

Expected: every test passes, including the new files under `tests/unit/` and
`tests/structure/test_normalization_boundary.py`.

## 2. The linter is clean

```bash
uv run ruff check . && uv run ruff format --check .
```

## 3. The hash is deterministic across processes

The claim that matters most, and the one a single-process test cannot make (contract C1, C9):

```bash
uv run pytest tests/unit/test_canonical.py -k subprocess -v
```

Expected: the determinism tests pass. They build the same conversation in two separate interpreters
and compare the hex digests.

## 4. What moves the hash, and what does not

```bash
uv run pytest tests/unit/test_canonical.py -v
```

Expected, matching [contracts/canonical-form.md](./contracts/canonical-form.md):

* a changed message, role, order, timestamp, tool result or non-text part → the hash changes;
* a changed title, provenance field or tag → the hash does not.

## 5. The boundary of Principle IV holds

```bash
uv run pytest tests/structure/test_normalization_boundary.py -v
```

Expected: the static import check and the runtime `sys.modules` check both pass.

To see the guard bite rather than take it on trust, add `import httpx` to any file under
`src/hermes_memory/normalization/` and re-run: both tests fail, the static one naming the file and
the line. Remove it again.

## 6. The model is usable without anything else

```bash
uv run python -c "
from datetime import UTC, datetime
from hermes_memory.normalization import Conversation, Message, Role, Source

c = Conversation(
    source=Source.CHATGPT,
    source_id='abc-123',
    title='Wolverine Saga Error Handling',
    started_at=datetime(2026, 1, 1, 9, tzinfo=UTC),
    messages=(Message(role=Role.USER, text='why does retain fail here?'),),
)
print(c.document_id)
print(c.content_hash())
print(c.model_copy(update={'title': 'Renamed'}).content_hash() == c.content_hash())
"
```

Expected:

```text
chatgpt:abc-123
<64 hex characters>
True
```

The third line is ADR-006 decision 4 in one assertion: a rename does not re-extract.

## 7. The diff is confined

```bash
git diff --stat origin/main...HEAD
```

Expected (SC-007): files under `src/hermes_memory/normalization/`, `tests/` and
`specs/006-normalized-conversation-model/`, plus one deliberate line in
`tests/structure/test_module_layout.py` adding `normalization` to `FILLED_BOUNDARIES`
(research R13). Nothing else — in particular no change to `pyproject.toml`, since this feature adds
no dependency.
