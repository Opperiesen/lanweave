"""Exercise the public CLI apply/convergence path on an isolated network."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml

from lanweave.client import UniFiClient

pytestmark = pytest.mark.integration_mutation


def _env(name: str) -> str:
    return os.getenv(name, "").strip()


def _cli_config(name: str, domain_name: str) -> dict[str, Any]:
    return {
        "version": 2,
        "profile": "integration",
        "controllers": {
            "integration": {
                "host_env": "LANWEAVE_INTEGRATION_HOST",
                "verify_tls": _env("LANWEAVE_INTEGRATION_VERIFY_TLS").lower()
                not in {"0", "false", "no", "off"},
                "auth": {
                    "username_env": "LANWEAVE_INTEGRATION_USER",
                    "password_env": "LANWEAVE_INTEGRATION_PASS",
                },
            }
        },
        "profiles": {
            "integration": {
                "controller": "integration",
                "site": _env("LANWEAVE_INTEGRATION_SITE") or "default",
            }
        },
        "networks": [
            {
                "name": name,
                "purpose": "vlan-only",
                "subnet": _env("LANWEAVE_INTEGRATION_MUTATION_SUBNET"),
                "vlan": int(_env("LANWEAVE_INTEGRATION_MUTATION_VLAN")),
                "domain_name": domain_name,
            }
        ],
        "wlans": [],
    }


def _run_cli(*arguments: str) -> subprocess.CompletedProcess[str]:
    executable = shutil.which("lanweave")
    if executable is None:
        pytest.fail("the installed lanweave console entry point is not on PATH")
    return subprocess.run(
        [executable, *arguments],
        check=False,
        capture_output=True,
        text=True,
        env=os.environ.copy(),
        timeout=90,
    )


def _assert_secret_free(result: subprocess.CompletedProcess[str]) -> None:
    output = result.stdout + result.stderr
    for value in (
        _env("LANWEAVE_INTEGRATION_API_KEY"),
        _env("LANWEAVE_INTEGRATION_USER"),
        _env("LANWEAVE_INTEGRATION_PASS"),
    ):
        if value:
            assert value not in output
    assert "op://" not in output


def _assert_converged(result: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    _assert_secret_free(result)
    assert result.returncode == 0, result.stderr[-2000:]
    assert result.stdout.strip()
    plan = json.loads(result.stdout)
    convergence_start = result.stderr.find("{")
    assert convergence_start >= 0, result.stderr
    convergence = json.loads(result.stderr[convergence_start:])
    assert convergence["state"] == "converged"
    assert convergence["read_only"] is True
    return plan


def _find_network(client: UniFiClient, name: str) -> dict[str, Any] | None:
    return next((item for item in client.networks() if item.get("name") == name), None)


def test_public_cli_apply_emits_convergence_and_cleans_up(
    integration_client: UniFiClient,
    tmp_path: Path,
) -> None:
    if _env("LANWEAVE_INTEGRATION_API_MODE") != "local-classic-session":
        pytest.skip("public CLI mutation evidence requires local session authentication")
    if _env("LANWEAVE_INTEGRATION_MUTATIONS").lower() not in {"1", "true", "yes", "on"}:
        pytest.skip("mutation suite is disabled")
    if _env("LANWEAVE_INTEGRATION_MUTATION_CONFIRM") != "I_UNDERSTAND":
        pytest.skip("mutation confirmation is not enabled")

    prefix = _env("LANWEAVE_INTEGRATION_MUTATION_PREFIX")
    if not prefix.startswith("lanweave-ci-"):
        pytest.fail("mutation prefix must start with lanweave-ci-")
    name = f"{prefix}{_env('LANWEAVE_INTEGRATION_RUN_ID')}-cli-network"
    if len(name) > 64:
        pytest.fail("CLI mutation network name must be at most 64 characters")
    if _find_network(integration_client, name) is not None:
        pytest.fail(f"refusing to reuse existing CLI mutation target {name}")

    initial = _cli_config(name, f"{name}.lanweave.invalid")
    updated = _cli_config(name, f"updated.{name}.lanweave.invalid")
    initial_path = tmp_path / "initial.yaml"
    updated_path = tmp_path / "updated.yaml"
    initial_path.write_text(yaml.safe_dump(initial, sort_keys=False), encoding="utf-8")
    updated_path.write_text(yaml.safe_dump(updated, sort_keys=False), encoding="utf-8")

    created_id: str | None = None
    try:
        create = _run_cli(
            "apply",
            "--config",
            str(initial_path),
            "--profile",
            "integration",
            "--yes",
            "--output",
            "json",
        )
        create_plan = _assert_converged(create)
        assert [(item["action"], item["name"]) for item in create_plan["diffs"]] == [
            ("create", name)
        ]

        created = _find_network(integration_client, name)
        assert created is not None
        created_id = str(created.get("_id") or created.get("id") or "")
        assert created_id

        update = _run_cli(
            "apply",
            "--config",
            str(updated_path),
            "--profile",
            "integration",
            "--yes",
            "--output",
            "json",
        )
        update_plan = _assert_converged(update)
        assert [(item["action"], item["name"]) for item in update_plan["diffs"]] == [
            ("update", name)
        ]

        changed = _find_network(integration_client, name)
        assert changed is not None
        assert changed.get("domain_name") == updated["networks"][0]["domain_name"]
    finally:
        remaining = _find_network(integration_client, name)
        if remaining is not None:
            remaining_id = str(remaining.get("_id") or remaining.get("id") or "")
            if not created_id or remaining_id != created_id or remaining.get("name") != name:
                raise AssertionError("refusing to delete a non-exact CLI mutation target")
            integration_client.delete(
                f"{integration_client.site_url('rest/networkconf')}/{remaining_id}"
            )

    assert _find_network(integration_client, name) is None
