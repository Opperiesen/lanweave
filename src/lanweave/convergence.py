"""Read-only post-apply convergence verification and recovery evidence."""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import Any

from .adapters import Adapter
from .audit import AUDIT_RESOURCE_ORDER, AuditState, audit_config
from .contracts import CONVERGENCE_FORMAT_VERSION
from .plan import Plan
from .profiles import TargetIdentity


class ConvergenceState(StrEnum):
    """Stable states exposed by the post-apply verification contract."""

    CONVERGED = "converged"
    DRIFTED = "drifted"
    UNCERTAIN = "uncertain"
    UNSUPPORTED = "unsupported"


_RESOURCE_BY_KIND = {
    "network": "networks",
    "wlan": "wlans",
    "dns": "dns",
    "firewall_zone": "firewall",
    "firewall_group": "firewall",
    "firewall_rule": "firewall",
    "nat": "nat",
}
_AUDIT_TO_CONVERGENCE = {
    AuditState.IN_SYNC.value: ConvergenceState.CONVERGED,
    AuditState.DRIFTED.value: ConvergenceState.DRIFTED,
    AuditState.UNKNOWN.value: ConvergenceState.UNCERTAIN,
    AuditState.UNSUPPORTED.value: ConvergenceState.UNSUPPORTED,
}
_STATE_PRIORITY = {
    ConvergenceState.CONVERGED: 0,
    ConvergenceState.DRIFTED: 1,
    ConvergenceState.UNSUPPORTED: 2,
    ConvergenceState.UNCERTAIN: 3,
}


def _affected_resources(plan: Plan) -> list[str]:
    resources = set()
    for diff in plan.diffs:
        if diff.action == "noop":
            continue
        try:
            resources.add(_RESOURCE_BY_KIND[diff.kind])
        except KeyError:
            raise ValueError(f"cannot verify unsupported plan resource: {diff.kind}") from None
    return sorted(resources, key=AUDIT_RESOURCE_ORDER.index)


def _resource_evidence(item: Mapping[str, Any]) -> dict[str, Any]:
    evidence: dict[str, Any] = {
        "resource": item["resource"],
        "state": _AUDIT_TO_CONVERGENCE[item["state"]].value,
        "declared_count": item["declared_count"],
        "observed_count": item["observed_count"],
        "findings": item.get("findings", []),
    }
    if item.get("coverage") is not None:
        evidence["coverage"] = item["coverage"]
    return evidence


def _overall_state(states: list[ConvergenceState]) -> ConvergenceState:
    if not states:
        return ConvergenceState.CONVERGED
    return max(states, key=_STATE_PRIORITY.__getitem__)


def _summary(resources: list[Mapping[str, Any]]) -> dict[str, int]:
    return {
        state.value: sum(item["state"] == state.value for item in resources)
        for state in ConvergenceState
    }


def _recovery_guidance(state: ConvergenceState) -> list[str]:
    if state is ConvergenceState.CONVERGED:
        return ["The affected resource families match the reviewed plan."]
    if state is ConvergenceState.DRIFTED:
        return [
            "Generate a fresh plan before retrying.",
            "Review the live differences and reconcile them through a new explicit apply.",
            "Do not repeat the previous plan blindly.",
        ]
    if state is ConvergenceState.UNSUPPORTED:
        return [
            "The selected adapter cannot prove convergence for every affected resource family.",
            "Use a compatible read-only adapter or inspect the controller before retrying.",
            "Do not treat an unsupported readback as confirmation of success.",
        ]
    return [
        "Read the affected controller state again before retrying.",
        "Treat failed or timed-out requests as uncertain; no automatic rollback was attempted.",
        "Generate a fresh plan and retry only that reviewed plan.",
    ]


def _inconclusive_report(
    plan: Plan,
    affected: list[str],
    *,
    target: TargetIdentity | None,
    reason: str,
) -> dict[str, Any]:
    resources = [
        {
            "resource": resource,
            "state": ConvergenceState.UNCERTAIN.value,
            "declared_count": None,
            "observed_count": None,
            "findings": [],
            "coverage": {"status": "uncertain", "reason": reason},
        }
        for resource in affected
    ]
    result: dict[str, Any] = {
        "format_version": CONVERGENCE_FORMAT_VERSION,
        "read_only": True,
        "state": ConvergenceState.UNCERTAIN.value,
        "plan_summary": plan.summary(),
        "affected_resources": affected,
        "summary": _summary(resources),
        "resources": resources,
        "recovery": _recovery_guidance(ConvergenceState.UNCERTAIN),
    }
    if target is not None:
        result["target"] = target.to_dict()
    return result


def verify_plan_convergence(
    client: Adapter,
    config: Mapping[str, Any],
    plan: Plan,
    *,
    target: TargetIdentity | None = None,
) -> dict[str, Any]:
    """Re-read only affected families and classify the post-apply outcome.

    Verification never writes, retries, compensates or rolls back. Any read
    failure becomes ``uncertain`` so callers cannot mistake missing evidence
    for convergence.
    """
    affected = _affected_resources(plan)
    if not affected:
        result: dict[str, Any] = {
            "format_version": CONVERGENCE_FORMAT_VERSION,
            "read_only": True,
            "state": ConvergenceState.CONVERGED.value,
            "plan_summary": plan.summary(),
            "affected_resources": [],
            "summary": _summary([]),
            "resources": [],
            "recovery": _recovery_guidance(ConvergenceState.CONVERGED),
        }
        if target is not None:
            result["target"] = target.to_dict()
        return result

    try:
        audit = audit_config(client, config, target=target, resources=affected)
    except Exception:
        return _inconclusive_report(
            plan,
            affected,
            target=target,
            reason="post_apply_readback_failed",
        )

    resources = [_resource_evidence(item) for item in audit["resources"]]
    state = _overall_state([ConvergenceState(item["state"]) for item in resources])
    result = {
        "format_version": CONVERGENCE_FORMAT_VERSION,
        "read_only": True,
        "state": state.value,
        "plan_summary": plan.summary(),
        "affected_resources": affected,
        "summary": _summary(resources),
        "resources": resources,
        "recovery": _recovery_guidance(state),
    }
    if audit.get("capabilities") is not None:
        result["capabilities"] = audit["capabilities"]
    if target is not None:
        result["target"] = target.to_dict()
    return result


def convergence_exit_code(result: Mapping[str, Any]) -> int:
    """Map a convergence result to a stable CLI exit code."""
    state = result.get("state")
    if state == ConvergenceState.CONVERGED.value:
        return 0
    if state == ConvergenceState.DRIFTED.value:
        return 1
    return 2


__all__ = [
    "CONVERGENCE_FORMAT_VERSION",
    "ConvergenceState",
    "convergence_exit_code",
    "verify_plan_convergence",
]
