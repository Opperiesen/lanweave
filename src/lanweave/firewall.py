"""Portable firewall contract and validation helpers.

The public configuration deliberately uses names and network references. UniFi
object IDs and Integration API payloads stay in the adapter/planner boundary.
"""

from __future__ import annotations

import ipaddress
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

FIREWALL_KEYS = {"zones", "address_groups", "port_groups", "rules"}
ZONE_KEYS = {"name", "networks"}
ADDRESS_GROUP_KEYS = {"name", "addresses"}
PORT_GROUP_KEYS = {"name", "ports"}
RULE_KEYS = {
    "name",
    "order",
    "source",
    "destination",
    "action",
    "enabled",
    "ip_version",
    "protocol",
    "protocol_number",
    "connection_states",
    "ipsec",
    "logging",
    "allow_return_traffic",
    "description",
}
SIDE_KEYS = {
    "zone",
    "networks",
    "address_group",
    "port_group",
    "match_opposite",
    "port_match_opposite",
}

SUPPORTED_ACTIONS = {"ALLOW", "BLOCK", "REJECT"}
SUPPORTED_IP_VERSIONS = {"IPV4", "IPV4_AND_IPV6", "IPV6"}
SUPPORTED_CONNECTION_STATES = {"NEW", "INVALID", "ESTABLISHED", "RELATED"}
SUPPORTED_IPSEC = {"MATCH_ENCRYPTED", "MATCH_NOT_ENCRYPTED"}

# This is the named-protocol subset exposed by the first portable contract.
# Protocol numbers remain available for less common protocols.
SUPPORTED_PROTOCOLS = {
    "AH",
    "DCCP",
    "ESP",
    "GRE",
    "ICMP",
    "ICMPV6",
    "IGMP",
    "IP",
    "IPCOMP",
    "IPENCAP",
    "IPIP",
    "L2TP",
    "OSPF",
    "PIM",
    "SCTP",
    "TCP",
    "TCP_UDP",
    "UDP",
    "UDPLITE",
    "VRRP",
}


class FirewallError(ValueError):
    """Raised when portable firewall state is malformed or unsafe."""


def _mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise FirewallError(f"{label} must be a mapping")
    return dict(value)


def _string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise FirewallError(f"{label} must be a non-empty string")
    return value.strip()


def _reject_unknown(mapping: Mapping[str, Any], allowed: set[str], label: str) -> None:
    unknown = sorted(set(mapping) - allowed, key=str)
    if unknown:
        raise FirewallError(f"unsupported field(s) in {label}: {', '.join(map(str, unknown))}")


def _unique_strings(values: Any, label: str, *, allow_empty: bool = False) -> list[str]:
    if not isinstance(values, list):
        raise FirewallError(f"{label} must be a list of strings")
    result: list[str] = []
    for index, value in enumerate(values):
        item = _string(value, f"{label}[{index}]")
        if item in result:
            raise FirewallError(f"duplicate value in {label}: {item}")
        result.append(item)
    if not allow_empty and not result:
        raise FirewallError(f"{label} must not be empty")
    return result


def _canonical_ip(value: str, label: str) -> tuple[int, str, str]:
    """Return IP family, canonical value and matching kind."""
    try:
        if "/" in value:
            network = ipaddress.ip_network(value, strict=False)
            return network.version, str(network), "SUBNET"
        address = ipaddress.ip_address(value)
        return address.version, str(address), "IP_ADDRESS"
    except ValueError as exc:
        raise FirewallError(f"{label} must be an IP address or CIDR subnet") from exc


def normalize_address_item(value: Any, label: str = "address") -> dict[str, Any]:
    """Normalize one portable address/group item to an API-neutral shape."""
    if isinstance(value, str):
        family, canonical, match_type = _canonical_ip(value.strip(), label)
        return {"type": match_type, "value": canonical, "family": family}
    item = _mapping(value, label)
    _reject_unknown(item, {"start", "stop"}, label)
    start = _string(item.get("start"), f"{label}.start")
    stop = _string(item.get("stop"), f"{label}.stop")
    try:
        start_ip = ipaddress.ip_address(start)
        stop_ip = ipaddress.ip_address(stop)
    except ValueError as exc:
        raise FirewallError(f"{label}.start and stop must be IP addresses") from exc
    if start_ip.version != stop_ip.version:
        raise FirewallError(f"{label}.start and stop must use the same IP version")
    if int(start_ip) > int(stop_ip):
        raise FirewallError(f"{label}.start must not be after stop")
    return {
        "type": "IP_ADDRESS_RANGE",
        "start": str(start_ip),
        "stop": str(stop_ip),
        "family": start_ip.version,
    }


def normalize_address_items(
    values: Sequence[Any], label: str = "addresses"
) -> list[dict[str, Any]]:
    result = [
        normalize_address_item(value, f"{label}[{index}]") for index, value in enumerate(values)
    ]
    if not result:
        raise FirewallError(f"{label} must not be empty")
    fingerprints = {tuple(sorted(item.items())) for item in result}
    if len(fingerprints) != len(result):
        raise FirewallError(f"{label} must not contain duplicate values")
    families = {item["family"] for item in result}
    if len(families) != 1:
        raise FirewallError(f"{label} must use one IP version")
    return result


def normalize_port_item(value: Any, label: str = "port") -> dict[str, Any]:
    if isinstance(value, bool):
        raise FirewallError(f"{label} must be a port number or range")
    if isinstance(value, int):
        if not 1 <= value <= 65535:
            raise FirewallError(f"{label} must be between 1 and 65535")
        return {"type": "PORT_NUMBER", "value": value}
    item = _mapping(value, label)
    _reject_unknown(item, {"start", "stop"}, label)
    start = item.get("start")
    stop = item.get("stop")
    if any(isinstance(port, bool) or not isinstance(port, int) for port in (start, stop)):
        raise FirewallError(f"{label}.start and stop must be port numbers")
    if not 1 <= start <= 65535 or not 1 <= stop <= 65535:
        raise FirewallError(f"{label}.start and stop must be between 1 and 65535")
    if start > stop:
        raise FirewallError(f"{label}.start must not be after stop")
    return {"type": "PORT_NUMBER_RANGE", "start": start, "stop": stop}


def normalize_port_items(values: Sequence[Any], label: str = "ports") -> list[dict[str, Any]]:
    result = [normalize_port_item(value, f"{label}[{index}]") for index, value in enumerate(values)]
    if not result:
        raise FirewallError(f"{label} must not be empty")
    fingerprints = {tuple(sorted(item.items())) for item in result}
    if len(fingerprints) != len(result):
        raise FirewallError(f"{label} must not contain duplicate values")
    return result


def _portable_address_item(item: dict[str, Any]) -> str | dict[str, str]:
    if item["type"] in {"IP_ADDRESS", "SUBNET"}:
        return item["value"]
    return {"start": item["start"], "stop": item["stop"]}


def _portable_port_item(item: dict[str, Any]) -> int | dict[str, int]:
    if item["type"] == "PORT_NUMBER":
        return item["value"]
    return {"start": item["start"], "stop": item["stop"]}


def _validate_zone(value: Any, index: int, network_names: set[str] | None) -> dict[str, Any]:
    label = f"firewall.zones[{index}]"
    zone = _mapping(value, label)
    _reject_unknown(zone, ZONE_KEYS, label)
    name = _string(zone.get("name"), f"{label}.name")
    networks = _unique_strings(zone.get("networks", []), f"{label}.networks", allow_empty=True)
    if network_names is not None:
        unknown = sorted(set(networks) - network_names)
        if unknown:
            raise FirewallError(
                f"{label}.networks refers to unknown network(s): {', '.join(unknown)}"
            )
    return {"name": name, "networks": networks}


def _validate_address_group(value: Any, index: int) -> dict[str, Any]:
    label = f"firewall.address_groups[{index}]"
    group = _mapping(value, label)
    _reject_unknown(group, ADDRESS_GROUP_KEYS, label)
    name = _string(group.get("name"), f"{label}.name")
    addresses = group.get("addresses")
    if not isinstance(addresses, list):
        raise FirewallError(f"{label}.addresses must be a non-empty list")
    normalized = normalize_address_items(addresses, f"{label}.addresses")
    return {"name": name, "addresses": [_portable_address_item(item) for item in normalized]}


def _validate_port_group(value: Any, index: int) -> dict[str, Any]:
    label = f"firewall.port_groups[{index}]"
    group = _mapping(value, label)
    _reject_unknown(group, PORT_GROUP_KEYS, label)
    name = _string(group.get("name"), f"{label}.name")
    ports = group.get("ports")
    if not isinstance(ports, list):
        raise FirewallError(f"{label}.ports must be a non-empty list")
    normalized = normalize_port_items(ports, f"{label}.ports")
    return {"name": name, "ports": [_portable_port_item(item) for item in normalized]}


def _validate_side(
    value: Any,
    label: str,
    *,
    network_names: set[str] | None,
    address_group_names: set[str],
    port_group_names: set[str],
) -> dict[str, Any]:
    side = _mapping(value, label)
    _reject_unknown(side, SIDE_KEYS, label)
    zone = _string(side.get("zone"), f"{label}.zone")
    # A rule may target a system-defined zone that is absent from the desired
    # custom-zone list. The live inventory resolves that reference later.

    networks = side.get("networks")
    normalized_networks: list[str] | None = None
    if networks is not None:
        normalized_networks = _unique_strings(networks, f"{label}.networks")
        if network_names is not None:
            unknown = sorted(set(normalized_networks) - network_names)
            if unknown:
                raise FirewallError(
                    f"{label}.networks refers to unknown network(s): {', '.join(unknown)}"
                )

    address_group = side.get("address_group")
    if address_group is not None:
        address_group = _string(address_group, f"{label}.address_group")
        if address_group not in address_group_names:
            raise FirewallError(f"{label}.address_group refers to an unknown address group")
    if normalized_networks is not None and address_group is not None:
        raise FirewallError(f"{label} must not define both networks and address_group")

    port_group = side.get("port_group")
    if port_group is not None:
        port_group = _string(port_group, f"{label}.port_group")
        if port_group not in port_group_names:
            raise FirewallError(f"{label}.port_group refers to an unknown port group")

    match_opposite = side.get("match_opposite", False)
    if not isinstance(match_opposite, bool):
        raise FirewallError(f"{label}.match_opposite must be a boolean")
    if match_opposite and normalized_networks is None and address_group is None:
        raise FirewallError(f"{label}.match_opposite requires networks or address_group")

    port_match_opposite = side.get("port_match_opposite", False)
    if not isinstance(port_match_opposite, bool):
        raise FirewallError(f"{label}.port_match_opposite must be a boolean")
    if port_match_opposite and port_group is None:
        raise FirewallError(f"{label}.port_match_opposite requires port_group")

    result: dict[str, Any] = {"zone": zone}
    if normalized_networks is not None:
        result["networks"] = normalized_networks
    if address_group is not None:
        result["address_group"] = address_group
    if port_group is not None:
        result["port_group"] = port_group
    if match_opposite:
        result["match_opposite"] = True
    if port_match_opposite:
        result["port_match_opposite"] = True
    return result


def _validate_rule(
    value: Any,
    index: int,
    *,
    network_names: set[str] | None,
    address_group_names: set[str],
    port_group_names: set[str],
) -> dict[str, Any]:
    label = f"firewall.rules[{index}]"
    rule = _mapping(value, label)
    _reject_unknown(rule, RULE_KEYS, label)
    name = _string(rule.get("name"), f"{label}.name")
    order = rule.get("order")
    if isinstance(order, bool) or not isinstance(order, int) or order < 0:
        raise FirewallError(f"{label}.order must be a non-negative integer")
    source = _validate_side(
        rule.get("source"),
        f"{label}.source",
        network_names=network_names,
        address_group_names=address_group_names,
        port_group_names=port_group_names,
    )
    destination = _validate_side(
        rule.get("destination"),
        f"{label}.destination",
        network_names=network_names,
        address_group_names=address_group_names,
        port_group_names=port_group_names,
    )

    action = _string(rule.get("action"), f"{label}.action").upper()
    if action not in SUPPORTED_ACTIONS:
        raise FirewallError(
            f"{label}.action must be one of: {', '.join(sorted(SUPPORTED_ACTIONS))}"
        )

    enabled = rule.get("enabled", True)
    if not isinstance(enabled, bool):
        raise FirewallError(f"{label}.enabled must be a boolean")
    ip_version = str(rule.get("ip_version", "IPV4_AND_IPV6")).upper()
    if ip_version not in SUPPORTED_IP_VERSIONS:
        raise FirewallError(
            f"{label}.ip_version must be one of: {', '.join(sorted(SUPPORTED_IP_VERSIONS))}"
        )

    protocol = rule.get("protocol")
    protocol_number = rule.get("protocol_number")
    if protocol is not None and protocol_number is not None:
        raise FirewallError(f"{label} must define either protocol or protocol_number, not both")
    if protocol is not None:
        protocol = _string(protocol, f"{label}.protocol").upper()
        if protocol not in SUPPORTED_PROTOCOLS:
            raise FirewallError(f"{label}.protocol is not supported: {protocol}")
    if protocol_number is not None and (
        isinstance(protocol_number, bool)
        or not isinstance(protocol_number, int)
        or not 0 <= protocol_number <= 255
    ):
        raise FirewallError(f"{label}.protocol_number must be an integer between 0 and 255")

    states = rule.get("connection_states")
    normalized_states: list[str] | None = None
    if states is not None:
        if not isinstance(states, list) or not states:
            raise FirewallError(f"{label}.connection_states must be a non-empty list")
        normalized_states = []
        for state in states:
            normalized_state = _string(state, f"{label}.connection_states").upper()
            if normalized_state not in SUPPORTED_CONNECTION_STATES:
                raise FirewallError(f"{label}.connection_states contains unsupported state")
            if normalized_state in normalized_states:
                raise FirewallError(f"duplicate connection state in {label}.connection_states")
            normalized_states.append(normalized_state)

    ipsec = rule.get("ipsec")
    if ipsec is not None:
        ipsec = _string(ipsec, f"{label}.ipsec").upper()
        if ipsec not in SUPPORTED_IPSEC:
            raise FirewallError(f"{label}.ipsec contains an unsupported value")

    logging = rule.get("logging", False)
    allow_return_traffic = rule.get("allow_return_traffic", False)
    for key, flag in (("logging", logging), ("allow_return_traffic", allow_return_traffic)):
        if not isinstance(flag, bool):
            raise FirewallError(f"{label}.{key} must be a boolean")
    description = rule.get("description")
    if description is not None:
        description = _string(description, f"{label}.description")

    normalized: dict[str, Any] = {
        "name": name,
        "order": order,
        "source": source,
        "destination": destination,
        "action": action,
        "enabled": enabled,
        "ip_version": ip_version,
        "logging": logging,
        "allow_return_traffic": allow_return_traffic,
    }
    if protocol is not None:
        normalized["protocol"] = protocol
    if protocol_number is not None:
        normalized["protocol_number"] = protocol_number
    if normalized_states is not None:
        normalized["connection_states"] = normalized_states
    if ipsec is not None:
        normalized["ipsec"] = ipsec
    if description is not None:
        normalized["description"] = description
    return normalized


def validate_firewall(
    value: Any,
    *,
    network_names: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Validate and normalize the portable firewall document.

    ``network_names`` is supplied by the top-level configuration validator when
    available. Rule zones may still refer to system-defined controller zones;
    those are resolved against live inventory by the planner.
    """
    if value is None:
        return {"zones": [], "address_groups": [], "port_groups": [], "rules": []}
    firewall = _mapping(value, "firewall")
    _reject_unknown(firewall, FIREWALL_KEYS, "firewall")
    names = set(network_names) if network_names is not None else None

    raw_zones = firewall.get("zones", [])
    if not isinstance(raw_zones, list):
        raise FirewallError("firewall.zones must be a list")
    zones = [_validate_zone(zone, index, names) for index, zone in enumerate(raw_zones)]
    zone_names = {zone["name"] for zone in zones}
    if len(zone_names) != len(zones):
        raise FirewallError("firewall.zones must not contain duplicate names")

    raw_address_groups = firewall.get("address_groups", [])
    if not isinstance(raw_address_groups, list):
        raise FirewallError("firewall.address_groups must be a list")
    address_groups = [
        _validate_address_group(group, index) for index, group in enumerate(raw_address_groups)
    ]
    address_group_names = {group["name"] for group in address_groups}
    if len(address_group_names) != len(address_groups):
        raise FirewallError("firewall.address_groups must not contain duplicate names")

    raw_port_groups = firewall.get("port_groups", [])
    if not isinstance(raw_port_groups, list):
        raise FirewallError("firewall.port_groups must be a list")
    port_groups = [
        _validate_port_group(group, index) for index, group in enumerate(raw_port_groups)
    ]
    port_group_names = {group["name"] for group in port_groups}
    if len(port_group_names) != len(port_groups):
        raise FirewallError("firewall.port_groups must not contain duplicate names")
    overlap = sorted(address_group_names & port_group_names)
    if overlap:
        raise FirewallError(f"firewall group names must be globally unique: {', '.join(overlap)}")

    raw_rules = firewall.get("rules", [])
    if not isinstance(raw_rules, list):
        raise FirewallError("firewall.rules must be a list")
    rules = [
        _validate_rule(
            rule,
            index,
            network_names=names,
            address_group_names=address_group_names,
            port_group_names=port_group_names,
        )
        for index, rule in enumerate(raw_rules)
    ]
    rule_names = [rule["name"] for rule in rules]
    if len(set(rule_names)) != len(rule_names):
        raise FirewallError("firewall.rules must not contain duplicate names")
    order_keys = [
        (rule["source"]["zone"], rule["destination"]["zone"], rule["order"]) for rule in rules
    ]
    if len(set(order_keys)) != len(order_keys):
        raise FirewallError("firewall.rules order must be unique per source/destination zone pair")

    return {
        "zones": zones,
        "address_groups": address_groups,
        "port_groups": port_groups,
        "rules": rules,
    }


def firewall_rule_is_broad(rule: Mapping[str, Any]) -> bool:
    """Return whether a rule omits a selector and therefore matches broadly."""
    for side_name in ("source", "destination"):
        side = rule.get(side_name) or {}
        if not side.get("networks") and not side.get("address_group"):
            return True
    return not rule.get("protocol") and rule.get("protocol_number") is None


def firewall_rule_match_key(rule: Mapping[str, Any]) -> tuple[Any, ...]:
    """Return a stable key for conservative exact-shadowing analysis."""

    def side_key(side: Mapping[str, Any]) -> tuple[Any, ...]:
        return (
            side.get("zone"),
            tuple(side.get("networks") or ()),
            side.get("address_group"),
            side.get("port_group"),
            bool(side.get("match_opposite", False)),
            bool(side.get("port_match_opposite", False)),
        )

    return (
        side_key(rule.get("source") or {}),
        side_key(rule.get("destination") or {}),
        rule.get("ip_version", "IPV4_AND_IPV6"),
        rule.get("protocol"),
        rule.get("protocol_number"),
        tuple(rule.get("connection_states") or ()),
        rule.get("ipsec"),
    )


__all__ = [
    "ADDRESS_GROUP_KEYS",
    "FIREWALL_KEYS",
    "FirewallError",
    "PORT_GROUP_KEYS",
    "RULE_KEYS",
    "SUPPORTED_ACTIONS",
    "SUPPORTED_CONNECTION_STATES",
    "SUPPORTED_IPSEC",
    "SUPPORTED_IP_VERSIONS",
    "SUPPORTED_PROTOCOLS",
    "firewall_rule_is_broad",
    "firewall_rule_match_key",
    "normalize_address_item",
    "normalize_address_items",
    "normalize_port_item",
    "normalize_port_items",
    "validate_firewall",
]
