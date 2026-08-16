"""Read-only probes against a real or explicitly designated UniFi controller."""

from __future__ import annotations

import json

import pytest

from lanweave.client import UniFiClient
from lanweave.export import export_config

pytestmark = pytest.mark.integration


def test_health_is_readable(integration_client: UniFiClient) -> None:
    health = integration_client.health()

    assert isinstance(health, list)


def test_inventory_views_are_readable(integration_client: UniFiClient) -> None:
    devices = integration_client.devices()
    clients = integration_client.clients()

    assert isinstance(devices, list)
    assert isinstance(clients, list)


def test_declarative_resources_are_readable(integration_client: UniFiClient) -> None:
    networks = integration_client.networks()
    wlans = integration_client.wlans()

    assert isinstance(networks, list)
    assert isinstance(wlans, list)


def test_nat_inventory_and_export_are_readable_with_session_auth(
    integration_client: UniFiClient,
) -> None:
    if integration_client.settings.api_key:
        pytest.skip("NAT inventory evidence requires local session authentication")

    mappings = integration_client.nat()
    exported = export_config(integration_client)

    assert isinstance(mappings, list)
    assert isinstance(exported["nat"], list)
    serialized = json.dumps(exported, sort_keys=True)
    assert '"_id"' not in serialized
    assert '"_origin"' not in serialized


def test_firewall_inventory_and_export_are_readable(
    integration_client: UniFiClient,
) -> None:
    if not integration_client.settings.api_key:
        pytest.skip("firewall Integration API evidence requires an API key")

    zones = integration_client.firewall_zones()
    groups = integration_client.firewall_traffic_matching_lists()
    policies = integration_client.firewall_policies()
    orderings = {
        (
            policy["source"]["zone_id"],
            policy["destination"]["zone_id"],
        ): integration_client.firewall_policy_ordering(
            policy["source"]["zone_id"],
            policy["destination"]["zone_id"],
        )
        for policy in policies
    }

    assert isinstance(zones, list)
    assert isinstance(groups, list)
    assert isinstance(policies, list)
    assert all(orderings.values())

    exported = export_config(integration_client)
    assert set(exported["firewall"]) == {"zones", "address_groups", "port_groups", "rules"}
    serialized = json.dumps(exported, sort_keys=True)
    assert "_origin" not in serialized
    assert '"metadata"' not in serialized


def test_vpn_inventory_is_read_only_and_honest(
    integration_client: UniFiClient,
) -> None:
    if not integration_client.settings.api_key:
        pytest.skip("VPN inventory evidence requires an Integration API key")

    inventory = integration_client.vpn()
    health = integration_client.vpn_health()
    exported = export_config(integration_client, resources=("vpn",))

    assert set(inventory) == {"servers", "site_to_site_tunnels", "peers", "routes"}
    assert isinstance(inventory["servers"], list)
    assert isinstance(inventory["site_to_site_tunnels"], list)
    assert isinstance(inventory["peers"], list)
    assert inventory["routes"] == []
    assert health["status"] in {"inventory-only", "not-configured"}
    assert health["coverage"]["routes"] == "not-reported-by-official-overview-api"
    assert exported["vpn"]["routes"] == []

    serialized = json.dumps({"inventory": inventory, "health": health, "export": exported})
    for key in ("private_key", "preshared_key", "qr_code", "configuration", "secret", "token"):
        assert key not in serialized.lower()
