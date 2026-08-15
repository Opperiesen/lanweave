"""Portable NAT and port-forwarding contract.

The public model describes reachability without controller identifiers or
vendor payload fields. Controller-specific endpoint mapping belongs to the
adapter/planner boundary introduced by later v0.6 issues.
"""

from __future__ import annotations

import ipaddress
from collections.abc import Iterable, Mapping
from typing import Any

NAT_MAPPING_KEYS = {
    "name",
    "enabled",
    "protocol",
    "ip_version",
    "public",
    "source",
    "private",
    "hairpin",
    "description",
}
NAT_PUBLIC_KEYS = {"interface", "address", "port"}
NAT_SOURCE_KEYS = {"zone", "addresses"}
NAT_PRIVATE_KEYS = {"network", "address", "port"}
NAT_USER_ORIGINS = frozenset({"USER", "USER_DEFINED", "CUSTOM"})
SUPPORTED_NAT_PROTOCOLS = frozenset({"TCP", "UDP", "TCP_UDP"})
SUPPORTED_NAT_IP_VERSIONS = frozenset({"IPV4", "IPV6"})
NAT_PORT_MIN = 1
NAT_PORT_MAX = 65535


class NatError(ValueError):
    """Raised when portable NAT state is malformed or ambiguous."""


class UnsupportedNatVariantError(NatError):
    """Raised when a controller variant is outside the v0.6 contract."""


def _mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise NatError(f"{label} must be a mapping")
    return dict(value)


def _string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise NatError(f"{label} must be a non-empty string")
    return value.strip()


def _reject_unknown(mapping: Mapping[str, Any], allowed: set[str], label: str) -> None:
    unknown = sorted(set(mapping) - allowed, key=str)
    if unknown:
        raise NatError(f"unsupported field(s) in {label}: {', '.join(map(str, unknown))}")


def _canonical_address(value: Any, label: str, *, allow_network: bool) -> tuple[str, int]:
    text = _string(value, label)
    try:
        if allow_network and "/" in text:
            parsed = ipaddress.ip_network(text, strict=False)
        else:
            parsed = ipaddress.ip_address(text)
    except ValueError as exc:
        kind = "IP address or CIDR network" if allow_network else "IP address"
        raise NatError(f"{label} must be an {kind}") from exc
    return str(parsed), parsed.version


def normalize_nat_port(value: Any, label: str = "port") -> int | dict[str, int]:
    """Normalize one translated port or inclusive port range."""
    if isinstance(value, bool):
        raise NatError(f"{label} must be a port number or range")
    if isinstance(value, int):
        if not NAT_PORT_MIN <= value <= NAT_PORT_MAX:
            raise NatError(f"{label} must be between {NAT_PORT_MIN} and {NAT_PORT_MAX}")
        return value

    item = _mapping(value, label)
    _reject_unknown(item, {"start", "stop"}, label)
    start = item.get("start")
    stop = item.get("stop")
    if any(isinstance(port, bool) or not isinstance(port, int) for port in (start, stop)):
        raise NatError(f"{label}.start and stop must be port numbers")
    if not NAT_PORT_MIN <= start <= NAT_PORT_MAX or not NAT_PORT_MIN <= stop <= NAT_PORT_MAX:
        raise NatError(f"{label}.start and stop must be between {NAT_PORT_MIN} and {NAT_PORT_MAX}")
    if start > stop:
        raise NatError(f"{label}.start must not be after stop")
    if start == stop:
        return start
    return {"start": start, "stop": stop}


def _port_bounds(value: int | Mapping[str, Any]) -> tuple[int, int]:
    if isinstance(value, int):
        return value, value
    return int(value["start"]), int(value["stop"])


def _validate_source(value: Any, label: str) -> tuple[dict[str, Any], set[int]]:
    if value is None:
        return {"addresses": []}, set()
    source = _mapping(value, label)
    _reject_unknown(source, NAT_SOURCE_KEYS, label)
    zone = source.get("zone")
    normalized_zone = _string(zone, f"{label}.zone") if zone is not None else None
    addresses = source.get("addresses", [])
    if not isinstance(addresses, list):
        raise NatError(f"{label}.addresses must be a list of IP addresses or CIDR networks")
    normalized_addresses: list[str] = []
    families: set[int] = set()
    for index, address in enumerate(addresses):
        normalized, family = _canonical_address(
            address,
            f"{label}.addresses[{index}]",
            allow_network=True,
        )
        if normalized in normalized_addresses:
            raise NatError(f"duplicate source address in {label}.addresses: {normalized}")
        normalized_addresses.append(normalized)
        families.add(family)
    if len(families) > 1:
        raise NatError(f"{label}.addresses must use one IP version")
    result: dict[str, Any] = {"addresses": sorted(normalized_addresses)}
    if normalized_zone is not None:
        result["zone"] = normalized_zone
    return result, families


def _validate_public(value: Any, label: str) -> tuple[dict[str, Any], int | None]:
    public = _mapping(value, label)
    _reject_unknown(public, NAT_PUBLIC_KEYS, label)
    interface = _string(public.get("interface"), f"{label}.interface")
    port = normalize_nat_port(public.get("port"), f"{label}.port")
    result: dict[str, Any] = {"interface": interface, "port": port}
    address = public.get("address")
    if address is not None:
        normalized_address, family = _canonical_address(
            address,
            f"{label}.address",
            allow_network=False,
        )
        result["address"] = normalized_address
        return result, family
    return result, None


def _validate_private(
    value: Any,
    label: str,
    *,
    network_names: set[str] | None,
) -> tuple[dict[str, Any], int]:
    private = _mapping(value, label)
    _reject_unknown(private, NAT_PRIVATE_KEYS, label)
    address, family = _canonical_address(
        private.get("address"),
        f"{label}.address",
        allow_network=False,
    )
    port = normalize_nat_port(private.get("port"), f"{label}.port")
    network = private.get("network")
    if network is not None:
        network = _string(network, f"{label}.network")
        if network_names is not None and network not in network_names:
            raise NatError(f"{label}.network refers to unknown network: {network}")
    result: dict[str, Any] = {"address": address, "port": port}
    if network is not None:
        result["network"] = network
    return result, family


def normalize_nat_mapping(
    value: Mapping[str, Any],
    label: str = "nat",
    *,
    network_names: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Validate and canonicalize one portable NAT mapping."""
    mapping = _mapping(value, label)
    _reject_unknown(mapping, NAT_MAPPING_KEYS, label)
    name = _string(mapping.get("name"), f"{label}.name")
    protocol = _string(mapping.get("protocol"), f"{label}.protocol").upper()
    if protocol not in SUPPORTED_NAT_PROTOCOLS:
        allowed = ", ".join(sorted(SUPPORTED_NAT_PROTOCOLS))
        raise NatError(f"{label}.protocol must be one of: {allowed}")

    raw_ip_version = mapping.get("ip_version")
    ip_version = None
    if raw_ip_version is not None:
        ip_version = _string(raw_ip_version, f"{label}.ip_version").upper()
        if ip_version not in SUPPORTED_NAT_IP_VERSIONS:
            allowed = ", ".join(sorted(SUPPORTED_NAT_IP_VERSIONS))
            raise NatError(f"{label}.ip_version must be one of: {allowed}")

    networks = set(network_names) if network_names is not None else None
    public, public_family = _validate_public(mapping.get("public"), f"{label}.public")
    source, source_families = _validate_source(mapping.get("source"), f"{label}.source")
    private, private_family = _validate_private(
        mapping.get("private"),
        f"{label}.private",
        network_names=networks,
    )

    families = {private_family}
    if public_family is not None:
        families.add(public_family)
    families.update(source_families)
    if len(families) != 1:
        raise NatError(f"{label} must use one IP version across public, source and private")
    inferred_ip_version = "IPV4" if private_family == 4 else "IPV6"
    if ip_version is not None and ip_version != inferred_ip_version:
        raise NatError(f"{label}.ip_version does not match the mapping addresses")

    public_start, public_stop = _port_bounds(public["port"])
    private_start, private_stop = _port_bounds(private["port"])
    if public_stop - public_start != private_stop - private_start:
        raise NatError(f"{label}.public.port and private.port must cover the same number of ports")

    enabled = mapping.get("enabled", True)
    if not isinstance(enabled, bool):
        raise NatError(f"{label}.enabled must be a boolean")
    hairpin = mapping.get("hairpin", False)
    if not isinstance(hairpin, bool):
        raise NatError(f"{label}.hairpin must be a boolean")
    description = mapping.get("description")
    if description is not None:
        description = _string(description, f"{label}.description")

    result: dict[str, Any] = {
        "name": name,
        "enabled": enabled,
        "protocol": protocol,
        "ip_version": ip_version or inferred_ip_version,
        "public": public,
        "source": source,
        "private": private,
        "hairpin": hairpin,
    }
    if description is not None:
        result["description"] = description
    return result


def validate_nat(
    value: Any,
    *,
    network_names: Iterable[str] | None = None,
) -> list[dict[str, Any]]:
    """Validate and normalize the top-level ``nat`` list."""
    if value is None:
        return []
    if not isinstance(value, list):
        raise NatError("nat must be a list")
    normalized = [
        normalize_nat_mapping(
            mapping,
            f"nat[{index}]",
            network_names=network_names,
        )
        for index, mapping in enumerate(value)
    ]
    names = [mapping["name"] for mapping in normalized]
    if len(set(names)) != len(names):
        raise NatError("nat must not contain duplicate mapping names")
    return normalized


def nat_is_broad(value: Mapping[str, Any]) -> bool:
    """Return whether a mapping accepts traffic from any source address."""
    source = value.get("source") or {}
    return not source.get("addresses")


def nat_is_user_managed(value: Mapping[str, Any]) -> bool:
    """Return whether a live controller mapping is safe for mutation/prune."""
    return str(value.get("_origin", "UNKNOWN")).upper() in NAT_USER_ORIGINS


def nat_mapping_identity(value: Mapping[str, Any]) -> str:
    """Return the stable portable identity for one NAT mapping."""
    return str(value["name"])


__all__ = [
    "NAT_MAPPING_KEYS",
    "NAT_PORT_MAX",
    "NAT_PORT_MIN",
    "NAT_USER_ORIGINS",
    "NatError",
    "SUPPORTED_NAT_IP_VERSIONS",
    "SUPPORTED_NAT_PROTOCOLS",
    "UnsupportedNatVariantError",
    "nat_is_broad",
    "nat_is_user_managed",
    "nat_mapping_identity",
    "normalize_nat_mapping",
    "normalize_nat_port",
    "validate_nat",
]
