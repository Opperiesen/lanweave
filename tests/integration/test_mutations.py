"""Explicitly authorized create/update/delete coverage for the plan engine."""

from __future__ import annotations

from typing import Protocol

import pytest

from lanweave.client import UniFiClient
from lanweave.config import validate_config
from lanweave.plan import apply_plan, build_plan

pytestmark = pytest.mark.integration_mutation


class MutationTarget(Protocol):
    client: UniFiClient
    name: str
    subnet: str
    vlan: int


def _config(target: MutationTarget, domain_name: str) -> dict[str, object]:
    return {
        "version": 1,
        "controller": {"site": target.client.settings.site},
        "networks": [
            {
                "name": target.name,
                "purpose": "vlan-only",
                "subnet": target.subnet,
                "vlan": target.vlan,
                "domain_name": domain_name,
            }
        ],
        "wlans": [],
    }


def _find_network(target: MutationTarget) -> dict[str, object] | None:
    return next(
        (network for network in target.client.networks() if network.get("name") == target.name),
        None,
    )


def test_network_create_update_delete_is_cleaned_up(mutation_target: MutationTarget) -> None:
    if _find_network(mutation_target) is not None:
        pytest.fail(f"refusing to reuse existing mutation target {mutation_target.name}")

    created_id: str | None = None
    initial = _config(mutation_target, f"{mutation_target.name}.lanweave.invalid")
    updated = _config(mutation_target, f"updated.{mutation_target.name}.lanweave.invalid")
    validate_config(initial)
    validate_config(updated)

    try:
        create_plan = build_plan(mutation_target.client, initial)
        assert [(diff.action, diff.name) for diff in create_plan.diffs] == [
            ("create", mutation_target.name)
        ]
        apply_plan(mutation_target.client, create_plan)

        created = _find_network(mutation_target)
        assert created is not None
        created_id = str(created.get("_id") or created.get("id") or "")
        assert created_id

        update_plan = build_plan(mutation_target.client, updated)
        assert [(diff.action, diff.name) for diff in update_plan.diffs] == [
            ("update", mutation_target.name)
        ]
        apply_plan(mutation_target.client, update_plan)

        changed = _find_network(mutation_target)
        assert changed is not None
        assert changed.get("domain_name") == updated["networks"][0]["domain_name"]
    finally:
        created = _find_network(mutation_target)
        cleanup_id = created_id or (str(created.get("_id") or created.get("id")) if created else "")
        if cleanup_id:
            mutation_target.client.delete(
                f"{mutation_target.client.site_url('rest/networkconf')}/{cleanup_id}"
            )
