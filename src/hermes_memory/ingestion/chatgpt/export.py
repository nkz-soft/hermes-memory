"""Where a ChatGPT export keeps its conversations, and how they are opened (research R2).

An export arrives as the archive the person downloaded, the directory it was extracted into, or the
conversations file on its own. All three are read in place: an archive is streamed member by member
rather than extracted, so no copy of private history is left in a temporary directory.

The conversations are in `conversations.json`, or — in an export split into parts — in
`conversations-000.json`, `conversations-001.json` and so on. An export holding both forms is
refused rather than guessed at, because nothing says which one is authoritative.
"""

from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path
from typing import TextIO

from hermes_memory.ingestion.source import SourceFormatError, SourceUnavailable

__all__ = ["Export"]

SINGLE = "conversations.json"
_SPLIT = re.compile(r"^conversations-(\d+)\.json$")


def _conversation_files(names: list[str]) -> tuple[str, ...]:
    split = sorted((int(match.group(1)), name) for name in names if (match := _SPLIT.match(name)))
    single = SINGLE in names
    if single and split:
        raise SourceFormatError(
            "the export holds both conversations.json and split conversation files"
        )
    if single:
        return (SINGLE,)
    if split:
        return tuple(name for _, name in split)
    raise SourceFormatError("the export holds no conversations file")


class Export:
    """An opened export: the names of its conversation files, and a way to read each.

    Opening fails fast. A path that cannot be reached is `SourceUnavailable`, which is retryable; a
    path that is reachable but is not an export is `SourceFormatError`, which is not.

    Every file is opened with `newline=""`, so that line endings reach the scanner as written and a
    conversation's original is the export's own text, not a translation of it.
    """

    def __init__(self, path: Path) -> None:
        self._directory: Path | None = None
        self._archive: zipfile.ZipFile | None = None
        try:
            is_directory = path.is_dir()
            path.stat()
        except OSError as unreachable:
            raise SourceUnavailable("the export could not be reached") from unreachable

        if is_directory:
            self._directory = path
            self.names = _conversation_files(self._listing(path))
        elif path.suffix.lower() == ".json":
            self._directory = path.parent
            self.names = (path.name,)
        elif path.suffix.lower() == ".zip" or zipfile.is_zipfile(path):
            self._archive = self._open_archive(path)
            try:
                self.names = _conversation_files(self._archive.namelist())
            except SourceFormatError:
                self.close()
                raise
        else:
            raise SourceFormatError("the export is neither an archive, a directory nor a JSON file")

    @staticmethod
    def _listing(directory: Path) -> list[str]:
        try:
            return [entry.name for entry in directory.iterdir() if entry.is_file()]
        except OSError as unreachable:
            raise SourceUnavailable("the export directory could not be listed") from unreachable

    @staticmethod
    def _open_archive(path: Path) -> zipfile.ZipFile:
        try:
            return zipfile.ZipFile(path)
        except zipfile.BadZipFile as corrupt:
            raise SourceFormatError("the export archive is not a readable zip file") from corrupt
        except OSError as unreachable:
            raise SourceUnavailable("the export archive could not be opened") from unreachable

    def open(self, name: str) -> TextIO:
        """Open one conversation file as UTF-8 text, exactly as written."""
        try:
            if self._archive is not None:
                return io.TextIOWrapper(self._archive.open(name), encoding="utf-8", newline="")
            assert self._directory is not None
            return (self._directory / name).open(encoding="utf-8", newline="")
        except (OSError, zipfile.BadZipFile) as unreachable:
            raise SourceUnavailable("a conversations file could not be opened") from unreachable

    def close(self) -> None:
        if self._archive is not None:
            self._archive.close()
            self._archive = None

    def __enter__(self) -> Export:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
