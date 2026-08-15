"""Explicitly authorized DNS lifecycle coverage for the Integration API."""

from __future__ import annotations

from typing import Protocol

import pytest

from lanweave.config import validate_config
from lanweave.dns import dns_is_user_managed
from lanweave.plan import apply_plan, build_plan

pytestmark = pytest.mark.integration_mutation


class DnsTarget(Protocol):
    client: object
    name: str
    initial_address: str
    updated_address: str


def _config(target: DnsTarget, address: str) -> dict[str, object]:
    return {
        "version": 1,
        "controller": {"site": target.client.settings.site},
        "networks": [],
        "wlans": [],
        "dns": [
            {
                "name": target.name,
                "type": "A",
                "address": address,
                "ttl_seconds": 300,
            }
        ],
    }


def _find(target: DnsTarget) -> dict[str, object] | None:
    return next(
        (
            record
            for record in target.client.dns()
            if record.get("name") == target.name and record.get("type") == "A"
        ),
        None,
    )


def test_dns_create_update_and_prune_are_cleaned_up(dns_mutation_target: DnsTarget) -> None:
    target = dns_mutation_target
    if _find(target) is not None:
        pytest.fail(f"refusing to reuse existing DNS mutation target {target.name}")

    initial = _config(target, target.initial_address)
    updated = _config(target, target.updated_address)
    empty = {**initial, "dns": []}
    validate_config(initial)
    validate_config(updated)
    validate_config(empty)

    try:
        create_plan = build_plan(target.client, initial)
        assert [(diff.action, diff.name) for diff in create_plan.diffs] == [
            ("create", f"{target.name} [A]")
        ]
        apply_plan(target.client, create_plan)

        created = _find(target)
        assert created is not None
        assert created.get("address") == target.initial_address
        assert dns_is_user_managed(created)

        update_plan = build_plan(target.client, updated)
        assert [(diff.action, diff.name) for diff in update_plan.diffs] == [
            ("update", f"{target.name} [A]")
        ]
        apply_plan(target.client, update_plan)
        changed = _find(target)
        assert changed is not None
        assert changed.get("address") == target.updated_address

        prune_plan = build_plan(target.client, empty, prune=True)
        assert [(diff.action, diff.name) for diff in prune_plan.diffs] == [
            ("delete", f"{target.name} [A]")
        ]
        apply_plan(target.client, prune_plan)
        assert _find(target) is None
    finally:
        remaining = _find(target)
        if remaining is not None and dns_is_user_managed(remaining):
            object_id = remaining.get("_id") or remaining.get("id")
            if object_id:
                target.client.delete_dns(str(object_id))
