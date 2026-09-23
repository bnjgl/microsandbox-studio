"""Plan host-to-guest copies before touching the sandbox."""

import os
from collections.abc import Iterable, Iterator
from pathlib import Path, PurePosixPath
from typing import NamedTuple


class CopyEntry(NamedTuple):
    source: Path
    guest: str
    is_dir: bool


class Skipped(NamedTuple):
    source: Path


def is_link(path: Path) -> bool:
    # Windows junctions are not symlinks to pathlib but can loop back up the tree.
    return path.is_symlink() or path.is_junction()


def _walk(source: Path, guest: PurePosixPath) -> Iterator[CopyEntry | Skipped]:
    """Entries below ``source`` in copy order, parents before children."""
    if is_link(source):
        yield Skipped(source)
    elif source.is_dir():
        yield CopyEntry(source, str(guest), True)
        for child in sorted(source.iterdir()):
            yield from _walk(child, guest / child.name)
    elif source.is_file():
        yield CopyEntry(source, str(guest), False)
    elif source.exists():
        yield Skipped(source)
    else:
        raise ValueError(f"Source no longer exists: {source}")


def _roots(paths: Iterable[str], target: PurePosixPath) -> Iterator[tuple[Path, PurePosixPath]]:
    """Selected sources with their guest path; their names must differ."""
    names: set[str] = set()
    for value in dict.fromkeys(paths):
        source = Path(os.path.abspath(value))
        if not source.name or source.name in names:
            raise ValueError("Please select sources with different names; the root directory is not allowed.")
        names.add(source.name)
        yield source, target / source.name


def copy_plan(paths: list[str], destination: str) -> tuple[list[CopyEntry], int]:
    """Walk the selected sources. Returns the entries in copy order and the number of skipped links/special files."""
    target = PurePosixPath(destination)
    if not destination.startswith("/") or ".." in target.parts or "\0" in destination:
        raise ValueError("Please enter an absolute destination folder without '..', e.g. /uploads.")
    if not paths:
        raise ValueError("Please select files or folders.")
    walked = [item for source, guest in _roots(paths, target) for item in _walk(source, guest)]
    entries = [item for item in walked if isinstance(item, CopyEntry)]
    return entries, len(walked) - len(entries)


def top_level_targets(entries: Iterable[CopyEntry], destination: str) -> list[str]:
    """Guest paths of the selected sources themselves, e.g. /uploads/project."""
    root = PurePosixPath(destination)
    return list(dict.fromkeys(str(root / PurePosixPath(entry.guest).relative_to(root).parts[0]) for entry in entries))
