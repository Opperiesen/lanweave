"""Portable DNS records and the UniFi Integration API normalization boundary."""

from __future__ import annotations

import ipaddress
import re
from collections.abc import Mapping, Sequence
from typing import Any

SUPPORTED_DNS_TYPES = frozenset({"A", "AAAA", "CNAME"})
API_DNS_TYPES = {
    "A": "A_RECORD",
    "AAAA": "AAAA_RECORD",
    "CNAME": "CNAME_RECORD",
}
DNS_TYPES_FROM_API = {value: key for key, value in API_DNS_TYPES.items()}
DNS_RECORD_KEYS = {"name", "type", "address", "target", "ttl_seconds", "enabled"}
DNS_INTERNAL_KEYS = {"_id", "_origin"}
DNS_DEFAULT_TTL = 300
DNS_TTL_LIMITS = {"A": 86400, "AAAA": 86400, "CNAME": 604800}
DNS_USER_ORIGINS = frozenset({"USER", "USER_DEFINED", "CUSTOM"})
_HOST_LABEL_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")


class DnsError(RuntimeError):
    """Raised when a DNS record is malformed or cannot be managed safely."""


class UnsupportedDnsRecordError(DnsError):
    """Raised for a controller DNS policy outside the v0.4 portable model."""


def canonical_hostname(value: Any, label: str = "DNS name") -> str:
    """Return one lowercase, dot-normalized ASCII hostname."""
    if not isinstance(value, str) or not value.strip():
        raise DnsError(f"{label} must be a non-empty hostname")
    hostname = value.strip().lower()
    if hostname.endswith("."):
        hostname = hostname[:-1]
    if not hostname or len(hostname) > 253 or "*" in hostname:
        raise DnsError(f"{label} must be a hostname without wildcards")
    labels = hostname.split(".")
    if any(not _HOST_LABEL_RE.fullmatch(part) for part in labels):
        raise DnsError(f"{label} contains an invalid hostname label")
    return hostname


def _record_type(value: Any, label: str) -> str:
    if not isinstance(value, str) or value.strip().upper() not in SUPPORTED_DNS_TYPES:
        allowed = ", ".join(sorted(SUPPORTED_DNS_TYPES))
        raise DnsError(f"{label}.type must be one of: {allowed}")
    return value.strip().upper()


def _ttl(value: Any, record_type: str, label: str) -> int:
    if value is None:
        return DNS_DEFAULT_TTL
    if isinstance(value, bool) or not isinstance(value, int):
        raise DnsError(f"{label}.ttl_seconds must be a positive integer")
    if not 1 <= value <= DNS_TTL_LIMITS[record_type]:
        raise DnsError(f"{label}.ttl_seconds must be between 1 and {DNS_TTL_LIMITS[record_type]}")
    return value


def _address(value: Any, version: int, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DnsError(f"{label} must be an IPv{version} address")
    try:
        parsed = ipaddress.ip_address(value.strip())
    except ValueError as exc:
        raise DnsError(f"{label} must be an IPv{version} address") from exc
    if parsed.version != version:
        raise DnsError(f"{label} must be an IPv{version} address")
    return str(parsed)


def normalize_dns_record(value: Mapping[str, Any], label: str = "dns") -> dict[str, Any]:
    """Validate and canonicalize one portable desired DNS record."""
    if not isinstance(value, Mapping):
        raise DnsError(f"{label} must be a mapping")
    unknown = sorted(set(value) - DNS_RECORD_KEYS - DNS_INTERNAL_KEYS, key=str)
    if unknown:
        raise DnsError(f"unsupported field(s) in {label}: {', '.join(map(str, unknown))}")
    record_type = _record_type(value.get("type"), label)
    name = canonical_hostname(value.get("name"), f"{label}.name")
    address = value.get("address")
    target = value.get("target")
    if record_type == "A":
        if target is not None:
            raise DnsError(f"{label}.target is not valid for A records")
        address = _address(address, 4, f"{label}.address")
    elif record_type == "AAAA":
        if target is not None:
            raise DnsError(f"{label}.target is not valid for AAAA records")
        address = _address(address, 6, f"{label}.address")
    else:
        if address is not None:
            raise DnsError(f"{label}.address is not valid for CNAME records")
        target = canonical_hostname(target, f"{label}.target")
    if "enabled" in value and not isinstance(value["enabled"], bool):
        raise DnsError(f"{label}.enabled must be a boolean")
    result: dict[str, Any] = {
        "name": name,
        "type": record_type,
        "ttl_seconds": _ttl(value.get("ttl_seconds"), record_type, label),
        "enabled": value.get("enabled", True),
    }
    if record_type in {"A", "AAAA"}:
        result["address"] = address
    else:
        result["target"] = target
    return result


def validate_dns_records(records: Any, label: str = "dns") -> list[dict[str, Any]]:
    """Return canonical records and reject ambiguous identities or aliases."""
    if not isinstance(records, Sequence) or isinstance(records, (str, bytes, bytearray)):
        raise DnsError(f"{label} must be a list")
    normalized = [
        normalize_dns_record(record, f"{label}[{index}]") for index, record in enumerate(records)
    ]
    identities: set[tuple[str, str]] = set()
    types_by_name: dict[str, set[str]] = {}
    for record in normalized:
        identity = dns_record_identity(record)
        if identity in identities:
            raise DnsError(f"duplicate DNS identity: {record['name']} ({record['type']})")
        identities.add(identity)
        types_by_name.setdefault(record["name"], set()).add(record["type"])
    for name, types in types_by_name.items():
        if "CNAME" in types and len(types) > 1:
            raise DnsError(f"CNAME cannot coexist with another record type for {name}")
    return normalized


def dns_record_identity(record: Mapping[str, Any]) -> tuple[str, str]:
    """Return the stable identity used by planning and ownership checks."""
    return (str(record["name"]), str(record["type"]))


def dns_display_name(record: Mapping[str, Any]) -> str:
    return f"{record['name']} [{record['type']}]"


def dns_to_unifi(record: Mapping[str, Any]) -> dict[str, Any]:
    """Convert a canonical portable record to the Integration API payload."""
    normalized = normalize_dns_record(record)
    record_type = normalized["type"]
    payload: dict[str, Any] = {
        "type": API_DNS_TYPES[record_type],
        "enabled": normalized["enabled"],
        "domain": normalized["name"],
        "ttlSeconds": normalized["ttl_seconds"],
    }
    if record_type == "A":
        payload["ipv4Address"] = normalized["address"]
    elif record_type == "AAAA":
        payload["ipv6Address"] = normalized["address"]
    else:
        payload["targetDomain"] = normalized["target"]
    return payload


def normalize_controller_dns(
    value: Mapping[str, Any], label: str = "controller.dns"
) -> dict[str, Any]:
    """Normalize one Integration API DNS policy while retaining safe metadata."""
    if not isinstance(value, Mapping):
        raise DnsError(f"{label} must be a mapping")
    api_type = str(value.get("type") or "").strip().upper()
    record_type = DNS_TYPES_FROM_API.get(api_type)
    if record_type is None:
        raise UnsupportedDnsRecordError(
            f"unsupported controller DNS record type: {api_type or 'missing'}"
        )
    portable: dict[str, Any] = {
        "name": value.get("domain"),
        "type": record_type,
        "enabled": value.get("enabled", True),
        "ttl_seconds": value.get("ttlSeconds", DNS_DEFAULT_TTL),
    }
    if record_type == "A":
        portable["address"] = value.get("ipv4Address")
    elif record_type == "AAAA":
        portable["address"] = value.get("ipv6Address")
    else:
        portable["target"] = value.get("targetDomain")
    normalized = normalize_dns_record(portable, label)
    origin_value = (
        value.get("metadata", {}).get("origin")
        if isinstance(value.get("metadata"), Mapping)
        else None
    )
    origin = str(origin_value or "").strip().upper() or "UNKNOWN"
    normalized["_id"] = value.get("id") or value.get("_id")
    normalized["_origin"] = origin
    return normalized


def normalize_controller_dns_list(values: Any) -> list[dict[str, Any]]:
    """Keep supported controller records and ignore unsupported policy families."""
    if not isinstance(values, list):
        raise DnsError("controller DNS response must be a list")
    normalized: list[dict[str, Any]] = []
    for index, value in enumerate(values):
        try:
            normalized.append(normalize_controller_dns(value, f"controller.dns[{index}]"))
        except UnsupportedDnsRecordError:
            continue
    identities: set[tuple[str, str]] = set()
    for record in normalized:
        identity = dns_record_identity(record)
        if identity in identities:
            raise DnsError(
                f"controller returned duplicate DNS identity: {dns_display_name(record)}"
            )
        identities.add(identity)
    return sorted(normalized, key=dns_record_identity)


def dns_is_user_managed(record: Mapping[str, Any]) -> bool:
    """Return whether a controller record is safe for Lanweave mutation."""
    return str(record.get("_origin", "UNKNOWN")).upper() in DNS_USER_ORIGINS


def dns_export_record(record: Mapping[str, Any]) -> dict[str, Any]:
    """Strip controller identity and origin from a canonical live record."""
    normalized = normalize_dns_record(record)
    return normalized


__all__ = [
    "API_DNS_TYPES",
    "DNS_DEFAULT_TTL",
    "DNS_RECORD_KEYS",
    "DNS_TTL_LIMITS",
    "DNS_TYPES_FROM_API",
    "DNS_USER_ORIGINS",
    "DnsError",
    "SUPPORTED_DNS_TYPES",
    "UnsupportedDnsRecordError",
    "canonical_hostname",
    "dns_display_name",
    "dns_export_record",
    "dns_is_user_managed",
    "dns_record_identity",
    "dns_to_unifi",
    "normalize_controller_dns",
    "normalize_controller_dns_list",
    "normalize_dns_record",
    "validate_dns_records",
]
