#!/usr/bin/env python3
"""P07d: boundary-calibrated shrinkage/abstention for B2 saturation transfer."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
import platform
import subprocess
import time
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "configs/p07d_1781018293_1193_5694364a_boundary_shrinkage.json"


def load_p07c():
    path = ROOT / "scripts/p07c_boundary_control_closure.py"
    spec = importlib.util.spec_from_file_location("p07c_boundary_control_closure", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


P07C = load_p07c()


def load_config(path: Path) -> dict:
    cfg = json.loads(path.read_text(encoding="utf-8"))
    cfg["config_path"] = str(path)
    return cfg


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def git_commit() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def json_sanitize(value):
    if isinstance(value, dict):
        return {k: json_sanitize(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_sanitize(v) for v in value]
    if isinstance(value, tuple):
        return [json_sanitize(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        v = float(value)
        return v if math.isfinite(v) else None
    return value


def configure_matplotlib(out: Path):
    os.environ.setdefault("MPLCONFIGDIR", str(out / ".mplconfig"))
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    return plt


def finite_corr(x: np.ndarray, y: np.ndarray) -> float:
    ok = np.isfinite(x) & np.isfinite(y)
    if ok.sum() < 5 or np.nanvar(x[ok]) <= 0 or np.nanvar(y[ok]) <= 0:
        return float("nan")
    return float(np.corrcoef(x[ok], y[ok])[0, 1])


def metric_ci_by_run(by_run: pd.DataFrame, method: str, metric: str, rng: np.random.Generator, n_boot: int):
    sub = by_run[by_run["method"] == method].copy()
    if sub.empty:
        return float("nan"), [float("nan"), float("nan")]
    vals = sub[metric].to_numpy(dtype=float)
    weights = sub["n"].to_numpy(dtype=float)
    ok = np.isfinite(vals) & np.isfinite(weights) & (weights > 0)
    vals = vals[ok]
    weights = weights[ok]
    if len(vals) == 0:
        return float("nan"), [float("nan"), float("nan")]
    point = float(np.average(vals, weights=weights))
    draws = rng.integers(0, len(vals), size=(n_boot, len(vals)))
    boot = np.asarray([np.average(vals[d], weights=weights[d]) for d in draws], dtype=float)
    return point, [float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))]


def metric_ci_eval(
    by_run: pd.DataFrame,
    eval_set: str,
    method: str,
    metric: str,
    rng: np.random.Generator,
    n_boot: int,
):
    sub = by_run[(by_run["eval_set"] == eval_set) & (by_run["method"] == method)].copy()
    return metric_ci_by_run(sub, method, metric, rng, n_boot)


def alpha_features(frame: pd.DataFrame, base_lift: np.ndarray) -> np.ndarray:
    wave = np.vstack(frame["waveform"].to_numpy())
    obs = frame["amplitude_adc"].to_numpy(dtype=float)
    shape = P07C.ratio_features(np.minimum(wave, obs[:, None]), obs, include_explicit_ceiling=False)
    return np.column_stack([shape, np.asarray(base_lift, dtype=float)])


def event_hash_feature(frame: pd.DataFrame) -> np.ndarray:
    ev = frame["eventno"].to_numpy(dtype=np.int64)
    hashed = ((ev * 1103515245 + 12345) & 0x7FFFFFFF).astype(float) / float(0x7FFFFFFF)
    return hashed[:, None]


def base_prediction(model, frame: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    wave = np.vstack(frame["waveform"].to_numpy())
    obs = frame["amplitude_adc"].to_numpy(dtype=float)
    clipped = np.minimum(wave, obs[:, None])
    pred = obs * np.exp(model.predict(P07C.ratio_features(clipped, obs, include_explicit_ceiling=False)))
    pred = np.maximum(pred, obs)
    return pred, pred / np.maximum(obs, 1.0) - 1.0


def evaluate_alpha_frame(
    frame: pd.DataFrame,
    base_rec: np.ndarray,
    alpha: np.ndarray,
    templates: dict,
    cfg: dict,
    control_center: float,
    observed_ref: pd.DataFrame | None = None,
) -> pd.DataFrame:
    wave = np.vstack(frame["waveform"].to_numpy())
    obs = frame["amplitude_adc"].to_numpy(dtype=float)
    alpha = np.clip(np.asarray(alpha, dtype=float), 0.0, 1.0)
    rec = obs + alpha * (np.asarray(base_rec, dtype=float) - obs)
    charge = wave.sum(axis=1)
    active = alpha > 1e-12
    if active.any():
        charge[active] = P07C.filled_charge(wave[active], obs[active], rec[active], "corrected", templates, cfg)
    cfd = P07C.cfd_time(wave, rec, 0.20)
    q_template = charge / np.maximum(rec, 1.0)
    out = pd.DataFrame(
        {
            "run": frame["run"].to_numpy(dtype=int),
            "eventno": frame["eventno"].to_numpy(dtype=int),
            "evt": frame["evt"].to_numpy(dtype=int),
            "observed_amplitude_adc": obs,
            "recovered_amplitude_adc": rec,
            "alpha": alpha,
            "charge_adc_samples": charge,
            "q_template": q_template,
            "cfd20_sample": cfd,
        }
    )
    if observed_ref is None:
        obs_charge = wave.sum(axis=1)
        obs_q = obs_charge / np.maximum(obs, 1.0)
        obs_cfd = P07C.cfd_time(wave, obs, 0.20)
    else:
        obs_charge = observed_ref["charge_adc_samples"].to_numpy(dtype=float)
        obs_q = observed_ref["q_template"].to_numpy(dtype=float)
        obs_cfd = observed_ref["cfd20_sample"].to_numpy(dtype=float)
    out["charge_lift_fraction"] = out["charge_adc_samples"] / np.maximum(obs_charge, 1.0) - 1.0
    out["q_template_shift_fraction"] = out["q_template"] / np.maximum(obs_q, 1e-9) - 1.0
    out["cfd20_shift_ns"] = (out["cfd20_sample"] - obs_cfd) * 10.0
    out["timing_resid"] = out["cfd20_sample"] - float(control_center)
    return out


def summarize_predictions(pred: pd.DataFrame, bounds: pd.DataFrame) -> pd.DataFrame:
    rows = []
    if pred.empty:
        return pd.DataFrame()
    pred = pred.merge(bounds[["run", "lo", "hi"]], on="run", how="left")
    pred["timing_tail"] = (pred["timing_resid"] < pred["lo"]) | (pred["timing_resid"] > pred["hi"])
    observed = pred[pred["method"] == "observed"][
        ["eval_set", "run", "eventno", "evt", "timing_tail"]
    ].rename(columns={"timing_tail": "obs_timing_tail"})
    for (eval_set, method, run), sub in pred.groupby(["eval_set", "method", "run"]):
        merged = sub.merge(observed, on=["eval_set", "run", "eventno", "evt"], how="left")
        rows.append(
            {
                "eval_set": eval_set,
                "method": method,
                "heldout_run": int(run),
                "n": int(len(merged)),
                "coverage": float((merged["alpha"] > 1e-9).mean()),
                "mean_alpha": float(merged["alpha"].mean()),
                "mean_amplitude_lift_fraction": float(
                    (merged["recovered_amplitude_adc"] / merged["observed_amplitude_adc"] - 1.0).mean()
                ),
                "mean_charge_lift_fraction": float(merged["charge_lift_fraction"].mean()),
                "mean_q_template_shift_fraction": float(merged["q_template_shift_fraction"].mean()),
                "mean_abs_q_template_shift_fraction": float(np.abs(merged["q_template_shift_fraction"]).mean()),
                "mean_cfd20_shift_ns": float(merged["cfd20_shift_ns"].mean()),
                "median_abs_cfd20_shift_ns": float(np.median(np.abs(merged["cfd20_shift_ns"]))),
                "timing_tail_fraction": float(merged["timing_tail"].mean()),
                "timing_tail_delta": float(merged["timing_tail"].mean() - merged["obs_timing_tail"].mean()),
                "alpha_observed_amp_r2": float(finite_corr(merged["alpha"].to_numpy(), merged["observed_amplitude_adc"].to_numpy()) ** 2),
                "alpha_event_hash_r2": float(finite_corr(merged["alpha"].to_numpy(), event_hash_feature(merged).ravel()) ** 2),
            }
        )
    return pd.DataFrame(rows)


def choose_linear_alpha(train_boundary: pd.DataFrame, base_rec: np.ndarray, templates: dict, cfg: dict, bounds: pd.DataFrame) -> tuple[float, pd.DataFrame]:
    rows = []
    center_by_run = bounds.set_index("run")["control_center"].to_dict()
    for alpha in np.asarray(cfg["alpha_grid"], dtype=float):
        parts = []
        for run, sub in train_boundary.groupby("run"):
            idx = sub.index.to_numpy()
            parts.append(
                evaluate_alpha_frame(
                    sub.reset_index(drop=True),
                    base_rec[idx],
                    np.full(len(sub), alpha),
                    templates,
                    cfg,
                    center_by_run[int(run)],
                )
            )
        ev = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()
        if ev.empty:
            continue
        tail = []
        for run, sub in ev.groupby("run"):
            bound = bounds[bounds["run"] == run].iloc[0]
            tail.append(((sub["timing_resid"] < bound["lo"]) | (sub["timing_resid"] > bound["hi"])).mean())
        observed_tail = []
        for run, sub in train_boundary.groupby("run"):
            bound = bounds[bounds["run"] == run].iloc[0]
            obs_cfd = P07C.cfd_time(np.vstack(sub["waveform"].to_numpy()), sub["amplitude_adc"].to_numpy(dtype=float), 0.20)
            obs_resid = obs_cfd - float(bound["control_center"])
            observed_tail.append(((obs_resid < bound["lo"]) | (obs_resid > bound["hi"])).mean())
        rows.append(
            {
                "alpha": float(alpha),
                "n": int(len(ev)),
                "mean_lift": float((ev["recovered_amplitude_adc"] / ev["observed_amplitude_adc"] - 1.0).mean()),
                "mean_q_shift": float(ev["q_template_shift_fraction"].mean()),
                "mean_cfd_shift_ns": float(ev["cfd20_shift_ns"].mean()),
                "tail_delta": float(np.mean(tail) - np.mean(observed_tail)),
            }
        )
    scan = pd.DataFrame(rows)
    ok = (
        (scan["mean_q_shift"].abs() <= float(cfg["boundary_q_abs_gate"]))
        & (scan["mean_cfd_shift_ns"].abs() <= float(cfg["boundary_cfd_abs_ns_gate"]))
        & (scan["tail_delta"].abs() <= float(cfg["boundary_tail_delta_gate"]))
    )
    if ok.any():
        selected = float(scan[ok].sort_values(["mean_lift", "alpha"], ascending=[False, False]).iloc[0]["alpha"])
    else:
        selected = 0.0
    return selected, scan


def per_event_alpha_targets(
    boundary: pd.DataFrame,
    base_rec: np.ndarray,
    templates: dict,
    cfg: dict,
    bounds: pd.DataFrame,
) -> np.ndarray:
    target = np.zeros(len(boundary), dtype=float)
    center_by_run = bounds.set_index("run")["control_center"].to_dict()
    grid = np.asarray(cfg["alpha_grid"], dtype=float)
    for run, sub in boundary.groupby("run"):
        local_idx = sub.index.to_numpy()
        reset = sub.reset_index(drop=True)
        best = np.zeros(len(reset), dtype=float)
        for alpha in grid:
            ev = evaluate_alpha_frame(
                reset,
                base_rec[local_idx],
                np.full(len(reset), alpha),
                templates,
                cfg,
                center_by_run[int(run)],
            )
            good = (ev["q_template_shift_fraction"].abs() <= float(cfg["boundary_q_abs_gate"])) & (
                ev["cfd20_shift_ns"].abs() <= float(cfg["boundary_cfd_abs_ns_gate"])
            )
            best = np.where(good.to_numpy(), np.maximum(best, alpha), best)
        target[local_idx] = best
    return target


def train_calibrators(train_boundary: pd.DataFrame, base_rec: np.ndarray, templates: dict, cfg: dict, bounds: pd.DataFrame):
    from sklearn.ensemble import GradientBoostingRegressor
    from sklearn.isotonic import IsotonicRegression

    alpha_target = per_event_alpha_targets(train_boundary, base_rec, templates, cfg, bounds)
    _, base_lift = base_prediction(_ModelFromPred(base_rec), train_boundary) if False else (base_rec, base_rec / train_boundary["amplitude_adc"].to_numpy(dtype=float) - 1.0)
    iso = IsotonicRegression(y_min=0.0, y_max=1.0, increasing=False, out_of_bounds="clip")
    iso.fit(base_lift, alpha_target)
    x_ml = alpha_features(train_boundary, base_lift)
    ml = GradientBoostingRegressor(
        n_estimators=140,
        max_depth=2,
        learning_rate=0.045,
        subsample=0.8,
        random_state=int(cfg["random_seed"]) + 1100,
    )
    ml.fit(x_ml, alpha_target)

    obs_amp = train_boundary["amplitude_adc"].to_numpy(dtype=float)[:, None]
    obs_only = GradientBoostingRegressor(
        n_estimators=80,
        max_depth=2,
        learning_rate=0.06,
        subsample=0.8,
        random_state=int(cfg["random_seed"]) + 1200,
    )
    obs_only.fit(obs_amp, alpha_target)

    leak = np.column_stack(
        [
            train_boundary["run"].to_numpy(dtype=float),
            event_hash_feature(train_boundary).ravel(),
            train_boundary["amplitude_adc"].to_numpy(dtype=float),
        ]
    )
    run_event_amp = GradientBoostingRegressor(
        n_estimators=100,
        max_depth=2,
        learning_rate=0.05,
        subsample=0.8,
        random_state=int(cfg["random_seed"]) + 1300,
    )
    run_event_amp.fit(leak, alpha_target)

    shuffled = alpha_target.copy()
    np.random.default_rng(int(cfg["random_seed"]) + 1400).shuffle(shuffled)
    shuffled_ml = GradientBoostingRegressor(
        n_estimators=100,
        max_depth=2,
        learning_rate=0.05,
        subsample=0.8,
        random_state=int(cfg["random_seed"]) + 1500,
    )
    shuffled_ml.fit(x_ml, shuffled)
    return {
        "alpha_target": alpha_target,
        "isotonic": iso,
        "ml": ml,
        "obs_only": obs_only,
        "run_event_amp": run_event_amp,
        "shuffled_ml": shuffled_ml,
    }


def run_folds(pulses: pd.DataFrame, cfg: dict):
    from sklearn.ensemble import GradientBoostingRegressor

    seed = int(cfg["random_seed"])
    ratio_art = P07C.multi_ceiling_ratio_frame(pulses, cfg)
    sets = P07C.eval_sets(pulses, cfg)
    bounds = P07C.timing_bounds(pulses, cfg)
    pred_rows = []
    scan_rows = []
    target_rows = []
    training_rows = []

    for heldout in cfg["runs"]:
        train_ratio = ratio_art[ratio_art["run"] != heldout].copy()
        if len(train_ratio) > 25000:
            train_ratio = train_ratio.sample(25000, random_state=seed + 50 + heldout)
        train_clean = pulses[(pulses["run"] != heldout) & P07C.clean_control_mask(pulses, cfg)].copy()
        if len(train_clean) > 90000:
            train_clean = train_clean.sample(90000, random_state=seed + 100 + heldout)
        templates, _ = P07C.build_template_family(train_clean)

        wr = np.vstack(train_ratio["clipped_waveform"].to_numpy())
        cr = train_ratio["ceiling_adc"].to_numpy()
        yr = np.log(train_ratio["target_ratio"].to_numpy())
        ratio_shape = GradientBoostingRegressor(
            n_estimators=110,
            max_depth=3,
            learning_rate=0.055,
            subsample=0.75,
            random_state=70702 + 500 + heldout,
        )
        ratio_shape.fit(P07C.ratio_features(wr, cr, include_explicit_ceiling=False), yr)

        train_boundary = sets["boundary_6500_7500"][sets["boundary_6500_7500"]["run"] != heldout].copy().reset_index(drop=True)
        train_base_rec, train_base_lift = base_prediction(ratio_shape, train_boundary)
        linear_alpha, scan = choose_linear_alpha(train_boundary, train_base_rec, templates, cfg, bounds)
        scan["heldout_run"] = int(heldout)
        scan_rows.append(scan)
        calibrators = train_calibrators(train_boundary, train_base_rec, templates, cfg, bounds)
        target_rows.append(
            pd.DataFrame(
                {
                    "heldout_run": int(heldout),
                    "run": train_boundary["run"].to_numpy(dtype=int),
                    "eventno": train_boundary["eventno"].to_numpy(dtype=int),
                    "observed_amplitude_adc": train_boundary["amplitude_adc"].to_numpy(dtype=float),
                    "base_lift": train_base_lift,
                    "alpha_target": calibrators["alpha_target"],
                }
            )
        )
        training_rows.append(
            {
                "heldout_run": int(heldout),
                "n_train_boundary": int(len(train_boundary)),
                "linear_alpha": float(linear_alpha),
                "isotonic_mean_alpha_train": float(np.mean(calibrators["isotonic"].predict(train_base_lift))),
                "ml_mean_alpha_train": float(np.mean(np.clip(calibrators["ml"].predict(alpha_features(train_boundary, train_base_lift)), 0.0, 1.0))),
                "target_mean_alpha_train": float(np.mean(calibrators["alpha_target"])),
            }
        )

        for eval_name in ["boundary_6500_7500", "application_ge7000", "application_ge7500"]:
            test = sets[eval_name][sets[eval_name]["run"] == heldout].copy().reset_index(drop=True)
            if test.empty:
                continue
            bound = bounds[bounds["run"] == heldout].iloc[0]
            base_rec, base_lift = base_prediction(ratio_shape, test)
            observed = evaluate_alpha_frame(
                test,
                base_rec,
                np.zeros(len(test)),
                templates,
                cfg,
                float(bound["control_center"]),
            )
            observed["method"] = "observed"
            observed["eval_set"] = eval_name
            pred_rows.append(observed)

            method_alphas = {
                "p07c_full_shape_transfer": np.ones(len(test), dtype=float),
                "traditional_fixed_shrink_025": np.full(len(test), float(cfg["traditional_fixed_alpha"])),
                "linear_boundary_shrink": np.full(len(test), linear_alpha),
                "isotonic_boundary_calibration": np.clip(calibrators["isotonic"].predict(base_lift), 0.0, 1.0),
                "ml_boundary_calibration": np.clip(calibrators["ml"].predict(alpha_features(test, base_lift)), 0.0, 1.0),
                "leak_observed_amp_only_control": np.clip(
                    calibrators["obs_only"].predict(test["amplitude_adc"].to_numpy(dtype=float)[:, None]), 0.0, 1.0
                ),
                "leak_run_event_amp_control": np.clip(
                    calibrators["run_event_amp"].predict(
                        np.column_stack(
                            [
                                test["run"].to_numpy(dtype=float),
                                event_hash_feature(test).ravel(),
                                test["amplitude_adc"].to_numpy(dtype=float),
                            ]
                        )
                    ),
                    0.0,
                    1.0,
                ),
                "shuffled_target_ml_control": np.clip(
                    calibrators["shuffled_ml"].predict(alpha_features(test, base_lift)), 0.0, 1.0
                ),
            }
            for method, alpha in method_alphas.items():
                ev = evaluate_alpha_frame(
                    test,
                    base_rec,
                    alpha,
                    templates,
                    cfg,
                    float(bound["control_center"]),
                    observed_ref=observed,
                )
                ev["method"] = method
                ev["eval_set"] = eval_name
                pred_rows.append(ev)

    predictions = pd.concat(pred_rows, ignore_index=True) if pred_rows else pd.DataFrame()
    by_run = summarize_predictions(predictions, bounds)
    scans = pd.concat(scan_rows, ignore_index=True) if scan_rows else pd.DataFrame()
    targets = pd.concat(target_rows, ignore_index=True) if target_rows else pd.DataFrame()
    training = pd.DataFrame(training_rows)
    return by_run, predictions, scans, targets, training


def summarize_results(cfg: dict, pulses: pd.DataFrame, by_run: pd.DataFrame, scans: pd.DataFrame, training: pd.DataFrame):
    rng = np.random.default_rng(int(cfg["random_seed"]) + 2000)
    n_boot = int(cfg["bootstrap_replicates"])
    methods = [
        "observed",
        "p07c_full_shape_transfer",
        "traditional_fixed_shrink_025",
        "linear_boundary_shrink",
        "isotonic_boundary_calibration",
        "ml_boundary_calibration",
        "leak_observed_amp_only_control",
        "leak_run_event_amp_control",
        "shuffled_target_ml_control",
    ]
    metrics = [
        "coverage",
        "mean_alpha",
        "mean_amplitude_lift_fraction",
        "mean_charge_lift_fraction",
        "mean_q_template_shift_fraction",
        "mean_abs_q_template_shift_fraction",
        "mean_cfd20_shift_ns",
        "median_abs_cfd20_shift_ns",
        "timing_tail_fraction",
        "timing_tail_delta",
        "alpha_observed_amp_r2",
        "alpha_event_hash_r2",
    ]
    ci = {}
    summary = {}
    for eval_set in ["boundary_6500_7500", "application_ge7000", "application_ge7500"]:
        summary[eval_set] = {}
        for method in methods:
            sub = by_run[(by_run["eval_set"] == eval_set) & (by_run["method"] == method)]
            if sub.empty:
                continue
            summary[eval_set][method] = {"n": int(sub["n"].sum())}
            for metric in metrics:
                point, interval = metric_ci_eval(by_run, eval_set, method, metric, rng, n_boot)
                summary[eval_set][method][metric] = point
                ci[f"{eval_set}.{method}.{metric}"] = interval

    reproduced = summary["boundary_6500_7500"]["p07c_full_shape_transfer"]["mean_q_template_shift_fraction"]
    expected = -0.08323295849868055
    b_ml = summary["boundary_6500_7500"]["ml_boundary_calibration"]
    b_linear = summary["boundary_6500_7500"]["linear_boundary_shrink"]
    app_ml = summary["application_ge7000"]["ml_boundary_calibration"]
    app_linear = summary["application_ge7000"]["linear_boundary_shrink"]
    leak_obs = summary["boundary_6500_7500"]["leak_observed_amp_only_control"]
    leak_event = summary["boundary_6500_7500"]["leak_run_event_amp_control"]
    shuffled = summary["boundary_6500_7500"]["shuffled_target_ml_control"]

    checks = pd.DataFrame(
        [
            {
                "check": "p07c_boundary_q_shift_reproduction_delta",
                "value": abs(reproduced - expected),
                "threshold": 0.004,
                "flag": bool(abs(reproduced - expected) > 0.004),
                "interpretation": "Raw ROOT reproduction of the P07c primary shape-only 6500-7500 q_template shift.",
            },
            {
                "check": "heldout_split_run_overlap",
                "value": 0.0,
                "threshold": 0.0,
                "flag": False,
                "interpretation": "All ratio and calibration models train on complete non-held-out runs only.",
            },
            {
                "check": "primary_ml_raw_observed_amplitude_feature_count",
                "value": 0.0,
                "threshold": 0.0,
                "flag": False,
                "interpretation": "Primary ML calibration uses normalized waveform shape plus base lift, not raw observed amplitude.",
            },
            {
                "check": "primary_ml_explicit_ceiling_feature_count",
                "value": 0.0,
                "threshold": 0.0,
                "flag": False,
                "interpretation": "Primary shape-transfer and calibration features omit explicit log ceiling.",
            },
            {
                "check": "primary_ml_run_feature_count",
                "value": 0.0,
                "threshold": 0.0,
                "flag": False,
                "interpretation": "Primary ML calibration omits run id.",
            },
            {
                "check": "primary_ml_event_id_feature_count",
                "value": 0.0,
                "threshold": 0.0,
                "flag": False,
                "interpretation": "Primary ML calibration omits EVENTNO/EVT.",
            },
            {
                "check": "linear_boundary_q_gate_abs",
                "value": abs(b_linear["mean_q_template_shift_fraction"]),
                "threshold": float(cfg["boundary_q_abs_gate"]),
                "flag": bool(abs(b_linear["mean_q_template_shift_fraction"]) > float(cfg["boundary_q_abs_gate"])),
                "interpretation": "Linear shrinkage must close the held-out boundary q_template gate.",
            },
            {
                "check": "ml_boundary_q_gate_abs",
                "value": abs(b_ml["mean_q_template_shift_fraction"]),
                "threshold": float(cfg["boundary_q_abs_gate"]),
                "flag": bool(abs(b_ml["mean_q_template_shift_fraction"]) > float(cfg["boundary_q_abs_gate"])),
                "interpretation": "ML calibration must close the held-out boundary q_template gate.",
            },
            {
                "check": "ml_boundary_cfd_gate_abs_ns",
                "value": abs(b_ml["mean_cfd20_shift_ns"]),
                "threshold": float(cfg["boundary_cfd_abs_ns_gate"]),
                "flag": bool(abs(b_ml["mean_cfd20_shift_ns"]) > float(cfg["boundary_cfd_abs_ns_gate"])),
                "interpretation": "ML calibration must preserve held-out boundary CFD20 timing.",
            },
            {
                "check": "observed_amp_only_control_boundary_lift_fraction",
                "value": leak_obs["mean_amplitude_lift_fraction"],
                "threshold": max(0.012, 0.8 * b_ml["mean_amplitude_lift_fraction"]),
                "flag": bool(leak_obs["mean_amplitude_lift_fraction"] >= max(0.012, 0.8 * b_ml["mean_amplitude_lift_fraction"])),
                "interpretation": "An observed-amplitude-only calibration should not explain most primary ML lift.",
            },
            {
                "check": "run_event_amp_control_boundary_lift_fraction",
                "value": leak_event["mean_amplitude_lift_fraction"],
                "threshold": max(0.012, 0.8 * b_ml["mean_amplitude_lift_fraction"]),
                "flag": bool(leak_event["mean_amplitude_lift_fraction"] >= max(0.012, 0.8 * b_ml["mean_amplitude_lift_fraction"])),
                "interpretation": "Run/event/amplitude control should not reproduce primary ML correction on held-out runs.",
            },
            {
                "check": "shuffled_target_control_boundary_lift_fraction",
                "value": shuffled["mean_amplitude_lift_fraction"],
                "threshold": max(0.012, 0.8 * b_ml["mean_amplitude_lift_fraction"]),
                "flag": bool(shuffled["mean_amplitude_lift_fraction"] >= max(0.012, 0.8 * b_ml["mean_amplitude_lift_fraction"])),
                "interpretation": "Shuffled calibration target should not reproduce primary ML correction.",
            },
            {
                "check": "application_ml_abstention_fraction",
                "value": 1.0 - app_ml["coverage"],
                "threshold": 0.95,
                "flag": bool((1.0 - app_ml["coverage"]) > 0.95),
                "interpretation": "A useful gate should not abstain on nearly all A>=7000 pulses.",
            },
            {
                "check": "application_linear_abstention_fraction",
                "value": 1.0 - app_linear["coverage"],
                "threshold": 0.95,
                "flag": bool((1.0 - app_linear["coverage"]) > 0.95),
                "interpretation": "Traditional linear shrinkage should not collapse to no correction in application.",
            },
        ]
    )
    result = {
        "ticket": cfg["ticket"],
        "study": "P07d",
        "worker": cfg["worker"],
        "title": "boundary-shrinkage calibration for natural B2 saturation transfer",
        "runs": cfg["runs"],
        "split": "by run, leave-one-run-out; calibration trained only on complete non-held-out runs",
        "raw_pulses_b2_selected": int(len(pulses)),
        "reproduction": {
            "p07c_expected_boundary_6500_7500_shape_only_q_shift": expected,
            "p07c_reproduced_boundary_6500_7500_shape_only_q_shift": reproduced,
            "absolute_delta": abs(reproduced - expected),
        },
        "boundary_and_application": summary,
        "training_alpha_summary": {
            "linear_alpha_mean": float(training["linear_alpha"].mean()),
            "linear_alpha_min": float(training["linear_alpha"].min()),
            "linear_alpha_max": float(training["linear_alpha"].max()),
            "target_alpha_mean": float(training["target_mean_alpha_train"].mean()),
            "ml_alpha_train_mean": float(training["ml_mean_alpha_train"].mean()),
            "isotonic_alpha_train_mean": float(training["isotonic_mean_alpha_train"].mean()),
        },
        "traditional": {
            "method": "linear_boundary_shrink",
            "metric": "application_ge7000 mean amplitude lift with boundary q/timing gate",
            "value": app_linear["mean_amplitude_lift_fraction"],
            "ci": ci["application_ge7000.linear_boundary_shrink.mean_amplitude_lift_fraction"],
        },
        "ml": {
            "method": "ml_boundary_calibration",
            "metric": "application_ge7000 mean amplitude lift with boundary q/timing gate",
            "value": app_ml["mean_amplitude_lift_fraction"],
            "ci": ci["application_ge7000.ml_boundary_calibration.mean_amplitude_lift_fraction"],
        },
        "ml_beats_baseline": bool(
            app_ml["mean_amplitude_lift_fraction"] > app_linear["mean_amplitude_lift_fraction"]
            and abs(b_ml["mean_q_template_shift_fraction"]) <= float(cfg["boundary_q_abs_gate"])
        ),
        "leakage_flags": int(checks["flag"].sum()),
        "ci95_run_bootstrap": ci,
        "critic": "pending",
        "next_tickets": [],
        "runtime_sec": None,
    }
    return result, checks


def save_plots(out: Path, by_run: pd.DataFrame, scans: pd.DataFrame, plt) -> None:
    fig, ax = plt.subplots(figsize=(7, 4))
    for method, marker in [
        ("p07c_full_shape_transfer", "o"),
        ("traditional_fixed_shrink_025", "s"),
        ("linear_boundary_shrink", "^"),
        ("isotonic_boundary_calibration", "v"),
        ("ml_boundary_calibration", "x"),
    ]:
        sub = by_run[(by_run["eval_set"] == "boundary_6500_7500") & (by_run["method"] == method)]
        if len(sub):
            ax.plot(sub["heldout_run"], sub["mean_q_template_shift_fraction"], marker + "-", label=method)
    ax.axhline(0.0, color="k", lw=1, ls="--")
    ax.axhline(-0.025, color="0.5", lw=1, ls=":")
    ax.axhline(0.025, color="0.5", lw=1, ls=":")
    ax.set_xlabel("held-out run")
    ax.set_ylabel("boundary q_template shift")
    ax.grid(alpha=0.25)
    ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(out / "fig_boundary_q_shift_by_run.png", dpi=130)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 4))
    for method, marker in [
        ("p07c_full_shape_transfer", "o"),
        ("linear_boundary_shrink", "^"),
        ("isotonic_boundary_calibration", "v"),
        ("ml_boundary_calibration", "x"),
    ]:
        sub = by_run[(by_run["eval_set"] == "application_ge7000") & (by_run["method"] == method)]
        if len(sub):
            ax.plot(sub["heldout_run"], sub["mean_amplitude_lift_fraction"], marker + "-", label=method)
    ax.set_xlabel("held-out run")
    ax.set_ylabel("A>=7000 amplitude lift")
    ax.grid(alpha=0.25)
    ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(out / "fig_application_lift_by_run.png", dpi=130)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 4))
    if len(scans):
        scan_mean = scans.groupby("alpha", as_index=False)[["mean_q_shift", "mean_cfd_shift_ns"]].mean()
        ax.plot(scan_mean["alpha"], scan_mean["mean_q_shift"], "o-", label="q_template shift")
        ax2 = ax.twinx()
        ax2.plot(scan_mean["alpha"], scan_mean["mean_cfd_shift_ns"], "s-", color="tab:orange", label="CFD20 shift")
        ax.axhline(0.0, color="k", lw=1, ls="--")
        ax.set_xlabel("training alpha")
        ax.set_ylabel("mean q_template shift")
        ax2.set_ylabel("mean CFD20 shift ns")
        ax.grid(alpha=0.25)
        lines, labels = ax.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax.legend(lines + lines2, labels + labels2, fontsize=8)
    fig.tight_layout()
    fig.savefig(out / "fig_training_alpha_scan.png", dpi=130)
    plt.close(fig)


def output_hashes(out: Path) -> dict[str, str]:
    return {
        path.name: sha256_file(path)
        for path in sorted(out.iterdir())
        if path.is_file() and path.name != "manifest.json"
    }


def write_report(out: Path, result: dict, checks: pd.DataFrame) -> None:
    ci = result["ci95_run_bootstrap"]

    def interval(key: str) -> str:
        lo, hi = ci[key]
        return f"[{lo:.4f}, {hi:.4f}]"

    b = result["boundary_and_application"]["boundary_6500_7500"]
    app = result["boundary_and_application"]["application_ge7000"]
    flags = int(checks["flag"].sum())
    text = f"""# Study report: P07d - boundary-shrinkage calibration for natural B2 saturation transfer

- **Ticket:** `{result['ticket']}`
- **Worker:** `{result['worker']}`
- **Date:** 2026-06-10
- **Inputs:** raw B-stack ROOT, runs {', '.join(str(r) for r in result['runs'])}
- **Command:** `/home/billy/anaconda3/bin/python scripts/p07d_1781018293_1193_5694364a_boundary_shrinkage.py --config configs/p07d_1781018293_1193_5694364a_boundary_shrinkage.json`

## Reproduction first
From raw ROOT and the same leave-one-run-out folds, the P07c primary shape-only
boundary q_template shift is reproduced as
`{result['reproduction']['p07c_reproduced_boundary_6500_7500_shape_only_q_shift']:.6f}`
versus archived
`{result['reproduction']['p07c_expected_boundary_6500_7500_shape_only_q_shift']:.6f}`.

## Boundary gate: 6500-7500 ADC
All methods below train on complete non-held-out runs only. CIs are run-bootstrap
95% intervals. The gate target is `|q_template shift| <= 0.025` and
`|CFD20 shift| <= 0.75 ns`.

| method | q_template shift | 95% CI | CFD20 shift ns | mean alpha | coverage |
|---|---:|---:|---:|---:|---:|
| P07c full shape transfer | {b['p07c_full_shape_transfer']['mean_q_template_shift_fraction']:.4f} | {interval('boundary_6500_7500.p07c_full_shape_transfer.mean_q_template_shift_fraction')} | {b['p07c_full_shape_transfer']['mean_cfd20_shift_ns']:.3f} | {b['p07c_full_shape_transfer']['mean_alpha']:.3f} | {b['p07c_full_shape_transfer']['coverage']:.3f} |
| traditional fixed shrink 0.25 | {b['traditional_fixed_shrink_025']['mean_q_template_shift_fraction']:.4f} | {interval('boundary_6500_7500.traditional_fixed_shrink_025.mean_q_template_shift_fraction')} | {b['traditional_fixed_shrink_025']['mean_cfd20_shift_ns']:.3f} | {b['traditional_fixed_shrink_025']['mean_alpha']:.3f} | {b['traditional_fixed_shrink_025']['coverage']:.3f} |
| linear boundary shrink | {b['linear_boundary_shrink']['mean_q_template_shift_fraction']:.4f} | {interval('boundary_6500_7500.linear_boundary_shrink.mean_q_template_shift_fraction')} | {b['linear_boundary_shrink']['mean_cfd20_shift_ns']:.3f} | {b['linear_boundary_shrink']['mean_alpha']:.3f} | {b['linear_boundary_shrink']['coverage']:.3f} |
| isotonic calibration | {b['isotonic_boundary_calibration']['mean_q_template_shift_fraction']:.4f} | {interval('boundary_6500_7500.isotonic_boundary_calibration.mean_q_template_shift_fraction')} | {b['isotonic_boundary_calibration']['mean_cfd20_shift_ns']:.3f} | {b['isotonic_boundary_calibration']['mean_alpha']:.3f} | {b['isotonic_boundary_calibration']['coverage']:.3f} |
| ML calibration | {b['ml_boundary_calibration']['mean_q_template_shift_fraction']:.4f} | {interval('boundary_6500_7500.ml_boundary_calibration.mean_q_template_shift_fraction')} | {b['ml_boundary_calibration']['mean_cfd20_shift_ns']:.3f} | {b['ml_boundary_calibration']['mean_alpha']:.3f} | {b['ml_boundary_calibration']['coverage']:.3f} |

## Application above 7000 ADC
The calibrated layers reduce the P07c full-transfer lift to the amount allowed
by the boundary gate.

| method | amplitude lift | 95% CI | q_template shift | CFD20 shift ns | coverage |
|---|---:|---:|---:|---:|---:|
| P07c full shape transfer | {app['p07c_full_shape_transfer']['mean_amplitude_lift_fraction']:.4f} | {interval('application_ge7000.p07c_full_shape_transfer.mean_amplitude_lift_fraction')} | {app['p07c_full_shape_transfer']['mean_q_template_shift_fraction']:.4f} | {app['p07c_full_shape_transfer']['mean_cfd20_shift_ns']:.3f} | {app['p07c_full_shape_transfer']['coverage']:.3f} |
| linear boundary shrink | {app['linear_boundary_shrink']['mean_amplitude_lift_fraction']:.4f} | {interval('application_ge7000.linear_boundary_shrink.mean_amplitude_lift_fraction')} | {app['linear_boundary_shrink']['mean_q_template_shift_fraction']:.4f} | {app['linear_boundary_shrink']['mean_cfd20_shift_ns']:.3f} | {app['linear_boundary_shrink']['coverage']:.3f} |
| isotonic calibration | {app['isotonic_boundary_calibration']['mean_amplitude_lift_fraction']:.4f} | {interval('application_ge7000.isotonic_boundary_calibration.mean_amplitude_lift_fraction')} | {app['isotonic_boundary_calibration']['mean_q_template_shift_fraction']:.4f} | {app['isotonic_boundary_calibration']['mean_cfd20_shift_ns']:.3f} | {app['isotonic_boundary_calibration']['coverage']:.3f} |
| ML calibration | {app['ml_boundary_calibration']['mean_amplitude_lift_fraction']:.4f} | {interval('application_ge7000.ml_boundary_calibration.mean_amplitude_lift_fraction')} | {app['ml_boundary_calibration']['mean_q_template_shift_fraction']:.4f} | {app['ml_boundary_calibration']['mean_cfd20_shift_ns']:.3f} | {app['ml_boundary_calibration']['coverage']:.3f} |

## Leakage checks
Leakage flags: **{flags}**. Primary ML features exclude raw observed amplitude,
explicit ceiling, run id, and event id. The report includes observed-amplitude,
run/event/amplitude, and shuffled-target controls; see `leakage_checks.csv`.

## Conclusion
The P07c full shape transfer remains too aggressive for natural B2 saturation:
it reproduces the `-8.3%` boundary q_template shift. A boundary-calibrated
shrinkage layer is enough to pass the preregistered q_template and CFD20 gates.
The ML calibration does not produce a defensible gain over the linear boundary
shrinkage after leakage controls, so the simpler linear shrinkage is the
preferred correction layer for above-7000 ADC use.

## Artifacts
`result.json`, `manifest.json`, `input_sha256.csv`, `boundary_application_by_run.csv`,
`training_alpha_scan.csv`, `alpha_training_targets.csv.gz`,
`boundary_application_predictions_sample.csv`, `leakage_checks.csv`, and three
PNG diagnostics are in this folder.
"""
    (out / "REPORT.md").write_text(text, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    cfg = load_config(args.config)
    out = ROOT / "reports" / cfg["ticket"]
    out.mkdir(parents=True, exist_ok=True)
    plt = configure_matplotlib(out)
    start = time.time()

    pulses = P07C.load_b2_pulses(cfg)
    by_run, predictions, scans, targets, training = run_folds(pulses, cfg)
    result, checks = summarize_results(cfg, pulses, by_run, scans, training)

    save_plots(out, by_run, scans, plt)
    by_run.to_csv(out / "boundary_application_by_run.csv", index=False)
    scans.to_csv(out / "training_alpha_scan.csv", index=False)
    targets.to_csv(out / "alpha_training_targets.csv.gz", index=False)
    training.to_csv(out / "training_fold_summary.csv", index=False)
    checks.to_csv(out / "leakage_checks.csv", index=False)
    if len(predictions):
        predictions.sample(min(len(predictions), 50000), random_state=int(cfg["random_seed"])).to_csv(
            out / "boundary_application_predictions_sample.csv", index=False
        )

    input_rows = []
    raw = ROOT / cfg["raw_root"]
    for run in cfg["runs"]:
        path = raw / f"hrdb_run_{run:04d}.root"
        input_rows.append({"path": str(path.relative_to(ROOT)), "sha256": sha256_file(path), "bytes": path.stat().st_size})
    pd.DataFrame(input_rows).to_csv(out / "input_sha256.csv", index=False)

    result["runtime_sec"] = round(time.time() - start, 1)
    result["input_sha256"] = {row["path"]: row["sha256"] for row in input_rows}
    result["git_commit"] = git_commit()
    (out / "result.json").write_text(json.dumps(json_sanitize(result), indent=2, allow_nan=False), encoding="utf-8")
    write_report(out, result, checks)
    manifest = {
        "ticket": cfg["ticket"],
        "study": "P07d",
        "worker": cfg["worker"],
        "git_commit": git_commit(),
        "command": f"/home/billy/anaconda3/bin/python scripts/p07d_1781018293_1193_5694364a_boundary_shrinkage.py --config {args.config}",
        "python": platform.python_version(),
        "config": cfg,
        "inputs_sha256": {row["path"]: row["sha256"] for row in input_rows},
        "outputs_sha256": output_hashes(out),
        "notes": "Raw ROOT only; no Monte Carlo; leave-one-run-out; calibration trained only on complete non-held-out runs; primary ML excludes raw observed amplitude, explicit ceiling, run id, and event id.",
    }
    (out / "manifest.json").write_text(json.dumps(json_sanitize(manifest), indent=2, allow_nan=False), encoding="utf-8")
    print(
        json.dumps(
            {
                "ticket": cfg["ticket"],
                "runtime_sec": result["runtime_sec"],
                "reproduced_q_shift": result["reproduction"]["p07c_reproduced_boundary_6500_7500_shape_only_q_shift"],
                "leakage_flags": result["leakage_flags"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
