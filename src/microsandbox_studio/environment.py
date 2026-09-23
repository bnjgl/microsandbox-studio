"""Environment variables and secrets in the documented sandbox YAML shape.

See https://docs.microsandbox.dev/sandboxes/secrets#yaml-configuration.
Settings are always normalized: every secret carries all fields, and a secret
value of "" means "host variable with the same name" (``${KEY}``).
"""

import os
import re
from collections.abc import Callable, Mapping
from typing import Any
from uuid import uuid4

from microsandbox import Secret, SecretSubstitution, ViolationAction

from .config import Config, spec

type Settings = dict[str, Any]
type SecretSettings = dict[str, Any]

VIOLATION_ACTIONS = ("block-and-log", "block", "block-and-terminate")
DEFAULT_ACTION = "block-and-log"
LOCATIONS = ("headers", "query", "body")
# The Python SDK's modify() only accepts source, allowed hosts and placeholder.
CREATE_ONLY_FIELDS = ("substitution", "passthrough", "violation_action", "require_tls_identity")

_KEY = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_REFERENCE = re.compile(r"^\$\{([A-Za-z_][A-Za-z0-9_]*)\}$")


def secret_defaults() -> SecretSettings:
    return {
        "value": "",
        "allow": [],
        "substitution": {"headers": True, "query": False, "body": False},
        "passthrough": [],
        "violation_action": None,
        "require_tls_identity": True,
    }


def defaults() -> dict[str, Any]:
    """The defaults the frontend fills in; this module is their only source."""
    return {"secret": secret_defaults(), "secret_violation_action": DEFAULT_ACTION}


# Validation


def _mapping(value: Any, where: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        # A ValueError like every other validation message shown to the user.
        raise ValueError(f"{where} must be a mapping NAME: ….")  # noqa: TRY004
    return value


def _only_fields(value: dict[str, Any], allowed: Any, where: str) -> None:
    if unknown := set(value) - set(allowed):
        raise ValueError(f"{where}: unknown field {', '.join(sorted(unknown))}.")


def _key(key: Any) -> str:
    if not isinstance(key, str) or not _KEY.fullmatch(key):
        raise ValueError(f'Invalid name "{key}": letters, digits and _ only, not starting with a digit.')
    return key


def _text(value: Any, where: str) -> str:
    if not isinstance(value, str) or "\0" in value:
        raise ValueError(f"{where} must be text without NUL characters.")
    return value


def _hosts(value: Any, where: str) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(host, str) or not host.strip() for host in value):
        raise ValueError(f"{where} must be a list of hosts.")
    return [host.strip() for host in value]


def _action(value: Any, where: str) -> Any:
    if value not in VIOLATION_ACTIONS:
        raise ValueError(f"{where}: invalid action.")
    return value


def _secret(key: str, value: Any) -> SecretSettings:
    where = f"secrets.{key}"
    given = _mapping(value, where)
    _only_fields(given, secret_defaults(), where)
    merged = {**secret_defaults(), **given}
    text = "" if merged["value"] in (None, f"${{{key}}}") else _text(merged["value"], f"{where}.value")
    allow = _hosts(merged["allow"], f"{where}.allow")
    if not allow:
        raise ValueError(f"{where}: enter at least one allowed host (allow).")
    passthrough = _hosts(merged["passthrough"], f"{where}.passthrough")
    substitution = _mapping(merged["substitution"], f"{where}.substitution")
    _only_fields(substitution, LOCATIONS, f"{where}.substitution")
    substitution = {**secret_defaults()["substitution"], **substitution}
    flags = [*substitution.values(), merged["require_tls_identity"]]
    if any(type(flag) is not bool for flag in flags):
        raise ValueError(f"{where}: substitution and require_tls_identity expect true/false.")
    if merged["violation_action"] is not None:
        _action(merged["violation_action"], f"{where}.violation_action")
    return {**merged, "value": text, "allow": allow, "substitution": substitution, "passthrough": passthrough}


def _variable_conflict(key: str, env: Mapping[str, str]) -> str:
    if key in env:
        raise ValueError(f"{key} is both a variable and a secret.")
    return key


def normalize(data: Any) -> Settings:
    """Validate settings from the frontend and fill in defaults."""
    data = _mapping(data, "The configuration")
    _only_fields(data, ("env", "secrets", "secret_violation_action"), "Konfiguration")
    action = _action(data.get("secret_violation_action") or DEFAULT_ACTION, "secret_violation_action")
    env = {_key(key): _text(value, f"env.{key}") for key, value in _mapping(data.get("env"), "env").items()}
    secrets = {
        _variable_conflict(_key(key), env): _secret(key, value)
        for key, value in _mapping(data.get("secrets"), "secrets").items()
    }
    return {"env": env, "secrets": secrets, "secret_violation_action": action}


# Stored config


def _stored_hosts(item: dict[str, Any], field: str) -> list[str]:
    def host(value: Any) -> str:
        if value in ("any", "Any"):
            return "*"
        return value if isinstance(value, str) else next(iter(value.values()))

    return [host(value) for value in item.get(field, [])]


def _stored_env(stored: Any) -> dict[str, str]:
    if not isinstance(stored, list):
        return stored
    if all(isinstance(item, dict) for item in stored):
        return {item["key"]: item["value"] for item in stored}
    return dict(stored)


def _stored_secret(item: dict[str, Any]) -> SecretSettings:
    key, source = item["env_var"], item.get("source")
    if source and source.get("kind") != "env":
        raise ValueError(f"{key}: this secret source is not supported by Microsandbox Studio.")
    return {
        "value": f"${{{source['var']}}}" if source else item.get("value", ""),
        "allow": _stored_hosts(item, "allowed_hosts"),
        "passthrough": _stored_hosts(item, "passthrough_hosts"),
        **{
            field: item[field]
            for field in ("substitution", "require_tls_identity", "violation_action")
            if field in item
        },
    }


def from_config(config: Config) -> tuple[Settings, dict[str, str]]:
    """Read settings and secret placeholders from a stored sandbox config."""
    stored = spec(config)
    network_secrets = (stored.get("network") or {}).get("secrets") or {}
    items = network_secrets.get("secrets", [])
    secrets = {item["env_var"]: _stored_secret(item) for item in items}
    placeholders = {item["env_var"]: item["placeholder"] for item in items if item.get("placeholder")}
    # Secret placeholders are also stored in the guest environment.
    env = {key: value for key, value in _stored_env(stored.get("env") or {}).items() if key not in secrets}
    settings = normalize(
        {"env": env, "secrets": secrets, "secret_violation_action": network_secrets.get("violation_action")}
    )
    return settings, placeholders


# Host variables and SDK arguments


def host_reference(key: str, secret: SecretSettings) -> str | None:
    """Name of the host variable a secret reads from, or None for an inline value."""
    if not secret["value"]:
        return key
    match = _REFERENCE.fullmatch(secret["value"])
    return match[1] if match else None


def require_host_variable(key: str, secret: SecretSettings, environ: Mapping[str, str] = os.environ) -> None:
    variable = host_reference(key, secret)
    if variable and not environ.get(variable):
        raise ValueError(f"{key}: host variable {variable} is not set in the environment of Microsandbox Studio.")


def modify_spec(key: str, secret: SecretSettings, placeholder: str | None = None) -> dict[str, Any]:
    """Secret entry for ``Sandbox.modify(secrets=...)``."""
    variable = host_reference(key, secret)
    source = {"env": variable} if variable else {"value": secret["value"]}
    return {**source, "allowed_hosts": secret["allow"], **({"placeholder": placeholder} if placeholder else {})}


def create_secrets(
    settings: Settings, inert: Callable[[], str] = lambda: uuid4().hex
) -> tuple[list[Secret], dict[str, Any]]:
    """``Sandbox.create(secrets=...)`` entries and the references to switch to right after.

    Python create() only accepts inline secret values. Reference-backed secrets
    start with ``inert`` random material and are switched to their host variable
    afterwards with ``modify()``, so real credentials are never stored by the app.
    """
    references = {
        key: modify_spec(key, secret) for key, secret in settings["secrets"].items() if host_reference(key, secret)
    }

    def entry(key: str, secret: SecretSettings) -> Secret:
        action = secret["violation_action"]
        return Secret.env(
            key,
            value=inert() if key in references else secret["value"],
            allow=secret["allow"],
            passthrough=secret["passthrough"],
            require_tls_identity=secret["require_tls_identity"],
            substitution=SecretSubstitution(**secret["substitution"]),
            violation_action=ViolationAction(action) if action else None,
        )

    return [entry(key, secret) for key, secret in settings["secrets"].items()], references


def create_only_change(settings: Settings, before: Settings) -> str | None:
    """First change the SDK only accepts at creation time, as a message."""
    if settings["secret_violation_action"] != before["secret_violation_action"]:
        return "secret_violation_action can only be set on creation."
    return next(
        (
            f"{key}: {field} can only be set on creation."
            for key, secret in settings["secrets"].items()
            for field in CREATE_ONLY_FIELDS
            if secret[field] != (before["secrets"].get(key) or secret_defaults())[field]
        ),
        None,
    )


def modify_patch(
    settings: Settings,
    before: Settings,
    placeholders: Mapping[str, str],
    environ: Mapping[str, str] = os.environ,
) -> dict[str, Any]:
    """``Sandbox.modify()`` arguments that turn ``before`` into ``settings``."""

    def changed_secret(key: str, secret: SecretSettings) -> dict[str, Any]:
        require_host_variable(key, secret, environ)
        return modify_spec(key, secret, placeholders.get(key))

    return {
        "env": {key: value for key, value in settings["env"].items() if before["env"].get(key) != value},
        "env_rm": sorted(before["env"].keys() - settings["env"].keys()),
        "secrets": {
            key: changed_secret(key, secret)
            for key, secret in settings["secrets"].items()
            if before["secrets"].get(key) != secret
        },
        "secrets_rm": sorted(before["secrets"].keys() - settings["secrets"].keys()),
    }
