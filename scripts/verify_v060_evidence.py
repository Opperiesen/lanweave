"""Check the offline v0.6.0 NAT evidence and release gates."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

import yaml

from lanweave.config import validate_config
from lanweave.nat import UnsupportedNatVariantError, normalize_controller_nat_list

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "tests" / "fixtures" / "nat"
EVIDENCE = ROOT / "docs" / "evidence" / "v0.6.0-nat.md"


def _fail(message: str) -> None:
    raise SystemExit(f"v0.6 evidence verification: {message}")


def _required_documents() -> None:
    required_text = {
        "docs/roadmap-v0.6.0.md": "v0.6.0 roadmap",
        "docs/migration-v0.6.md": "Migration de v0.5.0 vers v0.6.0",
        "docs/release-v0.6.0.md": "Lanweave v0.6.0",
        "docs/nat.md": "NAT and port-forwarding contract",
        "docs/contracts.md": "v0.6.0 NAT",
        "docs/compatibility.md": "rest/portforward",
        "docs/recovery.md": "NAT writes",
        "SECURITY.md": "Internet-facing NAT plans",
        ".github/workflows/integration.yml": "run_nat_mutations",
        "tests/integration/test_nat_mutations.py": "NAT lifecycle",
        "examples/nat.yaml": "nat:",
    }
    for relative, marker in required_text.items():
        path = ROOT / relative
        if not path.is_file():
            _fail(f"missing v0.6 evidence file: {relative}")
        if marker not in path.read_text(encoding="utf-8"):
            _fail(f"evidence marker missing from {relative}: {marker}")
    if not EVIDENCE.is_file() or "Offline NAT evidence: passed" not in EVIDENCE.read_text(
        encoding="utf-8"
    ):
        _fail("offline NAT evidence is missing")


def _verify_example() -> None:
    path = ROOT / "examples" / "nat.yaml"
    text = path.read_text(encoding="utf-8")
    if "op://" in text or re.search(
        r"^\s*(?:password|api_key|token|secret)\s*:", text, re.MULTILINE
    ):
        _fail("credential marker found in NAT example")
    document = yaml.safe_load(text)
    if not isinstance(document, dict):
        _fail("NAT example is not a mapping")
    try:
        validate_config(document)
    except Exception as exc:
        _fail(f"NAT example does not validate: {type(exc).__name__}")
    nat = document.get("nat")
    if not isinstance(nat, list) or not nat:
        _fail("NAT example must contain at least one mapping")


def _verify_fixtures() -> None:
    paths = sorted(FIXTURE_DIR.glob("*.json"))
    if not paths:
        _fail("no NAT fixtures found")
    forbidden = re.compile(
        r"(?:op://|x-api-key|authorization|api[_-]?key|password|secret|token)",
        re.IGNORECASE,
    )
    names = {path.name for path in paths}
    for required in (
        "portforward-page-1.json",
        "portforward-empty-page.json",
        "portforward-unsupported.json",
        "portforward-malformed.json",
    ):
        if required not in names:
            _fail(f"required NAT fixture is missing: {required}")

    supported_count = 0
    for path in paths:
        text = path.read_text(encoding="utf-8")
        if forbidden.search(text):
            _fail(f"credential marker found in fixture: {path.name}")
        try:
            document: Any = json.loads(text)
        except json.JSONDecodeError as exc:
            _fail(f"invalid JSON fixture {path.name}: {exc}")
        if "unsupported" in path.name or "malformed" in path.name:
            try:
                normalize_controller_nat_list(document)
            except UnsupportedNatVariantError:
                continue
            except Exception as exc:
                _fail(f"invalid NAT fixture failed with the wrong error: {type(exc).__name__}")
            _fail(f"invalid NAT fixture was accepted: {path.name}")
        try:
            supported_count += len(normalize_controller_nat_list(document))
        except Exception as exc:
            _fail(f"supported NAT fixture failed: {path.name}: {type(exc).__name__}")
    if supported_count < 2:
        _fail("fixtures must cover at least two supported NAT mappings")


def _verify_contracts() -> None:
    for relative in (
        "docs/contracts/config-v1.schema.json",
        "docs/contracts/config-v2.schema.json",
        "docs/contracts/plan-v1.schema.json",
    ):
        try:
            document = json.loads((ROOT / relative).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            _fail(f"invalid contract schema {relative}: {exc}")
        rendered = json.dumps(document)
        if relative.endswith("config-v1.schema.json") and "nat_mapping" not in rendered:
            _fail("v1 config schema does not advertise NAT mappings")
        if relative.endswith("config-v2.schema.json") and '"nat"' not in rendered:
            _fail("v2 config schema does not advertise NAT mappings")
        if relative.endswith("plan-v1.schema.json") and '"nat"' not in rendered:
            _fail("plan schema does not advertise NAT changes")
    mcp_source = (ROOT / "src/lanweave/mcp.py").read_text(encoding="utf-8")
    if "never applies changes" not in mcp_source:
        _fail("MCP read-only boundary marker is missing")
    if re.search(r"def lanweave_(?:apply|delete)", mcp_source):
        _fail("MCP exposes a mutation tool")


def _verify_live_gate_when_requested() -> None:
    if os.getenv("LANWEAVE_REQUIRE_V060_LIVE_EVIDENCE", "").lower() not in {
        "1",
        "true",
        "yes",
        "on",
    }:
        return
    text = EVIDENCE.read_text(encoding="utf-8")
    for marker in (
        "Read-only NAT evidence: passed",
        "Authorized NAT lifecycle: passed",
    ):
        if marker not in text:
            _fail(f"stable release requires live evidence marker: {marker}")


def main() -> int:
    _required_documents()
    _verify_example()
    _verify_fixtures()
    _verify_contracts()
    _verify_live_gate_when_requested()
    print("v0.6 evidence verification: NAT contracts, fixtures, examples and gates are present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
