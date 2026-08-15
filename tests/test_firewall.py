import json
from pathlib import Path

import pytest

from lanweave.firewall import (
    FirewallError,
    UnsupportedFirewallVariantError,
    export_firewall_config,
    firewall_group_to_unifi,
    firewall_is_user_managed,
    firewall_rule_is_broad,
    firewall_rule_to_unifi,
    firewall_zone_to_unifi,
    normalize_address_items,
    normalize_controller_firewall_policy,
    normalize_controller_firewall_zone,
    normalize_controller_traffic_matching_list,
    normalize_port_items,
    validate_firewall,
)

FIREWALL_FIXTURES = Path(__file__).parent / "fixtures" / "firewall"


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


def test_firewall_export_is_secret_free_and_preserves_group_references() -> None:
    zones = [
        normalize_controller_firewall_zone(
            {
                "id": "zone-lan",
                "name": "LAN",
                "networkIds": ["network-home"],
                "metadata": {"origin": "SYSTEM_DEFINED"},
            }
        ),
        normalize_controller_firewall_zone(
            {
                "id": "zone-custom",
                "name": "Trusted",
                "networkIds": ["network-home"],
                "metadata": {"origin": "USER_DEFINED"},
            }
        ),
    ]
    groups = [
        normalize_controller_traffic_matching_list(
            {
                "id": "group-web",
                "name": "web",
                "type": "PORTS",
                "items": [{"type": "PORT_NUMBER", "value": 443}],
                "metadata": {"origin": "USER_DEFINED"},
            }
        )
    ]
    policy = normalize_controller_firewall_policy(
        {
            "id": "policy-1",
            "name": "allow-web",
            "enabled": True,
            "action": {"type": "ALLOW", "allowReturnTraffic": True},
            "source": {"zoneId": "zone-custom"},
            "destination": {
                "zoneId": "zone-lan",
                "trafficFilter": {
                    "type": "PORT",
                    "portFilter": {
                        "type": "TRAFFIC_MATCHING_LIST",
                        "trafficMatchingListId": "group-web",
                        "matchOpposite": False,
                    },
                },
            },
            "ipProtocolScope": {
                "ipVersion": "IPV4",
                "protocolFilter": {
                    "type": "NAMED_PROTOCOL",
                    "protocol": {"name": "tcp"},
                    "matchOpposite": False,
                },
            },
            "connectionStateFilter": ["NEW"],
            "loggingEnabled": False,
            "metadata": {"origin": "USER_DEFINED"},
        }
    )

    exported = export_firewall_config(
        zones=zones,
        groups=groups,
        policies=[policy],
        orderings={
            ("zone-custom", "zone-lan"): {
                "before_system_defined": [],
                "after_system_defined": ["policy-1"],
            }
        },
        network_names_by_id={"network-home": "Home"},
    )

    assert exported["zones"] == [{"name": "Trusted", "networks": ["Home"]}]
    assert exported["port_groups"] == [{"name": "web", "ports": [443]}]
    assert exported["rules"][0]["destination"] == {"zone": "LAN", "port_group": "web"}
    assert exported["rules"][0]["protocol"] == "TCP"
    assert "policy-1" not in str(exported)
    assert "zone-custom" not in str(exported)


def test_firewall_payloads_follow_integration_api_shape() -> None:
    assert firewall_zone_to_unifi(
        {"name": "Trusted", "networks": ["Home"]},
        {"Home": "network-home"},
    ) == {"name": "Trusted", "networkIds": ["network-home"]}
    assert firewall_group_to_unifi(
        {"name": "web", "ports": [443, {"start": 8000, "stop": 8080}]}
    ) == {
        "name": "web",
        "type": "PORTS",
        "items": [
            {"type": "PORT_NUMBER", "value": 443},
            {"type": "PORT_NUMBER_RANGE", "start": 8000, "stop": 8080},
        ],
    }
    assert firewall_rule_to_unifi(
        {
            "name": "allow-web",
            "source": {"zone": "Trusted", "address_group": "servers"},
            "destination": {"zone": "LAN", "port_group": "web"},
            "action": "ALLOW",
            "enabled": True,
            "ip_version": "IPV4",
            "protocol": "TCP",
            "connection_states": ["NEW"],
            "logging": False,
            "allow_return_traffic": True,
        },
        zone_ids_by_name={"Trusted": "zone-trusted", "LAN": "zone-lan"},
        network_ids_by_name={"Home": "network-home"},
        group_ids_by_name={"servers": "group-servers", "web": "group-web"},
    ) == {
        "name": "allow-web",
        "enabled": True,
        "action": {"type": "ALLOW", "allowReturnTraffic": True},
        "source": {
            "zoneId": "zone-trusted",
            "trafficFilter": {
                "type": "IP_ADDRESS",
                "ipAddressFilter": {
                    "type": "TRAFFIC_MATCHING_LIST",
                    "trafficMatchingListId": "group-servers",
                    "matchOpposite": False,
                },
            },
        },
        "destination": {
            "zoneId": "zone-lan",
            "trafficFilter": {
                "type": "PORT",
                "portFilter": {
                    "type": "TRAFFIC_MATCHING_LIST",
                    "trafficMatchingListId": "group-web",
                    "matchOpposite": False,
                },
            },
        },
        "ipProtocolScope": {
            "ipVersion": "IPV4",
            "protocolFilter": {
                "type": "NAMED_PROTOCOL",
                "matchOpposite": False,
                "protocol": {"name": "tcp"},
            },
        },
        "connectionStateFilter": ["NEW"],
        "loggingEnabled": False,
    }


def test_firewall_export_rejects_policy_missing_from_ordering() -> None:
    policy = normalize_controller_firewall_policy(
        {
            "id": "policy-1",
            "name": "allow-web",
            "action": {"type": "ALLOW"},
            "source": {"zoneId": "zone-lan"},
            "destination": {"zoneId": "zone-lan"},
            "ipProtocolScope": {"ipVersion": "IPV4_AND_IPV6"},
            "metadata": {"origin": "USER_DEFINED"},
        }
    )

    with pytest.raises(FirewallError, match="absent from its controller ordering"):
        export_firewall_config(
            zones=[
                normalize_controller_firewall_zone(
                    {
                        "id": "zone-lan",
                        "name": "LAN",
                        "metadata": {"origin": "SYSTEM_DEFINED"},
                    }
                )
            ],
            groups=[],
            policies=[policy],
            orderings={
                ("zone-lan", "zone-lan"): {
                    "before_system_defined": [],
                    "after_system_defined": [],
                }
            },
            network_names_by_id={},
        )


def test_firewall_fixtures_cover_unsupported_variants_and_protected_origins() -> None:
    unsupported = json.loads(
        (FIREWALL_FIXTURES / "firewall-traffic-matching-list-unsupported.json").read_text()
    )
    with pytest.raises(UnsupportedFirewallVariantError):
        normalize_controller_traffic_matching_list(unsupported)

    protected = json.loads(
        (FIREWALL_FIXTURES / "firewall-traffic-matching-list-system.json").read_text()
    )
    normalized = normalize_controller_traffic_matching_list(protected)
    assert normalized["_origin"] == "SYSTEM_DEFINED"
    assert firewall_is_user_managed(normalized) is False


def test_firewall_empty_fixture_is_a_valid_empty_page() -> None:
    page = json.loads((FIREWALL_FIXTURES / "firewall-empty-page.json").read_text())
    assert page["data"] == []
    assert page["totalCount"] == 0


def test_firewall_malformed_fixture_is_not_accepted_as_pagination_metadata() -> None:
    page = json.loads((FIREWALL_FIXTURES / "firewall-malformed-page.json").read_text())
    with pytest.raises((TypeError, ValueError)):
        int(page["totalCount"])
