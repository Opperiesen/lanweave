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
from .dns import normalize_controller_dns_list
from .firewall import (
    normalize_controller_firewall_policy,
    normalize_controller_firewall_zone,
    normalize_controller_traffic_matching_list,
)
from .nat import normalize_controller_nat_list

INTEGRATION_API_PREFIX = "/proxy/network/integration/v1"
INTEGRATION_PAGE_SIZE = 200
INTEGRATION_MAX_PAGES = 1000


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
    elif security_type == "OPEN":
        security = "open"
    else:
        raise RuntimeError(
            f"UniFi integration API returned unsupported WiFi security type: {security_type}"
        )

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

    def _integration_response(self, method: str, path: str, **kwargs: Any) -> Any:
        normalized_path = path.rstrip("/")
        is_dns_policy_path = "/dns/policies" in normalized_path
        is_firewall_path = any(
            marker in normalized_path
            for marker in (
                "/firewall/zones",
                "/firewall/policies",
                "/traffic-matching-lists",
            )
        )
        if method.upper() != "GET" and not (is_dns_policy_path or is_firewall_path):
            raise RuntimeError(
                "API-key mode supports mutations only for supported DNS and firewall "
                "integration endpoints"
            )
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
        return response.json()

    def _integration_request(self, method: str, path: str, **kwargs: Any) -> Any:
        payload = self._integration_response(method, path, **kwargs)
        if isinstance(payload, dict) and "data" in payload:
            return payload["data"]
        return payload

    def _integration_site(self) -> str:
        if self._integration_site_id:
            return self._integration_site_id
        configured_site = self.settings.site.strip().lower()
        sites = self._integration_list("sites")
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
        items: list[dict[str, Any]] = []
        offset = 0
        for _page in range(INTEGRATION_MAX_PAGES):
            payload = self._integration_response(
                "GET",
                resource,
                params={"offset": offset, "limit": INTEGRATION_PAGE_SIZE},
            )
            if isinstance(payload, list):
                page = _as_list(payload)
                total_count: int | None = None
                page_limit = INTEGRATION_PAGE_SIZE
            elif isinstance(payload, dict):
                page = _as_list(payload.get("data"))
                total_count = payload.get("totalCount")
                page_limit = payload.get("limit", INTEGRATION_PAGE_SIZE)
                try:
                    total_count = int(total_count) if total_count is not None else None
                    page_limit = int(page_limit)
                except (TypeError, ValueError):
                    raise RuntimeError(
                        f"UniFi integration API returned invalid pagination metadata for {resource}"
                    ) from None
                if total_count is not None and total_count < 0:
                    raise RuntimeError(
                        f"UniFi integration API returned invalid pagination metadata for {resource}"
                    )
                if page_limit <= 0:
                    page_limit = INTEGRATION_PAGE_SIZE
            else:
                raise RuntimeError(
                    f"UniFi integration API returned an unexpected list response for {resource}"
                )

            items.extend(page)
            if not page:
                return items

            next_offset = offset + len(page)
            if total_count is not None and next_offset >= total_count:
                return items
            if total_count is None and len(page) < page_limit:
                return items
            if next_offset <= offset:
                raise RuntimeError(f"UniFi integration pagination did not advance for {resource}")
            offset = next_offset

        raise RuntimeError(f"UniFi integration pagination exceeded the safety limit for {resource}")

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

    def nat(self) -> list[dict[str, Any]]:
        """List supported port-forwarding mappings through local session auth."""
        if self.settings.api_key:
            raise RuntimeError("NAT inventory currently requires local session authentication")
        return normalize_controller_nat_list(self.get(self.site_url("rest/portforward")) or [])

    def dns(self) -> list[dict[str, Any]]:
        """List supported DNS policies through the official Integration API."""
        if not self.settings.api_key:
            raise RuntimeError("DNS policy support requires an Integration API key")
        return normalize_controller_dns_list(
            self._integration_list(self._integration_site_path("dns/policies"))
        )

    def create_dns(self, payload: dict[str, Any]) -> Any:
        """Create one DNS policy through the API-key-only Integration API."""
        if not self.settings.api_key:
            raise RuntimeError("DNS policy support requires an Integration API key")
        return self._integration_request(
            "POST",
            self._integration_site_path("dns/policies"),
            json=payload,
        )

    def update_dns(self, object_id: str, payload: dict[str, Any]) -> Any:
        """Update one DNS policy through the API-key-only Integration API."""
        if not self.settings.api_key:
            raise RuntimeError("DNS policy support requires an Integration API key")
        return self._integration_request(
            "PUT",
            self._integration_site_path(f"dns/policies/{object_id}"),
            json=payload,
        )

    def delete_dns(self, object_id: str) -> Any:
        """Delete one DNS policy through the API-key-only Integration API."""
        if not self.settings.api_key:
            raise RuntimeError("DNS policy support requires an Integration API key")
        return self._integration_request(
            "DELETE",
            self._integration_site_path(f"dns/policies/{object_id}"),
        )

    def firewall_zones(self) -> list[dict[str, Any]]:
        """List firewall zones through the official Integration API."""
        if not self.settings.api_key:
            raise RuntimeError("firewall support requires an Integration API key")
        return sorted(
            (
                normalize_controller_firewall_zone(value, f"controller.firewall.zones[{index}]")
                for index, value in enumerate(
                    self._integration_list(self._integration_site_path("firewall/zones"))
                )
            ),
            key=lambda item: (item["name"], item["id"]),
        )

    def firewall_traffic_matching_lists(self) -> list[dict[str, Any]]:
        """List address and port groups, fetching detail items when required."""
        if not self.settings.api_key:
            raise RuntimeError("firewall support requires an Integration API key")
        resource = self._integration_site_path("traffic-matching-lists")
        normalized: list[dict[str, Any]] = []
        for index, summary in enumerate(self._integration_list(resource)):
            identifier = summary.get("id") or summary.get("_id")
            detail = (
                self._integration_request("GET", f"{resource}/{identifier}")
                if identifier
                else summary
            )
            if not isinstance(detail, dict):
                detail = summary
            merged = {**summary, **detail}
            normalized.append(
                normalize_controller_traffic_matching_list(
                    merged, f"controller.firewall.traffic_matching_lists[{index}]"
                )
            )
        return sorted(normalized, key=lambda item: (item["name"], item["id"]))

    def firewall_policies(self) -> list[dict[str, Any]]:
        """List firewall policies without inferring order from controller indexes."""
        if not self.settings.api_key:
            raise RuntimeError("firewall support requires an Integration API key")
        policies = [
            normalize_controller_firewall_policy(value, f"controller.firewall.policies[{index}]")
            for index, value in enumerate(
                self._integration_list(self._integration_site_path("firewall/policies"))
            )
        ]
        return sorted(
            policies,
            key=lambda item: (
                item["source"]["zone_id"],
                item["destination"]["zone_id"],
                item["name"],
                item["id"],
            ),
        )

    def firewall_policy_ordering(
        self, source_zone_id: str, destination_zone_id: str
    ) -> dict[str, list[str]]:
        """Read user-defined order for one source/destination zone pair."""
        if not self.settings.api_key:
            raise RuntimeError("firewall support requires an Integration API key")
        payload = self._integration_request(
            "GET",
            self._integration_site_path("firewall/policies/ordering"),
            params={
                "sourceFirewallZoneId": source_zone_id,
                "destinationFirewallZoneId": destination_zone_id,
            },
        )
        if not isinstance(payload, dict):
            raise RuntimeError("UniFi integration API returned invalid firewall policy ordering")
        ordered = payload.get(
            "orderedFirewallPolicyIds", payload.get("ordered_firewall_policy_ids")
        )
        if not isinstance(ordered, dict):
            raise RuntimeError("UniFi integration API returned invalid firewall policy ordering")
        result: dict[str, list[str]] = {}
        for api_key, portable_key in (
            ("afterSystemDefined", "after_system_defined"),
            ("beforeSystemDefined", "before_system_defined"),
        ):
            values = ordered.get(api_key, ordered.get(portable_key, []))
            if not isinstance(values, list) or not all(isinstance(item, str) for item in values):
                raise RuntimeError(
                    "UniFi integration API returned invalid firewall policy ordering"
                )
            result[portable_key] = list(values)
        return result

    def create_firewall_zone(self, payload: dict[str, Any]) -> Any:
        if not self.settings.api_key:
            raise RuntimeError("firewall support requires an Integration API key")
        return self._integration_request(
            "POST", self._integration_site_path("firewall/zones"), json=payload
        )

    def update_firewall_zone(self, object_id: str, payload: dict[str, Any]) -> Any:
        if not self.settings.api_key:
            raise RuntimeError("firewall support requires an Integration API key")
        return self._integration_request(
            "PUT", self._integration_site_path(f"firewall/zones/{object_id}"), json=payload
        )

    def delete_firewall_zone(self, object_id: str) -> Any:
        if not self.settings.api_key:
            raise RuntimeError("firewall support requires an Integration API key")
        return self._integration_request(
            "DELETE", self._integration_site_path(f"firewall/zones/{object_id}")
        )

    def create_firewall_traffic_matching_list(self, payload: dict[str, Any]) -> Any:
        if not self.settings.api_key:
            raise RuntimeError("firewall support requires an Integration API key")
        return self._integration_request(
            "POST", self._integration_site_path("traffic-matching-lists"), json=payload
        )

    def update_firewall_traffic_matching_list(self, object_id: str, payload: dict[str, Any]) -> Any:
        if not self.settings.api_key:
            raise RuntimeError("firewall support requires an Integration API key")
        return self._integration_request(
            "PUT",
            self._integration_site_path(f"traffic-matching-lists/{object_id}"),
            json=payload,
        )

    def delete_firewall_traffic_matching_list(self, object_id: str) -> Any:
        if not self.settings.api_key:
            raise RuntimeError("firewall support requires an Integration API key")
        return self._integration_request(
            "DELETE", self._integration_site_path(f"traffic-matching-lists/{object_id}")
        )

    def create_firewall_policy(self, payload: dict[str, Any]) -> Any:
        if not self.settings.api_key:
            raise RuntimeError("firewall support requires an Integration API key")
        return self._integration_request(
            "POST", self._integration_site_path("firewall/policies"), json=payload
        )

    def update_firewall_policy(self, object_id: str, payload: dict[str, Any]) -> Any:
        if not self.settings.api_key:
            raise RuntimeError("firewall support requires an Integration API key")
        return self._integration_request(
            "PUT", self._integration_site_path(f"firewall/policies/{object_id}"), json=payload
        )

    def delete_firewall_policy(self, object_id: str) -> Any:
        if not self.settings.api_key:
            raise RuntimeError("firewall support requires an Integration API key")
        return self._integration_request(
            "DELETE", self._integration_site_path(f"firewall/policies/{object_id}")
        )

    def reorder_firewall_policies(
        self,
        source_zone_id: str,
        destination_zone_id: str,
        *,
        after_system_defined: list[str],
        before_system_defined: list[str],
    ) -> Any:
        if not self.settings.api_key:
            raise RuntimeError("firewall support requires an Integration API key")
        return self._integration_request(
            "PUT",
            self._integration_site_path("firewall/policies/ordering"),
            params={
                "sourceFirewallZoneId": source_zone_id,
                "destinationFirewallZoneId": destination_zone_id,
            },
            json={
                "orderedFirewallPolicyIds": {
                    "afterSystemDefined": after_system_defined,
                    "beforeSystemDefined": before_system_defined,
                }
            },
        )

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
