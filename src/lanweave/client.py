"""Small, testable client for the local UniFi Network API."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Self
from urllib.parse import urljoin

import httpx
from dotenv import load_dotenv

from .adapters import (
    ADAPTER_LOCAL_CLASSIC,
    AUTH_MODE_API_KEY,
    AUTH_MODE_SESSION,
    AdapterCapabilities,
    local_classic_capabilities,
)

INTEGRATION_API_PREFIX = "/proxy/network/integration/v1"


class CredentialsError(ValueError):
    """Raised when controller credentials are absent or unsafe."""


def _env_bool(name: str, default: bool, environment: Mapping[str, str]) -> bool:
    value = environment.get(name)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise CredentialsError(f"{name} must be true or false")


def _reject_unresolved(values: dict[str, str]) -> None:
    unresolved = sorted(name for name, value in values.items() if value.startswith("op://"))
    if unresolved:
        raise CredentialsError(
            "unresolved secret-manager reference in: "
            + ", ".join(unresolved)
            + ". Resolve it before starting the tool."
        )


def _as_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise RuntimeError("UniFi API returned an unexpected list response")
    return [item for item in value if isinstance(item, dict)]


def _integration_network(summary: dict[str, Any], detail: dict[str, Any]) -> dict[str, Any]:
    """Normalize a v1 integration network to Lanweave's classic read model."""
    name = str(summary.get("name") or detail.get("name") or "")
    vlan_id = summary.get("vlanId", detail.get("vlanId"))
    try:
        vlan = int(vlan_id) if vlan_id is not None else 1
    except (TypeError, ValueError):
        vlan = 1

    management = str(detail.get("management") or summary.get("management") or "").upper()
    purpose = "vlan-only" if management in {"VLAN_ONLY", "VLAN-ONLY"} else "corporate"
    if "guest" in name.lower():
        purpose = "guest"

    ipv4 = detail.get("ipv4Configuration") or {}
    dhcp = ipv4.get("dhcpConfiguration") or {}
    host_ip = ipv4.get("hostIpAddress")
    prefix_length = ipv4.get("prefixLength")
    result: dict[str, Any] = {
        "_id": summary.get("id") or detail.get("id"),
        "id": summary.get("id") or detail.get("id"),
        "name": name,
        "purpose": purpose,
        "vlan_enabled": vlan != 1,
    }
    if vlan != 1:
        result["vlan"] = str(vlan)
    if host_ip and prefix_length is not None:
        result["ip_subnet"] = f"{host_ip}/{prefix_length}"

    dhcp_mode = str(dhcp.get("mode") or "").upper()
    result["dhcpd_enabled"] = dhcp_mode == "SERVER"
    ip_range = dhcp.get("ipAddressRange") or {}
    if ip_range.get("start"):
        result["dhcpd_start"] = ip_range["start"]
    if ip_range.get("stop"):
        result["dhcpd_stop"] = ip_range["stop"]
    if dhcp.get("leaseTimeSeconds") is not None:
        result["dhcpd_leasetime"] = dhcp["leaseTimeSeconds"]
    if dhcp.get("domainName"):
        result["domain_name"] = dhcp["domainName"]
    for index, dns in enumerate(dhcp.get("dnsServerIpAddressesOverride") or [], start=1):
        result[f"dhcpd_dns_{index}"] = dns
    return result


def _integration_wlan(value: dict[str, Any]) -> dict[str, Any]:
    """Normalize a v1 WiFi broadcast to Lanweave's classic read model."""
    frequencies = value.get("broadcastingFrequenciesGHz") or []
    bands: list[str] = []
    for frequency in frequencies:
        try:
            numeric_frequency = float(frequency)
        except (TypeError, ValueError):
            continue
        band = {2.4: "2g", 5.0: "5g", 6.0: "6g"}.get(numeric_frequency)
        if band and band not in bands:
            bands.append(band)
    if not bands:
        bands = ["2g", "5g"]

    security_config = value.get("securityConfiguration") or {}
    security_type = str(security_config.get("type") or "OPEN").upper()
    if security_type == "WPA3_PERSONAL":
        security = "wpa3"
    elif security_type == "WPA2_WPA3_PERSONAL":
        security = "wpa3-transition"
    elif security_type == "WPA2_PERSONAL":
        security = "wpa2"
    else:
        security = "open"

    network = value.get("network") or {}
    result: dict[str, Any] = {
        "_id": value.get("id"),
        "id": value.get("id"),
        "name": value.get("name", "Unnamed"),
        "enabled": value.get("enabled", True),
        "networkconf_id": network.get("networkId", ""),
        "wlan_bands": bands,
        "wlan_band": bands[0] if len(bands) == 1 else "both",
        "security": security,
        "wpa3_support": security in {"wpa3", "wpa3-transition"},
        "wpa3_transition": security == "wpa3-transition",
        "fast_roaming_enabled": bool(security_config.get("fastRoamingEnabled", False)),
        "pmf_mode": str(security_config.get("pmfMode") or "optional").lower(),
    }
    return result


@dataclass(frozen=True)
class ControllerSettings:
    """Connection settings loaded from environment variables."""

    host: str
    site: str = "default"
    verify_tls: bool = True
    api_key: str = ""
    username: str = ""
    password: str = ""

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> ControllerSettings:
        if environ is None:
            load_dotenv()
            environment = os.environ
        else:
            environment = environ
        settings = cls(
            host=environment.get("UNIFI_HOST", "").rstrip("/"),
            site=environment.get("UNIFI_SITE", "default"),
            verify_tls=_env_bool("UNIFI_VERIFY_TLS", True, environment),
            api_key=environment.get("UNIFI_API_KEY", ""),
            username=environment.get("UNIFI_USER", ""),
            password=environment.get("UNIFI_PASS", ""),
        )
        _reject_unresolved(
            {
                "UNIFI_API_KEY": settings.api_key,
                "UNIFI_USER": settings.username,
                "UNIFI_PASS": settings.password,
            }
        )
        if not settings.host:
            raise CredentialsError("UNIFI_HOST is required")
        if not settings.api_key and not (settings.username and settings.password):
            raise CredentialsError("set UNIFI_API_KEY or both UNIFI_USER and UNIFI_PASS")
        return settings


class LocalClassicAdapter:
    """Local UniFi classic adapter with v0.2 behavior preserved."""

    adapter_name = ADAPTER_LOCAL_CLASSIC

    def __init__(
        self,
        settings: ControllerSettings,
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
        self._csrf_token: str | None = None
        self._integration_site_id: str | None = None

    @property
    def capabilities(self) -> AdapterCapabilities:
        """Return capabilities for the selected local authentication mode."""
        auth_mode = AUTH_MODE_API_KEY if self.settings.api_key else AUTH_MODE_SESSION
        return local_classic_capabilities(auth_mode)

    def __enter__(self) -> Self:
        if not self.settings.api_key:
            self.login()
        return self

    def __exit__(self, *_args: Any) -> None:
        self.close()

    def close(self) -> None:
        self._http.close()

    def login(self) -> None:
        response = self._http.post(
            "/api/auth/login",
            json={
                "username": self.settings.username,
                "password": self.settings.password,
            },
        )
        response.raise_for_status()
        self._csrf_token = response.headers.get("X-CSRF-Token") or response.cookies.get("TOKEN")

    def site_url(self, path: str) -> str:
        return f"/proxy/network/api/s/{self.settings.site}/{path.lstrip('/')}"

    def _integration_request(self, method: str, path: str, **kwargs: Any) -> Any:
        if method.upper() != "GET":
            raise RuntimeError("API-key mode currently supports read-only integration endpoints")
        url = urljoin("/", f"{INTEGRATION_API_PREFIX}/{path.lstrip('/')}")
        response = self._http.request(
            method,
            url,
            headers={"Accept": "application/json", "X-API-KEY": self.settings.api_key},
            **kwargs,
        )
        if response.status_code >= 400:
            raise RuntimeError(
                f"UniFi integration API returned HTTP {response.status_code} for {path}"
            )
        if not response.content:
            return None
        payload = response.json()
        if isinstance(payload, dict) and "data" in payload:
            return payload["data"]
        return payload

    def _integration_site(self) -> str:
        if self._integration_site_id:
            return self._integration_site_id
        configured_site = self.settings.site.strip().lower()
        sites = _as_list(self._integration_request("GET", "sites", params={"limit": 200}))
        for site in sites:
            site_id = str(site.get("id") or "")
            site_name = str(site.get("name") or "").strip().lower()
            if site_id == self.settings.site or site_name == configured_site:
                self._integration_site_id = site_id
                return site_id
        raise RuntimeError("configured UniFi integration site was not found")

    def _integration_site_path(self, resource: str) -> str:
        return f"sites/{self._integration_site()}/{resource.lstrip('/')}"

    def _integration_list(self, resource: str) -> list[dict[str, Any]]:
        return _as_list(self._integration_request("GET", resource, params={"limit": 200}))

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.settings.api_key:
            headers["X-API-Key"] = self.settings.api_key
        elif self._csrf_token:
            headers["X-CSRF-Token"] = self._csrf_token
        return headers

    def request(self, method: str, path: str, **kwargs: Any) -> Any:
        if self.settings.api_key:
            raise RuntimeError("API-key mode currently supports read-only integration endpoints")
        url = urljoin("/", path.lstrip("/"))
        response = self._http.request(method, url, headers=self._headers(), **kwargs)
        if response.status_code == 401 and not self.settings.api_key:
            self.login()
            response = self._http.request(method, url, headers=self._headers(), **kwargs)
        if response.status_code >= 400:
            raise RuntimeError(
                f"UniFi API returned HTTP {response.status_code} for {method} {path}"
            )
        if not response.content:
            return None
        payload = response.json()
        if isinstance(payload, dict):
            return payload.get("data", payload)
        return payload

    def get(self, path: str, **kwargs: Any) -> Any:
        return self.request("GET", path, **kwargs)

    def post(self, path: str, json: Any = None, **kwargs: Any) -> Any:
        return self.request("POST", path, json=json, **kwargs)

    def put(self, path: str, json: Any = None, **kwargs: Any) -> Any:
        return self.request("PUT", path, json=json, **kwargs)

    def delete(self, path: str, **kwargs: Any) -> Any:
        return self.request("DELETE", path, **kwargs)

    def networks(self) -> list[dict[str, Any]]:
        if self.settings.api_key:
            summaries = self._integration_list(self._integration_site_path("networks"))
            return [
                _integration_network(
                    summary,
                    self._integration_request(
                        "GET",
                        self._integration_site_path(f"networks/{summary.get('id')}"),
                    ),
                )
                for summary in summaries
                if summary.get("id")
            ]
        return self.get(self.site_url("rest/networkconf")) or []

    def wlans(self) -> list[dict[str, Any]]:
        if self.settings.api_key:
            return [
                _integration_wlan(item)
                for item in self._integration_list(self._integration_site_path("wifi/broadcasts"))
            ]
        return self.get(self.site_url("rest/wlanconf")) or []

    def devices(self) -> list[dict[str, Any]]:
        if self.settings.api_key:
            return [
                {
                    "_id": item.get("id"),
                    "id": item.get("id"),
                    "name": item.get("name"),
                    "hostname": item.get("name"),
                    "ip": item.get("ipAddress"),
                    "mac": item.get("macAddress"),
                    "model": item.get("model"),
                    "state": item.get("state"),
                }
                for item in self._integration_list(self._integration_site_path("devices"))
            ]
        return self.get(self.site_url("stat/device")) or []

    def clients(self) -> list[dict[str, Any]]:
        if self.settings.api_key:
            return [
                {
                    "_id": item.get("id"),
                    "id": item.get("id"),
                    "name": item.get("name"),
                    "ip": item.get("ipAddress"),
                    "mac": item.get("macAddress"),
                    "is_wired": str(item.get("type") or "").upper() == "WIRED",
                    "uplink_device_id": item.get("uplinkDeviceId"),
                    "connected_at": item.get("connectedAt"),
                }
                for item in self._integration_list(self._integration_site_path("clients"))
            ]
        return self.get(self.site_url("stat/sta")) or []

    def health(self) -> list[dict[str, Any]]:
        if self.settings.api_key:
            info = self._integration_request("GET", "info") or {}
            if not isinstance(info, dict):
                return []
            return [
                {
                    "subsystem": "application",
                    "status": "up",
                    "version": info.get("applicationVersion"),
                }
            ]
        return self.get(self.site_url("stat/health")) or []


class UniFiClient(LocalClassicAdapter):
    """Backward-compatible public name for :class:`LocalClassicAdapter`."""
