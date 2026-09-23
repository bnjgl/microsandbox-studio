"""Pure helpers for the stored sandbox config returned by ``SandboxHandle.config()``."""

import hashlib
import json
from typing import Any

type Config = dict[str, Any]

DEFAULT_SHELL = "/bin/sh"


def spec(config: Config) -> Config:
    """The sandbox spec; older configs store it at the top level."""
    return config.get("spec", config)


def shell(config: Config) -> str:
    return config.get("shell") or DEFAULT_SHELL


def image_label(config: Config) -> str:
    """Readable image name, e.g. from {"image": {"Oci": {"reference": ...}}}."""
    image = config.get("image") or config.get("image_name")
    if isinstance(image, dict) and len(image) == 1:
        image = next(iter(image.values()))
    if isinstance(image, dict):
        image = image.get("reference") or image.get("path")
    return image if isinstance(image, str) and image else "—"


def revision(settings: Any) -> str:
    """Stable fingerprint of settings, to detect changes made in the meantime."""
    return hashlib.sha256(json.dumps(settings, sort_keys=True).encode()).hexdigest()
