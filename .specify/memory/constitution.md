# hermes-memory Constitution

## Core Principles

### I. Raw Archive Is the Source of Truth

Every imported conversation MUST be persisted in the raw archive — original form
and normalized form — independently of Hindsight, before or alongside the
`retain` call. No conversation may exist only as extracted memory.

Ingestion MUST be re-runnable end to end from the raw archive alone, without
requesting a new export from ChatGPT, Claude or any other source service.

Rationale: `retain` is lossy extraction. Keeping the originals is what allows the
retain mission, the extractor model, the parser, the redaction rules or Hindsight
itself to change later without losing history (ARCHITECTURE.md §3.1, ADR-001
exit strategy).

### II. Provenance and Stable Identity

Every retained item MUST carry provenance metadata — source, source id, original
timestamp, project, repository when known, and importer version — and the tags
defined by the tag convention (ARCHITECTURE.md §6).

`document_id` MUST be derived deterministically from the source and its native
identifier (`chatgpt:{conversation-id}` and equivalents) and MUST be stable
across runs. Generating an identifier per import run is forbidden.

`timestamp` MUST be the conversation's real time. The import time MUST NOT be
used in its place.

Re-importing unchanged content MUST NOT create duplicates and MUST NOT pay for
extraction twice: the importer skips by source id plus content hash, and relies
on `document_id` upsert plus `operation_id` on the Hindsight side.

Rationale: identity and time are what make temporal retrieval work, and what
keep a second import run from corrupting the bank (§§3.3, 10, 11, 17).

### III. Test-First (NON-NEGOTIABLE)

Tests are written before the implementation, MUST fail first, and only then is
the code written to make them pass. Red → green → refactor, per change, no
exceptions for "obvious" code.

Minimum coverage that MUST exist before a pipeline stage is considered done:
unit tests for the source parser and the secret sanitizer against realistic
fixtures; contract tests for every boundary in §8; an end-to-end test that
imports a conversation and recalls a fact from it.

A bug fix starts with a failing test that reproduces the bug.

Rationale: export parsing and secret redaction fail silently — a missed field or
an unredacted token is invisible until the damage is already in the bank.

### IV. Replaceable Boundaries

Each boundary listed in ARCHITECTURE.md §8 MUST be an interface with a single
responsibility. The domain model and the ingestion pipeline MUST NOT reference
Hindsight, its types, its endpoints or its vocabulary; only the memory store
implementation may.

The same applies to the raw archive, the import-state store and the LLM
endpoint: each is reached through an interface, so local storage, an
OpenAI-compatible proxy or the memory engine itself can be swapped without
touching ingestion.

Pipeline stages (parse → normalize → sanitize → classify → enrich) MUST be
independently testable and composable, and the pipeline MUST run conversation by
conversation so that one failure cannot abort a run.

Rationale: the dependency on Hindsight is deliberate but not permanent; the
architecture only survives it if the dependency stays in one place (ADR-001).

### V. Secrets Never Reach the Memory Engine

Sanitization runs before any content leaves the process for Hindsight. The
minimum redaction categories of §13 MUST be covered, and a redaction MUST
replace the secret value while preserving the surrounding context rather than
dropping the enclosing text.

Credentials MUST come from environment variables or a secret store, never from
files in the repository. Conversation contents are not logged by default;
credentials, tokens and authorization headers are never logged.

Hindsight MUST be a self-hosted instance, and the raw archive stays on local
storage under the user's control.

Rationale: the corpus is years of private engineering history; a leaked token
inside it is a live credential, and once extracted it is replicated across facts
and the graph.

## Technology Stack

The implementation stack is fixed. It is chosen to optimise, in this order:

```text
time-to-experiment > ecosystem access > replaceability of components >
developer productivity > raw throughput
```

Maximum static typing and enterprise-platform consistency are explicitly not the
optimisation target. The project's near-term question is whether engineering
memory works on real history and which retrieval patterns carry value, and the
stack is selected to answer that question cheaply.

| Area | Choice |
|---|---|
| Runtime | Python 3.13 |
| Dependency management | uv |
| API | FastAPI |
| CLI | Typer |
| Models and contracts | Pydantic v2 |
| HTTP client | httpx |
| Database access | SQLAlchemy 2 |
| Import-state store (MVP) | SQLite |
| Metadata database (production) | PostgreSQL |
| Raw archive (production) | S3 / MinIO |
| Memory engine | Hindsight |
| Retry | Tenacity |
| Logging | structlog |
| Telemetry | OpenTelemetry |
| Tests | pytest |
| Integration tests | testcontainers-python |
| Secret scanning | Gitleaks, plus the project's own sanitizer |
| Packaging | Docker |

Rationale: the project lives in the AI/agent/RAG domain, where new libraries,
reference implementations and evaluation tooling appear in Python first, and
where Hindsight and any replacement memory engine are reached most directly from
Python. Ingestion, memory and evaluation remain Python even if a component is
later moved to another runtime for load or latency reasons.

The MVP runs on SQLite and local archive storage; PostgreSQL and S3/MinIO are
the production targets behind the same interfaces required by Principle IV, and
adopting them MUST NOT change ingestion code. FastAPI is the choice for an HTTP
surface when one is introduced — it is not a mandate to build one; the MVP is
driven by the Typer CLI.

The system is a modular monolith with Hindsight as an external service reached
over HTTP/MCP. Microservices are not introduced for the MVP. Module layout:

```text
engineering-memory
├── api
├── cli
├── ingestion
│   ├── chatgpt
│   ├── claude_code
│   └── codex
├── normalization
├── sanitization
├── classification
├── archive
├── memory
│   ├── interface
│   └── hindsight
├── evaluation
└── observability
```

The boundaries of Principle IV map onto these modules: `memory/hindsight` is the
only module permitted to know about Hindsight, and `memory/interface` is what
every other module depends on.

## Additional Constraints

The memory bank is a single shared bank, `engineering-global`; scoping is by
`project:` tags, never by creating a bank per consumer or per repository
(ADR-002). The bank MUST be provisioned and its retain mission configured as an
explicit step before the first import (ADR-003).

Behaviour the architecture depends on — the Hindsight contract in §9, the tag
convention in §6, the document-id scheme in §10 — MUST be verified against the
running instance by a test, not assumed from documentation.

The stack in the Technology Stack section above is the decision recorded as
ADR-004 in ARCHITECTURE.md §23; that record holds its rationale, this one holds
the enforceable list. Changing any entry, or adding a dependency that displaces
one, requires a new decision record — not a commit that quietly introduces it.

## Development Workflow

Work is spec-driven through Spec Kit: `/speckit-specify` → `/speckit-plan` →
`/speckit-tasks` → `/speckit-implement`, with the spec and plan committed
alongside the code they produce.

Every plan MUST state how the change complies with these principles, and MUST
justify any deviation in writing. A deviation that cannot be justified is a
reason to change the design, not the principle.

Each new history source (Claude chats, Claude Code, Codex, Hermes) is separate
work with its own specification and its own decision record. Nothing may assume
a source that has not been added this way.

All files in the repository — documentation, code, comments, commit messages —
are written in English.

## Governance

This constitution supersedes other conventions and preferences for this
repository. Where it conflicts with ARCHITECTURE.md, the conflict is a defect:
one of the two documents MUST be amended rather than silently ignored.

Amendments are made by editing this file in a pull request that states the
rationale and bumps the version. Versioning is semantic: MAJOR for removing or
redefining a principle in a backward-incompatible way, MINOR for adding a
principle or materially expanding guidance, PATCH for clarifications and
wording.

Compliance is reviewed at two gates: when a plan is produced, against the
principles above; and before a branch is merged, against the tests the plan
promised. Reviewers MUST reject work that adds a second source of truth for
history, an unstable document id, an unsanitized path to Hindsight, or a
Hindsight reference outside the memory store.

**Version**: 1.1.0 | **Ratified**: 2026-09-12 | **Last Amended**: 2026-09-12
