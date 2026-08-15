# Lanweave v0.2.0 release notes

`v0.2.0` extends the stable local-first core with explicit local controller
profiles. It is a focused multi-controller and multi-site release, not a new
cloud or resource-family platform.

## Included

- version-2 configuration documents with named local controllers and profiles;
- explicit selector precedence through CLI, document configuration and
  `LANWEAVE_PROFILE`;
- version-1 configuration compatibility and migration guidance;
- target identity `{profile, controller, site}` in CLI planning output and plan
  JSON;
- pre-mutation rejection of missing or mismatched target identities;
- offline `profiles list` and `profiles validate` commands;
- MCP contract v2 with explicit target selectors and sanitized response
  envelopes;
- redaction, compatibility fixtures and guarded read-only profile probes.

## Deliberate compatibility decisions

- configuration schema v1 remains accepted;
- plan format stays v1 because `target` is optional and additive;
- the MCP contract increments to v2 because bare arrays and bare exported
  configuration responses become target envelopes;
- legacy environment-only MCP target resolution remains callable, but clients
  consuming contract v1 response shapes must update after checking the contract
  version.

## Excluded from v0.2.0

- official UniFi cloud adapters;
- firewall, DNS, NAT, VPN or other new resource families;
- write-capable MCP tools;
- implicit controller or site discovery;
- hosted relay, telemetry or private topology publication.

The release gates and commands are maintained in the
[v0.2.0 roadmap](roadmap.md). Migration steps are in
[migration-v0.2.md](migration-v0.2.md), and API/version compatibility is in
[compatibility.md](compatibility.md).
