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
| C5 | `gitleaks git .` over the full history, pinned, with `-v --redact` | The history contains no credential outside the exemptions committed in `.gitleaks.toml` | Any finding, in any reachable commit |
| C6 | `docker build` of the repository's `Dockerfile` | The image builds from the pinned interpreter and the committed lock file | Any build failure, including a lock file that disagrees with `pyproject.toml` |
| C7 | `docker run` of the built image, with its output asserted | The command-line application's usage text is printed and the container exits 0 | No usage text, a non-zero exit, or an image that cannot start the application |

C4 subsumes the module-layout check of FR-005: it is a test in the suite, not a separate command,
so it runs everywhere the suite runs.

C5, C6 and C7 were added by `004-ci-scanning-packaging`, exercising the stability clause below. Their
exact invocations are in `specs/004-ci-scanning-packaging/quickstart.md`, in the single form both a
contributor and CI use — CI does not paraphrase them.

**C5, C6 and C7 need a container runtime; C1–C4 need only uv.** This is stated rather than assumed:
a contributor without one can run the first four and relies on CI for the rest, and should not
conclude from a local pass that all seven passed. No non-container fallback exists on purpose — a
second way of running a check produces a second verdict, and only one of them would be CI's.

## Guarantees

- **No side effects.** None of the seven modifies a tracked file. C2 and C3 report rather than fix;
  the fixing variants (`ruff check --fix`, `ruff format`) exist but are not part of the contract
  and are never what CI runs. C5 writes no report; C6 and C7 leave an image in the local container
  daemon and nothing in the tree.
- **No secrets, no network beyond the package index and the pinned scanner image.** Nothing in the
  set reads a credential, contacts Hindsight, or touches `data/`. C6 and C7 push nothing to any
  registry. This is what lets the workflow run unchanged on a pull request from a fork.
- **Same runtime everywhere.** C1–C4 run under the interpreter pinned by `.python-version`, and C6
  builds the image on that same pin — a test asserts the two still agree.
- **Order.** C1 first, because C2, C3 and C4 run through the environment it installs. C2, C3 and C4
  are independent of one another. C5 is independent of all of them. C7 depends on C6, which built
  the image it runs.

## Exit codes

Standard POSIX: `0` pass, non-zero fail. The consumer — a contributor's shell, or a CI step — reads
the exit code and nothing else. No check signals failure through its output alone.

## Stability

This contract is additive: a later feature may add a check (a type checker, an import-linter
contract, a container build), and adding one changes the workflow and this table together. Removing
or weakening one is a change to what the repository guarantees about itself and belongs in a pull
request that says so.
