"""Check the offline v0.9.0 convergence contract and release boundaries."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "tests" / "fixtures" / "convergence"


def _fail(message: str) -> None:
    raise SystemExit(f"v0.9 evidence verification: {message}")


def _required_documents() -> None:
    required_text = {
        "docs/roadmap-v0.9.0.md": "Roadmap v0.9.0",
        "docs/migration-v0.9.md": "Migration de v0.8.0 vers v0.9.0",
        "docs/release-v0.9.0.md": "Lanweave v0.9.0",
        "docs/contracts.md": "Post-apply convergence result format v1",
        "docs/recovery.md": "Post-apply convergence",
        "docs/compatibility.md": "v0.9.0 post-apply compatibility",
        "docs/evidence/v0.9.0-convergence.md": "Offline convergence evidence: passed",
        "docs/contracts/convergence-v1.schema.json": '"format_version"',
        ".github/workflows/ci.yml": "verify_v090_evidence.py",
        ".github/workflows/release.yml": "Verify v0.9 convergence evidence gate",
        "src/lanweave/convergence.py": "post-apply verification",
        "src/lanweave/cli.py": "verify_plan_convergence",
        "tests/test_convergence.py": "ConvergenceState",
    }
    for relative, marker in required_text.items():
        path = ROOT / relative
        if not path.is_file():
            _fail(f"missing v0.9 evidence file: {relative}")
        if marker not in path.read_text(encoding="utf-8"):
            _fail(f"evidence marker missing from {relative}: {marker}")


def _verify_schema() -> None:
    path = ROOT / "docs/contracts/convergence-v1.schema.json"
    try:
        schema = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        _fail(f"invalid convergence schema: {exc}")
    if schema.get("properties", {}).get("format_version", {}).get("const") != 1:
        _fail("convergence schema format version is not 1")
    if schema.get("properties", {}).get("read_only", {}).get("const") is not True:
        _fail("convergence schema is not read-only")
    if schema.get("properties", {}).get("state", {}).get("enum") != [
        "converged",
        "drifted",
        "uncertain",
        "unsupported",
    ]:
        _fail("convergence schema states are not stable")


def _verify_fixtures() -> None:
    required = {
        "convergence-converged.json": "converged",
        "convergence-drifted.json": "drifted",
        "convergence-uncertain.json": "uncertain",
        "convergence-unsupported.json": "unsupported",
    }
    paths = sorted(FIXTURE_DIR.glob("*.json"))
    if set(required) - {path.name for path in paths}:
        _fail("one or more convergence outcome fixtures are missing")
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
            _fail(f"invalid convergence envelope: {path.name}")
        if document.get("read_only") is not True:
            _fail(f"fixture is not read-only: {path.name}")
        expected_state = required.get(path.name)
        if expected_state is None:
            _fail(f"unexpected convergence fixture: {path.name}")
        if document.get("state") != expected_state:
            _fail(f"fixture state does not match its name: {path.name}")
        summary = document.get("summary")
        if not isinstance(summary, dict) or set(summary) != {
            "converged",
            "drifted",
            "uncertain",
            "unsupported",
        }:
            _fail(f"fixture summary is incomplete: {path.name}")
        if not isinstance(document.get("resources"), list) or not document["resources"]:
            _fail(f"fixture has no resources: {path.name}")


def _verify_boundaries() -> None:
    mcp_source = (ROOT / "src/lanweave/mcp.py").read_text(encoding="utf-8")
    if "never applies changes" not in mcp_source:
        _fail("MCP read-only boundary marker is missing")
    if re.search(r"def lanweave_(?:apply|delete|create|update)_", mcp_source):
        _fail("MCP exposes a mutation tool")
    cli_source = (ROOT / "src/lanweave/cli.py").read_text(encoding="utf-8")
    if "verify_plan_convergence" not in cli_source or 'output == "json"' not in cli_source:
        _fail("CLI convergence integration marker is missing")


def main() -> int:
    _required_documents()
    _verify_schema()
    _verify_fixtures()
    _verify_boundaries()
    print("v0.9 evidence verification: convergence contract, fixtures, docs and gates are present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
