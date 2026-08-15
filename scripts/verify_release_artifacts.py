"""Verify the wheel and source distribution produced for a release."""

from __future__ import annotations

import sys
import tarfile
import zipfile
from pathlib import Path


def _fail(message: str) -> None:
    raise SystemExit(f"artifact verification: {message}")


def main() -> int:
    if len(sys.argv) != 3:
        raise SystemExit("usage: verify_release_artifacts.py VERSION DIST_DIR")

    version, dist_arg = sys.argv[1:]
    dist = Path(dist_arg)
    wheels = sorted(dist.glob(f"lanweave-{version}-*.whl"))
    sdists = sorted(dist.glob(f"lanweave-{version}.tar.gz"))
    if len(wheels) != 1:
        _fail(f"expected one wheel for {version}, found {len(wheels)}")
    if len(sdists) != 1:
        _fail(f"expected one source distribution for {version}, found {len(sdists)}")

    wheel = wheels[0]
    with zipfile.ZipFile(wheel) as archive:
        metadata_names = [name for name in archive.namelist() if name.endswith("/METADATA")]
        if len(metadata_names) != 1:
            _fail("wheel metadata is missing or ambiguous")
        metadata = archive.read(metadata_names[0]).decode("utf-8")
        if f"Version: {version}\n" not in metadata:
            _fail("wheel metadata version does not match the release")
        if "Provides-Extra: mcp\n" not in metadata:
            _fail("MCP is no longer exposed as an optional extra")
        if not any(
            line.startswith("Requires-Dist: mcp") and "extra ==" in line
            for line in metadata.splitlines()
        ):
            _fail("MCP dependency is not optional in wheel metadata")

    expected_root = f"lanweave-{version}/"
    with tarfile.open(sdists[0], "r:gz") as archive:
        names = archive.getnames()
        if not any(name.startswith(expected_root) for name in names):
            _fail("source distribution root directory is unexpected")
        if not any(
            name.startswith(expected_root) and name.endswith("/pyproject.toml") for name in names
        ):
            _fail("source distribution does not contain pyproject.toml")

    print(f"artifact verification: {wheel.name} and {sdists[0].name} are valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
