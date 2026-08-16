from types import SimpleNamespace
from typing import Any

from lanweave.adapters import AdapterCapabilities, AdapterCapability
from lanweave.audit import AuditState, audit_config, audit_exit_code


def _config(**overrides: Any) -> dict[str, Any]:
    config: dict[str, Any] = {
        "version": 1,
        "controller": {"site": "default"},
        "networks": [
            {
                "name": "Home",
                "purpose": "corporate",
                "subnet": "192.168.10.0/24",
                "vlan": 10,
            }
        ],
        "wlans": [
            {
                "name": "Home",
                "ssid": "Home",
                "network": "Home",
                "bands": ["5g"],
                "security": "wpa2",
                "password_env": "WIFI_HOME_PASSWORD",
            }
        ],
    }
    config.update(overrides)
    return config


class FakeAuditController:
    settings = SimpleNamespace(site="default")

    def __init__(self, *, drift: bool = False, fail: bool = False) -> None:
        self.drift = drift
        self.fail = fail

    def networks(self) -> list[dict[str, Any]]:
        if self.fail:
            raise RuntimeError("controller response secret=fixture-secret")
        return [
            {
                "_id": "network-controller-id",
                "name": "Home",
                "purpose": "corporate",
                "vlan_enabled": True,
                "vlan": "20" if self.drift else "10",
                "ip_subnet": "192.168.10.1/24",
            }
        ]

    def wlans(self) -> list[dict[str, Any]]:
        return [
            {
                "_id": "wlan-controller-id",
                "name": "Home",
                "networkconf_id": "network-controller-id",
                "wlan_bands": ["5g"],
                "security": "wpapsk",
                "wpa3_support": False,
                "x_passphrase": "fixture-secret",
            }
        ]


class VpnAuditController(FakeAuditController):
    def vpn(self) -> dict[str, Any]:
        return {
            "servers": [
                {
                    "id": "vpn-controller-id",
                    "name": "Remote Access",
                    "type": "WireGuard",
                    "enabled": True,
                }
            ],
            "site_to_site_tunnels": [],
            "peers": [],
            "routes": [],
        }


def test_audit_is_in_sync_and_deterministic_without_credentials() -> None:
    config = _config()
    first = audit_config(FakeAuditController(), config)
    second = audit_config(
        FakeAuditController(),
        {**config, "networks": list(reversed(config["networks"]))},
    )

    assert first == second
    assert first["state"] == AuditState.IN_SYNC
    assert audit_exit_code(first) == 0
    assert "fixture-secret" not in str(first)
    assert "network-controller-id" not in str(first)
    assert "WIFI_HOME_PASSWORD" not in str(first)


def test_audit_reports_proven_drift_with_explainable_fields() -> None:
    result = audit_config(FakeAuditController(drift=True), _config())

    assert result["state"] == AuditState.DRIFTED
    assert audit_exit_code(result) == 1
    network = next(item for item in result["resources"] if item["resource"] == "networks")
    assert network["findings"] == [{"kind": "changed", "name": "Home", "fields": ["vlan"]}]


def test_audit_reports_unsupported_declared_resource() -> None:
    class LimitedController(FakeAuditController):
        capabilities = AdapterCapabilities(
            adapter="fixture",
            auth_modes=("fixture",),
            resources=(
                AdapterCapability("networks", ("read", "export")),
                AdapterCapability("wlans", ("read", "export")),
            ),
        )

    result = audit_config(LimitedController(), _config(nat=[]))

    assert result["state"] == AuditState.UNSUPPORTED
    assert audit_exit_code(result) == 2
    nat = next(item for item in result["resources"] if item["resource"] == "nat")
    assert nat["state"] == AuditState.UNSUPPORTED
    assert nat["coverage"]["reason"] == "unsupported_export_capability"


def test_audit_reports_unknown_when_live_collection_fails() -> None:
    result = audit_config(FakeAuditController(fail=True), _config())

    assert result["state"] == AuditState.UNKNOWN
    assert audit_exit_code(result) == 2
    assert {item["state"] for item in result["resources"]} == {AuditState.UNKNOWN}
    assert all(
        item["coverage"]["reason"] == "live_observation_failed" for item in result["resources"]
    )
    assert "fixture-secret" not in str(result)


def test_vpn_routes_are_explicitly_unknown_when_overview_does_not_report_them() -> None:
    result = audit_config(
        VpnAuditController(),
        _config(
            vpn={
                "servers": [{"name": "Remote Access", "type": "WireGuard"}],
                "site_to_site_tunnels": [],
                "routes": [
                    {
                        "name": "remote-lan",
                        "destination": "10.20.0.0/16",
                        "via": "Remote Access",
                    }
                ],
            }
        ),
    )

    vpn = next(item for item in result["resources"] if item["resource"] == "vpn")
    assert vpn["state"] == AuditState.UNKNOWN
    assert vpn["coverage"]["reason"] == "routes_not_reported_by_official_overview_api"


def test_wan_networks_are_not_reported_as_proven_drift() -> None:
    result = audit_config(
        FakeAuditController(),
        _config(
            networks=[
                {
                    "name": "Home",
                    "purpose": "corporate",
                    "subnet": "192.168.10.0/24",
                    "vlan": 10,
                },
                {"name": "WAN", "purpose": "wan"},
            ]
        ),
    )

    networks = next(item for item in result["resources"] if item["resource"] == "networks")
    assert networks["state"] == AuditState.UNKNOWN
    assert networks["coverage"]["reason"] == "wan_networks_not_reported_by_portable_export"
    assert result["state"] == AuditState.UNKNOWN
    assert audit_exit_code(result) == 2
