"""Secret-redacted local snapshots of controller state."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from . import __version__
from .client import UniFiClient

BACKUP_ENDPOINTS = (
    ("clients", "stat/sta"),
    ("known_clients", "rest/user"),
    ("devices", "stat/device"),
    ("health", "stat/health"),
    ("wlans", "rest/wlanconf"),
    ("networks", "rest/networkconf"),
    ("firewall_rules", "rest/firewallrule"),
    ("firewall_groups", "rest/firewallgroup"),
    ("port_forwards", "rest/portforward"),
    ("routing", "rest/routing"),
    ("switch_port_profiles", "rest/portconf"),
    ("user_groups", "rest/usergroup"),
)
SENSITIVE_KEY_PARTS = ("password", "passphrase", "secret", "token", "api_key", "private_key")


def redact_snapshot(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: (
                "***"
                if any(part in str(key).lower() for part in SENSITIVE_KEY_PARTS)
                else redact_snapshot(child)
            )
            for key, child in value.items()
        }
    if isinstance(value, list):
        return [redact_snapshot(child) for child in value]
    return value


def capture_backup(client: UniFiClient) -> dict[str, Any]:
    snapshot: dict[str, Any] = {
        "format_version": 1,
        "tool_version": __version__,
        "timestamp": datetime.now(UTC).isoformat(),
        "site": client.settings.site,
    }
    for label, path in BACKUP_ENDPOINTS:
        try:
            snapshot[label] = redact_snapshot(client.get(client.site_url(path)))
        except RuntimeError as exc:
            snapshot[label] = {"error": str(exc)}
    return snapshot


def default_backup_dir() -> Path:
    return Path.home() / ".lanweave" / "backups"


def write_backup(snapshot: dict[str, Any], output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y-%m-%d_%H-%M-%S_%f")
    path = output_dir / f"lanweave-{timestamp}.json"
    path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    path.chmod(0o600)
    return path
