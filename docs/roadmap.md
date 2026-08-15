# Roadmap

Lanweave is a local-first, declarative GitOps tool for UniFi Network
controllers. Its release strategy favors tested operator value, explicit
safety boundaries and a small number of well-supported resource families over
endpoint count.

The CLI is the primary interface. MCP is an optional read-only adapter and
must never bypass the plan safety boundary.

## Version policy

- `alpha` (`aN`): contracts and behavior may still change;
- `beta` (`bN`): feature scope is frozen and compatibility work is the focus;
- `rcN`: only release-blocking fixes are accepted;
- stable patch releases contain fixes and documentation only;
- a new minor release adds a meaningful capability or resource family;
- a major release is reserved for a breaking public contract.

The first stable local-first package is planned as `v0.1.0`. `v1.0.0` means
that the CLI, configuration, plan format and read-only MCP contract are ready
for long-term compatibility; it does not require every UniFi endpoint to be
implemented.

## Release train

| Release | Objective | Milestone | Exit condition |
| --- | --- | --- | --- |
| `v0.1.0a1` | First public alpha | released | Simulated-controller product slice is available |
| `v0.1.0a2` | Real-controller reliability | [milestone](https://github.com/Opperiesen/lanweave/milestone/1) | Integration evidence, compatibility policy and recovery semantics are published |
| `v0.1.0b1` | Core contract freeze | [milestone](https://github.com/Opperiesen/lanweave/milestone/2) | Configuration, CLI, plan JSON and read-only MCP contracts are documented and tested |
| `v0.1.0rc1` | Release rehearsal | [milestone](https://github.com/Opperiesen/lanweave/milestone/3) | Protected release workflow builds and verifies installable artifacts |
| `v0.1.0` | Stable local-first core | [milestone](https://github.com/Opperiesen/lanweave/milestone/3) | PyPI publication, provenance and compatibility matrix are complete |
| `v0.2.0` | Multi-controller profiles | [milestone](https://github.com/Opperiesen/lanweave/milestone/4) | Explicit multi-site targeting works without breaking version-1 configs |
| `v0.3.0` | Adapter architecture | [milestone](https://github.com/Opperiesen/lanweave/milestone/5) | Local and optional cloud adapters expose explicit capabilities |
| `v0.4.0+` | Additional resource families | [milestone](https://github.com/Opperiesen/lanweave/milestone/6) | Each family has fixtures, dependency ordering and recovery semantics |

## Current release — `v0.1.0a2`

The first alpha currently provides:

- local classic UniFi Network API access;
- API-key and session authentication;
- declarative networks and WLANs;
- strict configuration validation;
- secret-free export;
- deterministic plan generation;
- explicit, confirmed apply operations;
- opt-in pruning with a separate confirmation;
- redacted local backups;
- health, device and client views;
- six read-only MCP tools;
- public CI, security policy and contribution workflow;
- exact controller compatibility evidence with separate read-only and
  authorized mutation paths;
- dependency-safe partial apply reporting and manual recovery semantics;
- a documented boundary between confirmed, uncertain and not-started state.

The supported API surface is documented in
[compatibility.md](compatibility.md), and partial apply behavior is documented
in [recovery.md](recovery.md). The release is deliberately limited to networks,
WLANs and read-oriented operational views.

## `v0.1.0b1` — core contract freeze

Tracked work:

- [#13 — stabilize the v1 core contracts](https://github.com/Opperiesen/lanweave/issues/13).

The beta freezes:

- configuration schema version 1;
- CLI commands, options and exit codes;
- machine-readable plan JSON;
- secret-redaction guarantees;
- the six read-only MCP tools;
- migration and deprecation rules.

This milestone does not include cloud support, multi-site profiles, new
resource families or write-capable MCP tools.

## `v0.1.0rc1` and `v0.1.0` — stable local-first core

Release engineering is tracked separately:

- [#17 — protected release workflow and artifact provenance](https://github.com/Opperiesen/lanweave/issues/17);
- [#2 — publish the first stable package to PyPI](https://github.com/Opperiesen/lanweave/issues/2).

The release workflow must:

- build wheel and sdist from a protected tag;
- verify that the tag and project versions match;
- run the complete required CI;
- test installation in a clean environment;
- publish GitHub Release assets and checksums;
- use PyPI Trusted Publishing rather than a long-lived token;
- publish provenance or artifact attestations;
- keep MCP as an optional dependency.

`v0.1.0` is the stable local-first core. It does not promise cloud support,
multi-site management, firewall, DNS, NAT, VPN or device mutation workflows.

## `v0.2.0` — multi-controller and multi-site profiles

Tracked work:

- [#3 — explicit multi-controller and multi-site profiles](https://github.com/Opperiesen/lanweave/issues/3).

The profile model must:

- keep credentials in the environment or an approved secret provider;
- make controller and site selection explicit;
- identify the target in plans, JSON output and MCP responses;
- define precedence between CLI, configuration and environment;
- preserve version-1 single-controller files;
- reject incomplete or ambiguous profiles;
- prevent cross-controller and cross-site apply mistakes.

## `v0.3.0` — adapter capability boundary

The architecture is split before cloud implementation:

- [#14 — adapter capability boundary](https://github.com/Opperiesen/lanweave/issues/14);
- [#4 — official UniFi cloud API adapter](https://github.com/Opperiesen/lanweave/issues/4).

The local classic adapter remains the default and must not regress. The cloud
adapter is opt-in, independently tested and explicit about unsupported
resources. A local-to-cloud automatic fallback is not allowed.

Each adapter must expose capabilities for:

- authentication;
- target selection;
- supported resources;
- read, create, update and delete operations;
- endpoint or payload differences;
- known compatibility limits.

MCP remains read-only and must expose the selected adapter and target.

## `v0.4.0+` — resource families one at a time

Every resource family follows the same progression:

1. read and inventory;
2. portable export;
3. validation and deterministic planning;
4. controlled apply;
5. explicit prune and recovery behavior.

The backlog is intentionally split:

- [#15 — firewall resources](https://github.com/Opperiesen/lanweave/issues/15);
- [#16 — DNS resources](https://github.com/Opperiesen/lanweave/issues/16);
- [#18 — NAT and port forwarding](https://github.com/Opperiesen/lanweave/issues/18);
- [#19 — VPN resources](https://github.com/Opperiesen/lanweave/issues/19).

Firewall, NAT and VPN writes require stronger validation than the current
network/WLAN workflow because a bad plan can expose services or disconnect the
operator. They must not be bundled into a single large release.

Device adoption, restart, firmware and other high-impact mutations remain
post-`v1.0.0` candidates unless an independent safety model is approved.

## MCP roadmap

MCP is deliberately conservative:

- `v0.1.0`: stable read-only health, device, client, export, validation and
  planning tools;
- `v0.2.0`: explicit profile and target identity in every response;
- `v0.3.0`: adapter and capability discovery;
- `v1.0.0`: stable tool names, parameters, errors and redaction behavior.

Write-capable MCP tools are not on this roadmap. They would require a separate
approval, identity, audit and prompt-injection threat model.

## Definition of done for every release

A release is not complete when the code merely exists. It needs:

- implementation and focused tests;
- sanitized fixtures for controller-specific behavior;
- documentation and compatibility notes;
- changelog entry and version update;
- green unit, integration and security checks appropriate to its scope;
- no secrets in logs, plans, fixtures or artifacts;
- a reproducible build;
- a clear rollback or recovery story for mutations;
- an explicit list of unsupported behavior.

The detailed work and acceptance criteria live in the
[GitHub roadmap issues](https://github.com/Opperiesen/lanweave/issues).

## Non-goals

- hosted relay or telemetry service;
- replacement for the UniFi administration UI;
- implicit controller or cloud discovery;
- write-capable MCP without an independent approval model;
- publishing private household topology, exports or operational history;
- implementing every UniFi endpoint regardless of safety and compatibility.
