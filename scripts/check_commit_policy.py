"""Reject unsafe metadata and non-GitHub commit identities in CI."""

from __future__ import annotations

import re
import subprocess
import sys
from collections.abc import Iterable

EXPECTED_GITHUB_AUTHOR_EMAIL = "77763298+Opperiesen@users.noreply.github.com"
ALLOWED_COMMITTER_EMAILS = frozenset({EXPECTED_GITHUB_AUTHOR_EMAIL, "noreply@github.com"})

FORBIDDEN_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("Co-authored-by trailer", re.compile(r"(?im)^\s*co-authored-by\s*:")),
    ("Git trailer", re.compile(r"(?im)^\s*(?:signed-off-by|reviewed-by|tested-by)\s*:")),
    (
        "generation marker",
        re.compile(r"(?im)^\s*(?:generated|created|written)\s+(?:by|with)\b"),
    ),
    ("agent signature", re.compile(r"(?i)\b(?:codex|copilot|chatgpt)\b")),
)


def _commits(base_sha: str, head_sha: str) -> Iterable[tuple[str, str, str, str]]:
    if not head_sha:
        raise SystemExit("commit policy: HEAD_SHA is required")

    zero_sha = "0" * 40
    if not base_sha or base_sha == zero_sha:
        revision = head_sha
        command = ["git", "log", "-1", "--format=%H%x00%ae%x00%ce%x00%B%x00", revision]
    else:
        revision = f"{base_sha}..{head_sha}"
        command = ["git", "log", "--format=%H%x00%ae%x00%ce%x00%B%x00", revision]

    result = subprocess.run(command, check=True, text=True, capture_output=True)
    fields = result.stdout.split("\x00")
    for index in range(0, len(fields) - 1, 4):
        commit_sha = fields[index].strip()
        author_email = fields[index + 1].strip()
        committer_email = fields[index + 2].strip()
        message = fields[index + 3]
        if commit_sha:
            yield commit_sha, author_email, committer_email, message


def _violations(message: str) -> list[str]:
    return [label for label, pattern in FORBIDDEN_PATTERNS if pattern.search(message)]


def _identity_violations(author_email: str, committer_email: str) -> list[str]:
    violations: list[str] = []
    if author_email != EXPECTED_GITHUB_AUTHOR_EMAIL:
        violations.append("author is not the Opperiesen GitHub noreply identity")
    if committer_email not in ALLOWED_COMMITTER_EMAILS:
        violations.append("committer is not the Opperiesen GitHub identity")
    return violations


def main() -> int:
    if len(sys.argv) != 3:
        raise SystemExit("usage: check_commit_policy.py BASE_SHA HEAD_SHA")

    violations: list[tuple[str, list[str]]] = []
    for commit_sha, author_email, committer_email, message in _commits(sys.argv[1], sys.argv[2]):
        reasons = _violations(message) + _identity_violations(author_email, committer_email)
        if reasons:
            violations.append((commit_sha, reasons))

    if violations:
        for commit_sha, reasons in violations:
            print(f"forbidden commit metadata in {commit_sha}: {', '.join(reasons)}")
        return 1

    print("commit policy: metadata and GitHub identity checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
