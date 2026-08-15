# Local profile contract v0.2.0

This document freezes the design of Lanweave's local multi-controller and
multi-site profile layer for `v0.2.0`. It defines selection, target identity,
credential references and migration. Runtime support is implemented separately
by the child issues in the [v0.2.0 roadmap](roadmap.md) and validated by the
release evidence workflow.

The existing version-1 configuration remains valid and its `v0.1.x` behavior
is unchanged. The `v0.2.0` read-only MCP surface is explicitly versioned as
contract v2 because its controller-facing responses now expose a target
envelope; the migration is documented in
[`migration-v0.2.md`](migration-v0.2.md).

## Goals and boundaries

The profile layer must:

- make the selected controller and site explicit before any controller request;
- allow several sites on one controller and several local controllers in one
  configuration;
- keep credentials out of declarative YAML, plans, logs, fixtures and errors;
- preserve the current version-1 single-controller workflow;
- provide one sanitized target identity for the CLI, plans, JSON and MCP.

The `v0.2.0` profile layer does not include the official UniFi cloud adapter,
new resource families, implicit controller discovery or write-capable MCP.

## Version-2 document shape

Version 2 keeps the portable resource model (`networks` and `wlans`) at the
top level. It adds a controller registry and named target profiles. The
top-level `profile` is an optional configuration selector; a controller-facing
command must provide an explicit selector through one of the sources described
below when it is absent.

```yaml
version: 2
profile: office

controllers:
  local:
    host_env: LANWEAVE_LOCAL_HOST
    verify_tls: true
    auth:
      api_key_env: LANWEAVE_LOCAL_API_KEY

  backup:
    host_env: LANWEAVE_BACKUP_HOST
    verify_tls: true
    auth:
      username_env: LANWEAVE_BACKUP_USER
      password_env: LANWEAVE_BACKUP_PASSWORD

profiles:
  office:
    controller: local
    site: default

  guest:
    controller: local
    site: guest

  backup-default:
    controller: backup
    site: default

networks: []
wlans: []
```

The machine-readable contract for the connection layer is
[`profile-layer-v2.schema.json`](contracts/profile-layer-v2.schema.json).
The complete resource document schema is
[`config-v2.schema.json`](contracts/config-v2.schema.json), and the loader
validates both the profile layer and the existing resource model.

### Stable identifiers

- `controllers` and `profiles` map keys are stable lower-case identifiers
  matching `^[a-z][a-z0-9-]{0,63}$`;
- `profile.controller` must name a declared controller;
- `profile.site` is the controller-native site name or ID and must be a
  non-empty string; its case is preserved;
- `host_env` names the environment variable containing the controller URL;
- `verify_tls` defaults to `true` and must be explicit when disabled;
- `auth` contains exactly one API-key form or one username/password form.

The profile layer never stores a URL, API key, username or password value in
the YAML example. A secret provider may populate the referenced environment
variables before Lanweave starts, for example through a process wrapper. A
provider-specific URI such as `op://...` is not a v2 YAML value and is not
resolved by the profile layer.

The two supported authentication forms are:

```yaml
auth:
  api_key_env: LANWEAVE_LOCAL_API_KEY
```

or:

```yaml
auth:
  username_env: LANWEAVE_LOCAL_USER
  password_env: LANWEAVE_LOCAL_PASSWORD
```

Environment variable names must match `^[A-Z_][A-Z0-9_]*$`. The referenced
values are resolved only when a controller operation needs them; validation
and profile listing never print them.

## Selector precedence

The effective profile selector uses this order:

| Priority | Source | Rule |
| --- | --- | --- |
| 1 | CLI `--profile NAME` | Explicit command selection; a conflicting lower-priority selector is an error |
| 2 | Configuration `profile: NAME` | Documented default; a conflicting `LANWEAVE_PROFILE` is an error |
| 3 | `LANWEAVE_PROFILE` | Process-level default when the document has no selector |
| 4 | Version-1 compatibility mode | No profile selector; use the existing `controller.site` and legacy `UNIFI_*` settings |

The precedence order resolves missing values; it does not silently conceal a
conflict. If two present selectors name different profiles, the command fails
before loading credentials or contacting a controller. A version-2 document
with multiple profiles and no effective selector is always rejected. A
version-2 document with one profile is also required to select it explicitly;
profile count is never used as an implicit target choice.

`profiles list` and `profiles validate` are local discovery and validation
operations. They may enumerate a version-2 document without selecting a
controller target and must not contact a controller.

### Version-1 compatibility precedence

Version-1 files retain their current behavior:

- `controller.site` from the configuration overrides `UNIFI_SITE` when a
  command has loaded a configuration;
- `UNIFI_HOST`, `UNIFI_VERIFY_TLS`, `UNIFI_API_KEY`, `UNIFI_USER` and
  `UNIFI_PASS` remain the credential and connection sources;
- `--profile` is rejected for a version-1 document;
- `LANWEAVE_PROFILE` is not consulted in version-1 compatibility mode.

There is no automatic conversion from version 1 to version 2. This prevents a
profile name or controller target from being guessed during migration.

## Target identity

Every selected target is represented by the non-secret tuple:

```json
{
  "profile": "office",
  "controller": "local",
  "site": "default"
}
```

The human-readable form is:

```text
profile=office controller=local site=default
```

Target identity never contains `host`, an environment value, a credential,
an access token or a controller response. The profile name is included even
when two profiles point to the same controller and site, so an operator can
see which declared intent produced a plan. The CLI, plan JSON and MCP
consumers expose this identity through the v0.2.0 operator surfaces.

## Migration from version 1

Given a version-1 file:

```yaml
version: 1
controller:
  site: default
networks: []
wlans: []
```

The equivalent version-2 connection layer is:

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
```

The resource lists can be copied unchanged. The operator must deliberately
choose the new environment variable names and profile name. The migration
must not copy secret values or infer a controller from a profile name.

During the `v0.2.x` line, version-1 files remain accepted. A future removal of
version-1 compatibility would require a separate release decision, a
deprecation period and a migration note.

## Contract decisions and follow-up

This issue freezes the profile shape and selection semantics. The remaining
work is intentionally split:

- the resolver loads this layer and produces one target and credential source;
- configuration validation composes this layer with the existing resource
  schema and adds `profiles list` and `profiles validate`;
- CLI, plan JSON and MCP consumers expose the target identity without
  reimplementing selection.

No consumer may choose a target by inspecting the first profile, by discovering
controller sites implicitly or by falling back from one controller to another.
