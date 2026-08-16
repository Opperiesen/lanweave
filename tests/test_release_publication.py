from __future__ import annotations

import hashlib
import runpy
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[1] / "scripts/verify_publication.py"


def _publication_module() -> dict:
    return runpy.run_path(str(SCRIPT), run_name="lanweave_verify_publication")


def test_expected_public_release_assets_are_stable() -> None:
    expected_assets = _publication_module()["_expected_assets"]

    assert expected_assets("1.0.0") == (
        "lanweave-1.0.0-py3-none-any.whl",
        "lanweave-1.0.0.tar.gz",
        "SHA256SUMS",
        "lanweave-1.0.0-provenance.intoto.jsonl",
    )


def test_release_checksums_cover_exactly_the_two_distributions(tmp_path: Path) -> None:
    verify_checksums = _publication_module()["_verify_checksums"]
    wheel = tmp_path / "lanweave-1.0.0-py3-none-any.whl"
    sdist = tmp_path / "lanweave-1.0.0.tar.gz"
    wheel.write_bytes(b"wheel")
    sdist.write_bytes(b"sdist")
    wheel_digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
    sdist_digest = hashlib.sha256(sdist.read_bytes()).hexdigest()
    (tmp_path / "SHA256SUMS").write_text(
        f"{wheel_digest}  {wheel.name}\n{sdist_digest}  {sdist.name}\n",
        encoding="utf-8",
    )

    verify_checksums(tmp_path, "1.0.0")


def test_release_checksums_reject_unexpected_entries(tmp_path: Path) -> None:
    verify_checksums = _publication_module()["_verify_checksums"]
    (tmp_path / "lanweave-1.0.0-py3-none-any.whl").write_bytes(b"wheel")
    (tmp_path / "lanweave-1.0.0.tar.gz").write_bytes(b"sdist")
    (tmp_path / "extra.txt").write_bytes(b"extra")
    (tmp_path / "SHA256SUMS").write_text(
        "0" * 64 + "  extra.txt\n",
        encoding="utf-8",
    )

    with pytest.raises(SystemExit, match="exactly the wheel and source distribution"):
        verify_checksums(tmp_path, "1.0.0")
