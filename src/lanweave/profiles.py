"""Resolve versioned local controller profiles into safe targets."""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from typing import Any

from dotenv import load_dotenv

from .adapters import (
    ADAPTER_CLOUD_SITE_MANAGER,
    ADAPTER_LOCAL_CLASSIC,
    AUTH_MODE_API_KEY,
    AUTH_MODE_SESSION,
)
from .client import ControllerSettings, CredentialsError
from .config import ConfigError, validate_config
from .contracts import PROFILE_LAYER_VERSION

PROFILE_SELECTOR_ENV = "LANWEAVE_PROFILE"
IDENTIFIER_RE = re.compile(r"^[a-z][a-z0-9-]{0,63}$")
ENV_NAME_RE = re.compile(r"^[A-Z_][A-Z0-9_]*$")
PROFILE_DOCUMENT_KEYS = {
    "version",
    "profile",
    "controllers",
    "profiles",
    "networks",
    "wlans",
    "dns",
    "firewall",
    "nat",
    "vpn",
}
CONTROLLER_PROFILE_KEYS = {"host_env", "verify_tls", "auth", "adapter"}
AUTH_PROFILE_KEYS = {"api_key_env", "username_env", "password_env"}
TARGET_IDENTITY_KEYS = ("profile", "controller", "site", "adapter")
SUPPORTED_ADAPTERS = frozenset({ADAPTER_CLOUD_SITE_MANAGER, ADAPTER_LOCAL_CLASSIC})


@dataclass(frozen=True)
class TargetIdentity:
    """Non-secret identity of the selected profile target."""

    profile: str
    controller: str
    site: str
    adapter: str = ADAPTER_LOCAL_CLASSIC

    def to_dict(self) -> dict[str, str]:
        return {key: getattr(self, key) for key in TARGET_IDENTITY_KEYS}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> TargetIdentity:
        """Load a target identity, defaulting legacy documents to local-classic."""
        document = _require_mapping(value, "target")
        _reject_unknown(document, set(TARGET_IDENTITY_KEYS), "target")
        profile = _validate_identifier(
            _require_string(document, "profile", "target"), "target.profile"
        )
        controller = _validate_identifier(
            _require_string(document, "controller", "target"), "target.controller"
        )
        site = _require_string(document, "site", "target")
        adapter = _validate_adapter(
            document.get("adapter", ADAPTER_LOCAL_CLASSIC), "target.adapter"
        )
        return cls(profile=profile, controller=controller, site=site, adapter=adapter)

    def label(self) -> str:
        return (
            f"profile={self.profile} controller={self.controller} "
            f"site={self.site} adapter={self.adapter}"
        )


@dataclass(frozen=True)
class ResolvedTarget:
    """A controller client configuration paired with its sanitized identity."""

    identity: TargetIdentity
    settings: ControllerSettings = field(repr=False)

    def target_dict(self) -> dict[str, str]:
        return self.identity.to_dict()


def _require_mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ConfigError(f"{label} must be a mapping")
    return value


def _require_string(mapping: Mapping[str, Any], key: str, label: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"{label}.{key} must be a non-empty string")
    return value


def _reject_unknown(mapping: Mapping[str, Any], allowed: set[str], label: str) -> None:
    unknown = sorted(set(mapping) - allowed, key=str)
    if unknown:
        names = ", ".join(str(name) for name in unknown)
        raise ConfigError(f"unsupported field(s) in {label}: {names}")


def _validate_identifier(value: Any, label: str) -> str:
    if not isinstance(value, str) or not IDENTIFIER_RE.fullmatch(value):
        raise ConfigError(f"{label} must match ^[a-z][a-z0-9-]{{0,63}}$")
    return value


def _validate_env_name(value: Any, label: str) -> str:
    if not isinstance(value, str) or not ENV_NAME_RE.fullmatch(value):
        raise ConfigError(f"{label} must be an uppercase environment variable name")
    return value


def _validate_adapter(value: Any, label: str) -> str:
    if not isinstance(value, str) or value not in SUPPORTED_ADAPTERS:
        allowed = ", ".join(sorted(SUPPORTED_ADAPTERS))
        raise ConfigError(f"{label} must be one of: {allowed}")
    return value


def _validate_auth(auth: Mapping[str, Any], label: str) -> None:
    _reject_unknown(auth, AUTH_PROFILE_KEYS, label)
    has_api_key = "api_key_env" in auth
    session_keys = {"username_env", "password_env"}
    has_any_session = bool(session_keys & set(auth))
    has_complete_session = session_keys <= set(auth)
    if (has_api_key and has_any_session) or (not has_api_key and not has_complete_session):
        raise ConfigError(
            f"{label} must define exactly one api_key_env or username_env/password_env form"
        )
    for key in AUTH_PROFILE_KEYS & set(auth):
        _validate_env_name(auth[key], f"{label}.{key}")


def validate_profile_document(config: Mapping[str, Any]) -> None:
    """Validate the version-2 profile layer without resolving credentials."""
    document = _require_mapping(config, "config")
    _reject_unknown(document, PROFILE_DOCUMENT_KEYS, "config")
    if document.get("version") != PROFILE_LAYER_VERSION:
        raise ConfigError(f"profile version must be {PROFILE_LAYER_VERSION}")

    if "profile" in document:
        _validate_identifier(document["profile"], "config.profile")

    controllers = _require_mapping(document.get("controllers"), "controllers")
    if not controllers:
        raise ConfigError("controllers must contain at least one controller")
    for name, raw_controller in controllers.items():
        controller_name = _validate_identifier(name, "controller name")
        controller = _require_mapping(raw_controller, f"controllers.{controller_name}")
        _reject_unknown(controller, CONTROLLER_PROFILE_KEYS, f"controllers.{controller_name}")
        _validate_adapter(
            controller.get("adapter", ADAPTER_LOCAL_CLASSIC),
            f"controllers.{controller_name}.adapter",
        )
        _validate_env_name(
            _require_string(controller, "host_env", f"controllers.{controller_name}"),
            f"controllers.{controller_name}.host_env",
        )
        verify_tls = controller.get("verify_tls", True)
        if not isinstance(verify_tls, bool):
            raise ConfigError(f"controllers.{controller_name}.verify_tls must be a boolean")
        _validate_auth(
            _require_mapping(controller.get("auth"), f"controllers.{controller_name}.auth"),
            f"controllers.{controller_name}.auth",
        )
        if (
            controller.get("adapter", ADAPTER_LOCAL_CLASSIC) == ADAPTER_CLOUD_SITE_MANAGER
            and "api_key_env" not in controller["auth"]
        ):
            raise ConfigError("cloud-site-manager requires auth.api_key_env")

    profiles = _require_mapping(document.get("profiles"), "profiles")
    if not profiles:
        raise ConfigError("profiles must contain at least one profile")
    for name, raw_profile in profiles.items():
        profile_name = _validate_identifier(name, "profile name")
        profile = _require_mapping(raw_profile, f"profiles.{profile_name}")
        _reject_unknown(profile, {"controller", "site"}, f"profiles.{profile_name}")
        controller_name = _validate_identifier(
            _require_string(profile, "controller", f"profiles.{profile_name}"),
            f"profiles.{profile_name}.controller",
        )
        if controller_name not in controllers:
            raise ConfigError(
                f"profiles.{profile_name}.controller refers to an unknown controller: "
                f"{controller_name}"
            )
        _require_string(profile, "site", f"profiles.{profile_name}")


def list_profile_identities(config: Mapping[str, Any]) -> tuple[TargetIdentity, ...]:
    """Return all declared target identities without loading credentials."""
    document = _require_mapping(config, "config")
    if document.get("version") == 1:
        validate_config(dict(document))
        site = str(document["controller"]["site"])
        return (TargetIdentity("legacy", "legacy", site),)
    if document.get("version") != PROFILE_LAYER_VERSION:
        raise ConfigError(f"unsupported profile configuration version: {document.get('version')}")
    validate_profile_document(document)
    controllers = _require_mapping(document["controllers"], "controllers")
    profiles = _require_mapping(document["profiles"], "profiles")
    identities: list[TargetIdentity] = []
    for name, raw in sorted(profiles.items()):
        profile = _require_mapping(raw, f"profiles.{name}")
        controller_name = _validate_identifier(
            _require_string(profile, "controller", f"profiles.{name}"),
            f"profiles.{name}.controller",
        )
        controller = _require_mapping(
            controllers[controller_name], f"controllers.{controller_name}"
        )
        identities.append(
            TargetIdentity(
                profile=name,
                controller=controller_name,
                site=_require_string(profile, "site", f"profiles.{name}"),
                adapter=_validate_adapter(
                    controller.get("adapter", ADAPTER_LOCAL_CLASSIC),
                    f"controllers.{controller_name}.adapter",
                ),
            )
        )
    return tuple(identities)


def resolve_identity(
    config: Mapping[str, Any] | None = None,
    *,
    profile: str | None = None,
    environ: Mapping[str, str] | None = None,
) -> TargetIdentity:
    """Resolve a target identity without loading credentials or contacting a target."""
    environment = _runtime_environment(environ)
    if config is None:
        if profile is not None:
            raise ConfigError("profile selection requires a version-2 configuration")
        return TargetIdentity("legacy", "legacy", environment.get("UNIFI_SITE", "default"))

    document = _require_mapping(config, "config")
    version = document.get("version")
    if version == 1:
        if profile is not None:
            raise ConfigError("--profile is not supported by version-1 configuration")
        validate_config(dict(document))
        return TargetIdentity("legacy", "legacy", str(document["controller"]["site"]))
    if version != PROFILE_LAYER_VERSION:
        raise ConfigError(f"unsupported profile configuration version: {version}")

    validate_profile_document(document)
    selected_name = _select_profile(document, profile, environment)
    profiles = _require_mapping(document["profiles"], "profiles")
    selected_profile = _require_mapping(profiles[selected_name], f"profiles.{selected_name}")
    controller_name = str(selected_profile["controller"])
    controllers = _require_mapping(document["controllers"], "controllers")
    controller = _require_mapping(controllers[controller_name], f"controllers.{controller_name}")
    return TargetIdentity(
        selected_name,
        controller_name,
        str(selected_profile["site"]),
        _validate_adapter(
            controller.get("adapter", ADAPTER_LOCAL_CLASSIC),
            f"controllers.{controller_name}.adapter",
        ),
    )


def auth_mode_for_identity(
    config: Mapping[str, Any] | None,
    identity: TargetIdentity,
    *,
    environ: Mapping[str, str] | None = None,
) -> str:
    """Return the declared auth mode without resolving its secret value."""
    environment = _runtime_environment(environ)
    if config is None or config.get("version") == 1:
        return (
            AUTH_MODE_API_KEY if environment.get("UNIFI_API_KEY", "").strip() else AUTH_MODE_SESSION
        )

    controllers = _require_mapping(config.get("controllers"), "controllers")
    controller = _require_mapping(controllers.get(identity.controller), "controller")
    auth = _require_mapping(controller.get("auth"), "controller.auth")
    return AUTH_MODE_API_KEY if "api_key_env" in auth else AUTH_MODE_SESSION


def _runtime_environment(environ: Mapping[str, str] | None) -> Mapping[str, str]:
    if environ is not None:
        return environ
    load_dotenv()
    return os.environ


def _environment_value(environment: Mapping[str, str], name: str, label: str) -> str:
    value = environment.get(name)
    if value is None or not value.strip():
        raise CredentialsError(f"missing environment variable {name} for {label}")
    if value.startswith("op://"):
        raise CredentialsError(
            f"unresolved secret-manager reference in environment variable {name}"
        )
    return value


def _select_profile(
    config: Mapping[str, Any],
    requested_profile: str | None,
    environment: Mapping[str, str],
) -> str:
    selectors: list[tuple[str, str]] = []
    if requested_profile is not None:
        selectors.append(("CLI", _validate_identifier(requested_profile, "--profile")))
    if "profile" in config:
        selectors.append(
            (
                "configuration",
                _validate_identifier(config["profile"], "config.profile"),
            )
        )
    environment_profile = environment.get(PROFILE_SELECTOR_ENV)
    if environment_profile is not None:
        selectors.append(
            (
                PROFILE_SELECTOR_ENV,
                _validate_identifier(environment_profile, PROFILE_SELECTOR_ENV),
            )
        )
    distinct = {value for _, value in selectors}
    if len(distinct) > 1:
        sources = ", ".join(source for source, _ in selectors)
        raise ConfigError(f"conflicting profile selectors from {sources}")
    if not selectors:
        raise ConfigError("version-2 configuration requires an explicit profile selection")
    selected_name = selectors[0][1]
    profiles = _require_mapping(config["profiles"], "profiles")
    if selected_name not in profiles:
        raise ConfigError(f"unknown profile: {selected_name}")
    return selected_name


def _settings_for_v2(
    controller: Mapping[str, Any],
    profile: Mapping[str, Any],
    environment: Mapping[str, str],
) -> ControllerSettings:
    host_env = str(controller["host_env"])
    host = _environment_value(environment, host_env, "controller host").rstrip("/")
    verify_tls = controller.get("verify_tls", True)
    auth = _require_mapping(controller["auth"], "controller.auth")
    site = str(profile["site"])
    if "api_key_env" in auth:
        api_key = _environment_value(environment, str(auth["api_key_env"]), "API key")
        return ControllerSettings(host=host, site=site, verify_tls=verify_tls, api_key=api_key)
    username = _environment_value(environment, str(auth["username_env"]), "username")
    password = _environment_value(environment, str(auth["password_env"]), "password")
    return ControllerSettings(
        host=host,
        site=site,
        verify_tls=verify_tls,
        username=username,
        password=password,
    )


def resolve_target(
    config: Mapping[str, Any] | None = None,
    *,
    profile: str | None = None,
    environ: Mapping[str, str] | None = None,
) -> ResolvedTarget:
    """Resolve a v1 or v2 configuration into one explicit controller target."""
    environment = _runtime_environment(environ)
    if config is None:
        if profile is not None:
            raise ConfigError("profile selection requires a version-2 configuration")
        settings = ControllerSettings.from_env(environ=environment)
        return ResolvedTarget(
            TargetIdentity("legacy", "legacy", settings.site),
            settings,
        )

    document = _require_mapping(config, "config")
    version = document.get("version")
    if version == 1:
        if profile is not None:
            raise ConfigError("--profile is not supported by version-1 configuration")
        validate_config(dict(document))
        settings = ControllerSettings.from_env(environ=environment)
        site = str(document["controller"]["site"])
        settings = replace(settings, site=site)
        return ResolvedTarget(
            TargetIdentity("legacy", "legacy", site, ADAPTER_LOCAL_CLASSIC), settings
        )

    if version != PROFILE_LAYER_VERSION:
        raise ConfigError(f"unsupported profile configuration version: {version}")

    validate_profile_document(document)
    selected_name = _select_profile(document, profile, environment)
    profiles = _require_mapping(document["profiles"], "profiles")
    selected_profile = _require_mapping(profiles[selected_name], f"profiles.{selected_name}")
    controller_name = str(selected_profile["controller"])
    controllers = _require_mapping(document["controllers"], "controllers")
    controller = _require_mapping(controllers[controller_name], f"controllers.{controller_name}")
    settings = _settings_for_v2(controller, selected_profile, environment)
    adapter = _validate_adapter(
        controller.get("adapter", ADAPTER_LOCAL_CLASSIC),
        f"controllers.{controller_name}.adapter",
    )
    identity = TargetIdentity(selected_name, controller_name, settings.site, adapter)
    return ResolvedTarget(identity, settings)


__all__ = [
    "auth_mode_for_identity",
    "PROFILE_SELECTOR_ENV",
    "ResolvedTarget",
    "TargetIdentity",
    "list_profile_identities",
    "resolve_identity",
    "resolve_target",
    "validate_profile_document",
]
