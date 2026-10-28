import pytest
from pydantic import ValidationError

from microsandbox_studio import workspaces
from microsandbox_studio.config import StoredConfig
from microsandbox_studio.models import FOLDERS


def test_from_config_reads_only_workspace_binds(stored_config):
    stored_config["mounts"] += [
        {"type": "Bind", "host": "/h/data", "guest": "/data"},
        {"type": "Owned", "guest": "/workspaces/cache"},
    ]
    folders = workspaces.from_config(StoredConfig.model_validate(stored_config))
    assert folders == [{"source": "/home/me/project", "target": "/workspaces/project"}]


def test_folders_are_resolved_existing_folders_counted_once(tmp_path):
    (tmp_path / "app").mkdir()
    (tmp_path / "file").write_text("")
    app = str((tmp_path / "app").resolve())
    assert FOLDERS.validate_python([str(tmp_path / "app" / ".." / "app"), app]) == [app]
    with pytest.raises(ValidationError, match="not a folder"):
        FOLDERS.validate_python([str(tmp_path / "file")])
    with pytest.raises(ValidationError, match="folder not found"):
        FOLDERS.validate_python([str(tmp_path / "gone")])


def test_targets_get_a_free_numbered_name():
    folders = workspaces.with_targets(["/home/u/app", "/srv/app", "/", "/x/app/"])
    assert [folder["target"] for folder in folders] == [
        "/workspaces/app",
        "/workspaces/app-2",
        "/workspaces/workspace",
        "/workspaces/app-3",
    ]
    assert workspaces.with_targets(["/home/me/a\\b", "/home/me/C:"])[0]["target"] == "/workspaces/a\\b"


def test_volumes_bind_each_folder_at_its_target():
    assert list(workspaces.volumes(["/home/me/app", "/srv/app"])) == ["/workspaces/app", "/workspaces/app-2"]
