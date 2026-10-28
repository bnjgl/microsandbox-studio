import pytest
from pydantic import ValidationError

from microsandbox_studio import environment
from microsandbox_studio.config import StoredConfig
from microsandbox_studio.models import EnvironmentSettings


def settings(env=None, **secrets):
    return EnvironmentSettings.model_validate({"env": env or {"MODE": "dev"}, "secrets": secrets})


def test_settings_clean_hosts():
    result = settings(TOKEN={"value": "t", "allow": [" api.github.com ", ""]}).model_dump()
    assert result["secrets"] == {"TOKEN": {"value": "t", "allow": ["api.github.com"]}}


@pytest.mark.parametrize(
    ("data", "message"),
    [
        ({"env": {"1X": "v"}}, "env.1X.\\[key\\]"),
        ({"env": {"A": "v"}, "secrets": {"A": {"value": "x", "allow": ["a"]}}}, "both a variable and a secret"),
        ({"secrets": {"A": {"value": "x", "allow": [" "]}}}, "at least one allowed host"),
        ({"secrets": {"A": {"value": "", "allow": ["a"]}}}, "secrets.A.value"),
        ({"env": {"A": "x\0"}}, "env.A"),
    ],
)
def test_settings_reject(data, message):
    with pytest.raises(ValidationError, match=message):
        EnvironmentSettings.model_validate(data)


def test_variables_from_the_image_are_left_out_unless_changed(stored_config):
    image_env = {"PATH": "/usr/bin:/bin", "HOME": "/root"}
    stored_config["env"] = [{"key": "PATH", "value": "/usr/bin:/bin"}, {"key": "HOME", "value": "/home/dev"}]
    before = environment.from_config(StoredConfig.model_validate(stored_config), image_env)
    assert before.env == {"HOME": "/home/dev"}
    patch = environment.modify_patch(before.model_copy(update={"env": {}}), before)
    assert (patch["env"], patch["env_rm"]) == ({}, ["HOME"])


def test_from_config_refuses_secrets_set_up_outside_the_app(stored_config):
    stored_config["network"]["secrets"]["secrets"][0]["source"] = {"kind": "env", "var": "GH_TOKEN"}
    with pytest.raises(ValueError, match="TOKEN: secret set up outside Microsandbox Studio"):
        environment.from_config(StoredConfig.model_validate(stored_config), {})


def test_modify_patch_only_contains_changes():
    before = settings(TOKEN={"value": "old", "allow": ["a.com"]}, KEEP={"value": "k", "allow": ["k.com"]})
    after = settings({"NEW": "1"}, TOKEN={"value": "new", "allow": ["b.com"]}, KEEP={"value": "k", "allow": ["k.com"]})
    assert environment.modify_patch(after, before) == {
        "env": {"NEW": "1"},
        "env_rm": ["MODE"],
        "secrets": {"TOKEN": {"value": "new", "allowed_hosts": ["b.com"]}},
        "secrets_rm": [],
    }


def test_create_secrets():
    entries = environment.create_secrets(
        settings(A={"value": "a", "allow": ["a.com"]}, B={"value": "b", "allow": ["*"]})
    )
    assert [(entry.env_var, entry.value) for entry in entries] == [("A", "a"), ("B", "b")]
