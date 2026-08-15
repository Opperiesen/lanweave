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
3. refresh network and WLAN inventory when those resources are involved;
4. delete WLANs;
5. delete user-managed DNS policies;
6. create or update WLANs;
7. delete networks.

This ensures a WLAN can reference a network before it is written, and that a
network is not deleted before its dependent WLANs have been removed. Operations
after the failure are not started.

DNS policies are independent of networks and WLANs in v0.4. Their writes run
before DNS deletes, and only records whose controller metadata identifies a
user-managed origin can be updated or pruned. System and unknown-origin records
are retained. DNS writes are available only through the local API-key
Integration API endpoint; session-authenticated adapters fail before mutation.

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
