"""The command-line entry point is a shell, and prints its usage.

004-ci-scanning-packaging added this entry point for one reason: the container image's entry point
must be the installed application, and the packaging target cannot be exercised without one. It is
deliberately empty of behaviour. Feature 001 said the Typer application "arrives with the feature
that has something to run", and that remains true — this feature has something to *package*, not
something to run.

So there are two checks here, and the second matters more than it looks. One proves the usage text
exists, which is what the image's smoke test asserts on. The other proves no command has been
added, which is what keeps a packaging detail from quietly becoming the project's command surface
before any specification has designed it (FR-022).
"""

from __future__ import annotations

from typer.testing import CliRunner

from hermes_memory.cli import app

runner = CliRunner()


def test_help_exits_zero_and_names_the_application() -> None:
    """`--help` prints usage and succeeds (check P2, FR-020).

    This is the assertion the image's smoke test mirrors. `--help` is used rather than a bare
    invocation on purpose: the exit status of a group invoked with no arguments has varied between
    releases of the underlying argument parser, while `--help` is specified to exit 0
    (specs/004-ci-scanning-packaging/research.md R10).
    """
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0, f"`--help` exited {result.exit_code}:\n{result.output}"
    assert "Usage:" in result.output, f"`--help` printed no usage text:\n{result.output}"
    assert "hermes-memory" in result.output.lower().replace("_", "-"), (
        f"The usage text does not name the application:\n{result.output}"
    )


def test_no_behavioural_command_is_registered() -> None:
    """The application registers no command (check P3, FR-022).

    The entry point exists so the packaging target can be exercised. Commands arrive with the
    features that have something to run, each with its own specification. If this test fails
    because a command was added, the question to answer is which specification designed it — not
    whether to update the assertion.
    """
    assert app.registered_commands == [], (
        f"The CLI registers commands {[c.name for c in app.registered_commands]!r}. This entry "
        "point is a packaging shell; a command belongs to the feature that specifies it."
    )
