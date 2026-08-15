from __future__ import annotations

import pytest

from lanweave.resources import (
    DependencyGraph,
    ResourceContractError,
    ResourceKey,
    validate_resource_operations,
)


def test_dependency_graph_is_stable_and_dependency_first() -> None:
    network = ResourceKey("network", "Home")
    wlan = ResourceKey("wlan", "Home")
    dns = ResourceKey("dns", "printer.home.arpa [A]")
    graph = DependencyGraph()
    graph.add_dependency(wlan, network)
    graph.add(dns)

    assert graph.topological_order() == [dns, network, wlan]


def test_dependency_graph_rejects_cycles() -> None:
    first = ResourceKey("dns", "one")
    second = ResourceKey("dns", "two")
    graph = DependencyGraph()
    graph.add_dependency(first, second)
    graph.add_dependency(second, first)

    with pytest.raises(ResourceContractError, match="dependency cycle"):
        graph.topological_order()


def test_resource_operation_contract_is_canonical() -> None:
    assert validate_resource_operations(("prune", "read", "read")) == (
        "read",
        "prune",
    )
    with pytest.raises(ResourceContractError, match="unsupported resource operation"):
        validate_resource_operations(("read", "destroy"))
