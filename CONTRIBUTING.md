# Contributing

## Development setup

    uv sync --extra dev
    uv run pytest
    uv run ruff check .
    uv run ruff format --check .

Unit tests must not require a live controller. Use httpx mock transports for
API behavior. Hardware compatibility tests belong in a separate, explicitly
opt-in workflow.

## Pull requests

- explain the resource or behavior being added;
- include fixtures and tests for API payloads;
- keep read-only and mutating paths separate;
- do not include real exports, backups, MAC addresses, hostnames or secrets;
- update the compatibility notes when an endpoint is controller-version-specific.

Open a focused branch from `main`, run the local checks, and open a pull
request with the provided template. Maintainers prefer small, reviewable
changes. A pull request should not require access to a live controller to run
its unit tests.

## Scope

Small, composable changes are preferred. New resource families need a schema,
validation, plan behavior, API fixtures and a rollback story before they are
enabled by default.
