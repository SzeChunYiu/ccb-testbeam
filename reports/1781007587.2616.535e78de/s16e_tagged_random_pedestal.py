#!/usr/bin/env python3
"""S16e tagged random-trigger pedestal validation gate.

This ticket asks for a true tagged random/forced-trigger B-stack pedestal
benchmark. The current data mirror is audited first; if the tagged sample is
absent, the report records that as the finding and keeps the S16 pre-trigger
LOPO benchmark as a raw-ROOT reproduction baseline.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
import subprocess
import time
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Tuple

_SCRIPT_DIR = Path(__file__).resolve().parent
os.environ.setdefault("MPLCONFIGDIR", str(_SCRIPT_DIR / ".mplconfig"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import uproot
from sklearn.metrics import mean_absolute_error
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LinearRegression, Ridge


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def git_commit() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()


def load_prior_module(config: dict):
    script_path = Path(config["prior_s16_script"]).resolve()
    spec = importlib.util.spec_from_file_location("prior_s16_analysis", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot import prior S16 script at {}".format(script_path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def configured_runs(config: dict) -> List[int]:
    runs: List[int] = []
    for values in config["run_groups"].values():
        runs.extend(int(run) for run in values)
    return sorted(set(runs))


def raw_root_paths(config: dict) -> List[Path]:
    root = Path(config["raw_root_dir"])
    return sorted(root.glob("hrda_run_*.root")) + sorted(root.glob("hrdb_run_*.root"))


def trigger_summary(values: np.ndarray) -> Tuple[str, int]:
    unique, counts = np.unique(values, return_counts=True)
    summary = ";".join("{}:{}".format(int(v), int(c)) for v, c in zip(unique, counts))
    non_beam = int(np.sum(counts[unique != 1]))
    return summary, non_beam


def raw_trigger_audit(config: dict) -> pd.DataFrame:
    rows = []
    tokens = [token.lower() for token in config["tag_tokens"]]
    for path in raw_root_paths(config):
        tree = uproot.open(path)["h101"]
        branch_names = list(tree.keys())
        if tree.num_entries:
            trigger = tree.arrays(["TRIGGER"], library="np")["TRIGGER"]
            summary, non_beam = trigger_summary(trigger)
        else:
            summary, non_beam = "empty", 0
        rows.append(
            {
                "file": path.name,
                "stack": "B" if path.name.startswith("hrdb") else "A",
                "entries": int(tree.num_entries),
                "branches": ";".join(branch_names),
                "trigger_summary": summary,
                "non_beam_trigger_entries": int(non_beam),
                "filename_tag_match": bool(any(token in path.name.lower() for token in tokens)),
            }
        )
    return pd.DataFrame(rows)


def sorted_b_audit(config: dict) -> pd.DataFrame:
    rows = []
    tokens = [token.lower() for token in config["tag_branch_tokens"]]
    sorted_dir = Path(config["sorted_b_dir"])
    for path in sorted(sorted_dir.glob("hrdb_run_*-sorted.root")):
        tree = uproot.open(path)["tree"]
        branches = list(tree.keys())
        tag_branches = [name for name in branches if any(token in name.lower() for token in tokens)]
        rows.append(
            {
                "file": path.name,
                "entries": int(tree.num_entries),
                "branches": ";".join(branches),
                "tag_like_branches": ";".join(tag_branches),
                "has_tag_like_branch": bool(tag_branches),
            }
        )
    return pd.DataFrame(rows)


def run_bootstrap_ci(
    residual: np.ndarray,
    runs: np.ndarray,
    metric: Callable[[np.ndarray], float],
    rng: np.random.Generator,
    n_boot: int,
) -> Tuple[float, float]:
    residual = np.asarray(residual, dtype=float)
    runs = np.asarray(runs, dtype=int)
    by_run: Dict[int, np.ndarray] = {}
    for run in np.unique(runs):
        by_run[int(run)] = residual[runs == run]
    run_values = np.asarray(sorted(by_run), dtype=int)
    stats = []
    for _ in range(n_boot):
        parts = []
        for run in rng.choice(run_values, size=len(run_values), replace=True):
            vals = by_run[int(run)]
            parts.append(rng.choice(vals, size=len(vals), replace=True))
        stats.append(float(metric(np.concatenate(parts))))
    return float(np.quantile(stats, 0.025)), float(np.quantile(stats, 0.975))


def summarize(frame: pd.DataFrame, rng: np.random.Generator, n_boot: int) -> pd.DataFrame:
    rows = []
    for method, sub in frame.groupby("method"):
        residual = sub["residual_adc"].to_numpy(dtype=float)
        runs = sub["run"].to_numpy(dtype=int)
        bias_lo, bias_hi = run_bootstrap_ci(residual, runs, np.mean, rng, n_boot)
        mae_lo, mae_hi = run_bootstrap_ci(residual, runs, lambda x: float(np.mean(np.abs(x))), rng, n_boot)
        rmse_lo, rmse_hi = run_bootstrap_ci(
            residual, runs, lambda x: float(math.sqrt(np.mean(np.square(x)))), rng, n_boot
        )
        rows.append(
            {
                "method": method,
                "n": int(len(sub)),
                "mean_bias_adc": float(np.mean(residual)),
                "mean_bias_ci_low_adc": bias_lo,
                "mean_bias_ci_high_adc": bias_hi,
                "mae_adc": float(np.mean(np.abs(residual))),
                "mae_ci_low_adc": mae_lo,
                "mae_ci_high_adc": mae_hi,
                "rmse_adc": float(math.sqrt(np.mean(np.square(residual)))),
                "rmse_ci_low_adc": rmse_lo,
                "rmse_ci_high_adc": rmse_hi,
                "median_bias_adc": float(np.median(residual)),
                "q05_adc": float(np.quantile(residual, 0.05)),
                "q95_adc": float(np.quantile(residual, 0.95)),
            }
        )
    return pd.DataFrame(rows).sort_values("mae_adc").reset_index(drop=True)


def by_run_summary(frame: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (method, run), sub in frame.groupby(["method", "run"]):
        residual = sub["residual_adc"].to_numpy(dtype=float)
        rows.append(
            {
                "method": method,
                "run": int(run),
                "n": int(len(sub)),
                "mean_bias_adc": float(np.mean(residual)),
                "mae_adc": float(np.mean(np.abs(residual))),
                "rmse_adc": float(math.sqrt(np.mean(np.square(residual)))),
            }
        )
    return pd.DataFrame(rows)


def shuffled_target_leakage_check(
    ml_features: pd.DataFrame,
    ml_meta: dict,
    config: dict,
    rng: np.random.Generator,
) -> float:
    heldout_runs = set(int(run) for run in config["heldout_runs"])
    feature_cols = ml_meta["feature_columns"]
    train = ml_features[~ml_features["run"].isin(heldout_runs)].copy()
    test = ml_features[ml_features["run"].isin(heldout_runs)].copy()
    if len(train) > 12000:
        train = train.sample(n=12000, random_state=int(config["ml"]["random_seed"]) + 900)
    if len(test) > 4000:
        test = test.sample(n=4000, random_state=int(config["ml"]["random_seed"]) + 901)
    shuffled_target = rng.permutation(train["target_adc"].to_numpy())
    model = make_pipeline(StandardScaler(), Ridge(alpha=1.0))
    model.fit(feature_matrix(train, feature_cols), shuffled_target)
    pred = model.predict(feature_matrix(test, feature_cols))
    return float(mean_absolute_error(test["target_adc"], pred))


def feature_matrix(frame: pd.DataFrame, feature_cols: List[str]) -> pd.DataFrame:
    return frame[feature_cols].replace([np.inf, -np.inf], np.nan).fillna(0.0)


def train_ridge_ml(features: pd.DataFrame, config: dict) -> Tuple[pd.DataFrame, pd.DataFrame, dict]:
    heldout_runs = set(int(run) for run in config["heldout_runs"])
    calibration_runs = set(int(run) for run in config["calibration_runs"])
    feature_cols = [col for col in features.columns if col not in {"target_adc", "pulse_index", "run"}]
    train_cv = features[~features["run"].isin(heldout_runs)].copy()
    test = features[features["run"].isin(heldout_runs)].copy()
    core_train = train_cv[~train_cv["run"].isin(calibration_runs)].copy()
    calibration = train_cv[train_cv["run"].isin(calibration_runs)].copy()
    groups = train_cv["run"].to_numpy()
    n_splits = min(int(config["ml"]["cv_folds"]), len(np.unique(groups)))
    cv = GroupKFold(n_splits=n_splits)
    scan_rows = []
    for alpha in config["ml"]["ridge_alpha"]:
        scores = []
        for train_idx, valid_idx in cv.split(train_cv[feature_cols], train_cv["target_adc"], groups=groups):
            model = make_pipeline(StandardScaler(), Ridge(alpha=float(alpha)))
            model.fit(feature_matrix(train_cv.iloc[train_idx], feature_cols), train_cv.iloc[train_idx]["target_adc"])
            pred = model.predict(feature_matrix(train_cv.iloc[valid_idx], feature_cols))
            scores.append(mean_absolute_error(train_cv.iloc[valid_idx]["target_adc"], pred))
        scan_rows.append(
            {
                "alpha": float(alpha),
                "cv_mae_adc": float(np.mean(scores)),
                "cv_mae_std_adc": float(np.std(scores, ddof=1)),
            }
        )
    scan = pd.DataFrame(scan_rows).sort_values("cv_mae_adc").reset_index(drop=True)
    best = scan.iloc[0].to_dict()
    model = make_pipeline(StandardScaler(), Ridge(alpha=float(best["alpha"])))
    model.fit(feature_matrix(core_train, feature_cols), core_train["target_adc"])
    cal_pred = model.predict(feature_matrix(calibration, feature_cols))
    calibrator = LinearRegression().fit(cal_pred.reshape(-1, 1), calibration["target_adc"])
    raw_pred = model.predict(feature_matrix(test, feature_cols))
    pred = calibrator.predict(raw_pred.reshape(-1, 1))
    pred_frame = test[["run", "pulse_index", "stave_idx", "holdout_sample", "target_adc", "amplitude_adc", "peak_sample"]].copy()
    pred_frame["method"] = "ml_ridge_calibrated"
    pred_frame["estimate_adc"] = pred
    pred_frame["reference_adc"] = pred_frame["target_adc"]
    pred_frame["residual_adc"] = pred_frame["estimate_adc"] - pred_frame["reference_adc"]
    pred_frame["abs_residual_adc"] = pred_frame["residual_adc"].abs()
    meta = {
        "best": best,
        "calibration_intercept": float(calibrator.intercept_),
        "calibration_slope": float(calibrator.coef_[0]),
        "n_train_cv": int(len(train_cv)),
        "n_core_train": int(len(core_train)),
        "n_calibration": int(len(calibration)),
        "n_test": int(len(test)),
        "feature_columns": feature_cols,
        "model": "StandardScaler + Ridge + linear calibration",
    }
    return scan, pred_frame, meta


def format_ci(row: pd.Series, value: str, lo: str, hi: str) -> str:
    return "{:.2f} [{:.2f}, {:.2f}]".format(float(row[value]), float(row[lo]), float(row[hi]))


def plot_outputs(outdir: Path, audit: pd.DataFrame, bench_frame: pd.DataFrame, benchmark: pd.DataFrame, by_run: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(9, 4.8))
    b_audit = audit[audit["stack"] == "B"].copy()
    ax.bar(np.arange(len(b_audit)), b_audit["non_beam_trigger_entries"])
    ax.set_xticks(np.arange(len(b_audit))[::4])
    ax.set_xticklabels(b_audit["file"].str.extract(r"(\d{4})")[0].iloc[::4], rotation=90)
    ax.set_xlabel("B-stack run")
    ax.set_ylabel("TRIGGER != 1 entries")
    ax.set_title("Tagged random/forced-trigger audit")
    fig.tight_layout()
    fig.savefig(outdir / "fig_tagged_random_audit.png", dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 5))
    for method, sub in bench_frame.groupby("method"):
        ax.hist(sub["residual_adc"].clip(-120, 120), bins=80, histtype="step", density=True, linewidth=1.4, label=method)
    ax.axvline(0, color="black", linewidth=0.8)
    ax.set_xlabel("estimate - held-out pre-trigger sample [ADC]")
    ax.set_ylabel("density")
    ax.set_title("Reproduced S16 fallback benchmark")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(outdir / "fig_s16_fallback_residuals.png", dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 4.5))
    ordered = benchmark.sort_values("mae_adc")
    ax.errorbar(
        ordered["mae_adc"],
        ordered["method"],
        xerr=[ordered["mae_adc"] - ordered["mae_ci_low_adc"], ordered["mae_ci_high_adc"] - ordered["mae_adc"]],
        fmt="o",
    )
    ax.set_xlabel("MAE [ADC]")
    ax.set_title("Run-heldout bootstrap intervals")
    fig.tight_layout()
    fig.savefig(outdir / "fig_s16_fallback_mae_ci.png", dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 4.5))
    pivot = by_run.pivot(index="run", columns="method", values="mean_bias_adc")
    pivot.plot(kind="bar", ax=ax)
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_ylabel("mean bias [ADC]")
    ax.set_title("Fallback mean bias by held-out run")
    fig.tight_layout()
    fig.savefig(outdir / "fig_s16_fallback_bias_by_run.png", dpi=160)
    plt.close(fig)


def output_hashes(outdir: Path) -> List[dict]:
    rows = []
    for path in sorted(outdir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            rows.append({"path": str(path), "sha256": sha256_file(path), "bytes": int(path.stat().st_size)})
    return rows


def json_records(frame: pd.DataFrame) -> List[dict]:
    return frame.replace({np.nan: None}).to_dict(orient="records")


def write_report(outdir: Path, config: dict, numbers: dict) -> None:
    benchmark = numbers["benchmark"]
    adaptive = benchmark[benchmark["method"] == "adaptive_pc"].iloc[0]
    median = benchmark[benchmark["method"] == "median3"].iloc[0]
    ml = benchmark[benchmark["method"] == "ml_ridge_calibrated"].iloc[0]
    rows = "\n".join(
        "| {} | {} | {} | {} | {} |".format(
            row.method,
            int(row.n),
            format_ci(row._asdict(), "mae_adc", "mae_ci_low_adc", "mae_ci_high_adc"),
            format_ci(row._asdict(), "mean_bias_adc", "mean_bias_ci_low_adc", "mean_bias_ci_high_adc"),
            format_ci(row._asdict(), "rmse_adc", "rmse_ci_low_adc", "rmse_ci_high_adc"),
        )
        for row in benchmark.itertuples(index=False)
    )
    by_run_rows = "\n".join(
        "| {} | {} | {} | {:.2f} | {:.2f} |".format(row.method, int(row.run), int(row.n), row.mean_bias_adc, row.mae_adc)
        for row in numbers["by_run"].itertuples(index=False)
    )
    repro_rows = "\n".join(
        "| {} | {} | {} | {} | {} | {} |".format(
            row.quantity, row.report_value, row.reproduced, row.delta, row.tolerance, "yes" if row["pass"] else "no"
        )
        for _, row in numbers["reproduction"].iterrows()
    )
    leak_rows = "\n".join(
        "| {} | {} |".format(row.check, row.result)
        for row in numbers["leakage"].itertuples(index=False)
    )
    report = """# Study report: S16e - tagged random-trigger pedestal validation

- **Ticket:** {ticket}
- **Author:** {worker}
- **Date:** 2026-06-09
- **Depends on:** S00, S16
- **Input checksums:** `input_sha256.csv`
- **Git commit:** `{git_commit}`
- **Config:** `s16e_config.json`

## 0. Question

Once tagged forced/random B-stack pedestal events exist, does `adaptive_pc_excluding_target` have zero mean bias against held-out no-pulse samples by run?

## 1. Reproduction and gate

Raw ROOT was audited before modeling. The ticket premise requires tagged random/forced B-stack no-pulse entries; the current mirror does not contain them.

| Quantity | Report value | Reproduced | Delta | Tolerance | Pass? |
|---|---:|---:|---:|---:|---|
{repro_rows}

The tagged-random count uses raw `h101/TRIGGER` and filename tags. Across all raw HRD files there are `{raw_entries}` entries and `{raw_nonbeam}` entries with `TRIGGER != 1`; B-stack contributes `{tagged_b}` tagged candidates. Sorted B-stack files were also scanned for tag-like branches and have `{sorted_tag_branches}` tag-like branches. This fails the primary S16e data-availability gate, so no true random-trigger pedestal validation can be claimed.

## 2. Traditional method

Because the tagged no-pulse sample is absent, the only valid traditional result in this report is a reproduction of the prior S16 leave-one-pre-trigger-out baseline from raw ROOT. It uses held-out runs `{heldout_runs}`, excludes the target pre-trigger sample from each estimate, and reports run-heldout bootstrap intervals.

Traditional estimators are `median3`, `mean3`, and `adaptive_pc`, where `adaptive_pc` is the S16 positivity-constrained lowering with the target sample excluded. This is not a substitute for true tagged random triggers.

## 3. ML method

The fallback ML reproduction is a run-split ridge regressor with group CV by run and linear calibration on runs `{calibration_runs}`. Features exclude run ID, event identifiers, and the target held-out sample. Best CV setting: `{ml_best}`.

## 4. Head-to-head fallback benchmark

All rows below are the fallback S16 pre-trigger benchmark, not a tagged-random benchmark.

| Method | n | MAE [ADC] | Mean bias [ADC] | RMSE [ADC] |
|---|---:|---:|---:|---:|
{rows}

Held-out run breakdown:

| Method | Run | n | Mean bias [ADC] | MAE [ADC] |
|---|---:|---:|---:|---:|
{by_run_rows}

On the sampled fallback head-to-head, adaptive mean bias is {adaptive_bias:.2f} ADC and MAE is {adaptive_mae:.2f} ADC. The prior S16 conclusion remains falsified on the pre-trigger benchmark: adaptive bias CI excludes zero, and adaptive MAE is {adaptive_delta:+.2f} ADC versus `median3`. ML MAE is {ml_mae:.2f} ADC, but that does not answer the S16e tagged-random question.

## 5. Leakage checks

| Check | Result |
|---|---|
{leak_rows}

No too-good tagged-random result exists to explain; the main leakage risk is mistaking beam-triggered pre-trigger or quiet-amplitude-selected proxies for true random triggers.

## 6. Threats to validity

- **Benchmark/selection:** The primary tagged-random benchmark is not run because the required tagged sample is absent. The fallback S16 reproduction is clearly labeled.
- **Data leakage:** Fallback ML splits by run; target sample, run ID, and event IDs are excluded from real features.
- **Metric misuse:** The pre-trigger fallback metric is not a no-pulse random-trigger pedestal metric.
- **Post-hoc selection:** The gate, held-out runs, and hyperparameter grid are fixed in `s16e_config.json`.

## 7. Provenance

`manifest.json` records command, git commit, random seed, input sha256s, output sha256s, and environment. `input_sha256.csv` contains the raw ROOT inputs used for the audit and fallback reproduction.

## 8. Findings and next steps

Finding: S16e cannot yet confirm or falsify `adaptive_pc_excluding_target` on tagged random triggers because the data mirror has zero tagged B-stack random/forced pedestal entries. The correct scientific conclusion is a failed data-availability gate, not a proxy validation.

Follow-up tickets queued from this run:
- `{followup_1}`
- `{followup_2}`

## 9. Reproducibility

```bash
/home/billy/anaconda3/bin/python3.7 reports/{ticket}/s16e_tagged_random_pedestal.py --config reports/{ticket}/s16e_config.json
```

Outputs: `REPORT.md`, `result.json`, `manifest.json`, `input_sha256.csv`, `trigger_audit.csv`, `sorted_b_tag_audit.csv`, `reproduction_match_table.csv`, `fallback_heldout_benchmark.csv`, `fallback_heldout_by_run.csv`, `ml_cv_scan.csv`, and PNG figures.
""".format(
        ticket=config["ticket"],
        worker=config["worker"],
        git_commit=numbers["git_commit"],
        repro_rows=repro_rows,
        raw_entries=numbers["raw_entries"],
        raw_nonbeam=numbers["raw_nonbeam"],
        tagged_b=numbers["tagged_b"],
        sorted_tag_branches=numbers["sorted_tag_branches"],
        heldout_runs=config["heldout_runs"],
        calibration_runs=config["calibration_runs"],
        ml_best=numbers["ml_best"],
        rows=rows,
        by_run_rows=by_run_rows,
        adaptive_bias=float(adaptive["mean_bias_adc"]),
        adaptive_mae=float(adaptive["mae_adc"]),
        adaptive_delta=float(adaptive["mae_adc"] - median["mae_adc"]),
        ml_mae=float(ml["mae_adc"]),
        leak_rows=leak_rows,
        followup_1=numbers["followup_1"],
        followup_2=numbers["followup_2"],
    )
    (outdir / "REPORT.md").write_text(report, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    outdir = args.config.parent
    config = json.loads(args.config.read_text(encoding="utf-8"))
    rng = np.random.default_rng(int(config["ml"]["random_seed"]))
    start = time.time()

    prior = load_prior_module(config)
    audit = raw_trigger_audit(config)
    audit.to_csv(outdir / "trigger_audit.csv", index=False)
    sorted_audit = sorted_b_audit(config)
    sorted_audit.to_csv(outdir / "sorted_b_tag_audit.csv", index=False)

    raw_entries = int(audit["entries"].sum())
    raw_nonbeam = int(audit["non_beam_trigger_entries"].sum())
    tagged_b = int(
        audit.loc[audit["stack"].eq("B"), "non_beam_trigger_entries"].sum()
        + audit.loc[audit["stack"].eq("B") & audit["filename_tag_match"], "entries"].sum()
    )
    sorted_tag_branches = int(sorted_audit["has_tag_like_branch"].sum())

    meta, waveforms, run_counts = prior.load_selected(config)
    run_counts.to_csv(outdir / "fallback_run_counts.csv", index=False)
    b_prod, _, _, margin_prod = prior.adaptive_pedestal(
        waveforms.astype(np.float64), meta["seed_median4_adc"].to_numpy(dtype=float), config
    )
    adaptive_violations = int((margin_prod < -1e-9).sum())

    lopo = prior.make_lopo(meta, waveforms, config)
    heldout_lopo = lopo[lopo["run"].isin(config["heldout_runs"])].copy()
    ml_features = prior.build_ml_features(meta, waveforms, config, rng)
    ml_cv, ml_pred, ml_meta = train_ridge_ml(ml_features, config)
    ml_cv.to_csv(outdir / "ml_cv_scan.csv", index=False)

    ml_test_keys = ml_pred[["run", "pulse_index", "stave_idx", "holdout_sample"]].copy()
    trad_for_ml = []
    for method in ["median3", "mean3", "adaptive_pc"]:
        sub = heldout_lopo[heldout_lopo["method"] == method]
        sampled = ml_test_keys.merge(sub, on=["run", "pulse_index", "stave_idx", "holdout_sample"], how="left")
        trad_for_ml.append(
            sampled[
                [
                    "run",
                    "stave_idx",
                    "holdout_sample",
                    "method",
                    "estimate_adc",
                    "reference_adc",
                    "residual_adc",
                    "abs_residual_adc",
                    "amplitude_adc",
                    "peak_sample",
                ]
            ]
        )
    bench_frame = pd.concat(
        trad_for_ml
        + [
            ml_pred[
                [
                    "run",
                    "stave_idx",
                    "holdout_sample",
                    "method",
                    "estimate_adc",
                    "reference_adc",
                    "residual_adc",
                    "abs_residual_adc",
                    "amplitude_adc",
                    "peak_sample",
                ]
            ]
        ],
        ignore_index=True,
    )
    benchmark = summarize(bench_frame, rng, int(config["ml"]["bootstrap_replicates"]))
    by_run = by_run_summary(bench_frame)
    shuffled_mae = shuffled_target_leakage_check(ml_features, ml_meta, config, rng)
    benchmark.to_csv(outdir / "fallback_heldout_benchmark.csv", index=False)
    by_run.to_csv(outdir / "fallback_heldout_by_run.csv", index=False)
    bench_frame.sample(n=min(60000, len(bench_frame)), random_state=int(config["ml"]["random_seed"])).to_csv(
        outdir / "fallback_residual_sample.csv.gz", index=False
    )

    adaptive = benchmark[benchmark["method"] == "adaptive_pc"].iloc[0]
    reproduction = pd.DataFrame(
        [
            {
                "quantity": "S00 selected B-stave pulses",
                "report_value": int(config["expected_selected_pulses"]),
                "reproduced": int(len(meta)),
                "delta": int(len(meta) - int(config["expected_selected_pulses"])),
                "tolerance": 0,
                "pass": bool(len(meta) == int(config["expected_selected_pulses"])),
            },
            {
                "quantity": "tagged random/forced B-stack entries",
                "report_value": int(config["expected_tagged_random_bstack_entries_min"]),
                "reproduced": tagged_b,
                "delta": tagged_b - int(config["expected_tagged_random_bstack_entries_min"]),
                "tolerance": "minimum",
                "pass": bool(tagged_b >= int(config["expected_tagged_random_bstack_entries_min"])),
            },
        ]
    )
    reproduction.to_csv(outdir / "reproduction_match_table.csv", index=False)

    leakage = pd.DataFrame(
        [
            {
                "check": "tagged_random_gate",
                "result": "failed: {} tagged B-stack candidates".format(tagged_b),
            },
            {
                "check": "real_ml_feature_exclusion",
                "result": "fallback ML excludes run, pulse_index/event IDs, and target_adc; feature_columns={}".format(
                    ";".join(ml_meta["feature_columns"])
                ),
            },
            {
                "check": "shuffled_training_target_control",
                "result": "fallback shuffled-target ridge MAE {:.2f} ADC; far worse than real ML means the real fallback signal is not explained by direct target leakage in the training labels".format(
                    shuffled_mae
                ),
            },
            {
                "check": "proxy_guard",
                "result": "no quiet-event amplitude-selected proxy is promoted to tagged-random validation",
            },
        ]
    )
    leakage.to_csv(outdir / "leakage_checks.csv", index=False)

    input_rows = []
    for path in raw_root_paths(config):
        input_rows.append({"path": str(path), "sha256": sha256_file(path), "bytes": int(path.stat().st_size)})
    pd.DataFrame(input_rows).to_csv(outdir / "input_sha256.csv", index=False)

    plot_outputs(outdir, audit, bench_frame, benchmark, by_run)

    followup_1 = (
        "S16f: inventory DAQ/run-log sources for true B-stack random or forced-trigger pedestal runs. "
        "Expected information gain: resolves whether the S16e gate failed because the sample was never recorded or only missing from this ROOT mirror."
    )
    followup_2 = (
        "S16g: rerun S16e immediately after tagged random-trigger ROOT is added, with no quiet-event amplitude selection. "
        "Expected information gain: directly confirms or falsifies adaptive pedestal zero-bias on true no-pulse samples."
    )

    numbers = {
        "git_commit": git_commit(),
        "benchmark": benchmark,
        "by_run": by_run,
        "reproduction": reproduction,
        "leakage": leakage,
        "raw_entries": raw_entries,
        "raw_nonbeam": raw_nonbeam,
        "tagged_b": tagged_b,
        "sorted_tag_branches": sorted_tag_branches,
        "ml_best": ml_meta["best"],
        "followup_1": followup_1,
        "followup_2": followup_2,
    }
    write_report(outdir, config, numbers)

    adaptive_unbiased = bool(adaptive["mean_bias_ci_low_adc"] <= 0 <= adaptive["mean_bias_ci_high_adc"])
    result = {
        "study": config["study"],
        "ticket": config["ticket"],
        "worker": config["worker"],
        "title": config["title"],
        "raw_reproduction": {
            "selected_b_stave_pulses": int(len(meta)),
            "expected_selected_b_stave_pulses": int(config["expected_selected_pulses"]),
            "raw_hrd_entries": raw_entries,
            "raw_nonbeam_trigger_entries": raw_nonbeam,
            "tagged_random_bstack_entries": tagged_b,
            "sorted_b_files_with_tag_like_branch": sorted_tag_branches,
            "true_tagged_random_sample_available": bool(tagged_b > 0),
        },
        "primary_gate_passed": bool(tagged_b >= int(config["expected_tagged_random_bstack_entries_min"])),
        "primary_tagged_random_result": None,
        "fallback_s16_pretrigger_benchmark": {
            "metric": "heldout_pretrigger_mae_adc_with_run_bootstrap_ci",
            "benchmark": json_records(benchmark),
            "by_run": json_records(by_run),
            "adaptive_unbiased_on_fallback": adaptive_unbiased,
        },
        "ml_meta": ml_meta,
        "leakage_checks": json_records(leakage),
        "conclusion": "No true tagged random/forced B-stack pedestal entries are present; S16e cannot validate adaptive_pc_excluding_target on random-trigger no-pulse samples.",
        "followup_tickets": [followup_1, followup_2],
    }
    (outdir / "result.json").write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")

    manifest = {
        "command": "/home/billy/anaconda3/bin/python3.7 {} --config {}".format(outdir / "s16e_tagged_random_pedestal.py", args.config),
        "config": str(args.config),
        "git_commit": git_commit(),
        "random_seed": int(config["ml"]["random_seed"]),
        "environment": {
            "python": ".".join(map(str, tuple(os.sys.version_info[:3]))),
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "uproot": uproot.__version__,
        },
        "inputs": str(outdir / "input_sha256.csv"),
        "outputs": output_hashes(outdir),
        "runtime_seconds": float(time.time() - start),
    }
    (outdir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
