# Security policy

This tool can change network configuration. Treat it as infrastructure
automation, not as a harmless status client.

## Safe usage

- use a dedicated local API key with the minimum permissions required;
- keep the controller reachable only from a trusted network;
- keep TLS verification enabled unless the controller certificate is
  deliberately managed elsewhere;
- review the plan before applying it;
- keep exports and backups outside Git;
- never paste API keys, passwords, exports or controller logs into issues.

## Reporting a vulnerability

Please do not open a public issue for a credential leak, authentication
problem or remotely exploitable behavior. Use GitHub's private security
advisory mechanism when the public repository exists, or contact the
maintainers privately with reproduction steps and affected versions.

Do not test destructive operations against a controller you do not own or
administer.
