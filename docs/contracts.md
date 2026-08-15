# Lanweave configuration, CLI and adapter contracts

The v1 sections are normative for the original configuration contract. The v2
sections define the backward-compatible local profile additions for `v0.2.0`.
The `v0.4.0` DNS, `v0.5.0` firewall and `v0.6.0 NAT` extensions are additive
within those schema and plan versions. DNS adds optional local `A`, `AAAA` and
`CNAME` records. Firewall adds optional local zones, address groups, port
groups and ordered rules. NAT adds optional local port-forwarding mappings
without adding a write-capable MCP tool. See [`firewall.md`](firewall.md) and
[`nat.md`](nat.md) for the portable resource contracts.

The version identifiers are defined in
[`src/lanweave/contracts.py`](../src/lanweave/contracts.py): configuration
schema `1`, profile layer `2`, plan format `1`, MCP contract `3` and adapter
capability format `1`.

The v0.3 adapter boundary is defined by
[`adapter-capabilities-v1.schema.json`](contracts/adapter-capabilities-v1.schema.json).
It is additive to the v0.2 contracts: it describes adapter capabilities while
keeping the configuration and plan format versions stable. The v0.3 operator
surface consumes the selected adapter and exposes capabilities through the CLI
and MCP contract v3.

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
# optional local DNS records
dns: []
# optional local NAT mappings
nat: []
```

The public fields are:

- `controller.site`: selected UniFi site name;
- `networks[]`: `name`, `purpose`, optional `subnet`, `vlan`, `domain_name`,
  `dhcp` and `ipv6`;
- `wlans[]`: `name`, `ssid`, `network`, `bands`, `security`, optional WLAN
  behavior flags and either `password_env` or a `${UPPERCASE_ENV_NAME}`
  placeholder for protected WLANs.
- optional `dns[]`: normalized local `A`, `AAAA` and `CNAME` records. A/AAAA
  use `address`; CNAME uses `target`; `ttl_seconds` defaults to 300 and
  controller-origin metadata is never part of the portable file.
- optional `firewall`: `zones[]`, `address_groups[]`, `port_groups[]` and
  `rules[]`; zones and groups use names, rules use explicit relative order and
  placement, and controller IDs/origins are never portable fields.
- optional `nat[]`: named public interfaces, source scopes, private endpoints,
  protocols and translated port ranges; controller IDs/origins are never
  portable fields.

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
- optional `controllers.<name>.adapter`: `local-classic` by default, or the
  explicitly selected `cloud-site-manager` backend;
- `profiles`: named controller/site targets;
- optional `profile`: an explicit document-level selector;
- the unchanged `networks[]`, `wlans[]`, DNS, firewall and NAT resource model.

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
| `apply` | `--config`, `--profile`, `--prune`, `--output table/json`, `--yes`, `--acknowledge-risk` (`--acknowledge-firewall-risk` alias) | Apply only after confirmation; firewall and NAT warnings require explicit risk acknowledgement |
| `backup` | `--output`, `--config`, `--profile` | Write a local redacted snapshot with mode `0600` |
| `status` | `--output table/json`, `--config`, `--profile` | Show health and device summary |
| `clients` | `--filter`, `--wired`, `--output table/json`, `--config`, `--profile` | Show filtered client inventory |
| `capabilities` | `--output table/json`, `--config`, `--profile` | Show selected adapter capabilities without contacting a target |

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
    "site": "default",
    "adapter": "local-classic"
  },
  "summary": {"create": 0, "update": 0, "delete": 0, "noop": 0},
  "changes": []
}
```

`target` is optional for compatibility with plans produced before `v0.2.0`.
The `v0.2.0` CLI always includes `profile`, `controller` and `site`; the
v0.3.0 CLI adds the selected adapter to that non-secret tuple. The plan format
deliberately remains version 1:
adding this optional field does not change the meaning of any existing field,
so old v1 plan JSON remains valid and readable. A target-bound plan cannot be
applied without the same selected identity; a mismatch is rejected before any
controller mutation. Legacy plans without `target` retain their v1 behavior and
are restricted to `local-classic` when they are loaded into the v0.3 target
model. Legacy target objects without `adapter` default to `local-classic`.

Every change has `kind`, `action`, `name`, `id`, `changed_fields` and a
`payload`. `changes` excludes `noop` entries, while `summary.noop` retains the
count of unchanged resources. Consumers must reject an unsupported
`format_version` rather than guessing its meaning.

Firewall plans may use `kind` values `firewall_zone`, `firewall_group` and
`firewall_rule`. A rule ordering change uses `action: reorder`, a
`changed_fields` value of `order`, and a payload containing the
source/destination zone names plus the explicit before/after lists. Risk text
is carried in an optional `warnings` array and never contains request payloads
or credentials. NAT plans use `kind: nat`, keep the portable mapping in the
redacted payload, and carry exposure/conflict warnings through the same field.

The redaction guarantee is part of the format: the plan contains no current
controller object, request body outside the redacted payload, response body or
credential. Sensitive keys such as `password`, `passphrase`, `secret`, `token`
and `api_key` are represented as `***`. The guarantee applies recursively to
the serialized plan and is covered by unit tests.

Adding an optional field within format v1 requires preserving all existing
fields and meanings. Renaming, removing or changing the semantics of a field
requires a new format version and a release note.

## Read-only MCP contract v3

The superseded **Read-only MCP contract v2** remains documented by the
v0.2.0 release gate; v3 is the additive capability-aware successor.

The optional stdio adapter exposes exactly these seven tools:

| Tool | Parameters | Logical return value |
| --- | --- | --- |
| `lanweave_get_health` | `config_path: string|null = null`, `profile: string|null = null` | `{target, capabilities, health, devices, online_clients?}` |
| `lanweave_get_capabilities` | `config_path: string|null = null`, `profile: string|null = null` | `{target, capabilities}` without a target request |
| `lanweave_list_devices` | `config_path: string|null = null`, `profile: string|null = null` | `{target, capabilities, devices}` |
| `lanweave_list_clients` | `include_wired: boolean = true`, `config_path: string|null = null`, `profile: string|null = null` | `{target, clients}` |
| `lanweave_export_config` | `config_path: string|null = null`, `profile: string|null = null` | `{target, config}` with secret-free configuration schema v1 |
| `lanweave_validate_config` | `config_path: string = "config/network.yaml"` | `{valid: true, version: 1 or 2, networks, wlans, dns, firewall, nat}` |
| `lanweave_plan_changes` | `config_path: string = "config/network.yaml"`, `prune: boolean = false`, `profile: string|null = null` | target-bound redacted plan JSON format v1 |

The four controller-facing inventory/export tools preserve their version-1
environment-only invocation when `config_path` and `profile` are omitted. When
`config_path` points to a version-2 file, the shared resolver requires an
explicit profile from the tool argument, the document selector or
`LANWEAVE_PROFILE`; conflicting selectors fail before controller access. The
plan tool always reads its configuration path and applies the same rule.

Every controller-facing response exposes the sanitized target tuple
`{profile, controller, site, adapter}`. Inventory responses also expose the
selected adapter's versioned capability document. The list and export tools
therefore use an object envelope instead of returning a bare array or bare
configuration document. Clients consuming contract v1 output must update their
decoders and check the advertised MCP contract version before upgrading.

Tool names, parameter names, defaults and descriptions are tested from the
MCP tool listing. No MCP tool can call `apply`, `delete` or any other mutation
operation; the adapter only reads, validates, exports and plans.

Tool failures are protocol errors with one of these stable prefixes:

- `invalid_configuration`: the local file or schema is invalid;
- `credentials_error`: controller credentials or TLS settings are incomplete;
- `controller_error`: a read request failed;
- `unsupported_capability`: the selected adapter does not expose the requested
  resource or operation;
- `rate_limit`: the selected adapter was rate-limited and may provide a retry hint;
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

No write-capable MCP tool or cloud mutation is part of this contract. The
v0.3/v0.4 cloud adapter remains read-only and limited to its documented Site
Manager capabilities. The v0.5 firewall family remains local API-key-only;
the v0.6 NAT family is local-session-only, and VPN remains a future resource
family.
