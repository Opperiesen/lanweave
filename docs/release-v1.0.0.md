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

The protected [v1.0.0 release workflow run](https://github.com/Opperiesen/lanweave/actions/runs/31942097161)
built and published the package from commit
`5cedd2ae471689692a82bdbbafedfcd945ab709f`. Its required CI, build, clean
installation, PyPI publication and GitHub Release jobs passed. The first
post-publication step exposed a missing `GH_TOKEN` environment mapping; this
was corrected in [PR #161](https://github.com/Opperiesen/lanweave/pull/161).

The complete public verification then passed in the rerunnable
[verification workflow run](https://github.com/Opperiesen/lanweave/actions/runs/31942363200),
covering the annotated tag target, release assets, checksums, PyPI files,
GitHub artifact attestation and PyPI PEP 740 attestations for both the wheel
and source distribution.

The public artifacts are the [GitHub Release v1.0.0](https://github.com/Opperiesen/lanweave/releases/tag/v1.0.0),
the [PyPI package](https://pypi.org/project/lanweave/1.0.0/) and the annotated
[v1.0.0 tag](https://github.com/Opperiesen/lanweave/tree/v1.0.0). The complete
operator procedure remains in the [release verification guide](release.md).
