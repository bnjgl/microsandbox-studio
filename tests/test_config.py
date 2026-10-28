import pytest
from pydantic import ValidationError

from microsandbox_studio import environment, network, workspaces
from microsandbox_studio.config import StoredConfig


def test_everything_the_app_reads_from_a_stored_config(stored, image_env):
    assert (stored.image_label, stored.oci_reference) == ("alpine:3.20", "alpine:3.20")
    assert stored.runtime.workdir == "/workspaces/project"
    assert (stored.resources.cpus, stored.resources.memory_mib) == (2, 1024)
    assert network.from_config(stored) == {"mode": "internet", "ports": [{"host": 18080, "guest": 80}]}
    assert workspaces.from_config(stored) == [{"source": "/home/me/project", "target": "/workspaces/project"}]
    assert environment.counts(stored, image_env) == {"variables": 2, "secrets": 2}
    assert environment.from_config(stored, image_env).model_dump() == {
        "env": {"MODE": "dev", "EXTRA": "1"},
        "secrets": {
            "TOKEN": {"value": "token-value", "allow": ["api.github.com"]},
            "INLINE": {"value": "plain", "allow": ["x.com"]},
        },
    }


def test_secret_hosts_read_as_entered(stored_config):
    stored_config["network"]["secrets"]["secrets"][0]["allowed_hosts"] = [{"exact": "api.github.com"}, "any"]
    secret = StoredConfig.model_validate(stored_config).network.secrets.secrets[0]
    assert secret.hosts == ["api.github.com", "*"]


@pytest.mark.parametrize("missing", ["image", "env", "resources", "runtime", "mounts", "network", "labels"])
def test_a_config_without_a_part_the_app_reads_is_refused(stored_config, missing):
    del stored_config[missing]
    with pytest.raises(ValidationError):
        StoredConfig.model_validate(stored_config)
