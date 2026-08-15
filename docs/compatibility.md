# Compatibility

## Version 0.2 profile compatibility

Lanweave `v0.2.0` keeps the version-1 resource and local environment behavior
while adding a version-2 profile layer for multiple local controllers and
sites. The sanitized target identity is carried through controller-facing CLI,
plan and MCP responses; credentials and controller URLs remain outside the
identity.

Preserved behavior:

- version-1 YAML files remain valid and keep their `controller.site` and
  `UNIFI_*` precedence;
- version-1 plan JSON remains valid because `target` is an optional additive
  field;
- legacy CLI invocations without a profile continue to resolve the single
  target from the existing environment;
- the MCP adapter remains read-only and still supports environment-only target
  resolution for version-1 usage.

Deliberate v0.2 changes:

- controller-facing CLI commands accept explicit `--config` and `--profile`
  selectors and reject conflicts before controller access;
- version-2 plans include `{profile, controller, site}` and reject a missing or
  different identity before mutation;
- the MCP contract is v2: controller-facing tools accept `config_path` and
  `profile`, while list/export responses use a `target` envelope;
- version-2 configurations require an effective selector and never choose the
  first profile implicitly.

Cloud adapters, new resource families and write-capable MCP remain outside the
v0.2.0 compatibility claim.

Lanweave 0.1 supports two local UniFi Network API surfaces. Username/password
session authentication uses the classic endpoints below `/proxy/network/api`.
API-key authentication uses the v1 Integration API below
`/proxy/network/integration/v1` and is currently read-only. Both modes resolve
the current site selected by `UNIFI_SITE` (default: `default`).

## Supported in 0.1

| Area | Endpoints used | Capability |
| --- | --- | --- |
| Health | `stat/health` / `v1/info` | read |
| Devices | `stat/device` / `v1/sites/{siteId}/devices` | read |
| Clients | `stat/sta` / `v1/sites/{siteId}/clients` | read |
| Networks | `rest/networkconf` / `v1/sites/{siteId}/networks` | session read/create/update/delete; API key read |
| WLANs | `rest/wlanconf` / `v1/sites/{siteId}/wifi/broadcasts` | session read/create/update/delete; API key read |
| Backup | common `stat/*` and `rest/*` endpoints | redacted read |

The exact fields returned by UniFi can vary between Network application
versions. Lanweave keeps the API payload adapter narrow and ignores fields it
does not own when comparing declarative resources.

Partial apply behavior, dependency ordering, sanitized failure reports and the
manual retry boundary are documented in [apply recovery](recovery.md).

## Tested compatibility matrix

Only combinations listed as **tested** have published integration evidence.
Other controller versions are best-effort compatibility and must not be
treated as supported without a corresponding report.

| Deployment | UniFi OS | UniFi Network | Authentication | TLS | Read-only probes | Mutations |
| --- | --- | --- | --- | --- | --- | --- |
| UniFi Dream Router 7 (designated local controller) | 5.1.19 | 10.5.67 | local session | verification disabled locally | **tested** — 3 passed | **tested** — [create/update/delete passed](https://github.com/Opperiesen/lanweave/actions/runs/31884501527) |
| UniFi Dream Router 7 (designated local controller) | 5.1.19 | 10.5.67 | local API key (v1 Integration API) | verification disabled locally | **tested** — [3 passed](https://github.com/Opperiesen/lanweave/actions/runs/31883645969) | not run |

The first evidence was collected on 2026-08-15 with the dedicated
`lanweave-ci` account. The probes covered health, device and client inventory,
networks and WLANs. No controller host, site name, credentials, topology or
raw response is part of this matrix.

The authorized mutation evidence used the separate local-only `Lanweave
Mutation` role and created, updated and deleted one VLAN-only network on the
dedicated target; the final controller inventory contains no mutation target.

This matrix currently proves read-only session and API-key authentication, plus
session create/update/delete coverage, for one exact controller combination. A
second controller version and API-key mutations remain separate evidence
tracks.

## Authentication and TLS

- The v0.3 adapter name for this surface is `local-classic`.
- Session authentication exposes read, export, plan, apply and explicit prune
  for the supported network and WLAN resources.
- API-key authentication remains read-only at the controller boundary; it can
  inventory, export and plan the supported resources but cannot apply or
  prune them.
- API-key authentication targets the v1 Integration API and is read-only for
  now.
- Username/password session authentication targets the classic API and is
  required for declarative mutations.
- TLS certificate verification is enabled by default.
- `UNIFI_VERIFY_TLS=false` is an explicit escape hatch for local certificates.

The official cloud API is not claimed as compatible by this release. A future
adapter may support it once the authentication and resource semantics are
covered by fixtures and integration tests.

## Controller integration workflow

The repository contains an opt-in, manually triggered workflow at
`.github/workflows/integration.yml`. It runs against a disposable or explicitly
designated controller through the protected GitHub environment
`unifi-integration`.

The read-only job uses these environment secrets and variables:

- `UNIFI_HOST` secret;
- either `UNIFI_API_KEY` or `UNIFI_USER` plus `UNIFI_PASS` secrets;
- the mutation job additionally uses the separate `UNIFI_MUTATION_USER` plus
  `UNIFI_MUTATION_PASS` secrets;
- `UNIFI_SITE` variable, defaulting to `default`;
- `UNIFI_VERIFY_TLS` variable, defaulting to `true`.

The `api_mode` workflow input selects the authentication surface. API-key mode
requires `UNIFI_API_KEY`; session mode ignores that secret. The mutation job
rejects API-key mode and forces session authentication.

The workflow input records the exact UniFi Network version, UniFi OS version
and authentication mode used for the run. The resulting artifact contains only
those public compatibility fields and test outcomes; it never contains the
controller host, credentials, topology or raw API responses.

The mutation job is disabled by default. Enabling it requires all of:

1. the `run_mutations` workflow input;
2. the `LANWEAVE_INTEGRATION_MUTATION_CONFIRM` environment secret set to the
   explicit confirmation value;
3. a `LANWEAVE_MUTATION_PREFIX` variable beginning with `lanweave-ci-`;
4. a dedicated IPv4 test subnet and VLAN in environment variables.

Its session credentials are separate from the read-only credentials and belong
to a local-only `Lanweave Mutation` role with site-level network administration
and no Identity permissions.

The suite creates, updates and deletes one VLAN-only test network and cleans it
up in a `finally` block. It must never be enabled against an operator's normal
production target without a dedicated network and recovery plan.

The integration jobs run on a dedicated self-hosted runner labelled
`lanweave-unifi` because a GitHub-hosted runner cannot reach a controller on a
private home network. The runner is isolated in a non-privileged Proxmox
container with no inbound service; the workflow remains `workflow_dispatch`
only and the `unifi-integration` environment is protected. Self-hosted jobs are
not container-isolated, so this runner must not be shared with untrusted
pull-request workflows. The container is provisioned with Debian 13's system
Python 3.13 and `uv` in `/usr/local/bin`; the integration workflow verifies this
toolchain directly because `setup-python` does not publish binaries for Debian
13.

For local execution, export the same `LANWEAVE_INTEGRATION_*` variables and
run the read-only suite explicitly:

```shell
uv run pytest \
  tests/integration/test_controller.py \
  tests/integration/test_profile_integration.py \
  -m integration -q
```

Mutations must be run separately and only with a dedicated target:

```shell
LANWEAVE_INTEGRATION_MUTATIONS=true \
LANWEAVE_INTEGRATION_MUTATION_CONFIRM=I_UNDERSTAND \
uv run pytest tests/integration/test_mutations.py -m integration_mutation -q
```

An absent protected configuration causes the read-only tests to skip safely;
it does not turn simulated fixtures into a compatibility claim.

## Reporting a controller difference

Please include the UniFi Network application/controller version, the command
that failed, a redacted response or fixture, and whether the request used an
API key or session authentication. Never attach credentials, private keys,
Wi-Fi passphrases, public IPs or a raw controller backup.

Use the [issue tracker](https://github.com/Opperiesen/lanweave/issues) for
reproducible compatibility reports. Security-sensitive reports belong in the
[private advisory channel](../SECURITY.md).
