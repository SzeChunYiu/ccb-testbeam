"""MV1: truth-level proton vs deuteron PID ceiling study.

ML evaluation discipline (ML-001 / ML-002 / ML-003 / ML-004):

* The simple-cut PID threshold is fit on the TRAINING groups only and reported
  on the held-out test groups with a Wilson uncertainty (ML-001 — no same-set
  fit/evaluate leakage).
* The default train/test split is group-disjoint, keyed by ``event_id``
  (ML-002 — no row-index parity leakage across tracks of one event).
* Model failure or insufficient samples downgrade the study to FAILED / BLOCKED
  rather than publishing ``_ml_error`` / ``skipped_ml`` under PRODUCTION status
  (ML-003 — fail-closed; the validation layer additionally rejects any
  PRODUCTION result carrying those markers).
* Estimators carry explicit ``random_state`` and library versions are recorded
  in provenance (ML-004 — deterministic + reproducible).
"""

from __future__ import annotations

import platform
from typing import Any, Mapping

import numpy as np

from ccb_mc_validation.studies.common import (
    CutflowRecorder,
    StudyResult,
    StudyStatus,
    require_keys,
)
from ccb_mc_validation.studies.splits import SplitRegistry, default_group_split

PROTON_PDG = 2212
DEUTERON_PDG = 1000010020
MV1_FEATURES = ("edep_l0", "edep_l1", "edep_tot", "stop_layer")
MIN_BINARY_SAMPLES = 2000
DEFAULT_SPLIT_SEED = 171101


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


def _wilson_ci(successes: int, trials: int, z: float = 1.0) -> tuple[float, float]:
    """Approximate 1-sigma (z=1) Wilson interval for a binomial purity.

    Used as a held-out uncertainty on the simple-cut purity (ML-001). Returns
    (0, 0) when there are no test selections.
    """
    n = int(trials)
    if n <= 0:
        return 0.0, 0.0
    k = int(successes)
    phat = k / n
    denom = 1.0 + z * z / n
    center = (phat + z * z / (2 * n)) / denom
    half = z * np.sqrt(phat * (1 - phat) / n + z * z / (4 * n * n)) / denom
    return float(center - half), float(center + half)


def _library_versions() -> dict[str, str]:
    out: dict[str, str] = {"python": platform.python_version()}
    try:
        import numpy as _np

        out["numpy"] = _np.__version__
    except Exception:  # pragma: no cover - numpy is a hard dep
        pass
    try:
        import sklearn as _sk

        out["scikit-learn"] = _sk.__version__
    except Exception:
        out["scikit-learn"] = "unavailable"
    return out


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

    Train/test split defaults to a group-disjoint holdout keyed by
    ``records['event_id']`` (ML-002); pass a :class:`SplitRegistry` for
    registry-driven splits. When ``event_id`` is absent each track is treated as
    its own group (singleton groups cannot leak).
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
        "Group-disjoint default split keyed by event_id (ML-002); singleton groups "
        "when event_id absent.",
        "Simple-cut threshold fit on TRAIN groups, reported on held-out TEST (ML-001).",
    ]

    # ML-003: insufficient samples is a missing-precondition -> BLOCKED (never
    # PRODUCTION with a skipped_ml marker).
    if mask.sum() <= MIN_BINARY_SAMPLES:
        reason = f"insufficient binary samples ({int(mask.sum())} <= {MIN_BINARY_SAMPLES})"
        return StudyResult(
            study_id="MV1",
            status=StudyStatus.BLOCKED,
            metrics={**metrics, "reason": reason, "required_binary_samples": MIN_BINARY_SAMPLES},
            cutflow=cutflow.as_dict(),
            notes=notes + [f"BLOCKED: {reason} for ML evaluation."],
            provenance={"features": list(MV1_FEATURES)},
        )

    X = _build_feature_matrix(records, mask)
    y = isd[mask].astype(int)
    n = len(y)

    # ML-002: group-disjoint split over the masked subset. event_id is the
    # immutable group key; fall back to singleton groups (row index) only when
    # no group key is present (singletons cannot leak).
    full_groups = np.asarray(records.get("event_id", np.arange(len(pdg))))
    groups_sub = full_groups[mask]
    if split is None:
        tr, te = default_group_split(groups_sub, seed=DEFAULT_SPLIT_SEED)
        split_name = "default_group_holdout"
        split_strategy = "group_holdout"
    else:
        tr, te = split.train_test_masks(n, groups=groups_sub)
        split_name = split.name
        split_strategy = split.strategy

    metrics["split"] = split_name
    metrics["split_strategy"] = split_strategy
    metrics["n_train"] = int(tr.sum())
    metrics["n_test"] = int(te.sum())

    # ML-001: train/test masks lifted back to full-record indexing so the
    # simple-cut threshold can be fit on TRAIN protons/deuterons only.
    masked_idx = np.where(mask)[0]
    train_full = np.zeros(len(pdg), dtype=bool)
    test_full = np.zeros(len(pdg), dtype=bool)
    train_full[masked_idx[tr]] = True
    test_full[masked_idx[te]] = True

    # ML model evaluation (deterministic estimators, ML-004). Any failure is
    # fail-closed -> FAILED (ML-003); never swallowed under PRODUCTION.
    ml_failed = False
    ml_failure_msg = ""
    try:
        from sklearn.ensemble import HistGradientBoostingClassifier
        from sklearn.linear_model import LogisticRegression
        from sklearn.metrics import roc_auc_score

        for name, model in (
            ("logreg", LogisticRegression(max_iter=500, random_state=0)),
            ("hgb", HistGradientBoostingClassifier(random_state=0)),
        ):
            model.fit(X[tr], y[tr])
            scores = model.predict_proba(X[te])[:, 1]
            metrics[f"{name}_auc"] = float(roc_auc_score(y[te], scores))
            metrics[f"{name}_purity_at_90eff"] = _purity_at_efficiency(scores, y[te], eff=0.90)
    except Exception as exc:
        ml_failed = True
        ml_failure_msg = str(exc)
        notes.append(f"ML model failure (status -> FAILED): {exc}")

    # ML-001: simple-cut PID baseline. Threshold is fit on TRAIN protons +
    # deuterons only; purity / efficiency are HELD-OUT metrics on TEST with a
    # Wilson 1-sigma interval. Never fit and evaluate on the same set.
    edep_l0 = np.asarray(records["edep_l0"])
    train_pool = np.concatenate(
        [
            edep_l0[isp & train_full],
            edep_l0[isd & train_full],
        ]
    )
    thr = float(np.median(train_pool)) if train_pool.size else 0.0
    x_te = X[te, 0]
    y_te = y[te]
    pred_te = (x_te > thr).astype(int)
    tp = int(((pred_te == 1) & (y_te == 1)).sum())
    fp = int(((pred_te == 1) & (y_te == 0)).sum())
    purity = float(tp / (tp + fp)) if (tp + fp) > 0 else 0.0
    efficiency = float(tp / max(int(y_te.sum()), 1))
    ci_lo, ci_hi = _wilson_ci(tp, tp + fp)
    metrics["cut_edep_l0_thr_MeV"] = thr
    metrics["cut_purity_heldout"] = purity
    metrics["cut_purity_heldout_wilson68_low"] = ci_lo
    metrics["cut_purity_heldout_wilson68_high"] = ci_hi
    metrics["cut_efficiency_heldout"] = efficiency
    metrics["cut_n_train_fit"] = int((isp & train_full).sum() + (isd & train_full).sum())
    metrics["cut_n_test_eval"] = int(te.sum())

    # ML-003: status resolution. Model failure -> FAILED (the ML evaluation did
    # not complete); never PRODUCTION. fixture only softens a clean run.
    if ml_failed:
        status = StudyStatus.FAILED
        metrics["ml_failure"] = ml_failure_msg
    elif fixture:
        status = StudyStatus.FIXTURE
    else:
        status = StudyStatus.PRODUCTION

    provenance: dict[str, Any] = {
        "features": list(MV1_FEATURES),
        "split": {
            "name": split_name,
            "strategy": split_strategy,
            "group_key": "event_id",
            "n_train": int(tr.sum()),
            "n_test": int(te.sum()),
        },
        "estimators": {
            "logreg": "sklearn.linear_model.LogisticRegression(max_iter=500, random_state=0)",
            "hgb": "sklearn.ensemble.HistGradientBoostingClassifier(random_state=0)",
        },
        "versions": _library_versions(),
    }

    return StudyResult(
        study_id="MV1",
        status=status,
        metrics=metrics,
        cutflow=cutflow.as_dict(),
        notes=notes,
        provenance=provenance,
    )
