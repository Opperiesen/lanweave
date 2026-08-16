"""Check the offline v0.7.0 VPN evidence and release boundaries."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

import yaml

from lanweave.config import validate_config
from lanweave.vpn import (
    UnsupportedVpnVariantError,
    normalize_controller_vpn_server,
    normalize_controller_vpn_tunnel,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "tests" / "fixtures" / "vpn"
EVIDENCE = ROOT / "docs" / "evidence" / "v0.7.0-vpn.md"


def _fail(message: str) -> None:
    raise SystemExit(f"v0.7 evidence verification: {message}")


def _required_documents() -> None:
    required_text = {
        "docs/roadmap-v0.7.0.md": "Roadmap v0.7.0",
        "docs/migration-v0.7.md": "Migration de v0.6.0 vers v0.7.0",
        "docs/release-v0.7.0.md": "Lanweave v0.7.0",
        "docs/vpn.md": "Contrat VPN v0.7.0",
        "docs/contracts.md": "v0.7.0 VPN",
        "docs/compatibility.md": "vpn/servers",
        "docs/recovery.md": "VPN resources",
        "SECURITY.md": "private keys",
        "examples/vpn.yaml": "vpn:",
        ".github/workflows/ci.yml": "verify_v070_evidence.py",
        ".github/workflows/release.yml": "Verify v0.7 VPN evidence gate",
        "tests/test_vpn.py": "read-only",
    }
    for relative, marker in required_text.items():
        path = ROOT / relative
        if not path.is_file():
            _fail(f"missing v0.7 evidence file: {relative}")
        if marker not in path.read_text(encoding="utf-8"):
            _fail(f"evidence marker missing from {relative}: {marker}")
    if not EVIDENCE.is_file() or "Offline fixture gate: passed" not in EVIDENCE.read_text(
        encoding="utf-8"
    ):
        _fail("offline VPN evidence is missing")


def _verify_example() -> None:
    path = ROOT / "examples" / "vpn.yaml"
    text = path.read_text(encoding="utf-8")
    if "op://" in text or re.search(
        r"^\s*(?:password|api_key|token|secret|private_key|preshared_key)\s*:",
        text,
        re.MULTILINE | re.IGNORECASE,
    ):
        _fail("credential marker found in VPN example")
    document = yaml.safe_load(text)
    if not isinstance(document, dict):
        _fail("VPN example is not a mapping")
    try:
        validate_config(document)
    except Exception as exc:
        _fail(f"VPN example does not validate: {type(exc).__name__}")
    vpn = document.get("vpn")
    if not isinstance(vpn, dict) or not vpn.get("servers") or not vpn.get("routes"):
        _fail("VPN example must contain servers and routes")


def _verify_fixtures() -> None:
    paths = sorted(FIXTURE_DIR.glob("*.json"))
    if not paths:
        _fail("no VPN fixtures found")
    forbidden = re.compile(
        r"(?:op://|x-api-key|authorization|api[_ -]?key|password|secret|token|"
        r"private[_ -]?key|preshared[_ -]?key|qr[_ -]?code)",
        re.IGNORECASE,
    )
    names = {path.name for path in paths}
    for required in (
        "vpn-servers-page-1.json",
        "vpn-site-to-site-tunnels-page-1.json",
        "vpn-clients-page-1.json",
        "vpn-empty-page.json",
        "vpn-malformed.json",
    ):
        if required not in names:
            _fail(f"required VPN fixture is missing: {required}")

    for path in paths:
        text = path.read_text(encoding="utf-8")
        if forbidden.search(text):
            _fail(f"credential marker found in fixture: {path.name}")
        try:
            document: Any = json.loads(text)
        except json.JSONDecodeError as exc:
            _fail(f"invalid JSON fixture {path.name}: {exc}")
        if path.name == "vpn-malformed.json":
            try:
                normalize_controller_vpn_server(document)
            except UnsupportedVpnVariantError:
                continue
            except Exception as exc:
                _fail(f"malformed VPN fixture failed with the wrong error: {type(exc).__name__}")
            _fail("malformed VPN fixture was accepted")
        if path.name == "vpn-empty-page.json":
            if document.get("data") != [] or document.get("totalCount") != 0:
                _fail("empty VPN fixture is not empty")
            continue
        if path.name == "vpn-servers-page-1.json":
            values = document.get("data", [])
            for index, value in enumerate(values):
                try:
                    normalize_controller_vpn_server(value, f"servers[{index}]")
                except Exception as exc:
                    _fail(f"supported server fixture failed: {type(exc).__name__}")
        elif path.name == "vpn-site-to-site-tunnels-page-1.json":
            values = document.get("data", [])
            for index, value in enumerate(values):
                try:
                    normalize_controller_vpn_tunnel(value, f"tunnels[{index}]")
                except Exception as exc:
                    _fail(f"supported tunnel fixture failed: {type(exc).__name__}")
        elif not isinstance(document, dict):
            _fail(f"VPN fixture must be an object: {path.name}")


def _verify_contracts_and_boundaries() -> None:
    config_schema = json.loads(
        (ROOT / "docs/contracts/config-v1.schema.json").read_text(encoding="utf-8")
    )
    config_v2_schema = json.loads(
        (ROOT / "docs/contracts/config-v2.schema.json").read_text(encoding="utf-8")
    )
    plan_schema = json.loads(
        (ROOT / "docs/contracts/plan-v1.schema.json").read_text(encoding="utf-8")
    )
    if "vpn" not in config_schema["properties"] or "vpn" not in config_v2_schema["properties"]:
        _fail("configuration schemas do not advertise VPN")
    if "read_only" not in plan_schema["properties"]:
        _fail("plan schema does not advertise read-only observations")
    mcp_source = (ROOT / "src/lanweave/mcp.py").read_text(encoding="utf-8")
    if "lanweave_list_vpn" not in mcp_source or "never applies changes" not in mcp_source:
        _fail("MCP VPN read-only boundary marker is missing")
    if re.search(r"def lanweave_(?:apply|delete|create|update)_vpn", mcp_source):
        _fail("MCP exposes a VPN mutation tool")
    for relative in ("src/lanweave/client.py", "src/lanweave/vpn.py"):
        source = (ROOT / relative).read_text(encoding="utf-8")
        if re.search(r"(?:create|update|delete)_vpn", source):
            _fail(f"VPN mutation method found in {relative}")


def _verify_live_gate_when_requested() -> None:
    if os.getenv("LANWEAVE_REQUIRE_V070_LIVE_EVIDENCE", "").lower() not in {
        "1",
        "true",
        "yes",
        "on",
    }:
        return
    text = EVIDENCE.read_text(encoding="utf-8")
    if "Read-only VPN evidence: passed" not in text:
        _fail("stable release requested live VPN evidence but it is not recorded")


def main() -> int:
    _required_documents()
    _verify_example()
    _verify_fixtures()
    _verify_contracts_and_boundaries()
    _verify_live_gate_when_requested()
    print("v0.7 evidence verification: VPN contracts, fixtures, examples and gates are present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
