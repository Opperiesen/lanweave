from __future__ import annotations

from pathlib import Path

import pytest

from lanweave.config import load_config
from lanweave.profiles import list_profile_identities

ROOT = Path(__file__).parents[1]
EXAMPLES = tuple(sorted((ROOT / "examples").glob("*.yaml")))


@pytest.mark.parametrize("example_path", EXAMPLES, ids=lambda path: path.name)
def test_public_yaml_examples_validate(example_path: Path) -> None:
    config = load_config(example_path)
    assert config["version"] in {1, 2}
    if config["version"] == 2:
        assert list_profile_identities(config)


def test_v1_onboarding_runbook_covers_the_stable_operator_path() -> None:
    document = (ROOT / "docs/onboarding-v1.0.md").read_text(encoding="utf-8")
    for marker in (
        "lanweave validate",
        "lanweave capabilities",
        "lanweave export",
        "lanweave plan",
        "lanweave audit",
        "lanweave apply",
        "lanweave-mcp",
        "converged",
        "uncertain",
    ):
        assert marker in document
