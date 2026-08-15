"""Read-only client for the official UniFi Site Manager API v1."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import httpx

from .adapters import (
    ADAPTER_CLOUD_SITE_MANAGER,
    AUTH_MODE_API_KEY,
    AdapterAuthenticationError,
    AdapterCapabilities,
    AdapterCapability,
    AdapterConfigurationError,
    AdapterRateLimitError,
    AdapterTransportError,
    UnsupportedCapabilityError,
)

SITE_MANAGER_API_VERSION = "v1"
SITE_MANAGER_DEFAULT_HOST = "https://api.ui.com"
SITE_MANAGER_DEFAULT_PAGE_SIZE = 200
SITE_MANAGER_MAX_PAGES = 1000


def site_manager_capabilities() -> AdapterCapabilities:
    """Return the static, read-only capability set for Site Manager v1."""
    return AdapterCapabilities(
        adapter=ADAPTER_CLOUD_SITE_MANAGER,
        auth_modes=(AUTH_MODE_API_KEY,),
        resources=(
            AdapterCapability("devices", ("read",)),
            AdapterCapability("health", ("read",)),
            AdapterCapability("hosts", ("read",)),
            AdapterCapability("sites", ("read",)),
        ),
    )


@dataclass(frozen=True)
class SiteManagerSettings:
    """Non-secret connection settings plus an API key loaded separately."""

    host: str = SITE_MANAGER_DEFAULT_HOST
    api_key: str = ""
    verify_tls: bool = True
    page_size: int = SITE_MANAGER_DEFAULT_PAGE_SIZE

    def __post_init__(self) -> None:
        host = self.host.rstrip("/")
        if not host.startswith("https://"):
            raise AdapterConfigurationError("Site Manager host must use HTTPS")
        if not self.api_key or self.api_key.startswith("op://"):
            raise AdapterConfigurationError("Site Manager API key is missing or unresolved")
        if not isinstance(self.page_size, int) or not 1 <= self.page_size <= 200:
            raise AdapterConfigurationError("Site Manager page_size must be between 1 and 200")
        object.__setattr__(self, "host", host)

    @classmethod
    def from_controller_settings(cls, settings: Any) -> SiteManagerSettings:
        """Convert a profile-resolved settings object without importing the local client."""
        if getattr(settings, "username", "") or getattr(settings, "password", ""):
            raise AdapterConfigurationError(
                "cloud-site-manager requires API-key authentication, not session credentials"
            )
        return cls(
            host=getattr(settings, "host", SITE_MANAGER_DEFAULT_HOST),
            api_key=getattr(settings, "api_key", ""),
            verify_tls=getattr(settings, "verify_tls", True),
        )


class SiteManagerClient:
    """Explicit read-only Site Manager adapter with bounded pagination."""

    adapter_name = ADAPTER_CLOUD_SITE_MANAGER

    def __init__(
        self,
        settings: SiteManagerSettings,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.settings = settings
        self._http = httpx.Client(
            base_url=settings.host,
            verify=settings.verify_tls,
            timeout=15.0,
            follow_redirects=True,
            transport=transport,
        )

    @property
    def capabilities(self) -> AdapterCapabilities:
        return site_manager_capabilities()

    @classmethod
    def from_controller_settings(
        cls,
        settings: Any,
        transport: httpx.BaseTransport | None = None,
    ) -> SiteManagerClient:
        """Build the cloud adapter from the shared profile settings object."""
        return cls(SiteManagerSettings.from_controller_settings(settings), transport=transport)

    def __enter__(self) -> SiteManagerClient:
        return self

    def __exit__(self, *_args: Any) -> None:
        self.close()

    def close(self) -> None:
        self._http.close()

    def site_url(self, path: str) -> str:
        """Return the versioned cloud path for adapter-compatible callers."""
        return f"/{SITE_MANAGER_API_VERSION}/{path.lstrip('/')}"

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        if method.upper() != "GET":
            raise UnsupportedCapabilityError(self.adapter_name, "controller", "apply")
        try:
            response = self._http.request(
                method,
                self.site_url(path),
                headers={"Accept": "application/json", "X-API-KEY": self.settings.api_key},
                **kwargs,
            )
        except httpx.HTTPError:
            raise AdapterTransportError("Site Manager request failed") from None

        if response.status_code in {401, 403}:
            raise AdapterAuthenticationError("Site Manager authentication failed")
        if response.status_code == 429:
            retry_after = self._retry_after(response.headers.get("Retry-After"))
            raise AdapterRateLimitError(retry_after=retry_after)
        if response.status_code >= 400:
            raise AdapterTransportError(f"Site Manager returned HTTP {response.status_code}")
        if not response.content:
            return None
        try:
            payload = response.json()
        except ValueError:
            raise AdapterTransportError("Site Manager returned invalid JSON") from None
        if not isinstance(payload, dict):
            raise AdapterTransportError("Site Manager returned an invalid response envelope")
        return payload

    @staticmethod
    def _retry_after(value: str | None) -> int | None:
        if value is None:
            return None
        try:
            parsed = int(float(value))
        except ValueError:
            return None
        return max(parsed, 0)

    def _list(self, path: str, params: Mapping[str, Any] | None = None) -> list[dict[str, Any]]:
        query = dict(params or {})
        query["pageSize"] = self.settings.page_size
        items: list[dict[str, Any]] = []
        next_token: str | None = None
        seen_tokens: set[str] = set()

        for _page in range(SITE_MANAGER_MAX_PAGES):
            if next_token is not None:
                query["nextToken"] = next_token
            payload = self._request("GET", path, params=query)
            if not isinstance(payload.get("data"), list):
                raise AdapterTransportError("Site Manager response data is not a list")
            items.extend(item for item in payload["data"] if isinstance(item, dict))
            candidate = payload.get("nextToken")
            if candidate in (None, ""):
                return items
            if not isinstance(candidate, str) or candidate in seen_tokens:
                raise AdapterTransportError("Site Manager pagination token did not advance")
            seen_tokens.add(candidate)
            next_token = candidate

        raise AdapterTransportError("Site Manager pagination exceeded the safety limit")

    def hosts(self) -> list[dict[str, Any]]:
        """List all hosts visible to the API key."""
        return self._list("hosts")

    def sites(self) -> list[dict[str, Any]]:
        """List all Network sites visible to the API key."""
        return self._list("sites")

    def devices(self) -> list[dict[str, Any]]:
        """List visible devices in the normalized Lanweave read model."""
        devices = self._list("devices")
        return [
            {
                "_id": item.get("id") or item.get("deviceId"),
                "id": item.get("id") or item.get("deviceId"),
                "name": item.get("name") or item.get("model") or item.get("id"),
                "hostname": item.get("name") or item.get("hostname"),
                "ip": item.get("ipAddress") or item.get("ip"),
                "mac": item.get("macAddress") or item.get("mac"),
                "model": item.get("model"),
                "state": item.get("state") or item.get("status"),
                "host_id": item.get("hostId"),
                "site_id": item.get("siteId"),
            }
            for item in devices
        ]

    def health(self) -> list[dict[str, Any]]:
        """Return reachability-oriented health records derived from site inventory."""
        health: list[dict[str, Any]] = []
        for site in self.sites():
            metadata = site.get("meta") or {}
            site_id = site.get("siteId") or site.get("id")
            name = metadata.get("name") or metadata.get("desc") or site_id
            health.append(
                {
                    "subsystem": "site",
                    "status": "up",
                    "site_id": site_id,
                    "name": name,
                    "host_id": site.get("hostId"),
                    "permission": site.get("permission"),
                }
            )
        return health

    def clients(self) -> list[dict[str, Any]]:
        raise UnsupportedCapabilityError(self.adapter_name, "clients", "read")

    def networks(self) -> list[dict[str, Any]]:
        raise UnsupportedCapabilityError(self.adapter_name, "networks", "read")

    def wlans(self) -> list[dict[str, Any]]:
        raise UnsupportedCapabilityError(self.adapter_name, "wlans", "read")

    def nat(self) -> list[dict[str, Any]]:
        raise UnsupportedCapabilityError(self.adapter_name, "nat", "read")

    def create_nat(self, payload: dict[str, Any]) -> Any:
        raise UnsupportedCapabilityError(self.adapter_name, "nat", "apply")

    def update_nat(self, object_id: str, payload: dict[str, Any]) -> Any:
        raise UnsupportedCapabilityError(self.adapter_name, "nat", "apply")

    def delete_nat(self, object_id: str) -> Any:
        raise UnsupportedCapabilityError(self.adapter_name, "nat", "prune")

    def dns(self) -> list[dict[str, Any]]:
        raise UnsupportedCapabilityError(self.adapter_name, "dns", "read")

    def create_dns(self, payload: dict[str, Any]) -> Any:
        raise UnsupportedCapabilityError(self.adapter_name, "dns", "apply")

    def update_dns(self, object_id: str, payload: dict[str, Any]) -> Any:
        raise UnsupportedCapabilityError(self.adapter_name, "dns", "apply")

    def delete_dns(self, object_id: str) -> Any:
        raise UnsupportedCapabilityError(self.adapter_name, "dns", "prune")

    def get(self, path: str, **kwargs: Any) -> Any:
        raise UnsupportedCapabilityError(self.adapter_name, "controller", "read")

    def post(self, path: str, json: Any = None, **kwargs: Any) -> Any:
        raise UnsupportedCapabilityError(self.adapter_name, "controller", "apply")

    def put(self, path: str, json: Any = None, **kwargs: Any) -> Any:
        raise UnsupportedCapabilityError(self.adapter_name, "controller", "apply")

    def delete(self, path: str, **kwargs: Any) -> Any:
        raise UnsupportedCapabilityError(self.adapter_name, "controller", "prune")


__all__ = [
    "SITE_MANAGER_API_VERSION",
    "SITE_MANAGER_DEFAULT_HOST",
    "SITE_MANAGER_DEFAULT_PAGE_SIZE",
    "SiteManagerClient",
    "SiteManagerSettings",
    "site_manager_capabilities",
]
