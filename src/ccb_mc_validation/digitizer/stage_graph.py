"""Fail-closed digitizer stage-graph resolver (issue #1077).

Requested stage lists must resolve to an explicit effective execution graph
before event 0. Hidden sampling/electronics fallbacks are not provenance-safe.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Sequence

STAGE_GRAPH_SCHEMA = "ccb-digitizer-stage-graph/v1"

# Physical upstream stages that may be requested by callers.
OPTIONAL_UPSTREAM_STAGES: tuple[str, ...] = (
    "birks",
    "scintillation",
    "transport",
    "sampling",
)

# Final waveform observation is always part of the ADC production path and is
# recorded in the resolved graph even when callers omit it from the request.
MANDATORY_FINAL_STAGE = "daq_observation"

# Deprecated name that previously looked toggleable but did not control the
# final gain/pedestal/noise/quantize path.
DEPRECATED_STAGES: tuple[str, ...] = ("electronics",)

ALLOWED_REQUEST_STAGES: frozenset[str] = frozenset(OPTIONAL_UPSTREAM_STAGES)

# Sampling must precede any ADC waveform claim: light_curve is formed there.
UPSTREAM_ORDER: tuple[str, ...] = (
    "birks",
    "scintillation",
    "transport",
    "sampling",
)


@dataclass(frozen=True)
class ResolvedStageGraph:
    schema_version: str
    requested_stages: tuple[str, ...]
    resolved_stages: tuple[str, ...]
    mandatory_insertions: tuple[str, ...]
    graph_sha256: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "requested_stages": list(self.requested_stages),
            "resolved_stages": list(self.resolved_stages),
            "mandatory_insertions": list(self.mandatory_insertions),
            "graph_sha256": self.graph_sha256,
        }


def _graph_digest(resolved: Sequence[str], mandatory: Sequence[str], requested: Sequence[str]) -> str:
    payload = {
        "schema_version": STAGE_GRAPH_SCHEMA,
        "mandatory_insertions": list(mandatory),
        "requested_stages": list(requested),
        "resolved_stages": list(resolved),
    }
    blob = (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def resolve_stage_graph(requested_stages: Sequence[str]) -> ResolvedStageGraph:
    """Resolve a requested stage list to one effective ADC production graph.

    Rules (fail-closed):
    - unknown stages rejected
    - deprecated ``electronics`` rejected (use mandatory ``daq_observation``)
    - duplicates rejected
    - order must respect UPSTREAM_ORDER subsequence
    - ``sampling`` is required for ADC waveform production
    - ``daq_observation`` is always appended as a mandatory final node
    """
    requested = [str(s) for s in requested_stages]
    if not requested:
        raise ValueError(
            "digitizer stage graph is empty; refuse silent ADC synthesis "
            f"(schema={STAGE_GRAPH_SCHEMA})"
        )

    seen: set[str] = set()
    for name in requested:
        if name in DEPRECATED_STAGES:
            raise ValueError(
                f"stage {name!r} is deprecated and not an executable toggle; "
                f"final gain/pedestal/noise/quantize is mandatory node "
                f"{MANDATORY_FINAL_STAGE!r} recorded in the resolved graph"
            )
        if name not in ALLOWED_REQUEST_STAGES:
            raise ValueError(f"unknown digitizer stage {name!r}")
        if name in seen:
            raise ValueError(f"duplicate digitizer stage {name!r}")
        seen.add(name)

    order_index = {name: i for i, name in enumerate(UPSTREAM_ORDER)}
    last = -1
    for name in requested:
        idx = order_index[name]
        if idx < last:
            raise ValueError(
                f"digitizer stage order invalid: {name!r} appears after a later stage "
                f"(required subsequence of {list(UPSTREAM_ORDER)})"
            )
        last = idx

    if "sampling" not in seen:
        raise ValueError(
            "requested stage graph omits mandatory 'sampling' for ADC waveform "
            "production; refusing hidden integrate_samples fallback"
        )

    mandatory = (MANDATORY_FINAL_STAGE,)
    resolved = tuple(requested) + mandatory
    digest = _graph_digest(resolved, mandatory, requested)
    return ResolvedStageGraph(
        schema_version=STAGE_GRAPH_SCHEMA,
        requested_stages=tuple(requested),
        resolved_stages=resolved,
        mandatory_insertions=mandatory,
        graph_sha256=digest,
    )
