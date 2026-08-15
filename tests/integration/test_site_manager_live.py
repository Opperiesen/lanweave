"""Protected read-only probes for the official UniFi Site Manager API."""

from __future__ import annotations

import os

import pytest

from lanweave.adapters import ADAPTER_CLOUD_SITE_MANAGER, AUTH_MODE_API_KEY
from lanweave.site_manager import (
    SITE_MANAGER_DEFAULT_HOST,
    SiteManagerClient,
    SiteManagerSettings,
    site_manager_capabilities,
)

pytestmark = pytest.mark.integration


def _cloud_client() -> SiteManagerClient:
    api_key = os.getenv("LANWEAVE_SITE_MANAGER_API_KEY", "").strip()
    if not api_key:
        pytest.skip("Site Manager API key is not configured")
    if api_key.startswith("op://"):
        pytest.fail("Site Manager API key must be resolved before the test starts")
    host = os.getenv("LANWEAVE_SITE_MANAGER_HOST", "").strip() or SITE_MANAGER_DEFAULT_HOST
    return SiteManagerClient(SiteManagerSettings(host=host, api_key=api_key))


def test_site_manager_read_only_inventory_is_reachable() -> None:
    client = _cloud_client()

    with client:
        assert client.capabilities.adapter == ADAPTER_CLOUD_SITE_MANAGER
        assert client.capabilities.auth_modes == (AUTH_MODE_API_KEY,)
        assert client.capabilities.to_dict() == site_manager_capabilities().to_dict()

        hosts = client.hosts()
        sites = client.sites()
        devices = client.devices()
        health = client.health()

    for collection in (hosts, sites, devices, health):
        assert isinstance(collection, list)
        assert all(isinstance(item, dict) for item in collection)


def test_site_manager_live_adapter_has_no_mutation_capability() -> None:
    client = _cloud_client()

    with client:
        assert not client.capabilities.supports("clients", "read")
        assert not client.capabilities.supports("networks", "apply")
        assert not client.capabilities.supports("wlans", "apply")
