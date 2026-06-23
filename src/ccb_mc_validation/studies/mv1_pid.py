"""MV1: truth-level proton vs deuteron PID ceiling study."""

from __future__ import annotations

from typing import Any, Mapping

import numpy as np

from ccb_mc_validation.studies.common import (
    CutflowRecorder,
    StudyResult,
    StudyStatus,
    require_keys,
)
from ccb_mc_validation.studies.splits import SplitRegistry, legacy_parity_split

PROTON_PDG = 2212
DEUTERON_PDG = 1000010020
MV1_FEATURES = ("edep_l0", "edep_l1", "edep_tot", "stop_layer")
MIN_BINARY_SAMPLES = 2000


def _median(x: np.ndarray) -> float:
    return float(np.median(x)) if x.size else 0.0


def _build_feature_matrix(records: Mapping[str, np.ndarray], mask: np.ndarray) -> np.ndarray:
    return np.column_stack(
        [
            records["edep_l0"][mask],
            records["edep_l1"][mask],
            records["edep_tot"][mask],
            records["stop_layer"][mask].astype(float),
        ]
    )


def _purity_at_efficiency(scores: np.ndarray, labels: np.ndarray, eff: float = 0.90) -> float:
    pos = labels == 1
    if not pos.any():
        return 0.0
    thr = np.quantile(scores[pos], 1.0 - eff)
    sel = scores >= thr
    if not sel.any():
        return 0.0
    return float((labels[sel] == 1).mean())


def run_mv1(
    records: Mapping[str, np.ndarray],
    config: dict[str, Any] | None = None,
    *,
    split: SplitRegistry | None = None,
    fixture: bool = False,
) -> StudyResult:
    """
    Run MV1 PID ceiling study on per-track truth records.

    Truth labels come from entry PDG (proton vs deuteron binary task).
    Features: edep_l0, edep_l1, edep_tot, stop_layer.

    Train/test split defaults to legacy index parity (idx % 2 == 0 train) for
    parity with scripts/mv1_mv2_truth_pid_energy.py; pass SplitRegistry for
    registry-driven splits.
    """
    config = config or {}
    require_keys(records, ("pdg", "edep_l0", "edep_l1", "edep_tot", "stop_layer"))
    cutflow = CutflowRecorder()

    pdg = np.asarray(records["pdg"])
    cutflow.record("n_tracks", int(pdg.size))
    isp = pdg == PROTON_PDG
    isd = pdg == DEUTERON_PDG
    cutflow.record("n_proton", int(isp.sum()))
    cutflow.record("n_deuteron", int(isd.sum()))

    metrics: dict[str, Any] = {
        "n_tracks": int(pdg.size),
        "n_proton": int(isp.sum()),
        "n_deuteron": int(isd.sum()),
        "deltaE_E_medians": {
            "proton": {
                "edep_l0": _median(records["edep_l0"][isp]),
                "edep_l1": _median(records["edep_l1"][isp]),
                "edep_tot": _median(records["edep_tot"][isp]),
                "stop_layer": _median(records["stop_layer"][isp].astype(float)),
            },
            "deuteron": {
                "edep_l0": _median(records["edep_l0"][isd]),
                "edep_l1": _median(records["edep_l1"][isd]),
                "edep_tot": _median(records["edep_tot"][isd]),
                "stop_layer": _median(records["stop_layer"][isd].astype(float)),
            },
        },
    }

    mask = isp | isd
    cutflow.record("n_binary_pid", int(mask.sum()))
    notes = [
        "Legacy parity split: train = index % 2 == 0 (see scripts/mv1_mv2_truth_pid_energy.py).",
        "SplitRegistry supported via config mc_validation/splits.yaml.",
    ]

    status = StudyStatus.FIXTURE if fixture else StudyStatus.PRODUCTION
    if mask.sum() <= MIN_BINARY_SAMPLES:
        metrics["skipped_ml"] = f"insufficient binary samples ({int(mask.sum())} <= {MIN_BINARY_SAMPLES})"
        return StudyResult(
            study_id="MV1",
            status=status,
            metrics=metrics,
            cutflow=cutflow.as_dict(),
            notes=notes,
        )

    X = _build_feature_matrix(records, mask)
    y = isd[mask].astype(int)
    n = len(y)
    if split is None:
        split_name = config.get("split", "legacy_parity")
        if split_name == "legacy_parity":
            tr, te = legacy_parity_split(n)
        else:
            split = SplitRegistry.load(config.get("splits_config", "configs/mc_validation/splits.yaml"), split_name)
            tr, te = split.train_test_masks(n)
    else:
        tr, te = split.train_test_masks(n)

    metrics["split"] = split.name if split else config.get("split", "legacy_parity")

    try:
        from sklearn.ensemble import HistGradientBoostingClassifier
        from sklearn.linear_model import LogisticRegression
        from sklearn.metrics import roc_auc_score

        for name, model in (
            ("logreg", LogisticRegression(max_iter=500)),
            ("hgb", HistGradientBoostingClassifier()),
        ):
            model.fit(X[tr], y[tr])
            scores = model.predict_proba(X[te])[:, 1]
            metrics[f"{name}_auc"] = float(roc_auc_score(y[te], scores))
            metrics[f"{name}_purity_at_90eff"] = _purity_at_efficiency(scores, y[te], eff=0.90)
    except Exception as exc:
        metrics["_ml_error"] = str(exc)

    thr = float(np.median(np.concatenate([records["edep_l0"][isp], records["edep_l0"][isd]])))
    pred = (X[:, 0] > thr).astype(int)
    tp = int(((pred == 1) & (y == 1)).sum())
    fp = int(((pred == 1) & (y == 0)).sum())
    metrics["cut_edep_l0_thr_MeV"] = thr
    metrics["cut_purity"] = float(tp / (tp + fp)) if (tp + fp) > 0 else 0.0
    metrics["cut_efficiency"] = float(tp / max(int(y.sum()), 1))

    return StudyResult(
        study_id="MV1",
        status=status,
        metrics=metrics,
        cutflow=cutflow.as_dict(),
        notes=notes,
        provenance={"features": list(MV1_FEATURES)},
    )
