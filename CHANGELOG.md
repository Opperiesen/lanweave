# Changelog

## Unreleased

- no unreleased changes.

## 0.1.0b1 — 2026-08-15

- freeze configuration schema version 1 and publish its machine-readable
  contract;
- freeze CLI commands, options and exit-code behavior;
- version and document the redacted plan JSON format;
- document the six read-only MCP tools, parameters, return values and stable
  error codes;
- add explicit migration and deprecation rules for future breaking changes;
- expand smoke and contract tests across configuration, CLI, plan JSON and MCP.

## 0.1.0a2 — 2026-08-15

- enforce formatting and locked dependency/security audits in CI;
- exercise the optional MCP extra on the supported Python boundary versions;
- pin GitHub Actions to reviewed commit SHAs and disable checkout credential
  persistence;
- add a manually triggered, protected controller integration workflow with
  redacted compatibility reports;
- separate live read-only probes from an explicitly authorized mutation suite;
- publish designated-controller read-only compatibility evidence;
- route manual controller integration jobs through a dedicated LAN runner;
- support read-only UniFi v1 Integration API access with API keys;
- use a separate scoped session account for the authorized mutation suite;
- publish successful create/update/delete compatibility evidence on the
  designated controller;
- report partial apply state without payload or credential leakage and document
  deterministic manual recovery semantics.

## 0.1.0a1 — 2026-08-15

- initial public Lanweave package and Apache-2.0 project foundation;
- declarative networks and WLANs with validation and environment-backed
  secrets;
- deterministic redacted plan, explicit apply and opt-in prune;
- secret-free export, redacted local backup, health and client views;
- optional read-only MCP server over stdio;
- simulated controller tests and CI checks.
