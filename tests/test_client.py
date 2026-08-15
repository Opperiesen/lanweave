import httpx
import pytest

from lanweave.client import ControllerSettings, CredentialsError, UniFiClient


def test_site_url_is_controller_relative() -> None:
    settings = ControllerSettings(host="https://controller.example", api_key="test")

    with UniFiClient(settings) as client:
        assert client.site_url("stat/device") == ("/proxy/network/api/s/default/stat/device")


def test_devices_unwraps_unifi_data() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/proxy/network/api/s/default/stat/device"
        assert request.headers["X-API-Key"] == "test"
        return httpx.Response(200, json={"meta": {}, "data": [{"name": "gateway"}]})

    settings = ControllerSettings(host="https://controller.example", api_key="test")
    transport = httpx.MockTransport(handler)

    with UniFiClient(settings, transport=transport) as client:
        assert client.devices() == [{"name": "gateway"}]


def test_api_error_does_not_echo_request_body() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "failed"})

    settings = ControllerSettings(host="https://controller.example", api_key="test")
    transport = httpx.MockTransport(handler)

    with UniFiClient(settings, transport=transport) as client, pytest.raises(RuntimeError) as error:
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
