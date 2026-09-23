import pytest

from microsandbox_studio import carryover, workspaces


def _bind(host, guest, **options):
    return {"type": "Bind", "host": host, "guest": guest, "options": options}


def test_from_config_reads_only_workspace_binds():
    config = {
        "spec": {
            "mounts": [
                _bind("/h/app", "/workspaces/app"),
                _bind("/h/data", "/data"),
                {"type": "Owned", "guest": "/workspaces/cache"},
            ]
        }
    }
    assert workspaces.from_config(config) == [{"source": "/h/app", "target": "/workspaces/app"}]


def test_normalize_resolves_and_validates(tmp_path):
    (tmp_path / "app").mkdir()
    (tmp_path / "file").write_text("")
    folders = workspaces.normalize([{"source": str(tmp_path / "app" / ".." / "app"), "target": "/workspaces/app"}])
    assert folders == [{"source": str((tmp_path / "app").resolve()), "target": "/workspaces/app"}]
    with pytest.raises(ValueError, match="unique"):
        workspaces.normalize([*folders, {"source": str(tmp_path / "app"), "target": "/workspaces/other"}])
    with pytest.raises(ValueError, match="/workspaces/<folder name>"):
        workspaces.normalize([{"source": str(tmp_path / "app"), "target": "/data/app"}])
    with pytest.raises(ValueError, match="Not a folder"):
        workspaces.normalize([{"source": str(tmp_path / "file"), "target": "/workspaces/file"}])


def test_with_workspaces_replaces_workspace_mounts_only():
    config = {
        "spec": {
            "mounts": [
                _bind("/h/app", "/workspaces/app", readonly=True),
                _bind("/h/lib", "/workspaces/lib"),
                _bind("/h/data", "/data"),
            ],
            "runtime": {"workdir": "/workspaces/lib/src"},
            "labels": {"a": "b"},
        }
    }
    before = carryover.plan(config)
    current = workspaces.from_config(config)
    folders = [current[0], {"source": "/h/new", "target": "/workspaces/new"}]
    after = carryover.with_workspaces(before, current, folders)
    assert list(after.restore["volumes"]) == ["/data", "/workspaces/app", "/workspaces/new"]
    # Unchanged folders keep their mount options.
    assert after.restore["volumes"]["/workspaces/app"] is before.restore["volumes"]["/workspaces/app"]
    # The working directory was inside the removed folder.
    assert after.modify == {"labels": {"a": "b"}, "workdir": "/workspaces/app"}
    assert "workdir" not in carryover.with_workspaces(before, current, []).modify


def test_problem_explains_refusal():
    assert carryover.problem({"spec": {}}) is None
    assert "Tmpfs" in carryover.problem({"spec": {"mounts": [{"type": "Tmpfs", "guest": "/tmp"}]}})
