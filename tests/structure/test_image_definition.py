"""The `Dockerfile` and `.dockerignore` keep the promises `contracts/checks.md` makes about them.

An image cannot be unit-tested — the honest proof is C6 and C7, which build it and run it. What is
asserted here is the set of properties that rot silently between builds: that the image is still
built on the interpreter the tests ran on, that it still installs from the lock file, that it still
does not ship the development dependencies or the tests, that it still runs as a real user, and
that its entry point is still the installed application rather than something that merely exits 0.

The file is parsed into instructions rather than searched as text, for the reason
`test_ci_workflow.py` records: this file's own comments contain most of the strings being looked
for, and a check a comment can satisfy is not a check.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCKERFILE = REPO_ROOT / "Dockerfile"
DOCKERIGNORE = REPO_ROOT / ".dockerignore"
PYTHON_VERSION_FILE = REPO_ROOT / ".python-version"

CONSOLE_SCRIPT = "hermes-memory"


def _instructions() -> list[tuple[str, str]]:
    """The Dockerfile as (instruction, argument) pairs, comments and continuations resolved."""
    assert DOCKERFILE.exists(), "The image definition is missing at Dockerfile."

    text = DOCKERFILE.read_text(encoding="utf-8")
    text = re.sub(r"\\\r?\n", " ", text)  # join continued lines before splitting

    parsed: list[tuple[str, str]] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        instruction, _, argument = stripped.partition(" ")
        parsed.append((instruction.upper(), argument.strip()))

    assert parsed, "The Dockerfile contains no instructions."
    return parsed


def _arguments(instruction: str) -> list[str]:
    return [argument for name, argument in _instructions() if name == instruction]


def test_the_image_is_defined() -> None:
    """A Dockerfile exists at the repository root (check I1, FR-012)."""
    assert DOCKERFILE.exists(), (
        "There is no Dockerfile. ADR-004 fixes Docker as the packaging target, and an unexercised "
        "packaging target is discovered broken at the moment someone first needs it."
    )


def test_the_runtime_interpreter_matches_the_repository_pin() -> None:
    """The image is built on the interpreter the tests ran on (check I2, FR-013).

    A packaging target built on a different interpreter than CI tested proves nothing about what
    ships. The pin is read from `.python-version`, the same file a contributor's uv reads.
    """
    pin = PYTHON_VERSION_FILE.read_text(encoding="utf-8").strip()
    bases = _arguments("FROM")

    assert bases, "The Dockerfile declares no FROM instruction."

    # Every stage naming a Python version, not only the last. A builder pinned to a different minor
    # version produces a virtual environment whose interpreter does not exist in the runtime stage:
    # C7 would catch it, but only after a build that should never have been attempted.
    versioned = [base for base in bases if re.search(r"python:?3\.\d+", base)]
    assert versioned, f"No stage names a Python version: {bases}."

    mismatched = [base for base in versioned if pin not in base]
    assert not mismatched, (
        f"These stages are built on {mismatched}, which do not carry the interpreter pinned in "
        f".python-version ({pin}). The image would ship a different runtime than the one every "
        "check ran on."
    )


def test_dependencies_are_installed_from_the_lock_file_without_dev_extras() -> None:
    """The build installs with `--locked` and `--no-dev` (check I3, FR-013, FR-018).

    `--locked` refuses to re-resolve, so the image cannot ship a dependency set the tests never
    ran against. `--no-dev` is what makes "no development dependencies in the image" true at the
    source rather than by deleting things afterwards.
    """
    syncs = [argument for argument in _arguments("RUN") if "uv sync" in argument]

    assert syncs, "No RUN instruction installs the environment with `uv sync`."
    for sync in syncs:
        assert "--locked" in sync, (
            f"A `uv sync` in the image omits --locked: {sync!r}. The image could then ship "
            "dependencies that disagree with uv.lock."
        )
        assert "--no-dev" in sync, (
            f"A `uv sync` in the image omits --no-dev: {sync!r}. pytest and ruff would ship "
            "inside the published artifact."
        )


def test_the_entry_point_is_the_application_with_help_as_its_default() -> None:
    """`ENTRYPOINT` is the console script and `CMD` is `--help` (check I4, FR-014).

    Together these resolve both halves of FR-014: running the image with no arguments prints usage
    and exits 0, and running it with arguments passes them to the application rather than to a
    shell. The exec form matters — a shell form would put argument quoting and signal handling in
    a shell's hands (research R10).
    """
    entrypoints = _arguments("ENTRYPOINT")
    commands = _arguments("CMD")

    assert entrypoints, "The image declares no ENTRYPOINT, so `docker run` would start a shell."
    entrypoint = entrypoints[-1]

    assert entrypoint.startswith("["), (
        f"ENTRYPOINT {entrypoint!r} is not in exec form. In shell form the arguments a caller "
        "passes are interpreted by a shell instead of reaching the application."
    )
    assert CONSOLE_SCRIPT in entrypoint, (
        f"ENTRYPOINT {entrypoint!r} does not start the installed console script {CONSOLE_SCRIPT!r}."
    )

    assert commands, (
        "The image declares no CMD. Without `--help` as the default argument, running the image "
        "with no arguments depends on the argument parser's no-args exit status, which has "
        "differed between releases."
    )
    assert "--help" in commands[-1], (
        f"CMD {commands[-1]!r} is not `--help`. Issue #7's acceptance criterion is an image whose "
        "entry point runs the CLI's --help."
    )


def test_the_container_does_not_run_as_root() -> None:
    """A non-root USER is selected, and nothing switches back (check I5, FR-019)."""
    users = _arguments("USER")

    assert users, "The image declares no USER, so the container runs as root."
    assert users[-1].split(":")[0] not in ("root", "0"), (
        f"The image's final USER is {users[-1]!r}. The container must run unprivileged."
    )


def test_the_build_context_excludes_what_must_not_ship() -> None:
    """`.dockerignore` excludes the repository's history, tests, specs and data (check I6).

    `data/` is the one that matters beyond image size: it is where conversation exports live, it is
    untracked, and it must never reach a built artifact (constitution, Principle I and V).
    """
    assert DOCKERIGNORE.exists(), (
        "There is no .dockerignore, so the whole working tree — including data/ — is sent to the "
        "build daemon as context."
    )

    entries = {
        line.strip().rstrip("/")
        for line in DOCKERIGNORE.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    }
    missing = [
        required for required in (".git", "tests", "specs", "data") if required not in entries
    ]

    assert not missing, (
        f".dockerignore does not exclude {missing}. Everything not excluded is sent to the build "
        "daemon and can end up in the image."
    )
