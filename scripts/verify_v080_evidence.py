"""Check the offline v0.8.0 audit contract and release boundaries."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "tests" / "fixtures" / "audit"


def _fail(message: str) -> None:
    raise SystemExit(f"v0.8 evidence verification: {message}")


def _required_documents() -> None:
    required_text = {
        "docs/roadmap-v0.8.0.md": "Roadmap v0.8.0",
        "docs/migration-v0.8.md": "Migration de v0.7.0 vers v0.8.0",
        "docs/release-v0.8.0.md": "Lanweave v0.8.0",
        "docs/audit.md": "lanweave audit",
        "docs/contracts.md": "Audit result format v1",
        "docs/evidence/v0.8.0-audit.md": "Offline audit evidence: passed",
        "docs/contracts/audit-v1.schema.json": '"format_version"',
        ".github/workflows/ci.yml": "verify_v080_evidence.py",
        ".github/workflows/release.yml": "Verify v0.8 audit evidence gate",
        "src/lanweave/audit.py": "unsupported_export_capability",
        "src/lanweave/cli.py": 'subparsers.add_parser(\n        "audit"',
        "src/lanweave/mcp.py": "lanweave_audit_config",
    }
    for relative, marker in required_text.items():
        path = ROOT / relative
        if not path.is_file():
            _fail(f"missing v0.8 evidence file: {relative}")
        if marker not in path.read_text(encoding="utf-8"):
            _fail(f"evidence marker missing from {relative}: {marker}")


def _verify_schema() -> None:
    path = ROOT / "docs/contracts/audit-v1.schema.json"
    try:
        schema = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        _fail(f"invalid audit schema: {exc}")
    if schema.get("properties", {}).get("format_version", {}).get("const") != 1:
        _fail("audit schema format version is not 1")
    if schema.get("properties", {}).get("read_only", {}).get("const") is not True:
        _fail("audit schema is not read-only")
    if schema.get("properties", {}).get("state", {}).get("enum") != [
        "in-sync",
        "drifted",
        "unknown",
        "unsupported",
    ]:
        _fail("audit schema states are not stable")


def _verify_fixtures() -> None:
    paths = sorted(FIXTURE_DIR.glob("*.json"))
    required = {
        "audit-in-sync.json": "in-sync",
        "audit-drifted.json": "drifted",
        "audit-unknown.json": "unknown",
        "audit-unsupported.json": "unsupported",
    }
    if set(required) - {path.name for path in paths}:
        _fail("one or more audit outcome fixtures are missing")
    forbidden = re.compile(
        r"(?:op://|authorization|api[_ -]?key|password|passphrase|secret|token|"
        r"private[_ -]?key|preshared[_ -]?key|qr[_ -]?code|x_passphrase)",
        re.IGNORECASE,
    )
    for path in paths:
        text = path.read_text(encoding="utf-8")
        if forbidden.search(text):
            _fail(f"credential marker found in fixture: {path.name}")
        try:
            document: Any = json.loads(text)
        except json.JSONDecodeError as exc:
            _fail(f"invalid JSON fixture {path.name}: {exc}")
        if not isinstance(document, dict) or document.get("format_version") != 1:
            _fail(f"invalid audit envelope: {path.name}")
        if document.get("read_only") is not True:
            _fail(f"fixture is not read-only: {path.name}")
        expected_state = required.get(path.name)
        if expected_state is None:
            _fail(f"unexpected audit fixture: {path.name}")
        if document.get("state") != expected_state:
            _fail(f"fixture state does not match its name: {path.name}")
        summary = document.get("summary")
        if not isinstance(summary, dict) or set(summary) != {
            "in-sync",
            "drifted",
            "unknown",
            "unsupported",
        }:
            _fail(f"fixture summary is incomplete: {path.name}")
        if not isinstance(document.get("resources"), list) or not document["resources"]:
            _fail(f"fixture has no resources: {path.name}")


def _verify_read_only_boundary() -> None:
    mcp_source = (ROOT / "src/lanweave/mcp.py").read_text(encoding="utf-8")
    if "lanweave_audit_config" not in mcp_source or "never applies changes" not in mcp_source:
        _fail("MCP audit read-only boundary marker is missing")
    if re.search(r"def lanweave_(?:apply|delete|create|update)_audit", mcp_source):
        _fail("MCP exposes an audit mutation tool")


def main() -> int:
    _required_documents()
    _verify_schema()
    _verify_fixtures()
    _verify_read_only_boundary()
    print("v0.8 evidence verification: audit contract, fixtures, docs and gates are present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
