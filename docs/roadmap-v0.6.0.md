# Lanweave v0.6.0 roadmap

Lanweave v0.6.0 is the completed release after the stable firewall resource
family. It adds only local NAT and port-forwarding resources. VPN remains an
independent v0.7.0 release with a separate secret and route safety model.

The public release is available as the [GitHub
Release](https://github.com/Opperiesen/lanweave/releases/tag/v0.6.0) and on
[PyPI](https://pypi.org/project/lanweave/0.6.0/). Its protected controller
evidence passed in [workflow run
31907918542](https://github.com/Opperiesen/lanweave/actions/runs/31907918542),
and the package, provenance and publication gates passed in [release workflow
31908100009](https://github.com/Opperiesen/lanweave/actions/runs/31908100009).

The release builds on the v0.4 resource lifecycle, the v0.5 firewall safety
analysis, explicit profile selection, capability reporting and manual recovery
semantics. It must preserve the read-only MCP boundary and all existing
network, WLAN, DNS and firewall behavior.

The frozen field-level contract is documented in [nat.md](nat.md). Controller
payload conversion and live endpoint semantics are implemented only for the
session-authenticated local-classic subset described by the work breakdown and
compatibility evidence below.

## Product outcome

At the end of v0.6.0 an operator can:

- read supported local NAT and port-forwarding mappings;
- export portable state without controller IDs, credentials or raw payloads;
- declare public interfaces, source scopes, private endpoints, protocols and
  port ranges;
- inspect deterministic exposure, conflict, overlap and dependency analysis;
- see which private service becomes reachable from which boundary;
- apply supported changes only after explicit plan review, confirmation and
  risk acknowledgement;
- prune only explicitly managed user-origin mappings;
- recover from timeout, partial or ambiguous operations through a fresh read and
  reviewed plan;
- discover NAT capabilities through the CLI while keeping MCP read-only.

## Why NAT is next

Firewall work established ordered policy, ownership protection and exposure
warnings. NAT is the next useful resource family, but it creates a direct
reachability path from a public or inter-zone boundary to a private service.
The release therefore treats exposure analysis and conflict detection as
first-class product behavior, before any mutation endpoint is implemented.

## Locked scope

### Included

- the local-classic adapter and explicit controller/site/profile selection;
- controller/API versions and endpoint families proven by sanitized fixtures;
- supported local port-forwarding mappings with public interface, source
  scope, private endpoint, protocol and port ranges;
- normalized inventory, secret-free export, validation and deterministic plan;
- explicit apply and opt-in prune through the existing safety boundary;
- stable identities, protected ownership and dependency-aware phases;
- warnings for WAN exposure, broad sources, privileged ports and conflicts;
- separately authorized controller evidence and independent release gates.

### Excluded

- Site Manager cloud NAT mutations or undocumented UI-only endpoints;
- automatic controller/API-version discovery;
- implicit source expansion, port translation or hairpin assumptions;
- deletion of system, default or unknown-origin mappings;
- automatic rollback or transaction emulation;
- VPN, device actions, firmware changes and write-capable MCP tools;
- controller-wide rewrites when exact semantics cannot be normalized.

The release claim follows the tested controller matrix. A UI feature or an
undocumented response is not support evidence.

## Contract decisions

### Mapping identity and normalization

The desired state must describe a mapping independently of controller IDs and
array positions:

- public interface and source scope are explicit;
- private endpoint, protocol and public/private port ranges are normalized;
- supported mapping types and zone boundaries are enumerated;
- controller-generated IDs remain inventory metadata, never portable identity;
- duplicate mappings and ambiguous translations fail before planning.

### Exposure and conflict analysis

Plans must identify changes that can alter reachability:

- Internet-facing or inter-zone exposure;
- broad source ranges or unrestricted sources;
- privileged destination ports;
- duplicate public bindings and overlapping ranges;
- private endpoint collisions and unsupported translations;
- hairpin or firewall dependency ambiguity;
- changes whose effect cannot be proven from the supported API surface.

Each warning names the affected boundary, mapping and private service. A
warning is visible before confirmation and cannot be silently downgraded to a
normal update.

### Ownership and prune

Only user-managed mappings with a confirmed ownership origin may be pruned.
System/default and unknown-origin mappings remain protected. When the classic
endpoint omits origin metadata, a successful create is treated as managed only
inside the current client session; a later client returns to the unknown-origin
guard. Every planned delete is rendered explicitly and requires the existing
separate prune confirmation.

### Capability boundary

The adapter reports NAT read, export, plan, apply and prune support
independently. API-key, session and unsupported paths must not be inferred from
one another. No cloud fallback is allowed and no write-capable MCP tool is
added.

### Recovery

The controller API is not assumed to be transactional. A failed operation must
report the sanitized target, resource identity, operation, phase, confirmed
operations, uncertain operation and not-started operations. It must not expose
credentials, raw payloads or private topology. Recovery always begins with a
fresh inventory read and a newly reviewed plan.

## Work breakdown

The GitHub parent epic is
[#18 — add NAT and port-forwarding resources safely](https://github.com/Opperiesen/lanweave/issues/18).
The six child issues below are all assigned to the v0.6.0 milestone and are
executed in order.

### 1. Contract foundation

[#97 — define the v0.6.0 NAT and port-forwarding contract](https://github.com/Opperiesen/lanweave/issues/97)

Freeze mapping identities, normalized state, vendor payload boundaries,
exposure semantics, conflict invariants, ownership, capabilities and recovery
rules.

Exit condition: implementation can proceed without inventing a second resource
model or weakening the v0.5 safety boundary.

### 2. Inventory, export and compatibility

[#98 — add NAT inventory, export and versioned controller fixtures](https://github.com/Opperiesen/lanweave/issues/98)

Cover normalized reads, secret-free export, the non-paginated classic response
envelope, malformed and unsupported responses, protected origins and exact
controller/API evidence.

Exit condition: the supported NAT response shape is stable and fixture-backed.

### 3. Validation and deterministic planning

[#99 — add deterministic NAT validation and exposure/conflict planning](https://github.com/Opperiesen/lanweave/issues/99)

Implement type-aware validation, stable identities, conflict and overlap
analysis, exposure warnings, firewall dependency checks, no-op behavior and
fail-closed prune planning.

Exit condition: identical inputs produce byte-stable plans and unsafe state
fails or warns before mutation.

### 4. Apply, prune and recovery

[#100 — add controlled NAT apply, prune and recovery semantics](https://github.com/Opperiesen/lanweave/issues/100)

Implement the supported local-session writes, explicit warnings and
confirmations, dependency-safe ordering, protected prune, partial-failure
reporting and the separate authorized NAT controller lifecycle.

Exit condition: a designated controller demonstrates a safe NAT lifecycle and a
documented fresh-plan recovery path.

### 5. CLI, capabilities and read-only MCP

[#101 — expose NAT through the existing CLI, capabilities and read-only MCP](https://github.com/Opperiesen/lanweave/issues/101)

Thread NAT state through validate, export, plan, apply and capabilities. Keep
MCP read-only and ensure every surface agrees on the selected target and
capability matrix.

Exit condition: an operator can discover, export, validate and plan NAT state
without a second mutation path.

### 6. Evidence, documentation and release

[#102 — complete v0.6.0 NAT evidence, documentation and release gates](https://github.com/Opperiesen/lanweave/issues/102)

Update schemas, examples, migration, compatibility, recovery, security,
changelog and release notes. Add the offline evidence verifier, the dedicated
read-only and NAT mutation workflow gates, and verify package, checksums,
provenance, PyPI and GitHub publication.

Exit condition: the published package and documentation describe the same
tested NAT surface, independently of VPN.

## Execution order and PR slicing

The intended order is:

1. #97 contract and mapping semantics;
2. #98 inventory, export and fixtures;
3. #99 validation, exposure analysis and deterministic plan;
4. #100 apply, prune and recovery;
5. #101 CLI, capabilities and read-only MCP;
6. #102 evidence, documentation and release.

Each issue may result in several focused PRs. Every PR must use the Opperiesen
GitHub identity, contain no commit trailers or co-authored identities, and
pass the repository policy before merge.

## Release gates

### v0.6.0a1 — contract and read foundation

- #97 is merged;
- mapping schemas, examples and negative cases exist;
- offline validation rejects unknown, malformed and ambiguous mappings;
- no new mutation path is exposed.

### v0.6.0b1 — usable read and plan surface

- #98, #99 and #101 are merged;
- read, export, validate, plan and capability behavior is complete;
- exposure, conflict, ownership, redaction and warning tests pass;
- existing v0.5 behavior remains green.

### v0.6.0rc1 — controlled mutation and evidence freeze

- #100 is merged;
- protected read-only and separately authorized NAT mutation evidence passes;
- the NAT lifecycle job is session-only, uses a disabled `lanweave-ci-*`
  mapping and leaves no test resource behind;
- timeout, partial failure, protected prune and fresh-plan recovery are
  documented and tested;
- only release-blocking fixes remain.

### v0.6.0 — public release

- #102 is complete and every v0.6.0 child issue is closed;
- full unit, integration, security, dependency and packaging checks pass;
- wheel and source distribution install cleanly;
- annotated tag and project version match exactly;
- GitHub assets, checksums, provenance, PyPI publication and attestations
  verify from a fresh checkout;
- the v0.6.0 milestone is closed and the v0.7.0 VPN milestone remains outside
  the gate.

All release-gate conditions are satisfied by the published tag v0.6.0. The
milestone is closed with the epic and all six child issues completed.

## Definition of done

The release is complete only when implementation, focused tests, sanitized
fixtures, protected controller evidence, compatibility notes, recovery
documentation, release metadata and published artifacts describe the same NAT
surface. A passing unit test alone is not a release gate.
