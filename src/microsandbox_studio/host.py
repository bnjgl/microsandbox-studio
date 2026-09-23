"""Host-side commands, chosen by platform. Pure, so every platform can be tested anywhere."""

import re
from collections.abc import Mapping
from typing import NamedTuple


class ClipboardCommand(NamedTuple):
    args: list[str]
    encoding: str


def clipboard_command(platform: str, environ: Mapping[str, str]) -> ClipboardCommand:
    if platform == "win32":
        # clip.exe only reads Unicode correctly as UTF-16 with BOM, which "utf-16" writes.
        return ClipboardCommand(["clip"], "utf-16")
    if platform == "darwin":
        return ClipboardCommand(["pbcopy"], "utf-8")
    if environ.get("WAYLAND_DISPLAY"):
        return ClipboardCommand(["wl-copy"], "utf-8")
    return ClipboardCommand(["xclip", "-selection", "clipboard"], "utf-8")


def is_web_url(url: str) -> bool:
    return re.match(r"https?://", url, re.IGNORECASE) is not None
