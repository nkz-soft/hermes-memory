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

Architecture is fixed; implementation has not started. The stack is Python — a
modular monolith calling a self-hosted Hindsight instance.

The first milestone is narrow on purpose: import ChatGPT history, and have
Hermes answer a question from it. Claude Code, Codex and other sources follow as
separate work, each with its own decision record.

## Documentation

[ARCHITECTURE.md](ARCHITECTURE.md) — scope, boundaries, memory bank strategy,
the Hindsight contract the design relies on, phases, and decision records.

## License

See [LICENSE](LICENSE).
