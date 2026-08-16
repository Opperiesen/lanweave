# Migration from v0.9.0 to v1.0.0

Lanweave v1.0.0 is a compatibility and stability release. It does not change
the configuration schema, plan JSON format, capability format, audit result
format, convergence result format or read-only MCP tool names introduced by
the v0.x releases.

## Before upgrading

Capture a redacted backup and inspect the current target:

```shell
lanweave backup --config config/network.yaml
lanweave capabilities --config config/network.yaml --output json
lanweave validate --config config/network.yaml
lanweave plan --config config/network.yaml --output json > plan.json
```

Do not commit the backup, plan, export or any credential-bearing environment
file.

## Package upgrade

```shell
uv tool install --upgrade lanweave==1.0.0
lanweave --version
```

The optional MCP extra remains opt-in:

```shell
uv tool install --upgrade 'lanweave[mcp]==1.0.0'
```

## Compatibility

Existing v1 configuration files and v2 profile files remain valid. Existing
plans remain readable when their target identity is compatible. A plan bound to
another profile, controller, site or adapter must be regenerated rather than
forced through the safety boundary.

The v1.0.0 release does not turn unsupported capabilities into supported ones:
VPN writes, cloud writes, generic API-key writes and write-capable MCP remain
outside the product contract.

Compatibility is also intentionally scoped to the designated controller
combination documented in [`compatibility.md`](compatibility.md). An upgrade
does not imply support for another UniFi OS/Network version; verify that target
against a published report first.

## Rollback

If an application-level issue is discovered, reinstall `0.9.0`, restore the
last known-good configuration if required, and generate a fresh plan before
retrying. A package rollback does not roll back a controller mutation; use the
documented recovery procedure and an explicitly reviewed plan.

## Future breaking changes

The v1.x line accepts additive changes that preserve existing meanings. A
removal, rename, semantic change, new mutation boundary or MCP write operation
requires a new contract version, migration guidance, focused compatibility
tests and an explicit release decision.
