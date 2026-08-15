# Migration from v0.3.0 to v0.4.0

Lanweave `v0.4.0` keeps the v0.3 adapter, profile, CLI, plan and read-only MCP
contracts. DNS is an additive optional resource family; an existing v1 or v2
configuration remains valid without changes.

## Add DNS only when it is intentional

Add an optional top-level `dns` list to the desired configuration:

```yaml
dns:
  - name: printer.home.arpa
    type: A
    address: 192.0.2.10
    ttl_seconds: 300
```

The portable model supports only `A`, `AAAA` and `CNAME` records. A and AAAA
records use `address`; CNAME records use `target`. Names are canonicalized to
lowercase without a trailing dot. Wildcards, duplicate `(name, type)`
identities, CNAME conflicts and out-of-range TTLs are rejected locally.

No migration tool rewrites existing files. The field is optional, so the
safest migration is to add records gradually, validate, inspect a plan and
apply only after reviewing the exact changes:

```shell
lanweave validate --config config/network.yaml
lanweave capabilities --config config/network.yaml --output json
lanweave plan --config config/network.yaml --output json
lanweave apply --config config/network.yaml
```

## Authentication boundary

DNS policies use the official local Network Integration API endpoint
`/proxy/network/integration/v1/sites/{siteId}/dns/policies`. The v0.4 adapter
supports DNS read, export, plan, apply and prune only with a resolved API key.
The generic API-key path for networks and WLANs remains read-only, and session
authentication does not advertise DNS operations.

The controller must expose the documented DNS policy contract (the release
evidence targets Network 10.3.58). Site Manager cloud profiles do not gain DNS
support and MCP remains read-only.

## Export and ownership

`lanweave export` includes only user-managed supported DNS policies. Controller
IDs and origin metadata never enter the portable YAML. System and unknown-origin
policies are retained by planning and excluded from prune.

`--prune` is still opt-in. A missing DNS record in the file is not deleted
unless `--prune` is supplied and the controller identifies it as user-managed.
After any failed apply, generate a fresh plan before retrying; Lanweave does
not claim automatic rollback.

See the [DNS roadmap](roadmap-v0.4.0.md), [compatibility matrix](compatibility.md)
and [recovery guide](recovery.md) for exact support limits.
