# Product design

## Layers

    declarative YAML
            |
            v
    schema + validation
            |
            v
    controller adapter
            |
            +--> read-only queries
            |
            +--> deterministic plan
                         |
                         +--> explicit CLI apply
                         |
                         +--> optional MCP plan/apply adapter

The plan is the safety boundary. Interfaces must not construct their own
mutating API calls outside the plan engine.

## Safety rules

- read-only operations are the default;
- a plan must be printable and serializable before application;
- prune is opt-in and requires an explicit confirmation;
- credentials never appear in logs, plans or exceptions;
- self-signed TLS is an explicit setting, never the default;
- controller compatibility is recorded per resource and endpoint;
- an MCP server does not receive write capability unless the operator enables it.

## Configuration model

The public model starts with networks and WLANs. Firewall, DNS, NAT, VPN and
device actions are separate resource families, added only with fixtures and
rollback behavior.

The schema is versioned. Unknown top-level fields should fail validation so a
typo cannot silently produce a partial network configuration.
