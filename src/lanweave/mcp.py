"""Read-only MCP adapter for Lanweave."""

from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from pathlib import Path
from typing import Any

import httpx

from .adapters import AdapterError
from .backup import redact_snapshot
from .client import CredentialsError, UniFiClient
from .config import ConfigError, load_config, load_config_with_options
from .contracts import CONFIG_SCHEMA_VERSION, MCP_CONTRACT_VERSION
from .export import export_config
from .plan import build_plan
from .profiles import (
    ResolvedTarget,
    auth_mode_for_identity,
    resolve_identity,
    resolve_target,
)
from .runtime import capabilities_for_target, create_adapter
from .site_manager import SiteManagerClient


class MCPToolError(RuntimeError):
    """Stable, secret-free error raised by a read-only MCP tool."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        super().__init__(f"{code}: {detail}")


def _safe_tool(function: Callable[..., Any]) -> Callable[..., Any]:
    """Translate implementation failures into the public MCP error contract."""

    @wraps(function)
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        try:
            return function(*args, **kwargs)
        except MCPToolError:
            raise
        except ConfigError as exc:
            raise MCPToolError("invalid_configuration", str(exc)) from None
        except CredentialsError as exc:
            raise MCPToolError("credentials_error", str(exc)) from None
        except AdapterError as exc:
            raise MCPToolError(exc.code, str(exc)) from None
        except (RuntimeError, httpx.HTTPError):
            raise MCPToolError("controller_error", "controller operation failed") from None
        except Exception:
            raise MCPToolError("internal_error", "tool execution failed") from None

    return wrapped


def _resolve_mcp_target(config_path: str | None, profile: str | None) -> ResolvedTarget:
    config = load_config(Path(config_path)) if config_path is not None else None
    return resolve_target(config, profile=profile)


def _resolve_mcp_capabilities(
    config_path: str | None,
    profile: str | None,
) -> tuple[Any, Any]:
    config = load_config(Path(config_path)) if config_path is not None else None
    identity = resolve_identity(config, profile=profile)
    auth_mode = auth_mode_for_identity(config, identity)
    return identity, capabilities_for_target(identity.adapter, auth_mode)


def _create_mcp_adapter(target: ResolvedTarget) -> Any:
    return create_adapter(
        target,
        local_factory=UniFiClient,
        cloud_factory=SiteManagerClient.from_controller_settings,
    )


def _capabilities_for_adapter(client: Any, target: ResolvedTarget) -> Any:
    capabilities = getattr(client, "capabilities", None)
    if capabilities is not None:
        return capabilities
    auth_mode = "api-key" if getattr(target.settings, "api_key", "") else "session"
    return capabilities_for_target(target.identity.adapter, auth_mode)


def create_server() -> Any:
    """Create the optional FastMCP server without importing MCP in the core CLI."""
    from mcp.server.fastmcp import FastMCP

    server = FastMCP(
        "Lanweave",
        instructions=(
            "Read-only UniFi Network diagnostics and declarative planning. "
            f"MCP contract v{MCP_CONTRACT_VERSION}. "
            "This server never applies changes or deletes resources."
        ),
    )

    @server.tool()
    @_safe_tool
    def lanweave_get_health(
        config_path: str | None = None,
        profile: str | None = None,
    ) -> dict[str, Any]:
        """Return target identity, adapter capabilities, health and devices."""
        target = _resolve_mcp_target(config_path, profile)
        with _create_mcp_adapter(target) as client:
            capabilities = _capabilities_for_adapter(client, target)
            result: dict[str, Any] = {
                "target": target.target_dict(),
                "capabilities": capabilities.to_dict(),
                "health": client.health(),
                "devices": len(client.devices()),
            }
            if capabilities.supports("clients", "read"):
                result["online_clients"] = len(client.clients())
            return redact_snapshot(result)

    @server.tool()
    @_safe_tool
    def lanweave_get_capabilities(
        config_path: str | None = None,
        profile: str | None = None,
    ) -> dict[str, Any]:
        """Return target and adapter capabilities without contacting a target."""
        identity, capabilities = _resolve_mcp_capabilities(config_path, profile)
        return {"target": identity.to_dict(), "capabilities": capabilities.to_dict()}

    @server.tool()
    @_safe_tool
    def lanweave_list_devices(
        config_path: str | None = None,
        profile: str | None = None,
    ) -> dict[str, Any]:
        """Return target identity and adopted UniFi devices."""
        target = _resolve_mcp_target(config_path, profile)
        with _create_mcp_adapter(target) as client:
            devices = client.devices()
        return {
            "target": target.target_dict(),
            "capabilities": _capabilities_for_adapter(client, target).to_dict(),
            "devices": redact_snapshot(devices),
        }

    @server.tool()
    @_safe_tool
    def lanweave_list_clients(
        include_wired: bool = True,
        config_path: str | None = None,
        profile: str | None = None,
    ) -> dict[str, Any]:
        """Return target identity and connected clients."""
        target = _resolve_mcp_target(config_path, profile)
        with _create_mcp_adapter(target) as client:
            clients = client.clients()
        if include_wired:
            filtered = clients
        else:
            filtered = [client for client in clients if client.get("is_wired") is not True]
        return {"target": target.target_dict(), "clients": redact_snapshot(filtered)}

    @server.tool()
    @_safe_tool
    def lanweave_export_config(
        config_path: str | None = None,
        profile: str | None = None,
    ) -> dict[str, Any]:
        """Return target identity and a secret-free portable configuration."""
        target = _resolve_mcp_target(config_path, profile)
        with _create_mcp_adapter(target) as client:
            exported = export_config(client)
        return {"target": target.target_dict(), "config": exported}

    @server.tool()
    @_safe_tool
    def lanweave_validate_config(config_path: str = "config/network.yaml") -> dict[str, Any]:
        """Validate a local declarative configuration without contacting UniFi."""
        config = load_config(Path(config_path))
        firewall = config.get("firewall") or {}
        return {
            "valid": True,
            "version": config.get("version", CONFIG_SCHEMA_VERSION),
            "networks": len(config["networks"]),
            "wlans": len(config["wlans"]),
            "dns": len(config.get("dns", [])),
            "firewall": {
                "zones": len(firewall.get("zones", [])),
                "address_groups": len(firewall.get("address_groups", [])),
                "port_groups": len(firewall.get("port_groups", [])),
                "rules": len(firewall.get("rules", [])),
            },
        }

    @server.tool()
    @_safe_tool
    def lanweave_plan_changes(
        config_path: str = "config/network.yaml",
        prune: bool = False,
        profile: str | None = None,
    ) -> dict[str, Any]:
        """Return a target-bound redacted plan; this tool never applies it."""
        path = Path(config_path)
        target_config = load_config(path)
        config = load_config_with_options(path, resolve_secrets=True)
        target = resolve_target(target_config, profile=profile)
        with _create_mcp_adapter(target) as client:
            return build_plan(
                client,
                config,
                prune=prune,
                target=target.identity,
            ).to_dict()

    return server


def main() -> None:
    """Run the server over MCP stdio for local hosts."""
    create_server().run(transport="stdio")


if __name__ == "__main__":
    main()
