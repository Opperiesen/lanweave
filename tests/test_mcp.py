import warnings

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
