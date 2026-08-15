"""Stable adapter, capability and error contracts for Lanweave.

The concrete local and cloud implementations are intentionally kept outside
this module. This module defines the dependency-free boundary they must
implement so selection, capability reporting and failures stay deterministic.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol, Self, runtime_checkable

from .contracts import CAPABILITY_FORMAT_VERSION

ADAPTER_LOCAL_CLASSIC = "local-classic"
ADAPTER_CLOUD_SITE_MANAGER = "cloud-site-manager"
AUTH_MODE_API_KEY = "api-key"
AUTH_MODE_SESSION = "session"

_IDENTIFIER_RE = re.compile(r"^[a-z][a-z0-9-]{0,63}$")
_OPERATION_ORDER = {
    "read": 0,
    "export": 1,
    "plan": 2,
    "apply": 3,
    "prune": 4,
}


class AdapterOperation(StrEnum):
    """Operations that an adapter can advertise for a resource."""

    READ = "read"
    EXPORT = "export"
    PLAN = "plan"
    APPLY = "apply"
    PRUNE = "prune"


def _operation_value(value: str | AdapterOperation) -> str:
    return value.value if isinstance(value, AdapterOperation) else value


def _identifier(value: str, label: str) -> str:
    if not isinstance(value, str) or not _IDENTIFIER_RE.fullmatch(value):
        raise ValueError(f"{label} must match ^[a-z][a-z0-9-]{{0,63}}$")
    return value


def _ordered_unique(values: tuple[str, ...], *, label: str) -> tuple[str, ...]:
    if any(not isinstance(value, str) or not value.strip() for value in values):
        raise ValueError(f"{label} must contain non-empty strings")
    return tuple(dict.fromkeys(sorted(values)))


@dataclass(frozen=True)
class AdapterCapability:
    """A deterministic set of operations for one logical resource."""

    resource: str
    operations: tuple[str | AdapterOperation, ...]

    def __post_init__(self) -> None:
        resource = _identifier(self.resource, "resource")
        operations = tuple(_operation_value(operation) for operation in self.operations)
        unsupported = sorted(set(operations) - set(_OPERATION_ORDER))
        if unsupported:
            names = ", ".join(unsupported)
            raise ValueError(f"unsupported operation(s): {names}")
        if len(set(operations)) != len(operations):
            raise ValueError("operations must not contain duplicates")
        ordered = tuple(sorted(operations, key=_OPERATION_ORDER.__getitem__))
        object.__setattr__(self, "resource", resource)
        object.__setattr__(self, "operations", ordered)

    def supports(self, operation: str | AdapterOperation) -> bool:
        """Return whether this resource supports the requested operation."""
        return _operation_value(operation) in self.operations

    def to_dict(self) -> dict[str, Any]:
        """Return the public, secret-free representation."""
        return {"resource": self.resource, "operations": list(self.operations)}


@dataclass(frozen=True)
class AdapterCapabilities:
    """Versioned capabilities advertised by one adapter instance."""

    adapter: str
    auth_modes: tuple[str, ...]
    resources: tuple[AdapterCapability, ...]
    format_version: int = CAPABILITY_FORMAT_VERSION

    def __post_init__(self) -> None:
        adapter = _identifier(self.adapter, "adapter")
        if self.format_version != CAPABILITY_FORMAT_VERSION:
            raise ValueError(f"capability format must be {CAPABILITY_FORMAT_VERSION}")
        auth_modes = _ordered_unique(tuple(self.auth_modes), label="auth_modes")
        resources = tuple(self.resources)
        if not all(isinstance(resource, AdapterCapability) for resource in resources):
            raise ValueError("resources must contain AdapterCapability values")
        resource_names = [resource.resource for resource in resources]
        if len(set(resource_names)) != len(resource_names):
            raise ValueError("resources must not contain duplicates")
        ordered_resources = tuple(sorted(resources, key=lambda item: item.resource))
        object.__setattr__(self, "adapter", adapter)
        object.__setattr__(self, "auth_modes", auth_modes)
        object.__setattr__(self, "resources", ordered_resources)

    def supports(self, resource: str, operation: str | AdapterOperation) -> bool:
        """Return whether the adapter advertises an operation for a resource."""
        return any(
            capability.resource == resource and capability.supports(operation)
            for capability in self.resources
        )

    def require(self, resource: str, operation: str | AdapterOperation) -> None:
        """Raise a stable error when an operation is outside the capability set."""
        normalized_operation = _operation_value(operation)
        if not self.supports(resource, normalized_operation):
            raise UnsupportedCapabilityError(self.adapter, resource, normalized_operation)

    def to_dict(self) -> dict[str, Any]:
        """Return the deterministic machine-readable capability document."""
        return {
            "format_version": self.format_version,
            "adapter": self.adapter,
            "auth_modes": list(self.auth_modes),
            "resources": [resource.to_dict() for resource in self.resources],
        }


class AdapterError(RuntimeError):
    """Base class for secret-free adapter failures."""

    code = "adapter_error"

    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(f"{self.code}: {detail}")

    def to_dict(self) -> dict[str, str]:
        return {"error": self.code, "detail": self.detail}


class AdapterConfigurationError(AdapterError):
    """Raised when adapter configuration or selection is invalid."""

    code = "invalid_configuration"


class AdapterAuthenticationError(AdapterError):
    """Raised when an adapter cannot authenticate."""

    code = "authentication_error"


class AdapterTransportError(AdapterError):
    """Raised when an adapter transport fails without exposing a raw response."""

    code = "transport_error"


class AdapterRateLimitError(AdapterError):
    """Raised when a read is rejected by a remote rate limit."""

    code = "rate_limit"

    def __init__(self, retry_after: int | None = None) -> None:
        if retry_after is not None and retry_after < 0:
            raise ValueError("retry_after must not be negative")
        self.retry_after = retry_after
        super().__init__("adapter rate limit exceeded")

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = super().to_dict()
        result["retry_after"] = self.retry_after
        return result


class UnsupportedCapabilityError(AdapterError):
    """Raised before an unsupported adapter operation can reach the network."""

    code = "unsupported_capability"

    def __init__(self, adapter: str, resource: str, operation: str) -> None:
        self.adapter = _identifier(adapter, "adapter")
        self.resource = _identifier(resource, "resource")
        if operation not in _OPERATION_ORDER:
            raise ValueError(f"unsupported operation: {operation}")
        self.operation = operation
        super().__init__(f"{self.adapter} does not support {operation} on {resource}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "error": self.code,
            "adapter": self.adapter,
            "resource": self.resource,
            "operation": self.operation,
            "detail": self.detail,
        }


@runtime_checkable
class Adapter(Protocol):
    """Structural interface consumed by current CLI, plan and status code."""

    settings: Any
    capabilities: AdapterCapabilities
    adapter_name: str

    def __enter__(self) -> Self: ...

    def __exit__(self, *_args: Any) -> None: ...

    def close(self) -> None: ...

    def site_url(self, path: str) -> str: ...

    def health(self) -> list[dict[str, Any]]: ...

    def devices(self) -> list[dict[str, Any]]: ...

    def clients(self) -> list[dict[str, Any]]: ...

    def networks(self) -> list[dict[str, Any]]: ...

    def wlans(self) -> list[dict[str, Any]]: ...

    def get(self, path: str, **kwargs: Any) -> Any: ...

    def post(self, path: str, json: Any = None, **kwargs: Any) -> Any: ...

    def put(self, path: str, json: Any = None, **kwargs: Any) -> Any: ...

    def delete(self, path: str, **kwargs: Any) -> Any: ...


AdapterFactory = Callable[..., Adapter]


class AdapterRegistry:
    """Explicit, deterministic registry used by adapter factories."""

    def __init__(self, factories: Mapping[str, AdapterFactory] | None = None) -> None:
        self._factories: dict[str, AdapterFactory] = {}
        for name, factory in (factories or {}).items():
            self.register(name, factory)

    def register(self, name: str, factory: AdapterFactory) -> None:
        """Register one adapter factory; duplicate names are rejected."""
        normalized = _identifier(name, "adapter")
        if normalized in self._factories:
            raise AdapterConfigurationError(f"adapter already registered: {normalized}")
        self._factories[normalized] = factory

    def names(self) -> tuple[str, ...]:
        """Return registered adapter names in deterministic order."""
        return tuple(sorted(self._factories))

    def create(self, name: str, *args: Any, **kwargs: Any) -> Adapter:
        """Create an explicitly selected adapter or fail without fallback."""
        normalized = _identifier(name, "adapter")
        factory = self._factories.get(normalized)
        if factory is None:
            raise AdapterConfigurationError(f"unknown adapter: {normalized}")
        adapter = factory(*args, **kwargs)
        adapter_name = getattr(adapter, "adapter_name", None)
        if adapter_name != normalized:
            raise AdapterConfigurationError(
                f"adapter factory returned {adapter_name}, expected {normalized}"
            )
        return adapter


def local_classic_capabilities(auth_mode: str) -> AdapterCapabilities:
    """Return the v0.2 local capability set for one authentication mode."""
    if auth_mode == AUTH_MODE_SESSION:
        resource_operations = {
            "clients": ("read",),
            "devices": ("read",),
            "health": ("read",),
            "networks": ("read", "export", "plan", "apply", "prune"),
            "wlans": ("read", "export", "plan", "apply", "prune"),
        }
    elif auth_mode == AUTH_MODE_API_KEY:
        resource_operations = {
            "clients": ("read",),
            "devices": ("read",),
            "health": ("read",),
            "networks": ("read", "export", "plan"),
            "wlans": ("read", "export", "plan"),
        }
    else:
        raise AdapterConfigurationError(f"unsupported local authentication mode: {auth_mode}")
    return AdapterCapabilities(
        adapter=ADAPTER_LOCAL_CLASSIC,
        auth_modes=(auth_mode,),
        resources=tuple(
            AdapterCapability(resource, operations)
            for resource, operations in resource_operations.items()
        ),
    )


__all__ = [
    "ADAPTER_CLOUD_SITE_MANAGER",
    "ADAPTER_LOCAL_CLASSIC",
    "AUTH_MODE_API_KEY",
    "AUTH_MODE_SESSION",
    "Adapter",
    "AdapterAuthenticationError",
    "AdapterCapability",
    "AdapterConfigurationError",
    "AdapterError",
    "AdapterFactory",
    "AdapterOperation",
    "AdapterRateLimitError",
    "AdapterRegistry",
    "AdapterTransportError",
    "AdapterCapabilities",
    "UnsupportedCapabilityError",
    "local_classic_capabilities",
]
