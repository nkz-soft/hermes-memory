# Contract: the scanning and packaging checks

**Feature**: `specs/004-ci-scanning-packaging` | **Date**: 2026-09-14

This feature exercises the stability clause of
[`specs/001-project-skeleton/contracts/checks.md`](../../001-project-skeleton/contracts/checks.md),
which reserved the right of a later feature to add a check and named "a container build" as the
example. It adds three commands to that table and does not change C1–C4.

Implementation amends the 001 contract in place, so that one table remains the answer to "what does
this repository check about itself". This file is the specification of what is added and the list of
checks written before the code (Principle III).

## The commands added

| # | Command | Passes when | Fails when |
|---|---|---|---|
| C5 | `gitleaks git .` over the full history, pinned, `-v --redact` | The history contains no credential outside the committed exemptions | Any finding, in any reachable commit |
| C6 | `docker build` of the repository's `Dockerfile` | The image builds from the pinned interpreter and the committed lock file | Any build failure, including a lock file that disagrees with the project definition |
| C7 | `docker run` of the built image, output asserted | The application's usage text is printed and the container exits 0 | No usage text, a non-zero exit, or an image that cannot start the application |

The exact invocations, in the single form both CI and a contributor use, are in
[quickstart.md](quickstart.md). They are one string in one place; CI does not paraphrase them.

### Prerequisites, stated rather than assumed

C1–C4 need only `uv`. **C5, C6 and C7 need a container runtime.** A contributor without one can run
the first four and relies on CI for the rest; this is recorded so that nobody concludes from a local
pass that all seven passed. No fallback path exists on purpose (research R13): a second way of
running the scan would produce a second verdict, and only one of them would be CI's.

### Guarantees carried over

- **No side effects.** None of C5–C7 modifies a tracked file. C5 writes no report by default; C6
  and C7 leave an image in the local daemon and nothing in the tree.
- **No secrets, no registry.** C5–C7 read no credential, and C6/C7 push nothing. This is what keeps
  the workflow running unchanged on a pull request from a fork, and it is asserted (check S10).
- **Exit codes.** POSIX: `0` pass, non-zero fail. No check signals failure through output alone.

## The negative control

A check that has never been observed to fail is not known to work. Two facts, both measured during
planning (research R4, R5, R7), make this concrete here:

1. The repository's own test fixtures contain credential-shaped values by design, so the scan must
   be exempted somewhere or it can never pass.
2. An exemption is invisible in a passing build. The way this feature ships broken is with an
   exemption one character too broad and a green tick over it.

So the feature commits a fixture that **must** be found, at `tests/fixtures/secret_scanning/`, and
CI scans that directory on its own and requires a non-zero exit.

This works because of a measured property of the scanner's configuration resolution: the
configuration is read from the *scanned path*, so a scan of the repository root applies
`.gitleaks.toml` and its exemptions, while a scan of the fixture directory — which contains no
configuration of its own — runs against the default rules and finds the key. Verified both ways
during planning: root scan `no leaks found`, exit 0; fixture scan `leaks found: 1`, exit 1.

The fixture's literal **may not be edited casually**, and is quoted nowhere in this specification —
only in the fixture itself and in the exemption that covers it, so that no document needs an
exemption merely to discuss the check. The upstream rule matches a base32 tail, excluding the digits
`0`, `1`, `8` and `9`; a plausible-looking key containing any of them is not matched, and the
negative control would then pass by finding nothing while claiming to prove the opposite
(research R7). A comment beside the literal says so.

## Checks written before the code

Principle III orders the work: each check below is written first and observed to fail. Checks S1–S10
and I1–I9 are pytest structure tests over committed files; P1–P4 are pytest tests over the
application; C5–C7 are the executable commands themselves, whose verdict is the deliverable rather
than an assertion about it.

### Scanning configuration and workflow

| # | Check |
|---|---|
| S1 | The workflow runs the scanner as a `run:` command, in a job of its own, parsed from YAML rather than matched as text |
| S2 | The scanner reference is pinned to an exact version — a `vX.Y.Z` tag. `latest`, a bare major, or an unpinned reference fails |
| S3 | The invocation carries both `-v` and `--redact`: without the first there is no file, line or rule in the output (FR-004); without the second the secret is printed into a public build log |
| S4 | The scanning job's checkout step sets `fetch-depth: 0`, asserted against that step's parsed `with:` mapping. Without it the history scan passes vacuously over one commit |
| S5 | `.gitleaks.toml` exists, parses as TOML, and sets `[extend] useDefault = true` — the exemptions extend the upstream rules rather than replacing them |
| S6 | Every `[[allowlists]]` entry sets `condition = "AND"`. The default is OR, under which `paths` alone exempts a whole file for that rule |
| S7 | Every `[[allowlists]]` entry declares a non-empty `targetRules`, a non-empty `paths` and a non-empty `regexes`. All three conditions must be present for FR-008's narrowness to mean anything |
| S8 | Every `paths` pattern is anchored (`^`…`$`) and ends in a file extension — no entry may name a directory, which is the blanket exemption FR-008 forbids |
| S9 | The workflow runs the negative control against `tests/fixtures/secret_scanning/` and requires a non-zero exit |
| S10 | The workflow still references no repository secret and still declares `permissions: contents: read` — the existing fork-safety assertion, re-run with the new jobs present |

### Image definition and workflow

| # | Check |
|---|---|
| I1 | A `Dockerfile` exists at the repository root |
| I2 | Its runtime base interpreter version agrees with `.python-version`. A packaging target built on a different interpreter than the tests ran on proves nothing |
| I3 | The build installs with `uv sync` carrying both `--locked` and `--no-dev` — the first so the image cannot ship a re-resolved dependency set, the second so FR-018 holds at the source |
| I4 | `ENTRYPOINT` is the exec form naming the console script, and `CMD` is `["--help"]` (research R10) |
| I5 | A `USER` directive selects a non-root user, and no later instruction returns to root |
| I6 | `.dockerignore` excludes at minimum `.git`, `tests/`, `specs/` and `data/` |
| I7 | The workflow builds the image as a `run:` command in a job of its own |
| I8 | The workflow asserts on the **content** of the container's output — the usage text — and not on its exit status alone. An entry point that exits 0 having printed nothing must fail this |
| I9 | The image job contains no registry login and no push |

### The command-line entry point

| # | Check |
|---|---|
| P1 | `pyproject.toml` declares the console script `hermes-memory` pointing into `hermes_memory.cli` |
| P2 | Invoking the application with `--help` exits 0 and prints usage text naming the application |
| P3 | The application registers no behavioural command — the command list is empty (FR-022). This check is what keeps the entry point a shell rather than a surface |
| P4 | The runtime dependency guard lists `typer` exactly once, alongside the five already declared |

### The contract itself

| # | Check |
|---|---|
| X1 | Every command in the amended 001 checks table is executed by the workflow — the existing `test_runs_every_check_in_the_contract`, extended to C5, C6 and C7, so that removing a step from the workflow fails the suite (FR-024) |

## Stability

This contract is additive in the same sense 001's is. A later feature may add a check; adding one
changes the workflow and the 001 table together. Widening an exemption in `.gitleaks.toml` is a
change to what this repository guarantees about itself, and belongs in a pull request that says so —
which is why S6, S7 and S8 constrain the *shape* of an exemption rather than its contents: the shape
is what a reviewer can check at a glance.
