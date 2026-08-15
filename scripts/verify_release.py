"""Verify that a release tag is annotated, points at HEAD and matches pyproject."""

from __future__ import annotations

import re
import subprocess
import sys
import tomllib
from pathlib import Path

TAG_PATTERN = re.compile(r"^v\d+\.\d+\.\d+(?:(?:a|b|rc)\d+)?$")


def _git(*args: str) -> str:
    result = subprocess.run(["git", *args], check=True, text=True, capture_output=True)
    return result.stdout.strip()


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: verify_release.py TAG")

    tag = sys.argv[1]
    if not TAG_PATTERN.fullmatch(tag):
        raise SystemExit(f"release verification: unsupported tag format: {tag}")

    if _git("cat-file", "-t", tag) != "tag":
        raise SystemExit("release verification: release tags must be annotated tags")

    tag_commit = _git("rev-parse", f"{tag}^{{}}")
    head_commit = _git("rev-parse", "HEAD")
    if tag_commit != head_commit:
        raise SystemExit(
            "release verification: tag does not point at the checked-out commit "
            f"({tag_commit} != {head_commit})"
        )

    with Path("pyproject.toml").open("rb") as pyproject_file:
        project = tomllib.load(pyproject_file)["project"]
    version = project["version"]
    expected_version = tag.removeprefix("v")
    if version != expected_version:
        raise SystemExit(
            "release verification: tag and project versions differ "
            f"({expected_version} != {version})"
        )

    print(f"release verification: {tag} -> {tag_commit} -> version {version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
