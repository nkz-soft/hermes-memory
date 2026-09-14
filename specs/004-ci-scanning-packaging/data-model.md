# Data Model: Secret Scanning and Image Packaging in CI

**Feature**: `specs/004-ci-scanning-packaging` | **Date**: 2026-09-14

This feature stores nothing and defines no runtime type. What it does define is a small set of
committed declarations that the checks read and that reviewers weigh, and they have a shape worth
writing down — the shape is what checks S5–S8 assert, and it is the difference between an exemption
a reviewer can evaluate and one they must take on trust.

## Exemption

One declared statement that a specific credential-shaped value, at a specific place, is deliberate.
Expressed as one `[[allowlists]]` entry in `.gitleaks.toml`.

| Field | Required | Meaning | Constraint |
|---|---|---|---|
| `description` | yes | Why this value exists and is safe | Non-empty prose; the sentence a reviewer reads |
| `condition` | yes | How the conditions combine | Exactly `"AND"`. The default is OR, which would make `paths` alone sufficient (S6) |
| `targetRules` | yes | Which detection rules this exempts | Non-empty. Exempting all rules is forbidden (S7) |
| `paths` | yes | Which files | Non-empty; each anchored `^…$` and naming a file, never a directory (S8) |
| `regexes` | yes | Which values | Non-empty; matches the specific literal, not a family of them (S7) |

**Validation rule, stated once because it is the whole point**: an exemption is the conjunction of
three independent narrowings. Drop any one and the remaining two still bite. A real credential
pasted into an exempted file is still found, because its value does not match; a real credential of
the exempted value's kind elsewhere is still found, because its path does not match.

**Known instances** (measured in research R4 — five locations, ten occurrences across history):

| Rule | File | Value |
|---|---|---|
| `github-pat` | `tests/unit/test_redaction_canary.py` | The 003 canary token |
| `jwt` | `tests/unit/test_redaction_values.py` | The shape roster's JWT |
| `generic-api-key` | `tests/unit/test_redaction_names.py` | `hs-live-…`, the project's invented token shape |
| `generic-api-key` | `specs/003-logging-telemetry-baseline/quickstart.md` | The same literal, in a worked example |
| `aws-access-token` | `tests/fixtures/secret_scanning/` | The negative control (below) |

## Finding

One reported occurrence, produced by the scanner and consumed by whoever reads the build. Not
persisted by this project.

| Field | Meaning |
|---|---|
| `RuleID` | The kind of credential matched |
| `File`, `Line` | Where it is |
| `Commit` | Which reachable commit it is in — present for a history scan, absent for a tree scan |
| `Fingerprint` | `file:rule:line`, the scanner's identity for the occurrence |
| `Secret`, `Finding` | The matched value and its context — **always redacted** in this project's invocations (S3) |

**State**: a finding has no lifecycle here. There is no triage state, no "acknowledged", no
"accepted". A finding is either a real credential, which is revoked and then removed, or a
deliberate fixture, which becomes an Exemption in a commit a reviewer sees. The absence of a third
state is deliberate: an accepted-findings list is a baseline, and research R5 rejected baselines
because line numbers move and a stale baseline masks new findings.

## Negative control fixture

A committed file that **must** be found, at `tests/fixtures/secret_scanning/`.

| Property | Value |
|---|---|
| Literal | Quoted only in the fixture and in the exemption covering it — never in a specification document, which would otherwise need an exemption to discuss it |
| Matched by | `aws-access-token` |
| Exempted from | The repository scan, by one Exemption scoped to that rule, that path and that value |
| Not exempted from | The negative-control scan, which targets the directory directly and so never reads the root configuration |

**Invariant**: the literal's tail must lie in the base32 alphabet `[A-Z2-7]` — no `0`, `1`, `8` or
`9`. A key violating it is not matched, and the control then proves nothing while appearing to pass
(research R7).

## Image definition

The committed `Dockerfile` and `.dockerignore`.

| Property | Constraint | Checked by |
|---|---|---|
| Runtime interpreter | Agrees with `.python-version` | I2 |
| Dependency installation | `uv sync --locked --no-dev --no-editable` | I3 |
| Entry point | Exec form, the installed console script | I4 |
| Default argument | `["--help"]` | I4 |
| User | Non-root, not returned to root afterwards | I5 |
| Excluded from context | `.git`, `tests/`, `specs/`, `data/` | I6 |

## Check

An entry in the repository's checks contract. This feature adds three — C5, C6, C7 — to the four
that exist. A Check is a command, a pass condition and a fail condition; the set is the same for a
contributor and for CI, which is the property FR-010 and X1 preserve.
