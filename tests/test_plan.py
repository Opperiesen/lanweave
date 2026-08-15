from typing import Any

import yaml

from lanweave.config import EXAMPLE_CONFIG
from lanweave.plan import (
    Plan,
    ResourceDiff,
    apply_plan,
    build_plan,
    network_to_unifi,
)


class FakeController:
    def __init__(
        self,
        networks: list[dict[str, Any]] | None = None,
        wlans: list[dict[str, Any]] | None = None,
    ) -> None:
        self._networks = networks or []
        self._wlans = wlans or []
        self.calls: list[tuple[str, str, Any]] = []

    def site_url(self, path: str) -> str:
        return f"/{path}"

    def networks(self) -> list[dict[str, Any]]:
        return self._networks

    def wlans(self) -> list[dict[str, Any]]:
        return self._wlans

    def post(self, path: str, json: Any = None) -> Any:
        self.calls.append(("POST", path, json))
        if path.endswith("networkconf"):
            created = {"_id": "network-created", **(json or {})}
            self._networks.append(created)
            return [created]
        created = {"_id": "wlan-created", **(json or {})}
        self._wlans.append(created)
        return [created]

    def put(self, path: str, json: Any = None) -> Any:
        self.calls.append(("PUT", path, json))
        return json

    def delete(self, path: str) -> Any:
        self.calls.append(("DELETE", path, None))
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
