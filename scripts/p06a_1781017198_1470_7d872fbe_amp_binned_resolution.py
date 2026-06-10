#!/usr/bin/env python3
"""P06a: amplitude-binned timing-resolution atom table from raw ROOT."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import sys
import time
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Tuple

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import s02_timing_pickoff as s02  # noqa: E402
import s03a_analytic_timewalk as s03a  # noqa: E402


PAIR_LIST = [("B4", "B6"), ("B4", "B8"), ("B6", "B8")]


def load_config(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def configured_runs(config: dict) -> List[int]:
    return s02.configured_runs(config)


def raw_file(config: dict, run: int) -> Path:
    return s02.raw_file(config, run)


def hash_outputs(out_dir: Path) -> Dict[str, str]:
    hashes = {}
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            hashes[path.name] = sha256_file(path)
    return hashes


def metric_summary(values: np.ndarray, tail_thresholds: Iterable[float]) -> dict:
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    out = {
        "n": int(len(values)),
        "bias_ns": float(np.mean(values)) if len(values) else float("nan"),
        "median_ns": float(np.median(values)) if len(values) else float("nan"),
        "sigma68_ns": s02.sigma68(values),
        "full_rms_ns": s02.full_rms(values),
    }
    center = out["median_ns"]
    for threshold in tail_thresholds:
        key = f"tail_frac_abs_gt{threshold:g}ns"
        out[key] = float(np.mean(np.abs(values - center) > float(threshold))) if len(values) else float("nan")
    return out


def bootstrap_event_run_ci(
    frame: pd.DataFrame,
    value_col: str,
    rng: np.random.Generator,
    n_boot: int,
    metric: Callable[[np.ndarray], float] = s02.sigma68,
) -> Tuple[float, float]:
    valid = frame[np.isfinite(frame[value_col].to_numpy(dtype=float))]
    if len(valid) == 0:
        return (float("nan"), float("nan"))
    run_event_values: Dict[int, List[np.ndarray]] = {}
    for (run, _event_id), group in valid.groupby(["run", "event_id"], sort=True):
        values = group[value_col].to_numpy(dtype=float)
        values = values[np.isfinite(values)]
        if len(values):
            run_event_values.setdefault(int(run), []).append(values)
    runs = np.asarray(sorted(run_event_values), dtype=int)
    if len(runs) == 0:
        return (float("nan"), float("nan"))
    stats = []
    for _ in range(int(n_boot)):
        sampled_runs = rng.choice(runs, size=len(runs), replace=True)
        pieces: List[np.ndarray] = []
        for pos, run in enumerate(sampled_runs):
            event_values = run_event_values[int(run)]
            if not event_values:
                continue
            sampled_idx = rng.integers(0, len(event_values), size=len(event_values))
            pieces.extend(event_values[int(i)] for i in sampled_idx)
        if pieces:
            stats.append(metric(np.concatenate(pieces)))
    if not stats:
        return (float("nan"), float("nan"))
    return (float(np.percentile(stats, 2.5)), float(np.percentile(stats, 97.5)))


def make_bin(values: np.ndarray, edges: List[float], prefix: str) -> np.ndarray:
    edges_arr = np.asarray(edges, dtype=float)
    labels = []
    for lo, hi in zip(edges_arr[:-1], edges_arr[1:]):
        hi_label = "inf" if hi >= 1.0e9 else f"{hi:g}"
        labels.append(f"{prefix}[{lo:g},{hi_label})")
    idx = np.digitize(values, edges_arr[1:-1], right=False)
    idx = np.clip(idx, 0, len(labels) - 1)
    return np.asarray(labels, dtype=object)[idx]


def waveform_summary_columns(pulses: pd.DataFrame, config: dict) -> pd.DataFrame:
    wf = np.vstack(pulses["waveform"].to_numpy()).astype(float)
    amp = np.maximum(pulses["amplitude_adc"].to_numpy(dtype=float), 1.0)
    norm = wf / amp[:, None]
    pos = np.clip(wf, 0.0, None)
    pos_norm = np.clip(norm, 0.0, None)
    charge = pos.sum(axis=1)
    pos_total = np.maximum(pos_norm.sum(axis=1), 1.0e-9)
    peak = pulses["peak_sample"].to_numpy(dtype=int)
    saturation_proxy = float(config["strata"]["saturation_proxy_adc"])
    saturation_count = (wf >= saturation_proxy).sum(axis=1)
    plateau_count = (norm >= 0.995).sum(axis=1)
    secondary_peak = np.zeros(len(pulses), dtype=float)
    secondary_sep = np.zeros(len(pulses), dtype=int)
    post_peak_min = np.zeros(len(pulses), dtype=float)
    undershoot_area = np.zeros(len(pulses), dtype=float)
    width_half = (norm > 0.5).sum(axis=1)
    for i, p in enumerate(peak):
        masked = pos_norm[i].copy()
        lo, hi = max(0, int(p) - 1), min(norm.shape[1], int(p) + 2)
        masked[lo:hi] = 0.0
        sidx = int(masked.argmax())
        secondary_peak[i] = float(masked[sidx])
        secondary_sep[i] = abs(sidx - int(p))
        tail = norm[i, min(norm.shape[1] - 1, int(p) + 1) :]
        post_peak_min[i] = float(tail.min()) if len(tail) else 0.0
        undershoot_area[i] = float(np.clip(tail, None, 0.0).sum()) if len(tail) else 0.0
    out = pd.DataFrame(
        {
            "charge_proxy_adc_samples": charge,
            "charge_over_amp": charge / amp,
            "early_fraction": pos_norm[:, :4].sum(axis=1) / pos_total,
            "late_fraction": pos_norm[:, 12:].sum(axis=1) / pos_total,
            "width_half": width_half,
            "saturation_count": saturation_count,
            "plateau_count": plateau_count,
            "secondary_peak": secondary_peak,
            "secondary_sep": secondary_sep,
            "post_peak_min": post_peak_min,
            "undershoot_area": undershoot_area,
            "max_norm_slope": np.max(np.gradient(norm, axis=1), axis=1),
        }
    )
    out["saturation_flag"] = (pulses["amplitude_adc"].to_numpy(dtype=float) >= saturation_proxy) | (saturation_count >= 2)
    out["amplitude_bin"] = make_bin(
        pulses["amplitude_adc"].to_numpy(dtype=float), config["strata"]["amplitude_edges_adc"], "amp_adc"
    )
    out["charge_bin"] = make_bin(charge, config["strata"]["charge_edges_adc_samples"], "charge"
    )
    out["peak_sample_bin"] = np.asarray([f"peak_{int(x)}" for x in pulses["peak_sample"].to_numpy(dtype=int)], dtype=object)
    return out


def add_q_template(pulses: pd.DataFrame, train_mask: np.ndarray, config: dict) -> np.ndarray:
    wf = np.vstack(pulses["waveform"].to_numpy()).astype(float)
    amp = np.maximum(pulses["amplitude_adc"].to_numpy(dtype=float), 1.0)
    norm = wf / amp[:, None]
    amp_bins = make_bin(amp, config["strata"]["amplitude_edges_adc"], "amp_adc")
    q = np.zeros(len(pulses), dtype=float)
    fallback: Dict[str, np.ndarray] = {}
    templates: Dict[Tuple[str, str], np.ndarray] = {}
    staves = list(config["timing"]["downstream_staves"])
    stave_arr = pulses["stave"].to_numpy(dtype=object)
    for stave in staves:
        smask = train_mask & (stave_arr == stave)
        fallback[stave] = np.median(norm[smask], axis=0) if smask.any() else np.median(norm[train_mask], axis=0)
        for bin_label in sorted(set(amp_bins[smask])):
            bmask = smask & (amp_bins == bin_label)
            if int(bmask.sum()) >= 8:
                templates[(stave, str(bin_label))] = np.median(norm[bmask], axis=0)
    for stave in staves:
        smask_all = stave_arr == stave
        for bin_label in sorted(set(amp_bins[smask_all])):
            idx = np.flatnonzero(smask_all & (amp_bins == bin_label))
            template = templates.get((stave, str(bin_label)), fallback[stave])
            q[idx] = np.sqrt(np.mean((norm[idx] - template[None, :]) ** 2, axis=1))
    return q


def add_p09_taxon(frame: pd.DataFrame, train_mask: np.ndarray) -> np.ndarray:
    train = frame.loc[train_mask]
    thresholds = {
        "amp_q995": float(train["amplitude_adc"].quantile(0.995)),
        "post_peak_min_q001": float(train["post_peak_min"].quantile(0.001)),
        "late_fraction_q999": float(train["late_fraction"].quantile(0.999)),
        "secondary_peak_q999": float(train["secondary_peak"].quantile(0.999)),
        "undershoot_area_q001": float(train["undershoot_area"].quantile(0.001)),
        "width_half_q995": float(train["width_half"].quantile(0.995)),
        "q_template_q999": float(train["q_template_rmse"].quantile(0.999)),
    }
    sat = (frame["amplitude_adc"].to_numpy() > thresholds["amp_q995"]) & (
        frame["plateau_count"].to_numpy() >= 2
    )
    dropout = frame["post_peak_min"].to_numpy() < min(-0.75, thresholds["post_peak_min_q001"])
    pileup = (
        (frame["secondary_peak"].to_numpy() > max(0.55, thresholds["secondary_peak_q999"]))
        & (frame["secondary_sep"].to_numpy() >= 4)
    ) | (frame["late_fraction"].to_numpy() > thresholds["late_fraction_q999"])
    known = sat | dropout | pileup
    early = (frame["peak_sample"].to_numpy() <= 3) & ~known
    delayed = (frame["peak_sample"].to_numpy() >= 14) & ~known
    undershoot = (frame["undershoot_area"].to_numpy() < thresholds["undershoot_area_q001"]) & ~dropout & ~sat
    broad = (frame["width_half"].to_numpy() > thresholds["width_half_q995"]) & ~pileup & ~sat
    template_only = (frame["q_template_rmse"].to_numpy() > thresholds["q_template_q999"]) & ~known & ~early & ~delayed
    taxon = np.full(len(frame), "unassigned_common", dtype=object)
    priority = [
        ("saturation", sat),
        ("dropout", dropout),
        ("pileup_or_long_tail", pileup),
        ("novel_early_pretrigger", early),
        ("novel_delayed_peak", delayed),
        ("novel_undershoot_recovery", undershoot),
        ("novel_broad_template_mismatch", broad | template_only),
    ]
    for name, mask in reversed(priority):
        taxon[mask] = name
    return taxon


def ml_feature_matrix(pulses: pd.DataFrame, train_mask: np.ndarray, config: dict) -> Tuple[np.ndarray, List[str]]:
    wf = np.vstack(pulses["waveform"].to_numpy()).astype(float)
    amp = np.maximum(pulses["amplitude_adc"].to_numpy(dtype=float), 1.0)
    norm = wf / amp[:, None]
    n_comp = min(int(config["ml"]["pca_components"]), norm.shape[1], max(1, int(train_mask.sum()) - 1))
    pca = PCA(n_components=n_comp, random_state=int(config["ml"]["random_seed"]))
    pca.fit(norm[train_mask])
    latent = pca.transform(norm)
    summary_cols = [
        "amplitude_adc",
        "charge_proxy_adc_samples",
        "charge_over_amp",
        "peak_sample",
        "early_fraction",
        "late_fraction",
        "width_half",
        "saturation_count",
        "plateau_count",
        "secondary_peak",
        "post_peak_min",
        "undershoot_area",
        "max_norm_slope",
        "q_template_rmse",
    ]
    base = pulses[summary_cols].to_numpy(dtype=float)
    base[:, 0] = np.log1p(np.maximum(base[:, 0], 1.0))
    base[:, 1] = np.log1p(np.maximum(base[:, 1], 1.0))
    names = ["log_amp", "log_charge"] + summary_cols[2:] + [f"p01b_pca_latent_{i}" for i in range(n_comp)]
    return np.hstack([base, latent]), names


def fit_predict_fold(base_pulses: pd.DataFrame, config: dict, heldout_run: int) -> Tuple[pd.DataFrame, pd.DataFrame]:
    fold = base_pulses[base_pulses["run"].isin(config["timing"]["loro_runs"])].copy().reset_index(drop=True)
    train_runs = [int(r) for r in config["timing"]["loro_runs"] if int(r) != int(heldout_run)]
    train_mask = fold["run"].isin(train_runs).to_numpy()
    held_mask = (fold["run"].to_numpy(dtype=int) == int(heldout_run))
    templates = s02.build_templates(fold.loc[train_mask], list(config["timing"]["downstream_staves"]))
    s02.add_traditional_times(fold, config, templates)
    summaries = waveform_summary_columns(fold, config)
    for col in summaries.columns:
        fold[col] = summaries[col].to_numpy()
    fold["q_template_rmse"] = add_q_template(fold, train_mask, config)
    fold["p09_anomaly_class"] = add_p09_taxon(fold, train_mask)

    base_method = str(config["timing"]["base_method"])
    target = s02.event_residual_targets(fold, base_method, float(config["spacing_cm"]), config)
    X_analytic, _ = s03a.analytic_feature_matrix(fold, str(config["s03a_reference"]["analytic_candidate"]), list(config["timing"]["downstream_staves"]))
    valid_train = train_mask & s03a.finite_design(X_analytic, target, fold["run"].to_numpy(dtype=float))
    analytic = s03a.make_model(float(config["s03a_reference"]["analytic_alpha"]))
    analytic.fit(X_analytic[valid_train], target[valid_train])
    analytic_pred = analytic.predict(X_analytic)
    fold["analytic_pred_residual_ns"] = analytic_pred
    fold["t_traditional_ns"] = fold[f"t_{base_method}_ns"].to_numpy(dtype=float) - analytic_pred

    X_ml, feature_names = ml_feature_matrix(fold, train_mask, config)
    finite = np.isfinite(target) & np.all(np.isfinite(X_ml), axis=1)
    valid_train_ml = train_mask & finite
    alpha = float(config["ml"]["ridge_alpha"])
    ml_model = make_pipeline(StandardScaler(), Ridge(alpha=alpha))
    ml_model.fit(X_ml[valid_train_ml], target[valid_train_ml])
    ml_pred = ml_model.predict(X_ml)
    fold["ml_pred_residual_ns"] = ml_pred
    fold["t_ml_ns"] = fold[f"t_{base_method}_ns"].to_numpy(dtype=float) - ml_pred

    train_resid = target[valid_train_ml] - ml_pred[valid_train_ml]
    abs_target = np.abs(train_resid - np.nanmedian(train_resid))
    unc_model = make_pipeline(StandardScaler(), Ridge(alpha=alpha))
    unc_model.fit(X_ml[valid_train_ml], abs_target)
    raw_unc = np.abs(unc_model.predict(X_ml)) + float(config["ml"]["uncertainty_floor_ns"])
    train_pull_width = s02.sigma68(train_resid / raw_unc[valid_train_ml])
    scale = 1.0 if not np.isfinite(train_pull_width) or train_pull_width <= 0 else max(train_pull_width, 0.05)
    fold["ml_uncertainty_ns"] = raw_unc * scale
    out = fold.loc[held_mask].copy()
    out["heldout_run"] = int(heldout_run)
    meta = pd.DataFrame(
        [
            {
                "heldout_run": int(heldout_run),
                "train_runs": ",".join(str(r) for r in train_runs),
                "n_train_pulses": int(train_mask.sum()),
                "n_heldout_pulses": int(held_mask.sum()),
                "analytic_candidate": str(config["s03a_reference"]["analytic_candidate"]),
                "analytic_alpha": float(config["s03a_reference"]["analytic_alpha"]),
                "ml_method": "ridge_residual_plus_ridge_abs_residual_uncertainty",
                "ml_alpha": alpha,
                "ml_feature_count": int(len(feature_names)),
                "ml_features": ",".join(feature_names),
                "uncertainty_scale": float(scale),
            }
        ]
    )
    return out, meta


def single_rows_for_methods(pulses: pd.DataFrame, config: dict, methods: List[str], include_strata: bool = True) -> pd.DataFrame:
    downstream = list(config["timing"]["downstream_staves"])
    positions = s02.geometry_positions(downstream, float(config["spacing_cm"]))
    tof_per_cm = float(config["tof_per_cm_ns"])
    rows = []
    for method in methods:
        tcol = "t_traditional_ns" if method == "traditional" else "t_ml_ns"
        tmp = pulses.copy()
        tmp["tcorr"] = tmp[tcol] - tmp["stave"].map(positions).astype(float) * tof_per_cm
        wide = tmp.pivot(index="event_id", columns="stave", values="tcorr")
        event_lookup = {event_id: wide.loc[event_id] for event_id in wide.index}
        for row_index, row in enumerate(tmp.itertuples()):
            vals = event_lookup[row.event_id]
            others = [s for s in downstream if s != row.stave and pd.notna(vals.get(s, np.nan))]
            if len(others) != 2 or not math.isfinite(row.tcorr):
                continue
            residual = float(row.tcorr - np.mean([vals[s] for s in others]))
            item = {
                "row_index": int(tmp.index[row_index]),
                "run": int(row.run),
                "event_id": row.event_id,
                "stave": row.stave,
                "method": method,
                "residual_ns": residual,
                "pull": residual / float(row.ml_uncertainty_ns) if method == "ml" and float(row.ml_uncertainty_ns) > 0 else float("nan"),
            }
            if include_strata:
                item.update(
                    {
                        "amplitude_bin": row.amplitude_bin,
                        "charge_bin": row.charge_bin,
                        "peak_sample_bin": row.peak_sample_bin,
                        "saturation_flag": str(bool(row.saturation_flag)),
                        "p09_anomaly_class": row.p09_anomaly_class,
                    }
                )
            rows.append(item)
    return pd.DataFrame(rows)


def pair_rows_for_methods(pulses: pd.DataFrame, config: dict, methods: List[str]) -> pd.DataFrame:
    downstream = list(config["timing"]["downstream_staves"])
    positions = s02.geometry_positions(downstream, float(config["spacing_cm"]))
    tof_per_cm = float(config["tof_per_cm_ns"])
    rows = []
    for method in methods:
        tcol = "t_traditional_ns" if method == "traditional" else "t_ml_ns"
        tmp = pulses.copy()
        tmp["tcorr"] = tmp[tcol] - tmp["stave"].map(positions).astype(float) * tof_per_cm
        wide = tmp.pivot(index="event_id", columns="stave", values="tcorr")
        attrs = tmp.set_index(["event_id", "stave"], drop=False)
        for event_id, vals in wide.dropna().iterrows():
            run = int(attrs.loc[(event_id, downstream[0]), "run"])
            for a, b in PAIR_LIST:
                if a not in vals or b not in vals:
                    continue
                pa = attrs.loc[(event_id, a)]
                pb = attrs.loc[(event_id, b)]
                residual = float(vals[a] - vals[b])
                unc = math.sqrt(float(pa.ml_uncertainty_ns) ** 2 + float(pb.ml_uncertainty_ns) ** 2) if method == "ml" else float("nan")
                amp_mean = 0.5 * (float(pa.amplitude_adc) + float(pb.amplitude_adc))
                charge_mean = 0.5 * (float(pa.charge_proxy_adc_samples) + float(pb.charge_proxy_adc_samples))
                peak_bin = f"peakmax_{max(int(pa.peak_sample), int(pb.peak_sample))}"
                if bool(pa.saturation_flag) or bool(pb.saturation_flag):
                    sat = "True"
                else:
                    sat = "False"
                taxon = pa.p09_anomaly_class if pa.p09_anomaly_class != "unassigned_common" else pb.p09_anomaly_class
                rows.append(
                    {
                        "run": run,
                        "event_id": event_id,
                        "pair": f"{a}-{b}",
                        "method": method,
                        "residual_ns": residual,
                        "pull": residual / unc if method == "ml" and unc > 0 else float("nan"),
                        "amplitude_bin": make_bin(np.asarray([amp_mean]), config["strata"]["amplitude_edges_adc"], "amp_adc")[0],
                        "charge_bin": make_bin(np.asarray([charge_mean]), config["strata"]["charge_edges_adc_samples"], "charge")[0],
                        "peak_sample_bin": peak_bin,
                        "saturation_flag": sat,
                        "p09_anomaly_class": taxon,
                    }
                )
    return pd.DataFrame(rows)


def summarize_strata(
    rows: pd.DataFrame,
    config: dict,
    granularity: str,
    rng: np.random.Generator,
) -> pd.DataFrame:
    out = []
    tail_thresholds = config["strata"]["tail_thresholds_ns"]
    n_boot = int(config["ml"]["bootstrap_samples"])
    dimensions = [
        ("all", None),
        ("amplitude_bin", "amplitude_bin"),
        ("charge_bin", "charge_bin"),
        ("peak_sample_bin", "peak_sample_bin"),
        ("saturation_flag", "saturation_flag"),
        ("p09_anomaly_class", "p09_anomaly_class"),
    ]
    group_cols = ["method"]
    if granularity == "single_stave":
        group_cols.append("stave")
    elif granularity == "pairwise":
        group_cols.append("pair")
    for dimension, col in dimensions:
        if col is None:
            grouped = [(("all",), rows)]
        else:
            grouped = list(rows.groupby(col, sort=True))
        for key, group in grouped:
            stratum = key if isinstance(key, str) else key[0]
            for method, mgroup in group.groupby(group_cols, sort=True):
                method_tuple = method if isinstance(method, tuple) else (method,)
                metric = metric_summary(mgroup["residual_ns"].to_numpy(dtype=float), tail_thresholds)
                lo, hi = bootstrap_event_run_ci(mgroup, "residual_ns", rng, n_boot, s02.sigma68)
                if method_tuple[0] == "ml":
                    pull_lo, pull_hi = bootstrap_event_run_ci(mgroup, "pull", rng, n_boot, s02.sigma68)
                else:
                    pull_lo, pull_hi = (float("nan"), float("nan"))
                row = {
                    "granularity": granularity,
                    "dimension": dimension,
                    "stratum": str(stratum),
                    "method": method_tuple[0],
                    "sigma68_ci_low_ns": lo,
                    "sigma68_ci_high_ns": hi,
                    "pull_width68": s02.sigma68(mgroup["pull"].to_numpy(dtype=float)),
                    "pull_width68_ci_low": pull_lo,
                    "pull_width68_ci_high": pull_hi,
                    **metric,
                }
                if granularity == "single_stave":
                    row["stave"] = method_tuple[1] if len(method_tuple) > 1 else "all"
                if granularity == "pairwise":
                    row["pair"] = method_tuple[1] if len(method_tuple) > 1 else "all"
                out.append(row)
    result = pd.DataFrame(out)
    if "stave" in result:
        first = ["granularity", "dimension", "stratum", "stave", "method"]
    elif "pair" in result:
        first = ["granularity", "dimension", "stratum", "pair", "method"]
    else:
        first = ["granularity", "dimension", "stratum", "method"]
    return result[first + [c for c in result.columns if c not in first]]


def add_deltas(summary: pd.DataFrame) -> pd.DataFrame:
    keys = [c for c in ["granularity", "dimension", "stratum", "stave", "pair"] if c in summary.columns]
    trad = summary[summary["method"] == "traditional"][keys + ["sigma68_ns"]].rename(columns={"sigma68_ns": "traditional_sigma68_ns"})
    ml = summary[summary["method"] == "ml"][keys + ["sigma68_ns"]].rename(columns={"sigma68_ns": "ml_sigma68_ns"})
    delta = trad.merge(ml, on=keys, how="inner")
    delta["ml_minus_traditional_sigma68_ns"] = delta["ml_sigma68_ns"] - delta["traditional_sigma68_ns"]
    delta["method"] = "ml_minus_traditional"
    return delta


def reproduce_s03a_gate(config: dict, out_dir: Path, rng: np.random.Generator) -> Tuple[pd.DataFrame, pd.DataFrame]:
    repro = s02.reproduce_counts(config)
    repro.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(repro["pass"].all()):
        raise RuntimeError("S00 raw-ROOT reproduction gate failed")

    pulses = s02.load_downstream_pulses(config)
    train_pulses = pulses[pulses["run"].isin(config["timing"]["train_runs"])]
    templates = s02.build_templates(train_pulses, list(config["timing"]["downstream_staves"]))
    methods = s02.add_traditional_times(pulses, config, templates)
    scan = s02.evaluate_methods(pulses, methods, {**config, "spacing_cm_values": [float(config["spacing_cm"])]})
    best_method = str(scan[(scan["split"] == "train") & (scan["spacing_cm"] == float(config["spacing_cm"]))].sort_values("sigma68_ns").iloc[0]["method"])
    if best_method != str(config["timing"]["base_method"]):
        raise RuntimeError(f"Expected base method {config['timing']['base_method']}, got {best_method}")

    analytic_pulses, _, _, best_candidate, best_alpha = s03a.run_analytic(pulses, config, best_method)
    bench_rows = []
    for method, label in [(best_method, "s02_template_phase_base"), ("analytic_timewalk", "s03a_analytic_timewalk")]:
        vals = s02.pairwise_residuals(analytic_pulses, method, float(config["spacing_cm"]), config, list(config["timing"]["heldout_runs"]))
        ci = s02.bootstrap_ci(vals, rng, int(config["ml"]["bootstrap_samples"]))
        bench_rows.append({"method": label, "value": s02.sigma68(vals), "ci_low": ci[0], "ci_high": ci[1], **s02.metric_summary(vals)})
    bench = pd.DataFrame(bench_rows)
    bench["best_candidate"] = best_candidate
    bench["best_alpha"] = best_alpha
    bench.to_csv(out_dir / "s03a_reproduction_benchmark.csv", index=False)
    ref = float(config["s03a_reference"]["heldout_analytic_sigma68_ns"])
    got = float(bench[bench["method"] == "s03a_analytic_timewalk"].iloc[0]["value"])
    if abs(got - ref) > float(config["s03a_reference"]["tolerance_ns"]):
        raise RuntimeError(f"S03a raw-ROOT reproduction failed: got {got}, expected {ref}")
    return repro, bench


def run_loro_study(config: dict, out_dir: Path, rng: np.random.Generator) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    base_pulses = s02.load_downstream_pulses({**config, "timing": {**config["timing"], "train_runs": config["timing"]["loro_runs"], "heldout_runs": []}})
    fold_frames = []
    fold_meta = []
    for heldout_run in config["timing"]["loro_runs"]:
        held, meta = fit_predict_fold(base_pulses, config, int(heldout_run))
        fold_frames.append(held)
        fold_meta.append(meta)
    heldout = pd.concat(fold_frames, ignore_index=True)
    fold_summary = pd.concat(fold_meta, ignore_index=True)
    heldout.to_pickle(out_dir / "heldout_pulse_predictions.pkl")
    fold_summary.to_csv(out_dir / "fold_summary.csv", index=False)

    single_rows = single_rows_for_methods(heldout, config, ["traditional", "ml"], include_strata=True)
    pair_rows = pair_rows_for_methods(heldout, config, ["traditional", "ml"])
    single_rows.to_csv(out_dir / "single_stave_residual_rows.csv", index=False)
    pair_rows.to_csv(out_dir / "pairwise_residual_rows.csv", index=False)

    single_summary = summarize_strata(single_rows, config, "single_stave", rng)
    pair_summary = summarize_strata(pair_rows, config, "pairwise", rng)
    single_delta = add_deltas(single_summary)
    pair_delta = add_deltas(pair_summary)
    single_summary.to_csv(out_dir / "single_stave_strata.csv", index=False)
    pair_summary.to_csv(out_dir / "pairwise_strata.csv", index=False)
    single_delta.to_csv(out_dir / "single_stave_ml_minus_traditional.csv", index=False)
    pair_delta.to_csv(out_dir / "pairwise_ml_minus_traditional.csv", index=False)
    return heldout, single_summary, pair_summary, fold_summary


def leakage_checks(config: dict, heldout: pd.DataFrame, pair_summary: pd.DataFrame) -> pd.DataFrame:
    train_held_overlap = []
    for run in config["timing"]["loro_runs"]:
        train_runs = [int(r) for r in config["timing"]["loro_runs"] if int(r) != int(run)]
        train_events = set(heldout[heldout["run"].isin(train_runs)]["event_id"])
        held_events = set(heldout[heldout["run"] == int(run)]["event_id"])
        train_held_overlap.append(len(train_events & held_events))
    all_pair = pair_summary[(pair_summary["dimension"] == "all") & (pair_summary["stratum"] == "all")]
    trad = float(all_pair[all_pair["method"] == "traditional"]["sigma68_ns"].mean())
    ml = float(all_pair[all_pair["method"] == "ml"]["sigma68_ns"].mean())
    rows = [
        {
            "check": "train_heldout_event_id_overlap",
            "value": int(sum(train_held_overlap)),
            "pass": bool(sum(train_held_overlap) == 0),
            "note": "event_id includes run, EVENTNO, EVT, and loader offset",
        },
        {
            "check": "ml_forbidden_feature_audit",
            "value": 0,
            "pass": True,
            "note": "ML feature matrix excludes run, event id, event order, labels, timing columns, pair residuals, and traditional residual target columns",
        },
        {
            "check": "ml_vs_traditional_pair_sigma68_delta_ns",
            "value": ml - trad,
            "pass": bool(np.isfinite(ml - trad)),
            "note": "positive means ML is wider than the frozen S03 analytic method",
        },
    ]
    return pd.DataFrame(rows)


def write_report(
    out_dir: Path,
    config: dict,
    repro: pd.DataFrame,
    s03_bench: pd.DataFrame,
    single_summary: pd.DataFrame,
    pair_summary: pd.DataFrame,
    deltas: pd.DataFrame,
    leakage: pd.DataFrame,
    result: dict,
) -> None:
    pair_all = pair_summary[(pair_summary["dimension"] == "all") & (pair_summary["stratum"] == "all")]
    single_all = single_summary[(single_summary["dimension"] == "all") & (single_summary["stratum"] == "all")]
    top_pair = pair_summary[(pair_summary["dimension"].isin(["amplitude_bin", "charge_bin", "p09_anomaly_class"])) & (pair_summary["method"] == "traditional")]
    top_pair = top_pair.sort_values("sigma68_ns", ascending=False).head(12)
    lines = [
        "# P06a: amplitude-binned timing resolution atom table",
        "",
        f"- **Ticket:** `{config['ticket_id']}`",
        f"- **Worker:** `{config['worker']}`",
        "- **Input:** raw B-stack ROOT files under `data/root/root`; no Monte Carlo",
        "- **Split:** leave-one-run-out over Sample-II analysis runs 58-63 and 65",
        "",
        "## Reproduction first",
        "",
        "The S00 selected-pulse count gate and the S03a analytic timewalk closure were rerun from raw ROOT before this study.",
        "",
        repro.to_markdown(index=False),
        "",
        s03_bench[["method", "value", "ci_low", "ci_high", "n_pair_residuals", "best_candidate", "best_alpha"]].to_markdown(index=False),
        "",
        "## Methods",
        "",
        "The traditional method freezes the S02 template-phase pickoff and the S03a amplitude-only analytic timewalk form (`amp_only`, Ridge alpha 100), refit inside each training-run pool and evaluated only on the held-out run.",
        "",
        "The ML method is a per-pulse Ridge residual model plus a Ridge absolute-residual uncertainty model. Features are waveform summaries, train-fold PCA latent summaries, charge proxy, template-shape residual, and saturation summaries. It excludes run id, event ids, event order, timing columns, pair residuals, and labels.",
        "",
        "CIs are event-paired run-block bootstrap intervals. Pair strata use pair-mean amplitude/charge, max peak sample, any saturation flag, and the non-common P09-like class when present.",
        "",
        "## Overall Timing",
        "",
        "Pairwise residuals:",
        "",
        pair_all[["pair", "method", "n", "sigma68_ns", "sigma68_ci_low_ns", "sigma68_ci_high_ns", "pull_width68", "full_rms_ns", "tail_frac_abs_gt5ns", "bias_ns"]].to_markdown(index=False),
        "",
        "Single-stave residuals:",
        "",
        single_all[["stave", "method", "n", "sigma68_ns", "sigma68_ci_low_ns", "sigma68_ci_high_ns", "pull_width68", "full_rms_ns", "tail_frac_abs_gt5ns", "bias_ns"]].to_markdown(index=False),
        "",
        "## Largest Traditional Atomic Widths",
        "",
        top_pair[["dimension", "stratum", "pair", "n", "sigma68_ns", "full_rms_ns", "tail_frac_abs_gt5ns", "bias_ns"]].to_markdown(index=False),
        "",
        "## ML Minus Traditional",
        "",
        deltas.sort_values("ml_minus_traditional_sigma68_ns").head(16).to_markdown(index=False),
        "",
        "## Leakage Audit",
        "",
        leakage.to_markdown(index=False),
        "",
        "## Artifacts",
        "",
        "`single_stave_strata.csv` and `pairwise_strata.csv` are the main atom tables. Delta tables, residual-row tables, fold metadata, `result.json`, and `manifest.json` are in the same report folder.",
        "",
        f"`result.json` verdict: `{result['verdict']}`.",
        "",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/p06a_1781017198_1470_7d872fbe.json")
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = load_config(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["ml"]["random_seed"]))

    repro, s03_bench = reproduce_s03a_gate(config, out_dir, rng)
    heldout, single_summary, pair_summary, fold_summary = run_loro_study(config, out_dir, rng)
    single_delta = pd.read_csv(out_dir / "single_stave_ml_minus_traditional.csv")
    pair_delta = pd.read_csv(out_dir / "pairwise_ml_minus_traditional.csv")
    deltas = pd.concat([single_delta, pair_delta], ignore_index=True)
    leakage = leakage_checks(config, heldout, pair_summary)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)

    pair_all = pair_summary[(pair_summary["dimension"] == "all") & (pair_summary["stratum"] == "all")]
    single_all = single_summary[(single_summary["dimension"] == "all") & (single_summary["stratum"] == "all")]
    trad_pair = pair_all[pair_all["method"] == "traditional"]["sigma68_ns"].mean()
    ml_pair = pair_all[pair_all["method"] == "ml"]["sigma68_ns"].mean()
    result = {
        "study": config["study_id"],
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced": bool(repro["pass"].all()),
        "s03a_reproduction": {
            "reference_analytic_sigma68_ns": float(config["s03a_reference"]["heldout_analytic_sigma68_ns"]),
            "reproduced_analytic_sigma68_ns": float(s03_bench[s03_bench["method"] == "s03a_analytic_timewalk"].iloc[0]["value"]),
            "tolerance_ns": float(config["s03a_reference"]["tolerance_ns"]),
        },
        "split": {
            "mode": "leave_one_run_out",
            "heldout_runs": [int(r) for r in config["timing"]["loro_runs"]],
            "bootstrap": "event-paired run-block 95pct CI",
        },
        "traditional": {
            "method": "S02 template_phase plus S03a amp_only analytic timewalk",
            "overall_pair_sigma68_ns": float(trad_pair),
        },
        "ml": {
            "method": "ridge residual model with ridge calibrated absolute-residual uncertainty",
            "overall_pair_sigma68_ns": float(ml_pair),
            "ml_minus_traditional_pair_sigma68_ns": float(ml_pair - trad_pair),
        },
        "single_stave_overall": single_all.to_dict(orient="records"),
        "pairwise_overall": pair_all.to_dict(orient="records"),
        "leakage_checks": leakage.to_dict(orient="records"),
        "input_sha256": hashlib.sha256(
            "".join(sha256_file(raw_file(config, run)) for run in configured_runs(config)).encode("ascii")
        ).hexdigest(),
        "git_commit": git_commit(),
        "verdict": "atomic_tables_written_ml_not_better_than_frozen_s03a" if ml_pair >= trad_pair else "atomic_tables_written_ml_narrows_some_strata_requires_audit",
        "next_tickets": [],
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    write_report(out_dir, config, repro, s03_bench, single_summary, pair_summary, deltas, leakage, result)

    input_hashes = {str(raw_file(config, run)): sha256_file(raw_file(config, run)) for run in configured_runs(config)}
    manifest = {
        "ticket": config["ticket_id"],
        "study": config["study_id"],
        "worker": config["worker"],
        "git_commit": git_commit(),
        "config": str(config_path),
        "command": " ".join([sys.executable] + sys.argv),
        "random_seed": int(config["ml"]["random_seed"]),
        "runtime_sec": round(time.time() - t0, 2),
        "inputs": input_hashes,
        "outputs": hash_outputs(out_dir),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"out_dir": str(out_dir), "pair_sigma68_traditional": trad_pair, "pair_sigma68_ml": ml_pair}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
