## Summary

<!-- What changed and why? Keep this focused on one reviewable outcome. -->

## Validation

- [ ] `uv run ruff check .`
- [ ] `uv run pytest -q`
- [ ] Documentation and compatibility notes updated when relevant

## Safety review

- [ ] No credentials, real exports, backups, MAC addresses, hostnames or private topology included
- [ ] Read-only and mutating paths remain clearly separated
- [ ] Destructive behavior, if any, is covered by tests and explicit confirmation

## Reviewer notes

<!-- Mention controller versions, fixtures, trade-offs or follow-up issues. -->
