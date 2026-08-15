# Roadmap

Lanweave is deliberately narrow in its first public release. The roadmap is
organized around safe, tested operator value rather than endpoint count.

## Current release — 0.1 alpha

- local classic UniFi Network API adapter;
- declarative networks and WLANs;
- validate, export, plan, apply and redacted backup workflows;
- health and client views;
- read-only MCP tools;
- public CI, security policy and contribution workflow.

## Next

- publish signed wheels to PyPI once the compatibility matrix has real
  controller coverage;
- add multi-site and multi-controller profiles without putting credentials in
  YAML;
- add an explicit adapter for the official cloud API when its resource
  semantics can be covered by fixtures;
- expand resource families one at a time with dependency ordering and a
  rollback story;
- add a disposable-controller integration workflow.

## Non-goals

- a hosted relay or telemetry service;
- a full replacement for the UniFi administration UI;
- write-capable MCP tools without an independent, reviewable approval model;
- copying private household topology, exports or operational history into the
  public project.

Concrete work is tracked in the [GitHub issues](https://github.com/Opperiesen/lanweave/issues).
