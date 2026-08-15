"""Read-only probes against a real or explicitly designated UniFi controller."""

from __future__ import annotations

import pytest

from lanweave.client import UniFiClient

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
