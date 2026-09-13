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

## Documentation

[ARCHITECTURE.md](ARCHITECTURE.md) — scope, boundaries, memory bank strategy,
the Hindsight contract the design relies on, phases, and decision records.

## License

See [LICENSE](LICENSE).
