# Quickstart: validating the scanning and packaging checks

**Feature**: `specs/004-ci-scanning-packaging` | **Date**: 2026-09-14

Every command here was run during planning against this repository, and the outputs quoted are the
ones observed. Reproducing them is how the deliverable is validated by hand.

## Prerequisites

- A container runtime. C5, C6 and C7 need one; C1–C4 do not
  ([contracts/checks.md](contracts/checks.md)).
- A **full** clone. A shallow one makes the history scan pass over a single commit, which is the
  one way this check fails open.

## C5 — scan the history

The invocation is the same one CI runs. Three parts carry weight: `-v` so a finding names its file,
line and rule; `--redact` so the value never reaches a public build log; and the `GIT_CONFIG_*`
trio, which exempts the bind-mounted repository from git's ownership check — without it the scanner
can report zero findings on a repository it never read (research R3).

```bash
docker run --rm \
  -v "$PWD:/repo" -w /repo \
  -e GIT_CONFIG_COUNT=1 -e GIT_CONFIG_KEY_0=safe.directory -e GIT_CONFIG_VALUE_0='*' \
  ghcr.io/gitleaks/gitleaks:v8.30.1 git . --no-banner --redact -v
```

In PowerShell, substitute `${PWD}` for `$PWD` and drop the line continuations.

Expected, once the exemptions are committed:

```text
INF 33 commits scanned.
INF scanned ~1369809 bytes (1.37 MB) in 2.79s
INF no leaks found
```

Exit status 0. Against the repository **before** this feature's `.gitleaks.toml` exists, the same
command reports `leaks found: 10` and exits 1 — the ten occurrences of the five deliberate fixtures
enumerated in [data-model.md](data-model.md). Running it in that order is worth doing once: it is
the only way to see that the exemptions are load-bearing rather than decorative.

## The negative control — prove the scan can fail

A check never observed failing is not known to work. This scans the committed fixture directory
directly, which contains no configuration of its own and therefore runs against the default rules,
exemptions and all bypassed.

```bash
docker run --rm -v "$PWD:/repo" -w /repo \
  ghcr.io/gitleaks/gitleaks:v8.30.1 dir tests/fixtures/secret_scanning \
  --no-banner --redact -v
```

Expected — a finding, and **exit status 1**:

```text
Finding:     aws_access_key_id = REDACTED
Secret:      REDACTED
RuleID:      aws-access-token
File:        leaky_config.ini
Line:        1
Fingerprint: leaky_config.ini:aws-access-token:1

WRN leaks found: 1
```

If this exits 0, the scanning check is not working, whatever C5 reported. The most likely cause is
an edited fixture literal: the rule's tail is base32, so a key containing `0`, `1`, `8` or `9` is
not matched (research R7).

## C6 — build the image

```bash
docker build -t hermes-memory:local .
```

Expected: a successful build. It fails, by design, when `uv.lock` disagrees with `pyproject.toml` —
`--locked` inside the build refuses to re-resolve, so the image can never ship a dependency set the
tests did not run against.

## C7 — run it

```bash
docker run --rm hermes-memory:local
```

Expected: the application's usage text, and exit status 0. No arguments are needed because `--help`
is the image's default argument (research R10); the entry point is the installed console script, so
arguments given instead reach the application directly:

```bash
docker run --rm hermes-memory:local --version
```

Assert on the **text**, not the status. An entry point that exits 0 having printed nothing satisfies
a status check and fails the thing this check exists for — which is why check I8 requires the
workflow to match the output's content.

## Confirming what the image does not contain

```bash
docker run --rm --entrypoint sh hermes-memory:local -c 'ls /app/tests 2>&1; python -c "import pytest" 2>&1; id -u'
```

Expected: no such directory, a `ModuleNotFoundError` for pytest, and a non-zero uid. Those are
SC-007 and SC-008 — no tests and no development dependencies in the image, and not running as root.

## The rest of the suite

Unchanged, and still the first thing to run:

```bash
uv sync --locked && uv run ruff check . && uv run ruff format --check . && uv run pytest
```

The structure tests added by this feature (S1–S10, I1–I9, P1–P4) run inside that `pytest` and need
no container runtime: they read the committed workflow, `Dockerfile` and `.gitleaks.toml` rather
than executing them.
