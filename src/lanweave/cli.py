"""Command-line entry point for safe UniFi operations."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Any

import httpx

from . import __version__
from .backup import capture_backup, default_backup_dir, write_backup
from .client import ControllerSettings, CredentialsError, UniFiClient
from .config import EXAMPLE_CONFIG, ConfigError, load_config, load_config_with_options
from .export import export_yaml
from .plan import Plan, PlanApplyError, apply_plan, build_plan
from .status import filter_clients, format_bytes, status_summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lanweave",
        description="Safe, declarative tooling for local UniFi Network controllers.",
    )
    parser.add_argument("--version", action="version", version=__version__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="create a generic configuration")
    init_parser.add_argument(
        "--path",
        type=Path,
        default=Path("config/network.yaml"),
        help="configuration path (default: config/network.yaml)",
    )
    init_parser.add_argument("--force", action="store_true", help="overwrite an existing file")

    validate_parser = subparsers.add_parser("validate", help="validate a configuration locally")
    validate_parser.add_argument(
        "--config",
        type=Path,
        default=Path("config/network.yaml"),
        help="configuration path (default: config/network.yaml)",
    )

    doctor_parser = subparsers.add_parser(
        "doctor",
        help="check controller settings, optionally probing the controller",
    )
    doctor_parser.add_argument(
        "--check",
        action="store_true",
        help="also perform a health request against the controller",
    )

    export_parser = subparsers.add_parser("export", help="export live state as secret-free YAML")
    export_parser.add_argument(
        "--out",
        type=Path,
        default=Path("-"),
        help="output path, or - for stdout (default: -)",
    )
    export_parser.add_argument("--force", action="store_true", help="overwrite an existing file")

    for command, help_text in (
        ("plan", "show the changes that would be applied"),
        ("apply", "apply a reviewed plan to the controller"),
    ):
        command_parser = subparsers.add_parser(command, help=help_text)
        command_parser.add_argument(
            "--config",
            type=Path,
            default=Path("config/network.yaml"),
            help="configuration path (default: config/network.yaml)",
        )
        command_parser.add_argument(
            "--prune",
            action="store_true",
            help="include unmanaged resources in the deletion plan",
        )
        command_parser.add_argument(
            "--output",
            choices=("table", "json"),
            default="table",
            help="plan format (default: table)",
        )
        if command == "apply":
            command_parser.add_argument(
                "--yes",
                action="store_true",
                help="confirm the complete plan without an interactive prompt",
            )

    backup_parser = subparsers.add_parser("backup", help="write a redacted local snapshot")
    backup_parser.add_argument(
        "--output",
        type=Path,
        default=default_backup_dir(),
        help="backup directory (default: ~/.lanweave/backups)",
    )

    status_parser = subparsers.add_parser("status", help="show controller health")
    status_parser.add_argument("--output", choices=("table", "json"), default="table")

    clients_parser = subparsers.add_parser("clients", help="list connected clients")
    clients_parser.add_argument("--filter", dest="query", help="filter by name, hostname or MAC")
    clients_parser.add_argument("--wired", action="store_true", help="include wired clients")
    clients_parser.add_argument("--output", choices=("table", "json"), default="table")
    return parser


def _init(path: Path, force: bool) -> int:
    if path.exists() and not force:
        print(f"refusing to overwrite existing file: {path}", file=sys.stderr)
        return 2
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(EXAMPLE_CONFIG, encoding="utf-8")
    print(f"created {path}")
    return 0


def _validate(path: Path) -> int:
    try:
        config = load_config(path)
    except ConfigError as exc:
        print(f"invalid configuration: {exc}", file=sys.stderr)
        return 2
    print(
        f"valid configuration: {len(config['networks'])} network(s), {len(config['wlans'])} WLAN(s)"
    )
    return 0


def _doctor(check: bool = False) -> int:
    try:
        settings = ControllerSettings.from_env()
    except CredentialsError as exc:
        print(f"controller configuration incomplete: {exc}", file=sys.stderr)
        return 2
    auth_mode = "api-key" if settings.api_key else "session"
    tls_mode = "verified" if settings.verify_tls else "insecure"
    print(f"controller configuration looks usable: {settings.host}")
    print(f"site={settings.site} auth={auth_mode} tls={tls_mode}")
    if check:
        try:
            with UniFiClient(settings) as client:
                health = client.health()
        except (RuntimeError, httpx.HTTPError) as exc:
            print(f"controller check failed: {type(exc).__name__}", file=sys.stderr)
            return 2
        print(f"controller reachable: {len(health)} health record(s)")
    return 0


def _settings_for_config(config: dict[str, Any]) -> ControllerSettings:
    settings = ControllerSettings.from_env()
    site = config.get("controller", {}).get("site")
    return replace(settings, site=site or settings.site)


def _with_client(
    operation: Callable[[UniFiClient], int],
    config: dict[str, Any] | None = None,
) -> int:
    try:
        settings = (
            _settings_for_config(config) if config is not None else ControllerSettings.from_env()
        )
        with UniFiClient(settings) as client:
            return operation(client)
    except (ConfigError, CredentialsError, RuntimeError) as exc:
        print(f"operation failed: {exc}", file=sys.stderr)
        return 2
    except httpx.HTTPError as exc:
        print(f"controller request failed: {type(exc).__name__}", file=sys.stderr)
        return 2


def _render_plan(plan: Plan, output: str) -> None:
    if output == "json":
        print(json.dumps(plan.to_dict(), indent=2, sort_keys=True))
        return
    summary = plan.summary()
    print(
        "Plan: "
        f"+{summary['create']} create  "
        f"~{summary['update']} update  "
        f"-{summary['delete']} delete  "
        f"={summary['noop']} unchanged"
    )
    for diff in plan.diffs:
        if diff.action == "noop":
            continue
        fields = ", ".join(diff.changed_fields) or "-"
        print(f"{diff.action:>6}  {diff.kind:<7} {diff.name:<30} {fields}")


def _load_runtime_config(path: Path) -> dict[str, Any]:
    return load_config_with_options(path, resolve_secrets=True)


def _plan(path: Path, prune: bool, output: str) -> int:
    try:
        config = _load_runtime_config(path)
    except ConfigError as exc:
        print(f"invalid configuration: {exc}", file=sys.stderr)
        return 2

    return _with_client(
        lambda client: _plan_with_client(client, config, prune, output),
        config,
    )


def _plan_with_client(client: UniFiClient, config: dict[str, Any], prune: bool, output: str) -> int:
    plan = build_plan(client, config, prune=prune)
    _render_plan(plan, output)
    return 0


def _confirm_apply(plan: Plan, prune: bool, yes: bool) -> bool:
    if not plan.has_changes():
        return True
    if yes:
        return True
    if not sys.stdin.isatty():
        print(
            "refusing non-interactive apply; pass --yes after reviewing the plan",
            file=sys.stderr,
        )
        return False
    if prune:
        answer = input("Type DELETE to allow prune operations: ")
        if answer != "DELETE":
            print("prune cancelled")
            return False
    answer = input("Type APPLY to apply this plan: ")
    if answer != "APPLY":
        print("apply cancelled")
        return False
    return True


def _apply(path: Path, prune: bool, output: str, yes: bool) -> int:
    try:
        config = _load_runtime_config(path)
    except ConfigError as exc:
        print(f"invalid configuration: {exc}", file=sys.stderr)
        return 2

    def operation(client: UniFiClient) -> int:
        plan = build_plan(client, config, prune=prune)
        _render_plan(plan, output)
        if not plan.has_changes():
            print("nothing to apply")
            return 0
        if not _confirm_apply(plan, prune, yes):
            return 2
        try:
            apply_plan(client, plan)
        except PlanApplyError as exc:
            if output == "json":
                print(json.dumps(exc.to_dict(), indent=2, sort_keys=True), file=sys.stderr)
            else:
                print(f"apply failed: {exc}", file=sys.stderr)
            return 2
        print("plan applied")
        return 0

    return _with_client(operation, config)


def _export(out: Path, force: bool) -> int:
    def operation(client: UniFiClient) -> int:
        text = export_yaml(client)
        if str(out) == "-":
            sys.stdout.write(text)
            return 0
        if out.exists() and not force:
            print(f"refusing to overwrite existing file: {out}", file=sys.stderr)
            return 2
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        print(f"exported {out}")
        return 0

    return _with_client(operation)


def _backup(output: Path) -> int:
    def operation(client: UniFiClient) -> int:
        path = write_backup(capture_backup(client), output)
        print(f"backup written to {path}")
        return 0

    return _with_client(operation)


def _status(output: str) -> int:
    def operation(client: UniFiClient) -> int:
        summary = status_summary(client.health(), client.clients(), client.devices())
        if output == "json":
            print(json.dumps(summary, indent=2, sort_keys=True))
            return 0
        print(f"online clients: {summary['online_clients']}")
        print(f"devices: {summary['devices']}")
        for item in summary["health"]:
            print(f"{item.get('subsystem', '?')}: {item.get('status', '?')}")
        return 0

    return _with_client(operation)


def _clients(query: str | None, wired: bool, output: str) -> int:
    def operation(client: UniFiClient) -> int:
        clients = filter_clients(client.clients(), query=query, include_wired=wired)
        if output == "json":
            print(json.dumps(clients, indent=2, sort_keys=True, default=str))
            return 0
        print(f"clients: {len(clients)}")
        for item in clients:
            name = item.get("name") or item.get("hostname") or "-"
            signal = item.get("signal") or item.get("rssi") or "-"
            rx = format_bytes(item.get("rx_bytes"))
            tx = format_bytes(item.get("tx_bytes"))
            print(f"{name:<28} {item.get('ip', '-'):>15}  {signal:>5}  down={rx:<8} up={tx:<8}")
        return 0

    return _with_client(operation)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "init":
        return _init(args.path, args.force)
    if args.command == "validate":
        return _validate(args.config)
    if args.command == "doctor":
        return _doctor(args.check)
    if args.command == "export":
        return _export(args.out, args.force)
    if args.command == "plan":
        return _plan(args.config, args.prune, args.output)
    if args.command == "apply":
        return _apply(args.config, args.prune, args.output, args.yes)
    if args.command == "backup":
        return _backup(args.output)
    if args.command == "status":
        return _status(args.output)
    if args.command == "clients":
        return _clients(args.query, args.wired, args.output)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
