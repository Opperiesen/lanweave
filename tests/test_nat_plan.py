from types import SimpleNamespace
from typing import Any

import pytest

from lanweave.adapters import (
    AUTH_MODE_SESSION,
    UnsupportedCapabilityError,
    local_classic_capabilities,
)
from lanweave.nat import NatError, analyze_nat_exposure, nat_mapping_conflict
from lanweave.plan import Plan, ResourceDiff, apply_plan, build_plan
from lanweave.resources import ResourceContractError


def _mapping(
    name: str,
    *,
    port: int | dict[str, int] = 443,
    source: dict[str, Any] | None = None,
    protocol: str = "TCP",
    address: str | None = None,
    hairpin: bool = False,
) -> dict[str, Any]:
    public: dict[str, Any] = {"interface": "WAN", "port": port}
    if address is not None:
        public["address"] = address
    return {
        "name": name,
        "enabled": True,
        "protocol": protocol,
        "ip_version": "IPV4",
        "public": public,
        "source": source or {"addresses": []},
        "private": {"address": "192.0.2.10", "port": 8443},
        "hairpin": hairpin,
    }


class FakeNatController:
    capabilities = local_classic_capabilities(AUTH_MODE_SESSION)

    def __init__(self, mappings: list[dict[str, Any]] | None = None) -> None:
        self.settings = SimpleNamespace(host="https://controller.test", site="default")
        self._mappings = list(mappings or [])

    def networks(self) -> list[dict[str, Any]]:
        return []

    def wlans(self) -> list[dict[str, Any]]:
        return []

    def nat(self) -> list[dict[str, Any]]:
        return list(self._mappings)


def test_nat_exposure_analysis_is_deterministic_and_explains_risk() -> None:
    mapping = _mapping("web", source={"addresses": []}, hairpin=True)

    warnings = analyze_nat_exposure([mapping])

    assert warnings == {
        "web": (
            "source scope is unrestricted for private service 192.0.2.10:8443",
            "public boundary WAN may expose private service 192.0.2.10:8443 "
            "at an Internet boundary",
            "firewall dependency for private service 192.0.2.10:8443 is not proven by "
            + "NAT analysis",
            "public address is interface-selected; exact WAN binding for private "
            "service 192.0.2.10:8443 is not explicit",
            "privileged public port is in scope for 192.0.2.10:8443",
            "hairpin behavior for private service 192.0.2.10:8443 is not proven by "
            "the local classic adapter",
        )
    }


def test_nat_conflicts_are_rejected_only_when_public_flows_overlap() -> None:
    base = _mapping("first")
    assert nat_mapping_conflict(
        base,
        _mapping("second", source={"addresses": ["198.51.100.0/25"]}),
    )
    assert not nat_mapping_conflict(
        base,
        _mapping("second", port=8443),
    )
    assert not nat_mapping_conflict(
        _mapping("first", source={"addresses": ["198.51.100.0/25"]}),
        _mapping("second", source={"addresses": ["198.51.100.128/25"]}),
    )
    assert not nat_mapping_conflict(
        base,
        _mapping("second", protocol="UDP"),
    )

    with pytest.raises(NatError, match="overlapping public binding"):
        analyze_nat_exposure([base, _mapping("second")])


def test_nat_plan_is_sorted_warns_and_is_byte_stable() -> None:
    desired = [_mapping("zulu", port=8443), _mapping("alpha")]
    controller = FakeNatController()
    config = {"networks": [], "wlans": [], "nat": desired}

    first = build_plan(controller, config)
    second = build_plan(controller, {**config, "nat": list(reversed(desired))})

    assert [(diff.action, diff.name) for diff in first.diffs] == [
        ("create", "alpha"),
        ("create", "zulu"),
    ]
    assert first.to_dict() == second.to_dict()
    assert first.risk_warnings()
    assert first.to_dict()["changes"][0]["warnings"]


def test_nat_plan_protects_system_origin_and_prunes_only_user_origin() -> None:
    current = [
        {**_mapping("system"), "_id": "system-id", "_origin": "SYSTEM_DEFINED"},
        {**_mapping("old"), "_id": "old-id", "_origin": "USER_DEFINED"},
    ]
    controller = FakeNatController(current)

    plan = build_plan(
        controller,
        {"networks": [], "wlans": [], "nat": [_mapping("old")]},
        prune=True,
    )

    assert [(diff.action, diff.name) for diff in plan.diffs] == [("noop", "old")]

    prune_plan = build_plan(controller, {"networks": [], "wlans": [], "nat": []}, prune=True)
    assert [(diff.action, diff.name) for diff in prune_plan.diffs] == [("delete", "old")]

    with pytest.raises(ResourceContractError, match="protected origin SYSTEM_DEFINED"):
        build_plan(
            controller,
            {"networks": [], "wlans": [], "nat": [_mapping("system", port=9443)]},
        )


def test_nat_plan_detects_updates_and_rejects_invalid_ports() -> None:
    current = {**_mapping("web"), "_id": "web-id", "_origin": "USER_DEFINED"}
    controller = FakeNatController([current])

    plan = build_plan(
        controller,
        {"networks": [], "wlans": [], "nat": [_mapping("web", port=8443)]},
    )

    assert [(diff.action, diff.name, diff.object_id) for diff in plan.diffs] == [
        ("update", "web", "web-id")
    ]

    with pytest.raises(ResourceContractError, match="between"):
        build_plan(
            FakeNatController(),
            {"networks": [], "wlans": [], "nat": [_mapping("invalid", port=0)]},
        )


def test_nat_apply_is_blocked_before_the_mutation_tranche() -> None:
    controller = FakeNatController()
    plan = Plan(
        diffs=[
            ResourceDiff(
                kind="nat",
                action="create",
                name="web",
                payload=_mapping("web"),
            )
        ]
    )

    with pytest.raises(UnsupportedCapabilityError, match="does not support apply on nat"):
        apply_plan(controller, plan)
