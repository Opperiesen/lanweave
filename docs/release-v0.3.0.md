# Lanweave v0.3.0 release notes

Lanweave `v0.3.0` adds an explicit adapter architecture and a deliberately
small read-only integration with the official UniFi Site Manager API v1. It
preserves the local-first v0.2 behavior while making adapter selection and
capability limits visible before an operation starts.

## Included

- explicit `local-classic` and `cloud-site-manager` adapter identities;
- deterministic, versioned capability documents;
- offline `lanweave capabilities` CLI output;
- MCP contract v3 with `lanweave_get_capabilities`;
- adapter-aware local status, plans, exports and target-bound responses;
- fixture-backed Site Manager hosts, sites, devices and derived health reads;
- bounded pagination, TLS verification, API-key authentication and normalized
  rate-limit/transport failures;
- protected, manually triggered Site Manager read-only evidence workflow;
- protected real-account evidence for API v1.0.0: [workflow run
  31895015047](https://github.com/Opperiesen/lanweave/actions/runs/31895015047);
- migration, compatibility, redaction and release-gate documentation.

## Deliberate exclusions

Site Manager is read-only in v0.3.0. The release does not provide cloud client,
network, WLAN, backup, export, plan, apply, prune, configuration-management,
device-adoption or firmware operations. It does not scrape browser sessions,
reuse cookies, discover accounts automatically or provide a hosted relay.

The local classic adapter remains the only adapter with the v0.2 declarative
network/WLAN apply and prune behavior, subject to its authentication limits.

## Upgrade

Existing v0.2 local configurations continue to work unchanged. See
[`migration-v0.3.md`](migration-v0.3.md) for the optional cloud profile shape,
capability checks, MCP changes and rollback instructions.

## Protected evidence

The protected Site Manager workflow ran against a real UI account on `main`
with API v1.0.0. Both read-only inventory reachability and the no-mutation
capability guard passed. The uploaded report is sanitized and excludes the API
host, key, inventory names, topology and raw responses.

## Release verification

The release must be produced from an annotated `v0.3.0` tag and pass the
protected release workflow. Verify the published assets with:

```shell
gh release download v0.3.0 --repo Opperiesen/lanweave --dir release-v0.3.0
cd release-v0.3.0
sha256sum -c SHA256SUMS
gh attestation verify \
  lanweave-0.3.0-py3-none-any.whl \
  --repo Opperiesen/lanweave \
  --source-ref refs/tags/v0.3.0 \
  --signer-workflow Opperiesen/lanweave/.github/workflows/release.yml
```

PyPI publication uses Trusted Publishing and PEP 740 attestations. The
protected Site Manager evidence is linked above while keeping the API host,
key, inventory and raw responses private.
