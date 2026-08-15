from pathlib import Path

import pytest

from unifi_tools.config import EXAMPLE_CONFIG, ConfigError, load_config, validate_config


def test_example_configuration_is_valid() -> None:
    import yaml

    config = yaml.safe_load(EXAMPLE_CONFIG)
    validate_config(config)


def test_load_config_from_file(tmp_path: Path) -> None:
    path = tmp_path / "network.yaml"
    path.write_text(EXAMPLE_CONFIG, encoding="utf-8")

    config = load_config(path)

    assert config["version"] == 1
    assert len(config["networks"]) == 2


def test_literal_password_is_rejected() -> None:
    import yaml

    config = yaml.safe_load(EXAMPLE_CONFIG)
    config["wlans"][0]["password"] = "do-not-commit-this"

    with pytest.raises(ConfigError, match="environment placeholder"):
        validate_config(config)


def test_unknown_wlan_network_is_rejected() -> None:
    import yaml

    config = yaml.safe_load(EXAMPLE_CONFIG)
    config["wlans"][0]["network"] = "Missing"

    with pytest.raises(ConfigError, match="unknown network"):
        validate_config(config)
