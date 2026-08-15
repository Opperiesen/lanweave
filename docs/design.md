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
                         +--> optional read-only MCP adapter

The plan is the safety boundary. Interfaces must not construct their own
mutating API calls outside the plan engine.

## Safety rules

- read-only operations are the default;
- a plan must be printable and serializable before application;
- prune is opt-in and requires an explicit confirmation;
- credentials never appear in logs, plans or exceptions;
- apply failures report confirmed, uncertain and not-started operations without
  payloads or exception bodies; no automatic rollback is claimed;
- self-signed TLS is an explicit setting, never the default;
- controller compatibility is recorded per resource and endpoint;
- the MCP server receives no write capability in the public product.

## Configuration model

The public model starts with networks and WLANs. Firewall, DNS, NAT, VPN and
device actions are separate resource families, added only with fixtures and
rollback behavior.

The schema is versioned. Unknown top-level fields should fail validation so a
typo cannot silently produce a partial network configuration.

The v1 configuration, CLI, plan JSON and read-only MCP contracts are frozen in
[contracts.md](contracts.md). Breaking changes require an explicit version and
migration decision.

The local multi-controller and multi-site profile design for `v0.2.0` is in
[profiles.md](profiles.md). Profile resolution is a separate boundary from
resource validation and planning: consumers receive one explicit target and
must not discover or choose another controller implicitly.
