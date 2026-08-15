"""Export live controller state into the portable YAML model."""

from __future__ import annotations

import ipaddress
from typing import Any

import yaml

from .adapters import Adapter
from .contracts import CONFIG_SCHEMA_VERSION
from .dns import dns_export_record, dns_is_user_managed
from .firewall import export_firewall_config


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


def export_config(client: Adapter) -> dict[str, Any]:
    """Read networks/WLANs and return a secret-free portable configuration."""
    networks = client.networks()
    wlans = client.wlans()
    networks_by_id = {
        str(network.get("_id") or network.get("id")): network["name"]
        for network in networks
        if network.get("name") and (network.get("_id") or network.get("id"))
    }
    capabilities = getattr(client, "capabilities", None)
    supports_dns = (
        capabilities.supports("dns", "export")
        if capabilities is not None
        else callable(getattr(client, "dns", None))
    )
    dns_records: list[dict[str, Any]] = []
    if supports_dns:
        dns_records = [
            dns_export_record(record) for record in client.dns() if dns_is_user_managed(record)
        ]
    supports_firewall = (
        capabilities.supports("firewall", "export")
        if capabilities is not None
        else callable(getattr(client, "firewall_zones", None))
    )
    firewall_config = {"zones": [], "address_groups": [], "port_groups": [], "rules": []}
    if supports_firewall:
        firewall_zones = client.firewall_zones()
        firewall_groups = client.firewall_traffic_matching_lists()
        firewall_policies = client.firewall_policies()
        orderings: dict[tuple[str, str], dict[str, list[str]]] = {}
        for policy in firewall_policies:
            pair = (policy["source"]["zone_id"], policy["destination"]["zone_id"])
            if pair not in orderings:
                orderings[pair] = client.firewall_policy_ordering(*pair)
        firewall_config = export_firewall_config(
            zones=firewall_zones,
            groups=firewall_groups,
            policies=firewall_policies,
            orderings=orderings,
            network_names_by_id=networks_by_id,
        )
    return {
        "version": CONFIG_SCHEMA_VERSION,
        "controller": {"site": client.settings.site},
        "networks": [
            network_from_unifi(network) for network in networks if network.get("purpose") != "wan"
        ],
        "wlans": [wlan_from_unifi(wlan, networks_by_id) for wlan in wlans],
        "dns": dns_records,
        "firewall": firewall_config,
    }


def export_yaml(client: Adapter) -> str:
    return yaml.safe_dump(
        export_config(client),
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
    )
