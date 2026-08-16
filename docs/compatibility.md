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
v0.2.0 compatibility claim. The v0.3 additions are described below.

Lanweave 0.6 supports two local UniFi Network API surfaces. Username/password
session authentication uses the classic endpoints below `/proxy/network/api`.
API-key authentication uses the v1 Integration API below
`/proxy/network/integration/v1`. Both modes resolve the current site selected by
`UNIFI_SITE` (default: `default`).

The v0.5 firewall extension uses only the local API-key Integration API and does
not broaden session or Site Manager capabilities. Its protected evidence is
recorded in [`evidence/v0.5.0-firewall.md`](evidence/v0.5.0-firewall.md).

The v0.6 NAT and port-forwarding extension uses only the local classic session
endpoint `rest/portforward`. It does not infer support from the Integration API,
API-key mode, Site Manager or VPN endpoints. Its protected evidence is tracked
separately in [`evidence/v0.6.0-nat.md`](evidence/v0.6.0-nat.md).

## v0.7.0 VPN compatibility

The v0.7.0 VPN family uses only the local API-key Integration API overview
endpoints `vpn/servers` and `vpn/site-to-site-tunnels`. Connected `VPN` and
`TELEPORT` clients are read from the documented clients endpoint. The selected
capability is `read/export/plan`; session authentication, Site Manager and all
VPN mutations remain unsupported. Routes and handshakes are marked as not
reported when the official overview does not provide them.

The designated controller has no active VPN configuration available for a
safe live lifecycle in this release. The limitation is recorded in
[`evidence/v0.7.0-vpn.md`](evidence/v0.7.0-vpn.md); fixtures and the offline
gate prove the normalization and secret boundary without turning an absent
resource into a compatibility claim.

## v0.8.0 audit compatibility

The v0.8.0 audit compares only the portable resource families already exposed
by the selected adapter with `export` capability. Local API-key targets cover
networks, WLANs, DNS, firewall and VPN according to the capability document;
local session targets cover networks, WLANs and NAT. The cloud Site Manager
adapter does not expose these resource exports and therefore returns
`unsupported` without making a resource request.

The audit is read-only and uses the same target identity and secret boundary as
export and plan. WAN networks are outside the portable network export, and
VPN route tables are outside the official overview; both are reported as
`unknown` when declared. A proven portable difference is `drifted`; a read or
coverage limitation is never downgraded to compliance.

## v0.9.0 post-apply compatibility

The v0.9.0 convergence check reuses the selected adapter's read/export
capabilities and verifies only the resource families changed by the reviewed
plan. It supports the already published network, WLAN, DNS, firewall and NAT
families; it does not turn VPN observations into writable or fully verifiable
resources.

The check is read-only and does not retry, compensate or roll back a request.
`converged` is proof that the affected portable state matches the declaration;
`drifted` is a proven difference; `uncertain` covers failed or incomplete
readback; and `unsupported` covers an adapter without the required export
capability. The latter two states are never treated as success.

After a partial failure, the same readback is included in the sanitized
recovery report. A fresh plan remains mandatory before retrying. The MCP
contract remains read-only and unchanged at v3.

## Supported local surfaces

| Area | Endpoints used | Capability |
| --- | --- | --- |
| Health | `stat/health` / `v1/info` | read |
| Devices | `stat/device` / `v1/sites/{siteId}/devices` | read |
| Clients | `stat/sta` / `v1/sites/{siteId}/clients` | read |
| Networks | `rest/networkconf` / `v1/sites/{siteId}/networks` | session read/create/update/delete; API key read |
| WLANs | `rest/wlanconf` / `v1/sites/{siteId}/wifi/broadcasts` | session read/create/update/delete; API key read |
| DNS policies | n/a / `v1/sites/{siteId}/dns/policies` | API key read/export/plan/create/update/delete/prune; session unsupported |
| Firewall zones | n/a / `v1/sites/{siteId}/firewall/zones` | API key read/export/plan/apply/prune; session and cloud unsupported |
| Firewall groups | n/a / `v1/sites/{siteId}/traffic-matching-lists` | API key read/export/plan/apply/prune for `PORTS`, `IPV4_ADDRESSES` and `IPV6_ADDRESSES` |
| Firewall policies/order | n/a / `v1/sites/{siteId}/firewall/policies` and `/ordering` | API key read/export/plan/apply/prune; index-based order is excluded |
| NAT / port forwarding | `rest/portforward` / n/a | local session read/export/plan/apply/prune for the supported IPv4 subset; API key, cloud and VPN unsupported |
| VPN servers | n/a / `v1/sites/{siteId}/vpn/servers` | local API key read/export/plan; secret-free overview only; session, cloud and mutation unsupported |
| Site-to-site VPN tunnels | n/a / `v1/sites/{siteId}/vpn/site-to-site-tunnels` | local API key read/export/plan; overview only; routes and handshakes not inferred |
| Connected VPN peers | n/a / `v1/sites/{siteId}/clients` filtered to `VPN`/`TELEPORT` | local API key read through the VPN inventory; no generated profiles or keys |
| Backup | classic `stat/*` and `rest/*` endpoints | local session redacted read/export; API-key and cloud unsupported |

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
| UniFi Dream Router 7 (designated local controller) | 5.1.19 | 10.5.67 | local session (NAT v0.6.0) | verification disabled locally | **tested** — [protected NAT probes passed](https://github.com/Opperiesen/lanweave/actions/runs/31907918542) | **tested** — [NAT create/update/protected-prune/delete passed](https://github.com/Opperiesen/lanweave/actions/runs/31907918542) |
| UniFi Dream Router 7 (designated local controller) | 5.1.19 | 10.5.67 | local API key (v1 Integration API) | verification disabled locally | **tested** — [3 passed](https://github.com/Opperiesen/lanweave/actions/runs/31883645969) | **tested** — DNS create/update/prune |
| UniFi Dream Router 7 (designated local controller) | 5.1.19 | 10.5.67 | local API key (v1 Integration API) | verification disabled locally | **tested** — [6 passed](https://github.com/Opperiesen/lanweave/actions/runs/31903782251) | **tested** — [firewall create/update/reorder/delete passed](https://github.com/Opperiesen/lanweave/actions/runs/31903782251) |

The first evidence was collected on 2026-08-15 with the dedicated
`lanweave-ci` account. The probes covered health, device and client inventory,
networks and WLANs. No controller host, site name, credentials, topology or
raw response is part of this matrix.

The v0.4 DNS evidence used the same designated controller and a protected API
key. It read the DNS policy family, created and updated one isolated `A`
record, pruned it as a user-managed policy and verified an empty final state.
The sanitized record is documented in
[`evidence/v0.4.0-dns.md`](evidence/v0.4.0-dns.md).

The authorized mutation evidence used the separate local-only `Lanweave
Mutation` role and created, updated and deleted one VLAN-only network on the
dedicated target; the final controller inventory contains no mutation target.

This matrix currently proves read-only session and API-key authentication,
session network and NAT mutations, API-key DNS policy mutations and API-key
firewall mutations for one exact controller combination. The NAT claim is
limited to the documented IPv4 subset and the session-scoped ownership rule;
a second controller version remains a separate evidence track.

## Authentication and TLS

- The v0.3 adapter name for this surface is `local-classic`.
- Session authentication exposes read, export, plan, apply and explicit prune
  for the supported network and WLAN resources.
- API-key authentication remains read-only for networks and WLANs. The
  documented local DNS policy and firewall endpoints are the only API-key
  mutation exceptions; no generic API-key mutation is enabled.
- The v0.7 VPN overview is local API-key-only and read-only. It exposes
  normalized server, tunnel and connected-peer inventory; it does not expose
  private keys, generated profiles, route tables or handshake state.
- NAT inventory and mutations require local session authentication and the
  classic `rest/portforward` endpoint. The v0.6 portable write subset is IPv4,
  interface-selected public address, at most one source CIDR and no explicit
  description, source zone or hairpin behavior; unsupported variants fail
  closed. The endpoint omits ownership metadata on the tested controller, so
  IDs created successfully in the current client session are the only extra
  ownership evidence; a later client keeps them protected as `UNKNOWN`.
- DNS policies require UniFi Network 10.3.58 or a controller version with the
  same official Integration API contract. The portable scope is `A`, `AAAA`
  and `CNAME`; unsupported policy types are ignored on read and are never
  silently converted.
- Firewall policies require the documented Integration API families for zones,
  traffic matching lists, policies and ordering. The portable v0.5 subset is
  limited to the fields in [`firewall.md`](firewall.md); unsupported group,
  filter, action or ordering variants fail closed.
- Firewall apply and prune are API-key-only and are available only to the
  `local-classic` adapter. A plan with broad, external, privileged-port,
  shadowing or reorder warnings requires an additional explicit risk
  acknowledgement. MCP remains read-only.
- Username/password session authentication targets the classic API and is
  required for declarative network, WLAN and supported NAT mutations; it does
  not advertise DNS or firewall policy operations.
- TLS certificate verification is enabled by default.
- `UNIFI_VERIFY_TLS=false` is an explicit escape hatch for local certificates.

The v0.3 adapter name for the official cloud surface is
`cloud-site-manager`. It targets the versioned Site Manager API at
`https://api.ui.com/v1` with the `X-API-KEY` header and is deliberately
read-only. The first supported slice inventories visible hosts, sites and
devices, and exposes a reachability-oriented health view derived from sites.
Pagination is bounded and rate-limit responses are normalized without
including credentials in errors.

The cloud adapter does not expose clients, networks, WLANs, export, plan,
apply or prune. It is selected explicitly through the profile adapter field;
there is no automatic local/cloud fallback. The cloud capability claim remains
limited to this documented read-only slice. It was exercised against a real UI
account by the protected [Site Manager integration run
31895015047](https://github.com/Opperiesen/lanweave/actions/runs/31895015047)
using API v1.0.0. The published report contains only the endpoint scope and
test outcome; the API host, credentials, inventory and raw responses remain
private.

## v0.3 operator and MCP compatibility

`lanweave capabilities` resolves the selected target identity and capability
document locally. It never loads a credential value and never makes a target
request. The JSON form is the canonical operator-facing representation:

```json
{
  "target": {
    "profile": "cloud-overview",
    "controller": "cloud",
    "site": "organization",
    "adapter": "cloud-site-manager"
  },
  "capabilities": {
    "format_version": 1,
    "adapter": "cloud-site-manager",
    "auth_modes": ["api-key"],
    "resources": [
      {"resource": "devices", "operations": ["read"]},
      {"resource": "health", "operations": ["read"]},
      {"resource": "hosts", "operations": ["read"]},
      {"resource": "sites", "operations": ["read"]}
    ]
  }
}
```

The read-only MCP contract is v3. It adds
`lanweave_get_capabilities`, keeps the existing target selectors, and includes
the selected capability document in health and device responses. Cloud health
does not invent client data: `online_clients` is omitted when the selected
adapter does not support client reads. Unsupported cloud reads, exports and
plans return `unsupported_capability` before a network request.

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

The same workflow has a separate `run_firewall_mutations` input. It requires
API-key mode, the protected `I_UNDERSTAND` firewall confirmation, a
`lanweave-ci-*` prefix and uses only disabled groups/rules. Its lifecycle
evidence is independent from the network and DNS mutation suites. The v0.5
protected run covered one exact controller combination and passed both the
read-only and firewall lifecycle jobs.

The workflow also has a separate `run_nat_mutations` input. It requires local
session mode, the protected `I_UNDERSTAND` confirmation, the same dedicated
mutation account and a `lanweave-ci-*` prefix. The NAT suite uses one disabled
IPv4 mapping on an unprivileged port, verifies create/update/protected prune and
cleans it up in a `finally` block. Its evidence is independent from network,
DNS and firewall mutation suites and is not enabled by default.

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

For the separately guarded NAT lifecycle, use a local session target and the
dedicated NAT confirmation/prefix variables:

```shell
LANWEAVE_INTEGRATION_NAT_MUTATIONS=true \
LANWEAVE_INTEGRATION_NAT_MUTATION_CONFIRM=I_UNDERSTAND \
uv run pytest tests/integration/test_nat_mutations.py -m integration_mutation -q
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
