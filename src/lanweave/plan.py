"""Declarative planning and application for networks and WLANs."""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit

from .adapters import Adapter
from .contracts import PLAN_FORMAT_VERSION
from .dns import (
    dns_display_name,
    dns_is_user_managed,
    dns_record_identity,
    dns_to_unifi,
    validate_dns_records,
)
from .firewall import (
    FirewallError,
    firewall_group_to_unifi,
    firewall_is_user_managed,
    firewall_policy_to_portable,
    firewall_rule_is_broad,
    firewall_rule_match_key,
    firewall_rule_to_unifi,
    firewall_zone_to_unifi,
    validate_firewall,
)
from .nat import (
    NatError,
    analyze_nat_exposure,
    nat_export_mapping,
    nat_is_user_managed,
    nat_to_unifi,
    validate_nat_conflicts,
)
from .profiles import TargetIdentity
from .resources import DependencyGraph, ResourceContractError, ResourceKey
from .vpn import plan_observation, validate_vpn

SENSITIVE_FIELDS = {
    "api_key",
    "password",
    "passphrase",
    "private_key",
    "secret",
    "token",
    "x_iapp_key",
    "x_passphrase",
}
READ_ONLY_FIELDS = {
    "_id",
    "id",
    "site_id",
    "attr_no_delete",
    "attr_hidden_id",
    "attr_hidden",
}


def _object_id(value: dict[str, Any]) -> str | None:
    identifier = value.get("_id") or value.get("id")
    return str(identifier) if identifier else None


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: "***" if str(key).lower() in SENSITIVE_FIELDS else _redact(child)
            for key, child in value.items()
        }
    if isinstance(value, list):
        return [_redact(child) for child in value]
    return value


def _subnet_to_gateway(subnet: str | None) -> str | None:
    if not subnet:
        return None
    network = ipaddress.ip_network(subnet, strict=False)
    if isinstance(network, ipaddress.IPv4Network):
        return f"{network.network_address + 1}/{network.prefixlen}"
    return f"{network.network_address}/{network.prefixlen}"


def network_to_unifi(network: dict[str, Any]) -> dict[str, Any]:
    """Convert the portable network model to the classic Network API payload."""
    dhcp = network.get("dhcp") or {}
    ipv6 = network.get("ipv6") or {}
    vlan = network.get("vlan", 1)
    payload: dict[str, Any] = {
        "name": network["name"],
        "purpose": network["purpose"],
        "vlan_enabled": vlan != 1,
        "vlan": str(vlan) if vlan != 1 else None,
        "ip_subnet": _subnet_to_gateway(network.get("subnet")),
        "domain_name": network.get("domain_name"),
        "dhcpd_enabled": bool(dhcp.get("enabled", False)),
        "dhcpd_start": dhcp.get("start"),
        "dhcpd_stop": dhcp.get("stop"),
        "dhcpd_leasetime": dhcp.get("lease_time"),
        "dhcpd_dns_enabled": bool(dhcp.get("dns")),
        "ipv6_interface_type": ipv6.get("type") if ipv6.get("enabled") else "none",
    }
    for index, dns in enumerate(dhcp.get("dns") or [], start=1):
        payload[f"dhcpd_dns_{index}"] = dns
    return {key: value for key, value in payload.items() if value is not None}


def wlan_to_unifi(
    wlan: dict[str, Any],
    networks_by_name: dict[str, str],
) -> dict[str, Any]:
    """Convert the portable WLAN model to a classic Network API payload."""
    bands = wlan.get("bands", ["5g"])
    band_set = set(bands)
    if band_set == {"2g"}:
        wlan_band = "2g"
    elif band_set == {"5g"}:
        wlan_band = "5g"
    elif band_set == {"6g"}:
        wlan_band = "6g"
    else:
        wlan_band = "both"

    network_name = wlan["network"]
    payload: dict[str, Any] = {
        "name": wlan["ssid"],
        "enabled": wlan.get("enabled", True),
        "is_guest": "guest" in network_name.lower(),
        "networkconf_id": networks_by_name.get(network_name, ""),
        "wlan_band": wlan_band,
        "wlan_bands": bands,
        "hide_ssid": wlan.get("hide_ssid", False),
        "fast_roaming_enabled": wlan.get("fast_roaming", False),
        "proxy_arp": wlan.get("proxy_arp", False),
        "l2_isolation": wlan.get("client_isolation", False),
        "mcastenhance_enabled": wlan.get("multicast_enhancement", False),
        "schedule_enabled": wlan.get("schedule_enabled", False),
    }

    security = wlan.get("security", "open")
    password = wlan.get("password")
    pmf = wlan.get("pmf", "optional")
    if security == "open":
        payload.update(
            {
                "security": "open",
                "wpa3_support": False,
                "wpa3_transition": False,
            }
        )
    elif security == "wpa2":
        payload.update(
            {
                "security": "wpapsk",
                "wpa_mode": "wpa2",
                "wpa_enc": "ccmp",
                "wpa3_support": False,
                "wpa3_transition": False,
                "pmf_mode": pmf if pmf in {"disabled", "optional"} else "disabled",
            }
        )
    elif security == "wpa3-transition":
        payload.update(
            {
                "security": "wpapsk",
                "wpa_mode": "wpa2",
                "wpa_enc": "ccmp",
                "wpa3_support": True,
                "wpa3_transition": True,
                "pmf_mode": pmf if pmf != "disabled" else "optional",
            }
        )
    elif security == "wpa3":
        payload.update(
            {
                "security": "wpapsk",
                "wpa_mode": "wpa2",
                "wpa_enc": "ccmp",
                "wpa3_support": True,
                "wpa3_transition": False,
                "wpa3_fast_roaming": wlan.get("fast_roaming", False),
                "pmf_mode": "required",
            }
        )
    else:
        raise ValueError(f"unsupported WLAN security mode: {security}")

    if password:
        payload["x_passphrase"] = password
    return payload


@dataclass
class ResourceDiff:
    kind: str
    action: str
    name: str
    payload: dict[str, Any] = field(default_factory=dict)
    current: dict[str, Any] = field(default_factory=dict)
    object_id: str | None = None
    source: dict[str, Any] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()

    @property
    def changed_fields(self) -> list[str]:
        if self.action == "reorder":
            fields = {"order"}
        elif self.action == "create":
            fields = {key for key in self.payload if key not in SENSITIVE_FIELDS}
        elif self.action == "delete":
            fields = set()
        else:
            fields = {
                key
                for key, value in self.payload.items()
                if key not in SENSITIVE_FIELDS and self.current.get(key) != value
            }
        if any(key in self.payload for key in SENSITIVE_FIELDS):
            fields.add("credentials")
        return sorted(fields)

    def to_dict(self) -> dict[str, Any]:
        result = {
            "kind": self.kind,
            "action": self.action,
            "name": self.name,
            "id": self.object_id,
            "changed_fields": self.changed_fields,
            "payload": _redact(self.payload),
        }
        if self.warnings:
            result["warnings"] = list(self.warnings)
        return result


@dataclass
class Plan:
    diffs: list[ResourceDiff] = field(default_factory=list)
    target: TargetIdentity | None = None
    read_only: dict[str, Any] = field(default_factory=dict)

    def has_changes(self) -> bool:
        return any(diff.action != "noop" for diff in self.diffs)

    def by_action(self, action: str) -> list[ResourceDiff]:
        return [diff for diff in self.diffs if diff.action == action]

    def summary(self) -> dict[str, int]:
        summary = {
            action: len(self.by_action(action)) for action in ("create", "update", "delete", "noop")
        }
        reorder_count = len(self.by_action("reorder"))
        if reorder_count:
            summary["reorder"] = reorder_count
        return summary

    def risk_warnings(self) -> list[str]:
        return [warning for diff in self.diffs for warning in diff.warnings]

    def to_dict(self) -> dict[str, Any]:
        rendered = {
            "format_version": PLAN_FORMAT_VERSION,
            "summary": self.summary(),
            "changes": [diff.to_dict() for diff in self.diffs if diff.action != "noop"],
        }
        if self.read_only:
            rendered["read_only"] = _redact(self.read_only)
        if self.target is not None:
            rendered["target"] = self.target.to_dict()
        return rendered


def _diff_label(diff: ResourceDiff) -> str:
    return f"{diff.kind}/{diff.name}:{diff.action}"


class PlanApplyError(RuntimeError):
    """A plan stopped after a controller operation failed.

    UniFi's classic API is not transactional.  The error therefore records
    only facts that Lanweave can establish: completed operations, the failed
    operation and operations that were not started.  It deliberately omits
    request payloads, response bodies and exception text.
    """

    def __init__(
        self,
        *,
        target: str,
        resource: str,
        operation: str,
        phase: str,
        completed: list[ResourceDiff],
        pending: list[ResourceDiff],
        partial_request: bool,
        cause_type: str,
    ) -> None:
        self.target = target
        self.resource = resource
        self.operation = operation
        self.phase = phase
        self.completed = tuple(_diff_label(diff) for diff in completed)
        self.pending = tuple(_diff_label(diff) for diff in pending)
        self.partial_request = partial_request
        self.cause_type = cause_type
        super().__init__(self._message())

    @property
    def state(self) -> str:
        if self.completed or self.partial_request:
            return "partial"
        return "unknown"

    def _message(self) -> str:
        completed = ", ".join(self.completed) or "none"
        pending = ", ".join(self.pending) or "none"
        return (
            f"apply stopped: target={self.target}; resource={self.resource}; "
            f"operation={self.operation}; phase={self.phase}; state={self.state}; "
            f"completed={completed}; pending={pending}; "
            "automatic_rollback=false; re-read the controller before retrying"
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a safe, machine-readable recovery report."""
        return {
            "error": "plan_apply_failed",
            "target": self.target,
            "failed": {
                "resource": self.resource,
                "operation": self.operation,
                "phase": self.phase,
            },
            "state": self.state,
            "confirmed_completed": list(self.completed),
            "uncertain_failed": f"{self.resource}:{self.operation}",
            "not_started": list(self.pending),
            "automatic_rollback": False,
            "recovery": [
                "Read the current controller state again before retrying.",
                "Review the newly generated plan; do not assume the failed request was reverted.",
                "Retry only the reviewed plan. Prune remains opt-in and requires "
                "normal confirmation.",
            ],
        }


class PlanTargetMismatchError(RuntimeError):
    """A target-bound plan does not match the selected live target."""

    def __init__(
        self,
        *,
        expected: TargetIdentity,
        actual: TargetIdentity | None,
    ) -> None:
        self.expected = expected
        self.actual = actual
        super().__init__(self._message())

    def _message(self) -> str:
        actual = self.actual.label() if self.actual is not None else "none"
        return f"plan target mismatch: expected={self.expected.label()}; selected={actual}"

    def to_dict(self) -> dict[str, Any]:
        """Return a deterministic, secret-free mismatch report."""
        return {
            "error": "plan_target_mismatch",
            "expected_target": self.expected.to_dict(),
            "selected_target": self.actual.to_dict() if self.actual is not None else None,
        }


class PlanRiskError(RuntimeError):
    """Raised when a risky Firewall plan has not been explicitly acknowledged."""

    def __init__(self, warnings: list[str]) -> None:
        self.warnings = tuple(dict.fromkeys(warnings))
        super().__init__("firewall risk acknowledgement required")

    def to_dict(self) -> dict[str, Any]:
        return {
            "error": "firewall_risk_acknowledgement_required",
            "warnings": list(self.warnings),
        }


def _index_by_name(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {item["name"]: item for item in items if item.get("name")}


def _significant_diff(desired: dict[str, Any], current: dict[str, Any]) -> bool:
    for key, value in desired.items():
        if key in SENSITIVE_FIELDS:
            # Some controller versions omit passphrases from GET responses.
            # Compare them when present, but do not create a perpetual diff
            # when the API deliberately hides the current value.
            if key in current and current.get(key) != value:
                return True
            continue
        if current.get(key) != value:
            return True
    return False


def _append_resource_plan(
    plan: Plan,
    *,
    kind: str,
    desired: list[dict[str, Any]],
    current: list[dict[str, Any]],
    payload_factory: Any,
    prune: bool,
) -> None:
    current_by_name = _index_by_name(current)
    desired_names: set[str] = set()
    for source in desired:
        payload = payload_factory(source)
        name = payload["name"]
        desired_names.add(name)
        existing = current_by_name.get(name)
        if existing is None:
            plan.diffs.append(
                ResourceDiff(kind=kind, action="create", name=name, payload=payload, source=source)
            )
        elif _significant_diff(payload, existing):
            plan.diffs.append(
                ResourceDiff(
                    kind=kind,
                    action="update",
                    name=name,
                    payload=payload,
                    current=existing,
                    object_id=_object_id(existing),
                    source=source,
                )
            )
        else:
            plan.diffs.append(ResourceDiff(kind=kind, action="noop", name=name, source=source))

    if prune:
        for name, existing in current_by_name.items():
            if name in desired_names:
                continue
            if kind == "network" and existing.get("purpose") == "wan":
                continue
            if kind == "network" and name.lower() == "default":
                continue
            plan.diffs.append(
                ResourceDiff(
                    kind=kind,
                    action="delete",
                    name=name,
                    current=existing,
                    object_id=_object_id(existing),
                )
            )


def _dns_current_payload(record: dict[str, Any]) -> dict[str, Any]:
    """Render a normalized live record for plan comparison and updates."""
    payload = dns_to_unifi(record)
    if record.get("_origin") is not None:
        payload["_origin"] = record["_origin"]
    return payload


def _append_dns_plan(
    plan: Plan,
    *,
    desired: list[dict[str, Any]],
    current: list[dict[str, Any]],
    prune: bool,
) -> None:
    """Append DNS changes while protecting system and unknown-origin records."""
    desired_records = validate_dns_records(desired)
    current_by_identity = {dns_record_identity(record): record for record in current}
    desired_identities = {dns_record_identity(record) for record in desired_records}

    for source in desired_records:
        identity = dns_record_identity(source)
        name = dns_display_name(source)
        existing = current_by_identity.get(identity)
        payload = dns_to_unifi(source)
        if existing is None:
            plan.diffs.append(
                ResourceDiff(kind="dns", action="create", name=name, payload=payload, source=source)
            )
            continue
        current_payload = _dns_current_payload(existing)
        if not _significant_diff(payload, current_payload):
            plan.diffs.append(ResourceDiff(kind="dns", action="noop", name=name, source=source))
            continue
        if not dns_is_user_managed(existing):
            origin = existing.get("_origin", "UNKNOWN")
            raise ResourceContractError(
                f"refusing to mutate DNS record with protected origin {origin}: {name}"
            )
        object_id = _object_id(existing)
        if not object_id:
            raise ResourceContractError(f"managed DNS record has no controller id: {name}")
        plan.diffs.append(
            ResourceDiff(
                kind="dns",
                action="update",
                name=name,
                payload=payload,
                current=current_payload,
                object_id=object_id,
                source=source,
            )
        )

    if not prune:
        return
    for identity in sorted(set(current_by_identity) - desired_identities):
        existing = current_by_identity[identity]
        if not dns_is_user_managed(existing):
            continue
        name = dns_display_name(existing)
        object_id = _object_id(existing)
        if not object_id:
            raise ResourceContractError(f"managed DNS record has no controller id: {name}")
        plan.diffs.append(
            ResourceDiff(
                kind="dns",
                action="delete",
                name=name,
                current=_dns_current_payload(existing),
                object_id=object_id,
            )
        )


def _nat_unique_name_index(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for item in items:
        name = item.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ResourceContractError("NAT mapping is missing a stable name")
        if name in indexed:
            raise ResourceContractError(f"ambiguous NAT mapping name: {name}")
        indexed[name] = item
    return indexed


def _nat_current_payload(mapping: dict[str, Any]) -> dict[str, Any]:
    try:
        return nat_export_mapping(mapping)
    except NatError as exc:
        raise ResourceContractError(f"invalid current NAT mapping {mapping.get('name')}") from exc


def _append_nat_plan(
    plan: Plan,
    *,
    desired: Any,
    current: list[dict[str, Any]],
    network_names: set[str],
    prune: bool,
) -> None:
    try:
        desired_mappings = validate_nat_conflicts(
            desired,
        )
        desired_mappings = [nat_export_mapping(mapping) for mapping in desired_mappings]
        warnings = analyze_nat_exposure(desired_mappings)
    except NatError as exc:
        raise ResourceContractError(str(exc)) from None

    for mapping in desired_mappings:
        private_network = mapping.get("private", {}).get("network")
        if private_network is not None and private_network not in network_names:
            raise ResourceContractError(
                f"NAT mapping refers to an unknown network: {private_network}"
            )

    current_by_name = _nat_unique_name_index(current)
    desired_names = {mapping["name"] for mapping in desired_mappings}
    for source in sorted(desired_mappings, key=lambda item: item["name"]):
        name = source["name"]
        payload = nat_export_mapping(source)
        existing = current_by_name.get(name)
        if existing is None:
            plan.diffs.append(
                ResourceDiff(
                    kind="nat",
                    action="create",
                    name=name,
                    payload=payload,
                    source=source,
                    warnings=warnings[name],
                )
            )
            continue

        current_payload = _nat_current_payload(existing)
        if not _significant_diff(payload, current_payload):
            plan.diffs.append(ResourceDiff(kind="nat", action="noop", name=name, source=source))
            continue
        if not nat_is_user_managed(existing):
            origin = existing.get("_origin", "UNKNOWN")
            raise ResourceContractError(
                f"refusing to mutate NAT mapping with protected origin {origin}: {name}"
            )
        object_id = _object_id(existing)
        if not object_id:
            raise ResourceContractError(f"managed NAT mapping has no controller id: {name}")
        plan.diffs.append(
            ResourceDiff(
                kind="nat",
                action="update",
                name=name,
                payload=payload,
                current=current_payload,
                object_id=object_id,
                source=source,
                warnings=warnings[name],
            )
        )

    if not prune:
        return
    for name in sorted(set(current_by_name) - desired_names):
        existing = current_by_name[name]
        if not nat_is_user_managed(existing):
            continue
        object_id = _object_id(existing)
        if not object_id:
            raise ResourceContractError(f"managed NAT mapping has no controller id: {name}")
        plan.diffs.append(
            ResourceDiff(
                kind="nat",
                action="delete",
                name=name,
                current=_nat_current_payload(existing),
                object_id=object_id,
            )
        )


def _firewall_current_payload(
    zone: dict[str, Any], network_names_by_id: dict[str, str]
) -> dict[str, Any]:
    try:
        networks = [network_names_by_id[identifier] for identifier in zone.get("network_ids", [])]
    except KeyError as exc:
        raise ResourceContractError(
            f"managed firewall zone {zone.get('name')} refers to an unknown network"
        ) from exc
    return {"name": zone["name"], "networks": networks}


def _firewall_group_current_payload(group: dict[str, Any]) -> dict[str, Any]:
    key = "addresses" if group.get("group_type") == "address_group" else "ports"
    if group.get("group_type") not in {"address_group", "port_group"}:
        raise ResourceContractError(f"unsupported firewall group type: {group.get('group_type')}")
    return {"name": group["name"], key: list(group.get("items", []))}


def _firewall_rule_content(rule: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in rule.items() if key not in {"order", "placement"}}


def _firewall_order_position(
    policy: dict[str, Any], ordering: dict[str, list[str]]
) -> tuple[int, str]:
    identifier = str(policy["id"])
    for placement in ("before_system_defined", "after_system_defined"):
        values = ordering.get(placement, [])
        if identifier in values:
            return values.index(identifier), placement
    raise ResourceContractError(
        f"firewall policy ordering does not contain managed policy {policy['name']}"
    )


def _firewall_unique_name_index(
    items: list[dict[str, Any]], resource: str
) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for item in items:
        name = item.get("name")
        if not isinstance(name, str) or not name:
            raise ResourceContractError(f"firewall {resource} is missing a stable name")
        if name in indexed:
            raise ResourceContractError(f"ambiguous firewall {resource} name: {name}")
        indexed[name] = item
    return indexed


def _merge_firewall_order(
    current: dict[str, list[str]],
    requested: dict[str, list[str]],
    *,
    desired_names: set[str],
    protected_policy_names: set[str],
    prune: bool,
) -> dict[str, list[str]]:
    """Merge declared order with live policies outside the desired document."""
    merged: dict[str, list[str]] = {}
    for placement in ("before_system_defined", "after_system_defined"):
        original = [
            name
            for name in current.get(placement, [])
            if not prune or name in desired_names or name in protected_policy_names
        ]
        requested_names = requested.get(placement, [])
        merged_values: list[str] = []
        requested_index = 0
        for name in original:
            if name in desired_names:
                if requested_index < len(requested_names):
                    merged_values.append(requested_names[requested_index])
                    requested_index += 1
                continue
            merged_values.append(name)
        merged_values.extend(requested_names[requested_index:])
        merged[placement] = merged_values
    return merged


def _read_firewall_inventory(
    client: Adapter,
    current_networks: list[dict[str, Any]],
) -> dict[str, Any]:
    """Read supported firewall resources and resolve explicit user ordering."""
    zones = client.firewall_zones()
    groups = client.firewall_traffic_matching_lists()
    policies = client.firewall_policies()
    zones_by_name = _firewall_unique_name_index(zones, "zone")
    groups_by_name = _firewall_unique_name_index(groups, "group")
    policies_by_name: dict[str, dict[str, Any]] = {}
    protected_policy_names: set[str] = set()
    for policy in policies:
        name = str(policy["name"])
        if firewall_is_user_managed(policy):
            if name in policies_by_name or name in protected_policy_names:
                raise ResourceContractError(f"ambiguous firewall policy name: {name}")
            policies_by_name[name] = policy
        else:
            protected_policy_names.add(name)
    network_names_by_id = {
        str(network.get("_id") or network.get("id")): str(network["name"])
        for network in current_networks
        if network.get("name") and (network.get("_id") or network.get("id"))
    }
    zone_names_by_id = {str(zone["id"]): str(zone["name"]) for zone in zones}
    groups_by_id = {str(group["id"]): group for group in groups}
    pairs = sorted(
        {
            (str(policy["source"]["zone_id"]), str(policy["destination"]["zone_id"]))
            for policy in policies
        }
    )
    orderings = {pair: client.firewall_policy_ordering(*pair) for pair in pairs}
    current_rules: dict[str, dict[str, Any]] = {}
    for policy in policies:
        if not firewall_is_user_managed(policy):
            continue
        pair = (policy["source"]["zone_id"], policy["destination"]["zone_id"])
        order, placement = _firewall_order_position(policy, orderings[pair])
        generated: list[dict[str, Any]] = []
        portable = firewall_policy_to_portable(
            policy,
            order=order,
            placement=placement,
            zone_names_by_id=zone_names_by_id,
            network_names_by_id=network_names_by_id,
            groups_by_id=groups_by_id,
            generated=generated,
            used_names={str(group["name"]) for group in groups},
        )
        current_rules[policy["name"]] = portable
    return {
        "zones": zones,
        "groups": groups,
        "policies": policies,
        "zones_by_name": zones_by_name,
        "groups_by_name": groups_by_name,
        "policies_by_name": policies_by_name,
        "protected_policy_names": protected_policy_names,
        "orderings": orderings,
        "zone_names_by_id": zone_names_by_id,
        "network_names_by_id": network_names_by_id,
        "current_rules": current_rules,
    }


def _firewall_rule_warnings(
    rules: list[dict[str, Any]],
    groups_by_name: dict[str, dict[str, Any]],
) -> dict[str, tuple[str, ...]]:
    warnings: dict[str, list[str]] = {str(rule["name"]): [] for rule in rules}
    for rule in rules:
        name = str(rule["name"])
        if firewall_rule_is_broad(rule):
            warnings[name].append("broad match: source, destination or protocol is unrestricted")
        zones = (str(rule["source"]["zone"]), str(rule["destination"]["zone"]))
        if any(
            token in zone.lower()
            for zone in zones
            for token in ("wan", "internet", "external", "untrusted")
        ):
            warnings[name].append("external or untrusted zone can change Internet reachability")
        for side_name in ("source", "destination"):
            port_group_name = rule[side_name].get("port_group")
            if not port_group_name:
                continue
            group = groups_by_name.get(str(port_group_name), {})
            for item in group.get("ports", []):
                first = item if isinstance(item, int) else item.get("start")
                if isinstance(first, int) and first <= 1024:
                    warnings[name].append("privileged destination/source port is in scope")
                    break
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for rule in sorted(
        rules,
        key=lambda item: (
            item["source"]["zone"],
            item["destination"]["zone"],
            item.get("placement", "after_system_defined"),
            item["order"],
        ),
    ):
        pair = (
            str(rule["source"]["zone"]),
            str(rule["destination"]["zone"]),
            str(rule.get("placement", "after_system_defined")),
        )
        grouped.setdefault(pair, []).append(rule)
    for grouped_rules in grouped.values():
        seen: dict[tuple[Any, ...], str] = {}
        for rule in grouped_rules:
            key = firewall_rule_match_key(rule)
            previous = seen.get(key)
            if previous is not None:
                warnings[rule["name"]].append(f"may be shadowed by earlier rule {previous}")
            else:
                seen[key] = str(rule["name"])
    return {name: tuple(dict.fromkeys(values)) for name, values in warnings.items()}


def _append_firewall_plan(
    plan: Plan,
    *,
    client: Adapter,
    config: dict[str, Any],
    current_networks: list[dict[str, Any]],
    prune: bool,
) -> None:
    try:
        desired = validate_firewall(
            config.get("firewall"),
            network_names={str(network["name"]) for network in config.get("networks", [])},
        )
    except FirewallError as exc:
        raise ResourceContractError(str(exc)) from None
    inventory = _read_firewall_inventory(client, current_networks)
    current_zones = inventory["zones_by_name"]
    current_groups = inventory["groups_by_name"]
    current_policies = inventory["policies_by_name"]
    current_rules = inventory["current_rules"]
    known_zone_names = set(current_zones) | {str(zone["name"]) for zone in desired["zones"]}
    for rule in desired["rules"]:
        for side_name in ("source", "destination"):
            zone_name = str(rule[side_name]["zone"])
            if zone_name not in known_zone_names:
                raise ResourceContractError(f"firewall rule refers to an unknown zone: {zone_name}")

    desired_zones = desired["zones"]
    desired_zone_names = {str(zone["name"]) for zone in desired_zones}
    for zone in desired_zones:
        name = str(zone["name"])
        payload = {"name": name, "networks": list(zone.get("networks", []))}
        existing = current_zones.get(name)
        if existing is None:
            plan.diffs.append(
                ResourceDiff(
                    kind="firewall_zone", action="create", name=name, payload=payload, source=zone
                )
            )
            continue
        if not firewall_is_user_managed(existing):
            current_payload = _firewall_current_payload(existing, inventory["network_names_by_id"])
            if current_payload != payload:
                raise ResourceContractError(f"refusing to mutate protected firewall zone: {name}")
            plan.diffs.append(ResourceDiff(kind="firewall_zone", action="noop", name=name))
            continue
        current_payload = _firewall_current_payload(existing, inventory["network_names_by_id"])
        action = "update" if current_payload != payload else "noop"
        plan.diffs.append(
            ResourceDiff(
                kind="firewall_zone",
                action=action,
                name=name,
                payload=payload,
                current=current_payload,
                object_id=existing.get("id"),
                source=zone,
            )
        )
    if prune:
        for name, existing in current_zones.items():
            if name not in desired_zone_names and firewall_is_user_managed(existing):
                plan.diffs.append(
                    ResourceDiff(
                        kind="firewall_zone",
                        action="delete",
                        name=name,
                        current=_firewall_current_payload(
                            existing, inventory["network_names_by_id"]
                        ),
                        object_id=existing.get("id"),
                    )
                )

    desired_groups = [*desired["address_groups"], *desired["port_groups"]]
    desired_group_names = {str(group["name"]) for group in desired_groups}
    for group in desired_groups:
        name = str(group["name"])
        existing = current_groups.get(name)
        payload = dict(group)
        if existing is None:
            plan.diffs.append(
                ResourceDiff(
                    kind="firewall_group", action="create", name=name, payload=payload, source=group
                )
            )
            continue
        if not firewall_is_user_managed(existing):
            current_payload = _firewall_group_current_payload(existing)
            if current_payload != payload:
                raise ResourceContractError(f"refusing to mutate protected firewall group: {name}")
            plan.diffs.append(ResourceDiff(kind="firewall_group", action="noop", name=name))
            continue
        current_payload = _firewall_group_current_payload(existing)
        if set(current_payload) != set(payload):
            raise ResourceContractError(f"firewall group type cannot change in place: {name}")
        action = "update" if current_payload != payload else "noop"
        plan.diffs.append(
            ResourceDiff(
                kind="firewall_group",
                action=action,
                name=name,
                payload=payload,
                current=current_payload,
                object_id=existing.get("id"),
                source=group,
            )
        )
    if prune:
        for name, existing in current_groups.items():
            if name not in desired_group_names and firewall_is_user_managed(existing):
                plan.diffs.append(
                    ResourceDiff(
                        kind="firewall_group",
                        action="delete",
                        name=name,
                        current=_firewall_group_current_payload(existing),
                        object_id=existing.get("id"),
                    )
                )

    desired_rules = desired["rules"]
    rule_warnings = _firewall_rule_warnings(
        desired_rules,
        {str(group["name"]): group for group in desired_groups},
    )
    desired_rule_names = {str(rule["name"]) for rule in desired_rules}
    for rule in desired_rules:
        name = str(rule["name"])
        existing = current_policies.get(name)
        payload = dict(rule)
        if existing is None:
            if name in inventory["protected_policy_names"]:
                raise ResourceContractError(f"refusing to mutate protected firewall rule: {name}")
            plan.diffs.append(
                ResourceDiff(
                    kind="firewall_rule",
                    action="create",
                    name=name,
                    payload=payload,
                    source=rule,
                    warnings=rule_warnings[name],
                )
            )
            continue
        if not firewall_is_user_managed(existing):
            raise ResourceContractError(f"refusing to mutate protected firewall rule: {name}")
        current_payload = current_rules[name]
        action = (
            "update"
            if _firewall_rule_content(current_payload) != _firewall_rule_content(payload)
            else "noop"
        )
        comparison_current = {
            **current_payload,
            "order": payload["order"],
            "placement": payload["placement"],
        }
        plan.diffs.append(
            ResourceDiff(
                kind="firewall_rule",
                action=action,
                name=name,
                payload=payload,
                current=comparison_current,
                object_id=existing.get("id"),
                source=rule,
                warnings=rule_warnings[name] if action != "noop" else (),
            )
        )
    if prune:
        for name, existing in current_policies.items():
            if name not in desired_rule_names and firewall_is_user_managed(existing):
                plan.diffs.append(
                    ResourceDiff(
                        kind="firewall_rule",
                        action="delete",
                        name=name,
                        current=current_rules[name],
                        object_id=existing.get("id"),
                    )
                )

    desired_by_pair: dict[tuple[str, str], dict[str, list[str]]] = {}
    for rule in desired_rules:
        pair = (rule["source"]["zone"], rule["destination"]["zone"])
        placement = rule.get("placement", "after_system_defined")
        desired_by_pair.setdefault(pair, {"before_system_defined": [], "after_system_defined": []})[
            placement
        ].append(rule["name"])
    for values in desired_by_pair.values():
        for placement in values:
            values[placement].sort(
                key=lambda name: next(
                    rule["order"] for rule in desired_rules if rule["name"] == name
                )
            )

    policy_by_id = {str(policy["id"]): policy for policy in inventory["policies"]}
    current_by_pair: dict[tuple[str, str], dict[str, list[str]]] = {}
    for pair_ids, ordering in inventory["orderings"].items():
        try:
            pair = (
                inventory["zone_names_by_id"][pair_ids[0]],
                inventory["zone_names_by_id"][pair_ids[1]],
            )
        except KeyError as exc:
            raise ResourceContractError(
                "firewall policy refers to an unknown firewall zone"
            ) from exc
        current_by_pair[pair] = {"before_system_defined": [], "after_system_defined": []}
        for placement in current_by_pair[pair]:
            for identifier in ordering.get(placement, []):
                policy = policy_by_id.get(identifier)
                if policy is None:
                    raise ResourceContractError(
                        "firewall policy ordering refers to an unknown policy"
                    )
                name = str(policy["name"])
                if any(name in values for values in current_by_pair[pair].values()):
                    raise ResourceContractError(
                        f"firewall policy ordering has an ambiguous policy name: {name}"
                    )
                current_by_pair[pair][placement].append(name)
    for pair, desired_order in desired_by_pair.items():
        current_order = current_by_pair.get(
            pair, {"before_system_defined": [], "after_system_defined": []}
        )
        merged_order = _merge_firewall_order(
            current_order,
            desired_order,
            desired_names=desired_rule_names,
            protected_policy_names=inventory["protected_policy_names"],
            prune=prune,
        )
        if current_order == merged_order:
            continue
        plan.diffs.append(
            ResourceDiff(
                kind="firewall_rule",
                action="reorder",
                name=f"{pair[0]} -> {pair[1]}",
                payload={
                    "source_zone": pair[0],
                    "destination_zone": pair[1],
                    "before_system_defined": merged_order["before_system_defined"],
                    "after_system_defined": merged_order["after_system_defined"],
                },
                current=current_order,
                source={"source_zone": pair[0], "destination_zone": pair[1]},
                warnings=("rule order changes first-match behavior",),
            )
        )


def build_plan(
    client: Adapter,
    config: dict[str, Any],
    prune: bool = False,
    *,
    target: TargetIdentity | None = None,
) -> Plan:
    """Build a deterministic plan from the live controller and desired config."""
    current_networks = client.networks()
    current_wlans = client.wlans()
    network_ids = {
        network["name"]: _object_id(network)
        for network in current_networks
        if network.get("name") and _object_id(network)
    }
    plan = Plan(target=target)
    _append_resource_plan(
        plan,
        kind="network",
        desired=config.get("networks", []),
        current=current_networks,
        payload_factory=network_to_unifi,
        prune=prune,
    )
    _append_resource_plan(
        plan,
        kind="wlan",
        desired=config.get("wlans", []),
        current=current_wlans,
        payload_factory=lambda wlan: wlan_to_unifi(wlan, network_ids),
        prune=prune,
    )
    desired_dns = validate_dns_records(config.get("dns", []))
    if desired_dns or (prune and "dns" in config):
        capabilities = getattr(client, "capabilities", None)
        if capabilities is not None:
            capabilities.require("dns", "plan")
        if not callable(getattr(client, "dns", None)):
            raise RuntimeError("selected adapter cannot read DNS policies")
        _append_dns_plan(
            plan,
            desired=desired_dns,
            current=client.dns(),
            prune=prune,
        )
    if "firewall" in config:
        capabilities = getattr(client, "capabilities", None)
        if capabilities is not None:
            capabilities.require("firewall", "plan")
        required_methods = (
            "firewall_zones",
            "firewall_traffic_matching_lists",
            "firewall_policies",
            "firewall_policy_ordering",
        )
        if any(not callable(getattr(client, method, None)) for method in required_methods):
            raise RuntimeError("selected adapter cannot read firewall resources")
        _append_firewall_plan(
            plan,
            client=client,
            config=config,
            current_networks=current_networks,
            prune=prune,
        )
    desired_nat = config.get("nat")
    if desired_nat or (prune and "nat" in config):
        capabilities = getattr(client, "capabilities", None)
        if capabilities is not None:
            capabilities.require("nat", "plan")
        if not callable(getattr(client, "nat", None)):
            raise RuntimeError("selected adapter cannot read NAT mappings")
        _append_nat_plan(
            plan,
            desired=desired_nat or [],
            current=client.nat(),
            network_names={str(network["name"]) for network in config.get("networks", [])},
            prune=prune,
        )
    if "vpn" in config:
        capabilities = getattr(client, "capabilities", None)
        if capabilities is not None:
            capabilities.require("vpn", "plan")
        if not callable(getattr(client, "vpn", None)):
            raise RuntimeError("selected adapter cannot read VPN resources")
        desired_vpn = validate_vpn(
            config.get("vpn"),
            network_names={str(network["name"]) for network in config.get("networks", [])},
        )
        plan.read_only["vpn"] = plan_observation(desired_vpn, client.vpn())
    return plan


def _merge_for_update(current: dict[str, Any], desired: dict[str, Any]) -> dict[str, Any]:
    payload = {**current, **desired}
    for key in READ_ONLY_FIELDS:
        payload.pop(key, None)
    return payload


def _created_id(result: Any) -> str | None:
    if isinstance(result, list) and result and isinstance(result[0], dict):
        return _object_id(result[0])
    if isinstance(result, dict):
        return _object_id(result)
    return None


def _target_label(client: Adapter, identity: TargetIdentity | None = None) -> str:
    """Build a target label without ever including URL userinfo or secrets."""
    if identity is not None:
        return identity.label()
    settings = getattr(client, "settings", None)
    raw_host = str(getattr(settings, "host", "") or "")
    try:
        parsed = urlsplit(raw_host if "://" in raw_host else f"//{raw_host}")
        host = parsed.hostname or "controller"
        port = f":{parsed.port}" if parsed.port else ""
    except ValueError:
        host = "controller"
        port = ""
    site = str(getattr(settings, "site", "unknown") or "unknown").replace("\n", " ")
    return f"controller={host}{port} site={site}"


def _ordered_apply_diffs(plan: Plan) -> list[ResourceDiff]:
    """Return the exact dependency-safe execution order for a plan."""
    graph = DependencyGraph()
    diffs_by_key: dict[ResourceKey, ResourceDiff] = {}
    for diff in plan.diffs:
        if diff.action == "noop":
            continue
        key = ResourceKey(diff.kind, diff.name)
        graph.add(key)
        diffs_by_key[key] = diff
        if diff.kind == "wlan" and diff.source.get("network"):
            graph.add_dependency(
                key,
                ResourceKey("network", str(diff.source["network"])),
            )
        if diff.kind == "firewall_rule" and diff.action != "reorder":
            for side in (diff.source.get("source", {}), diff.source.get("destination", {})):
                if side.get("zone"):
                    graph.add_dependency(key, ResourceKey("firewall_zone", str(side["zone"])))
                for group_key in ("address_group", "port_group"):
                    if side.get(group_key):
                        graph.add_dependency(
                            key, ResourceKey("firewall_group", str(side[group_key]))
                        )
        if diff.kind == "firewall_rule" and diff.action == "reorder":
            for placement in ("before_system_defined", "after_system_defined"):
                for name in diff.payload.get(placement, []):
                    graph.add_dependency(key, ResourceKey("firewall_rule", str(name)))
        if diff.kind == "nat":
            nat_state = diff.source or diff.current
            network_name = (nat_state.get("private") or {}).get("network")
            if network_name:
                graph.add_dependency(key, ResourceKey("network", str(network_name)))
    dependency_order = graph.topological_order()

    def select(predicate: Any, *, reverse: bool = False) -> list[ResourceDiff]:
        keys = list(reversed(dependency_order)) if reverse else dependency_order
        return [
            diffs_by_key[key]
            for key in keys
            if key in diffs_by_key and predicate(diffs_by_key[key])
        ]

    network_writes = select(
        lambda item: item.kind == "network" and item.action in {"create", "update"}
    )
    dns_writes = select(lambda item: item.kind == "dns" and item.action in {"create", "update"})
    firewall_zone_writes = select(
        lambda item: item.kind == "firewall_zone" and item.action in {"create", "update"}
    )
    firewall_group_writes = select(
        lambda item: item.kind == "firewall_group" and item.action in {"create", "update"}
    )
    firewall_rule_writes = select(
        lambda item: item.kind == "firewall_rule" and item.action in {"create", "update"}
    )
    nat_writes = select(lambda item: item.kind == "nat" and item.action in {"create", "update"})
    wlan_deletes = select(
        lambda item: item.kind == "wlan" and item.action == "delete", reverse=True
    )
    dns_deletes = select(lambda item: item.kind == "dns" and item.action == "delete", reverse=True)
    firewall_rule_deletes = select(
        lambda item: item.kind == "firewall_rule" and item.action == "delete", reverse=True
    )
    nat_deletes = select(lambda item: item.kind == "nat" and item.action == "delete", reverse=True)
    firewall_reorders = select(
        lambda item: item.kind == "firewall_rule" and item.action == "reorder"
    )
    wlan_writes = select(lambda item: item.kind == "wlan" and item.action in {"create", "update"})
    network_deletes = select(
        lambda item: item.kind == "network" and item.action == "delete", reverse=True
    )
    firewall_group_deletes = select(
        lambda item: item.kind == "firewall_group" and item.action == "delete", reverse=True
    )
    firewall_zone_deletes = select(
        lambda item: item.kind == "firewall_zone" and item.action == "delete", reverse=True
    )
    return (
        network_writes
        + dns_writes
        + firewall_zone_writes
        + firewall_group_writes
        + firewall_rule_writes
        + nat_writes
        + wlan_deletes
        + dns_deletes
        + nat_deletes
        + firewall_rule_deletes
        + firewall_reorders
        + wlan_writes
        + firewall_group_deletes
        + firewall_zone_deletes
        + network_deletes
    )


def _raise_apply_error(
    client: Adapter,
    plan: Plan,
    *,
    ordered: list[ResourceDiff],
    completed: list[ResourceDiff],
    failed: ResourceDiff | None,
    resource: str,
    operation: str,
    phase: str,
    partial_request: bool,
    cause_type: str,
) -> None:
    pending_start = len(completed) + (1 if failed is not None else 0)
    raise PlanApplyError(
        target=_target_label(client, plan.target),
        resource=resource,
        operation=operation,
        phase=phase,
        completed=completed,
        pending=ordered[pending_start:],
        partial_request=partial_request,
        cause_type=cause_type,
    ) from None


def _verify_plan_target(
    plan: Plan,
    selected_target: TargetIdentity | None,
) -> None:
    if plan.target is None:
        return
    if selected_target != plan.target:
        raise PlanTargetMismatchError(expected=plan.target, actual=selected_target)


def apply_plan(
    client: Adapter,
    plan: Plan,
    *,
    target: TargetIdentity | None = None,
    acknowledge_firewall_risk: bool = False,
) -> None:
    """Apply a plan with dependency ordering and safe partial-failure reports."""
    _verify_plan_target(plan, target)
    if plan.risk_warnings() and not acknowledge_firewall_risk:
        raise PlanRiskError(plan.risk_warnings())
    if plan.read_only:
        resources = ", ".join(sorted(plan.read_only))
        raise RuntimeError(f"plan contains read-only resources and cannot be applied: {resources}")
    network_base = client.site_url("rest/networkconf")
    wlan_base = client.site_url("rest/wlanconf")
    ordered = _ordered_apply_diffs(plan)
    completed: list[ResourceDiff] = []

    # A WLAN may depend on a network. Network creates/updates must happen
    # before WLAN writes, while network deletes must wait until dependent WLAN
    # deletes have completed. The order is explicit so a failure report can
    # identify every operation that was not started.
    network_writes = [
        diff for diff in ordered if diff.kind == "network" and diff.action in {"create", "update"}
    ]
    for diff in network_writes:
        try:
            if diff.action == "create":
                client.post(network_base, json=diff.payload)
            else:
                if not diff.object_id:
                    raise RuntimeError("network update requires a controller object id")
                client.put(
                    f"{network_base}/{diff.object_id}",
                    json=_merge_for_update(diff.current, diff.payload),
                )
        except Exception as exc:
            _raise_apply_error(
                client,
                plan,
                ordered=ordered,
                completed=completed,
                failed=diff,
                resource=f"network/{diff.name}",
                operation=diff.action,
                phase="network",
                partial_request=False,
                cause_type=type(exc).__name__,
            )
        completed.append(diff)

    def apply_dns_diff(diff: ResourceDiff) -> None:
        try:
            if diff.action == "create":
                client.create_dns(diff.payload)
            elif diff.action == "update":
                if not diff.object_id:
                    raise RuntimeError("DNS update requires a controller object id")
                client.update_dns(diff.object_id, diff.payload)
            else:
                if not diff.object_id:
                    raise RuntimeError("DNS delete requires a controller object id")
                client.delete_dns(diff.object_id)
        except Exception as exc:
            _raise_apply_error(
                client,
                plan,
                ordered=ordered,
                completed=completed,
                failed=diff,
                resource=f"dns/{diff.name}",
                operation=diff.action,
                phase="dns",
                partial_request=False,
                cause_type=type(exc).__name__,
            )
        completed.append(diff)

    dns_writes = [
        diff for diff in ordered if diff.kind == "dns" and diff.action in {"create", "update"}
    ]
    for diff in dns_writes:
        apply_dns_diff(diff)

    firewall_changes = [diff for diff in ordered if diff.kind.startswith("firewall_")]
    firewall_zone_writes = [
        diff
        for diff in ordered
        if diff.kind == "firewall_zone" and diff.action in {"create", "update"}
    ]
    firewall_group_writes = [
        diff
        for diff in ordered
        if diff.kind == "firewall_group" and diff.action in {"create", "update"}
    ]
    firewall_rule_writes = [
        diff
        for diff in ordered
        if diff.kind == "firewall_rule" and diff.action in {"create", "update"}
    ]
    firewall_rule_deletes = [
        diff for diff in ordered if diff.kind == "firewall_rule" and diff.action == "delete"
    ]
    firewall_reorders = [
        diff for diff in ordered if diff.kind == "firewall_rule" and diff.action == "reorder"
    ]
    firewall_group_deletes = [
        diff for diff in ordered if diff.kind == "firewall_group" and diff.action == "delete"
    ]
    firewall_zone_deletes = [
        diff for diff in ordered if diff.kind == "firewall_zone" and diff.action == "delete"
    ]
    nat_writes = [
        diff for diff in ordered if diff.kind == "nat" and diff.action in {"create", "update"}
    ]
    nat_deletes = [diff for diff in ordered if diff.kind == "nat" and diff.action == "delete"]
    network_ids: dict[str, str | None] = {}
    firewall_zone_ids: dict[str, str] = {}
    firewall_group_ids: dict[str, str] = {}
    template: dict[str, Any] = {}
    if any(diff.kind in {"network", "wlan"} for diff in ordered) or firewall_changes:
        try:
            fresh_networks = client.networks()
            network_ids = {
                network["name"]: _object_id(network)
                for network in fresh_networks
                if network.get("name") and _object_id(network)
            }
            if any(diff.kind in {"network", "wlan"} for diff in ordered):
                existing_wlans = client.wlans()
                if existing_wlans:
                    template = {
                        key: value
                        for key, value in existing_wlans[0].items()
                        if key not in READ_ONLY_FIELDS | {"name", "x_passphrase", "x_iapp_key"}
                    }
            if firewall_changes:
                firewall_zone_ids = {
                    str(zone["name"]): str(zone["id"]) for zone in client.firewall_zones()
                }
                firewall_group_ids = {
                    str(group["name"]): str(group["id"])
                    for group in client.firewall_traffic_matching_lists()
                }
        except Exception as exc:
            _raise_apply_error(
                client,
                plan,
                ordered=ordered,
                completed=completed,
                failed=None,
                resource="controller inventory",
                operation="refresh",
                phase="inventory",
                partial_request=False,
                cause_type=type(exc).__name__,
            )

    def apply_firewall_zone_diff(diff: ResourceDiff) -> None:
        partial_request = True
        try:
            payload = firewall_zone_to_unifi(
                diff.payload,
                {name: identifier for name, identifier in network_ids.items() if identifier},
            )
            if diff.action == "create":
                client.create_firewall_zone(payload)
            else:
                if not diff.object_id:
                    raise RuntimeError("firewall zone update requires a controller object id")
                client.update_firewall_zone(diff.object_id, payload)
        except Exception as exc:
            _raise_apply_error(
                client,
                plan,
                ordered=ordered,
                completed=completed,
                failed=diff,
                resource=f"firewall_zone/{diff.name}",
                operation=diff.action,
                phase="firewall",
                partial_request=partial_request,
                cause_type=type(exc).__name__,
            )
        completed.append(diff)

    def apply_firewall_group_diff(diff: ResourceDiff) -> None:
        partial_request = True
        try:
            payload = firewall_group_to_unifi(diff.payload)
            if diff.action == "create":
                client.create_firewall_traffic_matching_list(payload)
            else:
                if not diff.object_id:
                    raise RuntimeError("firewall group update requires a controller object id")
                client.update_firewall_traffic_matching_list(diff.object_id, payload)
        except Exception as exc:
            _raise_apply_error(
                client,
                plan,
                ordered=ordered,
                completed=completed,
                failed=diff,
                resource=f"firewall_group/{diff.name}",
                operation=diff.action,
                phase="firewall",
                partial_request=partial_request,
                cause_type=type(exc).__name__,
            )
        completed.append(diff)

    for diff in firewall_zone_writes:
        apply_firewall_zone_diff(diff)
    for diff in firewall_group_writes:
        apply_firewall_group_diff(diff)

    if firewall_zone_writes or firewall_group_writes:
        try:
            fresh_networks = client.networks()
            network_ids = {
                network["name"]: _object_id(network)
                for network in fresh_networks
                if network.get("name") and _object_id(network)
            }
            firewall_zone_ids = {
                str(zone["name"]): str(zone["id"]) for zone in client.firewall_zones()
            }
            firewall_group_ids = {
                str(group["name"]): str(group["id"])
                for group in client.firewall_traffic_matching_lists()
            }
        except Exception as exc:
            _raise_apply_error(
                client,
                plan,
                ordered=ordered,
                completed=completed,
                failed=None,
                resource="controller firewall inventory",
                operation="refresh",
                phase="firewall",
                partial_request=False,
                cause_type=type(exc).__name__,
            )

    def apply_firewall_rule_diff(diff: ResourceDiff) -> None:
        partial_request = True
        try:
            if diff.action == "delete":
                if not diff.object_id:
                    raise RuntimeError("firewall rule delete requires a controller object id")
                client.delete_firewall_policy(diff.object_id)
            else:
                payload = firewall_rule_to_unifi(
                    diff.payload,
                    zone_ids_by_name=firewall_zone_ids,
                    network_ids_by_name={
                        name: identifier for name, identifier in network_ids.items() if identifier
                    },
                    group_ids_by_name=firewall_group_ids,
                )
                if diff.action == "create":
                    client.create_firewall_policy(payload)
                else:
                    if not diff.object_id:
                        raise RuntimeError("firewall rule update requires a controller object id")
                    client.update_firewall_policy(diff.object_id, payload)
        except Exception as exc:
            _raise_apply_error(
                client,
                plan,
                ordered=ordered,
                completed=completed,
                failed=diff,
                resource=f"firewall_rule/{diff.name}",
                operation=diff.action,
                phase="firewall",
                partial_request=partial_request,
                cause_type=type(exc).__name__,
            )
        completed.append(diff)

    for diff in firewall_rule_writes:
        apply_firewall_rule_diff(diff)

    def apply_wlan_diff(diff: ResourceDiff) -> None:
        partial_request = False
        try:
            if diff.action == "delete":
                if not diff.object_id:
                    raise RuntimeError("WLAN delete requires a controller object id")
                client.delete(f"{wlan_base}/{diff.object_id}")
            else:
                generated = wlan_to_unifi(diff.source, network_ids)
                if diff.action == "create":
                    result = client.post(wlan_base, json={**template, **generated})
                    created_id = _created_id(result)
                    if created_id:
                        partial_request = True
                        created = result[0] if isinstance(result, list) else result
                        client.put(
                            f"{wlan_base}/{created_id}",
                            json=_merge_for_update(created, generated),
                        )
                else:
                    if not diff.object_id:
                        raise RuntimeError("WLAN update requires a controller object id")
                    client.put(
                        f"{wlan_base}/{diff.object_id}",
                        json=_merge_for_update(diff.current, generated),
                    )
        except Exception as exc:
            _raise_apply_error(
                client,
                plan,
                ordered=ordered,
                completed=completed,
                failed=diff,
                resource=f"wlan/{diff.name}",
                operation=diff.action,
                phase="wlan",
                partial_request=partial_request,
                cause_type=type(exc).__name__,
            )
        completed.append(diff)

    wlan_deletes = [diff for diff in ordered if diff.kind == "wlan" and diff.action == "delete"]
    for diff in wlan_deletes:
        apply_wlan_diff(diff)

    dns_deletes = [diff for diff in ordered if diff.kind == "dns" and diff.action == "delete"]
    for diff in dns_deletes:
        apply_dns_diff(diff)

    for diff in firewall_rule_deletes:
        apply_firewall_rule_diff(diff)

    if firewall_reorders:
        try:
            fresh_zones = client.firewall_zones()
            firewall_zone_ids = {str(zone["name"]): str(zone["id"]) for zone in fresh_zones}
            fresh_policies = client.firewall_policies()
            requested_policy_names = {
                name
                for diff in firewall_reorders
                for placement in ("before_system_defined", "after_system_defined")
                for name in diff.payload[placement]
            }
            firewall_policy_ids: dict[str, str] = {}
            for policy in fresh_policies:
                name = str(policy["name"])
                if name not in requested_policy_names:
                    continue
                if name in firewall_policy_ids:
                    raise RuntimeError(f"ambiguous firewall policy name: {name}")
                firewall_policy_ids[name] = str(policy["id"])
        except Exception as exc:
            _raise_apply_error(
                client,
                plan,
                ordered=ordered,
                completed=completed,
                failed=None,
                resource="controller firewall inventory",
                operation="refresh",
                phase="firewall",
                partial_request=False,
                cause_type=type(exc).__name__,
            )
        for diff in firewall_reorders:
            partial_request = False
            try:
                source_zone = diff.payload["source_zone"]
                destination_zone = diff.payload["destination_zone"]
                source_zone_id = firewall_zone_ids[source_zone]
                destination_zone_id = firewall_zone_ids[destination_zone]
                before_ids = [
                    firewall_policy_ids[name] for name in diff.payload["before_system_defined"]
                ]
                after_ids = [
                    firewall_policy_ids[name] for name in diff.payload["after_system_defined"]
                ]
                partial_request = True
                client.reorder_firewall_policies(
                    source_zone_id,
                    destination_zone_id,
                    after_system_defined=after_ids,
                    before_system_defined=before_ids,
                )
            except Exception as exc:
                _raise_apply_error(
                    client,
                    plan,
                    ordered=ordered,
                    completed=completed,
                    failed=diff,
                    resource=f"firewall_rule/{diff.name}",
                    operation="reorder",
                    phase="firewall",
                    partial_request=partial_request,
                    cause_type=type(exc).__name__,
                )
            completed.append(diff)

    def apply_nat_diff(diff: ResourceDiff) -> None:
        partial_request = True
        try:
            if diff.action == "create":
                client.create_nat(nat_to_unifi(diff.payload))
            elif diff.action == "update":
                if not diff.object_id:
                    raise RuntimeError("NAT update requires a controller object id")
                client.update_nat(diff.object_id, nat_to_unifi(diff.payload))
            else:
                if not diff.object_id:
                    raise RuntimeError("NAT delete requires a controller object id")
                client.delete_nat(diff.object_id)
        except Exception as exc:
            _raise_apply_error(
                client,
                plan,
                ordered=ordered,
                completed=completed,
                failed=diff,
                resource=f"nat/{diff.name}",
                operation=diff.action,
                phase="nat",
                partial_request=partial_request,
                cause_type=type(exc).__name__,
            )
        completed.append(diff)

    for diff in nat_writes:
        apply_nat_diff(diff)
    for diff in nat_deletes:
        apply_nat_diff(diff)

    wlan_writes = [
        diff for diff in ordered if diff.kind == "wlan" and diff.action in {"create", "update"}
    ]
    for diff in wlan_writes:
        apply_wlan_diff(diff)

    for diff in firewall_group_deletes:
        partial_request = True
        try:
            if not diff.object_id:
                raise RuntimeError("firewall group delete requires a controller object id")
            client.delete_firewall_traffic_matching_list(diff.object_id)
        except Exception as exc:
            _raise_apply_error(
                client,
                plan,
                ordered=ordered,
                completed=completed,
                failed=diff,
                resource=f"firewall_group/{diff.name}",
                operation="delete",
                phase="firewall",
                partial_request=partial_request,
                cause_type=type(exc).__name__,
            )
        completed.append(diff)

    for diff in firewall_zone_deletes:
        partial_request = True
        try:
            if not diff.object_id:
                raise RuntimeError("firewall zone delete requires a controller object id")
            client.delete_firewall_zone(diff.object_id)
        except Exception as exc:
            _raise_apply_error(
                client,
                plan,
                ordered=ordered,
                completed=completed,
                failed=diff,
                resource=f"firewall_zone/{diff.name}",
                operation="delete",
                phase="firewall",
                partial_request=partial_request,
                cause_type=type(exc).__name__,
            )
        completed.append(diff)

    network_deletes = [
        diff for diff in ordered if diff.kind == "network" and diff.action == "delete"
    ]
    for diff in network_deletes:
        try:
            if not diff.object_id:
                raise RuntimeError("network delete requires a controller object id")
            client.delete(f"{network_base}/{diff.object_id}")
        except Exception as exc:
            _raise_apply_error(
                client,
                plan,
                ordered=ordered,
                completed=completed,
                failed=diff,
                resource=f"network/{diff.name}",
                operation=diff.action,
                phase="network",
                partial_request=False,
                cause_type=type(exc).__name__,
            )
        completed.append(diff)
