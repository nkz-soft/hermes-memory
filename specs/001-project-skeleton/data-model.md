# Data Model: Project Skeleton

**Feature**: `specs/001-project-skeleton` | **Date**: 2026-09-13

This feature introduces no runtime data and no persistence. The domain model of ARCHITECTURE.md
§7 arrives with the feature that first parses a conversation; nothing here anticipates it.

What follows is the model of the feature's own artifacts — the committed files that carry its
state — because those are what its tests assert against.

## Entities

### Project metadata — `pyproject.toml`

The declaration of the project and its tooling. Single instance, at the repository root.

| Field | Value for this feature | Constraint |
|---|---|---|
| `project.name` | `hermes-memory` | Matches the repository name (R1) |
| `project.requires-python` | `==3.13.*` | Fixed by the constitution's Technology Stack table |
| `project.version` | `0.1.0` | Placeholder; nothing consumes it yet |
| `project.dependencies` | empty | The skeleton adds no runtime dependency (FR-011) |
| dependency group `dev` | `pytest`, `ruff` | The only tools the checks need |
| build backend | one entry, `src/` layout | Makes `src/hermes_memory` the installed package |
| `[tool.ruff]` | line length, target version, rule selection | Single configuration for lint and format |
| `[tool.pytest.ini_options]` | test paths, strict markers, strict config | Keeps a mistyped marker or option an error |

Validation: `uv sync --locked` succeeds, and the declared `requires-python` agrees with
`.python-version`.

### Runtime pin — `.python-version`

One line, `3.13`. Read by `uv` locally and by the CI setup step, so both resolve the same
interpreter (FR-009). Must agree with `project.requires-python`.

### Lock file — `uv.lock`

The exact resolution of the metadata above, committed. Generated, never hand-edited.

Validation: `uv sync --locked` fails if it disagrees with `pyproject.toml`. That failure is the
mechanism behind the spec's second edge case.

### Module

A package directory under `src/hermes_memory/`, one per entry in the recorded module layout.

| Attribute | Description |
|---|---|
| path | Dotted path relative to the package root, e.g. `ingestion.chatgpt`, `memory.interface` |
| `__init__.py` | Present; contains a one-line docstring and nothing else (R4) |
| recorded | Whether the path appears in the constitution's module tree |
| present | Whether the directory exists on disk |

Invariant, asserted by the layout test: `recorded == present` for every path in the union of both
sets. A recorded-but-absent module and a present-but-unrecorded package are both failures.

The recorded set, derived from the constitution's tree:

```text
api            classification   memory
cli            archive          memory.interface
ingestion      evaluation       memory.hindsight
ingestion.chatgpt               normalization
ingestion.claude_code           observability
ingestion.codex                 sanitization
```

Relationship to ARCHITECTURE.md §8: `ingestion.*` realizes the conversation source boundary,
`sanitization` the secret sanitizer, `classification` the project classifier, `archive` the raw
archive, `memory.interface` and `memory.hindsight` the memory store. The import-state boundary of
§8 has no module of its own in the recorded layout and is not invented here — adding one would be
an unrecorded module, and the layout test would reject it.

### Check

A command with a pass/fail outcome, runnable identically by a contributor and by CI. Enumerated in
[`contracts/checks.md`](contracts/checks.md).

| Attribute | Description |
|---|---|
| command | The exact invocation |
| passes when | The condition for exit code 0 |
| runs in CI | All of them do (FR-008) |

## State transitions

None. Every entity above is a committed file whose only transitions are edits under review.
