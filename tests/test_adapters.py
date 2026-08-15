from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from lanweave.adapters import (
    ADAPTER_LOCAL_CLASSIC,
    AUTH_MODE_API_KEY,
    AUTH_MODE_SESSION,
    Adapter,
    AdapterAuthenticationError,
    AdapterCapabilities,
    AdapterCapability,
    AdapterConfigurationError,
    AdapterRateLimitError,
    AdapterRegistry,
    AdapterTransportError,
    UnsupportedCapabilityError,
    local_classic_capabilities,
)


def test_capabilities_are_sorted_and_operations_use_canonical_order() -> None:
    capabilities = AdapterCapabilities(
        adapter="test-adapter",
        auth_modes=("session", "api-key", "session"),
        resources=(
            AdapterCapability("wlans", ("prune", "read", "apply")),
            AdapterCapability("health", ("read",)),
        ),
    )

    assert capabilities.to_dict() == {
        "format_version": 1,
        "adapter": "test-adapter",
        "auth_modes": ["api-key", "session"],
        "resources": [
            {"resource": "health", "operations": ["read"]},
            {"resource": "wlans", "operations": ["read", "apply", "prune"]},
        ],
    }
    assert capabilities.supports("wlans", "apply")
    assert not capabilities.supports("health", "apply")


def test_capability_validation_rejects_duplicates_and_unknown_operations() -> None:
    with pytest.raises(ValueError, match="duplicates"):
        AdapterCapability("devices", ("read", "read"))

    with pytest.raises(ValueError, match="unsupported operation"):
        AdapterCapability("devices", ("inspect",))

    with pytest.raises(ValueError, match="resources must not contain duplicates"):
        AdapterCapabilities(
            adapter="test-adapter",
            auth_modes=("session",),
            resources=(
                AdapterCapability("devices", ("read",)),
                AdapterCapability("devices", ("read",)),
            ),
        )


def test_unsupported_capability_is_structured_and_secret_free() -> None:
    capabilities = AdapterCapabilities(
        adapter="cloud-site-manager",
        auth_modes=("api-key",),
        resources=(AdapterCapability("devices", ("read",)),),
    )

    with pytest.raises(UnsupportedCapabilityError) as caught:
        capabilities.require("devices", "apply")

    assert caught.value.to_dict() == {
        "error": "unsupported_capability",
        "adapter": "cloud-site-manager",
        "resource": "devices",
        "operation": "apply",
        "detail": "cloud-site-manager does not support apply on devices",
    }
    assert "secret" not in str(caught.value)


@pytest.mark.parametrize(
    ("auth_mode", "mutating"),
    [(AUTH_MODE_SESSION, True), (AUTH_MODE_API_KEY, False)],
)
def test_local_classic_capabilities_preserve_v02_auth_boundaries(
    auth_mode: str,
    mutating: bool,
) -> None:
    capabilities = local_classic_capabilities(auth_mode)

    assert capabilities.adapter == ADAPTER_LOCAL_CLASSIC
    assert capabilities.supports("devices", "read")
    assert capabilities.supports("networks", "plan")
    assert capabilities.supports("networks", "apply") is mutating
    assert capabilities.supports("networks", "prune") is mutating


def test_firewall_capabilities_are_api_key_only() -> None:
    session = local_classic_capabilities(AUTH_MODE_SESSION)
    api_key = local_classic_capabilities(AUTH_MODE_API_KEY)

    assert not session.supports("firewall", "read")
    assert api_key.supports("firewall", "read")
    assert api_key.supports("firewall", "export")
    assert api_key.supports("firewall", "plan")
    assert api_key.supports("firewall", "apply")
    assert api_key.supports("firewall", "prune")


def test_nat_read_and_export_are_session_only_until_mutation_support_exists() -> None:
    session = local_classic_capabilities(AUTH_MODE_SESSION)
    api_key = local_classic_capabilities(AUTH_MODE_API_KEY)

    assert session.supports("nat", "read")
    assert session.supports("nat", "export")
    assert session.supports("nat", "plan")
    assert not session.supports("nat", "apply")
    assert not api_key.supports("nat", "read")


def test_adapter_errors_use_stable_codes_without_response_payloads() -> None:
    errors = [
        AdapterConfigurationError("unknown adapter: cloud-site-manager"),
        AdapterAuthenticationError("authentication failed"),
        AdapterTransportError("request failed"),
        AdapterRateLimitError(retry_after=30),
    ]

    assert [error.to_dict()["error"] for error in errors] == [
        "invalid_configuration",
        "authentication_error",
        "transport_error",
        "rate_limit",
    ]
    assert errors[-1].to_dict()["retry_after"] == 30
    assert all("password" not in str(error) for error in errors)


class FakeAdapter:
    adapter_name = "fake"
    capabilities = AdapterCapabilities(
        adapter="fake",
        auth_modes=("fixture",),
        resources=(AdapterCapability("health", ("read",)),),
    )
    settings = SimpleNamespace(host="https://fixture.example", site="default")

    def __enter__(self) -> FakeAdapter:
        return self

    def __exit__(self, *_args: Any) -> None:
        return None

    def close(self) -> None:
        return None

    def site_url(self, path: str) -> str:
        return path

    def health(self) -> list[dict[str, Any]]:
        return []

    def devices(self) -> list[dict[str, Any]]:
        return []

    def clients(self) -> list[dict[str, Any]]:
        return []

    def networks(self) -> list[dict[str, Any]]:
        return []

    def wlans(self) -> list[dict[str, Any]]:
        return []

    def nat(self) -> list[dict[str, Any]]:
        return []

    def dns(self) -> list[dict[str, Any]]:
        return []

    def create_dns(self, payload: dict[str, Any]) -> Any:
        return payload

    def update_dns(self, object_id: str, payload: dict[str, Any]) -> Any:
        return payload

    def delete_dns(self, object_id: str) -> Any:
        return None

    def get(self, path: str, **kwargs: Any) -> Any:
        return None

    def post(self, path: str, json: Any = None, **kwargs: Any) -> Any:
        return None

    def put(self, path: str, json: Any = None, **kwargs: Any) -> Any:
        return None

    def delete(self, path: str, **kwargs: Any) -> Any:
        return None


def test_adapter_protocol_and_registry_are_explicit_without_fallback() -> None:
    assert isinstance(FakeAdapter(), Adapter)
    registry = AdapterRegistry({"fake": lambda: FakeAdapter()})

    assert registry.names() == ("fake",)
    assert registry.create("fake").adapter_name == "fake"

    with pytest.raises(AdapterConfigurationError, match="unknown adapter"):
        registry.create("missing")

    with pytest.raises(AdapterConfigurationError, match="already registered"):
        registry.register("fake", lambda: FakeAdapter())
