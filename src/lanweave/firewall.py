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
    "placement",
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
SUPPORTED_PLACEMENTS = {"before_system_defined", "after_system_defined"}
FIREWALL_USER_ORIGINS = frozenset({"USER", "USER_DEFINED", "CUSTOM"})

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


class UnsupportedFirewallVariantError(FirewallError):
    """Raised when a controller returns a firewall variant outside v0.5."""


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
    placement = str(rule.get("placement", "after_system_defined")).strip().lower()
    if placement not in SUPPORTED_PLACEMENTS:
        raise FirewallError(
            f"{label}.placement must be one of: {', '.join(sorted(SUPPORTED_PLACEMENTS))}"
        )
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
        "placement": placement,
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
        (
            rule["source"]["zone"],
            rule["destination"]["zone"],
            rule["placement"],
            rule["order"],
        )
        for rule in rules
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


def _controller_origin(value: Mapping[str, Any]) -> str:
    metadata = value.get("metadata")
    origin = metadata.get("origin") if isinstance(metadata, Mapping) else None
    return str(origin or "UNKNOWN").strip().upper()


def _controller_id(value: Mapping[str, Any]) -> str | None:
    identifier = value.get("id") or value.get("_id")
    return str(identifier) if identifier else None


def _controller_address_item(value: Any, label: str) -> str | dict[str, str]:
    if isinstance(value, str):
        return value
    if not isinstance(value, Mapping):
        raise UnsupportedFirewallVariantError(f"unsupported controller address item at {label}")
    item_type = str(value.get("type") or "").upper()
    if item_type in {"IP_ADDRESS", "SUBNET"} and isinstance(value.get("value"), str):
        return value["value"]
    if item_type == "IP_ADDRESS_RANGE":
        start = value.get("start")
        stop = value.get("stop")
        if isinstance(start, str) and isinstance(stop, str):
            return {"start": start, "stop": stop}
    raise UnsupportedFirewallVariantError(f"unsupported controller address item at {label}")


def _controller_port_item(value: Any, label: str) -> int | dict[str, int]:
    if not isinstance(value, Mapping):
        if isinstance(value, int) and not isinstance(value, bool):
            return value
        raise UnsupportedFirewallVariantError(f"unsupported controller port item at {label}")
    item_type = str(value.get("type") or "").upper()
    if item_type == "PORT_NUMBER" and isinstance(value.get("value"), int):
        return value["value"]
    if item_type == "PORT_NUMBER_RANGE":
        start = value.get("start")
        stop = value.get("stop")
        if isinstance(start, int) and isinstance(stop, int):
            return {"start": start, "stop": stop}
    raise UnsupportedFirewallVariantError(f"unsupported controller port item at {label}")


def normalize_controller_firewall_zone(
    value: Mapping[str, Any], label: str = "controller.zone"
) -> dict[str, Any]:
    """Normalize one Integration API firewall zone without exposing metadata."""
    if not isinstance(value, Mapping):
        raise FirewallError(f"{label} must be a mapping")
    identifier = _controller_id(value)
    name = value.get("name")
    network_ids = value.get("networkIds", value.get("network_ids", []))
    if not identifier or not isinstance(name, str) or not name.strip():
        raise FirewallError(f"{label} is missing id or name")
    if not isinstance(network_ids, list) or not all(isinstance(item, str) for item in network_ids):
        raise FirewallError(f"{label}.networkIds must be a list of strings")
    result: dict[str, Any] = {
        "_id": identifier,
        "id": identifier,
        "name": name.strip(),
        "network_ids": list(dict.fromkeys(network_ids)),
        "_origin": _controller_origin(value),
    }
    metadata = value.get("metadata")
    if isinstance(metadata, Mapping) and "configurable" in metadata:
        result["_configurable"] = bool(metadata["configurable"])
    return result


def normalize_controller_traffic_matching_list(
    value: Mapping[str, Any], label: str = "controller.traffic_matching_list"
) -> dict[str, Any]:
    """Normalize one supported address or port group from the Integration API.

    The official traffic-matching-list endpoint exposes editable lists but does
    not return entity metadata. Treating a list without metadata as unknown
    would make a create/update cycle impossible, so the endpoint's scope is
    used as the ownership boundary here.
    """
    if not isinstance(value, Mapping):
        raise FirewallError(f"{label} must be a mapping")
    identifier = _controller_id(value)
    name = value.get("name")
    list_type = str(value.get("type") or "").strip().upper()
    if not identifier or not isinstance(name, str) or not name.strip():
        raise FirewallError(f"{label} is missing id or name")
    raw_items = value.get("items")
    if not isinstance(raw_items, list):
        raise FirewallError(f"{label}.items must be a list")
    if list_type in {"IPV4_ADDRESSES", "IPV6_ADDRESSES"}:
        items = [
            _controller_address_item(item, f"{label}.items[{index}]")
            for index, item in enumerate(raw_items)
        ]
        normalized = normalize_address_items(items, f"{label}.items")
        expected_family = 4 if list_type == "IPV4_ADDRESSES" else 6
        if any(item["family"] != expected_family for item in normalized):
            raise FirewallError(f"{label} contains an item from the wrong IP version")
        group_type = "address_group"
        portable_items = [_portable_address_item(item) for item in normalized]
    elif list_type == "PORTS":
        normalized = normalize_port_items(
            [
                _controller_port_item(item, f"{label}.items[{index}]")
                for index, item in enumerate(raw_items)
            ],
            f"{label}.items",
        )
        group_type = "port_group"
        portable_items = [_portable_port_item(item) for item in normalized]
    else:
        raise UnsupportedFirewallVariantError(
            f"unsupported controller traffic matching list type: {list_type or 'missing'}"
        )
    origin = _controller_origin(value)
    if origin == "UNKNOWN":
        origin = "USER_DEFINED"
    return {
        "_id": identifier,
        "id": identifier,
        "name": name.strip(),
        "type": list_type,
        "group_type": group_type,
        "items": portable_items,
        "_origin": origin,
    }


def _normalize_controller_endpoint(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise FirewallError(f"{label} must be a mapping")
    zone_id = value.get("zoneId") or value.get("zone_id")
    if not isinstance(zone_id, str) or not zone_id:
        raise FirewallError(f"{label}.zoneId must be a non-empty string")
    result: dict[str, Any] = {"zone_id": zone_id}
    traffic_filter = value.get("trafficFilter", value.get("traffic_filter"))
    if traffic_filter is not None:
        if not isinstance(traffic_filter, Mapping):
            raise FirewallError(f"{label}.trafficFilter must be a mapping")
        result["traffic_filter"] = dict(traffic_filter)
    return result


def normalize_controller_firewall_policy(
    value: Mapping[str, Any], label: str = "controller.firewall_policy"
) -> dict[str, Any]:
    """Normalize a policy while preserving supported filter details for export."""
    if not isinstance(value, Mapping):
        raise FirewallError(f"{label} must be a mapping")
    identifier = _controller_id(value)
    name = value.get("name")
    if not identifier or not isinstance(name, str) or not name.strip():
        raise FirewallError(f"{label} is missing id or name")
    action = value.get("action")
    if isinstance(action, Mapping):
        action_type = str(action.get("type") or "").strip().upper()
        allow_return_traffic = bool(action.get("allowReturnTraffic", False))
    else:
        action_type = str(action or "").strip().upper()
        allow_return_traffic = False
    if action_type not in SUPPORTED_ACTIONS:
        raise UnsupportedFirewallVariantError(
            f"unsupported controller firewall action: {action_type or 'missing'}"
        )
    scope = value.get("ipProtocolScope", value.get("ip_protocol_scope"))
    if not isinstance(scope, Mapping):
        raise FirewallError(f"{label}.ipProtocolScope must be a mapping")
    ip_version = str(scope.get("ipVersion") or scope.get("ip_version") or "").upper()
    if ip_version not in SUPPORTED_IP_VERSIONS:
        raise UnsupportedFirewallVariantError(f"unsupported controller IP version: {ip_version}")
    result: dict[str, Any] = {
        "_id": identifier,
        "id": identifier,
        "name": name.strip(),
        "enabled": bool(value.get("enabled", True)),
        "action": action_type,
        "allow_return_traffic": allow_return_traffic,
        "source": _normalize_controller_endpoint(value.get("source"), f"{label}.source"),
        "destination": _normalize_controller_endpoint(
            value.get("destination"), f"{label}.destination"
        ),
        "ip_version": ip_version,
        "logging": bool(value.get("loggingEnabled", value.get("logging", False))),
        "_origin": _controller_origin(value),
    }
    protocol_filter = scope.get("protocolFilter", scope.get("protocol_filter"))
    if protocol_filter is not None:
        if not isinstance(protocol_filter, Mapping):
            raise FirewallError(f"{label}.protocolFilter must be a mapping")
        result["protocol_filter"] = dict(protocol_filter)
    states = value.get("connectionStateFilter", value.get("connection_states"))
    if states is not None:
        if not isinstance(states, list) or not all(isinstance(item, str) for item in states):
            raise FirewallError(f"{label}.connectionStateFilter must be a list of strings")
        result["connection_states"] = [str(item).upper() for item in states]
    ipsec = value.get("ipsecFilter", value.get("ipsec"))
    if ipsec is not None:
        result["ipsec"] = str(ipsec).upper()
    if value.get("description") is not None:
        result["description"] = str(value["description"])
    if value.get("schedule") is not None:
        result["schedule"] = value["schedule"]
    if value.get("index") is not None:
        result["controller_index"] = value["index"]
    return result


def _group_name_for_id(
    group_id: Any,
    groups_by_id: Mapping[str, Mapping[str, Any]],
    expected_type: str,
    label: str,
) -> str:
    identifier = str(group_id or "")
    group = groups_by_id.get(identifier)
    if group is None:
        raise FirewallError(f"{label} refers to an unknown traffic matching list")
    if group.get("group_type") != expected_type:
        raise FirewallError(f"{label} refers to a group of the wrong type")
    if not firewall_is_user_managed(group):
        raise FirewallError(f"{label} refers to a protected traffic matching list")
    return str(group["name"])


def _generated_group(
    generated: list[dict[str, Any]],
    used_names: set[str],
    *,
    base_name: str,
    group_type: str,
    items: list[Any],
) -> str:
    """Create a deterministic portable group for an inline controller filter."""
    import re

    base = re.sub(r"[^a-zA-Z0-9_-]+", "-", base_name).strip("-_").lower() or "rule"
    candidate = base
    suffix = 2
    while candidate in used_names:
        candidate = f"{base}-{suffix}"
        suffix += 1
    used_names.add(candidate)
    key = "addresses" if group_type == "address_group" else "ports"
    generated.append({"name": candidate, key: items})
    return candidate


def _export_api_address_filter(
    value: Mapping[str, Any],
    *,
    groups_by_id: Mapping[str, Mapping[str, Any]],
    generated: list[dict[str, Any]],
    used_names: set[str],
    label: str,
) -> tuple[str, bool]:
    filter_type = str(value.get("type") or "").upper()
    match_opposite = bool(value.get("matchOpposite", False))
    if filter_type == "TRAFFIC_MATCHING_LIST":
        return (
            _group_name_for_id(
                value.get("trafficMatchingListId"), groups_by_id, "address_group", label
            ),
            match_opposite,
        )
    if filter_type != "IP_ADDRESSES":
        raise UnsupportedFirewallVariantError(f"unsupported controller address filter at {label}")
    raw_items = value.get("items")
    if not isinstance(raw_items, list):
        raise FirewallError(f"{label}.items must be a list")
    items = [
        _controller_address_item(item, f"{label}.items[{index}]")
        for index, item in enumerate(raw_items)
    ]
    normalized = normalize_address_items(items, f"{label}.items")
    return (
        _generated_group(
            generated,
            used_names,
            base_name=label,
            group_type="address_group",
            items=[_portable_address_item(item) for item in normalized],
        ),
        match_opposite,
    )


def _export_api_port_filter(
    value: Mapping[str, Any],
    *,
    groups_by_id: Mapping[str, Mapping[str, Any]],
    generated: list[dict[str, Any]],
    used_names: set[str],
    label: str,
) -> tuple[str, bool]:
    filter_type = str(value.get("type") or "").upper()
    match_opposite = bool(value.get("matchOpposite", False))
    if filter_type == "TRAFFIC_MATCHING_LIST":
        return (
            _group_name_for_id(
                value.get("trafficMatchingListId"), groups_by_id, "port_group", label
            ),
            match_opposite,
        )
    if filter_type != "PORTS":
        raise UnsupportedFirewallVariantError(f"unsupported controller port filter at {label}")
    raw_items = value.get("items")
    if not isinstance(raw_items, list):
        raise FirewallError(f"{label}.items must be a list")
    items = [
        _controller_port_item(item, f"{label}.items[{index}]")
        for index, item in enumerate(raw_items)
    ]
    normalized = normalize_port_items(items, f"{label}.items")
    return (
        _generated_group(
            generated,
            used_names,
            base_name=label,
            group_type="port_group",
            items=[_portable_port_item(item) for item in normalized],
        ),
        match_opposite,
    )


def _export_endpoint(
    endpoint: Mapping[str, Any],
    *,
    is_source: bool,
    zone_names_by_id: Mapping[str, str],
    network_names_by_id: Mapping[str, str],
    groups_by_id: Mapping[str, Mapping[str, Any]],
    generated: list[dict[str, Any]],
    used_names: set[str],
    label: str,
) -> dict[str, Any]:
    zone_id = str(endpoint.get("zone_id") or "")
    zone_name = zone_names_by_id.get(zone_id)
    if zone_name is None:
        raise FirewallError(f"{label}.zone_id refers to an unknown firewall zone")
    result: dict[str, Any] = {"zone": zone_name}
    traffic_filter = endpoint.get("traffic_filter")
    if traffic_filter is None:
        return result
    if not isinstance(traffic_filter, Mapping):
        raise FirewallError(f"{label}.traffic_filter must be a mapping")
    filter_type = str(traffic_filter.get("type") or "").upper()
    if filter_type == "NETWORK":
        network_filter = traffic_filter.get("networkFilter")
        if not isinstance(network_filter, Mapping):
            raise FirewallError(f"{label}.networkFilter must be a mapping")
        network_ids = network_filter.get("networkIds")
        if not isinstance(network_ids, list) or not all(
            isinstance(item, str) for item in network_ids
        ):
            raise FirewallError(f"{label}.networkFilter.networkIds must be a list")
        try:
            result["networks"] = [network_names_by_id[item] for item in network_ids]
        except KeyError as exc:
            raise FirewallError(f"{label}.networkFilter refers to an unknown network") from exc
        if network_filter.get("matchOpposite"):
            result["match_opposite"] = True
    elif filter_type == "IP_ADDRESS":
        address_filter = traffic_filter.get("ipAddressFilter")
        if not isinstance(address_filter, Mapping):
            raise FirewallError(f"{label}.ipAddressFilter must be a mapping")
        group_name, match_opposite = _export_api_address_filter(
            address_filter,
            groups_by_id=groups_by_id,
            generated=generated,
            used_names=used_names,
            label=f"{label}.ipAddressFilter",
        )
        result["address_group"] = group_name
        if match_opposite:
            result["match_opposite"] = True
    elif filter_type != "PORT":
        raise UnsupportedFirewallVariantError(f"unsupported controller traffic filter at {label}")

    port_filter = traffic_filter.get("portFilter")
    if port_filter is not None:
        if not isinstance(port_filter, Mapping):
            raise FirewallError(f"{label}.portFilter must be a mapping")
        group_name, match_opposite = _export_api_port_filter(
            port_filter,
            groups_by_id=groups_by_id,
            generated=generated,
            used_names=used_names,
            label=f"{label}.portFilter",
        )
        result["port_group"] = group_name
        if match_opposite:
            result["port_match_opposite"] = True
    elif filter_type == "PORT":
        raise FirewallError(f"{label} is missing portFilter")
    return result


def _export_protocol_filter(value: Mapping[str, Any], label: str) -> dict[str, Any]:
    filter_type = str(value.get("type") or "").upper()
    if filter_type == "NAMED_PROTOCOL":
        protocol = value.get("protocol")
        if not isinstance(protocol, Mapping) or not isinstance(protocol.get("name"), str):
            raise FirewallError(f"{label}.protocol must be a mapping with a name")
        result = {"protocol": str(protocol["name"]).upper()}
    elif filter_type == "PRESET":
        preset = value.get("preset")
        if not isinstance(preset, Mapping) or not isinstance(preset.get("name"), str):
            raise FirewallError(f"{label}.preset must be a mapping with a name")
        result = {"protocol": str(preset["name"]).upper()}
    elif filter_type == "PROTOCOL_NUMBER":
        protocol_number = value.get("protocolNumber")
        if isinstance(protocol_number, bool) or not isinstance(protocol_number, int):
            raise FirewallError(f"{label}.protocolNumber must be an integer")
        result = {"protocol_number": protocol_number}
    else:
        raise UnsupportedFirewallVariantError(f"unsupported controller protocol filter at {label}")
    if value.get("matchOpposite"):
        raise UnsupportedFirewallVariantError(
            f"opposite protocol filters are not portable at {label}"
        )
    return result


def firewall_policy_to_portable(
    policy: Mapping[str, Any],
    *,
    order: int,
    placement: str,
    zone_names_by_id: Mapping[str, str],
    network_names_by_id: Mapping[str, str],
    groups_by_id: Mapping[str, Mapping[str, Any]],
    generated: list[dict[str, Any]],
    used_names: set[str],
) -> dict[str, Any]:
    """Convert one normalized live policy to the portable rule contract."""
    source = _export_endpoint(
        policy["source"],
        is_source=True,
        zone_names_by_id=zone_names_by_id,
        network_names_by_id=network_names_by_id,
        groups_by_id=groups_by_id,
        generated=generated,
        used_names=used_names,
        label=f"firewall rule {policy['name']} source",
    )
    destination = _export_endpoint(
        policy["destination"],
        is_source=False,
        zone_names_by_id=zone_names_by_id,
        network_names_by_id=network_names_by_id,
        groups_by_id=groups_by_id,
        generated=generated,
        used_names=used_names,
        label=f"firewall rule {policy['name']} destination",
    )
    result: dict[str, Any] = {
        "name": policy["name"],
        "order": order,
        "placement": placement,
        "source": source,
        "destination": destination,
        "action": policy["action"],
        "enabled": policy.get("enabled", True),
        "ip_version": policy["ip_version"],
        "logging": policy.get("logging", False),
        "allow_return_traffic": policy.get("allow_return_traffic", False),
    }
    protocol_filter = policy.get("protocol_filter")
    if protocol_filter is not None:
        result.update(_export_protocol_filter(protocol_filter, f"firewall rule {policy['name']}"))
    if policy.get("connection_states") is not None:
        result["connection_states"] = list(policy["connection_states"])
    if policy.get("ipsec") is not None:
        result["ipsec"] = policy["ipsec"]
    if policy.get("description"):
        result["description"] = policy["description"]
    return result


def export_firewall_config(
    *,
    zones: Sequence[Mapping[str, Any]],
    groups: Sequence[Mapping[str, Any]],
    policies: Sequence[Mapping[str, Any]],
    orderings: Mapping[tuple[str, str], Mapping[str, Sequence[str]]],
    network_names_by_id: Mapping[str, str],
) -> dict[str, Any]:
    """Export user-managed firewall resources without controller IDs."""
    all_zones = {str(zone["id"]): zone for zone in zones if zone.get("id")}
    zone_names_by_id = {identifier: str(zone["name"]) for identifier, zone in all_zones.items()}
    all_groups = {str(group["id"]): group for group in groups if group.get("id")}
    user_groups = [group for group in groups if firewall_is_user_managed(group)]
    user_zones = [zone for zone in zones if firewall_is_user_managed(zone)]
    user_policies = [policy for policy in policies if firewall_is_user_managed(policy)]
    used_names = {str(group["name"]) for group in user_groups}
    generated_groups: list[dict[str, Any]] = []

    exported_rules: list[dict[str, Any]] = []
    for policy in sorted(user_policies, key=lambda item: (str(item["name"]), str(item["id"]))):
        source_zone_id = policy["source"]["zone_id"]
        destination_zone_id = policy["destination"]["zone_id"]
        ordering = orderings.get((source_zone_id, destination_zone_id))
        if ordering is None:
            raise FirewallError(
                f"missing firewall policy ordering for {source_zone_id}/{destination_zone_id}"
            )
        placement = "after_system_defined"
        order = 0
        found_in_ordering = False
        for candidate_placement in ("before_system_defined", "after_system_defined"):
            ids = list(ordering.get(candidate_placement, []))
            if policy["id"] in ids:
                placement = candidate_placement
                order = ids.index(policy["id"])
                found_in_ordering = True
                break
        if not found_in_ordering:
            raise FirewallError(
                f"firewall policy {policy['name']} is absent from its controller ordering"
            )
        exported_rules.append(
            firewall_policy_to_portable(
                policy,
                order=order,
                placement=placement,
                zone_names_by_id=zone_names_by_id,
                network_names_by_id=network_names_by_id,
                groups_by_id=all_groups,
                generated=generated_groups,
                used_names=used_names,
            )
        )

    exported_zones: list[dict[str, Any]] = []
    for zone in sorted(user_zones, key=lambda item: (str(item["name"]), str(item["id"]))):
        network_ids = zone.get("network_ids", [])
        try:
            networks = [network_names_by_id[network_id] for network_id in network_ids]
        except KeyError as exc:
            raise FirewallError(
                f"firewall zone {zone['name']} refers to an unknown network"
            ) from exc
        exported_zones.append({"name": zone["name"], "networks": networks})

    exported_address_groups = [
        {"name": group["name"], "addresses": list(group["items"])}
        for group in sorted(user_groups, key=lambda item: (str(item["name"]), str(item["id"])))
        if group.get("group_type") == "address_group"
    ]
    exported_port_groups = [
        {"name": group["name"], "ports": list(group["items"])}
        for group in sorted(user_groups, key=lambda item: (str(item["name"]), str(item["id"])))
        if group.get("group_type") == "port_group"
    ]
    for group in generated_groups:
        if "addresses" in group:
            exported_address_groups.append(group)
        else:
            exported_port_groups.append(group)
    exported_address_groups.sort(key=lambda item: item["name"])
    exported_port_groups.sort(key=lambda item: item["name"])
    exported_rules.sort(
        key=lambda item: (
            item["source"]["zone"],
            item["destination"]["zone"],
            item["placement"],
            item["order"],
            item["name"],
        )
    )
    return {
        "zones": exported_zones,
        "address_groups": exported_address_groups,
        "port_groups": exported_port_groups,
        "rules": exported_rules,
    }


def firewall_zone_to_unifi(
    zone: Mapping[str, Any], network_ids_by_name: Mapping[str, str]
) -> dict[str, Any]:
    """Convert one portable zone to the official Integration API payload."""
    networks = zone.get("networks", [])
    try:
        network_ids = [network_ids_by_name[name] for name in networks]
    except KeyError as exc:
        raise FirewallError(
            f"firewall zone {zone.get('name')} refers to an unknown network"
        ) from exc
    return {"name": zone["name"], "networkIds": network_ids}


def firewall_group_to_unifi(group: Mapping[str, Any]) -> dict[str, Any]:
    """Convert one portable address or port group to the official payload."""
    if "addresses" in group:
        normalized = normalize_address_items(group["addresses"], f"group {group['name']}.addresses")
        family = normalized[0]["family"]
        list_type = "IPV4_ADDRESSES" if family == 4 else "IPV6_ADDRESSES"
        items = [
            {key: value for key, value in item.items() if key != "family"} for item in normalized
        ]
    elif "ports" in group:
        normalized = normalize_port_items(group["ports"], f"group {group['name']}.ports")
        list_type = "PORTS"
        items = normalized
    else:
        raise FirewallError(f"firewall group {group.get('name')} has no addresses or ports")
    return {"name": group["name"], "type": list_type, "items": items}


def _firewall_port_filter(group_id: str, match_opposite: bool) -> dict[str, Any]:
    return {
        "type": "TRAFFIC_MATCHING_LIST",
        "trafficMatchingListId": group_id,
        "matchOpposite": match_opposite,
    }


def _firewall_endpoint_to_unifi(
    side: Mapping[str, Any],
    *,
    network_ids_by_name: Mapping[str, str],
    zone_ids_by_name: Mapping[str, str],
    group_ids_by_name: Mapping[str, str],
) -> dict[str, Any]:
    try:
        zone_id = zone_ids_by_name[side["zone"]]
    except KeyError as exc:
        raise FirewallError(f"firewall rule refers to an unknown zone: {side.get('zone')}") from exc
    endpoint: dict[str, Any] = {"zoneId": zone_id}
    traffic_filter: dict[str, Any] | None = None
    match_opposite = bool(side.get("match_opposite", False))
    if side.get("networks"):
        try:
            network_ids = [network_ids_by_name[name] for name in side["networks"]]
        except KeyError as exc:
            raise FirewallError(
                f"firewall rule refers to an unknown network: {exc.args[0]}"
            ) from exc
        traffic_filter = {
            "type": "NETWORK",
            "networkFilter": {"networkIds": network_ids, "matchOpposite": match_opposite},
        }
    elif side.get("address_group"):
        try:
            group_id = group_ids_by_name[side["address_group"]]
        except KeyError as exc:
            raise FirewallError(
                f"firewall rule refers to an unknown address group: {side['address_group']}"
            ) from exc
        traffic_filter = {
            "type": "IP_ADDRESS",
            "ipAddressFilter": {
                "type": "TRAFFIC_MATCHING_LIST",
                "trafficMatchingListId": group_id,
                "matchOpposite": match_opposite,
            },
        }
    if side.get("port_group"):
        try:
            port_group_id = group_ids_by_name[side["port_group"]]
        except KeyError as exc:
            raise FirewallError(
                f"firewall rule refers to an unknown port group: {side['port_group']}"
            ) from exc
        port_filter = _firewall_port_filter(
            port_group_id, bool(side.get("port_match_opposite", False))
        )
        if traffic_filter is None:
            traffic_filter = {"type": "PORT"}
        traffic_filter["portFilter"] = port_filter
    if traffic_filter is not None:
        endpoint["trafficFilter"] = traffic_filter
    return endpoint


def firewall_rule_to_unifi(
    rule: Mapping[str, Any],
    *,
    zone_ids_by_name: Mapping[str, str],
    network_ids_by_name: Mapping[str, str],
    group_ids_by_name: Mapping[str, str],
) -> dict[str, Any]:
    """Convert one portable rule to the official Integration API payload."""
    payload: dict[str, Any] = {
        "name": rule["name"],
        "enabled": rule.get("enabled", True),
        "action": {"type": rule["action"]},
        "source": _firewall_endpoint_to_unifi(
            rule["source"],
            network_ids_by_name=network_ids_by_name,
            zone_ids_by_name=zone_ids_by_name,
            group_ids_by_name=group_ids_by_name,
        ),
        "destination": _firewall_endpoint_to_unifi(
            rule["destination"],
            network_ids_by_name=network_ids_by_name,
            zone_ids_by_name=zone_ids_by_name,
            group_ids_by_name=group_ids_by_name,
        ),
        "ipProtocolScope": {"ipVersion": rule.get("ip_version", "IPV4_AND_IPV6")},
        "loggingEnabled": rule.get("logging", False),
    }
    if rule["action"] == "ALLOW":
        payload["action"]["allowReturnTraffic"] = rule.get("allow_return_traffic", False)
    if rule.get("protocol"):
        protocol = rule["protocol"]
        if protocol == "TCP_UDP":
            protocol_filter = {"type": "PRESET", "preset": {"name": "TCP_UDP"}}
        else:
            protocol_filter = {
                "type": "NAMED_PROTOCOL",
                "matchOpposite": False,
                "protocol": {"name": protocol},
            }
        payload["ipProtocolScope"]["protocolFilter"] = protocol_filter
    elif rule.get("protocol_number") is not None:
        payload["ipProtocolScope"]["protocolFilter"] = {
            "type": "PROTOCOL_NUMBER",
            "matchOpposite": False,
            "protocolNumber": rule["protocol_number"],
        }
    if rule.get("connection_states") is not None:
        payload["connectionStateFilter"] = list(rule["connection_states"])
    if rule.get("ipsec") is not None:
        payload["ipsecFilter"] = rule["ipsec"]
    if rule.get("description") is not None:
        payload["description"] = rule["description"]
    return payload


def firewall_is_user_managed(value: Mapping[str, Any]) -> bool:
    """Return whether a live firewall object may be mutated or pruned."""
    return str(value.get("_origin", "UNKNOWN")).upper() in FIREWALL_USER_ORIGINS


__all__ = [
    "ADDRESS_GROUP_KEYS",
    "FIREWALL_KEYS",
    "FIREWALL_USER_ORIGINS",
    "FirewallError",
    "UnsupportedFirewallVariantError",
    "PORT_GROUP_KEYS",
    "RULE_KEYS",
    "SUPPORTED_ACTIONS",
    "SUPPORTED_CONNECTION_STATES",
    "SUPPORTED_IPSEC",
    "SUPPORTED_PLACEMENTS",
    "SUPPORTED_IP_VERSIONS",
    "SUPPORTED_PROTOCOLS",
    "firewall_rule_is_broad",
    "firewall_rule_match_key",
    "firewall_is_user_managed",
    "firewall_policy_to_portable",
    "export_firewall_config",
    "firewall_group_to_unifi",
    "firewall_rule_to_unifi",
    "firewall_zone_to_unifi",
    "normalize_address_item",
    "normalize_address_items",
    "normalize_port_item",
    "normalize_port_items",
    "normalize_controller_firewall_policy",
    "normalize_controller_firewall_zone",
    "normalize_controller_traffic_matching_list",
    "validate_firewall",
]
