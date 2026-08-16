from types import SimpleNamespace
from typing import Any

import pytest

from lanweave.adapters import AdapterCapabilities, AdapterCapability
from lanweave.convergence import (
    ConvergenceState,
    convergence_exit_code,
    verify_plan_convergence,
)
from lanweave.plan import Plan, PlanApplyError, ResourceDiff


def _config() -> dict[str, Any]:
    return {
        "version": 1,
        "controller": {"site": "default"},
        "networks": [
            {
                "name": "Home",
                "purpose": "corporate",
                "subnet": "192.168.10.0/24",
                "vlan": 10,
            }
        ],
        "wlans": [
            {
                "name": "Home",
                "ssid": "Home",
                "network": "Home",
                "bands": ["5g"],
                "security": "wpa2",
                "password_env": "WIFI_HOME_PASSWORD",
            }
        ],
    }


class FakeConvergenceController:
    settings = SimpleNamespace(site="default")

    def __init__(self, *, vlan: int = 10, fail_networks: bool = False) -> None:
        self.vlan = vlan
        self.fail_networks = fail_networks

    def networks(self) -> list[dict[str, Any]]:
        if self.fail_networks:
            raise RuntimeError("controller response secret=fixture-secret")
        return [
            {
                "_id": "network-controller-id",
                "name": "Home",
                "purpose": "corporate",
                "vlan_enabled": True,
                "vlan": str(self.vlan),
                "ip_subnet": "192.168.10.1/24",
            }
        ]

    def wlans(self) -> list[dict[str, Any]]:
        return [
            {
                "_id": "wlan-controller-id",
                "name": "Home",
                "networkconf_id": "network-controller-id",
                "wlan_bands": ["5g"],
                "security": "wpapsk",
                "wpa3_support": False,
                "x_passphrase": "fixture-secret",
            }
        ]


def _network_plan() -> Plan:
    return Plan(
        diffs=[
            ResourceDiff(
                kind="network",
                action="update",
                name="Home",
                payload={"vlan": "10"},
            )
        ]
    )


def test_convergence_reads_only_affected_resource_families() -> None:
    result = verify_plan_convergence(
        FakeConvergenceController(),
        _config(),
        _network_plan(),
    )

    assert result["state"] == ConvergenceState.CONVERGED
    assert result["affected_resources"] == ["networks"]
    assert [item["resource"] for item in result["resources"]] == ["networks"]
    assert convergence_exit_code(result) == 0
    assert "fixture-secret" not in str(result)
    assert "network-controller-id" not in str(result)


def test_convergence_distinguishes_proven_drift() -> None:
    result = verify_plan_convergence(
        FakeConvergenceController(vlan=20),
        _config(),
        _network_plan(),
    )

    assert result["state"] == ConvergenceState.DRIFTED
    assert result["resources"][0]["findings"] == [
        {"kind": "changed", "name": "Home", "fields": ["vlan"]}
    ]
    assert convergence_exit_code(result) == 1


def test_convergence_distinguishes_unsupported_readback() -> None:
    controller = FakeConvergenceController()
    controller.capabilities = AdapterCapabilities(
        adapter="fixture",
        auth_modes=("fixture",),
        resources=(AdapterCapability("networks", ("read", "export")),),
    )
    plan = Plan(
        diffs=[
            ResourceDiff(
                kind="wlan",
                action="update",
                name="Home",
                payload={"enabled": True},
            )
        ]
    )

    result = verify_plan_convergence(controller, _config(), plan)

    assert result["state"] == ConvergenceState.UNSUPPORTED
    assert result["resources"][0]["coverage"]["reason"] == "unsupported_export_capability"
    assert convergence_exit_code(result) == 2


def test_convergence_maps_all_mutation_families_in_deterministic_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    def fake_audit(_client, _config, *, target, resources):
        captured["target"] = target
        captured["resources"] = resources
        return {
            "resources": [
                {
                    "resource": resource,
                    "state": "in-sync",
                    "declared_count": 0,
                    "observed_count": 0,
                    "findings": [],
                }
                for resource in resources
            ]
        }

    monkeypatch.setattr("lanweave.convergence.audit_config", fake_audit)
    plan = Plan(
        diffs=[
            ResourceDiff(kind="nat", action="create", name="web"),
            ResourceDiff(kind="firewall_rule", action="update", name="allow-web"),
            ResourceDiff(kind="dns", action="delete", name="old [A]"),
            ResourceDiff(kind="network", action="update", name="Home"),
            ResourceDiff(kind="wlan", action="update", name="Home"),
        ]
    )

    result = verify_plan_convergence(object(), _config(), plan)

    assert captured["resources"] == ["networks", "wlans", "dns", "firewall", "nat"]
    assert result["affected_resources"] == captured["resources"]
    assert result["state"] == ConvergenceState.CONVERGED


def test_convergence_of_multi_family_plan_is_scoped_to_changed_families() -> None:
    plan = Plan(
        diffs=[
            ResourceDiff(kind="network", action="update", name="Home"),
            ResourceDiff(kind="wlan", action="update", name="Home"),
        ]
    )

    result = verify_plan_convergence(FakeConvergenceController(), _config(), plan)

    assert result["affected_resources"] == ["networks", "wlans"]
    assert result["summary"]["converged"] == 2


def test_convergence_marks_failed_readback_uncertain() -> None:
    result = verify_plan_convergence(
        FakeConvergenceController(fail_networks=True),
        _config(),
        _network_plan(),
    )

    assert result["state"] == ConvergenceState.UNCERTAIN
    assert result["resources"][0]["coverage"]["reason"] == "live_observation_failed"
    assert convergence_exit_code(result) == 2
    assert "fixture-secret" not in str(result)


def test_partial_apply_report_can_carry_convergence_evidence() -> None:
    plan = _network_plan()
    error = PlanApplyError(
        target="controller=controller.test site=default",
        resource="network/Home",
        operation="update",
        phase="network",
        completed=[],
        pending=[plan.diffs[0]],
        partial_request=False,
        cause_type="RuntimeError",
    )
    convergence = verify_plan_convergence(FakeConvergenceController(vlan=20), _config(), plan)
    error.attach_convergence(convergence)

    report = error.to_dict()

    assert report["convergence"]["state"] == "drifted"
    assert report["automatic_rollback"] is False
