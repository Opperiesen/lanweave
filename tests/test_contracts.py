import json
from pathlib import Path

from lanweave.contracts import CONFIG_SCHEMA_VERSION, MCP_CONTRACT_VERSION, PLAN_FORMAT_VERSION

ROOT = Path(__file__).parents[1]


def test_public_contract_versions_and_schemas_are_pinned() -> None:
    config_schema = json.loads(
        (ROOT / "docs/contracts/config-v1.schema.json").read_text(encoding="utf-8")
    )
    plan_schema = json.loads(
        (ROOT / "docs/contracts/plan-v1.schema.json").read_text(encoding="utf-8")
    )

    assert CONFIG_SCHEMA_VERSION == 1
    assert PLAN_FORMAT_VERSION == 1
    assert MCP_CONTRACT_VERSION == 1
    assert config_schema["properties"]["version"]["const"] == CONFIG_SCHEMA_VERSION
    assert plan_schema["properties"]["format_version"]["const"] == PLAN_FORMAT_VERSION
    assert config_schema["additionalProperties"] is False
    assert plan_schema["additionalProperties"] is False
