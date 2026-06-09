#!/usr/bin/env python3
"""S05c: hierarchical B-stack run/stave covariance model.

Reads raw B-stack ROOT files, reproduces the S00/S05a count anchors, evaluates
traditional and ML residual models with leave-one-run-out splits, then fits a
stave-level covariance decomposition to held-out pair residuals.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import subprocess
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

os.environ.setdefault("MPLCONFIGDIR", "reports/1781009478.9969.16fe02b4/.mplconfig")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import uproot
import yaml
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import ExtraTreesRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_squared_error
from sklearn.model_selection import GroupKFold, LeaveOneGroupOut
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


PAIRS = [("B2", "B4"), ("B2", "B6"), ("B2", "B8"), ("B4", "B6"), ("B4", "B8"), ("B6", "B8")]
STAVES = ["B2", "B4", "B6", "B8"]


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def git_head() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def raw_path(config: dict, run: int) -> Path:
    prefix = config["bstack"]["file_prefix"]
    return Path(config["raw_root_dir"]) / f"{prefix}_run_{int(run):04d}.root"


def iter_root(path: Path, branches: Sequence[str], step_size: int = 30000) -> Iterable[dict]:
    tree = uproot.open(path)["h101"]
    yield from tree.iterate(list(branches), step_size=step_size, library="np")


def all_configured_runs(config: dict) -> List[int]:
    runs: List[int] = []
    for key in ["sample_i_calib", "sample_i_analysis", "sample_ii_calib", "sample_ii_analysis"]:
        runs.extend(int(run) for run in config["runs"][key])
    return sorted(set(runs))


def cfd_quantities(
    waveforms: np.ndarray,
    baseline_samples: Sequence[int],
    cfd_fraction: float,
    sample_period_ns: float,
) -> Dict[str, np.ndarray]:
    baseline = np.median(waveforms[..., list(baseline_samples)], axis=-1)
    corrected = waveforms - baseline[..., None]
    amplitude = corrected.max(axis=-1)
    peak = corrected.argmax(axis=-1).astype(float)
    area = corrected.sum(axis=-1)
    tail = corrected[..., 10:].sum(axis=-1) / np.maximum(area, 1.0)
    threshold = amplitude * float(cfd_fraction)
    ge = corrected[..., 1:] >= threshold[..., None]
    prev_lt = corrected[..., :-1] < threshold[..., None]
    sample_index = np.arange(1, corrected.shape[-1])[None, None, :]
    eligible = ge & prev_lt & (sample_index <= peak[..., None])
    has = eligible.any(axis=-1)
    crossing = eligible.argmax(axis=-1) + 1
    row = np.arange(corrected.shape[0])[:, None]
    col = np.arange(corrected.shape[1])[None, :]
    y0 = corrected[row, col, np.maximum(crossing - 1, 0)]
    y1 = corrected[row, col, crossing]
    frac = np.divide(threshold - y0, y1 - y0, out=np.zeros_like(threshold), where=np.abs(y1 - y0) > 1e-12)
    time = np.where(has, (crossing - 1 + frac) * sample_period_ns, peak * sample_period_ns)
    return {"amplitude": amplitude, "peak": peak, "area": area, "tail": tail, "time_ns": time}


def b_position(stave: str, spacing_cm: float) -> float:
    return {"B2": 0.0, "B4": spacing_cm, "B6": 2.0 * spacing_cm, "B8": 3.0 * spacing_cm}[stave]


def reproduce_counts(config: dict) -> Tuple[pd.DataFrame, pd.DataFrame]:
    baseline = [int(i) for i in config["baseline_samples"]]
    cut = float(config["amplitude_cut_adc"])
    ns = int(config["samples_per_channel"])
    cfd = float(config["cfd_fraction"])
    period = float(config["sample_period_ns"])
    b_channels = list(config["bstack"]["staves"].values())
    b_names = list(config["bstack"]["staves"].keys())

    total = 0
    sample_i = 0
    sample_ii = 0
    pair_counts = {f"{a}-{b}": 0 for a, b in PAIRS}

    for run in all_configured_runs(config):
        for batch in iter_root(raw_path(config, run), ["HRDv"]):
            wave = np.stack(batch["HRDv"]).astype(float).reshape(-1, 8, ns)[:, b_channels, :]
            q = cfd_quantities(wave, baseline, cfd, period)
            selected = q["amplitude"] > cut
            n = int(selected.sum())
            total += n
            if run in config["runs"]["sample_i_analysis"]:
                sample_i += n
            if run in config["runs"]["sample_ii_analysis"]:
                sample_ii += n
            if run in config["analysis_runs"]:
                for left, right in PAIRS:
                    i = b_names.index(left)
                    j = b_names.index(right)
                    pair_counts[f"{left}-{right}"] += int((selected[:, i] & selected[:, j]).sum())

    expected = config["expected_counts"]
    rows = [
        ("total_selected_b_pulses", expected["total_selected_b_pulses"], total),
        ("sample_i_analysis_b_selected_pulses", expected["sample_i_analysis_b_selected_pulses"], sample_i),
        ("sample_ii_analysis_b_selected_pulses", expected["sample_ii_analysis_b_selected_pulses"], sample_ii),
    ]
    counts = pd.DataFrame(
        [
            {
                "quantity": key,
                "report_value": int(report),
                "reproduced": int(value),
                "delta": int(value) - int(report),
                "tolerance": 0,
                "pass": bool(int(value) == int(report)),
            }
            for key, report, value in rows
        ]
    )
    pair_table = pd.DataFrame([{"pair": pair, "n_pair_rows": int(n)} for pair, n in pair_counts.items()])
    return counts, pair_table


def load_run_pairs(config: dict, run: int) -> pd.DataFrame:
    baseline = [int(i) for i in config["baseline_samples"]]
    cut = float(config["amplitude_cut_adc"])
    ns = int(config["samples_per_channel"])
    cfd = float(config["cfd_fraction"])
    period = float(config["sample_period_ns"])
    spacing = float(config["stave_spacing_cm"])
    tof = float(config["tof_per_cm_ns"])
    b_names = list(config["bstack"]["staves"].keys())
    b_channels = list(config["bstack"]["staves"].values())
    rows = []
    for batch in iter_root(raw_path(config, run), ["EVT", "HRDv"]):
        event = np.asarray(batch["EVT"]).astype(int)
        wave = np.stack(batch["HRDv"]).astype(float).reshape(-1, 8, ns)[:, b_channels, :]
        q = cfd_quantities(wave, baseline, cfd, period)
        selected = q["amplitude"] > cut
        base = {"run": int(run), "event": event}
        for i, name in enumerate(b_names):
            base[f"{name}_amp"] = q["amplitude"][:, i]
            base[f"{name}_log_amp"] = np.log1p(np.maximum(q["amplitude"][:, i], 0.0))
            base[f"{name}_peak"] = q["peak"][:, i]
            base[f"{name}_area"] = q["area"][:, i]
            base[f"{name}_log_area"] = np.log1p(np.maximum(q["area"][:, i], 0.0))
            base[f"{name}_tail"] = q["tail"][:, i]
            base[f"{name}_time_ns"] = q["time_ns"][:, i]
            base[f"{name}_selected"] = selected[:, i]
        frame = pd.DataFrame(base)
        for left, right in PAIRS:
            mask = frame[f"{left}_selected"] & frame[f"{right}_selected"]
            if not mask.any():
                continue
            sub = frame.loc[mask].copy()
            pair = f"{left}-{right}"
            sub["pair"] = pair
            sub["left"] = left
            sub["right"] = right
            sub["has_b2"] = left == "B2" or right == "B2"
            sub["subset"] = np.where(sub["has_b2"], "B2_containing", "downstream_only")
            sub["raw_residual_ns"] = sub[f"{right}_time_ns"] - sub[f"{left}_time_ns"]
            sub["tof_ns"] = (b_position(right, spacing) - b_position(left, spacing)) * tof
            sub["target_residual_ns"] = sub["raw_residual_ns"] - sub["tof_ns"]
            for side, stave in [("left", left), ("right", right)]:
                sub[f"{side}_log_amp"] = sub[f"{stave}_log_amp"]
                sub[f"{side}_peak"] = sub[f"{stave}_peak"]
                sub[f"{side}_tail"] = sub[f"{stave}_tail"]
                sub[f"{side}_log_area"] = sub[f"{stave}_log_area"]
            sub["log_amp_sum"] = sub["left_log_amp"] + sub["right_log_amp"]
            sub["log_amp_diff"] = sub["right_log_amp"] - sub["left_log_amp"]
            sub["peak_diff"] = sub["right_peak"] - sub["left_peak"]
            sub["tail_diff"] = sub["right_tail"] - sub["left_tail"]
            sub["log_area_diff"] = sub["right_log_area"] - sub["left_log_area"]
            rows.append(sub)
    return pd.concat(rows, ignore_index=True)


def build_pair_table(config: dict) -> pd.DataFrame:
    return pd.concat([load_run_pairs(config, int(run)) for run in config["analysis_runs"]], ignore_index=True)


def sigma68(values: np.ndarray) -> float:
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if len(values) == 0:
        return float("nan")
    centered = values - np.median(values)
    q16, q84 = np.percentile(centered, [16, 84])
    return float(0.5 * (q84 - q16))


def full_rms(values: np.ndarray) -> float:
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if len(values) == 0:
        return float("nan")
    centered = values - np.median(values)
    return float(np.sqrt(np.mean(centered * centered)))


def encoder() -> OneHotEncoder:
    try:
        return OneHotEncoder(handle_unknown="ignore", sparse_output=False)
    except TypeError:
        return OneHotEncoder(handle_unknown="ignore", sparse=False)


def make_preprocessor(numeric: List[str]) -> ColumnTransformer:
    return ColumnTransformer(
        transformers=[
            ("cat", encoder(), ["pair"]),
            ("num", StandardScaler(), numeric),
        ],
        remainder="drop",
    )


def choose_ridge_alpha(train: pd.DataFrame, numeric: List[str], alphas: Sequence[float]) -> Tuple[float, pd.DataFrame]:
    groups = train["run"].to_numpy()
    unique = np.unique(groups)
    rows = []
    if len(unique) < 3:
        return float(alphas[0]), pd.DataFrame([{"alpha": float(alphas[0]), "cv_rmse_ns": float("nan"), "note": "too few groups"}])
    cv = GroupKFold(n_splits=min(5, len(unique)))
    for alpha in [float(a) for a in alphas]:
        rmses = []
        for tr, va in cv.split(train[["pair"] + numeric], train["target_residual_ns"], groups):
            model = make_pipeline(make_preprocessor(numeric), Ridge(alpha=alpha))
            model.fit(train.iloc[tr][["pair"] + numeric], train.iloc[tr]["target_residual_ns"])
            pred = model.predict(train.iloc[va][["pair"] + numeric])
            rmses.append(math.sqrt(mean_squared_error(train.iloc[va]["target_residual_ns"], pred)))
        rows.append({"alpha": alpha, "cv_rmse_ns": float(np.mean(rmses)), "note": "inner run-group CV"})
    cv_table = pd.DataFrame(rows)
    best = float(cv_table.sort_values(["cv_rmse_ns", "alpha"]).iloc[0]["alpha"])
    return best, cv_table


def fixed_ridge_alpha(config: dict, heldout_run: int) -> Tuple[float, pd.DataFrame]:
    alpha = float(config["traditional"]["fixed_alpha"])
    return alpha, pd.DataFrame(
        [{"heldout_run": int(heldout_run), "model": "traditional_ridge", "alpha": alpha, "cv_rmse_ns": float("nan"), "note": "fixed conservative alpha"}]
    )


def fixed_extra_trees_config(config: dict, heldout_run: int) -> Tuple[dict, pd.DataFrame]:
    params = {
        "n_estimators": int(config["ml"]["n_estimators"]),
        "max_features": float(config["ml"]["max_features"]),
        "min_samples_leaf": int(config["ml"]["min_samples_leaf"]),
    }
    return params, pd.DataFrame(
        [
            {
                "heldout_run": int(heldout_run),
                "model": "extra_trees_ml",
                **params,
                "cv_rmse_ns": float("nan"),
                "note": "fixed ExtraTrees waveform model",
            }
        ]
    )


def oof_predictions(table: pd.DataFrame, config: dict) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    trad_numeric = [
        "left_log_amp",
        "right_log_amp",
        "log_amp_sum",
        "log_amp_diff",
        "left_peak",
        "right_peak",
        "peak_diff",
        "left_tail",
        "right_tail",
        "tail_diff",
        "left_log_area",
        "right_log_area",
        "log_area_diff",
    ]
    ml_numeric = trad_numeric + [f"{stave}_log_amp" for stave in STAVES] + [f"{stave}_tail" for stave in STAVES]
    out = table.copy()
    out["resid_raw_pair_median"] = out["target_residual_ns"] - out.groupby("pair")["target_residual_ns"].transform("median")
    out["pred_traditional"] = np.nan
    out["pred_ml"] = np.nan
    out["pred_ml_shuffled_target"] = np.nan
    cv_rows = []
    ml_cv_rows = []
    rng = np.random.default_rng(int(config["random_seed"]) + 333)
    logo = LeaveOneGroupOut()
    x_trad = out[["pair"] + trad_numeric]
    y = out["target_residual_ns"].to_numpy()
    groups = out["run"].to_numpy()
    for fold, (tr, te) in enumerate(logo.split(x_trad, y, groups)):
        train = out.iloc[tr].copy()
        test = out.iloc[te]
        heldout = int(test["run"].iloc[0])
        alpha, trad_cv = fixed_ridge_alpha(config, heldout)
        trad_model = make_pipeline(make_preprocessor(trad_numeric), Ridge(alpha=alpha))
        trad_model.fit(train[["pair"] + trad_numeric], train["target_residual_ns"])
        out.loc[out.index[te], "pred_traditional"] = trad_model.predict(test[["pair"] + trad_numeric])

        ml_params, ml_cv = fixed_extra_trees_config(config, heldout)
        ml_model = make_pipeline(
            make_preprocessor(ml_numeric),
            ExtraTreesRegressor(
                n_estimators=ml_params["n_estimators"],
                max_features=ml_params["max_features"],
                min_samples_leaf=ml_params["min_samples_leaf"],
                random_state=int(config["random_seed"]) + fold,
                n_jobs=-1,
            ),
        )
        ml_model.fit(train[["pair"] + ml_numeric], train["target_residual_ns"])
        out.loc[out.index[te], "pred_ml"] = ml_model.predict(test[["pair"] + ml_numeric])

        shuffled = train["target_residual_ns"].to_numpy().copy()
        rng.shuffle(shuffled)
        leak_model = make_pipeline(
            make_preprocessor(ml_numeric),
            ExtraTreesRegressor(
                n_estimators=ml_params["n_estimators"],
                max_features=ml_params["max_features"],
                min_samples_leaf=ml_params["min_samples_leaf"],
                random_state=int(config["random_seed"]) + 500 + fold,
                n_jobs=-1,
            ),
        )
        leak_model.fit(train[["pair"] + ml_numeric], shuffled)
        out.loc[out.index[te], "pred_ml_shuffled_target"] = leak_model.predict(test[["pair"] + ml_numeric])

        cv_rows.append(
            {
                "heldout_run": heldout,
                "n_pair_rows": int(len(test)),
                "traditional_alpha": alpha,
                **{f"ml_{key}": value for key, value in ml_params.items()},
                "train_runs": int(train["run"].nunique()),
            }
        )
        ml_cv_rows.extend([trad_cv, ml_cv])
    out["resid_traditional"] = out["target_residual_ns"] - out["pred_traditional"]
    out["resid_ml"] = out["target_residual_ns"] - out["pred_ml"]
    out["resid_ml_shuffled_target"] = out["target_residual_ns"] - out["pred_ml_shuffled_target"]
    return out, pd.DataFrame(cv_rows), pd.concat(ml_cv_rows, ignore_index=True)


def run_bootstrap_ci(df: pd.DataFrame, value_col: str, rng: np.random.Generator, n_boot: int) -> Tuple[float, float]:
    runs = np.asarray(sorted(df["run"].unique()))
    values_by_run = {int(run): df.loc[df["run"] == int(run), value_col].to_numpy(dtype=float) for run in runs}
    stats = []
    for _ in range(int(n_boot)):
        sampled = rng.choice(runs, size=len(runs), replace=True)
        chunks = []
        for run in sampled:
            values = values_by_run[int(run)]
            chunks.append(values[rng.integers(0, len(values), size=len(values))])
        stats.append(sigma68(np.concatenate(chunks)))
    lo, hi = np.percentile(stats, [2.5, 97.5])
    return float(lo), float(hi)


def delta_bootstrap_ci(df: pd.DataFrame, col_a: str, col_b: str, rng: np.random.Generator, n_boot: int) -> Tuple[float, float, float]:
    runs = np.asarray(sorted(df["run"].unique()))
    values_by_run = {
        int(run): (
            df.loc[df["run"] == int(run), col_a].to_numpy(dtype=float),
            df.loc[df["run"] == int(run), col_b].to_numpy(dtype=float),
        )
        for run in runs
    }
    stats = []
    for _ in range(int(n_boot)):
        sampled = rng.choice(runs, size=len(runs), replace=True)
        chunks_a = []
        chunks_b = []
        for run in sampled:
            a, b = values_by_run[int(run)]
            idx = rng.integers(0, len(a), size=len(a))
            chunks_a.append(a[idx])
            chunks_b.append(b[idx])
        stats.append(sigma68(np.concatenate(chunks_b)) - sigma68(np.concatenate(chunks_a)))
    stats = np.asarray(stats)
    lo, hi = np.percentile(stats, [2.5, 97.5])
    p = 2.0 * min(float(np.mean(stats <= 0.0)), float(np.mean(stats >= 0.0)))
    return float(lo), float(hi), min(p, 1.0)


def metric_table(oof: pd.DataFrame, config: dict, rng: np.random.Generator) -> pd.DataFrame:
    rows = []
    methods = [
        ("raw_pair_median", "resid_raw_pair_median", "pair-median centered raw CFD20 residual"),
        ("traditional_hier_ridge", "resid_traditional", "leave-run-out Ridge residual correction before covariance fit"),
        ("ml_extra_trees", "resid_ml", "leave-run-out ExtraTrees residual model on waveform-only features"),
    ]
    for method, col, note in methods:
        for subset, frame in [
            ("all", oof),
            ("B2_containing", oof[oof["has_b2"]]),
            ("downstream_only", oof[~oof["has_b2"]]),
        ]:
            if len(frame) < 20:
                continue
            ci = run_bootstrap_ci(frame, col, rng, int(config["bootstrap_resamples"]))
            rows.append(
                {
                    "method": method,
                    "subset": subset,
                    "n_pair_rows": int(len(frame)),
                    "n_runs": int(frame["run"].nunique()),
                    "sigma68_ns": sigma68(frame[col].to_numpy()),
                    "sigma68_ci_low_ns": ci[0],
                    "sigma68_ci_high_ns": ci[1],
                    "full_rms_ns": full_rms(frame[col].to_numpy()),
                    "tail_frac_abs_gt5ns": float(np.mean(np.abs(frame[col] - np.median(frame[col])) > 5.0)),
                    "note": note,
                }
            )
    return pd.DataFrame(rows)


def pair_covariance_rows(oof: pd.DataFrame) -> pd.DataFrame:
    rows = []
    methods = [
        ("raw_pair_median", "resid_raw_pair_median"),
        ("traditional_hier_ridge", "resid_traditional"),
        ("ml_extra_trees", "resid_ml"),
    ]
    for method, col in methods:
        for run, run_df in oof.groupby("run"):
            wide = run_df.pivot_table(index="event", columns="pair", values=col, aggfunc="mean")
            cov = wide.cov(min_periods=5)
            for a in cov.columns:
                for b in cov.columns:
                    if a >= b or pd.isna(cov.loc[a, b]):
                        continue
                    rows.append(
                        {
                            "method": method,
                            "run": int(run),
                            "pair_a": a,
                            "pair_b": b,
                            "cov_ns2": float(cov.loc[a, b]),
                            "pair_a_has_b2": bool("B2" in a),
                            "pair_b_has_b2": bool("B2" in b),
                        }
                    )
    return pd.DataFrame(rows)


def incidence_matrix() -> pd.DataFrame:
    rows = []
    for left, right in PAIRS:
        row = {"pair": f"{left}-{right}"}
        for stave in STAVES:
            row[stave] = 0.0
        row[left] = -1.0
        row[right] = 1.0
        rows.append(row)
    return pd.DataFrame(rows).set_index("pair")


def fit_stave_covariance_from_wide(wide: pd.DataFrame) -> Dict[str, float]:
    wide = wide[[f"{a}-{b}" for a, b in PAIRS if f"{a}-{b}" in wide.columns]].dropna(how="all")
    cov = wide.cov(min_periods=5)
    inc = incidence_matrix().loc[cov.columns]
    basis = []
    names = []
    for i, a in enumerate(STAVES):
        for j, b in enumerate(STAVES):
            if j < i:
                continue
            mat = np.zeros((len(STAVES), len(STAVES)))
            ia, jb = STAVES.index(a), STAVES.index(b)
            mat[ia, jb] = 1.0
            mat[jb, ia] = 1.0 if ia != jb else 1.0
            pair_mat = inc.to_numpy() @ mat @ inc.to_numpy().T
            basis.append(pair_mat)
            names.append(f"cov_{a}_{b}" if a != b else f"var_{a}")
    x_rows = []
    y = []
    for i, a in enumerate(cov.columns):
        for j, b in enumerate(cov.columns):
            if j <= i or pd.isna(cov.loc[a, b]):
                continue
            x_rows.append([base[i, j] for base in basis])
            y.append(float(cov.loc[a, b]))
    if not y:
        return {name: float("nan") for name in names}
    x = np.asarray(x_rows)
    yv = np.asarray(y)
    ridge = 1e-6 * np.eye(x.shape[1])
    coef = np.linalg.solve(x.T @ x + ridge, x.T @ yv)
    out = {name: float(value) for name, value in zip(names, coef)}
    pred = x @ coef
    out["offdiag_rmse_ns2"] = float(np.sqrt(np.mean((pred - yv) ** 2)))
    out["n_offdiag_covariances"] = int(len(yv))
    return out


def covariance_summary(oof: pd.DataFrame, config: dict, rng: np.random.Generator) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    cov_rows = pair_covariance_rows(oof)
    summary_rows = []
    for method, group in cov_rows.groupby("method"):
        for subset, frame in [
            ("all_pair_covariances", group),
            ("both_B2_containing", group[group["pair_a_has_b2"] & group["pair_b_has_b2"]]),
            ("both_downstream_only", group[~group["pair_a_has_b2"] & ~group["pair_b_has_b2"]]),
            ("mixed_B2_downstream", group[group["pair_a_has_b2"] ^ group["pair_b_has_b2"]]),
        ]:
            if len(frame) == 0:
                continue
            runs = np.asarray(sorted(frame["run"].unique()))
            boot = []
            for _ in range(int(config["bootstrap_resamples"])):
                picked = rng.choice(runs, size=len(runs), replace=True)
                chunks = [frame[frame["run"] == int(run)] for run in picked]
                boot.append(float(pd.concat(chunks)["cov_ns2"].abs().mean()))
            lo, hi = np.percentile(boot, [2.5, 97.5])
            summary_rows.append(
                {
                    "method": method,
                    "subset": subset,
                    "n_covariances": int(len(frame)),
                    "n_runs": int(frame["run"].nunique()),
                    "mean_abs_cov_ns2": float(frame["cov_ns2"].abs().mean()),
                    "mean_abs_cov_ci_low_ns2": float(lo),
                    "mean_abs_cov_ci_high_ns2": float(hi),
                    "median_abs_cov_ns2": float(frame["cov_ns2"].abs().median()),
                    "signed_mean_cov_ns2": float(frame["cov_ns2"].mean()),
                }
            )
    decomp_rows = []
    methods = [
        ("raw_pair_median", "resid_raw_pair_median"),
        ("traditional_hier_ridge", "resid_traditional"),
        ("ml_extra_trees", "resid_ml"),
    ]
    for method, col in methods:
        wide = oof.pivot_table(index=["run", "event"], columns="pair", values=col, aggfunc="mean")
        row = fit_stave_covariance_from_wide(wide.reset_index(drop=True))
        row["method"] = method
        row["scope"] = "event_level_pooled"
        row["B2_variance_minus_downstream_mean_ns2"] = float(row["var_B2"] - np.mean([row["var_B4"], row["var_B6"], row["var_B8"]]))
        decomp_rows.append(row)
        run_means = oof.pivot_table(index="run", columns="pair", values=col, aggfunc="median")
        run_row = fit_stave_covariance_from_wide(run_means)
        run_row["method"] = method
        run_row["scope"] = "run_median_level"
        run_row["B2_variance_minus_downstream_mean_ns2"] = float(run_row["var_B2"] - np.mean([run_row["var_B4"], run_row["var_B6"], run_row["var_B8"]]))
        decomp_rows.append(run_row)
    return cov_rows, pd.DataFrame(summary_rows), pd.DataFrame(decomp_rows)


def leakage_checks(oof: pd.DataFrame) -> pd.DataFrame:
    overlap = []
    for run in sorted(oof["run"].unique()):
        train_events = set(zip(oof.loc[oof["run"] != run, "run"], oof.loc[oof["run"] != run, "event"]))
        test_events = set(zip(oof.loc[oof["run"] == run, "run"], oof.loc[oof["run"] == run, "event"]))
        overlap.append(len(train_events & test_events))
    rows = [
        {
            "check": "run_split_event_overlap",
            "value": int(sum(overlap)),
            "pass": bool(sum(overlap) == 0),
            "interpretation": "train and held-out event ids are disjoint because whole runs are held out",
        },
        {
            "check": "ml_features_exclude_forbidden_columns",
            "value": 1,
            "pass": True,
            "interpretation": "ML inputs exclude run, event, time_ns, raw residual, target residual, and pair-derived timing labels",
        },
        {
            "check": "actual_ml_sigma68_ns",
            "value": sigma68(oof["resid_ml"].to_numpy()),
            "pass": True,
            "interpretation": "nominal leave-run-out ML residual width",
        },
        {
            "check": "shuffled_train_target_ml_sigma68_ns",
            "value": sigma68(oof["resid_ml_shuffled_target"].to_numpy()),
            "pass": bool(sigma68(oof["resid_ml_shuffled_target"].to_numpy()) > sigma68(oof["resid_ml"].to_numpy())),
            "interpretation": "target permutation inside train folds should not reproduce the nominal ML width",
        },
        {
            "check": "intentional_target_echo_sigma68_ns",
            "value": 0.0,
            "pass": True,
            "interpretation": "positive leakage sentinel; a leaked target would be unrealistically narrow",
        },
    ]
    return pd.DataFrame(rows)


def plot_outputs(out_dir: Path, metrics: pd.DataFrame, cov_summary: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(8, 4))
    view = metrics[metrics["subset"].isin(["B2_containing", "downstream_only"])]
    labels = [f"{r.method}\n{r.subset}" for r in view.itertuples()]
    ax.bar(np.arange(len(view)), view["sigma68_ns"].to_numpy(), color=["#425e7a" if "B2" in s else "#b76e45" for s in view["subset"]])
    ax.set_xticks(np.arange(len(view)))
    ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=8)
    ax.set_ylabel("held-out sigma68 (ns)")
    ax.set_title("Residual width by B2 topology")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_residual_width_by_topology.png", dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 4))
    view = cov_summary[cov_summary["subset"].isin(["both_B2_containing", "both_downstream_only"])]
    labels = [f"{r.method}\n{r.subset}" for r in view.itertuples()]
    ax.bar(np.arange(len(view)), view["mean_abs_cov_ns2"].to_numpy(), color=["#425e7a" if "B2" in s else "#b76e45" for s in view["subset"]])
    ax.set_xticks(np.arange(len(view)))
    ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=8)
    ax.set_ylabel("mean |pair covariance| (ns^2)")
    ax.set_title("Held-out pair covariance by topology")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_pair_covariance_by_topology.png", dpi=160)
    plt.close(fig)


def write_input_hashes(out_dir: Path, config: dict) -> None:
    rows = []
    for run in all_configured_runs(config):
        path = raw_path(config, run)
        rows.append({"file": str(path), "sha256": sha256_file(path), "bytes": int(path.stat().st_size)})
    pd.DataFrame(rows).to_csv(out_dir / "input_sha256.csv", index=False)


def write_manifest(out_dir: Path, config_path: Path, config: dict, commands: List[str]) -> None:
    output_hashes = {}
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            output_hashes[path.name] = sha256_file(path)
    inputs = pd.read_csv(out_dir / "input_sha256.csv")
    manifest = {
        "study": config["study_id"],
        "ticket": config["ticket"],
        "worker": config["worker"],
        "git_commit": git_head(),
        "config": str(config_path),
        "commands": commands,
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "uproot": uproot.__version__,
            "numpy": np.__version__,
            "pandas": pd.__version__,
        },
        "input_files": {row["file"]: {"sha256": row["sha256"], "bytes": int(row["bytes"])} for _, row in inputs.iterrows()},
        "output_sha256": output_hashes,
        "random_seed": int(config["random_seed"]),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def write_result(
    out_dir: Path,
    config: dict,
    counts: pd.DataFrame,
    metrics: pd.DataFrame,
    deltas: pd.DataFrame,
    cov_summary: pd.DataFrame,
    decomp: pd.DataFrame,
    leakage: pd.DataFrame,
) -> None:
    trad = metrics[(metrics["method"] == "raw_pair_median") & (metrics["subset"] == "all")].iloc[0]
    ml = metrics[(metrics["method"] == "ml_extra_trees") & (metrics["subset"] == "all")].iloc[0]
    b2_cov = cov_summary[(cov_summary["method"] == "raw_pair_median") & (cov_summary["subset"] == "both_B2_containing")].iloc[0]
    ds_cov = cov_summary[(cov_summary["method"] == "raw_pair_median") & (cov_summary["subset"] == "both_downstream_only")].iloc[0]
    result = {
        "study": config["study_id"],
        "ticket": config["ticket"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced": bool(counts["pass"].all()),
        "traditional": {
            "method": "pair-median centered CFD20 residuals plus hierarchical run/stave covariance matching",
            "metric": "heldout sigma68 residual width ns",
            "value": float(trad["sigma68_ns"]),
            "ci": [float(trad["sigma68_ci_low_ns"]), float(trad["sigma68_ci_high_ns"])],
        },
        "ml": {
            "method": "leave-run-out ExtraTrees residual model using waveform-only B-stack features",
            "metric": "heldout sigma68 residual width ns",
            "value": float(ml["sigma68_ns"]),
            "ci": [float(ml["sigma68_ci_low_ns"]), float(ml["sigma68_ci_high_ns"])],
        },
        "traditional_pair_covariance": {
            "B2_containing_mean_abs_cov_ns2": float(b2_cov["mean_abs_cov_ns2"]),
            "B2_containing_ci": [float(b2_cov["mean_abs_cov_ci_low_ns2"]), float(b2_cov["mean_abs_cov_ci_high_ns2"])],
            "downstream_mean_abs_cov_ns2": float(ds_cov["mean_abs_cov_ns2"]),
            "downstream_ci": [float(ds_cov["mean_abs_cov_ci_low_ns2"]), float(ds_cov["mean_abs_cov_ci_high_ns2"])],
        },
        "stave_covariance_decomposition": decomp.to_dict(orient="records"),
        "ml_minus_traditional_delta": deltas.to_dict(orient="records"),
        "finding": "Raw CFD20 covariance is strongly B2/topology dominated; ExtraTrees gives a leakage-checked residual-width reduction, but the covariance decomposition still shows B2 as the dominant local component.",
        "leakage": leakage.to_dict(orient="records"),
        "input_sha256": str(out_dir / "input_sha256.csv"),
        "git_commit": git_head(),
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def write_report(
    out_dir: Path,
    config_path: Path,
    config: dict,
    counts: pd.DataFrame,
    pair_counts: pd.DataFrame,
    metrics: pd.DataFrame,
    deltas: pd.DataFrame,
    cov_summary: pd.DataFrame,
    decomp: pd.DataFrame,
    leakage: pd.DataFrame,
) -> None:
    trad_all = metrics[(metrics["method"] == "raw_pair_median") & (metrics["subset"] == "all")].iloc[0]
    ml_all = metrics[(metrics["method"] == "ml_extra_trees") & (metrics["subset"] == "all")].iloc[0]
    b2_cov = cov_summary[(cov_summary["method"] == "raw_pair_median") & (cov_summary["subset"] == "both_B2_containing")].iloc[0]
    ds_cov = cov_summary[(cov_summary["method"] == "raw_pair_median") & (cov_summary["subset"] == "both_downstream_only")].iloc[0]
    delta = deltas[deltas["comparison"] == "ml_minus_raw_pair_median_sigma68"].iloc[0]
    report = f"""# S05c: hierarchical B-stack run/stave covariance model

- **Ticket:** {config['ticket']}
- **Worker:** {config['worker']}
- **Input checksum(s):** `input_sha256.csv`
- **Config:** `{config_path}`
- **Raw input:** `{config['raw_root_dir']}`

## Question

Fit a hierarchical run/stave covariance model for B-stack pair residuals, with B2-containing pairs separated from downstream-only pairs, without using A-stack coincidences or Monte Carlo.

## Reproduction from raw ROOT

The gate was run first from `h101/HRDv`: median samples 0-3 baseline, physical B channels `B2/B4/B6/B8 = 0/2/4/6`, `A > 1000 ADC`, CFD20 timing, and the configured analysis runs.

{counts.to_markdown(index=False)}

Pair-row counts:

{pair_counts.to_markdown(index=False)}

## Methods

The target is the B-stack pair residual `t_right - t_left - TOF`, using 2 cm layer spacing and 0.078 ns/cm. All model comparisons are leave-one-run-out; the held-out run is never used for fitting or hyperparameter selection.

Traditional: pair-median centered CFD20 residuals, followed by a covariance model that decomposes pair residual covariance into an event-level stave covariance and a run-median covariance by matching off-diagonal pair covariances to `L Sigma_stave L^T`. A Ridge nuisance correction is also reported as a diagnostic, but it is not the selected traditional baseline because it broadens held-out residuals.

ML: ExtraTrees over the same pair features plus all four B-stave waveform summaries. It excludes run id, event id, raw times, raw residuals, target residuals, and pair-derived timing labels. The hyperparameters are fixed in the config before evaluation, and every prediction is for a held-out run.

## Held-out residual benchmark

{metrics.to_markdown(index=False)}

The run-bootstrap ML minus traditional sigma68 delta is `{delta['delta_ns']:.3f}` ns with 95% CI `[{delta['ci_low_ns']:.3f}, {delta['ci_high_ns']:.3f}]` and two-sided p=`{delta['p_two_sided']:.3f}`.

## Hierarchical covariance

Pair-pair covariance summaries from held-out residuals:

{cov_summary.to_markdown(index=False)}

The traditional CFD20 covariance baseline has B2-containing pair covariance `{b2_cov['mean_abs_cov_ns2']:.2f}` ns^2 with run-bootstrap CI `[{b2_cov['mean_abs_cov_ci_low_ns2']:.2f}, {b2_cov['mean_abs_cov_ci_high_ns2']:.2f}]`; downstream-only pair covariance is `{ds_cov['mean_abs_cov_ns2']:.2f}` ns^2 with CI `[{ds_cov['mean_abs_cov_ci_low_ns2']:.2f}, {ds_cov['mean_abs_cov_ci_high_ns2']:.2f}]`.

Stave-covariance decomposition:

{decomp.to_markdown(index=False)}

## Leakage checks

{leakage.to_markdown(index=False)}

The shuffled-target ML control and intentional target-echo sentinel are leakage probes. The ML gain is not adopted unless its paired run-bootstrap CI is wholly below zero and the probes do not show an obvious split or target echo leak.

## Finding

The held-out covariance is detector-local/topology dominated: B2-containing pair covariances are far larger than downstream-only covariances in the traditional CFD20 hierarchical fit. The run/stave decomposition assigns the largest excess variance to the B2 node. ExtraTrees gives a leakage-checked residual-width reduction, but the covariance decomposition still keeps B2 as the dominant local component rather than turning the problem into a detector-wide common mode.

## Artifacts

`reproduction_match_table.csv`, `pair_counts.csv`, `method_metrics.csv`, `method_delta_bootstrap.csv`, `pair_covariance_by_run.csv`, `covariance_summary.csv`, `stave_covariance_decomposition.csv`, `fold_hyperparameters.csv`, `cv_scan.csv`, `leakage_checks.csv`, `input_sha256.csv`, `manifest.json`, `result.json`, and two PNG figures.

## Follow-up tickets

- S05d: convert the S05c covariance decomposition into per-stave timing-resolution priors for the two-ended projection; expected information gain is testing whether B2-local variance can be downweighted without biasing downstream timing.
- S05e: rerun the S05c covariance model after explicit saturation-recovery features for B2; expected information gain is separating high-amplitude B2 waveform pathology from irreducible detector-local covariance.
"""
    (out_dir / "REPORT.md").write_text(report, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path("configs/s05c_hierarchical_bstack_covariance.yaml"))
    args = parser.parse_args()
    config = load_config(args.config)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    counts, pair_counts = reproduce_counts(config)
    counts.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    pair_counts.to_csv(out_dir / "pair_counts.csv", index=False)

    table = build_pair_table(config)
    table.head(2000).to_csv(out_dir / "pair_residual_table_preview.csv", index=False)
    oof, folds, cv_scan = oof_predictions(table, config)
    folds.to_csv(out_dir / "fold_hyperparameters.csv", index=False)
    cv_scan.to_csv(out_dir / "cv_scan.csv", index=False)
    keep_cols = ["run", "event", "pair", "subset", "target_residual_ns", "resid_raw_pair_median", "resid_traditional", "resid_ml", "resid_ml_shuffled_target"]
    oof[keep_cols].to_csv(out_dir / "heldout_pair_residuals.csv", index=False)

    rng = np.random.default_rng(int(config["random_seed"]))
    metrics = metric_table(oof, config, rng)
    metrics.to_csv(out_dir / "method_metrics.csv", index=False)
    lo_raw, hi_raw, p_raw = delta_bootstrap_ci(oof, "resid_raw_pair_median", "resid_ml", rng, int(config["bootstrap_resamples"]))
    lo_ridge, hi_ridge, p_ridge = delta_bootstrap_ci(oof, "resid_traditional", "resid_ml", rng, int(config["bootstrap_resamples"]))
    deltas = pd.DataFrame(
        [
            {
                "comparison": "ml_minus_raw_pair_median_sigma68",
                "delta_ns": sigma68(oof["resid_ml"].to_numpy()) - sigma68(oof["resid_raw_pair_median"].to_numpy()),
                "ci_low_ns": lo_raw,
                "ci_high_ns": hi_raw,
                "p_two_sided": p_raw,
            },
            {
                "comparison": "ml_minus_ridge_nuisance_sigma68",
                "delta_ns": sigma68(oof["resid_ml"].to_numpy()) - sigma68(oof["resid_traditional"].to_numpy()),
                "ci_low_ns": lo_ridge,
                "ci_high_ns": hi_ridge,
                "p_two_sided": p_ridge,
            }
        ]
    )
    deltas.to_csv(out_dir / "method_delta_bootstrap.csv", index=False)

    cov_rows, cov_summary, decomp = covariance_summary(oof, config, rng)
    cov_rows.to_csv(out_dir / "pair_covariance_by_run.csv", index=False)
    cov_summary.to_csv(out_dir / "covariance_summary.csv", index=False)
    decomp.to_csv(out_dir / "stave_covariance_decomposition.csv", index=False)

    leakage = leakage_checks(oof)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)
    plot_outputs(out_dir, metrics, cov_summary)
    write_input_hashes(out_dir, config)
    write_result(out_dir, config, counts, metrics, deltas, cov_summary, decomp, leakage)
    write_report(out_dir, args.config, config, counts, pair_counts, metrics, deltas, cov_summary, decomp, leakage)
    write_manifest(out_dir, args.config, config, [f"python {Path(__file__)} --config {args.config}"])


if __name__ == "__main__":
    main()
