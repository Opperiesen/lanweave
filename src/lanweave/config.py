"""Loading and validating the portable declarative configuration."""

from __future__ import annotations

import ipaddress
import os
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

import yaml

from .contracts import CONFIG_SCHEMA_VERSION, PROFILE_LAYER_VERSION

ENV_NAME_RE = re.compile(r"^[A-Z_][A-Z0-9_]*$")
PLACEHOLDER_RE = re.compile(r"^\$[{][A-Z_][A-Z0-9_]*[}]$")
PLACEHOLDER_SEARCH_RE = re.compile(r"\$[{]([A-Z_][A-Z0-9_]*)[}]")
SUPPORTED_PURPOSES = {"corporate", "guest", "vlan-only", "wan"}
SUPPORTED_SECURITY = {"open", "wpa2", "wpa3", "wpa3-transition"}
SUPPORTED_BANDS = {"2g", "5g", "6g"}
SUPPORTED_PMF = {"disabled", "optional", "required"}
TOP_LEVEL_KEYS = {"version", "controller", "networks", "wlans"}
CONTROLLER_KEYS = {"site"}
DHCP_KEYS = {"enabled", "start", "stop", "lease_time", "dns"}
IPV6_KEYS = {"enabled", "type"}
NETWORK_KEYS = {
    "name",
    "purpose",
    "subnet",
    "vlan",
    "domain_name",
    "dhcp",
    "ipv6",
}
WLAN_KEYS = {
    "name",
    "ssid",
    "network",
    "bands",
    "security",
    "password",
    "password_env",
    "enabled",
    "hide_ssid",
    "fast_roaming",
    "proxy_arp",
    "pmf",
    "client_isolation",
    "multicast_enhancement",
    "schedule_enabled",
}
SENSITIVE_KEYS = {
    "api_key",
    "password",
    "passphrase",
    "private_key",
    "secret",
    "token",
}

EXAMPLE_CONFIG = """\
version: 1

controller:
  site: default

networks:
  - name: Home
    purpose: corporate
    subnet: 192.168.10.0/24
    vlan: 10
    dhcp:
      enabled: true
      start: 192.168.10.100
      stop: 192.168.10.240
      lease_time: 86400

  - name: IoT
    purpose: vlan-only
    subnet: 192.168.20.0/24
    vlan: 20
    dhcp:
      enabled: true
      start: 192.168.20.100
      stop: 192.168.20.240
      lease_time: 86400

wlans:
  - name: Home
    ssid: Home
    network: Home
    bands: [5g, 6g]
    security: wpa3
    password_env: WIFI_HOME_PASSWORD

  - name: Home-IoT
    ssid: Home-IoT
    network: IoT
    bands: [2g]
    security: wpa2
    password_env: WIFI_IOT_PASSWORD
    client_isolation: true
"""


class ConfigError(ValueError):
    """Raised when a declarative configuration is unsafe or malformed."""


def _require_mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ConfigError(f"{label} must be a mapping")
    return value


def _require_string(mapping: dict[str, Any], key: str, label: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"{label}.{key} must be a non-empty string")
    return value


def _validate_ip(value: Any, label: str) -> None:
    if not isinstance(value, str):
        raise ConfigError(f"{label} must be an IP address")
    try:
        ipaddress.ip_address(value)
    except ValueError as exc:
        raise ConfigError(f"{label} must be an IP address") from exc


def _validate_sensitive_values(value: Any, path: str = "config") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            key_name = str(key).lower()
            if (
                key_name in SENSITIVE_KEYS
                and child not in (None, "")
                and (not isinstance(child, str) or not PLACEHOLDER_RE.fullmatch(child))
            ):
                raise ConfigError(
                    f"{path}.{key} must be an environment placeholder such as $" + "{WIFI_PASSWORD}"
                )
            _validate_sensitive_values(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _validate_sensitive_values(child, f"{path}[{index}]")


def _validate_env_name(value: Any, label: str) -> None:
    if not isinstance(value, str) or not ENV_NAME_RE.fullmatch(value):
        raise ConfigError(f"{label} must be an uppercase environment variable name")


def _reject_unknown_fields(mapping: dict[str, Any], allowed: set[str], label: str) -> None:
    unknown = sorted(set(mapping) - allowed, key=str)
    if unknown:
        names = ", ".join(str(name) for name in unknown)
        raise ConfigError(f"unsupported field(s) in {label}: {names}")


def _resolve_value(value: Any, lookup: Callable[[str], str | None], path: str) -> Any:
    if isinstance(value, str):

        def replace(match: re.Match[str]) -> str:
            name = match.group(1)
            resolved = lookup(name)
            if resolved is None:
                raise ConfigError(f"missing environment variable {name} referenced at {path}")
            if resolved.startswith("op://"):
                raise ConfigError(
                    f"unresolved secret-manager reference in environment variable {name}"
                )
            if not resolved and path.endswith(".password"):
                raise ConfigError(f"environment variable {name} is empty")
            return resolved

        return PLACEHOLDER_SEARCH_RE.sub(replace, value)
    if isinstance(value, dict):
        resolved: dict[str, Any] = {}
        for key, child in value.items():
            if key == "password_env" and path.startswith("config.wlans["):
                name = str(child)
                secret = lookup(name)
                if secret is None:
                    raise ConfigError(f"missing environment variable {name} referenced at {path}")
                if secret.startswith("op://"):
                    raise ConfigError(
                        f"unresolved secret-manager reference in environment variable {name}"
                    )
                if not secret:
                    raise ConfigError(f"environment variable {name} is empty")
                resolved["password"] = secret
            else:
                resolved[key] = _resolve_value(child, lookup, f"{path}.{key}")
        return resolved
    if isinstance(value, list):
        return [
            _resolve_value(child, lookup, f"{path}[{index}]") for index, child in enumerate(value)
        ]
    return value


def validate_config(config: dict[str, Any]) -> None:
    """Validate a supported version-1 or version-2 configuration."""
    _require_mapping(config, "config")
    if config.get("version") == PROFILE_LAYER_VERSION:
        from .profiles import validate_profile_document

        validate_profile_document(config)
        _validate_version_one_config(
            {
                "version": CONFIG_SCHEMA_VERSION,
                "controller": {"site": "default"},
                "networks": config.get("networks"),
                "wlans": config.get("wlans"),
            }
        )
        return
    _validate_version_one_config(config)


def _validate_version_one_config(config: dict[str, Any]) -> None:
    """Validate the shipped version-1 resource and controller contract.

    This intentionally validates only the portable subset. Controller-specific
    fields will be added through versioned schema changes rather than accepted
    silently.
    """
    _require_mapping(config, "config")
    unknown_top_level = sorted(set(config) - TOP_LEVEL_KEYS, key=str)
    if unknown_top_level:
        names = ", ".join(str(name) for name in unknown_top_level)
        raise ConfigError(f"unsupported top-level field(s): {names}")
    if config.get("version") != CONFIG_SCHEMA_VERSION:
        raise ConfigError(f"version must be {CONFIG_SCHEMA_VERSION}")
    _validate_sensitive_values(config)

    controller = _require_mapping(config.get("controller"), "controller")
    _reject_unknown_fields(controller, CONTROLLER_KEYS, "controller")
    _require_string(controller, "site", "controller")

    networks = config.get("networks")
    if not isinstance(networks, list):
        raise ConfigError("networks must be a list")
    network_names: set[str] = set()
    for index, raw_network in enumerate(networks):
        label = f"networks[{index}]"
        network = _require_mapping(raw_network, label)
        _reject_unknown_fields(network, NETWORK_KEYS, label)
        name = _require_string(network, "name", label)
        if name in network_names:
            raise ConfigError(f"duplicate network name: {name}")
        network_names.add(name)
        purpose = _require_string(network, "purpose", label)
        if purpose not in SUPPORTED_PURPOSES:
            allowed = ", ".join(sorted(SUPPORTED_PURPOSES))
            raise ConfigError(f"{label}.purpose must be one of: {allowed}")
        subnet = network.get("subnet")
        if subnet is not None:
            if not isinstance(subnet, str):
                raise ConfigError(f"{label}.subnet must be a network in CIDR notation")
            try:
                ipaddress.ip_network(subnet, strict=False)
            except ValueError as exc:
                raise ConfigError(f"{label}.subnet is not a valid network") from exc
        vlan = network.get("vlan")
        if vlan is not None and (
            isinstance(vlan, bool) or not isinstance(vlan, int) or not 1 <= vlan <= 4094
        ):
            raise ConfigError(f"{label}.vlan must be an integer between 1 and 4094")
        dhcp = network.get("dhcp")
        if dhcp is not None:
            if not isinstance(dhcp, dict):
                raise ConfigError(f"{label}.dhcp must be a mapping")
            _reject_unknown_fields(dhcp, DHCP_KEYS, f"{label}.dhcp")
            if "enabled" in dhcp and not isinstance(dhcp["enabled"], bool):
                raise ConfigError(f"{label}.dhcp.enabled must be a boolean")
            if "lease_time" in dhcp and (
                isinstance(dhcp["lease_time"], bool)
                or not isinstance(dhcp["lease_time"], int)
                or dhcp["lease_time"] <= 0
            ):
                raise ConfigError(f"{label}.dhcp.lease_time must be a positive integer")
            for ip_key in ("start", "stop"):
                if dhcp.get(ip_key) is not None:
                    _validate_ip(dhcp[ip_key], f"{label}.dhcp.{ip_key}")
            dns = dhcp.get("dns")
            if dns is not None and (
                not isinstance(dns, list) or not all(isinstance(server, str) for server in dns)
            ):
                raise ConfigError(f"{label}.dhcp.dns must be a list of strings")
            for index, server in enumerate(dns or []):
                _validate_ip(server, f"{label}.dhcp.dns[{index}]")
        ipv6 = network.get("ipv6")
        if ipv6 is not None:
            if not isinstance(ipv6, dict):
                raise ConfigError(f"{label}.ipv6 must be a mapping")
            _reject_unknown_fields(ipv6, IPV6_KEYS, f"{label}.ipv6")
            if "enabled" in ipv6 and not isinstance(ipv6["enabled"], bool):
                raise ConfigError(f"{label}.ipv6.enabled must be a boolean")

    wlans = config.get("wlans")
    if not isinstance(wlans, list):
        raise ConfigError("wlans must be a list")
    wlan_names: set[str] = set()
    for index, raw_wlan in enumerate(wlans):
        label = f"wlans[{index}]"
        wlan = _require_mapping(raw_wlan, label)
        _reject_unknown_fields(wlan, WLAN_KEYS, label)
        name = _require_string(wlan, "name", label)
        if name in wlan_names:
            raise ConfigError(f"duplicate WLAN name: {name}")
        wlan_names.add(name)
        _require_string(wlan, "ssid", label)
        network = _require_string(wlan, "network", label)
        if network not in network_names:
            raise ConfigError(f"{label}.network refers to an unknown network: {network}")
        security = _require_string(wlan, "security", label)
        if security not in SUPPORTED_SECURITY:
            allowed = ", ".join(sorted(SUPPORTED_SECURITY))
            raise ConfigError(f"{label}.security must be one of: {allowed}")
        if security != "open" and not wlan.get("password") and not wlan.get("password_env"):
            raise ConfigError(f"{label} needs password_env or password for protected WLANs")
        if security == "open" and (wlan.get("password") or wlan.get("password_env")):
            raise ConfigError(f"{label} must not define a password when security is open")
        if wlan.get("password") and wlan.get("password_env"):
            raise ConfigError(f"{label} must define either password or password_env, not both")
        if wlan.get("password_env") is not None:
            _validate_env_name(wlan["password_env"], f"{label}.password_env")
        bands = wlan.get("bands")
        if (
            not isinstance(bands, list)
            or not bands
            or not all(isinstance(band, str) for band in bands)
        ):
            raise ConfigError(f"{label}.bands must be a non-empty list of strings")
        unsupported_bands = sorted(set(bands) - SUPPORTED_BANDS)
        if unsupported_bands:
            raise ConfigError(
                f"{label}.bands contains unsupported band(s): {', '.join(unsupported_bands)}"
            )
        pmf = wlan.get("pmf")
        if pmf is not None and pmf not in SUPPORTED_PMF:
            raise ConfigError(f"{label}.pmf must be one of: {', '.join(sorted(SUPPORTED_PMF))}")
        for boolean_key in (
            "enabled",
            "hide_ssid",
            "fast_roaming",
            "proxy_arp",
            "client_isolation",
            "multicast_enhancement",
            "schedule_enabled",
        ):
            if boolean_key in wlan and not isinstance(wlan[boolean_key], bool):
                raise ConfigError(f"{label}.{boolean_key} must be a boolean")


def load_config(path: Path) -> dict[str, Any]:
    """Load and validate a YAML configuration from disk."""
    return load_config_with_options(path)


def load_config_with_options(
    path: Path,
    *,
    resolve_secrets: bool = False,
    environ: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Load configuration and optionally resolve environment-backed secrets."""
    if not path.exists():
        raise ConfigError(f"configuration not found: {path}")
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigError(f"invalid YAML in {path}: {exc}") from exc
    config = _require_mapping(raw, "config")
    validate_config(config)
    if not resolve_secrets:
        return config
    lookup = (os.environ if environ is None else environ).get
    return _resolve_value(config, lookup, "config")
