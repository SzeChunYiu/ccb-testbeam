#!/usr/bin/env python3
"""P10b explicit timewalk terms for amplitude-bin phase templates."""

from __future__ import annotations

import argparse
import csv
import json
import math
import subprocess
import time
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

import p10a_conditional_template as p10a


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def collect_downstream_events(config: dict, runs: Iterable[int]) -> pd.DataFrame:
    downstream = list(config["timing"]["downstream_staves"])
    all_staves = {name: int(ch) for name, ch in config["staves"].items()}
    channels = np.asarray([all_staves[name] for name in downstream])
    nsamp = int(config["samples_per_channel"])
    baseline_idx = [int(i) for i in config["baseline_samples"]]
    cut = float(config["amplitude_cut_adc"])
    rows = []
    uid_offset = 0
    for run in sorted({int(r) for r in runs}):
        for batch in p10a.iter_raw(p10a.raw_file(config, run), ["EVENTNO", "EVT", "HRDv"]):
            eventno = np.asarray(batch["EVENTNO"]).astype(int)
            evt = np.asarray(batch["EVT"]).astype(int)
            events = np.stack(batch["HRDv"]).astype(np.float32).reshape(-1, 8, nsamp)
            corrected, amplitude, peak, area = p10a.pulse_quantities(events[:, channels, :], baseline_idx)
            event_mask = (amplitude > cut).all(axis=1)
            for e in np.where(event_mask)[0]:
                uid = f"{run}:{int(eventno[e])}:{int(evt[e])}:{uid_offset + int(e)}"
                for sidx, stave in enumerate(downstream):
                    rows.append(
                        {
                            "event_id": uid,
                            "run": int(run),
                            "eventno": int(eventno[e]),
                            "evt": int(evt[e]),
                            "stave": stave,
                            "waveform": corrected[e, sidx].astype(np.float32),
                            "amplitude_adc": float(amplitude[e, sidx]),
                            "peak_sample": int(peak[e, sidx]),
                            "area_adc_samples": float(area[e, sidx]),
                        }
                    )
            uid_offset += len(eventno)
    return pd.DataFrame(rows)


def empirical_norm_templates(config: dict, table: pd.DataFrame, norm: np.ndarray, train_mask: np.ndarray) -> dict:
    edges = np.asarray(config["template_amplitude_edges_adc"], dtype=float)
    bins = p10a.assign_amp_bins(table["amplitude_adc"].to_numpy(), edges)
    pack = {}
    for stave in config["staves"]:
        stave_train = train_mask & (table["stave"].to_numpy() == stave)
        fallback = np.nanmedian(norm[stave_train], axis=0).astype(np.float32)
        for b in range(len(edges) - 1):
            mask = stave_train & (bins == b)
            pack[(stave, b)] = (
                np.nanmedian(norm[mask], axis=0).astype(np.float32)
                if int(mask.sum()) >= int(config["template_min_bin_pulses"])
                else fallback
            )
    return {"edges": edges, "templates": pack}


def timing_templates_for_pulses(
    config: dict,
    pulses: pd.DataFrame,
    empirical_pack: dict,
    holder: pd.DataFrame,
) -> Tuple[np.ndarray, np.ndarray]:
    edges = empirical_pack["edges"]
    bins = p10a.assign_amp_bins(pulses["amplitude_adc"].to_numpy(), edges)
    empirical = []
    for i, row in enumerate(pulses.itertuples()):
        empirical.append(empirical_pack["templates"][(row.stave, int(bins[i]))])
    tmp_table = pulses[["run", "stave", "amplitude_adc"]].copy()
    X, _ = p10a.condition_matrix(config, tmp_table, holder.attrs["stats"])
    cond = p10a.predict_conditional(holder.attrs["model"], holder.attrs["device"], X, int(config["ml"]["batch_size"]))
    return np.vstack(empirical).astype(np.float32), cond.astype(np.float32)


def positions(config: dict) -> Dict[str, float]:
    return {stave: i * float(config["spacing_cm"]) for i, stave in enumerate(config["timing"]["downstream_staves"])}


def pairwise_residuals(pulses: pd.DataFrame, method_col: str, config: dict, run: Optional[int] = None) -> np.ndarray:
    sub = pulses.copy()
    if run is not None:
        sub = sub[sub["run"] == int(run)].copy()
    sub["tcorr"] = sub[method_col] - sub["stave"].map(positions(config)).astype(float) * float(config["tof_per_cm_ns"])
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
    if len(values) == 0:
        return float("nan")
    q16, q84 = np.percentile(values, [16, 84])
    return float((q84 - q16) / 2.0)


def event_residual_targets(pulses: pd.DataFrame, base_col: str, config: dict) -> np.ndarray:
    sub = pulses.copy()
    sub["tcorr_base"] = sub[base_col] - sub["stave"].map(positions(config)).astype(float) * float(config["tof_per_cm_ns"])
    wide = sub.pivot(index="event_id", columns="stave", values="tcorr_base")
    target = np.full(len(sub), np.nan, dtype=float)
    downstream = list(config["timing"]["downstream_staves"])
    event_lookup = {event_id: wide.loc[event_id] for event_id in wide.index}
    for i, row in enumerate(sub.itertuples()):
        vals = event_lookup[row.event_id]
        others = [s for s in downstream if s != row.stave and pd.notna(vals.get(s, np.nan))]
        if len(others) == 2 and math.isfinite(row.tcorr_base):
            target[i] = float(row.tcorr_base - np.mean([vals[s] for s in others]))
    return target


def explicit_features(config: dict, pulses: pd.DataFrame, feature_set: str) -> np.ndarray:
    amp = pulses["amplitude_adc"].to_numpy(dtype=float)
    log_amp = np.log1p(amp)
    area_over_amp = pulses["area_adc_samples"].to_numpy(dtype=float) / np.maximum(amp, 1.0)
    peak = pulses["peak_sample"].to_numpy(dtype=float)
    staves = list(config["timing"]["downstream_staves"])
    stave_to_i = {stave: i for i, stave in enumerate(staves)}
    one_hot = np.zeros((len(pulses), len(staves)), dtype=float)
    for row, stave in enumerate(pulses["stave"].to_numpy()):
        one_hot[row, stave_to_i[stave]] = 1.0
    base = np.column_stack(
        [
            log_amp,
            log_amp**2,
            1.0 / np.sqrt(np.maximum(amp, 1.0)),
            area_over_amp,
            peak,
        ]
    )
    if feature_set == "amp_poly":
        X = np.hstack([base, one_hot])
        return np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)
    if feature_set == "amp_poly_by_stave":
        interactions = np.hstack([base[:, j : j + 1] * one_hot for j in range(base.shape[1])])
        X = np.hstack([base, one_hot, interactions])
        return np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)
    if feature_set == "amp_bin_by_stave":
        edges = np.asarray(config["template_amplitude_edges_adc"], dtype=float)
        bins = p10a.assign_amp_bins(amp, edges)
        bin_hot = np.zeros((len(pulses), len(edges) - 1), dtype=float)
        bin_hot[np.arange(len(pulses)), bins] = 1.0
        interactions = np.hstack([bin_hot[:, j : j + 1] * one_hot for j in range(bin_hot.shape[1])])
        X = np.hstack([base[:, [0, 2, 3, 4]], one_hot, interactions])
        return np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)
    raise ValueError(f"unknown feature_set {feature_set}")


def ridge_model(alpha: float):
    return make_pipeline(StandardScaler(), Ridge(alpha=max(float(alpha), 1.0e-9), solver="lsqr"))


def corrected_score(pulses: pd.DataFrame, corrected: np.ndarray, config: dict, rows: np.ndarray) -> Tuple[float, int]:
    tmp = pulses.iloc[rows].copy()
    tmp["t_explicit_cv_ns"] = corrected[rows]
    runs = sorted(tmp["run"].unique())
    vals = []
    for run in runs:
        vals.append(pairwise_residuals(tmp, "t_explicit_cv_ns", config, int(run)))
    vals = np.concatenate([v for v in vals if len(v)]) if vals else np.asarray([], dtype=float)
    return sigma68(vals), int(len(vals))


def fit_explicit_timewalk(config: dict, pulses: pd.DataFrame, base_col: str) -> Tuple[pd.DataFrame, pd.DataFrame, dict]:
    targets = event_residual_targets(pulses, base_col, config)
    runs = pulses["run"].to_numpy(dtype=int)
    train_mask = np.isin(runs, np.asarray(config["timing"]["train_runs"], dtype=int)) & np.isfinite(targets)
    idx_train = np.flatnonzero(train_mask)
    groups = runs[idx_train]
    n_splits = min(int(config["explicit_timewalk"]["cv_folds"]), len(np.unique(groups)))
    cv_rows = []
    best = {"score": math.inf, "feature_set": None, "alpha": None}
    for feature_set in config["explicit_timewalk"]["feature_sets"]:
        X = explicit_features(config, pulses, feature_set)
        splitter = GroupKFold(n_splits=n_splits)
        for alpha in config["explicit_timewalk"]["ridge_alphas"]:
            fold_scores = []
            for fold, (tr, va) in enumerate(splitter.split(X[idx_train], targets[idx_train], groups=groups), start=1):
                model = ridge_model(float(alpha))
                model.fit(X[idx_train][tr], targets[idx_train][tr])
                pred = np.full(len(pulses), np.nan, dtype=float)
                pred[idx_train[va]] = model.predict(X[idx_train][va])
                corrected = pulses[base_col].to_numpy(dtype=float) - pred
                score, n_res = corrected_score(pulses, corrected, config, idx_train[va])
                fold_scores.append(score)
                cv_rows.append(
                    {
                        "feature_set": feature_set,
                        "alpha": float(alpha),
                        "fold": int(fold),
                        "sigma68_ns": score,
                        "n_pair_residuals": n_res,
                    }
                )
            mean_score = float(np.nanmean(fold_scores))
            cv_rows.append(
                {
                    "feature_set": feature_set,
                    "alpha": float(alpha),
                    "fold": -1,
                    "sigma68_ns": mean_score,
                    "n_pair_residuals": 0,
                }
            )
            if mean_score < best["score"]:
                best = {"score": mean_score, "feature_set": feature_set, "alpha": float(alpha)}

    X = explicit_features(config, pulses, str(best["feature_set"]))
    model = ridge_model(float(best["alpha"]))
    model.fit(X[train_mask], targets[train_mask])
    pred = model.predict(X)
    out = pulses.copy()
    out["explicit_target_residual_ns"] = targets
    out["explicit_pred_residual_ns"] = pred
    out["t_empirical_timewalk_ns"] = out[base_col].to_numpy(dtype=float) - pred
    best["train_pulses"] = int(train_mask.sum())
    best["train_runs"] = sorted(int(v) for v in np.unique(runs[train_mask]))
    return out, pd.DataFrame(cv_rows), best


def run_shuffled_explicit_control(config: dict, pulses: pd.DataFrame, base_col: str, best: dict) -> float:
    rng = np.random.default_rng(int(config["random_seed"]) + 404)
    targets = event_residual_targets(pulses, base_col, config)
    runs = pulses["run"].to_numpy(dtype=int)
    train_mask = np.isin(runs, np.asarray(config["timing"]["train_runs"], dtype=int)) & np.isfinite(targets)
    shuffled = targets.copy()
    shuffled_train = shuffled[train_mask].copy()
    rng.shuffle(shuffled_train)
    shuffled[train_mask] = shuffled_train
    X = explicit_features(config, pulses, str(best["feature_set"]))
    model = ridge_model(float(best["alpha"]))
    model.fit(X[train_mask], shuffled[train_mask])
    pred = model.predict(X)
    tmp = pulses.copy()
    tmp["t_explicit_shuffled_ns"] = tmp[base_col].to_numpy(dtype=float) - pred
    per_run = [sigma68(pairwise_residuals(tmp, "t_explicit_shuffled_ns", config, int(run))) for run in config["timing"]["heldout_runs"]]
    return float(np.nanmean(per_run))


def bootstrap_run_summary(timing_run: pd.DataFrame, config: dict) -> dict:
    rng = np.random.default_rng(int(config["random_seed"]) + 29)
    value_cols = ["empirical_sigma68_ns", "empirical_timewalk_sigma68_ns", "conditional_sigma68_ns"]
    matrix = timing_run[value_cols].to_numpy(dtype=float)
    boots = []
    for _ in range(int(config["bootstrap_iterations"])):
        boots.append(matrix[rng.integers(0, len(matrix), len(matrix))].mean(axis=0))
    boots = np.asarray(boots)
    summary = {}
    means = matrix.mean(axis=0)
    for i, col in enumerate(value_cols):
        summary[col] = float(means[i])
        summary[f"{col}_ci"] = np.nanquantile(boots[:, i], [0.025, 0.975]).tolist()
    for name, idx in [("timewalk_minus_empirical", 1), ("conditional_minus_timewalk", 2), ("conditional_minus_empirical", 2)]:
        if name == "conditional_minus_empirical":
            delta = matrix[:, 2] - matrix[:, 0]
        elif name == "conditional_minus_timewalk":
            delta = matrix[:, 2] - matrix[:, 1]
        else:
            delta = matrix[:, idx] - matrix[:, 0]
        boots_delta = []
        for _ in range(int(config["bootstrap_iterations"])):
            boots_delta.append(delta[rng.integers(0, len(delta), len(delta))].mean())
        summary[f"delta_{name}_ns"] = float(np.nanmean(delta))
        summary[f"delta_{name}_ci_ns"] = np.nanquantile(boots_delta, [0.025, 0.975]).tolist()
    summary["n_pair_residuals"] = int(timing_run["empirical_sigma68_ns_n"].sum())
    return summary


def timing_by_run(pulses: pd.DataFrame, config: dict) -> Tuple[pd.DataFrame, dict]:
    rows = []
    for run in list(config["timing"]["heldout_runs"]):
        row = {"run": int(run)}
        for name, col in [
            ("empirical_sigma68_ns", "t_empirical_ns"),
            ("empirical_timewalk_sigma68_ns", "t_empirical_timewalk_ns"),
            ("conditional_sigma68_ns", "t_conditional_ns"),
        ]:
            vals = pairwise_residuals(pulses, col, config, int(run))
            row[name] = sigma68(vals)
            row[f"{name}_n"] = int(len(vals))
        rows.append(row)
    run_df = pd.DataFrame(rows)
    return run_df, bootstrap_run_summary(run_df, config)


def write_plots(out_dir: Path, q_run: pd.DataFrame, timing_run: pd.DataFrame, explicit_cv: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(q_run["run"], np.sqrt(q_run["empirical_mse"]), "o-", label="empirical bins")
    ax.plot(q_run["run"], np.sqrt(q_run["conditional_mse"]), "s-", label="conditional MLP")
    ax.set_xlabel("held-out run")
    ax.set_ylabel("q_template RMSE")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_dir / "fig_q_mse_by_run.png", dpi=130)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7.5, 4.2))
    ax.plot(timing_run["run"], timing_run["empirical_sigma68_ns"], "o-", label="empirical bins")
    ax.plot(timing_run["run"], timing_run["empirical_timewalk_sigma68_ns"], "^-", label="explicit timewalk")
    ax.plot(timing_run["run"], timing_run["conditional_sigma68_ns"], "s-", label="conditional MLP")
    ax.set_xlabel("held-out Sample-II run")
    ax.set_ylabel("pairwise sigma68 (ns)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_dir / "fig_timing_by_run.png", dpi=130)
    plt.close(fig)

    means = explicit_cv[explicit_cv["fold"] == -1].copy()
    means["candidate"] = means["feature_set"] + "/a=" + means["alpha"].astype(str)
    means = means.sort_values("sigma68_ns").head(12)
    fig, ax = plt.subplots(figsize=(8.5, 4.2))
    ax.bar(np.arange(len(means)), means["sigma68_ns"])
    ax.set_xticks(np.arange(len(means)))
    ax.set_xticklabels(means["candidate"], rotation=35, ha="right", fontsize=8)
    ax.set_ylabel("train run-CV sigma68 (ns)")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_explicit_timewalk_cv.png", dpi=130)
    plt.close(fig)


def write_report(
    out_dir: Path,
    config: dict,
    config_path: Path,
    repro: pd.DataFrame,
    q_summary: dict,
    timing: dict,
    best_ml: dict,
    best_explicit: dict,
    leakage: pd.DataFrame,
    result: dict,
) -> None:
    lines = [
        "# Study report: P10b - Explicit timewalk terms for amplitude-bin phase templates",
        "",
        f"- **Ticket:** {config['ticket_id']}",
        f"- **Worker:** {config['worker']}",
        "- **Date:** 2026-06-09",
        f"- **Input:** raw B-stack ROOT under `{config['raw_root_dir']}`",
        f"- **Config:** `{config_path}`",
        f"- **Git commit:** {result['git_commit']}",
        "",
        "## Question",
        "",
        "Can explicit train-run-only timewalk terms make the empirical amplitude-bin phase-template timing metric match or beat the P10a conditional timing observation while preserving the S01 q-template advantage?",
        "",
        "## Raw-ROOT reproduction gate",
        "",
        "The selected-pulse count was rerun from raw ROOT before fitting either method.",
        "",
        repro.to_markdown(index=False),
        "",
        "## Methods",
        "",
        "Traditional method: S01-style empirical median templates per B stave and amplitude bin, fit on calibration runs only. For timing, the empirical phase-template pickoff is corrected with explicit same-pulse timewalk terms selected by GroupKFold over train runs and refit only on train runs.",
        "",
        f"Selected explicit correction: feature_set `{best_explicit['feature_set']}`, ridge alpha `{best_explicit['alpha']}`, train pulses `{best_explicit['train_pulses']}`.",
        "",
        "ML method: the P10a conditional MLP maps `[standardized log(amplitude), stave one-hot]` to the waveform template. Hyperparameters were selected by GroupKFold over calibration runs, then the timing model was refit on raw normalized waveforms from calibration runs only.",
        "",
        f"Selected ML model: hidden_dim={best_ml['hidden_dim']}, depth={best_ml['depth']}, train_pulses={best_ml['train_pulses']}, device={best_ml['device']}.",
        "",
        "## Held-out q_template MSE",
        "",
        "Metric: mean squared residual to CFD20-aligned, amplitude-normalized waveforms on analysis runs, summarized by run-bootstrap 95% CIs.",
        "",
        "| Method | Value | 95% CI |",
        "|---|---:|---:|",
        f"| Empirical amplitude-bin template | {q_summary['empirical_mse']:.6g} | [{q_summary['empirical_mse_ci'][0]:.6g}, {q_summary['empirical_mse_ci'][1]:.6g}] |",
        f"| Conditional MLP template | {q_summary['conditional_mse']:.6g} | [{q_summary['conditional_mse_ci'][0]:.6g}, {q_summary['conditional_mse_ci'][1]:.6g}] |",
        f"| Delta conditional - empirical | {q_summary['delta_conditional_minus_empirical']:.6g} | [{q_summary['delta_ci'][0]:.6g}, {q_summary['delta_ci'][1]:.6g}] |",
        "",
        "Verdict on q_template MSE: empirical amplitude bins preserve the S01 advantage." if q_summary["delta_ci"][0] > 0 else "Verdict on q_template MSE: the S01 advantage was not preserved.",
        "",
        "## Downstream timing residual",
        "",
        "Metric: Sample-II B4/B6/B8 all-hit pairwise `sigma68` after geometry correction, evaluated only on held-out runs 58-63 and 65. Values are means of per-run `sigma68`; CIs bootstrap held-out runs.",
        "",
        "| Method | Value | 95% CI |",
        "|---|---:|---:|",
        f"| Empirical amplitude-bin phase template | {timing['empirical_sigma68_ns']:.6g} ns | [{timing['empirical_sigma68_ns_ci'][0]:.6g}, {timing['empirical_sigma68_ns_ci'][1]:.6g}] |",
        f"| Empirical + explicit timewalk terms | {timing['empirical_timewalk_sigma68_ns']:.6g} ns | [{timing['empirical_timewalk_sigma68_ns_ci'][0]:.6g}, {timing['empirical_timewalk_sigma68_ns_ci'][1]:.6g}] |",
        f"| Conditional MLP phase template | {timing['conditional_sigma68_ns']:.6g} ns | [{timing['conditional_sigma68_ns_ci'][0]:.6g}, {timing['conditional_sigma68_ns_ci'][1]:.6g}] |",
        f"| Delta conditional - explicit timewalk | {timing['delta_conditional_minus_timewalk_ns']:.6g} ns | [{timing['delta_conditional_minus_timewalk_ci_ns'][0]:.6g}, {timing['delta_conditional_minus_timewalk_ci_ns'][1]:.6g}] |",
        "",
        "Verdict on timing: explicit timewalk matches or beats the P10a conditional observation." if timing["delta_conditional_minus_timewalk_ci_ns"][0] >= 0 else "Verdict on timing: conditional MLP remains better than explicit timewalk.",
        "",
        "## Leakage checks",
        "",
        leakage.to_markdown(index=False),
        "",
        "Feature audit: the explicit correction uses only same-pulse amplitude-derived terms, area/amp, peak sample, and stave identity. It does not use run number, event id, event order, other-stave timing, or held-out labels as model inputs. The target uses same-event downstream residuals only on train runs for fitting; held-out targets are computed only for diagnostics. The ML comparator uses the P10a stave/log-amplitude inputs.",
        "",
        "## Files",
        "",
        "`result.json`, `manifest.json`, `input_sha256.csv`, run-level CSVs, CV CSVs, leakage checks, and figures are in this report directory. No Monte Carlo was used.",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/p10b_explicit_timewalk_terms.yaml")
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = p10a.load_config(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    table, aligned, norm = p10a.collect_selected(config)
    calib_mask = table["group"].str.endswith("_calib").to_numpy()
    analysis_mask = table["group"].str.endswith("_analysis").to_numpy()
    repro = pd.DataFrame(
        [
            {
                "quantity": "S00/S01 selected B-stave pulses",
                "report_value": int(config["expected_selected_pulses"]),
                "reproduced": int(len(table)),
                "delta": int(len(table) - int(config["expected_selected_pulses"])),
                "tolerance": 0,
                "pass": bool(len(table) == int(config["expected_selected_pulses"])),
            },
            {
                "quantity": "analysis selected rows",
                "report_value": int(config["expected_analysis_rows"]),
                "reproduced": int(analysis_mask.sum()),
                "delta": int(analysis_mask.sum() - int(config["expected_analysis_rows"])),
                "tolerance": 0,
                "pass": bool(int(analysis_mask.sum()) == int(config["expected_analysis_rows"])),
            },
        ]
    )
    repro.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(repro["pass"].all()):
        raise RuntimeError("Raw ROOT reproduction gate failed")

    empirical_pack, template_bins = p10a.build_empirical_templates(config, table, aligned, calib_mask)
    template_bins.to_csv(out_dir / "template_bin_counts.csv", index=False)
    emp_mse = p10a.empirical_mse(table, aligned, empirical_pack)
    best_ml, ml_cv, cond_pred, shuffle_pred = p10a.run_conditional_cv(config, table, aligned, calib_mask)
    ml_cv.to_csv(out_dir / "conditional_ml_cv.csv", index=False)
    cond_mse = p10a.mse_to_prediction(aligned, cond_pred)
    shuffle_mse = p10a.mse_to_prediction(aligned, shuffle_pred)
    q_run, q_summary = p10a.bootstrap_run_means(
        table,
        {"empirical_mse": emp_mse, "conditional_mse": cond_mse, "shuffled_conditional_mse": shuffle_mse},
        analysis_mask,
        config,
    )
    q_run.to_csv(out_dir / "q_template_run_benchmark.csv", index=False)

    empirical_norm = empirical_norm_templates(config, table, norm, calib_mask)
    timing_runs = sorted(set(config["timing"]["train_runs"] + config["timing"]["heldout_runs"]))
    timing_pulses = collect_downstream_events(config, timing_runs)
    _, stats = p10a.condition_matrix(config, table.iloc[np.flatnonzero(calib_mask)])
    X_full, stats = p10a.condition_matrix(config, table, stats)
    valid = np.isfinite(norm)
    final_idx = np.flatnonzero(calib_mask)
    rng = np.random.default_rng(int(config["random_seed"]))
    if len(final_idx) > int(config["ml"]["train_max_pulses"]):
        final_idx = rng.choice(final_idx, int(config["ml"]["train_max_pulses"]), replace=False)
    model, device = p10a.train_conditional_model(
        config,
        X_full,
        norm.astype(np.float32),
        valid,
        final_idx,
        best_ml,
        int(config["ml"]["final_epochs"]),
        int(config["random_seed"]) + 333,
    )
    holder = pd.DataFrame()
    holder.attrs["model"] = model
    holder.attrs["device"] = device
    holder.attrs["stats"] = stats
    grid_cfg = config["timing"]["template_shift_grid"]
    grid = np.arange(float(grid_cfg["min"]), float(grid_cfg["max"]) + 0.5 * float(grid_cfg["step"]), float(grid_cfg["step"]))
    emp_tmpl, cond_tmpl = timing_templates_for_pulses(config, timing_pulses, empirical_norm, holder)
    timing_pulses["t_empirical_ns"] = p10a.template_phase_dynamic(timing_pulses, emp_tmpl, grid, config)
    timing_pulses["t_conditional_ns"] = p10a.template_phase_dynamic(timing_pulses, cond_tmpl, grid, config)
    timing_pulses, explicit_cv, best_explicit = fit_explicit_timewalk(config, timing_pulses, "t_empirical_ns")
    explicit_cv.to_csv(out_dir / "explicit_timewalk_cv.csv", index=False)
    timing_run, timing = timing_by_run(timing_pulses, config)
    timing_run.to_csv(out_dir / "timing_run_benchmark.csv", index=False)

    shuffled_explicit = run_shuffled_explicit_control(config, timing_pulses, "t_empirical_ns", best_explicit)
    train_events = set(timing_pulses.loc[timing_pulses["run"].isin(config["timing"]["train_runs"]), "event_id"])
    heldout_events = set(timing_pulses.loc[timing_pulses["run"].isin(config["timing"]["heldout_runs"]), "event_id"])
    q_overlap = sorted(set(table.loc[calib_mask, "run"].unique()) & set(table.loc[analysis_mask, "run"].unique()))
    leakage = pd.DataFrame(
        [
            {"check": "q_calib_analysis_run_overlap", "value": len(q_overlap), "unit": "runs"},
            {"check": "timing_train_heldout_run_overlap", "value": len(set(config["timing"]["train_runs"]) & set(config["timing"]["heldout_runs"])), "unit": "runs"},
            {"check": "timing_train_heldout_event_overlap", "value": len(train_events & heldout_events), "unit": "events"},
            {"check": "explicit_shuffled_target_sigma68", "value": shuffled_explicit, "unit": "ns"},
            {"check": "explicit_uses_run_or_event_features", "value": 0, "unit": "bool"},
            {"check": "explicit_final_fit_uses_heldout_rows", "value": 0, "unit": "bool"},
            {"check": "conditional_shuffled_q_mse", "value": q_summary["shuffled_conditional_mse"], "unit": "mse"},
        ]
    )
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)

    write_plots(out_dir, q_run, timing_run, explicit_cv)
    with (out_dir / "input_sha256.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["path", "sha256"])
        writer.writeheader()
        for run in p10a.configured_runs(config):
            path = p10a.raw_file(config, run)
            writer.writerow({"path": str(path), "sha256": p10a.sha256_file(path)})

    result = {
        "study": config["study_id"],
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced": True,
        "repro_tolerance": "0 count delta versus S00/S01 selected-pulse gate from raw ROOT",
        "n_selected_pulses": int(len(table)),
        "traditional": {
            "method": "S01 empirical amplitude-bin template plus explicit train-run-only timewalk terms",
            "q_metric": "analysis_run_mean_q_template_mse",
            "q_value": q_summary["empirical_mse"],
            "q_ci": q_summary["empirical_mse_ci"],
            "timing_metric": "heldout_run_mean_pairwise_sigma68_ns",
            "timing_value": timing["empirical_timewalk_sigma68_ns"],
            "timing_ci": timing["empirical_timewalk_sigma68_ns_ci"],
            "best": best_explicit,
        },
        "ml": {
            "method": "conditional MLP template from stave and log amplitude",
            "best": best_ml,
            "q_metric": "analysis_run_mean_q_template_mse",
            "q_value": q_summary["conditional_mse"],
            "q_ci": q_summary["conditional_mse_ci"],
            "timing_metric": "heldout_run_mean_pairwise_sigma68_ns",
            "timing_value": timing["conditional_sigma68_ns"],
            "timing_ci": timing["conditional_sigma68_ns_ci"],
        },
        "falsification": {
            "q_delta_conditional_minus_empirical": q_summary["delta_conditional_minus_empirical"],
            "q_delta_ci": q_summary["delta_ci"],
            "timing_delta_conditional_minus_explicit_timewalk_ns": timing["delta_conditional_minus_timewalk_ns"],
            "timing_delta_conditional_minus_explicit_timewalk_ci_ns": timing["delta_conditional_minus_timewalk_ci_ns"],
            "timing_delta_explicit_timewalk_minus_empirical_ns": timing["delta_timewalk_minus_empirical_ns"],
            "timing_delta_explicit_timewalk_minus_empirical_ci_ns": timing["delta_timewalk_minus_empirical_ci_ns"],
            "explicit_shuffled_target_sigma68": shuffled_explicit,
            "conditional_shuffled_target_q_mse": q_summary["shuffled_conditional_mse"],
            "run_overlap": int(leakage.loc[leakage["check"] == "timing_train_heldout_run_overlap", "value"].iloc[0]),
            "event_overlap": int(leakage.loc[leakage["check"] == "timing_train_heldout_event_overlap", "value"].iloc[0]),
            "n_explicit_candidates": int(
                len(config["explicit_timewalk"]["feature_sets"]) * len(config["explicit_timewalk"]["ridge_alphas"])
            ),
        },
        "explicit_timewalk_matches_or_beats_conditional": bool(timing["delta_conditional_minus_timewalk_ci_ns"][0] >= 0),
        "s01_q_template_advantage_preserved": bool(q_summary["delta_ci"][0] > 0),
        "input_sha256": "input_sha256.csv",
        "git_commit": git_commit(),
        "next_tickets": [
            "P10c: train the explicit amplitude-bin phase correction on Sample-II run 64 only and compare against pooled calibration to isolate sample-transfer effects.",
            "P10d: add an external held-out timing closure using B2/B4/B6/B8 all-hit events to check whether the explicit correction generalizes beyond B4-B8 residual targets.",
        ],
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    write_report(out_dir, config, config_path, repro, q_summary, timing, best_ml, best_explicit, leakage, result)

    outputs = []
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            outputs.append({"path": str(path), "sha256": p10a.sha256_file(path)})
    inputs = []
    for run in p10a.configured_runs(config):
        path = p10a.raw_file(config, run)
        inputs.append({"path": str(path), "sha256": p10a.sha256_file(path)})
    manifest = {
        "study": config["study_id"],
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "git_commit": result["git_commit"],
        "config": str(config_path),
        "config_sha256": p10a.sha256_file(config_path),
        "script": str(Path(__file__)),
        "script_sha256": p10a.sha256_file(Path(__file__)),
        "command": f"/home/billy/anaconda3/bin/python {Path(__file__)} --config {config_path}",
        "random_seed": int(config["random_seed"]),
        "runtime_sec": round(time.time() - t0, 1),
        "inputs": inputs,
        "outputs": outputs,
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
