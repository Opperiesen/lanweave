# Roadmap v1.0.0 — stable local network control plane

Lanweave v1.0.0 freezes the local-first product contract. It is a stability
release, not an endpoint-count release: the supported surface is the one that
has a documented capability boundary, a recovery story and reproducible
evidence.

## Product promise

An operator can install Lanweave, declare local network intent, inspect a
deterministic redacted plan, apply it only after explicit confirmation, audit
the live state, verify post-apply convergence and consume the same read-only
observations through MCP without following implementation details.

The CLI remains the primary interface. MCP is optional and read-only. Cloud
Site Manager support remains a documented read-only inventory adapter.

## Frozen public surfaces

The v1.0 compatibility promise covers:

- configuration schema versions 1 and 2;
- plan JSON format v1;
- adapter capability format v1;
- audit result format v1;
- convergence result format v1;
- read-only MCP contract v3;
- the exported Python API listed in [`api.md`](api.md);
- CLI command names, stable options, exit codes and stdout/stderr rules.

An additive v1.x field must preserve the meaning of existing fields. Removing
or renaming a field, changing an error code, changing a mutation boundary or
adding a write-capable MCP operation requires a new contract decision and a
migration note.

## Supported resource boundary

| Family | v1.0 capability |
| --- | --- |
| Networks and WLANs | Local classic session read/export/plan/apply/prune; API-key read/export/plan |
| DNS policies | Local Integration API read/export/plan/apply/prune |
| Firewall | Local Integration API read/export/plan/apply/prune for the documented subset |
| NAT / port forwarding | Local classic session read/export/plan/apply/prune for the documented IPv4 subset |
| VPN | Local API-key read/export/plan overview only; no keys, profiles, route writes or mutations |
| Site Manager | Cloud hosts, sites, devices and derived health read-only inventory |
| MCP | Nine read-only tools; no apply, create, update, delete or prune |

Unsupported or unverified behavior is reported as `unknown` or `unsupported`;
it is never silently treated as compliant.

## Release gates

The v1.0.0 tag is allowed only when all of the following are true:

1. the public API, schemas, CLI and MCP contract snapshots pass;
2. the v0.9.0 migration and v1.x deprecation policy are published;
3. the live CLI, apply/convergence and MCP evidence runs pass on the
   designated controller;
4. VPN live evidence is either recorded or its limitation is explicitly
   represented in the compatibility matrix;
5. a second exact controller/API combination is tested or the compatibility
   claim is narrowed to the designated combination;
6. onboarding, operator recovery, security and examples are verified from a
   clean install;
7. dependency, workflow, secret-boundary and commit-policy checks pass;
8. the protected release workflow verifies wheel, sdist, checksums, clean
   installs, provenance, PyPI attestations and the public GitHub release.

The detailed execution is tracked in the v1.0.0 milestone and its audit
issues: [#117](https://github.com/Opperiesen/lanweave/issues/117),
[#136](https://github.com/Opperiesen/lanweave/issues/136),
[#140](https://github.com/Opperiesen/lanweave/issues/140),
[#143](https://github.com/Opperiesen/lanweave/issues/143),
[#145](https://github.com/Opperiesen/lanweave/issues/145),
[#146](https://github.com/Opperiesen/lanweave/issues/146),
[#147](https://github.com/Opperiesen/lanweave/issues/147) and
[#148](https://github.com/Opperiesen/lanweave/issues/148).

## Explicit non-goals

v1.0.0 does not promise every UniFi endpoint, device adoption or restart,
firmware workflows, cloud mutations, generic API-key writes, hosted telemetry,
automatic rollback or a write-capable MCP server.
