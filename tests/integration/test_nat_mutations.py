"""Explicitly authorized NAT lifecycle coverage on the classic session API."""

from __future__ import annotations

from typing import Protocol

import pytest

from lanweave.client import UniFiClient
from lanweave.config import validate_config
from lanweave.nat import nat_is_user_managed
from lanweave.plan import Plan, apply_plan, build_plan

pytestmark = pytest.mark.integration_mutation


class NatTarget(Protocol):
    client: UniFiClient
    name: str
    initial_port: int
    updated_port: int


def _config(target: NatTarget, port: int) -> dict[str, object]:
    return {
        "version": 1,
        "controller": {"site": target.client.settings.site},
        "networks": [],
        "wlans": [],
        "nat": [
            {
                "name": target.name,
                "enabled": False,
                "protocol": "TCP",
                "ip_version": "IPV4",
                "public": {"interface": "wan", "port": port},
                "source": {"addresses": ["198.51.100.0/24"]},
                "private": {"address": "192.0.2.10", "port": port},
                "hairpin": False,
            }
        ],
    }


def _find(target: NatTarget) -> dict[str, object] | None:
    return next(
        (mapping for mapping in target.client.nat() if mapping.get("name") == target.name), None
    )


def test_nat_create_update_protected_prune_and_cleanup(nat_mutation_target: NatTarget) -> None:
    """Exercise the complete isolated NAT lifecycle with a disabled mapping."""

    target = nat_mutation_target
    if _find(target) is not None:
        pytest.fail(f"refusing to reuse existing NAT mutation target {target.name}")

    initial = _config(target, target.initial_port)
    updated = _config(target, target.updated_port)
    empty = {**initial, "nat": []}
    validate_config(initial)
    validate_config(updated)
    validate_config(empty)

    try:
        create_plan = build_plan(target.client, initial)
        assert [(diff.action, diff.name) for diff in create_plan.diffs] == [("create", target.name)]
        assert create_plan.risk_warnings()
        apply_plan(target.client, create_plan, acknowledge_firewall_risk=True)

        created = _find(target)
        assert created is not None
        assert created.get("enabled") is False
        assert nat_is_user_managed(created)

        update_plan = build_plan(target.client, updated)
        assert [(diff.action, diff.name) for diff in update_plan.diffs] == [("update", target.name)]
        apply_plan(target.client, update_plan, acknowledge_firewall_risk=True)
        changed = _find(target)
        assert changed is not None
        public = changed.get("public")
        private = changed.get("private")
        assert isinstance(public, dict)
        assert isinstance(private, dict)
        assert public.get("port") == target.updated_port
        assert private.get("port") == target.updated_port

        full_prune_plan = build_plan(target.client, empty, prune=True)
        prune_plan = Plan(
            diffs=[diff for diff in full_prune_plan.diffs if diff.kind == "nat"],
            target=full_prune_plan.target,
        )
        assert [(diff.action, diff.name) for diff in prune_plan.diffs] == [("delete", target.name)]
        apply_plan(target.client, prune_plan, acknowledge_firewall_risk=True)
        assert _find(target) is None
    finally:
        remaining = _find(target)
        if remaining is not None:
            if not nat_is_user_managed(remaining):
                raise AssertionError("refusing to delete a protected NAT mutation target")
            object_id = remaining.get("_id") or remaining.get("id")
            if object_id:
                target.client.delete_nat(str(object_id))
