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
    assert (
        by_name["lanweave_validate_config"].inputSchema["properties"]["config_path"]["default"]
        == "config/network.yaml"
    )
    assert by_name["lanweave_plan_changes"].inputSchema["properties"]["prune"]["default"] is False
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
