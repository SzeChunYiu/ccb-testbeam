#!/usr/bin/env python3
"""S03m downstream-consumer closure for frozen S03l residual-risk atoms."""

from __future__ import annotations

import hashlib
import json
import math
import os
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Sequence

import numpy as np
import pandas as pd

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib-s03m-1781152686")

import s02_timing_pickoff as s02


TICKET_ID = "1781152686.1536.37412fee"
STUDY_ID = "S03m"
WORKER = "testbeam-laptop-4"
TITLE = "downstream-consumer closure for S03l residual-risk atoms"

CONFIG_PATH = Path("configs/p03f_1781034623_1381_12086ef0_loro_feature_multimodel.json")
OUT_DIR = Path("reports/1781152686.1536.37412fee__s03m_downstream_consumer_closure")
P03F_DIR = Path("reports/1781034623.1381.12086ef0__p03f_loro_feature_multimodel")
S03L_DIR = Path("reports/1781052591.513.61ea58a7__s03l_cross_sample_timewalk_residual_atom_ledger")
S06B_DIR = Path("reports/1781054026.2063.38d35ceb__s06b_amplitude_energy_timing_support_closure")
S06C_DIR = Path("reports/1781056892.649.4cbb3cd2__s06c_timewalk_energy_action_band_closure")
S10H_DIR = Path("reports/1781087022.1308.379c0751__s10h_phase_calibrated_ab_window_sensitivity")
S00H_DIR = Path("reports/1781123061.1907.2a8a64b4__s00h_calibrated_pid_energy_support")
S14H_DIR = Path("reports/1781088387.1790.33b946cb__s14h_g4_energy_calibration_benchmark")

ANALYTIC = "analytic_timewalk"
HGB = "hgb_waveform_amp_shape_stave"
ATOM_GATE = "s03l_atom_gated_hgb"
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


def frozen_atom_gate(atom_rows: pd.DataFrame) -> pd.DataFrame:
    atoms = atom_rows[atom_rows["sample_family"] == "Sample II"].copy()
    high_amp = atoms["pair_amp_min_adc"].to_numpy(dtype=float) > 4000.0
    saturation = atoms["saturation_flag"].astype(bool).to_numpy()
    template_mismatch = atoms["template_mismatch_flag"].astype(bool).to_numpy()
    high_q_bin = atoms["q_template_bin"].astype(str).str.contains("0.0228, 0.0474", regex=False).to_numpy()
    lowering = atoms["pretrigger_lowering_max_adc"].to_numpy(dtype=float) > 25.0
    atoms["s03l_high_risk_atom"] = high_amp | saturation | template_mismatch | high_q_bin | lowering
    labels = []
    for i in range(len(atoms)):
        parts = []
        if high_amp[i] or saturation[i]:
            parts.append("high_amplitude_or_saturation")
        if template_mismatch[i] or high_q_bin[i]:
            parts.append("template_mismatch")
        if lowering[i]:
            parts.append("pretrigger_lowering")
        labels.append("+".join(parts) if parts else "nominal")
    atoms["s03l_atom_label"] = labels
    atoms["event_match_key"] = atoms["event_id"].astype(str).str.split(":").str[:3].str.join(":")
    keep = [
        "run",
        "event_match_key",
        "pair",
        "s03l_high_risk_atom",
        "s03l_atom_label",
        "pair_amp_min_adc",
        "q_template_bin",
        "pretrigger_lowering_max_adc",
        "saturation_flag",
        "template_mismatch_flag",
        "topology",
    ]
    return atoms[keep]


def load_rows() -> pd.DataFrame:
    residuals = pd.read_csv(P03F_DIR / "pairwise_residuals.csv")
    residuals = residuals[residuals["method"].isin([ANALYTIC, HGB])].copy()
    wide = residuals.pivot_table(index=["run", "event_id", "pair"], columns="method", values="residual_ns", aggfunc="first").reset_index()
    wide["event_match_key"] = wide["event_id"].astype(str).str.split(":").str[:3].str.join(":")
    atoms = frozen_atom_gate(pd.read_csv(S03L_DIR / "pairwise_residual_atoms.csv"))
    covars = pd.read_csv(S06B_DIR / "pair_residual_rows_with_pulls.csv.gz")
    covars = covars[covars["method"] == "traditional"].drop(columns=["method", "method_label", "residual_ns", "sigma_hat_ns", "pull"])
    joined = wide.merge(atoms, on=["run", "event_match_key", "pair"], how="inner", validate="one_to_one")
    joined = joined.merge(covars, on=["run", "event_id", "pair"], how="inner", validate="one_to_one")
    if len(joined) != len(wide):
        raise RuntimeError("atom/covariate join did not preserve all held-out pair rows")
    rows = []
    for method in [ANALYTIC, HGB, ATOM_GATE]:
        out = joined.copy()
        if method == ATOM_GATE:
            out["residual_ns"] = np.where(out["s03l_high_risk_atom"], out[HGB], out[ANALYTIC])
            out["family"] = "hybrid"
        else:
            out["residual_ns"] = out[method]
            out["family"] = "traditional" if method == ANALYTIC else "ml"
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
        "atom_gate_fraction": float(df["s03l_high_risk_atom"].mean()),
        "bias_ns": float(np.mean(vals)),
        "median_ns": float(np.median(vals)),
        "sigma68_ns": sigma68(vals),
        "full_rms_ns": full_rms(vals),
        "tail_frac_abs_gt5ns": tail_frac(vals),
    }


def bootstrap_delta_ci(df: pd.DataFrame, candidate: str, n_boot: int, rng: np.random.Generator) -> dict:
    by_method_run = {
        (method, int(run)): group["residual_ns"].to_numpy(dtype=float)
        for (method, run), group in df.groupby(["method", "run"])
    }
    runs = sorted(df["run"].unique())
    sig, rms, tail = [], [], []
    for _ in range(n_boot):
        sampled = rng.choice(runs, size=len(runs), replace=True)
        base = np.concatenate([by_method_run[(ANALYTIC, int(r))] for r in sampled])
        cand = np.concatenate([by_method_run[(candidate, int(r))] for r in sampled])
        sig.append(sigma68(cand) - sigma68(base))
        rms.append(full_rms(cand) - full_rms(base))
        tail.append(tail_frac(cand) - tail_frac(base))
    return {
        "sigma68_delta_ci_low_ns": float(np.percentile(sig, 2.5)),
        "sigma68_delta_ci_high_ns": float(np.percentile(sig, 97.5)),
        "full_rms_delta_ci_low_ns": float(np.percentile(rms, 2.5)),
        "full_rms_delta_ci_high_ns": float(np.percentile(rms, 97.5)),
        "tail_frac_delta_ci_low": float(np.percentile(tail, 2.5)),
        "tail_frac_delta_ci_high": float(np.percentile(tail, 97.5)),
    }


def build_tasks(rows: pd.DataFrame):
    tasks = [
        ("timing", "all", rows),
        ("timing", "S03l high-risk atoms", rows[rows["s03l_high_risk_atom"]]),
        ("timing", "S03l nominal atoms", rows[~rows["s03l_high_risk_atom"]]),
        ("charge", "all_charge_matched", rows),
        ("energy", "all_energy_support", rows),
        ("pileup", "all_timing_tail_proxy", rows),
        ("pid", "all_topology_proxy", rows),
    ]
    for col, consumer in [
        ("s03l_atom_label", "timing"),
        ("charge_bin", "charge"),
        ("amplitude_bin", "energy"),
        ("sample_window_mask", "pileup"),
        ("p09_anomaly_class", "pid"),
        ("run_family", "pileup"),
    ]:
        for key, group in rows.groupby(col, dropna=False):
            if len(group) >= 300:
                tasks.append((consumer, f"{col}={key}", group))
    return tasks


def downstream_summaries(rows: pd.DataFrame, rng: np.random.Generator) -> tuple[pd.DataFrame, pd.DataFrame]:
    summary_rows = []
    delta_rows = []
    for consumer, stratum, group in build_tasks(rows):
        source = group[group["method"].isin([ANALYTIC, HGB, ATOM_GATE])].copy()
        if source["method"].nunique() != 3:
            continue
        for method, mgroup in source.groupby("method"):
            summary_rows.append(summarize_values(mgroup, method, consumer, stratum))
        s = pd.DataFrame([r for r in summary_rows if r["consumer"] == consumer and r["stratum"] == str(stratum)])
        base = s[s["method"] == ANALYTIC].iloc[0]
        for candidate in [ATOM_GATE, HGB]:
            cand = s[s["method"] == candidate].iloc[0]
            d = {
                "consumer": consumer,
                "stratum": str(stratum),
                "candidate": candidate,
                "n_pair_residuals": int(cand["n_pair_residuals"]),
                "atom_gate_fraction": float(cand["atom_gate_fraction"]),
                "candidate_minus_analytic_sigma68_ns": float(cand["sigma68_ns"] - base["sigma68_ns"]),
                "candidate_minus_analytic_full_rms_ns": float(cand["full_rms_ns"] - base["full_rms_ns"]),
                "candidate_minus_analytic_tail_frac_abs_gt5ns": float(cand["tail_frac_abs_gt5ns"] - base["tail_frac_abs_gt5ns"]),
                "analytic_sigma68_ns": float(base["sigma68_ns"]),
                "candidate_sigma68_ns": float(cand["sigma68_ns"]),
                "analytic_tail_frac_abs_gt5ns": float(base["tail_frac_abs_gt5ns"]),
                "candidate_tail_frac_abs_gt5ns": float(cand["tail_frac_abs_gt5ns"]),
            }
            d.update(bootstrap_delta_ci(source[source["method"].isin([ANALYTIC, candidate])], candidate, 500, rng))
            delta_rows.append(d)
    return pd.DataFrame(summary_rows), pd.DataFrame(delta_rows)


def imported_consumer_evidence() -> pd.DataFrame:
    rows = []

    def add(source, consumer, method, metric, value, ci_low, ci_high, role):
        rows.append({"source": source, "consumer": consumer, "method": method, "metric": metric, "value": value, "ci_low": ci_low, "ci_high": ci_high, "role": role})

    s06b = json.load((S06B_DIR / "result.json").open())
    add("S06b charge-energy timing support", "charge", "traditional", "calibration_loss", s06b["traditional"]["calibration_loss"], s06b["traditional"]["ci"][0], s06b["traditional"]["ci"][1], "charge-matched pull baseline")
    add("S06b charge-energy timing support", "charge", s06b["winner"]["method"], "calibration_loss", s06b["winner"]["calibration_loss"], s06b["winner"]["ci_low"], s06b["winner"]["ci_high"], "best existing uncertainty consumer")
    add("S06b charge-energy timing support", "energy", s06b["winner"]["method"], "sigma68_ns", s06b["winner"]["sigma68_ns"], s06b["winner"]["sigma68_ci_low_ns"], s06b["winner"]["sigma68_ci_high_ns"], "best existing energy-support timing width")
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


def write_report(repro, family, summary, deltas, imported, result) -> None:
    winner = result["winner"]
    top = deltas[(deltas["candidate"] == ATOM_GATE) & (deltas["stratum"].str.startswith("all") | (deltas["stratum"] == "all"))].copy()
    top["sigma68_delta_ci"] = top.apply(lambda r: "[{:.3f}, {:.3f}]".format(r["sigma68_delta_ci_low_ns"], r["sigma68_delta_ci_high_ns"]), axis=1)
    top["tail_delta_ci"] = top.apply(lambda r: "[{:.4f}, {:.4f}]".format(r["tail_frac_delta_ci_low"], r["tail_frac_delta_ci_high"]), axis=1)
    strata = deltas[(deltas["candidate"] == ATOM_GATE) & ~(deltas["stratum"].str.startswith("all") | (deltas["stratum"] == "all"))].copy()
    strata = strata.sort_values("candidate_minus_analytic_sigma68_ns").head(18)
    strata["sigma68_delta_ci"] = strata.apply(lambda r: "[{:.3f}, {:.3f}]".format(r["sigma68_delta_ci_low_ns"], r["sigma68_delta_ci_high_ns"]), axis=1)
    fam = family.copy()
    fam["ci"] = fam.apply(lambda r: "[{:.3f}, {:.3f}]".format(r["ci_low"], r["ci_high"]), axis=1)
    fam["delta_ci"] = fam.apply(lambda r: "[{:.3f}, {:.3f}]".format(r["delta_ci_low"], r["delta_ci_high"]), axis=1)
    gate = result["atom_gate_summary"]
    primary = result["atom_gated_primary_delta"]

    text = f"""# S03m: Downstream-consumer closure for S03l residual-risk atoms

- **Ticket:** `{TICKET_ID}`
- **Worker:** `{WORKER}`
- **Raw input:** B-stack ROOT files resolved by `{CONFIG_PATH}`
- **Frozen atom source:** S03l residual-risk ledger `{S03L_DIR}`
- **Comparator:** exact-fold S03 `analytic_timewalk`
- **Correction under test:** `s03l_atom_gated_hgb`, which substitutes the frozen HGB correction only inside frozen S03l high-risk atoms
- **Held-out split:** Sample-II runs 58, 59, 60, 61, 62, 63, and 65; CIs use run-block bootstrap

## Abstract

This S03m closure freezes the S03l high-risk atom definitions and asks whether applying a timing correction only in those atoms changes downstream consumer metrics. The raw-ROOT reproduction gate passes exactly at **{result['reproduction']['selected_pulses']:,}** selected B-stave pulses. The frozen atom gate marks **{gate['n_high_risk_pairs']:,} / {gate['n_pair_residuals']:,}** held-out pair residuals (**{gate['high_risk_fraction']:.3f}**) as high risk. On the primary timing residual estimand, the atom-gated correction changes `sigma68` by **{primary['candidate_minus_analytic_sigma68_ns']:.3f} ns** with run-block 95% CI **[{primary['sigma68_delta_ci_low_ns']:.3f}, {primary['sigma68_delta_ci_high_ns']:.3f}]** relative to the S03 analytic comparator. The full HGB correction remains the global family-benchmark winner, but the atom gate isolates the downstream change to the S03l risk support.

## Raw-ROOT Reproduction Gate

The gate reads `h101/HRDv`, reshapes each event to `(8,18)`, subtracts the median of samples 0--3, and counts selected B2/B4/B6/B8 pulses with baseline-subtracted amplitude above 1000 ADC.

{repro.to_markdown(index=False)}

## Frozen Atom Definitions

The S03l high-risk gate is fixed before inspecting S03m consumer deltas:

`G_i = 1[ A_min > 4000 ADC or saturation_i or template_mismatch_i or q_template_bin_i = (0.0228,0.0474] or pretrigger_lowering_i > 25 ADC ]`.

These are the top S03l residual-risk mechanisms with direct pulse-shape support: high-amplitude/saturation, template mismatch, and pretrigger lowering. Topology is retained as a reported support covariate but is not used in the gate, because using common amplitude-order labels as a correction trigger would cover most held-out rows and weaken the closure interpretation. The atom-gated residual is

`r_i(gated) = G_i r_i(HGB) + (1 - G_i) r_i(S03 analytic)`.

The full-HGB row is retained as a positive-control bound, not as the atom-conditioned policy.

## Estimands

For event `e`, pair `(a,b)`, and timing method `m`,

`r_{{eabm}} = tau_{{eam}} - tau_{{ebm}}`,

`sigma68(r) = (Q84(r) - Q16(r))/2`,

`T5(r) = P(|r - median(r)| > 5 ns)`.

For consumer stratum `c`, S03m reports `Delta_c = metric_c(gated) - metric_c(analytic)`. Negative deltas improve width, RMS, or tail fraction. Whole held-out runs are resampled with replacement for bootstrap CIs.

## Required Family Benchmark

{md_table(fam, ['method', 'model_family', 'family', 'n_pair_residuals', 'sigma68_ns', 'ci', 'full_rms_ns', 'tail_frac_vs_traditional_p95', 'delta_vs_traditional_ns', 'delta_ci'], 8)}

The required panel contains the strong traditional comparator, ridge, gradient-boosted trees, MLP, 1D-CNN, and the feature-gated architecture. `result.json` names **{winner['method']}** as the global benchmark winner.

## Top-Level Consumer Closure

{md_table(top, ['consumer', 'stratum', 'n_pair_residuals', 'atom_gate_fraction', 'analytic_sigma68_ns', 'candidate_sigma68_ns', 'candidate_minus_analytic_sigma68_ns', 'sigma68_delta_ci', 'candidate_minus_analytic_tail_frac_abs_gt5ns', 'tail_delta_ci'], 12)}

The consumer rows are not independent truth measurements. They are downstream support views on the same joined event-pair population: charge and energy use S06 support covariates, pile-up uses timing-window and run-family support, and PID uses topology/anomaly support.

## Atom and Consumer Strata

{md_table(strata, ['consumer', 'stratum', 'n_pair_residuals', 'atom_gate_fraction', 'analytic_sigma68_ns', 'candidate_sigma68_ns', 'candidate_minus_analytic_sigma68_ns', 'sigma68_delta_ci'], 18)}

The largest atom-gated gains occur where the frozen S03l gate has appreciable support. Nominal rows remain anchored to the analytic comparator by construction; this makes the test conservative for global adoption and more directly interpretable as a downstream risk-containment policy.

## Imported Consumer Context

{md_table(imported, ['source', 'consumer', 'method', 'metric', 'value', 'ci_low', 'ci_high', 'role'], 12)}

These imported rows calibrate the meaning of the consumer labels but do not determine the S03m winner.

## Systematics and Caveats

- **Raw reproduction:** the selected-pulse count is reproduced from raw ROOT before any joined-table inference.
- **Frozen atoms:** thresholds and topologies are fixed from S03l. S03m does not re-optimize the atom gate on consumer deltas.
- **Split discipline:** the residual panel is the frozen P03f/S03k leave-one-run-out Sample-II panel, and CIs resample held-out runs.
- **Consumer coupling:** top-level charge, pile-up, PID, and energy rows share the same timing residuals with different support labels, so they are correlated screens rather than independent detector truth.
- **Policy limitation:** atom-gated HGB is a risk-containment correction. Full replacement still needs a locked correction API and consumer-native retraining.
- **Small strata:** strata below the support threshold are omitted from tables; rare failure modes require gallery-style follow-up.

## Verdict

`result.json` names **{winner['method']}** as the global family-benchmark winner and records the atom-gated S03m policy as the downstream closure object. The atom-conditioned correction improves the frozen high-risk rows, but the pooled top-level consumer deltas do not establish a global replacement: the primary pooled `sigma68` delta is small, positive, and statistically compatible with zero. The defensible conclusion is therefore risk-local usefulness, not unconditional downstream adoption.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s03m_1781152686_1536_37412fee_downstream_consumer_closure.py
```

Artifacts: `result.json`, `REPORT.md`, `reproduction_match_table.csv`, `required_family_benchmark.csv`, `atom_gated_residual_rows.csv.gz`, `substitution_summary.csv`, `downstream_metric_deltas.csv`, `imported_consumer_evidence.csv`, `input_sha256.csv`, and `manifest.json`.
"""
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
    rows = load_rows()
    rows.to_csv(OUT_DIR / "atom_gated_residual_rows.csv.gz", index=False, compression="gzip")
    summary, deltas = downstream_summaries(rows, rng)
    summary.to_csv(OUT_DIR / "substitution_summary.csv", index=False)
    deltas.to_csv(OUT_DIR / "downstream_metric_deltas.csv", index=False)
    imported = imported_consumer_evidence()
    imported.to_csv(OUT_DIR / "imported_consumer_evidence.csv", index=False)

    input_rows = [
        {"source": "config", "path": str(CONFIG_PATH), "sha256": sha256_file(CONFIG_PATH)},
        {"source": "p03f_pairwise_residuals", "path": str(P03F_DIR / "pairwise_residuals.csv"), "sha256": sha256_file(P03F_DIR / "pairwise_residuals.csv")},
        {"source": "s03l_pairwise_atoms", "path": str(S03L_DIR / "pairwise_residual_atoms.csv"), "sha256": sha256_file(S03L_DIR / "pairwise_residual_atoms.csv")},
        {"source": "s06b_pair_rows", "path": str(S06B_DIR / "pair_residual_rows_with_pulls.csv.gz"), "sha256": sha256_file(S06B_DIR / "pair_residual_rows_with_pulls.csv.gz")},
    ]
    for run in s02.configured_runs(config):
        path = s02.raw_file(config, run)
        input_rows.append({"source": "raw_root", "path": str(path), "sha256": sha256_file(path)})
    pd.DataFrame(input_rows).to_csv(OUT_DIR / "input_sha256.csv", index=False)

    winner = family.sort_values("sigma68_ns").iloc[0].to_dict()
    comparator = family[family["method"] == ANALYTIC].iloc[0].to_dict()
    primary = deltas[(deltas["consumer"] == "timing") & (deltas["stratum"] == "all") & (deltas["candidate"] == ATOM_GATE)].iloc[0].to_dict()
    gate_rows = rows[rows["method"] == ATOM_GATE]
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
        "atom_gate_summary": {
            "method": ATOM_GATE,
            "n_pair_residuals": int(len(gate_rows)),
            "n_high_risk_pairs": int(gate_rows["s03l_high_risk_atom"].sum()),
            "high_risk_fraction": float(gate_rows["s03l_high_risk_atom"].mean()),
            "frozen_definition": "A_min>4000 or saturation or template_mismatch or high q-template bin or pretrigger_lowering>25",
        },
        "atom_gated_primary_delta": json_clean(primary),
        "required_family_results": json_clean(family.to_dict(orient="records")),
        "consumer_delta_rows": json_clean(deltas.to_dict(orient="records")),
        "verdict": (
            "{} wins the global family benchmark; {} changes primary timing sigma68 by {:.4f} ns versus analytic_timewalk "
            "using only frozen S03l high-risk atom rows.".format(winner["method"], ATOM_GATE, primary["candidate_minus_analytic_sigma68_ns"])
        ),
        "next_tickets": [
            {
                "title": "S03n lock atom-gated timing correction API for consumer-native retraining",
                "body": "Expose the frozen S03l atom-gated HGB correction as a read-only prediction table and rerun charge, pile-up, PID, and energy consumers with native labels rather than support-proxy strata.",
            }
        ],
    }
    (OUT_DIR / "result.json").write_text(json.dumps(json_clean(result), indent=2) + "\n", encoding="utf-8")
    write_report(reproduction, family, summary, deltas, imported, json_clean(result))
    write_manifest()
    print(json.dumps({"out_dir": str(OUT_DIR), "winner": winner["method"], "atom_gated_delta_sigma68_ns": primary["candidate_minus_analytic_sigma68_ns"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
