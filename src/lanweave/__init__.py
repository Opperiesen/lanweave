"""Public Python API for safe UniFi Network automation with Lanweave."""

from .client import ControllerSettings, UniFiClient
from .config import ConfigError, load_config, validate_config
from .contracts import CONFIG_SCHEMA_VERSION, MCP_CONTRACT_VERSION, PLAN_FORMAT_VERSION

__all__ = [
    "ConfigError",
    "CONFIG_SCHEMA_VERSION",
    "ControllerSettings",
    "MCP_CONTRACT_VERSION",
    "PLAN_FORMAT_VERSION",
    "UniFiClient",
    "load_config",
    "validate_config",
]

__version__ = "0.1.0rc1"
