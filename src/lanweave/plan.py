"""Declarative planning and application for networks and WLANs."""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass, field
from typing import Any

from .client import UniFiClient

SENSITIVE_FIELDS = {"api_key", "password", "passphrase", "secret", "token", "x_passphrase"}
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
            "summary": self.summary(),
            "changes": [diff.to_dict() for diff in self.diffs if diff.action != "noop"],
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


def apply_plan(client: UniFiClient, plan: Plan) -> None:
    """Apply a plan in dependency order, deleting dependent WLANs first."""
    network_base = client.site_url("rest/networkconf")
    wlan_base = client.site_url("rest/wlanconf")

    # A WLAN may depend on a network. Network creates/updates must happen
    # before WLAN writes, while network deletes must wait until dependent WLAN
    # deletes have completed.
    for diff in plan.diffs:
        if diff.kind != "network" or diff.action not in {"create", "update"}:
            continue
        if diff.action == "create":
            client.post(network_base, json=diff.payload)
        elif diff.action == "update":
            if not diff.object_id:
                raise RuntimeError(f"cannot update network without an id: {diff.name}")
            client.put(
                f"{network_base}/{diff.object_id}",
                json=_merge_for_update(diff.current, diff.payload),
            )
        elif diff.action == "delete":
            if not diff.object_id:
                raise RuntimeError(f"cannot delete network without an id: {diff.name}")
            client.delete(f"{network_base}/{diff.object_id}")

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

    for diff in plan.diffs:
        if diff.kind != "wlan" or diff.action == "noop":
            continue
        if diff.action == "delete":
            if not diff.object_id:
                raise RuntimeError(f"cannot delete WLAN without an id: {diff.name}")
            client.delete(f"{wlan_base}/{diff.object_id}")
            continue

        generated = wlan_to_unifi(diff.source, network_ids)
        if diff.action == "create":
            result = client.post(wlan_base, json={**template, **generated})
            created_id = _created_id(result)
            if created_id:
                created = result[0] if isinstance(result, list) else result
                client.put(
                    f"{wlan_base}/{created_id}",
                    json=_merge_for_update(created, generated),
                )
        elif diff.action == "update":
            if not diff.object_id:
                raise RuntimeError(f"cannot update WLAN without an id: {diff.name}")
            client.put(
                f"{wlan_base}/{diff.object_id}",
                json=_merge_for_update(diff.current, generated),
            )

    for diff in plan.diffs:
        if diff.kind != "network" or diff.action != "delete":
            continue
        if not diff.object_id:
            raise RuntimeError(f"cannot delete network without an id: {diff.name}")
        client.delete(f"{network_base}/{diff.object_id}")
