import stat
from pathlib import Path, PureWindowsPath

import pytest
from pydantic import ValidationError

from microsandbox_studio import ssh
from microsandbox_studio.models import is_ssh_name


@pytest.fixture
def paths(tmp_path, monkeypatch):
    def authorize(paths):
        paths.key.parent.mkdir(parents=True, exist_ok=True)
        paths.key.write_text("key")

    monkeypatch.setattr(ssh, "_authorize", authorize)
    return ssh.Paths(home=tmp_path, msb=tmp_path / "App" / "bin" / "msb")


def test_paths_cannot_change(paths):
    with pytest.raises(ValidationError):
        paths.home = Path("/elsewhere")


def test_alias_keeps_sandboxes_apart_from_real_hosts():
    assert ssh.alias("dev") == "dev.msb"


def test_names_that_would_break_ssh_config_are_refused():
    assert is_ssh_name("dev-1.x")
    for name in ("a b", "x\nHost *", "-o", ""):
        assert not is_ssh_name(name)


def test_host_entry_quotes_and_escapes_paths():
    paths = ssh.Paths(home=Path("/Users/me 100%"), msb=Path("/Applications/Studio 2.app/bin/msb"))
    assert ssh.host_entry(paths, "dev").splitlines()[:4] == [
        "Host dev.msb",
        "  User root",
        '  ProxyCommand "/Applications/Studio 2.app/bin/msb" ssh serve --stdio --no-inactivity-timeout dev',
        '  IdentityFile "/Users/me 100%%/.microsandbox-studio/ssh/id_ed25519"',
    ]
    with pytest.raises(ValueError):
        ssh.host_entry(ssh.Paths(home=Path('/Users/"me"'), msb=Path("/msb")), "dev")


def test_host_entry_writes_windows_paths_with_forward_slashes():
    paths = ssh.Paths.model_construct(
        home=PureWindowsPath(r"C:\Users\me"), msb=PureWindowsPath(r"C:\Program Files\Microsandbox Studio\msb.exe")
    )
    entry = ssh.host_entry(paths, "dev")
    assert '  ProxyCommand "C:/Program Files/Microsandbox Studio/msb.exe" ssh serve' in entry
    assert '  IdentityFile "C:/Users/me/.microsandbox-studio/ssh/id_ed25519"' in entry


def test_render_config_is_sorted_and_stable(paths):
    text = ssh.render_config(paths, ["b", "a"])
    assert text.index("Host a.msb") < text.index("Host b.msb")
    assert text == ssh.render_config(paths, ["a", "b"])
    assert "Host " not in ssh.render_config(paths, [])


def test_set_up_writes_its_own_files_and_leaves_the_user_config_alone(paths):
    assert not ssh.is_set_up(paths)
    ssh.set_up(paths, ["dev"])
    assert ssh.is_set_up(paths)
    assert "Host dev.msb" in paths.config.read_text()
    assert stat.S_IMODE(paths.config.stat().st_mode) == 0o600
    assert not paths.user_config.exists()


def test_include_is_found_in_the_user_config(paths):
    assert not ssh.is_included(paths)
    paths.user_config.parent.mkdir()
    paths.user_config.write_text("Host *\n  ServerAliveInterval 30\n")
    assert not ssh.is_included(paths)
    paths.user_config.write_text("  include ~/.microsandbox-studio/ssh_config\n\nHost *\n")
    assert ssh.is_included(paths)
    paths.user_config.write_text("# " + ssh.INCLUDE + "\n")
    assert not ssh.is_included(paths)


def test_remove_undoes_set_up(paths):
    ssh.set_up(paths, ["dev"])
    ssh.remove(paths)
    assert not ssh.is_set_up(paths)
    assert not paths.config.parent.exists()
    ssh.remove(paths)


def test_write_config_only_after_set_up_and_only_on_changes(paths):
    ssh.write_config(paths, ["dev"])
    assert not paths.config.exists()
    ssh.set_up(paths, [])
    ssh.write_config(paths, ["dev"])
    assert "Host dev.msb" in paths.config.read_text()
    before = paths.config.stat().st_mtime_ns
    ssh.write_config(paths, ["dev"])
    assert paths.config.stat().st_mtime_ns == before
    ssh.write_config(paths, [])
    assert "Host " not in paths.config.read_text()
