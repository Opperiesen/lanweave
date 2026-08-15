from pathlib import Path

import pytest

from lanweave.config import (
    EXAMPLE_CONFIG,
    ConfigError,
    load_config,
    load_config_with_options,
    validate_config,
)
from lanweave.contracts import CONFIG_SCHEMA_VERSION


def test_example_configuration_is_valid() -> None:
    import yaml

    config = yaml.safe_load(EXAMPLE_CONFIG)
    validate_config(config)


def test_load_config_from_file(tmp_path: Path) -> None:
    path = tmp_path / "network.yaml"
    path.write_text(EXAMPLE_CONFIG, encoding="utf-8")

    config = load_config(path)

    assert config["version"] == CONFIG_SCHEMA_VERSION
    assert len(config["networks"]) == 2


def test_minimal_version_one_configuration_remains_valid() -> None:
    validate_config(
        {
            "version": CONFIG_SCHEMA_VERSION,
            "controller": {"site": "default"},
            "networks": [],
            "wlans": [],
        }
    )


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


def test_unknown_top_level_field_is_rejected() -> None:
    import yaml

    config = yaml.safe_load(EXAMPLE_CONFIG)
    config["typo"] = True

    with pytest.raises(ConfigError, match="unsupported top-level"):
        validate_config(config)


def test_unknown_resource_field_is_rejected() -> None:
    import yaml

    config = yaml.safe_load(EXAMPLE_CONFIG)
    config["networks"][0]["mistyped_dhcp"] = True

    with pytest.raises(ConfigError, match=r"unsupported field.*networks\[0\]"):
        validate_config(config)


def test_open_wlan_cannot_carry_a_password() -> None:
    import yaml

    config = yaml.safe_load(EXAMPLE_CONFIG)
    config["wlans"][0]["security"] = "open"

    with pytest.raises(ConfigError, match="must not define a password"):
        validate_config(config)


def test_password_env_is_resolved_only_when_requested(tmp_path: Path) -> None:
    path = tmp_path / "network.yaml"
    path.write_text(EXAMPLE_CONFIG, encoding="utf-8")
    environment = {
        "WIFI_HOME_PASSWORD": "home-secret",
        "WIFI_IOT_PASSWORD": "iot-secret",
    }

    unresolved = load_config(path)
    resolved = load_config_with_options(path, resolve_secrets=True, environ=environment)

    assert unresolved["wlans"][0]["password_env"] == "WIFI_HOME_PASSWORD"
    assert "password" not in unresolved["wlans"][0]
    assert resolved["wlans"][0]["password"] == "home-secret"
    assert "password_env" not in resolved["wlans"][0]


def test_empty_password_environment_variable_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "network.yaml"
    path.write_text(EXAMPLE_CONFIG, encoding="utf-8")

    with pytest.raises(ConfigError, match="environment variable WIFI_HOME_PASSWORD is empty"):
        load_config_with_options(
            path,
            resolve_secrets=True,
            environ={"WIFI_HOME_PASSWORD": "", "WIFI_IOT_PASSWORD": "iot-secret"},
        )
