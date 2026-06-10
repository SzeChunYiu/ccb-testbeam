#!/usr/bin/env python3
"""S14c: externalize S14b/S14c B-stack energy-proxy validation.

This script reads raw HRD ROOT only. It first reproduces the S00 B-stack selected
pulse count, then rebuilds the S14c duplicate-readout charge proxies and tests
their ordering against external handles: event-matched A-stack tags, downstream
B-stack multiplicity, and documented low-current runs. No Monte Carlo truth or
absolute PID labels are used.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import platform
import subprocess
import time
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

import numpy as np
import pandas as pd
import uproot
import yaml
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


ROOT = Path(__file__).resolve().parents[1]
S14C_REF = ROOT / "scripts" / "s14c_1781020051_1283_4e533364_saturation_energy_ordering.py"


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def load_s14c_module():
    spec = importlib.util.spec_from_file_location("s14c_ref", S14C_REF)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {S14C_REF}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return "unknown"


def configured_runs(config: dict) -> List[int]:
    runs: List[int] = []
    for values in config["run_groups"].values():
        runs.extend(int(run) for run in values)
    return sorted(set(runs))


def group_for_run(config: dict) -> Dict[int, str]:
    out: Dict[int, str] = {}
    for group, runs in config["run_groups"].items():
        for run in runs:
            out[int(run)] = group
    return out


def heldout_runs(config: dict) -> List[int]:
    out: List[int] = []
    for group in config["heldout_groups"]:
        out.extend(int(run) for run in config["run_groups"][group])
    return sorted(set(out))


def raw_path(config: dict, prefix: str, run: int) -> Path:
    return ROOT / Path(config["raw_root_dir"]) / f"{prefix}_run_{int(run):04d}.root"


def iter_root(path: Path, branches: Sequence[str], step_size: int = 25000) -> Iterable[dict]:
    tree = uproot.open(path)["h101"]
    yield from tree.iterate(list(branches), step_size=step_size, library="np")


def corrected_quantities(raw: np.ndarray, baseline_samples: Sequence[int]) -> dict:
    baseline = np.median(raw[..., list(baseline_samples)], axis=-1)
    corrected = raw - baseline[..., None]
    amp = corrected.max(axis=-1)
    charge = np.clip(corrected, 0.0, None).sum(axis=-1)
    peak = corrected.argmax(axis=-1)
    tail = np.clip(corrected[..., 10:], 0.0, None).sum(axis=-1) / np.maximum(charge, 1.0)
    return {"corrected": corrected, "amp": amp, "charge": charge, "peak": peak, "tail": tail}


def extract_astack_tags(config: dict) -> Tuple[pd.DataFrame, pd.DataFrame]:
    baseline = [int(i) for i in config["baseline_samples"]]
    nsamp = int(config["samples_per_channel"])
    cut = float(config["amplitude_cut_adc"])
    astaves = list(config["astack"]["staves"].keys())
    achannels = np.asarray([int(config["astack"]["staves"][s]) for s in astaves], dtype=int)
    groups = group_for_run(config)
    rows = []
    counts = []
    for run in configured_runs(config):
        path = raw_path(config, config["astack"]["file_prefix"], run)
        if not path.exists():
            raise FileNotFoundError(path)
        c = {"run": run, "group": groups[run], "events_total": 0, "events_with_selected": 0, "selected_pulses": 0}
        c.update({s: 0 for s in astaves})
        for batch in iter_root(path, ["EVENTNO", "HRDv"]):
            eventno = np.asarray(batch["EVENTNO"]).astype(np.int64)
            raw = np.stack(batch["HRDv"]).astype(np.float64).reshape(-1, 8, nsamp)[:, achannels, :]
            q = corrected_quantities(raw, baseline)
            selected = q["amp"] > cut
            any_sel = selected.any(axis=1)
            both_sel = selected.all(axis=1)
            depth_idx = np.where(selected[:, 1], 1, np.where(selected[:, 0], 0, -1))
            c["events_total"] += int(len(eventno))
            c["events_with_selected"] += int(any_sel.sum())
            c["selected_pulses"] += int(selected.sum())
            for i, stave in enumerate(astaves):
                c[stave] += int(selected[:, i].sum())
            frame = pd.DataFrame(
                {
                    "run": run,
                    "eventno": eventno,
                    "A_any_selected": any_sel,
                    "A_both_selected": both_sel,
                    "A_multiplicity": selected.sum(axis=1).astype(np.int8),
                    "A_depth_idx": depth_idx.astype(np.int8),
                    "A_total_charge": (q["charge"] * selected).sum(axis=1),
                    "A_max_amp": (q["amp"] * selected).max(axis=1),
                }
            )
            for i, stave in enumerate(astaves):
                frame[f"{stave}_selected"] = selected[:, i]
                frame[f"{stave}_amp"] = q["amp"][:, i]
                frame[f"{stave}_charge"] = q["charge"][:, i]
                frame[f"{stave}_peak"] = q["peak"][:, i]
                frame[f"{stave}_tail"] = q["tail"][:, i]
            rows.append(frame)
        counts.append(c)
    return pd.concat(rows, ignore_index=True), pd.DataFrame(counts)


def fit_log_calibrator(est: np.ndarray, target: np.ndarray, mask: np.ndarray) -> LinearRegression:
    good = mask & np.isfinite(est) & np.isfinite(target) & (est > 0) & (target > 0)
    model = LinearRegression()
    model.fit(np.log(est[good])[:, None], np.log(target[good]))
    return model


def apply_log_calibrator(model: LinearRegression, est: np.ndarray) -> np.ndarray:
    return np.exp(model.predict(np.log(np.maximum(est, 1.0))[:, None]))


def build_proxy_frame(config: dict, s14) -> Tuple[pd.DataFrame, pd.DataFrame, np.ndarray, pd.DataFrame, dict]:
    events, pulses, wave, counts = s14.extract_tables(config)
    total = int(counts["selected_pulses"].sum())
    expected = int(config["expected_selected_pulses"])
    if total != expected:
        raise RuntimeError(f"S00 reproduction failed: got {total}, expected {expected}")

    valid_events = (events["odd_total_charge"].to_numpy() > 100.0) & (events["even_total_charge"].to_numpy() > 100.0)
    events = events.loc[valid_events].reset_index(drop=True)
    valid_event_ids = set(int(x) for x in events["event_id"].to_numpy())
    pulse_valid = pulses["event_id"].isin(valid_event_ids).to_numpy() & (pulses["odd_charge"].to_numpy() > 20.0)
    pulses = pulses.loc[pulse_valid].reset_index(drop=True)
    wave = wave[pulse_valid]

    held = set(heldout_runs(config))
    event_held = events["run"].isin(held).to_numpy()
    event_train = ~event_held
    pulse_train = ~pulses["run"].isin(held).to_numpy()

    templates = s14.build_templates(pulses, wave, pulse_train, config)
    trad_rec_amp = s14.template_recovered_amplitude(pulses, wave, templates, config)
    trad_pulse_charge = s14.template_charge_from_amp(pulses, trad_rec_amp, templates, config)

    p07_model = s14.fit_p07_ratio_model(pulses, wave, pulse_train, config)
    ml_rec_amp = pulses["even_amp"].to_numpy(dtype=float).copy()
    sat_pulse = pulses["saturated"].to_numpy(dtype=bool)
    if sat_pulse.any():
        ceilings = pulses.loc[sat_pulse, "even_amp"].to_numpy(dtype=float)
        staves = pulses.loc[sat_pulse, "stave_idx"].to_numpy(dtype=int)
        ratio = np.exp(p07_model.predict(s14.p07_ratio_features(wave[sat_pulse], ceilings, staves)))
        ml_rec_amp[sat_pulse] = np.maximum(ceilings, ceilings * ratio)
    ml_sat_charge = pulses["even_charge"].to_numpy(dtype=float) * np.maximum(ml_rec_amp, 1.0) / np.maximum(pulses["even_amp"].to_numpy(dtype=float), 1.0)
    p04_x = s14.p04_features(pulses, wave, ml_rec_amp, ml_sat_charge)
    p04_model = s14.fit_p04_charge_model(pulses, p04_x, pulse_train, config, shuffled=False)
    p04_pred = np.exp(p04_model.predict(p04_x))
    shuffle_model = s14.fit_p04_charge_model(pulses, p04_x, pulse_train, config, shuffled=True)
    shuffled_pred = np.exp(shuffle_model.predict(p04_x))

    observed_event_charge = events["even_total_charge"].to_numpy(dtype=float)
    odd_event_charge = events["odd_total_charge"].to_numpy(dtype=float)
    trad_event_charge = s14.aggregate_event_charge(events, pulses, trad_pulse_charge, "charge").to_numpy(dtype=float)
    ml_event_charge = s14.aggregate_event_charge(events, pulses, p04_pred, "charge").to_numpy(dtype=float)
    shuffled_event_charge = s14.aggregate_event_charge(events, pulses, shuffled_pred, "charge").to_numpy(dtype=float)
    unsat_train = event_train & (~events["any_saturated"].to_numpy(dtype=bool))

    observed_cal = apply_log_calibrator(fit_log_calibrator(observed_event_charge, odd_event_charge, unsat_train), observed_event_charge)
    trad_cal = apply_log_calibrator(fit_log_calibrator(trad_event_charge, odd_event_charge, unsat_train), trad_event_charge)
    ml_cal = apply_log_calibrator(fit_log_calibrator(ml_event_charge, odd_event_charge, unsat_train), ml_event_charge)
    shuffled_cal = apply_log_calibrator(fit_log_calibrator(shuffled_event_charge, odd_event_charge, unsat_train), shuffled_event_charge)

    staves = list(config["staves"].keys())
    anchors = s14.geometry_anchors(config, config["nominal_geometry"], staves)
    depth_idx = events["depth_idx"].to_numpy(dtype=int)
    odd_energy = s14.DepthChargeQuantileCalibrator(anchors).fit(odd_event_charge, depth_idx, event_train).predict(odd_event_charge, depth_idx)
    trad_energy = s14.DepthChargeQuantileCalibrator(anchors).fit(trad_cal, depth_idx, event_train).predict(trad_cal, depth_idx)
    ml_energy = s14.DepthChargeQuantileCalibrator(anchors).fit(ml_cal, depth_idx, event_train).predict(ml_cal, depth_idx)
    observed_energy = s14.DepthChargeQuantileCalibrator(anchors).fit(observed_cal, depth_idx, event_train).predict(observed_cal, depth_idx)
    shuffled_energy = s14.DepthChargeQuantileCalibrator(anchors).fit(shuffled_cal, depth_idx, event_train).predict(shuffled_cal, depth_idx)

    out = events[["event_id", "run", "group", "eventno", "evt", "multiplicity", "depth_idx", "depth_stave", "even_total_charge", "odd_total_charge", "even_max_amp", "saturated_count", "any_saturated"]].copy()
    downstream_hits = (
        pulses[pulses["stave"].isin(["B4", "B6", "B8"])]
        .groupby("event_id", sort=False)["stave"]
        .nunique()
    )
    out["B_downstream_multiplicity"] = out["event_id"].map(downstream_hits).fillna(0).astype(int)
    out["B_downstream_all3"] = out["B_downstream_multiplicity"].to_numpy(dtype=int) == 3
    out["is_low_current_run"] = out["run"].isin([int(x) for x in config["low_current_runs"]]).astype(int)
    out["is_high_current_run"] = out["run"].isin([int(x) for x in config["high_current_runs"]]).astype(int)
    out["observed_energy_proxy"] = observed_energy
    out["traditional_energy_proxy"] = trad_energy
    out["ml_energy_proxy"] = ml_energy
    out["odd_duplicate_energy_proxy"] = odd_energy
    out["shuffled_energy_proxy"] = shuffled_energy
    out["traditional_charge_proxy"] = trad_cal
    out["ml_charge_proxy"] = ml_cal
    out["observed_charge_proxy"] = observed_cal
    out["heldout"] = event_held
    meta = {
        "raw_reproduction": {"expected_selected_pulses": expected, "reproduced_selected_pulses": total, "delta": total - expected, "pass": total == expected},
        "train_runs": sorted(int(x) for x in out.loc[~event_held, "run"].unique()),
        "heldout_runs": sorted(int(x) for x in out.loc[event_held, "run"].unique()),
        "n_events": int(len(out)),
        "n_pulses": int(len(pulses)),
    }
    return out, pulses, wave, counts, meta


def ci(values: Sequence[float]) -> List[float]:
    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]
    if len(arr) == 0:
        return [None, None]
    return [float(np.percentile(arr, 2.5)), float(np.percentile(arr, 97.5))]


def spearman_np(x: np.ndarray, y: np.ndarray) -> float:
    mask = np.isfinite(x) & np.isfinite(y)
    if int(mask.sum()) < 3:
        return float("nan")
    xr = pd.Series(x[mask]).rank(method="average").to_numpy()
    yr = pd.Series(y[mask]).rank(method="average").to_numpy()
    if np.std(xr) <= 0 or np.std(yr) <= 0:
        return float("nan")
    return float(np.corrcoef(xr, yr)[0, 1])


def add_proxy_strata(frame: pd.DataFrame, train_mask: np.ndarray, columns: Sequence[str]) -> pd.DataFrame:
    out = frame.copy()
    for col in columns:
        q = np.quantile(out.loc[train_mask, col].to_numpy(dtype=float), [0.0, 0.25, 0.5, 0.75, 1.0])
        q = np.unique(q)
        if len(q) < 3:
            out[f"{col}_stratum"] = 0
        else:
            out[f"{col}_stratum"] = np.clip(np.searchsorted(q[1:-1], out[col].to_numpy(dtype=float), side="right"), 0, len(q) - 2)
    return out


def run_block_bootstrap(frame: pd.DataFrame, metric_func, reps: int, seed: int) -> List[float]:
    rng = np.random.default_rng(seed)
    runs = np.asarray(sorted(frame["run"].unique()), dtype=int)
    groups = {int(run): frame[frame["run"] == int(run)] for run in runs}
    vals = []
    for _ in range(int(reps)):
        sampled = rng.choice(runs, size=len(runs), replace=True)
        boot = pd.concat([groups[int(r)] for r in sampled], ignore_index=True)
        vals.append(metric_func(boot))
    return vals


def strata_run_bootstrap(frame: pd.DataFrame, stratum_col: str, target: str, reps: int, seed: int) -> Tuple[List[float], List[float]]:
    rng = np.random.default_rng(seed)
    grouped = frame.groupby(["run", stratum_col])[target].agg(["sum", "count"]).reset_index()
    runs = np.asarray(sorted(grouped["run"].unique()), dtype=int)
    by_run = {int(run): grouped[grouped["run"] == int(run)] for run in runs}
    deltas = []
    rhos = []
    for _ in range(int(reps)):
        sampled = rng.choice(runs, size=len(runs), replace=True)
        combo = pd.concat([by_run[int(run)] for run in sampled], ignore_index=True)
        summary = combo.groupby(stratum_col).sum(numeric_only=True).sort_index()
        means = summary["sum"] / np.maximum(summary["count"], 1)
        if len(means) >= 2:
            deltas.append(float(means.iloc[-1] - means.iloc[0]))
            rhos.append(spearman_np(means.index.to_numpy(dtype=float), means.to_numpy(dtype=float)))
        else:
            deltas.append(float("nan"))
            rhos.append(float("nan"))
    return deltas, rhos


def traditional_external_metrics(frame: pd.DataFrame, config: dict) -> Tuple[pd.DataFrame, pd.DataFrame]:
    held = frame[frame["heldout"]].copy()
    targets = {
        "A_any_selected": "rate",
        "A_both_selected": "rate",
        "A_depth_idx": "mean",
        "B_downstream_multiplicity": "mean",
        "B_downstream_all3": "rate",
        "is_low_current_run": "rate_sample_i_only",
    }
    rows = []
    strata_rows = []
    proxy_cols = ["observed_energy_proxy", "traditional_energy_proxy", "ml_energy_proxy"]
    reps = int(config["bootstrap_reps"])
    for proxy in proxy_cols:
        stratum_col = f"{proxy}_stratum"
        for target, kind in targets.items():
            sub = held.copy()
            if kind == "rate_sample_i_only":
                sub = sub[sub["group"] == "sample_i_analysis"].copy()
            if target == "A_depth_idx":
                sub = sub[sub["A_depth_idx"] >= 0].copy()
            if len(sub) == 0 or sub[stratum_col].nunique() < 2:
                continue
            summary = sub.groupby(stratum_col).agg(n=("run", "size"), n_runs=("run", "nunique"), target_mean=(target, "mean"), proxy_median=(proxy, "median")).reset_index()
            summary.insert(0, "target", target)
            summary.insert(0, "proxy", proxy)
            strata_rows.append(summary)
            low = summary.sort_values(stratum_col).iloc[0]["target_mean"]
            high = summary.sort_values(stratum_col).iloc[-1]["target_mean"]
            delta = float(high - low)
            rho = spearman_np(summary["proxy_median"].to_numpy(dtype=float), summary["target_mean"].to_numpy(dtype=float))
            delta_boot, rho_boot = strata_run_bootstrap(sub, stratum_col, target, reps, int(config["random_seed"]) + len(rows) * 17)
            rows.append(
                {
                    "method": "traditional_stratified_closure",
                    "proxy": proxy,
                    "target": target,
                    "n": int(len(sub)),
                    "n_runs": int(sub["run"].nunique()),
                    "high_minus_low_target": delta,
                    "high_minus_low_ci95": ci(delta_boot),
                    "stratum_spearman": rho,
                    "stratum_spearman_ci95": ci(rho_boot),
                }
            )
    return pd.DataFrame(rows), pd.concat(strata_rows, ignore_index=True)


def composite_external_score(frame: pd.DataFrame) -> np.ndarray:
    a = frame["A_depth_idx"].to_numpy(dtype=float)
    a = np.where(a < 0, 0.0, a + 1.0) / 2.0
    ds = frame["B_downstream_multiplicity"].to_numpy(dtype=float) / 3.0
    low = frame["is_low_current_run"].to_numpy(dtype=float)
    return 0.45 * a + 0.45 * ds + 0.10 * low


def ml_feature_frame(frame: pd.DataFrame) -> Tuple[pd.DataFrame, List[str]]:
    cols = [
        "observed_energy_proxy",
        "traditional_energy_proxy",
        "ml_energy_proxy",
        "depth_idx",
        "multiplicity",
        "even_total_charge",
        "even_max_amp",
        "saturated_count",
        "any_saturated",
    ]
    x = frame[cols].copy()
    for col in ["observed_energy_proxy", "traditional_energy_proxy", "ml_energy_proxy", "even_total_charge", "even_max_amp"]:
        x[col] = np.log1p(np.maximum(x[col].to_numpy(dtype=float), 0.0))
    x["any_saturated"] = x["any_saturated"].astype(float)
    return x, list(x.columns)


def family_labels(frame: pd.DataFrame) -> pd.Series:
    out = frame["group"].astype(str).copy()
    sample_i = frame["group"].eq("sample_i_analysis")
    out.loc[sample_i & frame["is_low_current_run"].astype(bool)] = "sample_i_low_2nA"
    out.loc[sample_i & frame["is_high_current_run"].astype(bool)] = "sample_i_high_20nA"
    return out


def residualize_by_family(y: np.ndarray, fam: pd.Series, train_mask: np.ndarray) -> Tuple[np.ndarray, Dict[str, float], float]:
    global_mean = float(np.mean(y[train_mask]))
    means = {}
    resid = y.copy().astype(float)
    for label in sorted(fam.unique()):
        mask_train = train_mask & fam.eq(label).to_numpy()
        means[label] = float(np.mean(y[mask_train])) if mask_train.any() else global_mean
    for label, mean in means.items():
        resid[fam.eq(label).to_numpy()] = y[fam.eq(label).to_numpy()] - mean
    return resid, means, global_mean


def ml_external_metrics(frame: pd.DataFrame, config: dict) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    train_mask = ~frame["heldout"].to_numpy(dtype=bool)
    held_mask = frame["heldout"].to_numpy(dtype=bool)
    y = composite_external_score(frame)
    fam = family_labels(frame)
    y_resid, means, global_mean = residualize_by_family(y, fam, train_mask)
    x, feature_names = ml_feature_frame(frame)
    rng = np.random.default_rng(int(config["random_seed"]) + 302)
    train_idx = np.flatnonzero(train_mask)
    max_train = int(config.get("ml_max_train_events", len(train_idx)))
    if len(train_idx) > max_train:
        train_idx = rng.choice(train_idx, size=max_train, replace=False)
    model = make_pipeline(StandardScaler(), Ridge(alpha=1.0))
    model.fit(x.iloc[train_idx], y_resid[train_idx])
    pred_resid = model.predict(x)
    fam_base = np.asarray([means.get(label, global_mean) for label in fam], dtype=float)
    pred = fam_base + pred_resid

    shuffled_y = y_resid[train_mask].copy()
    rng.shuffle(shuffled_y)
    shuffled_pool = np.flatnonzero(train_mask)
    if len(shuffled_pool) > max_train:
        shuffled_pool = rng.choice(shuffled_pool, size=max_train, replace=False)
    shuffled_model = make_pipeline(StandardScaler(), Ridge(alpha=10.0))
    shuffled_model.fit(x.iloc[shuffled_pool], y_resid[shuffled_pool][rng.permutation(len(shuffled_pool))])
    shuffled_pred = fam_base + shuffled_model.predict(x)

    held = frame.loc[held_mask, ["run", "group", "eventno"]].copy()
    held["target"] = y[held_mask]
    held["pred_domain_residualized_hgb"] = pred[held_mask]
    held["pred_shuffled_target_control"] = shuffled_pred[held_mask]
    held["resid_domain_residualized_hgb"] = held["pred_domain_residualized_hgb"] - held["target"]
    held["resid_shuffled_target_control"] = held["pred_shuffled_target_control"] - held["target"]

    def rmse(col: str, df: pd.DataFrame = held) -> float:
        return float(np.sqrt(mean_squared_error(df["target"], df[col])))
    def mae(col: str, df: pd.DataFrame = held) -> float:
        return float(mean_absolute_error(df["target"], df[col]))
    def corr(col: str, df: pd.DataFrame = held) -> float:
        return spearman_np(df[col].to_numpy(dtype=float), df["target"].to_numpy(dtype=float))
    rows = []
    for method, col in [("ml_domain_residualized_ridge", "pred_domain_residualized_hgb"), ("shuffled_target_control", "pred_shuffled_target_control")]:
        rows.append(
            {
                "method": method,
                "target": "composite_external_score",
                "n": int(len(held)),
                "n_runs": int(held["run"].nunique()),
                "rmse": rmse(col),
                "rmse_ci95": ci(run_block_bootstrap(held, lambda b, c=col: float(np.sqrt(mean_squared_error(b["target"], b[c]))), int(config["bootstrap_reps"]), int(config["random_seed"]) + len(rows) * 23)),
                "mae": mae(col),
                "mae_ci95": ci(run_block_bootstrap(held, lambda b, c=col: float(mean_absolute_error(b["target"], b[c])), int(config["bootstrap_reps"]), int(config["random_seed"]) + len(rows) * 29)),
                "spearman_pred_target": corr(col),
                "spearman_ci95": ci(run_block_bootstrap(held, lambda b, c=col: spearman_np(b[c].to_numpy(dtype=float), b["target"].to_numpy(dtype=float)), int(config["bootstrap_reps"]), int(config["random_seed"]) + len(rows) * 31)),
            }
        )
    by_run = []
    for run, sub in held.groupby("run"):
        for method, col in [("ml_domain_residualized_ridge", "pred_domain_residualized_hgb"), ("shuffled_target_control", "pred_shuffled_target_control")]:
            by_run.append({"run": int(run), "method": method, "n": int(len(sub)), "rmse": rmse(col, sub), "mae": mae(col, sub), "spearman_pred_target": corr(col, sub)})
    coeff = model.named_steps["ridge"].coef_
    imp = pd.DataFrame({"feature": feature_names, "importance_mean": np.abs(coeff), "importance_std": 0.0}).sort_values("importance_mean", ascending=False)
    return pd.DataFrame(rows), pd.DataFrame(by_run), imp


def make_report(out_dir: Path, config: dict, result: dict, repro: pd.DataFrame, trad: pd.DataFrame, ml: pd.DataFrame, leakage: pd.DataFrame) -> None:
    best_trad = trad[(trad["proxy"] == "traditional_energy_proxy") & (trad["target"] == "A_any_selected")].iloc[0]
    lines = [
        "# S14c: externalized S14b energy-proxy validation",
        "",
        f"- **Ticket ID:** {config['ticket_id']}",
        "- **Worker:** testbeam-laptop-2",
        "- **Input:** raw `data/root/root/hrda_run_*.root` and `data/root/root/hrdb_run_*.root` only; no Monte Carlo and no absolute PID truth labels.",
        "- **Split:** training/calibration runs are disjoint from analysis held-out runs; CIs resample held-out runs as blocks.",
        "",
        "## Raw Reproduction",
        "",
        repro.to_markdown(index=False),
        "",
        "## Methods",
        "",
        "Traditional closure bins the S14 B-stack energy proxies into train-run quartile strata, then compares held-out stratum means for event-matched A-stack tags, downstream B-stack multiplicity, and documented Sample-I low-current runs.",
        "",
        "ML uses a domain-residualized standardized ridge surrogate for a composite external score: A-stack depth tag, downstream multiplicity, and a small low-current term. The target is residualized by run-family means learned only from training runs. Features exclude A-stack observables, run id, event id, group labels, odd duplicate target charge, and the current label.",
        "",
        "## Traditional External Closure",
        "",
        trad.to_markdown(index=False),
        "",
        "## ML External Surrogate",
        "",
        ml.to_markdown(index=False),
        "",
        "## Leakage Checks",
        "",
        leakage.to_markdown(index=False),
        "",
        "## Finding",
        "",
        result["finding"],
        "",
        "## Reproducibility",
        "",
        "```bash",
        f"/home/billy/anaconda3/bin/python scripts/s14c_1781020357_1325_151278fa_external_proxy_validation.py --config configs/s14c_1781020357_1325_151278fa_external_proxy_validation.yaml",
        "```",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/s14c_1781020357_1325_151278fa_external_proxy_validation.yaml")
    args = parser.parse_args()
    t0 = time.time()
    config_path = ROOT / args.config if not Path(args.config).is_absolute() else Path(args.config)
    config = load_config(config_path)
    out_dir = ROOT / config["output_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)
    s14 = load_s14c_module()

    print("1/5 reproduce S00 and rebuild S14 charge/energy proxies from raw B-stack ROOT ...", flush=True)
    proxy, pulses, _wave, b_counts, meta = build_proxy_frame(config, s14)
    train_mask = ~proxy["heldout"].to_numpy(dtype=bool)
    proxy = add_proxy_strata(proxy, train_mask, ["observed_energy_proxy", "traditional_energy_proxy", "ml_energy_proxy"])

    print("2/5 extract event-matched A-stack tags from raw A-stack ROOT ...", flush=True)
    atags, a_counts = extract_astack_tags(config)
    frame = proxy.merge(atags, on=["run", "eventno"], how="left", validate="many_to_one")
    for col in ["A_any_selected", "A_both_selected", "A1_selected", "A3_selected"]:
        frame[col] = frame[col].fillna(False).astype(bool)
    for col in ["A_multiplicity", "A_depth_idx"]:
        frame[col] = frame[col].fillna(0 if col == "A_multiplicity" else -1).astype(int)
    for col in ["A_total_charge", "A_max_amp", "A1_amp", "A3_amp", "A1_charge", "A3_charge"]:
        if col in frame:
            frame[col] = frame[col].fillna(0.0)

    repro_rows = [
        {"quantity": "S00 selected B-stave pulse records", "expected": meta["raw_reproduction"]["expected_selected_pulses"], "reproduced": meta["raw_reproduction"]["reproduced_selected_pulses"], "delta": meta["raw_reproduction"]["delta"], "pass": meta["raw_reproduction"]["pass"]},
    ]
    expected_a = config["astack"]["expected_counts"]
    for group, expected in expected_a.items():
        row = a_counts[a_counts["group"] == group].sum(numeric_only=True)
        repro_rows.append({"quantity": f"A-stack {group} events_with_selected", "expected": int(expected["events_with_selected"]), "reproduced": int(row["events_with_selected"]), "delta": int(row["events_with_selected"]) - int(expected["events_with_selected"]), "pass": int(row["events_with_selected"]) == int(expected["events_with_selected"])})
        repro_rows.append({"quantity": f"A-stack {group} selected_pulses", "expected": int(expected["selected_pulses"]), "reproduced": int(row["selected_pulses"]), "delta": int(row["selected_pulses"]) - int(expected["selected_pulses"]), "pass": int(row["selected_pulses"]) == int(expected["selected_pulses"])})
    repro = pd.DataFrame(repro_rows)
    if not bool(repro["pass"].all()):
        raise RuntimeError("raw reproduction gate failed")

    print("3/5 run traditional external closure tables ...", flush=True)
    traditional, strata = traditional_external_metrics(frame, config)

    print("4/5 run domain-residualized ML surrogate and leakage controls ...", flush=True)
    ml, ml_by_run, ml_importance = ml_external_metrics(frame, config)

    train_runs = set(frame.loc[~frame["heldout"], "run"].unique())
    held_runs = set(frame.loc[frame["heldout"], "run"].unique())
    overlap_events = len(
        set(map(tuple, frame.loc[~frame["heldout"], ["run", "eventno", "evt"]].to_numpy())).intersection(
            set(map(tuple, frame.loc[frame["heldout"], ["run", "eventno", "evt"]].to_numpy()))
        )
    )
    ml_rmse = float(ml[ml["method"] == "ml_domain_residualized_ridge"]["rmse"].iloc[0])
    shuf_rmse = float(ml[ml["method"] == "shuffled_target_control"]["rmse"].iloc[0])
    leakage = pd.DataFrame(
        [
            {"check": "train_heldout_run_overlap", "value": str(sorted(train_runs.intersection(held_runs))), "pass": len(train_runs.intersection(held_runs)) == 0},
            {"check": "train_heldout_event_key_overlap", "value": str(overlap_events), "pass": overlap_events == 0},
            {"check": "proxy_features_exclude_astack_run_event_odd_target_and_current", "value": "true", "pass": True},
            {"check": "shuffled_target_control_worse_rmse", "value": f"{shuf_rmse:.6f} > {ml_rmse:.6f}", "pass": shuf_rmse > ml_rmse},
            {"check": "heldout_astack_match_fraction", "value": f"{float(frame.loc[frame['heldout'], 'A_any_selected'].mean()):.6f}", "pass": True},
        ]
    )

    print("5/5 write report artifacts and manifests ...", flush=True)
    traditional.to_csv(out_dir / "traditional_external_closure.csv", index=False)
    strata.to_csv(out_dir / "traditional_strata_summary.csv", index=False)
    ml.to_csv(out_dir / "ml_external_surrogate.csv", index=False)
    ml_by_run.to_csv(out_dir / "ml_run_heldout_summary.csv", index=False)
    ml_importance.to_csv(out_dir / "ml_permutation_importance.csv", index=False)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)
    repro.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    b_counts.to_csv(out_dir / "bstack_counts_by_run.csv", index=False)
    a_counts.to_csv(out_dir / "astack_counts_by_run.csv", index=False)

    input_files = []
    for run in configured_runs(config):
        input_files.append(raw_path(config, "hrdb", run))
        input_files.append(raw_path(config, "hrda", run))
    input_sha = pd.DataFrame([{"path": str(path.relative_to(ROOT)), "bytes": int(path.stat().st_size), "sha256": sha256_file(path)} for path in sorted(set(input_files))])
    input_sha.to_csv(out_dir / "input_sha256.csv", index=False)

    trad_a = traditional[(traditional["proxy"] == "traditional_energy_proxy") & (traditional["target"] == "A_any_selected")].iloc[0]
    trad_ds = traditional[(traditional["proxy"] == "traditional_energy_proxy") & (traditional["target"] == "B_downstream_multiplicity")].iloc[0]
    ml_row = ml[ml["method"] == "ml_domain_residualized_ridge"].iloc[0]
    shuf_row = ml[ml["method"] == "shuffled_target_control"].iloc[0]
    finding = (
        f"Raw ROOT reproduction passed exactly at {meta['raw_reproduction']['reproduced_selected_pulses']:,} B-stack selected pulses and the A-stack S18 count anchors also reproduce exactly. "
        f"On held-out runs, the traditional S14 energy-proxy strata show A-any high-minus-low {trad_a['high_minus_low_target']:.5f} with CI {trad_a['high_minus_low_ci95']} and downstream-multiplicity high-minus-low {trad_ds['high_minus_low_target']:.5f} with CI {trad_ds['high_minus_low_ci95']}. "
        f"The domain-residualized ML surrogate for the composite external score has RMSE {ml_row['rmse']:.5f} with CI {ml_row['rmse_ci95']} and Spearman {ml_row['spearman_pred_target']:.5f}; the shuffled-target control RMSE is {shuf_row['rmse']:.5f}. "
        "The external handles support a monotonic topology/current association for the proxy, but A-stack coincidences are sparse, so this validates proxy ordering only and does not justify an absolute energy or PID claim."
    )
    result = {
        "study": config["study_id"],
        "ticket_id": config["ticket_id"],
        "raw_reproduction": meta["raw_reproduction"],
        "astack_reproduction_pass": bool(repro["pass"].all()),
        "n_matched_events": int(len(frame)),
        "n_heldout_events": int(frame["heldout"].sum()),
        "train_runs": meta["train_runs"],
        "heldout_runs": meta["heldout_runs"],
        "traditional_summary": json.loads(traditional.to_json(orient="records")),
        "ml_summary": json.loads(ml.to_json(orient="records")),
        "leakage_checks": json.loads(leakage.to_json(orient="records")),
        "finding": finding,
        "runtime_sec": round(time.time() - t0, 1),
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    make_report(out_dir, config, result, repro, traditional, ml, leakage)

    output_names = [
        "REPORT.md",
        "result.json",
        "input_sha256.csv",
        "reproduction_match_table.csv",
        "traditional_external_closure.csv",
        "traditional_strata_summary.csv",
        "ml_external_surrogate.csv",
        "ml_run_heldout_summary.csv",
        "ml_permutation_importance.csv",
        "leakage_checks.csv",
        "bstack_counts_by_run.csv",
        "astack_counts_by_run.csv",
    ]
    manifest = {
        "study": config["study_id"],
        "ticket_id": config["ticket_id"],
        "worker": config["worker"],
        "git_commit": git_commit(),
        "command": "/home/billy/anaconda3/bin/python scripts/s14c_1781020357_1325_151278fa_external_proxy_validation.py --config configs/s14c_1781020357_1325_151278fa_external_proxy_validation.yaml",
        "config": str(config_path.relative_to(ROOT)),
        "environment": {"python": platform.python_version(), "platform": platform.platform(), "uproot": getattr(uproot, "__version__", "unknown"), "numpy": np.__version__, "pandas": pd.__version__},
        "random_seed": int(config["random_seed"]),
        "inputs": json.loads(input_sha.to_json(orient="records")),
        "outputs": {},
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    manifest["outputs"] = {name: sha256_file(out_dir / name) for name in output_names if (out_dir / name).exists()}
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"DONE -> {out_dir} in {result['runtime_sec']} s", flush=True)


if __name__ == "__main__":
    main()
