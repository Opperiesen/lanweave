# Lanweave v0.5.0 roadmap

Lanweave v0.5.0 is the next release after the stable DNS resource family. It
adds only the local firewall resource family. NAT and VPN are separate releases
with separate milestones and release gates because their safety models and
controller semantics are materially different.

The release builds on the v0.4 resource lifecycle, dependency graph,
capability matrix, explicit confirmations and manual recovery semantics. It
must preserve the read-only MCP boundary and the existing local DNS, network
and WLAN behavior.

## Product outcome

At the end of v0.5.0 an operator can:

- read and export supported local firewall zones, groups and ordered rules;
- declare portable firewall state without controller IDs or raw payloads;
- validate references, protocols, ports, directions and actions locally;
- inspect deterministic rule-order, dependency, shadowing and exposure changes;
- apply supported changes only through the existing plan and confirmation
  boundary;
- prune only explicitly managed user-origin resources;
- recover from timeout, partial or ambiguous operations through a fresh read and
  reviewed plan;
- discover firewall capabilities through the CLI while keeping MCP read-only.

## Why firewall is next

DNS established the reusable lifecycle without changing traffic policy. Firewall
is the next meaningful operator capability, but it carries a higher blast
radius: first-match ordering, implicit defaults, cross-zone traffic and broad
rules can change connectivity or isolation immediately. The release therefore
freezes the safety model before endpoint implementation and treats ordering as
part of resource identity, not as incidental controller array position.

## Locked scope

### Included

- the local-classic adapter and explicit controller/site/profile selection;
- the controller/API versions and endpoint families proven by fixtures;
- supported zones or network references, address groups and port groups;
- ordered firewall rules with explicit source, destination, protocol, ports,
  direction and action;
- read, export, validate, plan, apply and explicit prune;
- stable identities, dependency-aware phases and protected ownership;
- warnings and confirmations for broad, shadowing or Internet-impacting rules;
- sanitized read-only evidence and separately authorized mutation evidence;
- independent v0.5.0 packaging, provenance and publication gates.

### Excluded

- Site Manager cloud firewall mutations;
- undocumented UI-only endpoints or automatic API-version discovery;
- implicit rule reordering or index-based identity;
- deletion of system, default or unknown-origin rules;
- automatic rollback or transaction emulation;
- NAT, port forwarding, VPN, device actions and write-capable MCP tools;
- controller-wide policy rewrites when exact semantics cannot be normalized.

The release claim follows the tested controller matrix. A UI feature or an
undocumented response is not support evidence.

## Contract decisions

### Resource model and ordering

The desired state must distinguish reusable references from ordered policy:

- zones or network boundaries are explicit references;
- address and port groups have stable normalized identities;
- rules carry an explicit order key and are compared independently of
  controller-generated array positions;
- dependencies are visible in the plan and determine mutation phases;
- duplicate identities, dangling references, cycles and unsupported combinations
  fail before mutation.

Rule order is security behavior. A reorder is therefore a first-class planned
change and never an incidental side effect of sorting or pagination.

### Ownership and prune

Only user-managed resources with a confirmed ownership origin may be pruned.
System/default and unknown-origin resources remain protected. Every planned
delete is rendered explicitly and requires the existing separate prune
confirmation.

### Safety analysis

Plans must identify changes that can alter reachability or isolation:

- broad sources or destinations;
- Internet-facing or inter-zone scope;
- privileged ports;
- shadowed or unreachable rules;
- conflicting group or reference changes;
- rule moves that change first-match behavior.

These cases must produce a visible warning before the confirmation boundary;
they must not be silently downgraded to ordinary updates.

### Capability boundary

The adapter must report firewall read, export, plan, apply and prune support
independently. API-key, session and unsupported paths must not be inferred from
one another. No cloud fallback is allowed and no write-capable MCP tool is
added.

### Recovery

The controller API is not assumed to be transactional. A failed operation must
report the sanitized target, resource identity, operation, phase, confirmed
operations, uncertain operation and not-started operations. It must not expose
credentials, raw payloads or topology. Recovery always begins with a fresh
inventory read and a newly reviewed plan.

## Work breakdown

The GitHub parent epic is
[#15 — add firewall resources with dependency-aware planning](https://github.com/Opperiesen/lanweave/issues/15).
The issues below are all assigned to the v0.5.0 milestone and are executed in
order.

### 1. Contract and ordering foundation

[#86 — define the v0.5.0 firewall resource contract and ordering model](https://github.com/Opperiesen/lanweave/issues/86)

Freeze resource identities, normalized state, vendor payload boundaries,
ordered-rule semantics, dependency edges, ownership, capability and recovery
invariants.

Exit condition: implementation can proceed without inventing a second resource
model or weakening the v0.4 contract.

### 2. Inventory, export and compatibility

[#87 — add firewall inventory, export and versioned controller fixtures](https://github.com/Opperiesen/lanweave/issues/87)

Cover normalized reads, secret-free export, bounded pagination, malformed
responses, unsupported variants, protected origins and exact controller/API
evidence.

Exit condition: the supported firewall response shape is stable and
fixture-backed.

### 3. Validation and deterministic planning

[#88 — add deterministic firewall validation and dependency-aware planning](https://github.com/Opperiesen/lanweave/issues/88)

Implement type-aware validation, stable ordering, dependency phases, conflict
and shadowing analysis, broad-rule warnings, no-op behavior and fail-closed
prune planning.

Exit condition: identical inputs produce byte-stable plans and unsafe state
fails before mutation.

### 4. Apply, prune and recovery

[#89 — add controlled firewall apply, prune and recovery semantics](https://github.com/Opperiesen/lanweave/issues/89)

Implement supported local writes, explicit warnings and confirmations,
dependency-safe ordering, protected prune, partial-failure reporting and
authorized controller evidence.

Exit condition: a designated controller demonstrates a safe firewall lifecycle
and a documented fresh-plan recovery path.

### 5. CLI, capabilities and read-only MCP

[#90 — expose firewall through the existing CLI, capabilities and read-only MCP surfaces](https://github.com/Opperiesen/lanweave/issues/90)

Thread firewall state through validate, export, plan, apply and capabilities.
Keep MCP read-only and ensure all surfaces agree on the selected target and
capability matrix.

Exit condition: an operator can discover, export, validate and plan firewall
state without a second mutation path.

### 6. Evidence, documentation and release

[#91 — complete v0.5.0 firewall evidence, documentation and release gates](https://github.com/Opperiesen/lanweave/issues/91)

Update examples, migration, compatibility, recovery, security notes, changelog
and release notes. Add reproducible evidence checks and verify package,
checksums, provenance, PyPI and GitHub publication.

Exit condition: the published package and documentation describe the same
tested firewall surface, independently of NAT and VPN.

## Execution order and PR slicing

The intended order is:

1. #86 contract and ordering;
2. #87 inventory, export and fixtures;
3. #88 validation and deterministic plan;
4. #89 apply, prune and recovery;
5. #90 CLI, capabilities and read-only MCP;
6. #91 evidence, documentation and release.

Each issue may result in several focused PRs. Every PR must use the
Opperiesen GitHub identity, contain no commit trailers or co-authored
identities, and pass the repository policy before merge.

## Release gates

### v0.5.0a1 — contract and read foundation

- #86 is merged;
- schemas, examples and ordering fixtures exist;
- offline validation rejects unknown, malformed and ambiguous firewall state;
- no new mutation path is exposed.

### v0.5.0b1 — usable read and plan surface

- #87, #88 and #90 are merged;
- read, export, validate, plan and capability behavior is complete;
- rule order, dependency, ownership, redaction and warning tests pass;
- existing v0.4 behavior remains green.

### v0.5.0rc1 — controlled mutation and evidence freeze

- #89 is merged;
- protected read-only and separately authorized mutation evidence passes;
- timeout, partial failure, protected prune and fresh-plan recovery are
  documented and tested;
- only release-blocking fixes remain.

### v0.5.0 — public release

- #91 is complete and every v0.5.0 child issue is closed;
- full unit, integration, security, dependency and packaging checks pass;
- wheel and source distribution install cleanly;
- the annotated tag and project version match exactly;
- GitHub assets, checksums, provenance, PyPI publication and attestations
  verify from a fresh checkout;
- the v0.5.0 milestone is closed and the next milestone remains untouched.

## Future sequence

The next independent releases are already aligned:

- [v0.6.0 — NAT and port forwarding](https://github.com/Opperiesen/lanweave/milestone/8),
  tracked by [#18](https://github.com/Opperiesen/lanweave/issues/18);
- [v0.7.0 — VPN resources](https://github.com/Opperiesen/lanweave/milestone/9),
  tracked by [#19](https://github.com/Opperiesen/lanweave/issues/19).

Neither family is part of v0.5.0 or may be pulled into its release gate.

## Definition of done

The release is complete only when implementation, focused tests, sanitized
fixtures, protected controller evidence, compatibility notes, recovery
documentation, release metadata and published artifacts describe the same
firewall surface. A passing unit test alone is not a release gate.
