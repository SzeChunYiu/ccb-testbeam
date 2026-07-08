#!/usr/bin/env python3
"""S02j support-drift audit for the S02i residual-correction benchmark.

The script rechecks the S02i raw ROOT reproduction gate, then treats the frozen
S02i leave-one-run-out predictions as train-fold predictions and asks whether
using each correction in a timing selection changes charge/current/topology/run
support relative to the uncorrected CFD20 timing gate.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Iterable, Sequence

os.environ.setdefault("MPLCONFIGDIR", "/tmp/s02j_mplconfig")
os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("MKL_NUM_THREADS", "2")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "2")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
S02I_SCRIPT = ROOT / "scripts/s02i_1781032083_463_2d9c6a45_pretrigger_atom_transfer.py"
METHOD_ORDER = [
    "traditional_atom_slope",
    "ridge",
    "gradient_boosted_trees",
    "mlp",
    "cnn1d",
    "siamese_cnn_meta",
]


def import_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, str(path))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


s02i = import_module(S02I_SCRIPT, "s02i_source_for_s02j")


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


def json_ready(value):
    if isinstance(value, dict):
        return {str(k): json_ready(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_ready(v) for v in value]
    if isinstance(value, tuple):
        return [json_ready(v) for v in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, (np.floating, float)):
        out = float(value)
        return out if math.isfinite(out) else None
    return value


def sigma68(values: Sequence[float]) -> float:
    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]
    if len(arr) == 0:
        return float("nan")
    q16, q84 = np.quantile(arr, [0.16, 0.84])
    return float((q84 - q16) / 2.0)


def tvd(values_a: Iterable, values_b: Iterable, categories: Sequence) -> float:
    a = np.asarray(list(values_a))
    b = np.asarray(list(values_b))
    if len(a) == 0 or len(b) == 0:
        return float("nan")
    pa = np.asarray([(a == cat).mean() for cat in categories], dtype=float)
    pb = np.asarray([(b == cat).mean() for cat in categories], dtype=float)
    return float(0.5 * np.abs(pa - pb).sum())


def configured_runs(config: dict) -> list[int]:
    source_config = json.loads((ROOT / config["source_s02i_config"]).read_text(encoding="utf-8"))
    return s02i.configured_runs(source_config)


def raw_file(config: dict, run: int) -> Path:
    return ROOT / Path(config["raw_root_dir"]) / f"hrdb_run_{int(run):04d}.root"


def load_inputs(config: dict) -> tuple[dict, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    source_config = json.loads((ROOT / config["source_s02i_config"]).read_text(encoding="utf-8"))
    src = ROOT / Path(config["source_s02i_report_dir"])
    pred_path = src / "heldout_predictions.csv.gz"
    pair_path = src / "sample_ii_pair_table.csv.gz"
    summary_path = src / "method_summary.csv"
    missing = [str(p) for p in [pred_path, pair_path, summary_path] if not p.exists()]
    if missing:
        raise FileNotFoundError("missing S02i artifacts: " + ", ".join(missing))
    return source_config, pd.read_csv(pred_path), pd.read_csv(pair_path), pd.read_csv(summary_path)


def add_support_features(pairs: pd.DataFrame, config: dict) -> pd.DataFrame:
    out = pairs.copy()
    out["event_uid"] = out["event_id"].astype(str).str.split(":").str[-1].astype(int)
    out["event_order_proxy"] = out.groupby("run")["event_uid"].rank(pct=True, method="average")
    out["charge_bin"] = pd.cut(
        out["min_amplitude_adc"],
        bins=[float(x) for x in config["charge_bins_adc"]],
        labels=False,
        include_lowest=True,
        right=False,
    ).astype(int)
    out["current_proxy_bin"] = pd.cut(
        out["event_order_proxy"],
        bins=[float(x) for x in config["current_proxy_quantiles"]],
        labels=False,
        include_lowest=True,
    ).astype(int)
    out["run_family"] = out["run"].astype(int).astype(str)
    out["late_peak_proxy"] = (out["max_peak_sample"] >= 7).astype(int)
    out["low_charge_proxy"] = (out["min_amplitude_adc"] < 1300.0).astype(int)
    return out


def join_predictions(pred: pd.DataFrame, pairs: pd.DataFrame, config: dict) -> pd.DataFrame:
    methods = ["uncorrected_cfd20", *config["required_methods"]]
    missing = sorted(set(methods) - set(pred["method"].unique()))
    if missing:
        raise ValueError("missing required S02i prediction methods: " + ", ".join(missing))
    cols = [
        "event_id",
        "run",
        "pair",
        "min_amplitude_adc",
        "max_peak_sample",
        "event_order_proxy",
        "charge_bin",
        "current_proxy_bin",
        "run_family",
        "late_peak_proxy",
        "low_charge_proxy",
    ]
    joined = pred[pred["method"].isin(methods)].merge(pairs[cols], on=["event_id", "run", "pair"], how="left", validate="many_to_one")
    if joined[cols].isna().any().any():
        raise RuntimeError("prediction/support join has missing values")
    return joined


def add_gates(joined: pd.DataFrame, config: dict) -> pd.DataFrame:
    out = joined.copy()
    cut = float(config["selection_abs_residual_ns"])
    raw = out[out["method"] == "uncorrected_cfd20"][["event_id", "pair", "residual_ns"]].copy()
    raw["baseline_pass_abs5"] = raw["residual_ns"].abs() <= cut
    out = out.merge(raw[["event_id", "pair", "baseline_pass_abs5"]], on=["event_id", "pair"], how="left", validate="many_to_one")
    out["method_pass_abs5"] = out["corrected_residual_ns"].abs() <= cut
    out["method_pass_fixed_eff"] = False
    out["fixed_eff_threshold_ns"] = np.nan
    for method in [m for m in out["method"].unique() if m != "uncorrected_cfd20"]:
        for run in sorted(out["run"].unique()):
            train_raw = out[(out["method"] == "uncorrected_cfd20") & (out["run"] != run)]
            baseline_eff = float(train_raw["baseline_pass_abs5"].mean())
            train_method = out[(out["method"] == method) & (out["run"] != run)]
            threshold = float(np.quantile(train_method["corrected_residual_ns"].abs().to_numpy(dtype=float), baseline_eff))
            mask = (out["method"] == method) & (out["run"] == run)
            out.loc[mask, "fixed_eff_threshold_ns"] = threshold
            out.loc[mask, "method_pass_fixed_eff"] = out.loc[mask, "corrected_residual_ns"].abs() <= threshold
    out.loc[out["method"] == "uncorrected_cfd20", "method_pass_fixed_eff"] = out.loc[
        out["method"] == "uncorrected_cfd20", "baseline_pass_abs5"
    ]
    out.loc[out["method"] == "uncorrected_cfd20", "fixed_eff_threshold_ns"] = cut
    return out


def support_metrics(frame: pd.DataFrame, method_pass_col: str) -> dict:
    baseline = frame[frame["baseline_pass_abs5"].astype(bool)]
    selected = frame[frame[method_pass_col].astype(bool)]
    charge_cats = sorted(frame["charge_bin"].dropna().unique())
    current_cats = sorted(frame["current_proxy_bin"].dropna().unique())
    pair_cats = ["B4-B6", "B4-B8", "B6-B8"]
    run_cats = sorted(frame["run_family"].dropna().unique())
    charge = tvd(baseline["charge_bin"], selected["charge_bin"], charge_cats)
    current = tvd(baseline["current_proxy_bin"], selected["current_proxy_bin"], current_cats)
    topo = tvd(baseline["pair"], selected["pair"], pair_cats)
    run_tvd = tvd(baseline["run_family"], selected["run_family"], run_cats)
    late = abs(float(selected["late_peak_proxy"].mean()) - float(baseline["late_peak_proxy"].mean())) if len(selected) and len(baseline) else float("nan")
    lowq = abs(float(selected["low_charge_proxy"].mean()) - float(baseline["low_charge_proxy"].mean())) if len(selected) and len(baseline) else float("nan")
    vals = frame.loc[frame[method_pass_col].astype(bool), "corrected_residual_ns"].to_numpy(dtype=float)
    raw_vals = frame.loc[frame["baseline_pass_abs5"].astype(bool), "residual_ns"].to_numpy(dtype=float)
    return {
        "n_pairs": int(len(frame)),
        "n_events": int(frame["event_id"].nunique()),
        "baseline_efficiency_abs5": float(frame["baseline_pass_abs5"].mean()),
        "method_efficiency": float(frame[method_pass_col].mean()),
        "efficiency_delta": float(frame[method_pass_col].mean() - frame["baseline_pass_abs5"].mean()),
        "baseline_sigma68_selected_ns": sigma68(raw_vals),
        "method_sigma68_selected_ns": sigma68(vals),
        "charge_support_tvd": charge,
        "current_proxy_tvd": current,
        "topology_support_tvd": topo,
        "run_family_tvd": run_tvd,
        "late_peak_fraction_delta": late,
        "low_charge_fraction_delta": lowq,
        "support_drift_max": float(np.nanmax([charge, current, topo, run_tvd, late, lowq])),
    }


def per_run_metrics(joined: pd.DataFrame, gate: str) -> pd.DataFrame:
    pass_col = "method_pass_abs5" if gate == "absolute_abs5" else "method_pass_fixed_eff"
    rows = []
    for (method, run), frame in joined.groupby(["method", "run"]):
        if method == "uncorrected_cfd20" and gate == "fixed_eff_abs5_trainmatched":
            continue
        row = {"method": method, "heldout_run": int(run), "gate": gate}
        row.update(support_metrics(frame, pass_col))
        rows.append(row)
    return pd.DataFrame(rows)


def bootstrap_summary(joined: pd.DataFrame, config: dict, gate: str, rng: np.random.Generator) -> pd.DataFrame:
    pass_col = "method_pass_abs5" if gate == "absolute_abs5" else "method_pass_fixed_eff"
    rows = []
    methods = [m for m in config["required_methods"]]
    for method in methods:
        sub = joined[joined["method"] == method].reset_index(drop=True)
        point = support_metrics(sub, pass_col)
        runs = np.asarray(sorted(sub["run"].unique()), dtype=int)
        by_run = {}
        for run, df in sub.groupby("run"):
            by_run[int(run)] = [idx.to_numpy(dtype=int) for _, idx in df.groupby("event_id").groups.items()]
        boot_rows = []
        for _ in range(int(config["bootstrap_samples"])):
            pieces = []
            for run in rng.choice(runs, size=len(runs), replace=True):
                event_groups = by_run[int(run)]
                chosen = rng.integers(0, len(event_groups), size=len(event_groups))
                pieces.extend(event_groups[int(i)] for i in chosen)
            boot_rows.append(support_metrics(sub.iloc[np.concatenate(pieces)], pass_col))
        boot = pd.DataFrame(boot_rows)
        row = {"method": method, "gate": gate, **point}
        for col in [
            "method_efficiency",
            "efficiency_delta",
            "method_sigma68_selected_ns",
            "charge_support_tvd",
            "current_proxy_tvd",
            "topology_support_tvd",
            "run_family_tvd",
            "late_peak_fraction_delta",
            "low_charge_fraction_delta",
            "support_drift_max",
        ]:
            row[f"{col}_ci_low"] = float(np.nanquantile(boot[col], 0.025))
            row[f"{col}_ci_high"] = float(np.nanquantile(boot[col], 0.975))
        rows.append(row)
    return pd.DataFrame(rows)


def leakage_checks(config: dict, joined: pd.DataFrame, reproduction: pd.DataFrame) -> pd.DataFrame:
    methods = ["uncorrected_cfd20", *config["required_methods"]]
    return pd.DataFrame(
        [
            {"check": "raw_root_reproduction_passes", "value": bool(reproduction["pass"].all()), "pass": bool(reproduction["pass"].all())},
            {"check": "required_methods_present", "value": ",".join(sorted(joined["method"].unique())), "pass": set(methods) <= set(joined["method"].unique())},
            {"check": "one_prediction_per_method_event_pair", "value": int(joined.groupby(["method", "event_id", "pair"]).size().max()), "pass": bool(joined.groupby(["method", "event_id", "pair"]).size().max() == 1)},
            {"check": "all_support_features_finite", "value": int(np.isfinite(joined[["min_amplitude_adc", "max_peak_sample", "event_order_proxy"]]).sum().sum()), "pass": bool(np.isfinite(joined[["min_amplitude_adc", "max_peak_sample", "event_order_proxy"]]).all().all())},
            {"check": "fixed_eff_thresholds_finite", "value": int(np.isfinite(joined["fixed_eff_threshold_ns"]).sum()), "pass": bool(np.isfinite(joined["fixed_eff_threshold_ns"]).all())},
        ]
    )


def fmt_repro(df: pd.DataFrame) -> str:
    return "\n".join(
        f"| {r.quantity} | {int(r.report_value)} | {int(r.reproduced)} | {int(r.delta)} | {int(r.tolerance)} | {'yes' if bool(r.pass_) else 'no'} |"
        for r in df.rename(columns={"pass": "pass_"}).itertuples()
    )


def fmt_support(summary: pd.DataFrame, gate: str) -> str:
    rows = []
    sub = summary[summary["gate"] == gate].copy()
    sub["order"] = sub["method"].map({m: i for i, m in enumerate(METHOD_ORDER)})
    for r in sub.sort_values("order").itertuples():
        rows.append(
            f"| {r.method} | {r.method_efficiency:.4f} [{r.method_efficiency_ci_low:.4f}, {r.method_efficiency_ci_high:.4f}] | "
            f"{r.support_drift_max:.4f} [{r.support_drift_max_ci_low:.4f}, {r.support_drift_max_ci_high:.4f}] | "
            f"{r.charge_support_tvd:.4f} [{r.charge_support_tvd_ci_low:.4f}, {r.charge_support_tvd_ci_high:.4f}] | "
            f"{r.current_proxy_tvd:.4f} [{r.current_proxy_tvd_ci_low:.4f}, {r.current_proxy_tvd_ci_high:.4f}] | "
            f"{r.topology_support_tvd:.4f} [{r.topology_support_tvd_ci_low:.4f}, {r.topology_support_tvd_ci_high:.4f}] | "
            f"{r.run_family_tvd:.4f} [{r.run_family_tvd_ci_low:.4f}, {r.run_family_tvd_ci_high:.4f}] |"
        )
    return "\n".join(rows)


def fmt_timing(summary: pd.DataFrame) -> str:
    rows = []
    fixed = summary[summary["gate"] == "fixed_eff_abs5_trainmatched"].copy()
    fixed["order"] = fixed["method"].map({m: i for i, m in enumerate(METHOD_ORDER)})
    for r in fixed.sort_values("order").itertuples():
        rows.append(
            f"| {r.method} | {r.method_sigma68_selected_ns:.3f} [{r.method_sigma68_selected_ns_ci_low:.3f}, {r.method_sigma68_selected_ns_ci_high:.3f}] | "
            f"{r.efficiency_delta:+.4f} [{r.efficiency_delta_ci_low:+.4f}, {r.efficiency_delta_ci_high:+.4f}] |"
        )
    return "\n".join(rows)


def fmt_per_run(per_run: pd.DataFrame, winner: str) -> str:
    keep = per_run[(per_run["gate"] == "fixed_eff_abs5_trainmatched") & (per_run["method"].isin(["traditional_atom_slope", winner]))]
    rows = []
    for r in keep.sort_values(["heldout_run", "method"]).itertuples():
        rows.append(
            f"| {int(r.heldout_run)} | {r.method} | {r.method_efficiency:.4f} | {r.support_drift_max:.4f} | "
            f"{r.charge_support_tvd:.4f} | {r.current_proxy_tvd:.4f} | {r.topology_support_tvd:.4f} |"
        )
    return "\n".join(rows)


def fmt_checks(checks: pd.DataFrame) -> str:
    return "\n".join(f"| {r.check} | {r.value} | {'yes' if bool(r.pass_) else 'no'} |" for r in checks.rename(columns={"pass": "pass_"}).itertuples())


def write_report(out_dir: Path, config: dict, numbers: dict) -> None:
    command = f"{sys.executable} scripts/s02j_1781099999_773_32991407_support_drift_audit.py --config {numbers['config_path']}"
    if numbers["decision_rule"] == "support_safe_min_timing_sigma":
        decision_label = "support-safe winner"
        gate_phrase = (
            f"its fixed-efficiency support-drift 95% CI high is `{numbers['winner_drift_ci_high']:.4f}`, "
            f"below the configured gate `{config['support_drift_ci_high_gate']}`"
        )
        operational_phrase = (
            "fixed-efficiency use keeps charge/current/topology/run support shifts inside the configured audit gate for this dataset"
        )
    else:
        decision_label = "lowest-drift fallback winner"
        gate_phrase = (
            f"no method's fixed-efficiency support-drift 95% CI high is at or below the configured gate "
            f"`{config['support_drift_ci_high_gate']}`; the selected fallback has the lowest CI high "
            f"(`{numbers['winner_drift_ci_high']:.4f}`)"
        )
        operational_phrase = (
            "fixed-efficiency use reduces but does not clear the configured support-drift audit gate, so adoption should be treated as conditional"
        )
    md = fr"""# S02j: Support-Drift Audit For S02i Residual Correction

- **Study ID:** S02j
- **Ticket:** {config["ticket"]}
- **Worker:** {config["worker"]}
- **Input:** raw B-stack ROOT files under `{config["raw_root_dir"]}` plus frozen S02i held-out predictions from `{config["source_s02i_report_dir"]}`
- **Split:** Sample-II leave-one-run-out by run; support confidence intervals use run/event bootstrap
- **Primary support metric:** maximum total-variation or fraction drift over charge, current proxy, topology, run-family, late-peak, and low-charge supports
- **Winner rule:** lowest S02i mean held-out-run sigma68 among methods whose fixed-efficiency support-drift 95% CI high is no larger than `{config["support_drift_ci_high_gate"]}`
- **Git commit:** `{numbers["git_commit"]}`

## 1. Question And Raw-ROOT Reproduction

The S02j question is whether the S02i winning `siamese_cnn_meta` correction is only a resolution improvement, or whether it changes the charge/current/topology support of timing-selected rows enough to bias downstream physics selections. The audit starts by rerunning the same selected-pulse count gate directly from raw ROOT.

| Quantity | Report value | Reproduced | Delta | Tolerance | Pass? |
|---|---:|---:|---:|---:|---|
{numbers["repro_rows"]}

The support audit then uses `{numbers["n_pairs"]}` held-out pair rows and `{numbers["n_events"]}` events from S02i. All method predictions are frozen leave-one-run-out predictions: ridge, gradient-boosted trees, MLP, 1D-CNN, the strong traditional `traditional_atom_slope` comparator, and the pair-symmetric `siamese_cnn_meta` architecture.

## 2. Estimands

For each pair row \(i\), the uncorrected timing selection is

\\[
B_i = \\mathbb{{1}}(|r_i| \\le 5\\,\\mathrm{{ns}}),
\\]

where \(r_i\) is the raw CFD20 pair residual. For method \(m\), the corrected residual is

\\[
\\epsilon_i^{{(m)}} = r_i - \\hat f_m(X_i).
\\]

Two operating points are audited. The absolute gate uses \(A_i^{{(m)}}=\\mathbb{{1}}(|\\epsilon_i^{{(m)}}|\\le 5\\,\\mathrm{{ns}})\). The fixed-efficiency gate chooses a threshold \(\\tau_m^{{(-k)}}\) from training runs only so that the train-run corrected acceptance equals the train-run uncorrected 5 ns acceptance, then applies \(F_i^{{(m)}}=\\mathbb{{1}}(|\\epsilon_i^{{(m)}}|\\le \\tau_m^{{(-k)}})\) to held-out run \(k\).

Support drift is measured against the uncorrected accepted set in the same rows. For categorical supports, the metric is total variation distance,

\\[
D_{{\\mathrm{{TV}}}}(p,q)=\\frac12\\sum_c |p_c-q_c|.
\\]

The headline support-drift score is the maximum over charge-bin TVD, current-proxy-bin TVD, topology-pair TVD, run-family TVD, late-peak fraction shift, and low-charge fraction shift.

## 3. Support Results: Absolute 5 ns Gate

The absolute gate answers what happens if a downstream analysis simply replaces the raw residual by the corrected residual and keeps the same 5 ns cut.

| Method | Efficiency [95% CI] | Max support drift [95% CI] | Charge TVD [95% CI] | Current TVD [95% CI] | Topology TVD [95% CI] | Run-family TVD [95% CI] |
|---|---:|---:|---:|---:|---:|---:|
{numbers["absolute_rows"]}

## 4. Support Results: Train-Fold Fixed Efficiency

The fixed-efficiency gate isolates support reweighting from the trivial gain in timing acceptance. Thresholds are determined only from non-held-out runs.

| Method | Efficiency [95% CI] | Max support drift [95% CI] | Charge TVD [95% CI] | Current TVD [95% CI] | Topology TVD [95% CI] | Run-family TVD [95% CI] |
|---|---:|---:|---:|---:|---:|---:|
{numbers["fixed_rows"]}

The selected-residual resolution under the fixed-efficiency gate is:

| Method | Selected sigma68 ns [95% CI] | Efficiency delta vs raw gate [95% CI] |
|---|---:|---:|
{numbers["timing_rows"]}

Representative held-out run rows for the traditional comparator and winner:

| Held-out run | Method | Efficiency | Max drift | Charge TVD | Current TVD | Topology TVD |
|---:|---|---:|---:|---:|---:|---:|
{numbers["per_run_rows"]}

## 5. Decision

The {decision_label} is **{numbers["winner"]}**. Under the decision rule, {gate_phrase}, while its S02i timing benchmark mean-run sigma68 is `{numbers["winner_s02i_sigma"]:.3f} ns`. The best traditional comparator remains `traditional_atom_slope` with S02i mean-run sigma68 `{numbers["traditional_s02i_sigma"]:.3f} ns`.

Operational interpretation: the S02i winner should not be promoted as an unqualified physics-production correction from this audit alone. A naive absolute 5 ns replacement mostly changes efficiency; {operational_phrase}. Downstream PID, charge, and energy analyses should propagate the reweighting uncertainty because the support variables are proxies rather than full detector truth.

## 6. Leakage And Systematics

| Check | Value | Pass? |
|---|---:|---|
{numbers["check_rows"]}

Systematics and caveats: current is approximated by event-order quantiles within run, not by a scaler readback. Charge support uses minimum pair amplitude bins, so it is conservative for two-ended charge but not a calibrated energy spectrum. Topology is the downstream pair identity only. Pair rows share events; therefore all confidence intervals resample runs and then events, carrying all three pair rows for a sampled event. The fixed-efficiency threshold is train-fold frozen, which tests deployable use more directly than fitting thresholds on the held-out run. This is still a data-only support audit; it does not prove the correction is unbiased for every downstream physics observable.

## 7. Reproducibility

```bash
{command}
```

Primary artifacts: `result.json`, `REPORT.md`, `manifest.json`, `reproduction_match_table.csv`, `support_summary.csv`, `per_run_support.csv`, `joined_support_predictions.csv.gz`, `leakage_checks.csv`, and figures.
"""
    (out_dir / "REPORT.md").write_text(md, encoding="utf-8")


def plot_outputs(out_dir: Path, summary: pd.DataFrame, winner: str) -> None:
    fixed = summary[summary["gate"] == "fixed_eff_abs5_trainmatched"].copy()
    fixed["order"] = fixed["method"].map({m: i for i, m in enumerate(METHOD_ORDER)})
    fixed = fixed.sort_values("order")
    fig, ax = plt.subplots(figsize=(8.8, 4.4))
    x = np.arange(len(fixed))
    ax.errorbar(
        x,
        fixed["support_drift_max"],
        yerr=[
            fixed["support_drift_max"] - fixed["support_drift_max_ci_low"],
            fixed["support_drift_max_ci_high"] - fixed["support_drift_max"],
        ],
        fmt="o",
        capsize=3,
    )
    ax.axhline(0.05, color="tab:red", linestyle="--", linewidth=1)
    ax.set_xticks(x)
    ax.set_xticklabels(fixed["method"], rotation=25, ha="right")
    ax.set_ylabel("max support drift")
    ax.set_title("S02j fixed-efficiency support drift")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_fixed_eff_support_drift.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7.4, 4.2))
    sub = fixed[fixed["method"].isin(["traditional_atom_slope", winner])]
    x = np.arange(len(sub))
    width = 0.18
    for j, col in enumerate(["charge_support_tvd", "current_proxy_tvd", "topology_support_tvd", "run_family_tvd"]):
        ax.bar(x + (j - 1.5) * width, sub[col], width=width, label=col.replace("_", " "))
    ax.set_xticks(x)
    ax.set_xticklabels(sub["method"], rotation=15, ha="right")
    ax.set_ylabel("support drift component")
    ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_winner_component_drift.png", dpi=150)
    plt.close(fig)


def output_hashes(out_dir: Path) -> dict[str, str]:
    return {p.name: sha256_file(p) for p in sorted(out_dir.iterdir()) if p.is_file() and p.name != "manifest.json"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    t0 = time.time()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    out_dir = ROOT / config["output_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["random_seed"]))

    source_config, pred, pairs, s02i_summary = load_inputs(config)
    reproduction = s02i.reproduce_counts(source_config)
    reproduction.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(reproduction["pass"].all()):
        raise RuntimeError("raw ROOT reproduction gate failed")

    pairs = add_support_features(pairs, config)
    joined = add_gates(join_predictions(pred, pairs, config), config)
    joined.to_csv(out_dir / "joined_support_predictions.csv.gz", index=False)

    summaries = pd.concat(
        [
            bootstrap_summary(joined, config, "absolute_abs5", rng),
            bootstrap_summary(joined, config, "fixed_eff_abs5_trainmatched", rng),
        ],
        ignore_index=True,
    )
    summaries.to_csv(out_dir / "support_summary.csv", index=False)
    per_run = pd.concat(
        [per_run_metrics(joined, "absolute_abs5"), per_run_metrics(joined, "fixed_eff_abs5_trainmatched")],
        ignore_index=True,
    )
    per_run.to_csv(out_dir / "per_run_support.csv", index=False)
    checks = leakage_checks(config, joined, reproduction)
    checks.to_csv(out_dir / "leakage_checks.csv", index=False)

    timing_lookup = s02i_summary.set_index("method")["mean_run_sigma68_ns"].to_dict()
    fixed = summaries[summaries["gate"] == "fixed_eff_abs5_trainmatched"].copy()
    fixed["s02i_mean_run_sigma68_ns"] = fixed["method"].map(timing_lookup)
    eligible = fixed[fixed["support_drift_max_ci_high"] <= float(config["support_drift_ci_high_gate"])]
    if len(eligible):
        winner_row = eligible.sort_values(["s02i_mean_run_sigma68_ns", "support_drift_max"]).iloc[0]
        decision = "support_safe_min_timing_sigma"
    else:
        winner_row = fixed.sort_values(["support_drift_max_ci_high", "s02i_mean_run_sigma68_ns"]).iloc[0]
        decision = "no_method_passed_support_gate_lowest_drift"
    winner = str(winner_row["method"])
    plot_outputs(out_dir, summaries, winner)

    input_hash_rows = [{"file": str(raw_file(config, run)), "sha256": sha256_file(raw_file(config, run))} for run in configured_runs(config)]
    result = {
        "study": config["study"],
        "ticket": config["ticket"],
        "title": config["title"],
        "worker": config["worker"],
        "date": "2026-07-09",
        "reproduced_raw_root_first": bool(reproduction["pass"].all()),
        "raw_reproduction": json_ready(json.loads(reproduction.to_json(orient="records"))),
        "split": "Sample-II leave-one-run-out by run; support CIs from run/event bootstrap",
        "required_methods": config["required_methods"],
        "primary_metric": "fixed-efficiency maximum support drift with bootstrap CI, constrained before timing winner selection",
        "winner": {
            "method": winner,
            "decision_rule": decision,
            "fixed_eff_support_drift_max": float(winner_row["support_drift_max"]),
            "fixed_eff_support_drift_ci_low": float(winner_row["support_drift_max_ci_low"]),
            "fixed_eff_support_drift_ci_high": float(winner_row["support_drift_max_ci_high"]),
            "s02i_mean_run_sigma68_ns": float(winner_row["s02i_mean_run_sigma68_ns"]),
        },
        "traditional_comparator": {
            "method": "traditional_atom_slope",
            "s02i_mean_run_sigma68_ns": float(timing_lookup["traditional_atom_slope"]),
        },
        "support_summary": json_ready(json.loads(summaries.to_json(orient="records"))),
        "leakage_checks_pass": bool(checks["pass"].astype(bool).all()),
        "failed_leakage_checks": json_ready(json.loads(checks[~checks["pass"].astype(bool)].to_json(orient="records"))),
        "next_tickets": [
            "Validate the support-preserving S02i correction against calibrated charge/PID observables in simulation and real-data sidebands before physics-production adoption."
        ],
        "git_commit": git_commit(),
        "runtime_seconds": float(time.time() - t0),
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    numbers = {
        "git_commit": result["git_commit"],
        "repro_rows": fmt_repro(reproduction),
        "n_pairs": int(joined[joined["method"] == "uncorrected_cfd20"].shape[0]),
        "n_events": int(joined[joined["method"] == "uncorrected_cfd20"]["event_id"].nunique()),
        "absolute_rows": fmt_support(summaries, "absolute_abs5"),
        "fixed_rows": fmt_support(summaries, "fixed_eff_abs5_trainmatched"),
        "timing_rows": fmt_timing(summaries),
        "per_run_rows": fmt_per_run(per_run, winner),
        "winner": winner,
        "decision_rule": decision,
        "winner_drift_ci_high": float(winner_row["support_drift_max_ci_high"]),
        "winner_s02i_sigma": float(winner_row["s02i_mean_run_sigma68_ns"]),
        "traditional_s02i_sigma": float(timing_lookup["traditional_atom_slope"]),
        "check_rows": fmt_checks(checks),
        "config_path": str(args.config),
    }
    write_report(out_dir, config, numbers)

    manifest = {
        "script": "scripts/s02j_1781099999_773_32991407_support_drift_audit.py",
        "config": str(args.config),
        "output_dir": str(out_dir.relative_to(ROOT)),
        "command": f"{sys.executable} scripts/s02j_1781099999_773_32991407_support_drift_audit.py --config {args.config}",
        "ticket": config["ticket"],
        "worker": config["worker"],
        "git_commit": result["git_commit"],
        "python": platform.python_version(),
        "libraries": {"numpy": np.__version__, "pandas": pd.__version__},
        "config_json": config,
        "input_sha256": input_hash_rows,
        "output_sha256": output_hashes(out_dir),
        "runtime_seconds": float(time.time() - t0),
    }
    (out_dir / "manifest.json").write_text(json.dumps(json_ready(manifest), indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"out_dir": str(out_dir.relative_to(ROOT)), "winner": winner, "runtime_seconds": result["runtime_seconds"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
