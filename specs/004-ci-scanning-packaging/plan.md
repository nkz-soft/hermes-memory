# Implementation Plan: Secret Scanning and Image Packaging in CI

**Branch**: `004-ci-scanning-packaging` | **Date**: 2026-09-14 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/004-ci-scanning-packaging/spec.md`, derived from
GitHub issue #7 (Phase 1, wave 2; depends on #4, merged as PR #33).

## Summary

Make two promises the repository already makes about itself enforceable: no credential in a public
tree, and a container is how this ships. Concretely — a pinned secret scanner run over the full
history in CI with findings failing the build, a committed exemption file whose shape makes a
blanket exemption hard to write, a two-stage `Dockerfile` whose entry point is the installed
command-line application, and the minimal Typer shell that entry point needs in order to exist.

Four ideas in it beyond the obvious assembly.

First, **the scan is a history scan, and only a history scan** ([research.md](research.md) R2). A
pull request's changes are commits by the time CI sees them, so one scan covers both of the spec's
scanning requirements — and covers them in the stronger form, because a credential added in one
commit of a branch and deleted in the next is invisible to a diff and permanent in git.

Second, **an exemption is a conjunction of three narrowings, not a path** (R5). Rule, file and value
must all match. This is the difference between "the redaction tests may contain fixtures" and "the
redaction tests are not scanned" — and the second is what a one-line mistake would silently produce,
in exactly the files most likely to receive a real credential by accident.

Third, **there is a negative control, and it is committed** (contract, R7). This feature's failure
mode is a green tick over a check that cannot fail. So a fixture that must be found is committed,
CI scans it directly, and CI requires that scan to fail. Planning already produced one false pass
here — a fake AWS key that no rule matched — which is the evidence that this is not a theoretical
concern.

Fourth, **the image's default argument is `--help`** (R10). `ENTRYPOINT` plus `CMD ["--help"]`
satisfies both halves of the entry-point requirement at once and takes the exit status out of the
argument parser's hands, where it has varied between releases.

The scanning half is the half that matters. If only one of the two shipped, it should be that one.

## Technical Context

**Language/Version**: Python 3.13, as pinned by `.python-version` and by the skeleton. The image's
runtime base is derived from the same pin, and a check asserts they still agree (I2).

**Primary Dependencies**: `typer` — one runtime dependency added, fixed by the constitution's
Technology Stack table (CLI row). No new development dependency; the structure tests read committed
files using `pyyaml`, already present, and the standard library's `tomllib`.

**External tooling**: `ghcr.io/gitleaks/gitleaks:v8.30.1`, pinned to an exact patch tag (R8), and a
container runtime. Neither enters the project's dependency graph.

**Storage**: none. The scan persists nothing; no baseline, no report (R5).

**Testing**: pytest. New structure tests under `tests/structure/` over the committed workflow,
`Dockerfile`, `.dockerignore` and `.gitleaks.toml`; new unit tests under `tests/unit/` over the
command-line entry point. These read files rather than running containers, so `pytest` keeps needing
only `uv`. The container-executed checks are C5–C7 in the contract, run by CI and reproducible
locally by one documented command each.

**Target Platform**: `ubuntu-latest` in CI; developer machines with a container runtime for C5–C7.
The image is built for the build's architecture only (spec assumption).

**Performance Goals**: SC-005 allows the scanning step two minutes. **Measured**: 33 commits,
1.37 MB, 2.79 s (R2). The step's real cost is the image pull.

**Constraints**: no repository secret and no elevated token, so every new job runs on a pull request
from a fork (FR-005, FR-017, check S10). Nothing is pushed to a registry. No new runtime dependency
beyond the stack table's CLI row. The scan must report location and kind without printing the secret
into a public build log (R6).

**Scale/Scope**: 2 new CI jobs, 3 new checks in the contract, 5 committed exemptions covering 10
measured occurrences, 1 negative-control fixture, 24 contract checks, 1 runtime dependency,
3 existing tests changed on purpose.

## Constitution Check

*GATE: passed before Phase 0 research; re-evaluated after Phase 1 design — see below.*

| Principle | Compliance |
|---|---|
| **I — Raw Archive Is the Source of Truth** | Not engaged. Nothing here reads, writes or derives history. The negative-control fixture is a synthetic credential in a test directory, not conversation data, and `data/` is excluded from the image's build context (I6) precisely so that no archive content can be packaged by accident. |
| **II — Provenance and Stable Identity** | Not engaged. No document, identifier or timestamp is produced. |
| **III — Test-First (NON-NEGOTIABLE)** | Engaged, and it orders the work. Every one of the 24 checks in [contracts/checks.md](contracts/checks.md) is written before the file it constrains and observed to fail. The check this principle bears on hardest is the negative control: a scanning check is exactly the kind that passes vacuously, so the feature commits a fixture that must be found and requires the scan of it to fail. Red before green is not a formality here — R7 records a case where the red step was skipped in planning and produced a false pass. |
| **IV — Replaceable Boundaries** | Engaged lightly. `cli` is a boundary in the constitution's module tree; this feature fills it with an application object and nothing else, and FR-022 forbids adding a command. No Hindsight type, endpoint or vocabulary appears anywhere in this feature. The scanner is invoked as an external process against the repository, never imported, so it is not a dependency of any boundary. |
| **V — Secrets Never Reach the Memory Engine** | Engaged, and this feature is the repository-facing half of it. The principle's clauses about credentials are enforced for the *corpus* by ARCHITECTURE.md §13's sanitizer and for the *log* by feature 003; nothing yet enforced them for the *repository*, though the constitution named Gitleaks in the stack. That gap is what closes here. Two design choices follow directly from the principle rather than from convenience: `--redact`, so the check cannot itself publish a secret into a public build log (R6); and the conjunction rule for exemptions, so that a fixture file being exempted never means a real credential in it would be missed (R5). |

**Technology Stack compliance**: Gitleaks is the fixed entry for Secret scanning, Docker for
Packaging, Typer for CLI. All three are used as fixed; nothing is displaced and no competing tool is
introduced, so the constitution's "changing any entry, or adding a dependency that displaces one"
clause is not triggered and **no decision record is required**. This matches issue #7's governance
answer of "None of the above".

Two clarifications a reviewer might otherwise have to derive:

- **The scanner is not a project dependency.** It is invoked as a pinned external image against the
  repository. It appears in no dependency group, and the Python environment is unchanged by it.
- **This feature is not ARCHITECTURE.md §13's sanitizer, and does not substitute for it.** §13
  protects the corpus on its way to the memory engine; this protects the repository. Feature 003's
  research recorded the same boundary from the other side (R7 there). Neither removes the need for
  the other, and the plan says so because the failure mode is someone later concluding that secret
  handling is "done".

**Three existing tests change on purpose, in the commits that require them** (R14):

- `tests/structure/test_packaging.py::test_runtime_dependencies_are_exactly_the_declared_set` gains
  `typer`, with the stack-table row that permits it named in its docstring. Still a guard, now over
  six.
- `tests/structure/test_ci_workflow.py::test_runs_every_check_in_the_contract` gains C5, C6 and C7,
  per FR-024. The file's existing docstring records why it parses YAML rather than matching text —
  a comment must not be able to satisfy a check — and the new assertions follow that rule.
- `tests/structure/test_module_layout.py` records `cli` in `FILLED_BOUNDARIES` alongside
  `observability`, so the remaining thirteen boundaries stay guarded and filling one stays a
  deliberate edit in the feature's own commit.

Each is called out because a reviewer seeing a weakened assertion should be able to find the
sentence that authorised it.

**The §8 / module-tree conflict raised by 001 is untouched.** Still awaiting the feature that needs
the *Import state* boundary.

**Branch naming**: `004-ci-scanning-packaging`, matching the feature directory, per the Development
Workflow section. Created by hand because the `before_specify` hook is not installed here.

**Post-design re-evaluation**: unchanged, no violations. Phase 1 added one contract, one data model
and no runtime behaviour beyond an entry point that prints its own usage. The two design decisions
carrying the most weight both move towards Principle V rather than away from it: the conjunction
rule for exemptions narrows what can be excused, and `--redact` closes a disclosure channel the
check would otherwise open. The Complexity Tracking table below stays empty.

## Alternatives Considered

The issue records one rejected alternative; research produced the rest. Full reasoning in
[research.md](research.md).

| Alternative | Rejected because |
|---|---|
| **A pre-commit hook alone** (the issue's alternative) | It protects the machine that has it installed. This project's own workflow runs from throwaway worktrees, and a public repository's risk comes from the contributor whose machine you do not control. |
| `gitleaks/gitleaks-action@v2` (R1) | Reads `GITHUB_TOKEN`, and needs a paid licence for organisation-owned repositories. Either breaks fork-safety — and a scanner that silently skips fork pull requests is worse than none, because the tick still appears. |
| Downloading the release binary instead of the image (R1) | Pins by asset URL and needs checksum verification to stay honest; the image tag is the same pin with integrity already handled. |
| A diff scan against the merge base (R2) | Misses a credential added and then deleted within the branch — permanent in git, invisible in the diff, and the whole subject of Story 2. |
| `gitleaks dir` on the working tree (R2) | Sees the tip only; history is where a leak survives. |
| `git config --global --add safe.directory` on the host (R3) | Mutates state on whatever machine runs it. Tolerable on a throwaway runner, not on a contributor's machine — and FR-010 requires the same command in both places. |
| `paths`-only exemptions, or a `tests/` exemption (R5) | Exempts a whole file or directory for a rule. The redaction tests are the likeliest place for a real credential to be pasted, so they are the last place to stop scanning. |
| A committed baseline report (R5) | Freezes findings by `file:rule:line`. Measured: line numbers already moved between commits here, so the baseline goes stale silently and masks new findings in files it covers. |
| `gitleaks:allow` comments in the source (R5) | Puts scanner syntax beside a credential in test code, where it is easy to copy into code that should not carry it; and cannot exempt a Markdown code block. |
| Lowering rule entropy thresholds (R5) | Weakens detection globally to solve five specific cases. |
| Omitting `-v`, or omitting `--redact` (R6) | Without `-v` the output names no file, line or rule and the contributor cannot act. Without `--redact` the build log publishes the secret — on a public repository, a second leak. |
| A floating `latest` scanner tag (R8) | Makes the verdict a function of an upstream release rather than the change under test, and a contributor cannot distinguish that from a real finding. |
| Single-stage image, `pip install .`, distroless or Alpine base (R9) | Respectively: ships the toolchain; ignores `uv.lock` so the image's dependencies are not the ones tested; removes the shell the content assertions use; trades manylinux wheels for musl surprises with nothing gained. |
| `ENTRYPOINT` with no default `CMD` (R10) | Makes the acceptance criterion depend on the argument parser's no-args exit status, which has differed between releases. |
| `python -m hermes_memory`, or a shell script printing usage (R11) | Neither proves the packaged console script runs — the second would pass on an image with no working Python at all. |
| Appending the new steps to the existing `checks` job (R12) | The scan needs `fetch-depth: 0`, which would slow every lint and test run; and a red build would say "checks" rather than naming the scan or the image. |
| A non-container fallback for the local scan (R13) | A second code path with a second verdict, only one of which is CI's — precisely what FR-010 exists to prevent. |

## Project Structure

### Documentation (this feature)

```text
specs/004-ci-scanning-packaging/
├── spec.md                    # Feature specification
├── plan.md                    # This file
├── research.md                # Phase 0 output — R1..R14, measurements marked
├── data-model.md              # Phase 1 output — the exemption, the finding, the fixture
├── quickstart.md              # Phase 1 output — validating the deliverable by hand
├── contracts/
│   └── checks.md              # Phase 1 output — C5..C7, and the 24 checks
├── checklists/
│   └── requirements.md        # Specification quality checklist
└── tasks.md                   # Phase 2 output (/speckit-tasks — NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
.github/workflows/ci.yml                # CHANGED: + `scan` and `image` jobs; `checks` untouched
.gitleaks.toml                          # NEW: [extend] useDefault, 5 narrow exemptions
Dockerfile                              # NEW: two stages, non-root, ENTRYPOINT + CMD ["--help"]
.dockerignore                           # NEW: .git, tests/, specs/, data/, .claude/
pyproject.toml                          # CHANGED: + typer, + [project.scripts] hermes-memory
uv.lock                                 # Re-resolved, committed
README.md                               # + the two new checks and the container prerequisite
specs/001-project-skeleton/contracts/checks.md   # CHANGED: the table gains C5, C6, C7

src/
└── hermes_memory/
    └── cli/
        └── __init__.py                 # CHANGED: the Typer application; no command (FR-022)

tests/
├── fixtures/
│   └── secret_scanning/
│       └── leaky_config.ini            # NEW: the negative control — must be found
├── structure/
│   ├── test_ci_workflow.py             # CHANGED: + C5..C7, S1..S4, S9, I7..I9
│   ├── test_packaging.py               # CHANGED: guards six runtime dependencies; + P1
│   ├── test_module_layout.py           # CHANGED: cli recorded as filled
│   ├── test_secret_scanning_config.py  # NEW: S5..S8 — the exemptions' shape
│   └── test_image_definition.py        # NEW: I1..I6 — the Dockerfile and .dockerignore
└── unit/
    └── test_cli.py                     # NEW: P2, P3 — usage text, and no command registered
```

**Structure Decision**: the configuration files live at the repository root, where their tools look
for them by default — a scanner configuration found only via a flag is one a contributor's ad-hoc
run will silently not use. The two new test modules are split by subject rather than merged into the
existing workflow test, because the workflow test's subject is the workflow and these two are about
files it merely invokes.

`tests/fixtures/` is created by this feature. The repository has had no fixture directory; the
project's own convention, recorded in CLAUDE.md, is that fixtures are synthesized rather than taken
from real history, and this one is synthetic by construction.

## Deferred, deliberately

Named so a reviewer can see these were considered rather than forgotten:

- **Publishing the image.** Needs registry credentials, which would end fork-safety for the image
  job. What is proven here is that the image builds and starts; where it is published belongs to the
  feature that first needs a published artifact.
- **Multi-architecture builds, image signing, an SBOM, image vulnerability scanning.** All are
  supply-chain concerns worth having once something is published.
- **A pre-commit hook.** Rejected as *the* control, but a reasonable convenience later, behind the
  same pinned scanner and the same configuration.
- **Scanning the corpus under `data/`.** Not this feature's subject, and `data/` is untracked; the
  corpus's protection is ARCHITECTURE.md §13's sanitizer.
- **Any behavioural command on the CLI.** FR-022, and check P3 keeps it that way.
- **Adding the scan to a scheduled run.** The history is scanned on every pull request and every
  push to the default branch; a nightly run would add a third trigger and no information.

## Complexity Tracking

> Fill ONLY if Constitution Check has violations that must be justified

No violations. No deviation from the constitution is taken, and no entry in the fixed technology
stack is changed, displaced or added to in a way that requires a decision record. The three existing
tests that change do so under sentences their own authors wrote for that purpose, and all three
remain guards afterwards.
