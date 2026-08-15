# Security policy

This tool can change network configuration. Treat it as infrastructure
automation, not as a harmless status client.

## Safe usage

- use a dedicated local API key with the minimum permissions required;
- keep the controller reachable only from a trusted network;
- keep TLS verification enabled unless the controller certificate is
  deliberately managed elsewhere;
- review the plan before applying it;
- treat NAT and port-forwarding changes as reachability changes: use disabled,
  uniquely prefixed test mappings and a dedicated session account for evidence;
- require an explicit risk acknowledgement before applying broad or
  Internet-facing NAT plans, and never infer support for an undocumented
  controller variant;
- keep exports and backups outside Git;
- never paste API keys, passwords, exports or controller logs into issues.

## Reporting a vulnerability

Please do not open a public issue for a credential leak, authentication
problem or remotely exploitable behavior. Use GitHub's private security
advisory mechanism when the public repository exists, or contact the
maintainers privately with reproduction steps and affected versions.

Do not test destructive operations against a controller you do not own or
administer. For a confirmed vulnerability, use the repository's
[private security advisory](https://github.com/Opperiesen/lanweave/security/advisories/new)
instead of a public issue.
