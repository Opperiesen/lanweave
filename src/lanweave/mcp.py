"""Read-only MCP adapter for Lanweave."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .backup import redact_snapshot
from .client import ControllerSettings, UniFiClient
from .config import load_config, load_config_with_options
from .export import export_config
from .plan import build_plan


def create_server() -> Any:
    """Create the optional FastMCP server without importing MCP in the core CLI."""
    from mcp.server.fastmcp import FastMCP

    server = FastMCP(
        "Lanweave",
        instructions=(
            "Read-only UniFi Network diagnostics and declarative planning. "
            "This server never applies changes or deletes resources."
        ),
    )

    @server.tool()
    def lanweave_get_health() -> dict[str, Any]:
        """Return controller health, connected clients and adopted devices."""
        with UniFiClient(ControllerSettings.from_env()) as client:
            return redact_snapshot({
                "health": client.health(),
                "online_clients": len(client.clients()),
                "devices": len(client.devices()),
            })

    @server.tool()
    def lanweave_list_devices() -> list[dict[str, Any]]:
        """List adopted UniFi devices."""
        with UniFiClient(ControllerSettings.from_env()) as client:
            return redact_snapshot(client.devices())

    @server.tool()
    def lanweave_list_clients(include_wired: bool = True) -> list[dict[str, Any]]:
        """List connected clients, optionally including wired clients."""
        with UniFiClient(ControllerSettings.from_env()) as client:
            clients = client.clients()
        if include_wired:
            return redact_snapshot(clients)
        return redact_snapshot([client for client in clients if client.get("is_wired") is not True])

    @server.tool()
    def lanweave_export_config() -> dict[str, Any]:
        """Export networks and WLANs as a secret-free portable configuration."""
        with UniFiClient(ControllerSettings.from_env()) as client:
            return export_config(client)

    @server.tool()
    def lanweave_validate_config(config_path: str = "config/network.yaml") -> dict[str, Any]:
        """Validate a local declarative configuration without contacting UniFi."""
        config = load_config(Path(config_path))
        return {
            "valid": True,
            "version": config["version"],
            "networks": len(config["networks"]),
            "wlans": len(config["wlans"]),
        }

    @server.tool()
    def lanweave_plan_changes(
        config_path: str = "config/network.yaml",
        prune: bool = False,
    ) -> dict[str, Any]:
        """Return a redacted plan; this tool never applies it."""
        config = load_config_with_options(Path(config_path), resolve_secrets=True)
        settings = ControllerSettings.from_env()
        if config.get("controller", {}).get("site"):
            from dataclasses import replace

            settings = replace(settings, site=config["controller"]["site"])
        with UniFiClient(settings) as client:
            return build_plan(client, config, prune=prune).to_dict()

    return server


def main() -> None:
    """Run the server over MCP stdio for local hosts."""
    create_server().run(transport="stdio")


if __name__ == "__main__":
    main()
