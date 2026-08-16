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

The repository is currently maintained by one GitHub account. Branch
protection therefore requires a pull request and all required checks, while
the approval count remains zero; enabling mandatory approval will be the next
governance step when an independent maintainer is available.

## GitHub identity and commit messages

- push branches, open pull requests, merge, tag and publish releases through
  the `Opperiesen` GitHub account;
- new commit authors must use `77763298+Opperiesen@users.noreply.github.com`;
- GitHub's generated `noreply@github.com` committer is accepted for squash
  merges, while another committer identity is rejected by CI;
- never add `Co-authored-by`, `Signed-off-by` or other trailers;
- never mention an agent, generator or assistant in a commit message;
- the `commit-policy` CI check rejects these metadata patterns and identities
  before merge;
- two historical commits retain the old local Mac identity by explicit
  decision; history is not rewritten, and the policy applies to new changes.

The repository has one maintainer. Branch protection requires pull requests,
linear history, the complete required CI set, protected release tags and the
protected release environment; mandatory approving reviews remain at zero
until an independent maintainer is available. At that point the required
review count must be raised before broadening the stable release process.

## Scope

Small, composable changes are preferred. New resource families need a schema,
validation, plan behavior, API fixtures and a rollback story before they are
enabled by default.
