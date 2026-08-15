"""Small, stable summaries for status and client commands."""

from __future__ import annotations

from typing import Any


def format_bytes(value: int | float | None) -> str:
    if not value:
        return "-"
    amount = float(value)
    for unit in ("B", "K", "M", "G", "T"):
        if amount < 1024:
            return f"{amount:.1f}{unit}"
        amount /= 1024
    return f"{amount:.1f}P"


def filter_clients(
    clients: list[dict[str, Any]],
    *,
    query: str | None = None,
    include_wired: bool = False,
) -> list[dict[str, Any]]:
    result = clients
    if query:
        needle = query.lower()
        result = [
            client
            for client in result
            if needle
            in (
                str(client.get("name", ""))
                + str(client.get("hostname", ""))
                + str(client.get("mac", ""))
            ).lower()
        ]
    if not include_wired:
        result = [client for client in result if client.get("is_wired") is not True]
    return sorted(
        result,
        key=lambda client: client.get("signal") or client.get("rssi") or -100,
        reverse=True,
    )


def status_summary(
    health: list[dict[str, Any]],
    clients: list[dict[str, Any]],
    devices: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "health": health,
        "online_clients": len(clients),
        "devices": len(devices),
    }
