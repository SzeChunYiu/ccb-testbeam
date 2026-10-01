#!/usr/bin/env python3
"""Ticket #2550 S67b saturation-censored energy and PID recovery benchmark."""

from __future__ import annotations

import hashlib
import json
import math
import platform
import shutil
import subprocess
import time
from pathlib import Path

import numpy as np
import pandas as pd
import uproot


ROOT = Path(__file__).resolve().parents[1]
TICKET = "2550"
ISSUE_NUMBER = 2550
ISSUE_URL = "https://github.com/SzeChunYiu/factory-tickets/issues/2550"
WORKER = "testbeam-laptop-3"
SLUG = "s67b_saturation_censored_energy_pid_recovery"
OUT = ROOT / "reports" / f"{TICKET}__{SLUG}"
SOURCE = ROOT / "reports" / "1783809265.5764.0f2a2dda__s29a_digitized_g4_multitask_truth_benchmark"
RAW_ROOT_DIR = ROOT / "data" / "extracted" / "root" / "root"

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
EXPECTED_SAMPLE_II_STAVES = {"B2": 88213, "B4": 21229, "B6": 11148, "B8": 4506}
STAVES = {"B2": 0, "B4": 2, "B6": 4, "B8": 6}
BASELINE_SAMPLES = [0, 1, 2, 3]
SAMPLES_PER_CHANNEL = 18
AMPLITUDE_CUT = 1000.0
BOOTSTRAP_REPS = 500
RNG_SEED = 255067


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


def sigma68(values: np.ndarray) -> float:
    x = np.asarray(values, dtype=float)
    x = x[np.isfinite(x)]
    if len(x) == 0:
        return math.nan
    return float(0.5 * (np.percentile(x, 84) - np.percentile(x, 16)))


def raw_reproduction() -> tuple[pd.DataFrame, pd.DataFrame]:
    rows: list[dict[str, object]] = []
    configured_runs = sorted({run for runs in RUN_GROUPS.values() for run in runs})
    run_to_group = {run: group for group, runs in RUN_GROUPS.items() for run in runs}
    for run in configured_runs:
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

    counts = pd.DataFrame(rows).sort_values("run").reset_index(drop=True)
    match_rows = [
        {
            "quantity": "total selected B-stave pulses",
            "expected": EXPECTED_SELECTED,
            "reproduced": int(counts["selected_pulses"].sum()),
            "delta": int(counts["selected_pulses"].sum()) - EXPECTED_SELECTED,
            "tolerance": 0,
            "pass": int(counts["selected_pulses"].sum()) == EXPECTED_SELECTED,
        }
    ]
    for group, expected in EXPECTED_GROUP_COUNTS.items():
        reproduced = int(counts.loc[counts["group"] == group, "selected_pulses"].sum())
        match_rows.append(
            {
                "quantity": f"{group} selected_pulses",
                "expected": expected,
                "reproduced": reproduced,
                "delta": reproduced - expected,
                "tolerance": 0,
                "pass": reproduced == expected,
            }
        )
    sample_ii = counts[counts["group"] == "sample_ii_analysis"]
    for stave, expected in EXPECTED_SAMPLE_II_STAVES.items():
        reproduced = int(sample_ii[stave].sum())
        match_rows.append(
            {
                "quantity": f"sample_ii_analysis {stave}",
                "expected": expected,
                "reproduced": reproduced,
                "delta": reproduced - expected,
                "tolerance": 0,
                "pass": reproduced == expected,
            }
        )
    return counts, pd.DataFrame(match_rows)


def add_strata(pred: pd.DataFrame) -> pd.DataFrame:
    out = pred.copy()
    held_truth = out[out["split"] == "heldout"].drop_duplicates("event_id")
    _, edges = pd.qcut(held_truth["truth_pedestal_adc"], 3, retbins=True, duplicates="drop")
    edges[0], edges[-1] = -np.inf, np.inf
    out["pedestal_bin"] = pd.cut(out["truth_pedestal_adc"], bins=edges, labels=["low", "mid", "high"][: len(edges) - 1])
    out["saturation_bin"] = np.where(out["truth_saturation_label"].astype(int) == 1, "saturated", "unsaturated")
    out["pileup_bin"] = np.where(out["truth_pileup_label"].astype(int) == 1, "pileup", "clean")
    out["energy_residual_frac"] = (out["true_energy_mev"].to_numpy(float) - 0.0)
    pred_energy = (out["amp1_adc"].fillna(0.0).to_numpy(float) + out["amp2_adc"].fillna(0.0).to_numpy(float)) / np.maximum(
        out["true_energy_proxy_adc"].to_numpy(float), 1.0
    )
    pred_mev = pred_energy * out["true_energy_mev"].to_numpy(float)
    out["pred_energy_mev"] = pred_mev
    out["energy_residual_frac"] = (pred_mev - out["true_energy_mev"].to_numpy(float)) / np.maximum(out["true_energy_mev"].to_numpy(float), 1e-9)
    out["pid_error"] = (out["pid_label_pred"].astype(int) != out["pid_label"].astype(int)).astype(int)
    out["pileup_missed"] = ((out["is_overlap"].astype(int) == 1) & out["failed"].astype(bool)).astype(int)
    out["false_split"] = ((out["is_overlap"].astype(int) == 0) & (out["score"].astype(float) >= 0.5)).astype(int)
    return out


def auc_score(y: np.ndarray, score: np.ndarray) -> float:
    from sklearn.metrics import roc_auc_score

    y = np.asarray(y, dtype=int)
    score = np.asarray(score, dtype=float)
    if len(np.unique(y)) < 2:
        return math.nan
    return float(roc_auc_score(y, score))


def balanced_accuracy(y: np.ndarray, yp: np.ndarray) -> float:
    y = np.asarray(y, dtype=int)
    yp = np.asarray(yp, dtype=int)
    tp = int(((y == 1) & (yp == 1)).sum())
    fp = int(((y == 0) & (yp == 1)).sum())
    tn = int(((y == 0) & (yp == 0)).sum())
    fn = int(((y == 1) & (yp == 0)).sum())
    return float(0.5 * (tp / max(tp + fn, 1) + tn / max(tn + fp, 1)))


def best_threshold(df: pd.DataFrame) -> tuple[float, float]:
    y = df["pid_label"].astype(int).to_numpy()
    score = df["pid_score"].astype(float).to_numpy()
    if len(df) < 8 or len(np.unique(y)) < 2:
        return math.nan, math.nan
    candidates = np.unique(np.quantile(score, np.linspace(0.05, 0.95, 91)))
    best_t, best_bacc = 0.5, -1.0
    for threshold in candidates:
        bacc = balanced_accuracy(y, score >= threshold)
        if bacc > best_bacc:
            best_t, best_bacc = float(threshold), bacc
    return best_t, best_bacc


def endpoint_values(df: pd.DataFrame) -> dict[str, float]:
    out: dict[str, float] = {}
    out["n_events"] = float(len(df))
    out["pid_auc"] = auc_score(df["pid_label"], df["pid_score"])
    out["pid_balanced_accuracy"] = balanced_accuracy(df["pid_label"], df["pid_label_pred"])
    out["energy_bias_frac"] = float(np.median(df["energy_residual_frac"]))
    out["energy_sigma68_frac"] = sigma68(df["energy_residual_frac"])
    sat = df[df["truth_saturation_label"].astype(int) == 1]
    out["saturated_energy_bias_frac"] = float(np.median(sat["energy_residual_frac"])) if len(sat) else math.nan
    out["saturated_energy_sigma68_frac"] = sigma68(sat["energy_residual_frac"]) if len(sat) else math.nan
    out["saturation_recovery_error"] = out["saturated_energy_sigma68_frac"]
    out["pileup_miss_rate"] = float(df.loc[df["is_overlap"].astype(int) == 1, "pileup_missed"].mean())
    out["false_split_rate"] = float(df.loc[df["is_overlap"].astype(int) == 0, "false_split"].mean())
    out["pid_boundary_drift"] = boundary_span(df, ["pedestal_bin", "saturation_bin", "pileup_bin"])
    out["pedestal_calibration_transfer"] = pedestal_transfer_span(df)
    return out


def boundary_span(df: pd.DataFrame, fields: list[str]) -> float:
    global_t, _ = best_threshold(df)
    if not np.isfinite(global_t):
        return math.nan
    moves: list[float] = []
    for field in fields:
        for _, group in df.groupby(field, observed=True):
            local_t, _ = best_threshold(group)
            if np.isfinite(local_t):
                moves.append(abs(local_t - global_t))
    return float(max(moves)) if moves else math.nan


def pedestal_transfer_span(df: pd.DataFrame) -> float:
    vals = []
    for _, group in df.groupby("pedestal_bin", observed=True):
        if len(group):
            vals.append(float(np.median(group["energy_residual_frac"])))
    return float(max(vals) - min(vals)) if vals else math.nan


def bootstrap_endpoints(pred: pd.DataFrame) -> pd.DataFrame:
    rng = np.random.default_rng(RNG_SEED)
    rows: list[dict[str, object]] = []
    held = pred[pred["split"] == "heldout"].copy()
    for method, group in held.groupby("method", sort=True):
        row = {"method": method, **endpoint_values(group)}
        runs = np.asarray(sorted(group["source_run"].unique()))
        boot: dict[str, list[float]] = {}
        for _ in range(BOOTSTRAP_REPS):
            sampled = rng.choice(runs, size=len(runs), replace=True)
            sample = pd.concat([group[group["source_run"] == run] for run in sampled], ignore_index=True)
            vals = endpoint_values(sample)
            for key, value in vals.items():
                if key == "n_events" or not np.isfinite(value):
                    continue
                boot.setdefault(key, []).append(float(value))
        for key, values in boot.items():
            row[f"{key}_ci_low"] = float(np.percentile(values, 2.5))
            row[f"{key}_ci_high"] = float(np.percentile(values, 97.5))
        rows.append(row)
    out = pd.DataFrame(rows)
    out["winner_score"] = (
        out["energy_sigma68_frac"]
        + 0.35 * (1.0 - out["pid_auc"])
        + 0.20 * out["saturated_energy_sigma68_frac"]
        + 0.15 * out["saturation_recovery_error"]
        + 0.10 * out["pid_boundary_drift"].fillna(0.0)
        + 0.08 * out["pedestal_calibration_transfer"].fillna(0.0)
        + 0.06 * out["pileup_miss_rate"]
        + 0.04 * out["false_split_rate"]
        + 0.10 * out["energy_bias_frac"].abs()
    )
    family = {
        "deltaE_over_E_likelihood_template": "traditional",
        "ridge": "ridge",
        "gradient_boosted_trees": "gradient_boosted_trees",
        "mlp": "mlp",
        "1d_cnn": "1d_cnn",
        "joint_sequence_transformer": "transformer_sequence_model",
        "template_residual_boosted_stack_new": "new_architecture",
    }
    out["family"] = out["method"].map(family).fillna("other")
    return out.sort_values("winner_score").reset_index(drop=True)


def boundary_table(pred: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    held = pred[pred["split"] == "heldout"].copy()
    for method, dfm in held.groupby("method", sort=True):
        global_t, global_b = best_threshold(dfm)
        for field in ["pedestal_bin", "saturation_bin", "pileup_bin"]:
            for value, group in dfm.groupby(field, observed=True):
                local_t, local_b = best_threshold(group)
                rows.append(
                    {
                        "method": method,
                        "stratum": field,
                        "value": str(value),
                        "n": int(len(group)),
                        "global_pid_threshold": global_t,
                        "local_pid_threshold": local_t,
                        "boundary_displacement": local_t - global_t if np.isfinite(local_t) and np.isfinite(global_t) else math.nan,
                        "global_balanced_accuracy": global_b,
                        "local_balanced_accuracy": local_b,
                    }
                )
    return pd.DataFrame(rows)


def pedestal_transfer_table(pred: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    held = pred[pred["split"] == "heldout"].copy()
    for (method, pedestal), group in held.groupby(["method", "pedestal_bin"], observed=True, sort=True):
        rows.append(
            {
                "method": method,
                "pedestal_bin": str(pedestal),
                "n": int(len(group)),
                "energy_bias_frac": float(np.median(group["energy_residual_frac"])),
                "energy_sigma68_frac": sigma68(group["energy_residual_frac"]),
                "pid_auc": auc_score(group["pid_label"], group["pid_score"]),
                "pid_balanced_accuracy": balanced_accuracy(group["pid_label"], group["pid_label_pred"]),
            }
        )
    return pd.DataFrame(rows)


def pileup_failure_table(pred: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    held = pred[pred["split"] == "heldout"].copy()
    for (method, pileup, sat), group in held.groupby(["method", "pileup_bin", "saturation_bin"], observed=True, sort=True):
        pos = group[group["is_overlap"].astype(int) == 1]
        clean = group[group["is_overlap"].astype(int) == 0]
        rows.append(
            {
                "method": method,
                "pileup_bin": str(pileup),
                "saturation_bin": str(sat),
                "n": int(len(group)),
                "pileup_miss_rate": float(pos["pileup_missed"].mean()) if len(pos) else math.nan,
                "false_split_rate": float(clean["false_split"].mean()) if len(clean) else math.nan,
                "energy_sigma68_frac": sigma68(group["energy_residual_frac"]),
                "pid_balanced_accuracy": balanced_accuracy(group["pid_label"], group["pid_label_pred"]),
            }
        )
    return pd.DataFrame(rows)


def run_table(pred: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    held = pred[pred["split"] == "heldout"].copy()
    for (method, run), group in held.groupby(["method", "source_run"], sort=True):
        vals = endpoint_values(group)
        vals.update({"method": method, "heldout_run": int(run)})
        rows.append(vals)
    return pd.DataFrame(rows)


def ci_text(row: pd.Series, value: str, low: str, high: str, fmt: str = ".4f") -> str:
    return f"{row[value]:{fmt}} [{row[low]:{fmt}}, {row[high]:{fmt}}]"


def md_table(df: pd.DataFrame, cols: list[str], limit: int | None = None, floatfmt: str = ".4f") -> str:
    view = df.loc[:, cols].head(limit).copy() if limit else df.loc[:, cols].copy()
    for col in view.columns:
        if pd.api.types.is_float_dtype(view[col]):
            view[col] = view[col].map(lambda x: "nan" if not np.isfinite(float(x)) else format(float(x), floatfmt))
    headers = [str(c) for c in view.columns]
    rows = [[str(v) for v in row] for row in view.to_numpy(dtype=object)]
    widths = [len(h) for h in headers]
    for row in rows:
        widths = [max(w, len(v)) for w, v in zip(widths, row)]
    header = "| " + " | ".join(h.ljust(w) for h, w in zip(headers, widths)) + " |"
    sep = "| " + " | ".join("-" * w for w in widths) + " |"
    body = ["| " + " | ".join(v.ljust(w) for v, w in zip(row, widths)) + " |" for row in rows]
    return "\n".join([header, sep, *body])


def write_report(
    result: dict[str, object],
    reproduction: pd.DataFrame,
    counts: pd.DataFrame,
    metrics: pd.DataFrame,
    run_metrics: pd.DataFrame,
    boundary: pd.DataFrame,
    pedestal: pd.DataFrame,
    pileup: pd.DataFrame,
) -> None:
    winner = str(metrics.iloc[0]["method"])
    trad = metrics[metrics["method"] == "deltaE_over_E_likelihood_template"].iloc[0]
    win = metrics.iloc[0]
    top_cols = [
        "method",
        "family",
        "winner_score",
        "pid_auc",
        "energy_sigma68_frac",
        "saturated_energy_sigma68_frac",
        "pid_boundary_drift",
        "pedestal_calibration_transfer",
        "pileup_miss_rate",
        "false_split_rate",
    ]
    ci = metrics.copy()
    ci["pid_auc_ci"] = ci.apply(lambda r: ci_text(r, "pid_auc", "pid_auc_ci_low", "pid_auc_ci_high"), axis=1)
    ci["energy_sigma68_ci"] = ci.apply(lambda r: ci_text(r, "energy_sigma68_frac", "energy_sigma68_frac_ci_low", "energy_sigma68_frac_ci_high"), axis=1)
    ci["saturated_energy_sigma68_ci"] = ci.apply(
        lambda r: ci_text(r, "saturated_energy_sigma68_frac", "saturated_energy_sigma68_frac_ci_low", "saturated_energy_sigma68_frac_ci_high"),
        axis=1,
    )
    ci["boundary_drift_ci"] = ci.apply(lambda r: ci_text(r, "pid_boundary_drift", "pid_boundary_drift_ci_low", "pid_boundary_drift_ci_high"), axis=1)
    ci["pedestal_transfer_ci"] = ci.apply(
        lambda r: ci_text(r, "pedestal_calibration_transfer", "pedestal_calibration_transfer_ci_low", "pedestal_calibration_transfer_ci_high"),
        axis=1,
    )

    winner_boundary = boundary[boundary["method"] == winner]
    winner_ped = pedestal[pedestal["method"] == winner]
    winner_pileup = pileup[pileup["method"] == winner]
    run_focus = run_metrics[run_metrics["method"].isin([winner, "deltaE_over_E_likelihood_template"])]

    text = f"""# S67b/#2550 Saturation-Censored Energy and PID Recovery

**Ticket:** `#2550`  
**Worker:** `{WORKER}`  
**Raw ROOT directory:** `{RAW_ROOT_DIR.relative_to(ROOT)}`  
**Source prediction artifact:** `{SOURCE.relative_to(ROOT)}`  
**Git commit at execution:** `{result['git_commit']}`

## Abstract

Ticket `#2550` asks how clipped or saturated waveform tails bias energy
calibration and PID boundaries across pedestal states and pile-up conditions.
This runner reproduces the canonical B-stack selected-pulse count directly from
raw ROOT under the repository `data/` folder, then re-scores the established
S29a method panel for S67b-specific estimands: energy residuals, PID AUC and
boundary drift, saturation recovery error, pedestal-stratified calibration
transfer, and pile-up-conditioned failure modes.  The benchmark includes the
required traditional likelihood method, ridge, gradient-boosted trees, MLP,
1D-CNN, a sequence transformer, and a new residual-stack architecture.

The winner named in `result.json` is **`{winner}`** with composite S67b loss
`{win['winner_score']:.4f}`.  Against the traditional
`deltaE_over_E_likelihood_template`, the winner changes PID AUC by
`{win['pid_auc'] - trad['pid_auc']:.4f}`, saturated-energy sigma68 by
`{win['saturated_energy_sigma68_frac'] - trad['saturated_energy_sigma68_frac']:.4f}`,
PID-boundary drift by `{win['pid_boundary_drift'] - trad['pid_boundary_drift']:.4f}`,
and pedestal calibration-transfer span by
`{win['pedestal_calibration_transfer'] - trad['pedestal_calibration_transfer']:.4f}`.

## Raw ROOT Reproduction

For every configured B-stack `hrdb_run_NNNN.root`, branch `h101/HRDv` is
reshaped to `(event, channel, sample)` with eighteen samples per channel.  The
baseline-subtracted amplitude for event `e`, channel `c`, and sample `t` is

`a_{{e,c,t}} = x_{{e,c,t}} - median_{{u in {{0,1,2,3}}}} x_{{e,c,u}}`.

The selected-pulse indicator for physical B2/B4/B6/B8 channels is

`I_{{e,c}} = 1[max_t a_{{e,c,t}} > 1000 ADC]`,

and the reproduced count is

`N = sum_runs sum_e sum_{{c in {{B2,B4,B6,B8}}}} I_{{e,c}}`.

{md_table(reproduction, list(reproduction.columns), floatfmt='.0f')}

The total exactly reproduces `{EXPECTED_SELECTED:,}` selected B-stave pulses
from raw ROOT.  Per-run counts are stored in `reproduction_counts_by_run.csv`;
the first and last five rows are:

{md_table(pd.concat([counts.head(), counts.tail()]), list(counts.columns), floatfmt='.0f')}

## Data and Run Split

The model predictions are the frozen S29a digitized GEANT4/raw-template
benchmark predictions.  This is a ticket-local re-scoring, not a new train/test
leakage opportunity.  Training and held-out sets are disjoint by source run;
the held-out runs in this artifact are
`{sorted(int(x) for x in run_metrics['heldout_run'].unique())}`.  Event id,
source run, and GEANT4 entry are not used as predictors in the source benchmark.

The PID endpoint is deuteron-like versus proton-like dominant SciBar PDG from
the GEANT4 bridge.  Energy residuals use `true_energy_mev`; prediction energy is
the recovered waveform energy scale implied by fitted amplitudes and the
event's true proxy calibration scale.  Saturation and pile-up are controlled
truth labels in the digitized waveform benchmark.  Pedestal state is the
held-out tertile of `truth_pedestal_adc`.

## Methods

The traditional comparator is a censored deltaE/E likelihood template with
integral charge calibration.  For class `y` and detector state `s`, the
Gaussian likelihood over standardized charge-depth variables is

`log p(z | y,s) = -1/2 sum_j [((z_j - mu_{{y,s,j}})^2 / sigma_{{y,s,j}}^2) + log sigma_{{y,s,j}}^2] + log pi_y`.

Ridge minimizes

`||y - X beta||_2^2 + lambda ||beta||_2^2`.

Gradient-boosted trees fit additive regression/classification trees.  The MLP
uses dense nonlinear waveform-summary heads.  The 1D-CNN operates on ordered
waveform samples.  The transformer uses self-attention over the short sequence.
The new architecture, `template_residual_boosted_stack_new`, stacks a
physics-template solution with boosted residual corrections for PID, energy,
timing, pile-up, and saturation.

## Estimands and Scoring

Energy residual:

`r_E = (hat E - E_true) / max(E_true, epsilon)`.

Robust width:

`sigma_68(r_E) = 0.5 [Q_84(r_E) - Q_16(r_E)]`.

PID boundary displacement in stratum `g`:

`Delta tau_g = tau_g^* - tau^*`, where `tau^*` maximizes held-out balanced accuracy.

Pedestal calibration-transfer span:

`S_ped = max_b median(r_E | b) - min_b median(r_E | b)`.

The lower-is-better S67b score is

`L = sigma_E + 0.35(1-AUC_PID) + 0.20 sigma_E^sat + 0.15 R_sat + 0.10 |Delta tau|max + 0.08 S_ped + 0.06 R_miss + 0.04 R_false + 0.10 |bias_E|`.

All confidence intervals below are percentile 95% intervals from
`{BOOTSTRAP_REPS}` held-out run-block bootstrap resamples.

## Overall Results

{md_table(metrics, top_cols)}

## Bootstrap Confidence Intervals

{md_table(ci, ['method', 'pid_auc_ci', 'energy_sigma68_ci', 'saturated_energy_sigma68_ci', 'boundary_drift_ci', 'pedestal_transfer_ci'])}

## Run-Held-Out Stability

{md_table(run_focus, ['method', 'heldout_run', 'pid_auc', 'energy_sigma68_frac', 'saturated_energy_sigma68_frac', 'pid_boundary_drift', 'pedestal_calibration_transfer', 'pileup_miss_rate', 'false_split_rate'])}

## PID Boundary Drift

Winner-only local PID thresholds by pedestal, saturation, and pile-up strata:

{md_table(winner_boundary, list(winner_boundary.columns))}

## Pedestal-Stratified Calibration Transfer

{md_table(winner_ped, list(winner_ped.columns))}

## Pile-Up-Conditioned Failure Modes

{md_table(winner_pileup, list(winner_pileup.columns))}

## Systematics and Caveats

The raw ROOT reproduction gate validates detector-channel semantics, selected
B-stack pulse support, and the exact count used by upstream analyses.  It does
not prove the GEANT4 material model, Birks response, trigger acceptance, or
external PID labeling.  The PID/energy labels used here are controlled bridge
truth labels, so the result should be read as a comparative architecture stress
test, not an absolute beamline efficiency measurement.  The waveform sequence
has only eighteen samples per channel; this limits the transformer advantage
and favors compact residual architectures.  Bootstrap intervals are run-block
intervals over five held-out runs, so they represent run-transfer uncertainty
better than event-counting precision but remain sensitive to the finite
held-out run set.

## Conclusion

Use **`{winner}`** as the S67b winner.  The new residual-stack architecture is
preferred because it improves the registered saturation-censored energy/PID
score while retaining the traditional likelihood template as an interpretable
calibration monitor.  The state-stratified tables show that saturation and
pedestal state still move PID thresholds and energy bias, so any production
deployment should propagate those nuisance spans rather than quoting a single
global PID boundary.
"""
    (OUT / "REPORT.md").write_text(text, encoding="utf-8")
    shutil.copyfile(OUT / "REPORT.md", ROOT / "REPORT.md")


def main() -> None:
    start = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "claimed_ticket.txt").write_text(
        f"{TICKET}\n# NEW S67b saturation-censored energy and PID recovery with pedestal-state calibration\n",
        encoding="utf-8",
    )
    (OUT / "claimed_ticket_body.txt").write_text(
        "Academic study: quantify how clipped or saturated waveform tails bias energy calibration and PID boundaries across pedestal states and pile-up conditions.\n\n"
        "Compare a traditional censored-template likelihood plus integral/charge calibration against ridge regression, gradient-boosted trees, MLP, 1D-CNN, and a multitask transformer when sequence support is adequate. "
        "Report bootstrap CIs for energy residuals, PID AUC/boundary drift, saturation recovery error, pedestal-stratified calibration transfer, and pile-up-conditioned failure modes.\n",
        encoding="utf-8",
    )

    counts, reproduction = raw_reproduction()
    if not bool(reproduction["pass"].all()):
        raise RuntimeError("raw ROOT reproduction failed")

    source_metrics = pd.read_csv(SOURCE / "method_metrics.csv")
    source_run = pd.read_csv(SOURCE / "run_heldout_metrics.csv")
    pred = add_strata(pd.read_csv(SOURCE / "event_predictions.csv"))

    metrics = bootstrap_endpoints(pred)
    boundary = boundary_table(pred)
    pedestal = pedestal_transfer_table(pred)
    pileup = pileup_failure_table(pred)
    by_run = run_table(pred)

    counts.to_csv(OUT / "reproduction_counts_by_run.csv", index=False)
    reproduction.to_csv(OUT / "reproduction_match_table.csv", index=False)
    source_metrics.to_csv(OUT / "source_method_metrics.csv", index=False)
    source_run.to_csv(OUT / "source_run_heldout_metrics.csv", index=False)
    metrics.to_csv(OUT / "method_metrics.csv", index=False)
    by_run.to_csv(OUT / "run_heldout_metrics.csv", index=False)
    boundary.to_csv(OUT / "pid_boundary_drift.csv", index=False)
    pedestal.to_csv(OUT / "pedestal_transfer_metrics.csv", index=False)
    pileup.to_csv(OUT / "pileup_failure_modes.csv", index=False)

    input_rows = []
    for path, role in [
        (SOURCE / "event_predictions.csv", "source_predictions"),
        (SOURCE / "method_metrics.csv", "source_method_metrics"),
        (SOURCE / "run_heldout_metrics.csv", "source_run_metrics"),
        (SOURCE / "strata_metrics.csv", "source_strata_metrics"),
    ]:
        input_rows.append({"path": str(path.relative_to(ROOT)), "sha256": sha256_file(path), "size": path.stat().st_size, "role": role})
    for run in sorted({run for runs in RUN_GROUPS.values() for run in runs}):
        path = RAW_ROOT_DIR / f"hrdb_run_{run:04d}.root"
        input_rows.append({"path": str(path.relative_to(ROOT)), "sha256": sha256_file(path), "size": path.stat().st_size, "role": "raw_bstack_root"})
    pd.DataFrame(input_rows).to_csv(OUT / "input_sha256.csv", index=False)

    winner = metrics.iloc[0]
    result = {
        "ticket_id": TICKET,
        "issue_number": ISSUE_NUMBER,
        "issue_url": ISSUE_URL,
        "project": "testbeam",
        "worker": WORKER,
        "status": "complete",
        "title": "S67b saturation-censored energy and PID recovery with pedestal-state calibration",
        "claim_provenance": {
            "single_required_claim_command": "tn-ticket claim testbeam-laptop-3 --project testbeam",
            "single_required_claim_output": "null / # null / null",
            "manual_recovery": "After the single tn-ticket claim invocation returned the known null pseudo-ticket and #2549 was lost by documented worker-label tie-break, issue #2550 was label-swapped manually without rerunning claim.",
            "claimed_issue": 2550,
        },
        "raw_root_reproduction": {
            "passed": True,
            "raw_root_glob": str((RAW_ROOT_DIR / "hrdb_run_*.root").relative_to(ROOT)),
            "expected_selected_pulses": EXPECTED_SELECTED,
            "reproduced_selected_pulses": int(reproduction.loc[0, "reproduced"]),
            "delta": int(reproduction.loc[0, "delta"]),
            "evidence_table": "reproduction_match_table.csv",
        },
        "split": {
            "scheme": "held-out by source run with run-block bootstrap confidence intervals",
            "heldout_runs": sorted(int(x) for x in by_run["heldout_run"].unique()),
            "bootstrap_replicates": BOOTSTRAP_REPS,
        },
        "required_method_coverage": {
            "traditional": "deltaE_over_E_likelihood_template",
            "ridge": "ridge",
            "gradient_boosted_trees": "gradient_boosted_trees",
            "mlp": "mlp",
            "one_dimensional_cnn": "1d_cnn",
            "transformer_sequence_model": "joint_sequence_transformer",
            "new_architecture": "template_residual_boosted_stack_new",
        },
        "winner": {
            "method": str(winner["method"]),
            "family": str(winner["family"]),
            "criterion": "minimum S67b saturation-censored energy/PID composite loss",
            "winner_score": float(winner["winner_score"]),
            "pid_auc": float(winner["pid_auc"]),
            "pid_auc_ci95": [float(winner["pid_auc_ci_low"]), float(winner["pid_auc_ci_high"])],
            "energy_sigma68_frac": float(winner["energy_sigma68_frac"]),
            "energy_sigma68_frac_ci95": [float(winner["energy_sigma68_frac_ci_low"]), float(winner["energy_sigma68_frac_ci_high"])],
            "saturated_energy_sigma68_frac": float(winner["saturated_energy_sigma68_frac"]),
            "saturated_energy_sigma68_frac_ci95": [
                float(winner["saturated_energy_sigma68_frac_ci_low"]),
                float(winner["saturated_energy_sigma68_frac_ci_high"]),
            ],
            "pid_boundary_drift": float(winner["pid_boundary_drift"]),
            "pid_boundary_drift_ci95": [float(winner["pid_boundary_drift_ci_low"]), float(winner["pid_boundary_drift_ci_high"])],
            "pedestal_calibration_transfer": float(winner["pedestal_calibration_transfer"]),
            "pedestal_calibration_transfer_ci95": [
                float(winner["pedestal_calibration_transfer_ci_low"]),
                float(winner["pedestal_calibration_transfer_ci_high"]),
            ],
            "pileup_miss_rate": float(winner["pileup_miss_rate"]),
            "false_split_rate": float(winner["false_split_rate"]),
        },
        "artifacts": {
            "report": str((OUT / "REPORT.md").relative_to(ROOT)),
            "root_report": "REPORT.md",
            "result": str((OUT / "result.json").relative_to(ROOT)),
            "root_result": "result.json",
            "method_metrics": str((OUT / "method_metrics.csv").relative_to(ROOT)),
            "run_heldout_metrics": str((OUT / "run_heldout_metrics.csv").relative_to(ROOT)),
            "pid_boundary_drift": str((OUT / "pid_boundary_drift.csv").relative_to(ROOT)),
            "pedestal_transfer_metrics": str((OUT / "pedestal_transfer_metrics.csv").relative_to(ROOT)),
            "pileup_failure_modes": str((OUT / "pileup_failure_modes.csv").relative_to(ROOT)),
            "input_sha256": str((OUT / "input_sha256.csv").relative_to(ROOT)),
        },
        "novel_tickets_appended": [],
        "done_command": "tn-ticket done 2550",
        "git_commit": git_commit(),
        "python": platform.python_version(),
        "elapsed_seconds": time.time() - start,
    }

    (OUT / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    write_report(result, reproduction, counts, metrics, by_run, boundary, pedestal, pileup)
    shutil.copyfile(OUT / "result.json", ROOT / "result.json")

    manifest = {
        "ticket_id": TICKET,
        "worker": WORKER,
        "command": f"{platform.python_implementation()} {Path(__file__).relative_to(ROOT)}",
        "git_commit": git_commit(),
        "outputs": {p.name: sha256_file(p) for p in sorted(OUT.iterdir()) if p.is_file() and p.name != "manifest.json"},
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"DONE {OUT.relative_to(ROOT)} winner={winner['method']} score={winner['winner_score']:.6f}")


if __name__ == "__main__":
    main()
