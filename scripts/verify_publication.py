"""Verify the public metadata and attestations of a Lanweave release."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

TAG_PATTERN = re.compile(r"^v\d+\.\d+\.\d+(?:(?:a|b|rc)\d+)?$")
PYPI_PROJECT = "lanweave"
PYPI_BASE_URL = "https://pypi.org"
PROVENANCE_RETRIES = 12
PROVENANCE_RETRY_SECONDS = 5


def _fail(message: str) -> None:
    raise SystemExit(f"publication verification: {message}")


def _gh_api(repository: str, endpoint: str) -> dict:
    result = subprocess.run(
        ["gh", "api", f"repos/{repository}/{endpoint}"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        _fail(f"GitHub API request failed for {endpoint}: {detail}")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        _fail(f"GitHub API returned invalid JSON for {endpoint}: {exc}")


def _fetch_json(url: str, *, retries: int = 1) -> dict:
    for attempt in range(retries):
        try:
            request = Request(url, headers={"Accept": "application/json"})
            with urlopen(request, timeout=30) as response:  # noqa: S310
                return json.load(response)
        except HTTPError as exc:
            if exc.code != 404 or attempt == retries - 1:
                _fail(f"HTTP {exc.code} while reading {url}")
        except (URLError, TimeoutError, json.JSONDecodeError) as exc:
            if attempt == retries - 1:
                _fail(f"could not read {url}: {exc}")
        time.sleep(PROVENANCE_RETRY_SECONDS)
    _fail(f"could not read {url}")


def _expected_assets(version: str) -> tuple[str, ...]:
    return (
        f"lanweave-{version}-py3-none-any.whl",
        f"lanweave-{version}.tar.gz",
        "SHA256SUMS",
        f"lanweave-{version}-provenance.intoto.jsonl",
    )


def _verify_tag(repository: str, tag: str, expected_commit: str) -> None:
    reference = _gh_api(repository, f"git/ref/tags/{tag}")
    reference_object = reference.get("object", {})
    if reference_object.get("type") != "tag":
        _fail(f"{tag} is not an annotated tag")

    tag_object = _gh_api(repository, f"git/tags/{reference_object.get('sha', '')}")
    target = tag_object.get("object", {})
    if target.get("type") != "commit":
        _fail(f"annotated tag {tag} does not target a commit")
    if target.get("sha") != expected_commit:
        _fail(
            f"tag {tag} targets {target.get('sha')}, expected checked-out commit {expected_commit}"
        )


def _verify_release(repository: str, tag: str, version: str) -> None:
    release = _gh_api(repository, f"releases/tags/{tag}")
    if release.get("draft") is not False:
        _fail("GitHub Release is still a draft")
    expected_prerelease = bool(re.search(r"(?:a|b|rc)\d+$", tag))
    if release.get("prerelease") != expected_prerelease:
        _fail("GitHub Release prerelease flag does not match the tag")
    if not release.get("published_at"):
        _fail("GitHub Release has no publication timestamp")

    asset_names = {asset.get("name") for asset in release.get("assets", [])}
    missing = sorted(set(_expected_assets(version)) - asset_names)
    if missing:
        _fail(f"GitHub Release is missing assets: {', '.join(missing)}")


def _checksum_entries(checksum_path: Path) -> dict[str, str]:
    entries: dict[str, str] = {}
    for line in checksum_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        digest, filename = line.split(maxsplit=1)
        entries[filename.removeprefix("*")] = digest
    return entries


def _verify_checksums(asset_dir: Path, version: str) -> None:
    checksum_path = asset_dir / "SHA256SUMS"
    if not checksum_path.is_file():
        _fail("downloaded GitHub Release has no SHA256SUMS")

    expected_files = {
        f"lanweave-{version}-py3-none-any.whl",
        f"lanweave-{version}.tar.gz",
    }
    entries = _checksum_entries(checksum_path)
    if set(entries) != expected_files:
        _fail("SHA256SUMS does not contain exactly the wheel and source distribution")

    for filename, expected_digest in entries.items():
        path = asset_dir / filename
        if not path.is_file():
            _fail(f"checksum entry has no downloaded asset: {filename}")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != expected_digest:
            _fail(f"checksum mismatch for {filename}")


def _verify_pypi(version: str, asset_dir: Path) -> None:
    release = _fetch_json(f"{PYPI_BASE_URL}/pypi/{PYPI_PROJECT}/{version}/json")
    if release.get("info", {}).get("version") != version:
        _fail("PyPI reports a different project version")

    files = {item.get("filename"): item for item in release.get("urls", [])}
    expected_files = (
        f"lanweave-{version}-py3-none-any.whl",
        f"lanweave-{version}.tar.gz",
    )
    for filename in expected_files:
        metadata = files.get(filename)
        if metadata is None:
            _fail(f"PyPI is missing {filename}")
        local_digest = hashlib.sha256((asset_dir / filename).read_bytes()).hexdigest()
        if metadata.get("digests", {}).get("sha256") != local_digest:
            _fail(f"PyPI digest does not match the GitHub Release asset: {filename}")

        provenance_url = (
            f"{PYPI_BASE_URL}/integrity/{PYPI_PROJECT}/{version}/"
            f"{quote(filename, safe='')}/provenance"
        )
        provenance = _fetch_json(provenance_url, retries=PROVENANCE_RETRIES)
        bundles = provenance.get("attestation_bundles", [])
        if not bundles or not any(bundle.get("attestations") for bundle in bundles):
            _fail(f"PyPI has no attestations for {filename}")


def verify_publication(
    *,
    tag: str,
    repository: str,
    expected_commit: str,
    asset_dir: Path,
    verify_pypi: bool,
) -> None:
    if not TAG_PATTERN.fullmatch(tag):
        _fail(f"unsupported tag format: {tag}")
    version = tag.removeprefix("v")
    _verify_tag(repository, tag, expected_commit)
    _verify_release(repository, tag, version)
    _verify_checksums(asset_dir, version)
    if verify_pypi:
        _verify_pypi(version, asset_dir)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tag")
    parser.add_argument("repository")
    parser.add_argument("expected_commit")
    parser.add_argument("--asset-dir", type=Path, default=Path("release-assets"))
    parser.add_argument(
        "--skip-pypi",
        action="store_true",
        help="skip PyPI metadata and integrity-attestation checks for prereleases",
    )
    args = parser.parse_args()
    verify_publication(
        tag=args.tag,
        repository=args.repository,
        expected_commit=args.expected_commit,
        asset_dir=args.asset_dir,
        verify_pypi=not args.skip_pypi,
    )
    scope = (
        "GitHub Release, checksums and PyPI files/attestations"
        if not args.skip_pypi
        else "GitHub Release and checksums"
    )
    print(f"publication verification: {args.tag} tag and {scope} passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
