# Lanweave configuration, CLI and adapter contracts

The v1 sections are normative for the `v0.1.x` line. The v2 sections define
the backward-compatible local profile additions for `v0.2.0`. Both versions
keep the public configuration, CLI, plan JSON and read-only MCP surfaces
explicit; neither adds new resource families or write-capable MCP tools.

The version identifiers are defined in
[`src/lanweave/contracts.py`](../src/lanweave/contracts.py): configuration
schema `1`, profile layer `2`, plan format `1` and MCP contract `2`.

The `v0.2.0` profile design is documented separately in
[`profiles.md`](profiles.md). It adds a version-2 local connection layer while
keeping the version-1 resource and controller contracts accepted. Runtime
support is delivered incrementally by the profile roadmap issues; the v1
surface remains unchanged while the v2 release is assembled.

## Configuration schema v1

The canonical machine-readable schema is
[`config-v1.schema.json`](contracts/config-v1.schema.json). YAML files use the
same object model because the loader parses YAML into JSON-compatible values.

Every valid v1 file contains:

```yaml
version: 1
controller:
  site: default
networks: []
wlans: []
```

The public fields are:

- `controller.site`: selected UniFi site name;
- `networks[]`: `name`, `purpose`, optional `subnet`, `vlan`, `domain_name`,
  `dhcp` and `ipv6`;
- `wlans[]`: `name`, `ssid`, `network`, `bands`, `security`, optional WLAN
  behavior flags and either `password_env` or a `${UPPERCASE_ENV_NAME}`
  placeholder for protected WLANs.

Unknown fields fail validation at every documented object level. Literal
passwords, secret-manager references and unresolved environment values are
rejected. `lanweave export` emits version 1 and never emits a WLAN password.

Valid version-1 files remain accepted throughout the `v0.1.x` line. A future
optional field may be added only if existing files keep the same meaning and
remain valid. A semantic change or removal requires a new schema version, a
migration note and an explicit release decision; Lanweave does not silently
rewrite a file between schema versions.

## Configuration schema v2

The canonical machine-readable schema is
[`config-v2.schema.json`](contracts/config-v2.schema.json). It composes the
existing version-1 network and WLAN resource definitions with the version-2
local profile layer from [`profiles.md`](profiles.md).

Version-2 files add:

- `controllers`: named local controller connection definitions using only
  environment variable references for host and credentials;
- `profiles`: named controller/site targets;
- optional `profile`: an explicit document-level selector;
- the unchanged `networks[]` and `wlans[]` resource model.

`validate` and `profiles validate` reject unknown, incomplete or ambiguous
profile fields locally. `profiles list` prints only sanitized profile target
identities and never contacts a controller or resolves credentials. Version-1
files remain accepted and retain their legacy environment precedence.

## CLI contract

The executable is `lanweave`. `--help` and `--version` exit with `0`.
All command-specific failures, refused overwrites, declined confirmations,
invalid configurations, controller failures and non-interactive mutation
refusals exit with `2`. Argument parsing errors also use argparse's exit code
`2`. No command uses `1` as a public result.

| Command | Stable options | Result |
| --- | --- | --- |
| `init` | `--path`, `--force` | Create the generic v1 YAML file; never overwrite without `--force` |
| `validate` | `--config` | Validate locally; no controller request |
| `profiles list` | `--config` | List sanitized v1 or v2 target identities; no controller request |
| `profiles validate` | `--config` | Validate v1 or v2 configuration locally; no controller request |
| `doctor` | `--check`, `--config`, `--profile` | Inspect settings; probe health only with `--check` |
| `export` | `--out`, `--force`, `--config`, `--profile` | Write secret-free v1 YAML or stdout |
| `plan` | `--config`, `--profile`, `--prune`, `--output table/json` | Print deterministic changes; JSON is plan format v1 |
| `apply` | `--config`, `--profile`, `--prune`, `--output table/json`, `--yes` | Apply only after confirmation; no implicit mutation |
| `backup` | `--output`, `--config`, `--profile` | Write a local redacted snapshot with mode `0600` |
| `status` | `--output table/json`, `--config`, `--profile` | Show health and device summary |
| `clients` | `--filter`, `--wired`, `--output table/json`, `--config`, `--profile` | Show filtered client inventory |

`--prune` is opt-in and retains its separate confirmation boundary.
`apply --output json` writes a structured failure report to stderr when
application stops part-way through; successful plan JSON is written to stdout.

## Plan JSON format v1

The canonical schema is
[`plan-v1.schema.json`](contracts/plan-v1.schema.json). A plan always has:

```json
{
  "format_version": 1,
  "target": {
    "profile": "office",
    "controller": "local",
    "site": "default"
  },
  "summary": {"create": 0, "update": 0, "delete": 0, "noop": 0},
  "changes": []
}
```

`target` is optional for compatibility with plans produced before `v0.2.0`.
The `v0.2.0` CLI always includes it and the value is the non-secret tuple of
profile, controller and site. The plan format deliberately remains version 1:
adding this optional field does not change the meaning of any existing field,
so old v1 plan JSON remains valid and readable. A target-bound plan cannot be
applied without the same selected identity; a mismatch is rejected before any
controller mutation. Legacy plans without `target` retain their v1 behavior and
should be regenerated when more than one target is available.

Every change has `kind`, `action`, `name`, `id`, `changed_fields` and a
`payload`. `changes` excludes `noop` entries, while `summary.noop` retains the
count of unchanged resources. Consumers must reject an unsupported
`format_version` rather than guessing its meaning.

The redaction guarantee is part of the format: the plan contains no current
controller object, request body outside the redacted payload, response body or
credential. Sensitive keys such as `password`, `passphrase`, `secret`, `token`
and `api_key` are represented as `***`. The guarantee applies recursively to
the serialized plan and is covered by unit tests.

Adding an optional field within format v1 requires preserving all existing
fields and meanings. Renaming, removing or changing the semantics of a field
requires a new format version and a release note.

## Read-only MCP contract v2

The optional stdio adapter exposes exactly these six tools:

| Tool | Parameters | Logical return value |
| --- | --- | --- |
| `lanweave_get_health` | `config_path: string|null = null`, `profile: string|null = null` | `{target, health, online_clients, devices}` |
| `lanweave_list_devices` | `config_path: string|null = null`, `profile: string|null = null` | `{target, devices}` |
| `lanweave_list_clients` | `include_wired: boolean = true`, `config_path: string|null = null`, `profile: string|null = null` | `{target, clients}` |
| `lanweave_export_config` | `config_path: string|null = null`, `profile: string|null = null` | `{target, config}` with secret-free configuration schema v1 |
| `lanweave_validate_config` | `config_path: string = "config/network.yaml"` | `{valid: true, version: 1 or 2, networks, wlans}` |
| `lanweave_plan_changes` | `config_path: string = "config/network.yaml"`, `prune: boolean = false`, `profile: string|null = null` | target-bound redacted plan JSON format v1 |

The four controller-facing inventory/export tools preserve their version-1
environment-only invocation when `config_path` and `profile` are omitted. When
`config_path` points to a version-2 file, the shared resolver requires an
explicit profile from the tool argument, the document selector or
`LANWEAVE_PROFILE`; conflicting selectors fail before controller access. The
plan tool always reads its configuration path and applies the same rule.

Every controller-facing response exposes the sanitized target tuple
`{profile, controller, site}`. The list and export tools therefore use an
object envelope in contract v2 instead of returning a bare array or bare
configuration document. Clients consuming contract v1 output must update their
decoders and check the advertised MCP contract version before upgrading.

Tool names, parameter names, defaults and descriptions are tested from the
MCP tool listing. No MCP tool can call `apply`, `delete` or any other mutation
operation; the adapter only reads, validates, exports and plans.

Tool failures are protocol errors with one of these stable prefixes:

- `invalid_configuration`: the local file or schema is invalid;
- `credentials_error`: controller credentials or TLS settings are incomplete;
- `controller_error`: a read request failed;
- `internal_error`: an unexpected adapter failure.

The detail after the prefix is operational guidance only and must not contain
credentials, request payloads or raw controller response bodies.

## Change and deprecation policy

Within `v0.1.x`, additive changes are preferred and existing v1 behavior stays
valid. A breaking configuration, CLI, plan or MCP change requires all of:

1. an explicit schema, format or contract version decision;
2. a migration or deprecation note in this document and the changelog;
3. focused tests for the old and new behavior where compatibility is promised;
4. a release decision recorded in the roadmap and release notes.

No cloud adapter, multi-controller profile, new resource family or write-capable
MCP tool is part of this contract. Those belong to later roadmap milestones.
