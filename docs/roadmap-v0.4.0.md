# Lanweave v0.4.0 roadmap

Lanweave v0.4.0 is the first release after the adapter and cloud-read-only
work. It introduces one additional declarative resource family: local DNS
records. The release is intentionally narrow. Its value is not the number of
endpoints covered, but a reusable lifecycle that is safe enough to extend to
firewall, NAT and VPN later.

The current stable release remains v0.3.0 until the implementation and release
gates below are complete.

## Product outcome

At the end of v0.4.0 an operator can:

- declare local DNS records in a portable v1 or v2 configuration;
- use A, AAAA and CNAME records with strict type-aware validation;
- read and export supported records without credentials or controller metadata;
- inspect the selected adapter, target and DNS operation capabilities before
  mutation;
- review a deterministic plan with stable identities and explicit deletes;
- apply create and update operations only through the existing confirmation
  boundary;
- prune only explicitly managed, user-origin records after a separate DELETE
  confirmation;
- recover from an ambiguous or partial operation by reading the controller and
  reviewing a fresh plan;
- keep the MCP adapter read-only, with DNS available only through existing
  export and plan responses where the selected adapter supports it.

## Why DNS first

DNS is useful to almost every local network, but its changes do not normally
alter routing or traffic policy. It is therefore a better first additional
family than firewall, NAT or VPN. It also exercises the difficult parts of
Lanweave's product contract: vendor normalization, ownership, deterministic
identity, capabilities, versioned schemas, explicit prune and recovery.

The release must not become a generic resource framework project. The
abstraction is complete only when it directly serves DNS and leaves a small,
clear extension point for the next family.

## Locked scope

### Included

- the explicit `local-classic` adapter and local controller/site/profile
  selection;
- one managed value per normalized `name + type` identity;
- A and AAAA records using an IP address;
- CNAME records using a canonical DNS target;
- enabled state and a bounded positive TTL;
- read, export, validate, plan, apply and explicit prune;
- exact controller/API versions and endpoint families backed by fixtures;
- separate capability declarations for API-key and session authentication;
- additive configuration evolution when v1/v2 documents and their meanings can
  remain valid;
- the existing plan format v1 when the DNS extension preserves its contract;
- sanitized read-only evidence and separately authorized mutation evidence.

### Excluded

- Site Manager cloud DNS or any cloud mutation;
- write-capable MCP tools;
- forwarding policies and split-horizon or network-scoped DNS;
- MX, TXT, SRV and PTR records in the first DNS model;
- automatic discovery of controllers, accounts or API versions;
- system-managed, built-in or unknown-origin record deletion;
- firewall, NAT, port forwarding, VPN and device mutation;
- automatic rollback or transaction emulation.

If the controller only exposes a record through an endpoint whose semantics
cannot be normalized and fixture-tested, that record stays excluded. The
release claim follows the tested matrix, not the existence of a UI control or
an undocumented response.

## Contract decisions

### Portable DNS model

The configuration shape is intentionally small. The exact field names and
normalization rules are frozen by the resource-contract issue before feature
implementation. The intended shape is:

```yaml
dns:
  - name: printer.home.arpa
    type: A
    address: 192.168.10.50
    ttl_seconds: 300
    enabled: true
  - name: app.home.arpa
    type: CNAME
    target: server.home.arpa
    ttl_seconds: 300
```

Names are compared case-insensitively with one documented canonical form.
Duplicate normalized identities, malformed hostnames, invalid addresses,
invalid CNAME targets and invalid TTLs fail locally. Controller metadata such as
IDs and origins is never part of the desired portable state.

### Configuration and plan compatibility

The preferred path is an additive `dns` collection in the existing v1 and v2
documents. Existing configurations must remain valid and keep the same
meaning. The plan format remains v1 if `kind: dns` can use the existing
`create`, `update`, `delete`, `changed_fields` and redaction guarantees without
changing their semantics.

If that compatibility test fails, implementation stops at the contract issue:
the new configuration or plan version, migration, rejection rules and release
notes must be designed before code is merged. Lanweave must never accept an
unknown field and silently drop it.

### Controller and authentication boundary

The exact DNS endpoint family, controller versions and authentication modes are
part of the compatibility matrix. A capability document must state, for each
mode, whether DNS supports `read`, `export`, `plan`, `apply` and `prune`.

The official UniFi Network API v10.3.58 documents DNS policies as a separate
resource with list, create, get, update and delete operations. Its examples use
the Integration API and an API key. Lanweave must still verify the endpoint,
response shape, origin metadata, pagination and mutation behavior on the
designated controller before claiming support. A session path is not inferred
from the existence of an API-key path, and no cloud fallback is allowed.

### Ownership and prune

Prune is safe only when Lanweave can distinguish user-managed records from
system-managed or unknown-origin records. Unknown origin fails closed. The
plan must show every delete, and apply retains the current separate `DELETE`
confirmation in addition to the normal apply confirmation.

### Recovery

The controller API is not assumed to be transactional. DNS failures report the
sanitized target, resource identity, operation, phase, confirmed operations,
uncertain operation and not-started operations. They do not include payloads,
responses, topology or credentials. The documented recovery path is always a
fresh read followed by a newly reviewed plan; automatic rollback is not claimed.

## Work breakdown

The GitHub milestone is tracked by
[Epic #82](https://github.com/Opperiesen/lanweave/issues/82).

### 1. Foundation

[#77 — define the v0.4 resource contract and dependency-aware lifecycle](https://github.com/Opperiesen/lanweave/issues/77)

This issue freezes:

- resource identity, normalized state and vendor payload boundaries;
- read, export, validate, plan, apply and prune lifecycle stages;
- deterministic ordering, dependency edges and cycle detection;
- capability and authentication matrices;
- additive schema/plan evolution rules;
- ownership, redaction and recovery invariants.

Exit condition: DNS code can be implemented without inventing a second model
or silently weakening a v0.3 contract.

### 2. Inventory, export and compatibility

[#16 — add DNS resources with versioned controller fixtures](https://github.com/Opperiesen/lanweave/issues/16)

This issue covers normalized reads, secret-free export, pagination, malformed
responses, unsupported record types, system-origin records and the exact
controller/API evidence. Read-only evidence is kept separate from authorized
mutation evidence.

Exit condition: the supported DNS response shape is stable and fixture-backed.

### 3. Validation and deterministic planning

[#78 — add deterministic DNS validation and planning](https://github.com/Opperiesen/lanweave/issues/78)

This issue covers type-aware validation, canonicalization, duplicate and
conflict detection, stable sorting, no-op behavior, explicit prune and
fail-closed ownership checks.

Exit condition: identical inputs and controller state produce byte-stable
plans, and every unsafe or unsupported case fails before mutation.

### 4. Apply, prune and recovery

[#79 — add controlled DNS apply, prune and recovery semantics](https://github.com/Opperiesen/lanweave/issues/79)

This issue covers supported local endpoint writes, authentication limits,
create/update-before-delete ordering, explicit confirmations, timeout handling,
partial failure reports and authorized test-controller evidence.

Exit condition: a designated test controller demonstrates safe lifecycle
behavior and a fresh-plan recovery workflow.

### 5. CLI, capabilities and read-only MCP

[#80 — expose DNS through existing CLI and capability-aware read-only MCP surfaces](https://github.com/Opperiesen/lanweave/issues/80)

The existing `validate`, `export`, `plan`, `apply` and `capabilities` commands
must agree on one selected target and one capability matrix. Existing read-only
MCP export and plan responses may carry DNS where supported. A new write tool is
not added; a DNS-specific read tool would require a separate contract decision.

Exit condition: operators can discover, export and plan DNS through the current
surfaces without a second mutation path.

### 6. Evidence, documentation and release

[#81 — complete v0.4.0 DNS evidence, documentation and release gates](https://github.com/Opperiesen/lanweave/issues/81)

This issue updates the README, compatibility matrix, recovery guide, examples,
changelog and release notes. It adds a reproducible evidence command,
sanitized reports and the final package/tag/provenance checks.

Exit condition: a fresh checkout can reproduce the documented claim and the
published artifacts match the exact release commit.

## Execution order and PR slicing

The intended order is:

1. #77 contract and lifecycle;
2. #16 inventory/export and fixtures;
3. #78 validation and deterministic plan;
4. #79 apply/prune/recovery;
5. #80 CLI, capabilities and read-only MCP;
6. #81 evidence, documentation and release.

Each issue may result in several PRs, but each PR remains one coherent unit,
uses the `Opperiesen` GitHub identity, contains no commit trailers or
co-authored identities, and passes the repository policy before merge.

## Release gates

### `v0.4.0a1` — contract and read foundation

- #77 is merged;
- schemas, examples and compatibility fixtures exist;
- offline validation rejects unknown, malformed and ambiguous DNS state;
- no new mutation path is exposed.

### `v0.4.0b1` — usable read and plan surface

- #16, #78 and #80 are merged;
- read, export, validate, plan and capability behavior is complete;
- deterministic ordering, redaction, ownership and unsupported-capability
  tests pass;
- existing v0.3 local/cloud behavior remains green.

### `v0.4.0rc1` — controlled mutation and evidence freeze

- #79 is merged;
- protected read-only and separately authorized mutation evidence passes;
- timeout, partial failure, protected prune and fresh-plan recovery are
  documented and tested;
- compatibility and migration notes match the implementation;
- only release-blocking fixes remain.

### `v0.4.0` — public release

- #81 is complete and every v0.4.0 child issue is closed;
- full unit, integration, security, dependency and packaging checks pass;
- clean wheel and source-distribution installation checks pass;
- the annotated tag and project version match exactly;
- GitHub assets, checksums, provenance, PyPI publication and attestations
  verify from a fresh checkout;
- post-release tag, asset and attestation verification is recorded.

## Design references

The decomposition borrows proven boundaries without copying another tool's
state model:

- [Official UniFi Network API v10.3.58 DNS policy documentation](https://developer.ui.com/network/v10.3.58/creatednspolicy)
  provides the resource types, TTL field and documented endpoint family;
- [ubiquiti-community/terraform-provider-unifi](https://github.com/ubiquiti-community/terraform-provider-unifi)
  demonstrates the value of resource-specific schemas, import/state identity
  and an explicit plan-before-apply workflow;
- [external-dns-unifi-webhook](https://github.com/ubiquiti-community/external-dns-unifi-webhook)
  is a useful reference for keeping DNS reconciliation focused on records
  rather than turning it into a general controller-management API.

These projects are references, not compatibility dependencies. Lanweave keeps
its local-first Python CLI, its existing plan/recovery guarantees and its
read-only MCP boundary.

## Future resource sequence

The open backlog is moved to milestone
[`v0.5.0+`](https://github.com/Opperiesen/lanweave/milestone/7):

- [#15 — firewall resources](https://github.com/Opperiesen/lanweave/issues/15);
- [#18 — NAT and port forwarding](https://github.com/Opperiesen/lanweave/issues/18);
- [#19 — VPN resources](https://github.com/Opperiesen/lanweave/issues/19).

They remain independent workstreams. Firewall ordering and policy safety should
come first, then NAT exposure analysis, then VPN dependencies and secret
handling. None is part of the v0.4.0 release claim.

## Definition of done

The release is complete only when implementation, focused tests, sanitized
fixtures, protected controller evidence, compatibility notes, recovery
documentation, release metadata and published artifacts describe the same
DNS surface. A passing unit test alone is not a release gate.
