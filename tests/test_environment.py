import pytest

from microsandbox_studio import environment


def settings(**secrets):
    return environment.normalize({"env": {"MODE": "dev"}, "secrets": secrets})


def test_normalize_fills_defaults_and_drops_self_reference():
    result = environment.normalize({"secrets": {"TOKEN": {"value": "${TOKEN}", "allow": [" api.github.com "]}}})
    assert result["secret_violation_action"] == "block-and-log"
    assert result["secrets"]["TOKEN"] == {**environment.secret_defaults(), "allow": ["api.github.com"]}


@pytest.mark.parametrize(
    ("data", "message"),
    [
        ({"env": {"1X": "v"}}, "Invalid name"),
        ({"env": {"A": "v"}, "secrets": {"A": {"allow": ["a"]}}}, "both a variable and a secret"),
        ({"secrets": {"A": {}}}, "at least one allowed host"),
        ({"secrets": {"A": {"allow": ["a"], "substitution": {"body": 1}}}}, "true/false"),
        ({"other": 1}, "unknown field other"),
    ],
)
def test_normalize_rejects(data, message):
    with pytest.raises(ValueError, match=message):
        environment.normalize(data)


def test_from_config_reads_secret_source_and_placeholder():
    config = {
        "spec": {
            "env": [{"key": "A", "value": "1"}, {"key": "TOKEN", "value": "$MSB_TOKEN"}],
            "network": {
                "secrets": {
                    "secrets": [
                        {
                            "env_var": "TOKEN",
                            "allowed_hosts": ["any", {"Exact": "x.com"}],
                            "source": {"kind": "env", "var": "GH"},
                            "placeholder": "$MSB_TOKEN",
                        }
                    ]
                }
            },
        }
    }
    result, placeholders = environment.from_config(config)
    assert result["env"] == {"A": "1"}
    assert result["secrets"]["TOKEN"]["value"] == "${GH}"
    assert result["secrets"]["TOKEN"]["allow"] == ["*", "x.com"]
    assert placeholders == {"TOKEN": "$MSB_TOKEN"}


def test_modify_patch_only_contains_changes():
    before = settings(TOKEN={"allow": ["a.com"]})
    after = environment.normalize({"env": {"NEW": "1"}, "secrets": {"TOKEN": {"allow": ["b.com"]}}})
    patch = environment.modify_patch(after, before, {"TOKEN": "$P"}, environ={"TOKEN": "x"})
    assert patch == {
        "env": {"NEW": "1"},
        "env_rm": ["MODE"],
        "secrets": {"TOKEN": {"env": "TOKEN", "allowed_hosts": ["b.com"], "placeholder": "$P"}},
        "secrets_rm": [],
    }


def test_modify_patch_requires_host_variable_of_changed_secrets():
    with pytest.raises(ValueError, match="host variable GH"):
        environment.modify_patch(settings(TOKEN={"value": "${GH}", "allow": ["a"]}), settings(), {}, environ={})


def test_create_secrets_uses_inert_value_for_references():
    entries, references = environment.create_secrets(
        settings(REF={"allow": ["a"]}, INLINE={"value": "plain", "allow": ["b"]}),
        inert=lambda: "inert",
    )
    assert [entry.value for entry in entries] == ["inert", "plain"]
    assert references == {"REF": {"env": "REF", "allowed_hosts": ["a"]}}


def test_create_only_change_reports_first_locked_field():
    before = settings(TOKEN={"allow": ["a"]})
    assert environment.create_only_change(before, before) is None
    assert environment.create_only_change(settings(TOKEN={"allow": ["a"], "passthrough": ["b"]}), before) == (
        "TOKEN: passthrough can only be set on creation."
    )
