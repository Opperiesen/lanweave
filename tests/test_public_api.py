from __future__ import annotations

import json
from pathlib import Path

import lanweave

ROOT = Path(__file__).parents[1]

EXPECTED_PUBLIC_EXPORTS = (
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
)


def test_public_python_api_is_frozen_for_v1() -> None:
    assert tuple(lanweave.__all__) == EXPECTED_PUBLIC_EXPORTS
    assert lanweave.__version__ == "1.0.0"


def test_public_contract_documents_match_exported_versions() -> None:
    contracts = (ROOT / "docs/contracts.md").read_text(encoding="utf-8")
    assert "v1.0" in contracts
    assert "MCP contract v3" in contracts
    assert "Change and deprecation policy" in contracts

    for schema_name in (
        "config-v1.schema.json",
        "config-v2.schema.json",
        "plan-v1.schema.json",
        "adapter-capabilities-v1.schema.json",
        "audit-v1.schema.json",
        "convergence-v1.schema.json",
    ):
        schema = json.loads((ROOT / "docs/contracts" / schema_name).read_text(encoding="utf-8"))
        assert schema.get("additionalProperties") is False


def test_package_declares_typing_information() -> None:
    assert (ROOT / "src/lanweave/py.typed").is_file()
