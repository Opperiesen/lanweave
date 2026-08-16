"""Exercise the installed public CLI against a protected controller."""

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
    return {
        "version": 2,
        "profile": "integration",
        "controllers": {
            "integration": {
                "host_env": "LANWEAVE_INTEGRATION_HOST",
                "verify_tls": _env("LANWEAVE_INTEGRATION_VERIFY_TLS").lower()
                not in {"0", "false", "no", "off"},
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


def _write_config(path: Path) -> None:
    path.write_text(
        yaml.safe_dump(_profile_config(), sort_keys=False),
        encoding="utf-8",
    )


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
    for name in (
        "LANWEAVE_INTEGRATION_API_KEY",
        "LANWEAVE_INTEGRATION_USER",
        "LANWEAVE_INTEGRATION_PASS",
    ):
        assert name not in output
    for value in (
        _env("LANWEAVE_INTEGRATION_API_KEY"),
        _env("LANWEAVE_INTEGRATION_USER"),
        _env("LANWEAVE_INTEGRATION_PASS"),
    ):
        if value:
            assert value not in output
    assert "op://" not in output


def _json_stdout(result: subprocess.CompletedProcess[str]) -> Any:
    _assert_secret_free(result)
    assert result.stdout.strip(), result.stderr[-1000:]
    return json.loads(result.stdout)


def _assert_success(result: subprocess.CompletedProcess[str]) -> None:
    _assert_secret_free(result)
    assert result.returncode == 0, result.stderr[-2000:]


def test_installed_cli_read_only_matrix(
    integration_client: UniFiClient,
    tmp_path: Path,
) -> None:
    """Run every documented read-only wrapper through the console script."""

    del integration_client  # The fixture performs the protected-credential skip/guard.
    config = tmp_path / "profiles.yaml"
    _write_config(config)

    version = _run_cli("--version")
    _assert_success(version)
    assert version.stdout.strip() == "1.0.0"

    profiles_list = _run_cli("profiles", "list", "--config", str(config))
    _assert_success(profiles_list)
    assert "profile=integration controller=integration" in profiles_list.stdout
    assert "LANWEAVE_" not in profiles_list.stdout

    profiles_validate = _run_cli("profiles", "validate", "--config", str(config))
    _assert_success(profiles_validate)

    validate = _run_cli("validate", "--config", str(config))
    _assert_success(validate)

    capabilities = _run_cli(
        "capabilities",
        "--config",
        str(config),
        "--profile",
        "integration",
        "--output",
        "json",
    )
    capabilities_json = _json_stdout(capabilities)
    assert capabilities.returncode == 0
    assert capabilities_json["target"]["profile"] == "integration"
    assert capabilities_json["capabilities"]["format_version"] == 1

    doctor = _run_cli(
        "doctor",
        "--check",
        "--config",
        str(config),
        "--profile",
        "integration",
    )
    _assert_success(doctor)
    assert "controller reachable:" in doctor.stdout

    status_table = _run_cli(
        "status",
        "--config",
        str(config),
        "--profile",
        "integration",
    )
    _assert_success(status_table)
    assert "devices:" in status_table.stdout

    status_json = _run_cli(
        "status",
        "--config",
        str(config),
        "--profile",
        "integration",
        "--output",
        "json",
    )
    status_document = _json_stdout(status_json)
    assert status_json.returncode == 0
    assert status_document["target"]["profile"] == "integration"

    clients_table = _run_cli(
        "clients",
        "--config",
        str(config),
        "--profile",
        "integration",
    )
    _assert_success(clients_table)
    assert "clients:" in clients_table.stdout

    clients_json = _run_cli(
        "clients",
        "--config",
        str(config),
        "--profile",
        "integration",
        "--output",
        "json",
    )
    clients_document = _json_stdout(clients_json)
    assert clients_json.returncode == 0
    assert isinstance(clients_document, list)

    export_path = tmp_path / "export.yaml"
    export = _run_cli(
        "export",
        "--config",
        str(config),
        "--profile",
        "integration",
        "--out",
        str(export_path),
    )
    _assert_success(export)
    exported = yaml.safe_load(export_path.read_text(encoding="utf-8"))
    assert isinstance(exported, dict)
    exported_text = export_path.read_text(encoding="utf-8")
    assert _env("LANWEAVE_INTEGRATION_HOST") not in exported_text
    assert _env("LANWEAVE_INTEGRATION_API_KEY") not in exported_text

    backup_dir = tmp_path / "backup"
    backup = _run_cli(
        "backup",
        "--config",
        str(config),
        "--profile",
        "integration",
        "--output",
        str(backup_dir),
    )
    if _env("LANWEAVE_INTEGRATION_API_KEY"):
        _assert_secret_free(backup)
        assert backup.returncode == 2
        assert "unsupported_capability" in backup.stderr
    else:
        _assert_success(backup)
        backup_files = tuple(backup_dir.glob("*.json"))
        assert len(backup_files) == 1
        backup_document = json.loads(backup_files[0].read_text(encoding="utf-8"))
        assert isinstance(backup_document, dict)

    plan_table = _run_cli(
        "plan",
        "--config",
        str(config),
        "--profile",
        "integration",
    )
    _assert_success(plan_table)
    assert "Plan:" in plan_table.stdout

    plan_json = _run_cli(
        "plan",
        "--config",
        str(config),
        "--profile",
        "integration",
        "--output",
        "json",
    )
    plan_document = _json_stdout(plan_json)
    assert plan_json.returncode == 0
    assert plan_document["target"]["profile"] == "integration"

    audit_table = _run_cli(
        "audit",
        "--config",
        str(config),
        "--profile",
        "integration",
    )
    _assert_secret_free(audit_table)
    assert audit_table.returncode in {0, 1, 2}
    assert "Audit:" in audit_table.stdout or "operation failed:" in audit_table.stderr

    audit_json = _run_cli(
        "audit",
        "--config",
        str(config),
        "--profile",
        "integration",
        "--output",
        "json",
    )
    audit_document = _json_stdout(audit_json)
    assert audit_json.returncode in {0, 1, 2}
    assert audit_document["state"] in {"in-sync", "drifted", "unknown", "unsupported"}
    expected_audit_codes = {"in-sync": 0, "drifted": 1, "unknown": 2, "unsupported": 2}
    assert audit_json.returncode == expected_audit_codes[audit_document["state"]]

    vpn_table = _run_cli(
        "vpn",
        "--config",
        str(config),
        "--profile",
        "integration",
    )
    _assert_secret_free(vpn_table)
    vpn_json = _run_cli(
        "vpn",
        "--config",
        str(config),
        "--profile",
        "integration",
        "--output",
        "json",
    )
    if _env("LANWEAVE_INTEGRATION_API_KEY"):
        vpn_document = _json_stdout(vpn_json)
        assert vpn_json.returncode == 0
        assert vpn_document["read_only"] is True
        assert vpn_document["health"]["coverage"]["routes"] == (
            "not-reported-by-official-overview-api"
        )
        _assert_success(vpn_table)
    else:
        assert vpn_table.returncode == 2
        assert vpn_json.returncode == 2
        assert "unsupported_capability" in vpn_json.stderr
