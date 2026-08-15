# Apply recovery

Lanweave applies the classic UniFi API one request at a time. The API is not
transactional, so `apply` never claims to provide an automatic rollback.
Lanweave stops at the first failed operation and reports what it knows instead
of hiding a partial change.

## Execution order

The plan engine uses this dependency-safe order:

1. create or update networks;
2. refresh network and WLAN inventory;
3. delete WLANs;
4. create or update WLANs;
5. delete networks.

This ensures a WLAN can reference a network before it is written, and that a
network is not deleted before its dependent WLANs have been removed. Operations
after the failure are not started.

## Failure report

A failed apply reports a sanitized target, resource, operation and phase. It
does not include request payloads, response bodies, credentials or exception
text. With `--output json`, the report has this shape:

```json
{
  "error": "plan_apply_failed",
  "target": "controller=controller.example site=default",
  "failed": {
    "resource": "wlan/Home",
    "operation": "create",
    "phase": "wlan"
  },
  "state": "partial",
  "confirmed_completed": ["network/Home:create"],
  "uncertain_failed": "wlan/Home:create",
  "not_started": ["wlan/Guest:create"],
  "automatic_rollback": false
}
```

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
