# Data Model: Environment Configuration

Phase 1 output for [plan.md](plan.md). This feature's data is its configuration, so the model is
the settings object and nothing else. No persistence, no schema, no migration.

## Entities

### `Settings`

The single typed collection the whole project reads configuration from (FR-001). Loaded once,
validated as a whole, and immutable thereafter.

| Field | Type | Required | Default | Notes |
|---|---|---|---|---|
| `hindsight` | `HindsightSettings` | — | — | Nested group |
| `llm` | `LlmSettings` | — | — | Nested group |
| `archive_root` | absolute path | no | `<repo>/data/archive` | Resolved, never created (R7) |
| `import_state_path` | absolute path | no | `<repo>/data/import-state.db` | Resolved, never created (R7) |

Sources, in precedence order (R8): environment variable → `.env` → declared default.

Environment names carry the `HERMES_` prefix, with `__` separating a group from its field (R4):

```text
HERMES_HINDSIGHT__BASE_URL
HERMES_HINDSIGHT__TOKEN
HERMES_HINDSIGHT__BANK_ID
HERMES_LLM__BASE_URL
HERMES_LLM__API_KEY
HERMES_ARCHIVE_ROOT
HERMES_IMPORT_STATE_PATH
```

### `HindsightSettings`

| Field | Type | Required | Default | Notes |
|---|---|---|---|---|
| `base_url` | URL | **yes** | — | The self-hosted instance (§19.3) |
| `token` | secret | no | unset | Secret-typed whether set or not (R3, R6) |
| `bank_id` | non-empty string | no | `engineering-global` | Fixed by ADR-002; overridable for tests |

### `LlmSettings`

| Field | Type | Required | Default | Notes |
|---|---|---|---|---|
| `base_url` | URL | **yes** | — | OpenAI-compatible endpoint (§19.4) |
| `api_key` | secret | no | unset | Secret-typed whether set or not |

No model name field: §19.4 records that the actual model is proxy configuration rather than
anything hardcoded here, and inventing a setting for it now would contradict that.

## Validation rules

| Rule | Applies to | Failure mode |
|---|---|---|
| Present and non-empty after stripping | every required field | Load fails naming the field (FR-005) |
| Parses as a URL with a scheme and host | both `base_url` fields | Load fails naming the field (FR-006) |
| Non-empty after stripping | `bank_id` | Load fails naming the field |
| Resolved to an absolute path against the repository root | both path fields | — (FR-013) |
| All failures collected, not the first only | the whole object | One error listing every fault (FR-005) |
| Unrelated environment variables ignored | the whole object | — |

## Invariants

- **Nothing outside `Settings` reads the environment** (FR-001, SC-008). The invariant is checked
  by a test over the committed tree, not by convention.
- **A secret's value appears in no default rendering** (FR-007, SC-003): `repr`, `str`,
  `model_dump`, `model_dump_json`, and the rendered text of a load failure.
- **Loading has no side effects** (FR-012, SC-007): no network call, no file or directory created.
- **`.env.example` and the declared fields name the same set** (FR-010, SC-004), derived from the
  class rather than re-typed (R5).

## Non-entities

Named so their absence is visible as a decision:

- No secret-store client, no cached credential, no token refresh. Principle V permits a secret
  store; the environment is the MVP's mechanism and `Settings` is the seam where another source
  would attach.
- No connection, client or session object. Those belong to the features that talk to Hindsight and
  to the LLM endpoint.
- No mutable or reloadable configuration. A run is configured at startup; changing a setting means
  starting again.
