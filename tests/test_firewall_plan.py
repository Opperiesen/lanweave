from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace
from typing import Any

import pytest

from lanweave.firewall import (
    normalize_controller_firewall_policy,
    normalize_controller_firewall_zone,
    normalize_controller_traffic_matching_list,
)
from lanweave.plan import PlanRiskError, apply_plan, build_plan


class FakeFirewallController:
    def __init__(self) -> None:
        self.settings = SimpleNamespace(host="https://controller.test", site="default")
        self.calls: list[tuple[str, str]] = []
        self._networks = [
            {
                "_id": "network-home",
                "name": "Home",
                "purpose": "corporate",
                "vlan_enabled": False,
                "dhcpd_enabled": False,
                "dhcpd_dns_enabled": False,
                "ipv6_interface_type": "none",
            }
        ]
        self._zones = [
            normalize_controller_firewall_zone(
                {
                    "id": "zone-lan",
                    "name": "LAN",
                    "networkIds": ["network-home"],
                    "metadata": {"origin": "SYSTEM_DEFINED"},
                }
            )
        ]
        self._groups: list[dict[str, Any]] = []
        self._policies: list[dict[str, Any]] = []
        self._orderings: dict[tuple[str, str], dict[str, list[str]]] = {}

    def site_url(self, path: str) -> str:
        return f"/{path}"

    def networks(self) -> list[dict[str, Any]]:
        return deepcopy(self._networks)

    def wlans(self) -> list[dict[str, Any]]:
        return []

    def firewall_zones(self) -> list[dict[str, Any]]:
        return deepcopy(self._zones)

    def firewall_traffic_matching_lists(self) -> list[dict[str, Any]]:
        return deepcopy(self._groups)

    def firewall_policies(self) -> list[dict[str, Any]]:
        return deepcopy(self._policies)

    def firewall_policy_ordering(
        self, source_zone_id: str, destination_zone_id: str
    ) -> dict[str, list[str]]:
        return deepcopy(
            self._orderings.get(
                (source_zone_id, destination_zone_id),
                {"before_system_defined": [], "after_system_defined": []},
            )
        )

    def create_firewall_zone(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(("create", "zone"))
        zone = normalize_controller_firewall_zone(
            {
                **payload,
                "id": f"zone-{payload['name'].lower()}",
                "metadata": {"origin": "USER_DEFINED"},
            }
        )
        self._zones.append(zone)
        return zone

    def update_firewall_zone(self, object_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(("update", "zone"))
        for index, current in enumerate(self._zones):
            if current["id"] == object_id:
                self._zones[index] = normalize_controller_firewall_zone(
                    {**payload, "id": object_id, "metadata": {"origin": "USER_DEFINED"}}
                )
                return self._zones[index]
        raise AssertionError(object_id)

    def delete_firewall_zone(self, object_id: str) -> None:
        self.calls.append(("delete", "zone"))
        self._zones[:] = [zone for zone in self._zones if zone["id"] != object_id]

    def create_firewall_traffic_matching_list(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(("create", "group"))
        group = normalize_controller_traffic_matching_list(
            {
                **payload,
                "id": f"group-{payload['name']}",
                "metadata": {"origin": "USER_DEFINED"},
            }
        )
        self._groups.append(group)
        return group

    def update_firewall_traffic_matching_list(
        self, object_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        self.calls.append(("update", "group"))
        for index, current in enumerate(self._groups):
            if current["id"] == object_id:
                self._groups[index] = normalize_controller_traffic_matching_list(
                    {
                        **payload,
                        "id": object_id,
                        "metadata": {"origin": "USER_DEFINED"},
                    }
                )
                return self._groups[index]
        raise AssertionError(object_id)

    def delete_firewall_traffic_matching_list(self, object_id: str) -> None:
        self.calls.append(("delete", "group"))
        self._groups[:] = [group for group in self._groups if group["id"] != object_id]

    def create_firewall_policy(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(("create", "rule"))
        policy_id = f"policy-{payload['name']}"
        policy = normalize_controller_firewall_policy(
            {
                **payload,
                "id": policy_id,
                "metadata": {"origin": "USER_DEFINED"},
            }
        )
        self._policies.append(policy)
        pair = (policy["source"]["zone_id"], policy["destination"]["zone_id"])
        self._orderings.setdefault(pair, {"before_system_defined": [], "after_system_defined": []})[
            "after_system_defined"
        ].append(policy_id)
        return policy

    def update_firewall_policy(self, object_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(("update", "rule"))
        for index, current in enumerate(self._policies):
            if current["id"] == object_id:
                policy = normalize_controller_firewall_policy(
                    {
                        **payload,
                        "id": object_id,
                        "metadata": {"origin": "USER_DEFINED"},
                    }
                )
                self._policies[index] = policy
                return policy
        raise AssertionError(object_id)

    def delete_firewall_policy(self, object_id: str) -> None:
        self.calls.append(("delete", "rule"))
        self._policies[:] = [policy for policy in self._policies if policy["id"] != object_id]
        for ordering in self._orderings.values():
            for placement in ordering:
                ordering[placement] = [
                    identifier for identifier in ordering[placement] if identifier != object_id
                ]

    def reorder_firewall_policies(
        self,
        source_zone_id: str,
        destination_zone_id: str,
        *,
        after_system_defined: list[str],
        before_system_defined: list[str],
    ) -> None:
        self.calls.append(("reorder", "rule"))
        self._orderings[(source_zone_id, destination_zone_id)] = {
            "before_system_defined": list(before_system_defined),
            "after_system_defined": list(after_system_defined),
        }


def _config() -> dict[str, Any]:
    return {
        "version": 1,
        "controller": {"site": "default"},
        "networks": [{"name": "Home", "purpose": "corporate"}],
        "wlans": [],
        "firewall": {
            "zones": [{"name": "Trusted", "networks": ["Home"]}],
            "address_groups": [{"name": "servers", "addresses": ["192.0.2.10"]}],
            "port_groups": [{"name": "web", "ports": [443]}],
            "rules": [
                {
                    "name": "allow-web",
                    "order": 100,
                    "source": {"zone": "Trusted", "address_group": "servers"},
                    "destination": {"zone": "LAN", "networks": ["Home"], "port_group": "web"},
                    "action": "ALLOW",
                    "ip_version": "IPV4",
                    "protocol": "TCP",
                    "connection_states": ["NEW", "ESTABLISHED"],
                }
            ],
        },
    }


def test_firewall_plan_is_deterministic_and_exposes_order_changes() -> None:
    controller = FakeFirewallController()

    first = build_plan(controller, _config())
    second = build_plan(controller, _config())

    assert first.to_dict() == second.to_dict()
    assert first.summary() == {"create": 4, "update": 0, "delete": 0, "noop": 1, "reorder": 1}
    assert first.by_action("reorder")[0].payload["after_system_defined"] == ["allow-web"]
    assert first.risk_warnings()


def test_firewall_apply_requires_acknowledgement_and_replays_to_noop() -> None:
    controller = FakeFirewallController()
    plan = build_plan(controller, _config())

    with pytest.raises(PlanRiskError) as caught:
        apply_plan(controller, plan)

    assert caught.value.to_dict()["error"] == "firewall_risk_acknowledgement_required"
    assert controller.calls == []

    apply_plan(controller, plan, acknowledge_firewall_risk=True)

    assert controller.calls == [
        ("create", "zone"),
        ("create", "group"),
        ("create", "group"),
        ("create", "rule"),
        ("reorder", "rule"),
    ]
    assert build_plan(controller, _config()).summary() == {
        "create": 0,
        "update": 0,
        "delete": 0,
        "noop": 5,
    }
