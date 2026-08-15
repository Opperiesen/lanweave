"""Loading and validating the portable declarative configuration."""

from __future__ import annotations

import ipaddress
import re
from pathlib import Path
from typing import Any

import yaml

PLACEHOLDER_RE = re.compile(r"^\$[{][A-Z_][A-Z0-9_]*[}]$")
SUPPORTED_PURPOSES = {"corporate", "guest", "vlan-only", "wan"}
SUPPORTED_SECURITY = {"open", "wpa2", "wpa3", "wpa3-transition"}
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

  - name: Home-IoT
    ssid: Home-IoT
    network: IoT
    bands: [2g]
    security: wpa2
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
                    f"{path}.{key} must be an environment placeholder such as "
                    "$" + "{WIFI_PASSWORD}"
                )
            _validate_sensitive_values(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _validate_sensitive_values(child, f"{path}[{index}]")


def validate_config(config: dict[str, Any]) -> None:
    """Validate the public configuration contract.

    This intentionally validates only the portable subset. Controller-specific
    fields will be added through versioned schema changes rather than accepted
    silently.
    """
    _require_mapping(config, "config")
    if config.get("version") != 1:
        raise ConfigError("version must be 1")

    controller = _require_mapping(config.get("controller"), "controller")
    _require_string(controller, "site", "controller")

    networks = config.get("networks")
    if not isinstance(networks, list):
        raise ConfigError("networks must be a list")
    network_names: set[str] = set()
    for index, raw_network in enumerate(networks):
        label = f"networks[{index}]"
        network = _require_mapping(raw_network, label)
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
            try:
                ipaddress.ip_network(subnet, strict=False)
            except ValueError as exc:
                raise ConfigError(f"{label}.subnet is not a valid network") from exc
        vlan = network.get("vlan")
        if vlan is not None and (not isinstance(vlan, int) or not 1 <= vlan <= 4094):
            raise ConfigError(f"{label}.vlan must be an integer between 1 and 4094")

    wlans = config.get("wlans")
    if not isinstance(wlans, list):
        raise ConfigError("wlans must be a list")
    wlan_names: set[str] = set()
    for index, raw_wlan in enumerate(wlans):
        label = f"wlans[{index}]"
        wlan = _require_mapping(raw_wlan, label)
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
        bands = wlan.get("bands")
        if (
            not isinstance(bands, list)
            or not bands
            or not all(isinstance(band, str) for band in bands)
        ):
            raise ConfigError(f"{label}.bands must be a non-empty list of strings")

    _validate_sensitive_values(config)


def load_config(path: Path) -> dict[str, Any]:
    """Load and validate a YAML configuration from disk."""
    if not path.exists():
        raise ConfigError(f"configuration not found: {path}")
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigError(f"invalid YAML in {path}: {exc}") from exc
    config = _require_mapping(raw, "config")
    validate_config(config)
    return config
