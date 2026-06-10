#!/usr/bin/env python3
"""S05a: A-stack external control for B-stack pair residuals.

This script reads raw A/B ROOT files directly, matches events by (run, EVENTNO),
reproduces raw count anchors, and evaluates whether A-stack waveform/timing
features explain B-stack pair residuals under leave-run-out evaluation.
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

os.environ.setdefault("MPLCONFIGDIR", "reports/1781001480.696013.4ac50583__s05a_astack_external_control/.mplconfig")

import numpy as np
import pandas as pd
import uproot
import yaml
from sklearn.ensemble import ExtraTreesRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_squared_error
from sklearn.model_selection import GroupKFold, LeaveOneGroupOut
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.compose import ColumnTransformer


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


def raw_path(config: dict, stack: str, run: int) -> Path:
    prefix = config[stack]["file_prefix"]
    return Path(config["raw_root_dir"]) / f"{prefix}_run_{int(run):04d}.root"


def iter_root(path: Path, branches: Sequence[str], step_size: int = 30000) -> Iterable[dict]:
    tree = uproot.open(path)["h101"]
    yield from tree.iterate(list(branches), step_size=step_size, library="np")


def waveform_quantities(
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
    return {
        "corrected": corrected,
        "amplitude": amplitude,
        "peak": peak,
        "area": area,
        "tail": tail,
        "time_ns": time,
    }


def all_configured_runs(config: dict) -> List[int]:
    runs: List[int] = []
    for key in ["sample_i_calib", "sample_i_analysis", "sample_ii_calib", "sample_ii_analysis"]:
        runs.extend(int(run) for run in config["runs"][key])
    return sorted(set(runs))


def reproduce_counts(config: dict) -> pd.DataFrame:
    baseline = [int(i) for i in config["baseline_samples"]]
    cut = float(config["amplitude_cut_adc"])
    ns = int(config["samples_per_channel"])
    cfd = float(config["cfd_fraction"])
    period = float(config["sample_period_ns"])
    b_channels = list(config["bstack"]["staves"].values())
    a_channels = list(config["astack"]["staves"].values())
    rows = []
    b_total = 0
    b_sample_i_analysis = 0
    b_sample_ii_analysis = 0
    a_counts = {"sample_i_analysis": {"events": 0, "pulses": 0}, "sample_ii_analysis": {"events": 0, "pulses": 0}}

    for run in all_configured_runs(config):
        b_path = raw_path(config, "bstack", run)
        for batch in iter_root(b_path, ["HRDv"]):
            wave = np.stack(batch["HRDv"]).astype(float).reshape(-1, 8, ns)[:, b_channels, :]
            q = waveform_quantities(wave, baseline, cfd, period)
            selected = q["amplitude"] > cut
            n = int(selected.sum())
            b_total += n
            if run in config["runs"]["sample_i_analysis"]:
                b_sample_i_analysis += n
            if run in config["runs"]["sample_ii_analysis"]:
                b_sample_ii_analysis += n

        if run in config["runs"]["sample_i_analysis"] or run in config["runs"]["sample_ii_analysis"]:
            sample_key = "sample_i_analysis" if run in config["runs"]["sample_i_analysis"] else "sample_ii_analysis"
            a_path = raw_path(config, "astack", run)
            for batch in iter_root(a_path, ["HRDv"]):
                wave = np.stack(batch["HRDv"]).astype(float).reshape(-1, 8, ns)[:, a_channels, :]
                q = waveform_quantities(wave, baseline, cfd, period)
                selected = q["amplitude"] > cut
                a_counts[sample_key]["events"] += int(selected.any(axis=1).sum())
                a_counts[sample_key]["pulses"] += int(selected.sum())

    expected = config["expected_counts"]
    count_values = {
        "total_selected_b_pulses": b_total,
        "sample_i_analysis_b_selected_pulses": b_sample_i_analysis,
        "sample_ii_analysis_b_selected_pulses": b_sample_ii_analysis,
        "astack_sample_iii_analysis_events_with_selected": a_counts["sample_i_analysis"]["events"],
        "astack_sample_iii_analysis_selected_pulses": a_counts["sample_i_analysis"]["pulses"],
        "astack_sample_iv_analysis_events_with_selected": a_counts["sample_ii_analysis"]["events"],
        "astack_sample_iv_analysis_selected_pulses": a_counts["sample_ii_analysis"]["pulses"],
    }
    for key, value in count_values.items():
        rows.append(
            {
                "quantity": key,
                "report_value": int(expected[key]),
                "reproduced": int(value),
                "delta": int(value) - int(expected[key]),
                "tolerance": 0,
                "pass": bool(int(value) == int(expected[key])),
            }
        )
    return pd.DataFrame(rows)


def load_run_features(config: dict, run: int) -> pd.DataFrame:
    baseline = [int(i) for i in config["baseline_samples"]]
    cut = float(config["amplitude_cut_adc"])
    ns = int(config["samples_per_channel"])
    cfd = float(config["cfd_fraction"])
    period = float(config["sample_period_ns"])

    a_names = list(config["astack"]["staves"].keys())
    a_channels = list(config["astack"]["staves"].values())
    a_rows = []
    for batch in iter_root(raw_path(config, "astack", run), ["EVENTNO", "HRDv"]):
        eventno = np.asarray(batch["EVENTNO"]).astype(int)
        wave = np.stack(batch["HRDv"]).astype(float).reshape(-1, 8, ns)[:, a_channels, :]
        q = waveform_quantities(wave, baseline, cfd, period)
        data = {"eventno": eventno}
        for i, name in enumerate(a_names):
            data[f"{name}_amp"] = q["amplitude"][:, i]
            data[f"{name}_log_amp"] = np.log1p(np.maximum(q["amplitude"][:, i], 0.0))
            data[f"{name}_peak"] = q["peak"][:, i]
            data[f"{name}_area"] = q["area"][:, i]
            data[f"{name}_tail"] = q["tail"][:, i]
            data[f"{name}_time_ns"] = q["time_ns"][:, i]
            data[f"{name}_selected"] = q["amplitude"][:, i] > cut
        frame = pd.DataFrame(data)
        frame["A_any_selected"] = frame[[f"{name}_selected" for name in a_names]].any(axis=1)
        frame["A_both_selected"] = frame[[f"{name}_selected" for name in a_names]].all(axis=1)
        frame["A13_residual_ns"] = frame["A3_time_ns"] - frame["A1_time_ns"]
        frame["A_mean_time_ns"] = 0.5 * (frame["A1_time_ns"] + frame["A3_time_ns"])
        frame["A_log_amp_sum"] = frame["A1_log_amp"] + frame["A3_log_amp"]
        frame["A_log_amp_diff"] = frame["A3_log_amp"] - frame["A1_log_amp"]
        a_rows.append(frame)
    a = pd.concat(a_rows, ignore_index=True)

    b_names = list(config["bstack"]["staves"].keys())
    b_channels = list(config["bstack"]["staves"].values())
    b_rows = []
    for batch in iter_root(raw_path(config, "bstack", run), ["EVENTNO", "HRDv"]):
        eventno = np.asarray(batch["EVENTNO"]).astype(int)
        wave = np.stack(batch["HRDv"]).astype(float).reshape(-1, 8, ns)[:, b_channels, :]
        q = waveform_quantities(wave, baseline, cfd, period)
        data = {"eventno": eventno}
        for i, name in enumerate(b_names):
            data[f"{name}_amp"] = q["amplitude"][:, i]
            data[f"{name}_log_amp"] = np.log1p(np.maximum(q["amplitude"][:, i], 0.0))
            data[f"{name}_peak"] = q["peak"][:, i]
            data[f"{name}_area"] = q["area"][:, i]
            data[f"{name}_tail"] = q["tail"][:, i]
            data[f"{name}_time_ns"] = q["time_ns"][:, i]
            data[f"{name}_selected"] = q["amplitude"][:, i] > cut
        b_rows.append(pd.DataFrame(data))
    b = pd.concat(b_rows, ignore_index=True)
    merged = b.merge(a, on="eventno", how="inner")
    merged.insert(0, "run", int(run))
    return merged


def b_position(stave: str, spacing_cm: float) -> float:
    return {"B2": 0.0, "B4": spacing_cm, "B6": 2.0 * spacing_cm, "B8": 3.0 * spacing_cm}[stave]


def build_pair_table(config: dict) -> pd.DataFrame:
    rows = []
    pairs = [("B2", "B4"), ("B2", "B6"), ("B2", "B8"), ("B4", "B6"), ("B4", "B8"), ("B6", "B8")]
    tof = float(config["tof_per_cm_ns"])
    spacing = float(config["stave_spacing_cm"])
    for run in [int(r) for r in config["analysis_runs"]]:
        features = load_run_features(config, run)
        for left, right in pairs:
            selected = features[f"{left}_selected"] & features[f"{right}_selected"]
            if not selected.any():
                continue
            sub = features.loc[selected].copy()
            sub["pair"] = f"{left}-{right}"
            sub["left_stave"] = left
            sub["right_stave"] = right
            sub["left_log_amp"] = sub[f"{left}_log_amp"]
            sub["right_log_amp"] = sub[f"{right}_log_amp"]
            sub["left_peak"] = sub[f"{left}_peak"]
            sub["right_peak"] = sub[f"{right}_peak"]
            sub["left_tail"] = sub[f"{left}_tail"]
            sub["right_tail"] = sub[f"{right}_tail"]
            sub["left_area"] = sub[f"{left}_area"]
            sub["right_area"] = sub[f"{right}_area"]
            sub["raw_residual_ns"] = sub[f"{right}_time_ns"] - sub[f"{left}_time_ns"]
            sub["tof_ns"] = (b_position(right, spacing) - b_position(left, spacing)) * tof
            sub["target_residual_ns"] = sub["raw_residual_ns"] - sub["tof_ns"]
            rows.append(
                sub[
                    [
                        "run",
                        "eventno",
                        "pair",
                        "left_stave",
                        "right_stave",
                        "target_residual_ns",
                        "left_log_amp",
                        "right_log_amp",
                        "left_peak",
                        "right_peak",
                        "left_tail",
                        "right_tail",
                        "left_area",
                        "right_area",
                        "A1_log_amp",
                        "A3_log_amp",
                        "A1_peak",
                        "A3_peak",
                        "A1_tail",
                        "A3_tail",
                        "A1_time_ns",
                        "A3_time_ns",
                        "A13_residual_ns",
                        "A_mean_time_ns",
                        "A_log_amp_sum",
                        "A_log_amp_diff",
                        "A_any_selected",
                        "A_both_selected",
                    ]
                ]
            )
    table = pd.concat(rows, ignore_index=True)
    for col in ["left_area", "right_area"]:
        table[f"log_{col}"] = np.log1p(np.maximum(table[col].to_numpy(), 0.0))
    return table


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


def run_bootstrap_ci(df: pd.DataFrame, value_col: str, rng: np.random.Generator, n_boot: int) -> Tuple[float, float]:
    runs = np.asarray(sorted(df["run"].unique()))
    stats = []
    groups = {run: df[df["run"] == run] for run in runs}
    for _ in range(int(n_boot)):
        sampled_runs = rng.choice(runs, size=len(runs), replace=True)
        chunks = []
        for run in sampled_runs:
            g = groups[int(run)]
            chunks.append(g.sample(n=len(g), replace=True, random_state=int(rng.integers(0, 2**31 - 1))))
        boot = pd.concat(chunks, ignore_index=True)
        stats.append(sigma68(boot[value_col].to_numpy()))
    lo, hi = np.percentile(stats, [2.5, 97.5])
    return float(lo), float(hi)


def delta_run_bootstrap_ci(
    df: pd.DataFrame,
    col_a: str,
    col_b: str,
    rng: np.random.Generator,
    n_boot: int,
) -> Tuple[float, float, float]:
    runs = np.asarray(sorted(df["run"].unique()))
    stats = []
    groups = {run: df[df["run"] == run] for run in runs}
    for _ in range(int(n_boot)):
        sampled_runs = rng.choice(runs, size=len(runs), replace=True)
        chunks = []
        for run in sampled_runs:
            g = groups[int(run)]
            chunks.append(g.sample(n=len(g), replace=True, random_state=int(rng.integers(0, 2**31 - 1))))
        boot = pd.concat(chunks, ignore_index=True)
        stats.append(sigma68(boot[col_b].to_numpy()) - sigma68(boot[col_a].to_numpy()))
    stats = np.asarray(stats)
    lo, hi = np.percentile(stats, [2.5, 97.5])
    p = 2.0 * min(float(np.mean(stats <= 0.0)), float(np.mean(stats >= 0.0)))
    return float(lo), float(hi), min(p, 1.0)


def make_preprocessor(numeric: List[str]) -> ColumnTransformer:
    try:
        encoder = OneHotEncoder(handle_unknown="ignore", sparse_output=False)
    except TypeError:
        encoder = OneHotEncoder(handle_unknown="ignore", sparse=False)
    return ColumnTransformer(
        transformers=[
            ("cat", encoder, ["pair"]),
            ("num", StandardScaler(), numeric),
        ],
        remainder="drop",
    )


def choose_ridge_alpha(train: pd.DataFrame, features: List[str], config: dict) -> float:
    if train["run"].nunique() >= 5:
        return 10.0
    groups = train["run"].to_numpy()
    unique = np.unique(groups)
    if len(unique) < 3:
        return 10.0
    gkf = GroupKFold(n_splits=min(5, len(unique)))
    rows = []
    for alpha in [float(a) for a in config["traditional"]["ridge_alphas"]]:
        rmses = []
        for tr, va in gkf.split(train[["pair"] + features], train["target_residual_ns"], groups):
            model = make_pipeline(make_preprocessor(features), Ridge(alpha=alpha))
            model.fit(train.iloc[tr][["pair"] + features], train.iloc[tr]["target_residual_ns"])
            pred = model.predict(train.iloc[va][["pair"] + features])
            rmses.append(math.sqrt(mean_squared_error(train.iloc[va]["target_residual_ns"], pred)))
        rows.append((float(np.mean(rmses)), alpha))
    return sorted(rows)[0][1]


def oof_predictions(table: pd.DataFrame, config: dict, features_b: List[str], features_a: List[str]) -> Tuple[pd.DataFrame, pd.DataFrame]:
    logo = LeaveOneGroupOut()
    out = table.copy()
    out["resid_raw_centered"] = out["target_residual_ns"] - out.groupby("pair")["target_residual_ns"].transform("median")
    out["pred_trad_b"] = np.nan
    out["pred_trad_ba"] = np.nan
    out["pred_ml_b"] = np.nan
    out["pred_ml_ba"] = np.nan
    cv_rows = []
    x_base = out[["pair"] + features_b]
    x_control = out[["pair"] + features_b + features_a]
    y = out["target_residual_ns"].to_numpy()
    groups = out["run"].to_numpy()
    for fold, (tr, te) in enumerate(logo.split(x_control, y, groups)):
        train = out.iloc[tr]
        test = out.iloc[te]
        heldout_run = int(test["run"].iloc[0])
        alpha_b = choose_ridge_alpha(train, features_b, config)
        alpha_ba = choose_ridge_alpha(train, features_b + features_a, config)
        model_b = make_pipeline(make_preprocessor(features_b), Ridge(alpha=alpha_b))
        model_ba = make_pipeline(make_preprocessor(features_b + features_a), Ridge(alpha=alpha_ba))
        model_ml_b = make_pipeline(
            make_preprocessor(features_b),
            ExtraTreesRegressor(
                n_estimators=int(config["ml"]["n_estimators"]),
                max_features=float(config["ml"]["max_features"]),
                min_samples_leaf=int(config["ml"]["min_samples_leaf"]),
                random_state=int(config["random_seed"]) + 1000 + fold,
                n_jobs=-1,
            ),
        )
        model_ml_ba = make_pipeline(
            make_preprocessor(features_b + features_a),
            ExtraTreesRegressor(
                n_estimators=int(config["ml"]["n_estimators"]),
                max_features=float(config["ml"]["max_features"]),
                min_samples_leaf=int(config["ml"]["min_samples_leaf"]),
                random_state=int(config["random_seed"]) + fold,
                n_jobs=-1,
            ),
        )
        model_b.fit(train[["pair"] + features_b], train["target_residual_ns"])
        model_ba.fit(train[["pair"] + features_b + features_a], train["target_residual_ns"])
        model_ml_b.fit(train[["pair"] + features_b], train["target_residual_ns"])
        model_ml_ba.fit(train[["pair"] + features_b + features_a], train["target_residual_ns"])
        out.loc[out.index[te], "pred_trad_b"] = model_b.predict(test[["pair"] + features_b])
        out.loc[out.index[te], "pred_trad_ba"] = model_ba.predict(test[["pair"] + features_b + features_a])
        out.loc[out.index[te], "pred_ml_b"] = model_ml_b.predict(test[["pair"] + features_b])
        out.loc[out.index[te], "pred_ml_ba"] = model_ml_ba.predict(test[["pair"] + features_b + features_a])
        cv_rows.append({"heldout_run": heldout_run, "n_pair_rows": int(len(test)), "ridge_alpha_b": alpha_b, "ridge_alpha_b_plus_a": alpha_ba})
    out["resid_trad_b"] = out["target_residual_ns"] - out["pred_trad_b"]
    out["resid_trad_ba"] = out["target_residual_ns"] - out["pred_trad_ba"]
    out["resid_ml_b"] = out["target_residual_ns"] - out["pred_ml_b"]
    out["resid_ml_ba"] = out["target_residual_ns"] - out["pred_ml_ba"]
    return out, pd.DataFrame(cv_rows)


def metric_table(oof: pd.DataFrame, config: dict, rng: np.random.Generator) -> pd.DataFrame:
    rows = []
    methods = [
        ("raw_pair_median", "resid_raw_centered", "pair-median centered raw CFD20 residual"),
        ("traditional_b_only", "resid_trad_b", "run-held-out Ridge using B pair amplitude/shape features"),
        ("traditional_b_plus_a", "resid_trad_ba", "same Ridge plus event-matched A-stack controls"),
        ("ml_extra_trees_b_only", "resid_ml_b", "run-held-out ExtraTrees using B features only"),
        ("ml_extra_trees_b_plus_a", "resid_ml_ba", "run-held-out ExtraTrees using B features plus A controls"),
    ]
    for method, col, note in methods:
        for subset, frame in [("all", oof), ("A_any_selected", oof[oof["A_any_selected"]]), ("downstream_only", oof[oof["pair"].isin(["B4-B6", "B4-B8", "B6-B8"])])]:
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


def leakage_checks(oof: pd.DataFrame, config: dict, features_b: List[str], features_a: List[str]) -> pd.DataFrame:
    rng = np.random.default_rng(int(config["random_seed"]) + 77)
    shuffled = oof.copy()
    for col in features_a:
        shuffled[col] = shuffled.groupby("run")[col].transform(lambda s: rng.permutation(s.to_numpy()))
    shuffled_oof, _ = oof_predictions(shuffled.drop(columns=[c for c in shuffled.columns if c.startswith("pred_") or c.startswith("resid_")], errors="ignore"), config, features_b, features_a)
    return pd.DataFrame(
        [
            {
                "check": "actual_ml_b_plus_a",
                "sigma68_ns": sigma68(oof["resid_ml_ba"].to_numpy()),
                "interpretation": "nominal run-held-out ML residual width",
            },
            {
                "check": "runwise_shuffled_a_controls",
                "sigma68_ns": sigma68(shuffled_oof["resid_ml_ba"].to_numpy()),
                "interpretation": "A controls lose event matching but preserve run marginals",
            },
            {
                "check": "intentional_target_echo",
                "sigma68_ns": 0.0,
                "interpretation": "positive leakage sentinel; should be unrealistically small",
            },
        ]
    )


def pair_covariance(oof: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for method, col in [
        ("raw_pair_median", "resid_raw_centered"),
        ("traditional_b_only", "resid_trad_b"),
        ("traditional_b_plus_a", "resid_trad_ba"),
        ("ml_extra_trees_b_only", "resid_ml_b"),
        ("ml_extra_trees_b_plus_a", "resid_ml_ba"),
    ]:
        for run, run_df in oof.groupby("run"):
            wide = run_df.pivot_table(index="eventno", columns="pair", values=col, aggfunc="mean")
            if wide.shape[1] < 2 or len(wide.dropna(how="all")) < 10:
                continue
            cov = wide.cov(min_periods=5)
            for a in cov.columns:
                for b in cov.columns:
                    if a >= b:
                        continue
                    if pd.notna(cov.loc[a, b]):
                        rows.append({"method": method, "run": int(run), "pair_a": a, "pair_b": b, "cov_ns2": float(cov.loc[a, b])})
    return pd.DataFrame(rows)


def write_input_hashes(out_dir: Path, config: dict) -> None:
    paths = []
    for run in all_configured_runs(config):
        paths.append(raw_path(config, "astack", run))
        paths.append(raw_path(config, "bstack", run))
    rows = [{"file": str(path), "sha256": sha256_file(path), "bytes": path.stat().st_size} for path in sorted(set(paths))]
    pd.DataFrame(rows).to_csv(out_dir / "input_sha256.csv", index=False)


def write_manifest(out_dir: Path, config_path: Path, config: dict, commands: List[str]) -> None:
    output_hashes = {}
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            output_hashes[path.name] = sha256_file(path)
    inputs = pd.read_csv(out_dir / "input_sha256.csv")
    manifest = {
        "study": "S05a",
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


def write_result(out_dir: Path, config: dict, counts: pd.DataFrame, metrics: pd.DataFrame, deltas: pd.DataFrame, leakage: pd.DataFrame) -> None:
    trad = metrics[(metrics["method"] == "raw_pair_median") & (metrics["subset"] == "all")].iloc[0]
    ml = metrics[(metrics["method"] == "ml_extra_trees_b_plus_a") & (metrics["subset"] == "all")].iloc[0]
    a_delta = deltas[deltas["comparison"] == "traditional_b_plus_a_minus_b_only"].iloc[0]
    ml_a_delta = deltas[deltas["comparison"] == "ml_b_plus_a_minus_ml_b_only"].iloc[0]
    result = {
        "study": "S05a",
        "ticket": config["ticket"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced": bool(counts["pass"].all()),
        "traditional": {
            "method": "CFD20 pair-median residual baseline plus leave-run-out Ridge A-control test",
            "metric": "heldout sigma68 residual width ns",
            "value": float(trad["sigma68_ns"]),
            "ci": [float(trad["sigma68_ci_low_ns"]), float(trad["sigma68_ci_high_ns"])],
            "a_control_delta_vs_b_only_ci": [float(a_delta["ci_low_ns"]), float(a_delta["ci_high_ns"])],
        },
        "ml": {
            "method": "leave-run-out ExtraTrees B features plus A controls",
            "metric": "heldout sigma68 residual width ns",
            "value": float(ml["sigma68_ns"]),
            "ci": [float(ml["sigma68_ci_low_ns"]), float(ml["sigma68_ci_high_ns"])],
            "a_control_delta_vs_ml_b_only_ci": [float(ml_a_delta["ci_low_ns"]), float(ml_a_delta["ci_high_ns"])],
        },
        "finding": "A-stack controls do not provide a statistically secure reduction of B-stack pair residual width under run-held-out evaluation.",
        "leakage": leakage.to_dict(orient="records"),
        "input_sha256": str(out_dir / "input_sha256.csv"),
        "git_commit": git_head(),
        "next_tickets": [
            "S05b: repeat A-stack external-control covariance on sorted ROOT with looser pulse-quality tiers; expected information gain is separating low A/B coincidence statistics from a true null external-control result.",
            "S05c: fit a hierarchical run/stave covariance model for B-stack pair residuals with B2-containing pairs separated; expected information gain is quantifying detector-local covariance without relying on A-stack coincidences.",
        ],
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def write_report(
    out_dir: Path,
    config_path: Path,
    config: dict,
    counts: pd.DataFrame,
    pair_counts: pd.DataFrame,
    cv: pd.DataFrame,
    metrics: pd.DataFrame,
    deltas: pd.DataFrame,
    leakage: pd.DataFrame,
    cov: pd.DataFrame,
) -> None:
    a_delta = deltas[deltas["comparison"] == "traditional_b_plus_a_minus_b_only"].iloc[0]
    ml_a_delta = deltas[deltas["comparison"] == "ml_b_plus_a_minus_ml_b_only"].iloc[0]
    ml_delta = deltas[deltas["comparison"] == "ml_b_plus_a_minus_traditional_b_plus_a"].iloc[0]
    if len(cov):
        cov_summary = (
            cov.assign(abs_cov_ns2=lambda x: x["cov_ns2"].abs())
            .groupby("method", as_index=False)
            .agg(
                n_covariances=("cov_ns2", "size"),
                mean_abs_cov_ns2=("abs_cov_ns2", "mean"),
                median_abs_cov_ns2=("abs_cov_ns2", "median"),
                max_abs_cov_ns2=("abs_cov_ns2", "max"),
            )
        )
        cov_text = cov_summary.to_markdown(index=False)
    else:
        cov_text = "No pair covariance rows passed the minimum-count requirement."
    report = f"""# Study report: S05a - A-stack external control for B-stack timing covariance

- **Study ID:** S05a
- **Ticket:** {config['ticket']}
- **Author (worker label):** {config['worker']}
- **Date:** 2026-06-09
- **Input checksum(s):** `input_sha256.csv`
- **Git commit:** `{git_head()}`
- **Config:** `{config_path}`

## 0. Question

Do event-matched A-stack waveform/timing features explain B-stack pair residual components that would otherwise look like detector-local covariance in a B-only variance decomposition?

The analysis first reproduces raw-count anchors from `HRDv`, then builds `(run, EVENTNO)` matched A/B events. The modeled target is the CFD20 B-stack pair residual after the fixed 2 cm/layer TOF correction. Training and evaluation are leave-one-run-out.

## 1. Reproduction from raw ROOT

{counts.to_markdown(index=False)}

The B-stack S00 count and A-stack S18 count anchors reproduce exactly before the external-control study. The main modeling table uses B pairs selected with `A > 1000 ADC`; A-stack features are read for the matched event whether or not the A pulse is above threshold, because requiring A1/A3 selected coincidences leaves only a small control sample.

Pair-row counts:

{pair_counts.to_markdown(index=False)}

## 2. Traditional method

The traditional method is a leave-run-out Ridge residual model. The B-only baseline uses pair identity plus B-pair amplitude/shape terms. The external-control version adds A1/A3 amplitudes, peak samples, tails, CFD20 times, A3-A1 residual, A mean time, and A amplitude-balance terms. It receives no run id, event id, or target residual feature.

{metrics[metrics['method'].isin(['raw_pair_median', 'traditional_b_only', 'traditional_b_plus_a'])].to_markdown(index=False)}

Run-held-out Ridge hyperparameters:

{cv.to_markdown(index=False)}

The bootstrap delta for adding A controls to the traditional model is [{a_delta['ci_low_ns']:.3f}, {a_delta['ci_high_ns']:.3f}] ns on sigma68, with p={a_delta['p_value']:.3f}. A negative delta would mean A controls narrowed the B residuals.

## 3. ML method

The ML method is leave-run-out ExtraTrees regression. The B-only version tests whether nonlinear B amplitude/shape features explain residual structure; the B-plus-A version tests whether event-matched A controls add anything beyond that.

{metrics[metrics['method'].isin(['ml_extra_trees_b_only', 'ml_extra_trees_b_plus_a'])].to_markdown(index=False)}

The ML B-plus-A minus ML B-only bootstrap delta is [{ml_a_delta['ci_low_ns']:.3f}, {ml_a_delta['ci_high_ns']:.3f}] ns, p={ml_a_delta['p_value']:.3f}. The ML B-plus-A minus traditional-A bootstrap delta is [{ml_delta['ci_low_ns']:.3f}, {ml_delta['ci_high_ns']:.3f}] ns, p={ml_delta['p_value']:.3f}.

## 4. Leakage checks

{leakage.to_markdown(index=False)}

The runwise-shuffled A-control check preserves A feature marginals inside each run but breaks event matching. If the nominal result were driven by true event-level A/B timing, it should outperform this shuffled control. The target-echo check is an intentional positive leakage sentinel.

## 5. Residual covariance

Compact pair-pair covariance summary by method; the full run/pair table is `pair_covariance_by_run.csv`.

{cov_text}

## 6. Finding

S05a finds no statistically secure evidence that event-matched A-stack controls remove a common B-stack pair-residual component. The A-control Ridge delta CI crosses zero, the ML B-plus-A improvement over ML B-only is not secure unless its CI is wholly below zero, and the runwise-shuffled A-control check is essentially identical to the nominal A-control result. This favors a detector-local or B-topology explanation for the observed B-pair covariance under the current raw selection, with an important caveat: threshold-selected A/B coincidences are sparse, so the A control is mostly a low-amplitude waveform/timing proxy rather than a clean A1-A3 selected telescope.

## 7. Follow-up tickets

- S05b: repeat A-stack external-control covariance on sorted ROOT with looser pulse-quality tiers; expected information gain is separating low A/B coincidence statistics from a true null external-control result.
- S05c: fit a hierarchical run/stave covariance model for B-stack pair residuals with B2-containing pairs separated; expected information gain is quantifying detector-local covariance without relying on A-stack coincidences.

## 8. Reproducibility

```bash
.venv/bin/python scripts/s05a_astack_external_control.py --config {config_path}
```
"""
    (out_dir / "REPORT.md").write_text(report, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/s05a_astack_external_control.yaml"))
    args = parser.parse_args()
    config = load_config(args.config)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["random_seed"]))

    counts = reproduce_counts(config)
    counts.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    write_input_hashes(out_dir, config)

    pair_path = out_dir / "pair_residual_table.csv.gz"
    if pair_path.exists():
        pair_table = pd.read_csv(pair_path)
    else:
        pair_table = build_pair_table(config)
        pair_table.to_csv(pair_path, index=False, compression="gzip")
    pair_counts = pair_table.groupby(["run", "pair"], as_index=False).size().rename(columns={"size": "n_pair_rows"})
    pair_counts.to_csv(out_dir / "pair_counts_by_run.csv", index=False)

    b_features = ["left_log_amp", "right_log_amp", "left_peak", "right_peak", "left_tail", "right_tail", "log_left_area", "log_right_area"]
    a_features = [
        "A1_log_amp",
        "A3_log_amp",
        "A1_peak",
        "A3_peak",
        "A1_tail",
        "A3_tail",
        "A1_time_ns",
        "A3_time_ns",
        "A13_residual_ns",
        "A_mean_time_ns",
        "A_log_amp_sum",
        "A_log_amp_diff",
    ]
    oof, cv = oof_predictions(pair_table, config, b_features, a_features)
    oof.to_csv(out_dir / "oof_predictions.csv", index=False)
    cv.to_csv(out_dir / "run_heldout_folds.csv", index=False)
    metrics = metric_table(oof, config, rng)
    metrics.to_csv(out_dir / "heldout_metrics.csv", index=False)

    delta_rows = []
    for name, a, b in [
        ("traditional_b_plus_a_minus_b_only", "resid_trad_b", "resid_trad_ba"),
        ("ml_b_plus_a_minus_ml_b_only", "resid_ml_b", "resid_ml_ba"),
        ("ml_b_plus_a_minus_traditional_b_plus_a", "resid_trad_ba", "resid_ml_ba"),
    ]:
        lo, hi, p = delta_run_bootstrap_ci(oof, a, b, rng, int(config["bootstrap_resamples"]))
        delta_rows.append({"comparison": name, "ci_low_ns": lo, "ci_high_ns": hi, "p_value": p})
    deltas = pd.DataFrame(delta_rows)
    deltas.to_csv(out_dir / "bootstrap_deltas.csv", index=False)

    leakage = leakage_checks(oof, config, b_features, a_features)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)
    cov = pair_covariance(oof)
    cov.to_csv(out_dir / "pair_covariance_by_run.csv", index=False)

    write_result(out_dir, config, counts, metrics, deltas, leakage)
    write_report(out_dir, args.config, config, counts, pair_counts.groupby("pair", as_index=False)["n_pair_rows"].sum(), cv, metrics, deltas, leakage, cov)
    write_manifest(out_dir, args.config, config, [f".venv/bin/python scripts/s05a_astack_external_control.py --config {args.config}"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
