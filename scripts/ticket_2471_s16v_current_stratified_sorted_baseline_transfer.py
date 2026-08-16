#!/usr/bin/env python3
"""S16v current-stratified sorted-baseline timing-tail transfer.

This runner keeps the S16t raw ROOT waveform extraction and model benchmark,
then adds externally defined current-family strata and a standardized proxy
coefficient sign-transfer diagnostic for ticket #2471.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
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
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

CONFIG_DEFAULT = "configs/ticket_2471_s16v_current_stratified_sorted_baseline_transfer.json"
S16T_PATH = "scripts/s16t_2438_sorted_baseline_timing_tail_nuisance.py"


def load_module(name: str, path: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


S16T = load_module("s16t_helpers_for_2471", S16T_PATH)
S16M = S16T.S16M
S16L = S16T.S16L


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
    view = df.loc[:, list(columns)].copy()
    return view.to_markdown(index=False)


def configured_runs(config: dict) -> List[int]:
    out: List[int] = []
    for runs in config["run_groups"].values():
        out.extend(int(r) for r in runs)
    return sorted(set(out))


def raw_file(config: dict, run: int) -> Path:
    return Path(config["raw_root_dir"]) / ("hrdb_run_%04d.root" % int(run))


def sorted_file(config: dict, run: int) -> Path:
    return Path(config["sorted_root_dir"]) / ("hrdb_run_%04d-sorted.root" % int(run))


def input_hashes(config: dict) -> pd.DataFrame:
    rows = []
    for run in configured_runs(config):
        for role, path in [("raw", raw_file(config, run)), ("sorted", sorted_file(config, run))]:
            if path.exists():
                rows.append(
                    {
                        "run": int(run),
                        "role": role,
                        "path": str(path),
                        "sha256": sha256_file(path),
                        "bytes": int(path.stat().st_size),
                    }
                )
    return pd.DataFrame(rows)


def reproduce_counts(config: dict) -> pd.DataFrame:
    baseline_idx = [int(i) for i in config["baseline_samples"]]
    staves = {name: int(ch) for name, ch in config["staves"].items()}
    stave_names = list(staves.keys())
    channels = np.asarray([staves[name] for name in stave_names], dtype=int)
    nsamp = int(config["samples_per_channel"])
    cut = float(config["amplitude_cut_adc"])
    counts: Dict[str, Dict[str, int]] = {
        "sample_i_analysis": {"selected_pulses": 0, **{s: 0 for s in stave_names}},
        "sample_ii_analysis": {"selected_pulses": 0, **{s: 0 for s in stave_names}},
    }
    total = 0
    for run in configured_runs(config):
        tree = uproot.open(raw_file(config, run))["h101"]
        for batch in tree.iterate(["HRDv"], step_size=20000, library="np"):
            events = np.stack(batch["HRDv"]).astype(np.float64).reshape(-1, 8, nsamp)
            waves = events[:, channels, :]
            ped = np.median(waves[..., baseline_idx], axis=-1)
            amp = (waves - ped[..., None]).max(axis=-1)
            selected = amp > cut
            total += int(selected.sum())
            for group in ["sample_i_analysis", "sample_ii_analysis"]:
                if int(run) in set(int(r) for r in config["run_groups"][group]):
                    counts[group]["selected_pulses"] += int(selected.sum())
                    for i, stave in enumerate(stave_names):
                        counts[group][stave] += int(selected[:, i].sum())
    rows = [
        {
            "quantity": "total selected B-stave pulses",
            "report_value": int(config["expected_counts"]["total_selected_pulses"]),
            "reproduced": int(total),
            "tolerance": 0,
        }
    ]
    for group in ["sample_i_analysis", "sample_ii_analysis"]:
        for key, value in config["expected_counts"][group].items():
            rows.append({"quantity": f"{group} {key}", "report_value": int(value), "reproduced": int(counts[group][key]), "tolerance": 0})
    out = pd.DataFrame(rows)
    out["delta"] = out["reproduced"] - out["report_value"]
    out["pass"] = out["delta"].abs() <= out["tolerance"]
    return out[["quantity", "report_value", "reproduced", "delta", "tolerance", "pass"]]


def run_to_current(config: dict) -> Dict[int, str]:
    mapping: Dict[int, str] = {}
    for period, families in config["current_families"].items():
        for family, runs in families.items():
            for run in runs:
                mapping[int(run)] = family
    return mapping


def period_config(config: dict, period: str) -> dict:
    sub = json.loads(json.dumps(config))
    runs = [int(r) for r in config["analysis_periods"][period]]
    sub["analysis_runs"] = runs
    sub["heldout_runs"] = runs
    sub["models"]["random_seed"] = int(config["models"]["random_seed"]) + (0 if period == "sample_i" else 1000)
    return sub


def run_period(config: dict, period: str, out_dir: Path):
    sub = period_config(config, period)
    meta, waves = S16L.load_selected_pulses(sub)
    nuisance = S16T.sorted_recoverability_features(sub)
    if len(meta) != len(nuisance):
        raise RuntimeError(f"{period}: meta/nuisance length mismatch {len(meta)} != {len(nuisance)}")
    pairs = S16M.build_pairs(meta, nuisance, sub)
    scored = S16M.fit_fold_models(pairs, waves, sub)
    pairs["sample_period"] = period
    scored["sample_period"] = period
    current = run_to_current(config)
    pairs["current_family"] = pairs["run"].map(current).fillna("unmapped")
    scored["current_family"] = scored["run"].map(current).fillna("unmapped")
    pairs.to_csv(out_dir / f"{period}_pair_rows.csv.gz", index=False)
    scored.to_csv(out_dir / f"{period}_method_predictions.csv.gz", index=False)
    return pairs, scored


def add_run_bootstrap_cis(metrics: pd.DataFrame, scored: pd.DataFrame, reps: int, seed: int, group_cols: Sequence[str]) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    for keys, group in scored.groupby(list(group_cols) + ["method"]):
        if not isinstance(keys, tuple):
            keys = (keys,)
        base = dict(zip(list(group_cols) + ["method"], keys))
        runs = np.asarray(sorted(group["run"].unique()), dtype=int)
        by_run = {int(r): g["corrected_residual_ns"].to_numpy(dtype=float) for r, g in group.groupby("run")}
        vals = []
        for _ in range(reps):
            chosen = rng.choice(runs, size=len(runs), replace=True)
            vals.append(S16M.metric_dict(np.concatenate([by_run[int(r)] for r in chosen])))
        for metric in ["sigma68_ns", "tail_abs_gt_0p5_ns", "bias_ns"]:
            arr = np.asarray([v[metric] for v in vals], dtype=float)
            base[f"{metric}_ci_low"] = float(np.percentile(arr, 2.5))
            base[f"{metric}_ci_high"] = float(np.percentile(arr, 97.5))
        rows.append(base)
    ci = pd.DataFrame(rows)
    return metrics.merge(ci, on=list(group_cols) + ["method"], how="left")


def summarize(scored: pd.DataFrame, reps: int, seed: int):
    pooled = S16M.summarize_metrics(scored).sort_values("sigma68_ns").reset_index(drop=True)
    pooled = add_run_bootstrap_cis(pooled, scored, reps, seed, [])
    by_current = []
    for keys, group in scored.groupby(["sample_period", "current_family", "method"]):
        row = {"sample_period": keys[0], "current_family": keys[1], "method": keys[2]}
        row.update(S16M.metric_dict(group["corrected_residual_ns"].to_numpy(dtype=float)))
        by_current.append(row)
    by_current = pd.DataFrame(by_current).sort_values(["sample_period", "current_family", "sigma68_ns"]).reset_index(drop=True)
    by_current = add_run_bootstrap_cis(by_current, scored, reps, seed + 1, ["sample_period", "current_family"])
    per_run = S16M.per_run_metrics(scored).merge(
        scored[["sample_period", "current_family", "run", "method"]].drop_duplicates(),
        on=["run", "method"],
        how="left",
    )
    return pooled, by_current, per_run


def coefficient_sign_table(pairs: pd.DataFrame, config: dict) -> pd.DataFrame:
    rows = []
    control_cols = S16T.control_columns(pairs)
    proxy_col = "nuisance_signed_diff_adc"
    cols = [c for c in control_cols if c in pairs.columns] + [proxy_col]
    rng = np.random.default_rng(int(config["models"]["random_seed"]) + 3000)
    for (period, family), group in pairs.groupby(["sample_period", "current_family"]):
        if group["run"].nunique() < 2 or len(group) < 100:
            continue
        x = group[cols].replace([np.inf, -np.inf], np.nan).copy()
        x = x.fillna(x.median(axis=0).fillna(0.0))
        y = group["raw_residual_ns"].to_numpy(dtype=float)
        model = make_pipeline(StandardScaler(), Ridge(alpha=float(config["models"]["ridge_alpha"])))
        model.fit(x, y)
        coef = float(model.named_steps["ridge"].coef_[list(x.columns).index(proxy_col)])
        boot = []
        runs = np.asarray(sorted(group["run"].unique()), dtype=int)
        by_run = {int(r): g for r, g in group.groupby("run")}
        for _ in range(int(config["bootstrap_replicates"])):
            chosen = rng.choice(runs, size=len(runs), replace=True)
            b = pd.concat([by_run[int(r)] for r in chosen], ignore_index=True)
            bx = b[cols].replace([np.inf, -np.inf], np.nan).copy()
            bx = bx.fillna(bx.median(axis=0).fillna(0.0))
            by = b["raw_residual_ns"].to_numpy(dtype=float)
            bm = make_pipeline(StandardScaler(), Ridge(alpha=float(config["models"]["ridge_alpha"])))
            bm.fit(bx, by)
            boot.append(float(bm.named_steps["ridge"].coef_[list(bx.columns).index(proxy_col)]))
        arr = np.asarray(boot, dtype=float)
        rows.append(
            {
                "sample_period": period,
                "current_family": family,
                "n_pairs": int(len(group)),
                "n_runs": int(group["run"].nunique()),
                "standardized_proxy_coef_ns": coef,
                "coef_ci_low": float(np.percentile(arr, 2.5)),
                "coef_ci_high": float(np.percentile(arr, 97.5)),
                "sign": "positive" if coef > 0 else "negative" if coef < 0 else "zero",
                "positive_bootstrap_fraction": float(np.mean(arr > 0)),
            }
        )
    return pd.DataFrame(rows).sort_values(["sample_period", "current_family"]).reset_index(drop=True)


def transfer_verdict(coef: pd.DataFrame) -> str:
    def sign_for(period: str, family: str):
        row = coef[(coef["sample_period"] == period) & (coef["current_family"] == family)]
        if row.empty:
            return None
        lo = float(row.iloc[0]["coef_ci_low"])
        hi = float(row.iloc[0]["coef_ci_high"])
        point = float(row.iloc[0]["standardized_proxy_coef_ns"])
        if lo > 0:
            return "positive"
        if hi < 0:
            return "negative"
        return "ambiguous_positive" if point > 0 else "ambiguous_negative"

    s1 = sign_for("sample_i", "high_20nA")
    s2 = sign_for("sample_ii", "high_all_three_rate")
    if s1 is None or s2 is None:
        return "not_testable_missing_high_current_stratum"
    if s1 == s2 and not s1.startswith("ambiguous"):
        return "survives_within_current_matching"
    if s1.replace("ambiguous_", "") == s2.replace("ambiguous_", ""):
        return "same_point_sign_but_ci_ambiguous"
    return "does_not_survive_within_current_matching"


def make_plots(pooled: pd.DataFrame, by_current: pd.DataFrame, coef: pd.DataFrame, out_dir: Path):
    fig, ax = plt.subplots(figsize=(9.5, 5.3))
    order = pooled.sort_values("sigma68_ns")["method"].tolist()
    ax.barh(order, pooled.set_index("method").loc[order]["sigma68_ns"], color="#496f73")
    ax.set_xlabel("pooled held-out sigma68 (ns)")
    ax.set_title("S16v run-held-out method benchmark")
    fig.tight_layout()
    fig.savefig(out_dir / "pooled_method_benchmark.png", dpi=180)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(10.5, 5.6))
    winners = by_current[by_current["method"] != "uncorrected"].sort_values("sigma68_ns").groupby(["sample_period", "current_family"]).head(1)
    labels = winners["sample_period"] + "\n" + winners["current_family"] + "\n" + winners["method"]
    ax.bar(np.arange(len(winners)), winners["sigma68_ns"], color="#7f624f")
    ax.set_xticks(np.arange(len(winners)))
    ax.set_xticklabels(labels, rotation=30, ha="right", fontsize=8)
    ax.set_ylabel("winner sigma68 (ns)")
    ax.set_title("Best method inside each current family")
    fig.tight_layout()
    fig.savefig(out_dir / "current_family_winners.png", dpi=180)
    plt.close(fig)

    if not coef.empty:
        fig, ax = plt.subplots(figsize=(8.5, 4.8))
        labels = coef["sample_period"] + "\n" + coef["current_family"]
        x = np.arange(len(coef))
        y = coef["standardized_proxy_coef_ns"].to_numpy(dtype=float)
        yerr = np.vstack([y - coef["coef_ci_low"].to_numpy(dtype=float), coef["coef_ci_high"].to_numpy(dtype=float) - y])
        ax.errorbar(x, y, yerr=yerr, fmt="o", color="#3f617d", capsize=3)
        ax.axhline(0.0, color="black", lw=1)
        ax.set_xticks(x)
        ax.set_xticklabels(labels, rotation=30, ha="right", fontsize=8)
        ax.set_ylabel("standardized ridge coefficient (ns)")
        ax.set_title("Sorted-baseline signed-difference coefficient by current state")
        fig.tight_layout()
        fig.savefig(out_dir / "proxy_coefficient_sign_transfer.png", dpi=180)
        plt.close(fig)


def write_report(config: dict, result: dict, reproduction: pd.DataFrame, pooled: pd.DataFrame, by_current: pd.DataFrame, coef: pd.DataFrame, per_run: pd.DataFrame, out_dir: Path):
    winner = result["winner"]
    report = f"""# S16v: Current-Stratified Sorted-Baseline Timing-Tail Transfer

## Abstract

Ticket `#2471` asks whether the sorted-baseline timing-tail proxy from S16u/S16t keeps the same sign after stratifying by an external electronics-current ledger. I claimed the ticket for `testbeam-laptop-3` after the `tn-ticket claim` helper returned the known `null|null|null` edge-case response, then performed a fresh raw ROOT reproduction gate and a run-held-out benchmark across Sample-I and Sample-II analysis runs. The named winner in `result.json` is **{winner}** on pooled held-out `sigma68_ns`. The sign-transfer verdict is **{result["sign_transfer_verdict"]}**.

## Raw ROOT Reproduction

Raw B-stack ROOT files under `{config["raw_root_dir"]}` were scanned directly from `h101/HRDv`. For event `i`, stave `s`, and sample `t`, the reproduced selection is

`A_is = max_t(x_ist - median(x_is0,x_is1,x_is2,x_is3)) > {config["amplitude_cut_adc"]:.0f} ADC`.

{md_table(reproduction, ["quantity", "report_value", "reproduced", "delta", "tolerance", "pass"])}

This exactly reproduces the 640,737 selected B-stave pulses and the Sample-I/Sample-II analysis-period counts used by the downstream timing-tail benchmark.

## Estimand

For a downstream pair `(a,b)` in event `i`, the raw timing residual is

`r_iab = (t_ia^CFD20 - t_ib^CFD20) - (x_a - x_b) * tau`,

where `tau = {config["tof_per_cm_ns"]}` ns/cm and CFD20 uses the raw four-sample median pedestal. A model estimates a correction `c_iab = f(z_iab)` from run-held-out training data and is scored on `r_iab - c_iab`. The primary width is

`sigma68(r) = (Q84(r) - Q16(r)) / 2`.

The sorted-baseline signed proxy is `u_iab = u_ia - u_ib`, where `u_ip = b_ip^sorted - median(raw pretrigger)`. The sign-transfer diagnostic fits a standardized ridge model inside each current family and reports the coefficient of `u_iab`; bootstrap CIs resample source runs.

## External Current Ledger

Sample roles and raw-product identity are taken from `configs/daq/run_ledger.yaml`. Current-family labels follow the repository's electronics-current convention used by prior current studies: Sample-I runs 46-47 are `low_2nA`, while runs 44,45,48-57 are `high_20nA`. Sample-II lacks literal 2 nA/20 nA labels in the ledger, so the externally audited all-three-rate families are used: runs 58 and 65 are low-edge, 59 and 63 mid-rate, and 60-62 high-rate.

## Methods

The traditional method is the S16t hierarchical binned median correction over pair identity, amplitude-ratio bin, raw pretrigger-dispersion bin, and sorted-proxy magnitude bin, with coarser fallbacks. The ML/NN panel is ridge regression, histogram gradient-boosted trees, MLP, a 1D-CNN over raw paired waveforms, and the new nuisance-gated pair CNN. All methods are trained in leave-one-run-out folds separately inside Sample-I and Sample-II, then evaluated on held-out runs. Bootstrap intervals resample held-out source runs and preserve all paired predictions within a sampled run.

## Pooled Method Benchmark

{md_table(pooled, ["method", "n_pairs", "sigma68_ns", "sigma68_ns_ci_low", "sigma68_ns_ci_high", "tail_abs_gt_0p5_ns", "tail_abs_gt_0p5_ns_ci_low", "tail_abs_gt_0p5_ns_ci_high", "bias_ns", "bias_ns_ci_low", "bias_ns_ci_high"])}

## Current-Stratified Results

{md_table(by_current, ["sample_period", "current_family", "method", "n_pairs", "sigma68_ns", "sigma68_ns_ci_low", "sigma68_ns_ci_high", "tail_abs_gt_0p5_ns", "bias_ns"])}

## Proxy Coefficient Sign Transfer

{md_table(coef, ["sample_period", "current_family", "n_runs", "n_pairs", "standardized_proxy_coef_ns", "coef_ci_low", "coef_ci_high", "sign", "positive_bootstrap_fraction"])}

The decision rule is conservative: sign transfer is accepted only when Sample-I high-current and Sample-II high-rate coefficients share the same CI-excluding sign. Ambiguous intervals are reported as non-adoptable even when point estimates agree.

## Run-Held-Out Stability

{md_table(per_run, ["method", "run", "sample_period", "current_family", "n_pairs", "sigma68_ns", "tail_abs_gt_0p5_ns", "bias_ns"])}

## Systematics and Caveats

The response is a pair-residual timing-tail proxy, not an external clock truth. Sample-II current families are rate-derived external strata rather than literal electronics-current set points, so the Sample-I/Sample-II comparison tests sign portability across matched current-like operating states rather than a calibrated current scale. The sorted ROOT branches are reconstruction products; they are used here as diagnostic covariates and not as permission to alter the raw CFD20 pedestal definition. Low-current support is sparse, with only two Sample-I low-current and two Sample-II low-edge runs, so bootstrap CIs are conditional and should not be read as population intervals. Neural models are compact CPU-reproducible benchmarks, not exhaustive architecture searches.

## Conclusion

The best pooled held-out method is **{winner}**. The current-stratified coefficient table is the ticket's decisive systematic: the sorted-baseline signed-difference coefficient is only transferable if the high-current Sample-I and high-rate Sample-II signs agree with run-bootstrap support. The reported verdict is **{result["sign_transfer_verdict"]}**, so downstream adoption should follow that verdict rather than the pooled method winner alone.
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

    reproduction = reproduce_counts(config)
    reproduction.to_csv(out_dir / "reproduction_counts.csv", index=False)
    if not bool(reproduction["pass"].all()):
        raise RuntimeError("raw ROOT reproduction gate failed")

    hashes = input_hashes(config)
    hashes.to_csv(out_dir / "input_sha256.csv", index=False)

    all_pairs = []
    all_scored = []
    for period in ["sample_i", "sample_ii"]:
        pairs, scored = run_period(config, period, out_dir)
        all_pairs.append(pairs)
        all_scored.append(scored)
    pairs = pd.concat(all_pairs, ignore_index=True)
    scored = pd.concat(all_scored, ignore_index=True)
    pairs.to_csv(out_dir / "pair_rows.csv.gz", index=False)
    scored.to_csv(out_dir / "method_predictions.csv.gz", index=False)

    pooled, by_current, per_run = summarize(scored, int(config["bootstrap_replicates"]), int(config["models"]["random_seed"]))
    coef = coefficient_sign_table(pairs, config)
    verdict = transfer_verdict(coef)
    pooled.to_csv(out_dir / "method_metrics.csv", index=False)
    by_current.to_csv(out_dir / "current_stratified_method_metrics.csv", index=False)
    per_run.to_csv(out_dir / "per_run_metrics.csv", index=False)
    coef.to_csv(out_dir / "proxy_coefficient_sign_transfer.csv", index=False)
    make_plots(pooled, by_current, coef, out_dir)

    winner = str(pooled[pooled["method"] != "uncorrected"].iloc[0]["method"])
    result = {
        "study": config["study"],
        "ticket": config["ticket"],
        "worker": config["worker"],
        "title": config["title"],
        "status": "complete",
        "winner": winner,
        "winner_metrics": pooled[pooled["method"] == winner].iloc[0].to_dict(),
        "primary_metric": config["primary_metric"],
        "raw_reproduction": {"all_pass": bool(reproduction["pass"].all()), "rows": reproduction.to_dict(orient="records")},
        "methods": sorted(scored["method"].unique().tolist()),
        "split": "leave-one-run-out within Sample-I and Sample-II analysis periods",
        "bootstrap": {"unit": "held-out source run", "replicates": int(config["bootstrap_replicates"]), "paired": True},
        "current_families": config["current_families"],
        "sign_transfer_verdict": verdict,
        "proxy_coefficient_sign_transfer": coef.to_dict(orient="records"),
        "n_pairs": int(len(pairs)),
        "input_root_files": int(len(hashes)),
        "git_commit": git_commit(),
        "runtime_seconds": round(time.time() - start, 3),
        "outputs": [
            "REPORT.md",
            "result.json",
            "reproduction_counts.csv",
            "input_sha256.csv",
            "pair_rows.csv.gz",
            "method_predictions.csv.gz",
            "method_metrics.csv",
            "current_stratified_method_metrics.csv",
            "per_run_metrics.csv",
            "proxy_coefficient_sign_transfer.csv",
            "pooled_method_benchmark.png",
            "current_family_winners.png",
            "proxy_coefficient_sign_transfer.png",
        ],
        "next_tickets": [],
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    shutil.copy2(config_path, out_dir / "config.json")
    write_report(config, result, reproduction, pooled, by_current, coef, per_run, out_dir)
    manifest = {
        "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "git_commit": git_commit(),
        "command": "python3 scripts/ticket_2471_s16v_current_stratified_sorted_baseline_transfer.py --config " + str(config_path),
        "files": {p.name: sha256_file(p) for p in out_dir.iterdir() if p.is_file()},
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({"out_dir": str(out_dir), "winner": winner, "sign_transfer_verdict": verdict, "n_pairs": int(len(pairs))}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
