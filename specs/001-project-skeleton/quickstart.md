# Quickstart: validating the project skeleton

**Feature**: `specs/001-project-skeleton` | **Date**: 2026-09-13

How to confirm the feature actually delivers what [`spec.md`](spec.md) promises. Each scenario maps
to success criteria; the commands are the ones in [`contracts/checks.md`](contracts/checks.md).

## Prerequisites

- `uv` installed ([docs.astral.sh/uv](https://docs.astral.sh/uv/)). Nothing else — `uv` provisions
  the Python 3.13 interpreter itself from `.python-version`.
- A clone of the repository on the feature branch. Scenario 1 wants a *fresh* clone, not the
  working directory the implementation happened in.
- No credentials, no Hindsight instance, no history export. None of the checks touch them.

## Scenario 1 — Clean clone to green suite (SC-001, SC-002, SC-003)

```bash
git clone <repository-url> /tmp/skeleton-check
cd /tmp/skeleton-check && git switch 001-project-skeleton
uv sync --locked
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

Expected: `uv sync --locked` installs without re-resolving; `pytest` reports zero failures and zero
errors and exits 0; both `ruff` invocations report no findings and exit 0. No step outside this
block, and no step not written in `README.md`.

## Scenario 2 — The module tree matches the record (SC-004, SC-007)

```bash
uv run pytest -k layout -v
```

Expected: the layout test passes, having read the module tree out of
`.specify/memory/constitution.md` rather than a copy.

Then prove it can fail, in a scratch commit that is thrown away:

```bash
mkdir -p src/hermes_memory/unrecorded && touch src/hermes_memory/unrecorded/__init__.py
uv run pytest -k layout          # expect failure: unrecorded module
rm -rf src/hermes_memory/unrecorded

git mv src/hermes_memory/archive src/hermes_memory/archive_renamed
uv run pytest -k layout          # expect failure: recorded module missing
git mv src/hermes_memory/archive_renamed src/hermes_memory/archive
```

Expected: both runs fail, each naming the specific module. A check that cannot be made to fail has
not been verified.

For SC-007, that the modules carry no behaviour:

```bash
find src/hermes_memory -name '__init__.py' -size +200c
```

Expected: no output. Each `__init__.py` is a single docstring.

## Scenario 3 — The lock file is binding (spec edge case 2)

```bash
uv sync --locked   # passes on the committed tree
# then, without regenerating the lock:
#   add a dependency line to pyproject.toml
uv sync --locked   # expect failure, not a silent re-resolve
git checkout pyproject.toml
```

Expected: the second run fails and says the lock file is out of date.

## Scenario 4 — CI reports on a pull request (SC-005, SC-006)

Open the pull request for this branch and read the checks on it.

Expected: the workflow runs without being triggered by hand, and the pull request shows a completed
pass/fail result.

For SC-006, push a scratch commit that breaks one thing at a time and confirm the check turns red,
then revert it:

- a lint violation — an unused import in any module — must fail C2;
- a test asserting something false must fail C4.

Expected: each is reported as a failing check on the pull request, not a passing one.

## What this quickstart does not cover

The Hindsight contract, the tag convention, the document-id scheme and the sanitizer are all
verified by tests the constitution requires — of the features that introduce them. The skeleton
creates their empty modules and asserts nothing about behaviour that does not yet exist.
