# Lanweave v1.0 onboarding

This is the operator path for installing Lanweave, validating a declaration,
reviewing a live target and applying only an explicitly reviewed plan. The CLI
is the primary interface. MCP is optional and read-only.

## 1. Install and create a declaration

For a clean user installation:

```shell
uv tool install lanweave==1.0.0
lanweave --version
lanweave init --path config/network.yaml
```

`pipx install lanweave==1.0.0` provides the same isolated CLI installation.
Inside an existing virtual environment, use
`python -m pip install lanweave==1.0.0` instead.

For a checkout containing the public examples:

```shell
uv sync --extra dev
cp examples/network.yaml config/network.yaml
```

Validate locally before configuring a controller. This step makes no network
request:

```shell
lanweave validate --config config/network.yaml
lanweave profiles list --config config/network.yaml
lanweave profiles validate --config config/network.yaml
```

The v1 resource examples are intentionally separate so an operator can choose
the resource family and authentication boundary that applies to the target:

- [`examples/network.yaml`](../examples/network.yaml): networks and WLANs;
- [`examples/dns.yaml`](../examples/dns.yaml): DNS `A`, `AAAA` and `CNAME`;
- [`examples/firewall.yaml`](../examples/firewall.yaml): zones, groups and
  ordered rules;
- [`examples/nat.yaml`](../examples/nat.yaml): the supported IPv4 mapping
  shape, disabled by default;
- [`examples/vpn.yaml`](../examples/vpn.yaml): read-only VPN overview and
  route observations.

## 2. Configure credentials without putting them in YAML

Copy `.env.example` to a local ignored file or export variables in the process
environment. Never commit `.env`, a backup, an export or a raw controller
response.

For local API-key read operations:

```shell
export UNIFI_HOST=https://controller.example.invalid
export UNIFI_SITE=default
export UNIFI_VERIFY_TLS=true
export UNIFI_API_KEY='provided-by-the-controller'
```

For the legacy session surface, use `UNIFI_USER` and `UNIFI_PASS` instead of
`UNIFI_API_KEY`. Prefer a dedicated least-privilege account. TLS verification
is enabled by default; `UNIFI_VERIFY_TLS=false` is only an explicit escape
hatch for a locally controlled certificate.

Check the resolved settings and target before any mutation:

```shell
lanweave doctor --config config/network.yaml
lanweave doctor --check --config config/network.yaml
lanweave capabilities --config config/network.yaml --output json
```

`capabilities` is local and does not contact the target. `doctor --check` is a
read-only health request.

## 3. Inspect, export and audit the live target

Use a selected v2 profile with `--profile`, or use the single v1 target from
the environment:

```shell
lanweave status --config config/network.yaml
lanweave clients --config config/network.yaml --output json
lanweave export --config config/network.yaml --out live.yaml
lanweave backup --config config/network.yaml --output backups/
lanweave audit --config config/network.yaml --output table
lanweave audit --config config/network.yaml --output json > audit.json
```

The export and backup are redacted. Audit exit codes are stable: `0` means
in-sync, `1` means proven drift and `2` means unknown or unsupported coverage.
Unknown and unsupported state is never treated as compliance.

## 4. Plan, review and apply

Always save and review a deterministic redacted plan before applying:

```shell
lanweave plan --config config/network.yaml --output json > plan.json
lanweave plan --config config/network.yaml
lanweave apply --config config/network.yaml
```

Non-interactive automation must make the confirmation explicit:

```shell
lanweave apply --config config/network.yaml --yes
```

`--prune` is opt-in and has its own confirmation. Firewall and NAT risk
warnings additionally require `--acknowledge-risk` after the plan has been
reviewed. VPN observations are read-only and a plan containing them cannot
perform a VPN write.

After a write, Lanweave performs a scoped read-only convergence check. A
successful result is `converged`; `drifted`, `uncertain` and `unsupported`
require a fresh read and plan. Lanweave never retries, compensates or rolls
back a failed controller request automatically. The complete manual recovery
procedure is in [`docs/recovery.md`](recovery.md).

## 5. Use explicit v2 profiles

[`examples/profiles-v2.yaml`](../examples/profiles-v2.yaml) shows one API-key
target and one session target without storing their URLs or credentials.
Validate and list it offline:

```shell
lanweave profiles validate --config examples/profiles-v2.yaml
lanweave profiles list --config examples/profiles-v2.yaml
lanweave capabilities --config examples/profiles-v2.yaml --profile office --output json
lanweave plan --config examples/profiles-v2.yaml --profile office --output json
```

The profile selector must be explicit when the document has no top-level
`profile`; `--profile` and `LANWEAVE_PROFILE` must not conflict. A v2 target
identity is `{profile, controller, site, adapter}` and is carried into plans
and read-only responses so a plan cannot silently target another controller.

## 6. Understand the capability boundaries

| Authentication/adapter | Supported v1 surface |
| --- | --- |
| Local session | Network/WLAN read and supported mutations; NAT read/export/plan/apply/prune; redacted backup |
| Local API key | Network/WLAN read; DNS and documented firewall lifecycle; VPN read/export/plan overview |
| Cloud Site Manager | Hosts, sites, devices and derived health read-only inventory |
| Any MCP target | Nine read-only tools; no apply, create, update, delete or prune |

Run `lanweave capabilities --output json` against the selected profile rather
than inferring support from another authentication mode. Unsupported
operations fail closed with a structured capability error.

## 7. Optional MCP setup

Install the optional extra and launch the local stdio server:

```shell
uv tool install --upgrade 'lanweave[mcp]==1.0.0'
lanweave-mcp
```

With `pipx`, the equivalent is:

```shell
pipx install 'lanweave[mcp]==1.0.0'
lanweave-mcp
```

Configure the MCP host to launch `lanweave-mcp` with the same environment
variables as the CLI. The server exposes health, capabilities, devices,
clients, VPN inventory, audit, export, validation and planning. It keeps one
authenticated adapter per target for the lifetime of a stdio session and
never becomes a write path around the reviewed CLI plan. See the frozen
[MCP contract](contracts.md#read-only-mcp-contract-v3).

## 8. Clean-install verification

From a clean checkout, the offline onboarding path is reproducible with:

```shell
uv sync --extra dev --locked
uv run lanweave init --path /tmp/lanweave-network.yaml
uv run lanweave validate --config /tmp/lanweave-network.yaml
uv run lanweave profiles list --config examples/profiles-v2.yaml
uv run lanweave profiles validate --config examples/profiles-v2.yaml
uv run pytest tests/test_onboarding.py -q
```

The protected release workflow repeats wheel and source-distribution clean
installs. Live `doctor --check`, export, plan, audit and apply verification
belongs to the protected controller workflow because it requires an explicitly
designated target and credentials.
