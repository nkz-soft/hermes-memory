# Feature Specification: Secret Scanning and Image Packaging in CI

**Feature Branch**: `004-ci-scanning-packaging`

**Created**: 2026-09-14

**Status**: Draft

**Input**: GitHub issue #7 — "Run secret scanning and image packaging in CI". Phase 1, wave 2.
Depends on #4.

## User Scenarios & Testing *(mandatory)*

The users of this feature are the contributors who open pull requests against a public repository
whose subject matter is private engineering history, and the reviewers who have to decide whether a
change is safe to merge. The value delivered is that two promises the repository already makes about
itself — no credential in the tree, and a container is how this ships — stop being promises a human
has to keep by reading diffs, and become checks that fail the build.

Both promises are already written down and neither is currently enforced. The constitution's
Technology Stack names Gitleaks and Docker; nothing in `.github/workflows/ci.yml` runs either. The
checks contract (`specs/001-project-skeleton/contracts/checks.md`) anticipated exactly this: it
declares itself additive and names "a container build" as an example of a check a later feature
would add.

### User Story 1 - A credential cannot be merged into a public repository (Priority: P1)

A contributor pastes a debug dump into a test fixture to reproduce a parser defect, and the dump
carries a live access key. They open a pull request. The build fails on the scanning step, naming
the file and the line, before any reviewer has had to spot it by eye and before the change reaches
the default branch.

**Why this priority**: this is the reason the issue exists. The repository is public and the corpus
it processes is years of private engineering history, where a leaked token is a live credential
(Principle V). A review that catches such a paste is luck; a check that catches it is the control.
Everything else in this feature is worth less than this.

**Independent Test**: add a file containing a credential of a recognised shape to a working tree,
run the scan the way the build runs it, and observe a non-zero exit that names the file and the
line.

**Acceptance Scenarios**:

1. **Given** a pull request whose changes add a value of a recognised credential shape, **When** the
   build runs, **Then** the scanning step fails and the build fails with it.
2. **Given** that failure, **When** a contributor reads the build output, **Then** it names the file,
   the line and the kind of credential found, so the finding can be acted on without re-running the
   scan locally to discover what it was.
3. **Given** a pull request whose changes carry no credential, **When** the build runs, **Then** the
   scanning step passes and reports no finding.
4. **Given** a pull request opened from a fork, **When** the build runs, **Then** the scanning step
   runs exactly as it does for a branch in this repository — it reads no repository secret and
   requires no elevated token.
5. **Given** the scanning step fails, **When** the build's other checks are considered, **Then** the
   overall result is a failure regardless of how the lint, format and test checks ended; a finding
   is never advisory.

---

### User Story 2 - The history behind the default branch is proven clean, not assumed clean (Priority: P1)

A maintainer wants to know whether anything already committed to this repository carries a
credential — including in a commit that was later amended away in the working tree but is still
reachable in history. The build scans the history, and its result is the answer.

**Why this priority**: a scan of a diff protects the future only. Git history is permanent and
public: a credential committed once and deleted in the next commit is still there to be fetched, and
the only way the repository can claim to be clean is to have looked. Equal in priority to Story 1
because a leak already in history is the more dangerous of the two — it exists now.

**Independent Test**: run the historical scan over the repository at its current commit and observe
that it examines commits rather than the working tree, and that it exits zero on a history with no
finding and non-zero on one with a finding.

**Acceptance Scenarios**:

1. **Given** the repository's committed history, **When** the build runs, **Then** the history is
   scanned in full — every reachable commit, not only the commits of the pull request.
2. **Given** a commit in history that introduced a credential and a later commit that removed it,
   **When** the history is scanned, **Then** the finding is reported, because the credential is still
   reachable.
3. **Given** a history with no finding, **When** the history is scanned, **Then** the step passes and
   the build is not slowed to the point of being unusable (SC-005).
4. **Given** the repository's history as it stands on the default branch today, **When** the history
   is scanned, **Then** the scan passes — this feature does not merge with a known unaddressed
   finding behind it.

---

### User Story 3 - A deliberate fixture is not mistaken for a leak (Priority: P2)

The repository already contains, on purpose, values shaped exactly like credentials: the redaction
tests assert that a bearer token, a JSON web token and a conventionally prefixed API key are
withheld from log output, which requires having them in the tree. A contributor who adds another
such fixture can do so, declare it, and the build stays meaningful for everyone else.

**Why this priority**: a check that cries wolf is turned off, and turning this one off returns the
repository to Story 1's unprotected state. But it is derivative of Story 1 — it protects the check
rather than the repository — and it only matters once the check exists.

**Independent Test**: run the scan over the repository as it stands, with its existing
credential-shaped test fixtures in place, and observe zero findings.

**Acceptance Scenarios**:

1. **Given** the repository as it stands, with its existing credential-shaped test fixtures, **When**
   the scan runs, **Then** it reports zero findings.
2. **Given** a contributor who must add a new synthetic credential to a fixture, **When** they follow
   the project's documented procedure for declaring it, **Then** the scan passes, and the declaration
   is visible in the diff of their pull request for a reviewer to weigh.
3. **Given** a declaration that exempts a fixture, **When** a real credential is added elsewhere in
   the repository, **Then** it is still found — no declaration may be broad enough to disable the
   check for the tree, for a whole directory of sources, or for a credential kind everywhere.
4. **Given** the project's documentation, **When** a contributor hits a finding they believe is a
   false positive, **Then** the documentation tells them how to tell the two apart and what to do in
   each case.

---

### User Story 4 - The container the project says it ships is proven to build and run (Priority: P2)

A contributor changes a dependency, the interpreter pin, or the package layout. The build assembles
the project's container image from scratch and runs it. If the image no longer builds, or builds but
cannot start the command-line application, the pull request says so.

**Why this priority**: ADR-004 fixes Docker as the packaging target, and an unexercised packaging
target decays silently — it is discovered broken at the moment someone first needs it, which is the
worst moment. It ranks below the scanning stories because a broken image costs time, while a leaked
credential costs a credential.

**Independent Test**: build the image from the repository and run the resulting container with no
arguments; observe that it prints the command-line application's usage text and exits successfully.

**Acceptance Scenarios**:

1. **Given** the repository at any commit under review, **When** the build runs, **Then** the image
   is built from the repository's own definition, from the pinned interpreter and the committed lock
   file.
2. **Given** the built image, **When** a container is run from it with no arguments, **Then** the
   command-line application's usage text is printed and the container exits successfully.
3. **Given** the built image, **When** a container is run from it with arguments, **Then** the
   arguments reach the command-line application rather than being interpreted by a shell inside the
   image.
4. **Given** a change that breaks the image — an unresolvable dependency, a missing package, an
   interpreter that no longer matches the pin — **When** the build runs, **Then** the build fails on
   the image step.
5. **Given** the image build and its smoke test, **When** they run, **Then** no repository secret is
   read, nothing is pushed to any registry, and no credential is required.

---

### Edge Cases

- A finding lies in a file the scan cannot read as text — a lock file, a binary fixture, an encoded
  blob. It must be examined or explicitly excluded by the configuration, never skipped silently
  because it was inconvenient.
- The scan's own output contains the credential it found. A build log is public on a public
  repository, so the output must identify a finding by location and kind without reproducing the
  secret value in full.
- The default branch's history grows. The historical scan must stay within the time budget of
  SC-005, and the design must state what happens when it no longer does, rather than leaving a
  future contributor to discover a build that times out.
- A pull request rewrites history — a force push, a rebase. The scan must reflect what is actually
  reachable at the commit under test rather than a cached earlier result.
- The scanning tool changes its findings between versions, and a build that passed yesterday fails
  today with no change to the repository. The version must be pinned so that a build result is
  attributable to the change under test.
- The container image is built on a machine with a different architecture from the one a contributor
  runs. The check proves the image builds and starts, not that it runs everywhere; the boundary must
  be stated rather than implied.
- The command-line application has no commands yet. Its usage text is still the thing the image's
  entry point must produce, and the smoke test must not be satisfied by an entry point that merely
  exits zero having printed nothing.
- The declaration file that exempts fixtures is itself edited in a pull request. The change must be
  as visible to a reviewer as any other change, because widening it is how this check is disabled.

## Requirements *(mandatory)*

### Functional Requirements

#### Secret scanning

- **FR-001**: The build MUST run a secret scan on every pull request against the default branch and
  on every push to it, as a step whose failure fails the build.
- **FR-002**: The scan MUST examine the repository's full reachable commit history, not only the
  changes of the pull request.
- **FR-003**: A finding MUST fail the build. There MUST be no mode in which a finding is reported
  and the build still passes.
- **FR-004**: The scan MUST report each finding with its file, its line and the kind of credential
  matched, and MUST NOT reproduce the matched secret value in full in output that is publicly
  readable.
- **FR-005**: The scan MUST read no repository secret and require no token beyond read access to the
  repository's contents, so that it runs unchanged on a pull request from a fork — the property
  `tests/structure/test_ci_workflow.py` already asserts over the workflow MUST continue to hold with
  the new steps present.
- **FR-006**: The scanning tool's version MUST be pinned in the committed configuration, so that a
  build result is attributable to the change under test rather than to an upstream release.
- **FR-007**: The project MUST carry a committed scanner configuration, so that what is scanned and
  what is exempted is reviewable in the repository rather than held in build settings.
- **FR-008**: The configuration MUST exempt the repository's existing deliberate credential-shaped
  test fixtures, and each exemption MUST be scoped to the specific value or path it concerns. A
  blanket exemption — for the tree, for a whole source directory, or for a credential kind
  everywhere — is forbidden.
- **FR-009**: The scan MUST pass over the repository's history as it stands at the commit this
  feature merges into. Merging with a known unaddressed finding behind it is not permitted.
- **FR-010**: The same scan MUST be runnable by a contributor locally with a single documented
  command, producing the same verdict as the build, so that a finding can be reproduced and fixed
  without pushing.
- **FR-011**: The project's documentation MUST state how to run the scan, how to distinguish a real
  finding from a deliberate fixture, what to do in each case, and that a real finding means the
  credential is to be revoked rather than merely deleted from the diff.

#### Image packaging

- **FR-012**: The repository MUST carry a committed definition of a container image for the
  command-line application.
- **FR-013**: The image MUST be built from the interpreter version pinned by the repository and
  install the project's dependencies from the committed lock file, failing rather than re-resolving
  when the lock file disagrees with the project definition.
- **FR-014**: The image's entry point MUST be the command-line application, such that running a
  container with no arguments prints its usage text and exits successfully, and running it with
  arguments passes those arguments to the application.
- **FR-015**: The build MUST build the image on every pull request against the default branch and on
  every push to it, and MUST fail when the image does not build.
- **FR-016**: The build MUST run the built image and assert that the usage text is produced —
  an image that builds but cannot start the application MUST fail the build. The assertion MUST be
  on the content of the output, not on the exit status alone.
- **FR-017**: The image build MUST NOT publish to any registry, MUST read no repository secret, and
  MUST require no credential, so that it too runs on a pull request from a fork.
- **FR-018**: The image MUST NOT contain the repository's development dependencies, its tests, or
  any file under the ignored data directory.
- **FR-019**: The container MUST run as an unprivileged user rather than as root.

#### The command-line surface this feature requires

- **FR-020**: The project MUST expose a command-line entry point that prints usage text describing
  the application and exits successfully when invoked with no arguments or with a help request.
- **FR-021**: That entry point MUST be installed by the project's own packaging, so that the image's
  entry point is the installed application rather than a path into the source tree.
- **FR-022**: This feature MUST NOT add any behavioural command. The entry point exists so that the
  packaging target can be exercised; the commands arrive with the features that have something to
  run.

#### The checks contract

- **FR-023**: The checks contract of `specs/001-project-skeleton/contracts/checks.md` MUST be
  extended with the checks this feature adds, so that the set of commands a contributor runs by hand
  and the set the build runs remain the same set.
- **FR-024**: The automated check that asserts the build runs every command in the contract MUST be
  extended to the new commands, so that removing a step from the build fails the test suite.
- **FR-025**: The new checks MUST NOT modify a tracked file, consistent with the contract's
  no-side-effects guarantee.

### Key Entities

- **Secret scan**: the examination of the repository's content and history for credential-shaped
  values, with a verdict of pass or fail.
- **Finding**: one reported occurrence — its location, the kind of credential matched, and the
  commit it is reachable from.
- **Scanner configuration**: the committed file declaring what is scanned, what is exempted and on
  what grounds.
- **Exemption**: one declared, narrowly scoped statement that a specific credential-shaped value at a
  specific place is deliberate.
- **Image definition**: the committed description from which the container image is built.
- **Image smoke test**: the run of the built image that proves its entry point starts the
  command-line application.
- **Command-line entry point**: the installed application the image runs, whose usage text is what
  the smoke test asserts on.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A pull request that adds a credential of a recognised shape fails the build, verified
  by running the scan over a tree containing such a value and observing a non-zero exit — not by
  assertion.
- **SC-002**: Zero findings are reported over the repository's full history at the commit this
  feature merges into.
- **SC-003**: Zero findings are reported over the repository's existing deliberate credential-shaped
  test fixtures — the false-positive rate on the tree as it stands is zero, so that no contributor
  meets a spurious failure on their first pull request.
- **SC-004**: 100% of the exemptions in the committed configuration are scoped to a specific value or
  path; zero exemptions disable a credential kind across the repository or cover a source directory
  wholesale, verified against the committed configuration.
- **SC-005**: The scanning step adds no more than 2 minutes to the build's wall-clock time on the
  repository's history as it stands.
- **SC-006**: The image builds from a clean checkout with zero manual steps, and a container run from
  it with no arguments prints usage text and exits with status zero.
- **SC-007**: The image contains zero development dependencies, zero test files and zero files from
  the ignored data directory, verified by inspecting the built image.
- **SC-008**: A container run from the image reports a non-root user.
- **SC-009**: Zero repository secrets are referenced by the workflow after this feature — the
  existing fork-safety assertion still passes with the new steps present.
- **SC-010**: 100% of the commands in the checks contract are executed by the build, enforced by the
  existing automated check extended to the new commands.
- **SC-011**: A contributor can reproduce the build's scanning verdict locally with one documented
  command, verified by that command appearing in the checks contract and in the documentation.

## Assumptions

- The technology is not an open question, and no decision record is implied. The constitution's
  Technology Stack fixes Gitleaks for secret scanning, Docker for packaging and Typer for the
  command-line surface, and ADR-004 records the rationale. This specification states the outcomes so
  that the checks stay verifiable; the plan states how they are met with those tools. This is the
  same posture as `specs/003-logging-telemetry-baseline`.
- The scan complements the project's own sanitizer rather than replacing it. ARCHITECTURE.md §13's
  sanitizer protects the corpus on its way to the memory engine; this scan protects the repository.
  Neither substitutes for the other, and this feature does not touch the sanitizer.
- The command-line entry point introduced here is a shell: an application object, its usage text, and
  nothing else. Issue #7's acceptance criterion — an image whose entry point runs the CLI's `--help`
  — cannot be met without one, since `cli` is an empty package today. Fixing the command surface is
  explicitly deferred to the features that have a command to add, per the checks contract of
  feature 001.
- Publishing the image is out of scope. Publishing requires registry credentials, which would make
  the workflow unable to run on a pull request from a fork — the property FR-005 and FR-017 preserve.
  What is proven here is that the image builds and starts; where it is published, and under what
  tags, is a decision for the feature that first needs a published artifact.
- Multi-architecture image builds are out of scope for the same reason of cost against return: the
  MVP runs on a contributor's machine and in the build, both of which are the one architecture.
- A pre-commit hook is out of scope, as the issue records. It protects only the machine that has it
  installed, and this project's own workflow runs from throwaway worktrees where nothing is
  installed. The build is the enforcement point; a hook could be added later as a convenience, not
  as the control.
- Signing the image, generating a software bill of materials, and scanning the image for vulnerable
  packages are out of scope. They are supply-chain concerns worth having once something is published,
  and publishing is out of scope here.
- The historical scan is expected to be fast because the history is short — fewer than ten commits at
  the time of writing. The time budget in SC-005 is stated so that the point at which this stops
  being true is a measurable event rather than a surprise.
- This feature adds no runtime dependency beyond the command-line library the stack table already
  fixes, and the guard test over runtime dependencies is updated in the same commit, deliberately,
  for that entry alone.
- The container image is exercised in the build, which provides a container runtime. A contributor
  without one can still run every other check; the image check is documented as requiring a container
  runtime rather than assumed to be universally runnable.
