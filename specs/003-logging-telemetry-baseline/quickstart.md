# Quickstart: validating the logging and telemetry baseline

How to satisfy yourself, by hand, that the deliverable does what
[spec.md](spec.md) says — beyond the suite, which asserts the same things without a human reading
them. The contract is [contracts/observability.md](contracts/observability.md).

## Prerequisites

A checkout with the environment synced. No Hindsight instance, no LLM proxy, no collector and no
`.env` are needed: this feature contacts nothing.

```bash
uv sync
```

## 1. The suite

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

Expected: green, with the new suites under `tests/unit/` for the pipeline and `tests/structure/`
for the repository invariants.

## 2. A record is structured, and carries what §18 asks for

```bash
uv run python -c "
from hermes_memory.observability import ingestion_operation
with ingestion_operation(source='chatgpt', source_id='abc-123', bank='engineering-global',
                         project='hermes-memory', document_id='chatgpt:abc-123'):
    pass
"
```

Expected: one JSON object on standard error carrying `event`, `source`, `source_id`, `project`,
`bank`, `document_id`, `start_time`, `duration_ms`, `status` and `error` — with `status` of
`imported` and `error` of `null`.

## 3. A failure still reports, and still propagates

```bash
uv run python -c "
from hermes_memory.observability import ingestion_operation
try:
    with ingestion_operation(source='chatgpt', source_id='abc-123', bank='engineering-global'):
        raise RuntimeError('the export was truncated')
except RuntimeError as error:
    print('the caller still saw:', error)
"
```

Expected: one record with `status` of `failed` and the message in `error`, **and** the last line
showing the exception reached the caller. Both halves matter: a context manager that swallowed the
failure would look identical in the log.

## 4. A credential does not appear — the check this feature exists for

```bash
uv run python -c "
from hermes_memory.observability import get_logger
get_logger().info('calling hindsight',
                  hindsight_token='hs-live-9f3c2a7e51b04d6f',
                  authorization='Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.c2lnbmF0dXJl',
                  note='the proxy at https://user:hunter2@proxy.internal refused it',
                  author='someone')
"
```

Expected: `hindsight_token` and `authorization` replaced by the marker; the password gone from the
URL inside `note` while the rest of the sentence survives; `author` untouched. The last one is the
point of the name roster being segments rather than substrings.

## 5. Conversation content is absent by default, and present only when asked

```bash
uv run python -c "
from hermes_memory.observability import ConversationContent, get_logger
get_logger().info('parsed a conversation', body=ConversationContent('the private text'))
"
```

Expected: `[redacted:content]`, with no configuration set.

```bash
HERMES_LOGGING__INCLUDE_CONVERSATION_CONTENT=true uv run python -c "
from hermes_memory.observability import ConversationContent, configure, get_logger
from hermes_memory.settings import load_settings
configure(load_settings())
get_logger().info('parsed a conversation',
                  body=ConversationContent('the private text'),
                  hindsight_token='hs-live-9f3c2a7e51b04d6f')
"
```

Expected: the body present, and the token still redacted. That second half is FR-015 — the flag
consents to conversation text, never to a credential. This step needs the Hindsight and LLM
variables set, because `load_settings` validates the whole object; `.env.example` says which.

## 6. A span has somewhere to attach, and exports nothing

```bash
uv run python -c "
from hermes_memory.observability import configure, get_logger, get_tracer
from hermes_memory.settings import load_settings
configure(load_settings())
with get_tracer(__name__).start_as_current_span('retain'):
    get_logger().info('inside a span')
get_logger().info('outside a span')
"
```

Expected: the first record carries `trace_id` and `span_id`, the second carries neither, and
nothing hangs or retries — there is no collector and none is looked for.

## 7. The configuration roster has not drifted

```bash
uv run pytest tests/unit/test_settings_example.py
```

Expected: green, with `HERMES_LOGGING__LEVEL` and
`HERMES_LOGGING__INCLUDE_CONVERSATION_CONTENT` now listed in `.env.example`. This is 002's check,
unchanged, which is why this feature adds no check of its own for it.

## What this quickstart deliberately does not show

Retaining anything, parsing an export, or exporting a trace. None of it exists yet; this feature is
the record and the tracer those will use.
