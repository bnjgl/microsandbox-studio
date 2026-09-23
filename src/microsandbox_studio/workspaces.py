"""Workspace folders: host folders bind-mounted writable at /workspaces/<name>.

The settings are a list of ``{"source": host path, "target": guest path}``,
the same shape the frontend builds in ``workspaces.js``. Microsandbox cannot
change mounts of an existing sandbox (``modify()`` has no volume options), so
changing them re-creates the sandbox; see ``carryover.with_workspaces()``.
"""

from pathlib import Path, PurePosixPath
from typing import Any

from microsandbox import Volume

from .config import Config
from .config import spec as config_spec

type Folders = list[dict[str, str]]


def is_target(guest: str) -> bool:
    """Whether ``guest`` is a workspace mount point, /workspaces/<name>."""
    path = PurePosixPath(guest)
    return len(path.parts) == 3 and path.parts[:2] == ("/", "workspaces") and path.name != ".."


def normalize(data: Any) -> Folders:
    """Validated folders with resolved host paths."""
    folders: Folders = []
    for folder in data or []:
        source = Path(folder["source"]).resolve(strict=True)
        target = str(PurePosixPath(folder["target"]))
        if not source.is_dir():
            raise ValueError(f"Not a folder: {source}")
        if not is_target(target):
            raise ValueError("Workspace target must be /workspaces/<folder name>.")
        if any(other["target"] == target or other["source"] == str(source) for other in folders):
            raise ValueError("Workspace folders and target paths must be unique.")
        folders.append({"source": str(source), "target": target})
    return folders


def volumes(folders: Folders) -> dict[str, Volume]:
    return {folder["target"]: Volume.bind(folder["source"]) for folder in folders}


def from_config(config: Config) -> Folders:
    """Host folders bound at /workspaces/<name>, in mount order."""
    return [
        {"source": str(mount["host"]), "target": mount["guest"]}
        for mount in config_spec(config).get("mounts") or []
        if mount.get("type") == "Bind" and is_target(mount.get("guest", ""))
    ]
