import json
from pathlib import Path

import pytest

from lanweave.nat import (
    NatError,
    UnsupportedNatVariantError,
    nat_export_mapping,
    nat_is_broad,
    nat_is_user_managed,
    nat_mapping_identity,
    nat_to_unifi,
    normalize_controller_nat_list,
    normalize_nat_mapping,
    normalize_nat_port,
    validate_nat,
)


def _mapping() -> dict[str, object]:
    return {
        "name": "https",
        "protocol": "tcp",
        "public": {
            "interface": "WAN",
            "address": "203.0.113.2",
            "port": 443,
        },
        "source": {
            "zone": "External",
            "addresses": ["198.51.100.0/24", "198.51.100.10"],
        },
        "private": {
            "network": "Home",
            "address": "192.168.10.10",
            "port": 8443,
        },
        "hairpin": False,
    }


def test_nat_contract_normalizes_identity_endpoints_and_source_scope() -> None:
    mapping = normalize_nat_mapping(_mapping(), network_names={"Home"})

    assert mapping == {
        "name": "https",
        "enabled": True,
        "protocol": "TCP",
        "ip_version": "IPV4",
        "public": {
            "interface": "WAN",
            "address": "203.0.113.2",
            "port": 443,
        },
        "source": {
            "zone": "External",
            "addresses": ["198.51.100.0/24", "198.51.100.10"],
        },
        "private": {
            "network": "Home",
            "address": "192.168.10.10",
            "port": 8443,
        },
        "hairpin": False,
    }

    assert nat_mapping_identity(mapping) == "https"


def test_nat_contract_normalizes_equal_port_ranges_and_ipv6() -> None:
    mapping = normalize_nat_mapping(
        {
            "name": "dns",
            "protocol": "udp",
            "ip_version": "ipv6",
            "public": {"interface": "WAN6", "port": {"start": 5300, "stop": 5302}},
            "private": {"address": "2001:db8:10::53", "port": {"start": 53, "stop": 55}},
            "source": {"addresses": []},
            "hairpin": True,
        }
    )

    assert mapping["ip_version"] == "IPV6"
    assert mapping["public"]["port"] == {"start": 5300, "stop": 5302}
    assert mapping["private"]["port"] == {"start": 53, "stop": 55}
    assert mapping["hairpin"] is True
    assert nat_is_broad(mapping) is True


@pytest.mark.parametrize(
    ("value", "message"),
    [
        (0, "between"),
        ({"start": 100, "stop": 99}, "must not be after"),
        ({"start": 100, "stop": 100, "extra": 1}, "unsupported"),
    ],
)
def test_nat_port_normalization_rejects_unsafe_values(value: object, message: str) -> None:
    with pytest.raises(NatError, match=message):
        normalize_nat_port(value)


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda mapping: mapping.update(protocol="icmp"), "protocol"),
        (
            lambda mapping: mapping["private"].update(address="192.168.10.10/24"),
            "IP address",
        ),
        (
            lambda mapping: mapping["source"].update(addresses=["0.0.0.0/0", "::/0"]),
            "one IP version",
        ),
        (
            lambda mapping: mapping["private"].update(network="Missing"),
            "unknown network",
        ),
        (
            lambda mapping: mapping["private"].update(port={"start": 9000, "stop": 9001}),
            "same number of ports",
        ),
        (
            lambda mapping: mapping.update(extra=True),
            "unsupported field",
        ),
    ],
)
def test_nat_contract_rejects_unsafe_or_ambiguous_state(change, message: str) -> None:
    mapping = _mapping()
    change(mapping)

    with pytest.raises(NatError, match=message):
        normalize_nat_mapping(mapping, network_names={"Home"})


def test_nat_contract_rejects_mixed_families_and_duplicate_names() -> None:
    mapping = _mapping()
    mapping["public"]["address"] = "2001:db8::2"
    with pytest.raises(NatError, match="one IP version"):
        normalize_nat_mapping(mapping)

    with pytest.raises(NatError, match="duplicate mapping names"):
        validate_nat([_mapping(), _mapping()])


def test_nat_contract_defaults_missing_source_to_broad_and_preserves_ownership_boundary() -> None:
    mapping = _mapping()
    mapping.pop("source")
    normalized = normalize_nat_mapping(mapping)

    assert normalized["source"] == {"addresses": []}
    assert nat_is_broad(normalized) is True
    assert nat_is_user_managed({"_origin": "USER_DEFINED"}) is True
    assert nat_is_user_managed({"_origin": "SYSTEM_DEFINED"}) is False


def test_top_level_nat_validation_is_a_list_and_allows_empty_state() -> None:
    assert validate_nat(None) == []
    assert validate_nat([]) == []

    with pytest.raises(NatError, match="nat must be a list"):
        validate_nat({"mappings": []})


def test_controller_fixture_normalizes_legacy_fields_ports_and_origins() -> None:
    fixture = json.loads(
        (Path(__file__).parent / "fixtures" / "nat" / "portforward-page-1.json").read_text(
            encoding="utf-8"
        )
    )

    normalized = normalize_controller_nat_list(fixture)

    assert [(item["name"], item["_id"], item["_origin"]) for item in normalized] == [
        ("controller-dns", "nat-system-1", "SYSTEM_DEFINED"),
        ("web", "nat-user-1", "USER_DEFINED"),
    ]
    assert normalized[0]["protocol"] == "UDP"
    assert normalized[0]["ip_version"] == "IPV6"
    assert normalized[0]["public"]["port"] == {"start": 5300, "stop": 5302}
    assert normalized[0]["private"]["port"] == {"start": 53, "stop": 55}
    assert normalized[0]["source"] == {"addresses": []}
    assert normalized[1]["source"] == {"addresses": ["198.51.100.0/24"]}


def test_controller_fixture_rejects_unsupported_and_malformed_variants() -> None:
    fixture_dir = Path(__file__).parent / "fixtures" / "nat"
    unsupported = json.loads((fixture_dir / "portforward-unsupported.json").read_text())
    malformed = json.loads((fixture_dir / "portforward-malformed.json").read_text())

    with pytest.raises(UnsupportedNatVariantError, match="proto is unsupported"):
        normalize_controller_nat_list(unsupported)
    with pytest.raises(UnsupportedNatVariantError, match="proto must be"):
        normalize_controller_nat_list(malformed)


def test_controller_empty_fixture_is_a_valid_empty_inventory() -> None:
    fixture = json.loads(
        (Path(__file__).parent / "fixtures" / "nat" / "portforward-empty-page.json").read_text(
            encoding="utf-8"
        )
    )

    assert normalize_controller_nat_list(fixture) == []


def test_nat_export_drops_controller_metadata() -> None:
    live = normalize_controller_nat_list(
        {
            "data": [
                {
                    "_id": "nat-user-1",
                    "name": "web",
                    "enabled": True,
                    "pfwd_interface": "wan",
                    "src": "any",
                    "dst_port": "443",
                    "fwd": "192.0.2.10",
                    "fwd_port": "8443",
                    "proto": "tcp",
                    "setting_preference": "manual",
                }
            ]
        }
    )[0]

    exported = nat_export_mapping(live)

    assert exported["name"] == "web"
    assert "_id" not in exported
    assert "_origin" not in exported


def test_nat_mutation_payload_is_legacy_and_portable_metadata_free() -> None:
    payload = nat_to_unifi(
        {
            "name": "web",
            "enabled": True,
            "protocol": "TCP_UDP",
            "public": {"interface": "wan", "port": {"start": 443, "stop": 445}},
            "source": {"addresses": ["198.51.100.0/24"]},
            "private": {"address": "192.0.2.10", "port": {"start": 8443, "stop": 8445}},
            "hairpin": False,
        }
    )

    assert payload == {
        "name": "web",
        "enabled": True,
        "pfwd_interface": "wan",
        "src": "198.51.100.0/24",
        "dst_port": "443-445",
        "fwd": "192.0.2.10",
        "fwd_port": "8443-8445",
        "proto": "tcp_udp",
    }


@pytest.mark.parametrize(
    "change",
    [
        lambda mapping: mapping.update(ip_version="IPV6"),
        lambda mapping: mapping.update(hairpin=True),
        lambda mapping: mapping.update(description="not supported by classic writes"),
        lambda mapping: mapping["source"].update(zone="External"),
        lambda mapping: mapping["source"].update(addresses=["198.51.100.0/24", "203.0.113.0/24"]),
        lambda mapping: mapping["public"].update(address="203.0.113.2"),
    ],
)
def test_nat_mutation_rejects_unproven_controller_variants(change) -> None:
    mapping = {
        "name": "web",
        "protocol": "TCP",
        "public": {"interface": "wan", "port": 443},
        "source": {"addresses": []},
        "private": {"address": "192.0.2.10", "port": 8443},
    }
    change(mapping)

    with pytest.raises(UnsupportedNatVariantError):
        nat_to_unifi(mapping)
