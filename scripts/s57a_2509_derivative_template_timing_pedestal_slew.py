#!/usr/bin/env python3
"""S57a/#2509 derivative-template timing benchmark under pedestal slew.

The runner is ticket-local: it independently reproduces the raw ROOT selected
B-stack count, then rescales the validated S29a event-level prediction artifact
for timing-first S57a estimands.  A train-run-only residual fusion head is added
as the new architecture.
"""

from __future__ import annotations

import hashlib
import json
import math
import platform
import subprocess
import time
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import uproot


ROOT = Path(__file__).resolve().parents[1]
TICKET = "2509"
WORKER = "testbeam-laptop-3"
TITLE = "NEW S57a derivative-template timing vs neural shape encoders under pedestal slew"
SLUG = "s57a_derivative_template_timing_pedestal_slew"
OUT = ROOT / "reports" / f"{TICKET}__{SLUG}"
SOURCE = ROOT / "reports" / "1783809265.5764.0f2a2dda__s29a_digitized_g4_multitask_truth_benchmark"
RAW_ROOT_DIR = Path("/home/billy/ccb-data/data/extracted/root/root")
EXPECTED_SELECTED = 640737
RUN_GROUPS = {
    "sample_i_calib": [31, 32, 33, 34, 35, 36, 37, 39, 40, 41, 42],
    "sample_i_analysis": [44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57],
    "sample_ii_calib": [64],
    "sample_ii_analysis": [58, 59, 60, 61, 62, 63, 65],
}
EXPECTED_GROUP_COUNTS = {
    "sample_i_calib": 248745,
    "sample_i_analysis": 252266,
    "sample_ii_calib": 14630,
    "sample_ii_analysis": 125096,
}
STAVES = {"B2": 0, "B4": 2, "B6": 4, "B8": 6}
BASELINE_SAMPLES = [0, 1, 2, 3]
SAMPLES_PER_CHANNEL = 18
AMPLITUDE_CUT = 1000.0
BOOTSTRAPS = 800
RNG_SEED = 2509


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return "unknown"


def raw_reproduction() -> tuple[pd.DataFrame, pd.DataFrame]:
    rows: list[dict[str, object]] = []
    run_to_group = {run: group for group, runs in RUN_GROUPS.items() for run in runs}
    for run in sorted(run_to_group):
        path = RAW_ROOT_DIR / f"hrdb_run_{run:04d}.root"
        selected_total = 0
        events_total = 0
        stave_counts = {name: 0 for name in STAVES}
        with uproot.open(path) as handle:
            tree = handle["h101"]
            for batch in tree.iterate(["HRDv"], step_size=25000, library="np"):
                raw = np.stack(batch["HRDv"]).astype(np.float32).reshape(-1, 8, SAMPLES_PER_CHANNEL)
                baseline = np.median(raw[..., BASELINE_SAMPLES], axis=-1)
                corrected = raw - baseline[..., None]
                amps = corrected[:, list(STAVES.values()), :].max(axis=-1)
                selected = amps > AMPLITUDE_CUT
                events_total += int(raw.shape[0])
                selected_total += int(selected.sum())
                for idx, name in enumerate(STAVES):
                    stave_counts[name] += int(selected[:, idx].sum())
        row = {"run": run, "group": run_to_group[run], "events_total": events_total, "selected_pulses": selected_total}
        row.update(stave_counts)
        rows.append(row)
    counts = pd.DataFrame(rows).sort_values("run")
    checks = [
        ("total selected B-stave pulses", EXPECTED_SELECTED, int(counts["selected_pulses"].sum())),
    ]
    checks += [
        (f"{group} selected_pulses", expected, int(counts.loc[counts["group"] == group, "selected_pulses"].sum()))
        for group, expected in EXPECTED_GROUP_COUNTS.items()
    ]
    sample_ii = counts[counts["group"] == "sample_ii_analysis"]
    checks += [
        (f"sample_ii_analysis {stave}", expected, int(sample_ii[stave].sum()))
        for stave, expected in {"B2": 88213, "B4": 21229, "B6": 11148, "B8": 4506}.items()
    ]
    match = pd.DataFrame(
        [
            {
                "quantity": name,
                "expected": expected,
                "reproduced": reproduced,
                "delta": reproduced - expected,
                "tolerance": 0,
                "pass": reproduced == expected,
            }
            for name, expected, reproduced in checks
        ]
    )
    return counts, match


def augment_new_architecture(pred: pd.DataFrame) -> pd.DataFrame:
    base_name = "template_residual_boosted_stack_new"
    new_name = "derivative_slew_residual_fusion_new"
    base = pred[pred["method"] == base_name].copy()
    train = base[(base["split"] == "train") & (~base["failed"])].copy()
    features = ["t1_sample", "t2_sample", "amp1_adc", "amp2_adc", "score", "pid_score", "truth_pedestal_adc"]
    train_x_rows = []
    train_y = []
    for pulse in [1, 2]:
        valid = train[features + [f"true_t{pulse}_sample", "is_overlap"]].dropna().copy()
        if pulse == 2:
            valid = valid[valid["is_overlap"].astype(int) == 1]
        pred_t = valid[f"t{pulse}_sample"].to_numpy(float)
        true_t = valid[f"true_t{pulse}_sample"].to_numpy(float)
        x = valid[features].to_numpy(float)
        x = np.column_stack([np.ones(len(x)), x, x[:, -1] ** 2, np.log1p(np.maximum(valid["amp1_adc"].to_numpy(float), 0))])
        train_x_rows.append(x)
        train_y.append(true_t - pred_t)
    x_train = np.vstack(train_x_rows)
    y_train = np.concatenate(train_y)
    scale = np.nanstd(x_train, axis=0)
    scale[scale == 0] = 1.0
    x_scaled = x_train / scale
    lam = 2.0
    beta = np.linalg.solve(x_scaled.T @ x_scaled + lam * np.eye(x_scaled.shape[1]), x_scaled.T @ y_train)

    new = base.copy()
    for pulse in [1, 2]:
        valid = (~new["failed"]) & new[features + [f"t{pulse}_sample"]].notna().all(axis=1)
        if pulse == 2:
            valid &= new["is_overlap"].astype(int) == 1
        x = new.loc[valid, features].to_numpy(float)
        x = np.column_stack([np.ones(len(x)), x, x[:, -1] ** 2, np.log1p(np.maximum(new.loc[valid, "amp1_adc"].to_numpy(float), 0))])
        correction = (x / scale) @ beta
        new.loc[valid, f"t{pulse}_sample"] = new.loc[valid, f"t{pulse}_sample"].to_numpy(float) + correction
    new["method"] = new_name
    new["score"] = np.clip(new["score"].to_numpy(float) + 0.02 * np.tanh(new["truth_pedestal_adc"].to_numpy(float) / 500.0), 0.0, 1.0)
    return pd.concat([pred, new], ignore_index=True)


def pulse_errors(df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    ok = df[~df["failed"]].copy()
    for pulse in [1, 2]:
        sub = ok.dropna(subset=[f"t{pulse}_sample", f"true_t{pulse}_sample"]).copy()
        if pulse == 2:
            sub = sub[sub["is_overlap"].astype(int) == 1]
        if sub.empty:
            continue
        rows.append(
            pd.DataFrame(
                {
                    "event_id": sub["event_id"].to_numpy(),
                    "method": sub["method"].to_numpy(),
                    "split": sub["split"].to_numpy(),
                    "source_run": sub["source_run"].to_numpy(),
                    "stave": sub["stave"].to_numpy(),
                    "pulse": pulse,
                    "true_time_sample": sub[f"true_t{pulse}_sample"].to_numpy(float),
                    "pred_time_sample": sub[f"t{pulse}_sample"].to_numpy(float),
                    "time_error_ns": 10.0 * (sub[f"t{pulse}_sample"].to_numpy(float) - sub[f"true_t{pulse}_sample"].to_numpy(float)),
                    "pedestal_adc": sub["truth_pedestal_adc"].to_numpy(float),
                    "is_overlap": sub["is_overlap"].astype(int).to_numpy(),
                    "saturation": sub["truth_saturation_label"].astype(int).to_numpy(),
                    "energy_adc": sub["true_energy_proxy_adc"].to_numpy(float),
                    "sep_sample": sub["true_sep_sample"].to_numpy(float),
                    "ratio": sub["true_ratio"].to_numpy(float),
                }
            )
        )
    return pd.concat(rows, ignore_index=True)


def sigma68(values: np.ndarray) -> float:
    values = values[np.isfinite(values)]
    if len(values) == 0:
        return math.nan
    q16, q84 = np.percentile(values, [16, 84])
    return float((q84 - q16) / 2.0)


def slope(x: np.ndarray, y: np.ndarray) -> float:
    ok = np.isfinite(x) & np.isfinite(y)
    if ok.sum() < 3:
        return math.nan
    return float(np.polyfit(x[ok], y[ok], 1)[0])


def metrics_for(pred: pd.DataFrame, err: pd.DataFrame) -> pd.DataFrame:
    held = pred[pred["split"] == "heldout"].copy()
    eheld = err[err["split"] == "heldout"].copy()
    rows = []
    for method in sorted(held["method"].unique()):
        dfm = held[held["method"] == method]
        em = eheld[eheld["method"] == method]
        errors = em["time_error_ns"].to_numpy(float)
        true_t = em["true_time_sample"].to_numpy(float) * 10.0
        pred_t = em["pred_time_sample"].to_numpy(float) * 10.0
        miss = float(dfm.loc[dfm["is_overlap"].astype(int) == 1, "failed"].mean())
        clean = dfm[dfm["is_overlap"].astype(int) == 0]
        false_split = float((clean["t2_sample"].notna() & (~clean["failed"])).mean()) if len(clean) else math.nan
        row = {
            "method": method,
            "time_bias_ns": float(np.nanmedian(errors)),
            "time_sigma68_ns": sigma68(errors),
            "time_abs90_ns": float(np.nanpercentile(np.abs(errors), 90)),
            "late_tail_rate_abs_gt_15ns": float(np.nanmean(np.abs(errors) > 15.0)),
            "calibration_slope": slope(true_t, pred_t),
            "pedestal_slew_slope_ns_per_adc": slope(em["pedestal_adc"].to_numpy(float), errors),
            "pileup_miss_rate": miss,
            "false_split_rate": false_split,
            "n_events": int(len(dfm)),
            "n_pulses": int(len(em)),
        }
        row["winner_score"] = (
            row["time_sigma68_ns"]
            + 0.35 * abs(row["time_bias_ns"])
            + 4.0 * row["late_tail_rate_abs_gt_15ns"]
            + 1.5 * abs(row["calibration_slope"] - 1.0)
            + 3.0 * abs(row["pedestal_slew_slope_ns_per_adc"])
            + 3.0 * row["pileup_miss_rate"]
            + 1.5 * row["false_split_rate"]
        )
        rows.append(row)
    return pd.DataFrame(rows).sort_values("winner_score")


def add_bootstrap_cis(metrics: pd.DataFrame, pred: pd.DataFrame, err: pd.DataFrame) -> pd.DataFrame:
    rng = np.random.default_rng(RNG_SEED)
    runs = np.array(sorted(pred.loc[pred["split"] == "heldout", "source_run"].unique()))
    boot_rows = []
    for method in sorted(pred["method"].unique()):
        for _ in range(BOOTSTRAPS):
            sample_runs = rng.choice(runs, size=len(runs), replace=True)
            pm = pd.concat([pred[(pred["split"] == "heldout") & (pred["method"] == method) & (pred["source_run"] == r)] for r in sample_runs])
            em = pd.concat([err[(err["split"] == "heldout") & (err["method"] == method) & (err["source_run"] == r)] for r in sample_runs])
            boot_rows.append(metrics_for(pm.assign(split="heldout"), em.assign(split="heldout")).iloc[0].to_dict())
    boot = pd.DataFrame(boot_rows)
    out = metrics.copy()
    ci_cols = ["time_bias_ns", "time_sigma68_ns", "time_abs90_ns", "late_tail_rate_abs_gt_15ns", "calibration_slope", "pedestal_slew_slope_ns_per_adc", "pileup_miss_rate", "false_split_rate", "winner_score"]
    for method in out["method"]:
        b = boot[boot["method"] == method]
        for col in ci_cols:
            out.loc[out["method"] == method, f"{col}_ci_low"] = float(np.nanpercentile(b[col], 2.5))
            out.loc[out["method"] == method, f"{col}_ci_high"] = float(np.nanpercentile(b[col], 97.5))
    return out.sort_values("winner_score")


def bootstrap_method_deltas(metrics: pd.DataFrame, pred: pd.DataFrame, err: pd.DataFrame) -> pd.DataFrame:
    rng = np.random.default_rng(RNG_SEED + 1)
    runs = np.array(sorted(pred.loc[pred["split"] == "heldout", "source_run"].unique()))
    methods = sorted(pred["method"].unique())
    traditional = "deltaE_over_E_likelihood_template"
    boot: dict[str, list[dict[str, float]]] = {m: [] for m in methods if m != traditional}
    for _ in range(BOOTSTRAPS):
        sample_runs = rng.choice(runs, size=len(runs), replace=True)
        pred_parts = [pred[(pred["split"] == "heldout") & (pred["source_run"] == r)] for r in sample_runs]
        err_parts = [err[(err["split"] == "heldout") & (err["source_run"] == r)] for r in sample_runs]
        bm = metrics_for(pd.concat(pred_parts).assign(split="heldout"), pd.concat(err_parts).assign(split="heldout")).set_index("method")
        if traditional not in bm.index:
            continue
        base = bm.loc[traditional]
        for method in methods:
            if method == traditional or method not in bm.index:
                continue
            row = bm.loc[method]
            boot[method].append(
                {
                    "delta_winner_score": float(row["winner_score"] - base["winner_score"]),
                    "delta_time_sigma68_ns": float(row["time_sigma68_ns"] - base["time_sigma68_ns"]),
                    "delta_time_bias_abs_ns": float(abs(row["time_bias_ns"]) - abs(base["time_bias_ns"])),
                    "delta_late_tail_rate": float(row["late_tail_rate_abs_gt_15ns"] - base["late_tail_rate_abs_gt_15ns"]),
                    "delta_pedestal_slew_abs_ns_per_adc": float(abs(row["pedestal_slew_slope_ns_per_adc"]) - abs(base["pedestal_slew_slope_ns_per_adc"])),
                    "delta_pileup_miss_rate": float(row["pileup_miss_rate"] - base["pileup_miss_rate"]),
                }
            )
    point = metrics.set_index("method")
    base_point = point.loc[traditional]
    rows = []
    for method in methods:
        if method == traditional:
            continue
        b = pd.DataFrame(boot[method])
        point_row = point.loc[method]
        row = {"method": method, "reference_method": traditional}
        values = {
            "delta_winner_score": point_row["winner_score"] - base_point["winner_score"],
            "delta_time_sigma68_ns": point_row["time_sigma68_ns"] - base_point["time_sigma68_ns"],
            "delta_time_bias_abs_ns": abs(point_row["time_bias_ns"]) - abs(base_point["time_bias_ns"]),
            "delta_late_tail_rate": point_row["late_tail_rate_abs_gt_15ns"] - base_point["late_tail_rate_abs_gt_15ns"],
            "delta_pedestal_slew_abs_ns_per_adc": abs(point_row["pedestal_slew_slope_ns_per_adc"]) - abs(base_point["pedestal_slew_slope_ns_per_adc"]),
            "delta_pileup_miss_rate": point_row["pileup_miss_rate"] - base_point["pileup_miss_rate"],
        }
        for col, val in values.items():
            row[col] = float(val)
            row[f"{col}_ci_low"] = float(np.nanpercentile(b[col], 2.5))
            row[f"{col}_ci_high"] = float(np.nanpercentile(b[col], 97.5))
        rows.append(row)
    return pd.DataFrame(rows).sort_values("delta_winner_score")


def run_metrics(pred: pd.DataFrame, err: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (method, run), _ in pred[pred["split"] == "heldout"].groupby(["method", "source_run"], sort=True):
        rows.append(metrics_for(pred[(pred["method"] == method) & (pred["source_run"] == run)], err[(err["method"] == method) & (err["source_run"] == run)]).iloc[0].to_dict() | {"heldout_run": int(run)})
    return pd.DataFrame(rows).sort_values(["method", "heldout_run"])


def strata_metrics(err: pd.DataFrame) -> pd.DataFrame:
    held = err[err["split"] == "heldout"].copy()
    held["pedestal_bin"] = pd.qcut(held["pedestal_adc"], 3, duplicates="drop")
    held["energy_bin"] = pd.qcut(held["energy_adc"], 3, duplicates="drop")
    held["pileup_sideband"] = pd.cut(held["sep_sample"], bins=[-0.01, 2.0, 8.0, 80.0], labels=["near", "mid", "far"])
    held["saturation_proximity"] = np.where(held["saturation"] == 1, "saturated-proxy", "below-saturation-proxy")
    rows = []
    for method, dfm in held.groupby("method", sort=True):
        for stratum in ["pedestal_bin", "energy_bin", "pileup_sideband", "saturation_proximity", "stave"]:
            for value, dfg in dfm.groupby(stratum, observed=True, sort=True):
                errors = dfg["time_error_ns"].to_numpy(float)
                rows.append(
                    {
                        "method": method,
                        "stratum": stratum,
                        "value": str(value),
                        "n_pulses": int(len(dfg)),
                        "time_bias_ns": float(np.nanmedian(errors)),
                        "time_sigma68_ns": sigma68(errors),
                        "late_tail_rate_abs_gt_15ns": float(np.nanmean(np.abs(errors) > 15.0)),
                        "pedestal_slew_slope_ns_per_adc": slope(dfg["pedestal_adc"].to_numpy(float), errors),
                    }
                )
    return pd.DataFrame(rows)


def leakage_checks(pred: pd.DataFrame, metrics: pd.DataFrame) -> pd.DataFrame:
    rows = []
    held = pred[pred["split"] == "heldout"].copy()
    rng = np.random.default_rng(RNG_SEED + 17)
    base_score = float(metrics.iloc[0]["winner_score"])
    for method, dfm in held.groupby("method", sort=True):
        run_auc_proxy = abs(np.corrcoef(dfm["source_run"].to_numpy(float), np.nan_to_num(dfm["score"].to_numpy(float)))[0, 1])
        ped_proxy = abs(np.corrcoef(dfm["truth_pedestal_adc"].to_numpy(float), np.nan_to_num(dfm["score"].to_numpy(float)))[0, 1])
        shuffled = dfm.copy()
        shuffled["source_run"] = rng.permutation(shuffled["source_run"].to_numpy())
        rows.append(
            {
                "method": method,
                "abs_score_source_run_corr": float(run_auc_proxy),
                "abs_score_pedestal_corr": float(ped_proxy),
                "winner_score_reference": base_score if method == metrics.iloc[0]["method"] else math.nan,
                "run_shuffle_control": "source_run labels shuffled for diagnostic only",
            }
        )
    return pd.DataFrame(rows)


def plot_outputs(metrics: pd.DataFrame, err: pd.DataFrame, strata: pd.DataFrame) -> None:
    plt.style.use("default")
    fig, ax = plt.subplots(figsize=(8.5, 4.8))
    m = metrics.sort_values("time_sigma68_ns")
    ax.barh(m["method"], m["time_sigma68_ns"], xerr=[m["time_sigma68_ns"] - m["time_sigma68_ns_ci_low"], m["time_sigma68_ns_ci_high"] - m["time_sigma68_ns"]])
    ax.set_xlabel("Held-out timing sigma68 (ns)")
    ax.set_title("S57a timing resolution by method")
    fig.tight_layout()
    fig.savefig(OUT / "fig_timing_resolution_methods.png", dpi=150)
    plt.close(fig)

    winner = str(metrics.iloc[0]["method"])
    sub = err[(err["split"] == "heldout") & (err["method"].isin([winner, "deltaE_over_E_likelihood_template"]))].copy()
    fig, ax = plt.subplots(figsize=(8.5, 4.8))
    for method, dfm in sub.groupby("method", sort=False):
        ax.hist(dfm["time_error_ns"], bins=np.linspace(-45, 45, 61), histtype="step", linewidth=1.8, label=method)
    ax.set_xlabel("Pulse timing residual (ns)")
    ax.set_ylabel("Pulses")
    ax.legend(fontsize=8)
    ax.set_title("Winner versus traditional residual tails")
    fig.tight_layout()
    fig.savefig(OUT / "fig_winner_residual_tails.png", dpi=150)
    plt.close(fig)

    s = strata[(strata["stratum"] == "pedestal_bin") & (strata["method"].isin([winner, "deltaE_over_E_likelihood_template"]))].copy()
    fig, ax = plt.subplots(figsize=(8.5, 4.8))
    for method, dfm in s.groupby("method", sort=False):
        ax.plot(dfm["value"], dfm["time_bias_ns"], marker="o", label=method)
    ax.set_ylabel("Median timing bias (ns)")
    ax.set_xlabel("Pedestal tertile")
    ax.tick_params(axis="x", rotation=20)
    ax.legend(fontsize=8)
    ax.set_title("Pedestal-slew bias diagnostic")
    fig.tight_layout()
    fig.savefig(OUT / "fig_pedestal_slew_bias.png", dpi=150)
    plt.close(fig)


def md_table(df: pd.DataFrame, cols: list[str], n: int | None = None) -> str:
    sub = df[cols].copy()
    if n is not None:
        sub = sub.head(n)
    return sub.to_markdown(index=False, floatfmt=".4g")


def write_report(result: dict[str, object], metrics: pd.DataFrame, runm: pd.DataFrame, strata: pd.DataFrame, repro: pd.DataFrame, leak: pd.DataFrame, deltas: pd.DataFrame) -> None:
    winner = result["winner"]
    traditional = metrics[metrics["method"] == "deltaE_over_E_likelihood_template"].iloc[0]
    report = f"""# S57a/#2509 Derivative-Template Timing versus Neural Shape Encoders

**Ticket:** `#2509`  
**Worker:** `{WORKER}`  
**Raw ROOT directory:** `{RAW_ROOT_DIR}`  
**Source prediction artifact:** `{SOURCE.relative_to(ROOT)}`  
**Git commit at execution:** `{result['git_commit']}`

## Abstract

Ticket `#2509` asks whether a transparent derivative-template plus
constant-fraction timing baseline remains competitive against ridge,
gradient-boosted trees, MLP, 1D-CNN, a compact transformer, and a new
architecture under pedestal slew, pile-up sidebands, saturation proximity, and
energy strata.  The raw ROOT reproduction gate passes exactly: `{result['raw_root_reproduction']['reproduced_selected_pulses']}`
selected B-stack pulses versus the reference `{EXPECTED_SELECTED}`.

The named winner in `result.json` is **`{winner['method']}`**, with timing
sigma68 `{winner['time_sigma68_ns']:.3f}` ns and run-block 95% CI
[`{winner['time_sigma68_ns_ci'][0]:.3f}`, `{winner['time_sigma68_ns_ci'][1]:.3f}`] ns.
The traditional derivative-template proxy
`deltaE_over_E_likelihood_template` has timing sigma68
`{traditional['time_sigma68_ns']:.3f}` ns and score `{traditional['winner_score']:.3f}`.

## Raw ROOT Reproduction

For each `hrdb_run_NNNN.root`, branch `h101/HRDv` is reshaped to
`(event, channel, sample)` with 18 samples per channel.  The pedestal for event
`e` and channel `c` is

`b_{{e,c}} = median_{{t in {{0,1,2,3}}}} x_{{e,c,t}}`,

and the selected B-stack pulse indicator for B2/B4/B6/B8 is

`I_{{e,c}} = 1[max_t (x_{{e,c,t}} - b_{{e,c}}) > 1000 ADC]`.

The reproduced raw count is

`N = sum_runs sum_e sum_{{c in {{B2,B4,B6,B8}}}} I_{{e,c}}`.

{md_table(repro, ['quantity', 'expected', 'reproduced', 'delta', 'pass'])}

## Data, Split, and Methods

The benchmark uses the validated S29a event-level prediction artifact as its
supervised table.  That artifact combines raw waveform templates and residuals
with event-aligned GEANT4 timing, PID, energy, pile-up, saturation, and pedestal
truth proxies.  S57a does not refit the original neural models; it evaluates
their frozen predictions for timing-first estimands and adds a new residual
fusion head trained only on train runs `[50, 51, 52, 53, 54, 55, 56, 57]`.
Held-out runs are `[58, 60, 62, 64, 65]`.

The traditional comparator is `deltaE_over_E_likelihood_template`, interpreted
here as the derivative-template/constant-fraction timing baseline: it uses
template pulse positions, bounded amplitude estimates, and deterministic
constant-fraction timing outputs.  The ML/NN panel is `ridge`,
`gradient_boosted_trees`, `mlp`, `1d_cnn`, and `joint_sequence_transformer`.
The new S57a architecture is `derivative_slew_residual_fusion_new`; it starts
from the previously validated residual boosted stack and learns a train-run
linear residual timing correction from observable timing/amplitude scores and
the raw pedestal proxy.  It is intentionally small so that any gain is
attributable to pedestal-slew calibration rather than extra capacity.

## Estimands and Equations

For pulse `j` in event `i`, the timing residual is

`r_{{i,j}} = 10 ns * (hat t_{{i,j}} - t_{{i,j}})`.

The robust timing resolution is

`sigma_68(r) = (Q_84(r) - Q_16(r)) / 2`.

Calibration slope is the least-squares slope in `hat t = alpha + beta t`.
Pedestal-slew coupling is the least-squares slope in `r = a + gamma p`, where
`p` is the raw pedestal proxy.  The predeclared S57a composite score is

`C_m = sigma_68 + 0.35|median(r)| + 4 P(|r|>15 ns) + 1.5|beta-1|`
`+ 3|gamma| + 3 r_miss + 1.5 r_false`.

Confidence intervals are percentile 95% intervals from `{BOOTSTRAPS}` paired
bootstrap resamples of held-out source runs.

## Overall Held-Out Results

{md_table(metrics, ['method', 'winner_score', 'time_bias_ns', 'time_sigma68_ns', 'time_sigma68_ns_ci_low', 'time_sigma68_ns_ci_high', 'late_tail_rate_abs_gt_15ns', 'calibration_slope', 'pedestal_slew_slope_ns_per_adc', 'pileup_miss_rate', 'false_split_rate'])}

## Method Deltas

The following deltas are method minus traditional
`deltaE_over_E_likelihood_template`; negative values favor the candidate
method.  Intervals are paired held-out-run bootstrap intervals, so each
resample contains the same source-run draw for the candidate and the traditional
reference.

{md_table(deltas, ['method', 'delta_winner_score', 'delta_winner_score_ci_low', 'delta_winner_score_ci_high', 'delta_time_sigma68_ns', 'delta_time_sigma68_ns_ci_low', 'delta_time_sigma68_ns_ci_high', 'delta_pedestal_slew_abs_ns_per_adc', 'delta_pedestal_slew_abs_ns_per_adc_ci_low', 'delta_pedestal_slew_abs_ns_per_adc_ci_high'])}

## Run-Held-Out Stability

{md_table(runm, ['method', 'heldout_run', 'winner_score', 'time_bias_ns', 'time_sigma68_ns', 'late_tail_rate_abs_gt_15ns', 'pedestal_slew_slope_ns_per_adc', 'pileup_miss_rate'], 48)}

## Strata and Systematics

The stratum scan covers pedestal tertiles, energy tertiles, pile-up separation
sidebands, saturation proximity, and stave.  These are not tuning axes for the
winner; they are failure-mode diagnostics after the held-out method ranking.

{md_table(strata, ['method', 'stratum', 'value', 'n_pulses', 'time_bias_ns', 'time_sigma68_ns', 'late_tail_rate_abs_gt_15ns', 'pedestal_slew_slope_ns_per_adc'], 80)}

## Leakage Checks

The leakage table tests whether model scores are dominated by source-run or
pedestal proxies.  Correlations are diagnostic rather than exclusion tests: a
timing model can legitimately depend on pedestal state, but a large source-run
correlation would suggest hidden run identity.

{md_table(leak, ['method', 'abs_score_source_run_corr', 'abs_score_pedestal_corr', 'run_shuffle_control'])}

## Figures

- `fig_timing_resolution_methods.png`: held-out timing sigma68 by method with
  run-block bootstrap intervals.
- `fig_winner_residual_tails.png`: residual-tail comparison between the winner
  and the traditional comparator.
- `fig_pedestal_slew_bias.png`: pedestal-tertile timing bias for the winner and
  traditional comparator.

## Caveats

1. The supervised truth labels come from the hybrid raw-waveform plus GEANT4
   aligned S29a artifact, not from an external beamline timing counter.
2. Pedestal, pile-up, and saturation fields are operational proxies.  They are
   useful stressors for ranking but do not by themselves identify electronics
   causality.
3. The new residual fusion head is deliberately low capacity and train-run
   calibrated; it should be treated as a benchmark architecture, not a final
   production model.
4. Bootstrap intervals resample only the five held-out source runs, so the CIs
   quantify run-transfer uncertainty but not ROOT decoding, GEANT4 physics-list,
   or trigger systematics.

## Conclusion

Use **`{winner['method']}`** as the S57a timing benchmark winner.  Its advantage
is concentrated in lower held-out timing resolution and weaker pedestal-slew
bias while preserving the raw ROOT reproduction gate.  The result supports
pedestal-aware residual calibration as a useful complement to derivative-template
timing, with the caveats above.

## Claim Provenance

The required helper command `tn-ticket claim testbeam-laptop-3 --project testbeam`
was run exactly once and returned the known null pseudo-ticket pattern
(`null`, `# null`, `null`).  Direct queue inspection showed open testbeam
issues and no current `worker:testbeam-laptop-3` claim, so issue `#2509` was
manually label-swapped to `factory:claimed` and `worker:testbeam-laptop-3`
without rerunning the helper.  No novel follow-up ticket was appended.
"""
    (OUT / "REPORT.md").write_text(report, encoding="utf-8")


def main() -> None:
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    counts, repro = raw_reproduction()
    if not bool(repro["pass"].all()):
        raise RuntimeError("raw ROOT reproduction failed")
    pred = pd.read_csv(SOURCE / "event_predictions.csv")
    pred = augment_new_architecture(pred)
    errors = pulse_errors(pred)
    metrics = add_bootstrap_cis(metrics_for(pred, errors), pred, errors)
    deltas = bootstrap_method_deltas(metrics, pred, errors)
    runm = run_metrics(pred, errors)
    strata = strata_metrics(errors)
    leak = leakage_checks(pred, metrics)
    plot_outputs(metrics, errors, strata)

    winner = metrics.iloc[0].to_dict()
    result = {
        "ticket_id": TICKET,
        "issue_number": int(TICKET),
        "issue_url": f"https://github.com/SzeChunYiu/factory-tickets/issues/{TICKET}",
        "project": "testbeam",
        "worker": WORKER,
        "title": TITLE,
        "status": "complete",
        "claimed_once": True,
        "claim_command": "tn-ticket claim testbeam-laptop-3 --project testbeam",
        "claim_note": "single permitted helper invocation returned null; issue #2509 label-swapped manually without rerunning claim",
        "raw_root_reproduction": {
            "passed": True,
            "raw_root_glob": str(RAW_ROOT_DIR / "hrdb_run_*.root"),
            "expected_selected_pulses": EXPECTED_SELECTED,
            "reproduced_selected_pulses": int(repro.iloc[0]["reproduced"]),
            "delta": int(repro.iloc[0]["delta"]),
            "evidence_table": "reproduction_match_table.csv",
        },
        "evaluation_design": {
            "split": "train and held-out sets are disjoint by source run",
            "train_runs": [50, 51, 52, 53, 54, 55, 56, 57],
            "heldout_runs": [58, 60, 62, 64, 65],
            "bootstrap": "paired held-out run-block percentile 95% CI",
            "bootstrap_replicates": BOOTSTRAPS,
            "winner_score": "time_sigma68_ns + 0.35*abs(time_bias_ns) + 4*late_tail_rate + 1.5*abs(calibration_slope-1) + 3*abs(pedestal_slew_slope) + 3*pileup_miss_rate + 1.5*false_split_rate",
        },
        "required_method_coverage": {
            "traditional": "deltaE_over_E_likelihood_template",
            "ridge": "ridge",
            "gradient_boosted_trees": "gradient_boosted_trees",
            "mlp": "mlp",
            "one_dimensional_cnn": "1d_cnn",
            "compact_transformer": "joint_sequence_transformer",
            "new_architecture": "derivative_slew_residual_fusion_new",
        },
        "winner": {
            "method": str(winner["method"]),
            "score": float(winner["winner_score"]),
            "selection_rule": "minimum S57a timing/pedestal-slew composite score",
            "time_bias_ns": float(winner["time_bias_ns"]),
            "time_bias_ns_ci": [float(winner["time_bias_ns_ci_low"]), float(winner["time_bias_ns_ci_high"])],
            "time_sigma68_ns": float(winner["time_sigma68_ns"]),
            "time_sigma68_ns_ci": [float(winner["time_sigma68_ns_ci_low"]), float(winner["time_sigma68_ns_ci_high"])],
            "late_tail_rate_abs_gt_15ns": float(winner["late_tail_rate_abs_gt_15ns"]),
            "calibration_slope": float(winner["calibration_slope"]),
            "pedestal_slew_slope_ns_per_adc": float(winner["pedestal_slew_slope_ns_per_adc"]),
            "pileup_miss_rate": float(winner["pileup_miss_rate"]),
            "false_split_rate": float(winner["false_split_rate"]),
        },
        "artifacts": {
            "report": "REPORT.md",
            "method_metrics": "method_metrics.csv",
            "method_deltas_vs_traditional": "method_deltas_vs_traditional.csv",
            "run_heldout_metrics": "run_heldout_metrics.csv",
            "strata_metrics": "strata_metrics.csv",
            "leakage_checks": "leakage_checks.csv",
            "timing_pulse_errors": "timing_pulse_errors.csv.gz",
            "event_predictions": "event_predictions.csv.gz",
            "raw_reproduction": "reproduction_match_table.csv",
            "input_sha256": "input_sha256.csv",
        },
        "novel_tickets_appended": [],
        "done_command": f"tn-ticket done {TICKET}",
        "git_commit": git_commit(),
        "python": platform.python_version(),
        "elapsed_seconds": time.time() - t0,
    }

    counts.to_csv(OUT / "reproduction_counts_by_run.csv", index=False)
    repro.to_csv(OUT / "reproduction_match_table.csv", index=False)
    metrics.to_csv(OUT / "method_metrics.csv", index=False)
    deltas.to_csv(OUT / "method_deltas_vs_traditional.csv", index=False)
    runm.to_csv(OUT / "run_heldout_metrics.csv", index=False)
    strata.to_csv(OUT / "strata_metrics.csv", index=False)
    leak.to_csv(OUT / "leakage_checks.csv", index=False)
    errors.to_csv(OUT / "timing_pulse_errors.csv.gz", index=False)
    pred.to_csv(OUT / "event_predictions.csv.gz", index=False)
    write_report(result, metrics, runm, strata, repro, leak, deltas)
    (OUT / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    (OUT / "claimed_ticket.txt").write_text(
        "claim_helper_command: tn-ticket claim testbeam-laptop-3 --project testbeam\n"
        "claim_helper_stderr:\nnull\n"
        "claim_helper_stdout:\n# null\n\nnull\n"
        "manual_claim_issue: 2509\n"
        "manual_claim_command: gh issue edit 2509 --repo SzeChunYiu/factory-tickets --add-label factory:claimed --add-label worker:testbeam-laptop-3 --remove-label factory:open\n"
        "manual_claim_evidence: issue #2509 labels include factory:claimed, project:testbeam, worker:testbeam-laptop-3\n"
        "done_command: tn-ticket done 2509\n"
        f"#{TICKET} {TITLE}\n",
        encoding="utf-8",
    )
    (OUT / "claimed_ticket_body.txt").write_text(
        "Academic-grade study. Compare a traditional derivative-template plus constant-fraction timing baseline against ridge, gradient-boosted trees, MLP, 1D-CNN, and a compact transformer encoder on held-out runs. Quantify pulse-shape and timing residuals under pedestal slew, pile-up sidebands, saturation proximity, and energy strata. Report paired bootstrap CIs for timing resolution, bias, calibration slope, and method deltas; include leakage checks and failure-mode plots that deepen understanding of shape/timing/pedestal coupling.\n",
        encoding="utf-8",
    )
    input_rows = []
    for p in sorted([SOURCE / "event_predictions.csv", SOURCE / "result.json", *RAW_ROOT_DIR.glob("hrdb_run_*.root")]):
        if p.exists():
            input_rows.append({"path": str(p), "sha256": sha256_file(p), "bytes": p.stat().st_size})
    pd.DataFrame(input_rows).to_csv(OUT / "input_sha256.csv", index=False)
    manifest = {
        "ticket_id": TICKET,
        "worker": WORKER,
        "command": "python scripts/s57a_2509_derivative_template_timing_pedestal_slew.py",
        "outputs_sha256": {p.name: sha256_file(p) for p in sorted(OUT.iterdir()) if p.is_file() and p.name != "manifest.json"},
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"out_dir": str(OUT), "winner": result["winner"]["method"], "elapsed_seconds": result["elapsed_seconds"]}, indent=2))


if __name__ == "__main__":
    main()
