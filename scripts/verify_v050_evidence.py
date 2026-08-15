"""Check the offline v0.5.0 firewall evidence and release gates."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

import yaml

from lanweave.config import validate_config
from lanweave.firewall import (
    UnsupportedFirewallVariantError,
    normalize_controller_traffic_matching_list,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "tests" / "fixtures" / "firewall"
EVIDENCE = ROOT / "docs" / "evidence" / "v0.5.0-firewall.md"


def _fail(message: str) -> None:
    raise SystemExit(f"v0.5 evidence verification: {message}")


def _required_documents() -> None:
    required_text = {
        "docs/roadmap-v0.5.0.md": "v0.5.0 roadmap",
        "docs/migration-v0.5.md": "Migration de v0.4.0 vers v0.5.0",
        "docs/release-v0.5.0.md": "Lanweave v0.5.0",
        "docs/firewall.md": "Firewall déclaratif",
        "docs/contracts.md": "firewall",
        "docs/compatibility.md": "firewall/policies",
        "docs/recovery.md": "Firewall",
        ".github/workflows/integration.yml": "run_firewall_mutations",
        "tests/integration/test_firewall_mutations.py": "authorized firewall lifecycle",
        "examples/firewall.yaml": "firewall:",
    }
    for relative, marker in required_text.items():
        path = ROOT / relative
        if not path.is_file():
            _fail(f"missing v0.5 evidence file: {relative}")
        if marker not in path.read_text(encoding="utf-8"):
            _fail(f"evidence marker missing from {relative}: {marker}")
    if not EVIDENCE.is_file() or "Offline fixture gate: passed" not in EVIDENCE.read_text(
        encoding="utf-8"
    ):
        _fail("offline firewall evidence is missing")


def _verify_example() -> None:
    path = ROOT / "examples" / "firewall.yaml"
    text = path.read_text(encoding="utf-8")
    if "op://" in text or re.search(
        r"^\s*(?:password|api_key|token|secret)\s*:", text, re.MULTILINE
    ):
        _fail("credential marker found in firewall example")
    document = yaml.safe_load(text)
    if not isinstance(document, dict):
        _fail("firewall example is not a mapping")
    try:
        validate_config(document)
    except Exception as exc:
        _fail(f"firewall example does not validate: {type(exc).__name__}")
    firewall = document.get("firewall")
    if not isinstance(firewall, dict) or not firewall.get("rules"):
        _fail("firewall example must contain at least one rule")


def _verify_fixtures() -> None:
    paths = sorted(FIXTURE_DIR.glob("*.json"))
    if not paths:
        _fail("no firewall fixtures found")
    forbidden = re.compile(
        r"(?:op://|x-api-key|authorization|api[_-]?key|password|secret|token)",
        re.IGNORECASE,
    )
    names = {path.name for path in paths}
    for required in (
        "firewall-empty-page.json",
        "firewall-malformed-page.json",
        "firewall-traffic-matching-list-unsupported.json",
        "firewall-traffic-matching-list-system.json",
    ):
        if required not in names:
            _fail(f"required firewall fixture is missing: {required}")

    for path in paths:
        text = path.read_text(encoding="utf-8")
        if forbidden.search(text):
            _fail(f"credential marker found in fixture: {path.name}")
        try:
            document: Any = json.loads(text)
        except json.JSONDecodeError as exc:
            _fail(f"invalid JSON fixture {path.name}: {exc}")
        if "unsupported" in path.name:
            try:
                normalize_controller_traffic_matching_list(document)
            except UnsupportedFirewallVariantError:
                continue
            except Exception as exc:
                _fail(f"unsupported fixture failed with the wrong error: {type(exc).__name__}")
            _fail("unsupported firewall fixture was accepted")
        if "malformed" in path.name:
            if not isinstance(document, dict) or isinstance(document.get("totalCount"), int):
                _fail("malformed pagination fixture is not malformed")
            continue
        if "empty" in path.name:
            if document.get("data") != [] or document.get("totalCount") != 0:
                _fail("empty firewall fixture is not empty")
            continue
        if not isinstance(document, dict):
            _fail(f"firewall fixture must be an object: {path.name}")


def _verify_contracts_and_boundaries() -> None:
    config_schema = json.loads(
        (ROOT / "docs/contracts/config-v1.schema.json").read_text(encoding="utf-8")
    )
    plan_schema = json.loads(
        (ROOT / "docs/contracts/plan-v1.schema.json").read_text(encoding="utf-8")
    )
    if "firewall" not in config_schema["properties"]:
        _fail("configuration schema does not advertise firewall")
    rendered_plan = json.dumps(plan_schema)
    for marker in ("firewall_zone", "firewall_group", "firewall_rule", "reorder", "warnings"):
        if marker not in rendered_plan:
            _fail(f"plan schema does not advertise {marker}")
    mcp_source = (ROOT / "src/lanweave/mcp.py").read_text(encoding="utf-8")
    if "never applies changes" not in mcp_source:
        _fail("MCP read-only boundary marker is missing")
    if re.search(r"def lanweave_(?:apply|delete)", mcp_source):
        _fail("MCP exposes a mutation tool")


def _verify_live_gate_when_requested() -> None:
    if os.getenv("LANWEAVE_REQUIRE_V050_LIVE_EVIDENCE", "").lower() not in {
        "1",
        "true",
        "yes",
        "on",
    }:
        return
    text = EVIDENCE.read_text(encoding="utf-8")
    for marker in (
        "Read-only firewall evidence: passed",
        "Authorized firewall lifecycle: passed",
    ):
        if marker not in text:
            _fail(f"stable release requires live evidence marker: {marker}")


def main() -> int:
    _required_documents()
    _verify_example()
    _verify_fixtures()
    _verify_contracts_and_boundaries()
    _verify_live_gate_when_requested()
    print(
        "v0.5 evidence verification: firewall contracts, fixtures, examples and gates are present"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
