"""ROOT truth-tree inspection and bounded record loading via uproot."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

import numpy as np

from ccb_mc_validation.truth.pdg import mass_of
from ccb_mc_validation.truth.trigger import process_chunk

DEFAULT_TRUTH_BRANCHES: tuple[str, ...] = (
    "Sci_bar_LayerID",
    "Sci_bar_LayerID1",
    "Sci_bar_PDG",
    "Sci_bar_EDep",
    "Sci_bar_Time",
    "Sci_bar_TrackID",
    "Sci_bar_TrackLength",
    "Sci_bar_Momentum_X",
    "Sci_bar_Momentum_Y",
    "Sci_bar_Momentum_Z",
)


def _require_uproot():
    try:
        import uproot  # type: ignore
    except ImportError as exc:  # pragma: no cover - exercised when optional dep absent
        raise ImportError("uproot is required for ROOT truth I/O; install ccb-mc-validation[root]") from exc
    return uproot


def list_root_objects(path: Path | str) -> list[str]:
    """List top-level keys in a ROOT file."""
    uproot = _require_uproot()
    with uproot.open(path) as handle:
        return list(handle.keys())


def resolve_truth_branches(
    path: Path | str,
    tree: str = "hibeam",
    *,
    required: tuple[str, ...] = DEFAULT_TRUTH_BRANCHES,
) -> dict[str, Any]:
    """Check that required branches exist in a truth tree."""
    uproot = _require_uproot()
    with uproot.open(path) as handle:
        if tree not in handle:
            available = sorted(k.split(";")[0] for k in handle.keys())
            raise KeyError(f"tree {tree!r} not found; available: {available}")
        ttree = handle[tree]
        available = set(ttree.keys())
        missing = [b for b in required if b not in available]
        present = {name: str(ttree[name].typename) for name in required if name in available}
        return {
            "path": str(Path(path).resolve()),
            "tree": tree,
            "n_entries": int(ttree.num_entries),
            "present": present,
            "missing": missing,
            "ok": not missing,
        }


def audit_truth_tree(
    path: Path | str,
    tree: str = "hibeam",
    *,
    required: tuple[str, ...] = DEFAULT_TRUTH_BRANCHES,
) -> dict[str, Any]:
    """Alias for schema audit used by CLI."""
    return resolve_truth_branches(path, tree=tree, required=required)


def _first_or_default(values: Any, default: float = 0.0) -> float:
    arr = np.asarray(values)
    if arr.size == 0:
        return float(default)
    return float(arr.reshape(-1)[0])


def _records_from_truth_arrays(arrays: Mapping[str, Any], *, coinc_ns: float = 15.0) -> dict[str, np.ndarray]:
    """Convert jagged event truth arrays into per-event study records.

    This is an event-level aggregate suitable for the current MV1-MV3 truth
    scaffolds.  It intentionally records provenance-friendly, label-safe fields:
    sample labels are computed from trigger-entry truth and event parity is not
    used for production Sample I/II assignment.
    """
    layer = np.asarray(arrays["Sci_bar_LayerID"], dtype=object)
    arm = np.asarray(arrays["Sci_bar_LayerID1"], dtype=object)
    pdg_j = np.asarray(arrays["Sci_bar_PDG"], dtype=object)
    edep_j = np.asarray(arrays["Sci_bar_EDep"], dtype=object)
    time_j = np.asarray(arrays["Sci_bar_Time"], dtype=object)
    tracklen_j = np.asarray(arrays.get("Sci_bar_TrackLength", [np.array([])] * len(layer)), dtype=object)
    px_j = np.asarray(arrays.get("Sci_bar_Momentum_X", [np.array([])] * len(layer)), dtype=object)
    py_j = np.asarray(arrays.get("Sci_bar_Momentum_Y", [np.array([])] * len(layer)), dtype=object)
    pz_j = np.asarray(arrays.get("Sci_bar_Momentum_Z", [np.array([])] * len(layer)), dtype=object)

    flags = process_chunk(layer, arm, pdg_j, time_j, coinc_ns)
    n = len(layer)
    pdg = np.zeros(n, dtype=np.int64)
    edep_l0 = np.zeros(n, dtype=np.float64)
    edep_l1 = np.zeros(n, dtype=np.float64)
    edep_tot = np.zeros(n, dtype=np.float64)
    stop_layer = np.zeros(n, dtype=np.int16)
    nlayers = np.zeros(n, dtype=np.int16)
    tracklen = np.zeros(n, dtype=np.float64)
    ekin = np.zeros(n, dtype=np.float64)
    sample_label = np.full(n, "NONE", dtype=object)

    for i in range(n):
        lay = np.asarray(layer[i], dtype=np.int16)
        e = np.asarray(edep_j[i], dtype=np.float64)
        pvals = np.asarray(pdg_j[i], dtype=np.int64)
        if pvals.size:
            pdg[i] = int(pvals.reshape(-1)[0])
        if lay.size and e.size:
            usable = min(lay.size, e.size)
            lay_u = lay[:usable]
            e_u = e[:usable]
            edep_l0[i] = float(e_u[lay_u == 0].sum())
            edep_l1[i] = float(e_u[lay_u == 1].sum())
            edep_tot[i] = float(e_u.sum())
            hit_layers = lay_u[e_u > 0]
            stop_layer[i] = int(hit_layers.max()) if hit_layers.size else int(lay_u.max())
            nlayers[i] = int(np.unique(lay_u).size)
        tracklen[i] = _first_or_default(tracklen_j[i], 0.0)
        px = _first_or_default(px_j[i], 0.0)
        py = _first_or_default(py_j[i], 0.0)
        pz = _first_or_default(pz_j[i], 0.0)
        mass = mass_of(int(pdg[i])) if int(pdg[i]) else 0.0
        momentum = float(np.sqrt(px * px + py * py + pz * pz))
        ekin[i] = float(np.sqrt(momentum * momentum + mass * mass) - mass) if mass else 0.0
        if flags["sample_I"][i]:
            sample_label[i] = "I"
        elif flags["sample_II"][i]:
            sample_label[i] = "II"

    return {
        "pdg": pdg,
        "edep_l0": edep_l0,
        "edep_l1": edep_l1,
        "edep_tot": edep_tot,
        "stop_layer": stop_layer,
        "nlayers": nlayers,
        "tracklen": tracklen,
        "ekin": ekin,
        "event_id": np.arange(n, dtype=np.int64),
        "sample_label": sample_label,
    }


def load_truth_records(
    path: Path | str,
    tree: str = "hibeam",
    *,
    max_events: int | None = 100_000,
    coinc_ns: float = 15.0,
) -> dict[str, np.ndarray]:
    """Load per-event truth records from ROOT.

    ``max_events=None`` or ``max_events<=0`` loads all entries and should only be
    used inside an approved SLURM allocation.  The bounded default supports smoke
    and fail-closed production debugging without accidentally scanning everything.
    """
    uproot = _require_uproot()
    branches = DEFAULT_TRUTH_BRANCHES
    entry_stop = None if max_events is None or max_events <= 0 else int(max_events)
    with uproot.open(path) as handle:
        if tree not in handle:
            available = sorted(k.split(";")[0] for k in handle.keys())
            raise KeyError(f"tree {tree!r} not found; available: {available}")
        arrays = handle[tree].arrays(branches, library="np", entry_stop=entry_stop)
    return _records_from_truth_arrays(arrays, coinc_ns=coinc_ns)
