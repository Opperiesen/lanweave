"""Portable, secret-free VPN contracts and controller normalization."""

from __future__ import annotations

import ipaddress
import re
from collections.abc import Iterable, Mapping
from typing import Any

VPN_KEYS = {"servers", "site_to_site_tunnels", "routes"}
VPN_SERVER_KEYS = {"name", "type", "enabled"}
VPN_TUNNEL_KEYS = {"name", "type", "enabled"}
VPN_ROUTE_KEYS = {"name", "destination", "via", "enabled", "metric"}
_NAME_RE = re.compile(r"^[^\r\n/\\]{1,128}$")
_TYPE_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")


class VpnError(ValueError):
    """Raised when a portable VPN document is invalid."""


class UnsupportedVpnVariantError(VpnError):
    """Raised when a controller VPN response is outside the supported subset."""


def _mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise VpnError(f"{label} must be a mapping")
    return value


def _non_empty_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise VpnError(f"{label} must be a non-empty string")
    return value.strip()


def _name(value: Any, label: str) -> str:
    result = _non_empty_string(value, label)
    if not _NAME_RE.fullmatch(result):
        raise VpnError(f"{label} contains unsupported characters")
    return result


def _vpn_type(value: Any, label: str) -> str:
    result = _non_empty_string(value, label)
    if not _TYPE_RE.fullmatch(result):
        raise VpnError(f"{label} contains an invalid VPN type")
    return result.upper()


def _reject_unknown(mapping: Mapping[str, Any], allowed: set[str], label: str) -> None:
    unknown = sorted(set(mapping) - allowed, key=str)
    if unknown:
        raise VpnError(f"unsupported field(s) in {label}: {', '.join(map(str, unknown))}")


def _bool_if_present(mapping: Mapping[str, Any], key: str, label: str) -> None:
    if key in mapping and not isinstance(mapping[key], bool):
        raise VpnError(f"{label}.{key} must be a boolean")


def _unique_names(items: Iterable[Mapping[str, Any]], label: str) -> set[str]:
    names: set[str] = set()
    for item in items:
        name = str(item["name"])
        if name in names:
            raise VpnError(f"duplicate VPN name in {label}: {name}")
        names.add(name)
    return names


def _validate_vpn_item(
    raw: Any,
    *,
    index: int,
    label: str,
    allowed: set[str],
) -> dict[str, Any]:
    item = _mapping(raw, f"{label}[{index}]")
    item_label = f"{label}[{index}]"
    _reject_unknown(item, allowed, item_label)
    normalized = {
        "name": _name(item.get("name"), f"{item_label}.name"),
        "type": _vpn_type(item.get("type"), f"{item_label}.type"),
    }
    if "enabled" in item:
        _bool_if_present(item, "enabled", item_label)
        normalized["enabled"] = item["enabled"]
    return normalized


def _validate_route(raw: Any, index: int) -> dict[str, Any]:
    label = f"vpn.routes[{index}]"
    route = _mapping(raw, label)
    _reject_unknown(route, VPN_ROUTE_KEYS, label)
    normalized = {"name": _name(route.get("name"), f"{label}.name")}
    destination = _non_empty_string(route.get("destination"), f"{label}.destination")
    try:
        normalized["destination"] = str(ipaddress.ip_network(destination, strict=False))
    except ValueError as exc:
        raise VpnError(f"{label}.destination must be an IP network in CIDR notation") from exc
    if "via" in route:
        normalized["via"] = _name(route["via"], f"{label}.via")
    if "enabled" in route:
        _bool_if_present(route, "enabled", label)
        normalized["enabled"] = route["enabled"]
    if "metric" in route:
        metric = route["metric"]
        if isinstance(metric, bool) or not isinstance(metric, int) or metric <= 0:
            raise VpnError(f"{label}.metric must be a positive integer")
        normalized["metric"] = metric
    return normalized


def validate_vpn(value: Any, *, network_names: Iterable[str] = ()) -> dict[str, Any]:
    """Validate the additive v1 VPN section and its route dependencies.

    The section is intentionally declarative but read-only in v0.7.0.  It
    contains only public overview fields and route intent; private keys,
    generated profiles, preshared keys and controller object identifiers are
    outside this contract.
    """
    if value is None:
        return {"servers": [], "site_to_site_tunnels": [], "routes": []}
    vpn = _mapping(value, "vpn")
    _reject_unknown(vpn, VPN_KEYS, "vpn")
    servers = [
        _validate_vpn_item(
            raw,
            index=index,
            label="vpn.servers",
            allowed=VPN_SERVER_KEYS,
        )
        for index, raw in enumerate(vpn.get("servers", []))
    ]
    tunnels = [
        _validate_vpn_item(
            raw,
            index=index,
            label="vpn.site_to_site_tunnels",
            allowed=VPN_TUNNEL_KEYS,
        )
        for index, raw in enumerate(vpn.get("site_to_site_tunnels", []))
    ]
    for key, items in (
        ("servers", servers),
        ("site_to_site_tunnels", tunnels),
    ):
        if not isinstance(vpn.get(key, []), list):
            raise VpnError(f"vpn.{key} must be a list")
        _unique_names(items, f"vpn.{key}")

    all_names = _unique_names([*servers, *tunnels], "vpn resources")
    routes_raw = vpn.get("routes", [])
    if not isinstance(routes_raw, list):
        raise VpnError("vpn.routes must be a list")
    routes = [_validate_route(raw, index) for index, raw in enumerate(routes_raw)]
    _unique_names(routes, "vpn.routes")
    for index, route in enumerate(routes):
        via = route.get("via")
        if via is not None and via not in all_names:
            raise VpnError(f"vpn.routes[{index}].via refers to an unknown VPN resource: {via}")

    # Keep the argument part of the public function contract.  A future route
    # validator can use LAN network names without changing its call sites.
    set(network_names)
    return {
        "servers": servers,
        "site_to_site_tunnels": tunnels,
        "routes": routes,
    }


def _controller_identifier(value: Mapping[str, Any], label: str) -> str:
    identifier = value.get("id") or value.get("_id")
    if not isinstance(identifier, str) or not identifier.strip():
        raise UnsupportedVpnVariantError(f"{label} has no stable controller id")
    return identifier.strip()


def normalize_controller_vpn_server(value: Any, label: str = "vpn.server") -> dict[str, Any]:
    """Normalize the documented Integration API VPN server overview."""
    item = _mapping(value, label)
    identifier = _controller_identifier(item, label)
    name = _non_empty_string(item.get("name"), f"{label}.name")
    vpn_type = _vpn_type(item.get("type"), f"{label}.type")
    enabled = item.get("enabled", True)
    if not isinstance(enabled, bool):
        raise UnsupportedVpnVariantError(f"{label}.enabled is not boolean")
    result: dict[str, Any] = {
        "id": identifier,
        "_id": identifier,
        "name": name,
        "type": vpn_type,
        "enabled": enabled,
    }
    metadata = item.get("metadata")
    if isinstance(metadata, dict):
        for key in ("origin", "source"):
            if isinstance(metadata.get(key), str) and metadata[key].strip():
                result[key] = metadata[key].strip()
    return result


def normalize_controller_vpn_tunnel(
    value: Any, label: str = "vpn.site_to_site_tunnel"
) -> dict[str, Any]:
    """Normalize the documented Integration API site-to-site overview."""
    item = _mapping(value, label)
    identifier = _controller_identifier(item, label)
    name = _non_empty_string(item.get("name"), f"{label}.name")
    vpn_type = _vpn_type(item.get("type"), f"{label}.type")
    result: dict[str, Any] = {
        "id": identifier,
        "_id": identifier,
        "name": name,
        "type": vpn_type,
    }
    metadata = item.get("metadata")
    if isinstance(metadata, dict):
        for key in ("origin", "source"):
            if isinstance(metadata.get(key), str) and metadata[key].strip():
                result[key] = metadata[key].strip()
    if "enabled" in item:
        if not isinstance(item["enabled"], bool):
            raise UnsupportedVpnVariantError(f"{label}.enabled is not boolean")
        result["enabled"] = item["enabled"]
    return result


def normalize_controller_vpn_peer(value: Any, label: str = "vpn.peer") -> dict[str, Any]:
    """Keep only non-secret connected VPN client fields."""
    item = _mapping(value, label)
    identifier = _controller_identifier(item, label)
    client_type = _non_empty_string(item.get("type"), f"{label}.type").upper()
    if client_type not in {"VPN", "TELEPORT"}:
        raise UnsupportedVpnVariantError(f"{label}.type is not a VPN client type")
    result: dict[str, Any] = {
        "id": identifier,
        "name": _non_empty_string(item.get("name") or identifier, f"{label}.name"),
        "type": client_type,
    }
    for source_key, target_key in (
        ("ipAddress", "ip_address"),
        ("macAddress", "mac_address"),
        ("connectedAt", "connected_at"),
        ("uplinkDeviceId", "uplink_device_id"),
    ):
        if isinstance(item.get(source_key), str) and item[source_key].strip():
            result[target_key] = item[source_key].strip()
    return result


def inventory_to_export(inventory: Mapping[str, Any]) -> dict[str, Any]:
    """Convert normalized live VPN state to the portable, ID-free section."""
    servers = [
        {key: value for key, value in item.items() if key in {"name", "type", "enabled"}}
        for item in inventory.get("servers", [])
    ]
    tunnels = [
        {key: value for key, value in item.items() if key in {"name", "type", "enabled"}}
        for item in inventory.get("site_to_site_tunnels", [])
    ]
    return {
        "servers": sorted(servers, key=lambda item: item["name"]),
        "site_to_site_tunnels": sorted(tunnels, key=lambda item: item["name"]),
        # Routes are not returned by the documented overview endpoints.  Do
        # not infer them from a server or emit a guessed default route.
        "routes": [],
    }


def health_from_inventory(inventory: Mapping[str, Any]) -> dict[str, Any]:
    """Return honest VPN health: inventory status, not handshake telemetry."""
    servers = list(inventory.get("servers", []))
    tunnels = list(inventory.get("site_to_site_tunnels", []))
    peers = list(inventory.get("peers", []))
    configured = bool(servers or tunnels)
    return {
        "subsystem": "vpn",
        "status": "inventory-only" if configured else "not-configured",
        "servers": len(servers),
        "enabled_servers": sum(item.get("enabled", True) is True for item in servers),
        "site_to_site_tunnels": len(tunnels),
        "connected_peers": len(peers),
        "routes_reported": len(inventory.get("routes", [])),
        "coverage": {
            "servers": "reported",
            "site_to_site_tunnels": "reported",
            "peers": "connected-clients",
            "routes": "not-reported-by-official-overview-api",
        },
    }


def plan_observation(desired: Mapping[str, Any], inventory: Mapping[str, Any]) -> dict[str, Any]:
    """Build the non-mutating VPN section carried by a plan v1 document."""
    observed = inventory_to_export(inventory)
    checks: list[dict[str, str]] = []
    for resource in ("servers", "site_to_site_tunnels", "routes"):
        desired_items = {
            str(item["name"]): item for item in desired.get(resource, []) if item.get("name")
        }
        observed_items = {
            str(item["name"]): item for item in observed.get(resource, []) if item.get("name")
        }
        for name in sorted(set(desired_items) | set(observed_items)):
            expected = desired_items.get(name)
            actual = observed_items.get(name)
            if expected is None:
                state = "observed-only"
            elif actual is None:
                state = "missing-from-overview"
            elif expected == actual:
                state = "matches-overview"
            else:
                state = "differs-from-overview"
            checks.append({"resource": resource, "name": name, "state": state})
    return {
        "resource": "vpn",
        "mode": "read-only",
        "apply_supported": False,
        "desired": dict(desired),
        "observed": observed,
        "health": health_from_inventory(inventory),
        "checks": checks,
    }


__all__ = [
    "VPN_KEYS",
    "VPN_ROUTE_KEYS",
    "VPN_SERVER_KEYS",
    "VPN_TUNNEL_KEYS",
    "UnsupportedVpnVariantError",
    "VpnError",
    "health_from_inventory",
    "inventory_to_export",
    "normalize_controller_vpn_peer",
    "normalize_controller_vpn_server",
    "normalize_controller_vpn_tunnel",
    "plan_observation",
    "validate_vpn",
]
