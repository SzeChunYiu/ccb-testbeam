"""Case-control sampling weights with multi-stage inclusion (issue #958)."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def apply_second_stage_class_cap(
    ml_rows: pd.DataFrame,
    *,
    max_sample: int,
    random_seed: int,
    class_column: str = "selected",
    weight_column: str = "sampling_weight",
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Apply per-class sample cap and update Horvitz–Thompson weights.

    Stage-1 weights are already ``1 / p(class)``. When the stage-2 without-
    replacement cap binds for a class (``n < N``), each retained row's inclusion
    probability is multiplied by ``n / N``, so the HT weight is multiplied by
    ``N / n``. When the cap does not bind, stage-2 factors are 1.
    """
    if ml_rows.empty:
        return ml_rows.copy(), {
            "stages": ["case_control_bernoulli", "per_class_cap"],
            "classes": {},
            "cap_bound": False,
        }

    if weight_column not in ml_rows.columns:
        raise ValueError(f"missing required weight column {weight_column!r}")
    if class_column not in ml_rows.columns:
        raise ValueError(f"missing required class column {class_column!r}")

    capped_parts: list[pd.DataFrame] = []
    class_meta: dict[str, Any] = {}
    any_bound = False
    for selected_value, subset in ml_rows.groupby(class_column, sort=True):
        n_available = int(len(subset))
        n_keep = min(n_available, int(max_sample))
        if n_keep < 1:
            continue
        stage2_p = float(n_keep) / float(n_available)
        stage2_factor = float(n_available) / float(n_keep)
        bound = n_keep < n_available
        any_bound = any_bound or bound
        taken = subset.sample(
            n=n_keep,
            random_state=int(random_seed) + int(selected_value),
        ).copy()
        stage1_w = taken[weight_column].to_numpy(dtype=float)
        if np.any(stage1_w <= 0) or not np.all(np.isfinite(stage1_w)):
            raise ValueError("stage-1 sampling weights must be finite and positive")
        stage1_p = 1.0 / stage1_w
        inclusion_p = stage1_p * stage2_p
        taken["stage1_inclusion_p"] = stage1_p
        taken["stage2_inclusion_p"] = stage2_p
        taken["inclusion_p"] = inclusion_p
        taken[weight_column] = 1.0 / inclusion_p
        capped_parts.append(taken)
        class_meta[str(int(selected_value))] = {
            "n_available": n_available,
            "n_kept": n_keep,
            "stage2_inclusion_p": stage2_p,
            "stage2_ht_factor": stage2_factor,
            "cap_bound": bound,
        }

    if not capped_parts:
        return ml_rows.iloc[0:0].copy(), {
            "stages": ["case_control_bernoulli", "per_class_without_replacement_cap"],
            "classes": class_meta,
            "cap_bound": any_bound,
            "n_rows": 0,
        }

    out = pd.concat(capped_parts, ignore_index=True)
    weights = out[weight_column].to_numpy(dtype=float)
    ess = float((np.sum(weights) ** 2) / np.sum(weights ** 2)) if weights.size else float("nan")
    manifest = {
        "stages": ["case_control_bernoulli", "per_class_without_replacement_cap"],
        "classes": class_meta,
        "cap_bound": any_bound,
        "n_rows": int(len(out)),
        "effective_sample_size": ess,
        "max_weight": float(np.max(weights)) if weights.size else float("nan"),
        "sum_weight": float(np.sum(weights)) if weights.size else 0.0,
        "weight_semantics": "horvitz_thompson_two_stage_case_control",
    }
    return out, manifest
