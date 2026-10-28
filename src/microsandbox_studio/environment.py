from collections.abc import Collection, Mapping
from typing import Any

from microsandbox import Secret

from .config import StoredConfig
from .models import EnvironmentSettings


def _own_env(stored: StoredConfig, image_env: Mapping[str, str], secrets: Collection[str]) -> dict[str, str]:
    return {var.key: var.value for var in stored.env if var.key not in secrets and image_env.get(var.key) != var.value}


def from_config(stored: StoredConfig, image_env: Mapping[str, str]) -> EnvironmentSettings:
    items = stored.network.secrets.secrets
    if unsupported := [item.env_var for item in items if item.source]:
        raise ValueError(f"{', '.join(unsupported)}: secret set up outside Microsandbox Studio, which it cannot edit.")
    secrets = {item.env_var: {"value": item.value, "allow": item.hosts} for item in items}
    return EnvironmentSettings(env=_own_env(stored, image_env, secrets), secrets=secrets)


def counts(stored: StoredConfig, image_env: Mapping[str, str]) -> dict[str, int]:
    secrets = {item.env_var for item in stored.network.secrets.secrets}
    return {"variables": len(_own_env(stored, image_env, secrets)), "secrets": len(secrets)}


def create_secrets(settings: EnvironmentSettings) -> list[Secret]:
    return [Secret.env(key, value=secret.value, allow=secret.allow) for key, secret in settings.secrets.items()]


def modify_patch(settings: EnvironmentSettings, before: EnvironmentSettings) -> dict[str, Any]:
    return {
        "env": {key: value for key, value in settings.env.items() if before.env.get(key) != value},
        "env_rm": sorted(before.env.keys() - settings.env.keys()),
        "secrets": {
            key: {"value": secret.value, "allowed_hosts": secret.allow}
            for key, secret in settings.secrets.items()
            if before.secrets.get(key) != secret
        },
        "secrets_rm": sorted(before.secrets.keys() - settings.secrets.keys()),
    }
