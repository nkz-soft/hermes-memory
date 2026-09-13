# Research: Environment Configuration

Phase 0 output for [plan.md](plan.md). Each entry states the question, the decision, and what was
rejected. Where a claim is about third-party behaviour, it says how the claim is verified — the
constitution's Additional Constraints require behaviour the architecture depends on to be proven by
a test rather than taken from documentation, and that discipline is applied here too.

## R1 — Where does the settings object live?

**Question**: the constitution's module tree records fifteen packages, and
`tests/structure/test_module_layout.py` fails on any package under `src/hermes_memory/` that the
tree does not record. Configuration has no package there. Where does it go?

**Decision**: a single top-level module, `src/hermes_memory/settings.py`, beside
`src/hermes_memory/__init__.py` — not a package.

The layout check derives the present set from `source.parent.relative_to(PACKAGE_ROOT)` and skips
files whose parent *is* the package root. A top-level module is therefore outside what that check
governs, by its existing construction rather than by an exception carved for this feature. This is
also the honest shape of the thing: configuration is consumed by every boundary in
ARCHITECTURE.md §8 and owned by none of them, so giving it a peer package would misrepresent it as
a sixteenth boundary.

**Rejected**:

| Alternative | Rejected because |
|---|---|
| Amend the constitution's module tree to add `config/` | A constitution amendment, which the issue's Governance impact explicitly excludes ("None of the above"). Amending a binding document as a side effect of an implementation feature is exactly what the Governance section forbids. |
| Put settings inside `observability/` or `api/` | Neither owns it. Every module would then import across a boundary that means something else, which is the drift Principle IV exists to prevent. |
| A package `hermes_memory/settings/` with `__init__.py` | Trips `test_no_unrecorded_modules_exist`, correctly. The check is right and the design is wrong, not the other way round. |

**Consequence, stated so it is not a surprise**: `test_modules_carry_no_behaviour` walks *every*
`.py` under the package root, including top-level ones, and asserts each holds nothing but a
docstring. This feature writes the first real code in the package, so that test changes in the same
commit. Its own docstring anticipates this ("The first feature to write real code changes this test
on purpose"). The change narrows its scope to the module tree it was written for; it does not
delete the guard.

## R2 — How are the settings loaded?

**Question**: Pydantic v2 is fixed by the constitution for "models and contracts". Pydantic v2 does
not itself carry `BaseSettings` — it was moved to the separate `pydantic-settings` distribution at
the v1→v2 split. Is using it an addition to the fixed stack?

**Decision**: `pydantic-settings`, providing `BaseSettings` with `SettingsConfigDict`.

It is not a new stack entry. It is the part of Pydantic v2 that does the job the stack table already
assigns to Pydantic, separated for packaging reasons and released by the same project against the
same version line. Nothing is displaced: no other configuration library enters, and the "changing
any entry, or adding a dependency that displaces one" clause of the constitution is not triggered.
The plan records this reasoning rather than letting the extra distribution appear silently in the
lock file.

This feature therefore adds the project's first two runtime dependencies, `pydantic` and
`pydantic-settings`, and changes `tests/structure/test_packaging.py::test_no_runtime_dependencies`
in the same commit — deliberately, which is the whole purpose that guard was written to serve.

**Rejected**:

| Alternative | Rejected because |
|---|---|
| Hand-rolled loading from `os.environ` into a plain `BaseModel` | Re-implements precedence, `.env` parsing, required/optional handling and error aggregation, each a place to get it subtly wrong, to avoid one dependency the stack already implies. |
| `python-dotenv` directly, plus a `BaseModel` | Two dependencies instead of one, and the validation and the loading end up in different places. |
| `os.environ` reads at each call site | Exactly what FR-001 exists to forbid, and what the issue names as the failure mode. |

## R3 — What actually stops a credential from being printed?

**Question**: `SecretStr` is the obvious answer. The claim worth checking is *which* renderings it
covers, because FR-007 names four and a gap in any of them is a live credential in a log.

**Decision**: `pydantic.SecretStr` for every credential field, with the coverage of all four
surfaces asserted by tests rather than assumed:

| Surface | What the test asserts |
|---|---|
| `repr()` of the settings object and of the field | the literal value is absent |
| `str()` of both | the literal value is absent |
| `model_dump()` and `model_dump_json()` with default arguments | the literal value is absent |
| the rendered text of a `ValidationError` raised while loading | the literal value is absent |

The fourth is the one that cannot be taken from documentation. Pydantic's validation errors carry
the offending input, and the question is whether a secret field's input reaches the rendered
message when *that* field fails. The test is written first, against a settings object deliberately
fed a bad value, and it is what tells us whether an explicit guard is needed on top of `SecretStr`.
If it is, the guard is part of this feature; if it is not, the test stays as the regression that
notices a future Pydantic release changing its mind.

**Answered during implementation: `SecretStr` does not cover it, and a guard was needed.** A raw
`ValidationError` renders the input verbatim — `Input should be a valid string [type=string_type,
input_value=12345, input_type=int]` — for a `SecretStr` field as readily as for any other. The
secret type governs how the *model* renders a value it accepted; it has nothing to say about how
the validation machinery reports one it rejected.

Two consequences, both in `load_settings`:

1. A `ValidationError` never escapes. It is caught and re-raised as `SettingsError`, whose message
   is built from `loc`, `msg` and `type` only. The `input` is dropped.
2. The re-raise happens **after** the `except` block, not inside it. `raise ... from None` clears
   `__cause__` but leaves the original hanging off `__context__`, where a logger rendering the
   exception chain finds it — the credential included. Once the handler has exited there is no
   context to attach. `test_the_exception_chain_is_severed` was observed to fail against the
   `from None` version, which is how this was found rather than assumed.

`get_secret_value()` is the deliberate accessor FR-008 requires: obtaining the credential is a
visible act at the call site, which is what makes a review able to see it.

**Rejected**:

| Alternative | Rejected because |
|---|---|
| A plain `str` plus a redacting log processor | Moves the protection from the value to every place that renders it, and the places have not been written yet. A single missed call site is a leaked token. |
| A custom secret wrapper | Same behaviour as `SecretStr`, written by us, tested by us, and unknown to anything else in the ecosystem. |
| Relying on structlog processors (ADR-004 names structlog) | Real and worth having later, but it protects logs only — not `repr` in a debugger, not a serialized payload, not a traceback. |

## R4 — Variable names

**Decision**: a common `HERMES_` prefix on every variable, with nested structure expressed by a
double-underscore delimiter where a group of settings belongs together — for example
`HERMES_HINDSIGHT__BASE_URL`. The prefix keeps the project's variables identifiable in an
environment shared with other tools and makes accidental collisions (a bare `BANK_ID`) impossible.

Grouping the Hindsight settings and the LLM settings into nested models, rather than a flat roster
of eight names, keeps each group replaceable on its own and matches the boundaries of §8. The
delimiter is `pydantic-settings` configuration, not a convention we enforce by hand.

This is a naming decision inside the fixed stack, so it needs no decision record — as the spec's
Assumptions section already states.

**Rejected**: unprefixed names (collide in a shared shell); a single JSON-valued variable (moves
the parsing back into our code and defeats per-setting error messages).

## R5 — Keeping `.env.example` honest

**Question**: FR-010 wants agreement in both directions, and SC-005 wants a scratch change in
either direction to break the check.

**Decision**: the test derives the expected name set from the settings class itself — walking its
fields, including nested models, and composing the same names `pydantic-settings` would read — and
compares it against the variable names parsed out of `.env.example`. Neither side is a re-typed
list.

This is the same idea as `test_module_layout.py` parsing the constitution instead of copying it:
one record, read rather than duplicated. A test that compared two hand-maintained lists would only
prove the two lists matched each other.

The comparison must fail loudly when `.env.example` is missing or parses to nothing, for the same
reason `ModuleTreeError` exists — a check that cannot find what it checks against would otherwise
report green while enforcing nothing.

SC-006 is asserted by the same parser: every name the example file assigns a value to is checked
against the secret fields, and a secret carrying anything but an empty value or a marked
placeholder fails.

**Rejected**: a hand-written expected list in the test (a second source of truth); generating
`.env.example` at build time (a generated file in the repository that a human is nevertheless
expected to read and edit).

## R6 — Which settings are required, and what defaults exist

**Decision**:

| Setting | Required | Default | Why |
|---|---|---|---|
| Hindsight base URL | yes | — | Self-hosted, per operator; no default is correct for everyone, and a wrong default is worse than a startup failure. |
| Hindsight token | no | unset | ARCHITECTURE.md §19.3 targets a self-hosted instance, which may run without authentication. Requiring it would force placeholder credentials — the habit this feature exists to prevent. Secret-typed either way. |
| Bank id | no | `engineering-global` | Fixed by ADR-002 as the single shared bank. It is a recorded project decision, not an operator's choice; overridable for tests. |
| LLM base URL | yes | — | Per operator, same reasoning as the Hindsight URL (§19.4: an existing LiteLLM proxy in this setup). |
| LLM API key | no | unset | A local proxy may accept unauthenticated calls. Secret-typed either way. |
| Raw archive root | no | `data/archive` | `data/` is already ignored and reserved for history by the working agreements. A default that is safe by construction beats a required value everyone sets identically. |
| Import-state location | no | `data/import-state.db` | Same reasoning; `*.db` is already ignored. |

Two required settings is what makes SC-002 meaningful — a roster with none would leave FR-005
untested.

**Rejected**: requiring everything (produces placeholder credentials and a longer first-run
ritual); requiring nothing (FR-005 would have nothing to demonstrate, and a default Hindsight URL
would silently point a real import at the wrong instance).

## R7 — Path handling

**Decision**: filesystem settings are typed as paths and resolved to absolute paths at validation
time, relative to the repository root rather than to the process's working directory (FR-013).

A relative `data/archive` must mean the same directory whether the CLI is run from the repository
root or from a subdirectory; resolving against the working directory would scatter archives. The
repository root is derived from the package's own location, not from `os.getcwd()`.

Validation stops there. The directory is not created and its existence is not asserted — FR-012 and
SC-007 keep this feature free of side effects, and the feature that writes to the archive is the
one that should decide what to do when it is absent.

**Two cases tightened during code review**, both of which had resolved silently to something
wrong:

* A blank value — `HERMES_ARCHIVE_ROOT=` uncommented but not filled in, the likeliest mistake given
  how `.env.example` presents it — resolved to the repository root itself, which would have put the
  raw archive in the checkout and made the import-state path a directory. Blank is now rejected,
  consistent with how a blank bank id is treated.
* A relative path in a deployment that is not a source checkout resolved against whatever
  `parents[2]` happens to be — inside `site-packages` for a non-editable install. It is now
  rejected with a message saying to set an absolute path, which turns a silent wrong answer into a
  startup failure.

**Rejected**: leaving paths as strings (pushes resolution to every consumer); creating the
directories during load (a side effect in a function whose whole contract is that it has none).

## R8 — Precedence and empty values

**Decision**: environment variable over `.env` file over default — the `pydantic-settings` default
ordering, asserted by a test because FR-004 depends on it.

An empty or whitespace-only string for a required setting is rejected as if absent (FR-005,
edge case). `pydantic-settings` treats an empty environment variable as a present empty string,
which would satisfy a plain `str` field; a minimum-length constraint plus stripping is what turns
it back into the loud failure the spec asks for.

A missing `.env` file is normal and silent. An unreadable or malformed one must raise rather than
be skipped, so that a typo in the file is not indistinguishable from the file being absent.

## R9 — Documentation

**Decision**: the README gains a short configuration section naming the example file, the copy
step, and the two required variables. `docs/` gains nothing: there is no workflow here to describe
beyond those three facts, and the 001 precedent puts contributor-facing commands in the README.
