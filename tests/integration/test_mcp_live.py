"""Exercise the installed read-only MCP server with the official MCP client."""

from __future__ import annotations

import asyncio
import io
import json
import os
import shutil
from pathlib import Path
from typing import Any

import pytest
import yaml

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


def _assert_secret_free(value: Any) -> None:
    serialized = json.dumps(value, sort_keys=True, default=str)
    for secret in (
        _env("LANWEAVE_INTEGRATION_HOST"),
        _env("LANWEAVE_INTEGRATION_API_KEY"),
        _env("LANWEAVE_INTEGRATION_USER"),
        _env("LANWEAVE_INTEGRATION_PASS"),
    ):
        if secret:
            assert secret not in serialized
    assert "op://" not in serialized
    for key in ("x_passphrase", "private_key", "preshared_key", "qr_code"):
        assert key not in serialized.lower()


async def _exercise_mcp(config_path: Path) -> None:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    command = shutil.which("lanweave-mcp")
    if command is None:
        pytest.fail("the installed lanweave-mcp console entry point is not on PATH")

    server_stderr = io.StringIO()
    parameters = StdioServerParameters(
        command=command,
        env=os.environ.copy(),
        cwd=Path.cwd(),
    )
    async with (
        stdio_client(parameters, errlog=server_stderr) as (read, write),
        ClientSession(read, write) as session,
    ):
        initialize = await session.initialize()
        assert initialize.serverInfo.name == "Lanweave"
        assert initialize.instructions and "read-only" in initialize.instructions.lower()

        listed = await session.list_tools()
        tool_names = {tool.name for tool in listed.tools}
        assert tool_names == {
            "lanweave_get_health",
            "lanweave_get_capabilities",
            "lanweave_list_devices",
            "lanweave_list_clients",
            "lanweave_list_vpn",
            "lanweave_audit_config",
            "lanweave_export_config",
            "lanweave_validate_config",
            "lanweave_plan_changes",
        }
        assert not any(
            any(word in name for word in ("apply", "create", "update", "delete", "prune"))
            for name in tool_names
        )

        target_arguments = {
            "config_path": str(config_path),
            "profile": "integration",
        }
        calls = {
            "lanweave_get_health": target_arguments,
            "lanweave_get_capabilities": target_arguments,
            "lanweave_list_devices": target_arguments,
            "lanweave_list_clients": {**target_arguments, "include_wired": False},
            "lanweave_list_vpn": target_arguments,
            "lanweave_audit_config": target_arguments,
            "lanweave_export_config": target_arguments,
            "lanweave_validate_config": {"config_path": str(config_path)},
            "lanweave_plan_changes": target_arguments,
        }
        results: dict[str, Any] = {}
        for name, arguments in calls.items():
            result = await session.call_tool(name, arguments)
            _assert_secret_free(result)
            if name == "lanweave_list_vpn" and not _env("LANWEAVE_INTEGRATION_API_KEY"):
                assert result.isError is True
                error_text = " ".join(getattr(item, "text", "") for item in result.content)
                assert "unsupported_capability" in error_text
                continue
            assert result.isError is False, result.content
            assert result.structuredContent is not None
            results[name] = result.structuredContent

        assert results["lanweave_get_health"]["target"]["profile"] == "integration"
        assert results["lanweave_get_capabilities"]["capabilities"]["format_version"] == 1
        assert results["lanweave_list_devices"]["target"]["controller"] == "integration"
        assert isinstance(results["lanweave_list_clients"]["clients"], list)
        assert results["lanweave_audit_config"]["read_only"] is True
        assert results["lanweave_export_config"]["target"]["site"] == (
            _env("LANWEAVE_INTEGRATION_SITE") or "default"
        )
        assert results["lanweave_validate_config"]["valid"] is True
        assert results["lanweave_plan_changes"]["target"]["profile"] == "integration"
        if _env("LANWEAVE_INTEGRATION_API_KEY"):
            vpn = results["lanweave_list_vpn"]
            assert vpn["read_only"] is True
            assert vpn["health"]["coverage"]["routes"] == ("not-reported-by-official-overview-api")

    _assert_secret_free(server_stderr.getvalue())


def test_installed_mcp_stdio_client_exercises_read_only_contract(tmp_path: Path) -> None:
    if not _env("LANWEAVE_INTEGRATION_HOST"):
        pytest.skip("live integration credentials are not configured")
    if not _env("LANWEAVE_INTEGRATION_API_KEY") and not (
        _env("LANWEAVE_INTEGRATION_USER") and _env("LANWEAVE_INTEGRATION_PASS")
    ):
        pytest.skip("set an integration API key or both session credentials")

    config_path = tmp_path / "profiles.yaml"
    config_path.write_text(
        yaml.safe_dump(_profile_config(), sort_keys=False),
        encoding="utf-8",
    )
    asyncio.run(_exercise_mcp(config_path))
