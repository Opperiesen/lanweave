"""Command-line entry point for the public foundation."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .client import ControllerSettings, CredentialsError
from .config import EXAMPLE_CONFIG, ConfigError, load_config


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="unifi-tools",
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

    subparsers.add_parser(
        "doctor",
        help="check controller environment variables without contacting the controller",
    )
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
        f"valid configuration: {len(config['networks'])} network(s), "
        f"{len(config['wlans'])} WLAN(s)"
    )
    return 0


def _doctor() -> int:
    try:
        settings = ControllerSettings.from_env()
    except CredentialsError as exc:
        print(f"controller configuration incomplete: {exc}", file=sys.stderr)
        return 2
    auth_mode = "api-key" if settings.api_key else "session"
    tls_mode = "verified" if settings.verify_tls else "insecure"
    print(f"controller configuration looks usable: {settings.host}")
    print(f"site={settings.site} auth={auth_mode} tls={tls_mode}")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "init":
        return _init(args.path, args.force)
    if args.command == "validate":
        return _validate(args.config)
    if args.command == "doctor":
        return _doctor()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
