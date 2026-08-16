"""Check the offline v1.0.0 contract, packaging and documentation boundary."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import lanweave

ROOT = Path(__file__).resolve().parents[1]


def _fail(message: str) -> None:
    raise SystemExit(f"v1.0 evidence verification: {message}")


def _required_documents() -> None:
    required_text = {
        "README.md": "Lanweave `1.0.0`",
        "CHANGELOG.md": "## 1.0.0",
        "docs/roadmap.md": "Release status — `v1.0.0`",
        "docs/roadmap-v1.0.0.md": "# Roadmap v1.0.0",
        "docs/contracts.md": "v1.0 stability promise",
        "docs/api.md": "Public Python API",
        "docs/migration-v1.0.md": "Migration from v0.9.0 to v1.0.0",
        "docs/release-v1.0.0.md": "Lanweave v1.0.0",
        "docs/evidence/v1.0.0-contracts.md": "Offline v1.0 evidence: passed",
        "docs/evidence/v1.0.0-vpn.md": "Protected read-only evidence: passed",
        ".github/workflows/ci.yml": "verify_v100_evidence.py",
        ".github/workflows/release.yml": "Verify v1.0 evidence gate",
    }
    for relative, marker in required_text.items():
        path = ROOT / relative
        if not path.is_file():
            _fail(f"missing v1.0 evidence file: {relative}")
        if marker not in path.read_text(encoding="utf-8"):
            _fail(f"evidence marker missing from {relative}: {marker}")


def _verify_version_and_api() -> None:
    with (ROOT / "pyproject.toml").open("rb") as stream:
        version = tomllib.load(stream)["project"]["version"]
    if version != "1.0.0":
        _fail(f"project version is {version}, expected 1.0.0")
    if lanweave.__version__ != version:
        _fail("runtime version does not match project metadata")
    if not (ROOT / "src/lanweave/py.typed").is_file():
        _fail("public package is missing py.typed")
    api_document = (ROOT / "docs/api.md").read_text(encoding="utf-8")
    for name in lanweave.__all__:
        if f"`{name}`" not in api_document:
            _fail(f"public API name is undocumented: {name}")


def _verify_contract_boundary() -> None:
    contracts = (ROOT / "docs/contracts.md").read_text(encoding="utf-8")
    if "Within `v1.x`" not in contracts:
        _fail("v1.x change policy is missing")
    if "MCP contract v3" not in contracts:
        _fail("MCP v3 contract marker is missing")
    mcp_source = (ROOT / "src/lanweave/mcp.py").read_text(encoding="utf-8")
    if re.search(r"def lanweave_(?:apply|delete|create|update|prune)", mcp_source):
        _fail("MCP exposes a mutation tool")
    if "read-only" not in mcp_source.lower():
        _fail("MCP read-only boundary marker is missing")


def _verify_public_docs_are_secret_free() -> None:
    paths = [
        ROOT / "docs/roadmap-v1.0.0.md",
        ROOT / "docs/api.md",
        ROOT / "docs/migration-v1.0.md",
        ROOT / "docs/release-v1.0.0.md",
        ROOT / "docs/evidence/v1.0.0-contracts.md",
    ]
    forbidden = re.compile(
        r"(?:op://|fixture-secret|x-api-key|authorization:\s*bearer|"
        r"private[_ -]?key\s*[:=]|preshared[_ -]?key\s*[:=])",
        re.IGNORECASE,
    )
    for path in paths:
        if forbidden.search(path.read_text(encoding="utf-8")):
            _fail(f"credential marker found in public document: {path.relative_to(ROOT)}")


def main() -> int:
    _required_documents()
    _verify_version_and_api()
    _verify_contract_boundary()
    _verify_public_docs_are_secret_free()
    print("v1.0 evidence verification: contracts, API, docs, packaging and boundaries are present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
