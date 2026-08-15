"""Public Python API for safe UniFi Network automation with Lanweave."""

from .adapters import (
    ADAPTER_CLOUD_SITE_MANAGER,
    ADAPTER_LOCAL_CLASSIC,
    AUTH_MODE_API_KEY,
    AUTH_MODE_SESSION,
    Adapter,
    AdapterAuthenticationError,
    AdapterCapabilities,
    AdapterCapability,
    AdapterConfigurationError,
    AdapterError,
    AdapterOperation,
    AdapterRateLimitError,
    AdapterRegistry,
    AdapterTransportError,
    UnsupportedCapabilityError,
    local_classic_capabilities,
)
from .client import ControllerSettings, UniFiClient
from .config import ConfigError, load_config, validate_config
from .contracts import (
    CAPABILITY_FORMAT_VERSION,
    CONFIG_SCHEMA_VERSION,
    MCP_CONTRACT_VERSION,
    PLAN_FORMAT_VERSION,
)

__all__ = [
    "ADAPTER_CLOUD_SITE_MANAGER",
    "ADAPTER_LOCAL_CLASSIC",
    "AUTH_MODE_API_KEY",
    "AUTH_MODE_SESSION",
    "Adapter",
    "AdapterAuthenticationError",
    "AdapterCapability",
    "AdapterConfigurationError",
    "AdapterError",
    "AdapterOperation",
    "AdapterRateLimitError",
    "AdapterRegistry",
    "AdapterTransportError",
    "AdapterCapabilities",
    "ConfigError",
    "CAPABILITY_FORMAT_VERSION",
    "CONFIG_SCHEMA_VERSION",
    "ControllerSettings",
    "MCP_CONTRACT_VERSION",
    "PLAN_FORMAT_VERSION",
    "UnsupportedCapabilityError",
    "UniFiClient",
    "local_classic_capabilities",
    "load_config",
    "validate_config",
]

__version__ = "0.2.0"
