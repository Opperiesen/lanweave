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

The first stable local-first package was `v0.1.0`. `v1.0.0` means
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
| `v0.2.0` | Multi-controller and multi-site profiles | [milestone](https://github.com/Opperiesen/lanweave/milestone/4) | Explicit local target selection works across CLI, plans and read-only MCP without breaking version-1 configs |
| `v0.3.0` | Adapter architecture and read-only cloud inventory | [milestone](https://github.com/Opperiesen/lanweave/milestone/5) | Local compatibility is preserved and the opt-in Site Manager adapter exposes documented capabilities |
| `v0.4.0` | Safe local DNS resource family | [milestone](https://github.com/Opperiesen/lanweave/milestone/6) | DNS read/export/plan/apply/prune is fixture-backed, deterministic and recoverable |
| `v0.5.0` | Safe local firewall resource family | [milestone](https://github.com/Opperiesen/lanweave/milestone/7) | Firewall ordering, exposure analysis, fixtures and protected lifecycle are independently verified |
| `v0.6.0` | Safe local NAT and port-forwarding resource family | [milestone](https://github.com/Opperiesen/lanweave/milestone/8) | NAT exposure, conflict analysis, fixtures and protected lifecycle are independently verified |
| `v0.7.0` | Safe local VPN resource family | [milestone](https://github.com/Opperiesen/lanweave/milestone/9) | VPN secrets, routes, dependencies, fixtures and read-only-first lifecycle are independently verified |
| `v0.8.0` | Drift audit and compliance reports | [milestone](https://github.com/Opperiesen/lanweave/milestone/12) | Stable audit semantics, deterministic JSON/CI exit codes and no broad mutation expansion |
| `v0.9.0` | Post-apply verification and operational hardening | [milestone](https://github.com/Opperiesen/lanweave/milestone/10) | Re-read, convergence and recovery evidence are explicit before any rollback automation |
| `v1.0.0` | Stable local network control plane | [milestone](https://github.com/Opperiesen/lanweave/milestone/11) | Public contracts, packaging, security and compatibility policy are frozen |

## `v0.2.0` — stable local-first core

The `v0.2.0` release provided:

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
- seven read-only MCP tools with explicit v3 target and capability selection;
- public CI, security policy and contribution workflow;
- exact controller compatibility evidence with separate read-only and
  authorized mutation paths;
- dependency-safe partial apply reporting and manual recovery semantics;
- a documented boundary between confirmed, uncertain and not-started state;
- frozen configuration, CLI, plan JSON and read-only MCP contracts.
- a protected release rehearsal workflow with tag/version and artifact checks;
- clean wheel and source-distribution installation checks;
- GitHub artifact checksums and signed build provenance.
- PyPI Trusted Publishing and package attestations.

The supported API surface is documented in
[compatibility.md](compatibility.md), and partial apply behavior is documented
in [recovery.md](recovery.md). The release is deliberately limited to networks,
WLANs and read-oriented operational views. The complete frozen surface is in
[contracts.md](contracts.md).

This release does not include cloud resource mutations, firewall, NAT, VPN or
write-capable MCP tools.

## Historical release — `v0.5.0`

`v0.5.0` was the stable release that provided the complete local-first
surface through the safe local firewall family:

- the released `v0.4.0` DNS resource family and `v0.3.0` adapter surface;
- local firewall zones, address groups, port groups and ordered rules;
- deterministic firewall planning with exposure and dependency analysis;
- explicit apply, prune, acknowledgement and manual recovery boundaries;
- fixture-backed read-only evidence and authorized controller mutation
  evidence for Network 10.5.67;
- protected tag/version checks, clean installs, checksums and signed
  provenance.

The protected controller evidence is recorded in [workflow run
31903782251](https://github.com/Opperiesen/lanweave/actions/runs/31903782251).
The package was published by [the protected release workflow
31904325887](https://github.com/Opperiesen/lanweave/actions/runs/31904325887),
and is available as the [GitHub Release](https://github.com/Opperiesen/lanweave/releases/tag/v0.5.0)
and on [PyPI](https://pypi.org/project/lanweave/0.5.0/).

Milestone `v0.5.0` is closed with all seven issues completed. The complete
firewall scope is maintained in
[roadmap-v0.5.0.md](roadmap-v0.5.0.md).

## Release status — `v0.6.0`

`v0.6.0` is the current stable release. It adds the safe local NAT and
port-forwarding family while preserving the v0.5 firewall, v0.4 DNS, profile,
cloud-read-only and read-only MCP surfaces.

The release includes:

- portable NAT mappings without controller IDs or raw payloads;
- deterministic exposure, conflict and dependency analysis;
- guarded local-classic session mutations for the supported IPv4 subset;
- protected ownership, explicit prune and partial-failure recovery semantics;
- sanitized controller evidence and reproducible package gates.

The protected NAT controller lifecycle passed in [workflow run
31907918542](https://github.com/Opperiesen/lanweave/actions/runs/31907918542).
The package, tag, provenance, PyPI and GitHub publication gates passed in
[release workflow
31908100009](https://github.com/Opperiesen/lanweave/actions/runs/31908100009).
The release is available as the [GitHub
Release](https://github.com/Opperiesen/lanweave/releases/tag/v0.6.0) and on
[PyPI](https://pypi.org/project/lanweave/0.6.0/).

Milestone `v0.6.0` is closed with all seven issues completed. The next active
milestone is `v0.7.0` for safe local VPN resources; its read-only-first scope
remains outside the v0.6.0 release gate. The complete NAT scope is maintained
in [roadmap-v0.6.0.md](roadmap-v0.6.0.md).

## Release status — `v0.7.0`

`v0.7.0` is the current stable release. It adds the local VPN overview family
with a strict read-only and secret-free boundary: servers, site-to-site
tunnels, connected peers, route dependency validation, export, CLI, MCP and
plan observations.

The offline fixture gate, migration, compatibility, recovery and release
artifacts are documented in [roadmap-v0.7.0.md](roadmap-v0.7.0.md) and
[release-v0.7.0.md](release-v0.7.0.md). Live VPN lifecycle evidence remains
explicitly limited because the designated controller has no active VPN
resource to exercise safely.

Milestone `v0.7.0` is closed with the epic and all six implementation issues
completed. The next active milestone is `v0.8.0` for drift audit and
compliance reports.

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

This release is tracked as an umbrella epic:

- [#3 — explicit multi-controller and multi-site profiles](https://github.com/Opperiesen/lanweave/issues/3).

The work is deliberately decomposed into the following sequence.

### Foundation

- [#40 — define the profile contract and precedence rules](https://github.com/Opperiesen/lanweave/issues/40);
- [#41 — implement local profile resolution and credential sources](https://github.com/Opperiesen/lanweave/issues/41);
- [#42 — add version-2 configuration validation and profile commands](https://github.com/Opperiesen/lanweave/issues/42).

### Operator surfaces

- [#43 — thread explicit profiles through the CLI and apply safety checks](https://github.com/Opperiesen/lanweave/issues/43);
- [#44 — add stable target identity to plan JSON and planning outputs](https://github.com/Opperiesen/lanweave/issues/44);
- [#45 — make MCP profile and target selection explicit](https://github.com/Opperiesen/lanweave/issues/45).

### Evidence and release

- [#46 — validate v0.2.0 with integration evidence, migration docs and release gates](https://github.com/Opperiesen/lanweave/issues/46).

Expected release gates:

- `v0.2.0a1`: profile contract, resolver and version-1 compatibility are usable;
- `v0.2.0b1`: CLI, plan JSON and MCP surfaces are implemented with focused tests;
- `v0.2.0rc1`: integration evidence, migration documentation, redaction and wrong-target safety checks are complete;
- `v0.2.0`: all required checks pass and compatibility notes are published.

The gates are executable from a checkout:

```shell
# alpha: contracts, fixtures and resolver behavior
uv run python scripts/verify_v020_evidence.py
uv run pytest tests/test_profiles.py tests/test_config.py tests/test_contracts.py -q

# beta: complete non-live operator surface
uv run pytest -m "not integration and not integration_mutation" -q

# rc: protected controller and profile evidence on the dedicated LAN runner
uv run pytest tests/integration/test_controller.py tests/integration/test_profile_integration.py \
  -m integration -q

# stable: reproducible package and release metadata
uv run pytest -q
uv build
```

The rc command requires the protected `LANWEAVE_INTEGRATION_*` environment and
is run manually by `.github/workflows/integration.yml`. The stable tag workflow
then verifies the annotated tag, project version, clean artifacts, checksums,
provenance and publication state.

The profile model must:

- keep credentials in the environment or an approved secret provider;
- make controller and site selection explicit;
- identify the target in plans, JSON output and MCP responses;
- define precedence between CLI, configuration and environment;
- preserve version-1 single-controller files;
- reject incomplete or ambiguous profiles;
- prevent cross-controller and cross-site apply mistakes.

The release is limited to local controllers and sites. Cloud adapters remain in
`v0.3.0`; new resource families begin in `v0.4.0`; write-capable MCP and
implicit controller discovery remain out of scope.

The migration and deliberate contract changes are recorded in
[migration-v0.2.md](migration-v0.2.md) and
[compatibility.md](compatibility.md). The v0.2.0 release notes must retain the
same exclusions: no cloud adapters, no new resource families and no
write-capable MCP.

## `v0.3.0` — adapter capability boundary

The complete release scope is maintained in
[roadmap-v0.3.0.md](roadmap-v0.3.0.md) and tracked by the
[v0.3.0 epic #56](https://github.com/Opperiesen/lanweave/issues/56).

The architecture is split before cloud implementation:

- [#14 — adapter capability boundary and architecture review](https://github.com/Opperiesen/lanweave/issues/14);
- [#57 — freeze adapter and capability contracts](https://github.com/Opperiesen/lanweave/issues/57);
- [#58 — put the local classic client behind the adapter boundary](https://github.com/Opperiesen/lanweave/issues/58);
- [#59 — add explicit adapter selection to profiles and target identity](https://github.com/Opperiesen/lanweave/issues/59);
- [#4 — official cloud adapter implementation umbrella](https://github.com/Opperiesen/lanweave/issues/4);
- [#60 — Site Manager authentication and transport](https://github.com/Opperiesen/lanweave/issues/60);
- [#61 — cloud read-only inventory and health capabilities](https://github.com/Opperiesen/lanweave/issues/61);
- [#62 — adapter and capability discovery in CLI, plans and read-only MCP](https://github.com/Opperiesen/lanweave/issues/62);
- [#63 — cross-adapter compatibility, redaction and protected evidence](https://github.com/Opperiesen/lanweave/issues/63);
- [#64 — migration documentation and release gates](https://github.com/Opperiesen/lanweave/issues/64).

The local classic adapter remains the default and must not regress. The cloud
adapter is opt-in, independently tested and limited to documented Site Manager
read operations in this release. A local-to-cloud automatic fallback is not
allowed, and cloud writes are explicitly out of scope.

Each adapter must expose capabilities for:

- authentication;
- target selection;
- supported resources;
- read, create, update and delete operations;
- endpoint or payload differences;
- known compatibility limits.

The v0.3.0 cloud slice is limited to documented hosts, sites, devices and
supported health metrics. Networks, WLANs, clients, export, plan and apply are
unsupported unless the selected official API version exposes them with stable
semantics and dedicated fixtures. MCP remains read-only and must expose the
selected adapter, target and capabilities.

## `v0.4.0` — safe local DNS resource family

The complete release decomposition is maintained in
[roadmap-v0.4.0.md](roadmap-v0.4.0.md) and tracked by
[Epic #82](https://github.com/Opperiesen/lanweave/issues/82).

The release is deliberately limited to local DNS records. Its first goal is to
prove a reusable resource lifecycle — normalized inventory, portable export,
strict validation, deterministic planning, controlled apply, explicit prune
and manual recovery — without weakening the existing v0.3 adapter or MCP
contracts.

The work is ordered as follows:

1. [#77 — resource contract and dependency-aware lifecycle](https://github.com/Opperiesen/lanweave/issues/77);
2. [#16 — DNS inventory, export and versioned controller fixtures](https://github.com/Opperiesen/lanweave/issues/16);
3. [#78 — deterministic DNS validation and planning](https://github.com/Opperiesen/lanweave/issues/78);
4. [#79 — controlled DNS apply, prune and recovery](https://github.com/Opperiesen/lanweave/issues/79);
5. [#80 — existing CLI, capabilities and read-only MCP surfaces](https://github.com/Opperiesen/lanweave/issues/80);
6. [#81 — evidence, documentation and release gates](https://github.com/Opperiesen/lanweave/issues/81).

The intended gates are `v0.4.0a1` for the contract and fixture foundation,
`v0.4.0b1` for the read/export/plan surface, `v0.4.0rc1` for authorized
controller mutation and recovery evidence, and `v0.4.0` for the complete
verified package and publication.

Device adoption, restart, firmware and other high-impact mutations remain
post-`v1.0.0` candidates unless an independent safety model is approved.

## `v0.5.0` — safe local firewall resource family

The complete decomposition is maintained in
[roadmap-v0.5.0.md](roadmap-v0.5.0.md) and tracked by parent issue
[#15](https://github.com/Opperiesen/lanweave/issues/15).

The work is ordered as follows:

1. [#86 — firewall resource contract and ordering model](https://github.com/Opperiesen/lanweave/issues/86);
2. [#87 — firewall inventory, export and versioned controller fixtures](https://github.com/Opperiesen/lanweave/issues/87);
3. [#88 — deterministic firewall validation and dependency-aware planning](https://github.com/Opperiesen/lanweave/issues/88);
4. [#89 — controlled firewall apply, prune and recovery](https://github.com/Opperiesen/lanweave/issues/89);
5. [#90 — existing CLI, capabilities and read-only MCP surfaces](https://github.com/Opperiesen/lanweave/issues/90);
6. [#91 — v0.5.0 evidence, documentation and release gates](https://github.com/Opperiesen/lanweave/issues/91).

The release gates were `v0.5.0a1` for the contract and read foundation,
`v0.5.0b1` for the read/export/plan surface, `v0.5.0rc1` for authorized
mutation and recovery evidence, and `v0.5.0` for the verified package and
publication. The protected controller gates passed in workflow run
[31903782251](https://github.com/Opperiesen/lanweave/actions/runs/31903782251),
and the package/tag/publication gates passed in workflow run
[31904325887](https://github.com/Opperiesen/lanweave/actions/runs/31904325887).
The `v0.5.0` milestone remains closed; its successor `v0.6.0` is now the
current stable release.

## v0.7.0 release decomposition

Each resource family has a different blast radius, controller contract and
release gate. The completed v0.7.0 release was decomposed as follows:

### `v0.7.0` — safe local VPN resources

The [VPN epic #19](https://github.com/Opperiesen/lanweave/issues/19) and its
six implementation issues were delivered in the
[v0.7.0 milestone](https://github.com/Opperiesen/lanweave/milestone/9) with a
read-only-first rollout and strict secret/route handling.

The decomposition is executed in this order:

1. [#118 — portable VPN contract and secret boundary](https://github.com/Opperiesen/lanweave/issues/118);
2. [#121 — local VPN inventory and versioned fixtures](https://github.com/Opperiesen/lanweave/issues/121);
3. [#116 — VPN health, peers, routes and dependency validation](https://github.com/Opperiesen/lanweave/issues/116);
4. [#122 — secret-free export and migration documentation](https://github.com/Opperiesen/lanweave/issues/122);
5. [#114 — capability-aware CLI and read-only MCP](https://github.com/Opperiesen/lanweave/issues/114);
6. [#115 — protected read-only evidence and release gates](https://github.com/Opperiesen/lanweave/issues/115).

The complete contract, gates and deliberate exclusions are maintained in
[`roadmap-v0.7.0.md`](roadmap-v0.7.0.md). v0.7 does not create VPNs, generate
private keys or profiles, apply routes, or expose a write-capable MCP tool.

## Next independent release — `v0.8.0`

- `v0.8.0` (#120) turns the read-only observations into first-class drift and
  compliance reports with stable semantics;
- `v0.9.0` (#119) adds post-apply convergence and operational recovery evidence;
- `v1.0.0` (#117) freezes the local control-plane contracts, packaging and
  compatibility policy rather than promising every UniFi endpoint.

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
