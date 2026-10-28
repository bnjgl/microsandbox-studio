import dataclasses
from typing import Any

from microsandbox import Network, NetworkProfile

from .config import StoredConfig
from .models import NetworkSettings

MODE_LABEL = "studio.network"

PRESETS = {
    "none": Network.none,
    "internet": lambda: Network.from_profiles(NetworkProfile.PUBLIC),
    "all": Network.allow_all,
}


def sdk(settings: NetworkSettings) -> Network:
    return dataclasses.replace(PRESETS[settings.mode](), ports={port.host: port.guest for port in settings.ports})


def from_config(stored: StoredConfig) -> dict[str, Any]:
    return {
        "mode": stored.labels.get(MODE_LABEL, "custom"),
        "ports": [{"host": port.host_port, "guest": port.guest_port} for port in stored.network.ports],
    }
