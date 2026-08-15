# Lanweave v0.4.0 release notes

Lanweave `v0.4.0` adds the first new declarative resource family since the
v0.1 core: local DNS policies through the official UniFi Network Integration
API.

## Included

- portable `A`, `AAAA` and `CNAME` DNS records in version-1 and version-2
  configurations;
- canonical hostnames, type-aware addresses, TTL limits and conflict checks;
- normalized controller reads with bounded pagination and unsupported-type
  filtering;
- secret-free DNS export with controller identity and ownership metadata
  removed;
- deterministic create/update/no-op planning and explicit user-owned prune;
- protected system/unknown-origin records and fail-closed missing-ID checks;
- API-key-only local DNS create/update/delete through the documented endpoint;
- DNS-aware CLI validation, export, plan, apply and capability output;
- DNS in the existing read-only MCP export, validation and planning responses;
- dependency-aware apply order and sanitized partial-failure recovery reports;
- fixture-backed tests, authorized controller lifecycle evidence and release
  artifact verification.

## Deliberate exclusions

The release does not add cloud DNS, write-capable MCP tools, DNS forwarding or
network-scoped policies, wildcard records, MX/TXT/SRV/PTR records, firewall,
NAT, VPN or device mutation workflows. Those remain outside the v0.4.0
compatibility claim.

## Upgrade

The `dns` field is optional and no migration is required for existing files.
Read [migration-v0.4.md](migration-v0.4.md) before declaring or pruning records.

## Verification

The release is built from an annotated `v0.4.0` tag whose commit contains the
same project version. A fresh checkout can run:

```shell
uv sync --extra dev --extra mcp --locked
uv run python scripts/verify_v040_evidence.py
uv run pytest -m "not integration and not integration_mutation" -q
uv build
```

The published release assets include checksums and GitHub build provenance.
PyPI publication uses Trusted Publishing and package attestations.
