"""Render a public, secret-free compatibility report from workflow metadata."""

from __future__ import annotations

import os
import re
from datetime import UTC, datetime
from pathlib import Path


def _env(name: str, default: str = "not-declared") -> str:
    value = os.getenv(name, "").strip()
    return value or default


def _public(value: str) -> str:
    """Keep operator-entered metadata safe for Markdown publication."""

    return re.sub(r"[^A-Za-z0-9 ._+/-]", "?", value)[:80] or "not-declared"


def main() -> None:
    report_path = Path(_env("LANWEAVE_INTEGRATION_REPORT_PATH", "reports/compatibility.md"))
    report_path.parent.mkdir(parents=True, exist_ok=True)

    host_configured = bool(_env("LANWEAVE_INTEGRATION_HOST", ""))
    api_key_configured = bool(_env("LANWEAVE_INTEGRATION_API_KEY", ""))
    session_configured = bool(
        _env("LANWEAVE_INTEGRATION_USER", "") and _env("LANWEAVE_INTEGRATION_PASS", "")
    )
    configured = host_configured and (api_key_configured or session_configured)
    mutation_requested = _env("LANWEAVE_INTEGRATION_MUTATIONS", "false").lower() == "true"
    dns_mutation_requested = _env("LANWEAVE_INTEGRATION_DNS_MUTATIONS", "false").lower() == "true"
    firewall_mutation_requested = (
        _env("LANWEAVE_INTEGRATION_FIREWALL_MUTATIONS", "false").lower() == "true"
    )
    nat_mutation_requested = _env("LANWEAVE_INTEGRATION_NAT_MUTATIONS", "false").lower() == "true"
    cli_matrix_requested = _env("LANWEAVE_INTEGRATION_CLI_MATRIX", "false").lower() == "true"
    mutation_requested = (
        mutation_requested
        or dns_mutation_requested
        or firewall_mutation_requested
        or nat_mutation_requested
    )
    mutation_guarded = (
        _env("LANWEAVE_INTEGRATION_MUTATION_CONFIRM", "") == "I_UNDERSTAND"
        or _env("LANWEAVE_INTEGRATION_DNS_MUTATION_CONFIRM", "") == "I_UNDERSTAND"
        or _env("LANWEAVE_INTEGRATION_FIREWALL_MUTATION_CONFIRM", "") == "I_UNDERSTAND"
        or _env("LANWEAVE_INTEGRATION_NAT_MUTATION_CONFIRM", "") == "I_UNDERSTAND"
    )
    generated = datetime.now(UTC).isoformat()

    read_only_status = _public(_env("LANWEAVE_INTEGRATION_STATUS"))
    if not configured:
        read_only_status = "not-configured"
    if mutation_requested:
        mutation_status = "authorized-run" if mutation_guarded else "guard-not-enabled"
    else:
        mutation_status = "not-requested"
    if nat_mutation_requested:
        mutation_scope = (
            "disabled NAT create/update/protected-prune/delete via the local classic session API"
        )
    elif firewall_mutation_requested:
        mutation_scope = (
            "disabled firewall group/rule create/update/reorder/delete via the local "
            "Integration API"
        )
    elif dns_mutation_requested:
        mutation_scope = "DNS policy create/update/prune via the local Integration API"
    else:
        mutation_scope = "network create/update/delete via the classic local API"

    lines = [
        "# Lanweave controller compatibility report",
        "",
        f"- Generated: {generated}",
        f"- Repository: {_public(_env('GITHUB_REPOSITORY'))}",
        f"- Commit: {_public(_env('GITHUB_SHA'))}",
        f"- Controller version: {_public(_env('LANWEAVE_INTEGRATION_CONTROLLER_VERSION'))}",
        f"- UniFi OS version: {_public(_env('LANWEAVE_INTEGRATION_OS_VERSION'))}",
        f"- API mode: {_public(_env('LANWEAVE_INTEGRATION_API_MODE'))}",
        f"- Site configured: {'yes' if bool(_env('LANWEAVE_INTEGRATION_SITE', '')) else 'default'}",
        f"- Protected credentials configured: {'yes' if configured else 'no'}",
        f"- Read-only probes: {read_only_status}",
        f"- Public CLI matrix: {read_only_status if cli_matrix_requested else 'not-requested'}",
        f"- Mutation suite: {mutation_status}",
        f"- Mutation scope: {mutation_scope}",
        "",
        "This report intentionally excludes controller hostnames, sites, credentials, "
        "topology, responses and raw backups.",
    ]
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
