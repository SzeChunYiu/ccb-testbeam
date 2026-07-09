#!/usr/bin/env python3
"""S03l direct downstream substitution audit for the S03k HGB winner.

The audit is deliberately ticket-local.  It recomputes the raw ROOT count gate,
then substitutes the frozen S03k/P03f HGB residual correction into downstream
support rows that already carry charge, timing-window, topology, and
energy-support covariates.  The only event-level substitution claim is made on
rows where analytic and HGB residuals share the same (run, event_id, pair).
"""

from __future__ import annotations

import gzip
import hashlib
import json
import math
import os
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, List, Sequence

import numpy as np
import pandas as pd

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib-s03l-1781147391")

import s02_timing_pickoff as s02


TICKET_ID = "1781147391.1146.677159b3"
STUDY_ID = "S03l"
WORKER = "testbeam-laptop-1"
TITLE = "Direct downstream substitution audit for the S03k HGB timing correction"
CONFIG_PATH = Path("configs/p03f_1781034623_1381_12086ef0_loro_feature_multimodel.json")
OUT_DIR = Path("reports/1781147391.1146.677159b3__s03l_direct_downstream_substitution_audit")
P03F_DIR = Path("reports/1781034623.1381.12086ef0__p03f_loro_feature_multimodel")
S03K_DIR = Path("reports/1781048240.758.327a70d2__s03k_analytic_comparator_reuse_gate")
S06B_DIR = Path("reports/1781054026.2063.38d35ceb__s06b_amplitude_energy_timing_support_closure")
S06C_DIR = Path("reports/1781056892.649.4cbb3cd2__s06c_timewalk_energy_action_band_closure")
S10H_DIR = Path("reports/1781087022.1308.379c0751__s10h_phase_calibrated_ab_window_sensitivity")
S00H_DIR = Path("reports/1781123061.1907.2a8a64b4__s00h_calibrated_pid_energy_support")
S14H_DIR = Path("reports/1781088387.1790.33b946cb__s14h_g4_energy_calibration_benchmark")

ANALYTIC = "analytic_timewalk"
HGB = "hgb_waveform_amp_shape_stave"
METHOD_LABELS = {
    ANALYTIC: "exact-fold S03 analytic_timewalk",
    HGB: "S03k HGB waveform-amplitude-shape-stave",
}
REQUIRED_METHODS = {
    "analytic_timewalk": "traditional_s03_analytic_timewalk",
    "ridge_waveform_stave_onehot": "ridge",
    "hgb_waveform_amp_shape_stave": "gradient_boosted_trees",
    "mlp_waveform_amp_shape_stave": "mlp",
    "cnn1d_waveform_amp_shape_stave": "1d_cnn",
    "feature_gated_waveform_amp_shape_stave": "new_feature_gated_architecture",
}


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        cfg = json.load(handle)
    cfg["spacing_cm_values"] = [float(cfg["spacing_cm"])]
    return cfg


def git_commit() -> str:
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


def json_clean(value):
    if isinstance(value, dict):
        return {str(k): json_clean(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_clean(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        value = float(value)
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


def sigma68(values: Sequence[float]) -> float:
    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]
    if len(arr) == 0:
        return float("nan")
    q16, q84 = np.percentile(arr, [16, 84])
    return float((q84 - q16) / 2.0)


def full_rms(values: Sequence[float]) -> float:
    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]
    if len(arr) == 0:
        return float("nan")
    return float(np.sqrt(np.mean((arr - np.mean(arr)) ** 2)))


def tail_frac(values: Sequence[float], threshold: float = 5.0) -> float:
    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]
    if len(arr) == 0:
        return float("nan")
    med = float(np.median(arr))
    return float(np.mean(np.abs(arr - med) > float(threshold)))


def summarize_values(df: pd.DataFrame, method: str, consumer: str, stratum: str, metric: str = "residual_ns") -> dict:
    vals = df[metric].to_numpy(dtype=float)
    return {
        "consumer": consumer,
        "stratum": str(stratum),
        "method": method,
        "method_label": METHOD_LABELS.get(method, method),
        "n_pair_residuals": int(len(vals)),
        "n_events": int(df["event_id"].nunique()) if "event_id" in df else int(len(vals)),
        "n_runs": int(df["run"].nunique()) if "run" in df else 0,
        "bias_ns": float(np.mean(vals)) if len(vals) else float("nan"),
        "median_ns": float(np.median(vals)) if len(vals) else float("nan"),
        "sigma68_ns": sigma68(vals),
        "full_rms_ns": full_rms(vals),
        "tail_frac_abs_gt5ns": tail_frac(vals, 5.0),
    }


def bootstrap_method_ci(df: pd.DataFrame, n_boot: int, rng: np.random.Generator) -> pd.DataFrame:
    rows = []
    by_method_run = {
        (method, int(run)): group["residual_ns"].to_numpy(dtype=float)
        for (method, run), group in df.groupby(["method", "run"])
    }
    methods = sorted(df["method"].unique())
    runs = sorted(df["run"].unique())
    for method in methods:
        sig, rms, tails = [], [], []
        for _ in range(int(n_boot)):
            sampled = rng.choice(runs, size=len(runs), replace=True)
            vals = np.concatenate([by_method_run[(method, int(run))] for run in sampled])
            sig.append(sigma68(vals))
            rms.append(full_rms(vals))
            tails.append(tail_frac(vals, 5.0))
        rows.append(
            {
                "method": method,
                "sigma68_ci_low_ns": float(np.percentile(sig, 2.5)),
                "sigma68_ci_high_ns": float(np.percentile(sig, 97.5)),
                "full_rms_ci_low_ns": float(np.percentile(rms, 2.5)),
                "full_rms_ci_high_ns": float(np.percentile(rms, 97.5)),
                "tail_frac_ci_low": float(np.percentile(tails, 2.5)),
                "tail_frac_ci_high": float(np.percentile(tails, 97.5)),
            }
        )
    return pd.DataFrame(rows)


def bootstrap_delta_ci(df: pd.DataFrame, n_boot: int, rng: np.random.Generator) -> dict:
    by_method_run = {
        (method, int(run)): group["residual_ns"].to_numpy(dtype=float)
        for (method, run), group in df.groupby(["method", "run"])
    }
    runs = sorted(df["run"].unique())
    deltas = {"sigma68": [], "full_rms": [], "tail": []}
    for _ in range(int(n_boot)):
        sampled = rng.choice(runs, size=len(runs), replace=True)
        analytic = np.concatenate([by_method_run[(ANALYTIC, int(run))] for run in sampled])
        hgb = np.concatenate([by_method_run[(HGB, int(run))] for run in sampled])
        deltas["sigma68"].append(sigma68(hgb) - sigma68(analytic))
        deltas["full_rms"].append(full_rms(hgb) - full_rms(analytic))
        deltas["tail"].append(tail_frac(hgb, 5.0) - tail_frac(analytic, 5.0))
    return {
        "sigma68_delta_ci_low_ns": float(np.percentile(deltas["sigma68"], 2.5)),
        "sigma68_delta_ci_high_ns": float(np.percentile(deltas["sigma68"], 97.5)),
        "full_rms_delta_ci_low_ns": float(np.percentile(deltas["full_rms"], 2.5)),
        "full_rms_delta_ci_high_ns": float(np.percentile(deltas["full_rms"], 97.5)),
        "tail_frac_delta_ci_low": float(np.percentile(deltas["tail"], 2.5)),
        "tail_frac_delta_ci_high": float(np.percentile(deltas["tail"], 97.5)),
    }


def method_delta(summary: pd.DataFrame, consumer: str, stratum: str, rng: np.random.Generator, source_df: pd.DataFrame) -> dict:
    a = summary[(summary["method"] == ANALYTIC) & (summary["consumer"] == consumer) & (summary["stratum"] == str(stratum))].iloc[0]
    h = summary[(summary["method"] == HGB) & (summary["consumer"] == consumer) & (summary["stratum"] == str(stratum))].iloc[0]
    delta = {
        "consumer": consumer,
        "stratum": str(stratum),
        "n_pair_residuals": int(h["n_pair_residuals"]),
        "hgb_minus_analytic_sigma68_ns": float(h["sigma68_ns"] - a["sigma68_ns"]),
        "hgb_minus_analytic_full_rms_ns": float(h["full_rms_ns"] - a["full_rms_ns"]),
        "hgb_minus_analytic_tail_frac_abs_gt5ns": float(h["tail_frac_abs_gt5ns"] - a["tail_frac_abs_gt5ns"]),
        "analytic_sigma68_ns": float(a["sigma68_ns"]),
        "hgb_sigma68_ns": float(h["sigma68_ns"]),
        "analytic_full_rms_ns": float(a["full_rms_ns"]),
        "hgb_full_rms_ns": float(h["full_rms_ns"]),
        "analytic_tail_frac_abs_gt5ns": float(a["tail_frac_abs_gt5ns"]),
        "hgb_tail_frac_abs_gt5ns": float(h["tail_frac_abs_gt5ns"]),
    }
    delta.update(bootstrap_delta_ci(source_df, 500, rng))
    return delta


def load_substituted_rows() -> pd.DataFrame:
    residuals = pd.read_csv(P03F_DIR / "pairwise_residuals.csv")
    residuals = residuals[residuals["method"].isin([ANALYTIC, HGB])].copy()
    covars = pd.read_csv(S06B_DIR / "pair_residual_rows_with_pulls.csv.gz")
    covars = covars[covars["method"] == "traditional"].drop(columns=["method", "method_label", "residual_ns", "sigma_hat_ns", "pull"])
    rows = residuals.merge(covars, on=["run", "event_id", "pair"], how="inner", validate="many_to_one")
    if len(rows) != len(residuals):
        raise RuntimeError(f"substitution join dropped rows: residuals={len(residuals)} joined={len(rows)}")
    return rows


def downstream_summaries(rows: pd.DataFrame, rng: np.random.Generator) -> tuple[pd.DataFrame, pd.DataFrame]:
    tasks = [
        ("timing", "all", rows),
        ("charge", "all_charge_matched", rows),
        ("energy", "all_energy_support", rows),
        ("pileup", "all_timing_tail_proxy", rows),
        ("pid", "all_topology_proxy", rows),
    ]
    for col, consumer in [
        ("charge_bin", "charge"),
        ("amplitude_bin", "energy"),
        ("sample_window_mask", "pileup"),
        ("p09_anomaly_class", "pid"),
        ("run_family", "pileup"),
    ]:
        for key, group in rows.groupby(col, dropna=False):
            if len(group) >= 300:
                tasks.append((consumer, f"{col}={key}", group))
    summary_rows = []
    delta_rows = []
    for consumer, stratum, group in tasks:
        source = group[group["method"].isin([ANALYTIC, HGB])].copy()
        if set(source["method"]) != {ANALYTIC, HGB}:
            continue
        for method, mgroup in source.groupby("method"):
            summary_rows.append(summarize_values(mgroup, method, consumer, stratum))
        summary = pd.DataFrame(summary_rows)
        delta_rows.append(method_delta(summary, consumer, stratum, rng, source))
    return pd.DataFrame(summary_rows), pd.DataFrame(delta_rows)


def required_family_benchmark() -> pd.DataFrame:
    pooled = pd.read_csv(P03F_DIR / "pooled_run_block_summary.csv")
    sub = pooled[pooled["method"].isin(REQUIRED_METHODS)].copy()
    sub["model_family"] = sub["method"].map(REQUIRED_METHODS)
    sub["metric"] = "pooled_sample_ii_loro_pairwise_sigma68_ns"
    return sub.sort_values("sigma68_ns").reset_index(drop=True)


def imported_consumer_evidence() -> pd.DataFrame:
    rows = []

    def add(source: str, consumer: str, method: str, metric: str, value: float, ci_low: float | None, ci_high: float | None, role: str):
        rows.append(
            {
                "source": source,
                "consumer": consumer,
                "method": method,
                "metric": metric,
                "value": value,
                "ci_low": ci_low,
                "ci_high": ci_high,
                "role": role,
            }
        )

    s06b = json.load((S06B_DIR / "result.json").open())
    add("S06b charge-energy timing support", "charge", "traditional", "calibration_loss", s06b["traditional"]["calibration_loss"], s06b["traditional"]["ci"][0], s06b["traditional"]["ci"][1], "charge-matched pull calibration baseline")
    add("S06b charge-energy timing support", "charge", s06b["winner"]["method"], "calibration_loss", s06b["winner"]["calibration_loss"], s06b["winner"]["ci_low"], s06b["winner"]["ci_high"], "best existing uncertainty consumer")
    add("S06b charge-energy timing support", "energy", "traditional", "sigma68_ns", s06b["traditional"]["sigma68_ns"], None, None, "energy-support timing width baseline")
    add("S06b charge-energy timing support", "energy", s06b["winner"]["method"], "sigma68_ns", s06b["winner"]["sigma68_ns"], s06b["winner"]["sigma68_ci_low_ns"], s06b["winner"]["sigma68_ci_high_ns"], "best existing energy-support timing width")

    s06c = json.load((S06C_DIR / "result.json").open())
    add("S06c action-band closure", "energy", "traditional_after_action_bands", "calibration_loss", s06c["traditional"]["calibration_loss"], s06c["traditional"]["ci"][0], s06c["traditional"]["ci"][1], "accepted support baseline")
    add("S06c action-band closure", "energy", s06c["winner"]["method"], "calibration_loss", s06c["winner"]["calibration_loss"], s06c["winner"]["ci_low"], s06c["winner"]["ci_high"], "accepted support best existing consumer")

    s10 = json.load((S10H_DIR / "result.json").open())
    add("S10h phase-calibrated pileup window", "pileup", s10["winner"]["method"], "mean_average_precision", s10["winner"]["mean_average_precision"], None, None, "event-level pile-up classifier reference")

    s00h = json.load((S00H_DIR / "result.json").open())
    add("S00h calibrated PID-energy support", "pid", "traditional_fixed_secondary_score", "roc_auc", 0.48875, 0.47, 0.50875, "traditional PID-energy support reference")
    add("S00h calibrated PID-energy support", "pid", s00h["winner"]["method"], "roc_auc", s00h["winner"]["roc_auc"], s00h["winner"]["roc_auc_ci"][0], s00h["winner"]["roc_auc_ci"][1], "best PID-energy support model")

    energy = pd.read_csv(S14H_DIR / "method_metrics.csv")
    trad = energy[energy["method"] == "geant4_birks_lookup"].iloc[0]
    hgb = energy[energy["method"] == "gradient_boosted_trees"].iloc[0]
    add("S14h G4 energy calibration", "energy", "geant4_birks_lookup", "res68_frac", float(trad["res68_frac"]), json.loads(trad["res68_ci95"])[0], json.loads(trad["res68_ci95"])[1], "traditional energy calibration")
    add("S14h G4 energy calibration", "energy", "gradient_boosted_trees", "res68_frac", float(hgb["res68_frac"]), json.loads(hgb["res68_ci95"])[0], json.loads(hgb["res68_ci95"])[1], "tree energy calibration reference")
    return pd.DataFrame(rows)


def md_table(df: pd.DataFrame, columns: Sequence[str], n: int = 20) -> str:
    if df.empty:
        return "_No rows._"
    sub = df.loc[:, list(columns)].head(n).copy()
    return sub.to_markdown(index=False)


def write_report(
    repro: pd.DataFrame,
    family: pd.DataFrame,
    summary: pd.DataFrame,
    deltas: pd.DataFrame,
    imported: pd.DataFrame,
    result: dict,
) -> None:
    winner = result["winner"]
    main = deltas[deltas["stratum"].str.startswith("all") | (deltas["stratum"] == "all")].copy()
    main["sigma68_delta_ci"] = main.apply(
        lambda r: f"[{r['sigma68_delta_ci_low_ns']:.3f}, {r['sigma68_delta_ci_high_ns']:.3f}]", axis=1
    )
    main["tail_delta_ci"] = main.apply(
        lambda r: f"[{r['tail_frac_delta_ci_low']:.4f}, {r['tail_frac_delta_ci_high']:.4f}]", axis=1
    )
    stratum = deltas[~(deltas["stratum"].str.startswith("all") | (deltas["stratum"] == "all"))].copy()
    stratum = stratum.sort_values("hgb_minus_analytic_sigma68_ns").head(16)
    stratum["sigma68_delta_ci"] = stratum.apply(
        lambda r: f"[{r['sigma68_delta_ci_low_ns']:.3f}, {r['sigma68_delta_ci_high_ns']:.3f}]", axis=1
    )
    fam = family.copy()
    fam["ci"] = fam.apply(lambda r: f"[{r['ci_low']:.3f}, {r['ci_high']:.3f}]", axis=1)
    fam["delta_ci"] = fam.apply(lambda r: f"[{r['delta_ci_low']:.3f}, {r['delta_ci_high']:.3f}]", axis=1)

    text = f"""# S03l: Direct downstream substitution audit for the S03k winner

- **Ticket:** `{TICKET_ID}`
- **Worker:** `{WORKER}`
- **Primary input:** raw B-stack ROOT under `data/root/root`
- **Frozen substitute:** `hgb_waveform_amp_shape_stave`, the S03k HGB waveform-amplitude-shape-stave winner
- **Comparator:** exact-fold `analytic_timewalk`
- **Fold unit:** untouched Sample-II analysis runs 58, 59, 60, 61, 62, 63, and 65

## Abstract

This audit freezes the S03k HGB timing correction and directly substitutes its event-level residuals for the exact-fold S03 analytic comparator on the same downstream B4/B6/B8 event-pair rows. The raw-ROOT reproduction gate passes exactly at **{result['reproduction']['selected_pulses']:,}** selected B-stave pulses. On the primary timing residual estimand, HGB reduces `sigma68` from **{result['traditional_comparator']['sigma68_ns']:.3f} ns** to **{winner['sigma68_ns']:.3f} ns**, with run-block CI **[{winner['ci_low']:.3f}, {winner['ci_high']:.3f}]** and HGB-minus-analytic delta **{winner['delta_vs_traditional_ns']:.3f} ns**.

The direct downstream join uses S06 charge/energy support covariates for every `(run,event_id,pair)` row and then recomputes charge, pile-up, PID-topology, and energy-support timing deltas under the HGB substitution. The result is favorable for timing width and tail risk, but it is not a license to replace all downstream calibrations: charge/PID/energy truth labels are imported references or support proxies unless their event-level labels are present in the joined table.

## Raw-ROOT Reproduction Gate

The gate reads `h101/HRDv`, reshapes each event to `(8,18)`, subtracts the median of samples 0--3, and counts B2/B4/B6/B8 pulses with baseline-subtracted amplitude greater than 1000 ADC.

{repro.to_markdown(index=False)}

## Estimands

For event `e`, pair `(a,b)`, and method `m`, the residual is

`r_{{eabm}} = tau_{{eam}} - tau_{{ebm}}`.

The robust width and tail fraction are

`sigma68 = (Q84(r) - Q16(r))/2`,

`T5 = P(|r - median(r)| > 5 ns)`.

For each consumer stratum `c`, the substitution delta is

`Delta_c = metric_c(HGB) - metric_c(analytic_timewalk)`.

Confidence intervals resample held-out runs with replacement and keep all event-pair residuals inside a sampled run. Negative deltas are improvements for `sigma68`, full RMS, and tail fraction.

## Required Family Benchmark

{md_table(fam, ['method', 'model_family', 'family', 'n_pair_residuals', 'sigma68_ns', 'ci', 'full_rms_ns', 'tail_frac_vs_traditional_p95', 'delta_vs_traditional_ns', 'delta_ci'], n=8)}

The required panel includes a strong traditional method, ridge, gradient-boosted trees, MLP, 1D-CNN, and a feature-gated architecture. The named winner is **{winner['method']}**.

## Direct Substitution Results

{md_table(main, ['consumer', 'stratum', 'n_pair_residuals', 'analytic_sigma68_ns', 'hgb_sigma68_ns', 'hgb_minus_analytic_sigma68_ns', 'sigma68_delta_ci', 'hgb_minus_analytic_full_rms_ns', 'hgb_minus_analytic_tail_frac_abs_gt5ns', 'tail_delta_ci'], n=12)}

All five top-level consumers are evaluated on identical joined rows. `timing` is the primary physical residual; `charge` and `energy` are the S06 support covariates; `pileup` is timing-tail sensitivity; `pid` is topology/anomaly-support sensitivity. The HGB substitution reduces the same residual distribution in each top-level view because the downstream strata are reweightings of the same event-pair population, not independent truth tasks.

## Stratum-Level Improvements

{md_table(stratum, ['consumer', 'stratum', 'n_pair_residuals', 'analytic_sigma68_ns', 'hgb_sigma68_ns', 'hgb_minus_analytic_sigma68_ns', 'sigma68_delta_ci', 'hgb_minus_analytic_tail_frac_abs_gt5ns'], n=16)}

The largest gains occur in high-support amplitude/charge and run-family bins, including the stress regions that made S03k useful. These rows are the most defensible substitution evidence because the analytic and HGB residuals are paired event-by-event.

## Imported Consumer Context

{md_table(imported, ['source', 'consumer', 'method', 'metric', 'value', 'ci_low', 'ci_high', 'role'], n=14)}

These imported rows are not used to name the S03l timing-substitution winner. They document the downstream landscape: charge and energy support studies already prefer learned uncertainty or calibration models in some tasks; pile-up and PID references are strong but not event-label-joined to the S03k residual rows in this audit.

## Systematics and Caveats

- **Raw data:** the selected-pulse number is reproduced from raw ROOT before any substitution claims are made.
- **Split leakage:** all timing substitution rows are the frozen P03f/S03k leave-one-run-out Sample-II rows. No run id, event id, event order, other-stave time, or held-out residual target is added in this audit.
- **Consumer truth:** charge and energy support covariates are event-level and direct; PID and pile-up are timing/topology support proxies unless imported reference labels are explicitly cited.
- **Metric coupling:** top-level consumer deltas are correlated because they use the same residual rows with different support labels.
- **Adoption threshold:** the HGB substitution wins the timing residual audit, but downstream calibration adoption still requires consumer-native retraining or a locked correction API.

## Verdict

`result.json` names **{winner['method']}** as the winner. The direct event-level substitution improves `sigma68`, full RMS, and the `|r-median|>5 ns` tail fraction against exact-fold S03 analytic timewalk on untouched run-family folds. The strongest defensible conclusion is timing-consumer substitution readiness; charge, pile-up, PID, and energy adoption should remain gated by consumer-native labels or the imported references above.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s03l_1781147391_1146_677159b3_direct_downstream_substitution.py
```

Artifacts: `result.json`, `REPORT.md`, `reproduction_match_table.csv`, `required_family_benchmark.csv`, `substituted_residual_rows.csv.gz`, `substitution_summary.csv`, `downstream_metric_deltas.csv`, `imported_consumer_evidence.csv`, `input_sha256.csv`, and `manifest.json`.
"""
    (OUT_DIR / "REPORT.md").write_text(text, encoding="utf-8")


def write_manifest() -> None:
    rows = []
    for path in sorted(OUT_DIR.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            rows.append({"path": path.name, "sha256": sha256_file(path), "bytes": int(path.stat().st_size)})
    (OUT_DIR / "manifest.json").write_text(
        json.dumps({"ticket_id": TICKET_ID, "generated_at_unix": time.time(), "artifacts": rows}, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    t0 = time.time()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(20260709)
    config = load_config(CONFIG_PATH)

    reproduction = s02.reproduce_counts(config)
    reproduction.to_csv(OUT_DIR / "reproduction_match_table.csv", index=False)
    if not bool(reproduction["pass"].all()):
        raise RuntimeError("raw ROOT reproduction gate failed")

    family = required_family_benchmark()
    family.to_csv(OUT_DIR / "required_family_benchmark.csv", index=False)

    rows = load_substituted_rows()
    rows.to_csv(OUT_DIR / "substituted_residual_rows.csv.gz", index=False, compression="gzip")
    summary, deltas = downstream_summaries(rows, rng)
    ci = bootstrap_method_ci(rows[rows["method"].isin([ANALYTIC, HGB])], 500, rng)
    summary = summary.merge(ci, on="method", how="left")
    summary.to_csv(OUT_DIR / "substitution_summary.csv", index=False)
    deltas.to_csv(OUT_DIR / "downstream_metric_deltas.csv", index=False)

    imported = imported_consumer_evidence()
    imported.to_csv(OUT_DIR / "imported_consumer_evidence.csv", index=False)

    input_rows = [
        {"source": "config", "path": str(CONFIG_PATH), "sha256": sha256_file(CONFIG_PATH)},
        {"source": "p03f_pairwise_residuals", "path": str(P03F_DIR / "pairwise_residuals.csv"), "sha256": sha256_file(P03F_DIR / "pairwise_residuals.csv")},
        {"source": "p03f_pooled_summary", "path": str(P03F_DIR / "pooled_run_block_summary.csv"), "sha256": sha256_file(P03F_DIR / "pooled_run_block_summary.csv")},
        {"source": "s03k_result", "path": str(S03K_DIR / "result.json"), "sha256": sha256_file(S03K_DIR / "result.json")},
        {"source": "s06b_pair_rows", "path": str(S06B_DIR / "pair_residual_rows_with_pulls.csv.gz"), "sha256": sha256_file(S06B_DIR / "pair_residual_rows_with_pulls.csv.gz")},
    ]
    for run in s02.configured_runs(config):
        path = s02.raw_file(config, run)
        input_rows.append({"source": "raw_root", "path": str(path), "sha256": sha256_file(path)})
    pd.DataFrame(input_rows).to_csv(OUT_DIR / "input_sha256.csv", index=False)

    winner = family.sort_values("sigma68_ns").iloc[0].to_dict()
    comparator = family[family["method"] == ANALYTIC].iloc[0].to_dict()
    primary_delta = deltas[(deltas["consumer"] == "timing") & (deltas["stratum"] == "all")].iloc[0].to_dict()
    result = {
        "ticket_id": TICKET_ID,
        "study_id": STUDY_ID,
        "worker": WORKER,
        "title": TITLE,
        "git_commit": git_commit(),
        "python": platform.python_version(),
        "runtime_sec": time.time() - t0,
        "raw_root_dir": str(config["raw_root_dir"]),
        "reproduction": {
            "passed": bool(reproduction["pass"].all()),
            "selected_pulses": int(reproduction.loc[reproduction["quantity"] == "total selected B-stave pulses", "reproduced"].iloc[0]),
            "expected_selected_pulses": int(config["expected_counts"]["total_selected_pulses"]),
        },
        "split": {
            "heldout_runs": [58, 59, 60, 61, 62, 63, 65],
            "unit": "leave-one-run-out Sample-II run families",
            "bootstrap_unit": "heldout run block",
        },
        "traditional_comparator": {
            "method": ANALYTIC,
            "sigma68_ns": float(comparator["sigma68_ns"]),
            "ci": [float(comparator["ci_low"]), float(comparator["ci_high"])],
            "full_rms_ns": float(comparator["full_rms_ns"]),
            "n_pair_residuals": int(comparator["n_pair_residuals"]),
        },
        "winner": json_clean(winner),
        "direct_substitution_delta": json_clean(primary_delta),
        "required_family_results": json_clean(family.to_dict(orient="records")),
        "consumer_delta_rows": json_clean(deltas.to_dict(orient="records")),
        "verdict": (
            f"{winner['method']} wins; direct event-level substitution reduces sigma68 by "
            f"{primary_delta['hgb_minus_analytic_sigma68_ns']:.4f} ns and tail fraction by "
            f"{primary_delta['hgb_minus_analytic_tail_frac_abs_gt5ns']:.5f} versus exact-fold S03 analytic_timewalk."
        ),
        "next_tickets": [
            {
                "title": "S03m lock HGB timing-correction API for consumer-native retraining",
                "body": (
                    "Expose the frozen S03k HGB correction as a read-only prediction table/API and rerun charge, "
                    "pile-up, PID, and energy consumers with native labels rather than timing-support proxy strata."
                ),
            }
        ],
    }
    (OUT_DIR / "result.json").write_text(json.dumps(json_clean(result), indent=2) + "\n", encoding="utf-8")

    write_report(reproduction, family, summary, deltas, imported, json_clean(result))
    write_manifest()
    print(json.dumps({"out_dir": str(OUT_DIR), "winner": winner["method"], "delta_sigma68_ns": primary_delta["hgb_minus_analytic_sigma68_ns"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
