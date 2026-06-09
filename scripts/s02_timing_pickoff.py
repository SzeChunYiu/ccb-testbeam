#!/usr/bin/env python3
"""S02 timing pickoff benchmark from raw ROOT waveforms.

The script keeps data read-only and writes only to the configured report directory.
Traditional candidates are pre-registered in configs/s02_timing_pickoff.yaml. The ML
method is a run-split Ridge residual corrector on waveform features.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import uproot
import yaml
from scipy.optimize import curve_fit
from sklearn.linear_model import Ridge
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


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
    runs: List[int] = []
    for group_runs in config["run_groups"].values():
        runs.extend(int(run) for run in group_runs)
    return sorted(set(runs))


def raw_file(config: dict, run: int) -> Path:
    return Path(config["raw_root_dir"]) / f"hrdb_run_{run:04d}.root"


def iter_raw(path: Path, branches: List[str], step_size: int = 20000) -> Iterable[dict]:
    tree = uproot.open(path)["h101"]
    yield from tree.iterate(branches, step_size=step_size, library="np")


def pulse_quantities(waveforms: np.ndarray, baseline_idx: List[int]) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    baseline = np.median(waveforms[..., baseline_idx], axis=-1)
    corrected = waveforms - baseline[..., None]
    amplitude = corrected.max(axis=-1)
    peak_sample = corrected.argmax(axis=-1)
    area = corrected.sum(axis=-1)
    return corrected, amplitude, peak_sample, area


def reproduce_counts(config: dict) -> pd.DataFrame:
    baseline_idx = [int(i) for i in config["baseline_samples"]]
    staves = {name: int(ch) for name, ch in config["staves"].items()}
    stave_names = list(staves.keys())
    channels = np.asarray([staves[name] for name in stave_names])
    nsamp = int(config["samples_per_channel"])
    cut = float(config["amplitude_cut_adc"])
    total = 0
    sample_ii = defaultdict(int)

    for run in configured_runs(config):
        path = raw_file(config, run)
        if not path.exists():
            raise FileNotFoundError(path)
        for batch in iter_raw(path, ["HRDv"]):
            events = np.stack(batch["HRDv"]).astype(np.float64).reshape(-1, 8, nsamp)
            waveforms = events[:, channels, :]
            _, amplitude, _, _ = pulse_quantities(waveforms, baseline_idx)
            selected = amplitude > cut
            total += int(selected.sum())
            if run in config["run_groups"]["sample_ii_analysis"]:
                sample_ii["selected_pulses"] += int(selected.sum())
                for i, stave in enumerate(stave_names):
                    sample_ii[stave] += int(selected[:, i].sum())

    exp = config["expected_counts"]
    rows = [
        {
            "quantity": "total selected B-stave pulses",
            "report_value": int(exp["total_selected_pulses"]),
            "reproduced": int(total),
            "tolerance": 0,
        }
    ]
    for key, value in exp["sample_ii_analysis"].items():
        rows.append(
            {
                "quantity": f"sample_ii_analysis {key}",
                "report_value": int(value),
                "reproduced": int(sample_ii[key]),
                "tolerance": 0,
            }
        )
    out = pd.DataFrame(rows)
    out["delta"] = out["reproduced"] - out["report_value"]
    out["pass"] = out["delta"].abs() <= out["tolerance"]
    return out[["quantity", "report_value", "reproduced", "delta", "tolerance", "pass"]]


def cfd_time_samples(waveforms: np.ndarray, amplitudes: np.ndarray, fraction: float) -> np.ndarray:
    threshold = amplitudes * float(fraction)
    ge = waveforms >= threshold[:, None]
    first = np.argmax(ge, axis=1)
    valid = ge.any(axis=1)
    out = np.full(len(waveforms), np.nan, dtype=float)
    for i in np.where(valid)[0]:
        j = int(first[i])
        if j <= 0:
            out[i] = float(j)
            continue
        y0, y1 = waveforms[i, j - 1], waveforms[i, j]
        denom = y1 - y0
        if denom <= 0:
            out[i] = float(j)
        else:
            out[i] = (j - 1) + (threshold[i] - y0) / denom
    return out


def leading_edge_time_samples(waveforms: np.ndarray, threshold_adc: float) -> np.ndarray:
    ge = waveforms >= float(threshold_adc)
    first = np.argmax(ge, axis=1)
    valid = ge.any(axis=1)
    out = np.full(len(waveforms), np.nan, dtype=float)
    for i in np.where(valid)[0]:
        j = int(first[i])
        if j <= 0:
            out[i] = float(j)
            continue
        y0, y1 = waveforms[i, j - 1], waveforms[i, j]
        denom = y1 - y0
        out[i] = float(j) if denom <= 0 else (j - 1) + (threshold_adc - y0) / denom
    return out


def build_templates(pulses: pd.DataFrame, stave_names: List[str]) -> Dict[str, np.ndarray]:
    templates = {}
    for stave in stave_names:
        sub = pulses[pulses["stave"] == stave]
        wf = np.vstack(sub["waveform"].to_numpy())
        amp = sub["amplitude_adc"].to_numpy()
        norm = wf / np.maximum(amp[:, None], 1.0)
        templates[stave] = np.median(norm, axis=0)
    return templates


def template_cfd_reference(template: np.ndarray, fraction: float = 0.2) -> float:
    amp = float(np.max(template))
    return float(cfd_time_samples(template[None, :], np.asarray([amp]), fraction)[0])


def shifted_template(template: np.ndarray, shift: float) -> np.ndarray:
    x = np.arange(len(template), dtype=float)
    return np.interp(x - shift, x, template, left=template[0], right=template[-1])


def template_phase_time(pulses: pd.DataFrame, templates: Dict[str, np.ndarray], grid: np.ndarray) -> np.ndarray:
    out = np.full(len(pulses), np.nan, dtype=float)
    for stave, template in templates.items():
        idx = np.flatnonzero(pulses["stave"].to_numpy() == stave)
        if len(idx) == 0:
            continue
        refs = template_cfd_reference(template)
        shifted = np.vstack([shifted_template(template, s) for s in grid])
        for row_idx in idx:
            wf = pulses.iloc[row_idx]["waveform"] / max(float(pulses.iloc[row_idx]["amplitude_adc"]), 1.0)
            sse = ((shifted - wf[None, :]) ** 2).sum(axis=1)
            out[row_idx] = refs + grid[int(np.argmin(sse))]
    return out


def optimal_filter_time(pulses: pd.DataFrame, templates: Dict[str, np.ndarray], window: Tuple[int, int]) -> np.ndarray:
    out = np.full(len(pulses), np.nan, dtype=float)
    lo, hi = int(window[0]), int(window[1])
    for stave, template in templates.items():
        idx = np.flatnonzero(pulses["stave"].to_numpy() == stave)
        if len(idx) == 0:
            continue
        refs = template_cfd_reference(template)
        deriv = np.gradient(template)
        sl = slice(lo, hi)
        denom = float(np.dot(deriv[sl], deriv[sl]))
        if denom <= 0:
            continue
        for row_idx in idx:
            wf = pulses.iloc[row_idx]["waveform"] / max(float(pulses.iloc[row_idx]["amplitude_adc"]), 1.0)
            delta = -float(np.dot(wf[sl] - template[sl], deriv[sl]) / denom)
            out[row_idx] = refs + delta
    return out


def load_downstream_pulses(config: dict) -> pd.DataFrame:
    baseline_idx = [int(i) for i in config["baseline_samples"]]
    all_staves = {name: int(ch) for name, ch in config["staves"].items()}
    downstream = list(config["timing"]["downstream_staves"])
    channels = np.asarray([all_staves[name] for name in downstream])
    nsamp = int(config["samples_per_channel"])
    cut = float(config["amplitude_cut_adc"])
    rows = []
    event_uid_base = 0
    for run in sorted(set(config["timing"]["train_runs"] + config["timing"]["heldout_runs"])):
        path = raw_file(config, run)
        for batch in iter_raw(path, ["EVENTNO", "EVT", "HRDv"]):
            eventno = np.asarray(batch["EVENTNO"]).astype(int)
            evt = np.asarray(batch["EVT"]).astype(int)
            events = np.stack(batch["HRDv"]).astype(np.float64).reshape(-1, 8, nsamp)
            waveforms = events[:, channels, :]
            corrected, amplitude, peak, area = pulse_quantities(waveforms, baseline_idx)
            selected = amplitude > cut
            event_mask = selected.all(axis=1)
            if not event_mask.any():
                continue
            event_idx = np.where(event_mask)[0]
            for e in event_idx:
                uid = f"{run}:{int(eventno[e])}:{int(evt[e])}:{event_uid_base + int(e)}"
                for sidx, stave in enumerate(downstream):
                    rows.append(
                        {
                            "event_id": uid,
                            "run": int(run),
                            "eventno": int(eventno[e]),
                            "evt": int(evt[e]),
                            "stave": stave,
                            "waveform": corrected[e, sidx].astype(float),
                            "amplitude_adc": float(amplitude[e, sidx]),
                            "peak_sample": int(peak[e, sidx]),
                            "area_adc_samples": float(area[e, sidx]),
                        }
                    )
            event_uid_base += len(eventno)
    return pd.DataFrame(rows)


def add_traditional_times(pulses: pd.DataFrame, config: dict, templates: Dict[str, np.ndarray]) -> List[str]:
    period = float(config["sample_period_ns"])
    methods = []
    wf = np.vstack(pulses["waveform"].to_numpy())
    amp = pulses["amplitude_adc"].to_numpy()

    pulses["t_le500_ns"] = period * leading_edge_time_samples(wf, float(config["timing"]["leading_edge_threshold_adc"]))
    methods.append("le500")

    for frac in config["timing"]["cfd_fractions"]:
        name = f"cfd{int(round(float(frac) * 100)):02d}"
        pulses[f"t_{name}_ns"] = period * cfd_time_samples(wf, amp, float(frac))
        methods.append(name)

    grid_cfg = config["timing"]["template_shift_grid"]
    grid = np.arange(float(grid_cfg["min"]), float(grid_cfg["max"]) + 0.5 * float(grid_cfg["step"]), float(grid_cfg["step"]))
    pulses["t_template_phase_ns"] = period * template_phase_time(pulses, templates, grid)
    methods.append("template_phase")

    for lo, hi in config["timing"]["of_windows"]:
        name = f"of_{int(lo)}_{int(hi)}"
        pulses[f"t_{name}_ns"] = period * optimal_filter_time(pulses, templates, (int(lo), int(hi)))
        methods.append(name)

    return methods


def geometry_positions(staves: List[str], spacing_cm: float) -> Dict[str, float]:
    order = {"B2": 0, "B4": 1, "B6": 2, "B8": 3}
    return {stave: spacing_cm * order[stave] for stave in staves}


def pairwise_residuals(pulses: pd.DataFrame, method: str, spacing_cm: float, config: dict, runs: List[int]) -> np.ndarray:
    downstream = list(config["timing"]["downstream_staves"])
    positions = geometry_positions(downstream, spacing_cm)
    tof_per_cm = float(config["tof_per_cm_ns"])
    sub = pulses[pulses["run"].isin(runs)].copy()
    sub["tcorr"] = sub[f"t_{method}_ns"] - sub["stave"].map(positions).astype(float) * tof_per_cm
    wide = sub.pivot(index="event_id", columns="stave", values="tcorr").dropna()
    residuals = []
    for a, b in [("B4", "B6"), ("B4", "B8"), ("B6", "B8")]:
        if a in wide and b in wide:
            residuals.append((wide[a] - wide[b]).to_numpy())
    if not residuals:
        return np.asarray([], dtype=float)
    values = np.concatenate(residuals)
    return values[np.isfinite(values)]


def sigma68(values: np.ndarray) -> float:
    values = np.asarray(values)
    if len(values) == 0:
        return float("nan")
    q16, q84 = np.percentile(values, [16, 84])
    return float((q84 - q16) / 2.0)


def full_rms(values: np.ndarray) -> float:
    values = np.asarray(values)
    if len(values) == 0:
        return float("nan")
    return float(np.sqrt(np.mean((values - values.mean()) ** 2)))


def gaussian_const(x: np.ndarray, amp: float, mu: float, sigma: float, c: float) -> np.ndarray:
    return amp * np.exp(-0.5 * ((x - mu) / sigma) ** 2) + c


def core_fit(values: np.ndarray) -> Dict[str, float]:
    values = np.asarray(values)
    med = np.median(values)
    core = values[np.abs(values - med) < 5.0]
    if len(core) < 50:
        return {"core_sigma_ns": float("nan"), "chi2_ndf": float("nan")}
    counts, edges = np.histogram(core, bins=40)
    centers = 0.5 * (edges[1:] + edges[:-1])
    err = np.sqrt(np.maximum(counts, 1.0))
    p0 = [float(counts.max()), float(np.median(core)), float(np.std(core)), float(np.percentile(counts, 5))]
    try:
        popt, _ = curve_fit(gaussian_const, centers, counts, p0=p0, sigma=err, absolute_sigma=True, maxfev=10000)
        expected = gaussian_const(centers, *popt)
        chi2 = float(np.sum(((counts - expected) / err) ** 2))
        ndf = max(len(counts) - len(popt), 1)
        return {"core_sigma_ns": abs(float(popt[2])), "chi2_ndf": chi2 / ndf}
    except Exception:
        return {"core_sigma_ns": float("nan"), "chi2_ndf": float("nan")}


def metric_summary(values: np.ndarray) -> Dict[str, float]:
    values = np.asarray(values)
    fit = core_fit(values)
    return {
        "n_pair_residuals": int(len(values)),
        "median_ns": float(np.median(values)) if len(values) else float("nan"),
        "sigma68_ns": sigma68(values),
        "full_rms_ns": full_rms(values),
        "tail_frac_abs_gt5ns": float(np.mean(np.abs(values - np.median(values)) > 5.0)) if len(values) else float("nan"),
        **fit,
    }


def bootstrap_ci(values: np.ndarray, rng: np.random.Generator, n_boot: int) -> Tuple[float, float]:
    values = np.asarray(values)
    if len(values) == 0:
        return (float("nan"), float("nan"))
    stats = []
    for _ in range(int(n_boot)):
        sample = rng.choice(values, size=len(values), replace=True)
        stats.append(sigma68(sample))
    return (float(np.percentile(stats, 2.5)), float(np.percentile(stats, 97.5)))


def evaluate_methods(pulses: pd.DataFrame, methods: List[str], config: dict) -> pd.DataFrame:
    rows = []
    train_runs = list(config["timing"]["train_runs"])
    heldout_runs = list(config["timing"]["heldout_runs"])
    for method in methods:
        for spacing in config["spacing_cm_values"]:
            for split, runs in [("train", train_runs), ("heldout", heldout_runs)]:
                values = pairwise_residuals(pulses, method, float(spacing), config, runs)
                rows.append(
                    {
                        "method": method,
                        "spacing_cm": float(spacing),
                        "split": split,
                        **metric_summary(values),
                    }
                )
    return pd.DataFrame(rows)


def feature_matrix(pulses: pd.DataFrame, staves: List[str]) -> np.ndarray:
    wf = np.vstack(pulses["waveform"].to_numpy())
    amp = pulses["amplitude_adc"].to_numpy()
    norm = wf / np.maximum(amp[:, None], 1.0)
    peak = pulses["peak_sample"].to_numpy(dtype=float)[:, None]
    log_amp = np.log1p(amp)[:, None]
    area_norm = (pulses["area_adc_samples"].to_numpy() / np.maximum(amp, 1.0))[:, None]
    one_hot = np.zeros((len(pulses), len(staves)))
    stave_to_i = {s: i for i, s in enumerate(staves)}
    for row, stave in enumerate(pulses["stave"]):
        one_hot[row, stave_to_i[stave]] = 1.0
    return np.hstack([norm, log_amp, peak, area_norm, one_hot])


def event_residual_targets(pulses: pd.DataFrame, base_method: str, spacing_cm: float, config: dict) -> np.ndarray:
    downstream = list(config["timing"]["downstream_staves"])
    positions = geometry_positions(downstream, spacing_cm)
    tof_per_cm = float(config["tof_per_cm_ns"])
    sub = pulses.copy()
    sub["tcorr_base"] = sub[f"t_{base_method}_ns"] - sub["stave"].map(positions).astype(float) * tof_per_cm
    wide = sub.pivot(index="event_id", columns="stave", values="tcorr_base")
    target = np.full(len(sub), np.nan, dtype=float)
    event_lookup = {event_id: wide.loc[event_id] for event_id in wide.index}
    for i, row in enumerate(sub.itertuples()):
        vals = event_lookup[row.event_id]
        others = [s for s in downstream if s != row.stave and pd.notna(vals.get(s, np.nan))]
        if len(others) == 2 and math.isfinite(row.tcorr_base):
            target[i] = float(row.tcorr_base - np.mean([vals[s] for s in others]))
    return target


def run_ml(pulses: pd.DataFrame, config: dict, base_method: str, spacing_cm: float) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    staves = list(config["timing"]["downstream_staves"])
    train_runs = list(config["timing"]["train_runs"])
    heldout_runs = list(config["timing"]["heldout_runs"])
    rng = np.random.default_rng(int(config["ml"]["random_seed"]))
    targets = event_residual_targets(pulses, base_method, spacing_cm, config)
    X = feature_matrix(pulses, staves)
    runs = pulses["run"].to_numpy()
    train_mask = np.isin(runs, train_runs) & np.isfinite(targets)
    heldout_mask = np.isin(runs, heldout_runs) & np.isfinite(targets)

    alphas = [float(a) for a in config["ml"]["ridge_alphas"]]
    cv_rows = []
    groups = runs[train_mask]
    n_splits = min(int(config["ml"]["cv_folds"]), len(np.unique(groups)))
    gkf = GroupKFold(n_splits=n_splits)
    for alpha in alphas:
        fold_metrics = []
        for fold, (tr, va) in enumerate(gkf.split(X[train_mask], targets[train_mask], groups=groups)):
            model = make_pipeline(StandardScaler(), Ridge(alpha=alpha))
            model.fit(X[train_mask][tr], targets[train_mask][tr])
            pred = np.full(len(pulses), np.nan)
            idx_train = np.flatnonzero(train_mask)
            pred[idx_train[va]] = model.predict(X[train_mask][va])
            tmp = pulses.copy()
            tmp[f"t_ml_ridge_ns"] = tmp[f"t_{base_method}_ns"] - pred
            vals = pairwise_residuals(tmp.iloc[idx_train[va]], "ml_ridge", spacing_cm, config, list(np.unique(runs[idx_train[va]])))
            fold_metrics.append(sigma68(vals))
            cv_rows.append({"alpha": alpha, "fold": int(fold), "sigma68_ns": sigma68(vals), "n_pair_residuals": int(len(vals))})
        cv_rows.append({"alpha": alpha, "fold": -1, "sigma68_ns": float(np.nanmean(fold_metrics)), "n_pair_residuals": 0})

    cv = pd.DataFrame(cv_rows)
    best_alpha = float(cv[cv["fold"] == -1].sort_values("sigma68_ns").iloc[0]["alpha"])
    model = make_pipeline(StandardScaler(), Ridge(alpha=best_alpha))
    model.fit(X[train_mask], targets[train_mask])
    pred = model.predict(X)
    out = pulses.copy()
    out["ml_target_residual_ns"] = targets
    out["ml_pred_residual_ns"] = pred
    out["t_ml_ridge_ns"] = out[f"t_{base_method}_ns"] - pred

    held = out[heldout_mask].copy()
    cal_rows = []
    if len(held):
        qs = np.quantile(held["ml_pred_residual_ns"], np.linspace(0, 1, 8))
        qs = np.unique(qs)
        if len(qs) >= 3:
            held["cal_bin"] = pd.cut(held["ml_pred_residual_ns"], qs, include_lowest=True, duplicates="drop")
            for _, group in held.groupby("cal_bin"):
                cal_rows.append(
                    {
                        "n": int(len(group)),
                        "pred_mean_ns": float(group["ml_pred_residual_ns"].mean()),
                        "target_mean_ns": float(group["ml_target_residual_ns"].mean()),
                    }
                )
    return out, cv, pd.DataFrame(cal_rows)


def variance_decomposition(pulses: pd.DataFrame, method: str, spacing_cm: float, config: dict, runs: List[int]) -> pd.DataFrame:
    downstream = list(config["timing"]["downstream_staves"])
    positions = geometry_positions(downstream, spacing_cm)
    tof_per_cm = float(config["tof_per_cm_ns"])
    sub = pulses[pulses["run"].isin(runs)].copy()
    sub["tcorr"] = sub[f"t_{method}_ns"] - sub["stave"].map(positions).astype(float) * tof_per_cm
    wide = sub.pivot(index="event_id", columns="stave", values="tcorr").dropna()
    pairs = {}
    for a, b in [("B4", "B6"), ("B4", "B8"), ("B6", "B8")]:
        pairs[(a, b)] = sigma68((wide[a] - wide[b]).to_numpy()) ** 2
    v46, v48, v68 = pairs[("B4", "B6")], pairs[("B4", "B8")], pairs[("B6", "B8")]
    vals = {
        "B4": max((v46 + v48 - v68) / 2.0, 0.0),
        "B6": max((v46 + v68 - v48) / 2.0, 0.0),
        "B8": max((v48 + v68 - v46) / 2.0, 0.0),
    }
    return pd.DataFrame([{"stave": k, "sigma68_ns": math.sqrt(v), "method": method, "spacing_cm": spacing_cm} for k, v in vals.items()])


def plot_outputs(out_dir: Path, scan: pd.DataFrame, pulses: pd.DataFrame, best_method: str, ml_method: str, config: dict, cal: pd.DataFrame) -> None:
    held = scan[scan["split"] == "heldout"].copy()
    fig, ax = plt.subplots(figsize=(9, 4.5))
    held["label"] = held["method"] + " / " + held["spacing_cm"].astype(str) + " cm"
    held = held.sort_values("sigma68_ns")
    ax.bar(np.arange(len(held)), held["sigma68_ns"])
    ax.set_xticks(np.arange(len(held)))
    ax.set_xticklabels(held["label"], rotation=75, ha="right", fontsize=8)
    ax.set_ylabel("held-out pairwise sigma68 (ns)")
    ax.set_title("Pre-registered timing-pickoff scan")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_traditional_scan.png", dpi=130)
    plt.close(fig)

    spacing = float(config["spacing_cm_values"][0])
    runs = list(config["timing"]["heldout_runs"])
    fig, ax = plt.subplots(figsize=(7, 4))
    for method, label in [(best_method, f"traditional {best_method}"), (ml_method, "ML ridge")]:
        vals = pairwise_residuals(pulses, method, spacing, config, runs)
        ax.hist(vals, bins=60, histtype="step", density=True, label=f"{label} sigma68={sigma68(vals):.3f} ns")
    ax.set_xlabel("pairwise corrected residual (ns)")
    ax.set_ylabel("density")
    ax.set_title(f"Held-out run {','.join(map(str, runs))}, spacing={spacing:g} cm")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_dir / "fig_heldout_residuals.png", dpi=130)
    plt.close(fig)

    if len(cal):
        fig, ax = plt.subplots(figsize=(5.5, 4))
        ax.plot(cal["pred_mean_ns"], cal["target_mean_ns"], "o-")
        lim = np.nanmax(np.abs(np.r_[cal["pred_mean_ns"], cal["target_mean_ns"]]))
        ax.plot([-lim, lim], [-lim, lim], "k--", lw=1)
        ax.set_xlabel("mean predicted residual (ns)")
        ax.set_ylabel("mean observed residual (ns)")
        ax.set_title("Held-out ML residual calibration")
        fig.tight_layout()
        fig.savefig(out_dir / "fig_ml_residual_calibration.png", dpi=130)
        plt.close(fig)


def hash_outputs(out_dir: Path) -> Dict[str, str]:
    hashes = {}
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            hashes[path.name] = sha256_file(path)
    return hashes


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/s02_timing_pickoff.yaml")
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = load_config(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    rng = np.random.default_rng(int(config["ml"]["random_seed"]))
    match = reproduce_counts(config)
    match.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(match["pass"].all()):
        raise RuntimeError("S00 reproduction gate failed; see reproduction_match_table.csv")

    pulses = load_downstream_pulses(config)
    pulses_for_template = pulses[pulses["run"].isin(config["timing"]["train_runs"])]
    templates = build_templates(pulses_for_template, list(config["timing"]["downstream_staves"]))
    methods = add_traditional_times(pulses, config, templates)
    scan = evaluate_methods(pulses, methods, config)
    scan.to_csv(out_dir / "traditional_scan_metrics.csv", index=False)

    train_2cm = scan[(scan["split"] == "train") & (scan["spacing_cm"] == 2.0)].sort_values("sigma68_ns")
    best_method = str(train_2cm.iloc[0]["method"])
    best_spacing = float(train_2cm.iloc[0]["spacing_cm"])
    ml_pulses, ml_cv, ml_cal = run_ml(pulses, config, "cfd20", 2.0)
    ml_cv.to_csv(out_dir / "ml_ridge_cv.csv", index=False)
    ml_cal.to_csv(out_dir / "ml_residual_calibration.csv", index=False)

    combined = ml_pulses
    bench_rows = []
    for method, label in [(best_method, f"traditional_best_{best_method}"), ("cfd20", "cfd20_reference"), ("ml_ridge", "ml_ridge")]:
        vals = pairwise_residuals(combined, method, 2.0, config, list(config["timing"]["heldout_runs"]))
        ci = bootstrap_ci(vals, rng, int(config["ml"]["bootstrap_samples"]))
        bench_rows.append(
            {
                "method": label,
                "metric": "heldout pairwise sigma68 ns",
                "value": sigma68(vals),
                "ci_low": ci[0],
                "ci_high": ci[1],
                **metric_summary(vals),
            }
        )
    benchmark = pd.DataFrame(bench_rows)
    benchmark.to_csv(out_dir / "head_to_head_benchmark.csv", index=False)

    single = pd.concat(
        [
            variance_decomposition(combined, best_method, 2.0, config, list(config["timing"]["heldout_runs"])),
            variance_decomposition(combined, "ml_ridge", 2.0, config, list(config["timing"]["heldout_runs"])),
        ],
        ignore_index=True,
    )
    single.to_csv(out_dir / "single_stave_variance_decomposition.csv", index=False)

    plot_outputs(out_dir, scan, combined, best_method, "ml_ridge", config, ml_cal)

    input_hashes = {str(raw_file(config, run)): sha256_file(raw_file(config, run)) for run in configured_runs(config)}
    best_trad = benchmark[benchmark["method"].str.startswith("traditional_best")].iloc[0]
    ml = benchmark[benchmark["method"] == "ml_ridge"].iloc[0]
    ml_delta = float(best_trad["value"] - ml["value"])
    ml_beats = bool(ml["value"] < best_trad["value"])
    result = {
        "study": "S02",
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced": bool(match["pass"].all()),
        "repro_tolerance": "exact S00 selected-count reproduction",
        "traditional": {
            "metric": "heldout_pairwise_sigma68_ns",
            "method": best_method,
            "spacing_cm": best_spacing,
            "value": float(best_trad["value"]),
            "ci": [float(best_trad["ci_low"]), float(best_trad["ci_high"])],
        },
        "ml": {
            "metric": "heldout_pairwise_sigma68_ns",
            "method": "ridge_residual_corrector_on_cfd20",
            "value": float(ml["value"]),
            "ci": [float(ml["ci_low"]), float(ml["ci_high"])],
        },
        "ml_beats_baseline": ml_beats,
        "ml_delta_ns": ml_delta,
        "falsification": {
            "preregistered_metric": "heldout Sample-II B4/B6/B8 pairwise sigma68, run 65",
            "p_value": None,
            "n_tries": len(methods) * len(config["spacing_cm_values"]) + len(config["ml"]["ridge_alphas"]),
            "multiple_comparison": "fixed candidate scan; CIs reported, no discovery p-value claimed",
        },
        "input_sha256": hashlib.sha256("".join(input_hashes.values()).encode("ascii")).hexdigest(),
        "git_commit": git_commit(),
        "critic": "pending",
        "next_tickets": [
            "S02b: template alignment with amplitude-binned templates and timewalk closure",
            "S03a: run-held-out analytic timewalk correction using S02 best pickoff",
        ],
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")

    manifest = {
        "ticket": config["ticket_id"],
        "study": "S02",
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

    print(json.dumps({"out_dir": str(out_dir), "best_method": best_method, "ml_beats": ml_beats, "ml_delta_ns": ml_delta}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
