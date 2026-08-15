# UniFi Network Tools

Safe, declarative configuration and diagnostics for local UniFi Network
controllers.

Working name: the project will receive a final name and visual identity after
the product scope and trademark check are complete.

This project is not affiliated with, endorsed by, or sponsored by Ubiquiti
Inc. UniFi is a trademark of Ubiquiti Inc.

## Product direction

The goal is a local-first tool for turning a UniFi network into a small,
reviewable GitOps project:

1. describe the desired networks and WLANs in YAML;
2. validate the configuration locally;
3. inspect a readable plan;
4. apply changes only after explicit confirmation;
5. export and back up the live state.

The same engine will later power a read-only MCP adapter for AI clients.
The CLI remains useful without an AI client, a cloud account, or a hosted
service.

## Current status

This repository is the clean public foundation extracted from a private
operational project. The first slice provides:

- an installable Python package;
- a guided init command;
- local configuration validation;
- a credentials and controller doctor command;
- generic examples and public contribution/security rules.

The controller client, export, plan, apply, backup and MCP layers are being
ported behind tests. They are intentionally not copied wholesale from the
private repository.

## Quick start

Requires Python 3.11+ and uv.

    uv sync --extra dev
    uv run unifi-tools init
    uv run unifi-tools validate

Configure a local controller without committing credentials:

    cp .env.example .env

Use a local API key when possible. Self-signed TLS must be opted into
explicitly with UNIFI_VERIFY_TLS=false; the default is verification enabled.

## Planned command surface

    unifi-tools init
    unifi-tools doctor
    unifi-tools validate
    unifi-tools export
    unifi-tools plan
    unifi-tools apply
    unifi-tools backup
    unifi-tools status
    unifi-tools clients

plan will be read-only. apply and --prune will require explicit,
non-ambiguous confirmation. Generated exports, backups and plans stay outside
Git by default.

## Development

    uv sync --extra dev
    uv run pytest
    uv run ruff check .

Hardware compatibility tests must run against disposable or explicitly
designated controllers. Unit tests use simulated HTTP responses and never
need a real controller.

## License

Apache-2.0. See LICENSE.
