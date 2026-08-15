# NAT and port-forwarding contract

The v0.6.0 contract represents a local port-forwarding mapping without
controller IDs, UI-only fields or vendor payloads. The top-level configuration
field is `nat`, a list of named mappings.

```yaml
nat:
  - name: https
    enabled: true
    protocol: TCP
    ip_version: IPV4
    public:
      interface: WAN
      address: 203.0.113.2
      port: 443
    source:
      zone: External
      addresses:
        - 198.51.100.0/24
    private:
      network: Home
      address: 192.168.10.10
      port: 8443
    hairpin: false
```

## Frozen fields

- `name` is the portable identity and must be unique within `nat`;
- `enabled` defaults to `true`;
- `protocol` is one of `TCP`, `UDP` or `TCP_UDP`;
- `ip_version` is `IPV4` or `IPV6` and must match every address in the
  mapping; it is inferred from the private endpoint when omitted;
- `public.interface` is a named controller interface and `public.address` is
  optional when the interface selects the address;
- `public.port` and `private.port` are a number from 1 to 65535 or an inclusive
  `{start, stop}` range; both ranges must cover the same number of ports;
- `source.zone` is optional and `source.addresses` contains IP addresses or
  CIDR networks; an omitted or empty address list means any source and is
  intentionally broad;
- `private.network` is an optional reference to a declared network;
- `private.address` is one host IP address, never a hostname or CIDR network;
- `hairpin` defaults to `false` and must be explicit before a future adapter
  maps the behavior to a controller;
- `description` is optional operator documentation.

The normalizer canonicalizes protocol and IP version casing, IP addresses and
CIDR notation, removes duplicate source entries, and rejects unknown fields.
Controller IDs and ownership metadata are live inventory fields only; they are
never exported into YAML.

## Safety invariants

- mixed IPv4/IPv6 mappings are rejected;
- translated public and private ranges must have equal cardinality;
- duplicate names, unsupported protocols, invalid ports and unknown network
  references fail before planning;
- a mapping with no source addresses is broad and must receive a visible risk
  warning in the planning layer;
- only live mappings with a user-managed origin may later be pruned;
- system-managed and unknown-origin mappings remain protected;
- controller-specific payload conversion, exposure conflict analysis and
  mutation semantics remain outside the portable fields; the supported
  local-session boundary is documented below.

The contract is intentionally smaller than the controller UI. An unsupported
mapping is rejected rather than approximated with an undocumented endpoint or
an implicit source, port translation or hairpin behavior.

## v0.6.0 inventory compatibility

The first inventory implementation supports the local classic session endpoint:

```text
GET /proxy/network/api/{site}/rest/portforward
```

The adapter translates the proven legacy fields `name`, `enabled`,
`pfwd_interface`, `src`, `dst_port`, `fwd`, `fwd_port` and `proto`. Legacy
string ports such as `443` and `5300-5302` become the portable number or range
form. Controller counters, logging flags, site identifiers and other UI-only
fields are discarded from the portable export. The controller object ID and a
conservative ownership marker remain available only in live inventory.

This read path deliberately requires local session authentication. The current
Integration API capability matrix does not advertise NAT, so API-key mode does
not fall back to the classic endpoint. Site Manager and other unsupported
adapters likewise fail before a request is attempted.

Rules without a recognized user-managed origin are protected from export and
prune operations. A missing origin is therefore `UNKNOWN`, not an implicit
user-owned rule. The v0.6 controlled apply, prune and recovery boundary is
session-only and fail-closed for unsupported variants.

The classic response is a single inventory list rather than a paginated
Integration API collection. The adapter accepts an empty `data` list and fails
closed if a future response changes the envelope or mapping shape; it does not
invent pagination semantics for an endpoint that does not expose them.

## Planning boundary

The planning layer compares mappings by name, sorts the result by that stable
identity and refuses overlapping public flows when interface, address, port,
protocol and source scope can collide. Disabled mappings do not create an
active-flow conflict. A plan warning names the public boundary and private
service, and can call out unrestricted sources, interface-selected addresses,
privileged ports, hairpin uncertainty and an unproven firewall dependency.

The local-classic adapter now converts the supported IPv4 subset back to the
legacy write payload and exposes session-only create/update/delete operations.
The apply path requires the existing reviewed-plan confirmation and the
separate prune confirmation, keeps NAT writes behind the plan risk gate, and
reports partial failures as uncertain operations with a fresh-read recovery
instruction. API-key, cloud and unproven variants remain unsupported.

## Operator surfaces

The existing CLI and read-only MCP surface carry NAT without adding a second
resource model or a write-capable tool:

- `lanweave validate` and `profiles validate` report the number of declared
  mappings;
- `lanweave export` includes only user-managed, portable mappings and removes
  controller IDs and origin metadata;
- `lanweave plan` and `lanweave apply` use the same deterministic plan, with
  `--acknowledge-risk` for reviewed exposure warnings and the legacy
  `--acknowledge-firewall-risk` alias retained for compatibility;
- CLI and MCP capability documents advertise session-only `read`, `export`,
  `plan`, `apply` and `prune`; API-key and cloud targets do not gain NAT by
  fallback;
- MCP validation, export and planning remain read-only and never expose an
  apply or delete tool.
