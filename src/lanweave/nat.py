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

_CONTROLLER_PROTOCOLS = {
    "tcp": "TCP",
    "udp": "UDP",
    "tcp_udp": "TCP_UDP",
    "tcp/udp": "TCP_UDP",
    "both": "TCP_UDP",
}
_BROAD_SOURCE_VALUES = {"", "any", "all", "*", "0.0.0.0/0", "::/0"}


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


def _controller_port(value: Any, label: str) -> int | dict[str, int]:
    """Normalize the string or integer port form returned by the classic API."""
    if isinstance(value, bool):
        raise UnsupportedNatVariantError(f"{label} must be a port number or range")
    if isinstance(value, int):
        try:
            return normalize_nat_port(value, label)
        except NatError as exc:
            raise UnsupportedNatVariantError(str(exc)) from exc
    if not isinstance(value, str):
        raise UnsupportedNatVariantError(f"{label} must be a port number or range")

    text = value.strip()
    if not text:
        raise UnsupportedNatVariantError(f"{label} must be a port number or range")
    parts = text.split("-")
    if len(parts) == 1:
        try:
            return normalize_nat_port(int(parts[0]), label)
        except (TypeError, ValueError):
            raise UnsupportedNatVariantError(f"{label} must be a port number or range") from None
    if len(parts) != 2 or any(not part.strip().isdigit() for part in parts):
        raise UnsupportedNatVariantError(f"{label} must be a port number or range")
    try:
        return normalize_nat_port(
            {"start": int(parts[0]), "stop": int(parts[1])},
            label,
        )
    except NatError as exc:
        raise UnsupportedNatVariantError(str(exc)) from exc


def _controller_source(value: Any, label: str) -> dict[str, Any]:
    """Translate classic ``src`` values into the portable source scope."""
    if value is None:
        return {"addresses": []}
    if isinstance(value, str):
        raw_values = value.split(",")
    elif isinstance(value, list):
        raw_values = value
    else:
        raise UnsupportedNatVariantError(f"{label} must be any, an IP/CIDR, or a list")

    values = [item.strip() if isinstance(item, str) else item for item in raw_values]
    normalized_values = [str(item).lower() for item in values if isinstance(item, str)]
    if any(item in _BROAD_SOURCE_VALUES for item in normalized_values):
        if any(item not in _BROAD_SOURCE_VALUES for item in normalized_values):
            raise UnsupportedNatVariantError(f"{label} mixes unrestricted and restricted sources")
        return {"addresses": []}

    addresses: list[str] = []
    for index, source in enumerate(values):
        try:
            normalized, _family = _canonical_address(
                source,
                f"{label}[{index}]",
                allow_network=True,
            )
        except NatError as exc:
            raise UnsupportedNatVariantError(str(exc)) from exc
        if normalized not in addresses:
            addresses.append(normalized)
    return {"addresses": sorted(addresses)}


def _controller_origin(value: Mapping[str, Any]) -> str:
    """Return a conservative ownership marker for a legacy controller rule."""
    raw_origin = value.get("setting_preference", value.get("origin"))
    if raw_origin is None:
        return "UNKNOWN"
    normalized = str(raw_origin).strip().upper().replace("-", "_")
    if normalized in {"MANUAL", "USER", "USER_DEFINED", "CUSTOM"}:
        return "USER_DEFINED"
    if normalized in {"AUTO", "DEFAULT", "SYSTEM", "SYSTEM_DEFINED", "GENERATED"}:
        return "SYSTEM_DEFINED"
    return "UNKNOWN"


def normalize_controller_nat(
    value: Mapping[str, Any],
    label: str = "controller.nat",
) -> dict[str, Any]:
    """Normalize one classic ``rest/portforward`` response.

    The local classic endpoint uses legacy field names and string ports. Only
    the proven mapping fields are translated; counters and UI-only fields are
    intentionally discarded. Missing identifiers or unsupported variants fail
    closed so later mutation code cannot target an ambiguous rule.
    """
    controller = _mapping(value, label)
    object_id = controller.get("_id", controller.get("id"))
    try:
        object_id = _string(object_id, f"{label}._id")
        name = _string(controller.get("name"), f"{label}.name")
        interface = _string(controller.get("pfwd_interface"), f"{label}.pfwd_interface")
        private_address = _string(controller.get("fwd"), f"{label}.fwd")
    except NatError as exc:
        raise UnsupportedNatVariantError(str(exc)) from exc

    raw_protocol = controller.get("proto")
    if not isinstance(raw_protocol, str):
        raise UnsupportedNatVariantError(f"{label}.proto must be tcp, udp or tcp_udp")
    protocol = _CONTROLLER_PROTOCOLS.get(raw_protocol.strip().lower())
    if protocol is None:
        raise UnsupportedNatVariantError(
            f"{label}.proto is unsupported: {raw_protocol.strip() or '<empty>'}"
        )

    enabled = controller.get("enabled", True)
    if not isinstance(enabled, bool):
        raise UnsupportedNatVariantError(f"{label}.enabled must be a boolean")

    public_address: str | None = None
    raw_public_address = controller.get("dst")
    if raw_public_address is not None:
        if not isinstance(raw_public_address, str):
            raise UnsupportedNatVariantError(f"{label}.dst must be an IP address or any")
        public_text = raw_public_address.strip()
        if public_text and public_text.lower() not in _BROAD_SOURCE_VALUES:
            try:
                public_address = str(ipaddress.ip_address(public_text))
            except ValueError as exc:
                raise UnsupportedNatVariantError(
                    f"{label}.dst must be an IP address or any"
                ) from exc

    portable: dict[str, Any] = {
        "name": name,
        "enabled": enabled,
        "protocol": protocol,
        "public": {
            "interface": interface,
            "port": _controller_port(controller.get("dst_port"), f"{label}.dst_port"),
        },
        "source": _controller_source(controller.get("src"), f"{label}.src"),
        "private": {
            "address": private_address,
            "port": _controller_port(controller.get("fwd_port"), f"{label}.fwd_port"),
        },
        "hairpin": controller.get("hairpin", False),
    }
    if public_address is not None:
        portable["public"]["address"] = public_address
    if controller.get("description") is not None:
        portable["description"] = controller.get("description")

    try:
        normalized = normalize_nat_mapping(portable, label)
    except NatError as exc:
        raise UnsupportedNatVariantError(f"{label} is unsupported: {exc}") from exc
    normalized.update({"_id": object_id, "_origin": _controller_origin(controller)})
    return normalized


def normalize_controller_nat_list(
    value: Any,
    label: str = "controller.nat",
) -> list[dict[str, Any]]:
    """Normalize and deterministically order one classic inventory response."""
    if isinstance(value, Mapping):
        value = value.get("data")
    if not isinstance(value, list):
        raise UnsupportedNatVariantError(f"{label} must be a list response")

    normalized = [
        normalize_controller_nat(item, f"{label}[{index}]") for index, item in enumerate(value)
    ]
    identities = [nat_mapping_identity(item) for item in normalized]
    if len(set(identities)) != len(identities):
        raise UnsupportedNatVariantError(f"{label} contains duplicate mapping names")
    return sorted(normalized, key=lambda item: (item["name"], item["_id"]))


def nat_export_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    """Return one portable NAT mapping without live controller metadata."""
    portable = {key: value[key] for key in NAT_MAPPING_KEYS if key in value}
    return normalize_nat_mapping(portable, "nat export")


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
    "nat_export_mapping",
    "normalize_controller_nat",
    "normalize_controller_nat_list",
    "normalize_nat_mapping",
    "normalize_nat_port",
    "validate_nat",
]
