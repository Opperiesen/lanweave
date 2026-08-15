"""Check that the v0.2.0 release evidence is present and secret-free."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "tests" / "fixtures" / "profiles"


def _fail(message: str) -> None:
    raise SystemExit(f"v0.2 evidence verification: {message}")


def _load_fixture(name: str) -> tuple[dict[str, Any], str]:
    path = FIXTURE_DIR / name
    if not path.is_file():
        _fail(f"missing fixture: {path}")
    text = path.read_text(encoding="utf-8")
    document = yaml.safe_load(text)
    if not isinstance(document, dict):
        _fail(f"fixture is not a mapping: {path}")
    return document, text


def _verify_fixtures() -> None:
    v1, v1_text = _load_fixture("config-v1.yaml")
    if v1.get("version") != 1:
        _fail("version-1 migration fixture is not version 1")

    v2, v2_text = _load_fixture("config-v2-multi-target.yaml")
    if v2.get("version") != 2:
        _fail("multi-target fixture is not version 2")
    controllers = v2.get("controllers")
    profiles = v2.get("profiles")
    if not isinstance(controllers, dict) or len(controllers) < 2:
        _fail("multi-target fixture must contain at least two controllers")
    if not isinstance(profiles, dict) or len(profiles) < 2:
        _fail("multi-target fixture must contain at least two profiles")
    sites = {profile.get("site") for profile in profiles.values() if isinstance(profile, dict)}
    if len(sites) < 2:
        _fail("multi-target fixture must cover at least two sites")
    controller_names = {
        profile.get("controller") for profile in profiles.values() if isinstance(profile, dict)
    }
    if len(controller_names) < 2:
        _fail("multi-target fixture must cover at least two controllers")

    for name, text in (("config-v1.yaml", v1_text), ("config-v2-multi-target.yaml", v2_text)):
        if "fixture-secret" in text or "op://" in text:
            _fail(f"secret marker found in fixture: {name}")
        if re.search(r"^\s*(?:password|api_key|token|secret)\s*:", text, re.MULTILINE):
            _fail(f"literal credential field found in fixture: {name}")


def _verify_documents() -> None:
    required_text = {
        "docs/profiles.md": "Migration from version 1",
        "docs/migration-v0.2.md": "Equivalent version-2 configuration",
        "docs/compatibility.md": "Version 0.2 profile compatibility",
        "docs/contracts.md": "Read-only MCP contract v2",
        "docs/release-v0.2.0.md": "Excluded from v0.2.0",
        "docs/roadmap.md": "v0.2.0rc1",
    }
    for relative, marker in required_text.items():
        path = ROOT / relative
        if marker not in path.read_text(encoding="utf-8"):
            _fail(f"release evidence marker missing from {relative}: {marker}")

    scope_notes = "\n".join(
        (
            (ROOT / "docs" / "migration-v0.2.md").read_text(encoding="utf-8"),
            (ROOT / "docs" / "release-v0.2.0.md").read_text(encoding="utf-8"),
        )
    )
    for excluded in ("cloud", "write-capable MCP", "resource families"):
        if excluded not in scope_notes:
            _fail(f"v0.2 scope exclusion missing from release notes: {excluded}")


def main() -> int:
    _verify_fixtures()
    _verify_documents()
    print("v0.2 evidence verification: fixtures, migration notes and scope gates are present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
