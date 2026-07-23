"""MV3: stopping-depth / stave profile and Sample I vs II mapping skeleton.

Fail-closed physics discipline (MV3-001 / MV3-002):

* Sample I/II membership MUST come from ``records['sample_label']``. When labels
  are absent or contain no Sample I/II entries the study is BLOCKED — physics
  categories are NEVER synthesized from event-id parity (MV3-001).
* Layer occupancy MUST be computed from an actual per-layer hit/energy mask
  (``records['layer_hits']`` or ``records['edep_per_layer']``). A layer is
  "crossed" only if the track has a hit / energy deposit there; the previous
  ``stop_layer >= lay`` assumption counted skipped layers as crossed. When no
  per-layer mask is available the study is BLOCKED rather than falling back to
  the leaking stop-layer proxy (MV3-002).

NOTE for the truth/ owner: ``layer_hits`` should be populated from the per-track
``edep_by_layer`` dict already built in ``truth/track_builder.py`` (a 2D bool
array, ``layer_hits[t, l]`` True iff track *t* deposited energy in layer *l*).
This module consumes that field; populating it is out of this study's scope.
"""

from __future__ import annotations

from typing import Any, Mapping

import numpy as np

from ccb_mc_validation.studies.common import CutflowRecorder, StudyResult, StudyStatus, require_keys

# B-stack stave mapping hypotheses (LayerID → readout stave label)
DEFAULT_LAYER_TO_STAVE = {
    0: "B2",
    1: "B2",
    2: "B4",
    3: "B4",
    4: "B6",
    5: "B6",
    6: "B8",
    7: "B8",
}


def _resolve_layer_hits(records: Mapping[str, np.ndarray], n_tracks: int) -> np.ndarray | None:
    """Return a 2D bool per-layer hit mask (n_tracks, n_layers) or None.

    Accepts either ``layer_hits`` (bool/int) or ``edep_per_layer`` (float;
    converted via ``> 0``). Returns None when absent so the caller can BLOCK.
    """
    raw = records.get("layer_hits")
    if raw is None:
        epl = records.get("edep_per_layer")
        if epl is not None:
            raw = np.asarray(epl) > 0
    if raw is None:
        return None
    arr = np.asarray(raw)
    if arr.dtype != bool:
        arr = arr.astype(bool)
    if arr.ndim != 2 or arr.shape[0] != n_tracks:
        return None
    return arr


def _layer_occupancy(layer_hits: np.ndarray, mask: np.ndarray, n_layers: int = 8) -> np.ndarray:
    """Fraction of tracks with an actual hit / energy deposit in each layer.

    A layer counts as occupied for a track ONLY if that track has a hit there
    (MV3-002). This deliberately does NOT infer crossing from ``stop_layer`` —
    a skipped layer is not counted as crossed.
    """
    sub = np.asarray(layer_hits)[mask, :n_layers]
    total = max(int(mask.sum()), 1)
    return sub.sum(axis=0) / total


def _score_mapping_hypothesis(
    truth_profile: np.ndarray,
    data_profile: np.ndarray,
) -> float:
    """Lower is better: L1 distance between normalized occupancy profiles."""
    t = truth_profile / max(truth_profile.sum(), 1e-9)
    d = data_profile / max(data_profile.sum(), 1e-9)
    return float(np.abs(t - d).sum())


def run_mv3(
    records: Mapping[str, np.ndarray],
    config: dict[str, Any] | None = None,
    *,
    data_profiles: Mapping[str, np.ndarray] | None = None,
    fixture: bool = False,
) -> StudyResult:
    """
    Run MV3 stopping-depth profile study.

    Computes layer occupancy profiles (from per-layer hit masks) for Sample I vs
    II (from ``sample_label``) and scores LayerID↔stave mapping hypotheses
    against optional data reference profiles.
    """
    config = config or {}
    require_keys(records, ("pdg", "stop_layer", "edep_tot"))
    cutflow = CutflowRecorder()
    pdg = np.asarray(records["pdg"])
    n_tracks = int(pdg.size)
    cutflow.record("n_tracks", n_tracks)

    n_layers = int(config.get("n_layers", 8))
    layer_to_stave = dict(config.get("layer_to_stave", DEFAULT_LAYER_TO_STAVE))

    # MV3-002: require an actual per-layer hit/energy mask. Refuse the
    # stop_layer proxy that counted skipped layers as crossed.
    layer_hits = _resolve_layer_hits(records, n_tracks)
    if layer_hits is None:
        return StudyResult(
            study_id="MV3",
            status=StudyStatus.BLOCKED,
            metrics={
                "reason": (
                    "layer_hits (2D per-layer hit/edep mask) absent or mis-shaped; "
                    "cannot compute occupancy via stop_layer proxy (MV3-002)."
                )
            },
            cutflow=cutflow.as_dict(),
            notes=[
                "BLOCKED: per-layer hit mask required for occupancy; stop_layer "
                "proxy removed (it counted skipped layers as crossed).",
                "truth/track_builder should populate records['layer_hits'] from "
                "its edep_by_layer dict (out of this study's scope).",
            ],
        )
    n_layers = min(n_layers, int(layer_hits.shape[1]))

    # MV3-001: Sample I/II must come from sample_label. Never synthesize from
    # event-id parity.
    sample_labels = records.get("sample_label")
    labels: np.ndarray | None = None
    if sample_labels is not None and len(sample_labels) > 0:
        labels = np.asarray(sample_labels).astype(str)
    if labels is None or not ((labels == "I").any() or (labels == "II").any()):
        return StudyResult(
            study_id="MV3",
            status=StudyStatus.BLOCKED,
            metrics={
                "reason": (
                    "sample_label absent or contains no Sample I/II entries; "
                    "refusing event-parity proxy for physics categories (MV3-001)."
                )
            },
            cutflow=cutflow.as_dict(),
            notes=[
                "BLOCKED: sample_label required; event_id parity proxy removed "
                "(never synthesize physics categories from parity).",
            ],
        )

    sample_i = labels == "I"
    sample_ii = labels == "II"
    cutflow.record("n_sample_I", int(sample_i.sum()))
    cutflow.record("n_sample_II", int(sample_ii.sum()))

    prof_i = _layer_occupancy(layer_hits, sample_i, n_layers=n_layers)
    prof_ii = _layer_occupancy(layer_hits, sample_ii, n_layers=n_layers)

    metrics: dict[str, Any] = {
        "layer_occupancy_sample_I": prof_i.tolist(),
        "layer_occupancy_sample_II": prof_ii.tolist(),
        "layer_to_stave_mapping": layer_to_stave,
        "mapping_hypothesis_scores": {},
        "occupancy_source": "records['layer_hits'] (per-layer hit mask; MV3-002)",
        "sample_source": "records['sample_label'] (MV3-001)",
    }

    # Aggregate truth profile by stave under current mapping hypothesis.
    # stop_layer (deepest hit layer) is a genuine per-track quantity, so the
    # stave stop-count remains meaningful.
    stave_order = sorted(set(layer_to_stave.values()))
    stave_truth = {s: 0.0 for s in stave_order}
    stop = records["stop_layer"]
    for lay, stave in layer_to_stave.items():
        stave_truth[stave] += float((stop == lay).sum())
    metrics["truth_stave_counts"] = stave_truth

    if data_profiles:
        for name, ref in data_profiles.items():
            ref_arr = np.asarray(ref, dtype=float)
            metrics["mapping_hypothesis_scores"][name] = _score_mapping_hypothesis(
                np.array([stave_truth[s] for s in stave_order]),
                ref_arr,
            )

    notes = [
        "Sample I/II from records['sample_label'] (MV3-001); event-parity proxy removed.",
        "Occupancy from records['layer_hits'] per-layer hit mask (MV3-002); a skipped "
        "layer is not counted as crossed.",
        "Mapping hypothesis scoring skeleton — lower L1 score is better match to data profile.",
    ]
    status = StudyStatus.FIXTURE if fixture else StudyStatus.PRODUCTION

    return StudyResult(
        study_id="MV3",
        status=status,
        metrics=metrics,
        cutflow=cutflow.as_dict(),
        notes=notes,
    )
