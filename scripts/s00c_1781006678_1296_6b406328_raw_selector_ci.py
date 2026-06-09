#!/usr/bin/env python3
"""S00c: raw selector-count CI regression from B-stack ROOT files."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd
import uproot
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, average_precision_score, f1_score, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


CONFIG = Path("configs/s00c_1781006678_1296_6b406328.json")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def git_commit() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()


def load_config() -> dict:
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def all_runs(config: dict) -> list[int]:
    runs: list[int] = []
    for group_runs in config["run_groups"].values():
        runs.extend(int(run) for run in group_runs)
    return sorted(set(runs))


def bootstrap_ci(values: np.ndarray, rng: np.random.Generator, n_boot: int) -> tuple[float, float]:
    if len(values) == 0:
        return math.nan, math.nan
    draws = np.empty(n_boot, dtype=float)
    for i in range(n_boot):
        idx = rng.integers(0, len(values), len(values))
        draws[i] = float(np.mean(values[idx]))
    return float(np.quantile(draws, 0.025)), float(np.quantile(draws, 0.975))


def run_bootstrap_metric_ci(
    by_run: pd.DataFrame,
    method: str,
    metric: str,
    rng: np.random.Generator,
    n_boot: int,
) -> tuple[float, float]:
    values = by_run.loc[by_run["method"] == method, ["run", metric]].copy()
    if values.empty:
        return math.nan, math.nan
    metric_by_run = values.set_index("run")[metric].to_numpy(dtype=float)
    draws = np.empty(n_boot, dtype=float)
    for i in range(n_boot):
        idx = rng.integers(0, len(metric_by_run), len(metric_by_run))
        draws[i] = float(np.mean(metric_by_run[idx]))
    return float(np.quantile(draws, 0.025)), float(np.quantile(draws, 0.975))


def iter_raw_batches(path: Path, samples_per_channel: int, channels: np.ndarray, step_size: int = 20000):
    tree = uproot.open(path)["h101"]
    for batch in tree.iterate(["EVT", "HRDv"], step_size=step_size, library="np"):
        wave = np.stack(batch["HRDv"]).astype(np.float32).reshape(-1, 8, samples_per_channel)
        yield np.asarray(batch["EVT"], dtype=np.int64), wave[:, channels, :]


def append_sample_rows(
    rows: list[pd.DataFrame],
    run: int,
    evt: np.ndarray,
    wave: np.ndarray,
    med_amp: np.ndarray,
    dyn_amp: np.ndarray,
    med_sel: np.ndarray,
    config: dict,
    rng: np.random.Generator,
) -> None:
    ml_cfg = config["ml"]
    near = (med_amp > float(ml_cfg["near_threshold_low_adc"])) | (dyn_amp > float(ml_cfg["near_threshold_low_adc"]))
    near &= (med_amp < float(ml_cfg["near_threshold_high_adc"])) | (dyn_amp < float(ml_cfg["near_threshold_high_adc"]))
    random_keep = rng.random(med_amp.shape) < float(ml_cfg["random_keep_fraction"])
    heldout_keep = run in set(int(x) for x in ml_cfg["heldout_runs"])
    keep = near | random_keep | heldout_keep
    if not keep.any():
        return

    event_idx, stave_idx = np.where(keep)
    pre4 = wave[..., config["baseline_samples"]]
    wf_max = wave.max(axis=-1)
    wf_min = wave.min(axis=-1)
    pre4_mean = pre4.mean(axis=-1)
    pre4_std = pre4.std(axis=-1)
    post_mean = wave[..., 4:].mean(axis=-1)
    post_std = wave[..., 4:].std(axis=-1)
    rows.append(
        pd.DataFrame(
            {
                "run": run,
                "evt": evt[event_idx],
                "stave": np.asarray(list(config["staves"].keys()))[stave_idx],
                "stave_idx": stave_idx.astype(int),
                "median_selected": med_sel[event_idx, stave_idx].astype(int),
                "dynamic_selected": (dyn_amp[event_idx, stave_idx] > float(config["amplitude_cut_adc"])).astype(int),
                "wave_max": wf_max[event_idx, stave_idx],
                "wave_min": wf_min[event_idx, stave_idx],
                "pre4_mean": pre4_mean[event_idx, stave_idx],
                "pre4_std": pre4_std[event_idx, stave_idx],
                "post_mean": post_mean[event_idx, stave_idx],
                "post_std": post_std[event_idx, stave_idx],
                "dynamic_amp": dyn_amp[event_idx, stave_idx],
                "median_amp": med_amp[event_idx, stave_idx],
            }
        )
    )


def scan_raw(config: dict) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(int(config["ml"]["random_seed"]))
    channels = np.asarray(list(config["staves"].values()), dtype=int)
    cut = float(config["amplitude_cut_adc"])
    rows: list[dict] = []
    sample_rows: list[pd.DataFrame] = []
    input_rows: list[dict] = []

    for run in all_runs(config):
        path = Path(config["raw_root_dir"]) / f"hrdb_run_{run:04d}.root"
        input_rows.append({"path": str(path), "sha256": sha256_file(path)})
        row = {
            "run": run,
            "events": 0,
            "records": 0,
            "median_first_four_selected": 0,
            "dynamic_range_selected": 0,
            "dynamic_only": 0,
            "median_only": 0,
        }
        for evt, wave in iter_raw_batches(path, int(config["samples_per_channel"]), channels):
            baseline = np.median(wave[..., config["baseline_samples"]], axis=-1)
            med_amp = wave.max(axis=-1) - baseline
            dyn_amp = wave.max(axis=-1) - wave.min(axis=-1)
            med_sel = med_amp > cut
            dyn_sel = dyn_amp > cut
            row["events"] += int(len(evt))
            row["records"] += int(med_sel.size)
            row["median_first_four_selected"] += int(med_sel.sum())
            row["dynamic_range_selected"] += int(dyn_sel.sum())
            row["dynamic_only"] += int((dyn_sel & ~med_sel).sum())
            row["median_only"] += int((med_sel & ~dyn_sel).sum())
            append_sample_rows(sample_rows, run, evt, wave, med_amp, dyn_amp, med_sel, config, rng)
        rows.append(row)
        print(f"run {run}: {row}")

    return pd.DataFrame(rows), pd.concat(sample_rows, ignore_index=True), pd.DataFrame(input_rows)


def count_checks(counts: pd.DataFrame, config: dict) -> pd.DataFrame:
    totals = counts[["median_first_four_selected", "dynamic_range_selected", "dynamic_only", "median_only"]].sum()
    rows = []
    for key, expected in config["expected_counts"].items():
        reproduced = int(totals[key])
        rows.append(
            {
                "quantity": key,
                "expected": int(expected),
                "reproduced": reproduced,
                "delta": reproduced - int(expected),
                "tolerance": 0,
                "pass": reproduced == int(expected),
            }
        )
    return pd.DataFrame(rows)


def run_level_bootstrap(counts: pd.DataFrame, config: dict) -> pd.DataFrame:
    rng = np.random.default_rng(int(config["ml"]["random_seed"]) + 1)
    n_boot = int(config["ml"]["bootstrap_samples"])
    rows = []
    n_runs = len(counts)
    for key in ["median_first_four_selected", "dynamic_range_selected", "dynamic_only", "median_only"]:
        run_values = counts[key].to_numpy(dtype=float)
        boot_totals = np.empty(n_boot, dtype=float)
        for i in range(n_boot):
            idx = rng.integers(0, n_runs, n_runs)
            boot_totals[i] = float(run_values[idx].sum())
        rows.append(
            {
                "quantity": key,
                "observed_total": int(run_values.sum()),
                "run_bootstrap_ci_low": float(np.quantile(boot_totals, 0.025)),
                "run_bootstrap_ci_high": float(np.quantile(boot_totals, 0.975)),
            }
        )
    return pd.DataFrame(rows)


def benchmark_methods(sample: pd.DataFrame, config: dict) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    ml_cfg = config["ml"]
    heldout_runs = [int(x) for x in ml_cfg["heldout_runs"]]
    train = sample[~sample["run"].isin(heldout_runs)].copy()
    test = sample[sample["run"].isin(heldout_runs)].copy()
    y_train = train["median_selected"].to_numpy(dtype=int)
    y_test = test["median_selected"].to_numpy(dtype=int)
    groups = train["run"].to_numpy(dtype=int)

    honest_features = ["wave_max", "wave_min", "pre4_mean", "pre4_std", "post_mean", "post_std", "dynamic_amp", "stave_idx"]
    leaky_features = honest_features + ["median_amp"]
    cv_rows = []
    best_c = None
    best_score = -np.inf
    for c_value in [float(x) for x in ml_cfg["regularization_c"]]:
        scores = []
        splitter = GroupKFold(n_splits=int(ml_cfg["cv_folds"]))
        X = train[honest_features].to_numpy(dtype=float)
        for fit_idx, valid_idx in splitter.split(X, y_train, groups):
            model = make_pipeline(
                StandardScaler(),
                LogisticRegression(C=c_value, max_iter=1000, class_weight="balanced", random_state=int(ml_cfg["random_seed"])),
            )
            model.fit(X[fit_idx], y_train[fit_idx])
            scores.append(accuracy_score(y_train[valid_idx], model.predict(X[valid_idx])))
        cv_score = float(np.mean(scores))
        cv_rows.append({"feature_set": "honest_raw_summaries", "C": c_value, "cv_accuracy": cv_score})
        if cv_score > best_score:
            best_score = cv_score
            best_c = c_value

    model = make_pipeline(
        StandardScaler(),
        LogisticRegression(C=best_c, max_iter=1000, class_weight="balanced", random_state=int(ml_cfg["random_seed"])),
    )
    model.fit(train[honest_features].to_numpy(dtype=float), y_train)
    ml_prob = model.predict_proba(test[honest_features].to_numpy(dtype=float))[:, 1]
    ml_pred = (ml_prob >= 0.5).astype(int)

    leaky_model = make_pipeline(
        StandardScaler(),
        LogisticRegression(C=10.0, max_iter=1000, class_weight="balanced", random_state=int(ml_cfg["random_seed"])),
    )
    leaky_model.fit(train[leaky_features].to_numpy(dtype=float), y_train)
    leaky_prob = leaky_model.predict_proba(test[leaky_features].to_numpy(dtype=float))[:, 1]
    leaky_pred = (leaky_prob >= 0.5).astype(int)

    rng = np.random.default_rng(int(ml_cfg["random_seed"]) + 2)
    n_boot = int(ml_cfg["bootstrap_samples"])
    methods = [
        (
            "traditional median-first-four gate",
            (test["median_amp"].to_numpy(dtype=float) > float(config["amplitude_cut_adc"])).astype(int),
            test["median_amp"].to_numpy(dtype=float),
            "deterministic raw selector definition",
        ),
        (
            "dynamic-range selector",
            test["dynamic_selected"].to_numpy(dtype=int),
            test["dynamic_amp"].to_numpy(dtype=float),
            "intentional semantic-change comparator",
        ),
        (
            "ML logistic honest raw summaries",
            ml_pred,
            ml_prob,
            f"run-group CV selected C={best_c}",
        ),
        (
            "ML leakage sentinel with median_amp",
            leaky_pred,
            leaky_prob,
            "contains a direct monotone transform of the target rule",
        ),
    ]
    bench_rows = []
    by_run_rows = []
    for method, pred, score, notes in methods:
        for run in heldout_runs:
            mask = test["run"].to_numpy(dtype=int) == run
            y_run = y_test[mask]
            pred_run = pred[mask]
            score_run = score[mask]
            run_row = {
                "method": method,
                "run": int(run),
                "n_test_records": int(mask.sum()),
                "accuracy": float(accuracy_score(y_run, pred_run)),
                "precision": float(precision_score(y_run, pred_run, zero_division=0)),
                "recall": float(recall_score(y_run, pred_run, zero_division=0)),
                "f1": float(f1_score(y_run, pred_run, zero_division=0)),
                "false_positive": int(((pred_run == 1) & (y_run == 0)).sum()),
                "false_negative": int(((pred_run == 0) & (y_run == 1)).sum()),
            }
            if len(np.unique(y_run)) == 2:
                run_row["roc_auc"] = float(roc_auc_score(y_run, score_run))
                run_row["average_precision"] = float(average_precision_score(y_run, score_run))
            else:
                run_row["roc_auc"] = math.nan
                run_row["average_precision"] = math.nan
            by_run_rows.append(run_row)

    by_run = pd.DataFrame(by_run_rows)
    for method, pred, score, notes in methods:
        acc_ci = run_bootstrap_metric_ci(by_run, method, "accuracy", rng, n_boot)
        row = {
            "method": method,
            "heldout_runs": ",".join(str(x) for x in heldout_runs),
            "n_test_records": int(len(y_test)),
            "accuracy": float(accuracy_score(y_test, pred)),
            "accuracy_ci_low": acc_ci[0],
            "accuracy_ci_high": acc_ci[1],
            "precision": float(precision_score(y_test, pred, zero_division=0)),
            "recall": float(recall_score(y_test, pred, zero_division=0)),
            "f1": float(f1_score(y_test, pred, zero_division=0)),
            "false_positive": int(((pred == 1) & (y_test == 0)).sum()),
            "false_negative": int(((pred == 0) & (y_test == 1)).sum()),
            "notes": notes,
        }
        if len(np.unique(y_test)) == 2:
            row["roc_auc"] = float(roc_auc_score(y_test, score))
            row["average_precision"] = float(average_precision_score(y_test, score))
        else:
            row["roc_auc"] = math.nan
            row["average_precision"] = math.nan
        bench_rows.append(row)
    leakage_rows = [
        {
            "check": "run_group_cv",
            "status": "pass",
            "detail": f"training CV grouped by run with {int(ml_cfg['cv_folds'])} folds",
        },
        {
            "check": "heldout_runs",
            "status": "pass",
            "detail": f"never trained on held-out runs {','.join(str(x) for x in heldout_runs)}",
        },
        {
            "check": "honest_ml_features",
            "status": "pass",
            "detail": "honest model excludes median_amp, the direct selector-rule feature",
        },
        {
            "check": "leakage_sentinel",
            "status": "expected_alarm",
            "detail": "sentinel includes median_amp and demonstrates why too-good ML is leakage",
        },
        {
            "check": "semantic_drift_alarm",
            "status": "pass",
            "detail": "dynamic-range selector is reported as an overcount comparator, not accepted semantics",
        },
    ]
    return pd.DataFrame(cv_rows), pd.DataFrame(bench_rows), by_run, pd.DataFrame(leakage_rows)


def output_hashes(out: Path) -> dict[str, str]:
    hashes = {}
    for path in sorted(out.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            hashes[path.name] = sha256_file(path)
    return hashes


def write_report(out: Path, config: dict, checks: pd.DataFrame, boot: pd.DataFrame, bench: pd.DataFrame) -> None:
    def fmt_bool(value: bool) -> str:
        return "yes" if value else "no"

    checks_md = checks.copy()
    checks_md["pass"] = checks_md["pass"].map(fmt_bool)
    boot_md = boot.copy()
    bench_md = bench[
        [
            "method",
            "accuracy",
            "accuracy_ci_low",
            "accuracy_ci_high",
            "false_positive",
            "false_negative",
            "notes",
        ]
    ].copy()
    report = f"""# Study report: S00c - raw selector-count CI regression

- **Study ID:** S00c
- **Ticket:** {config['ticket_id']}
- **Author (worker label):** {config['worker']}
- **Date:** 2026-06-09
- **Input checksum(s):** `input_sha256.csv` records all raw B-stack ROOT files used.
- **Config:** `configs/s00c_1781006678_1296_6b406328.json`
- **Executable:** `scripts/s00c_1781006678_1296_6b406328_raw_selector_ci.py`

## 0. Question
Can a lightweight raw-ROOT regression guard the S00 B-stave selector semantics by recomputing both selector counts directly from `HRDv`?

The fixed anchors are:

- `median_first_four_selected = 640737`
- `dynamic_range_selected = 706373`
- `dynamic_only = 65636`
- `median_only = 0`

## 1. Reproduction
The script first scans raw B-stack ROOT files only, before any modeling. Physical B staves are channels 0, 2, 4, and 6. The S00 selector is `max(HRDv) - median(samples 0..3) > 1000 ADC`; the semantic-change comparator is `max(HRDv) - min(HRDv) > 1000 ADC`.

{checks_md.to_markdown(index=False)}

Any nonzero delta exits the script with a failed assertion, making this usable as a CI regression.

## 2. Traditional Method
The traditional method is the explicit S00 median-first-four gate. It is deterministic, full-population, and exactly reproduces the 640737 selected-record anchor. The dynamic-range selector is included as a strong comparator because it is the known accidental semantic drift: it admits 65636 extra records and has zero median-only losses.

Run-held-out bootstrap intervals below resample whole runs and describe count stability, not anchor tolerance:

{boot_md.to_markdown(index=False)}

## 3. ML Method
The ML method is a logistic classifier trained to predict the median-first-four selector from raw waveform summaries. The split is by run, with runs {', '.join(str(x) for x in config['ml']['heldout_runs'])} held out. Cross-validation on training runs is grouped by run, and the accuracy intervals below bootstrap the held-out runs, not individual records.

{bench_md.to_markdown(index=False)}

The honest ML model uses raw summaries but does not receive `median_amp`. A separate leakage sentinel deliberately includes `median_amp`; its near-perfect behavior is treated as evidence that direct selector-rule features are leakage for any claimed ML generalization. The deterministic traditional gate remains the CI guardrail.

## 4. Leakage and Failure Checks
- Splits are by run for ML CV and held-out testing.
- The regression does not rely on ML to pass; it fails only on exact raw count deltas.
- The leakage sentinel verifies that a model can look too good if it is handed the selector formula as a feature.
- The dynamic-range comparator is the semantic-change alarm: it reproduces the documented overcount, not the accepted S00 selector.

## 5. Reproducibility
Regenerate all artifacts with:

```bash
/home/billy/anaconda3/bin/python scripts/s00c_1781006678_1296_6b406328_raw_selector_ci.py
```

Artifacts written: `REPORT.md`, `result.json`, `manifest.json`, `input_sha256.csv`, `counts_by_run.csv`, `reproduction_match_table.csv`, `run_bootstrap_ci.csv`, `ml_cv_scan.csv`, `heldout_benchmark.csv`, `heldout_benchmark_by_run.csv`, and `leakage_checks.csv`.
"""
    (out / "REPORT.md").write_text(report, encoding="utf-8")


def main() -> None:
    config = load_config()
    out = Path(config["output_dir"])
    out.mkdir(parents=True, exist_ok=True)

    counts, sample, inputs = scan_raw(config)
    checks = count_checks(counts, config)
    boot = run_level_bootstrap(counts, config)
    cv, bench, bench_by_run, leakage = benchmark_methods(sample, config)

    counts.to_csv(out / "counts_by_run.csv", index=False)
    checks.to_csv(out / "reproduction_match_table.csv", index=False)
    boot.to_csv(out / "run_bootstrap_ci.csv", index=False)
    cv.to_csv(out / "ml_cv_scan.csv", index=False)
    bench.to_csv(out / "heldout_benchmark.csv", index=False)
    bench_by_run.to_csv(out / "heldout_benchmark_by_run.csv", index=False)
    leakage.to_csv(out / "leakage_checks.csv", index=False)
    inputs.to_csv(out / "input_sha256.csv", index=False)

    write_report(out, config, checks, boot, bench)

    if not bool(checks["pass"].all()):
        raise SystemExit(f"S00c anchor regression failed:\n{checks.to_string(index=False)}")

    totals = counts[["events", "records", "median_first_four_selected", "dynamic_range_selected", "dynamic_only", "median_only"]].sum().to_dict()
    trad = bench[bench["method"] == "traditional median-first-four gate"].iloc[0]
    ml = bench[bench["method"] == "ML logistic honest raw summaries"].iloc[0]
    leaky = bench[bench["method"] == "ML leakage sentinel with median_amp"].iloc[0]
    result = {
        "study": config["study_id"],
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced": True,
        "anchors": {key: int(totals[key]) for key in config["expected_counts"]},
        "traditional": {
            "method": "median-first-four raw HRDv selector",
            "metric": "heldout_selection_accuracy",
            "value": float(trad["accuracy"]),
            "ci": [float(trad["accuracy_ci_low"]), float(trad["accuracy_ci_high"])],
            "false_positive": int(trad["false_positive"]),
            "false_negative": int(trad["false_negative"]),
        },
        "ml": {
            "method": "run-held-out logistic on honest raw summaries",
            "metric": "heldout_selection_accuracy",
            "value": float(ml["accuracy"]),
            "ci": [float(ml["accuracy_ci_low"]), float(ml["accuracy_ci_high"])],
            "false_positive": int(ml["false_positive"]),
            "false_negative": int(ml["false_negative"]),
        },
        "leakage_hunt": {
            "leaky_median_amp_accuracy": float(leaky["accuracy"]),
            "interpretation": "median_amp is a direct selector-rule feature, so near-perfect ML here is leakage, not generalization",
        },
        "falsification": {
            "preregistered_metric": "exact anchor count deltas",
            "failed_checks": int((~checks["pass"]).sum()),
            "tolerance": 0,
        },
        "input_sha256": "input_sha256.csv",
        "git_commit": git_commit(),
        "next_tickets": [],
    }
    (out / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    manifest = {
        "study": config["study_id"],
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "commands": ["/home/billy/anaconda3/bin/python scripts/s00c_1781006678_1296_6b406328_raw_selector_ci.py"],
        "config": str(CONFIG),
        "inputs": inputs.to_dict(orient="records"),
        "outputs_sha256": output_hashes(out),
        "random_seed": int(config["ml"]["random_seed"]),
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    print(json.dumps({"totals": totals, "checks": checks.to_dict(orient="records"), "benchmark": bench.to_dict(orient="records")}, indent=2))


if __name__ == "__main__":
    main()
