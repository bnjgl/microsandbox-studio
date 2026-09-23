import pytest

from microsandbox_studio import carryover, network


def restricted(rules=(), profiles=("public",), ports=()):
    return {"mode": "restricted", "profiles": list(profiles), "rules": list(rules), "ports": list(ports)}


def test_normalize_defaults_and_cleans_rules():
    assert network.normalize(None) == network.default()
    rule = {"action": "deny", "target": " API.Example.com ", "protocol": "tcp", "port": " 443 "}
    assert network.normalize(restricted([rule]))["rules"] == [
        {"action": "deny", "target": "api.example.com", "protocol": "tcp", "port": "443"}
    ]


def test_normalize_ignores_rules_outside_restricted_mode():
    result = network.normalize({**restricted([{"action": "x"}]), "mode": "all"})
    assert result == {"mode": "all", "profiles": [], "rules": [], "ports": []}


@pytest.mark.parametrize(
    ("target", "kind"),
    [
        ("10.0.0.1", "ip"),
        ("::1", "ip"),
        ("10.0.0.0/8", "cidr"),
        (".example.com", "suffix"),
        ("api.example.com", "domain"),
    ],
)
def test_target_kind(target, kind):
    assert network.target_kind(target) == kind


def test_normalize_rejects_duplicate_host_ports():
    port = {"host_port": 8080, "guest_port": 80, "protocol": "tcp"}
    with pytest.raises(ValueError, match="Port mapping 2: host port 8080/tcp is used twice"):
        network.normalize(restricted(ports=[port, port]))


def stored(egress, ingress, rules=(), **network_spec):
    policy = {"default_egress": egress, "default_ingress": ingress, "rules": list(rules)}
    return {"spec": {"network": {"policy": policy, **network_spec}}}


DNS = {
    "action": "allow",
    "destination": {"group": "host"},
    "protocols": ["udp", "tcp"],
    "ports": [{"start": 53, "end": 53}],
}


@pytest.mark.parametrize(
    ("config", "settings"),
    [
        ({}, network.default()),
        ({"spec": {"network": {"enabled": False}}}, {"mode": "none", "profiles": [], "rules": [], "ports": []}),
        (stored("allow", "allow"), {"mode": "all", "profiles": [], "rules": [], "ports": []}),
        (stored("deny", "deny"), {"mode": "none", "profiles": [], "rules": [], "ports": []}),
        (
            stored(
                "deny",
                "allow",
                [
                    {
                        "action": "deny",
                        "destination": {"domain": "evil.com"},
                        "protocols": ["tcp"],
                        "ports": [{"start": 443, "end": 443}],
                    },
                    {"action": "allow", "destination": {"cidr": "10.0.0.0/8"}, "ports": [{"start": 8000, "end": 9000}]},
                    {"action": "allow", "destination": {"group": "public"}},
                    {"action": "allow", "destination": {"group": "host"}},
                ],
                ports=[{"host_port": 8080, "guest_port": 80, "protocol": "Udp", "host_bind": "0.0.0.0"}],
            ),
            restricted(
                [
                    {"action": "deny", "target": "evil.com", "protocol": "tcp", "port": "443"},
                    {"action": "allow", "target": "10.0.0.0/8", "protocol": "", "port": "8000-9000"},
                ],
                profiles=("public", "host"),
                ports=[{"host_port": 8080, "guest_port": 80, "protocol": "udp", "bind": "0.0.0.0"}],
            ),
        ),
        (
            stored("deny", "allow", [{"action": "allow", "destination": {"domain_suffix": "example.com"}}, DNS]),
            restricted([{"action": "allow", "target": ".example.com", "protocol": "", "port": ""}], profiles=()),
        ),
    ],
)
def test_from_config_reads_app_written_networks(config, settings):
    assert network.from_config(config) == settings


def test_from_config_refuses_foreign_rule_order():
    rules = [
        {"action": "allow", "destination": {"group": "public"}},
        {"action": "deny", "destination": {"domain": "evil.com"}},
    ]
    config = {"spec": {"network": {"policy": {"default_egress": "deny", "default_ingress": "allow", "rules": rules}}}}
    assert network.from_config(config) is None


def test_carryover_plan_lists_every_problem():
    config = {
        "spec": {
            "mounts": [{"type": "Tmpfs", "guest": "/tmp"}],
            "network": {"strict": True, "secrets": {"violation_action": "block"}},
        }
    }
    with pytest.raises(ValueError) as error:
        carryover.plan(config)
    assert str(error.value).splitlines()[1:] == [
        "– Mount /tmp (Tmpfs) cannot be restored.",
        "– Network: strict mode cannot be carried over.",
        "– Secrets: secret_violation_action can only be set on creation.",
    ]


def test_carryover_with_network_replaces_network_only():
    plan = carryover.plan({"spec": {"resources": {"cpus": 2}, "network": {"enabled": False}, "labels": {"a": "b"}}})
    assert plan.restore["disable_network"] is True
    changed = carryover.with_network(plan, network.default())
    assert "disable_network" not in changed.restore
    assert changed.restore["cpus"] == 2
    assert changed.modify == {"labels": {"a": "b"}}
