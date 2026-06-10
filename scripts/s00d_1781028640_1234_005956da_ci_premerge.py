#!/usr/bin/env python3
"""S00d: CI/pre-merge guard for the S00c raw selector-count anchors."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import uproot


TICKET_ID = "1781028640.1234.005956da"
CONFIG_PATH = Path("configs/s00d_1781028640_1234_005956da_ci_premerge.json")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def git_commit() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()


def load_config() -> dict:
    cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    source = json.loads(Path(cfg["source_config"]).read_text(encoding="utf-8"))
    merged = {**source, **cfg}
    merged["expected_counts"] = cfg["expected_counts"]
    env_root = os.environ.get(str(cfg["raw_root_env"]), "").strip()
    if env_root:
        merged["raw_root_dir"] = env_root
    return merged


def all_runs(config: dict) -> list[int]:
    runs: list[int] = []
    for group_runs in config["run_groups"].values():
        runs.extend(int(run) for run in group_runs)
    return sorted(set(runs))


def iter_raw_batches(path: Path, samples_per_channel: int, channels: np.ndarray, step_size: int = 50000):
    tree = uproot.open(path)["h101"]
    for batch in tree.iterate(["EVT", "HRDv"], step_size=step_size, library="np"):
        wave = np.stack(batch["HRDv"]).astype(np.float32).reshape(-1, 8, samples_per_channel)
        yield np.asarray(batch["EVT"], dtype=np.int64), wave[:, channels, :]


def scan_counts_only(config: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    channels = np.asarray(list(config["staves"].values()), dtype=int)
    cut = float(config["amplitude_cut_adc"])
    root_dir = Path(config["raw_root_dir"])
    rows: list[dict] = []
    input_rows: list[dict] = []
    for run in all_runs(config):
        path = root_dir / f"hrdb_run_{run:04d}.root"
        if not path.exists():
            raise FileNotFoundError(f"missing raw ROOT input for S00d guard: {path}")
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
            median_amp = wave.max(axis=-1) - baseline
            dynamic_amp = wave.max(axis=-1) - wave.min(axis=-1)
            median_sel = median_amp > cut
            dynamic_sel = dynamic_amp > cut
            row["events"] += int(len(evt))
            row["records"] += int(median_sel.size)
            row["median_first_four_selected"] += int(median_sel.sum())
            row["dynamic_range_selected"] += int(dynamic_sel.sum())
            row["dynamic_only"] += int((dynamic_sel & ~median_sel).sum())
            row["median_only"] += int((median_sel & ~dynamic_sel).sum())
        rows.append(row)
        print(f"run {run}: {row}", flush=True)
    return pd.DataFrame(rows), pd.DataFrame(input_rows)


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


def output_hashes(out_dir: Path) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            hashes[path.name] = sha256_file(path)
    return hashes


def import_s00c_module():
    sys.path.insert(0, str(Path("scripts").resolve()))
    import s00c_raw_selector_count_ci_regression as s00c  # type: ignore

    return s00c


def heldout_run_block_benchmark(sample: pd.DataFrame, config: dict, cv: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import accuracy_score
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    ml_cfg = config["ml"]
    heldout_runs = [int(x) for x in ml_cfg["heldout_runs"]]
    train = sample[~sample["run"].isin(heldout_runs)].copy()
    test = sample[sample["run"].isin(heldout_runs)].copy()
    y_train = train["median_selected"].to_numpy(dtype=int)
    y_test = test["median_selected"].to_numpy(dtype=int)
    honest_features = ["wave_max", "wave_min", "pre4_mean", "pre4_std", "post_mean", "post_std", "dynamic_amp", "stave_idx"]
    leaky_features = honest_features + ["median_amp"]
    best_c = float(cv.sort_values(["cv_accuracy", "C"], ascending=[False, True]).iloc[0]["C"])

    model = make_pipeline(
        StandardScaler(),
        LogisticRegression(C=best_c, max_iter=1000, class_weight="balanced", random_state=int(ml_cfg["random_seed"])),
    )
    model.fit(train[honest_features].to_numpy(dtype=float), y_train)
    ml_pred = (model.predict_proba(test[honest_features].to_numpy(dtype=float))[:, 1] >= 0.5).astype(int)

    leaky_model = make_pipeline(
        StandardScaler(),
        LogisticRegression(C=10.0, max_iter=1000, class_weight="balanced", random_state=int(ml_cfg["random_seed"])),
    )
    leaky_model.fit(train[leaky_features].to_numpy(dtype=float), y_train)
    leaky_pred = (leaky_model.predict_proba(test[leaky_features].to_numpy(dtype=float))[:, 1] >= 0.5).astype(int)

    method_preds = {
        "traditional median-first-four gate": (test["median_amp"].to_numpy(dtype=float) > float(config["amplitude_cut_adc"])).astype(int),
        "dynamic-range selector": test["dynamic_selected"].to_numpy(dtype=int),
        "ML logistic honest raw summaries": ml_pred,
        "ML leakage sentinel with median_amp": leaky_pred,
    }
    work = test[["run"]].copy()
    work["y_true"] = y_test
    per_run_rows = []
    for method, pred in method_preds.items():
        work["pred"] = pred
        for run, group in work.groupby("run"):
            yt = group["y_true"].to_numpy(dtype=int)
            yp = group["pred"].to_numpy(dtype=int)
            per_run_rows.append(
                {
                    "method": method,
                    "heldout_run": int(run),
                    "n_test_records": int(len(group)),
                    "accuracy": float(accuracy_score(yt, yp)),
                    "false_positive": int(((yp == 1) & (yt == 0)).sum()),
                    "false_negative": int(((yp == 0) & (yt == 1)).sum()),
                }
            )
    per_run = pd.DataFrame(per_run_rows)

    rng = np.random.default_rng(int(ml_cfg["random_seed"]) + 303)
    n_boot = int(ml_cfg["bootstrap_samples"])
    summary_rows = []
    for method, group in per_run.groupby("method"):
        values = group["accuracy"].to_numpy(dtype=float)
        draws = np.empty(n_boot, dtype=float)
        for i in range(n_boot):
            idx = rng.integers(0, len(values), len(values))
            draws[i] = float(values[idx].mean())
        summary_rows.append(
            {
                "method": method,
                "n_heldout_runs": int(len(values)),
                "mean_run_accuracy": float(values.mean()),
                "run_bootstrap_ci_low": float(np.quantile(draws, 0.025)),
                "run_bootstrap_ci_high": float(np.quantile(draws, 0.975)),
                "min_run_accuracy": float(values.min()),
                "max_run_accuracy": float(values.max()),
            }
        )
    summary = pd.DataFrame(summary_rows).sort_values("method").reset_index(drop=True)
    return per_run.sort_values(["method", "heldout_run"]).reset_index(drop=True), summary


def write_report(
    out_dir: Path,
    config: dict,
    checks: pd.DataFrame,
    boot: pd.DataFrame,
    bench: pd.DataFrame,
    run_block: pd.DataFrame,
    workflow_present: bool,
) -> None:
    checks_md = checks.copy()
    checks_md["pass"] = checks_md["pass"].map(lambda value: "yes" if bool(value) else "no")
    guard_status = "present" if workflow_present else "missing"
    trad = bench[bench["method"] == "traditional median-first-four gate"].iloc[0]
    ml = bench[bench["method"] == "ML logistic honest raw summaries"].iloc[0]
    leak = bench[bench["method"] == "ML leakage sentinel with median_amp"].iloc[0]
    report = f"""# S00d: S00c selector-count guard in CI

Ticket `{TICKET_ID}` asked to put the S00c raw selector-count regression on the pre-merge path so semantic drift in the median-first-four and dynamic-range selectors blocks merges.

## Reproduction First
The first operation in this ticket-specific run scanned the raw B-stack ROOT files under `{config['raw_root_dir']}` and recomputed the S00c anchors from `HRDv` before any model benchmark:

{checks_md.to_markdown(index=False)}

The guard uses zero tolerance. Any nonzero delta in `median_first_four_selected`, `dynamic_range_selected`, `dynamic_only`, or `median_only` raises before report success.

## CI Wiring
- Guard script: `scripts/s00d_1781028640_1234_005956da_ci_premerge.py --guard-only`
- Workflow: `{config['ci_workflow']}` ({guard_status})
- Data path override for runners: `{config['raw_root_env']}`

The guard-only mode intentionally performs just the raw ROOT count scan and exact anchor comparison; it does not rely on ML to pass.

## Traditional And ML Cross-Check
For continuity with S00c, the ticket also reran the full S00c benchmark with this ticket id. Whole-run bootstrap intervals summarize run-to-run stability:

{boot.to_markdown(index=False)}

Held-out benchmark:

{bench[['method', 'accuracy', 'accuracy_ci_low', 'accuracy_ci_high', 'false_positive', 'false_negative', 'notes']].to_markdown(index=False)}

Held-out run-block accuracy intervals resample the two held-out runs as blocks:

{run_block.to_markdown(index=False)}

The traditional median-first-four gate exactly reproduces the anchor on held-out records: accuracy `{float(trad['accuracy']):.6f}` with false positives `{int(trad['false_positive'])}` and false negatives `{int(trad['false_negative'])}`. The honest ML logistic model reaches `{float(ml['accuracy']):.6f}` accuracy with CI `[{float(ml['accuracy_ci_low']):.6f}, {float(ml['accuracy_ci_high']):.6f}]`, but it is not used as the merge guard.

## Leakage Hunt
The deliberately leaky sentinel includes `median_amp`, a direct selector-rule feature, and reaches `{float(leak['accuracy']):.6f}` accuracy. That near-perfect result is treated as leakage evidence, not a valid generalization claim. The CI path therefore uses the deterministic raw-count guard only.
"""
    (out_dir / "REPORT.md").write_text(report, encoding="utf-8")


def run_guard(config: dict, write_outputs: bool = False) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    counts, inputs = scan_counts_only(config)
    checks = count_checks(counts, config)
    if write_outputs:
        out_dir = Path(config["output_dir"])
        out_dir.mkdir(parents=True, exist_ok=True)
        counts.to_csv(out_dir / "ci_guard_counts_by_run.csv", index=False)
        checks.to_csv(out_dir / "ci_guard_reproduction_match_table.csv", index=False)
        inputs.to_csv(out_dir / "input_sha256.csv", index=False)
    if not bool(checks["pass"].all()):
        raise SystemExit(f"S00d CI guard failed:\n{checks.to_string(index=False)}")
    return counts, checks, inputs


def run_study(config: dict) -> None:
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    guard_counts, guard_checks, guard_inputs = run_guard(config, write_outputs=True)

    s00c = import_s00c_module()
    counts, sample, inputs = s00c.scan_raw(config)
    checks = s00c.count_checks(counts, config)
    if not bool(checks["pass"].all()):
        raise SystemExit(f"S00d full S00c regression failed:\n{checks.to_string(index=False)}")

    boot = s00c.run_level_bootstrap(counts, config)
    cv, bench = s00c.benchmark_methods(sample, config)
    per_run_bench, run_block = heldout_run_block_benchmark(sample, config, cv)
    workflow_present = Path(config["ci_workflow"]).exists()

    counts.to_csv(out_dir / "counts_by_run.csv", index=False)
    checks.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    boot.to_csv(out_dir / "run_bootstrap_ci.csv", index=False)
    sample.to_csv(out_dir / "ml_sample.csv.gz", index=False, compression="gzip")
    cv.to_csv(out_dir / "ml_cv_scan.csv", index=False)
    bench.to_csv(out_dir / "heldout_benchmark.csv", index=False)
    per_run_bench.to_csv(out_dir / "heldout_per_run_benchmark.csv", index=False)
    run_block.to_csv(out_dir / "heldout_run_block_benchmark.csv", index=False)
    inputs.to_csv(out_dir / "full_study_input_sha256.csv", index=False)
    write_report(out_dir, config, checks, boot, bench, run_block, workflow_present)

    totals = counts[["events", "records", "median_first_four_selected", "dynamic_range_selected", "dynamic_only", "median_only"]].sum().to_dict()
    trad = bench[bench["method"] == "traditional median-first-four gate"].iloc[0]
    ml = bench[bench["method"] == "ML logistic honest raw summaries"].iloc[0]
    leaky = bench[bench["method"] == "ML leakage sentinel with median_amp"].iloc[0]
    result = {
        "study": config["study_id"],
        "ticket": TICKET_ID,
        "worker": config["worker"],
        "title": config["title"],
        "reproduced_raw_root_first": bool(guard_checks["pass"].all()),
        "ci_guard": {
            "command": config["guard_command"],
            "workflow": config["ci_workflow"],
            "workflow_present": workflow_present,
            "guard_only_passed": True,
            "anchors": {key: int(totals[key]) for key in config["expected_counts"]},
            "tolerance": 0,
        },
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
            "interpretation": "median_amp directly encodes the selector formula and is excluded from the honest ML method",
        },
        "heldout_run_block": run_block.to_dict(orient="records"),
        "input_sha256": "input_sha256.csv",
        "full_study_input_sha256": "full_study_input_sha256.csv",
        "git_commit": git_commit(),
        "next_tickets": [],
        "follow_up_ticket_appended": False,
        "follow_up_ticket_reason": "Skipped: this ticket is CI wiring for an already completed S00c follow-up, and no non-duplicate next infrastructure study was identified.",
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    manifest = {
        "study": config["study_id"],
        "ticket": TICKET_ID,
        "worker": config["worker"],
        "commands": [config["guard_command"], config["study_command"]],
        "config": str(CONFIG_PATH),
        "source_config": config["source_config"],
        "ci_workflow": config["ci_workflow"],
        "inputs": guard_inputs.to_dict(orient="records"),
        "outputs_sha256": output_hashes(out_dir),
        "random_seed": int(config["ml"]["random_seed"]),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ticket": TICKET_ID, "guard": "passed", "totals": totals}, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--guard-only", action="store_true", help="Run only the raw ROOT anchor guard for CI/pre-merge.")
    mode.add_argument("--study", action="store_true", help="Run the ticket report path, including traditional and ML checks.")
    args = parser.parse_args()

    config = load_config()
    if args.guard_only:
        run_guard(config, write_outputs=False)
        print(json.dumps({"ticket": TICKET_ID, "guard": "passed"}, indent=2))
    else:
        run_study(config)


if __name__ == "__main__":
    main()
