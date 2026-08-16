 # Lanweave

[![CI](https://github.com/Opperiesen/lanweave/actions/workflows/ci.yml/badge.svg)](https://github.com/Opperiesen/lanweave/actions/workflows/ci.yml)
[![License](https://img.shields.io/github/license/Opperiesen/lanweave)](LICENSE)
[![Latest release](https://img.shields.io/github/v/release/Opperiesen/lanweave?include_prereleases)](https://github.com/Opperiesen/lanweave/releases)
[![PyPI version](https://img.shields.io/pypi/v/lanweave)](https://pypi.org/project/lanweave/)
[![PyPI downloads/month](https://img.shields.io/pypi/dm/lanweave?label=downloads%2Fmonth)](https://pypistats.org/packages/lanweave)
[![Python versions](https://img.shields.io/pypi/pyversions/lanweave)](https://pypi.org/project/lanweave/)

![Lanweave logo](https://raw.githubusercontent.com/Opperiesen/lanweave/v1.0.1/assets/logo.svg)

Lanweave is a local-first, open-source toolkit for managing and observing
UniFi Network controllers. It turns a controller into a small, reviewable
GitOps project without requiring a cloud service.

The name is intentionally independent from the controller vendor. Lanweave is
not affiliated with, endorsed by, or sponsored by Ubiquiti Inc. UniFi is a
trademark of Ubiquiti Inc.

> **Best fit:** operators who want a reviewable, local-first control plane for
> a UniFi network. Lanweave is not a replacement for the UniFi web interface
> and does not claim support for every controller endpoint.

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

Lanweave `1.0.1` is the current patch release of the stable v1.0 local
network control-plane. It preserves the
local-first profile behavior, read-only Site Manager cloud adapter, DNS,
firewall, guarded NAT and VPN families, and adds deterministic post-apply
readback and recovery evidence for the classic local UniFi Network API. It
targets self-hosted
UniFi Network applications and UniFi OS consoles; see
[compatibility](docs/compatibility.md) and the [apply recovery model](docs/recovery.md)
for the exact scope, tested matrix and partial-failure behavior. The frozen
public surfaces are described in [contracts](docs/contracts.md).

> **Stable support boundary:** v1.0.0 is validated on a UDR7 running UniFi OS
> 5.1.19 and UniFi Network 10.5.67. Other controller and application versions
> may work, but remain unverified until they appear in the
> [compatibility matrix](docs/compatibility.md).

Supported resource families in this release:

- networks;
- WLANs, including references to environment-provided passwords;
- local DNS `A`, `AAAA` and `CNAME` records;
- local firewall zones, address groups, port groups and ordered rules;
- local NAT and port-forwarding mappings in the documented IPv4 subset;
- local VPN server and site-to-site tunnel overviews, connected peers and
  route dependency validation;
- secret-free drift audits with deterministic JSON reports and CI exit codes;
- local controller/site profiles with explicit target selection;
- controller health, devices and clients;
- redacted snapshots of common operational endpoints.

The `0.7.0` and `0.8.0` releases add the read-only local VPN inventory and
declared-versus-live audit surfaces; see the [VPN contract](docs/vpn.md),
[audit contract](docs/audit.md) and [v0.8 roadmap](docs/roadmap-v0.8.0.md).
The `0.9.0` release adds [post-apply convergence](docs/roadmap-v0.9.0.md):
`apply` reports `converged`, `drifted`, `uncertain` or `unsupported` after a
read-only verification and never retries or rolls back automatically. It does
not generate VPN profiles or keys, apply VPN changes or repair drift.

The firewall family is limited to the documented local API-key Integration API
surface. See [firewall](docs/firewall.md), [compatibility](docs/compatibility.md)
and the [v0.5 roadmap](docs/roadmap-v0.5.0.md) for the exact support boundary.

The `cloud-site-manager` adapter exposes only documented read-only hosts,
sites, devices and derived site health. Run `lanweave capabilities` before
selecting a target to inspect its supported operations.

Device mutation workflows remain outside v1.0.0. NAT support is limited
to the documented IPv4 subset, with explicit exposure warnings and protected
ownership behavior; see [NAT](docs/nat.md) and the [v0.6.0 roadmap](docs/roadmap-v0.6.0.md).

## Quick start

Requires Python 3.11+. For an isolated CLI installation, [uv](https://docs.astral.sh/uv/)
is recommended:

```shell
uv tool install lanweave==1.0.1
lanweave --version
```

Equivalent installation options are available when `uv` is not already part
of the operator's toolchain:

```shell
pipx install lanweave==1.0.1
# or, inside an existing virtual environment:
python -m pip install lanweave==1.0.1
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

The complete operator path, profile examples and capability boundaries are in
the [v1.0 onboarding guide](docs/onboarding-v1.0.md).

### Safe first run

After configuring the controller environment, the normal operator path is:

```shell
lanweave init
# edit config/network.yaml and set UNIFI_* variables
lanweave validate
lanweave doctor --check
lanweave plan
lanweave apply
```

`validate` is local-only. `doctor --check` and `plan` are read-only; `apply`
is the only command in this sequence that can change the controller, and it
requires an explicit confirmation.

Edit `config/network.yaml` and provide secrets only through the environment:

```yaml
wlans:
  - name: Home
    ssid: Home
    network: Home
    security: wpa2
    password_env: WIFI_HOME_PASSWORD

dns:
  - name: printer.home.arpa
    type: A
    address: 192.0.2.10
    ttl_seconds: 300
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
lanweave capabilities --output json # inspect selected adapter capabilities
lanweave export --out live.yaml # export secret-free desired-state YAML
lanweave plan                    # show create/update/delete operations
lanweave plan --output json      # machine-readable, redacted plan
lanweave apply                   # interactive, explicitly confirmed apply
lanweave apply --yes             # non-interactive apply after review
lanweave apply --acknowledge-risk # authorize reviewed firewall/NAT warnings
lanweave backup                  # write a 0600 redacted local snapshot
lanweave status                  # health and device summary
lanweave clients --filter phone  # connected-client view
lanweave vpn --output json       # read-only VPN inventory and coverage
lanweave audit --output table    # compare declared and live portable state
lanweave audit --output json     # machine-readable audit report
```

`--prune` is opt-in. It never targets the controller's WAN or `Default`
network, skips system/unknown-origin DNS policies, and requires a separate
`DELETE` confirmation in interactive mode.
Firewall and NAT changes with broad, external, privileged-port, shadowing,
reorder or exposure warnings additionally require `--acknowledge-risk` (the
legacy `--acknowledge-firewall-risk` alias remains accepted) or the exact
interactive acknowledgement. The flag does not bypass the plan or prune
confirmation.
Non-interactive mutation requires `--yes`; there is no implicit apply.
If an apply stops part-way through, review a fresh plan before retrying; see
[apply recovery](docs/recovery.md).

## MCP adapter

Install the optional dependency and run the server over local stdio:

```shell
uv sync --extra mcp
uv run lanweave-mcp
```

The server exposes health, devices, clients, read-only VPN inventory, a
secret-free audit report, secret-free export, local validation and redacted
planning, including supported NAT state through export and plans. It
intentionally exposes no apply or delete tool. A desktop MCP
client should launch `lanweave-mcp` from this checkout (or
from the installed package) with the required `UNIFI_*` environment variables.
The tool names, parameters and error codes are frozen in
[the MCP contract](docs/contracts.md#read-only-mcp-contract-v3).

## Configuration and credentials

Copy `.env.example` to `.env`, or export the variables in the process
environment. `.env` is ignored by Git. API keys provide read-only access to
networks, WLANs and the VPN overview through the local Integration API, plus
the documented DNS policy create/update/delete endpoint. Username and password session
authentication remains required for network, WLAN and supported NAT mutations.

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
- [PyPI package](https://pypi.org/project/lanweave/);
- [issues and roadmap](https://github.com/Opperiesen/lanweave/issues);
- [v1.0.1 release notes](docs/release-v1.0.1.md);
- [MCP and audit contracts](docs/contracts.md);
- [v1.0 onboarding guide](docs/onboarding-v1.0.md);
- [v0.2.0 profile design](docs/profiles.md);
- [security policy](SECURITY.md);
- [contribution guide](CONTRIBUTING.md).
