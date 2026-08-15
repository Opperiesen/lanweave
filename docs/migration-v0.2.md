# Migration to Lanweave v0.2.0

Lanweave `v0.2.0` adds explicit local controller profiles while keeping
version-1 resource files valid. Migration is deliberate: Lanweave never
guesses a controller, site or credential source from an existing file.

## Version-1 configuration

The existing file remains usable without modification:

```yaml
version: 1
controller:
  site: default
networks: []
wlans: []
```

It continues to use `UNIFI_HOST`, `UNIFI_SITE`, `UNIFI_VERIFY_TLS`,
`UNIFI_API_KEY`, `UNIFI_USER` and `UNIFI_PASS`. The configuration site still
overrides `UNIFI_SITE` when a file is loaded. No profile selector is accepted
for a version-1 file.

## Equivalent version-2 configuration

The corresponding version-2 file separates connection definitions from
named targets:

```yaml
version: 2
profile: default

controllers:
  local:
    host_env: LANWEAVE_LOCAL_HOST
    verify_tls: true
    auth:
      api_key_env: LANWEAVE_LOCAL_API_KEY

profiles:
  default:
    controller: local
    site: default

networks: []
wlans: []
```

The resource lists are copied unchanged. The operator chooses the new
environment variable names and populates them outside the file, for example
with a local secret-manager process wrapper. Secret values and provider URIs
are never copied into YAML, plans or fixtures.

For a multi-target file, add one controller entry per local controller and one
profile per controller/site pair. Commands that contact a controller require
an effective profile from `--profile`, the document `profile`, or
`LANWEAVE_PROFILE`; conflicting selectors fail before credentials are loaded.

The sanitized target identity is always:

```text
profile=default controller=local site=default
```

## Surface changes in v0.2.0

- CLI controller commands accept `--config` and `--profile`; v2 operations
  announce the selected target and plans include it in table and JSON output.
- Plan format remains v1. The optional `target` field is additive, so old plan
  JSON without it remains readable. Target-bound plans refuse a missing or
  different identity before mutation.
- The read-only MCP surface is contract v2. Controller-facing tools accept
  `config_path` and `profile` and return a sanitized target envelope. Existing
  tool names remain, but clients decoding bare arrays or a bare exported config
  must update their response handling after checking the contract version.
- `profiles list` and `profiles validate` remain offline and never resolve
  credentials or contact a controller.

The v0.2 release remains local-only. It does not add the official cloud
adapter, firewall/DNS/NAT/VPN resource families or write-capable MCP tools.

## Validation checklist

Run the local compatibility checks before switching a file:

```shell
uv run lanweave profiles validate --config config/network.yaml
uv run lanweave profiles list --config config/network.yaml
uv run lanweave doctor --config config/network.yaml --profile default
uv run lanweave plan --config config/network.yaml --profile default --output json
```

Review the `target` object in the plan and confirm that the profile, controller
and site are the intended destination before any `apply`. Keep the original
version-1 file until the first version-2 plan and read-only verification have
been reviewed.

The complete profile contract and precedence rules are in
[`profiles.md`](profiles.md). The machine-readable CLI, plan and MCP contracts
are in [`contracts.md`](contracts.md).
