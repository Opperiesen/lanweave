"""Explicitly authorized firewall lifecycle coverage on an isolated scope."""

from __future__ import annotations

from typing import Any, Protocol

import pytest

from lanweave.plan import apply_plan, build_plan

pytestmark = pytest.mark.integration_mutation


class FirewallMutationTarget(Protocol):
    client: Any
    prefix: str
    zone: str
    address_group: str
    port_group: str
    first_rule: str
    second_rule: str


def _config(target: FirewallMutationTarget, *, reordered: bool = False) -> dict[str, Any]:
    first_order, second_order = (200, 100) if reordered else (100, 200)
    first_description = (
        "lanweave firewall lifecycle updated"
        if reordered
        else "lanweave firewall lifecycle initial"
    )
    return {
        "version": 1,
        "controller": {"site": target.client.settings.site},
        "networks": [],
        "wlans": [],
        "firewall": {
            "zones": [],
            "address_groups": [{"name": target.address_group, "addresses": ["192.0.2.10"]}],
            "port_groups": [{"name": target.port_group, "ports": [65535]}],
            "rules": [
                {
                    "name": target.first_rule,
                    "order": first_order,
                    "source": {"zone": target.zone, "address_group": target.address_group},
                    "destination": {"zone": target.zone, "port_group": target.port_group},
                    "action": "BLOCK",
                    "enabled": False,
                    "ip_version": "IPV4",
                    "protocol": "TCP",
                    "description": first_description,
                },
                {
                    "name": target.second_rule,
                    "order": second_order,
                    "source": {"zone": target.zone, "address_group": target.address_group},
                    "destination": {"zone": target.zone, "port_group": target.port_group},
                    "action": "BLOCK",
                    "enabled": False,
                    "ip_version": "IPV4",
                    "protocol": "TCP",
                    "description": "lanweave firewall lifecycle second rule",
                },
            ],
        },
    }


def _named(items: list[dict[str, Any]], name: str) -> dict[str, Any] | None:
    return next((item for item in items if item.get("name") == name), None)


def _delete_test_resources(target: FirewallMutationTarget) -> None:
    client = target.client
    for policy in client.firewall_policies():
        if str(policy.get("name", "")).startswith(target.prefix):
            if policy.get("_origin") not in {"USER", "USER_DEFINED", "CUSTOM"}:
                raise AssertionError("refusing to delete a non-user firewall policy")
            client.delete_firewall_policy(str(policy["id"]))
    for group in client.firewall_traffic_matching_lists():
        if str(group.get("name", "")).startswith(target.prefix):
            if group.get("_origin") not in {"USER", "USER_DEFINED", "CUSTOM"}:
                raise AssertionError("refusing to delete a non-user firewall group")
            client.delete_firewall_traffic_matching_list(str(group["id"]))
    for zone in client.firewall_zones():
        if str(zone.get("name", "")).startswith(target.prefix):
            if zone.get("_origin") not in {"USER", "USER_DEFINED", "CUSTOM"}:
                raise AssertionError("refusing to delete a non-user firewall zone")
            client.delete_firewall_zone(str(zone["id"]))


def test_firewall_create_update_reorder_delete_isolated(
    firewall_mutation_target: FirewallMutationTarget,
) -> None:
    target = firewall_mutation_target
    client = target.client
    for items in (
        client.firewall_zones(),
        client.firewall_traffic_matching_lists(),
        client.firewall_policies(),
    ):
        if any(str(item.get("name", "")).startswith(target.prefix) for item in items):
            pytest.fail("refusing to reuse an existing firewall mutation target")
    initial = _config(target)
    updated = _config(target, reordered=True)

    try:
        create_plan = build_plan(client, initial)
        assert {diff.action for diff in create_plan.diffs} >= {"create", "reorder"}
        apply_plan(client, create_plan, acknowledge_firewall_risk=True)

        assert _named(client.firewall_zones(), target.zone) is not None
        assert _named(client.firewall_traffic_matching_lists(), target.address_group) is not None
        assert _named(client.firewall_traffic_matching_lists(), target.port_group) is not None
        assert _named(client.firewall_policies(), target.first_rule) is not None
        assert _named(client.firewall_policies(), target.second_rule) is not None

        update_plan = build_plan(client, updated)
        assert any(diff.action == "update" for diff in update_plan.diffs)
        assert any(diff.action == "reorder" for diff in update_plan.diffs)
        apply_plan(client, update_plan, acknowledge_firewall_risk=True)

        final_policies = client.firewall_policies()
        assert _named(final_policies, target.first_rule) is not None
        assert _named(final_policies, target.second_rule) is not None
    finally:
        _delete_test_resources(target)

    assert _named(client.firewall_traffic_matching_lists(), target.address_group) is None
    assert _named(client.firewall_traffic_matching_lists(), target.port_group) is None
    assert _named(client.firewall_policies(), target.first_rule) is None
    assert _named(client.firewall_policies(), target.second_rule) is None
