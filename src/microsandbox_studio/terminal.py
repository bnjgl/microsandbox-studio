"""Shell start script and persistent shpool sessions for interactive terminals."""

import platform
import shlex
from pathlib import Path, PurePosixPath

SHPOOL_VERSION = "0.11.5"
# Versioned, so an updated shpool is copied next to the old one on the next connect.
GUEST_DIR = f"/opt/microsandbox-studio/shpool-{SHPOOL_VERSION}"
SESSION = "microsandbox-studio"

# forward_env passes the sandbox env and secret placeholders from the exec
# process to new shells; default_dir "." keeps the sandbox workdir.
SHPOOL_CONFIG = """\
forward_env = true
noread_etc_environment = true
default_dir = "."
prompt_prefix = ""
session_restore_mode = { lines = 2000 }
"""

# Run inside the guest. Pass the configured shell as an argument, never as code.
# The extra descriptor supplies Bash's rc file without modifying guest files.
START_SCRIPT = r"""
shell=$1
case "$shell" in
    sh|/bin/sh|/usr/bin/sh)
        shell=$(command -v bash) || exec "$1" -i
        ;;
esac
case "${shell##*/}" in
    bash)
        exec "$shell" --rcfile /dev/fd/3 -i 3<<'MICROSANDBOX_BASHRC'
exec 3<&-
if [ -r "$HOME/.bashrc" ]; then
    . "$HOME/.bashrc"
fi
if [ -z "${BASH_COMPLETION_VERSINFO:-}" ]; then
    if [ -r /usr/share/bash-completion/bash_completion ]; then
        . /usr/share/bash-completion/bash_completion
    elif [ -r /etc/bash_completion ]; then
        . /etc/bash_completion
    fi
fi
MICROSANDBOX_BASHRC
        ;;
    *) exec "$shell" -i ;;
esac
"""

# Set the size before attaching: shpool panics when restoring onto a 0x0 terminal.
ATTACH_SCRIPT = r"""
stty cols "$1" rows "$2" 2>/dev/null
exec "$3/shpool" --config-file "$3/config.toml" attach --force --cmd "$4" "$5"
"""


def clamp(size: int) -> int:
    return max(1, min(int(size), 1000))


def host_binary() -> Path:
    # MicroVMs run without emulation, so the guest shares the host architecture.
    machine = platform.machine().lower()
    arch = {"arm64": "aarch64", "amd64": "x86_64"}.get(machine, machine)
    path = Path(__file__).with_name("assets") / "shpool" / arch / "shpool"
    if not path.is_file():
        raise RuntimeError(f"shpool for {arch} is missing. Please run `uv run python scripts/fetch_shpool.py`.")
    return path


def attach_args(shell: str, cols: int, rows: int) -> list[str]:
    # shpool splits --cmd with shell-words, which understands POSIX quoting.
    command = shlex.join(["/bin/sh", f"{GUEST_DIR}/start.sh", shell])
    return [
        "-c",
        ATTACH_SCRIPT,
        "microsandbox-terminal",
        str(clamp(cols)),
        str(clamp(rows)),
        GUEST_DIR,
        command,
        SESSION,
    ]


def _interactive_shell(shell: str) -> list[str]:
    if PurePosixPath(shell).name == "sh":
        # Like START_SCRIPT: prefer an interactive bash, which reads ~/.bashrc
        # (and with it e.g. ~/.local/bin on PATH). No double quotes, which
        # Windows PowerShell mangles when passing arguments.
        return ["/bin/sh", "-c", "exec $(command -v bash || echo sh) -i"]
    return [shell, "-i"]


def _powershell_join(args: list[str]) -> str:
    # PowerShell, the default in Windows Terminal, runs a quoted path only after &.
    return "& " + " ".join("'" + arg.replace("'", "''") + "'" for arg in args)


def external_command(msb: str, name: str, shell: str, windows: bool) -> str:
    """Command line for the user's own terminal.

    It execs with a TTY, like Studio's own shell: same user and environment,
    no SSH inactivity timeout, but without shpool.
    """
    args = [msb, "exec", "--tty", name, "--", *_interactive_shell(shell)]
    return _powershell_join(args) if windows else shlex.join(args)
