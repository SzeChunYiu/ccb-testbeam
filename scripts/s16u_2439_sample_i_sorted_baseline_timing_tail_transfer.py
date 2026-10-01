#!/usr/bin/env python3
"""S16u Sample-I transfer of sorted-baseline recoverability proxy signs."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
import platform
import shutil
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Sequence

os.environ.setdefault("MPLCONFIGDIR", "/tmp/testbeam-mplconfig")
os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("MKL_NUM_THREADS", "2")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "2")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import uproot
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

CONFIG_DEFAULT = "configs/s16u_2439_sample_i_sorted_baseline_timing_tail_transfer.json"
S16M_PATH = "scripts/s16m_1781117966_1072_6bc44cc4_support_preserving_pedestal_imputation_timing_correction.py"


def load_module(name: str, path: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


S16M = load_module("s16m_helpers_for_s16t", S16M_PATH)
S16L = S16M.S16L


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


def md_table(df: pd.DataFrame, columns: Sequence[str]) -> str:
    if df.empty:
        return "_No rows._"
    return df.loc[:, list(columns)].to_markdown(index=False)


def stack_obj(values: np.ndarray) -> np.ndarray:
    if len(values) == 0:
        return np.empty((0, 0), dtype=np.float32)
    return np.stack(values).astype(np.float32)


def sorted_file(config: dict, run: int) -> Path:
    return Path(config["sorted_root_dir"]) / ("hrdb_run_%04d-sorted.root" % int(run))


def input_hashes(config: dict) -> pd.DataFrame:
    rows = []
    for run in S16L.configured_runs(config):
        for role, path in [("raw", S16L.raw_file(config, run)), ("sorted", sorted_file(config, run))]:
            if path.exists():
                rows.append({"run": int(run), "role": role, "path": str(path), "sha256": sha256_file(path), "bytes": path.stat().st_size})
    return pd.DataFrame(rows)


def reproduce_counts(config: dict, subset_key: str = "sample_i_analysis") -> pd.DataFrame:
    baseline_idx = [int(i) for i in config["baseline_samples"]]
    staves = {name: int(ch) for name, ch in config["staves"].items()}
    stave_names = list(staves.keys())
    channels = np.asarray([staves[name] for name in stave_names])
    nsamp = int(config["samples_per_channel"])
    cut = float(config["amplitude_cut_adc"])
    total = 0
    subset_runs = set(int(r) for r in config["run_groups"][subset_key])
    subset = {"selected_pulses": 0, **{name: 0 for name in stave_names}}

    for run in S16L.configured_runs(config):
        path = S16L.raw_file(config, run)
        if not path.exists():
            raise FileNotFoundError(path)
        tree = uproot.open(path)["h101"]
        for batch in tree.iterate(["HRDv"], step_size=20000, library="np"):
            events = np.stack(batch["HRDv"]).astype(np.float64).reshape(-1, 8, nsamp)
            waveforms = events[:, channels, :]
            seed = np.median(waveforms[..., baseline_idx], axis=-1)
            corrected = waveforms - seed[..., None]
            amplitude = corrected.max(axis=-1)
            selected = amplitude > cut
            total += int(selected.sum())
            if int(run) in subset_runs:
                subset["selected_pulses"] += int(selected.sum())
                for i, stave in enumerate(stave_names):
                    subset[stave] += int(selected[:, i].sum())

    rows = [
        {
            "quantity": "total selected B-stave pulses",
            "report_value": int(config["expected_counts"]["total_selected_pulses"]),
            "reproduced": int(total),
            "tolerance": 0,
        }
    ]
    for key, value in config["expected_counts"][subset_key].items():
        rows.append(
            {
                "quantity": f"{subset_key} {key}",
                "report_value": int(value),
                "reproduced": int(subset[key]),
                "tolerance": 0,
            }
        )
    out = pd.DataFrame(rows)
    out["delta"] = out["reproduced"] - out["report_value"]
    out["pass"] = out["delta"].abs() <= out["tolerance"]
    return out


def sorted_recoverability_features(config: dict) -> pd.DataFrame:
    staves = list(config["staves"].keys())
    channels = np.asarray([int(config["staves"][s]) for s in staves], dtype=int)
    nsamp = int(config["samples_per_channel"])
    pre_idx = np.asarray(config["pretrigger_samples"], dtype=int)
    cut = float(config["amplitude_cut_adc"])
    rows: List[pd.DataFrame] = []
    pulse_base = 0
    for run in [int(r) for r in config["analysis_runs"]]:
        raw_tree = uproot.open(S16L.raw_file(config, run))["h101"]
        sorted_tree = uproot.open(sorted_file(config, run))["tree"]
        if int(raw_tree.num_entries) != int(sorted_tree.num_entries):
            raise RuntimeError(f"raw/sorted entry count mismatch for run {run}")
        for start in range(0, int(raw_tree.num_entries), 20000):
            stop = min(start + 20000, int(raw_tree.num_entries))
            raw = raw_tree.arrays(["EVT", "HRDv"], entry_start=start, entry_stop=stop, library="np")
            srt = sorted_tree.arrays(
                ["hrdEvtNo", "hrd.baseline", "hrd.trap", "hrdMax", "hrdTrMax", "hrdMaxTS"],
                entry_start=start,
                entry_stop=stop,
                library="np",
            )
            evt = np.asarray(raw["EVT"], dtype=np.int64)
            if not np.array_equal(evt, np.asarray(srt["hrdEvtNo"], dtype=np.int64)):
                raise RuntimeError(f"raw EVT and sorted hrdEvtNo mismatch for run {run} entries {start}:{stop}")
            events = stack_obj(raw["HRDv"]).reshape(-1, 8, nsamp)
            waves = events[:, channels, :]
            raw_pre = np.median(waves[:, :, pre_idx], axis=-1)
            corrected = waves - raw_pre[:, :, None]
            amplitude = corrected.max(axis=-1)
            peak = corrected.argmax(axis=-1)
            selected = amplitude > cut
            event_idx, stave_idx = np.where(selected)
            if len(event_idx) == 0:
                continue
            ch = channels[stave_idx]
            baseline = stack_obj(srt["hrd.baseline"]).reshape(-1, 8, nsamp)[:, :, 0][event_idx, ch]
            trap = stack_obj(srt["hrd.trap"]).reshape(-1, 8, nsamp)[event_idx, ch, :]
            hmax = stack_obj(srt["hrdMax"])[event_idx, ch]
            trmax = stack_obj(srt["hrdTrMax"])[event_idx, ch]
            max_ts = stack_obj(srt["hrdMaxTS"])[event_idx, ch]
            target = raw_pre[event_idx, stave_idx]
            residual = baseline - target
            rec = pd.DataFrame(
                {
                    "pulse_index": np.arange(pulse_base, pulse_base + len(event_idx), dtype=int),
                    "sorted_baseline_residual_adc": residual,
                    "sorted_baseline_abs_residual_adc": np.abs(residual),
                    "sorted_baseline_adc": baseline,
                    "sorted_hrdMax_adc": hmax,
                    "sorted_hrdTrMax_adc": trmax,
                    "sorted_hrdMaxTS": max_ts.astype(float),
                    "sorted_trap_pre_ptp_adc": np.ptp(trap[:, pre_idx], axis=1),
                    "sorted_trap_late_mean_adc": trap[:, -4:].mean(axis=1),
                    "sorted_trap_std_adc": trap.std(axis=1),
                    "raw_peak_sample_check": peak[event_idx, stave_idx].astype(float),
                }
            )
            # Compatibility names let the S16m pair builder consume this as a
            # nuisance channel while preserving the sorted-baseline semantics.
            rec["line3_err_mean_adc"] = rec["sorted_baseline_residual_adc"]
            rec["line3_abs_err_mean_adc"] = rec["sorted_baseline_abs_residual_adc"]
            rec["line3_abs_err_max_adc"] = rec["sorted_baseline_abs_residual_adc"]
            rec["mean3_err_mean_adc"] = rec["sorted_baseline_residual_adc"]
            rec["mean3_abs_err_mean_adc"] = rec["sorted_baseline_abs_residual_adc"]
            rec["mean3_abs_err_max_adc"] = rec["sorted_baseline_abs_residual_adc"]
            rec["median3_err_mean_adc"] = rec["sorted_baseline_residual_adc"]
            rec["median3_abs_err_mean_adc"] = rec["sorted_baseline_abs_residual_adc"]
            rec["median3_abs_err_max_adc"] = rec["sorted_baseline_abs_residual_adc"]
            rec["target_excluded_spread_mean_adc"] = rec["sorted_trap_pre_ptp_adc"]
            rec["target_adc_std_adc"] = rec["sorted_trap_std_adc"]
            rec["visible_range_mean_adc"] = rec["sorted_trap_pre_ptp_adc"]
            rows.append(rec)
            pulse_base += len(event_idx)
    return pd.concat(rows, ignore_index=True)


def build_pairs_for_runs(config: dict, runs: Sequence[int]) -> pd.DataFrame:
    local = dict(config)
    local["analysis_runs"] = [int(r) for r in runs]
    local["heldout_runs"] = [int(r) for r in runs]
    meta, waves = S16L.load_selected_pulses(local)
    nuisance = sorted_recoverability_features(local)
    if len(meta) != len(nuisance):
        raise RuntimeError(f"pulse feature mismatch for runs {runs}: meta={len(meta)} nuisance={len(nuisance)}")
    return S16M.build_pairs(meta, nuisance, local)


def coefficient_sign_transfer(sample_i_pairs: pd.DataFrame, sample_ii_pairs: pd.DataFrame, config: dict) -> pd.DataFrame:
    proxy_cols = [
        "nuisance_abs_max_adc",
        "nuisance_abs_mean_adc",
        "nuisance_signed_diff_adc",
        "sorted_baseline_residual_adc_a",
        "sorted_baseline_residual_adc_b",
        "sorted_baseline_abs_residual_adc_a",
        "sorted_baseline_abs_residual_adc_b",
    ]
    cols = [c for c in proxy_cols if c in sample_i_pairs.columns and c in sample_ii_pairs.columns]
    rows = []
    for label, frame in [("Sample-I", sample_i_pairs), ("Sample-II", sample_ii_pairs)]:
        x = frame.loc[:, cols].replace([np.inf, -np.inf], np.nan).copy()
        x = x.fillna(x.median(axis=0).fillna(0.0))
        y = frame["raw_residual_ns"].to_numpy(dtype=float)
        model = make_pipeline(StandardScaler(), Ridge(alpha=float(config["models"]["ridge_alpha"])))
        model.fit(x, y)
        coefs = model.named_steps["ridge"].coef_
        for col, coef in zip(cols, coefs):
            rows.append(
                {
                    "domain": label,
                    "feature": col,
                    "standardized_ridge_coef_ns": float(coef),
                    "sign": "positive" if coef > 0 else ("negative" if coef < 0 else "zero"),
                    "n_pairs": int(len(frame)),
                }
            )
    out = pd.DataFrame(rows)
    wide = out.pivot(index="feature", columns="domain", values=["standardized_ridge_coef_ns", "sign", "n_pairs"]).reset_index()
    wide.columns = ["_".join([str(x) for x in col if str(x)]) for col in wide.columns.to_flat_index()]
    wide["sign_transfers"] = wide["sign_Sample-I"] == wide["sign_Sample-II"]
    return wide


def control_columns(pairs: pd.DataFrame) -> List[str]:
    names = S16M.feature_columns(pairs)
    forbidden = ("nuisance", "line3", "mean3", "median3", "target_", "visible_", "sorted_")
    return [c for c in names if not any(token in c for token in forbidden)]


def proxy_columns(pairs: pd.DataFrame) -> List[str]:
    return S16M.feature_columns(pairs)


def score_frame(test: pd.DataFrame, method: str, pred: np.ndarray) -> pd.DataFrame:
    out = test[["run", "event_id", "pair", "raw_residual_ns"]].copy()
    out["method"] = method
    out["predicted_correction_ns"] = np.asarray(pred, dtype=float)
    out["corrected_residual_ns"] = out["raw_residual_ns"] - out["predicted_correction_ns"]
    return out


def fit_ablation_models(pairs: pd.DataFrame, config: dict) -> pd.DataFrame:
    scored = []
    for run in sorted(pairs["run"].unique()):
        train = pairs[pairs["run"] != run].reset_index(drop=True)
        test = pairs[pairs["run"] == run].reset_index(drop=True)
        for family, cols in [("controls_only", control_columns(pairs)), ("plus_sorted_proxy", proxy_columns(pairs))]:
            xtr, xte = S16M.clean_xy(train, test, cols)
            y = train["raw_residual_ns"].to_numpy(dtype=float)
            ridge = make_pipeline(StandardScaler(), Ridge(alpha=float(config["models"]["ridge_alpha"])))
            ridge.fit(xtr, y)
            scored.append(score_frame(test, f"ridge_{family}", ridge.predict(xte)))
            hgb = HistGradientBoostingRegressor(
                max_iter=int(config["models"]["hgb_max_iter"]),
                learning_rate=float(config["models"]["hgb_learning_rate"]),
                max_leaf_nodes=int(config["models"]["hgb_max_leaf_nodes"]),
                l2_regularization=0.01,
                random_state=int(config["models"]["random_seed"]) + int(run),
            )
            hgb.fit(xtr, y)
            scored.append(score_frame(test, f"gradient_boosted_trees_{family}", hgb.predict(xte)))
    return pd.concat(scored, ignore_index=True)


def paired_delta_bootstrap(scored: pd.DataFrame, config: dict) -> pd.DataFrame:
    rng = np.random.default_rng(int(config["models"]["random_seed"]) + 250)
    runs = np.asarray(sorted(scored["run"].unique()), dtype=int)
    pairs = [
        ("ridge_plus_sorted_proxy", "ridge_controls_only"),
        ("gradient_boosted_trees_plus_sorted_proxy", "gradient_boosted_trees_controls_only"),
        ("traditional_binned_median", "uncorrected"),
        ("nuisance_gated_pair_cnn", "one_dimensional_cnn"),
    ]
    by_method_run = {(m, int(r)): g for (m, r), g in scored.groupby(["method", "run"])}
    rows = []
    for augmented, base in pairs:
        if augmented not in scored["method"].unique() or base not in scored["method"].unique():
            continue
        vals = []
        for _ in range(int(config["bootstrap_replicates"])):
            chosen = rng.choice(runs, size=len(runs), replace=True)
            aug = pd.concat([by_method_run[(augmented, int(r))] for r in chosen], ignore_index=True)
            ctl = pd.concat([by_method_run[(base, int(r))] for r in chosen], ignore_index=True)
            vals.append(S16M.metric_dict(aug["corrected_residual_ns"].to_numpy())["sigma68_ns"] - S16M.metric_dict(ctl["corrected_residual_ns"].to_numpy())["sigma68_ns"])
        point_aug = S16M.metric_dict(scored[scored["method"] == augmented]["corrected_residual_ns"].to_numpy())["sigma68_ns"]
        point_ctl = S16M.metric_dict(scored[scored["method"] == base]["corrected_residual_ns"].to_numpy())["sigma68_ns"]
        rows.append(
            {
                "augmented_method": augmented,
                "baseline_method": base,
                "delta_sigma68_ns": float(point_aug - point_ctl),
                "delta_sigma68_ns_ci_low": float(np.percentile(vals, 2.5)),
                "delta_sigma68_ns_ci_high": float(np.percentile(vals, 97.5)),
            }
        )
    return pd.DataFrame(rows)


def make_plots(metrics: pd.DataFrame, scored: pd.DataFrame, out_dir: Path):
    order = metrics.sort_values("sigma68_ns")["method"].tolist()
    fig, ax = plt.subplots(figsize=(9.5, 5.5))
    ax.barh(metrics.set_index("method").loc[order].index, metrics.set_index("method").loc[order]["sigma68_ns"], color="#4f6f7f")
    ax.set_xlabel("sigma68 corrected pair residual (ns)")
    ax.set_title("S16u Sample-I sorted-baseline proxy timing-tail benchmark")
    fig.tight_layout()
    fig.savefig(out_dir / "metric_summary.png", dpi=180)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 4.8))
    for method in ["uncorrected", "ridge_controls_only", "ridge_plus_sorted_proxy", str(metrics.sort_values("sigma68_ns").iloc[0]["method"])]:
        data = scored[scored["method"] == method]["corrected_residual_ns"].clip(-2, 2)
        if len(data):
            ax.hist(data, bins=80, histtype="step", density=True, label=method)
    ax.set_xlabel("corrected residual, clipped to +/-2 ns")
    ax.set_ylabel("density")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out_dir / "residual_distributions.png", dpi=180)
    plt.close(fig)


def write_report(
    config: dict,
    result: dict,
    reproduction: pd.DataFrame,
    metrics: pd.DataFrame,
    deltas: pd.DataFrame,
    per_run: pd.DataFrame,
    proxy_summary: pd.DataFrame,
    sign_transfer: pd.DataFrame,
    out_dir: Path,
):
    winner = result["winner"]
    report = f"""# S16u: Sample-I Transfer of Sorted-Baseline Timing-Tail Nuisance

## Abstract

Ticket `#2439` asks for the sorted-baseline residual timing-tail nuisance test on Sample-I runs with the same S02/S04 controls used in S16t, plus a comparison of proxy coefficient signs across Sample-I and Sample-II. Raw ROOT selected-pulse counts reproduce exactly, then downstream S02 CFD20 pair residuals are refit in leave-one-run-out Sample-I folds. The named winner in `result.json` is **{winner}**. The direct transfer audit is the sign agreement table between standardized Sample-I and Sample-II ridge coefficients on sorted-baseline proxy features.

## Raw ROOT Reproduction

The reproduction gate reads `h101/HRDv` from `{config["raw_root_dir"]}`, applies the B-stack stave map, four-sample median pedestal, and the `> {config["amplitude_cut_adc"]:.0f}` ADC selected-pulse threshold. Sorted ROOT files are used only after this gate to compute nuisance covariates. The Sample-I analysis subset is runs `{config["run_groups"]["sample_i_analysis"]}`.

{md_table(reproduction, ["quantity", "report_value", "reproduced", "delta", "tolerance", "pass"])}

## Estimand and Equations

For downstream pair `(a,b)` in event `i`,

`r_i = (t_i,a^CFD20 - t_i,b^CFD20) - (x_a - x_b) tau`,

where `tau = {config["tof_per_cm_ns"]}` ns/cm and CFD20 uses the original raw four-sample median baseline. A correction model estimates `c_i = E[r_i | z_i]`; the scored residual is `r_i - c_i`. The robust width is

`sigma68(r) = (Q84(r) - Q16(r)) / 2`.

The sorted-baseline residual proxy for pulse `p` is

`u_p = b_p^sorted - median(x_p,0:3)`.

Pair-level nuisance features use `max(|u_a|, |u_b|)`, `0.5(|u_a| + |u_b|)`, and `u_a - u_b`, plus sorted trapezoid sidebands. The control-only ablation removes all sorted/proxy terms while keeping pair identity, amplitudes, amplitude ratio/sum, peak samples, and raw pretrigger dispersion.

## Methods

The traditional comparator is a run-excluded hierarchical binned median correction over pair identity, amplitude-ratio bin, raw pretrigger-dispersion bin, and sorted-proxy magnitude bin, with fallbacks to coarser cells. ML/NN methods are ridge, histogram gradient-boosted trees, MLP, a 1D pair CNN over raw waveform pairs, and the new nuisance-gated pair CNN. Additional ridge and boosted-tree ablations are trained twice: controls only and controls plus sorted proxy. Model training and standardization are refit inside each leave-one-run-out fold.

Bootstrap intervals resample held-out Sample-I runs with replacement and preserve paired method predictions within each sampled run. For coefficient-transfer signs, a standardized ridge model is fit once on Sample-I pair rows and once on the Sample-II S16t companion rows using only sorted-proxy features; the sign comparison is diagnostic and not used to select the winner.

## Proxy Distribution

{md_table(proxy_summary, ["quantity", "value"])}

## Primary Results

{md_table(metrics, ["method", "n_pairs", "sigma68_ns", "sigma68_ns_ci_low", "sigma68_ns_ci_high", "tail_abs_gt_0p5_ns", "tail_abs_gt_0p5_ns_ci_low", "tail_abs_gt_0p5_ns_ci_high", "bias_ns", "bias_ns_ci_low", "bias_ns_ci_high"])}

## Paired Ablations

Negative deltas mean the sorted-proxy or gated method improved the robust residual width relative to its paired baseline.

{md_table(deltas, ["augmented_method", "baseline_method", "delta_sigma68_ns", "delta_sigma68_ns_ci_low", "delta_sigma68_ns_ci_high"])}

## Sample-I/Sample-II Coefficient Sign Transfer

The table compares standardized ridge coefficients for sorted-baseline proxy features only. A transferred sign supports a period-stable recoverability diagnostic; a sign flip suggests the proxy is more period-local or confounded with period-specific timing structure.

{md_table(sign_transfer, ["feature", "standardized_ridge_coef_ns_Sample-I", "sign_Sample-I", "standardized_ridge_coef_ns_Sample-II", "sign_Sample-II", "sign_transfers"])}

## Run-Held-Out Stability

{md_table(per_run, ["method", "run", "n_pairs", "sigma68_ns", "tail_abs_gt_0p5_ns", "bias_ns"])}

## Systematics and Caveats

The study is run-split, not event-split. No method receives run number, event identifiers, or peer residuals as features. The response is pairwise residual symmetry, not external time-of-flight truth. The sorted residual proxy uses raw pretrigger samples for diagnostic labeling, so it tests whether recoverability metadata predicts timing tails; it does not justify substituting sorted pedestals into CFD timing. Sample-I has more held-out run units than Sample-II but much lower downstream support in several runs, so the bootstrap is dominated by high-support runs 45, 50, 53, 54, and 56. The coefficient sign table is descriptive; it is not a causal proof because Sample-I and Sample-II differ in current state, penetration topology, and B2 dominance. The CNNs are intentionally compact and CPU reproducible, so they are capacity checks rather than exhaustive architecture searches.

## Conclusion

The decisive ticket question is whether the Sample-I proxy relation has the same sign structure as Sample-II and whether it improves timing residuals beyond amplitude and peak-time controls. The result table and `result.json` name `{winner}` as the lowest-sigma68 Sample-I correction method, while the paired-ablation and coefficient-transfer tables quantify the incremental sorted-baseline information gain and its period stability.
"""
    (out_dir / "REPORT.md").write_text(report, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=CONFIG_DEFAULT)
    args = parser.parse_args()
    start = time.time()
    config_path = Path(args.config)
    config = json.loads(config_path.read_text())
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    reproduction = reproduce_counts(config, "sample_i_analysis")
    reproduction.to_csv(out_dir / "reproduction_counts.csv", index=False)
    if not bool(reproduction["pass"].all()):
        raise RuntimeError("raw ROOT reproduction failed")
    hashes = input_hashes(config)
    hashes.to_csv(out_dir / "input_sha256.csv", index=False)
    meta, waves = S16L.load_selected_pulses(config)
    nuisance = sorted_recoverability_features(config)
    nuisance.to_csv(out_dir / "sorted_recoverability_features.csv.gz", index=False)
    if len(meta) != len(nuisance):
        raise RuntimeError(f"pulse feature mismatch: meta={len(meta)} nuisance={len(nuisance)}")
    pairs = S16M.build_pairs(meta, nuisance, config)
    pairs.to_csv(out_dir / "pair_rows.csv.gz", index=False)

    full_scored = S16M.fit_fold_models(pairs, waves, config)
    ablation_scored = fit_ablation_models(pairs, config)
    scored = pd.concat([full_scored, ablation_scored], ignore_index=True)
    scored.to_csv(out_dir / "method_predictions.csv.gz", index=False)

    metrics = S16M.summarize_metrics(scored)
    boot = S16M.bootstrap_summary(scored, int(config["bootstrap_replicates"]), int(config["models"]["random_seed"]))
    metrics_ci = S16M.add_cis(metrics, boot).sort_values("sigma68_ns").reset_index(drop=True)
    per_run = S16M.per_run_metrics(scored)
    deltas = paired_delta_bootstrap(scored, config)
    sample_ii_pairs = build_pairs_for_runs(config, config["run_groups"]["sample_ii_analysis"])
    sign_transfer = coefficient_sign_transfer(pairs, sample_ii_pairs, config)
    metrics_ci.to_csv(out_dir / "method_metrics.csv", index=False)
    per_run.to_csv(out_dir / "per_run_metrics.csv", index=False)
    boot.to_csv(out_dir / "bootstrap_metrics.csv", index=False)
    deltas.to_csv(out_dir / "paired_ablation_deltas.csv", index=False)
    sign_transfer.to_csv(out_dir / "coefficient_sign_transfer.csv", index=False)
    proxy_summary = pd.DataFrame(
        [
            {"quantity": "selected Sample-I pulses with sorted proxy", "value": float(len(nuisance))},
            {"quantity": "median abs sorted-baseline residual ADC", "value": float(nuisance["sorted_baseline_abs_residual_adc"].median())},
            {"quantity": "p90 abs sorted-baseline residual ADC", "value": float(nuisance["sorted_baseline_abs_residual_adc"].quantile(0.90))},
            {"quantity": "mean signed sorted-baseline residual ADC", "value": float(nuisance["sorted_baseline_residual_adc"].mean())},
            {"quantity": "timing pairs", "value": float(len(pairs))},
            {"quantity": "Sample-II companion timing pairs for sign transfer", "value": float(len(sample_ii_pairs))},
        ]
    )
    proxy_summary.to_csv(out_dir / "proxy_summary.csv", index=False)
    winner = str(metrics_ci[metrics_ci["method"] != "uncorrected"].iloc[0]["method"])
    make_plots(metrics_ci, scored, out_dir)

    result = {
        "study": config["study"],
        "ticket": config["ticket"],
        "worker": config["worker"],
        "title": config["title"],
        "status": "complete",
        "winner": winner,
        "winner_metrics": metrics_ci[metrics_ci["method"] == winner].iloc[0].to_dict(),
        "primary_metric": config["primary_metric"],
        "raw_reproduction": {"all_pass": bool(reproduction["pass"].all()), "rows": reproduction.to_dict(orient="records")},
        "paired_ablation_deltas": deltas.to_dict(orient="records"),
        "methods": sorted(scored["method"].unique().tolist()),
        "split": "leave-one-run-out over Sample-I analysis runs",
        "bootstrap": {"unit": "held-out run", "replicates": int(config["bootstrap_replicates"]), "paired": True},
        "coefficient_sign_transfer": sign_transfer.to_dict(orient="records"),
        "n_pairs": int(len(pairs)),
        "input_root_files": int(len(hashes)),
        "git_commit": git_commit(),
        "runtime_seconds": round(time.time() - start, 3),
        "outputs": [
            "REPORT.md",
            "result.json",
            "reproduction_counts.csv",
            "input_sha256.csv",
            "sorted_recoverability_features.csv.gz",
            "pair_rows.csv.gz",
            "method_predictions.csv.gz",
            "method_metrics.csv",
            "per_run_metrics.csv",
            "bootstrap_metrics.csv",
            "paired_ablation_deltas.csv",
            "coefficient_sign_transfer.csv",
            "proxy_summary.csv",
            "metric_summary.png",
            "residual_distributions.png",
        ],
        "next_tickets": config.get("next_tickets", [])[:1],
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    shutil.copy2(config_path, out_dir / "config.json")
    write_report(config, result, reproduction, metrics_ci, deltas, per_run, proxy_summary, sign_transfer, out_dir)
    manifest = {
        "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "git_commit": git_commit(),
        "command": "python scripts/s16u_2439_sample_i_sorted_baseline_timing_tail_transfer.py --config " + str(config_path),
        "files": {p.name: sha256_file(p) for p in out_dir.iterdir() if p.is_file()},
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({"winner": winner, "out_dir": str(out_dir), "n_pairs": int(len(pairs))}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
