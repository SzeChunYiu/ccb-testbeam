"""Machine-readable amplitude-map equivalence contract for S00 selectors.

Issue #1136 established that the public selector method names are not in
one-to-one correspondence with distinct scalar amplitude maps.  In particular,
``dynamic_range`` and ``rolling_min`` both compute the same pedestal,
``min(w)``, and the shared selector pipeline therefore gives the identical
amplitude ``max(w) - min(w)``.  Their only difference is the validity-state
policy layered on that scalar map.

This module keeps those two concepts separate:

* an ``amplitude_map_id`` identifies the mathematical scalar transformation;
* a ``validity_policy_id`` identifies the diagnostic/censoring interpretation.

Model comparison, multiplicity accounting, and robustness summaries should
operate on unique amplitude-map IDs.  Legacy method aliases remain available so
existing studies can be interpreted without silently rewriting history.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class SelectorMethodContract:
    """Semantic contract for one legacy/public selector method name."""

    method: str
    amplitude_map_id: str
    amplitude_formula: str
    validity_policy_id: str


_METHOD_CONTRACTS: tuple[SelectorMethodContract, ...] = (
    SelectorMethodContract(
        method="v1",
        amplitude_map_id="first_four_median_v1",
        amplitude_formula="max(w)-median(w[0:4])",
        validity_policy_id="first_four_shape_diagnostic_v1",
    ),
    SelectorMethodContract(
        method="dynamic_range",
        amplitude_map_id="range_max_minus_min_v1",
        amplitude_formula="max(w)-min(w)",
        validity_policy_id="range_trust_min_unless_saturated_v1",
    ),
    SelectorMethodContract(
        method="rolling_min",
        amplitude_map_id="range_max_minus_min_v1",
        amplitude_formula="max(w)-min(w)",
        validity_policy_id="range_cautious_min_diagnostic_v1",
    ),
    SelectorMethodContract(
        method="early_robust_p10",
        amplitude_map_id="full_window_p10_v1",
        amplitude_formula="max(w)-P10(w)",
        validity_policy_id="full_window_p10_spread_diagnostic_v1",
    ),
)

METHOD_CONTRACTS = {contract.method: contract for contract in _METHOD_CONTRACTS}


def method_contract(method: str) -> SelectorMethodContract:
    """Return the semantic contract for one selector method alias."""

    try:
        return METHOD_CONTRACTS[method]
    except KeyError as exc:
        raise KeyError(
            f"unknown selector method {method!r}; choices={sorted(METHOD_CONTRACTS)}"
        ) from exc


def amplitude_map_id(method: str) -> str:
    """Return the unique mathematical amplitude-map identity for ``method``."""

    return method_contract(method).amplitude_map_id


def amplitude_maps_available() -> list[str]:
    """Return unique scalar amplitude maps in stable declaration order."""

    return list(dict.fromkeys(contract.amplitude_map_id for contract in _METHOD_CONTRACTS))


def validity_policies_available() -> list[str]:
    """Return validity/censoring policies separately from amplitude maps."""

    return [contract.validity_policy_id for contract in _METHOD_CONTRACTS]


def collapse_method_names(methods: Iterable[str]) -> dict[str, tuple[str, ...]]:
    """Collapse method aliases into unique amplitude-map equivalence classes.

    The return value preserves first-seen map order and first-seen method order.
    It is intended for candidate accounting and reporting, where exact aliases
    must not be counted as independent mathematical hypotheses.
    """

    grouped: dict[str, list[str]] = {}
    for method in methods:
        map_id = amplitude_map_id(method)
        grouped.setdefault(map_id, [])
        if method not in grouped[map_id]:
            grouped[map_id].append(method)
    return {map_id: tuple(names) for map_id, names in grouped.items()}


def aliases_for_amplitude_map(map_id: str) -> tuple[str, ...]:
    """Return all selector method names implementing one amplitude map."""

    aliases = tuple(
        contract.method
        for contract in _METHOD_CONTRACTS
        if contract.amplitude_map_id == map_id
    )
    if not aliases:
        raise KeyError(
            f"unknown amplitude map {map_id!r}; choices={amplitude_maps_available()}"
        )
    return aliases
