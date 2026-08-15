# Lanweave

[![CI](https://github.com/Opperiesen/lanweave/actions/workflows/ci.yml/badge.svg)](https://github.com/Opperiesen/lanweave/actions/workflows/ci.yml)
[![License](https://img.shields.io/github/license/Opperiesen/lanweave)](LICENSE)
[![Latest release](https://img.shields.io/github/v/release/Opperiesen/lanweave?include_prereleases)](https://github.com/Opperiesen/lanweave/releases)

![Lanweave logo](assets/logo.svg)

Lanweave is a local-first, open-source toolkit for managing and observing
UniFi Network controllers. It turns a controller into a small, reviewable
GitOps project without requiring a cloud service.

The name is intentionally independent from the controller vendor. Lanweave is
not affiliated with, endorsed by, or sponsored by Ubiquiti Inc. UniFi is a
trademark of Ubiquiti Inc.

## Why Lanweave?

Lanweave is aimed at operators who want a safe middle ground between clicking
through a controller UI and adopting a complete infrastructure platform:

- declare networks and WLANs in YAML;
- validate locally before contacting the controller;
- inspect a deterministic, redacted plan;
- apply only after explicit confirmation;
- export a portable configuration without Wi-Fi passwords;
- capture a local, secret-redacted backup;
- expose the same read-only views to an MCP-compatible AI client.

The CLI is the primary interface. MCP is an optional read-only adapter, not a
requirement and not a write path around the plan safety boundary.

## Status

Lanweave `0.2.0` is the stable local-first profile release. It is tested
against simulated controller responses, with read-only and authorized mutation
evidence on one designated UniFi OS controller. It targets the classic local
UniFi Network API used by self-hosted UniFi Network applications and UniFi OS
consoles; see [compatibility](docs/compatibility.md) and the [apply recovery
model](docs/recovery.md) for the exact scope, tested matrix and partial-failure
behavior. The frozen public surfaces are described in [contracts](docs/contracts.md).

Supported resource families in this release:

- networks;
- WLANs, including references to environment-provided passwords;
- local controller/site profiles with explicit target selection;
- controller health, devices and clients;
- redacted snapshots of common operational endpoints.

Firewall, DNS, NAT, VPN and device mutation workflows are deliberately not
included yet. They need their own fixtures, dependency rules and rollback
story before being safe to expose.

## Quick start

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/). Install the stable
package from PyPI with:

```shell
uv tool install lanweave==0.2.0
lanweave --version
```

For a checkout and development environment:

```shell
uv sync --extra dev
uv run lanweave init
cp .env.example .env
uv run lanweave validate
```

See [release verification](docs/release.md) for checksums, provenance and
attestation verification.

Edit `config/network.yaml` and provide secrets only through the environment:

```yaml
wlans:
  - name: Home
    ssid: Home
    network: Home
    security: wpapsk
    password_env: WIFI_HOME_PASSWORD
```

Use a local API key when possible. TLS verification is enabled by default;
set `UNIFI_VERIFY_TLS=false` only when the controller's certificate cannot be
verified and the risk is understood.

## Command surface

```shell
lanweave init                    # create a generic config
lanweave doctor                  # check credentials and TLS settings
lanweave doctor --check          # also perform one health request
lanweave validate                # validate YAML locally
lanweave profiles list           # list sanitized local targets
lanweave profiles validate       # validate profiles without contacting UniFi
lanweave export --out live.yaml # export secret-free desired-state YAML
lanweave plan                    # show create/update/delete operations
lanweave plan --output json      # machine-readable, redacted plan
lanweave apply                   # interactive, explicitly confirmed apply
lanweave apply --yes             # non-interactive apply after review
lanweave backup                  # write a 0600 redacted local snapshot
lanweave status                  # health and device summary
lanweave clients --filter phone  # connected-client view
```

`--prune` is opt-in. It never targets the controller's WAN or `Default`
network, and it requires a separate `DELETE` confirmation in interactive mode.
Non-interactive mutation requires `--yes`; there is no implicit apply.
If an apply stops part-way through, review a fresh plan before retrying; see
[apply recovery](docs/recovery.md).

## MCP adapter

Install the optional dependency and run the server over local stdio:

```shell
uv sync --extra mcp
uv run lanweave-mcp
```

The server exposes health, devices, clients, secret-free export, local
validation and redacted planning. It intentionally exposes no apply or delete
tool. A desktop MCP client should launch `lanweave-mcp` from this checkout (or
from the installed package) with the required `UNIFI_*` environment variables.
The tool names, parameters and error codes are frozen in
[the MCP contract](docs/contracts.md#read-only-mcp-contract-v1).

## Configuration and credentials

Copy `.env.example` to `.env`, or export the variables in the process
environment. `.env` is ignored by Git. API keys provide read-only access to the
local Integration API; username and password session authentication are
required for declarative mutations.

Lanweave rejects literal WLAN passwords in YAML and refuses unresolved
`op://...` secret-manager references. This keeps the public configuration
portable and makes the secret boundary explicit.

## Development

```shell
uv sync --extra dev --extra mcp
uv lock --check
uv run ruff check .
uv run ruff format --check .
uv run pytest
uv build
```

Unit tests use simulated HTTP responses and never need a real controller.
Hardware compatibility tests must run against disposable or explicitly
designated controllers. See [contributing](CONTRIBUTING.md),
[security](SECURITY.md) and the [design notes](docs/design.md).

## License

Apache-2.0. See [LICENSE](LICENSE).

## Project links

- [source repository](https://github.com/Opperiesen/lanweave);
- [issues and roadmap](https://github.com/Opperiesen/lanweave/issues);
- [v1 contracts](docs/contracts.md);
- [v0.2.0 profile design](docs/profiles.md);
- [security policy](SECURITY.md);
- [contribution guide](CONTRIBUTING.md).
