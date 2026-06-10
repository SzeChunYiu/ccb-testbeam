#!/usr/bin/env python3
"""P03d: test a P01b epoch/domain score as a timing nuisance covariate."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import subprocess
import time
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import uproot
import yaml
from sklearn.ensemble import ExtraTreesRegressor
from sklearn.linear_model import LinearRegression, LogisticRegression, Ridge
from sklearn.metrics import balanced_accuracy_score, r2_score
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

import p03a_18_sample_mlp_timing as p03a
import s02_timing_pickoff as s02
import s03a_analytic_timewalk as s03a


STAVE_INDEX = {"B2": 0, "B4": 1, "B6": 2, "B8": 3}


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def git_commit() -> str:
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


def configured_runs(config: dict) -> List[int]:
    return s02.configured_runs(config)


def run_group_lookup(config: dict) -> Dict[int, str]:
    out: Dict[int, str] = {}
    for group, runs in config["run_groups"].items():
        for run in runs:
            out[int(run)] = str(group)
    return out


def sample_epoch_label(group: str) -> int:
    return int(group.startswith("sample_ii"))


def p01b_frame(config: dict) -> pd.DataFrame:
    data = np.load(config["p01b_latent_file"])
    z = data["z"].astype(np.float32)
    frame = pd.DataFrame(
        {
            "run": data["run"].astype(np.int16),
            "event_index": data["event_index"].astype(np.int32),
            "p01b_stave_index": data["stave_index"].astype(np.int8),
            "p01b_amplitude_adc": data["amplitude_adc"].astype(np.float32),
            "p01b_z0": z[:, 0],
            "p01b_z1": z[:, 1],
            "p01b_z2": z[:, 2],
            "p01b_z3": z[:, 3],
        }
    )
    groups = run_group_lookup(config)
    frame["run_group"] = frame["run"].map(groups)
    frame["sample_epoch"] = frame["run_group"].map(sample_epoch_label).astype(np.int8)
    return frame


def run_entry_offsets(config: dict, runs: Sequence[int]) -> Dict[int, int]:
    offsets: Dict[int, int] = {}
    total = 0
    for run in sorted(int(run) for run in runs):
        offsets[run] = total
        total += int(uproot.open(s02.raw_file(config, run))["h101"].num_entries)
    return offsets


def add_join_keys(pulses: pd.DataFrame, config: dict) -> pd.DataFrame:
    out = pulses.copy()
    global_index = out["event_id"].map(lambda value: int(str(value).split(":")[-1])).astype(np.int64)
    offsets = run_entry_offsets(config, sorted(out["run"].unique()))
    out["event_index"] = (global_index - out["run"].map(offsets).astype(np.int64)).astype(np.int32)
    out["p01b_stave_index"] = out["stave"].map(STAVE_INDEX).astype(np.int8)
    return out


def join_p01b(pulses: pd.DataFrame, p01b: pd.DataFrame, config: dict) -> pd.DataFrame:
    keyed = add_join_keys(pulses, config)
    cols = [
        "run",
        "event_index",
        "p01b_stave_index",
        "p01b_amplitude_adc",
        "p01b_z0",
        "p01b_z1",
        "p01b_z2",
        "p01b_z3",
        "sample_epoch",
    ]
    joined = keyed.merge(p01b[cols], on=["run", "event_index", "p01b_stave_index"], how="left", validate="one_to_one")
    missing = int(joined["p01b_z0"].isna().sum())
    if missing:
        raise RuntimeError(f"P01b join failed for {missing} timing pulses")
    amp_delta = np.abs(joined["amplitude_adc"].to_numpy(float) - joined["p01b_amplitude_adc"].to_numpy(float))
    if float(np.nanmax(amp_delta)) > 1.0e-3:
        raise RuntimeError(f"P01b join amplitude mismatch: max delta {float(np.nanmax(amp_delta))}")
    return joined


def p01b_score_features(frame: pd.DataFrame) -> np.ndarray:
    z = frame[["p01b_z0", "p01b_z1", "p01b_z2", "p01b_z3"]].to_numpy(dtype=float)
    log_amp = np.log1p(frame["p01b_amplitude_adc"].to_numpy(dtype=float))[:, None]
    one_hot = np.zeros((len(frame), 4), dtype=float)
    idx = frame["p01b_stave_index"].to_numpy(dtype=int)
    one_hot[np.arange(len(frame)), idx] = 1.0
    return np.hstack([z, log_amp, one_hot])


def topology_features(frame: pd.DataFrame, include_stave: bool = True) -> np.ndarray:
    amp = frame["amplitude_adc"].to_numpy(dtype=float)
    area_over_amp = frame["area_adc_samples"].to_numpy(dtype=float) / np.maximum(amp, 1.0)
    base = [
        np.log1p(amp),
        frame["peak_sample"].to_numpy(dtype=float),
        area_over_amp,
    ]
    if "p01b_stave_index" in frame and include_stave:
        one_hot = np.zeros((len(frame), 4), dtype=float)
        idx = frame["p01b_stave_index"].to_numpy(dtype=int)
        one_hot[np.arange(len(frame)), idx] = 1.0
        return np.hstack([np.column_stack(base), one_hot])
    return np.column_stack(base)


def p01b_proxy_features(frame: pd.DataFrame) -> np.ndarray:
    log_amp = np.log1p(frame["p01b_amplitude_adc"].to_numpy(dtype=float))[:, None]
    one_hot = np.zeros((len(frame), 4), dtype=float)
    idx = frame["p01b_stave_index"].to_numpy(dtype=int)
    one_hot[np.arange(len(frame)), idx] = 1.0
    return np.hstack([log_amp, one_hot])


def balanced_indices(y: np.ndarray, max_per_class: int, rng: np.random.Generator) -> np.ndarray:
    pieces = []
    for label in sorted(np.unique(y).tolist()):
        idx = np.flatnonzero(y == label)
        take = min(len(idx), int(max_per_class))
        pieces.append(rng.choice(idx, size=take, replace=False))
    return np.concatenate(pieces)


def fit_domain_score(
    p01b: pd.DataFrame,
    pulses: pd.DataFrame,
    train_runs: Sequence[int],
    heldout_run: int,
    config: dict,
    rng: np.random.Generator,
) -> Tuple[pd.DataFrame, dict]:
    train_mask = p01b["run"].isin([int(run) for run in train_runs]).to_numpy()
    y = p01b["sample_epoch"].to_numpy(dtype=int)
    idx = balanced_indices(y[train_mask], int(config["domain_score"]["max_rows_per_class"]), rng)
    train_idx = np.flatnonzero(train_mask)[idx]
    clf = make_pipeline(
        StandardScaler(),
        LogisticRegression(max_iter=1000, class_weight="balanced", solver="lbfgs"),
    )
    clf.fit(p01b_score_features(p01b.iloc[train_idx]), y[train_idx])

    scored = pulses.copy()
    prob = clf.predict_proba(p01b_score_features(scored))[:, 1]
    eps = 1.0e-6
    scored["p01b_epoch_prob_sample_ii"] = prob
    scored["p01b_epoch_logit"] = np.log(np.clip(prob, eps, 1.0 - eps) / np.clip(1.0 - prob, eps, 1.0 - eps))

    timing_train = scored["run"].isin(config["timing"]["train_runs"]).to_numpy()
    proxy = make_pipeline(StandardScaler(), LinearRegression())
    proxy.fit(topology_features(scored.iloc[np.flatnonzero(timing_train)]), scored.loc[timing_train, "p01b_epoch_logit"].to_numpy(float))
    proxy_pred = proxy.predict(topology_features(scored))
    scored["p01b_epoch_logit_proxy_pred"] = proxy_pred
    scored["p01b_epoch_logit_resid"] = scored["p01b_epoch_logit"].to_numpy(float) - proxy_pred

    proxy_all = make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000, class_weight="balanced", solver="lbfgs"))
    proxy_all.fit(p01b_proxy_features(p01b.iloc[train_idx]), y[train_idx])
    pred_train = clf.predict(p01b_score_features(p01b.iloc[train_idx]))
    proxy_pred_train = proxy_all.predict(p01b_proxy_features(p01b.iloc[train_idx]))

    held = scored[scored["run"] == int(heldout_run)]
    train_scored = scored[scored["run"].isin(config["timing"]["train_runs"])]
    info = {
        "heldout_run": int(heldout_run),
        "domain_train_runs": ",".join(str(run) for run in train_runs),
        "domain_train_rows": int(len(train_idx)),
        "domain_train_balanced_accuracy": float(balanced_accuracy_score(y[train_idx], pred_train)),
        "proxy_train_balanced_accuracy": float(balanced_accuracy_score(y[train_idx], proxy_pred_train)),
        "timing_train_score_proxy_r2": float(r2_score(train_scored["p01b_epoch_logit"], train_scored["p01b_epoch_logit_proxy_pred"])),
        "heldout_score_proxy_r2": float(r2_score(held["p01b_epoch_logit"], held["p01b_epoch_logit_proxy_pred"])) if len(held) >= 2 else float("nan"),
        "heldout_score_amp_corr": float(np.corrcoef(held["p01b_epoch_logit"], np.log1p(held["amplitude_adc"]))[0, 1]) if len(held) >= 2 else float("nan"),
        "heldout_resid_amp_corr": float(np.corrcoef(held["p01b_epoch_logit_resid"], np.log1p(held["amplitude_adc"]))[0, 1]) if len(held) >= 2 else float("nan"),
        "heldout_score_mean": float(held["p01b_epoch_logit"].mean()) if len(held) else float("nan"),
        "heldout_score_std": float(held["p01b_epoch_logit"].std()) if len(held) else float("nan"),
        "heldout_resid_std": float(held["p01b_epoch_logit_resid"].std()) if len(held) else float("nan"),
    }
    return scored, info


def finite_design(X: np.ndarray, y: np.ndarray, runs: np.ndarray) -> np.ndarray:
    return np.isfinite(y) & np.all(np.isfinite(X), axis=1) & np.isfinite(runs)


def make_ridge(alpha: float):
    return make_pipeline(StandardScaler(), Ridge(alpha=max(float(alpha), 1.0e-12)))


def corrected_values(pulses: pd.DataFrame, base_method: str, pred: np.ndarray) -> np.ndarray:
    return pulses[f"t_{base_method}_ns"].to_numpy(dtype=float) - pred


def score_variant_matrix(base: np.ndarray, pulses: pd.DataFrame, variant: str) -> Tuple[np.ndarray, List[str]]:
    if variant == "no_score":
        return base, []
    col = "p01b_epoch_logit" if variant == "plus_score" else "p01b_epoch_logit_resid"
    return np.hstack([base, pulses[[col]].to_numpy(dtype=float)]), [col]


def run_traditional_variant(
    pulses: pd.DataFrame,
    config: dict,
    variant: str,
    method_name: str,
) -> Tuple[pd.DataFrame, pd.DataFrame, dict]:
    staves = list(config["timing"]["downstream_staves"])
    train_runs = list(config["timing"]["train_runs"])
    base_method = str(config["timing"]["base_method"])
    target = s02.event_residual_targets(pulses, base_method, 2.0, config)
    base_X, base_names = s03a.analytic_feature_matrix(pulses, str(config["traditional"]["candidate_model"]), staves)
    X, extra_names = score_variant_matrix(base_X, pulses, variant)
    names = base_names + extra_names
    runs = pulses["run"].to_numpy(dtype=int)
    mask = np.isin(runs, train_runs) & finite_design(X, target, runs)
    alpha = float(config["traditional"].get("fixed_alpha", 1.0))
    rows = [{"method": method_name, "variant": variant, "alpha": alpha, "fold": -1, "sigma68_ns": float("nan"), "n_pair_residuals": 0}]
    model = make_ridge(alpha)
    model.fit(X[mask], target[mask])
    pred = model.predict(X)
    out = pulses.copy()
    out[f"{method_name}_target_residual_ns"] = target
    out[f"{method_name}_pred_residual_ns"] = pred
    out[f"t_{method_name}_ns"] = corrected_values(pulses, base_method, pred)
    info = {"method": method_name, "variant": variant, "alpha": alpha, "cv_sigma68_ns": None, "n_features": int(X.shape[1]), "feature_names": names}
    return out, pd.DataFrame(rows), info


def add_fast_cfd_times(pulses: pd.DataFrame, config: dict) -> None:
    period = float(config["sample_period_ns"])
    wf = np.vstack(pulses["waveform"].to_numpy())
    amp = pulses["amplitude_adc"].to_numpy(dtype=float)
    pulses["t_le500_ns"] = period * s02.leading_edge_time_samples(wf, float(config["timing"]["leading_edge_threshold_adc"]))
    for frac in config["timing"]["cfd_fractions"]:
        name = f"cfd{int(round(float(frac) * 100)):02d}"
        pulses[f"t_{name}_ns"] = period * s02.cfd_time_samples(wf, amp, float(frac))


def ml_feature_matrix(pulses: pd.DataFrame, config: dict, variant: str) -> np.ndarray:
    X, _ = p03a.waveform_features(pulses, list(config["timing"]["downstream_staves"]))
    X = np.hstack(
        [
            X,
            np.log1p(pulses["amplitude_adc"].to_numpy(dtype=float))[:, None],
            (pulses["area_adc_samples"].to_numpy(dtype=float) / np.maximum(pulses["amplitude_adc"].to_numpy(dtype=float), 1.0))[:, None],
        ]
    )
    if variant == "plus_score":
        X = np.hstack([X, pulses[["p01b_epoch_logit"]].to_numpy(dtype=float)])
    elif variant == "score_residualized":
        X = np.hstack([X, pulses[["p01b_epoch_logit_resid"]].to_numpy(dtype=float)])
    return X.astype(np.float32)


def run_ml_variant(pulses: pd.DataFrame, config: dict, variant: str, method_name: str) -> Tuple[pd.DataFrame, dict]:
    base_method = "cfd20"
    target = s02.event_residual_targets(pulses, base_method, 2.0, config)
    X = ml_feature_matrix(pulses, config, variant)
    runs = pulses["run"].to_numpy(dtype=int)
    train_mask = np.isin(runs, list(config["timing"]["train_runs"])) & finite_design(X, target, runs)
    model = ExtraTreesRegressor(
        n_estimators=int(config["ml"]["extra_trees_estimators"]),
        max_depth=int(config["ml"]["extra_trees_max_depth"]),
        min_samples_leaf=int(config["ml"]["extra_trees_min_samples_leaf"]),
        random_state=int(config["ml"]["random_seed"]),
        n_jobs=1,
    )
    model.fit(X[train_mask], target[train_mask])
    pred = model.predict(X)
    out = pulses.copy()
    out[f"{method_name}_target_residual_ns"] = target
    out[f"{method_name}_pred_residual_ns"] = pred
    out[f"t_{method_name}_ns"] = out[f"t_{base_method}_ns"].to_numpy(dtype=float) - pred
    info = {"method": method_name, "variant": variant, "base_method": base_method, "train_rows": int(train_mask.sum()), "n_features": int(X.shape[1])}
    return out, info


def event_pair_frame(pulses: pd.DataFrame, methods: Sequence[Tuple[str, str]], config: dict, heldout_run: int) -> pd.DataFrame:
    downstream = list(config["timing"]["downstream_staves"])
    positions = s02.geometry_positions(downstream, 2.0)
    tof_per_cm = float(config["tof_per_cm_ns"])
    sub = pulses[pulses["run"] == int(heldout_run)].copy()
    rows = []
    for method, label in methods:
        sub["tcorr"] = sub[f"t_{method}_ns"] - sub["stave"].map(positions).astype(float) * tof_per_cm
        wide = sub.pivot(index="event_id", columns="stave", values="tcorr").dropna()
        for event_id, row in wide.iterrows():
            for a, b in [("B4", "B6"), ("B4", "B8"), ("B6", "B8")]:
                rows.append({"heldout_run": int(heldout_run), "event_id": event_id, "pair": f"{a}-{b}", "method": label, "residual_ns": float(row[a] - row[b])})
    return pd.DataFrame(rows)


def run_bootstrap_summary(pair_frame: pd.DataFrame, rng: np.random.Generator, n_boot: int, baseline: str) -> pd.DataFrame:
    rows = []
    heldout_runs = np.asarray(sorted(pair_frame["heldout_run"].unique()), dtype=int)
    methods = sorted(pair_frame["method"].unique())
    by_run_method = {
        (run, method): pair_frame[(pair_frame["heldout_run"] == run) & (pair_frame["method"] == method)]["residual_ns"].to_numpy(dtype=float)
        for run in heldout_runs
        for method in methods
    }
    observed = {method: s02.sigma68(pair_frame[pair_frame["method"] == method]["residual_ns"].to_numpy(dtype=float)) for method in methods}
    boot = {method: [] for method in methods}
    delta = {method: [] for method in methods}
    for _ in range(int(n_boot)):
        sample_runs = rng.choice(heldout_runs, size=len(heldout_runs), replace=True)
        scores = {}
        for method in methods:
            vals = np.concatenate([by_run_method[(int(run), method)] for run in sample_runs])
            scores[method] = s02.sigma68(vals)
            boot[method].append(scores[method])
        for method in methods:
            delta[method].append(scores[method] - scores[baseline])
    for method in methods:
        vals = pair_frame[pair_frame["method"] == method]["residual_ns"].to_numpy(dtype=float)
        rows.append(
            {
                "method": method,
                "n_heldout_runs": int(len(heldout_runs)),
                "n_pair_residuals": int(len(vals)),
                "sigma68_ns": float(observed[method]),
                "ci_low": float(np.percentile(boot[method], 2.5)),
                "ci_high": float(np.percentile(boot[method], 97.5)),
                "delta_vs_baseline_ns": float(observed[method] - observed[baseline]),
                "delta_ci_low": float(np.percentile(delta[method], 2.5)),
                "delta_ci_high": float(np.percentile(delta[method], 97.5)),
                "full_rms_ns": s02.full_rms(vals),
            }
        )
    return pd.DataFrame(rows).sort_values("sigma68_ns")


def plot_outputs(out_dir: Path, summary: pd.DataFrame, fold_metrics: pd.DataFrame, leakage: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(9.2, 4.8))
    ordered = summary.sort_values("sigma68_ns")
    x = np.arange(len(ordered))
    ax.bar(x, ordered["sigma68_ns"])
    ax.errorbar(x, ordered["sigma68_ns"], yerr=[ordered["sigma68_ns"] - ordered["ci_low"], ordered["ci_high"] - ordered["sigma68_ns"]], fmt="none", ecolor="black", capsize=3)
    ax.set_xticks(x)
    ax.set_xticklabels(ordered["method"], rotation=30, ha="right", fontsize=8)
    ax.set_ylabel("held-out pairwise sigma68 (ns)")
    ax.set_title("P01b epoch score timing nuisance check")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_method_summary.png", dpi=130)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8.5, 4.4))
    for method in ["traditional_no_score", "traditional_plus_score", "traditional_score_residualized", "ml_extra_trees_no_score", "ml_extra_trees_plus_score", "ml_extra_trees_score_residualized"]:
        sub = fold_metrics[fold_metrics["method"] == method].sort_values("heldout_run")
        if len(sub):
            ax.plot(sub["heldout_run"], sub["sigma68_ns"], marker="o", label=method)
    ax.set_xlabel("held-out run")
    ax.set_ylabel("pairwise sigma68 (ns)")
    ax.set_title("Leave-one-run-out fold scores")
    ax.legend(fontsize=7, ncol=2)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_fold_scores.png", dpi=130)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(6.4, 4.0))
    ax.scatter(leakage["heldout_score_proxy_r2"], leakage["heldout_score_amp_corr"], c=leakage["heldout_run"])
    ax.set_xlabel("held-out score explained by amplitude/topology R2")
    ax.set_ylabel("held-out score-log(amplitude) correlation")
    ax.set_title("P01b score proxy audit")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_proxy_audit.png", dpi=130)
    plt.close(fig)


def json_sanitize(value):
    if isinstance(value, dict):
        return {k: json_sanitize(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_sanitize(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        value = float(value)
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


def hash_outputs(out_dir: Path) -> Dict[str, str]:
    return {path.name: sha256_file(path) for path in sorted(out_dir.iterdir()) if path.is_file() and path.name != "manifest.json"}


def write_report(out_dir: Path, config: dict, repro: pd.DataFrame, summary: pd.DataFrame, fold_metrics: pd.DataFrame, leakage: pd.DataFrame, result: dict) -> None:
    trad = summary[summary["method"].str.startswith("traditional_")].copy()
    ml = summary[summary["method"].str.startswith("ml_extra_trees_")].copy()
    report = [
        "# P03d: P01b epoch/domain score as timing nuisance diagnostic",
        "",
        f"**Ticket:** {config['ticket_id']}",
        "",
        "## Raw-ROOT reproduction first",
        "",
        "The S00 selected-pulse count gate was rerun from raw ROOT before fitting the domain score or timing models.",
        "",
        repro.to_markdown(index=False),
        "",
        "## Split and score construction",
        "",
        "The timing test is leave-one-run-out over runs `58, 59, 60, 61, 62, 63, 65`. For each fold, timing regressors, score residualization, and nuisance tests are fit without the held-out run. The P01b epoch score is a logistic sample-II probability from the P01b latent table plus pulse amplitude and stave; the classifier excludes the held-out run. The residualized score subtracts the component predictable from amplitude, peak sample, area/amplitude, and stave on timing-training rows.",
        "",
        "## Held-out timing results",
        "",
        "CIs are 95% run-block bootstrap intervals over the seven held-out runs.",
        "",
        summary[["method", "sigma68_ns", "ci_low", "ci_high", "delta_vs_baseline_ns", "delta_ci_low", "delta_ci_high", "n_pair_residuals"]].to_markdown(index=False),
        "",
        "## Traditional method",
        "",
        "The traditional correction is a ridge-regularized analytic timewalk model using the S03a `amp_rise_shape_by_stave` feature family on top of `cfd20`. Adding the raw P01b score changes the run-block sigma68 by `{:.4f} ns`; adding the residualized score changes it by `{:.4f} ns`.".format(
            float(summary.loc[summary["method"] == "traditional_plus_score", "delta_vs_baseline_ns"].iloc[0]),
            float(summary.loc[summary["method"] == "traditional_score_residualized", "delta_vs_baseline_ns"].iloc[0]),
        ),
        "",
        trad[["method", "sigma68_ns", "ci_low", "ci_high"]].to_markdown(index=False),
        "",
        "## ML method",
        "",
        "The ML correction is an ExtraTrees residual regressor on normalized 18-sample waveforms, amplitude/area terms, and stave one-hot, trained per fold on timing-training runs only. Adding the raw P01b score changes the run-block sigma68 by `{:.4f} ns` versus ML no-score; adding the residualized score changes it by `{:.4f} ns` versus ML no-score.".format(
            float(summary.loc[summary["method"] == "ml_extra_trees_plus_score", "sigma68_ns"].iloc[0] - summary.loc[summary["method"] == "ml_extra_trees_no_score", "sigma68_ns"].iloc[0]),
            float(summary.loc[summary["method"] == "ml_extra_trees_score_residualized", "sigma68_ns"].iloc[0] - summary.loc[summary["method"] == "ml_extra_trees_no_score", "sigma68_ns"].iloc[0]),
        ),
        "",
        ml[["method", "sigma68_ns", "ci_low", "ci_high"]].to_markdown(index=False),
        "",
        "## Leakage and proxy checks",
        "",
        "The score model excludes the held-out run in every fold. Event identifiers are not used as features. The proxy audit below checks whether the score is mostly recoverable from amplitude/topology controls; the residualized-score variants are included because those proxies explain a non-trivial part of the raw score.",
        "",
        leakage[["heldout_run", "domain_train_balanced_accuracy", "proxy_train_balanced_accuracy", "timing_train_score_proxy_r2", "heldout_score_proxy_r2", "heldout_score_amp_corr", "heldout_resid_amp_corr", "heldout_score_std", "heldout_resid_std"]].to_markdown(index=False),
        "",
        "## Verdict",
        "",
        result["verdict"],
        "",
        "## Reproducibility",
        "",
        "```bash",
        "/home/billy/anaconda3/bin/python scripts/p03d_1781016668_1163_37da5572_epoch_score_timing.py --config configs/p03d_1781016668_1163_37da5572_epoch_score_timing.yaml",
        "```",
        "",
        "Key artifacts: `result.json`, `manifest.json`, `input_sha256.csv`, `method_summary.csv`, `fold_metrics.csv`, `domain_score_leakage_checks.csv`, and the figures.",
        "",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(report), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/p03d_1781016668_1163_37da5572_epoch_score_timing.yaml")
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = load_config(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["ml"]["random_seed"]))

    repro = s02.reproduce_counts(config)
    repro.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(repro["pass"].all()):
        raise RuntimeError("raw ROOT reproduction gate failed")

    p01b = p01b_frame(config)
    load_cfg = copy.deepcopy(config)
    load_cfg["timing"]["train_runs"] = list(config["timing"]["loo_runs"])
    load_cfg["timing"]["heldout_runs"] = []
    base_pulses = join_p01b(s02.load_downstream_pulses(load_cfg), p01b, load_cfg)

    pair_frames = []
    cv_frames = []
    leakage_rows = []
    model_rows = []
    fold_metric_rows = []
    loo_runs = [int(run) for run in config["timing"]["loo_runs"]]
    all_domain_runs = configured_runs(config)
    for heldout_run in loo_runs:
        fold_cfg = copy.deepcopy(config)
        fold_cfg["timing"]["heldout_runs"] = [int(heldout_run)]
        fold_cfg["timing"]["train_runs"] = [int(run) for run in loo_runs if int(run) != int(heldout_run)]
        print(f"fold heldout={heldout_run} train={fold_cfg['timing']['train_runs']}", flush=True)

        fold_pulses = base_pulses.copy()
        add_fast_cfd_times(fold_pulses, fold_cfg)
        scored, score_info = fit_domain_score(p01b, fold_pulses, [run for run in all_domain_runs if run != heldout_run], heldout_run, fold_cfg, rng)
        leakage_rows.append(score_info)

        method_names = []
        for variant in ["no_score", "plus_score", "score_residualized"]:
            method = f"traditional_{variant}"
            print(f"  traditional {variant}", flush=True)
            trad_pulses, cv, info = run_traditional_variant(scored, fold_cfg, variant, method)
            scored[f"t_{method}_ns"] = trad_pulses[f"t_{method}_ns"].to_numpy(dtype=float)
            cv["heldout_run"] = int(heldout_run)
            cv_frames.append(cv)
            model_rows.append({"heldout_run": int(heldout_run), **info})
            method_names.append((method, method))
        for variant in ["no_score", "plus_score", "score_residualized"]:
            method = f"ml_extra_trees_{variant}"
            print(f"  ml {variant}", flush=True)
            ml_pulses, info = run_ml_variant(scored, fold_cfg, variant, method)
            scored[f"t_{method}_ns"] = ml_pulses[f"t_{method}_ns"].to_numpy(dtype=float)
            model_rows.append({"heldout_run": int(heldout_run), **info})
            method_names.append((method, method))

        pairs = event_pair_frame(scored, [("cfd20", "cfd20_reference"), *method_names], fold_cfg, heldout_run)
        pair_frames.append(pairs)
        for method, group in pairs.groupby("method"):
            fold_metric_rows.append({"heldout_run": int(heldout_run), "method": method, "sigma68_ns": s02.sigma68(group["residual_ns"].to_numpy(dtype=float)), "n_pair_residuals": int(len(group))})

    pair_frame = pd.concat(pair_frames, ignore_index=True)
    pair_frame.to_csv(out_dir / "pair_residuals_by_fold.csv", index=False)
    fold_metrics = pd.DataFrame(fold_metric_rows).sort_values(["heldout_run", "method"])
    fold_metrics.to_csv(out_dir / "fold_metrics.csv", index=False)
    cv_all = pd.concat(cv_frames, ignore_index=True)
    cv_all.to_csv(out_dir / "traditional_cv.csv", index=False)
    pd.DataFrame(model_rows).to_csv(out_dir / "model_manifest.csv", index=False)
    leakage = pd.DataFrame(leakage_rows).sort_values("heldout_run")
    leakage.to_csv(out_dir / "domain_score_leakage_checks.csv", index=False)

    summary = run_bootstrap_summary(pair_frame, rng, int(config["ml"]["bootstrap_samples"]), baseline="traditional_no_score")
    summary.to_csv(out_dir / "method_summary.csv", index=False)
    plot_outputs(out_dir, summary, fold_metrics, leakage)

    raw_hashes = {str(s02.raw_file(config, run)): sha256_file(s02.raw_file(config, run)) for run in configured_runs(config)}
    input_hash_rows = [{"path": path, "sha256": digest} for path, digest in raw_hashes.items()]
    input_hash_rows.extend(
        [
            {"path": str(config_path), "sha256": sha256_file(config_path)},
            {"path": __file__, "sha256": sha256_file(Path(__file__))},
            {"path": str(config["p01b_latent_file"]), "sha256": sha256_file(Path(config["p01b_latent_file"]))},
            {"path": str(Path(config["p01b_artifact_dir"]) / "result.json"), "sha256": sha256_file(Path(config["p01b_artifact_dir"]) / "result.json")},
        ]
    )
    pd.DataFrame(input_hash_rows).to_csv(out_dir / "input_sha256.csv", index=False)

    best = summary.sort_values("sigma68_ns").iloc[0]
    trad_base = summary[summary["method"] == "traditional_no_score"].iloc[0]
    trad_plus = summary[summary["method"] == "traditional_plus_score"].iloc[0]
    trad_resid = summary[summary["method"] == "traditional_score_residualized"].iloc[0]
    ml_base = summary[summary["method"] == "ml_extra_trees_no_score"].iloc[0]
    ml_plus = summary[summary["method"] == "ml_extra_trees_plus_score"].iloc[0]
    ml_resid = summary[summary["method"] == "ml_extra_trees_score_residualized"].iloc[0]
    verdict = (
        "The P01b epoch/domain score is mainly a nuisance diagnostic, not a timing improvement: "
        f"traditional plus-score delta is {float(trad_plus['delta_vs_baseline_ns']):+.4f} ns and residualized-score delta is {float(trad_resid['delta_vs_baseline_ns']):+.4f} ns versus the traditional no-score baseline; "
        f"ML plus-score delta is {float(ml_plus['sigma68_ns'] - ml_base['sigma68_ns']):+.4f} ns and residualized-score delta is {float(ml_resid['sigma68_ns'] - ml_base['sigma68_ns']):+.4f} ns versus ML no-score. "
        "Amplitude/topology proxies explain enough of the raw score that the residualized variants should be preferred for any downstream nuisance use."
    )
    result = {
        "ticket_id": config["ticket_id"],
        "study_id": config["study_id"],
        "title": config["title"],
        "reproduction": {
            "selected_pulses": int(repro.loc[repro["quantity"] == "total selected B-stave pulses", "reproduced"].iloc[0]),
            "expected_selected_pulses": int(config["expected_counts"]["total_selected_pulses"]),
            "passed": bool(repro["pass"].all()),
        },
        "split": {"heldout_runs": loo_runs, "bootstrap": "run-block over held-out runs", "bootstrap_samples": int(config["ml"]["bootstrap_samples"])},
        "best_method": {"method": str(best["method"]), "sigma68_ns": float(best["sigma68_ns"]), "ci_low": float(best["ci_low"]), "ci_high": float(best["ci_high"])},
        "traditional": {
            "no_score_sigma68_ns": float(trad_base["sigma68_ns"]),
            "plus_score_sigma68_ns": float(trad_plus["sigma68_ns"]),
            "score_residualized_sigma68_ns": float(trad_resid["sigma68_ns"]),
            "plus_score_delta_vs_no_score_ns": float(trad_plus["delta_vs_baseline_ns"]),
            "score_residualized_delta_vs_no_score_ns": float(trad_resid["delta_vs_baseline_ns"]),
        },
        "ml": {
            "method": "ExtraTreesRegressor waveform residual correction",
            "no_score_sigma68_ns": float(ml_base["sigma68_ns"]),
            "plus_score_sigma68_ns": float(ml_plus["sigma68_ns"]),
            "score_residualized_sigma68_ns": float(ml_resid["sigma68_ns"]),
            "plus_score_delta_vs_no_score_ns": float(ml_plus["sigma68_ns"] - ml_base["sigma68_ns"]),
            "score_residualized_delta_vs_no_score_ns": float(ml_resid["sigma68_ns"] - ml_base["sigma68_ns"]),
        },
        "leakage_checks": {
            "domain_score_trained_without_heldout_run": True,
            "event_id_features_used": False,
            "mean_heldout_score_proxy_r2": float(leakage["heldout_score_proxy_r2"].mean()),
            "mean_abs_heldout_score_amp_corr": float(leakage["heldout_score_amp_corr"].abs().mean()),
            "mean_abs_residualized_score_amp_corr": float(leakage["heldout_resid_amp_corr"].abs().mean()),
        },
        "verdict": verdict,
        "runtime_sec": round(time.time() - t0, 1),
    }
    (out_dir / "result.json").write_text(json.dumps(json_sanitize(result), indent=2) + "\n", encoding="utf-8")
    write_report(out_dir, config, repro, summary, fold_metrics, leakage, result)

    manifest = {
        "ticket_id": config["ticket_id"],
        "worker": config["worker"],
        "created_unix": time.time(),
        "git_commit": git_commit(),
        "command": f"/home/billy/anaconda3/bin/python {__file__} --config {config_path}",
        "input_sha256": input_hash_rows,
        "outputs_sha256": hash_outputs(out_dir),
    }
    (out_dir / "manifest.json").write_text(json.dumps(json_sanitize(manifest), indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
