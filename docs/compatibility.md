# Compatibility

Lanweave 0.1 targets the classic local UniFi Network API exposed below
`/proxy/network/api`. The adapter uses the current site selected by
`UNIFI_SITE` (default: `default`) and prefers an `X-API-Key` when one is
available.

## Supported in 0.1

| Area | Endpoints used | Capability |
| --- | --- | --- |
| Health | `stat/health` | read |
| Devices | `stat/device` | read |
| Clients | `stat/sta` | read |
| Networks | `rest/networkconf` | read, create, update, delete |
| WLANs | `rest/wlanconf` | read, create, update, delete |
| Backup | common `stat/*` and `rest/*` endpoints | redacted read |

The exact fields returned by UniFi can vary between Network application
versions. Lanweave keeps the API payload adapter narrow and ignores fields it
does not own when comparing declarative resources.

## Authentication and TLS

- API-key authentication is preferred.
- Username/password session authentication is available as a fallback.
- TLS certificate verification is enabled by default.
- `UNIFI_VERIFY_TLS=false` is an explicit escape hatch for local certificates.

The official cloud API is not claimed as compatible by this release. A future
adapter may support it once the authentication and resource semantics are
covered by fixtures and integration tests.

## Reporting a controller difference

Please include the UniFi Network application/controller version, the command
that failed, a redacted response or fixture, and whether the request used an
API key or session authentication. Never attach credentials, private keys,
Wi-Fi passphrases, public IPs or a raw controller backup.
