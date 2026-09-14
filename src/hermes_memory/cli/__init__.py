"""Command-line surface: the way the MVP is driven.

This is deliberately a shell. 004-ci-scanning-packaging needed an installed application for the
container image's entry point to start — the packaging target of ADR-004 cannot be exercised
without one — and needed nothing else. Feature 001's checks contract said the Typer application
"arrives with the feature that has something to run", and that still holds: the commands belong to
the features that specify them, each with its own specification.

`tests/unit/test_cli.py` asserts that no command has been registered. If that test fails because a
command was added, the question is which specification designed it.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

import typer

app = typer.Typer(
    name="hermes-memory",
    help="Engineering memory: private conversation history, retained and recallable.",
    no_args_is_help=True,
    add_completion=False,
)


def _version() -> str:
    """The installed distribution's version, or a marker when running from an unbuilt tree."""
    try:
        return version("hermes-memory")
    except PackageNotFoundError:  # pragma: no cover - only outside an installed environment
        return "unknown"


def _print_version(value: bool) -> None:
    if value:
        typer.echo(f"hermes-memory {_version()}")
        raise typer.Exit


@app.callback()
def main_callback(
    _version_flag: bool = typer.Option(
        False,
        "--version",
        callback=_print_version,
        is_eager=True,
        help="Show the installed version and exit.",
    ),
) -> None:
    """Engineering memory: private conversation history, retained and recallable."""


def main() -> None:
    """The console-script entry point declared in `pyproject.toml`."""
    app()
