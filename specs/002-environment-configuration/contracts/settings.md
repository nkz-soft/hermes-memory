# Contract: the configuration boundary

Phase 1 output for [plan.md](plan.md). ARCHITECTURE.md §8 lists six boundaries; configuration is
not one of them, but it is what every one of them will be handed. This file states what a consumer
may rely on, so that later features depend on the contract and not on the implementation.

## What this boundary offers

**One entry point.** A single call returns a validated `Settings`. It either returns a fully valid
object or raises; it never returns a partially populated one.

**Failure before work.** The call is made once, at startup, before anything else happens. Every
fault in the environment is reported together, each naming its setting (FR-005, FR-006).

**No side effects.** The call performs no network request and creates no file or directory
(FR-012). It is safe to make in a test, in a dry run, and in `--help`.

**Credentials that do not leak.** Every credential is a secret-typed value. Its content is absent
from `repr`, `str`, default serialization and load-failure text (FR-007). A consumer that needs the
value asks for it explicitly (FR-008) — and that call is visible in review.

**Absolute paths.** Filesystem settings arrive resolved, so the same configuration means the same
location regardless of where the process was started (FR-013). Their targets are not created and
their existence is not asserted; the feature that stores something decides that.

## What consumers must not do

| Forbidden | Why |
|---|---|
| Read the environment directly | FR-001, SC-008. The single source is the point of the feature. |
| Construct `Settings` field by field in production code | Bypasses validation and precedence. Tests may construct one explicitly; that is what makes them tests. |
| Log, format or serialize a credential's unwrapped value | Principle V. The secret type makes the accident impossible and the deliberate act visible. |
| Treat a configured path as existing | Loading does not create or check it. |
| Mutate settings after load | The object is immutable; a run is configured once. |

## Stability

Additive change — a new setting with a default — is a normal change and breaks no consumer. It
must arrive with its entry in `.env.example`, which the check in this feature enforces in both
directions (FR-010).

Making an existing setting required, renaming one, or changing a default is a breaking change for
every operator's environment. It belongs in a change that says so in its pull request body, not in
a commit that happens to touch the settings module.

Adding a *source* of settings — a secret store, a configuration server — attaches here and nowhere
else, which is the reason this is a boundary at all.

## Checks that hold this contract

| Check | Guarantees |
|---|---|
| Required-setting removal, one at a time | FR-005, SC-002 |
| Empty and whitespace-only values for required settings | FR-005, edge case |
| Malformed URL, empty bank id | FR-006 |
| Several faults at once | FR-005 (all reported, not the first) |
| Environment overrides `.env`; `.env` overrides default | FR-004, FR-003 |
| Missing `.env` loads; malformed `.env` raises naming the line | FR-003, edge case |
| Unreadable or undecodable `.env` raises `SettingsError`, not a raw decode error | FR-003, edge case |
| A blank path setting is rejected, never resolved to the repository root | FR-005, FR-013 |
| A relative path outside a source checkout is rejected rather than guessed | FR-013 |
| Secret absent from `repr`, `str`, `model_dump`, `model_dump_json`, load-failure text | FR-007, SC-003 |
| A validator's own message cannot carry the value into the failure | FR-007, SC-003 |
| The raised failure has no `__cause__` and no `__context__` | FR-007, SC-003 |
| `get_secret_value()` returns the value | FR-008 |
| Every credential field is secret-typed, including through `Annotated` | FR-007 |
| `.env.example` names exactly the declared settings, both directions | FR-010, SC-004, SC-005 |
| `.env.example` assigns no usable credential, `export NAME=value` included | SC-006 |
| A line the example-file parser cannot classify fails rather than being skipped | SC-006 |
| `.env` ignored and `.env.example` tracked by version control | FR-011 |
| No module outside the settings module reads the environment, or declares settings of its own | FR-001, SC-008 |
| Loading opens no socket and creates no path | FR-012, SC-007 |
| Relative path settings resolve identically from any working directory | FR-013 |

These are additive, like the checks contract of 001: a later feature adds rows, and removing one is
a deliberate act that its pull request has to justify.
