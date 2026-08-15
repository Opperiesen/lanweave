"""Check that v0.3.0 evidence, fixtures and release gates are present."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "tests" / "fixtures" / "site-manager"


def _fail(message: str) -> None:
    raise SystemExit(f"v0.3 evidence verification: {message}")


def _verify_documents() -> None:
    required_text = {
        "docs/roadmap-v0.3.0.md": "v0.3.0 roadmap",
        "docs/migration-v0.3.md": "Migration from v0.2.0",
        "docs/release-v0.3.0.md": "Lanweave v0.3.0 release notes",
        "docs/contracts.md": "Read-only MCP contract v3",
        "docs/compatibility.md": "cloud-site-manager",
        ".github/workflows/site-manager-integration.yml": "workflow_dispatch",
        "tests/integration/test_site_manager_live.py": "Site Manager API key",
    }
    for relative, marker in required_text.items():
        path = ROOT / relative
        if not path.is_file():
            _fail(f"missing v0.3 evidence file: {relative}")
        if marker not in path.read_text(encoding="utf-8"):
            _fail(f"evidence marker missing from {relative}: {marker}")


def _verify_fixtures() -> None:
    paths = sorted(FIXTURE_DIR.glob("*.json"))
    if not paths:
        _fail("no Site Manager fixtures found")
    forbidden = re.compile(
        r"(?:op://|x-api-key|authorization|api[_-]?key|password|secret|cloud-key)",
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
        if not isinstance(document, dict) or not isinstance(document.get("data"), list):
            _fail(f"fixture envelope must contain a data list: {path.name}")


def _verify_read_only_boundary() -> None:
    source = (ROOT / "src/lanweave/site_manager.py").read_text(encoding="utf-8")
    for marker in (
        'raise UnsupportedCapabilityError(self.adapter_name, "clients", "read")',
        'raise UnsupportedCapabilityError(self.adapter_name, "networks", "read")',
        'raise UnsupportedCapabilityError(self.adapter_name, "controller", "apply")',
        'raise UnsupportedCapabilityError(self.adapter_name, "controller", "prune")',
    ):
        if marker not in source:
            _fail(f"cloud read-only boundary marker missing: {marker}")


def main() -> int:
    _verify_documents()
    _verify_fixtures()
    _verify_read_only_boundary()
    print("v0.3 evidence verification: documents, fixtures and read-only gates are present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
