# Engineering Memory — Architecture

Status: architecture fixed, implementation not started. The technology stack is
Python, decided in ADR-004 (see §20).

## 1. Purpose

Build a single long-term engineering memory that aggregates the user's
accumulated interaction history with AI systems, so that an agent can retrieve
relevant context from past conversations, technical decisions, incident
investigations and development history.

**Primary goal: give Hermes access to the user's ChatGPT and Claude history —
both plain chats and coding-agent sessions.**

Everything else — Claude Code and Codex reading the same memory, mental models,
evaluation — follows from that, and is sequenced after it.

Hindsight is the memory engine. We do not build our own RAG, and we do not add a
vector database, a search engine or a custom knowledge graph. Hindsight owns
fact extraction, entity resolution, the knowledge graph, temporal relationships,
retrieval, reranking, consolidation, observations, mental models, and the
`retain` / `recall` / `reflect` operations.

## 2. Sources and consumers

Sources of history:

* ChatGPT export — **the only source in the MVP**;
* Claude chats;
* Claude Code sessions;
* Codex sessions;
* Hermes conversations.

Every source beyond ChatGPT is added as a separate piece of work with its own
architectural decision record. Nothing in this document assumes them.

Consumers of memory:

* Hermes — the primary consumer;
* Claude Code;
* Codex;
* other coding agents later.

## 3. Principles

### 3.1. Hindsight is derived memory, not the source of truth

Original exports are stored independently of Hindsight.

```text
Raw Archive  ──►  Importer  ──►  Hindsight
```

`retain()` extracts structured memories from the input; the original text must
not live only inside Hindsight. Keeping an independent archive lets us change
the extraction policy, upgrade Hindsight, change the retain mission, fix the
parser, apply new redaction rules, and re-run ingestion — without going back to
the original services for another export.

### 3.2. Memory is scoped by tags, not by consumer

Do not create per-agent memory (`claude-memory`, `codex-memory`,
`chatgpt-memory`). The originating system is recorded as metadata on the
content, never as a separate store. Project separation is expressed through
tags — see §5 and ADR-002.

### 3.3. Provenance is mandatory

Every imported conversation must make it possible to determine its source,
original ID, original time, project, repository (when known), and the version of
the importer that produced it.

```json
{
  "source": "chatgpt",
  "source_id": "conversation-id",
  "project": "miratorg",
  "repository": "",
  "title": "Wolverine Saga Error Handling",
  "imported_at": "2026-09-12T10:00:00Z",
  "importer_version": "1"
}
```

Hindsight stores metadata alongside memory units and returns it on retrieval.

## 4. Overall architecture

```text
                    ┌─────────────────────┐
                    │    DATA SOURCES     │
                    │                     │
                    │ ChatGPT export      │  ← MVP
                    │ Claude chats        │
                    │ Claude Code         │  ← later, separate ADRs
                    │ Codex               │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │   Import Service    │
                    │                     │
                    │ Parse               │
                    │ Normalize           │
                    │ Sanitize            │
                    │ Classify            │
                    │ Enrich metadata     │
                    └──────────┬──────────┘
                               │
                  ┌────────────┴────────────┐
                  ▼                         ▼
           ┌─────────────┐          ┌──────────────┐
           │ Raw Archive │          │  Hindsight   │
           │             │          │              │
           │ originals   │          │ facts        │
           │ normalized  │          │ entities     │
           └─────────────┘          │ graph        │
                                    │ observations │
                                    └──────┬───────┘
                                           │
                         ┌─────────────────┼─────────────────┐
                         ▼                 ▼                 ▼
                      Hermes          Claude Code          Codex
                    (primary)           (later)            (later)
```

A self-hosted Hindsight instance is deployed separately and shared by all
consumers. The instance embedded in Hermes is not used as the primary store,
because memory must be reachable by more than one consumer.

## 5. Memory bank strategy

**One shared bank: `engineering-global`.** Project separation is expressed
through `project:` tags, which consumers use to filter at recall time.

This is a deliberate departure from the per-repository convention used by the
official coding-agents integration, and is recorded as ADR-002.

## 6. Tags

A strict, stable convention — tags are the only scoping mechanism, so their
naming is part of the architecture:

```text
source:chatgpt          source:claude-chat
source:claude-code      source:codex
source:hermes

project:<slug>          project:unknown

type:conversation       type:coding-session
type:decision           type:troubleshooting

user:<user-id>
```

Hindsight supports tag filtering on `recall` and `reflect`, with match modes
(any / all / strict / exact). Hermes exposes the same filtering to its provider
configuration.

## 7. Ingestion pipeline

Logical stages, each independently testable:

```text
Source
  │  parse       — read the export, reconstruct conversation structure
  ▼
Normalize       — map to a source-independent conversation model
  │
  ▼
Sanitize        — redact secrets, preserve surrounding context
  │
  ▼
Classify        — determine the project
  │
  ▼
Enrich          — attach provenance metadata and tags
  │
  ├──────────────► Raw Archive   (originals + normalized form)
  │
  ▼
Hindsight retain
```

The pipeline is composable, and runs conversation by conversation.

A conversation is sent as **one logical document**, not message by message, so
that extraction sees the whole context.

## 8. Boundaries

Every boundary is an interface, so that any single part can be replaced without
disturbing the rest — in particular Hindsight itself (ADR-001, exit strategy):

| Boundary | Responsibility |
|---|---|
| Conversation source | Read one source format, yield normalized conversations |
| Secret sanitizer | Redact secrets, report what was redacted |
| Project classifier | Determine the project for a conversation |
| Raw archive | Persist originals and normalized forms |
| Memory store | `retain` / `recall` — the only component aware of Hindsight |
| Import state | Track what has already been imported |

Neither the domain model nor the pipeline references Hindsight. Only the memory
store implementation does.

## 9. Hindsight contract

Verified against the current Hindsight documentation. Recorded here because the
architecture depends on these semantics, not as an implementation detail.

| Operation | Endpoint |
|---|---|
| Retain | `POST /v1/default/banks/{bank_id}/retain` with `{ "items": [ … ] }` |
| Recall | `POST /v1/default/banks/{bank_id}/recall` |
| Bank config | `PATCH /v1/default/banks/{bank_id}/config` |

Per-item fields that carry our architecture: `content`, `document_id`,
`timestamp`, `context`, `metadata`, `tags`, `document_tags`, `update_mode`.
Request-level: `async`, `operation_id`.

Semantics we rely on:

* **Banks are created by writes, not reads.** A read against a bank that has
  never been written returns `404`. A bank must therefore be provisioned before
  first use — and the config call itself counts as a write.
* **`document_id` gives idempotent upsert.** With the default
  `update_mode: "replace"`, re-importing the same logical document replaces the
  previous version instead of creating duplicates.
* **`operation_id` is a separate retry idempotency key**, so a retry after a
  timeout does not pay for extraction twice.
* **`update_mode: "append"`** allows a single logical document to be delivered
  as several items — the mechanism for conversations too large to send at once.
* **`timestamp` drives temporal grounding**, and is per item.

## 10. Document identity

`document_id` is mandatory and stable across runs:

```text
chatgpt:{conversation-id}
claude-chat:{conversation-id}
claude-code:{session-id}
codex:{session-id}
hermes:{session-id}
```

A freshly generated identifier per import run is never acceptable — it is what
turns a re-import into duplicated memory.

## 11. Timestamps

Send the conversation's real timestamp. The import date must never be used as
the conversation date, because temporal retrieval depends on it: questions like
"what did we use before", "when did we move to X", "how did the decision change"
degrade without it.

## 12. Retain mission

Extraction is steered toward durable engineering knowledge:

```text
Prioritize:
  architecture decisions and rationale; technology choices; implementation
  decisions; debugging investigations; root causes; successful fixes;
  unsuccessful approaches and why they failed; infrastructure configuration;
  deployment procedures; API contracts; data model decisions; migrations and
  version changes; coding conventions; project constraints; security decisions;
  operational lessons.

Do not prioritize:
  greetings; conversational filler; temporary wording; repetitive status
  messages; credentials or secrets.
```

The mission is **bank-level configuration**, not a property of an individual
retain call — see ADR-003.

## 13. Secret sanitization

Historical imports are sanitized before reaching Hindsight.

Minimum categories: API keys, bearer tokens, JWTs, GitHub and GitLab PATs,
Anthropic and OpenAI keys, AWS access keys, private keys, passwords, connection
strings, `.env` values, Kubernetes secrets.

Values are replaced with `[REDACTED]` while the surrounding context is
preserved, because the context is often the knowledge worth keeping:

```text
Bad:   drop the entire tool output
Good:  GitLab request using token [REDACTED] returned HTTP 401 Unauthorized
```

## 14. Raw archive

Originals and normalized forms are stored separately from Hindsight, behind an
interface, so the backing store can change without touching ingestion. Local
storage in the MVP; object storage is a later option.

## 15. Project detection

1. **Explicit metadata** — use the repository or working directory when the
   source carries it.
2. **Deterministic rules** — match known repository names, paths, project names
   and aliases.
3. **Model-based classification** — out of scope; an extension point is left for
   it.

ChatGPT exports carry no repository or working directory, so level 1 does not
apply to the MVP source and detection rests on alias matching. A substantial
share of conversations will not resolve to a project. They are still imported,
tagged `project:unknown`, and remain retrievable — which is possible precisely
because there is one shared bank (ADR-002).

## 16. Retrieval

`recall` for ordinary lookups: it combines semantic, keyword, graph and temporal
retrieval, and must return facts regardless of which system they originated in.

`reflect` for questions that require synthesizing many memories — how an
approach evolved, what the overall shape of a decision is. Not for every query;
it is slower and reasons over accumulated memory rather than fetching it.

## 17. Idempotency and import state

Re-running an import must be safe and must not create duplicate documents.

Two independent layers:

* **Hindsight side** — stable `document_id` guarantees upsert semantics.
* **Importer side** — a local record of what was imported (source id, content
  hash, document id, time, status). A conversation whose source id and hash are
  unchanged is skipped before any call is made, which avoids paying for
  extraction again.

The content hash is computed over a canonical representation of the normalized
conversation.

## 18. Error handling, retry and observability

Import proceeds conversation by conversation; one failure must not abort the
run. The outcome is reported as imported / skipped / failed, and each failure is
recorded with its source id, error and time.

Retry transient failures only — 429, 502, 503, 504, connection resets, timeouts
— with exponential backoff and jitter, reusing the same idempotency key. Never
retry 400, 401, 403 or invalid input.

Structured logs per ingestion operation: source, source id, project, bank,
document id, start time, duration, status, error. Conversation contents are not
logged by default. Credentials, tokens and raw authorization headers are never
logged.

## 19. Security

1. The raw archive stays local.
2. Secrets are redacted before Hindsight.
3. A self-hosted Hindsight instance is used; data is not sent to a hosted one.
4. The LLM provider used for extraction is configurable, and reached through an
   OpenAI-compatible endpoint — an existing LiteLLM proxy in this setup, so the
   actual model is proxy configuration rather than anything hardcoded here.
5. Credentials come from environment variables or a secret store, never from
   configuration files in the repository.

## 20. Technology stack

The stack is decided in ADR-004: Python 3.13, with a modular monolith calling an
external Hindsight instance. The decisions this section previously deferred are
settled there — language and runtime, import-state storage, raw archive layout,
configuration, the command-line surface and the testing framework.

None of it changes anything above: the stack was chosen to fit the architecture,
not the other way round.

Still open, and deliberately so, are the details that only implementation can
settle — the on-disk layout of the raw archive, the schema of the import-state
store, and the exact command surface. They are constrained by ADR-004 rather
than free choices, and are fixed by the first specification that needs them.

## 21. Out of scope for the MVP

Custom vector database, embeddings, reranker, knowledge graph or RAG pipeline;
web frontend; multi-user authorization; distributed ingestion; message queues;
background workers; model-based project classification; cross-bank
synchronization; Confluence, Jira and GitLab importers; mental model management.

## 22. Phases

### Phase 1 — MVP: ChatGPT history reachable from Hermes

1. Hindsight runs locally through a documented setup, with extraction routed
   through the LiteLLM proxy.
2. The bank is provisioned and its retain mission configured.
3. ChatGPT exports are parsed into the normalized conversation model.
4. Secret sanitization works.
5. Deterministic project classification works.
6. Originals and normalized forms are archived.
7. Conversations are retained with stable document ids, original timestamps,
   provenance metadata and tags.
8. Re-importing creates no duplicates.
9. A dry run reports what would happen without contacting Hindsight.
10. Parser and sanitizer are covered by tests.
11. An end-to-end test imports a conversation and retrieves a fact from it.
12. **Hermes is configured against the same bank and finds that fact.**

Item 12 is what makes the phase meaningful; the rest is the means.

### Phase 2 — coding agents

Claude Code and Codex read and write the same bank through the official
integration, including tool calls, so that the chain command → error →
investigation → solution is preserved. Acceptance: a decision discussed in
ChatGPT and imported is found by Claude Code; a refinement made in Claude Code
is visible to Codex.

### Phase 3 — synthesis

Mental models for project architecture, current stack and architecture
decisions. `reflect` verified. An evaluation dataset of at least 30 questions
with expected topics, so that memory quality can be compared objectively after
changes to the retain mission, the extractor model, the Hindsight version or the
bank strategy.

## 23. Decision records

### ADR-001 — Hindsight as the memory engine

**Decision.** Use Hindsight as the primary long-term agent memory engine.

**Rationale.** It already provides fact extraction, entity resolution, a
knowledge graph, temporal memory, retrieval, reranking, consolidation,
observations, mental models, MCP, coding-agent integrations and a native Hermes
provider. Building our own RAG first would duplicate all of it.

**Consequences.** Less code, faster MVP, one memory API, memory shared across
agents, temporal reasoning — against a dependency on Hindsight's data model, a
retrieval pipeline that is partly a black box, and the obligation to maintain a
separate raw archive.

**Exit strategy.** The raw archive and the normalized conversation model are
independent of Hindsight, so the backend can be replaced later without
re-exporting anything from the original services.

### ADR-002 — One shared bank, projects separated by tags

**Decision.** Use a single bank, `engineering-global`, with `project:` tags for
scoping, instead of one bank per repository.

**Rationale.** The Hermes memory provider reads exactly one bank and has no
multi-bank query capability. With per-repository banks, Hermes would see one
project rather than the whole history — which contradicts the primary goal in
§1. Tag filtering is supported by both Hermes and the coding-agent integration,
so scoping is preserved without splitting storage. It also gives conversations
that resolve to no project somewhere to live (§15).

**Consequences.** Retrieval has more to sift through as the corpus grows, and we
depart from the official per-repository convention. Coding agents must be
pointed at this bank explicitly rather than using their default. If retrieval
quality degrades, the alternative is per-project banks plus a duplicate write
into a global bank — which costs extraction twice and requires cross-bank
synchronization that is currently out of scope. Because the bank is a
configuration value, that change would not alter the importer.

### ADR-003 — Retain mission is bank configuration

**Decision.** Configure the retain mission on the bank, not per retain call.

**Rationale.** Hindsight exposes the mission through the bank config API and a
server-level environment variable; it is not a per-item field.

**Consequences.** Provisioning becomes an explicit, separate step from
ingestion: the bank must be created and configured before the first import, and
changing the mission is an operation on the bank that affects everything
extracted afterwards. Since banks are created by writes only, the provisioning
call is also what brings the bank into existence.

### ADR-004 — Python as the implementation stack

**Decision.** Implement the system in Python 3.13, as a modular monolith that
calls an external Hindsight instance over HTTP/MCP.

The core is `uv` for dependencies, Typer for the command line, Pydantic v2 for
the domain model and contracts, httpx for HTTP, SQLAlchemy 2 over SQLite for
import state in the MVP and PostgreSQL in production, local storage for the raw
archive in the MVP and S3/MinIO in production, Tenacity for retry, structlog and
OpenTelemetry for observability, pytest with testcontainers for tests, FastAPI
if and when an HTTP surface is needed, and Docker for packaging. The full table
lives in the project constitution, which is where compliance is checked; this
record holds the reasoning.

Module layout mirrors the boundaries of §8 — `ingestion`, `normalization`,
`sanitization`, `classification`, `archive`, `memory/{interface,hindsight}`,
`evaluation`, `observability`, plus `cli` and `api`. Only `memory/hindsight`
knows about Hindsight.

**Rationale.** This is an AI/agent/RAG project, and that ecosystem — memory
engines, rerankers, embedding models, evaluation tooling — appears in Python
first, with reference implementations to match. The work ahead is largely
experimental: different ingestion strategies, classifiers, sanitizers, retrieval
approaches and evaluation sets, each cheap to try and often discarded. Python
lowers the cost of that loop, and it is the shortest path both to Hindsight and
to any replacement for it, which is what makes the exit strategy of ADR-001
real rather than theoretical.

The priority order behind the choice is explicit: time-to-experiment, then
ecosystem access, then replaceability of components, then developer
productivity, then raw throughput. Maximum static typing and enterprise-platform
consistency are not the target — .NET/C#, the original draft's candidate, wins
on those and loses on the ones that matter here.

**Consequences.** Less type safety at compile time, which Principle III of the
constitution compensates for by requiring tests first; Pydantic carries contract
validation at the boundaries instead. Runtime throughput is lower than a
compiled stack would give, which is acceptable because ingestion is bounded by
LLM extraction and network calls, not by local compute. Two storage targets
(SQLite/local now, PostgreSQL/object storage later) must sit behind the same
interfaces from the start, or the migration becomes a rewrite.

If the project later grows into a high-load multi-tenant platform, individual
components can move to Go, .NET or Rust. Ingestion, memory and evaluation stay
in Python: they are where experimentation continues.
