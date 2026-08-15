"""Check the offline v0.4.0 DNS evidence and release gates."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml

from lanweave.config import validate_config
from lanweave.dns import normalize_controller_dns_list

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "tests" / "fixtures" / "dns"


def _fail(message: str) -> None:
    raise SystemExit(f"v0.4 evidence verification: {message}")


def _required_documents() -> None:
    required_text = {
        "docs/roadmap-v0.4.0.md": "v0.4.0 roadmap",
        "docs/migration-v0.4.md": "Migration from v0.3.0",
        "docs/release-v0.4.0.md": "Lanweave v0.4.0 release notes",
        "docs/contracts.md": "A`, `AAAA` and `CNAME",
        "docs/compatibility.md": "DNS policies",
        "docs/recovery.md": "user-managed DNS policies",
        "docs/evidence/v0.4.0-dns.md": "Authorized lifecycle: passed",
        ".github/workflows/integration.yml": "run_dns_mutations",
        "tests/integration/test_dns_mutations.py": "DNS lifecycle",
    }
    for relative, marker in required_text.items():
        path = ROOT / relative
        if not path.is_file():
            _fail(f"missing v0.4 evidence file: {relative}")
        if marker not in path.read_text(encoding="utf-8"):
            _fail(f"evidence marker missing from {relative}: {marker}")


def _verify_examples() -> None:
    path = ROOT / "examples" / "dns.yaml"
    text = path.read_text(encoding="utf-8")
    if "op://" in text or re.search(
        r"^\s*(?:password|api_key|token|secret)\s*:", text, re.MULTILINE
    ):
        _fail("credential marker found in DNS example")
    document = yaml.safe_load(text)
    if not isinstance(document, dict):
        _fail("DNS example is not a mapping")
    try:
        validate_config(document)
    except Exception as exc:
        _fail(f"DNS example does not validate: {type(exc).__name__}")
    if len(document.get("dns", [])) != 3:
        _fail("DNS example must contain A, AAAA and CNAME records")


def _verify_fixtures() -> None:
    paths = sorted(FIXTURE_DIR.glob("*.json"))
    if not paths:
        _fail("no DNS fixtures found")
    supported_count = 0
    for path in paths:
        text = path.read_text(encoding="utf-8")
        if re.search(
            r"(?:op://|x-api-key|authorization|api[_-]?key|password|secret)",
            text,
            re.IGNORECASE,
        ):
            _fail(f"credential marker found in fixture: {path.name}")
        try:
            document: Any = json.loads(text)
        except json.JSONDecodeError as exc:
            _fail(f"invalid JSON fixture {path.name}: {exc}")
        if not isinstance(document, dict) or not isinstance(document.get("data"), list):
            _fail(f"fixture envelope must contain a data list: {path.name}")
        supported_count += len(normalize_controller_dns_list(document["data"]))
    if supported_count < 3:
        _fail("fixtures must cover at least three supported DNS records")


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
        if relative.endswith("plan-v1.schema.json") and '"dns"' not in rendered:
            _fail("plan schema does not advertise DNS changes")
        if relative.endswith("config-v1.schema.json") and "dns_record" not in rendered:
            _fail("v1 config schema does not advertise DNS records")


def main() -> int:
    _required_documents()
    _verify_examples()
    _verify_fixtures()
    _verify_contracts()
    print("v0.4 evidence verification: DNS contracts, fixtures, examples and gates are present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
