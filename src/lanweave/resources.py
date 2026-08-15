"""Small shared contracts for declarative resource lifecycles."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

RESOURCE_OPERATIONS = ("read", "export", "plan", "apply", "prune")


class ResourceContractError(ValueError):
    """Raised when a resource identity or dependency graph is unsafe."""


@dataclass(frozen=True, order=True)
class ResourceKey:
    """Stable, vendor-independent identity used by dependency ordering."""

    kind: str
    name: str

    def __post_init__(self) -> None:
        if not isinstance(self.kind, str) or not self.kind.strip():
            raise ResourceContractError("resource kind must be a non-empty string")
        if not isinstance(self.name, str) or not self.name.strip():
            raise ResourceContractError("resource name must be a non-empty string")

    def label(self) -> str:
        return f"{self.kind}/{self.name}"


@dataclass
class DependencyGraph:
    """Deterministic dependency graph with fail-closed cycle detection.

    An edge means that ``resource`` depends on ``dependency``. The returned
    order always places dependencies before their dependants. Callers applying
    deletes can reverse that order.
    """

    _dependencies: dict[ResourceKey, set[ResourceKey]] = field(default_factory=dict)

    def add(self, resource: ResourceKey) -> None:
        self._dependencies.setdefault(resource, set())

    def add_dependency(self, resource: ResourceKey, dependency: ResourceKey) -> None:
        self.add(resource)
        self.add(dependency)
        self._dependencies[resource].add(dependency)

    def topological_order(
        self, resources: Iterable[ResourceKey] | None = None
    ) -> list[ResourceKey]:
        """Return a stable dependency-first order or raise on a cycle."""
        selected = set(self._dependencies if resources is None else resources)
        pending = {
            resource: {
                dependency
                for dependency in self._dependencies.get(resource, set())
                if dependency in selected
            }
            for resource in selected
        }
        ordered: list[ResourceKey] = []
        while pending:
            ready = sorted(
                resource for resource, dependencies in pending.items() if not dependencies
            )
            if not ready:
                cycle = ", ".join(resource.label() for resource in sorted(pending))
                raise ResourceContractError(f"dependency cycle: {cycle}")
            ordered.extend(ready)
            for resource in ready:
                pending.pop(resource)
            for dependencies in pending.values():
                dependencies.difference_update(ready)
        return ordered


def validate_resource_operations(operations: Iterable[str]) -> tuple[str, ...]:
    """Normalize and validate the public lifecycle operation names."""
    values = tuple(dict.fromkeys(operations))
    unsupported = sorted(set(values) - set(RESOURCE_OPERATIONS))
    if unsupported:
        raise ResourceContractError(f"unsupported resource operation(s): {', '.join(unsupported)}")
    return tuple(operation for operation in RESOURCE_OPERATIONS if operation in values)


__all__ = [
    "DependencyGraph",
    "RESOURCE_OPERATIONS",
    "ResourceContractError",
    "ResourceKey",
    "validate_resource_operations",
]
