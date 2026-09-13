# Contract: the project's checks

**Feature**: `specs/001-project-skeleton` | **Date**: 2026-09-13

This feature exposes no HTTP surface and no command-line surface — `cli` and `api` are created
empty, and the Typer application arrives with the feature that has something to run. The only
interface it establishes is the set of checks, which contributors run by hand and CI runs on every
pull request. Both call the same commands, which is what makes a local pass and a CI pass mean the
same thing (FR-009).

## The checks

| # | Command | Passes when | Fails when |
|---|---|---|---|
| C1 | `uv sync --locked` | The environment resolves and installs from `uv.lock` exactly | `uv.lock` disagrees with `pyproject.toml`, or a dependency cannot be installed |
| C2 | `uv run ruff check .` | No lint violation in the repository's own sources | Any violation; nothing is rewritten |
| C3 | `uv run ruff format --check .` | Every source file is already formatted | Any file would be reformatted; nothing is rewritten |
| C4 | `uv run pytest` | The suite runs with zero failures and zero errors | Any failing test, any collection error, or nothing collected (exit 5) |

C4 subsumes the module-layout check of FR-005: it is a test in the suite, not a separate command,
so it runs everywhere the suite runs.

## Guarantees

- **No side effects.** None of the four modifies a tracked file. C2 and C3 report rather than fix;
  the fixing variants (`ruff check --fix`, `ruff format`) exist but are not part of the contract
  and are never what CI runs.
- **No secrets, no network beyond the package index.** Nothing in the set reads a credential,
  contacts Hindsight, or touches `data/`. This is what lets the workflow run unchanged on a pull
  request from a fork.
- **Same runtime everywhere.** All four run under the interpreter pinned by `.python-version`.
- **Order.** C1 first, because the other three run through the environment it installs. C2, C3 and
  C4 are independent of one another.

## Exit codes

Standard POSIX: `0` pass, non-zero fail. The consumer — a contributor's shell, or a CI step — reads
the exit code and nothing else. No check signals failure through its output alone.

## Stability

This contract is additive: a later feature may add a check (a type checker, an import-linter
contract, a container build), and adding one changes the workflow and this table together. Removing
or weakening one is a change to what the repository guarantees about itself and belongs in a pull
request that says so.
