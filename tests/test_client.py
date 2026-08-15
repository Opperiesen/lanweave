import json
from pathlib import Path

import httpx
import pytest

from lanweave.adapters import ADAPTER_LOCAL_CLASSIC, AUTH_MODE_API_KEY
from lanweave.client import ControllerSettings, CredentialsError, LocalClassicAdapter, UniFiClient


def test_classic_site_url_is_controller_relative() -> None:
    settings = ControllerSettings(host="https://controller.example", api_key="test")

    with UniFiClient(settings) as client:
        assert client.site_url("stat/device") == ("/proxy/network/api/s/default/stat/device")


def test_api_key_reads_integration_api() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["X-API-KEY"] == "test"
        if request.url.path.endswith("/info"):
            return httpx.Response(200, json={"applicationVersion": "10.5.67"})
        if request.url.path.endswith("/sites"):
            return httpx.Response(200, json={"data": [{"id": "site-1", "name": "Default"}]})
        if request.url.path.endswith("/devices"):
            return httpx.Response(
                200,
                json={"data": [{"id": "device-1", "name": "gateway", "ipAddress": "192.0.2.1"}]},
            )
        if request.url.path.endswith("/clients"):
            return httpx.Response(
                200,
                json={"data": [{"id": "client-1", "name": "phone", "type": "WIRELESS"}]},
            )
        if request.url.path.endswith("/networks"):
            return httpx.Response(
                200,
                json={"data": [{"id": "network-1", "name": "Lanweave", "vlanId": 99}]},
            )
        if request.url.path.endswith("/networks/network-1"):
            return httpx.Response(
                200,
                json={
                    "id": "network-1",
                    "name": "Lanweave",
                    "vlanId": 99,
                    "management": "VLAN_ONLY",
                },
            )
        if request.url.path.endswith("/wifi/broadcasts"):
            return httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "id": "wifi-1",
                            "name": "Lanweave WiFi",
                            "broadcastingFrequenciesGHz": [2.4, 5],
                            "network": {"type": "SPECIFIC", "networkId": "network-1"},
                            "securityConfiguration": {"type": "WPA2_PERSONAL"},
                        }
                    ]
                },
            )
        raise AssertionError(f"unexpected request path: {request.url.path}")

    settings = ControllerSettings(host="https://controller.example", api_key="test")
    transport = httpx.MockTransport(handler)

    with UniFiClient(settings, transport=transport) as client:
        assert client.health() == [
            {"subsystem": "application", "status": "up", "version": "10.5.67"}
        ]
        assert client.devices()[0]["name"] == "gateway"
        assert client.clients()[0]["is_wired"] is False
        assert client.networks()[0]["purpose"] == "vlan-only"
        assert client.wlans()[0]["security"] == "wpa2"


def test_api_key_paginates_integration_lists() -> None:
    requests: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        offset = request.url.params.get("offset", "0")
        requests.append((request.url.path, offset))
        if request.url.path.endswith("/sites"):
            return httpx.Response(
                200,
                json={
                    "offset": int(offset),
                    "limit": 200,
                    "count": 1,
                    "totalCount": 1,
                    "data": [{"id": "site-1", "name": "Default"}],
                },
            )
        if request.url.path.endswith("/devices"):
            pages = {
                "0": [{"id": "device-1", "name": "gateway"}],
                "1": [{"id": "device-2", "name": "switch"}],
            }
            page = pages.get(offset, [])
            return httpx.Response(
                200,
                json={
                    "offset": int(offset),
                    "limit": 200,
                    "count": len(page),
                    "totalCount": 2,
                    "data": page,
                },
            )
        raise AssertionError(f"unexpected request path: {request.url.path}")

    settings = ControllerSettings(host="https://controller.example", site="site-1", api_key="test")
    with UniFiClient(settings, transport=httpx.MockTransport(handler)) as client:
        assert [device["name"] for device in client.devices()] == ["gateway", "switch"]

    assert requests == [
        ("/proxy/network/integration/v1/sites", "0"),
        ("/proxy/network/integration/v1/sites/site-1/devices", "0"),
        ("/proxy/network/integration/v1/sites/site-1/devices", "1"),
    ]


def test_api_key_reads_and_mutates_dns_through_the_official_integration_endpoint() -> None:
    fixture_path = Path(__file__).parent / "fixtures" / "dns" / "dns-policies-page-1.json"
    dns_page = json.loads(fixture_path.read_text(encoding="utf-8"))
    calls: list[tuple[str, str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path, request.content))
        assert request.headers["X-API-KEY"] == "test"
        if request.url.path.endswith("/sites"):
            return httpx.Response(200, json={"data": [{"id": "site-1", "name": "Default"}]})
        if request.url.path.endswith("/dns/policies") and request.method == "GET":
            return httpx.Response(200, json=dns_page)
        if request.url.path.endswith("/dns/policies") and request.method == "POST":
            return httpx.Response(201, json={"data": {"id": "dns-created"}})
        if request.url.path.endswith("/dns/policies/dns-a-1") and request.method == "PUT":
            return httpx.Response(200, json={"data": {"id": "dns-a-1"}})
        if request.url.path.endswith("/dns/policies/dns-a-1") and request.method == "DELETE":
            return httpx.Response(204)
        raise AssertionError(f"unexpected request: {request.method} {request.url.path}")

    settings = ControllerSettings(host="https://controller.example", api_key="test")
    with UniFiClient(settings, transport=httpx.MockTransport(handler)) as client:
        records = client.dns()
        assert [record["type"] for record in records] == ["A", "CNAME", "A", "AAAA"]
        assert records[2]["_origin"] == "USER"
        assert client.create_dns({"type": "A_RECORD"}) == {"id": "dns-created"}
        assert client.update_dns("dns-a-1", {"type": "A_RECORD"}) == {"id": "dns-a-1"}
        assert client.delete_dns("dns-a-1") is None

    assert [method for method, path, _content in calls] == [
        "GET",
        "GET",
        "POST",
        "PUT",
        "DELETE",
    ]
    assert all("/proxy/network/integration/v1/" in path for _method, path, _content in calls)


def test_session_capabilities_do_not_advertise_dns_mutations() -> None:
    settings = ControllerSettings(
        host="https://controller.example", username="admin", password="password"
    )
    capabilities = LocalClassicAdapter(settings).capabilities

    assert not capabilities.supports("dns", "read")
    assert not capabilities.supports("dns", "apply")


def test_api_key_rejects_unknown_wifi_security_type() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/sites"):
            return httpx.Response(200, json={"data": [{"id": "site-1", "name": "Default"}]})
        if request.url.path.endswith("/wifi/broadcasts"):
            return httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "id": "wifi-1",
                            "name": "Enterprise",
                            "securityConfiguration": {"type": "WPA2_ENTERPRISE"},
                        }
                    ]
                },
            )
        raise AssertionError(f"unexpected request path: {request.url.path}")

    settings = ControllerSettings(host="https://controller.example", site="site-1", api_key="test")
    with (
        UniFiClient(settings, transport=httpx.MockTransport(handler)) as client,
        pytest.raises(RuntimeError, match="unsupported WiFi security type: WPA2_ENTERPRISE"),
    ):
        client.wlans()


def test_api_key_mutations_are_blocked() -> None:
    settings = ControllerSettings(host="https://controller.example", api_key="test")
    client = UniFiClient(settings, transport=httpx.MockTransport(lambda _: httpx.Response(200)))

    with pytest.raises(RuntimeError, match="read-only"):
        client.post("/somewhere", json={"name": "must-not-change"})


def test_local_classic_adapter_preserves_client_name_and_capabilities() -> None:
    settings = ControllerSettings(host="https://controller.example", api_key="test")
    adapter = LocalClassicAdapter(settings)
    legacy_client = UniFiClient(settings)

    assert adapter.adapter_name == ADAPTER_LOCAL_CLASSIC
    assert adapter.capabilities.adapter == ADAPTER_LOCAL_CLASSIC
    assert adapter.capabilities.auth_modes == (AUTH_MODE_API_KEY,)
    assert adapter.capabilities.supports("devices", "read")
    assert not adapter.capabilities.supports("networks", "apply")
    assert isinstance(legacy_client, LocalClassicAdapter)


def test_api_error_does_not_echo_request_body() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "failed"})

    settings = ControllerSettings(host="https://controller.example")
    transport = httpx.MockTransport(handler)

    with pytest.raises(RuntimeError) as error:
        client = UniFiClient(settings, transport=transport)
        client.post("/somewhere", json={"password": "must-not-appear"})

    assert "must-not-appear" not in str(error.value)


def test_secret_manager_reference_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("UNIFI_HOST", "https://controller.example")
    monkeypatch.setenv("UNIFI_API_KEY", "op://vault/item/key")
    monkeypatch.delenv("UNIFI_USER", raising=False)
    monkeypatch.delenv("UNIFI_PASS", raising=False)

    with pytest.raises(CredentialsError, match="secret-manager reference"):
        ControllerSettings.from_env()


def test_invalid_tls_setting_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("UNIFI_HOST", "https://controller.example")
    monkeypatch.setenv("UNIFI_API_KEY", "test-key")
    monkeypatch.setenv("UNIFI_VERIFY_TLS", "sometimes")

    with pytest.raises(CredentialsError, match="must be true or false"):
        ControllerSettings.from_env()
