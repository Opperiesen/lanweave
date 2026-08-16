# Public Python API

Lanweave exposes a small, typed Python surface for operators and integrations.
The package is marked `py.typed`; consumers should import only the names listed
below. The list is frozen for v1.x and is also asserted by
[`tests/test_public_api.py`](../tests/test_public_api.py).

## Version and contract identifiers

- `__version__`
- `ADAPTER_CLOUD_SITE_MANAGER`
- `ADAPTER_LOCAL_CLASSIC`
- `AUTH_MODE_API_KEY`
- `AUTH_MODE_SESSION`
- `CONFIG_SCHEMA_VERSION`
- `PROFILE_LAYER_VERSION`
- `PLAN_FORMAT_VERSION`
- `CAPABILITY_FORMAT_VERSION`
- `AUDIT_FORMAT_VERSION`
- `CONVERGENCE_FORMAT_VERSION`
- `MCP_CONTRACT_VERSION`

## Adapter types

- `Adapter`
- `AdapterCapabilities`
- `AdapterCapability`
- `AdapterOperation`
- `AdapterRegistry`
- `AdapterAuthenticationError`
- `AdapterConfigurationError`
- `AdapterError`
- `AdapterRateLimitError`
- `AdapterTransportError`
- `UnsupportedCapabilityError`

## Configuration and planning

- `ConfigError`
- `load_config`
- `validate_config`
- `ControllerSettings`
- `UniFiClient`
- `LocalClassicAdapter`
- `Adapter`
- `AdapterRegistry`
- `AdapterCapabilities`
- `AdapterCapability`
- `AdapterOperation`
- `local_classic_capabilities`
- `site_manager_capabilities`
- `SiteManagerClient`
- `SiteManagerSettings`

## Capability and error types

- `AdapterError`
- `AdapterAuthenticationError`
- `AdapterConfigurationError`
- `AdapterRateLimitError`
- `AdapterTransportError`
- `UnsupportedCapabilityError`
- `AuditError`
- `AuditState`
- `ConvergenceState`
- `VpnError`
- `UnsupportedVpnVariantError`

## Read-only analysis

- `audit_config`
- `audit_exit_code`
- `verify_plan_convergence`
- `convergence_exit_code`
- `validate_vpn`

The Python API does not provide a second mutation path. Mutations remain behind
the reviewed plan engine and the explicit CLI confirmation boundary.
