# Changelog

## Unreleased

- add the read-only local VPN contract for servers, site-to-site tunnels,
  connected peers and route dependency validation;
- add secret-free VPN export, plan observations, CLI/MCP inventory and
  capability-aware boundaries without accepting private keys or profiles;
- publish the v0.7.0 migration, compatibility, recovery and fixture evidence
  documentation.

## 0.6.0 — 2026-08-15

- add the portable local NAT and port-forwarding contract with exposure and
  conflict analysis;
- add session-only local-classic inventory, secret-free export, deterministic
  planning, controlled apply, protected prune and sanitized recovery reports;
- expose NAT through CLI validation, capabilities and read-only MCP responses;
- publish the NAT compatibility, migration, recovery and protected evidence
  boundary independently from the v0.7 VPN roadmap.

## 0.5.0 — 2026-08-15

- add the portable local firewall contract with zones, address groups, port
  groups and ordered rules;
- add fixture-backed inventory/export, deterministic planning, dependency-safe
  apply, protected prune and sanitized recovery reporting;
- keep firewall writes local API-key-only, MCP read-only and mutation evidence
  opt-in on disabled, prefixed test rules;
- publish protected read-only and authorized firewall lifecycle evidence for
  UniFi Network 10.5.67 on UniFi OS 5.1.19.

## 0.4.0 — 2026-08-15

- add the portable local DNS resource family for `A`, `AAAA` and `CNAME`;
- normalize official Integration API DNS policies with ownership-aware export;
- add deterministic DNS validation, planning, apply, prune and recovery;
- support API-key DNS policy mutations without opening generic API-key writes;
- expose DNS through existing CLI, capability and read-only MCP responses;
- publish fixture-backed and authorized controller evidence with migration and
  compatibility documentation.

## 0.3.0 — 2026-08-15

- introduce explicit local and Site Manager adapter boundaries with
  deterministic capability documents;
- add offline CLI capability discovery and MCP contract v3;
- add fixture-backed, read-only Site Manager hosts, sites, devices and health
  inventory with protected integration evidence gates;
- document v0.3 migration, compatibility limits and release verification.

## 0.2.0 — 2026-08-15

- define the v0.2.0 local profile shape, selector precedence and version-1
  migration contract;
- add the reusable version-1/version-2 local target resolver;
- validate version-2 local profile configurations and add offline `profiles`
  list and validation commands.
- thread explicit profile and configuration selectors through controller-facing
  CLI commands, with sanitized target announcements and early conflict checks.
- add non-secret target identity to v2 plans and reject mismatched plan targets
  before any mutation.
- version the read-only MCP surface as v2, require explicit profile selection
  for profile-backed targets and expose sanitized target envelopes.

## 0.1.0 — 2026-08-15

- publish the first stable local-first Lanweave package to PyPI;
- enable PyPI Trusted Publishing and PEP 740 attestations;
- document PyPI installation, checksum verification and provenance verification;
- mark the frozen CLI, configuration, plan JSON and read-only MCP contracts as
  stable for the `0.1.x` line.

## 0.1.0rc1 — 2026-08-15

- add a protected release workflow that runs the complete required CI;
- verify annotated tag identity, project version, wheel and source distribution;
- test both artifacts in clean environments before publication;
- publish checksums and a signed build-provenance bundle with GitHub Releases;
- reject forbidden commit trailers and generated-agent signatures in CI.

## 0.1.0b1 — 2026-08-15

- freeze configuration schema version 1 and publish its machine-readable
  contract;
- freeze CLI commands, options and exit-code behavior;
- version and document the redacted plan JSON format;
- document the six read-only MCP tools, parameters, return values and stable
  error codes;
- add explicit migration and deprecation rules for future breaking changes;
- expand smoke and contract tests across configuration, CLI, plan JSON and MCP.

## 0.1.0a2 — 2026-08-15

- enforce formatting and locked dependency/security audits in CI;
- exercise the optional MCP extra on the supported Python boundary versions;
- pin GitHub Actions to reviewed commit SHAs and disable checkout credential
  persistence;
- add a manually triggered, protected controller integration workflow with
  redacted compatibility reports;
- separate live read-only probes from an explicitly authorized mutation suite;
- publish designated-controller read-only compatibility evidence;
- route manual controller integration jobs through a dedicated LAN runner;
- support read-only UniFi v1 Integration API access with API keys;
- use a separate scoped session account for the authorized mutation suite;
- publish successful create/update/delete compatibility evidence on the
  designated controller;
- report partial apply state without payload or credential leakage and document
  deterministic manual recovery semantics.

## 0.1.0a1 — 2026-08-15

- initial public Lanweave package and Apache-2.0 project foundation;
- declarative networks and WLANs with validation and environment-backed
  secrets;
- deterministic redacted plan, explicit apply and opt-in prune;
- secret-free export, redacted local backup, health and client views;
- optional read-only MCP server over stdio;
- simulated controller tests and CI checks.
