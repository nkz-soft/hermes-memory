# Feature Specification: Environment Configuration

**Feature Branch**: `002-environment-configuration`

**Created**: 2026-09-13

**Status**: Draft

**Input**: GitHub issue #5 — "Load configuration and credentials from the environment". Phase 1,
wave 2. Depends on #4.

## User Scenarios & Testing *(mandatory)*

The users of this feature are the contributors and operators who run this project against their own
Hindsight instance, their own LLM proxy and their own history archive — and every later component
that needs to know where those are. The value delivered is that there is exactly one place a
setting comes from, and that a credential can never be the thing that makes the repository unsafe
to publish.

### User Story 1 - An operator configures the project without touching a repository file (Priority: P1)

Someone preparing to run an import has a Hindsight instance, a token for it and an
OpenAI-compatible LLM endpoint. They copy the committed example file to an untracked local file,
fill in their own values, and the project reads them. Nothing they filled in is tracked by version
control, and no file they had to edit lives in the repository.

**Why this priority**: this is the reason the issue exists. Principle V forbids credentials in
repository files; without a defined loading path the first convenience commit puts a token in one.
This story is the smallest slice that already delivers value on its own.

**Independent Test**: starting from a clean clone with the required values present in the
environment, the settings can be loaded and every value read back matches what was supplied.

**Acceptance Scenarios**:

1. **Given** every required value is present as an environment variable, **When** the settings are
   loaded, **Then** loading succeeds and each value is readable through the settings object.
2. **Given** the required values are absent from the environment but present in an untracked local
   environment file, **When** the settings are loaded, **Then** loading succeeds with the values
   from that file.
3. **Given** a value is present both as an environment variable and in the local environment file,
   **When** the settings are loaded, **Then** the environment variable wins, so a one-off override
   does not require editing a file.
4. **Given** no local environment file exists at all, **When** the settings are loaded with every
   required value in the environment, **Then** loading succeeds — the file is optional, not a
   prerequisite.
5. **Given** the repository as committed, **When** version control is asked what it tracks, **Then**
   the example file is tracked and any filled-in local environment file is ignored.

---

### User Story 2 - A missing or malformed setting fails at startup, not mid-import (Priority: P1)

Someone starts an import having forgotten one variable. The run stops immediately with a message
naming what is missing, rather than beginning work and failing partway through against a corrupted
or half-written state.

**Why this priority**: equal in importance to Story 1 and independently testable. A configuration
error discovered after the first `retain` call has already cost money and written to the bank; an
error discovered at startup has cost nothing.

**Independent Test**: remove one required value from an otherwise complete environment, attempt to
load the settings, and observe a failure that names the missing setting.

**Acceptance Scenarios**:

1. **Given** exactly one required value is missing, **When** the settings are loaded, **Then**
   loading fails, and the failure names the missing setting.
2. **Given** a required value is present but empty, **When** the settings are loaded, **Then**
   loading fails in the same way as if it were absent — an empty credential is not a credential.
3. **Given** a value is present but not of the expected shape, **When** the settings are loaded,
   **Then** loading fails and the failure names the offending setting.
4. **Given** several required values are missing at once, **When** the settings are loaded,
   **Then** the failure reports all of them, not only the first.
5. **Given** the environment carries unrelated variables, **When** the settings are loaded,
   **Then** they are ignored and loading succeeds.

---

### User Story 3 - A credential cannot be printed, logged or serialized by accident (Priority: P1)

A contributor debugging an import prints the settings, or a structured log line, or reads a stack
trace from a failed request. The tokens are not in any of it. Nobody had to remember to redact
them at the call site.

**Why this priority**: Principle V's rationale applies to the credentials themselves, not only to
conversation content — this corpus is private and the repository is public. The protection has to
be a property of the value, because the call sites that could leak it have not been written yet.

**Independent Test**: construct the settings with a known secret value, render the object and each
secret field the ways a program renders things, and assert the literal value appears in none of
them.

**Acceptance Scenarios**:

1. **Given** loaded settings holding a secret, **When** the settings object is rendered for
   display or debugging, **Then** the secret's value does not appear in the output.
2. **Given** loaded settings holding a secret, **When** an individual secret field is rendered the
   same way, **Then** its value does not appear either.
3. **Given** loaded settings holding a secret, **When** the settings are serialized to a data
   format by default, **Then** the secret's value is not present in the result.
4. **Given** a value that fails validation, **When** the resulting failure is rendered, **Then** a
   secret value does not appear in the message.
5. **Given** a component that legitimately needs the credential, **When** it asks for the value
   explicitly, **Then** it receives it — the protection guards accidents, not intended use.

---

### User Story 4 - The example file cannot drift from what the project actually reads (Priority: P2)

A later feature adds a setting. The committed example file stops describing reality, and the next
operator configures from it and still gets a startup failure. An automated check catches the
divergence before that happens.

**Why this priority**: valuable but derivative — Stories 1 to 3 already give a working, safe
configuration path. This one keeps it working as the project grows.

**Independent Test**: compare the example file against the settings the project declares; add a
setting without updating the file and observe the check fail.

**Acceptance Scenarios**:

1. **Given** the repository as committed, **When** the example file is compared to the declared
   settings, **Then** every declared setting appears in the file and the file names nothing the
   project does not read.
2. **Given** a setting is added to the project without being added to the example file, **When**
   the check runs, **Then** it fails and names the setting that is missing from the file.
3. **Given** the example file as committed, **When** it is inspected, **Then** it carries variable
   names and explanatory text only, and no value that could function as a credential.

---

### Edge Cases

- A required variable is present but set to the empty string, or to whitespace only — treated as
  absent rather than as a valid value.
- Both an environment variable and the local environment file define the same setting — precedence
  is defined rather than incidental.
- The local environment file is absent, unreadable, or malformed — absent is normal; unreadable or
  malformed must fail loudly rather than silently yield no settings.
- A filesystem location is given as a relative path — it must resolve to the same place regardless
  of the working directory the command was started from.
- A filesystem location names a directory that does not exist yet — this feature reports the
  configured location; it does not create or validate storage on behalf of a later feature.
- A secret value appears inside a validation failure message produced by the validation machinery
  itself, not by our code.
- The example file exists but is empty, or the check that compares it cannot locate it — the check
  must fail rather than pass on an empty comparison.
- The Hindsight instance, the LLM endpoint or the archive location named by the settings is wrong
  or unreachable — this feature does not contact any of them; it loads and validates shape only.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The project MUST expose a single typed settings object as the only source of
  configuration; no component may read the environment directly.
- **FR-002**: The settings MUST cover the Hindsight endpoint, the Hindsight credential, the memory
  bank identifier, the OpenAI-compatible LLM endpoint and its credential, the raw archive root and
  the import-state location.
- **FR-003**: Settings MUST be populated from environment variables, and from an optional local
  environment file that is not tracked by version control.
- **FR-004**: An environment variable MUST take precedence over the same setting in the local
  environment file.
- **FR-005**: A missing or empty required setting MUST cause loading to fail immediately, with a
  message naming every setting at fault, before any other work begins.
- **FR-006**: A setting whose value does not match its declared type or shape MUST cause loading to
  fail in the same way.
- **FR-007**: Every credential MUST be held in a type whose default rendering — display,
  debugging, serialization and validation failure messages — does not reveal the value.
- **FR-008**: The credential's real value MUST remain obtainable through an explicit, deliberate
  accessor, so legitimate use is possible and accidental exposure is not.
- **FR-009**: The repository MUST commit an example environment file listing every setting the
  project declares, by name, with explanatory text and no usable credential value.
- **FR-010**: An automated check MUST verify that the example file and the declared settings agree
  in both directions, and MUST fail when either names something the other does not.
- **FR-011**: Version control MUST ignore the local environment file and MUST track the example
  file.
- **FR-012**: This feature MUST NOT contact Hindsight, the LLM endpoint or any storage location; it
  loads, validates and exposes configuration and nothing else.
- **FR-013**: Filesystem locations MUST resolve to absolute paths, so the same configuration means
  the same location regardless of the working directory.
- **FR-014**: Settings not required for a run MUST carry a documented default where a correct one
  exists, so an operator supplies only what is genuinely theirs to choose.

### Key Entities

- **Settings object**: the single typed collection of every value the project reads from its
  environment, validated as a whole at load time.
- **Setting**: one named value with a type, a description, and either a default or the status of
  being required.
- **Secret setting**: a setting whose value is a credential, distinguished by a type that withholds
  it from every default rendering.
- **Local environment file**: the untracked, optional file an operator fills in with their own
  values.
- **Example environment file**: the committed, credential-free roster of setting names that tells
  an operator what the project reads.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An operator starting from a clean clone reaches loaded settings using only the
  committed example file and the repository's documentation, with no undocumented step.
- **SC-002**: For each required setting, removing it alone from an otherwise complete environment
  causes loading to fail with a message naming that setting — 100% of required settings, not a
  sample.
- **SC-003**: For each secret setting, the literal value appears in zero of the renderings a
  program produces by default: display, debugging, default serialization, and validation failure
  messages.
- **SC-004**: 100% of the settings the project declares are listed in the example environment file,
  and the file lists nothing the project does not read.
- **SC-005**: A deliberate scratch change that adds a setting without updating the example file
  makes the check fail; the same for a removal.
- **SC-006**: The committed example file contains zero values capable of authenticating against
  anything: every secret setting it names is left unassigned or carries an obvious placeholder, and
  an automated check asserts it.
- **SC-007**: Loading the settings performs zero network calls and creates zero files or
  directories.
- **SC-008**: Zero components outside the settings object read configuration from the environment,
  verified against the committed tree.

## Assumptions

- The technology is not an open question here. The constitution's Technology Stack section fixes
  Pydantic v2 for models and contracts, and the issue names it; this specification states outcomes
  so the checks stay verifiable, and the plan states how they are met.
- The variable naming scheme — in particular a common prefix — is a planning decision within the
  stack already fixed, not a change to it, and therefore needs no decision record.
- The memory bank identifier defaults to the single shared bank fixed by ADR-002 rather than being
  required, because it is a recorded project decision and not an operator's choice.
- The Hindsight credential and the LLM credential are treated as optional secrets: the MVP targets
  a self-hosted Hindsight instance and a local OpenAI-compatible proxy (ARCHITECTURE.md §19.3,
  §19.4), either of which may legitimately run without authentication. Requiring them would force
  operators to invent placeholder values, which is the habit this feature exists to prevent. They
  remain secret-typed whether or not they are set.
- The raw archive root and the import-state location default to paths under the repository's
  ignored `data/` directory, which the constitution's handling of history data already reserves.
- Secret-store integration — a vault, a cloud secret manager — is out of scope. Principle V permits
  "environment variables or a secret store"; the environment is the mechanism for the MVP, and the
  settings object is the seam at which another source could later be added.
- Validating that the configured endpoints exist, respond or authenticate belongs to the features
  that call them. This feature's contract ends at a validated, in-memory settings object.
- The on-disk home of the settings object within the source tree is a planning decision. The
  constitution's module tree records the pipeline boundaries; configuration is consumed by all of
  them and owned by none, so this feature does not add a module to that tree and no constitution
  amendment is implied.
- This feature introduces the project's first runtime dependency. The skeleton's guard test against
  runtime dependencies exists to make that a deliberate act, and this feature changes it on
  purpose, in the same commit.
