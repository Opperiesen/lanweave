"""Export live controller state into the portable YAML model."""

from __future__ import annotations

import ipaddress
from collections.abc import Sequence
from typing import Any

import yaml

from .adapters import Adapter
from .contracts import CONFIG_SCHEMA_VERSION
from .dns import dns_export_record, dns_is_user_managed
from .firewall import export_firewall_config
from .nat import nat_export_mapping, nat_is_user_managed
from .vpn import inventory_to_export

EXPORT_RESOURCE_ORDER = ("networks", "wlans", "dns", "firewall", "nat", "vpn")


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
        "enabled": wlan.get("enabled", True),
        "hide_ssid": wlan.get("hide_ssid", False),
        "fast_roaming": wlan.get("fast_roaming_enabled", False),
        "proxy_arp": wlan.get("proxy_arp", False),
        "pmf": wlan.get("pmf_mode", "optional"),
        "client_isolation": wlan.get("l2_isolation", False),
        "multicast_enhancement": wlan.get("mcastenhance_enabled", False),
        "schedule_enabled": wlan.get("schedule_enabled", False),
    }
    if security != "open":
        result["password_env"] = _password_env_name(name)
    return {key: value for key, value in result.items() if value is not None}


def export_config(
    client: Adapter,
    *,
    resources: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Read selected resources and return a secret-free portable configuration.

    A selective export still reads the network inventory when a selected
    resource needs controller network IDs to become portable (WLANs and
    firewall policies). The returned document contains only the requested
    resource families, which keeps post-apply verification independent from
    unrelated controller endpoints.
    """
    requested = set(EXPORT_RESOURCE_ORDER if resources is None else resources)
    unknown = requested - set(EXPORT_RESOURCE_ORDER)
    if unknown:
        names = ", ".join(sorted(unknown))
        raise ValueError(f"unsupported export resource(s): {names}")

    needs_networks = bool(requested & {"networks", "wlans", "firewall"})
    networks = client.networks() if needs_networks else []
    wlans = client.wlans() if "wlans" in requested else []
    networks_by_id = {
        str(network.get("_id") or network.get("id")): network["name"]
        for network in networks
        if network.get("name") and (network.get("_id") or network.get("id"))
    }
    result: dict[str, Any] = {
        "version": CONFIG_SCHEMA_VERSION,
        "controller": {"site": client.settings.site},
    }
    if "networks" in requested:
        result["networks"] = [
            network_from_unifi(network) for network in networks if network.get("purpose") != "wan"
        ]
    if "wlans" in requested:
        result["wlans"] = [wlan_from_unifi(wlan, networks_by_id) for wlan in wlans]

    capabilities = getattr(client, "capabilities", None)
    if "dns" in requested:
        supports_dns = (
            capabilities.supports("dns", "export")
            if capabilities is not None
            else callable(getattr(client, "dns", None))
        )
        if supports_dns:
            result["dns"] = [
                dns_export_record(record) for record in client.dns() if dns_is_user_managed(record)
            ]
    if "firewall" in requested:
        supports_firewall = (
            capabilities.supports("firewall", "export")
            if capabilities is not None
            else callable(getattr(client, "firewall_zones", None))
        )
        if supports_firewall:
            firewall_zones = client.firewall_zones()
            firewall_groups = client.firewall_traffic_matching_lists()
            firewall_policies = client.firewall_policies()
            orderings: dict[tuple[str, str], dict[str, list[str]]] = {}
            for policy in firewall_policies:
                pair = (policy["source"]["zone_id"], policy["destination"]["zone_id"])
                if pair not in orderings:
                    orderings[pair] = client.firewall_policy_ordering(*pair)
            result["firewall"] = export_firewall_config(
                zones=firewall_zones,
                groups=firewall_groups,
                policies=firewall_policies,
                orderings=orderings,
                network_names_by_id=networks_by_id,
            )
    if "nat" in requested:
        supports_nat = (
            capabilities.supports("nat", "export")
            if capabilities is not None
            else callable(getattr(client, "nat", None))
        )
        if supports_nat:
            result["nat"] = [
                nat_export_mapping(mapping)
                for mapping in client.nat()
                if nat_is_user_managed(mapping)
            ]
    if "vpn" in requested:
        supports_vpn = (
            capabilities.supports("vpn", "export")
            if capabilities is not None
            else callable(getattr(client, "vpn", None))
        )
        if supports_vpn:
            result["vpn"] = inventory_to_export(client.vpn())
    return result


def export_yaml(client: Adapter) -> str:
    return yaml.safe_dump(
        export_config(client),
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
    )
