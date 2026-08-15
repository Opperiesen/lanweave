from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest

from lanweave.adapters import (
    Adapter,
    AdapterAuthenticationError,
    AdapterConfigurationError,
    AdapterRateLimitError,
    AdapterTransportError,
    UnsupportedCapabilityError,
)
from lanweave.client import ControllerSettings
from lanweave.site_manager import SiteManagerClient, SiteManagerSettings

ROOT = Path(__file__).parents[1]
FIXTURES = ROOT / "tests/fixtures/site-manager"


def _fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_site_manager_settings_require_https_and_api_key_only() -> None:
    settings = ControllerSettings(host="https://api.ui.com", api_key="cloud-key")
    converted = SiteManagerSettings.from_controller_settings(settings)

    assert converted.host == "https://api.ui.com"
    assert converted.api_key == "cloud-key"

    with pytest.raises(AdapterConfigurationError, match="API-key authentication"):
        SiteManagerSettings.from_controller_settings(
            ControllerSettings(host="https://api.ui.com", username="user", password="pass")
        )

    with pytest.raises(AdapterConfigurationError, match="HTTPS"):
        SiteManagerSettings(host="http://api.ui.com", api_key="cloud-key")

    with pytest.raises(AdapterConfigurationError, match="missing or unresolved"):
        SiteManagerSettings(host="https://api.ui.com", api_key="op://vault/item/key")


def test_site_manager_lists_paginated_inventory_and_normalizes_devices() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.headers["X-API-KEY"] == "cloud-key"
        assert request.headers["Accept"] == "application/json"
        assert request.url.params["pageSize"] == "1"
        if request.url.path == "/v1/hosts":
            if request.url.params.get("nextToken") == "fixture-page-2":
                return httpx.Response(200, json=_fixture("hosts-page-2.json"))
            return httpx.Response(200, json=_fixture("hosts-page-1.json"))
        if request.url.path == "/v1/sites":
            return httpx.Response(200, json=_fixture("sites.json"))
        if request.url.path == "/v1/devices":
            return httpx.Response(200, json=_fixture("devices.json"))
        raise AssertionError(f"unexpected request path: {request.url.path}")

    client = SiteManagerClient(
        SiteManagerSettings(host="https://api.ui.com", api_key="cloud-key", page_size=1),
        transport=httpx.MockTransport(handler),
    )

    assert isinstance(client, Adapter)
    with client:
        assert [host["id"] for host in client.hosts()] == ["host-fixture-1", "host-fixture-2"]
        assert client.sites()[0]["siteId"] == "site-fixture-1"
        assert client.devices() == [
            {
                "_id": "device-fixture-1",
                "id": "device-fixture-1",
                "name": "Lanweave Gateway",
                "hostname": "Lanweave Gateway",
                "ip": "192.0.2.20",
                "mac": "02:00:00:00:00:20",
                "model": "UXG-Fixture",
                "state": "ONLINE",
                "host_id": "host-fixture-1",
                "site_id": "site-fixture-1",
            }
        ]
        assert client.health() == [
            {
                "subsystem": "site",
                "status": "up",
                "site_id": "site-fixture-1",
                "name": "default",
                "host_id": "host-fixture-1",
                "permission": "readonly",
            }
        ]

    assert [request.url.path for request in requests] == [
        "/v1/hosts",
        "/v1/hosts",
        "/v1/sites",
        "/v1/devices",
        "/v1/sites",
    ]


def test_site_manager_capabilities_are_read_only_and_explicit() -> None:
    client = SiteManagerClient(
        SiteManagerSettings(host="https://api.ui.com", api_key="cloud-key"),
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json={"data": []})),
    )

    assert client.capabilities.to_dict() == {
        "format_version": 1,
        "adapter": "cloud-site-manager",
        "auth_modes": ["api-key"],
        "resources": [
            {"resource": "devices", "operations": ["read"]},
            {"resource": "health", "operations": ["read"]},
            {"resource": "hosts", "operations": ["read"]},
            {"resource": "sites", "operations": ["read"]},
        ],
    }

    calls = 0

    def counting_handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={"data": []})

    client = SiteManagerClient(
        SiteManagerSettings(host="https://api.ui.com", api_key="cloud-key"),
        transport=httpx.MockTransport(counting_handler),
    )
    for operation in (
        lambda: client.clients(),
        lambda: client.networks(),
        lambda: client.wlans(),
        lambda: client.post("/v1/anything"),
        lambda: client.put("/v1/anything"),
        lambda: client.delete("/v1/anything"),
    ):
        with pytest.raises(UnsupportedCapabilityError):
            operation()
    assert calls == 0


@pytest.mark.parametrize(
    ("status", "headers", "expected"),
    [
        (401, {}, AdapterAuthenticationError),
        (502, {}, AdapterTransportError),
        (429, {"Retry-After": "7.8"}, AdapterRateLimitError),
    ],
)
def test_site_manager_errors_are_normalized_and_secret_free(
    status: int,
    headers: dict[str, str],
    expected: type[Exception],
) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status,
            headers=headers,
            json={"message": "cloud-key must not appear in an error"},
        )

    client = SiteManagerClient(
        SiteManagerSettings(host="https://api.ui.com", api_key="cloud-key"),
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(expected) as caught:
        client.hosts()

    assert "cloud-key" not in str(caught.value)
    if isinstance(caught.value, AdapterRateLimitError):
        assert caught.value.retry_after == 7


def test_site_manager_rejects_malformed_or_non_advancing_pages() -> None:
    responses = iter(
        [
            {"data": {"not": "a list"}},
            {"data": [], "nextToken": "same"},
            {"data": [], "nextToken": "same"},
        ]
    )

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=next(responses))

    client = SiteManagerClient(
        SiteManagerSettings(host="https://api.ui.com", api_key="cloud-key"),
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(AdapterTransportError, match="data is not a list"):
        client.hosts()

    non_advancing_client = SiteManagerClient(
        SiteManagerSettings(host="https://api.ui.com", api_key="cloud-key"),
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(AdapterTransportError, match="pagination token did not advance"):
        non_advancing_client.hosts()
