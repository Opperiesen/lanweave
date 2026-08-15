# Migration from v0.2.0 to v0.3.0

Lanweave `v0.3.0` keeps the v0.2 local profile and resource model. Existing
version-1 configurations, version-2 local profiles and v1 plan JSON do not
need to be rewritten. The release adds an explicit adapter boundary, offline
capability discovery and a read-only official Site Manager slice.

## Existing local installations

No configuration change is required for a local target. An omitted adapter
continues to mean `local-classic`:

```yaml
controllers:
  local:
    host_env: LANWEAVE_LOCAL_HOST
    verify_tls: true
    auth:
      api_key_env: LANWEAVE_LOCAL_API_KEY
```

The following commands remain local and do not contact a controller:

```shell
lanweave profiles validate --config config/network.yaml
lanweave profiles list --config config/network.yaml
lanweave capabilities --config config/network.yaml --profile office --output json
```

The capability report is the safest first check after upgrading. It shows the
selected adapter, authentication mode and supported operations without
resolving credential values or sending a request.

## Opting into Site Manager

Cloud selection is explicit in the controller definition and is never inferred
from a hostname or a failed local request:

```yaml
version: 2
profile: cloud-overview

controllers:
  cloud:
    adapter: cloud-site-manager
    host_env: LANWEAVE_CLOUD_HOST
    verify_tls: true
    auth:
      api_key_env: LANWEAVE_CLOUD_API_KEY

profiles:
  cloud-overview:
    controller: cloud
    site: organization

networks: []
wlans: []
```

`LANWEAVE_CLOUD_HOST` should normally be `https://api.ui.com`. The API key is
loaded from `LANWEAVE_CLOUD_API_KEY`; it must not be written to YAML, a plan,
an issue, a fixture or a shell command. Username/password session auth is not
valid for `cloud-site-manager`.

The first cloud release only reads visible hosts, sites, devices and the
derived site health view. Clients, networks, WLANs, backup, export, plan,
apply and prune are unsupported. Unsupported operations fail before a cloud
request, and no local/cloud fallback exists.

## MCP consumers

The read-only MCP contract increments from v2 to v3. Existing tool parameters
remain available; `lanweave_get_capabilities` is added. Health and device
responses include the selected capability document. A cloud health response
omits `online_clients` because the Site Manager adapter does not claim client
reads. Consumers must inspect the advertised contract version and handle the
`unsupported_capability` error code.

## Rollback

To return to the v0.2 local behavior, remove the cloud profile selection or
select a profile whose controller has `adapter: local-classic`, then rerun the
capability report. Existing local plans remain target-bound; do not apply a
plan whose target identity, including adapter, differs from the selected
target.

## Security checklist

- keep the API key in the approved secret manager or process environment;
- reject unresolved `op://` references before starting the adapter;
- review the capability report before invoking an operational command;
- treat Site Manager as read-only in this release;
- publish only sanitized compatibility reports, never raw inventory or
  response payloads.
