"""Render a public, secret-free Site Manager compatibility report."""

from __future__ import annotations

import os
import re
from datetime import UTC, datetime
from pathlib import Path


def _env(name: str, default: str = "not-declared") -> str:
    value = os.getenv(name, "").strip()
    return value or default


def _public(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9 ._+/-]", "?", value)[:80] or "not-declared"


def main() -> None:
    report_path = Path(_env("LANWEAVE_SITE_MANAGER_REPORT_PATH", "reports/site-manager.md"))
    report_path.parent.mkdir(parents=True, exist_ok=True)
    api_key_configured = bool(os.getenv("LANWEAVE_SITE_MANAGER_API_KEY", "").strip())
    status = _public(_env("LANWEAVE_SITE_MANAGER_STATUS"))
    if not api_key_configured:
        status = "not-configured"

    lines = [
        "# Lanweave Site Manager compatibility report",
        "",
        f"- Generated: {datetime.now(UTC).isoformat()}",
        f"- Repository: {_public(_env('GITHUB_REPOSITORY'))}",
        f"- Commit: {_public(_env('GITHUB_SHA'))}",
        f"- API version: {_public(_env('LANWEAVE_SITE_MANAGER_API_VERSION', 'v1.0.0'))}",
        "- Endpoint scope: hosts, sites, devices and derived site health",
        f"- Protected API key configured: {'yes' if api_key_configured else 'no'}",
        f"- Read-only probes: {status}",
        "- Mutation suite: not present",
        "",
        "This report intentionally excludes API hosts, credentials, response bodies, "
        "inventory names, topology and raw payloads.",
    ]
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
