#!/usr/bin/env python3
"""S14f: saturation energy-ordering geometry stress map.

The ticket asks for a raw-ROOT reproduction gate, then a run-held-out geometry
stress map for S14c-style saturated charge corrections. The target is duplicate
odd-readout closure, scored through monotonic PSTAR/depth energy-proxy envelopes
for 2 cm, 4 cm, and zero-offset geometries, with support-bin ordering and
log-charge diagnostics. This is not an absolute proton-energy calibration.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

import numpy as np
import pandas as pd
import uproot
import yaml
from sklearn.metrics import mean_absolute_error

ROOT = Path(__file__).resolve().parents[1]


def import_script(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


s14c = import_script("s14c_saturation_energy_ordering", ROOT / "scripts" / "s14c_1781014263_712_4e9c774b_saturation_energy_ordering.py")
s14g = import_script("s14g_g4energy", ROOT / "scripts" / "s14g_0000000003_1_g4energy.py")


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
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def ci_pair(values: Sequence[float]) -> List[float]:
    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]
    if len(arr) == 0:
        return [None, None]
    return [float(np.percentile(arr, 2.5)), float(np.percentile(arr, 97.5))]


def fmt_ci(values) -> str:
    if not isinstance(values, (list, tuple)) or len(values) != 2 or values[0] is None:
        return "[NA, NA]"
    return f"[{float(values[0]):.5g}, {float(values[1]):.5g}]"


def md_table(frame: pd.DataFrame, columns: List[str], max_rows: int = 40) -> str:
    sub = frame.loc[:, columns].head(max_rows).copy()
    for col in sub.columns:
        if sub[col].dtype.kind in "fc":
            sub[col] = sub[col].map(lambda v: "" if pd.isna(v) else f"{v:.5g}")
        elif sub[col].dtype.kind in "iu":
            sub[col] = sub[col].map(lambda v: f"{int(v)}")
        else:
            sub[col] = sub[col].map(lambda v: fmt_ci(v) if isinstance(v, (list, tuple)) else str(v))
    widths = [max(len(str(c)), int(sub[c].map(len).max() if len(sub) else 0)) for c in sub.columns]
    header = "| " + " | ".join(str(c).ljust(widths[i]) for i, c in enumerate(sub.columns)) + " |"
    sep = "| " + " | ".join("---" for _ in sub.columns) + " |"
    rows = ["| " + " | ".join(str(row[c]).ljust(widths[i]) for i, c in enumerate(sub.columns)) + " |" for _, row in sub.iterrows()]
    return "\n".join([header, sep] + rows)


def current_lookup(config: dict) -> Dict[int, str]:
    out: Dict[int, str] = {}
    for label, runs in config["current_strata"].items():
        for run in runs:
            out[int(run)] = label
    return out


def saturated_stave_labels(events: pd.DataFrame, pulses: pd.DataFrame, pulse_saturated: np.ndarray) -> List[str]:
    tmp = pulses.loc[pulse_saturated, ["event_id", "stave"]].copy()
    grouped = tmp.groupby("event_id")["stave"].apply(lambda vals: "+".join(sorted(set(str(v) for v in vals))))
    return events["event_id"].map(grouped).fillna("none").astype(str).tolist()


def charge_metrics(y: np.ndarray, pred: np.ndarray) -> dict:
    frac = (np.asarray(pred, dtype=float) - np.asarray(y, dtype=float)) / np.maximum(np.asarray(y, dtype=float), 1.0)
    return {
        "bias_frac": float(np.median(frac)),
        "res68_frac": float(np.percentile(np.abs(frac), 68)),
        "full_rms_frac": float(np.sqrt(np.mean(frac * frac))),
        "tail_gt10pct": float(np.mean(np.abs(frac) > 0.10)),
        "tail_gt25pct": float(np.mean(np.abs(frac) > 0.25)),
    }


def run_bootstrap_metric(events: pd.DataFrame, y: np.ndarray, pred: np.ndarray, mask: np.ndarray, reps: int, seed: int) -> dict:
    idx = np.flatnonzero(mask)
    runs = np.asarray(sorted(events.iloc[idx]["run"].unique()), dtype=int)
    if len(idx) == 0 or len(runs) < 2:
        return {"bias_ci95": [None, None], "res68_ci95": [None, None], "full_rms_ci95": [None, None], "mae_ci95": [None, None]}
    rng = np.random.default_rng(seed)
    by_run = {int(run): idx[events.iloc[idx]["run"].to_numpy(dtype=int) == int(run)] for run in runs}
    bias_vals: List[float] = []
    res_vals: List[float] = []
    rms_vals: List[float] = []
    mae_vals: List[float] = []
    for _ in range(reps):
        chosen = rng.choice(runs, size=len(runs), replace=True)
        sample = np.concatenate([by_run[int(run)] for run in chosen])
        m = charge_metrics(y[sample], pred[sample])
        bias_vals.append(m["bias_frac"])
        res_vals.append(m["res68_frac"])
        rms_vals.append(m["full_rms_frac"])
        mae_vals.append(float(mean_absolute_error(y[sample], pred[sample])))
    return {"bias_ci95": ci_pair(bias_vals), "res68_ci95": ci_pair(res_vals), "full_rms_ci95": ci_pair(rms_vals), "mae_ci95": ci_pair(mae_vals)}


def block_bootstrap_band(
    frame: pd.DataFrame,
    methods: Sequence[str],
    reps: int,
    seed: int,
    acceptance_margin: float,
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    group_cols = ["current_family", "depth_stave", "saturated_stave"]
    for keys, sub in frame.groupby(group_cols):
        current, depth, sat_stave = keys
        runs = np.asarray(sorted(sub["run"].unique()), dtype=int)
        if len(runs) < 2:
            continue
        by_run = {int(run): sub[sub["run"] == int(run)] for run in runs}
        for method in methods:
            sat_col = f"{method}_energy_residual_abs"
            control_col = f"{method}_control_energy_residual_abs"
            if sat_col not in sub or control_col not in sub:
                continue
            sat_res = float(np.percentile(sub[sat_col].to_numpy(dtype=float), 68))
            control_res = float(np.percentile(sub[control_col].dropna().to_numpy(dtype=float), 68))
            boot_sat = []
            boot_control = []
            boot_delta = []
            for _ in range(reps):
                chosen = rng.choice(runs, size=len(runs), replace=True)
                sample = pd.concat([by_run[int(run)] for run in chosen], ignore_index=True)
                s = float(np.percentile(sample[sat_col].to_numpy(dtype=float), 68))
                cvals = sample[control_col].dropna().to_numpy(dtype=float)
                c = float(np.percentile(cvals, 68)) if len(cvals) else float("nan")
                boot_sat.append(s)
                boot_control.append(c)
                boot_delta.append(s - c)
            delta = sat_res - control_res
            rows.append(
                {
                    "current_family": current,
                    "depth_stave": depth,
                    "saturated_stave": sat_stave,
                    "method": method,
                    "n_saturated": int(len(sub)),
                    "n_runs": int(len(runs)),
                    "matched_unsat_control_rows": int(
                        sub[["run", "current_family", "depth_stave", "matched_unsat_control_rows"]]
                        .drop_duplicates()["matched_unsat_control_rows"]
                        .sum()
                    ),
                    "saturated_energy_res68": sat_res,
                    "saturated_energy_res68_ci95": ci_pair(boot_sat),
                    "matched_unsat_energy_res68": control_res,
                    "matched_unsat_energy_res68_ci95": ci_pair(boot_control),
                    "sat_minus_unsat_res68": delta,
                    "sat_minus_unsat_res68_ci95": ci_pair(boot_delta),
                    "accepted_with_margin": bool(delta <= acceptance_margin),
                }
            )
    return pd.DataFrame(rows)


def depth_order_violation_rate(sub: pd.DataFrame, energy_col: str, margin_frac: float = 0.0) -> float:
    med = sub.groupby("depth_idx")[energy_col].median().sort_index()
    if len(med) < 2:
        return float("nan")
    vals = med.to_numpy(dtype=float)
    violations = vals[1:] < vals[:-1] * (1.0 + margin_frac)
    return float(np.mean(violations))


def bootstrap_ordering(
    sub: pd.DataFrame,
    energy_col: str,
    reps: int,
    seed: int,
    margin_frac: float = 0.0,
) -> List[float]:
    runs = np.asarray(sorted(sub["run"].unique()), dtype=int)
    if len(runs) < 2:
        return [None, None]
    rng = np.random.default_rng(seed)
    by_run = {int(run): sub[sub["run"] == int(run)] for run in runs}
    values: List[float] = []
    for _ in range(reps):
        chosen = rng.choice(runs, size=len(runs), replace=True)
        sample = pd.concat([by_run[int(run)] for run in chosen], ignore_index=True)
        values.append(depth_order_violation_rate(sample, energy_col, margin_frac))
    return ci_pair(values)


def support_stress_table(
    frame: pd.DataFrame,
    methods: Sequence[str],
    reps: int,
    seed: int,
    acceptance_margin: float,
    log_delta_limit: float,
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    group_cols = ["geometry", "current_family", "depth_stave", "saturated_stave"]
    for keys, sub in frame.groupby(group_cols):
        geom, current, depth, sat_stave = keys
        runs = np.asarray(sorted(sub["run"].unique()), dtype=int)
        if len(runs) < 2:
            continue
        by_run = {int(run): sub[sub["run"] == int(run)] for run in runs}
        for method in methods:
            resid_col = f"{method}_energy_residual_abs"
            sat_log_col = f"{method}_sat_log_residual"
            ctrl_log_col = f"{method}_control_log_residual"
            if resid_col not in sub or sat_log_col not in sub or ctrl_log_col not in sub:
                continue
            vals = sub[resid_col].to_numpy(dtype=float)
            ctrl = sub[ctrl_log_col].dropna().to_numpy(dtype=float)
            sat_res68 = float(np.percentile(vals, 68))
            sat_log = float(np.median(sub[sat_log_col].to_numpy(dtype=float)))
            control_log = float(np.median(ctrl)) if len(ctrl) else float("nan")
            delta = sat_log - control_log
            boot_res: List[float] = []
            boot_delta: List[float] = []
            for _ in range(reps):
                chosen = rng.choice(runs, size=len(runs), replace=True)
                sample = pd.concat([by_run[int(run)] for run in chosen], ignore_index=True)
                boot_res.append(float(np.percentile(sample[resid_col].to_numpy(dtype=float), 68)))
                sample_ctrl = sample[ctrl_log_col].dropna().to_numpy(dtype=float)
                if len(sample_ctrl):
                    boot_delta.append(
                        float(np.median(sample[sat_log_col].to_numpy(dtype=float)) - np.median(sample_ctrl))
                    )
            rows.append(
                {
                    "geometry": geom,
                    "current_family": current,
                    "depth_stave": depth,
                    "saturated_stave": sat_stave,
                    "method": method,
                    "n_saturated": int(len(sub)),
                    "n_runs": int(len(runs)),
                    "matched_unsat_control_rows": int(sub["matched_unsat_control_rows"].sum()),
                    "energy_res68": sat_res68,
                    "energy_res68_ci95": ci_pair(boot_res),
                    "sat_minus_unsat_log_charge_delta": delta,
                    "sat_minus_unsat_log_charge_delta_ci95": ci_pair(boot_delta),
                    "passes_res68_margin": bool(sat_res68 <= acceptance_margin + float(sub[f"{method}_control_energy_res68"].median())),
                    "passes_log_delta_limit": bool(abs(delta) <= log_delta_limit),
                }
            )
    return pd.DataFrame(rows)


def ordering_stress_table(
    frame: pd.DataFrame,
    methods: Sequence[str],
    reps: int,
    seed: int,
    margin_frac: float,
) -> pd.DataFrame:
    rows = []
    group_cols = ["geometry", "current_family", "saturated_stave"]
    for keys, sub in frame.groupby(group_cols):
        geom, current, sat_stave = keys
        if sub["depth_idx"].nunique() < 2:
            continue
        for method in methods:
            col = f"{method}_energy"
            if col not in sub:
                continue
            rows.append(
                {
                    "geometry": geom,
                    "current_family": current,
                    "saturated_stave": sat_stave,
                    "method": method,
                    "n_saturated": int(len(sub)),
                    "n_depth_bins": int(sub["depth_idx"].nunique()),
                    "depth_order_violation_rate": depth_order_violation_rate(sub, col, margin_frac),
                    "depth_order_violation_rate_ci95": bootstrap_ordering(
                        sub,
                        col,
                        reps,
                        seed + len(rows) + len(method),
                        margin_frac,
                    ),
                    "target_depth_order_violation_rate": depth_order_violation_rate(sub, "target_energy", margin_frac),
                }
            )
    return pd.DataFrame(rows)


def fit_ml_predictions(
    events: pd.DataFrame,
    event_wave: np.ndarray,
    target: np.ndarray,
    train: np.ndarray,
    config: dict,
    baseline: np.ndarray,
) -> Tuple[Dict[str, np.ndarray], List[str], str]:
    x, feature_names = s14g.event_features(events, event_wave)
    predictions: Dict[str, np.ndarray] = {}
    tabular = s14g.fit_tabular_models(x, target, train, config)
    for name, model in tabular.items():
        predictions[name] = s14g.exp_clip(model.predict(x))
    mlp_model, mlp_scaler = s14g.fit_torch_mlp(x, np.log(np.maximum(target, 1.0)), train, config, extra_seed=31)
    predictions["mlp"] = s14g.exp_clip(s14g.predict_torch_mlp(mlp_model, mlp_scaler, x))
    try:
        cnn, cnn_scaler = s14g.fit_cnn(event_wave, x, target, train, config)
        predictions["1d_cnn"] = s14g.predict_cnn(cnn, cnn_scaler, event_wave, x)
        cnn_status = "trained"
    except Exception as exc:
        predictions["1d_cnn"] = np.full(len(target), np.nan)
        cnn_status = f"failed: {exc}"
    residual_model, residual_scaler = s14g.fit_residual_mlp(x, baseline, target, train, config)
    predictions["template_residual_mlp"] = s14g.predict_residual_mlp(residual_model, residual_scaler, x, baseline)
    predictions = {name: np.clip(pred, *np.percentile(target[train], [0.1, 99.9])) for name, pred in predictions.items()}
    return predictions, feature_names, cnn_status


def safe_log_calibrated(est: np.ndarray, target: np.ndarray, train_mask: np.ndarray) -> np.ndarray:
    """Apply the S14c train-only log calibrator with numerical exp bounds only."""
    model = s14c.fit_log_calibrator(est, target, train_mask)
    log_pred = model.predict(np.log(np.maximum(est, 1.0))[:, None])
    return np.exp(np.clip(log_pred, -20.0, 20.0))


def sanitize_prediction(pred: np.ndarray) -> np.ndarray:
    """Keep S14c predictions but replace rare exp overflows with finite bounds."""
    out = np.asarray(pred, dtype=float).copy()
    finite = np.isfinite(out)
    if finite.all():
        return out
    if not finite.any():
        raise RuntimeError("prediction vector has no finite values")
    lo, hi = np.percentile(out[finite], [0.1, 99.9])
    return np.nan_to_num(out, nan=float(lo), posinf=float(hi), neginf=float(lo))


def make_figure(out_dir: Path, metrics: pd.DataFrame) -> None:
    try:
        import matplotlib.pyplot as plt
    except Exception:
        return
    ranked = metrics.sort_values("saturated_energy_res68").head(10)
    y = np.arange(len(ranked))
    fig, ax = plt.subplots(figsize=(8, 4.8))
    ax.barh(y, ranked["saturated_energy_res68"].to_numpy(dtype=float), color="#4c78a8")
    ax.set_yticks(y, ranked["method"].astype(str))
    ax.invert_yaxis()
    ax.set_xlabel("held-out saturated energy-proxy res68")
    ax.set_title("S14f saturated-event geometry stress benchmark")
    ax.grid(axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_s14f_saturated_res68.png", dpi=140)
    plt.close(fig)


def write_report(
    out_dir: Path,
    config: dict,
    result: dict,
    metrics: pd.DataFrame,
    acceptance: pd.DataFrame,
    by_run: pd.DataFrame,
    geometry: pd.DataFrame,
    support_stress: pd.DataFrame,
    ordering_stress: pd.DataFrame,
    method_geometry_summary: pd.DataFrame,
    leakage: pd.DataFrame,
) -> None:
    winner = result["winner"]
    named = metrics[metrics["method"].isin(["observed_even_charge", "traditional_template_corrected", "p07_p04_corrected"])].copy()
    ranked = metrics.sort_values("saturated_energy_res68")
    accepted = acceptance[acceptance["accepted_with_margin"]].sort_values(["saturated_energy_res68", "sat_minus_unsat_res68"])
    worsening = geometry[
        geometry["traditional_worsens_observed"] & geometry["method"].eq("traditional_template_corrected")
    ].copy()
    lines = [
        "# S14f: saturation energy-ordering geometry stress map",
        "",
        "## Abstract",
        "",
        (
            f"Raw B-stack ROOT reproduction passes exactly at {result['raw_reproduction']['reproduced_selected_pulses']:,} selected pulses. "
            f"The geometry-stress winner is **{winner['method']}** with worst-geometry saturated energy-proxy res68 "
            f"{winner['worst_geometry_saturated_energy_res68']:.5f}. The nominal center-4cm res68 is "
            f"{winner['saturated_energy_res68']:.5f} with run-bootstrap 95% CI {fmt_ci(winner['saturated_energy_res68_ci95'])}. "
            "Support-bin tables expose depth-order inversions, energy-proxy res68, and saturated-minus-unsaturated log-charge deltas across the 2 cm, 4 cm, and zero-offset geometry envelopes."
        ),
        "",
        "## 0. Question",
        "",
        "Does the S14c saturation-corrected charge proxy preserve energy ordering under the 2 cm, 4 cm, and zero-offset geometry envelopes after saturation, anomaly, and topology support restrictions are applied?",
        "",
        "## 1. Reproduction Gate",
        "",
        "The first operation rebuilds selected B2/B4/B6/B8 pulses directly from raw `HRDv`: median samples 0--3 define the baseline and the gate is peak amplitude above 1000 ADC.",
        "",
        "| Quantity | Report value | Reproduced | Delta | Tolerance | Pass? |",
        "|---|---:|---:|---:|---:|:---|",
        f"| S14c/S00 selected B-stave pulse records | {result['raw_reproduction']['expected_selected_pulses']:,} | {result['raw_reproduction']['reproduced_selected_pulses']:,} | {result['raw_reproduction']['delta']:+,} | 0 | {str(result['raw_reproduction']['pass']).lower()} |",
        "",
        "## 2. Methods",
        "",
        "The closure target is the same-event odd duplicate readout, restricted to valid positive charge. This target is not external calorimetry; it tests whether even-channel saturation correction is self-consistent under run-disjoint calibration.",
        "",
        "For each event and method, charge is mapped to a monotonic range-energy proxy by a train-only depth-charge quantile map. If \\(Q\\) is corrected even charge and depth is \\(d\\), the score uses \\(\\hat E=f_d(\\log Q)\\), where \\(f_d\\) maps train-run charge quantiles onto the PSTAR depth bin \\([E_{d,lo},E_{d,hi}]\\). The target is the analogous \\(E=f_d(\\log Q_{odd})\\).",
        "",
        "For a held-out support bin \\(b\\), the main resolution is \\(R_{68,b}=P_{68}(|(\\hat E-E)/E|)\\). The log-charge systematic is \\(\\Delta_{\\log Q,b}=\\operatorname{median}_{sat,b}\\log(\\hat Q/Q_{odd})-\\operatorname{median}_{unsat,b}\\log(\\hat Q/Q_{odd})\\), with unsaturated controls matched by run, current family, and depth. The depth-order violation rate is the fraction of adjacent depth-bin median pairs with \\(\\operatorname{median}(\\hat E_{d+1}) < \\operatorname{median}(\\hat E_d)\\). All CIs resample held-out runs with replacement.",
        "",
        "Traditional rising-edge correction uses train-run amplitude-binned median templates. For a saturated pulse, unclipped samples are fit by a shifted normalized template and the recovered amplitude rescales the template charge. The P07/P04 method first learns artificial fixed-ceiling amplitude recovery from train-run clean pulses, then predicts duplicate odd charge from even waveform features. Additional ML/NN comparators are ridge regression, gradient-boosted trees, tabular MLP, 1D-CNN over the four B-stave waveforms, and a template-residual MLP that learns a multiplicative correction to the traditional template estimate.",
        "",
        "The primary S14f selection metric is worst-geometry saturated energy-proxy res68. Nominal center-4cm saturated res68 is retained for comparison with S14d, while ordering and log-charge deltas are treated as systematics.",
        "",
        "## 3. Head-to-Head Benchmark",
        "",
        md_table(ranked, ["method", "family", "n_saturated", "saturated_bias_frac", "saturated_energy_res68", "saturated_energy_res68_ci95", "saturated_full_rms_frac", "saturated_tail_gt25pct", "all_heldout_energy_res68"]),
        "",
        "The named S14c correction families on the same saturated held-out rows are:",
        "",
        md_table(named, ["method", "family", "n_saturated", "saturated_energy_res68", "saturated_energy_res68_ci95", "saturated_charge_res68", "traditional_worsens_observed"]),
        "",
        "## 4. Geometry Stress Summary",
        "",
        "The winner is chosen by the smallest maximum saturated res68 across all geometry envelopes.",
        "",
        md_table(method_geometry_summary, ["method", "family", "worst_geometry_saturated_energy_res68", "best_geometry_saturated_energy_res68", "max_depth_order_violation_rate", "max_abs_log_charge_delta"], max_rows=20),
        "",
        "Per-geometry saturated-event metrics:",
        "",
        md_table(geometry, ["geometry", "method", "saturated_energy_res68", "saturated_energy_res68_ci95", "traditional_minus_observed_res68", "traditional_worsens_observed"], max_rows=120),
        "",
        "## 5. Support-Bin Stress Map",
        "",
        "A band is accepted when its saturated-event res68 is no more than `acceptance_margin_res68` above matched unsaturated controls. Controls are matched within held-out run, current family, and depth stave; the aggregate CI resamples held-out runs.",
        "",
        md_table(accepted, ["current_family", "depth_stave", "saturated_stave", "method", "n_saturated", "n_runs", "saturated_energy_res68", "saturated_energy_res68_ci95", "matched_unsat_energy_res68", "sat_minus_unsat_res68", "accepted_with_margin"], max_rows=30),
        "",
        "The S14f support map adds geometry and log-charge stress terms. The displayed rows are the strongest winner-method support cells by res68.",
        "",
        md_table(
            support_stress[support_stress["method"].eq(winner["method"])].sort_values(["energy_res68", "geometry"]),
            ["geometry", "current_family", "depth_stave", "saturated_stave", "method", "n_saturated", "energy_res68", "energy_res68_ci95", "sat_minus_unsat_log_charge_delta", "sat_minus_unsat_log_charge_delta_ci95", "passes_log_delta_limit"],
            max_rows=60,
        ),
        "",
        "## 6. Depth-Order Stress",
        "",
        "Rows show support bins with at least two depth staves. A zero rate means adjacent depth-bin medians remain nondecreasing for that method and geometry.",
        "",
        md_table(
            ordering_stress.sort_values(["depth_order_violation_rate", "geometry", "method"]),
            ["geometry", "current_family", "saturated_stave", "method", "n_saturated", "n_depth_bins", "depth_order_violation_rate", "depth_order_violation_rate_ci95", "target_depth_order_violation_rate"],
            max_rows=80,
        ),
        "",
        "## 7. Per-Run Diagnostics",
        "",
        md_table(by_run[by_run["method"].isin([winner["method"], "observed_even_charge", "traditional_template_corrected", "p07_p04_corrected"])], ["run", "current_family", "method", "n_saturated", "saturated_energy_res68", "saturated_charge_res68"], max_rows=80),
        "",
        "## 8. Traditional-Systematic Caveat",
        "",
        "The explicit S14c-style warning is the `traditional_worsens_observed` flag: the rising-edge template correction is worse than observed charge for the same geometry and saturated held-out rows.",
        "",
        "Rows where the traditional template worsens observed charge:",
        "",
        md_table(worsening, ["geometry", "method", "saturated_energy_res68", "traditional_minus_observed_res68", "traditional_worsens_observed"], max_rows=20),
        "",
        "## 9. Leakage and Caveats",
        "",
        md_table(leakage, ["check", "value", "pass"], max_rows=30),
        "",
        "The main caveat is target scope: duplicate odd-readout closure is an electronics self-consistency test, not deposited-energy truth. The PSTAR/depth map supplies an ordering proxy, while Birks quenching, material budget, geometry, and particle identity remain external systematics. Geometry variants are therefore stress envelopes, not calibrated detector survey alternatives. Current labels use the documented low-current runs 46--47 versus the otherwise high-current B-stack runs; Sample-II runs are treated as high-current for this audit.",
        "",
        "## 10. Finding",
        "",
        result["finding"],
        "",
        "## 11. Reproducibility",
        "",
        "```bash",
        "/home/billy/anaconda3/bin/python scripts/s14f_1781033587_678_10103f5a_saturation_geometry_stress_map.py --config configs/s14f_1781033587_678_10103f5a_saturation_geometry_stress_map.yaml",
        "```",
        "",
        "Artifacts: `result.json`, `manifest.json`, `method_metrics.csv`, `acceptance_bands.csv`, `support_stress_map.csv`, `ordering_stress.csv`, `method_geometry_summary.csv`, `per_run_acceptance.csv`, `geometry_systematics.csv`, `leakage_checks.csv`, `reproduction_match_table.csv`, `input_sha256.csv`, and `fig_s14f_saturated_res68.png`.",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/s14f_1781033587_678_10103f5a_saturation_geometry_stress_map.yaml")
    args = parser.parse_args()
    t0 = time.time()
    config_path = ROOT / args.config if not Path(args.config).is_absolute() else Path(args.config)
    config = load_config(config_path)
    out_dir = ROOT / config["output_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)
    rng_seed = int(config["random_seed"])

    print("1/8 raw ROOT reproduction and extraction", flush=True)
    events, pulses, event_wave, pulse_wave, counts = s14g.extract_tables(config)
    total = int(counts["selected_pulses"].sum())
    expected = int(config["expected_selected_pulses"])
    if total != expected:
        raise RuntimeError(f"raw selected-pulse reproduction failed: {total} != {expected}")

    valid_events = (events["odd_total_charge"].to_numpy(dtype=float) > 100.0) & (events["even_total_charge"].to_numpy(dtype=float) > 100.0)
    events = events.loc[valid_events].reset_index(drop=True)
    event_wave = event_wave[valid_events]
    valid_ids = set(int(x) for x in events["event_id"].to_numpy())
    pulse_valid = pulses["event_id"].isin(valid_ids).to_numpy() & (pulses["odd_charge"].to_numpy(dtype=float) > 20.0)
    pulses = pulses.loc[pulse_valid].reset_index(drop=True)
    pulse_wave = pulse_wave[pulse_valid]

    held_runs = s14c.heldout_runs(config)
    held = events["run"].isin(held_runs).to_numpy()
    train = ~held
    pulse_train = ~pulses["run"].isin(held_runs).to_numpy()
    current_map = current_lookup(config)
    events["current_family"] = events["run"].map(lambda run: current_map.get(int(run), "unknown"))

    print("2/8 S14c observed/template/P07-P04 corrections", flush=True)
    templates = s14c.build_templates(pulses, pulse_wave, pulse_train, config)
    trad_amp = s14c.template_recovered_amplitude(pulses, pulse_wave, templates, config)
    trad_pulse_charge = s14c.template_charge_from_amp(pulses, trad_amp, templates, config)
    p07_model = s14c.fit_p07_ratio_model(pulses, pulse_wave, pulse_train, config)
    p07_amp = pulses["even_amp"].to_numpy(dtype=float).copy()
    pulse_saturated = pulses["saturated"].to_numpy(dtype=bool)
    if pulse_saturated.any():
        ceilings = pulses.loc[pulse_saturated, "even_amp"].to_numpy(dtype=float)
        staves = pulses.loc[pulse_saturated, "stave_idx"].to_numpy(dtype=int)
        ratio = np.exp(p07_model.predict(s14c.p07_ratio_features(pulse_wave[pulse_saturated], ceilings, staves)))
        p07_amp[pulse_saturated] = np.maximum(ceilings, ceilings * ratio)
    p07_charge_seed = pulses["even_charge"].to_numpy(dtype=float) * np.maximum(p07_amp, 1.0) / np.maximum(pulses["even_amp"].to_numpy(dtype=float), 1.0)
    p04_x = s14c.p04_features(pulses, pulse_wave, p07_amp, p07_charge_seed)
    p04_model = s14c.fit_p04_charge_model(pulses, p04_x, pulse_train, config, shuffled=False)
    p04_pulse_pred = np.exp(p04_model.predict(p04_x))
    shuffled_model = s14c.fit_p04_charge_model(pulses, p04_x, pulse_train, config, shuffled=True)
    shuffled_pulse_pred = np.exp(shuffled_model.predict(p04_x))

    odd_charge = events["odd_total_charge"].to_numpy(dtype=float)
    observed = events["even_total_charge"].to_numpy(dtype=float)
    trad_event = s14c.aggregate_event_charge(events, pulses, trad_pulse_charge, "charge").to_numpy(dtype=float)
    p07p04_event = s14c.aggregate_event_charge(events, pulses, p04_pulse_pred, "charge").to_numpy(dtype=float)
    shuffled_event = s14c.aggregate_event_charge(events, pulses, shuffled_pulse_pred, "charge").to_numpy(dtype=float)
    unsat_train = train & (~events["any_saturated"].to_numpy(dtype=bool))
    observed_cal = sanitize_prediction(s14c.apply_log_calibrator(s14c.fit_log_calibrator(observed, odd_charge, unsat_train), observed))
    trad_cal = sanitize_prediction(s14c.apply_log_calibrator(s14c.fit_log_calibrator(trad_event, odd_charge, unsat_train), trad_event))
    p07p04_cal = safe_log_calibrated(p07p04_event, odd_charge, unsat_train)
    shuffled_cal = safe_log_calibrated(shuffled_event, odd_charge, unsat_train)

    print("3/8 ML/NN panel", flush=True)
    predictions: Dict[str, np.ndarray] = {
        "observed_even_charge": observed_cal,
        "traditional_template_corrected": trad_cal,
        "p07_p04_corrected": p07p04_cal,
    }
    ml_predictions, feature_names, cnn_status = fit_ml_predictions(events, event_wave, odd_charge, train, config, trad_cal)
    predictions.update(ml_predictions)
    families = {
        "observed_even_charge": "traditional_observed",
        "traditional_template_corrected": "traditional_rising_edge_template",
        "p07_p04_corrected": "ml_p07_p04_duplicate",
        "ridge": "ml_linear",
        "gradient_boosted_trees": "ml_tree",
        "mlp": "neural_tabular",
        "1d_cnn": "neural_waveform",
        "template_residual_mlp": "neural_template_residual",
    }
    predictions = {name: pred for name, pred in predictions.items() if np.isfinite(pred).all()}

    print("4/8 energy-proxy transforms", flush=True)
    staves = list(config["staves"].keys())
    geometry_energy: Dict[str, Tuple[np.ndarray, Dict[str, np.ndarray]]] = {}
    for geom in config["geometry_variants"]:
        anchors = s14c.geometry_anchors(config, geom, staves)
        depth = events["depth_idx"].to_numpy(dtype=int)
        y_energy = s14c.DepthChargeQuantileCalibrator(anchors).fit(odd_charge, depth, train).predict(odd_charge, depth)
        pred_energy = {
            name: s14c.DepthChargeQuantileCalibrator(anchors).fit(pred, depth, train).predict(pred, depth)
            for name, pred in predictions.items()
        }
        geometry_energy[geom] = (y_energy, pred_energy)

    print("5/8 aggregate metrics", flush=True)
    saturated = held & events["any_saturated"].to_numpy(dtype=bool)
    unsat_held = held & (~events["any_saturated"].to_numpy(dtype=bool))
    nominal_y, nominal_pred_energy = geometry_energy[config["nominal_geometry"]]
    metric_rows = []
    for method, pred_charge in predictions.items():
        pred_energy = nominal_pred_energy[method]
        sat_idx = np.flatnonzero(saturated)
        all_idx = np.flatnonzero(held)
        unsat_idx = np.flatnonzero(unsat_held)
        sat_m = charge_metrics(nominal_y[sat_idx], pred_energy[sat_idx])
        sat_charge = charge_metrics(odd_charge[sat_idx], pred_charge[sat_idx])
        row = {
            "method": method,
            "family": families.get(method, "unknown"),
            "n_saturated": int(len(sat_idx)),
            "n_heldout": int(len(all_idx)),
            "n_unsaturated_control": int(len(unsat_idx)),
            "saturated_bias_frac": sat_m["bias_frac"],
            "saturated_energy_res68": sat_m["res68_frac"],
            "saturated_full_rms_frac": sat_m["full_rms_frac"],
            "saturated_tail_gt10pct": sat_m["tail_gt10pct"],
            "saturated_tail_gt25pct": sat_m["tail_gt25pct"],
            "saturated_mae_proxy": float(mean_absolute_error(nominal_y[sat_idx], pred_energy[sat_idx])),
            "saturated_charge_res68": sat_charge["res68_frac"],
            "all_heldout_energy_res68": charge_metrics(nominal_y[all_idx], pred_energy[all_idx])["res68_frac"],
            "unsaturated_energy_res68": charge_metrics(nominal_y[unsat_idx], pred_energy[unsat_idx])["res68_frac"],
        }
        boot = run_bootstrap_metric(events, nominal_y, pred_energy, saturated, int(config["bootstrap_reps"]), rng_seed + len(method))
        row.update(
            {
                "saturated_bias_ci95": boot["bias_ci95"],
                "saturated_energy_res68_ci95": boot["res68_ci95"],
                "saturated_full_rms_ci95": boot["full_rms_ci95"],
                "saturated_mae_ci95": boot["mae_ci95"],
            }
        )
        metric_rows.append(row)
    metrics = pd.DataFrame(metric_rows).sort_values("saturated_energy_res68").reset_index(drop=True)
    obs_res = float(metrics.loc[metrics["method"] == "observed_even_charge", "saturated_energy_res68"].iloc[0])
    trad_res = float(metrics.loc[metrics["method"] == "traditional_template_corrected", "saturated_energy_res68"].iloc[0])
    metrics["traditional_worsens_observed"] = metrics["method"].eq("traditional_template_corrected") & (trad_res > obs_res)

    print("6/8 acceptance bands", flush=True)
    events["saturated_stave"] = saturated_stave_labels(events, pulses, pulse_saturated)
    band_base = events.loc[saturated, ["run", "current_family", "depth_stave", "saturated_stave"]].copy()
    control_key = events.loc[unsat_held, ["run", "current_family", "depth_stave"]].copy()
    for method in predictions:
        pred_e = nominal_pred_energy[method]
        abs_res = np.abs((pred_e - nominal_y) / np.maximum(nominal_y, 1.0))
        band_base[f"{method}_energy_residual_abs"] = abs_res[saturated]
        ctrl = control_key.copy()
        ctrl["abs_res"] = abs_res[unsat_held]
        control_stats = ctrl.groupby(["run", "current_family", "depth_stave"])["abs_res"].agg(
            matched_unsat_control_rows="size",
            control_res68=lambda values: float(np.percentile(values, 68)),
        )
        joined = band_base[["run", "current_family", "depth_stave"]].join(control_stats, on=["run", "current_family", "depth_stave"])
        band_base[f"{method}_control_energy_residual_abs"] = joined["control_res68"].to_numpy(dtype=float)
        band_base["matched_unsat_control_rows"] = joined["matched_unsat_control_rows"].fillna(0).astype(int).to_numpy()

    acceptance_methods = ["observed_even_charge", "traditional_template_corrected", "p07_p04_corrected", metrics.iloc[0]["method"]]
    acceptance_methods = list(dict.fromkeys(str(m) for m in acceptance_methods))
    acceptance = block_bootstrap_band(
        band_base,
        acceptance_methods,
        int(config["bootstrap_reps"]),
        rng_seed + 500,
        float(config["acceptance_margin_res68"]),
    )
    if not acceptance.empty:
        acceptance = acceptance[
            (acceptance["n_saturated"] >= int(config["min_saturated_cell"]))
            & (acceptance["matched_unsat_control_rows"] >= int(config["min_unsaturated_control_cell"]))
        ].reset_index(drop=True)

    by_run_rows = []
    for (run, current), sub in events.loc[saturated].groupby(["run", "current_family"]):
        idx = sub.index.to_numpy(dtype=int)
        for method, pred_charge in predictions.items():
            by_run_rows.append(
                {
                    "run": int(run),
                    "current_family": current,
                    "method": method,
                    "n_saturated": int(len(idx)),
                    "saturated_energy_res68": charge_metrics(nominal_y[idx], nominal_pred_energy[method][idx])["res68_frac"],
                    "saturated_charge_res68": charge_metrics(odd_charge[idx], pred_charge[idx])["res68_frac"],
                }
            )
    by_run = pd.DataFrame(by_run_rows)

    print("7/8 geometry and support stress maps", flush=True)
    geom_rows = []
    for geom, (y_energy, pred_energy) in geometry_energy.items():
        obs = charge_metrics(y_energy[np.flatnonzero(saturated)], pred_energy["observed_even_charge"][np.flatnonzero(saturated)])["res68_frac"]
        trad = charge_metrics(y_energy[np.flatnonzero(saturated)], pred_energy["traditional_template_corrected"][np.flatnonzero(saturated)])["res68_frac"]
        for method in predictions:
            if method not in pred_energy:
                continue
            boot = run_bootstrap_metric(events, y_energy, pred_energy[method], saturated, int(config["bootstrap_reps"]), rng_seed + 700 + len(method) + len(geom))
            geom_rows.append(
                {
                    "geometry": geom,
                    "method": method,
                    "family": families.get(method, "unknown"),
                    "saturated_energy_res68": charge_metrics(y_energy[np.flatnonzero(saturated)], pred_energy[method][np.flatnonzero(saturated)])["res68_frac"],
                    "saturated_energy_res68_ci95": boot["res68_ci95"],
                    "traditional_minus_observed_res68": trad - obs,
                    "traditional_worsens_observed": bool(trad > obs),
                }
            )
    geometry = pd.DataFrame(geom_rows)

    stress_frames = []
    base_stress = events.loc[saturated, ["run", "current_family", "depth_stave", "depth_idx", "saturated_stave"]].copy()
    control_key = events.loc[unsat_held, ["run", "current_family", "depth_stave"]].copy()
    for geom, (y_energy, pred_energy) in geometry_energy.items():
        frame = base_stress.copy()
        frame["geometry"] = geom
        frame["target_energy"] = y_energy[saturated]
        for method, pred_charge in predictions.items():
            pred_e = pred_energy[method]
            abs_res = np.abs((pred_e - y_energy) / np.maximum(y_energy, 1.0))
            log_res = np.log(np.maximum(pred_charge, 1.0) / np.maximum(odd_charge, 1.0))
            frame[f"{method}_energy"] = pred_e[saturated]
            frame[f"{method}_energy_residual_abs"] = abs_res[saturated]
            frame[f"{method}_sat_log_residual"] = log_res[saturated]
            ctrl = control_key.copy()
            ctrl["abs_res"] = abs_res[unsat_held]
            ctrl["log_res"] = log_res[unsat_held]
            control_stats = ctrl.groupby(["run", "current_family", "depth_stave"]).agg(
                matched_unsat_control_rows=("abs_res", "size"),
                control_energy_res68=("abs_res", lambda values: float(np.percentile(values, 68))),
                control_log_residual=("log_res", "median"),
            )
            joined = frame[["run", "current_family", "depth_stave"]].join(control_stats, on=["run", "current_family", "depth_stave"])
            frame[f"{method}_control_energy_res68"] = joined["control_energy_res68"].to_numpy(dtype=float)
            frame[f"{method}_control_log_residual"] = joined["control_log_residual"].to_numpy(dtype=float)
            frame["matched_unsat_control_rows"] = joined["matched_unsat_control_rows"].fillna(0).astype(int).to_numpy()
        stress_frames.append(frame)
    stress_frame = pd.concat(stress_frames, ignore_index=True)
    support_stress = support_stress_table(
        stress_frame,
        list(predictions.keys()),
        int(config["bootstrap_reps"]),
        rng_seed + 900,
        float(config["acceptance_margin_res68"]),
        float(config["log_charge_delta_acceptance"]),
    )
    if not support_stress.empty:
        support_stress = support_stress[
            (support_stress["n_saturated"] >= int(config["min_saturated_cell"]))
            & (support_stress["matched_unsat_control_rows"] >= int(config["min_unsaturated_control_cell"]))
        ].reset_index(drop=True)
    ordering_stress = ordering_stress_table(
        stress_frame,
        list(predictions.keys()),
        int(config["bootstrap_reps"]),
        rng_seed + 1100,
        float(config["ordering_margin_frac"]),
    )
    method_geometry_summary = geometry.groupby(["method", "family"], as_index=False).agg(
        worst_geometry_saturated_energy_res68=("saturated_energy_res68", "max"),
        best_geometry_saturated_energy_res68=("saturated_energy_res68", "min"),
    )
    if not ordering_stress.empty:
        order_summary = ordering_stress.groupby("method", as_index=False)["depth_order_violation_rate"].max().rename(
            columns={"depth_order_violation_rate": "max_depth_order_violation_rate"}
        )
        method_geometry_summary = method_geometry_summary.merge(order_summary, on="method", how="left")
    else:
        method_geometry_summary["max_depth_order_violation_rate"] = np.nan
    if not support_stress.empty:
        log_summary = support_stress.assign(abs_log_charge_delta=support_stress["sat_minus_unsat_log_charge_delta"].abs()).groupby(
            "method", as_index=False
        )["abs_log_charge_delta"].max().rename(columns={"abs_log_charge_delta": "max_abs_log_charge_delta"})
        method_geometry_summary = method_geometry_summary.merge(log_summary, on="method", how="left")
    else:
        method_geometry_summary["max_abs_log_charge_delta"] = np.nan
    method_geometry_summary = method_geometry_summary.sort_values("worst_geometry_saturated_energy_res68").reset_index(drop=True)

    print("8/9 leakage checks", flush=True)
    train_keys = set(map(tuple, events.loc[train, ["run", "eventno", "evt"]].to_numpy()))
    held_keys = set(map(tuple, events.loc[held, ["run", "eventno", "evt"]].to_numpy()))
    shuffled_unsat = np.flatnonzero(unsat_held)
    leakage = pd.DataFrame(
        [
            {
                "check": "train_heldout_run_overlap",
                "value": str(sorted(set(events.loc[train, "run"].unique()).intersection(set(events.loc[held, "run"].unique())))),
                "pass": set(events.loc[train, "run"].unique()).isdisjoint(set(events.loc[held, "run"].unique())),
            },
            {"check": "raw_reproduction_exact", "value": f"{total} of {expected}", "pass": total == expected},
            {"check": "train_heldout_event_key_overlap", "value": str(len(train_keys.intersection(held_keys))), "pass": len(train_keys.intersection(held_keys)) == 0},
            {
                "check": "ml_features_exclude_odd_charge_run_event_ids",
                "value": ",".join(feature_names),
                "pass": all(bad not in feature_names for bad in ["odd_total_charge", "run", "eventno", "evt"]),
            },
            {
                "check": "cnn_status",
                "value": cnn_status,
                "pass": cnn_status == "trained",
            },
            {
                "check": "shuffled_p04_unsaturated_charge_res68",
                "value": f"{charge_metrics(odd_charge[shuffled_unsat], shuffled_cal[shuffled_unsat])['res68_frac']:.6f}",
                "pass": bool(charge_metrics(odd_charge[shuffled_unsat], shuffled_cal[shuffled_unsat])["res68_frac"] > 0.10),
            },
        ]
    )

    print("9/9 outputs", flush=True)
    metrics.to_csv(out_dir / "method_metrics.csv", index=False)
    acceptance.to_csv(out_dir / "acceptance_bands.csv", index=False)
    support_stress.to_csv(out_dir / "support_stress_map.csv", index=False)
    ordering_stress.to_csv(out_dir / "ordering_stress.csv", index=False)
    method_geometry_summary.to_csv(out_dir / "method_geometry_summary.csv", index=False)
    by_run.to_csv(out_dir / "per_run_acceptance.csv", index=False)
    geometry.to_csv(out_dir / "geometry_systematics.csv", index=False)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)
    counts.to_csv(out_dir / "counts_by_run.csv", index=False)
    pd.DataFrame(
        [{"quantity": "S14c/S00 selected B-stave pulse records", "expected": expected, "reproduced": total, "delta": total - expected, "pass": total == expected}]
    ).to_csv(out_dir / "reproduction_match_table.csv", index=False)
    input_paths = [s14g.raw_path(config, run) for run in s14g.configured_runs(config)]
    input_sha = pd.DataFrame([{"path": str(path), "bytes": int(path.stat().st_size), "sha256": sha256_file(path)} for path in input_paths])
    input_sha.to_csv(out_dir / "input_sha256.csv", index=False)
    make_figure(out_dir, metrics)

    winner_summary = method_geometry_summary.iloc[0].to_dict()
    winner_row = metrics[metrics["method"].eq(winner_summary["method"])].iloc[0].to_dict()
    trad_worse_geoms = geometry[geometry["traditional_worsens_observed"]]["geometry"].drop_duplicates().tolist()
    accepted_count = int(acceptance["accepted_with_margin"].sum()) if not acceptance.empty else 0
    finding = (
        f"Raw ROOT reproduction passed exactly at {total:,} selected B-stave pulses. "
        f"The geometry-stress winner is {winner_row['method']} with worst-geometry saturated energy-proxy res68 "
        f"{float(winner_summary['worst_geometry_saturated_energy_res68']):.5f}; its nominal center-4cm res68 is "
        f"{float(winner_row['saturated_energy_res68']):.5f} {fmt_ci(winner_row['saturated_energy_res68_ci95'])}. "
        f"The strong traditional rising-edge template has res68 {trad_res:.5f}, observed charge has {obs_res:.5f}, "
        f"so traditional template correction {'worsens' if trad_res > obs_res else 'does not worsen'} the nominal saturated geometry proxy. "
        f"Accepted nominal current/depth/stave bands at margin {float(config['acceptance_margin_res68']):.3f}: {accepted_count}. "
        f"Maximum winner depth-order violation rate is {float(winner_summary.get('max_depth_order_violation_rate', float('nan'))):.3f}; "
        f"maximum absolute winner saturated-minus-unsaturated log-charge delta is {float(winner_summary.get('max_abs_log_charge_delta', float('nan'))):.3f}. "
        f"Traditional-worsening geometries: {trad_worse_geoms}. "
        "The result is an odd-readout closure and range-order proxy; it does not establish absolute deposited-energy truth."
    )
    result = {
        "study": config["study_id"],
        "ticket_id": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "raw_reproduction": {
            "expected_selected_pulses": expected,
            "reproduced_selected_pulses": total,
            "delta": total - expected,
            "pass": total == expected,
        },
        "train_runs": sorted(int(x) for x in events.loc[train, "run"].unique()),
        "heldout_runs": sorted(int(x) for x in events.loc[held, "run"].unique()),
        "n_event_rows_after_valid_charge_cut": int(len(events)),
        "n_saturated_heldout_events": int(saturated.sum()),
        "primary_metric": "minimum worst-geometry held-out saturated event energy-proxy res68, run-bootstrap 95% CIs per geometry",
        "winner": {
            "method": str(winner_row["method"]),
            "family": str(winner_row["family"]),
            "worst_geometry_saturated_energy_res68": float(winner_summary["worst_geometry_saturated_energy_res68"]),
            "best_geometry_saturated_energy_res68": float(winner_summary["best_geometry_saturated_energy_res68"]),
            "max_depth_order_violation_rate": float(winner_summary.get("max_depth_order_violation_rate", np.nan)),
            "max_abs_log_charge_delta": float(winner_summary.get("max_abs_log_charge_delta", np.nan)),
            "saturated_energy_res68": float(winner_row["saturated_energy_res68"]),
            "saturated_energy_res68_ci95": winner_row["saturated_energy_res68_ci95"],
            "saturated_charge_res68": float(winner_row["saturated_charge_res68"]),
            "all_heldout_energy_res68": float(winner_row["all_heldout_energy_res68"]),
        },
        "traditional_template_worsens_observed_nominal": bool(trad_res > obs_res),
        "traditional_worsening_geometries": trad_worse_geoms,
        "accepted_band_count": accepted_count,
        "method_metrics": json.loads(metrics.to_json(orient="records")),
        "method_geometry_summary": json.loads(method_geometry_summary.to_json(orient="records")),
        "support_stress_map_top": json.loads(support_stress.head(80).to_json(orient="records")),
        "ordering_stress": json.loads(ordering_stress.to_json(orient="records")),
        "acceptance_bands": json.loads(acceptance.to_json(orient="records")),
        "leakage_checks": json.loads(leakage.to_json(orient="records")),
        "finding": finding,
        "next_tickets": [
            {
                "title": "S14m: external A-stack geometry validation of S14f saturation stress bands",
                "body": "Use event-matched A-stack charge where topology supports it to test whether S14f geometry-stable saturated B-stack correction bands transfer to an external detector handle. Expected information gain: separates duplicate-readout closure from detector-independent range-energy support before any production saturation correction.",
            }
        ],
        "runtime_sec": round(time.time() - t0, 1),
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    write_report(out_dir, config, result, metrics, acceptance, by_run, geometry, support_stress, ordering_stress, method_geometry_summary, leakage)

    outputs = [
        "REPORT.md",
        "result.json",
        "method_metrics.csv",
        "acceptance_bands.csv",
        "support_stress_map.csv",
        "ordering_stress.csv",
        "method_geometry_summary.csv",
        "per_run_acceptance.csv",
        "geometry_systematics.csv",
        "leakage_checks.csv",
        "counts_by_run.csv",
        "reproduction_match_table.csv",
        "input_sha256.csv",
        "fig_s14f_saturated_res68.png",
    ]
    manifest = {
        "study": config["study_id"],
        "ticket_id": config["ticket_id"],
        "worker": config["worker"],
        "git_commit": git_commit(),
        "command": "/home/billy/anaconda3/bin/python scripts/s14f_1781033587_678_10103f5a_saturation_geometry_stress_map.py --config configs/s14f_1781033587_678_10103f5a_saturation_geometry_stress_map.yaml",
        "config": str(config_path.relative_to(ROOT)),
        "random_seed": int(config["random_seed"]),
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "uproot": getattr(uproot, "__version__", "unknown"),
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "torch": getattr(s14g.torch, "__version__", "unavailable") if s14g.torch is not None else "unavailable",
        },
        "inputs": json.loads(input_sha.to_json(orient="records")),
        "outputs": {},
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    manifest["outputs"] = {name: sha256_file(out_dir / name) for name in outputs if (out_dir / name).exists()}
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"DONE -> {out_dir} in {result['runtime_sec']} s; winner={result['winner']['method']}", flush=True)


if __name__ == "__main__":
    main()
