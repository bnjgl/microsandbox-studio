# Microsandbox Studio

Desktop app for local Microsandbox environments. The window runs on pywebview, the interface on Vue and Vuetify. The terminal is rendered with xterm.js and connected directly to the Microsandbox Python SDK through `exec_stream(..., tty=True)`. There is no custom CSS.

## Requirements

- macOS on Apple Silicon, Linux with KVM, or Windows with the Windows Hypervisor Platform (plus the WebView2 runtime, preinstalled on Windows 11)
- `uv`, Node.js and npm

## Getting started

```bash
cd frontend
npm ci --include=optional
npm run build
cd ..
uv sync
uv run python scripts/fetch_shpool.py
uv run microsandbox-studio
```

`fetch_shpool.py` downloads the static [shpool](https://github.com/shell-pool/shpool) binaries (version: `SHPOOL_VERSION` in `terminal.py`, Linux musl, aarch64 and x86_64, Apache-2.0) together with the license into `src/microsandbox_studio/assets/shpool/` and verifies their SHA-256 checksums. The files are not part of the repository.

The first time a sandbox is created, Microsandbox has to pull the selected container image. The app can create, start, stop, rename and delete sandboxes and provides an interactive shell.

New sandboxes use [`mcr.microsoft.com/devcontainers/base:ubuntu-24.04`](https://github.com/devcontainers/images/tree/main/src/base-ubuntu) by default. This Ubuntu development image includes Git, Bash with completion, Zsh, curl, wget, jq, an SSH client, nano, vim-tiny and htop, among others. It is available for ARM64 and AMD64. Language toolchains such as Node.js, Python with pip or Go are added as the project needs them. The image can be changed freely in the create dialog.

If the default shell is `sh`, the terminal prefers an interactive Bash when the image has one. This gives tab completion for files and commands, history, arrow keys and `Ctrl+R`. Your own `~/.bashrc` is loaded, and an installed `bash-completion` is enabled as well. Other explicitly configured shells are used as configured. Without Bash, an interactive `sh` is the fallback; how comfortable it is depends on the image.

## Building the app

```bash
scripts/build_app.sh
```

This builds the frontend, fetches shpool and packages the app with PyInstaller for the current OS into `dist/` (on macOS: `dist/Microsandbox Studio.app`). Pushing a tag `v*` builds it for macOS, Windows and Linux on GitHub and attaches the downloads to a release.

## Tests

The logic lives in pure functions (validation, reading and writing configuration, terminal commands); the pywebview bridge in `app.py` and the Vue components only connect them to the SDK, the window and the host. The tests therefore need neither a sandbox nor a window:

```bash
uv run pytest
cd frontend && npm test
```

The frontend uses Node's built-in test runner, without extra packages.

## Shell sessions persist

The shell runs inside the sandbox under [shpool](https://github.com/shell-pool/shpool); the app's terminal is only a client. Closing the app only disconnects the client; the shell, working directory, variables and running programs stay. On the next connection the terminal shows the last 2000 lines again. There is one session per sandbox (`microsandbox-studio`). `exit` ends it, Enter opens a new one. Stopping or restarting the sandbox ends it as well.

If sandboxes are still running when the app closes, a dialog asks what to do: "Close" keeps them and their shells running, "Stop all & close" stops them first, "Cancel" keeps the app open. If stopping fails, the app stays open and shows the error.

On the first connection the app copies the static shpool binary (about 5 MB, matching the host architecture the microVMs use) with its configuration and start script to `/opt/microsandbox-studio/shpool-<version>/`. This works with any Linux image and needs no package manager. The files survive restarts; a new shpool version goes into a new folder. To remove them: `rm -rf /opt/microsandbox-studio`. shpool puts its socket in `$XDG_RUNTIME_DIR/shpool/` or `~/.local/run/shpool/`. The key sequence `Ctrl+Space Ctrl+Q` detaches; Enter reconnects.

Selected text goes to the host clipboard with `Cmd+C` (macOS) or `Ctrl+Shift+C`; `Ctrl+C` still interrupts. Programs in the sandbox can write to the clipboard via OSC 52 (such as "c to copy" in Claude Code) but cannot read it. If a program captures the mouse, hold `Option` (macOS) or `Shift` to select. On Windows copying uses the built-in `clip`; on Linux it needs `wl-copy` (Wayland) or `xclip` (X11).

Richer completion, for example of command options, requires `bash-completion` in the sandbox image. On Ubuntu/Debian, install it as root in the sandbox terminal with `apt-get update && apt-get install -y bash-completion`. Then end the shell with `exit` and press Enter to open a new one. Starting the terminal installs no packages and changes no shell configuration files; it only puts the shpool files under `/opt/microsandbox-studio/` (see above).

## Interface

The terminal of the selected sandbox fills the window. Without a sandbox, the app shows a card for creating one in the middle. The sandbox list opens from the hamburger menu at the top left. Next to its status dot (green = running), each entry has a three-dot menu to rename, duplicate and delete.

The small up and down arrows next to the name in the terminal header switch to the previous or next sandbox in the list; they are greyed out at either end. `Ctrl+Tab` and `Ctrl+Shift+Tab` do the same from anywhere in the window, including the terminal, as long as no dialog is open. The header also holds "Copy files into the sandbox", "Duplicate", "Settings" and Start/Stop. The shell connects automatically on start; a running sandbox connects when it is selected. Shell sessions stay open while switching between sandboxes. When a shell ends, for example through `exit`, Enter opens a new one.

The settings dialog shows an overview of its sections: **General** (name, image, status), **Variables & secrets**, **Network**, **Workspace folders** and deleting the sandbox.

Microsandbox cannot rename sandboxes, so "Rename" sets a display name that only applies in the app. It is stored by sandbox ID in the interface's localStorage; for this, pywebview runs without private mode and keeps the data in its own storage folder. The CLI and SDK keep using the technical name.

After changing the frontend, run `npm run build` in `frontend/` again and restart the desktop app.

## Workspace folders

When creating a sandbox, "Add folders" selects one or more local folders, also in several passes. Each folder is mounted writable at `/workspaces/<folder name>`; folders with the same name get a numbered target. The dialog shows the mapping and lets you remove entries before creating. The terminal starts in the first workspace folder. Changes apply directly to the local files; deleting the sandbox does not remove these host folders.

Later, the folders can be managed under Settings → Workspace folders, with the same list as when creating. Mounts belong to the sandbox configuration, not to the container image. According to the [volume documentation](https://docs.microsandbox.dev/sandboxes/volumes), they are given on creation through `volumes` and `Volume.bind(...)`; `modify()` offers no mount changes, not even with a restart (see the [Python API](https://docs.microsandbox.dev/sdk/python/sandbox)). When [restoring a disk snapshot](https://docs.microsandbox.dev/sandboxes/snapshots#external-mounts), on the other hand, host folders are passed explicitly. "Apply" therefore rebuilds the sandbox, just like for the network (see [Rebuilding a sandbox](#rebuilding-a-sandbox)). Unchanged folders keep their mount options, and other mounts outside `/workspaces` stay as they are. If the working directory was inside a removed folder or none was set, the terminal then starts in the first workspace folder. Removed folders stay on the computer.

## Copying files and folders in

For a running sandbox, the upload icon in the terminal header opens a dialog with native multi-selection for files and folders. The destination folder can be chosen freely (default `/uploads`); selected sources keep their names, e.g. `project` → `/uploads/project`. Folders are transferred recursively, including empty subfolders and hidden files. The app uses the documented methods [`fs.copy_from_host()` and `fs.mkdir()`](https://github.com/superradcompany/microsandbox/blob/main/docs/sdk/python/filesystem.mdx) for this. `copy_from_host()` on its own copies a single file.

Symbolic links and special files are skipped and counted in the result. File contents and folder structure are transferred; the app does not carry over extra file permissions or timestamps. Existing targets with the same name cause an error before anything starts. If a transfer fails, files already copied are kept; the error message states how far it got. One-off copies are not synchronized with the source. If the destination lies in a mounted host folder, the data is stored there.

## Environment variables and secrets

For existing sandboxes, the editor is under Settings → "Variables & secrets"; when creating, use the button of the same name. It has two tabs that show the same state: **GUI** (form) and **YAML**. Every valid change in one tab is immediately applied to the other. If an input is invalid, that tab shows the error while the other keeps the last valid state; saving is disabled until it is fixed.

The YAML follows the documented format ([Secrets](https://docs.microsandbox.dev/sandboxes/secrets#yaml-configuration), [CLI configuration](https://docs.microsandbox.dev/cli/configuration#secrets)) and only allows `env`, `secrets` and `secret_violation_action`:

```yaml
env:
  MODE: "development"
  PORT: "3000"
secret_violation_action: "block-and-log"
secrets:
  GITHUB_TOKEN:
    value: "${GITHUB_TOKEN}"
    allow: ["api.github.com"]
    substitution:
      headers: true
      query: false
      body: false
    passthrough: ["api.anthropic.com"]
    violation_action: "block-and-terminate"
    require_tls_identity: true
```

Every secret needs at least one host in `allow`. Without `value`, the host variable of the same name is used; `${NAME}` refers to a different host variable. Both refer to the environment of the app process and are stored as a reference, not as plain text. As with the CLI loader, duplicate keys, multiple documents, anchors/aliases, custom tags and unquoted `yes`/`no`/`on`/`off` are rejected. The editor produces sparse YAML: fields with their default value are omitted, and comments are not preserved. Values in `env` are not expanded.

Plain variables are readable by guest programs and apply to new processes; type `exit` in an open shell and press Enter to open a new one. If the sandbox has to restart for new secrets, the app reconnects the shell automatically afterwards. For secrets, the sandbox only sees a placeholder (`$MSB_<NAME>`). New secrets require a restart of running sandboxes, which is shown before saving; rotating and removing secrets take effect without a restart. Stopped sandboxes pick up the configuration on their next start.

For existing sandboxes, the Python SDK only changes the source/value and the allowed hosts. `substitution`, `passthrough`, `violation_action`, `require_tls_identity` and `secret_violation_action` can only be set on creation; the GUI tab then locks these fields, and the YAML tab rejects a change with an error message.

On creation, the app initializes referenced secrets with random stand-in material and switches them to the host variable with `modify()` right afterwards. If that fails, the new sandbox is stopped. Secret values entered directly are stored by Microsandbox in its host configuration.

## Network

The network is set when creating through "Network" or changed later under Settings → Network (see [Networking](https://docs.microsandbox.dev/networking/overview)). There are three modes:

- **No network** blocks incoming and outgoing traffic. The terminal and file copies use a separate channel and keep working.
- **Restricted** only allows the selected zones: internet, local network and host computer (`host.microsandbox.internal`). The default is internet only, as in Microsandbox itself. DNS through the sandbox gateway is allowed automatically. Custom rules allow or block outgoing connections to a domain, a domain suffix (`.example.com`), an IP address or a CIDR range, optionally with a protocol and a port or port range. They are checked before the zones, and the first matching rule wins.
- **Unrestricted** allows everything, including the local network, the host computer and cloud metadata.

Port mappings make a service in the sandbox reachable on the computer (host port → sandbox port, TCP or UDP). They bind to `127.0.0.1` by default; `0.0.0.0` also makes the port reachable from other devices. The app does not offer DNS servers, TLS interception, strict mode or rate limits.

### Rebuilding a sandbox

Microsandbox cannot change the network or the workspace folders of an existing sandbox; `modify()` has no options for them. "Apply" therefore rebuilds the sandbox and lists every step in a confirmation dialog beforehand:

1. Disconnect the shell and stop the sandbox. Running programs and the shpool session end.
2. Create a disk snapshot (in a snapshot group of its own).
3. Delete the sandbox and re-create it from the snapshot under the same name with `Sandbox.restore()`, with the new network or the new workspace folders.
4. Re-apply the settings a snapshot does not contain: CPUs, memory, workspace folders and network during the restore; variables, secrets (with their previous placeholders), labels and working directory afterwards with `modify()`.
5. If the sandbox was stopped, stop it again. Then delete the snapshot.

If a step fails, the app restores the sandbox from the same snapshot with its previous settings. If that fails too, the snapshot is kept and the error message names its reference. The internal sandbox ID changes; the app moves the display name to the new ID.

Beforehand, the app checks whether anything would be lost and refuses to rebuild if so. This covers mounts other than host folders and owned volumes, secrets with options that can only be set on creation (`substitution`, `passthrough`, `violation_action`, `require_tls_identity`, `secret_violation_action`), secrets whose host variable is missing from the app's environment, as well as strict mode, custom DNS servers, rate limits, an outbound proxy and host CAs. A custom shell set through the CLI is not carried over. If the network was set up outside the app and does not fit the three modes, the dialog says so and offers no change.

## Duplicating a sandbox

"Duplicate" asks for a name for the copy and selects it afterwards. The source stays unchanged. A running sandbox is copied with [`branch()`](https://docs.microsandbox.dev/sandboxes/snapshots) including memory and running programs; the copy runs immediately, including the shpool shell. A stopped sandbox is saved as a disk snapshot and booted fresh from it with `Sandbox.restore()`; the app deletes the temporary snapshot afterwards. A disk snapshot only contains files, image and default user. The copy therefore gets the same settings that are carried over when rebuilding (see above), with the same limitations. It mounts the same workspace folders; both sandboxes see changes there. A display name is not carried over.
