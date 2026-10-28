import json
from pathlib import Path

import pytest

from microsandbox_studio.config import StoredConfig


@pytest.fixture
def stored_config():
    """A real config stored by microsandbox 0.7.11, as a fresh dict per test."""
    return json.loads((Path(__file__).parent / "stored_config.json").read_text())


@pytest.fixture
def stored(stored_config):
    return StoredConfig.model_validate(stored_config)


@pytest.fixture
def image_env():
    """What Image.inspect("alpine:3.20") reports as the image's variables."""
    return {"PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"}
