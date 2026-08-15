import json
from pathlib import Path

import httpx
import pytest

from lanweave.adapters import ADAPTER_LOCAL_CLASSIC, AUTH_MODE_API_KEY
from lanweave.client import ControllerSettings, CredentialsError, LocalClassicAdapter, UniFiClient
from lanweave.firewall import UnsupportedFirewallVariantError


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


def test_session_reads_classic_nat_inventory_from_versioned_fixture() -> None:
    fixture_path = Path(__file__).parent / "fixtures" / "nat" / "portforward-page-1.json"
    nat_page = json.loads(fixture_path.read_text(encoding="utf-8"))
    calls: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path))
        if request.url.path == "/api/auth/login":
            return httpx.Response(200, json={"data": {}})
        if request.url.path.endswith("/rest/portforward"):
            return httpx.Response(200, json=nat_page)
        raise AssertionError(f"unexpected request: {request.method} {request.url.path}")

    settings = ControllerSettings(
        host="https://controller.example",
        username="admin",
        password="fixture-password",
    )
    with UniFiClient(settings, transport=httpx.MockTransport(handler)) as client:
        mappings = client.nat()

    assert [mapping["name"] for mapping in mappings] == ["controller-dns", "web"]
    assert calls == [
        ("POST", "/api/auth/login"),
        ("GET", "/proxy/network/api/s/default/rest/portforward"),
    ]


def test_api_key_does_not_fallback_to_undocumented_nat_endpoint() -> None:
    settings = ControllerSettings(host="https://controller.example", api_key="test")
    transport = httpx.MockTransport(lambda _request: httpx.Response(500))
    with (
        UniFiClient(settings, transport=transport) as client,
        pytest.raises(RuntimeError, match="local session authentication"),
    ):
        client.nat()


def test_session_mutates_classic_nat_endpoint_with_csrf_and_object_id() -> None:
    calls: list[tuple[str, str, object, str | None]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/auth/login":
            return httpx.Response(200, headers={"X-CSRF-Token": "fixture-csrf"}, json={"data": {}})
        if request.url.path.endswith("/rest/portforward") and request.method == "POST":
            calls.append(
                (
                    request.method,
                    request.url.path,
                    json.loads(request.content),
                    request.headers.get("X-CSRF-Token"),
                )
            )
            return httpx.Response(201, json={"data": {"_id": "nat-created"}})
        if request.url.path.endswith("/rest/portforward/nat-1") and request.method == "PUT":
            calls.append(
                (
                    request.method,
                    request.url.path,
                    json.loads(request.content),
                    request.headers.get("X-CSRF-Token"),
                )
            )
            return httpx.Response(200, json={"data": {"_id": "nat-1"}})
        if request.url.path.endswith("/rest/portforward/nat-1") and request.method == "DELETE":
            calls.append(
                (request.method, request.url.path, None, request.headers.get("X-CSRF-Token"))
            )
            return httpx.Response(204)
        raise AssertionError(f"unexpected request: {request.method} {request.url.path}")

    settings = ControllerSettings(
        host="https://controller.example",
        username="admin",
        password="fixture-password",
    )
    payload = {
        "name": "web",
        "enabled": True,
        "pfwd_interface": "wan",
        "src": "any",
        "dst_port": "443",
        "fwd": "192.0.2.10",
        "fwd_port": "8443",
        "proto": "tcp",
    }
    with UniFiClient(settings, transport=httpx.MockTransport(handler)) as client:
        client.create_nat(payload)
        client.update_nat("nat-1", payload)
        client.delete_nat("nat-1")

    assert calls == [
        (
            "POST",
            "/proxy/network/api/s/default/rest/portforward",
            payload,
            "fixture-csrf",
        ),
        (
            "PUT",
            "/proxy/network/api/s/default/rest/portforward/nat-1",
            {**payload, "_id": "nat-1"},
            "fixture-csrf",
        ),
        (
            "DELETE",
            "/proxy/network/api/s/default/rest/portforward/nat-1",
            None,
            "fixture-csrf",
        ),
    ]


def test_api_key_rejects_nat_mutations_before_network_access() -> None:
    settings = ControllerSettings(host="https://controller.example", api_key="test")
    transport = httpx.MockTransport(lambda _request: httpx.Response(500))
    with UniFiClient(settings, transport=transport) as client:
        with pytest.raises(RuntimeError, match="local session authentication"):
            client.create_nat({})
        with pytest.raises(RuntimeError, match="local session authentication"):
            client.update_nat("nat-1", {})
        with pytest.raises(RuntimeError, match="local session authentication"):
            client.delete_nat("nat-1")


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


def test_api_key_reads_firewall_inventory_and_explicit_ordering() -> None:
    fixture_dir = Path(__file__).parent / "fixtures" / "firewall"
    zones_page = json.loads((fixture_dir / "firewall-zones-page-1.json").read_text())
    groups_page = json.loads(
        (fixture_dir / "firewall-traffic-matching-lists-page-1.json").read_text()
    )
    web_group = json.loads((fixture_dir / "firewall-traffic-matching-list-web.json").read_text())
    servers_group = json.loads(
        (fixture_dir / "firewall-traffic-matching-list-servers.json").read_text()
    )
    policies_page = json.loads((fixture_dir / "firewall-policies-page-1.json").read_text())
    ordering = json.loads((fixture_dir / "firewall-ordering.json").read_text())

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["X-API-KEY"] == "test"
        path = request.url.path
        if path.endswith("/sites"):
            return httpx.Response(200, json={"data": [{"id": "site-1", "name": "Default"}]})
        if path.endswith("/firewall/zones"):
            return httpx.Response(200, json=zones_page)
        if path.endswith("/traffic-matching-lists"):
            return httpx.Response(200, json=groups_page)
        if path.endswith("/traffic-matching-lists/group-web"):
            return httpx.Response(200, json=web_group)
        if path.endswith("/traffic-matching-lists/group-servers"):
            return httpx.Response(200, json=servers_group)
        if path.endswith("/firewall/policies"):
            return httpx.Response(200, json=policies_page)
        if path.endswith("/firewall/policies/ordering"):
            return httpx.Response(200, json=ordering)
        raise AssertionError(f"unexpected request: {request.method} {path}")

    settings = ControllerSettings(host="https://controller.example", site="site-1", api_key="test")
    with UniFiClient(settings, transport=httpx.MockTransport(handler)) as client:
        zones = client.firewall_zones()
        groups = client.firewall_traffic_matching_lists()
        policies = client.firewall_policies()
        policy_order = client.firewall_policy_ordering("zone-custom", "zone-lan")

    assert [(zone["name"], zone["_origin"]) for zone in zones] == [
        ("LAN", "SYSTEM_DEFINED"),
        ("Trusted", "USER_DEFINED"),
        ("WAN", "SYSTEM_DEFINED"),
    ]
    groups_by_name = {group["name"]: group for group in groups}
    assert groups_by_name["web"]["group_type"] == "port_group"
    assert groups_by_name["servers"]["items"] == ["192.0.2.10", "192.0.2.0/24"]
    assert policies[0]["source"]["zone_id"] == "zone-custom"
    assert policies[0]["action"] == "ALLOW"
    assert policy_order == {
        "after_system_defined": ["policy-allow"],
        "before_system_defined": [],
    }


def test_api_key_rejects_malformed_firewall_pagination() -> None:
    malformed_page = json.loads(
        (
            Path(__file__).parent / "fixtures" / "firewall" / "firewall-malformed-page.json"
        ).read_text()
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/sites"):
            return httpx.Response(200, json={"data": [{"id": "site-1", "name": "Default"}]})
        if request.url.path.endswith("/firewall/zones"):
            return httpx.Response(200, json=malformed_page)
        raise AssertionError(f"unexpected request: {request.method} {request.url.path}")

    settings = ControllerSettings(host="https://controller.example", site="site-1", api_key="test")
    with (
        UniFiClient(settings, transport=httpx.MockTransport(handler)) as client,
        pytest.raises(RuntimeError, match="invalid pagination metadata"),
    ):
        client.firewall_zones()


def test_api_key_rejects_unsupported_firewall_group_variant() -> None:
    unsupported = json.loads(
        (
            Path(__file__).parent
            / "fixtures"
            / "firewall"
            / "firewall-traffic-matching-list-unsupported.json"
        ).read_text()
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/sites"):
            return httpx.Response(200, json={"data": [{"id": "site-1", "name": "Default"}]})
        if request.url.path.endswith("/traffic-matching-lists"):
            return httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "id": unsupported["id"],
                            "name": unsupported["name"],
                            "type": unsupported["type"],
                        }
                    ],
                    "limit": 200,
                    "offset": 0,
                    "totalCount": 1,
                },
            )
        if request.url.path.endswith("/traffic-matching-lists/group-domain"):
            return httpx.Response(200, json=unsupported)
        raise AssertionError(f"unexpected request: {request.method} {request.url.path}")

    settings = ControllerSettings(host="https://controller.example", site="site-1", api_key="test")
    with (
        UniFiClient(settings, transport=httpx.MockTransport(handler)) as client,
        pytest.raises(UnsupportedFirewallVariantError),
    ):
        client.firewall_traffic_matching_lists()


def test_api_key_firewall_mutations_use_only_official_paths() -> None:
    calls: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path))
        if request.url.path.endswith("/sites"):
            return httpx.Response(200, json={"data": [{"id": "site-1", "name": "Default"}]})
        return httpx.Response(200, json={"data": {"id": "created"}})

    settings = ControllerSettings(host="https://controller.example", site="site-1", api_key="test")
    with UniFiClient(settings, transport=httpx.MockTransport(handler)) as client:
        client.create_firewall_zone({"name": "Trusted", "networkIds": []})
        client.update_firewall_zone("zone-1", {"name": "Trusted", "networkIds": []})
        client.delete_firewall_zone("zone-1")
        client.create_firewall_traffic_matching_list({"name": "web", "type": "PORTS", "items": []})
        client.update_firewall_traffic_matching_list(
            "group-1", {"name": "web", "type": "PORTS", "items": []}
        )
        client.delete_firewall_traffic_matching_list("group-1")
        client.create_firewall_policy({"name": "allow", "action": {"type": "ALLOW"}})
        client.update_firewall_policy("policy-1", {"name": "allow", "action": {"type": "ALLOW"}})
        client.delete_firewall_policy("policy-1")
        client.reorder_firewall_policies(
            "zone-1",
            "zone-2",
            after_system_defined=["policy-1"],
            before_system_defined=[],
        )

    assert [method for method, _path in calls] == [
        "GET",
        "POST",
        "PUT",
        "DELETE",
        "POST",
        "PUT",
        "DELETE",
        "POST",
        "PUT",
        "DELETE",
        "PUT",
    ]
    assert all(
        "/firewall/" in path or "/traffic-matching-lists" in path or path.endswith("/sites")
        for _, path in calls
    )


def test_session_capabilities_do_not_advertise_dns_mutations() -> None:
    settings = ControllerSettings(
        host="https://controller.example", username="admin", password="password"
    )
    capabilities = LocalClassicAdapter(settings).capabilities

    assert not capabilities.supports("dns", "read")
    assert not capabilities.supports("dns", "apply")
    assert not capabilities.supports("firewall", "read")
    assert not capabilities.supports("firewall", "apply")


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
