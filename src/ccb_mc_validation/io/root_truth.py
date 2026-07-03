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


B_ARM_ID = 1  # Sci_bar_LayerID1: 1 = B arm, 2 = A arm
MOMENTUM_UNIT_TO_MEV = 1000.0  # Sci_bar_Momentum_* is stored in GeV/c


def _records_from_truth_arrays(arrays: Mapping[str, Any], *, coinc_ns: float = 15.0) -> dict[str, np.ndarray]:
    """Convert jagged event truth arrays into per-event study records.

    This is an event-level aggregate suitable for the current MV1-MV3 truth
    scaffolds.  It intentionally records provenance-friendly, label-safe fields:
    sample labels are computed from trigger-entry truth and event parity is not
    used for production Sample I/II assignment.

    Fixed 2026-07-03 (EXTERNAL_REVIEW_2026-07-02.md):
      * all per-event energy/depth aggregates are restricted to B-arm hits
        (LayerID restarts per arm, so cross-arm sums double-counted layers);
      * ``pdg`` is the species carrying the largest B-arm energy deposit, not
        the event's first hit (which can be a secondary);
      * ``tracklen`` is the maximum recorded track length among B-arm hits of
        the dominant species (previously the first jagged element of any arm);
      * ``ekin`` converts the GeV/c momentum branches to MeV/c before mixing
        with MeV masses (previously eV-scale nonsense energies).
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
        lay = np.asarray(layer[i], dtype=np.int16).reshape(-1)
        arm_i = np.asarray(arm[i], dtype=np.int16).reshape(-1)
        e = np.asarray(edep_j[i], dtype=np.float64).reshape(-1)
        pvals = np.asarray(pdg_j[i], dtype=np.int64).reshape(-1)
        tl = np.asarray(tracklen_j[i], dtype=np.float64).reshape(-1)
        px = np.asarray(px_j[i], dtype=np.float64).reshape(-1)
        py = np.asarray(py_j[i], dtype=np.float64).reshape(-1)
        pz = np.asarray(pz_j[i], dtype=np.float64).reshape(-1)

        usable = min(lay.size, arm_i.size, e.size, pvals.size)
        if usable == 0:
            continue
        b = arm_i[:usable] == B_ARM_ID
        lay_b = lay[:usable][b]
        e_b = e[:usable][b]
        p_b = pvals[:usable][b]
        if lay_b.size == 0:
            continue

        # dominant species: PDG carrying the largest summed B-arm deposit
        dom_pdg = 0
        dom_edep = -1.0
        for species in np.unique(p_b):
            s = float(e_b[p_b == species].sum())
            if s > dom_edep:
                dom_edep = s
                dom_pdg = int(species)
        pdg[i] = dom_pdg

        edep_l0[i] = float(e_b[lay_b == 0].sum())
        edep_l1[i] = float(e_b[lay_b == 1].sum())
        edep_tot[i] = float(e_b.sum())
        hit_layers = lay_b[e_b > 0]
        stop_layer[i] = int(hit_layers.max()) if hit_layers.size else int(lay_b.max())
        nlayers[i] = int(np.unique(lay_b).size)

        dom = p_b == dom_pdg
        if tl.size >= usable:
            tl_b = tl[:usable][b]
            tracklen[i] = float(tl_b[dom].max()) if tl_b[dom].size else 0.0
        if px.size >= usable and py.size >= usable and pz.size >= usable:
            pmag_b = np.sqrt(
                px[:usable][b] ** 2 + py[:usable][b] ** 2 + pz[:usable][b] ** 2
            ) * MOMENTUM_UNIT_TO_MEV
            mass = mass_of(dom_pdg) if dom_pdg else 0.0
            if mass and pmag_b[dom].size:
                p_entry = float(pmag_b[dom].max())  # entry hit carries the largest momentum
                ekin[i] = float(np.sqrt(p_entry * p_entry + mass * mass) - mass)
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
        # sample_label is EXCLUSIVE ("II" means Sample II minus Sample I) and
        # is kept for backward compatibility only. The physics definition is
        # INCLUSIVE — Sample I (A+B coincidence) is a subset of Sample II
        # (B entry, A ignored) — so analyses comparing the samples must use
        # the boolean flags below, not the label.
        "sample_label": sample_label,
        "sample_I": np.asarray(flags["sample_I"], dtype=bool),
        "sample_II": np.asarray(flags["sample_II"], dtype=bool),
        "enter_A": np.asarray(flags["enter_A"], dtype=bool),
        "enter_B": np.asarray(flags["enter_B"], dtype=bool),
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
