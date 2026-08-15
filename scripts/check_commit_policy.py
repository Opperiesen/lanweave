"""Reject commit trailers and generated-agent signatures in CI."""

from __future__ import annotations

import re
import subprocess
import sys
from collections.abc import Iterable

FORBIDDEN_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("Co-authored-by trailer", re.compile(r"(?im)^\s*co-authored-by\s*:")),
    ("Git trailer", re.compile(r"(?im)^\s*(?:signed-off-by|reviewed-by|tested-by)\s*:")),
    (
        "generation marker",
        re.compile(r"(?im)^\s*(?:generated|created|written)\s+(?:by|with)\b"),
    ),
    ("agent signature", re.compile(r"(?i)\b(?:codex|copilot|chatgpt)\b")),
)


def _commits(base_sha: str, head_sha: str) -> Iterable[tuple[str, str]]:
    if not head_sha:
        raise SystemExit("commit policy: HEAD_SHA is required")

    zero_sha = "0" * 40
    if not base_sha or base_sha == zero_sha:
        revision = head_sha
        command = ["git", "log", "-1", "--format=%H%x00%B", revision]
    else:
        revision = f"{base_sha}..{head_sha}"
        command = ["git", "log", "--format=%H%x00%B", revision]

    result = subprocess.run(command, check=True, text=True, capture_output=True)
    fields = result.stdout.split("\x00")
    for index in range(0, len(fields) - 1, 2):
        commit_sha = fields[index].strip()
        message = fields[index + 1]
        if commit_sha:
            yield commit_sha, message


def _violations(message: str) -> list[str]:
    return [label for label, pattern in FORBIDDEN_PATTERNS if pattern.search(message)]


def main() -> int:
    if len(sys.argv) != 3:
        raise SystemExit("usage: check_commit_policy.py BASE_SHA HEAD_SHA")

    violations: list[tuple[str, list[str]]] = []
    for commit_sha, message in _commits(sys.argv[1], sys.argv[2]):
        reasons = _violations(message)
        if reasons:
            violations.append((commit_sha, reasons))

    if violations:
        for commit_sha, reasons in violations:
            print(f"forbidden commit metadata in {commit_sha}: {', '.join(reasons)}")
        return 1

    print("commit policy: no forbidden trailers or generated-agent signatures found")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
