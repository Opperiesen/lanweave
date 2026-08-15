"""Export live controller state into the portable YAML model."""

from __future__ import annotations

import ipaddress
from typing import Any

import yaml

from .client import UniFiClient


def _network_subnet(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return str(ipaddress.ip_interface(value).network)
    except ValueError:
        return value


def network_from_unifi(network: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {
        "name": network.get("name"),
        "purpose": network.get("purpose", "corporate"),
        "subnet": _network_subnet(network.get("ip_subnet")),
        "vlan": int(network.get("vlan") or 1) if network.get("vlan_enabled") else 1,
    }
    if network.get("domain_name"):
        result["domain_name"] = network["domain_name"]
    if network.get("dhcpd_enabled"):
        dns = [
            network.get(f"dhcpd_dns_{index}")
            for index in range(1, 5)
            if network.get(f"dhcpd_dns_{index}")
        ]
        result["dhcp"] = {
            "enabled": True,
            "start": network.get("dhcpd_start"),
            "stop": network.get("dhcpd_stop"),
            "lease_time": network.get("dhcpd_leasetime"),
        }
        if dns:
            result["dhcp"]["dns"] = dns
    if network.get("ipv6_interface_type") not in (None, "none"):
        result["ipv6"] = {"enabled": True, "type": network["ipv6_interface_type"]}
    return {key: value for key, value in result.items() if value is not None}


def _password_env_name(name: str) -> str:
    normalized = "".join(character if character.isalnum() else "_" for character in name.upper())
    return f"WIFI_{normalized}_PASSWORD"


def wlan_from_unifi(wlan: dict[str, Any], networks_by_id: dict[str, str]) -> dict[str, Any]:
    bands = wlan.get("wlan_bands")
    if not bands:
        band = wlan.get("wlan_band", "both")
        bands = ["2g", "5g"] if band == "both" else [band]

    if wlan.get("wpa3_support"):
        security = "wpa3-transition" if wlan.get("wpa3_transition") else "wpa3"
    else:
        security = {"open": "open", "wpapsk": "wpa2"}.get(wlan.get("security"), "open")

    name = wlan.get("name", "Unnamed")
    result: dict[str, Any] = {
        "name": name,
        "ssid": name,
        "network": networks_by_id.get(wlan.get("networkconf_id", ""), "Default"),
        "bands": bands,
        "security": security,
        "hide_ssid": wlan.get("hide_ssid", False),
        "fast_roaming": wlan.get("fast_roaming_enabled", False),
        "proxy_arp": wlan.get("proxy_arp", False),
        "pmf": wlan.get("pmf_mode", "optional"),
        "client_isolation": wlan.get("l2_isolation", False),
    }
    if security != "open":
        result["password_env"] = _password_env_name(name)
    return {key: value for key, value in result.items() if value is not None}


def export_config(client: UniFiClient) -> dict[str, Any]:
    """Read networks/WLANs and return a secret-free portable configuration."""
    networks = client.networks()
    wlans = client.wlans()
    networks_by_id = {
        str(network.get("_id") or network.get("id")): network["name"]
        for network in networks
        if network.get("name") and (network.get("_id") or network.get("id"))
    }
    return {
        "version": 1,
        "controller": {"site": client.settings.site},
        "networks": [
            network_from_unifi(network)
            for network in networks
            if network.get("purpose") != "wan"
        ],
        "wlans": [wlan_from_unifi(wlan, networks_by_id) for wlan in wlans],
    }


def export_yaml(client: UniFiClient) -> str:
    return yaml.safe_dump(
        export_config(client),
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
    )
