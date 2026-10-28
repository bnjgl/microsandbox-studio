from microsandbox_studio import api
from microsandbox_studio.models import NewSandbox


def test_api_exposes_only_its_methods():
    public = {name for name in dir(api.Api()) if not name.startswith("_")}
    assert public == {
        "create_sandbox",
        "delete_sandbox",
        "get_environment",
        "get_ssh",
        "list_sandboxes",
        "remove_ssh",
        "save_environment",
        "save_resources",
        "select_workspace_folders",
        "set_up_ssh",
        "start_sandbox",
        "stop_sandbox",
    }


def test_sync_runs_an_async_method_as_a_plain_one():
    class Probe:
        @api.async_to_sync
        async def double(self, value):
            return value * 2

    assert Probe().double(21) == 42
    assert Probe.double.__name__ == "double"


def test_new_sandbox_validates_the_whole_form(tmp_path):
    form = {
        "name": "dev",
        "image": "ubuntu:24.04",
        "cpus": 2,
        "memory": 1024,
        "folders": [str(tmp_path)],
        "environment": {"env": {"MODE": "dev"}},
        "network": {"mode": "none"},
    }
    new = NewSandbox.model_validate(form)
    assert (new.cpus, new.folders, new.environment.env, new.network.mode) == (
        2,
        [str(tmp_path.resolve())],
        {"MODE": "dev"},
        "none",
    )
    defaults = NewSandbox.model_validate({"name": "dev", "image": "ubuntu:24.04", "cpus": 1, "memory": 512})
    assert (defaults.folders, defaults.environment.secrets, defaults.network.mode) == ([], {}, "internet")
