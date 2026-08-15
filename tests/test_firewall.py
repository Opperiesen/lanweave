import pytest

from lanweave.firewall import (
    FirewallError,
    firewall_rule_is_broad,
    normalize_address_items,
    normalize_port_items,
    validate_firewall,
)


def _document() -> dict[str, object]:
    return {
        "zones": [{"name": "LAN", "networks": ["Home"]}],
        "address_groups": [{"name": "servers", "addresses": ["192.0.2.10", "192.0.2.0/24"]}],
        "port_groups": [{"name": "web", "ports": [443, {"start": 8000, "stop": 8080}]}],
        "rules": [
            {
                "name": "allow-web",
                "order": 100,
                "source": {"zone": "LAN", "address_group": "servers"},
                "destination": {"zone": "LAN", "port_group": "web"},
                "action": "ALLOW",
                "ip_version": "IPV4",
                "protocol": "TCP",
                "connection_states": ["NEW", "ESTABLISHED"],
            }
        ],
    }


def test_firewall_contract_normalizes_groups_and_defaults() -> None:
    document = validate_firewall(_document(), network_names={"Home"})

    assert document["address_groups"] == [
        {
            "name": "servers",
            "addresses": ["192.0.2.10", "192.0.2.0/24"],
        }
    ]
    assert document["port_groups"][0]["ports"][1] == {"start": 8000, "stop": 8080}
    assert document["rules"][0]["enabled"] is True
    assert document["rules"][0]["logging"] is False
    assert document["rules"][0]["allow_return_traffic"] is False


def test_firewall_contract_allows_references_to_system_zones() -> None:
    document = _document()
    document["rules"][0]["source"] = {"zone": "WAN", "address_group": "servers"}

    validate_firewall(document, network_names={"Home"})


@pytest.mark.parametrize(
    ("document", "message"),
    [
        (
            {"address_groups": [{"name": "bad", "addresses": ["192.0.2.1", "::1"]}]},
            "one IP version",
        ),
        (
            {"port_groups": [{"name": "bad", "ports": [{"start": 9000, "stop": 80}]}]},
            "must not be after",
        ),
        (
            {
                "rules": [
                    {
                        "name": "duplicate-order-a",
                        "order": 10,
                        "source": {"zone": "LAN"},
                        "destination": {"zone": "WAN"},
                        "action": "ALLOW",
                    },
                    {
                        "name": "duplicate-order-b",
                        "order": 10,
                        "source": {"zone": "LAN"},
                        "destination": {"zone": "WAN"},
                        "action": "BLOCK",
                    },
                ]
            },
            "order must be unique",
        ),
        (
            {
                "rules": [
                    {
                        "name": "bad-side",
                        "order": 10,
                        "source": {"zone": "LAN", "address_group": "missing"},
                        "destination": {"zone": "WAN"},
                        "action": "ALLOW",
                    }
                ]
            },
            "unknown address group",
        ),
    ],
)
def test_firewall_contract_rejects_unsafe_state(document: dict[str, object], message: str) -> None:
    with pytest.raises(FirewallError, match=message):
        validate_firewall(document)


def test_firewall_contract_rejects_unknown_network_references() -> None:
    document = _document()
    document["zones"][0]["networks"] = ["Missing"]

    with pytest.raises(FirewallError, match="unknown network"):
        validate_firewall(document, network_names={"Home"})


def test_firewall_normalizers_are_type_aware() -> None:
    addresses = normalize_address_items(
        ["192.0.2.1", {"start": "192.0.2.10", "stop": "192.0.2.20"}]
    )
    ports = normalize_port_items([443, {"start": 8000, "stop": 8080}])

    assert addresses[0]["type"] == "IP_ADDRESS"
    assert addresses[1]["type"] == "IP_ADDRESS_RANGE"
    assert ports == [
        {"type": "PORT_NUMBER", "value": 443},
        {"type": "PORT_NUMBER_RANGE", "start": 8000, "stop": 8080},
    ]


def test_broad_firewall_rules_are_detectable() -> None:
    document = validate_firewall(
        {
            "rules": [
                {
                    "name": "broad",
                    "order": 1,
                    "source": {"zone": "WAN"},
                    "destination": {"zone": "LAN"},
                    "action": "BLOCK",
                }
            ]
        }
    )

    assert firewall_rule_is_broad(document["rules"][0])
