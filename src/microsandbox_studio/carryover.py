"""Settings a disk snapshot does not keep, read from the source sandbox config.

A local disk snapshot holds the writable disk, the image and the default user
(see ``RestoreDefaults`` in microsandbox). Everything else starts from defaults
on ``Sandbox.restore()``. The app re-applies what it can: CPUs, memory, host
folders and network on restore; variables, secrets, labels and the working
directory with ``modify()`` right after. ``plan()`` refuses before anything is
touched if a setting would be lost.

Each reader returns what it can carry over together with the problems it
found, so ``plan()`` can report all of them at once.
"""

from pathlib import PurePosixPath
from typing import Any, NamedTuple

from microsandbox import Volume

from . import environment, network, workspaces
from .config import Config
from .config import spec as config_spec

type Problems = list[str]

# Shown in the dialogs, so users know what a re-created sandbox keeps.
KEPT = (
    "sandbox files, image, CPUs, memory, workspace folders, variables, secrets, labels, working directory and network"
)

# Restore argument and stored name of the connection limits.
_LIMITS = (("max_tcp_connections", "max_connections"), ("max_udp_connections", "max_udp_connections"))


class Plan(NamedTuple):
    restore: dict[str, Any]
    modify: dict[str, Any]


def _resources(spec: Config) -> dict[str, Any]:
    resources = spec.get("resources") or {}
    return {
        key: value for key, value in (("cpus", resources.get("cpus")), ("memory", resources.get("memory_mib"))) if value
    }


def _bind(mount: dict[str, Any]) -> Volume:
    options = mount.get("options") or {}
    return Volume.bind(
        str(mount["host"]),
        readonly=bool(options.get("readonly") or mount.get("readonly")),
        noexec=bool(options.get("noexec")),
        nosuid=bool(options.get("nosuid")),
        nodev=bool(options.get("nodev")),
    )


def _volumes(spec: Config) -> tuple[dict[str, Volume], Problems]:
    # Owned volumes are part of the snapshot.
    mounts = [mount for mount in spec.get("mounts") or [] if mount.get("type") != "Owned"]
    volumes = {mount["guest"]: _bind(mount) for mount in mounts if mount.get("type") == "Bind"}
    problems = [
        f"Mount {mount.get('guest', '?')} ({mount.get('type')}) cannot be restored."
        for mount in mounts
        if mount.get("type") != "Bind"
    ]
    return volumes, problems


def _network(spec: Config) -> tuple[dict[str, Any], Problems]:
    stored = spec.get("network") or {}
    dns = stored.get("dns") or {}
    unsupported = (
        (stored.get("strict"), "strict mode"),
        (dns.get("nameservers"), "custom DNS servers"),
        (dns.get("rebind_protection") is False, "disabled DNS rebinding protection"),
        (stored.get("rate_limiter"), "rate limits"),
        (stored.get("outbound_proxy"), "outbound proxy"),
        (stored.get("trust_host_cas"), "host CAs"),
    )
    problems = [f"Network: {label} cannot be carried over." for present, label in unsupported if present]
    limits = {key: stored.get(name, stored.get(key)) for key, name in _LIMITS}
    options = {
        "network_policy": network.stored_policy(spec),
        "ports": network.stored_ports(spec),
        **({"disable_network": True} if stored.get("enabled") is False else {}),
        **{key: value for key, value in limits.items() if value is not None},
    }
    return options, problems


def _secrets(config: Config) -> tuple[tuple[dict[str, str], dict[str, Any]], Problems]:
    settings, placeholders = environment.from_config(config)
    defaults = environment.secret_defaults()

    def secret_problems(key: str, secret: environment.SecretSettings) -> Problems:
        changed = [field for field in environment.CREATE_ONLY_FIELDS if secret[field] != defaults[field]]
        problems = [f"Secret {key}: {', '.join(changed)} can only be set on creation."] if changed else []
        try:
            environment.require_host_variable(key, secret)
        except ValueError as exc:
            problems.append(str(exc))
        return problems

    problems = [
        *(
            ["Secrets: secret_violation_action can only be set on creation."]
            if settings["secret_violation_action"] != environment.DEFAULT_ACTION
            else []
        ),
        *(problem for key, secret in settings["secrets"].items() for problem in secret_problems(key, secret)),
    ]
    secrets = {
        key: environment.modify_spec(key, secret, placeholders.get(key)) for key, secret in settings["secrets"].items()
    }
    return (settings["env"], secrets), problems


def plan(config: Config) -> Plan:
    """Restore and modify arguments for a copy of this config. Raises if something would be lost."""
    spec = config_spec(config)
    volumes, volume_problems = _volumes(spec)
    network_options, network_problems = _network(spec)
    (env, secrets), secret_problems = _secrets(config)
    if problems := volume_problems + network_problems + secret_problems:
        raise ValueError("The sandbox cannot be rebuilt without losing settings:\n– " + "\n– ".join(problems))
    runtime = spec.get("runtime") or {}
    modify = {
        "env": env,
        "secrets": secrets,
        "labels": spec.get("labels") or {},
        "workdir": runtime.get("workdir") or spec.get("workdir"),
    }
    return Plan(
        {**_resources(spec), "volumes": volumes, **network_options},
        {key: value for key, value in modify.items() if value},
    )


def problem(config: Config) -> str | None:
    """Why the sandbox cannot be re-created without loss, or None."""
    try:
        plan(config)
    except ValueError as exc:
        return str(exc)
    return None


def with_network(plan: Plan, settings: network.Settings) -> Plan:
    """The same plan, restoring with new network settings instead of the stored ones."""
    restore = {key: value for key, value in plan.restore.items() if key != "disable_network"}
    return plan._replace(
        restore={**restore, "network_policy": network.policy(settings), "ports": network.ports(settings)}
    )


def with_workspaces(plan: Plan, current: workspaces.Folders, folders: workspaces.Folders) -> Plan:
    """The same plan with other workspace folders; other mounts stay as they are.

    Unchanged folders keep their stored mount options. A working directory
    inside a removed folder, or none at all, moves to the first folder, as on
    create; without folders it falls back to the image default.
    """
    stored = plan.restore["volumes"]
    volumes = {guest: volume for guest, volume in stored.items() if not workspaces.is_target(guest)}
    volumes |= {
        folder["target"]: stored[folder["target"]] if folder in current else Volume.bind(folder["source"])
        for folder in folders
    }
    removed = [PurePosixPath(folder["target"]) for folder in current if folder not in folders]
    modify = {key: value for key, value in plan.modify.items() if key != "workdir"}
    workdir = plan.modify.get("workdir")
    if workdir is None or any(PurePosixPath(workdir).is_relative_to(target) for target in removed):
        workdir = folders[0]["target"] if folders else None
    return Plan({**plan.restore, "volumes": volumes}, modify | ({"workdir": workdir} if workdir else {}))
