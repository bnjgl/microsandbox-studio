import pytest
from microsandbox import Network
from pydantic import ValidationError

from microsandbox_studio import network
from microsandbox_studio.config import StoredConfig
from microsandbox_studio.models import NetworkSettings


def test_settings_default_to_internet():
    assert NetworkSettings().model_dump() == {"mode": "internet", "ports": []}
    settings = NetworkSettings.model_validate({"mode": "none", "ports": [{"host": 8080, "guest": 80}]})
    assert settings.model_dump() == {"mode": "none", "ports": [{"host": 8080, "guest": 80}]}


@pytest.mark.parametrize(
    ("data", "message"),
    [
        ({"mode": "restricted"}, "mode"),
        ({"mode": "all", "ports": [{"host": 0, "guest": 80}]}, "ports.0.host"),
        ({"mode": "all", "ports": [{"host": 80, "guest": None}]}, "ports.0.guest"),
        ({"mode": "all", "ports": [{"host": 80, "guest": 1}, {"host": 80, "guest": 2}]}, "only be published once"),
    ],
)
def test_settings_reject(data, message):
    with pytest.raises(ValidationError, match=message):
        NetworkSettings.model_validate(data)


def test_sdk_uses_the_preset_and_publishes_ports():
    result = network.sdk(NetworkSettings.model_validate({"mode": "all", "ports": [{"host": 8080, "guest": 80}]}))
    assert isinstance(result, Network)
    assert result.policy == Network.allow_all().policy
    assert result.ports == {8080: 80}


@pytest.mark.parametrize(
    ("labels", "mode"),
    [({"studio.network": "none"}, "none"), ({"studio.network": "all"}, "all"), ({}, "custom"), ({"x": "y"}, "custom")],
)
def test_from_config_reads_the_mode_label(stored_config, labels, mode):
    stored_config["labels"] = labels
    assert network.from_config(StoredConfig.model_validate(stored_config))["mode"] == mode
