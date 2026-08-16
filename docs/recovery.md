# Apply recovery

Lanweave applies controller changes one request at a time across the classic
and local Integration APIs. These APIs are not transactional, so `apply` never
claims to provide an automatic rollback.
Lanweave stops at the first failed operation and reports what it knows instead
of hiding a partial change.

## Execution order

The plan engine uses this dependency-safe order:

1. create or update networks;
2. create or update DNS policies;
3. create or update firewall zones;
4. create or update firewall groups;
5. create or update firewall rules;
6. create or update supported NAT mappings;
7. delete WLANs;
8. delete user-managed DNS policies;
9. delete user-managed NAT mappings;
10. delete firewall rules;
11. reorder firewall policies;
12. create or update WLANs;
13. delete firewall groups and zones;
14. delete networks.

## VPN resources

VPN resources in v0.7.0 are read-only observations, not apply operations. A
plan containing `read_only.vpn` is rejected by `lanweave apply` before any
controller write, so there is no VPN partial-apply or rollback state to infer.
If a VPN overview request fails, retry with the same API-key capability after
checking the controller version; do not replace missing routes or handshakes
with guessed values. The safe recovery artifact is a fresh `lanweave vpn
--output json` read and, when useful, a secret-free `lanweave export`.

This ensures a WLAN can reference a network before it is written, and that a
network is not deleted before its dependent WLANs have been removed. Operations
after the failure are not started.

DNS policies are independent of networks and WLANs in v0.4. Their writes run
before DNS deletes, and only records whose controller metadata identifies a
user-managed origin can be updated or pruned. System and unknown-origin records
are retained. DNS writes are available only through the local API-key
Integration API endpoint; session-authenticated adapters fail before mutation.

Firewall writes are independent of DNS but use the same one-request-at-a-time
boundary. Zone and group IDs are refreshed before rule writes, and zone/policy
IDs are read again before a reorder. Rules, groups and zones with unknown or
protected origins are never implicit prune targets. An apply containing
firewall warnings also requires the explicit risk acknowledgement described in
[`firewall.md`](firewall.md).

NAT writes run after firewall rule writes and before user-managed NAT deletes.
The local classic adapter supports only the proven IPv4 payload subset and
requires session authentication. Because the classic endpoint omits ownership
metadata, IDs created successfully in the current client session are the only
same-session ownership evidence; a later fresh client treats them as unknown.
Public WAN boundaries, broad sources, privileged ports and unproven firewall
dependencies remain visible risk warnings. Unknown or system-origin mappings
are never prune targets. A NAT request that fails is uncertain until a fresh
inventory and newly reviewed plan confirm the live state.

## Failure report

A failed apply reports a sanitized target, resource, operation and phase. It
does not include request payloads, response bodies, credentials or exception
text. With `--output json`, the report has this shape:

```json
{
  "error": "plan_apply_failed",
  "target": "profile=office controller=local site=default",
  "failed": {
    "resource": "dns/printer.home.arpa [A]",
    "operation": "create",
    "phase": "dns"
  },
  "state": "partial",
  "confirmed_completed": ["dns/old.home.arpa [A]:create"],
  "uncertain_failed": "dns/printer.home.arpa [A]:create",
  "not_started": ["dns/portal.home.arpa [CNAME]:create"],
  "automatic_rollback": false
}
```

For plans produced from a version-2 profile, the target label comes from the
plan identity and contains only `profile`, `controller` and `site`. A target
mismatch is rejected before mutation with the deterministic error code
`plan_target_mismatch`; its report contains the expected and selected
non-secret identities. Plans from the version-1 line may omit that identity and
retain the legacy `controller=<host> site=<site>` failure label.

The state model is deliberately conservative:

- `confirmed_completed` contains operations whose request completed
  successfully;
- `uncertain_failed` identifies the request that stopped the plan. The
  controller may have applied it before returning an error or losing the
  connection;
- `not_started` contains operations Lanweave did not attempt;
- `state=partial` means an earlier operation was confirmed or a multi-request
  resource had already been created; `state=unknown` means no change was
  confirmed before the failure.

For a WLAN create, the classic API can acknowledge the initial create and
still fail during the follow-up configuration request. In that case the WLAN
is reported as an uncertain partial resource. The report describes the known
state; it does not pretend to know whether the controller committed a failed
request.

## Safe retry

After a failure, re-read the controller and generate a fresh plan before
retrying:

```shell
lanweave plan --config config/network.yaml
lanweave apply --config config/network.yaml
```

Review the new plan rather than blindly repeating the old request. Networks
and WLANs are matched by name when planning, so a resource created before a
failure is normally reconciled as an update or becomes a no-op on the next
plan. If the controller returns incomplete or duplicate objects, resolve that
ambiguity in the UniFi UI first and then generate another plan.

`--prune` remains opt-in after a failure. Review all deletes and provide the
normal prune confirmation; never add `--prune` merely as a recovery shortcut.

## Prune failures

WLAN deletes run before network deletes. If a WLAN deletion succeeds and its
network deletion fails, the resulting state is intentionally reported as a
confirmed WLAN deletion, an uncertain or failed network deletion, and no
remaining network operations. The network is not automatically recreated or
deleted again. Re-run the plan after inspection; the next plan will show the
network if it still exists.

If a delete request times out, treat its result as uncertain even when the UI
appears unchanged. Confirm the live state before retrying. A redacted
`lanweave backup` or `lanweave export --out live.yaml` can preserve a local
read-only snapshot for the operator, but neither is an automatic rollback
mechanism.

## Recovery boundary

Lanweave provides deterministic ordering, sanitized failure facts and manual
recovery instructions. It does not provide compensation, transaction emulation
or automatic rollback for networks or WLANs. Recovery is an operator-reviewed
read, plan and retry cycle, with the UniFi UI available for resolving an
ambiguous or unsafe partial state.
