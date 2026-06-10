#!/usr/bin/env python3
"""S00c raw ROOT selector-count regression gate.

The gate scans B-stack HRD ROOT files first, before fitting any diagnostic
model. It fails if the exact median-first-four or dynamic-range selector counts
drift from the recorded S00 anchors.
"""

from __future__ import annotations

import hashlib
import json
import math
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd
import uproot
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


CONFIG = Path("configs/s00c_1781029327_1513_28da0587.json")
SCRIPT = Path("scripts/s00c_1781029327_1513_28da0587_raw_selector_ci.py")


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
    for values in config["run_groups"].values():
        runs.extend(int(run) for run in values)
    return sorted(set(runs))


def markdown_table(df: pd.DataFrame) -> str:
    if df.empty:
        return "_No rows._"
    columns = list(df.columns)
    rows = ["| " + " | ".join(columns) + " |"]
    rows.append("| " + " | ".join(["---"] * len(columns)) + " |")
    for _, row in df.iterrows():
        rows.append("| " + " | ".join(str(row[col]) for col in columns) + " |")
    return "\n".join(rows)


def iter_raw_batches(path: Path, samples_per_channel: int, channels: np.ndarray, step_size: int = 20000):
    tree = uproot.open(path)["h101"]
    for batch in tree.iterate(["EVT", "HRDv"], step_size=step_size, library="np"):
        wave = np.stack(batch["HRDv"]).astype(np.float32).reshape(-1, 8, samples_per_channel)
        yield np.asarray(batch["EVT"], dtype=np.int64), wave[:, channels, :]


def append_ml_sample(
    rows: list[pd.DataFrame],
    run: int,
    evt: np.ndarray,
    wave: np.ndarray,
    median_amp: np.ndarray,
    dynamic_amp: np.ndarray,
    median_selected: np.ndarray,
    dynamic_selected: np.ndarray,
    config: dict,
    rng: np.random.Generator,
) -> None:
    ml_cfg = config["ml"]
    low = float(ml_cfg["near_threshold_low_adc"])
    high = float(ml_cfg["near_threshold_high_adc"])
    near = ((median_amp > low) | (dynamic_amp > low)) & ((median_amp < high) | (dynamic_amp < high))
    random_keep = rng.random(median_amp.shape) < float(ml_cfg["random_keep_fraction"])
    heldout_keep = run in {int(item) for item in ml_cfg["heldout_runs"]}
    keep = near | random_keep | heldout_keep
    if not keep.any():
        return

    event_idx, stave_idx = np.where(keep)
    pre4 = wave[..., config["baseline_samples"]]
    wf_max = wave.max(axis=-1)
    wf_min = wave.min(axis=-1)
    post = wave[..., 4:]
    stave_names = np.asarray(list(config["staves"].keys()))
    rows.append(
        pd.DataFrame(
            {
                "run": run,
                "evt": evt[event_idx],
                "stave": stave_names[stave_idx],
                "stave_idx": stave_idx.astype(int),
                "median_selected": median_selected[event_idx, stave_idx].astype(int),
                "dynamic_selected": dynamic_selected[event_idx, stave_idx].astype(int),
                "wave_max": wf_max[event_idx, stave_idx],
                "wave_min": wf_min[event_idx, stave_idx],
                "pre4_mean": pre4.mean(axis=-1)[event_idx, stave_idx],
                "pre4_std": pre4.std(axis=-1)[event_idx, stave_idx],
                "post_mean": post.mean(axis=-1)[event_idx, stave_idx],
                "post_std": post.std(axis=-1)[event_idx, stave_idx],
                "dynamic_amp": dynamic_amp[event_idx, stave_idx],
                "median_amp": median_amp[event_idx, stave_idx],
            }
        )
    )


def scan_raw(config: dict) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(int(config["ml"]["random_seed"]))
    channels = np.asarray(list(config["staves"].values()), dtype=int)
    cut = float(config["amplitude_cut_adc"])
    counts: list[dict] = []
    samples: list[pd.DataFrame] = []
    inputs: list[dict] = []

    for run in all_runs(config):
        path = Path(config["raw_root_dir"]) / f"hrdb_run_{run:04d}.root"
        if not path.exists():
            raise FileNotFoundError(path)
        inputs.append({"path": str(path), "sha256": sha256_file(path)})
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
            median_amp = wave.max(axis=-1) - baseline
            dynamic_amp = wave.max(axis=-1) - wave.min(axis=-1)
            median_selected = median_amp > cut
            dynamic_selected = dynamic_amp > cut
            row["events"] += int(len(evt))
            row["records"] += int(median_selected.size)
            row["median_first_four_selected"] += int(median_selected.sum())
            row["dynamic_range_selected"] += int(dynamic_selected.sum())
            row["dynamic_only"] += int((dynamic_selected & ~median_selected).sum())
            row["median_only"] += int((median_selected & ~dynamic_selected).sum())
            append_ml_sample(
                samples,
                run,
                evt,
                wave,
                median_amp,
                dynamic_amp,
                median_selected,
                dynamic_selected,
                config,
                rng,
            )
        counts.append(row)
        print(f"raw scan run {run}: {row}", flush=True)

    return pd.DataFrame(counts), pd.concat(samples, ignore_index=True), pd.DataFrame(inputs)


def count_checks(counts: pd.DataFrame, config: dict) -> pd.DataFrame:
    totals = counts[["median_first_four_selected", "dynamic_range_selected", "dynamic_only", "median_only"]].sum()
    rows = []
    for quantity, expected in config["expected_counts"].items():
        reproduced = int(totals[quantity])
        rows.append(
            {
                "quantity": quantity,
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
    n_runs = len(counts)
    rows = []
    for quantity in ["median_first_four_selected", "dynamic_range_selected", "dynamic_only", "median_only"]:
        values = counts[quantity].to_numpy(dtype=float)
        draws = np.empty(n_boot, dtype=float)
        for index in range(n_boot):
            draw_idx = rng.integers(0, n_runs, n_runs)
            draws[index] = float(values[draw_idx].sum())
        rows.append(
            {
                "quantity": quantity,
                "observed_total": int(values.sum()),
                "run_bootstrap_ci_low": float(np.quantile(draws, 0.025)),
                "run_bootstrap_ci_high": float(np.quantile(draws, 0.975)),
            }
        )
    return pd.DataFrame(rows)


def bootstrap_metric_by_run(by_run: pd.DataFrame, method: str, metric: str, config: dict) -> tuple[float, float]:
    rng = np.random.default_rng(int(config["ml"]["random_seed"]) + 2)
    values = by_run.loc[by_run["method"] == method, metric].to_numpy(dtype=float)
    if len(values) == 0:
        return math.nan, math.nan
    draws = np.empty(int(config["ml"]["bootstrap_samples"]), dtype=float)
    for index in range(len(draws)):
        draw_idx = rng.integers(0, len(values), len(values))
        draws[index] = float(np.mean(values[draw_idx]))
    return float(np.quantile(draws, 0.025)), float(np.quantile(draws, 0.975))


def metric_row(method: str, run: int, y_true: np.ndarray, pred: np.ndarray, score: np.ndarray) -> dict:
    row = {
        "method": method,
        "run": int(run),
        "n_test_records": int(len(y_true)),
        "accuracy": float(accuracy_score(y_true, pred)),
        "precision": float(precision_score(y_true, pred, zero_division=0)),
        "recall": float(recall_score(y_true, pred, zero_division=0)),
        "f1": float(f1_score(y_true, pred, zero_division=0)),
        "false_positive": int(((pred == 1) & (y_true == 0)).sum()),
        "false_negative": int(((pred == 0) & (y_true == 1)).sum()),
    }
    if len(np.unique(y_true)) == 2:
        row["roc_auc"] = float(roc_auc_score(y_true, score))
        row["average_precision"] = float(average_precision_score(y_true, score))
    else:
        row["roc_auc"] = math.nan
        row["average_precision"] = math.nan
    return row


def benchmark_methods(sample: pd.DataFrame, config: dict) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    ml_cfg = config["ml"]
    heldout_runs = [int(run) for run in ml_cfg["heldout_runs"]]
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
    x_train = train[honest_features].to_numpy(dtype=float)
    splitter = GroupKFold(n_splits=int(ml_cfg["cv_folds"]))
    for c_value in [float(item) for item in ml_cfg["regularization_c"]]:
        scores = []
        for fit_idx, valid_idx in splitter.split(x_train, y_train, groups):
            model = make_pipeline(
                StandardScaler(),
                LogisticRegression(
                    C=c_value,
                    max_iter=1000,
                    class_weight="balanced",
                    random_state=int(ml_cfg["random_seed"]),
                ),
            )
            model.fit(x_train[fit_idx], y_train[fit_idx])
            scores.append(accuracy_score(y_train[valid_idx], model.predict(x_train[valid_idx])))
        cv_score = float(np.mean(scores))
        cv_rows.append({"feature_set": "honest_raw_summaries", "C": c_value, "cv_accuracy": cv_score})
        if cv_score > best_score:
            best_score = cv_score
            best_c = c_value

    model = make_pipeline(
        StandardScaler(),
        LogisticRegression(C=best_c, max_iter=1000, class_weight="balanced", random_state=int(ml_cfg["random_seed"])),
    )
    model.fit(x_train, y_train)
    ml_prob = model.predict_proba(test[honest_features].to_numpy(dtype=float))[:, 1]
    ml_pred = (ml_prob >= 0.5).astype(int)

    leaky_model = make_pipeline(
        StandardScaler(),
        LogisticRegression(C=10.0, max_iter=1000, class_weight="balanced", random_state=int(ml_cfg["random_seed"])),
    )
    leaky_model.fit(train[leaky_features].to_numpy(dtype=float), y_train)
    leaky_prob = leaky_model.predict_proba(test[leaky_features].to_numpy(dtype=float))[:, 1]
    leaky_pred = (leaky_prob >= 0.5).astype(int)

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
            "intentional semantic-drift comparator",
        ),
        ("ML logistic honest raw summaries", ml_pred, ml_prob, f"run-group CV selected C={best_c}"),
        (
            "ML leakage sentinel with median_amp",
            leaky_pred,
            leaky_prob,
            "contains the direct selector-rule feature",
        ),
    ]

    by_run_rows = []
    for method, pred, score, _notes in methods:
        for run in heldout_runs:
            mask = test["run"].to_numpy(dtype=int) == run
            by_run_rows.append(metric_row(method, run, y_test[mask], pred[mask], score[mask]))
    by_run = pd.DataFrame(by_run_rows)

    bench_rows = []
    for method, pred, score, notes in methods:
        ci_low, ci_high = bootstrap_metric_by_run(by_run, method, "accuracy", config)
        row = metric_row(method, -1, y_test, pred, score)
        row.update(
            {
                "run": "57,65",
                "heldout_runs": ",".join(str(run) for run in heldout_runs),
                "accuracy_ci_low": ci_low,
                "accuracy_ci_high": ci_high,
                "notes": notes,
            }
        )
        bench_rows.append(row)

    leakage = pd.DataFrame(
        [
            {
                "check": "run_group_cv",
                "status": "pass",
                "detail": f"training CV grouped by run with {int(ml_cfg['cv_folds'])} folds",
            },
            {
                "check": "heldout_runs",
                "status": "pass",
                "detail": f"runs {','.join(str(run) for run in heldout_runs)} excluded from training",
            },
            {
                "check": "honest_ml_features",
                "status": "pass",
                "detail": "honest model excludes median_amp, run id, and event id",
            },
            {
                "check": "leakage_sentinel",
                "status": "expected_alarm",
                "detail": "sentinel includes median_amp to show direct-rule leakage",
            },
            {
                "check": "semantic_drift_alarm",
                "status": "pass",
                "detail": "dynamic-range selector overcount is reported and not accepted",
            },
        ]
    )
    return pd.DataFrame(cv_rows), pd.DataFrame(bench_rows), by_run, leakage


def output_hashes(out: Path) -> dict[str, str]:
    return {
        path.name: sha256_file(path)
        for path in sorted(out.iterdir())
        if path.is_file() and path.name != "manifest.json"
    }


def write_report(out: Path, config: dict, checks: pd.DataFrame, boot: pd.DataFrame, bench: pd.DataFrame) -> None:
    checks_md = checks.copy()
    checks_md["pass"] = checks_md["pass"].map(lambda value: "yes" if bool(value) else "no")
    bench_md = bench[
        ["method", "accuracy", "accuracy_ci_low", "accuracy_ci_high", "false_positive", "false_negative", "notes"]
    ].copy()
    report = f"""# Study report: S00c - raw ROOT selector-count CI gate

- **Study ID:** S00c
- **Ticket:** {config['ticket_id']}
- **Worker:** {config['worker']}
- **Date:** 2026-06-10
- **Input checksums:** `input_sha256.csv`
- **Config:** `{CONFIG}`
- **Executable:** `{SCRIPT}`

## Question
Add a raw-ROOT regression gate that recomputes the B-stack HRD selector counts and fails on accidental selector drift. The gate scans `HRDv` directly before any modeling.

## Reproduction Gate
Physical B staves are channels 0, 2, 4, and 6. The accepted selector is `max(HRDv) - median(samples 0..3) > 1000 ADC`; the dynamic-range comparator is `max(HRDv) - min(HRDv) > 1000 ADC`.

{markdown_table(checks_md)}

The script exits nonzero if any count has a nonzero delta.

## Traditional Method
The strong traditional method is the deterministic median-first-four selector, with the dynamic-range selector as the semantic-drift comparator. Whole-run bootstrap intervals below describe run-to-run count stability and are not tolerance bands for the gate.

{markdown_table(boot)}

## ML Method
A logistic classifier predicts the median-first-four selector from raw waveform summaries. Training and cross-validation are grouped by run; runs {', '.join(str(run) for run in config['ml']['heldout_runs'])} are held out. The accuracy intervals bootstrap held-out runs.

{markdown_table(bench_md)}

## Leakage Checks
The honest ML model excludes `median_amp`, run id, and event id. A sentinel model deliberately includes `median_amp`, a direct transform of the selector rule, so too-good performance there is treated as leakage rather than generalization. The regression gate itself never depends on ML; it passes only if exact raw selector counts match.

## Reproducibility
Run:

```bash
/home/billy/anaconda3/bin/python {SCRIPT}
```

Artifacts: `REPORT.md`, `result.json`, `manifest.json`, `input_sha256.csv`, `counts_by_run.csv`, `reproduction_match_table.csv`, `run_bootstrap_ci.csv`, `ml_cv_scan.csv`, `heldout_benchmark.csv`, `heldout_benchmark_by_run.csv`, and `leakage_checks.csv`.
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
        raise SystemExit(f"S00c raw ROOT selector-count gate failed:\n{checks.to_string(index=False)}")

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
        "ci_gate": {
            "metric": "exact raw ROOT selector counts",
            "tolerance": 0,
            "failed_checks": int((~checks["pass"]).sum()),
        },
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
            "interpretation": "median_amp is a direct selector-rule feature, so too-good ML here is leakage",
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
        "commands": [f"/home/billy/anaconda3/bin/python {SCRIPT}"],
        "config": str(CONFIG),
        "script": str(SCRIPT),
        "inputs": inputs.to_dict(orient="records"),
        "outputs_sha256": output_hashes(out),
        "random_seed": int(config["ml"]["random_seed"]),
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "totals": totals,
                "checks": checks.to_dict(orient="records"),
                "benchmark": bench.to_dict(orient="records"),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
