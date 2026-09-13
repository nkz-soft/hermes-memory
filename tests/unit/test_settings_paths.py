"""Filesystem settings resolve to absolute paths, and loading creates nothing (FR-012, FR-013).

The failure this guards against is quiet: a relative `data/archive` interpreted against the
working directory scatters archives across whichever directory a command happened to be run from,
and Principle I's "the raw archive is the source of truth" becomes several sources of truth.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from hermes_memory.settings import PROJECT_ROOT, SettingsError, load_settings


def test_relative_paths_resolve_against_the_project_root(
    complete_environment: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """FR-013 — the default `data/archive` means one directory, not one per caller."""
    monkeypatch.setenv("HERMES_ARCHIVE_ROOT", "data/archive")

    settings = load_settings(env_file=None)

    assert settings.archive_root.is_absolute()
    assert settings.archive_root == PROJECT_ROOT / "data" / "archive"


def test_resolution_does_not_depend_on_the_working_directory(
    complete_environment: dict[str, str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The same configuration means the same location wherever the command was started."""
    monkeypatch.setenv("HERMES_ARCHIVE_ROOT", "data/archive")

    from_here = load_settings(env_file=None).archive_root

    monkeypatch.chdir(tmp_path)
    from_elsewhere = load_settings(env_file=None).archive_root

    assert from_here == from_elsewhere


def test_absolute_paths_are_preserved(
    complete_environment: dict[str, str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """An operator who names an absolute location gets that location.

    This is what a deployment outside a source checkout uses, where the relative defaults mean
    nothing.
    """
    elsewhere = tmp_path / "archives"
    monkeypatch.setenv("HERMES_ARCHIVE_ROOT", str(elsewhere))

    assert load_settings(env_file=None).archive_root == elsewhere


def test_both_path_settings_are_resolved(
    complete_environment: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The import-state location gets the same treatment as the archive root."""
    monkeypatch.setenv("HERMES_IMPORT_STATE_PATH", "data/import-state.db")

    settings = load_settings(env_file=None)

    assert settings.import_state_path.is_absolute()
    assert settings.import_state_path == PROJECT_ROOT / "data" / "import-state.db"


def test_loading_creates_nothing(
    complete_environment: dict[str, str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """FR-012, SC-007 — the call has no side effects, so it is safe behind `--help`."""
    monkeypatch.setenv("HERMES_ARCHIVE_ROOT", str(tmp_path / "archive"))
    monkeypatch.setenv("HERMES_IMPORT_STATE_PATH", str(tmp_path / "state.db"))
    before = set(os.listdir(tmp_path))

    settings = load_settings(env_file=None)

    assert not settings.archive_root.exists()
    assert not settings.import_state_path.exists()
    assert set(os.listdir(tmp_path)) == before


def test_loading_opens_no_socket(complete_environment: dict[str, str]) -> None:
    """FR-012, SC-007 — a configured endpoint is not contacted while being configured."""
    import socket

    def refuse(*args: object, **kwargs: object):
        raise AssertionError("load_settings() attempted a network connection.")

    original = socket.socket.connect
    socket.socket.connect = refuse  # type: ignore[method-assign]
    try:
        load_settings(env_file=None)
    finally:
        socket.socket.connect = original  # type: ignore[method-assign]


@pytest.mark.parametrize("blank", ["", "   "])
@pytest.mark.parametrize("variable", ["HERMES_ARCHIVE_ROOT", "HERMES_IMPORT_STATE_PATH"])
def test_a_blank_path_is_rejected_not_resolved_to_the_project_root(
    variable: str,
    blank: str,
    complete_environment: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An uncommented-but-unfilled line must not silently mean the repository root.

    `.env.example` ships these two commented out as `#NAME=`, so the likeliest operator mistake is
    uncommenting without filling in. Resolving "" against the project root would put the raw
    archive — Principle I's source of truth — in the checkout, and make the import-state path a
    directory. Blank is rejected here for the same reason it is rejected for the bank id.
    """
    monkeypatch.setenv(variable, blank)

    with pytest.raises(SettingsError) as failure:
        load_settings(env_file=None)

    assert variable in str(failure.value)
