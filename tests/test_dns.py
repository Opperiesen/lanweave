from __future__ import annotations

import pytest

from lanweave.dns import (
    DnsError,
    UnsupportedDnsRecordError,
    dns_export_record,
    dns_is_user_managed,
    dns_to_unifi,
    normalize_controller_dns,
    normalize_controller_dns_list,
    normalize_dns_record,
    validate_dns_records,
)


def test_dns_records_are_canonical_and_use_official_wire_fields() -> None:
    assert normalize_dns_record(
        {"name": "Printer.Home.arpa.", "type": "a", "address": "192.0.2.10"}
    ) == {
        "name": "printer.home.arpa",
        "type": "A",
        "address": "192.0.2.10",
        "ttl_seconds": 300,
        "enabled": True,
    }
    assert dns_to_unifi(
        {"name": "portal.home.arpa", "type": "CNAME", "target": "printer.home.arpa"}
    ) == {
        "type": "CNAME_RECORD",
        "enabled": True,
        "domain": "portal.home.arpa",
        "ttlSeconds": 300,
        "targetDomain": "printer.home.arpa",
    }


@pytest.mark.parametrize(
    ("record", "message"),
    [
        ({"name": "*.home.arpa", "type": "A", "address": "192.0.2.1"}, "wildcards"),
        ({"name": "host.home.arpa", "type": "A", "address": "2001:db8::1"}, "IPv4"),
        (
            {"name": "host.home.arpa", "type": "CNAME", "target": "target", "ttl_seconds": 700000},
            "between",
        ),
        (
            {"name": "host.home.arpa", "type": "A", "address": "192.0.2.1", "extra": 1},
            "unsupported",
        ),
    ],
)
def test_dns_validation_rejects_unsafe_records(record: dict[str, object], message: str) -> None:
    with pytest.raises(DnsError, match=message):
        normalize_dns_record(record)


def test_dns_validation_rejects_duplicate_and_cname_conflicts() -> None:
    with pytest.raises(DnsError, match="duplicate DNS identity"):
        validate_dns_records(
            [
                {"name": "host.home.arpa", "type": "A", "address": "192.0.2.1"},
                {"name": "HOST.home.arpa.", "type": "a", "address": "192.0.2.2"},
            ]
        )
    with pytest.raises(DnsError, match="CNAME cannot coexist"):
        validate_dns_records(
            [
                {"name": "host.home.arpa", "type": "CNAME", "target": "target.home.arpa"},
                {"name": "host.home.arpa", "type": "A", "address": "192.0.2.1"},
            ]
        )


def test_controller_dns_normalization_preserves_ownership_without_exporting_metadata() -> None:
    record = normalize_controller_dns(
        {
            "id": "dns-1",
            "type": "A_RECORD",
            "enabled": True,
            "domain": "Host.Home.arpa.",
            "ipv4Address": "192.0.2.1",
            "ttlSeconds": 300,
            "metadata": {"origin": "USER"},
        }
    )

    assert record == {
        "name": "host.home.arpa",
        "type": "A",
        "address": "192.0.2.1",
        "ttl_seconds": 300,
        "enabled": True,
        "_id": "dns-1",
        "_origin": "USER",
    }
    assert dns_is_user_managed(record)
    assert dns_export_record(record) == {
        "name": "host.home.arpa",
        "type": "A",
        "address": "192.0.2.1",
        "ttl_seconds": 300,
        "enabled": True,
    }


def test_controller_dns_list_skips_unsupported_families_and_rejects_bad_supported_data() -> None:
    values = [
        {
            "id": "a-1",
            "type": "A_RECORD",
            "domain": "a.home.arpa",
            "ipv4Address": "192.0.2.1",
            "metadata": {"origin": "USER"},
        },
        {"id": "forward-1", "type": "FORWARD", "domain": "ignored.home.arpa"},
    ]
    assert [record["name"] for record in normalize_controller_dns_list(values)] == ["a.home.arpa"]
    with pytest.raises(UnsupportedDnsRecordError):
        normalize_controller_dns({"type": "MX_RECORD", "domain": "mail.home.arpa"})
    with pytest.raises(DnsError, match="IPv4"):
        normalize_controller_dns(
            {
                "type": "A_RECORD",
                "domain": "bad.home.arpa",
                "ipv4Address": "2001:db8::1",
            }
        )
