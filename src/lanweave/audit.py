"""Declared-versus-live drift auditing for portable Lanweave resources."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from enum import StrEnum
from typing import Any

from .adapters import Adapter, AdapterError
from .contracts import AUDIT_FORMAT_VERSION
from .dns import DnsError, validate_dns_records
from .export import export_config
from .firewall import FirewallError, validate_firewall
from .nat import NatError, validate_nat
from .profiles import TargetIdentity
from .vpn import VpnError, validate_vpn

AUDIT_RESOURCE_ORDER = ("networks", "wlans", "dns", "firewall", "nat", "vpn")
REQUIRED_RESOURCES = ("networks", "wlans")
OPTIONAL_RESOURCES = tuple(
    resource for resource in AUDIT_RESOURCE_ORDER if resource not in REQUIRED_RESOURCES
)

_SENSITIVE_KEYS = {
    "api_key",
    "password",
    "password_env",
    "passphrase",
    "private_key",
    "preshared_key",
    "qr_code",
    "secret",
    "token",
    "profile",
    "configuration",
    "x_iapp_key",
    "x_passphrase",
}
_IDENTIFIER_KEYS = {
    "_id",
    "id",
    "site_id",
    "host_id",
    "networkconf_id",
    "uplink_device_id",
    "zone_id",
    "source_zone_id",
    "destination_zone_id",
}
_STATE_ORDER = {
    "in-sync": 0,
    "drifted": 1,
    "unsupported": 2,
    "unknown": 3,
}


class AuditState(StrEnum):
    """Stable states exposed by the audit JSON contract."""

    IN_SYNC = "in-sync"
    DRIFTED = "drifted"
    UNKNOWN = "unknown"
    UNSUPPORTED = "unsupported"


class AuditError(ValueError):
    """Raised when a portable state cannot be audited safely."""


def _safe(value: Any) -> Any:
    """Return a JSON-safe value without credentials or controller metadata."""
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for raw_key, child in value.items():
            key = str(raw_key)
            normalized_key = key.lower()
            if normalized_key in _SENSITIVE_KEYS or normalized_key in _IDENTIFIER_KEYS:
                continue
            if normalized_key.startswith("_") and normalized_key.endswith("origin"):
                continue
            result[key] = _safe(child)
        return result
    if isinstance(value, (list, tuple)):
        return [_safe(child) for child in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AuditError(f"{label} must be a non-empty string")
    return value.strip()


def _canonical_network(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise AuditError(f"{label} must be a mapping")
    result: dict[str, Any] = {
        "name": _text(value.get("name"), f"{label}.name"),
        "purpose": _text(value.get("purpose", "corporate"), f"{label}.purpose"),
        "vlan": int(value.get("vlan") or 1),
    }
    for key in ("subnet", "domain_name"):
        if value.get(key) is not None:
            result[key] = value[key]

    raw_dhcp = value.get("dhcp")
    if raw_dhcp is not None:
        if not isinstance(raw_dhcp, Mapping):
            raise AuditError(f"{label}.dhcp must be a mapping")
        if raw_dhcp.get("enabled", False):
            dhcp: dict[str, Any] = {"enabled": True}
            for key in ("start", "stop", "lease_time"):
                if raw_dhcp.get(key) is not None:
                    dhcp[key] = raw_dhcp[key]
            if raw_dhcp.get("dns"):
                dhcp["dns"] = sorted(str(server) for server in raw_dhcp["dns"])
            result["dhcp"] = dhcp

    raw_ipv6 = value.get("ipv6")
    if raw_ipv6 is not None:
        if not isinstance(raw_ipv6, Mapping):
            raise AuditError(f"{label}.ipv6 must be a mapping")
        if raw_ipv6.get("enabled", False):
            ipv6: dict[str, Any] = {"enabled": True}
            if raw_ipv6.get("type") is not None:
                ipv6["type"] = raw_ipv6["type"]
            result["ipv6"] = ipv6
    return result


def _canonical_wlan(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise AuditError(f"{label} must be a mapping")
    name = _text(value.get("name"), f"{label}.name")
    security = _text(value.get("security", "open"), f"{label}.security")
    result: dict[str, Any] = {
        "name": name,
        "ssid": _text(value.get("ssid", name), f"{label}.ssid"),
        "network": _text(value.get("network", "Default"), f"{label}.network"),
        "bands": sorted(dict.fromkeys(str(band) for band in value.get("bands", []))),
        "security": security,
        "enabled": bool(value.get("enabled", True)),
        "hide_ssid": bool(value.get("hide_ssid", False)),
        "fast_roaming": bool(value.get("fast_roaming", False)),
        "proxy_arp": bool(value.get("proxy_arp", False)),
        "pmf": str(value.get("pmf", "optional")),
        "client_isolation": bool(value.get("client_isolation", False)),
        "multicast_enhancement": bool(value.get("multicast_enhancement", False)),
        "schedule_enabled": bool(value.get("schedule_enabled", False)),
    }
    if security != "open":
        # Credential values and environment variable names are deliberately
        # absent. The audit only proves that a protected WLAN remains managed.
        result["credential_managed"] = True
    return result


def _canonical_firewall(value: Any, network_names: set[str]) -> dict[str, Any]:
    try:
        normalized = validate_firewall(value, network_names=network_names)
    except FirewallError as exc:
        raise AuditError(str(exc)) from None
    result = {
        "zones": sorted(normalized["zones"], key=lambda item: str(item["name"])),
        "address_groups": sorted(normalized["address_groups"], key=lambda item: str(item["name"])),
        "port_groups": sorted(normalized["port_groups"], key=lambda item: str(item["name"])),
        "rules": sorted(
            normalized["rules"],
            key=lambda item: (
                str(item["source"]["zone"]),
                str(item["destination"]["zone"]),
                str(item["placement"]),
                int(item["order"]),
                str(item["name"]),
            ),
        ),
    }
    return _safe(result)


def _canonical_nat(value: Any, network_names: set[str]) -> list[dict[str, Any]]:
    try:
        normalized = validate_nat(value, network_names=network_names)
    except NatError as exc:
        raise AuditError(str(exc)) from None
    return _safe(sorted(normalized, key=lambda item: str(item["name"])))


def _canonical_vpn(value: Any) -> dict[str, Any]:
    try:
        normalized = validate_vpn(value)
    except VpnError as exc:
        raise AuditError(str(exc)) from None
    resources: dict[str, list[dict[str, Any]]] = {}
    for key in ("servers", "site_to_site_tunnels", "routes"):
        items = []
        for item in normalized[key]:
            normalized_item = dict(item)
            if key in {"servers", "site_to_site_tunnels"}:
                normalized_item.setdefault("enabled", True)
            items.append(normalized_item)
        resources[key] = sorted(items, key=lambda item: str(item["name"]))
    return _safe(resources)


def canonical_resource(resource: str, value: Any, *, network_names: set[str]) -> Any:
    """Canonicalize one desired or observed portable resource family."""
    if resource == "networks":
        return sorted(
            (_canonical_network(item, f"{resource}[{index}]") for index, item in enumerate(value)),
            key=lambda item: item["name"],
        )
    if resource == "wlans":
        return sorted(
            (_canonical_wlan(item, f"{resource}[{index}]") for index, item in enumerate(value)),
            key=lambda item: item["name"],
        )
    if resource == "dns":
        try:
            normalized = validate_dns_records(value)
        except DnsError as exc:
            raise AuditError(str(exc)) from None
        return _safe(sorted(normalized, key=lambda item: (item["name"], item["type"])))
    if resource == "firewall":
        return _canonical_firewall(value, network_names)
    if resource == "nat":
        return _canonical_nat(value, network_names)
    if resource == "vpn":
        return _canonical_vpn(value)
    raise AuditError(f"unsupported audit resource: {resource}")


def _field_paths(expected: Any, observed: Any, prefix: str = "") -> list[str]:
    if isinstance(expected, Mapping) and isinstance(observed, Mapping):
        paths: list[str] = []
        for key in sorted(set(expected) | set(observed), key=str):
            child_prefix = f"{prefix}.{key}" if prefix else str(key)
            if key not in expected or key not in observed:
                paths.append(child_prefix)
            else:
                paths.extend(_field_paths(expected[key], observed[key], child_prefix))
        return paths
    if expected != observed:
        return [prefix or "value"]
    return []


def _identity(resource: str, value: Mapping[str, Any]) -> str:
    if resource == "dns":
        return f"{value.get('name')} [{value.get('type')}]"
    return str(value.get("name", "<unnamed>"))


def _collection_items(resource: str, value: Any) -> list[dict[str, Any]]:
    if resource in {"firewall", "vpn"}:
        items: list[dict[str, Any]] = []
        sections = (
            ("zones", "address_groups", "port_groups", "rules")
            if resource == "firewall"
            else ("servers", "site_to_site_tunnels", "routes")
        )
        for section in sections:
            for item in value.get(section, []):
                items.append({"_section": section, **item})
        return items
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise AuditError(f"{resource} must be a list")
    return [dict(item) for item in value]


def _compare_resource(resource: str, desired: Any, observed: Any) -> dict[str, Any]:
    desired_items = _collection_items(resource, desired)
    observed_items = _collection_items(resource, observed)
    desired_by_id = {
        (_identity(resource, item), item.get("_section")): item for item in desired_items
    }
    observed_by_id = {
        (_identity(resource, item), item.get("_section")): item for item in observed_items
    }
    findings: list[dict[str, Any]] = []
    for identity in sorted(set(desired_by_id) | set(observed_by_id), key=str):
        expected = desired_by_id.get(identity)
        actual = observed_by_id.get(identity)
        name = identity[0]
        section = identity[1]
        label = f"{section}/{name}" if section else name
        if expected is None:
            findings.append({"kind": "extra", "name": label})
        elif actual is None:
            findings.append({"kind": "missing", "name": label})
        else:
            fields = _field_paths(expected, actual)
            if section:
                fields = [field for field in fields if field != "_section"]
            if fields:
                findings.append({"kind": "changed", "name": label, "fields": fields})
    state = AuditState.DRIFTED if findings else AuditState.IN_SYNC
    return {
        "resource": resource,
        "state": state.value,
        "declared_count": len(desired_items),
        "observed_count": len(observed_items),
        "declared": _safe(desired),
        "observed": _safe(observed),
        "findings": findings,
    }


def _network_coverage(desired: Any) -> dict[str, str] | None:
    """Describe the intentional WAN boundary of the portable network export."""
    if not isinstance(desired, Sequence) or isinstance(desired, (str, bytes, bytearray)):
        return None
    if any(item.get("purpose") == "wan" for item in desired if isinstance(item, Mapping)):
        return {
            "status": AuditState.UNKNOWN.value,
            "reason": "wan_networks_not_reported_by_portable_export",
        }
    return None


def _reason_for_exception(exc: Exception) -> str:
    if isinstance(exc, AdapterError):
        return exc.code
    if isinstance(exc, (AuditError, DnsError, FirewallError, NatError, VpnError)):
        return "invalid_live_state"
    return "live_observation_failed"


def _capability_supports(client: Adapter, resource: str) -> bool:
    capabilities = getattr(client, "capabilities", None)
    if capabilities is not None:
        return capabilities.supports(resource, "export")
    if resource == "firewall":
        return all(
            callable(getattr(client, method, None))
            for method in (
                "firewall_zones",
                "firewall_traffic_matching_lists",
                "firewall_policies",
                "firewall_policy_ordering",
            )
        )
    method_by_resource = {
        "networks": "networks",
        "wlans": "wlans",
        "dns": "dns",
        "nat": "nat",
        "vpn": "vpn",
    }
    return callable(getattr(client, method_by_resource[resource], None))


def _unavailable(resource: str, state: AuditState, reason: str, desired: Any) -> dict[str, Any]:
    return {
        "resource": resource,
        "state": state.value,
        "declared_count": _count_items(resource, desired),
        "observed_count": None,
        "declared": _safe(desired),
        "observed": None,
        "findings": [],
        "coverage": {"status": state.value, "reason": reason},
    }


def _count_items(resource: str, value: Any) -> int:
    if resource in {"firewall", "vpn"} and isinstance(value, Mapping):
        sections = (
            ("zones", "address_groups", "port_groups", "rules")
            if resource == "firewall"
            else ("servers", "site_to_site_tunnels", "routes")
        )
        return sum(len(value.get(section, [])) for section in sections)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return len(value)
    return 0


def _overall_state(resources: Sequence[Mapping[str, Any]]) -> AuditState:
    if not resources:
        return AuditState.IN_SYNC
    state = max(
        (AuditState(item["state"]) for item in resources),
        key=lambda item: _STATE_ORDER[item.value],
    )
    return state


def audit_exit_code(result: Mapping[str, Any]) -> int:
    """Return the CI exit code for an audit result envelope."""
    if result.get("state") == AuditState.IN_SYNC.value:
        return 0
    if result.get("state") == AuditState.DRIFTED.value:
        return 1
    return 2


def audit_config(
    client: Adapter,
    config: Mapping[str, Any],
    *,
    target: TargetIdentity | None = None,
    resources: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Compare declared portable resources with a secret-free live export.

    ``resources`` narrows the readback to selected resource families. The
    default keeps the v0.8 full-audit behavior; post-apply verification uses
    the narrowed form so unrelated endpoints cannot obscure the result.
    """
    if resources is None:
        selected_resources = [
            *REQUIRED_RESOURCES,
            *(resource for resource in OPTIONAL_RESOURCES if resource in config),
        ]
    else:
        selected_resources = list(dict.fromkeys(resources))
        unknown = set(selected_resources) - set(AUDIT_RESOURCE_ORDER)
        if unknown:
            names = ", ".join(sorted(unknown))
            raise AuditError(f"unsupported audit resource(s): {names}")
        if not selected_resources:
            raise AuditError("at least one audit resource is required")

    network_names = {
        str(item.get("name")) for item in config.get("networks", []) if isinstance(item, Mapping)
    }
    desired: dict[str, Any] = {}
    for resource in selected_resources:
        raw = config.get(resource, [] if resource != "firewall" and resource != "vpn" else None)
        desired[resource] = canonical_resource(resource, raw, network_names=network_names)

    results: list[dict[str, Any]] = []
    supported_resources: list[str] = []
    for resource in selected_resources:
        if _capability_supports(client, resource):
            supported_resources.append(resource)
        else:
            results.append(
                _unavailable(
                    resource,
                    AuditState.UNSUPPORTED,
                    "unsupported_export_capability",
                    desired[resource],
                )
            )

    if supported_resources:
        try:
            observed_config = export_config(client, resources=supported_resources)
        except Exception as exc:
            reason = _reason_for_exception(exc)
            results.extend(
                _unavailable(resource, AuditState.UNKNOWN, reason, desired[resource])
                for resource in supported_resources
            )
        else:
            for resource in supported_resources:
                try:
                    observed = canonical_resource(
                        resource,
                        observed_config.get(resource),
                        network_names=network_names,
                    )
                except Exception as exc:
                    results.append(
                        _unavailable(
                            resource,
                            AuditState.UNKNOWN,
                            _reason_for_exception(exc),
                            desired[resource],
                        )
                    )
                else:
                    comparison = _compare_resource(resource, desired[resource], observed)
                    if resource == "networks":
                        coverage = _network_coverage(desired[resource])
                        if coverage is not None:
                            comparison["state"] = AuditState.UNKNOWN.value
                            comparison["coverage"] = coverage
                    if resource == "vpn" and desired[resource]["routes"] and not observed["routes"]:
                        comparison["state"] = AuditState.UNKNOWN.value
                        comparison["coverage"] = {
                            "status": AuditState.UNKNOWN.value,
                            "reason": "routes_not_reported_by_official_overview_api",
                        }
                    results.append(comparison)

    results.sort(key=lambda item: AUDIT_RESOURCE_ORDER.index(item["resource"]))
    summary = {
        state.value: sum(item["state"] == state.value for item in results) for state in AuditState
    }
    result: dict[str, Any] = {
        "format_version": AUDIT_FORMAT_VERSION,
        "read_only": True,
        "state": _overall_state(results).value,
        "summary": summary,
        "resources": results,
    }
    capabilities = getattr(client, "capabilities", None)
    if capabilities is not None:
        result["capabilities"] = capabilities.to_dict()
    if target is not None:
        result["target"] = target.to_dict()
    return result


__all__ = [
    "AUDIT_FORMAT_VERSION",
    "AUDIT_RESOURCE_ORDER",
    "AuditError",
    "AuditState",
    "audit_config",
    "audit_exit_code",
    "canonical_resource",
]
