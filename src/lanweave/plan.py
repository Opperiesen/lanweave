"""Declarative planning and application for networks and WLANs."""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit

from .client import UniFiClient
from .contracts import PLAN_FORMAT_VERSION

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

    @property
    def changed_fields(self) -> list[str]:
        if self.action == "create":
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
        return {
            "kind": self.kind,
            "action": self.action,
            "name": self.name,
            "id": self.object_id,
            "changed_fields": self.changed_fields,
            "payload": _redact(self.payload),
        }


@dataclass
class Plan:
    diffs: list[ResourceDiff] = field(default_factory=list)

    def has_changes(self) -> bool:
        return any(diff.action != "noop" for diff in self.diffs)

    def by_action(self, action: str) -> list[ResourceDiff]:
        return [diff for diff in self.diffs if diff.action == action]

    def summary(self) -> dict[str, int]:
        return {
            action: len(self.by_action(action)) for action in ("create", "update", "delete", "noop")
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "format_version": PLAN_FORMAT_VERSION,
            "summary": self.summary(),
            "changes": [diff.to_dict() for diff in self.diffs if diff.action != "noop"],
        }


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


def build_plan(client: UniFiClient, config: dict[str, Any], prune: bool = False) -> Plan:
    """Build a deterministic plan from the live controller and desired config."""
    current_networks = client.networks()
    current_wlans = client.wlans()
    network_ids = {
        network["name"]: _object_id(network)
        for network in current_networks
        if network.get("name") and _object_id(network)
    }
    plan = Plan()
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


def _target_label(client: UniFiClient) -> str:
    """Build a target label without ever including URL userinfo or secrets."""
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
    network_writes = [
        diff
        for diff in plan.diffs
        if diff.kind == "network" and diff.action in {"create", "update"}
    ]
    wlan_deletes = [diff for diff in plan.diffs if diff.kind == "wlan" and diff.action == "delete"]
    wlan_writes = [
        diff for diff in plan.diffs if diff.kind == "wlan" and diff.action in {"create", "update"}
    ]
    network_deletes = [
        diff for diff in plan.diffs if diff.kind == "network" and diff.action == "delete"
    ]
    return network_writes + wlan_deletes + wlan_writes + network_deletes


def _raise_apply_error(
    client: UniFiClient,
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
        target=_target_label(client),
        resource=resource,
        operation=operation,
        phase=phase,
        completed=completed,
        pending=ordered[pending_start:],
        partial_request=partial_request,
        cause_type=cause_type,
    ) from None


def apply_plan(client: UniFiClient, plan: Plan) -> None:
    """Apply a plan with dependency ordering and safe partial-failure reports."""
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

    try:
        fresh_networks = client.networks()
        network_ids = {
            network["name"]: _object_id(network)
            for network in fresh_networks
            if network.get("name") and _object_id(network)
        }
        existing_wlans = client.wlans()
        template = {}
        if existing_wlans:
            template = {
                key: value
                for key, value in existing_wlans[0].items()
                if key not in READ_ONLY_FIELDS | {"name", "x_passphrase", "x_iapp_key"}
            }
    except Exception as exc:
        _raise_apply_error(
            client,
            ordered=ordered,
            completed=completed,
            failed=None,
            resource="controller inventory",
            operation="refresh",
            phase="inventory",
            partial_request=False,
            cause_type=type(exc).__name__,
        )

    wlan_diffs = [diff for diff in ordered if diff.kind == "wlan"]
    for diff in wlan_diffs:
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
