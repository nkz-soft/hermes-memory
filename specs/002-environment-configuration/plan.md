# Implementation Plan: Environment Configuration

**Branch**: `002-environment-configuration` | **Date**: 2026-09-13 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/002-environment-configuration/spec.md`, derived from
GitHub issue #5 (Phase 1, wave 2; depends on #4, merged as PR #33).

## Summary

Give the project exactly one place a configured value comes from: a `Settings` object built on
Pydantic v2 through `pydantic-settings`, populated from `HERMES_`-prefixed environment variables and
an optional untracked `.env`, covering the Hindsight endpoint and credential, the bank id, the
OpenAI-compatible LLM endpoint and credential, the raw archive root and the import-state location.
Credentials are `SecretStr`, so a value cannot reach a log, a `repr` or a serialized payload by
accident. A committed `.env.example` holds names only.

Two ideas in it beyond the obvious assembly. First, the settings live in a top-level module rather
than a package, because the constitution's module tree records the pipeline boundaries and
configuration is not one of them — so no module is invented and no constitution amendment is
implied ([research.md](research.md) R1). Second, the `.env.example` check derives its expectation
from the settings class itself rather than from a re-typed list, the same way 001's layout check
parses the constitution: one record, read rather than duplicated (R5).

## Technical Context

**Language/Version**: Python 3.13, as pinned by the skeleton.

**Primary Dependencies**: `pydantic` and `pydantic-settings` — the project's first runtime
dependencies. Development dependencies unchanged (`pytest`, `ruff`, `pyyaml`).

**Storage**: none. This feature names where the archive and the import state will live; it neither
creates nor opens them (FR-012).

**Testing**: pytest. New suites under `tests/unit/` for the settings themselves and under
`tests/structure/` for the repository-level invariants (`.env` ignored, `.env.example` tracked, no
environment reads outside the settings module).

**Target Platform**: developer machines (Windows, macOS, Linux) and `ubuntu-latest` in CI. Path
handling goes through `pathlib`, and the tests assert resolution rather than a platform's
separator.

**Project Type**: single Python package, `src/` layout, unchanged from 001.

**Performance Goals**: N/A. One load at startup; the relevant budget is that it must be cheap
enough to call in every test, which it is because it touches no network and no disk beyond an
optional `.env` read.

**Constraints**: no network call, no file or directory created (FR-012, SC-007). No credential in
any committed file (Principle V). CI must keep running on fork pull requests, so the new tests must
need no repository secret — they do not; every secret in them is a literal invented in the test.

**Scale/Scope**: 7 settings across 3 models, ~15 checks, 2 runtime dependencies, 2 existing tests
changed on purpose.

## Constitution Check

*GATE: passed before Phase 0 research; re-evaluated after Phase 1 design — see below.*

| Principle | Compliance |
|---|---|
| **I — Raw Archive Is the Source of Truth** | Engaged only as a name. The archive root becomes a configured, resolved location, which is what makes the archive addressable by the feature that writes it. Nothing here reads, writes or derives history, so no second source of truth can arise. The default points inside the ignored `data/` directory, so the archive starts outside version control rather than being moved there later. |
| **II — Provenance and Stable Identity** | Not engaged: no retained item, no `document_id`, no timestamp. The bank id is configuration, not identity, and its default is the one ADR-002 records rather than a value invented here. |
| **III — Test-First (NON-NEGOTIABLE)** | Engaged, and it governs the task order. Every check in [contracts/settings.md](contracts/settings.md) is written before the code that satisfies it and observed to fail. The order that matters most: the four secret-leak assertions (R3) are written against a settings class that does not yet exist, and the fourth — that a load failure's rendered text carries no secret — is what *determines* whether `SecretStr` alone suffices or an explicit guard is needed. That is the constitution's Additional Constraints applied as written: behaviour the design depends on is verified by a test, not assumed from documentation. |
| **IV — Replaceable Boundaries** | Engaged. `Settings` is the seam at which configuration arrives, and [contracts/settings.md](contracts/settings.md) states what consumers may rely on so later features depend on the contract rather than the implementation. It references no Hindsight type, endpoint or vocabulary — only a base URL, a token and a bank id, which are operator facts, and which a replacement memory engine would express the same way. Nesting the Hindsight and LLM groups keeps each replaceable on its own. No module imports `settings` yet, so no dependency direction is established that a later feature must undo. |
| **V — Secrets Never Reach the Memory Engine** | Engaged, and this is the feature's purpose. Credentials come from the environment or an untracked `.env`, never from a repository file — the clause of Principle V that the issue quotes. `.env` is already ignored and `.env.example` already un-ignored by the skeleton's `.gitignore`; a test asserts both rather than trusting the file. Every credential is `SecretStr`, so the "credentials, tokens and authorization headers are never logged" clause becomes a property of the value instead of a rule each future call site must remember. `.env.example` carries names and comments only, asserted by the same parser that checks its agreement with the class. The sanitization half of this principle — redacting secrets out of conversation content — is a different feature and is untouched here. |

**Technology Stack compliance**: Pydantic v2 is the fixed entry for "models and contracts", and
this feature uses it as fixed. `pydantic-settings` is the part of Pydantic v2 that provides
`BaseSettings`, separated at the v1→v2 split for packaging reasons and released by the same project
against the same version line (R2). It displaces nothing and introduces no competing configuration
library, so the constitution's "changing any entry, or adding a dependency that displaces one"
clause is not triggered and no decision record is required. This matches the issue's Governance
impact: "None of the above". The reasoning is recorded here rather than left to be inferred from a
lock file diff.

**Two existing tests change on purpose, in the same commits as the code that requires it**:

- `tests/structure/test_packaging.py::test_no_runtime_dependencies` asserts an empty runtime
  dependency list. Its own docstring says its value "is as a guard, so that the first feature to add
  a runtime dependency has to change this test on purpose rather than slipping one in." This is that
  feature. The test becomes an assertion that the declared runtime dependencies are exactly
  `pydantic` and `pydantic-settings` — still a guard, now with something to guard.
- `tests/structure/test_module_layout.py::test_modules_carry_no_behaviour` asserts every `.py` under
  the package root holds nothing but a docstring. Its docstring likewise anticipates "The first
  feature to write real code changes this test on purpose." Its scope narrows to the recorded module
  tree — the boundaries it was written to keep empty — so it still fails if `archive/` or
  `memory/hindsight/` quietly grows an implementation. It is narrowed, not deleted.

Both changes are called out because a reviewer seeing a weakened assertion should be able to find
the sentence that authorised it.

**The §8 / module-tree conflict raised by 001 is not resolved here**, and this feature does not
depend on it. 001's plan noted that ARCHITECTURE.md §8 lists an *Import state* boundary that the
constitution's module tree has no module for, and left it open for the feature that needs import
state. This feature configures *where* the import state will live without creating the boundary
that owns it, so the conflict is untouched and still awaits the feature that stores something.

**Branch naming**: `002-environment-configuration`, matching the feature directory, per the
Development Workflow section. Created by hand because the `before_specify` hook is not installed
here.

**Post-design re-evaluation**: unchanged, no violations. Phase 1 added one boundary contract, one
data model and no behaviour beyond what the Constitution Check above describes. The design decision
with the most weight — deriving the `.env.example` expectation from the class instead of a second
list — moved towards Principle I's reasoning about single records rather than away from it. The
Complexity Tracking table below stays empty.

## Alternatives Considered

The issue records one rejected alternative; research produced the rest. Full reasoning in
[research.md](research.md).

| Alternative | Rejected because |
|---|---|
| **A configuration file in the repository with secrets injected at runtime** (the issue's alternative) | Principle V — the file is the hazard, not only what is in it today. A tracked configuration file is one convenience commit away from holding a live token, and the commit that does it will look reasonable in review. |
| Amend the constitution's module tree to add a `config` package (R1) | A constitution amendment as a side effect of an implementation feature, which the Governance section forbids and the issue's "None of the above" excludes. A top-level module needs no amendment and is the honest shape: configuration is owned by no boundary. |
| Hand-rolled loading from `os.environ` into a plain `BaseModel` (R2) | Re-implements precedence, `.env` parsing, required/optional handling and error aggregation — four places to be subtly wrong — to avoid a dependency the fixed stack already implies. |
| `python-dotenv` plus a `BaseModel` (R2) | Two dependencies where one suffices, with loading and validation in different places. |
| A plain `str` credential plus a redacting log processor (R3) | Moves the protection from the value to every place that renders it. The places have not been written yet, and one missed call site is a leaked token. |
| A custom secret wrapper instead of `SecretStr` (R3) | Identical behaviour, written and tested by us, and unknown to every other tool in the ecosystem. |
| Unprefixed variable names, or one JSON-valued variable (R4) | Collides in a shared shell; or moves parsing back into our code and destroys per-setting error messages. |
| A hand-written expected name list in the `.env.example` test (R5) | A second source of truth. The check would only prove the two copies matched each other. |
| Generating `.env.example` at build time (R5) | A generated file that a human is nevertheless expected to open and edit. |
| Requiring every setting (R6) | Forces placeholder credentials on operators whose self-hosted instances need none — the habit this feature exists to prevent. |
| Defaulting the Hindsight URL to localhost (R6) | A wrong default silently points a real import at the wrong instance; a startup failure costs a minute. |
| Creating the archive and state directories during load (R7) | A side effect in a call whose entire contract is that it has none (FR-012, SC-007). |

## Project Structure

### Documentation (this feature)

```text
specs/002-environment-configuration/
├── spec.md              # Feature specification
├── plan.md              # This file
├── research.md          # Phase 0 output — R1..R9
├── data-model.md        # Phase 1 output — the settings model
├── quickstart.md        # Phase 1 output — how to validate the deliverable by hand
├── contracts/
│   └── settings.md      # Phase 1 output — the configuration boundary
├── checklists/
│   └── requirements.md  # Specification quality checklist
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
.env.example                       # Committed roster of names, no values
pyproject.toml                     # + pydantic, pydantic-settings under [project] dependencies
uv.lock                            # Re-resolved, committed
README.md                          # + a Configuration section

src/
└── hermes_memory/
    └── settings.py                # Settings, HindsightSettings, LlmSettings, load_settings()

tests/
├── structure/
│   ├── test_packaging.py          # CHANGED: guards the two runtime dependencies
│   ├── test_module_layout.py      # CHANGED: behaviour guard narrowed to the recorded tree
│   └── test_environment_files.py  # NEW: .env ignored, .env.example tracked and credential-free
└── unit/
    ├── __init__.py
    ├── test_settings_loading.py   # required/empty/malformed, precedence, .env present and absent
    ├── test_settings_secrets.py   # the four leak surfaces, and the deliberate accessor
    ├── test_settings_paths.py     # absolute resolution, independent of working directory
    └── test_settings_example.py   # .env.example agrees with the class, both directions
```

**Structure Decision**: the settings are a top-level module, `src/hermes_memory/settings.py`, not a
package (R1). The constitution's module tree records the boundaries of ARCHITECTURE.md §8;
configuration is consumed by all of them and owned by none, so adding a sixteenth package would
misrepresent it and would require amending a binding document. The existing layout check already
skips files whose parent is the package root, so this needs no exception carved into it.

Tests gain a `tests/unit/` sibling to `tests/structure/`, which is the grouping 001's plan named as
arriving with the first feature that has units to test. Repository-level invariants — what version
control tracks, what the example file contains — stay in `tests/structure/`, because that is what
that directory is about.

## Deferred, deliberately

Named so a reviewer can see these were considered rather than forgotten:

- **Reading settings anywhere.** No module imports `settings` in this feature. The CLI, the archive
  and the memory store each wire it in when they exist; doing it now would create dependency
  directions with nothing at the other end.
- **A secret store** — a vault or a cloud secret manager. Principle V permits one; the environment
  is the MVP's mechanism, and `Settings` is the seam another source attaches to (R2, contract).
- **structlog and its redaction processors.** ADR-004 names structlog, and log redaction is worth
  having, but it protects logs only. `SecretStr` protects the value everywhere, and the logging
  feature can add processors on top.
- **Gitleaks**, still deferred from 001. SC-006 is asserted here by this feature's own check over
  `.env.example` rather than by a scanner, so the success criterion does not depend on a tool the
  repository has not adopted.
- **A model name setting for the LLM endpoint.** ARCHITECTURE.md §19.4 records that the model is
  proxy configuration, not something hardcoded here; adding the setting would contradict it.
- **Validating that the configured endpoints respond.** FR-012. It belongs to the features that
  call them.

## Complexity Tracking

> Fill ONLY if Constitution Check has violations that must be justified

No violations. No deviation from the constitution is taken, and no entry in the fixed technology
stack is changed, displaced or added to in a way that requires a decision record. The two existing
tests that change do so under sentences their own authors wrote for that purpose, and both remain
guards afterwards.
