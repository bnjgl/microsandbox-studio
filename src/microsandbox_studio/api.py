import asyncio
import base64
import functools
from collections.abc import Callable, Coroutine
from pathlib import Path, PurePosixPath
from typing import Any

import webview
from microsandbox import Image, ModificationPolicy, Sandbox, SandboxStatus, Snapshot, resolve_runtime
from microsandbox.errors import ImageNotFoundError
from pydantic import ValidationError

from . import environment, network, ssh, workspaces
from .config import StoredConfig
from .models import FOLDERS, EnvironmentSettings, NewSandbox, Resources, SandboxSettings, is_ssh_name

MAX_SANDBOXES = 100


def async_to_sync[**P, R](method: Callable[P, Coroutine[Any, Any, R]]) -> Callable[P, R]:
    @functools.wraps(method)
    def run(*args: P.args, **kwargs: P.kwargs) -> R:
        return asyncio.run(method(*args, **kwargs))

    return run


class Api:
    def __init__(self) -> None:
        self._window: Any = None

    @async_to_sync
    async def list_sandboxes(self) -> dict[str, Any]:
        return {"sandboxes": await self._cards(), "limit": MAX_SANDBOXES}

    @async_to_sync
    async def create_sandbox(self, sandbox: dict[str, Any]) -> None:
        new = NewSandbox.model_validate(sandbox)
        volumes = workspaces.volumes(new.folders)
        await Sandbox.create(
            new.name,
            image=new.image,
            cpus=new.cpus,
            memory=new.memory,
            volumes=volumes,
            workdir=next(iter(volumes), None),
            network=network.sdk(new.network),
            labels={network.MODE_LABEL: new.network.mode},
            intercept_tls=bool(new.environment.secrets),
            env=new.environment.env,
            secrets=environment.create_secrets(new.environment),
            detached=True,
        )

    @async_to_sync
    async def restore_snapshot(self, reference: str, sandbox: dict[str, Any]) -> None:
        new = SandboxSettings.model_validate(sandbox)
        volumes = workspaces.volumes(new.folders)
        sdk_network = network.sdk(new.network)
        await Sandbox.restore(
            reference,
            name=new.name,
            cpus=new.cpus,
            memory=new.memory,
            network_policy=sdk_network.policy,
            ports=sdk_network.ports,
            volumes=volumes,
            allow_missing_resources=True,
        )
        await self._modify(
            new.name,
            labels={network.MODE_LABEL: new.network.mode},
            workdir=next(iter(volumes), None),
            **await self._environment_patch(new.name, new.environment),
        )

    @async_to_sync
    async def take_snapshot(self, name: str) -> None:
        await Snapshot.create(from_sandbox=name)

    @async_to_sync
    async def delete_snapshot(self, name: str, reference: str) -> None:
        await self._remove_snapshot(name, reference)

    @async_to_sync
    async def upload_file(self, name: str, folder: str, filename: str, data: str) -> None:
        sandbox = await (await Sandbox.get(name)).connect()
        await sandbox.fs.mkdir(folder)
        await sandbox.fs.write(str(PurePosixPath(folder, filename)), base64.b64decode(data))

    @async_to_sync
    async def start_sandbox(self, name: str) -> None:
        if (await Sandbox.get(name)).status != SandboxStatus.RUNNING:
            await Sandbox.start(name, detached=True)

    @async_to_sync
    async def stop_sandbox(self, name: str) -> None:
        await self._stop(name)

    @async_to_sync
    async def delete_sandbox(self, name: str) -> None:
        await self._stop(name)
        await (await Sandbox.get(name)).destroy()
        for snapshot in await Snapshot.list():
            if snapshot.group == name:
                await self._remove_snapshot(name, snapshot.reference)

    @async_to_sync
    async def save_resources(self, name: str, cpus: int, memory: int) -> None:
        await self._modify(name, **Resources(cpus=cpus, memory=memory).model_dump())

    @async_to_sync
    async def get_environment(self, name: str) -> dict[str, Any]:
        stored = await self._stored(name)
        settings = environment.from_config(stored, await self._image_env(stored, {}))
        return settings.model_dump()

    @async_to_sync
    async def save_environment(self, name: str, settings: dict[str, Any]) -> None:
        patch = await self._environment_patch(name, EnvironmentSettings.model_validate(settings))
        if any(patch.values()):
            await self._modify(name, **patch)

    @async_to_sync
    async def get_ssh(self) -> dict[str, Any]:
        paths = self._ssh_paths()
        return {
            "on": ssh.is_set_up(paths),
            "included": ssh.is_included(paths),
            "include": ssh.INCLUDE,
            "config": str(paths.user_config),
        }

    @async_to_sync
    async def set_up_ssh(self) -> None:
        names = [card["name"] for card in await self._cards() if card.get("host")]
        ssh.set_up(self._ssh_paths(), names)

    @async_to_sync
    async def remove_ssh(self) -> None:
        ssh.remove(self._ssh_paths())

    @async_to_sync
    async def select_workspace_folders(self, folders: list[str]) -> list[dict[str, str]]:
        picked = self._window.create_file_dialog(webview.FileDialog.FOLDER, allow_multiple=True) or ()
        return workspaces.with_targets(FOLDERS.validate_python([*folders, *picked]))

    async def _cards(self) -> list[dict[str, Any]]:
        handles = (await Sandbox.list_with(limit=MAX_SANDBOXES)).sandboxes
        images: dict[str, dict[str, str]] = {}
        snapshots = sorted(await Snapshot.list(), key=lambda item: item.created_at, reverse=True)
        cards = sorted(
            [await self._card(handle, images, snapshots) for handle in handles], key=lambda item: item["name"].lower()
        )
        ssh.write_config(self._ssh_paths(), [card["name"] for card in cards if card.get("host")])
        return cards

    async def _card(self, handle: Any, images: dict[str, dict[str, str]], snapshots: list[Any]) -> dict[str, Any]:
        try:
            stored = StoredConfig.model_validate_json(handle.config_json)
        except ValidationError:
            problem = "Microsandbox Studio cannot read this sandbox's configuration."
            return {"name": handle.name, "status": handle.status.value, "image": "—", "problem": problem}
        return {
            "name": handle.name,
            "status": handle.status.value,
            "image": stored.image_label,
            "workdir": stored.runtime.workdir or "",
            "cpus": stored.resources.cpus,
            "memory": stored.resources.memory_mib,
            "environment": environment.counts(stored, await self._image_env(stored, images)),
            "network": network.from_config(stored),
            "folders": workspaces.from_config(stored),
            "snapshots": [
                {"reference": item.reference, "name": item.name, "created": item.created_at}
                for item in snapshots
                if item.group == handle.name
            ],
            "host": ssh.alias(handle.name) if is_ssh_name(handle.name) else None,
        }

    async def _remove_snapshot(self, name: str, reference: str) -> None:
        others = [item for item in await Snapshot.list() if item.group == name and item.reference != reference]
        if others:
            await Snapshot.group_head(f"{name}:{max(others, key=lambda item: item.created_at).name}")
        await Snapshot.remove(reference, force=True)

    async def _environment_patch(self, name: str, after: EnvironmentSettings) -> dict[str, Any]:
        stored = await self._stored(name)
        return environment.modify_patch(after, environment.from_config(stored, await self._image_env(stored, {})))

    async def _image_env(self, stored: StoredConfig, images: dict[str, dict[str, str]]) -> dict[str, str]:
        if (reference := stored.oci_reference) is None:
            return {}
        if reference not in images:
            try:
                image = (await Image.inspect(reference)).config
            except ImageNotFoundError:
                image = None
            images[reference] = dict(item.partition("=")[::2] for item in image.env) if image else {}
        return images[reference]

    async def _stored(self, name: str) -> StoredConfig:
        return StoredConfig.model_validate_json((await Sandbox.get(name)).config_json)

    async def _stop(self, name: str) -> None:
        sandbox = await Sandbox.get(name)
        if sandbox.status != SandboxStatus.STOPPED:
            await sandbox.stop()

    async def _modify(
        self, name: str, *, policy: ModificationPolicy = ModificationPolicy.RESTART, **changes: Any
    ) -> None:
        result = await (await Sandbox.get(name)).modify(**changes, policy=policy)
        if not result.get("applied"):
            raise RuntimeError("Microsandbox did not apply the changes.")

    def _ssh_paths(self) -> ssh.Paths:
        return ssh.Paths(home=Path.home(), msb=Path(resolve_runtime().msb_path))
