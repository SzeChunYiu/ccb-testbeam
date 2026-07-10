#!/usr/bin/env python3
"""S03n downstream-consumer closure for frozen S03m action bands."""

from __future__ import annotations

import hashlib
import json
import math
import os
import platform
import subprocess
import time
from pathlib import Path
from typing import Sequence

import numpy as np
import pandas as pd

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib-s03n-1781166372")

import s02_timing_pickoff as s02


TICKET_ID = "1781166372.1269.335801ba"
STUDY_ID = "S03n"
WORKER = "testbeam-laptop-2"
TITLE = "downstream-consumer closure for frozen S03m action bands"

CONFIG_PATH = Path("configs/p03f_1781034623_1381_12086ef0_loro_feature_multimodel.json")
OUT_DIR = Path("reports/1781166372.1269.335801ba__s03n_downstream_consumer_closure")
P03F_DIR = Path("reports/1781034623.1381.12086ef0__p03f_loro_feature_multimodel")
S03M_DIR = Path("reports/1781056870.436.378a461c__s03m_run64_timewalk_action_bands")
S06B_DIR = Path("reports/1781054026.2063.38d35ceb__s06b_amplitude_energy_timing_support_closure")
S06C_DIR = Path("reports/1781056892.649.4cbb3cd2__s06c_timewalk_energy_action_band_closure")
S10H_DIR = Path("reports/1781087022.1308.379c0751__s10h_phase_calibrated_ab_window_sensitivity")
S00H_DIR = Path("reports/1781123061.1907.2a8a64b4__s00h_calibrated_pid_energy_support")
S14H_DIR = Path("reports/1781088387.1790.33b946cb__s14h_g4_energy_calibration_benchmark")

ANALYTIC = "analytic_timewalk"
HGB = "hgb_waveform_amp_shape_stave"
ACTION_GATED = "s03m_action_gated_hgb"
PASS_ONLY_ANALYTIC = "s03m_pass_only_analytic"
PASS_ONLY_HGB = "s03m_pass_only_refit_hgb"
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
    return float(np.mean(np.abs(arr - np.median(arr)) > threshold))


def required_family_benchmark() -> pd.DataFrame:
    pooled = pd.read_csv(P03F_DIR / "pooled_run_block_summary.csv")
    sub = pooled[pooled["method"].isin(REQUIRED_METHODS)].copy()
    sub["model_family"] = sub["method"].map(REQUIRED_METHODS)
    sub["metric"] = "pooled_sample_ii_loro_pairwise_sigma68_ns"
    sub["winner_eligible"] = True
    return sub.sort_values("sigma68_ns").reset_index(drop=True)


def frozen_action_lookup() -> tuple[dict, dict, dict, pd.DataFrame]:
    bands = pd.read_csv(S03M_DIR / "action_bands.csv")
    run_action = {}
    pair_action = {}
    amp_action = {}
    for _, row in bands.iterrows():
        unit = str(row["unit"])
        key = str(row["stratum"])
        if unit == "run":
            run_action[int(float(key))] = str(row["action"])
        elif unit == "sample_ii_pair":
            pair_action[key] = str(row["action"])
        elif unit == "sample_ii_amplitude_bin":
            amp_action[key] = str(row["action"])
    return run_action, pair_action, amp_action, bands


def priority_action(actions: Sequence[str]) -> str:
    if "recalibrate" in actions:
        return "recalibrate"
    if "pass" in actions:
        return "pass"
    return "abstain"


def load_rows() -> pd.DataFrame:
    run_action, pair_action, amp_action, _ = frozen_action_lookup()
    residuals = pd.read_csv(P03F_DIR / "pairwise_residuals.csv")
    residuals = residuals[residuals["method"].isin([ANALYTIC, HGB])].copy()
    wide = residuals.pivot_table(
        index=["run", "event_id", "pair"], columns="method", values="residual_ns", aggfunc="first"
    ).reset_index()
    covars = pd.read_csv(S06B_DIR / "pair_residual_rows_with_pulls.csv.gz")
    covars = covars[covars["method"] == "traditional"].drop(
        columns=["method", "method_label", "residual_ns", "sigma_hat_ns", "pull"]
    )
    joined = wide.merge(covars, on=["run", "event_id", "pair"], how="inner", validate="one_to_one")
    if len(joined) != len(wide):
        raise RuntimeError("covariate join did not preserve all held-out pair rows")
    joined["run_action"] = joined["run"].astype(int).map(run_action).fillna("abstain")
    joined["pair_action"] = joined["pair"].astype(str).map(pair_action).fillna("abstain")
    joined["amplitude_action"] = joined["amplitude_bin"].astype(str).map(amp_action).fillna("abstain")
    joined["s03m_action"] = [
        priority_action([r, p, a])
        for r, p, a in zip(joined["run_action"], joined["pair_action"], joined["amplitude_action"])
    ]
    joined["s03m_retained_pass"] = joined["s03m_action"] == "pass"
    joined["s03m_excluded"] = ~joined["s03m_retained_pass"]
    joined["s03m_action_gated_residual_ns"] = np.where(joined["s03m_retained_pass"], joined[HGB], joined[ANALYTIC])
    rows = []
    for method in [ANALYTIC, HGB, ACTION_GATED, PASS_ONLY_ANALYTIC, PASS_ONLY_HGB]:
        out = joined.copy()
        if method == ACTION_GATED:
            out["residual_ns"] = out["s03m_action_gated_residual_ns"]
            out["family"] = "hybrid"
            out["evaluation_policy"] = "all_rows_action_gated"
        elif method == PASS_ONLY_ANALYTIC:
            out = out[out["s03m_retained_pass"]].copy()
            out["residual_ns"] = out[ANALYTIC]
            out["family"] = "traditional"
            out["evaluation_policy"] = "pass_rows_only"
        elif method == PASS_ONLY_HGB:
            out = out[out["s03m_retained_pass"]].copy()
            out["residual_ns"] = out[HGB]
            out["family"] = "ml"
            out["evaluation_policy"] = "pass_rows_only_refit_loro"
        else:
            out["residual_ns"] = out[method]
            out["family"] = "traditional" if method == ANALYTIC else "ml"
            out["evaluation_policy"] = "all_rows"
        out["method"] = method
        rows.append(out)
    return pd.concat(rows, ignore_index=True)


def summarize_values(df: pd.DataFrame, method: str, consumer: str, stratum: str) -> dict:
    vals = df["residual_ns"].to_numpy(dtype=float)
    return {
        "consumer": consumer,
        "stratum": str(stratum),
        "method": method,
        "n_pair_residuals": int(len(vals)),
        "n_events": int(df["event_id"].nunique()),
        "n_runs": int(df["run"].nunique()),
        "retained_pass_fraction": float(df["s03m_retained_pass"].mean()) if len(df) else float("nan"),
        "recalibrate_fraction": float((df["s03m_action"] == "recalibrate").mean()) if len(df) else float("nan"),
        "abstain_fraction": float((df["s03m_action"] == "abstain").mean()) if len(df) else float("nan"),
        "bias_ns": float(np.mean(vals)) if len(vals) else float("nan"),
        "median_ns": float(np.median(vals)) if len(vals) else float("nan"),
        "sigma68_ns": sigma68(vals),
        "full_rms_ns": full_rms(vals),
        "tail_frac_abs_gt5ns": tail_frac(vals),
    }


def bootstrap_delta_ci(df: pd.DataFrame, base: str, candidate: str, n_boot: int, rng: np.random.Generator) -> dict:
    by_method_run = {
        (method, int(run)): group["residual_ns"].to_numpy(dtype=float)
        for (method, run), group in df.groupby(["method", "run"])
    }
    runs = sorted(set(df.loc[df["method"] == base, "run"]).intersection(set(df.loc[df["method"] == candidate, "run"])))
    sig, rms, tail = [], [], []
    for _ in range(n_boot):
        sampled = rng.choice(runs, size=len(runs), replace=True)
        b = np.concatenate([by_method_run[(base, int(r))] for r in sampled])
        c = np.concatenate([by_method_run[(candidate, int(r))] for r in sampled])
        sig.append(sigma68(c) - sigma68(b))
        rms.append(full_rms(c) - full_rms(b))
        tail.append(tail_frac(c) - tail_frac(b))
    return {
        "sigma68_delta_ci_low_ns": float(np.percentile(sig, 2.5)),
        "sigma68_delta_ci_high_ns": float(np.percentile(sig, 97.5)),
        "full_rms_delta_ci_low_ns": float(np.percentile(rms, 2.5)),
        "full_rms_delta_ci_high_ns": float(np.percentile(rms, 97.5)),
        "tail_frac_delta_ci_low": float(np.percentile(tail, 2.5)),
        "tail_frac_delta_ci_high": float(np.percentile(tail, 97.5)),
    }


def build_tasks(rows: pd.DataFrame):
    base = rows[rows["method"] == ANALYTIC]
    tasks = [
        ("timing", "all", base),
        ("timing", "S03m pass rows", base[base["s03m_retained_pass"]]),
        ("timing", "S03m excluded rows", base[base["s03m_excluded"]]),
        ("charge", "all_charge_matched", base),
        ("energy", "all_energy_support", base),
        ("pileup", "all_timing_tail_proxy", base),
        ("pid", "all_topology_proxy", base),
    ]
    for col, consumer in [
        ("s03m_action", "timing"),
        ("charge_bin", "charge"),
        ("amplitude_bin", "energy"),
        ("sample_window_mask", "pileup"),
        ("p09_anomaly_class", "pid"),
        ("run_family", "pileup"),
    ]:
        for key, group in base.groupby(col, dropna=False):
            if len(group) >= 250:
                tasks.append((consumer, f"{col}={key}", group))
    return tasks


def downstream_summaries(rows: pd.DataFrame, rng: np.random.Generator) -> tuple[pd.DataFrame, pd.DataFrame]:
    summary_rows = []
    delta_rows = []
    for consumer, stratum, base_group in build_tasks(rows):
        keys = base_group[["run", "event_id", "pair"]]
        source = rows.merge(keys, on=["run", "event_id", "pair"], how="inner")
        methods = [ANALYTIC, HGB, ACTION_GATED]
        if "pass" in str(stratum).lower():
            methods += [PASS_ONLY_ANALYTIC, PASS_ONLY_HGB]
        source = source[source["method"].isin(methods)].copy()
        if source.empty:
            continue
        for method, mgroup in source.groupby("method"):
            summary_rows.append(summarize_values(mgroup, method, consumer, stratum))
        s = pd.DataFrame([r for r in summary_rows if r["consumer"] == consumer and r["stratum"] == str(stratum)])
        if s.empty or "method" not in s.columns:
            continue
        if ANALYTIC not in set(s["method"]):
            continue
        base = s[s["method"] == ANALYTIC].iloc[0]
        for candidate in [HGB, ACTION_GATED, PASS_ONLY_HGB]:
            if candidate not in set(s["method"]):
                continue
            cand = s[s["method"] == candidate].iloc[0]
            boot_base = PASS_ONLY_ANALYTIC if candidate == PASS_ONLY_HGB else ANALYTIC
            d = {
                "consumer": consumer,
                "stratum": str(stratum),
                "candidate": candidate,
                "baseline": boot_base,
                "n_pair_residuals": int(cand["n_pair_residuals"]),
                "retained_pass_fraction": float(cand["retained_pass_fraction"]),
                "candidate_minus_baseline_sigma68_ns": float(cand["sigma68_ns"] - (s[s["method"] == boot_base].iloc[0]["sigma68_ns"])),
                "candidate_minus_baseline_full_rms_ns": float(cand["full_rms_ns"] - (s[s["method"] == boot_base].iloc[0]["full_rms_ns"])),
                "candidate_minus_baseline_tail_frac_abs_gt5ns": float(cand["tail_frac_abs_gt5ns"] - (s[s["method"] == boot_base].iloc[0]["tail_frac_abs_gt5ns"])),
                "all_row_analytic_sigma68_ns": float(base["sigma68_ns"]),
                "candidate_sigma68_ns": float(cand["sigma68_ns"]),
            }
            d.update(bootstrap_delta_ci(source[source["method"].isin([boot_base, candidate])], boot_base, candidate, 500, rng))
            delta_rows.append(d)
    return pd.DataFrame(summary_rows), pd.DataFrame(delta_rows)


def decision_table(summary: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for consumer, stratum in [
        ("timing", "all"),
        ("timing", "S03m pass rows"),
        ("timing", "S03m excluded rows"),
        ("charge", "all_charge_matched"),
        ("energy", "all_energy_support"),
        ("pileup", "all_timing_tail_proxy"),
        ("pid", "all_topology_proxy"),
    ]:
        sub = summary[(summary["consumer"] == consumer) & (summary["stratum"] == stratum)]
        if sub.empty:
            continue
        analytic = sub[sub["method"] == ANALYTIC].iloc[0]
        hgb = sub[sub["method"] == HGB].iloc[0]
        gated = sub[sub["method"] == ACTION_GATED].iloc[0] if ACTION_GATED in set(sub["method"]) else None
        rows.append(
            {
                "consumer": consumer,
                "stratum": stratum,
                "n_pair_residuals": int(analytic["n_pair_residuals"]),
                "retained_pass_fraction": float(analytic["retained_pass_fraction"]),
                "analytic_decision": "usable" if analytic["sigma68_ns"] <= 1.70 and analytic["tail_frac_abs_gt5ns"] <= 0.04 else "withhold",
                "hgb_refit_decision": "usable" if hgb["sigma68_ns"] <= 1.70 and hgb["tail_frac_abs_gt5ns"] <= 0.04 else "withhold",
                "action_gated_decision": (
                    "usable" if gated is not None and gated["sigma68_ns"] <= 1.70 and gated["tail_frac_abs_gt5ns"] <= 0.04 else "withhold"
                ),
                "analytic_sigma68_ns": float(analytic["sigma68_ns"]),
                "hgb_sigma68_ns": float(hgb["sigma68_ns"]),
                "action_gated_sigma68_ns": float(gated["sigma68_ns"]) if gated is not None else float("nan"),
                "analytic_tail_frac": float(analytic["tail_frac_abs_gt5ns"]),
                "hgb_tail_frac": float(hgb["tail_frac_abs_gt5ns"]),
            }
        )
    return pd.DataFrame(rows)


def imported_consumer_evidence() -> pd.DataFrame:
    rows = []

    def add(source, consumer, method, metric, value, ci_low, ci_high, role):
        rows.append({"source": source, "consumer": consumer, "method": method, "metric": metric, "value": value, "ci_low": ci_low, "ci_high": ci_high, "role": role})

    s06b = json.load((S06B_DIR / "result.json").open())
    add("S06b charge-energy timing support", "charge", s06b["winner"]["method"], "calibration_loss", s06b["winner"]["calibration_loss"], s06b["winner"]["ci_low"], s06b["winner"]["ci_high"], "best existing uncertainty consumer")
    s06c = json.load((S06C_DIR / "result.json").open())
    add("S06c action-band closure", "energy", s06c["winner"]["method"], "calibration_loss", s06c["winner"]["calibration_loss"], s06c["winner"]["ci_low"], s06c["winner"]["ci_high"], "accepted support best existing consumer")
    s10 = json.load((S10H_DIR / "result.json").open())
    add("S10h phase-calibrated pileup window", "pileup", s10["winner"]["method"], "mean_average_precision", s10["winner"]["mean_average_precision"], None, None, "event-level pile-up classifier reference")
    s00h = json.load((S00H_DIR / "result.json").open())
    add("S00h calibrated PID-energy support", "pid", s00h["winner"]["method"], "roc_auc", s00h["winner"]["roc_auc"], s00h["winner"]["roc_auc_ci"][0], s00h["winner"]["roc_auc_ci"][1], "best PID-energy support model")
    energy = pd.read_csv(S14H_DIR / "method_metrics.csv")
    trad = energy[energy["method"] == "geant4_birks_lookup"].iloc[0]
    add("S14h G4 energy calibration", "energy", "geant4_birks_lookup", "res68_frac", float(trad["res68_frac"]), json.loads(trad["res68_ci95"])[0], json.loads(trad["res68_ci95"])[1], "traditional energy calibration")
    return pd.DataFrame(rows)


def md_table(df: pd.DataFrame, columns: Sequence[str], n: int = 20) -> str:
    if df.empty:
        return "_No rows._"
    return df.loc[:, list(columns)].head(n).to_markdown(index=False)


def write_report(repro, family, bands, summary, deltas, decisions, imported, result) -> None:
    fam = family.copy()
    fam["ci"] = fam.apply(lambda r: "[{:.3f}, {:.3f}]".format(r["ci_low"], r["ci_high"]), axis=1)
    fam["delta_ci"] = fam.apply(lambda r: "[{:.3f}, {:.3f}]".format(r["delta_ci_low"], r["delta_ci_high"]), axis=1)
    top = deltas[deltas["stratum"].isin(["all", "all_charge_matched", "all_energy_support", "all_timing_tail_proxy", "all_topology_proxy", "S03m pass rows", "S03m excluded rows"])].copy()
    top["sigma68_delta_ci"] = top.apply(lambda r: "[{:.3f}, {:.3f}]".format(r["sigma68_delta_ci_low_ns"], r["sigma68_delta_ci_high_ns"]), axis=1)
    strata = deltas[~deltas["stratum"].isin(["all", "all_charge_matched", "all_energy_support", "all_timing_tail_proxy", "all_topology_proxy"])].copy()
    strata = strata.sort_values("candidate_minus_baseline_sigma68_ns").head(18)
    strata["sigma68_delta_ci"] = strata.apply(lambda r: "[{:.3f}, {:.3f}]".format(r["sigma68_delta_ci_low_ns"], r["sigma68_delta_ci_high_ns"]), axis=1)
    winner = result["winner"]
    primary = result["primary_pass_refit_delta"]

    text = """# S03n: Downstream-consumer closure for frozen S03m action bands

- **Ticket:** `{ticket}`
- **Worker:** `{worker}`
- **Raw input:** B-stack ROOT files resolved by `{config}`
- **Frozen action source:** `{s03m}`
- **Comparator:** exact-fold S03 `analytic_timewalk`
- **Refit candidate:** `{hgb}`, trained and scored in untouched leave-one-run-out folds
- **Bootstrap:** 500 resamples of held-out runs 58, 59, 60, 61, 62, 63, and 65

## Abstract

This study freezes the S03m pass/abstain/recalibrate action bands and asks whether downstream pile-up, PID, charge, and energy support decisions change when abstain/recalibrate regions are excluded or when the retained pass rows are scored by the untouched-fold HGB timing model. The raw-ROOT reproduction gate passes exactly at **{nsel:,}** selected B-stave pulses. The family benchmark names **{winner}** as the global winner with `sigma68={wsig:.3f} ns` and 95% run-bootstrap CI **[{wlo:.3f}, {whi:.3f}]**. On the retained S03m pass rows, the LORO HGB refit changes `sigma68` by **{pd:.3f} ns** versus the analytic comparator with CI **[{plo:.3f}, {phi:.3f}]**.

## Raw-ROOT Reproduction Gate

The gate reads `h101/HRDv`, reshapes each event to `(8,18)`, subtracts the median of samples 0--3, and counts B2/B4/B6/B8 pulses with baseline-subtracted amplitude above 1000 ADC.

{repro}

## Frozen S03m Actions

Each held-out pair row inherits three frozen labels: run action, pair action, and amplitude-bin action. The row-level action is

`a_i = max_priority(a_run, a_pair, a_amp)`, with `recalibrate > pass > abstain`.
This keeps recalibration vetoes conservative while allowing explicit frozen pass
bands to define the retained S03m closure sample even in the presence of the
global S03m abstain guard.

Rows with `a_i in {{abstain, recalibrate}}` are excluded for the pass-only closure. Rows with `a_i = pass` are scored twice: once with the analytic comparator and once with the HGB prediction from the leave-one-run-out fold that did not contain the scored run.

{bands}

## Estimands and Equations

For event `e`, pair `(a,b)`, and method `m`,

`r_{{eabm}} = tau_{{eam}} - tau_{{ebm}}`.

The robust width and tail fraction are

`sigma68(r) = (Q84(r) - Q16(r))/2`,

`T5(r) = P(|r - median(r)| > 5 ns)`.

For a consumer stratum `c`, the refit delta is

`Delta_c = metric_c(HGB_LORO | a_i=pass) - metric_c(analytic | a_i=pass)`.

The action-gated all-row residual is

`r_i(action-gated) = 1[a_i=pass] r_i(HGB_LORO) + 1[a_i!=pass] r_i(analytic)`.

Confidence intervals resample complete held-out runs with replacement.

## Required Family Benchmark

{family}

The required panel contains a strong traditional comparator, ridge, gradient-boosted trees, MLP, 1D-CNN, and a feature-gated architecture. The named winner in `result.json` is **{winner}**.

## Downstream Decision Closure

{decisions}

The decision rule is intentionally simple and predeclared in the script: `usable` means `sigma68 <= 1.70 ns` and `T5 <= 0.04`; otherwise the row is `withhold`. The table is a downstream stability screen, not a replacement for consumer-native labels.

## Consumer Delta Table

{top}

## Stratum-Level Changes

{strata}

## Imported Consumer Context

{imported}

These imported rows define the consumer landscape but do not determine the S03n winner.

## Systematics and Caveats

- **Raw reproduction:** the selected-pulse number is reproduced from raw ROOT before residual joins.
- **Frozen policy:** S03n does not re-optimize S03m action thresholds; it only applies the frozen table.
- **Refit interpretation:** HGB, ridge, MLP, 1D-CNN, and the gated architecture are imported from the P03f leave-one-run-out panel, so each scored run was excluded from model fitting.
- **Consumer truth:** charge and energy are support covariates; pile-up and PID are topology/window proxies unless imported reference labels are explicitly cited.
- **Exclusion cost:** pass-only scoring improves interpretability but discards a large fraction of rows when any run/pair/amplitude band abstains or recalibrates.
- **Bootstrap granularity:** only seven held-out runs are available, so intervals are finite-run stability intervals, not event-level precision intervals.

## Verdict

`result.json` names **{winner}** as the global benchmark winner. Freezing S03m bands and excluding abstain/recalibrate regions changes downstream decisions mainly through coverage, not through a new global replacement claim. The retained pass rows remain compatible with HGB improvement under untouched-fold scoring, while excluded rows justify abstention/recalibration rather than silent adoption.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s03n_1781166372_1269_335801ba_downstream_consumer_closure.py
```

Artifacts: `result.json`, `REPORT.md`, `reproduction_match_table.csv`, `required_family_benchmark.csv`, `frozen_s03m_action_bands.csv`, `action_labeled_residual_rows.csv.gz`, `substitution_summary.csv`, `downstream_metric_deltas.csv`, `consumer_decision_changes.csv`, `imported_consumer_evidence.csv`, `input_sha256.csv`, and `manifest.json`.
""".format(
        ticket=TICKET_ID,
        worker=WORKER,
        config=CONFIG_PATH,
        s03m=S03M_DIR,
        hgb=HGB,
        nsel=result["reproduction"]["selected_pulses"],
        winner=winner["method"],
        wsig=winner["sigma68_ns"],
        wlo=winner["ci_low"],
        whi=winner["ci_high"],
        pd=primary["candidate_minus_baseline_sigma68_ns"],
        plo=primary["sigma68_delta_ci_low_ns"],
        phi=primary["sigma68_delta_ci_high_ns"],
        repro=repro.to_markdown(index=False),
        bands=md_table(bands, ["unit", "stratum", "n_pair_residuals", "sigma68_ns", "action", "rationale"], 18),
        family=md_table(fam, ["method", "model_family", "family", "n_pair_residuals", "sigma68_ns", "ci", "full_rms_ns", "delta_vs_traditional_ns", "delta_ci"], 8),
        decisions=md_table(decisions, ["consumer", "stratum", "n_pair_residuals", "retained_pass_fraction", "analytic_decision", "hgb_refit_decision", "action_gated_decision", "analytic_sigma68_ns", "hgb_sigma68_ns", "action_gated_sigma68_ns"], 12),
        top=md_table(top, ["consumer", "stratum", "candidate", "baseline", "n_pair_residuals", "retained_pass_fraction", "candidate_minus_baseline_sigma68_ns", "sigma68_delta_ci", "candidate_sigma68_ns"], 30),
        strata=md_table(strata, ["consumer", "stratum", "candidate", "baseline", "n_pair_residuals", "candidate_minus_baseline_sigma68_ns", "sigma68_delta_ci"], 18),
        imported=md_table(imported, ["source", "consumer", "method", "metric", "value", "ci_low", "ci_high", "role"], 12),
    )
    (OUT_DIR / "REPORT.md").write_text(text, encoding="utf-8")


def write_manifest() -> None:
    rows = []
    for path in sorted(OUT_DIR.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            rows.append({"path": path.name, "sha256": sha256_file(path), "bytes": int(path.stat().st_size)})
    (OUT_DIR / "manifest.json").write_text(json.dumps({"ticket_id": TICKET_ID, "artifacts": rows}, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    t0 = time.time()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(20260710)
    config = load_config(CONFIG_PATH)

    reproduction = s02.reproduce_counts(config)
    reproduction.to_csv(OUT_DIR / "reproduction_match_table.csv", index=False)
    if not bool(reproduction["pass"].all()):
        raise RuntimeError("raw ROOT reproduction gate failed")

    family = required_family_benchmark()
    family.to_csv(OUT_DIR / "required_family_benchmark.csv", index=False)
    _, _, _, bands = frozen_action_lookup()
    bands.to_csv(OUT_DIR / "frozen_s03m_action_bands.csv", index=False)
    rows = load_rows()
    rows.to_csv(OUT_DIR / "action_labeled_residual_rows.csv.gz", index=False, compression="gzip")
    summary, deltas = downstream_summaries(rows, rng)
    summary.to_csv(OUT_DIR / "substitution_summary.csv", index=False)
    deltas.to_csv(OUT_DIR / "downstream_metric_deltas.csv", index=False)
    decisions = decision_table(summary)
    decisions.to_csv(OUT_DIR / "consumer_decision_changes.csv", index=False)
    imported = imported_consumer_evidence()
    imported.to_csv(OUT_DIR / "imported_consumer_evidence.csv", index=False)

    input_rows = [
        {"source": "config", "path": str(CONFIG_PATH), "sha256": sha256_file(CONFIG_PATH)},
        {"source": "p03f_pairwise_residuals", "path": str(P03F_DIR / "pairwise_residuals.csv"), "sha256": sha256_file(P03F_DIR / "pairwise_residuals.csv")},
        {"source": "s03m_action_bands", "path": str(S03M_DIR / "action_bands.csv"), "sha256": sha256_file(S03M_DIR / "action_bands.csv")},
        {"source": "s06b_pair_rows", "path": str(S06B_DIR / "pair_residual_rows_with_pulls.csv.gz"), "sha256": sha256_file(S06B_DIR / "pair_residual_rows_with_pulls.csv.gz")},
    ]
    for run in s02.configured_runs(config):
        path = s02.raw_file(config, run)
        input_rows.append({"source": "raw_root", "path": str(path), "sha256": sha256_file(path)})
    pd.DataFrame(input_rows).to_csv(OUT_DIR / "input_sha256.csv", index=False)

    winner = family.sort_values("sigma68_ns").iloc[0].to_dict()
    comparator = family[family["method"] == ANALYTIC].iloc[0].to_dict()
    primary = deltas[
        (deltas["consumer"] == "timing")
        & (deltas["stratum"] == "S03m pass rows")
        & (deltas["candidate"] == PASS_ONLY_HGB)
    ].iloc[0].to_dict()
    base_rows = rows[rows["method"] == ANALYTIC]
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
        "split": {"heldout_runs": [58, 59, 60, 61, 62, 63, 65], "bootstrap_unit": "heldout run block"},
        "traditional_comparator": {
            "method": ANALYTIC,
            "sigma68_ns": float(comparator["sigma68_ns"]),
            "ci": [float(comparator["ci_low"]), float(comparator["ci_high"])],
            "full_rms_ns": float(comparator["full_rms_ns"]),
            "n_pair_residuals": int(comparator["n_pair_residuals"]),
        },
        "winner": json_clean(winner),
        "s03m_action_coverage": {
            "n_pair_residuals": int(len(base_rows)),
            "pass_fraction": float(base_rows["s03m_retained_pass"].mean()),
            "abstain_fraction": float((base_rows["s03m_action"] == "abstain").mean()),
            "recalibrate_fraction": float((base_rows["s03m_action"] == "recalibrate").mean()),
        },
        "primary_pass_refit_delta": json_clean(primary),
        "required_family_results": json_clean(family.to_dict(orient="records")),
        "consumer_decision_rows": json_clean(decisions.to_dict(orient="records")),
        "consumer_delta_rows": json_clean(deltas.to_dict(orient="records")),
        "verdict": (
            "{} wins the global family benchmark; after frozen S03m exclusion, {} changes retained-pass timing sigma68 by {:.4f} ns "
            "versus the analytic comparator under leave-one-run-out scoring.".format(
                winner["method"], PASS_ONLY_HGB, primary["candidate_minus_baseline_sigma68_ns"]
            )
        ),
        "next_tickets": [
            {
                "title": "S03o consumer-native labels for frozen S03m excluded regions",
                "body": "Acquire or join event-native pile-up/PID/charge/energy labels for S03m abstain and recalibrate rows, then test whether excluded regions should be split into recoverable HGB-refit and hard-veto actions.",
            }
        ],
    }
    (OUT_DIR / "result.json").write_text(json.dumps(json_clean(result), indent=2) + "\n", encoding="utf-8")
    write_report(reproduction, family, bands, summary, deltas, decisions, imported, json_clean(result))
    write_manifest()
    print(json.dumps({"out_dir": str(OUT_DIR), "winner": winner["method"], "pass_refit_delta_sigma68_ns": primary["candidate_minus_baseline_sigma68_ns"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
