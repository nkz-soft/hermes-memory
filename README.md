# hermes-memory

Long-term engineering memory shared across AI assistants.

The goal is to give [Hermes](https://github.com/NousResearch/hermes-agent) access
to the history that currently sits locked inside other tools — ChatGPT
conversations, Claude chats, and coding-agent sessions — so that past technical
decisions, investigations and reasoning can be recalled without being carried
over by hand.

## How it works

Conversation history is exported from each source, normalized into a
source-independent model, stripped of secrets, tagged with its project and
provenance, and retained in [Hindsight](https://github.com/vectorize-io/hindsight),
which handles fact extraction, the knowledge graph and retrieval. Agents then
recall from a single shared memory bank.

```text
ChatGPT export ──► import pipeline ──┬──► raw archive
                                     └──► Hindsight ──► Hermes
```

Originals are archived independently of Hindsight, so extraction can be re-run —
with a better model, a different mission or a fixed parser — without going back
to the original services for another export. It also keeps the memory engine
replaceable.

## Status

Architecture is fixed; the project skeleton exists and the modules are empty. The
stack is Python — a modular monolith calling a self-hosted Hindsight instance.

The first milestone is narrow on purpose: import ChatGPT history, and have
Hermes answer a question from it. Claude Code, Codex and other sources follow as
separate work, each with its own decision record.

## Development

Python 3.13, managed with [uv](https://docs.astral.sh/uv/). Nothing else needs to
be installed first — `uv` provisions the interpreter itself from `.python-version`.

```bash
uv sync                                              # install the environment
uv run pytest                                        # run the tests
uv run ruff check . && uv run ruff format --check .  # lint and formatting
```

The same three commands run in CI on every pull request, installing from the
committed `uv.lock`, so a local pass and a CI pass mean the same thing.

The module tree under `src/hermes_memory/` mirrors the layout recorded in the
[constitution](.specify/memory/constitution.md); a test parses that record and
fails if the two disagree in either direction.

## Configuration

Everything the project reads from its environment is listed in
[`.env.example`](.env.example). Copy it and fill in your own values:

```bash
cp .env.example .env
```

Two variables are required — `HERMES_HINDSIGHT__BASE_URL`, your self-hosted
Hindsight instance, and `HERMES_LLM__BASE_URL`, the OpenAI-compatible endpoint
extraction is routed through. Everything else has a working default. Tokens are
optional, because a local instance may run unauthenticated.

`.env` is ignored by git and must never be committed; credentials come from the
environment or from that untracked file, never from a file in the repository. A
real environment variable overrides the file, which is how to change one value
for a single run.

A missing or malformed setting fails at startup, naming every variable at fault,
rather than partway through an import.

## Logging

Records are JSON, one object per line, on standard error. Each ingestion
operation produces exactly one record carrying its source, source id, project,
bank, document id, start time, duration, status and error.

**Credentials are never logged.** Tokens, keys and authorization headers are
withheld by the logging pipeline itself — by field name, by secret type, and by
the shape of the value — so it is not something a caller has to remember. A
withheld value is replaced by `[redacted]` rather than dropped, so a reader can
tell redaction from absence.

**Conversation contents are not logged by default.** Set
`HERMES_LOGGING__INCLUDE_CONVERSATION_CONTENT=true` for a single debugging run
when you need to see the conversation a parser choked on. It puts private text
wherever your log goes, so leave it out of `.env`. It never reveals a
credential: those stay redacted whatever it is set to.

`HERMES_LOGGING__LEVEL` sets how much is emitted (`DEBUG` through `CRITICAL`,
default `INFO`). Both variables are described in [`.env.example`](.env.example).

## Documentation

[ARCHITECTURE.md](ARCHITECTURE.md) — scope, boundaries, memory bank strategy,
the Hindsight contract the design relies on, phases, and decision records.

## License

See [LICENSE](LICENSE).
