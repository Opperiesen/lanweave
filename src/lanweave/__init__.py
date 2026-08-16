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
from .audit import AuditError, AuditState, audit_config, audit_exit_code
from .client import ControllerSettings, LocalClassicAdapter, UniFiClient
from .config import ConfigError, load_config, validate_config
from .contracts import (
    AUDIT_FORMAT_VERSION,
    CAPABILITY_FORMAT_VERSION,
    CONFIG_SCHEMA_VERSION,
    CONVERGENCE_FORMAT_VERSION,
    MCP_CONTRACT_VERSION,
    PLAN_FORMAT_VERSION,
    PROFILE_LAYER_VERSION,
)
from .convergence import ConvergenceState, convergence_exit_code, verify_plan_convergence
from .site_manager import SiteManagerClient, SiteManagerSettings, site_manager_capabilities
from .vpn import UnsupportedVpnVariantError, VpnError, validate_vpn

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
    "AUDIT_FORMAT_VERSION",
    "CONVERGENCE_FORMAT_VERSION",
    "AuditError",
    "AuditState",
    "audit_config",
    "audit_exit_code",
    "ConvergenceState",
    "convergence_exit_code",
    "ConfigError",
    "CAPABILITY_FORMAT_VERSION",
    "CONFIG_SCHEMA_VERSION",
    "ControllerSettings",
    "LocalClassicAdapter",
    "MCP_CONTRACT_VERSION",
    "PLAN_FORMAT_VERSION",
    "PROFILE_LAYER_VERSION",
    "SiteManagerClient",
    "SiteManagerSettings",
    "site_manager_capabilities",
    "UnsupportedCapabilityError",
    "UnsupportedVpnVariantError",
    "UniFiClient",
    "VpnError",
    "local_classic_capabilities",
    "load_config",
    "validate_config",
    "validate_vpn",
    "verify_plan_convergence",
]

__version__ = "1.0.0"
