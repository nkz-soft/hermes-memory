# Research: Secret Scanning and Image Packaging in CI

**Feature**: `specs/004-ci-scanning-packaging` | **Date**: 2026-09-14

Findings marked **(measured)** were obtained by running the tool against this repository during
planning, not inferred from documentation. The commands are reproducible from
[quickstart.md](quickstart.md).

---

## R1 — How the scanner is invoked: the official image, not the GitHub Action

**Decision.** Run the pinned upstream container image `ghcr.io/gitleaks/gitleaks:v8.30.1` directly
from a `run:` step. Do not use `gitleaks/gitleaks-action`.

**Rationale.** The action wraps the same binary but adds two couplings this feature cannot accept.
It reads `GITHUB_TOKEN` from the workflow environment, and it requires a `GITLEAKS_LICENSE` secret
for repositories owned by an organisation. Either one breaks FR-005: a step that reads a repository
secret does not run on a pull request from a fork, because forks receive no secrets — and a scanning
step that silently does not run on exactly the pull requests least under our control is worse than
no scanning step, because the badge says it passed.

Invoking the image directly also makes FR-010 achievable without a second code path: the command a
contributor runs locally is character-for-character the command CI runs, so the two cannot drift.

**Alternatives considered.**

| Alternative | Rejected because |
|---|---|
| `gitleaks/gitleaks-action@v2` | Needs `GITHUB_TOKEN`, and a paid licence key for organisation-owned repositories. Both contradict FR-005/FR-017 fork-safety. |
| Download the release tarball and run the binary | Works, but pins by asset URL and adds checksum verification to keep the pin honest. The image tag is the same pin with the integrity check already done by the registry. |
| `pip install`/`go install` the scanner | Puts the scanner in the project's own dependency graph, which the constitution's stack table does not sanction and which would couple the scan to the Python environment it is supposed to scan. |

---

## R2 — One scan over history, not two scans

**Decision.** A single `gitleaks git` invocation over the full reachable history, with
`actions/checkout@v5` configured `fetch-depth: 0`. No separate diff scan.

**Rationale.** FR-001 (the pull request's changes) and FR-002 (the history) look like two
requirements, but a pull request's changes *are* commits by the time CI sees them. A history scan at
the commit under test therefore covers both, and covers them in the stronger form: a credential
added in one commit of the pull request and deleted in the next is still found, which is the case a
diff scan against the merge base would miss entirely and the case that matters most, because git
remembers what the diff forgets.

`fetch-depth: 0` is required and is not the default — `actions/checkout` fetches a single commit
unless told otherwise, and a history scan over a one-commit checkout passes vacuously. This is the
single most likely way for this feature to ship broken while appearing to work, which is why the
workflow test asserts on it (contracts/checks.md, check S4).

**Measured.** `gitleaks git` over this repository's history scans 33 commits and ~1.37 MB in 2.79 s
— about two orders of magnitude inside SC-005's two-minute budget. The dominant cost of the step is
the image pull, not the scan.

**Alternatives considered.**

| Alternative | Rejected because |
|---|---|
| `gitleaks dir` on the working tree only | Sees the tip only. A credential committed and then removed within the branch survives to `main` unreported — Story 2's whole subject. |
| Diff scan against the merge base, plus a scheduled full history scan | Two configurations to keep in agreement, and it moves the historical result away from the pull request that caused it. The history here is small enough that the simple thing is also the fast thing. |
| `--log-opts` to limit the scan to the pull request's range | An optimisation with no problem to solve at 2.79 s, and it reintroduces the merge-base reasoning that R2 exists to avoid. |

---

## R3 — Git's ownership check inside the container

**Decision.** Pass the ownership exemption through git's environment-variable configuration rather
than mutating any config file:

```text
-e GIT_CONFIG_COUNT=1 -e GIT_CONFIG_KEY_0=safe.directory -e GIT_CONFIG_VALUE_0=*
```

**Rationale.** The repository is bind-mounted into the container, where its files are owned by a uid
that is not the container user. Git refuses to operate on such a repository — "detected dubious
ownership" — and the scanner then reports zero findings on a repository it never read. That is a
silent false pass, the failure mode this feature least tolerates.

`GIT_CONFIG_COUNT` scopes the exemption to the single container invocation. The alternative,
`git config --global --add safe.directory`, mutates state on the host that runs it, which is
tolerable on a throwaway CI runner and not on a contributor's machine — and FR-010 requires the same
command in both places.

**Measured.** With the trio set, the history scan reads all 33 commits (R2). Without it the scan is
at the mercy of the host's uid mapping, which differs between the Linux runner and a contributor's
Docker Desktop — a difference that would otherwise surface as "passes in CI, fails for me".

---

## R4 — The exemptions the repository already needs

**Measured.** A default-configuration scan of this repository's history reports **10 findings across
5 distinct locations**, every one of them a deliberate synthetic value:

| Rule | Location | What it is |
|---|---|---|
| `github-pat` | `tests/unit/test_redaction_canary.py:28` | The canary token feature 003 asserts is never logged |
| `jwt` | `tests/unit/test_redaction_values.py` | The JWT in the shape roster's test |
| `generic-api-key` | `tests/unit/test_redaction_names.py:27` | `hs-live-…`, the project's invented token shape |
| `generic-api-key` | `specs/003-logging-telemetry-baseline/quickstart.md:65` | The same literal, in a documented worked example |
| `generic-api-key` | `specs/003-logging-telemetry-baseline/quickstart.md:94` | The same literal again |

The counts differ with what the scan can reach, and the difference is worth stating plainly rather
than leaving someone to reconcile two numbers later. A scan of the working tree reports 5, one per
location. A scan of a full clone's history reports 10, because several of those literals were
touched by more than one commit and one moved line. A scan of this feature branch's own ancestry —
which is what CI does on a pull request — reports 5 again. Same five places throughout.

The moved line is the part that constrains the design: **exemptions must survive a line moving**,
which rules out fingerprint-based exemptions for these cases (R5).

Story 3 is therefore not hypothetical. Without exemptions this feature cannot merge at all, since
FR-009 forbids merging with an unaddressed finding behind it, and the findings are all in code that
exists precisely to prove secrets are redacted.

---

## R5 — The shape of an exemption: path AND value, scoped to one rule

**Decision.** A committed `.gitleaks.toml` extending the default rule set, with one
`[[allowlists]]` entry per concern, each carrying `condition = "AND"`, a `targetRules` list, a
`paths` list of anchored per-file regexes, and a `regexes` list matching the specific literal.

```toml
[extend]
useDefault = true

[[allowlists]]
description = "..."
condition = "AND"
targetRules = ["github-pat"]
paths = ['''^tests/unit/test_redaction_canary\.py$''']
regexes = ['''ghp_Canary[A-Za-z0-9]{20,}''']
```

**Rationale.** FR-008 forbids a blanket exemption, and this shape makes a blanket exemption
impossible to write by accident. Three independent conditions must all hold — the rule, the file,
the value — so widening any one of them still leaves the other two biting. In particular, exempting
the canary file does not exempt other credential kinds in that file, and exempting the
`hs-live-…` literal does not exempt other generic keys in the same document.

`condition = "AND"` is load-bearing and is **not** the default: allowlist conditions default to OR,
under which `paths` alone would exempt the entire file for that rule. A reviewer should treat a
missing `condition = "AND"` as a defect, and check S6 in the contract asserts it is present on every
entry.

**Measured.** A trial configuration of exactly this shape, applied to the full history, takes the
run from 10 findings to `no leaks found` — while a file containing the negative-control key still
fails with exit status 1 and rule `aws-access-token`. Both halves were run; the exemption narrows
without disarming.

**Measured, and load-bearing for R7's fixture**: the scanner does not report findings inside the
configuration file it is using, so the literal quoted in an exemption's `regexes` does not itself
become a finding. Were it otherwise, every exemption would need an exemption.

**Alternatives considered.**

| Alternative | Rejected because |
|---|---|
| `paths` alone (no `regexes`, default OR condition) | Exempts the whole file for that rule. A real credential pasted into a redaction test — the likeliest place for one to arrive — would go unreported. |
| A `tests/` directory exemption | Exactly the blanket FR-008 forbids, and the corpus this project handles makes test fixtures a high-risk location rather than a safe one. |
| `--baseline-path` with a committed baseline report | Freezes findings by fingerprint (`file:rule:line`). R4 measured line numbers moving between commits, so the baseline would go stale silently and would also mask a *new* finding in a file already in the baseline. |
| Per-finding `gitleaks:allow` comments in the source | Puts scanner syntax in the redaction tests, where a comment sitting beside a credential is easy to copy into code that should not have it. It also cannot exempt a Markdown code block. |
| Lowering the rules' entropy thresholds | Changes detection globally to solve five specific cases, and silently weakens the check for every future one. |

---

## R5a — An exemption matches the line, not the captured secret

**Measured during implementation, after the first configuration left one finding standing.** An
exemption quoting the canary token's full literal did not exempt it. The reason is that a rule
captures a *fixed length*: the GitHub rule takes 36 characters, and the canary fixture is 40, so the
reported secret is the fixture truncated — a string that appears nowhere in the source file.
Matching against the secret would therefore require quoting the cut-off form, which no reviewer
could compare against the file it exempts.

**Decision.** Every entry sets `regexTarget = "line"`, so the literal quoted in the configuration is
the literal that appears in the source. This trades a sliver of breadth — any secret on that line,
of that rule, in that file — for exemptions a human can actually verify by reading. Given that
`targetRules` and `paths` still both apply, the sliver is not where the risk is; unreviewable
exemptions are.

**Measured after the change**: the branch's history scans clean — 10 commits, `no leaks found`,
exit 0.

---

## R6 — Reporting: `-v --redact`, and why both

**Decision.** Run with `-v` (verbose) and `--redact`.

**Rationale.** These pull in opposite directions and both are required. Without `-v`, the scanner
prints only `leaks found: N` — FR-004's file, line and rule are absent, and a contributor cannot act
on the failure without re-running the scan locally. Without `--redact`, the finding block prints the
matched secret in full, into a build log that is publicly readable on a public repository — which
would make the scanning step itself a disclosure channel, and a genuinely leaked credential twice
leaked.

**Measured.** With both flags a finding prints as:

```text
Finding:     aws_access_key_id = REDACTED
Secret:      REDACTED
RuleID:      aws-access-token
File:        config.ini
Line:        1
Fingerprint: config.ini:aws-access-token:1
```

Location and kind, no value. That is FR-004 exactly.

---

## R7 — The test key must match the rule's alphabet

**Measured, and recorded because it cost a false pass during planning.** The first fake AWS key
tried produced `no leaks found`. It was not wrong-looking; it was wrong in a way no reviewer would
catch by eye. The upstream `aws-access-token` rule matches a prefix followed by a **base32** tail —
sixteen characters drawn from `A`–`Z` and `2`–`7`, which excludes the digits `0`, `1`, `8` and `9`.
The key first tried contained three of them, so the rule never fired.

**Consequence for this feature.** Issue #7's acceptance criterion is "a pull request adding a fake
AWS key fails CI". A test written with a plausible-looking but unmatchable key would pass while
proving the opposite of what it claims. A key verified to be matched is therefore fixed in the
negative-control fixture, with a comment beside it recording the alphabet constraint and that it may
not be edited casually. A negative control — a scan that *fails* — is the only form of proof this
check accepts (Principle III).

**The literal lives in exactly two files**: the fixture, and the exemption in `.gitleaks.toml` that
keeps the repository scan green. It is deliberately absent from this plan and its sibling documents,
which describe it instead. A specification that quoted it would itself become a finding, and would
need an exemption of its own — an exemption whose only purpose is to permit talking about the
check. Every document here can therefore be read by the scanner without special pleading.

---

## R8 — Pinning the scanner version

**Decision.** Pin the image to the exact tag `v8.30.1`, the current release at the time of writing.

**Rationale.** A floating `latest` makes the build's verdict a function of an upstream release
rather than of the change under test, so a pull request that changed nothing relevant can fail, and
the contributor has no way to tell that from a real finding. Pinning also bounds R4's exemption set:
new rules in a later release may produce new findings, and adopting them should be a deliberate
commit that updates the pin and the exemptions together.

The repository pins its other actions by major tag (`actions/checkout@v5`, `astral-sh/setup-uv@v7`).
An exact patch tag is a stricter pin than the local convention, and deliberately so: for those two,
a surprise means a build-tooling change, while here it means a change in what counts as a secret.

---

## R9 — The image: two stages, `uv sync --locked --no-dev`, non-root

**Decision.** A two-stage `Dockerfile`. The builder stage uses the upstream uv image matching the
pinned interpreter, runs `uv sync --locked --no-dev --no-editable` into `/app/.venv`, and the
runtime stage is `python:3.13-slim-bookworm` with that virtual environment copied in, owned by and
run as a non-root user.

**Rationale.**

- `--locked` gives the image the property the CI environment already has: it fails when `uv.lock`
  disagrees with `pyproject.toml` rather than resolving something else. Without it the image could
  silently ship a different dependency set than the tests ran against (FR-013).
- `--no-dev` is what makes FR-018 true at the source rather than by deletion afterwards.
- `--no-editable` installs the project as a real package, so the entry point is the installed
  console script and not a path into a source tree that the runtime stage does not carry (FR-021).
- The interpreter tag is derived from `.python-version` (`3.13`), and a structure test asserts the
  two still agree — a pin that drifts from the pin the tests use is a packaging target that proves
  nothing (FR-013).
- Non-root is FR-019, and costs one `USER` line.

**Alternatives considered.**

| Alternative | Rejected because |
|---|---|
| Single-stage build | Ships uv, the build toolchain and the package cache in the runtime image for no benefit. |
| `pip install .` in the image | Ignores `uv.lock`, so the image's dependency set is resolved independently of the one CI tested. |
| A distroless runtime base | No shell, which the image-content assertions of SC-007 use, and a larger change than a feature about proving the target builds should make. |
| Alpine base | musl against manylinux wheels is a source of surprise for a scientific-adjacent dependency tree; nothing here needs the smaller image. |

---

## R10 — `ENTRYPOINT` plus a default `CMD` of `--help`

**Decision.** `ENTRYPOINT ["hermes-memory"]` and `CMD ["--help"]`.

**Rationale.** This is the one design choice in the packaging half worth arguing, and it resolves
FR-014's two clauses at once. `docker run <image>` runs `hermes-memory --help`: usage text, exit
status 0 — which is issue #7's acceptance criterion verbatim ("an image whose entry point runs the
CLI's `--help`"). `docker run <image> anything` replaces the default argument list, so arguments
reach the application rather than a shell, and the exec form means no shell is involved at all.

It also sidesteps a real hazard. The exit status of a command-line group invoked with *no arguments*
depends on the argument-parsing library's version — some releases print usage and exit 0, others
exit 2 — and FR-014 requires success. Making `--help` the default argument takes the answer out of
the library's hands: `--help` is specified to exit 0, in every version.

**Alternatives considered.**

| Alternative | Rejected because |
|---|---|
| `ENTRYPOINT` only, relying on no-args behaviour | Makes the acceptance criterion depend on an upstream library's exit-status choice, which changed between releases. |
| `CMD ["hermes-memory", "--help"]` with no `ENTRYPOINT` | `docker run <image> foo` would try to execute `foo` as a program instead of passing it to the application. |
| A shell-form entry point | Argument quoting becomes the shell's business, and signals do not reach the application. |

---

## R11 — The command-line entry point is a shell, deliberately

**Decision.** A Typer application in `hermes_memory.cli` with a callback, a description and a
`--version` option, registered as the console script `hermes-memory`. No behavioural command.

**Rationale.** `cli` is an empty package today; feature 001 stated explicitly that "the Typer
application arrives with the feature that has something to run". This feature has something to run
in a narrow sense — the packaging target cannot be exercised without an entry point — and nothing
more. FR-022 bounds it so that this does not become a command-surface design by accident, and so
that the feature that owns the first real command inherits an empty, uncontested surface.

Typer is the constitution's fixed entry for CLI, so this adds one runtime dependency the stack table
already sanctions. The guard test over runtime dependencies (`tests/structure/test_packaging.py`) is
updated in the same commit, for that one entry, the way feature 003 updated it for its three.

**Alternatives considered.**

| Alternative | Rejected because |
|---|---|
| `python -m hermes_memory` as the image's entry point | Not an installed console script, so FR-021's property — the image runs the packaged application — goes unproven. |
| A shell script printing static usage text | Proves the image starts, not that the packaged application starts. The smoke test would pass on an image with no working Python at all. |
| Adding a real first command now | Scope the issue did not ask for, on a surface no specification has designed. |

---

## R12 — Three jobs, not three more steps

**Decision.** Add two jobs, `scan` and `image`, alongside the existing `checks` job, rather than
appending steps to it.

**Rationale.** The scan needs `fetch-depth: 0` and the existing job deliberately does not have it;
adding it there would slow every run of the lint and test path for a reason unrelated to it. The
three jobs are independent and run in parallel, so the wall-clock cost of this feature is the
slowest of the two new jobs rather than their sum. Separate jobs also report separately: a red
build names the scan or the image, not "checks".

The workflow-level `permissions: contents: read` and the `concurrency` block are unchanged and cover
the new jobs, which keeps the existing fork-safety assertion in
`tests/structure/test_ci_workflow.py` true without modification (FR-005).

---

## R13 — What the local run costs a contributor

**Decision.** Both new checks require a container runtime, stated as a prerequisite in the checks
contract rather than assumed.

**Rationale.** C1–C4 need only uv, and that is worth preserving: a contributor with no Docker can
still run lint, format and tests, and CI remains the backstop for the other two. Pretending
otherwise — by, say, adding a fallback that installs the scanner binary when no container runtime is
found — would create a second code path whose verdict is not the one CI produces, which is precisely
what FR-010 exists to prevent.

---

## R14 — Existing tests that change, and why

Named here so a reviewer seeing a modified assertion can find the sentence that authorised it.

- **`tests/structure/test_packaging.py`** — `test_runtime_dependencies_are_exactly_the_declared_set`
  guards the exact runtime dependency set. It gains `typer`, with the stack-table row that permits
  it named in the docstring (R11). Still a guard, now over one more.
- **`tests/structure/test_ci_workflow.py`** — `test_runs_every_check_in_the_contract` enumerates the
  contract's commands. FR-024 requires it to cover the new ones. The existing file's own docstring
  records why it parses the workflow as YAML rather than matching text: a comment must not be able to
  satisfy a check. The new assertions follow that rule, and check S4 (`fetch-depth: 0`) is asserted
  against the parsed `with:` mapping of the checkout step in the scanning job specifically, not
  against the file's text.
- **`tests/structure/test_module_layout.py`** — `test_recorded_modules_carry_no_behaviour` treats
  recorded boundaries as docstring-only. `cli` stops being one, and joins `observability` in the
  explicit set of filled boundaries, so the remaining thirteen stay guarded.
