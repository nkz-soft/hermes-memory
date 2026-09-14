"""The CI workflow keeps the promises `contracts/checks.md` makes about it.

CI cannot be unit-tested — the only honest proof that it reports is a pull request that runs it.
What can be asserted here is the set of properties that rot silently: that it is still valid YAML
GitHub will actually run, that it still runs every check in the contract *as a command*, that
`uv sync` still carries `--locked`, and that it still needs no secret and therefore still runs on
pull requests from forks.

004-ci-scanning-packaging added the scanning and image jobs and their checks. Two of those deserve
naming here, because both guard against a green tick over nothing: `fetch-depth: 0`, without which
the history scan examines a single commit; and the negative control, without which no evidence
exists that the scan can fail at all.

The workflow is parsed as YAML rather than matched as text. An earlier version of this file did
match text, and a code review demonstrated the consequence: a workflow with no steps at all
satisfied every assertion, because `ci.yml`'s own comments contain the strings being searched for,
and so did a workflow with deliberately invalid YAML appended. A check a comment can satisfy is
not a check. PyYAML is a development dependency only — FR-011 forbids adding a *runtime*
dependency, and this is in the same group as pytest and ruff.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"


def _workflow() -> dict[str, Any]:
    """The parsed workflow. Fails if it is not valid YAML — GitHub would silently not run it."""
    assert WORKFLOW.exists(), f"The CI workflow is missing at {WORKFLOW.relative_to(REPO_ROOT)}."

    try:
        document = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    except yaml.YAMLError as error:  # pragma: no cover - only on a broken workflow
        raise AssertionError(
            f".github/workflows/ci.yml is not valid YAML, so GitHub will not run it: {error}"
        ) from error

    assert isinstance(document, dict), "The workflow did not parse to a mapping."
    return document


def _triggers(document: dict[str, Any]) -> dict[str, Any]:
    """The `on:` block. PyYAML resolves the bare key `on` to the boolean True (YAML 1.1)."""
    triggers = document.get("on", document.get(True))
    assert isinstance(triggers, dict), "The workflow declares no triggers."
    return triggers


def _run_commands(document: dict[str, Any], job_name: str | None = None) -> list[str]:
    """Every `run:` script in the workflow — the commands GitHub will actually execute.

    Comments and step names are excluded by construction, which is the point: only a real
    command satisfies the assertions below.

    With ``job_name``, only that job's scripts are returned. Asserting against the whole workflow
    would let a command in any job satisfy a claim about a specific one — and the scanning and
    image jobs each have properties the other must not be able to vouch for.
    """
    commands: list[str] = []
    jobs = document.get("jobs", {})

    if job_name is not None:
        jobs = {job_name: _job(document, job_name)}

    for job in jobs.values():
        for step in job.get("steps", []):
            script = step.get("run")
            if script:
                commands.append(script)

    return commands


def _job(document: dict[str, Any], name: str) -> dict[str, Any]:
    """One named job. Fails with the jobs that do exist, which is the useful message."""
    jobs = document.get("jobs", {})
    assert name in jobs, f"The workflow declares no job named {name!r}. It has: {sorted(jobs)}."

    job = jobs[name]
    assert isinstance(job, dict), f"Job {name!r} did not parse to a mapping."
    return job


def _step_using(document: dict[str, Any], job_name: str, action: str) -> dict[str, Any]:
    """The first step of a job whose `uses:` names ``action``, with its parsed inputs.

    Addressing the step rather than the file is what makes an assertion about `with:` mean
    something: a `fetch-depth: 0` anywhere in the file would otherwise satisfy a claim about the
    scanning job's checkout specifically.
    """
    for step in _job(document, job_name).get("steps", []):
        uses = step.get("uses", "")
        if uses.startswith(action):
            return step

    raise AssertionError(f"Job {job_name!r} has no step using {action!r}.")


def _executes(scripts: str, command: str | re.Pattern[str]) -> bool:
    """Whether the joined scripts run ``command`` — a literal, or a pattern where the version pin
    sits between the tool's name and its subcommand."""
    if isinstance(command, re.Pattern):
        return command.search(scripts) is not None
    return command in scripts


# The scanner is invoked through its pinned image, so the tag sits between the tool's name and its
# subcommand: `…/gitleaks:v8.30.1 git .`. Matching the literal "gitleaks git" would never hit.
HISTORY_SCAN = re.compile(r"gitleaks:\S+\s+git\b")


def test_runs_on_pull_requests_to_main() -> None:
    """Every pull request against main is checked automatically (FR-008).

    The branch list is read from inside the `pull_request` trigger specifically. Searching the
    whole file would be satisfied by the `push` trigger's identical branch list, and the
    pull-request trigger could be repointed elsewhere without this failing.
    """
    triggers = _triggers(_workflow())

    assert "pull_request" in triggers, "The workflow does not trigger on pull requests."

    branches = (triggers["pull_request"] or {}).get("branches")
    assert branches == ["main"], (
        f"The pull_request trigger targets {branches!r}, not ['main']. "
        "Pull requests against the default branch would go unchecked."
    )


def test_runs_every_check_in_the_contract() -> None:
    """All seven checks of contracts/checks.md run in CI as commands, not a subset.

    Each is looked for in the job that owns it. Searching the whole workflow would let the
    scanning job's `docker run` satisfy the claim that the image is smoke-tested — two different
    checks that happen to start with the same word.
    """
    document = _workflow()
    checks: dict[str, tuple[str, str | re.Pattern[str]]] = {
        "C1 environment install": ("checks", "uv sync"),
        "C2 lint": ("checks", "ruff check"),
        "C3 format": ("checks", "ruff format --check"),
        "C4 tests": ("checks", "pytest"),
        "C5 secret scan": ("scan", HISTORY_SCAN),
        "C6 image build": ("image", "docker build"),
        "C7 image smoke test": ("image", "docker run"),
    }

    missing = [
        name
        for name, (job, command) in checks.items()
        if not _executes(" \n".join(_run_commands(document, job)), command)
    ]

    assert not missing, (
        f"No `run:` step in the owning job executes these checks from contracts/checks.md: "
        f"{missing}. A check that runs only locally is a check that stops running."
    )


def test_install_is_locked() -> None:
    """CI installs from the committed lock file rather than re-resolving (FR-009).

    Without --locked, CI can quietly resolve a different dependency set than a contributor has,
    and a local pass and a CI pass stop meaning the same thing.
    """
    scripts = _run_commands(_workflow())
    syncs = [script for script in scripts if "uv sync" in script]

    assert syncs, "No `run:` step installs the environment with `uv sync`."
    assert all("--locked" in script for script in syncs), (
        f"A `uv sync` step omits --locked: {syncs}. It may re-resolve dependencies instead of "
        "failing when uv.lock disagrees with pyproject.toml."
    )


def test_needs_no_secrets_so_forks_can_run_it() -> None:
    """The workflow reads no secret and asks for no write access (Principle V).

    This is what lets it run unchanged on a pull request from a fork, and it is the property
    most likely to be lost by accident when a later step is added.
    """
    document = _workflow()

    assert "secrets." not in WORKFLOW.read_text(encoding="utf-8"), (
        "The workflow references a repository secret. None of the four checks needs one, "
        "and requiring one stops the workflow running on pull requests from forks."
    )
    assert document.get("permissions") == {"contents": "read"}, (
        f"The workflow declares permissions {document.get('permissions')!r}, "
        "expected {'contents': 'read'}. It only reads the repository; say so rather than "
        "inheriting the default token scope."
    )


# --- The secret scan (004-ci-scanning-packaging, checks S1-S4 and S9) -------------------------

SCANNER_IMAGE = re.compile(r"ghcr\.io/gitleaks/gitleaks:(\S+)")
EXACT_VERSION = re.compile(r"^v\d+\.\d+\.\d+$")
NEGATIVE_CONTROL = "tests/fixtures/secret_scanning"


def _scan_scripts() -> str:
    """Every `run:` script in the scanning job, joined."""
    return " \n".join(_run_commands(_workflow(), "scan"))


def test_the_scan_runs_as_a_command() -> None:
    """The scanner runs over the history, as a command, in its own job (check S1)."""
    assert HISTORY_SCAN.search(_scan_scripts()), (
        "No `run:` step in the `scan` job runs a history scan. A scanning job that does not "
        "scan is the failure this whole feature exists to prevent."
    )


def test_the_scanner_is_pinned_to_an_exact_version() -> None:
    """The scanner is pinned to `vX.Y.Z` (check S2, FR-006).

    With a floating tag the build's verdict becomes a function of an upstream release rather than
    of the change under test — and a contributor cannot tell that from a real finding.
    """
    tags = SCANNER_IMAGE.findall(_scan_scripts())

    assert tags, "The scanning job references no scanner image."

    floating = [tag for tag in tags if not EXACT_VERSION.match(tag)]
    assert not floating, (
        f"The scanner is referenced by these non-exact tags: {floating}. Pin `vX.Y.Z`, so that a "
        "build result is attributable to the change under test."
    )


def test_the_scan_reports_location_without_publishing_the_secret() -> None:
    """The history scan carries both `-v` and `--redact` (check S3, FR-004).

    The two pull in opposite directions and both are required. Without `-v` the output names no
    file, line or rule and a contributor cannot act on the failure. Without `--redact` the matched
    secret is printed into a build log that is public on a public repository — which would make the
    scanning step itself a disclosure channel.
    """
    history_scans = [
        script for script in _run_commands(_workflow(), "scan") if HISTORY_SCAN.search(script)
    ]

    assert history_scans, "No history scan command found in the `scan` job."

    for script in history_scans:
        assert " -v" in script or "--verbose" in script, (
            f"A history scan omits `-v`, so a finding would report no file, line or rule: {script}"
        )
        assert "--redact" in script, (
            f"A history scan omits `--redact`, so a finding would print the secret into a public "
            f"build log: {script}"
        )


def test_the_scan_fetches_the_whole_history() -> None:
    """The scanning job's checkout sets `fetch-depth: 0` (check S4, FR-002).

    This is the single most likely way for the feature to ship broken while appearing to work.
    `actions/checkout` fetches one commit by default, and a history scan over one commit passes
    vacuously — a green tick over a repository nobody looked at.

    Asserted against that step's own `with:` mapping: a `fetch-depth` anywhere else in the file
    must not be able to satisfy it.
    """
    checkout = _step_using(_workflow(), "scan", "actions/checkout")
    depth = (checkout.get("with") or {}).get("fetch-depth")

    assert depth == 0, (
        f"The scanning job's checkout sets fetch-depth {depth!r}, expected 0. Without the full "
        "history the scan examines a single commit and passes without looking at anything."
    )


def test_the_scan_is_proven_able_to_fail() -> None:
    """The job scans the negative-control fixture and requires that scan to fail (check S9).

    A check never observed failing is not known to work, and an exemption one character too broad
    is invisible under a green tick. So a fixture that must be found is committed, and the job
    fails when scanning it succeeds.
    """
    controls = [
        script for script in _run_commands(_workflow(), "scan") if NEGATIVE_CONTROL in script
    ]

    assert controls, (
        f"No `run:` step in the `scan` job scans {NEGATIVE_CONTROL}. Without the negative control "
        "nothing proves the scanning step can fail at all."
    )
    assert any("exit 1" in script for script in controls), (
        "The negative control does not fail the job when the scan finds nothing. It must invert "
        "the scanner's status: a clean result there means the check has stopped working."
    )


# --- The image (004-ci-scanning-packaging, checks I7-I9) ---------------------------------------

REGISTRY_WRITES = ("docker push", "docker login", "docker/login-action")


def _image_scripts() -> str:
    """Every `run:` script in the image job, joined."""
    return " \n".join(_run_commands(_workflow(), "image"))


def test_the_image_is_built() -> None:
    """The image is built on every run, as a command (check I7, FR-015)."""
    assert "docker build" in _image_scripts(), (
        "No `run:` step in the `image` job builds the image. An unexercised packaging target is "
        "discovered broken at the moment someone first needs it."
    )


def test_the_image_is_run_and_its_output_asserted() -> None:
    """The built image is run and its **output** checked (check I8, FR-016).

    An entry point that exits 0 having printed nothing satisfies a status check while failing the
    thing this check exists for. So the job must match the usage text, not merely succeed.
    """
    scripts = _image_scripts()

    assert "docker run" in scripts, "The `image` job builds the image but never runs it."
    assert "Usage:" in scripts, (
        "The `image` job does not match the application's usage text. Exit status alone is "
        "satisfied by an entry point that prints nothing at all, and a `grep` for some other "
        "string would satisfy a looser assertion than this one."
    )


def test_the_image_is_never_published() -> None:
    """Nothing is pushed and no registry is logged into (check I9, FR-017).

    Publishing needs registry credentials, and a job that needs a secret stops running on pull
    requests from forks — which is the property the whole workflow is built around.
    """
    job_text = str(_job(_workflow(), "image"))
    offenders = [write for write in REGISTRY_WRITES if write in job_text]

    assert not offenders, (
        f"The image job contains {offenders}. Publishing requires credentials, which would end "
        "this workflow's ability to run on a pull request from a fork."
    )
