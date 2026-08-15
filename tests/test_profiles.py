from pathlib import Path

import pytest
import yaml

from lanweave.client import CredentialsError
from lanweave.config import ConfigError
from lanweave.profiles import TargetIdentity, resolve_target, validate_profile_document

ROOT = Path(__file__).parents[1]
V2_FIXTURE = ROOT / "tests/fixtures/profiles/config-v2-multi-target.yaml"


def _v2_config() -> dict:
    return yaml.safe_load(V2_FIXTURE.read_text(encoding="utf-8"))


def _environment() -> dict[str, str]:
    return {
        "UNIFI_HOST": "https://legacy.example",
        "UNIFI_SITE": "legacy-site",
        "UNIFI_API_KEY": "legacy-key",
        "LANWEAVE_LOCAL_HOST": "https://local.example",
        "LANWEAVE_LOCAL_API_KEY": "local-key",
        "LANWEAVE_BACKUP_HOST": "https://backup.example",
        "LANWEAVE_BACKUP_USER": "backup-user",
        "LANWEAVE_BACKUP_PASSWORD": "backup-password",
    }


def test_v1_configuration_keeps_legacy_environment_and_site_precedence() -> None:
    config = yaml.safe_load(
        (ROOT / "tests/fixtures/profiles/config-v1.yaml").read_text(encoding="utf-8")
    )

    resolved = resolve_target(config, environ=_environment())

    assert resolved.settings.host == "https://legacy.example"
    assert resolved.settings.site == "default"
    assert resolved.settings.api_key == "legacy-key"
    assert resolved.identity == TargetIdentity("legacy", "legacy", "default")
    assert "legacy-key" not in repr(resolved)


def test_no_configuration_resolves_the_legacy_target() -> None:
    resolved = resolve_target(environ=_environment())

    assert resolved.identity == TargetIdentity("legacy", "legacy", "legacy-site")
    assert resolved.settings.site == "legacy-site"


def test_v2_configuration_resolves_the_declared_profile() -> None:
    resolved = resolve_target(_v2_config(), environ=_environment())

    assert resolved.identity == TargetIdentity("office", "local", "default")
    assert resolved.target_dict() == {
        "profile": "office",
        "controller": "local",
        "site": "default",
    }
    assert resolved.settings.host == "https://local.example"
    assert resolved.settings.api_key == "local-key"
    assert "local-key" not in resolved.identity.label()


def test_v2_session_credentials_are_loaded_from_environment() -> None:
    config = _v2_config()
    config["profile"] = "backup-default"

    resolved = resolve_target(config, environ=_environment())

    assert resolved.identity == TargetIdentity("backup-default", "backup", "default")
    assert resolved.settings.username == "backup-user"
    assert resolved.settings.password == "backup-password"


def test_profile_selection_conflict_is_rejected_before_credentials_are_loaded() -> None:
    config = _v2_config()
    config["profile"] = "office"

    with pytest.raises(ConfigError, match="conflicting profile selectors"):
        resolve_target(config, profile="guest", environ={})


def test_environment_profile_selects_when_configuration_has_no_selector() -> None:
    config = _v2_config()
    del config["profile"]
    environment = _environment()
    environment["LANWEAVE_PROFILE"] = "guest"

    resolved = resolve_target(config, environ=environment)

    assert resolved.identity == TargetIdentity("guest", "local", "guest")


def test_v2_without_an_effective_profile_is_rejected() -> None:
    config = _v2_config()
    del config["profile"]

    with pytest.raises(ConfigError, match="requires an explicit profile"):
        resolve_target(config, environ=_environment())


def test_missing_profile_credentials_fail_without_echoing_a_secret() -> None:
    config = _v2_config()
    environment = _environment()
    del environment["LANWEAVE_LOCAL_API_KEY"]

    with pytest.raises(CredentialsError) as caught:
        resolve_target(config, environ=environment)

    assert "LANWEAVE_LOCAL_API_KEY" in str(caught.value)
    assert "local-key" not in str(caught.value)


def test_literal_profile_credentials_are_rejected() -> None:
    config = _v2_config()
    config["controllers"]["local"]["auth"] = {"api_key": "literal-secret"}

    with pytest.raises(ConfigError, match="unsupported field") as caught:
        validate_profile_document(config)

    assert "literal-secret" not in str(caught.value)


def test_invalid_auth_form_and_unknown_controller_are_rejected() -> None:
    config = _v2_config()
    config["controllers"]["local"]["auth"] = {
        "api_key_env": "LANWEAVE_LOCAL_API_KEY",
        "username_env": "LANWEAVE_LOCAL_USER",
        "password_env": "LANWEAVE_LOCAL_PASSWORD",
    }

    with pytest.raises(ConfigError, match="exactly one"):
        validate_profile_document(config)

    config = _v2_config()
    config["profiles"]["office"]["controller"] = "missing"
    with pytest.raises(ConfigError, match="unknown controller"):
        validate_profile_document(config)


def test_profile_argument_is_rejected_for_version_one() -> None:
    config = yaml.safe_load(
        (ROOT / "tests/fixtures/profiles/config-v1.yaml").read_text(encoding="utf-8")
    )

    with pytest.raises(ConfigError, match="not supported"):
        resolve_target(config, profile="default", environ=_environment())
