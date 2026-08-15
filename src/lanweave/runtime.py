"""Explicit adapter construction and offline capability resolution."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .adapters import (
    ADAPTER_CLOUD_SITE_MANAGER,
    ADAPTER_LOCAL_CLASSIC,
    AUTH_MODE_API_KEY,
    Adapter,
    AdapterCapabilities,
    AdapterConfigurationError,
    local_classic_capabilities,
)
from .client import ControllerSettings, UniFiClient
from .profiles import ResolvedTarget
from .site_manager import SiteManagerClient, site_manager_capabilities

LocalAdapterFactory = Callable[[ControllerSettings], Adapter]
CloudAdapterFactory = Callable[[Any], Adapter]


def create_adapter(
    target: ResolvedTarget,
    *,
    local_factory: LocalAdapterFactory | None = None,
    cloud_factory: CloudAdapterFactory | None = None,
) -> Adapter:
    """Create only the adapter named by the target; never fall back."""
    adapter_name = target.identity.adapter
    if adapter_name == ADAPTER_LOCAL_CLASSIC:
        return (local_factory or UniFiClient)(target.settings)
    if adapter_name == ADAPTER_CLOUD_SITE_MANAGER:
        return (cloud_factory or SiteManagerClient.from_controller_settings)(target.settings)
    raise AdapterConfigurationError(f"unknown adapter: {adapter_name}")


def capabilities_for_target(adapter: str, auth_mode: str) -> AdapterCapabilities:
    """Return capabilities without loading credentials or contacting a target."""
    if adapter == ADAPTER_LOCAL_CLASSIC:
        return local_classic_capabilities(auth_mode)
    if adapter == ADAPTER_CLOUD_SITE_MANAGER:
        if auth_mode != AUTH_MODE_API_KEY:
            raise AdapterConfigurationError("cloud-site-manager requires API-key authentication")
        return site_manager_capabilities()
    raise AdapterConfigurationError(f"unknown adapter: {adapter}")


__all__ = ["capabilities_for_target", "create_adapter"]
