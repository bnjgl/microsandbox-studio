from pathlib import Path, PurePosixPath
from typing import Any

from microsandbox import Volume

from .config import StoredConfig


def is_target(guest: str) -> bool:
    path = PurePosixPath(guest)
    return len(path.parts) == 3 and path.parts[:2] == ("/", "workspaces") and path.name != ".."


def with_targets(sources: list[str]) -> list[dict[str, str]]:
    folders: list[dict[str, str]] = []
    for source in sources:
        name = Path(source).name or "workspace"
        target, suffix = f"/workspaces/{name}", 2
        while any(folder["target"] == target for folder in folders):
            target, suffix = f"/workspaces/{name}-{suffix}", suffix + 1
        folders.append({"source": source, "target": target})
    return folders


def volumes(sources: list[str]) -> dict[str, Volume]:
    return {folder["target"]: Volume.bind(folder["source"]) for folder in with_targets(sources)}


def from_config(stored: StoredConfig) -> list[dict[str, Any]]:
    return [
        {"source": mount.host, "target": mount.guest}
        for mount in stored.mounts
        if mount.type == "Bind" and is_target(mount.guest)
    ]
