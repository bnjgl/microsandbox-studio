"""Network settings: the settings form, the stored sandbox config and SDK objects.

See https://docs.microsandbox.dev/networking/overview. The app offers three
modes. "restricted" is microsandbox's deny-by-default policy built from
profiles (public, private, host) plus own egress rules, which are evaluated
before the profile rules. Published ports work in every mode except "none",
which also denies inbound traffic.
"""

import ipaddress
import re
from collections.abc import Iterable, Iterator
from itertools import product
from typing import Any

from microsandbox import (
    Action,
    DestGroup,
    Destination,
    Direction,
    NetworkPolicy,
    NetworkProfile,
    PortBinding,
    PortProtocol,
    Protocol,
    Rule,
)

from .config import Config
from .config import spec as config_spec

type Settings = dict[str, Any]

MODES = ("none", "restricted", "all")
PROFILES = ("public", "private", "host")
PROTOCOLS = ("", "tcp", "udp")

_DOMAIN = re.compile(
    r"^(?=.{1,253}$)([A-Za-z0-9_]([A-Za-z0-9_-]{0,61}[A-Za-z0-9])?\.)*[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?$"
)
_RANGE = re.compile(r"^(\d{1,5})(?:-(\d{1,5}))?$")


def default() -> Settings:
    """Microsandbox's own default: public internet, no published ports."""
    return {"mode": "restricted", "profiles": ["public"], "rules": [], "ports": []}


def _span_text(span: dict[str, int]) -> str:
    """A stored port span as "443" or "8000-9000"."""
    return str(span["start"]) if span["start"] == span["end"] else f"{span['start']}-{span['end']}"


# Settings form


def _port_number(value: Any, where: str) -> int:
    if type(value) is not int or not 1 <= value <= 65535:
        raise ValueError(f"{where}: enter a port from 1 to 65535.")
    return value


def _port_range(value: Any, where: str) -> str:
    text = str(value if value is not None else "").strip()
    if not text:
        return ""
    match = _RANGE.fullmatch(text)
    if not match or not 1 <= int(match[1]) <= int(match[2] or match[1]) <= 65535:
        raise ValueError(f"{where}: enter a port or range such as 443 or 8000-9000.")
    return text


def target_kind(target: str) -> str:
    """Kind of a rule target: ip, cidr, suffix or domain. Raises ValueError otherwise."""
    try:
        ipaddress.ip_address(target)
        return "ip"
    except ValueError:
        pass
    if "/" in target:
        ipaddress.ip_network(target, strict=False)
        return "cidr"
    if not _DOMAIN.fullmatch(target.removeprefix(".")):
        raise ValueError
    return "suffix" if target.startswith(".") else "domain"


def _profiles(value: Any) -> list[str]:
    profiles = value or []
    if not isinstance(profiles, list) or any(profile not in PROFILES for profile in profiles):
        raise ValueError("Network: invalid profile.")
    return [profile for profile in PROFILES if profile in profiles]


def _rule(index: int, rule: Any) -> dict[str, str]:
    where = f"Rule {index}"
    if (
        not isinstance(rule, dict)
        or rule.get("action") not in ("allow", "deny")
        or rule.get("protocol", "") not in PROTOCOLS
    ):
        raise ValueError(f"{where}: invalid values.")
    target = str(rule.get("target") or "").strip().lower()
    try:
        target_kind(target)
    except ValueError:
        raise ValueError(f'{where}: "{target}" is not a domain, .domain suffix, IP address or CIDR.') from None
    return {
        "action": rule["action"],
        "target": target,
        "protocol": rule.get("protocol", ""),
        "port": _port_range(rule.get("port"), where),
    }


def _port(index: int, port: Any) -> dict[str, Any]:
    where = f"Port mapping {index}"
    if not isinstance(port, dict) or port.get("protocol") not in ("tcp", "udp"):
        raise ValueError(f"{where}: invalid values.")
    bind = str(port.get("bind") or "127.0.0.1").strip()
    try:
        ipaddress.ip_address(bind)
    except ValueError:
        raise ValueError(f'{where}: "{bind}" is not an IP address.') from None
    return {
        "host_port": _port_number(port.get("host_port"), f"{where}, host port"),
        "guest_port": _port_number(port.get("guest_port"), f"{where}, sandbox port"),
        "protocol": port["protocol"],
        "bind": bind,
    }


def _ports(values: Iterable[Any]) -> Iterator[dict[str, Any]]:
    """Validated port bindings; stops at the first invalid or duplicate host port."""
    seen: set[tuple[int, str]] = set()
    for index, value in enumerate(values, 1):
        port = _port(index, value)
        key = (port["host_port"], port["protocol"])
        if key in seen:
            raise ValueError(f"Port mapping {index}: host port {port['host_port']}/{port['protocol']} is used twice.")
        seen.add(key)
        yield port


def normalize(data: Any) -> Settings:
    """Validate network settings from the frontend."""
    if data is None:
        return default()
    if not isinstance(data, dict) or set(data) - {"mode", "profiles", "rules", "ports"}:
        raise ValueError("Invalid network settings.")
    mode = data.get("mode")
    if mode not in MODES:
        raise ValueError("Network: invalid mode.")
    restricted = mode == "restricted"
    return {
        "mode": mode,
        "profiles": _profiles(data.get("profiles")) if restricted else [],
        "rules": [_rule(index, rule) for index, rule in enumerate(data.get("rules") or [], 1)] if restricted else [],
        "ports": list(_ports(data.get("ports") or [])),
    }


# SDK objects

_DESTINATIONS = {
    "ip": Destination.ip,
    "cidr": Destination.cidr,
    "suffix": Destination.domain_suffix,
    "domain": Destination.domain,
}


def _destination(target: str) -> Any:
    return _DESTINATIONS[target_kind(target)](target)


def policy(settings: Settings) -> NetworkPolicy:
    if settings["mode"] == "none":
        return NetworkPolicy.none()
    if settings["mode"] == "all":
        return NetworkPolicy.allow_all()
    own = tuple(
        Rule(
            Action(rule["action"]),
            Direction.EGRESS,
            _destination(rule["target"]),
            Protocol(rule["protocol"]) if rule["protocol"] else None,
            rule["port"] or None,
        )
        for rule in settings["rules"]
    )
    # Profiles bring gateway DNS; own allow rules for domains need it as well.
    needs_dns = not settings["profiles"] and any(rule["action"] == "allow" for rule in settings["rules"])
    dns = Rule.allow_dns() if needs_dns else ()
    generated = NetworkPolicy.from_profiles(NetworkProfile(profile) for profile in settings["profiles"])
    return NetworkPolicy(
        default_egress=Action.DENY, default_ingress=Action.ALLOW, rules=own + tuple(dns) + tuple(generated.rules)
    )


def ports(settings: Settings) -> list[PortBinding]:
    return [
        PortBinding(port["host_port"], port["guest_port"], bind=port["bind"], protocol=PortProtocol(port["protocol"]))
        for port in settings["ports"]
    ]


# Stored config (serialized Rust NetworkSpec: policy.rules[].destination is
# "any" or {"cidr"|"domain"|"domain_suffix"|"group": value})


def spec(config: Config) -> dict[str, Any]:
    return config_spec(config).get("network") or {}


def _is_dns(rule: dict[str, Any]) -> bool:
    return (
        rule.get("action") == "allow"
        and rule.get("destination") == {"group": "host"}
        and set(rule.get("protocols") or ()) <= {"udp", "tcp"}
        and rule.get("protocols")
        and rule.get("ports") == [{"start": 53, "end": 53}]
    )


def _target_text(destination: Any) -> str | None:
    if not isinstance(destination, dict) or len(destination) != 1:
        return None
    match next(iter(destination.items())):
        case "cidr", value:
            network = ipaddress.ip_network(value, strict=False)
            return str(network.network_address) if network.prefixlen == network.max_prefixlen else str(network)
        case "domain", value:
            return value
        case "domain_suffix", value:
            return f".{value.removeprefix('.')}"
    return None


def _stored_ports(network: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "host_port": port["host_port"],
            "guest_port": port["guest_port"],
            "protocol": str(port.get("protocol") or "tcp").lower(),
            "bind": port.get("host_bind") or port.get("bind") or "127.0.0.1",
        }
        for port in network.get("ports") or []
    ]


def _profile(rule: dict[str, Any]) -> str | None:
    """The profile an app-written rule stands for, e.g. {"group": "public"} → "public"."""
    destination = rule.get("destination")
    group = destination.get("group") if isinstance(destination, dict) else None
    plain = not rule.get("protocols") and not rule.get("ports")
    return group if rule.get("action") == "allow" and group in PROFILES and plain else None


def _own_rule(rule: dict[str, Any]) -> dict[str, str] | None:
    """Form rule for a stored rule, or None if the form cannot represent it."""
    target = _target_text(rule.get("destination"))
    protocols, spans = rule.get("protocols") or [], rule.get("ports") or []
    if target is None or len(protocols) > 1 or len(spans) > 1 or (protocols and protocols[0] not in ("tcp", "udp")):
        return None
    return {
        "action": rule.get("action"),
        "target": target,
        "protocol": protocols[0] if protocols else "",
        "port": _span_text(spans[0]) if spans else "",
    }


def _form_rules(rules: list[dict[str, Any]]) -> tuple[list[str], list[dict[str, str]]] | None:
    """Split stored rules into profiles and own rules, or None if the form cannot show them.

    The app writes own rules first, then the profile rules, and adds a DNS rule
    when needed. Any other order or shape would change the meaning.
    """
    profiles, own = [], []
    for rule in rules:
        if rule.get("direction", "egress") != "egress":
            return None
        if _is_dns(rule):
            continue
        if profile := _profile(rule):
            profiles.append(profile)
            continue
        converted = _own_rule(rule)
        if profiles or converted is None:
            return None
        own.append(converted)
    return profiles, own


def from_config(config: Config) -> Settings | None:
    """Form settings for a stored config, or None if the form cannot represent it."""
    network = spec(config)
    stored = network.get("policy")
    base = {**default(), "ports": _stored_ports(network)}
    if network.get("enabled") is False:
        return normalize({**base, "mode": "none"})
    if not stored:
        return normalize(base)
    defaults = stored.get("default_egress", "deny"), stored.get("default_ingress", "deny")
    rules = stored.get("rules") or []
    match defaults:
        case ("allow", "allow") if not rules:
            return normalize({**base, "mode": "all"})
        case ("deny", "deny") if not rules:
            return normalize({**base, "mode": "none"})
        case ("deny", "allow"):
            if (split := _form_rules(rules)) is None:
                return None
            profiles, own = split
            return normalize({**base, "profiles": profiles, "rules": own})
    return None


def _stored_destination(destination: Any) -> Any:
    if destination in (None, "any"):
        return Destination.any()
    if "group" in destination:
        return Destination.group(DestGroup(destination["group"].replace("_", "-")))
    return _destination(_target_text(destination))


def stored_policy(config: Config) -> NetworkPolicy:
    """Rebuild any stored policy, including ones the form cannot show."""
    stored = spec(config).get("policy")
    if not stored:
        return policy(default())
    rules = tuple(
        Rule(
            Action(rule["action"]),
            Direction(rule.get("direction", "egress")),
            _stored_destination(rule.get("destination")),
            Protocol(protocol) if protocol else None,
            _span_text(span) if span else None,
        )
        for rule in stored.get("rules") or []
        for protocol, span in product(rule.get("protocols") or [None], rule.get("ports") or [None])
    )
    return NetworkPolicy(
        default_egress=Action(stored.get("default_egress", "deny")),
        default_ingress=Action(stored.get("default_ingress", "deny")),
        rules=rules,
    )


def stored_ports(config: Config) -> list[PortBinding]:
    return ports({"ports": _stored_ports(spec(config))})
