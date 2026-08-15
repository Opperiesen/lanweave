"""Fixtures for opt-in live UniFi controller integration tests."""

from __future__ import annotations

import ipaddress
import os
from collections.abc import Iterator
from dataclasses import dataclass

import pytest

from lanweave.client import ControllerSettings, UniFiClient


def _env(name: str) -> str:
    return os.getenv(name, "").strip()


def _env_bool(name: str, default: bool) -> bool:
    value = _env(name)
    if not value:
        return default
    normalized = value.lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    pytest.fail(f"{name} must be true or false")


def _settings() -> ControllerSettings:
    host = _env("LANWEAVE_INTEGRATION_HOST")
    api_key = _env("LANWEAVE_INTEGRATION_API_KEY")
    username = _env("LANWEAVE_INTEGRATION_USER")
    password = _env("LANWEAVE_INTEGRATION_PASS")
    if not host:
        pytest.skip("live integration credentials are not configured")
    if not api_key and not (username and password):
        pytest.skip("set an integration API key or both session credentials")
    if any(value.startswith("op://") for value in (api_key, username, password)):
        pytest.fail("integration credentials must be resolved before the test starts")
    return ControllerSettings(
        host=host.rstrip("/"),
        site=_env("LANWEAVE_INTEGRATION_SITE") or "default",
        verify_tls=_env_bool("LANWEAVE_INTEGRATION_VERIFY_TLS", True),
        api_key=api_key,
        username=username,
        password=password,
    )


@pytest.fixture(scope="session")
def integration_client() -> Iterator[UniFiClient]:
    """Yield a live client, or skip safely when protected secrets are absent."""

    with UniFiClient(_settings()) as client:
        yield client


@dataclass(frozen=True)
class MutationTarget:
    client: UniFiClient
    name: str
    subnet: str
    vlan: int


@dataclass(frozen=True)
class DnsMutationTarget:
    client: UniFiClient
    name: str
    initial_address: str
    updated_address: str


@pytest.fixture(scope="session")
def mutation_target(integration_client: UniFiClient) -> MutationTarget:
    """Return a uniquely named, explicitly authorized mutation target."""

    if _env("LANWEAVE_INTEGRATION_MUTATIONS").lower() not in {"1", "true", "yes", "on"}:
        pytest.skip("mutation suite is disabled")
    if _env("LANWEAVE_INTEGRATION_MUTATION_CONFIRM") != "I_UNDERSTAND":
        pytest.skip("mutation confirmation is not enabled")

    prefix = _env("LANWEAVE_INTEGRATION_MUTATION_PREFIX")
    if not prefix.startswith("lanweave-ci-"):
        pytest.fail("mutation prefix must start with lanweave-ci-")
    run_id = _env("LANWEAVE_INTEGRATION_RUN_ID") or "local"
    name = f"{prefix}{run_id}-network"
    if len(name) > 64:
        pytest.fail("mutation network name must be at most 64 characters")

    subnet = _env("LANWEAVE_INTEGRATION_MUTATION_SUBNET")
    try:
        network = ipaddress.ip_network(subnet, strict=False)
    except ValueError as exc:
        pytest.fail(f"mutation subnet is invalid: {exc}")
    if network.version != 4 or network.prefixlen > 30:
        pytest.fail("mutation subnet must be an IPv4 network no smaller than /30")

    vlan_text = _env("LANWEAVE_INTEGRATION_MUTATION_VLAN")
    try:
        vlan = int(vlan_text)
    except ValueError:
        pytest.fail("mutation VLAN must be an integer")
    if not 2 <= vlan <= 4094:
        pytest.fail("mutation VLAN must be between 2 and 4094")

    return MutationTarget(client=integration_client, name=name, subnet=subnet, vlan=vlan)


@pytest.fixture(scope="session")
def dns_mutation_target(integration_client: UniFiClient) -> DnsMutationTarget:
    """Return an isolated DNS target for the API-key-only mutation suite."""

    if _env("LANWEAVE_INTEGRATION_DNS_MUTATIONS").lower() not in {"1", "true", "yes", "on"}:
        pytest.skip("DNS mutation suite is disabled")
    if _env("LANWEAVE_INTEGRATION_DNS_MUTATION_CONFIRM") != "I_UNDERSTAND":
        pytest.skip("DNS mutation confirmation is not enabled")
    if not integration_client.settings.api_key:
        pytest.fail("DNS mutations require a local Integration API key")

    prefix = _env("LANWEAVE_INTEGRATION_DNS_MUTATION_PREFIX")
    if not prefix.startswith("lanweave-ci-"):
        pytest.fail("DNS mutation prefix must start with lanweave-ci-")
    run_id = _env("LANWEAVE_INTEGRATION_RUN_ID") or "local"
    name = f"{prefix}{run_id}.home.arpa"
    if len(name) > 253:
        pytest.fail("DNS mutation name is too long")

    return DnsMutationTarget(
        client=integration_client,
        name=name,
        initial_address=_env("LANWEAVE_INTEGRATION_DNS_INITIAL_ADDRESS") or "192.0.2.10",
        updated_address=_env("LANWEAVE_INTEGRATION_DNS_UPDATED_ADDRESS") or "192.0.2.11",
    )
