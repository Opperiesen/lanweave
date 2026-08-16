# Lanweave v1.0.0

Lanweave v1.0.0 freezes the stable local network control-plane contract.

## Included

- frozen configuration, profile, plan, capability, audit and convergence
  contracts;
- typed public Python API with an explicit export list;
- CLI-first local controller workflows with deterministic redacted plans;
- read-only MCP contract v3 with nine tools and no mutation operation;
- read-only Site Manager inventory adapter;
- documented DNS, firewall, NAT and VPN boundaries;
- protected live read-only CLI, MCP and VPN compatibility evidence for the
  designated controller;
- post-apply convergence and partial-failure recovery evidence;
- migration guidance from v0.9.0 and v1.x deprecation policy;
- clean package installation, provenance, checksums, PyPI attestations and a
  protected GitHub Release.

The published compatibility claim is intentionally limited to the designated
UniFi Dream Router 7 running UniFi OS 5.1.19 and UniFi Network 10.5.67. The
second-controller evidence expansion is planned for
[v1.1.0 issue #147](https://github.com/Opperiesen/lanweave/issues/147) and is
not implied by this release.

## Deliberate exclusions

The release does not add cloud mutations, generic API-key writes, device
adoption/restart/firmware workflows, VPN key/profile generation, automatic
rollback or a hosted telemetry service.

## Verification

The exact release run, public release assets, PyPI page, live compatibility
reports and post-publication checks are linked from the v1.0.0 release issue
and the repository's [release verification procedure](release.md).
