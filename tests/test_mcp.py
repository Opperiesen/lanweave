import asyncio
import warnings
from pathlib import Path

import pytest


def test_optional_mcp_server_can_be_created() -> None:
    pytest.importorskip("mcp.server.fastmcp")

    from lanweave.mcp import create_server

    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message=r"Field 'lifespan' has an incomplete definition.*",
        )
        server = create_server()

    assert type(server).__name__ == "FastMCP"


def test_mcp_contract_freezes_tool_names_parameters_and_read_only_scope() -> None:
    pytest.importorskip("mcp.server.fastmcp")

    from lanweave.mcp import create_server

    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message=r"Field 'lifespan' has an incomplete definition.*",
        )
        tools = asyncio.run(create_server().list_tools())

    by_name = {tool.name: tool for tool in tools}
    assert set(by_name) == {
        "lanweave_get_health",
        "lanweave_list_devices",
        "lanweave_list_clients",
        "lanweave_export_config",
        "lanweave_validate_config",
        "lanweave_plan_changes",
    }
    assert by_name["lanweave_list_clients"].inputSchema["properties"]["include_wired"] == {
        "default": True,
        "title": "Include Wired",
        "type": "boolean",
    }
    for name in (
        "lanweave_get_health",
        "lanweave_list_devices",
        "lanweave_list_clients",
        "lanweave_export_config",
    ):
        properties = by_name[name].inputSchema["properties"]
        assert properties["config_path"]["default"] is None
        assert properties["profile"]["default"] is None
    assert (
        by_name["lanweave_validate_config"].inputSchema["properties"]["config_path"]["default"]
        == "config/network.yaml"
    )
    assert by_name["lanweave_plan_changes"].inputSchema["properties"]["prune"]["default"] is False
    assert by_name["lanweave_plan_changes"].inputSchema["properties"]["profile"]["default"] is None
    assert not any("apply" in name or "delete" in name for name in by_name)


def test_mcp_configuration_errors_use_stable_secret_free_codes(tmp_path: Path) -> None:
    pytest.importorskip("mcp.server.fastmcp")

    from lanweave.mcp import MCPToolError, create_server

    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message=r"Field 'lifespan' has an incomplete definition.*",
        )
        server = create_server()
    tool = server._tool_manager.get_tool("lanweave_validate_config")

    with pytest.raises(MCPToolError) as caught:
        tool.fn(str(tmp_path / "missing.yaml"))

    assert caught.value.code == "invalid_configuration"
    assert str(caught.value).startswith("invalid_configuration:")
    assert "password" not in str(caught.value)


def test_mcp_v2_requires_selection_and_exposes_only_sanitized_target(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    pytest.importorskip("mcp.server.fastmcp")

    from lanweave.mcp import MCPToolError, create_server

    fixture = Path(__file__).parents[1] / "tests/fixtures/profiles/config-v2-multi-target.yaml"
    config_path = tmp_path / "profiles.yaml"
    fixture_text = fixture.read_text(encoding="utf-8")
    config_path.write_text(fixture_text, encoding="utf-8")
    missing_selection_path = tmp_path / "profiles-without-selector.yaml"
    missing_selection_path.write_text(
        fixture_text.replace("profile: office\n", ""),
        encoding="utf-8",
    )
    monkeypatch.setenv("LANWEAVE_LOCAL_HOST", "https://local.example")
    monkeypatch.setenv("LANWEAVE_LOCAL_API_KEY", "local-key")

    class FakeClient:
        instances = 0

        def __init__(self, settings) -> None:
            type(self).instances += 1
            self.settings = settings

        def __enter__(self):
            return self

        def __exit__(self, *_args) -> None:
            return None

        def health(self):
            return [{"subsystem": "controller", "secret": "fixture-secret"}]

        def clients(self):
            return []

        def devices(self):
            return [{"name": "switch", "api_key": "fixture-secret"}]

        def networks(self):
            return []

        def wlans(self):
            return []

    monkeypatch.setattr("lanweave.mcp.UniFiClient", FakeClient)
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message=r"Field 'lifespan' has an incomplete definition.*",
        )
        server = create_server()

    health_tool = server._tool_manager.get_tool("lanweave_get_health")
    with pytest.raises(MCPToolError) as caught:
        health_tool.fn(config_path=str(missing_selection_path))

    assert caught.value.code == "invalid_configuration"
    assert "conflicting" not in str(caught.value)
    assert "explicit profile selection" in str(caught.value)
    assert FakeClient.instances == 0

    with pytest.raises(MCPToolError) as caught:
        health_tool.fn(config_path=str(config_path), profile="guest")

    assert caught.value.code == "invalid_configuration"
    assert "conflicting profile selectors" in str(caught.value)
    assert FakeClient.instances == 0

    health = health_tool.fn(config_path=str(config_path), profile="office")
    assert health["target"] == {
        "profile": "office",
        "controller": "local",
        "site": "default",
        "adapter": "local-classic",
    }
    assert "fixture-secret" not in str(health)

    devices_tool = server._tool_manager.get_tool("lanweave_list_devices")
    devices = devices_tool.fn(config_path=str(config_path), profile="office")
    assert devices["target"] == health["target"]
    assert devices["devices"] == [{"name": "switch", "api_key": "***"}]

    plan_tool = server._tool_manager.get_tool("lanweave_plan_changes")
    plan = plan_tool.fn(config_path=str(config_path), profile="office")
    assert plan["target"] == health["target"]
    assert "LANWEAVE_LOCAL_API_KEY" not in str(plan)

    validate_tool = server._tool_manager.get_tool("lanweave_validate_config")
    assert validate_tool.fn(str(config_path))["version"] == 2


def test_mcp_v1_environment_only_health_remains_callable(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("mcp.server.fastmcp")

    from lanweave.mcp import create_server

    monkeypatch.setenv("UNIFI_HOST", "https://legacy.example")
    monkeypatch.setenv("UNIFI_API_KEY", "legacy-key")

    class FakeClient:
        def __init__(self, settings) -> None:
            self.settings = settings

        def __enter__(self):
            return self

        def __exit__(self, *_args) -> None:
            return None

        def health(self):
            return []

        def clients(self):
            return []

        def devices(self):
            return []

    monkeypatch.setattr("lanweave.mcp.UniFiClient", FakeClient)
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message=r"Field 'lifespan' has an incomplete definition.*",
        )
        server = create_server()

    health = server._tool_manager.get_tool("lanweave_get_health").fn()

    assert health["target"] == {
        "profile": "legacy",
        "controller": "legacy",
        "site": "default",
        "adapter": "local-classic",
    }
