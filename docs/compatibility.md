# Compatibility

Lanweave 0.1 targets the classic local UniFi Network API exposed below
`/proxy/network/api`. The adapter uses the current site selected by
`UNIFI_SITE` (default: `default`) and prefers an `X-API-Key` when one is
available.

## Supported in 0.1

| Area | Endpoints used | Capability |
| --- | --- | --- |
| Health | `stat/health` | read |
| Devices | `stat/device` | read |
| Clients | `stat/sta` | read |
| Networks | `rest/networkconf` | read, create, update, delete |
| WLANs | `rest/wlanconf` | read, create, update, delete |
| Backup | common `stat/*` and `rest/*` endpoints | redacted read |

The exact fields returned by UniFi can vary between Network application
versions. Lanweave keeps the API payload adapter narrow and ignores fields it
does not own when comparing declarative resources.

## Tested compatibility matrix

Only combinations listed as **tested** have published integration evidence.
Other controller versions are best-effort compatibility and must not be
treated as supported without a corresponding report.

| Deployment | UniFi OS | UniFi Network | Authentication | TLS | Read-only probes | Mutations |
| --- | --- | --- | --- | --- | --- | --- |
| UniFi Dream Router 7 (designated local controller) | 5.1.19 | 10.5.67 | local session | verification disabled locally | **tested** — 3 passed | not run |

The first evidence was collected on 2026-08-15 with the dedicated
`lanweave-ci` account. The probes covered health, device and client inventory,
networks and WLANs. No controller host, site name, credentials, topology or
raw response is part of this matrix.

This matrix currently proves read-only session authentication for one exact
controller combination. API-key integration, a second controller version and
the opt-in mutation suite remain unverified. They must be added as separate
evidence before the support policy is broadened.

## Authentication and TLS

- API-key authentication is preferred.
- Username/password session authentication is available as a fallback.
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
- `UNIFI_SITE` variable, defaulting to `default`;
- `UNIFI_VERIFY_TLS` variable, defaulting to `true`.

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

The suite creates, updates and deletes one VLAN-only test network and cleans it
up in a `finally` block. It must never be enabled against an operator's normal
production target without a dedicated network and recovery plan.

The integration jobs run on a dedicated self-hosted runner labelled
`lanweave-unifi` because a GitHub-hosted runner cannot reach a controller on a
private home network. The runner is isolated in a non-privileged Proxmox
container with no inbound service; the workflow remains `workflow_dispatch`
only and the `unifi-integration` environment is protected. Self-hosted jobs are
not container-isolated, so this runner must not be shared with untrusted
pull-request workflows.

For local execution, export the same `LANWEAVE_INTEGRATION_*` variables and
run the read-only suite explicitly:

```shell
uv run pytest tests/integration/test_controller.py -m integration -q
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
