# Lanweave v0.3.0 roadmap

Lanweave v0.3.0 introduces an adapter boundary and a deliberately small
official-cloud product slice. It is an architecture and observability release,
not a promise to expose every UniFi endpoint.

The release keeps the local-first behavior of v0.2.0 and adds an explicit,
opt-in adapter for the official UniFi Site Manager API. The cloud adapter is
read-only in this release. It must never be selected implicitly after a local
failure, and it must never expose a write-capable MCP path.

## Product outcome

At the end of v0.3.0 an operator can:

- keep using existing v1 and v2 local profiles without migration work;
- see which adapter is selected for every target;
- inspect the supported resources and operations before running a command;
- use the existing local classic adapter with the v0.2.0 behavior;
- opt into a cloud target using an environment-backed API key;
- read documented Site Manager hosts, sites, devices and supported health
  metrics through the cloud adapter;
- receive a deterministic unsupported-capability error for cloud networks,
  WLANs, clients, export, plan, apply or prune paths not covered by the
  documented cloud API;
- discover the same adapter and capability information through the read-only
  MCP interface.

The official references for the cloud scope are the
[Ubiquiti API overview](https://help.ui.com/hc/en-us/articles/30076656117655-Getting-Started-with-the-Official-UniFi-API)
and the [Site Manager API v1 documentation](https://developer.ui.com/site-manager/v1.0.0/).
The detailed Network API remains a separate local application surface; its
version-specific documentation is published in the [Network API developer
portal](https://developer.ui.com/network/v9.4.17).

## Capability matrix

The capability report is the source of truth. An empty cell means that the
operation is not part of the v0.3.0 claim and must fail explicitly rather than
being emulated or sent to an undocumented endpoint.

| Adapter | Health / status | Hosts and sites | Devices | Clients | Networks / WLANs | Export / plan / apply |
| --- | --- | --- | --- | --- | --- | --- |
| `local-classic` with session auth | read | read | read | read | read, export, plan, apply, explicit prune | supported according to v0.2.0 limits |
| `local-classic` with API-key auth | read | read | read | read | read only | export, plan and apply remain restricted by the current API-key contract |
| `cloud-site-manager` | read | read | read | unsupported unless documented and fixture-backed | unsupported | unsupported; no cloud mutation path |

The matrix must be represented in machine-readable capability output and in
the compatibility documentation. The implementation cannot claim a shared
resource merely because two adapters return a field with the same name.

## Contract decisions

### Adapter boundary

The boundary separates:

1. transport and HTTP lifecycle;
2. authentication and secret loading;
3. target selection and non-secret identity;
4. resource operations and normalized read models;
5. capability discovery and safe error reporting.

Capabilities are keyed by resource and operation. They are deterministic,
ordered and secret-free. A capability response must make it possible to answer
all of the following before an operation starts:

- which adapter is selected;
- which target is selected;
- whether the resource is supported;
- whether the operation is read-only or mutating;
- which authentication mode and compatibility limits apply, without exposing
  credentials.

### Configuration and plans

- v1 configurations continue to resolve to `local-classic`;
- v2 controller definitions gain an optional `adapter` field;
- an omitted v2 adapter means `local-classic`, preserving existing files;
- cloud selection is explicit and cannot be inferred from a hostname or a
  failed local request;
- `TargetIdentity` gains the adapter as a non-secret field;
- the existing plan format remains readable: a legacy target without an
  adapter is local-classic only;
- target mismatch checks compare adapter, profile, controller and site before
  any controller request;
- exported configuration, plans, backups, logs and reports contain neither
  resolved credentials nor private endpoint values.

### MCP

The read-only MCP contract is extended for capability discovery. The v0.3
contract version is explicit, existing v2 local calls remain callable where
their parameters and response envelope are unchanged, and unsupported cloud
operations return structured errors. No write-capable tool is added.

## Work breakdown

The GitHub milestone is tracked by [Epic #56](https://github.com/Opperiesen/lanweave/issues/56).

### 1. Design and local compatibility

- [#14 — adapter capability boundary and architecture review](https://github.com/Opperiesen/lanweave/issues/14)
- [#57 — freeze adapter and capability contracts](https://github.com/Opperiesen/lanweave/issues/57)
- [#58 — put the local classic client behind the adapter boundary](https://github.com/Opperiesen/lanweave/issues/58)
- [#59 — add explicit adapter selection to profiles and target identity](https://github.com/Opperiesen/lanweave/issues/59)

Exit condition: existing v1/v2 local configurations, plans, CLI behavior and
MCP behavior remain green, while the adapter and target identity are explicit.

### 2. Official cloud read-only slice

- [#4 — official cloud adapter implementation umbrella](https://github.com/Opperiesen/lanweave/issues/4)
- [#60 — Site Manager authentication and transport](https://github.com/Opperiesen/lanweave/issues/60)
- [#61 — cloud inventory and health capabilities](https://github.com/Opperiesen/lanweave/issues/61)

The implementation follows the official API documentation and records the
exact API version and endpoint classes used. Authentication uses an
environment-backed API key and the documented header. Browser login, cookie
reuse, private endpoint scraping and cloud writes are out of scope.

Exit condition: the cloud adapter can perform only documented, fixture-backed
read operations and cannot reach a mutation path.

### 3. Operator and MCP surfaces

- [#62 — adapter and capability discovery in CLI, plans and read-only MCP](https://github.com/Opperiesen/lanweave/issues/62)

Exit condition: a user can inspect capabilities offline, every response is
adapter-aware, unsupported operations fail before network access, and no tool
can cause implicit adapter switching.

### 4. Evidence and release

- [#63 — cross-adapter compatibility, redaction and protected integration evidence](https://github.com/Opperiesen/lanweave/issues/63)
- [#64 — migration documentation and release gates](https://github.com/Opperiesen/lanweave/issues/64)

Exit condition: local regression, cloud fixture behavior, redaction, no-fallback
and protected read-only evidence are all reproducible and documented.

## Release gates

### `v0.3.0a1` — adapter contract

- architecture record and capability model are merged;
- local classic adapter implements the boundary;
- v1/v2 compatibility and adapter-aware target identity are tested;
- capability output is deterministic and secret-free.

### `v0.3.0b1` — cloud read-only slice

- documented Site Manager transport and API-key authentication work through
  injected fixtures;
- cloud hosts, sites, devices and supported health metrics are normalized;
- pagination, rate limits, malformed payloads and unsupported operations have
  deterministic behavior;
- no cloud write capability exists in code or MCP.

### `v0.3.0rc1` — operator and evidence freeze

- CLI, plan and MCP capability surfaces are complete;
- local and cloud redaction tests pass;
- compatibility matrix names exact controller/API versions and endpoint
  classes;
- protected local and cloud read-only evidence passes, with no mutation
  credentials in the cloud job;
- migration, recovery and unsupported-behavior documentation is complete.

### `v0.3.0` — public release

- all required CI and security checks pass;
- clean wheel and source-distribution installation checks pass;
- tag/version, checksums and provenance checks pass;
- PyPI Trusted Publishing and package attestations succeed;
- release notes state the read-only cloud limitation and all exclusions;
- all v0.3.0 issues are closed and no compatibility claim relies on fixtures
  alone when protected evidence is required.

## Security and operational invariants

- cloud API keys are loaded only from an environment-backed secret source;
- unresolved `op://` values and raw secret-manager URIs are rejected;
- API keys, cookies, authorization headers and private response bodies are
  redacted from errors, logs, fixtures and artifacts;
- cloud requests use TLS verification and bounded timeouts by default;
- retries are limited to safe idempotent reads and documented rate limits;
- local failure never triggers cloud fallback;
- cloud apply, prune and write-capable MCP remain impossible in v0.3.0;
- protected integration is manual-only and cannot execute untrusted PR code;
- reports contain versions, endpoint classes and outcomes, not topology or
  credentials.

## Explicit non-goals

- cloud configuration management or mutation;
- undocumented private UniFi endpoints;
- full parity between Site Manager and local Network APIs;
- firewall, DNS, NAT, VPN or other new resource families;
- device adoption, restart, firmware or other high-impact mutations;
- automatic controller, account or cloud discovery;
- hosted relay, telemetry or multi-tenant service;
- write-capable MCP tools.

## Definition of done

The release is complete only when implementation, focused tests, sanitized
fixtures, compatibility documentation, migration notes, redaction checks,
protected read-only evidence and reproducible release artifacts agree on the
same supported surface.
