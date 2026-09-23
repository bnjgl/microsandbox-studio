"""pywebview bridge for sandbox lifecycle and interactive SDK streams.

This module is the imperative shell: it talks to the SDK, the window and the
host. Decisions live in pure functions in the other modules, so they can be
tested without a sandbox.
"""

import asyncio
import contextlib
import functools
import inspect
import os
import re
import socket
import subprocess
import sys
import threading
import webbrowser
from collections.abc import AsyncIterator, Callable, Coroutine
from pathlib import Path, PurePosixPath
from typing import Any, Concatenate, NamedTuple
from uuid import uuid4

import webview
from microsandbox import (
    ExecEventType,
    InvalidConfigError,
    ModificationPolicy,
    Network,
    Sandbox,
    Snapshot,
    Stdin,
    ViolationAction,
    resolve_runtime,
)

from . import carryover, config, environment, events, host, workspaces
from . import network as networking
from .files import CopyEntry, copy_plan, is_link, top_level_targets
from .terminal import (
    GUEST_DIR,
    SHPOOL_CONFIG,
    START_SCRIPT,
    attach_args,
    clamp,
    external_command,
    host_binary,
)

_NAME = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,127}$")
_TOKEN = re.compile(r"^[0-9a-f]{32}$")


class Session(NamedTuple):
    handle: Any
    stdin: Any
    sandbox: str


# Validation


def sandbox_name(value: str) -> str:
    name = value.strip()
    if not _NAME.fullmatch(name):
        raise ValueError("Name: 1–128 characters; letters, digits, period, _ or - only.")
    return name


def sandbox_summary(handle: Any) -> dict[str, Any]:
    """List entry for the frontend."""
    return {
        "name": handle.name,
        "id": handle.id,
        "status": handle.status.value,
        "created_at": handle.created_at,
        "image": config.image_label(handle.config()),
    }


def needs_restart(status: str, dry_run: dict[str, Any]) -> bool:
    return status == "running" and any(
        change.get("disposition") == "requires restart" for change in dry_run.get("changes", [])
    )


def _require_applied(result: dict[str, Any], message: str) -> None:
    if not result.get("applied"):
        raise RuntimeError(message)


def _recreatable(handle: Any) -> dict[str, Any]:
    """What the dialogs show before a sandbox is re-created."""
    return {"status": handle.status.value, "problem": carryover.problem(handle.config()), "kept": carryover.KEPT}


def unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


# SDK helpers


async def _all_sandboxes() -> AsyncIterator[Any]:
    page = await Sandbox.list()
    while True:
        for handle in page.sandboxes:
            yield handle
        if not page.next_cursor:
            return
        page = await Sandbox.list_with(cursor=page.next_cursor)


async def _exists(name: str) -> bool:
    try:
        await Sandbox.get(name)
    # Any error counts as missing, as before. SandboxNotFoundError alone would be
    # safer (see the cleanup in _restore_copy) but is not verified for get().
    except Exception:  # noqa: BLE001
        return False
    return True


async def _snapshot(name: str) -> Any:
    # A group of its own, so the only member can be removed again and the
    # source's snapshot group stays untouched.
    return await Snapshot.create("studio", from_sandbox=name, group=f"microsandbox-studio-{uuid4().hex[:12]}")


async def _remove_snapshot(snapshot: Any) -> None:
    # Restored sandboxes do not depend on the snapshot. If Microsandbox
    # still refuses, the snapshot stays and can be removed with the CLI.
    with contextlib.suppress(Exception):
        await Snapshot.remove(snapshot.reference)


async def _restore_copy(snapshot: Any, name: str, plan: carryover.Plan) -> None:
    """Restore ``snapshot`` as ``name`` and re-apply what the snapshot does not keep."""
    # Checked first, so the cleanup below can only remove what this call created.
    if await _exists(name):
        raise ValueError(f"A sandbox named {name} already exists.")
    try:
        copy = await Sandbox.restore(snapshot, name=name, **plan.restore)
        await copy.detach()
        if plan.modify:
            result = await (await Sandbox.get(name)).modify(**plan.modify, policy=ModificationPolicy.RESTART)
            _require_applied(result, "Variables, secrets or working directory were not applied.")
    except Exception:
        # An incomplete child cannot be reused; the snapshot can be restored again.
        with contextlib.suppress(Exception):
            await (await Sandbox.get(name)).destroy(force=True)
        raise


async def _as_root(sandbox: Any, script: str, *args: str) -> None:
    result = await sandbox.exec("/bin/sh", ["-c", script, "microsandbox-studio", *args], user="root")
    if not result.success:
        raise RuntimeError(f"Could not set up shpool in the sandbox: {result.stderr_text.strip()}")


async def _install_shpool(sandbox: Any) -> None:
    binary = f"{GUEST_DIR}/shpool"
    if await sandbox.fs.exists(binary):
        return
    source = host_binary()
    await _as_root(sandbox, 'mkdir -p "$1" && rm -f "$1/shpool.part"', GUEST_DIR)
    await sandbox.fs.write(f"{GUEST_DIR}/config.toml", SHPOOL_CONFIG.encode())
    await sandbox.fs.write(f"{GUEST_DIR}/start.sh", START_SCRIPT.encode())
    await sandbox.fs.copy_from_host(str(source), f"{binary}.part")
    # Rename last, so an existing binary means the directory is complete.
    await _as_root(
        sandbox,
        'chmod 755 "$1" "$1/shpool.part" && chmod 644 "$1/config.toml" "$1/start.sh" && mv -f "$1/shpool.part" "$1/shpool"',
        GUEST_DIR,
    )


async def _copy_entry(sandbox: Any, entry: CopyEntry) -> None:
    if is_link(entry.source):
        raise ValueError("Source was replaced by a link while copying.")
    if entry.is_dir:
        await sandbox.fs.mkdir(entry.guest)
    else:
        await sandbox.fs.copy_from_host(str(entry.source), entry.guest)


def _counts(entries: list[CopyEntry]) -> tuple[int, int]:
    """Files and directories among ``entries``."""
    directories = sum(entry.is_dir for entry in entries)
    return len(entries) - directories, directories


# Bridge


def on_loop[**P, R](
    method: Callable[Concatenate["Bridge", P], Coroutine[Any, Any, R]],
) -> Callable[Concatenate["Bridge", P], R]:
    """Expose an async method to pywebview as a blocking call on the SDK loop."""

    @functools.wraps(method)
    def call(self: "Bridge", *args: P.args, **kwargs: P.kwargs) -> R:
        return self._run(method, self, *args, **kwargs)

    # pywebview reads the parameter names to build the JavaScript functions.
    call.__signature__ = inspect.signature(method)  # type: ignore[attr-defined]
    return call


class Bridge:
    """Methods exposed to the frontend. Each blocks on the SDK event loop thread.

    pywebview exposes every public attribute to JavaScript, recursively, so all
    state is private.
    """

    def __init__(self) -> None:
        self._loop = asyncio.new_event_loop()
        threading.Thread(target=self._loop.run_forever, daemon=True).start()
        self._window: Any = None
        self._sessions: dict[str, Session] = {}
        self._quitting = False
        # evaluate_js waits for the GUI thread without a timeout. Once the window
        # is gone that wait never ends, so nothing may be sent after closing.
        self._closed = threading.Event()
        # Terminal events wait here for the sender thread, so a busy GUI thread
        # neither blocks the SDK loop nor gets one evaluate_js per output chunk.
        self._outbox: list[events.Event] = []
        self._outbox_ready = threading.Condition()
        threading.Thread(target=self._send_outbox, daemon=True).start()

    def _run[R](self, function: Callable[..., Coroutine[Any, Any, R]], *args: Any, **kwargs: Any) -> R:
        # SDK awaitables bind to the running loop, so create them on the loop thread.
        async def call() -> R:
            return await function(*args, **kwargs)

        return asyncio.run_coroutine_threadsafe(call(), self._loop).result()

    def _can_send(self) -> bool:
        return self._window is not None and not self._closed.is_set()

    def _emit(self, event: str, payload: dict[str, Any]) -> None:
        if self._can_send():
            self._window.evaluate_js(events.js_call(event, payload))

    def _post(self, event: str, payload: dict[str, Any]) -> None:
        # Output arriving while the previous batch is still being sent is merged.
        with self._outbox_ready:
            self._outbox = events.enqueue(self._outbox, event, payload)
            self._outbox_ready.notify()

    def _send_outbox(self) -> None:
        while True:
            with self._outbox_ready:
                self._outbox_ready.wait_for(lambda: self._outbox)
                batch, self._outbox = self._outbox, []
            if self._can_send():
                self._window.evaluate_js(events.script(batch))

    # Window lifecycle, called from main()

    def _attach(self, window: Any) -> None:
        self._window = window
        window.events.closing += self._closing
        window.events.closed += self._closed.set

    def _shutdown(self) -> None:
        self._closed.set()
        # Detach the shell clients; the shpool sessions keep running. An emit that
        # was already waiting on the window can block the loop, hence the timeout.
        with contextlib.suppress(Exception):
            asyncio.run_coroutine_threadsafe(self._close_all_sessions(), self._loop).result(timeout=5)

    # Sandboxes

    async def _list_sandboxes(self) -> list[dict[str, Any]]:
        items = [sandbox_summary(handle) async for handle in _all_sandboxes()]
        return sorted(items, key=lambda item: item["name"].lower())

    list_sandboxes = on_loop(_list_sandboxes)

    def create_sandbox(
        self,
        name: str,
        image: str,
        memory: int,
        cpus: int,
        folders: list[dict[str, str]] | None = None,
        settings: dict[str, Any] | None = None,
        network: dict[str, Any] | None = None,
    ) -> None:
        name, image = sandbox_name(name), image.strip()
        if not image:
            raise ValueError("Please enter a container image.")
        if not 128 <= int(memory) <= 65536 or not 1 <= int(cpus) <= 64:
            raise ValueError("Invalid CPU count or memory size.")
        volumes = workspaces.volumes(workspaces.normalize(folders))
        settings = environment.normalize(settings)
        for key, secret in settings["secrets"].items():
            environment.require_host_variable(key, secret)
        network = networking.normalize(network)
        self._run(
            self._create_sandbox,
            name,
            settings,
            image=image,
            memory=int(memory),
            cpus=int(cpus),
            detached=True,
            volumes=volumes,
            workdir=next(iter(volumes), None),
            network=Network(policy=networking.policy(network), ports=networking.ports(network)),
        )

    async def _create_sandbox(self, name: str, settings: environment.Settings, **options: Any) -> None:
        secrets, references = environment.create_secrets(settings)
        sandbox = await Sandbox.create(
            name,
            **options,
            env=settings["env"],
            secrets=secrets,
            secret_violation_action=ViolationAction(settings["secret_violation_action"]),
        )
        if not references:
            return
        try:
            result = await sandbox.modify(secrets=references, policy=ModificationPolicy.RESTART)
            _require_applied(result, "Secret references were not applied.")
        except Exception as exc:
            await sandbox.stop()
            raise RuntimeError(
                "Sandbox created, but its secret references could not be activated. It was stopped; please check the configuration."
            ) from exc

    def start_sandbox(self, name: str) -> None:
        self._run(Sandbox.start, name, detached=True)

    async def _stop_sandbox(self, name: str) -> None:
        await self._close_sessions(name)
        sandbox = await Sandbox.get(name)
        if sandbox.status.value != "stopped":
            await sandbox.stop()

    stop_sandbox = on_loop(_stop_sandbox)

    def duplicate_sandbox(self, name: str, target: str) -> None:
        self._run(self._duplicate_sandbox, name, sandbox_name(target))

    async def _duplicate_sandbox(self, name: str, target: str) -> None:
        handle = await Sandbox.get(name)
        if handle.status.value == "running":
            await self._branch(handle, target)
            return
        # Disk snapshots need a stopped source. The copy binds the same workspace
        # folders and gets the settings the snapshot does not keep.
        plan = carryover.plan(handle.config())
        snapshot = await _snapshot(name)
        try:
            await _restore_copy(snapshot, target, plan)
        finally:
            await _remove_snapshot(snapshot)

    @staticmethod
    async def _branch(handle: Any, target: str) -> None:
        # A branch keeps disk and running processes, including the shpool shell.
        # Detach it like created sandboxes, so it outlives the app.
        try:
            branch = await handle.branch(target)
        except InvalidConfigError as exc:
            # Secrets, TLS interception and outbound proxies are host-backed.
            # branch() cannot authorize them; the snapshot path re-applies them.
            if "host-backed" not in str(exc):
                raise
            raise RuntimeError(
                "A running sandbox with secrets, TLS interception or a proxy cannot be duplicated directly. "
                "Stop the sandbox and duplicate it again; the copy then gets its secrets and settings through a snapshot."
            ) from exc
        await branch.detach()

    async def _delete_sandbox(self, name: str) -> None:
        await self._stop_sandbox(name)
        await (await Sandbox.get(name)).destroy()

    delete_sandbox = on_loop(_delete_sandbox)

    # Network

    async def _get_network(self, name: str) -> dict[str, Any]:
        handle = await Sandbox.get(name)
        stored = handle.config()
        settings = networking.from_config(stored)
        return {"settings": settings, "revision": settings and config.revision(settings), **_recreatable(handle)}

    get_network = on_loop(_get_network)

    def save_network(self, name: str, settings: dict[str, Any], revision: str) -> dict[str, Any]:
        return self._run(self._save_network, name, networking.normalize(settings), revision)

    async def _save_network(self, name: str, settings: networking.Settings, revision: str) -> dict[str, Any]:
        # modify() cannot change the network, so the sandbox is re-created.
        handle = await Sandbox.get(name)
        stored = handle.config()
        current = networking.from_config(stored)
        if current is None or config.revision(current) != revision:
            raise ValueError("The configuration has changed in the meantime. Please reopen the network settings.")
        if current == settings:
            return {"changed": False}
        before = carryover.plan(stored)  # Refuses before anything is touched.
        return await self._recreate(handle, before, carryover.with_network(before, settings), "network settings")

    # Workspace folders

    async def _get_workspaces(self, name: str) -> dict[str, Any]:
        handle = await Sandbox.get(name)
        folders = workspaces.from_config(handle.config())
        return {"folders": folders, "revision": config.revision(folders), **_recreatable(handle)}

    get_workspaces = on_loop(_get_workspaces)

    def save_workspaces(self, name: str, folders: list[dict[str, str]], revision: str) -> dict[str, Any]:
        return self._run(self._save_workspaces, name, workspaces.normalize(folders), revision)

    async def _save_workspaces(self, name: str, folders: workspaces.Folders, revision: str) -> dict[str, Any]:
        # modify() cannot change mounts, so the sandbox is re-created. Restoring a
        # disk snapshot takes the host folders explicitly (see docs: snapshots, external mounts).
        handle = await Sandbox.get(name)
        stored = handle.config()
        current = workspaces.from_config(stored)
        if config.revision(current) != revision:
            raise ValueError("The configuration has changed in the meantime. Please reopen the workspace folders.")
        if current == folders:
            return {"changed": False}
        before = carryover.plan(stored)  # Refuses before anything is touched.
        return await self._recreate(
            handle, before, carryover.with_workspaces(before, current, folders), "workspace folders"
        )

    # Re-creating a sandbox

    async def _recreate(self, handle: Any, before: carryover.Plan, after: carryover.Plan, what: str) -> dict[str, Any]:
        """Re-create the sandbox under the same name from a disk snapshot with ``after``.

        On failure it is restored with ``before``, i.e. unchanged.
        """
        name = handle.name
        running = handle.status.value != "stopped"
        await self._stop_sandbox(name)
        snapshot = await _snapshot(name)
        await (await Sandbox.get(name)).destroy()
        try:
            await _restore_copy(snapshot, name, after)
        except Exception as exc:
            try:
                await _restore_copy(snapshot, name, before)
            except Exception as again:
                raise RuntimeError(
                    f"Rebuilding failed ({exc}) and the previous sandbox could not be restored ({again}). "
                    f"Its files are in snapshot {snapshot.reference}; it is kept and can be restored with Sandbox.restore() or the msb CLI."
                ) from again
            await self._settle(name, running, snapshot)
            raise RuntimeError(
                f"The new {what} could not be applied ({exc}). The sandbox was restored with its previous settings."
            ) from exc
        await self._settle(name, running, snapshot)
        return {"changed": True, "restarted": running}

    async def _settle(self, name: str, running: bool, snapshot: Any) -> None:
        # Restore boots the sandbox; keep the state it had before.
        if not running:
            await self._stop_sandbox(name)
        await _remove_snapshot(snapshot)

    # Environment variables and secrets

    def environment_defaults(self) -> dict[str, Any]:
        return environment.defaults()

    async def _get_environment(self, name: str) -> dict[str, Any]:
        handle = await Sandbox.get(name)
        settings, _ = environment.from_config(handle.config())
        return {"settings": settings, "revision": config.revision(settings), "status": handle.status.value}

    get_environment = on_loop(_get_environment)

    def save_environment(self, name: str, settings: dict[str, Any], revision: str) -> dict[str, Any]:
        return self._run(self._save_environment, name, environment.normalize(settings), revision)

    async def _save_environment(self, name: str, settings: environment.Settings, revision: str) -> dict[str, Any]:
        handle = await Sandbox.get(name)
        before, placeholders = environment.from_config(handle.config())
        if config.revision(before) != revision:
            raise ValueError("The configuration has changed in the meantime. Please close and reopen the editor.")
        if problem := environment.create_only_change(settings, before):
            raise ValueError(problem)
        patch = environment.modify_patch(settings, before, placeholders)
        if not any(patch.values()):
            return {"restarted": False, "environment_changed": False}
        dry_run = await handle.modify(**patch, policy=ModificationPolicy.RESTART, dry_run=True)
        if dry_run.get("conflicts"):
            raise ValueError("Microsandbox reports a configuration conflict; changes were not saved.")
        restart = needs_restart(handle.status.value, dry_run)
        if restart:
            await self._close_sessions(name)
        result = await handle.modify(**patch, policy=ModificationPolicy.RESTART)
        _require_applied(result, "Microsandbox did not apply the changes. Please reload the configuration.")
        return {"restarted": restart, "environment_changed": bool(patch["env"] or patch["env_rm"])}

    # Files

    def select_workspace_folders(self) -> list[str]:
        result = self._window.create_file_dialog(webview.FileDialog.FOLDER, allow_multiple=True)
        return unique([str(Path(path).resolve()) for path in result or []])

    def select_copy_sources(self, folders: bool = False) -> list[str]:
        kind = webview.FileDialog.FOLDER if folders else webview.FileDialog.OPEN
        result = self._window.create_file_dialog(kind, allow_multiple=True)
        return unique([os.path.abspath(path) for path in result or []])

    def copy_into_sandbox(self, name: str, paths: list[str], destination: str) -> dict[str, int]:
        # Walks the host file system here, not on the SDK loop, which streams the terminals.
        entries, skipped = copy_plan(paths, destination)
        return self._run(self._copy_into_sandbox, name, entries, skipped, destination)

    async def _copy_into_sandbox(
        self, name: str, entries: list[CopyEntry], skipped: int, destination: str
    ) -> dict[str, int]:
        handle = await Sandbox.get(name)
        if handle.status.value != "running":
            raise ValueError("Please start the sandbox before copying.")
        sandbox = await handle.connect()
        # Check all selected top-level names before transferring anything.
        for target in top_level_targets(entries, destination):
            if await sandbox.fs.exists(target):
                raise ValueError(f"Target already exists: {target}. Please choose a different destination folder.")
        if entries:
            await sandbox.fs.mkdir(str(PurePosixPath(destination)))
        for index, entry in enumerate(entries):
            try:
                await _copy_entry(sandbox, entry)
            except Exception as exc:
                files, directories = _counts(entries[:index])
                raise RuntimeError(
                    f"Copying to {entry.guest} failed: {exc}. "
                    f"Already copied: {files} files, {directories} folders. These are kept."
                ) from exc
        files, directories = _counts(entries)
        return {"files": files, "directories": directories, "skipped": skipped}

    # Closing the app

    def _closing(self) -> bool:
        # Runs on the GUI thread. SDK calls may wait for evaluate_js, which needs
        # that thread, so the check runs in the background and the close is retried.
        if self._quitting:
            return True
        threading.Thread(target=self._confirm_close, daemon=True).start()
        return False

    def _confirm_close(self) -> None:
        try:
            running = [item["name"] for item in self.list_sandboxes() if item["status"] == "running"]
        except Exception:  # noqa: BLE001 - an unreadable list must not keep the app open
            running = []
        if not running:
            self.quit()
            return
        try:
            self._emit("close-requested", {"running": running})
        except Exception:  # noqa: BLE001 - a page that cannot ask must not keep the app open
            self.quit()

    def quit(self, stop: list[str] | None = None) -> None:
        if stop:
            self._run(self._stop_all, stop)
        self._quitting = True
        self._closed.set()
        self._window.destroy()

    async def _stop_all(self, names: list[str]) -> None:
        results = await asyncio.gather(*(self._stop_sandbox(name) for name in names), return_exceptions=True)
        if failed := [name for name, result in zip(names, results) if isinstance(result, Exception)]:
            raise RuntimeError(f"Not stopped: {', '.join(failed)}. The app stays open.")

    # Terminal

    def open_terminal(self, name: str, token: str, cols: int, rows: int) -> None:
        # The frontend picks the token, so it can route output that arrives before this returns.
        if not _TOKEN.fullmatch(token) or token in self._sessions:
            raise ValueError("Invalid terminal token.")
        self._run(self._open_terminal, name, token, cols, rows)

    async def _open_terminal(self, name: str, token: str, cols: int, rows: int) -> None:
        handle = await Sandbox.get(name)
        sandbox = await handle.connect_or_start(detached=True)
        await _install_shpool(sandbox)
        # shpool keeps the shell running in the guest; this process is only its client.
        process = await sandbox.exec_stream(
            "/bin/sh",
            attach_args(config.shell(handle.config()), cols, rows),
            stdin=Stdin.pipe(),
            tty=True,
            env={"TERM": "xterm-256color"},
        )
        stdin = process.take_stdin()
        if stdin is None:
            raise RuntimeError("Could not open the terminal input.")
        await process.resize(clamp(rows), clamp(cols))
        self._sessions[token] = Session(process, stdin, name)
        asyncio.create_task(self._pump(token, process))

    async def _pump(self, token: str, process: Any) -> None:
        try:
            async for event in process:
                if event.event_type in (ExecEventType.STDOUT, ExecEventType.STDERR):
                    self._post("terminal-data", {"token": token, "data": bytes(event.data or b"")})
                elif event.event_type == ExecEventType.EXITED:
                    self._post("terminal-exit", {"token": token, "code": event.code})
        except Exception as exc:  # noqa: BLE001 - reported to the terminal, which then closes
            self._post("terminal-error", {"token": token, "message": str(exc)})
        finally:
            self._sessions.pop(token, None)
            self._post("terminal-closed", {"token": token})

    def write_terminal(self, token: str, data: str) -> None:
        if session := self._sessions.get(token):
            self._run(session.stdin.write, data.encode("utf-8"))

    def resize_terminal(self, token: str, cols: int, rows: int) -> None:
        if session := self._sessions.get(token):
            self._run(session.handle.resize, clamp(rows), clamp(cols))

    async def _terminal_command(self, name: str) -> str:
        # The bundled msb moves with the app, so its path is resolved now.
        shell = config.shell((await Sandbox.get(name)).config())
        return external_command(str(resolve_runtime().msb_path), name, shell, windows=sys.platform == "win32")

    terminal_command = on_loop(_terminal_command)

    async def _close_terminal(self, token: str) -> None:
        # Killing the client only detaches; the shpool session keeps running.
        if session := self._sessions.pop(token, None):
            await session.handle.kill()
            await session.stdin.close()

    close_terminal = on_loop(_close_terminal)

    async def _close_all_sessions(self) -> None:
        for token in list(self._sessions):
            with contextlib.suppress(Exception):
                await self._close_terminal(token)

    async def _close_sessions(self, sandbox: str) -> None:
        for token in [token for token, session in self._sessions.items() if session.sandbox == sandbox]:
            await self._close_terminal(token)

    # Host

    def copy_to_clipboard(self, text: str) -> None:
        command = host.clipboard_command(sys.platform, os.environ)
        # Without CREATE_NO_WINDOW a console window flashes on Windows.
        flags = {"creationflags": subprocess.CREATE_NO_WINDOW} if sys.platform == "win32" else {}
        subprocess.run(command.args, input=text.encode(command.encoding), check=True, **flags)

    def open_url(self, url: str) -> None:
        # Links come from programs in the sandbox, so only web URLs reach the host.
        if not host.is_web_url(url):
            raise ValueError(f"Only http(s) links are opened: {url}")
        webbrowser.open(url)


def _port_in_use(port: int) -> bool:
    with socket.socket() as probe:
        # Mirrors the pywebview server, which reuses ports in TIME_WAIT; on
        # Windows the option would allow binding a port that is in use.
        if sys.platform != "win32":
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            probe.bind(("127.0.0.1", port))
        except OSError:
            return True
    return False


ALREADY_RUNNING = """<!doctype html>
<html><body style="margin:0;height:100vh;display:flex;flex-direction:column;justify-content:center;
align-items:center;gap:20px;background:#0B1020;color:#E6E8EF;font:15px -apple-system,'Segoe UI',sans-serif">
<p style="margin:0">Microsandbox Studio is already open.</p>
<button onclick="pywebview.api.close()" style="padding:6px 22px;font:inherit">OK</button>
</body></html>"""


class _Notice:
    def close(self) -> None:
        webview.windows[0].destroy()


def main() -> None:
    frontend = Path(__file__).with_name("frontend") / "index.html"
    if not frontend.exists():
        raise SystemExit("Frontend missing. Please run `npm install && npm run build` in frontend/ first.")
    # localStorage belongs to the origin, so the display names need the fixed
    # port. A second instance would not get it and must not start.
    if _port_in_use(webview.settings["DEFAULT_HTTP_PORT"]):
        webview.create_window(
            "Microsandbox Studio",
            html=ALREADY_RUNNING,
            js_api=_Notice(),
            width=400,
            height=160,
            resizable=False,
            background_color="#0B1020",
        )
        webview.start()
        return
    bridge = Bridge()
    bridge._attach(
        webview.create_window(
            "Microsandbox Studio",
            str(frontend),
            js_api=bridge,
            text_select=True,
            width=1440,
            height=900,
            min_size=(900, 620),
            background_color="#0B1020",
        )
    )
    # Without private mode, pywebview keeps localStorage (display names).
    icon = Path(__file__).with_name("assets") / ("icon.ico" if sys.platform == "win32" else "icon.png")
    webview.start(http_server=True, private_mode=False, icon=str(icon))
    bridge._shutdown()
    # quit() runs in a pywebview API thread, which afterwards returns its result
    # to the destroyed window via evaluate_js and never finishes. That thread is
    # not a daemon, so a normal interpreter exit would wait for it forever.
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0)
