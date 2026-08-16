import json
from pathlib import Path

from lanweave.contracts import (
    AUDIT_FORMAT_VERSION,
    CAPABILITY_FORMAT_VERSION,
    CONFIG_SCHEMA_VERSION,
    MCP_CONTRACT_VERSION,
    PLAN_FORMAT_VERSION,
    PROFILE_LAYER_VERSION,
)

ROOT = Path(__file__).parents[1]


def test_public_contract_versions_and_schemas_are_pinned() -> None:
    config_schema = json.loads(
        (ROOT / "docs/contracts/config-v1.schema.json").read_text(encoding="utf-8")
    )
    plan_schema = json.loads(
        (ROOT / "docs/contracts/plan-v1.schema.json").read_text(encoding="utf-8")
    )
    audit_schema = json.loads(
        (ROOT / "docs/contracts/audit-v1.schema.json").read_text(encoding="utf-8")
    )
    profile_schema = json.loads(
        (ROOT / "docs/contracts/profile-layer-v2.schema.json").read_text(encoding="utf-8")
    )
    config_v2_schema = json.loads(
        (ROOT / "docs/contracts/config-v2.schema.json").read_text(encoding="utf-8")
    )
    capability_schema = json.loads(
        (ROOT / "docs/contracts/adapter-capabilities-v1.schema.json").read_text(encoding="utf-8")
    )

    assert CONFIG_SCHEMA_VERSION == 1
    assert PROFILE_LAYER_VERSION == 2
    assert PLAN_FORMAT_VERSION == 1
    assert MCP_CONTRACT_VERSION == 3
    assert CAPABILITY_FORMAT_VERSION == 1
    assert config_schema["properties"]["version"]["const"] == CONFIG_SCHEMA_VERSION
    assert plan_schema["properties"]["format_version"]["const"] == PLAN_FORMAT_VERSION
    assert audit_schema["properties"]["format_version"]["const"] == AUDIT_FORMAT_VERSION
    assert config_schema["additionalProperties"] is False
    assert plan_schema["additionalProperties"] is False
    assert audit_schema["additionalProperties"] is False
    assert "target" in plan_schema["properties"]
    assert "target" not in plan_schema["required"]
    assert plan_schema["$defs"]["target"]["required"] == [
        "profile",
        "controller",
        "site",
    ]
    assert plan_schema["$defs"]["target"]["properties"]["adapter"]["default"] == ("local-classic")
    assert profile_schema["properties"]["version"]["const"] == 2
    assert profile_schema["required"] == ["version", "controllers", "profiles"]
    assert profile_schema["additionalProperties"] is False
    assert profile_schema["$defs"]["controller"]["properties"]["adapter"]["default"] == (
        "local-classic"
    )
    assert config_v2_schema["properties"]["version"]["const"] == 2
    assert config_v2_schema["required"] == [
        "version",
        "controllers",
        "profiles",
        "networks",
        "wlans",
    ]
    assert config_v2_schema["additionalProperties"] is False
    assert "nat" in config_v2_schema["properties"]
    assert "vpn" in config_schema["properties"]
    assert "vpn" in config_v2_schema["properties"]
    assert "read_only" in plan_schema["properties"]
    assert audit_schema["properties"]["read_only"]["const"] is True
    assert audit_schema["properties"]["state"]["enum"] == [
        "in-sync",
        "drifted",
        "unknown",
        "unsupported",
    ]
    assert "nat" in plan_schema["$defs"]["change"]["properties"]["kind"]["enum"]
    assert capability_schema["properties"]["format_version"]["const"] == 1
    assert capability_schema["additionalProperties"] is False


def test_profile_contract_fixtures_cover_legacy_and_multi_target_shapes() -> None:
    import yaml

    from lanweave.config import validate_config

    v1_path = ROOT / "tests/fixtures/profiles/config-v1.yaml"
    v2_path = ROOT / "tests/fixtures/profiles/config-v2-multi-target.yaml"
    v1 = yaml.safe_load(v1_path.read_text(encoding="utf-8"))
    v2 = yaml.safe_load(v2_path.read_text(encoding="utf-8"))

    validate_config(v1)
    assert v1["version"] == 1
    assert v2["version"] == 2
    assert v2["profile"] == "office"
    assert set(v2["controllers"]) == {"local", "backup"}
    assert set(v2["profiles"]) == {"office", "guest", "backup-default"}
    assert v2["profiles"]["guest"] == {"controller": "local", "site": "guest"}
    assert "fixture-secret" not in v2_path.read_text(encoding="utf-8")

    adapter_path = ROOT / "tests/fixtures/profiles/config-v2-adapters.yaml"
    adapter_config = yaml.safe_load(adapter_path.read_text(encoding="utf-8"))
    validate_config(adapter_config)
    assert adapter_config["controllers"]["cloud"]["adapter"] == "cloud-site-manager"
    assert "cloud-key" not in adapter_path.read_text(encoding="utf-8")
