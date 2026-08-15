from types import SimpleNamespace
from typing import Any

import pytest
import yaml

from lanweave.config import EXAMPLE_CONFIG
from lanweave.plan import (
    Plan,
    PlanApplyError,
    PlanTargetMismatchError,
    ResourceDiff,
    apply_plan,
    build_plan,
    network_to_unifi,
)
from lanweave.profiles import TargetIdentity


class FakeController:
    def __init__(
        self,
        networks: list[dict[str, Any]] | None = None,
        wlans: list[dict[str, Any]] | None = None,
        fail_on_call: int | None = None,
    ) -> None:
        self._networks = networks or []
        self._wlans = wlans or []
        self.calls: list[tuple[str, str, Any]] = []
        self.fail_on_call = fail_on_call
        self._mutation_call_count = 0
        self.settings = SimpleNamespace(host="https://controller.test", site="default")

    def site_url(self, path: str) -> str:
        return f"/{path}"

    def networks(self) -> list[dict[str, Any]]:
        return self._networks

    def wlans(self) -> list[dict[str, Any]]:
        return self._wlans

    def _record(self, method: str, path: str, json: Any = None) -> None:
        self.calls.append((method, path, json))
        self._mutation_call_count += 1
        if self._mutation_call_count == self.fail_on_call:
            raise RuntimeError("controller rejected payload secret=fixture-secret")

    def post(self, path: str, json: Any = None) -> Any:
        self._record("POST", path, json)
        if path.endswith("networkconf"):
            created = {"_id": "network-created", **(json or {})}
            self._networks.append(created)
            return [created]
        created = {"_id": "wlan-created", **(json or {})}
        self._wlans.append(created)
        return [created]

    def put(self, path: str, json: Any = None) -> Any:
        self._record("PUT", path, json)
        return json

    def delete(self, path: str) -> Any:
        self._record("DELETE", path)
        if "wlanconf/" in path:
            object_id = path.rsplit("/", maxsplit=1)[-1]
            self._wlans[:] = [item for item in self._wlans if item.get("_id") != object_id]
        if "networkconf/" in path:
            object_id = path.rsplit("/", maxsplit=1)[-1]
            self._networks[:] = [item for item in self._networks if item.get("_id") != object_id]
        return None


def test_network_subnet_is_converted_to_gateway_address() -> None:
    payload = network_to_unifi(
        {
            "name": "IoT",
            "purpose": "vlan-only",
            "subnet": "192.168.20.0/24",
            "vlan": 20,
        }
    )

    assert payload["ip_subnet"] == "192.168.20.1/24"
    assert payload["vlan"] == "20"


def test_empty_controller_produces_network_and_wlan_creates() -> None:
    config = yaml.safe_load(EXAMPLE_CONFIG)
    config["wlans"][0]["password"] = "test-secret"
    config["wlans"][1]["password"] = "test-iot-secret"
    controller = FakeController()

    plan = build_plan(controller, config)

    assert plan.summary() == {"create": 4, "update": 0, "delete": 0, "noop": 0}
    assert all(diff.action == "create" for diff in plan.diffs)
    assert all("test-secret" not in str(diff.to_dict()) for diff in plan.diffs)


def test_plan_json_has_version_and_redacts_sensitive_payloads() -> None:
    plan = Plan(
        diffs=[
            ResourceDiff(
                kind="wlan",
                action="create",
                name="Home",
                payload={"name": "Home", "x_passphrase": "fixture-secret"},
            )
        ]
    )

    rendered = plan.to_dict()

    assert rendered["format_version"] == 1
    assert rendered["summary"] == {"create": 1, "update": 0, "delete": 0, "noop": 0}
    assert rendered["changes"][0]["payload"]["x_passphrase"] == "***"
    assert "target" not in rendered
    assert "fixture-secret" not in str(rendered)


def test_profile_plan_includes_only_the_stable_target_identity() -> None:
    plan = Plan(
        target=TargetIdentity("office", "local", "default"),
        diffs=[
            ResourceDiff(
                kind="network",
                action="create",
                name="Home",
                payload={"name": "Home", "purpose": "corporate"},
            )
        ],
    )

    rendered = plan.to_dict()

    assert rendered["target"] == {
        "profile": "office",
        "controller": "local",
        "site": "default",
        "adapter": "local-classic",
    }
    assert "https://" not in str(rendered)


def test_password_change_is_planned_when_controller_returns_the_old_value() -> None:
    config = yaml.safe_load(EXAMPLE_CONFIG)
    config["wlans"][0].pop("password_env")
    config["wlans"][0]["password"] = "new-secret"
    controller = FakeController(
        networks=[{"_id": "network-1", "name": "Home", "purpose": "corporate"}],
        wlans=[
            {
                "_id": "wlan-1",
                "name": "Home",
                "networkconf_id": "network-1",
                "x_passphrase": "old-secret",
            }
        ],
    )

    plan = build_plan(controller, config)

    wlan_diff = next(diff for diff in plan.diffs if diff.kind == "wlan")
    assert wlan_diff.action == "update"
    assert "credentials" in wlan_diff.changed_fields
    assert "x_passphrase" not in wlan_diff.changed_fields
    assert "new-secret" not in str(wlan_diff.to_dict())


def test_prune_keeps_default_and_wan_networks() -> None:
    config = yaml.safe_load(EXAMPLE_CONFIG)
    config["networks"] = []
    config["wlans"] = []
    controller = FakeController(
        networks=[
            {"_id": "default", "name": "Default", "purpose": "corporate"},
            {"_id": "wan", "name": "WAN", "purpose": "wan"},
            {"_id": "old", "name": "Old", "purpose": "corporate"},
        ]
    )

    plan = build_plan(controller, config, prune=True)

    assert [(diff.action, diff.name) for diff in plan.diffs] == [("delete", "Old")]


def test_apply_orders_networks_before_wlans() -> None:
    controller = FakeController()
    plan = Plan(
        diffs=[
            ResourceDiff(
                kind="network",
                action="create",
                name="Home",
                payload={"name": "Home", "purpose": "corporate"},
            ),
            ResourceDiff(
                kind="wlan",
                action="create",
                name="Home",
                source={
                    "name": "Home",
                    "ssid": "Home",
                    "network": "Home",
                    "bands": ["5g"],
                    "security": "open",
                },
            ),
        ]
    )

    apply_plan(controller, plan)

    assert [call[0] for call in controller.calls] == ["POST", "POST", "PUT"]
    assert controller.calls[0][1].endswith("networkconf")
    assert controller.calls[1][1].endswith("wlanconf")


def test_apply_deletes_wlans_before_their_network() -> None:
    controller = FakeController(
        networks=[{"_id": "network-1", "name": "Old", "purpose": "corporate"}],
        wlans=[{"_id": "wlan-1", "name": "Old", "networkconf_id": "network-1"}],
    )
    plan = Plan(
        diffs=[
            ResourceDiff(
                kind="network",
                action="delete",
                name="Old",
                object_id="network-1",
            ),
            ResourceDiff(
                kind="wlan",
                action="delete",
                name="Old",
                object_id="wlan-1",
            ),
        ]
    )

    apply_plan(controller, plan)

    assert [call[0] for call in controller.calls] == ["DELETE", "DELETE"]
    assert controller.calls[0][1].endswith("wlanconf/wlan-1")
    assert controller.calls[1][1].endswith("networkconf/network-1")


def test_apply_failure_reports_completed_failed_and_pending_without_secrets() -> None:
    controller = FakeController(fail_on_call=2)
    plan = Plan(
        diffs=[
            ResourceDiff(
                kind="network",
                action="create",
                name="Home",
                payload={"name": "Home", "purpose": "corporate"},
            ),
            ResourceDiff(
                kind="network",
                action="create",
                name="IoT",
                payload={"name": "IoT", "purpose": "vlan-only", "password": "fixture-secret"},
            ),
            ResourceDiff(
                kind="wlan",
                action="create",
                name="Home",
                source={
                    "name": "Home",
                    "ssid": "Home",
                    "network": "Home",
                    "bands": ["5g"],
                    "security": "open",
                },
            ),
        ]
    )

    with pytest.raises(PlanApplyError) as caught:
        apply_plan(controller, plan)

    error = caught.value
    report = error.to_dict()
    assert error.target == "controller=controller.test site=default"
    assert error.resource == "network/IoT"
    assert error.operation == "create"
    assert error.state == "partial"
    assert report["confirmed_completed"] == ["network/Home:create"]
    assert report["uncertain_failed"] == "network/IoT:create"
    assert report["not_started"] == ["wlan/Home:create"]
    assert "fixture-secret" not in str(error)
    assert "fixture-secret" not in str(report)


def test_apply_rejects_a_mismatched_plan_target_before_controller_mutation() -> None:
    controller = FakeController()
    plan = Plan(
        target=TargetIdentity("office", "local", "default"),
        diffs=[
            ResourceDiff(
                kind="network",
                action="create",
                name="Home",
                payload={"name": "Home", "purpose": "corporate"},
            )
        ],
    )

    with pytest.raises(PlanTargetMismatchError) as caught:
        apply_plan(
            controller,
            plan,
            target=TargetIdentity("guest", "local", "guest"),
        )

    error = caught.value
    assert error.to_dict() == {
        "error": "plan_target_mismatch",
        "expected_target": {
            "profile": "office",
            "controller": "local",
            "site": "default",
            "adapter": "local-classic",
        },
        "selected_target": {
            "profile": "guest",
            "controller": "local",
            "site": "guest",
            "adapter": "local-classic",
        },
    }
    assert controller.calls == []


def test_apply_requires_an_identity_for_a_target_bound_plan() -> None:
    controller = FakeController()
    plan = Plan(target=TargetIdentity("office", "local", "default"))

    with pytest.raises(PlanTargetMismatchError) as caught:
        apply_plan(controller, plan)

    assert caught.value.actual is None
    assert controller.calls == []


def test_wlan_create_finalize_failure_marks_partial_resource_state() -> None:
    controller = FakeController(fail_on_call=3)
    plan = Plan(
        diffs=[
            ResourceDiff(
                kind="network",
                action="create",
                name="Home",
                payload={"name": "Home", "purpose": "corporate"},
            ),
            ResourceDiff(
                kind="wlan",
                action="create",
                name="Home",
                source={
                    "name": "Home",
                    "ssid": "Home",
                    "network": "Home",
                    "bands": ["5g"],
                    "security": "open",
                },
            ),
        ]
    )

    with pytest.raises(PlanApplyError) as caught:
        apply_plan(controller, plan)

    error = caught.value
    assert error.resource == "wlan/Home"
    assert error.phase == "wlan"
    assert error.partial_request is True
    assert error.state == "partial"
    assert error.completed[0] == "network/Home:create"
    assert controller._wlans[0]["name"] == "Home"
    assert "automatic_rollback=false" in str(error)


def test_prune_failure_reports_confirmed_wlan_delete_and_network_recovery() -> None:
    controller = FakeController(
        networks=[{"_id": "network-1", "name": "Old", "purpose": "corporate"}],
        wlans=[{"_id": "wlan-1", "name": "Old", "networkconf_id": "network-1"}],
        fail_on_call=2,
    )
    plan = Plan(
        diffs=[
            ResourceDiff(
                kind="network",
                action="delete",
                name="Old",
                object_id="network-1",
            ),
            ResourceDiff(
                kind="wlan",
                action="delete",
                name="Old",
                object_id="wlan-1",
            ),
        ]
    )

    with pytest.raises(PlanApplyError) as caught:
        apply_plan(controller, plan)

    error = caught.value
    assert error.resource == "network/Old"
    assert error.completed[0] == "wlan/Old:delete"
    assert error.to_dict()["not_started"] == []
    assert controller._wlans == []
    assert controller._networks == [{"_id": "network-1", "name": "Old", "purpose": "corporate"}]
