from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx
import pytest

from lanweave.adapters import AdapterCapabilities, AdapterCapability
from lanweave.client import ControllerSettings, UniFiClient
from lanweave.config import ConfigError, validate_config
from lanweave.export import export_config
from lanweave.plan import build_plan
from lanweave.vpn import (
    UnsupportedVpnVariantError,
    health_from_inventory,
    normalize_controller_vpn_server,
    plan_observation,
    validate_vpn,
)

ROOT = Path(__file__).parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "vpn"


def _vpn_config() -> dict[str, Any]:
    return {
        "version": 1,
        "controller": {"site": "default"},
        "networks": [],
        "wlans": [],
        "vpn": {
            "servers": [{"name": "Remote Access", "type": "wireguard", "enabled": True}],
            "site_to_site_tunnels": [{"name": "Branch Office", "type": "ipsec"}],
            "routes": [
                {
                    "name": "branch-network",
                    "destination": "10.20.0.0/24",
                    "via": "Branch Office",
                    "metric": 10,
                }
            ],
        },
    }


def test_vpn_config_is_additive_and_dependency_checked() -> None:
    config = _vpn_config()
    validate_config(config)
    assert validate_vpn(config["vpn"])["servers"][0]["type"] == "WIREGUARD"

    invalid = _vpn_config()
    invalid["vpn"]["routes"][0]["via"] = "missing"
    with pytest.raises(ConfigError, match="unknown VPN resource"):
        validate_config(invalid)

    invalid = _vpn_config()
    invalid["vpn"]["servers"][0]["private_key"] = "must-not-be-accepted"
    with pytest.raises(ConfigError, match="not accepted"):
        validate_config(invalid)


def test_vpn_normalization_rejects_malformed_controller_shape() -> None:
    malformed = json.loads((FIXTURES / "vpn-malformed.json").read_text(encoding="utf-8"))
    with pytest.raises(UnsupportedVpnVariantError, match="not boolean"):
        normalize_controller_vpn_server(malformed)


def test_api_key_reads_documented_vpn_overviews_and_connected_peers() -> None:
    servers = json.loads((FIXTURES / "vpn-servers-page-1.json").read_text(encoding="utf-8"))
    tunnels = json.loads(
        (FIXTURES / "vpn-site-to-site-tunnels-page-1.json").read_text(encoding="utf-8")
    )
    clients = json.loads((FIXTURES / "vpn-clients-page-1.json").read_text(encoding="utf-8"))

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        assert request.headers["X-API-KEY"] == "test"
        if path.endswith("/sites"):
            return httpx.Response(200, json={"data": [{"id": "site-1", "name": "Default"}]})
        if path.endswith("/vpn/servers"):
            return httpx.Response(200, json=servers)
        if path.endswith("/vpn/site-to-site-tunnels"):
            return httpx.Response(200, json=tunnels)
        if path.endswith("/clients"):
            return httpx.Response(200, json=clients)
        raise AssertionError(f"unexpected request: {request.method} {path}")

    settings = ControllerSettings(host="https://controller.example", api_key="test")
    with UniFiClient(settings, transport=httpx.MockTransport(handler)) as client:
        inventory = client.vpn()

    assert [item["name"] for item in inventory["servers"]] == ["Remote Access", "Teleport"]
    assert inventory["site_to_site_tunnels"][0]["type"] == "IPSEC"
    assert inventory["peers"] == [
        {
            "id": "vpn-peer-1",
            "name": "phone",
            "type": "VPN",
            "ip_address": "10.99.0.2",
            "connected_at": "2026-08-16T10:00:00Z",
        }
    ]
    assert inventory["routes"] == []
    assert health_from_inventory(inventory)["coverage"]["routes"] == (
        "not-reported-by-official-overview-api"
    )


class VpnExportController:
    settings = SimpleNamespace(site="default")
    capabilities = AdapterCapabilities(
        adapter="fixture",
        auth_modes=("fixture",),
        resources=(AdapterCapability("vpn", ("read", "export", "plan")),),
    )

    def networks(self) -> list[dict[str, Any]]:
        return []

    def wlans(self) -> list[dict[str, Any]]:
        return []

    def vpn(self) -> dict[str, Any]:
        return {
            "servers": [
                {
                    "id": "server-id",
                    "name": "Remote Access",
                    "type": "WIREGUARD",
                    "enabled": True,
                }
            ],
            "site_to_site_tunnels": [],
            "peers": [{"id": "peer-id", "name": "phone", "type": "VPN"}],
            "routes": [],
        }


def test_vpn_export_is_id_free_and_plan_is_read_only() -> None:
    controller = VpnExportController()
    exported = export_config(controller)
    assert exported["vpn"] == {
        "servers": [{"name": "Remote Access", "type": "WIREGUARD", "enabled": True}],
        "site_to_site_tunnels": [],
        "routes": [],
    }
    assert "server-id" not in str(exported)
    validate_config(exported)

    class PlanController(VpnExportController):
        def site_url(self, path: str) -> str:
            return path

        def vpn(self) -> dict[str, Any]:
            return super().vpn()

    plan = build_plan(PlanController(), _vpn_config())
    assert plan.read_only["vpn"]["apply_supported"] is False
    assert plan.to_dict()["read_only"]["vpn"]["mode"] == "read-only"
    assert plan_observation(_vpn_config()["vpn"], controller.vpn())["resource"] == "vpn"
