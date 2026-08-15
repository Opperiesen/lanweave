from types import SimpleNamespace
from typing import Any

from lanweave.backup import redact_snapshot
from lanweave.config import validate_config
from lanweave.export import export_config


class ExportController:
    settings = SimpleNamespace(site="default")

    def networks(self) -> list[dict[str, Any]]:
        return [
            {
                "_id": "network-1",
                "name": "Home",
                "purpose": "corporate",
                "vlan_enabled": True,
                "vlan": "10",
                "ip_subnet": "192.168.10.1/24",
            }
        ]

    def wlans(self) -> list[dict[str, Any]]:
        return [
            {
                "_id": "wlan-1",
                "name": "Home",
                "networkconf_id": "network-1",
                "wlan_bands": ["5g"],
                "security": "wpapsk",
                "wpa3_support": False,
                "x_passphrase": "never-export-this",
            }
        ]

    def dns(self) -> list[dict[str, Any]]:
        return [
            {
                "_id": "dns-user",
                "_origin": "USER",
                "name": "printer.home.arpa",
                "type": "A",
                "address": "192.0.2.10",
                "ttl_seconds": 300,
                "enabled": True,
            },
            {
                "_id": "dns-system",
                "_origin": "SYSTEM",
                "name": "gateway.home.arpa",
                "type": "A",
                "address": "192.0.2.1",
                "ttl_seconds": 300,
                "enabled": True,
            },
        ]

    def nat(self) -> list[dict[str, Any]]:
        return [
            {
                "_id": "nat-user",
                "_origin": "USER_DEFINED",
                "name": "web",
                "enabled": True,
                "protocol": "TCP",
                "ip_version": "IPV4",
                "public": {"interface": "wan", "port": 443},
                "source": {"addresses": []},
                "private": {"address": "192.0.2.10", "port": 8443},
                "hairpin": False,
            },
            {
                "_id": "nat-system",
                "_origin": "SYSTEM_DEFINED",
                "name": "system",
                "enabled": True,
                "protocol": "TCP",
                "ip_version": "IPV4",
                "public": {"interface": "wan", "port": 9443},
                "source": {"addresses": []},
                "private": {"address": "192.0.2.11", "port": 9443},
                "hairpin": False,
            },
        ]


def test_export_uses_environment_reference_instead_of_password() -> None:
    exported = export_config(ExportController())

    wlan = exported["wlans"][0]
    assert wlan["network"] == "Home"
    assert wlan["password_env"] == "WIFI_HOME_PASSWORD"
    assert "x_passphrase" not in str(exported)
    assert "never-export-this" not in str(exported)
    assert exported["dns"] == [
        {
            "name": "printer.home.arpa",
            "type": "A",
            "address": "192.0.2.10",
            "ttl_seconds": 300,
            "enabled": True,
        }
    ]
    assert "dns-user" not in str(exported)
    assert "gateway.home.arpa" not in str(exported)
    assert exported["nat"] == [
        {
            "name": "web",
            "enabled": True,
            "protocol": "TCP",
            "ip_version": "IPV4",
            "public": {"interface": "wan", "port": 443},
            "source": {"addresses": []},
            "private": {"address": "192.0.2.10", "port": 8443},
            "hairpin": False,
        }
    ]
    assert "nat-user" not in str(exported)
    assert "nat-system" not in str(exported)
    validate_config(exported)


def test_backup_redacts_nested_sensitive_fields() -> None:
    value = redact_snapshot(
        {
            "device": {
                "name": "gateway",
                "x_passphrase": "secret",
                "nested": [{"api_key": "secret-key"}],
            }
        }
    )

    assert value["device"]["x_passphrase"] == "***"
    assert value["device"]["nested"][0]["api_key"] == "***"
