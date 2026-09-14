# The packaging target ADR-004 fixes, built on every pull request so that it is exercised rather
# than assumed. See specs/004-ci-scanning-packaging/ — research R9 for the two-stage shape, R10 for
# the entry point, and contracts/checks.md for what CI asserts about the result.
#
# Nothing here is published. The image is built and run; where it is published, and under what
# tags, belongs to the feature that first needs a published artifact — and a registry credential
# would end this workflow's ability to run on a pull request from a fork.

# --- builder -----------------------------------------------------------------------------------
# The interpreter comes from the base image's tag, not from .python-version — that file is not in
# the build context. What keeps the two in step is a test: every stage naming a Python version is
# asserted to carry the pin .python-version holds. An image built on a different interpreter than
# the checks ran under proves nothing about what ships.
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

# Only what the install needs. README.md is here because the project metadata names it as the
# readme, and the build back end reads it.
COPY pyproject.toml uv.lock README.md ./
COPY src ./src

# --locked refuses to re-resolve, so the image cannot ship a dependency set the tests never ran
# against — the same guarantee CI's own `uv sync --locked` gives. --no-dev keeps pytest and ruff
# out of the artifact at the source rather than by deleting them afterwards. --no-editable installs
# the project as a real package, so the console script does not point back into a source tree the
# runtime stage below does not carry.
RUN uv sync --locked --no-dev --no-editable

# --- runtime -----------------------------------------------------------------------------------
FROM python:3.13-slim-bookworm AS runtime

# An unprivileged user, created before the copy so the virtual environment can be owned by it.
RUN useradd --create-home --uid 10001 hermes

COPY --from=builder --chown=hermes:hermes /app/.venv /app/.venv

ENV PATH="/app/.venv/bin:$PATH"

USER hermes
WORKDIR /app

# ENTRYPOINT plus a default CMD resolves both halves of FR-014 at once. `docker run <image>` runs
# `hermes-memory --help`: usage text, exit 0 — issue #7's acceptance criterion. `docker run <image>
# <args>` replaces the default argument list, so arguments reach the application rather than a
# shell. The exec form keeps a shell out of it entirely.
#
# --help is the default rather than relying on the no-argument behaviour because the exit status of
# a command group invoked with no arguments has differed between releases of the underlying
# argument parser, while --help is specified to exit 0.
ENTRYPOINT ["hermes-memory"]
CMD ["--help"]
