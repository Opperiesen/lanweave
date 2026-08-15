"""Guarded profile selection and target-safety probes against a local controller."""

from __future__ import annotations

import os
from typing import Any

import pytest

from lanweave.client import UniFiClient
from lanweave.plan import Plan, PlanTargetMismatchError, ResourceDiff, apply_plan, build_plan
from lanweave.profiles import TargetIdentity, resolve_target

pytestmark = pytest.mark.integration


def _env(name: str) -> str:
    return os.getenv(name, "").strip()


def _profile_config() -> dict[str, Any]:
    if _env("LANWEAVE_INTEGRATION_API_KEY"):
        auth = {"api_key_env": "LANWEAVE_INTEGRATION_API_KEY"}
    else:
        auth = {
            "username_env": "LANWEAVE_INTEGRATION_USER",
            "password_env": "LANWEAVE_INTEGRATION_PASS",
        }
    verify_tls = _env("LANWEAVE_INTEGRATION_VERIFY_TLS").lower()
    return {
        "version": 2,
        "profile": "integration",
        "controllers": {
            "integration": {
                "host_env": "LANWEAVE_INTEGRATION_HOST",
                "verify_tls": verify_tls not in {"0", "false", "no", "off"},
                "auth": auth,
            }
        },
        "profiles": {
            "integration": {
                "controller": "integration",
                "site": _env("LANWEAVE_INTEGRATION_SITE") or "default",
            }
        },
        "networks": [],
        "wlans": [],
    }


def test_profile_target_supports_read_only_discovery_and_planning(
    integration_client: UniFiClient,
) -> None:
    config = _profile_config()
    target = resolve_target(config, environ=os.environ)

    assert target.identity == TargetIdentity(
        profile="integration",
        controller="integration",
        site=_env("LANWEAVE_INTEGRATION_SITE") or "default",
    )

    with UniFiClient(target.settings) as client:
        assert isinstance(client.health(), list)
        assert isinstance(client.devices(), list)
        assert isinstance(client.clients(), list)
        assert isinstance(client.networks(), list)
        assert isinstance(client.wlans(), list)

        plan = build_plan(client, config, target=target.identity)

    assert plan.to_dict()["target"] == target.identity.to_dict()
    assert _env("LANWEAVE_INTEGRATION_HOST") not in str(plan.to_dict())
    assert "LANWEAVE_INTEGRATION_API_KEY" not in str(plan.to_dict())
    assert integration_client.settings.site == target.settings.site


def test_wrong_profile_target_is_rejected_before_any_mutation(
    integration_client: UniFiClient,
) -> None:
    target = resolve_target(_profile_config(), environ=os.environ)
    plan = Plan(
        target=target.identity,
        diffs=[
            ResourceDiff(
                kind="network",
                action="create",
                name="lanweave-profile-safety-check",
                payload={"name": "lanweave-profile-safety-check", "purpose": "vlan-only"},
            )
        ],
    )

    with pytest.raises(PlanTargetMismatchError) as caught:
        apply_plan(
            integration_client,
            plan,
            target=TargetIdentity("wrong-profile", "integration", target.settings.site),
        )

    assert caught.value.to_dict()["error"] == "plan_target_mismatch"
