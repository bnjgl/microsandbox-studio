import base64
import os

import pytest

from microsandbox_studio import app, config, events, files, host, terminal


@pytest.mark.parametrize(
    ("platform", "environ", "command"),
    [
        ("win32", {}, host.ClipboardCommand(["clip"], "utf-16")),
        ("darwin", {"WAYLAND_DISPLAY": "w"}, host.ClipboardCommand(["pbcopy"], "utf-8")),
        ("linux", {"WAYLAND_DISPLAY": "w"}, host.ClipboardCommand(["wl-copy"], "utf-8")),
        ("linux", {}, host.ClipboardCommand(["xclip", "-selection", "clipboard"], "utf-8")),
    ],
)
def test_clipboard_command(platform, environ, command):
    assert host.clipboard_command(platform, environ) == command


def test_is_web_url():
    assert host.is_web_url("HTTPS://example.com")
    assert not host.is_web_url("file:///etc/passwd")


def test_external_command_prefers_bash_for_sh():
    assert terminal.external_command("/opt/msb", "dev", "/bin/sh", windows=False) == (
        "/opt/msb exec --tty dev -- /bin/sh -c 'exec $(command -v bash || echo sh) -i'"
    )


def test_external_command_quotes_for_powershell():
    assert terminal.external_command("C:\\Program Files\\msb.exe", "dev", "/bin/zsh", windows=True) == (
        "& 'C:\\Program Files\\msb.exe' 'exec' '--tty' 'dev' '--' '/bin/zsh' '-i'"
    )


def test_attach_args_clamps_size():
    args = terminal.attach_args("/bin/sh", 0, 5000)
    assert args[3:5] == ["1", "1000"]


def test_image_label():
    assert config.image_label({"image": {"Oci": {"reference": "ubuntu:24.04"}}}) == "ubuntu:24.04"
    assert config.image_label({"image_name": "alpine"}) == "alpine"
    assert config.image_label({}) == "—"


def test_enqueue_merges_output_of_the_same_terminal():
    outbox = events.enqueue([], "terminal-data", {"token": "a", "data": b"1"})
    outbox = events.enqueue(outbox, "terminal-data", {"token": "a", "data": b"2"})
    outbox = events.enqueue(outbox, "terminal-data", {"token": "b", "data": b"3"})
    assert outbox == [("terminal-data", {"token": "a", "data": b"12"}), ("terminal-data", {"token": "b", "data": b"3"})]
    encoded = base64.b64encode(b"12").decode()
    assert events.script(outbox[:1]) == f'window.msbEvent("terminal-data", {{"token": "a", "data": "{encoded}"}})'


def test_needs_restart():
    changes = {"changes": [{"disposition": "requires restart"}]}
    assert app.needs_restart("running", changes)
    assert not app.needs_restart("stopped", changes)
    assert not app.needs_restart("running", {})


@pytest.mark.parametrize("name", [" dev ", "a.b_c-1"])
def test_sandbox_name_accepts(name):
    assert app.sandbox_name(name) == name.strip()


@pytest.mark.parametrize("name", ["", "-x", "a b", "x" * 129])
def test_sandbox_name_rejects(name):
    with pytest.raises(ValueError):
        app.sandbox_name(name)


@pytest.mark.skipif(os.name == "nt", reason="symlinks need privileges on Windows")
def test_copy_plan_walks_tree_and_skips_links(tmp_path):
    project = tmp_path / "project"
    (project / "sub").mkdir(parents=True)
    (project / "a.txt").write_text("a")
    (project / "sub" / "b.txt").write_text("b")
    (project / "link").symlink_to(project / "a.txt")
    entries, skipped = files.copy_plan([str(project)], "/uploads")
    assert [(entry.guest, entry.is_dir) for entry in entries] == [
        ("/uploads/project", True),
        ("/uploads/project/a.txt", False),
        ("/uploads/project/sub", True),
        ("/uploads/project/sub/b.txt", False),
    ]
    assert skipped == 1
    assert files.top_level_targets(entries, "/uploads") == ["/uploads/project"]


def test_copy_plan_rejects_same_names(tmp_path):
    (tmp_path / "a" / "x").mkdir(parents=True)
    (tmp_path / "b" / "x").mkdir(parents=True)
    with pytest.raises(ValueError, match="different names"):
        files.copy_plan([str(tmp_path / "a" / "x"), str(tmp_path / "b" / "x")], "/u")


def test_bridge_exposes_only_its_api():
    bridge = app.Bridge.__new__(app.Bridge)
    public = {name for name in dir(bridge) if not name.startswith("_")}
    assert public == {
        "close_terminal",
        "copy_into_sandbox",
        "copy_to_clipboard",
        "create_sandbox",
        "delete_sandbox",
        "duplicate_sandbox",
        "environment_defaults",
        "get_environment",
        "get_network",
        "get_workspaces",
        "list_sandboxes",
        "open_terminal",
        "open_url",
        "quit",
        "resize_terminal",
        "save_environment",
        "save_network",
        "save_workspaces",
        "select_copy_sources",
        "select_workspace_folders",
        "start_sandbox",
        "stop_sandbox",
        "terminal_command",
        "write_terminal",
    }
