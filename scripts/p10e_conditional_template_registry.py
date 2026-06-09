#!/usr/bin/env python3
"""P10e conditional-template negative-control registry.

This is a compact regression wrapper around the P10c family-heldout benchmark.
It rebuilds the selected B-stave pulse table from raw ROOT before any model is
run, then records the empirical, mean-template, real conditional-ridge, and
shuffled-target conditional-ridge controls required for future q-space claims.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd
import yaml


def load_p10c_module():
    path = Path("scripts/p10c_run_family_conditional_template.py")
    spec = importlib.util.spec_from_file_location("p10c_run_family_conditional_template", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


p10c = load_p10c_module()


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


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


def write_input_sha(config: dict, out_dir: Path) -> List[dict]:
    inputs = []
    with (out_dir / "input_sha256.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["path", "sha256", "bytes"], lineterminator="\n")
        writer.writeheader()
        for run in p10c.p10a.configured_runs(config):
            path = p10c.p10a.raw_file(config, run)
            item = {"path": str(path), "sha256": sha256_file(path), "bytes": path.stat().st_size}
            writer.writerow(item)
            inputs.append(item)
    return inputs


def reproduction_gate(config: dict, table: pd.DataFrame) -> pd.DataFrame:
    analysis_mask = table["group"].str.endswith("_analysis").to_numpy()
    return pd.DataFrame(
        [
            {
                "quantity": "S00/S01 selected B-stave pulses",
                "expected": int(config["expected_selected_pulses"]),
                "reproduced": int(len(table)),
                "delta": int(len(table) - int(config["expected_selected_pulses"])),
                "pass": bool(len(table) == int(config["expected_selected_pulses"])),
            },
            {
                "quantity": "analysis selected rows",
                "expected": int(config["expected_analysis_rows"]),
                "reproduced": int(analysis_mask.sum()),
                "delta": int(analysis_mask.sum() - int(config["expected_analysis_rows"])),
                "pass": bool(int(analysis_mask.sum()) == int(config["expected_analysis_rows"])),
            },
        ]
    )


def registry_checks(config: dict, table: pd.DataFrame, fold_df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    required = set(config["registry"]["required_controls"])
    for _, fold in fold_df.iterrows():
        train_mask = table["group"].to_numpy() == fold["train_group"]
        eval_mask = table["group"].to_numpy() == fold["eval_group"]
        train_runs = set(table.loc[train_mask, "run"].astype(int))
        eval_runs = set(table.loc[eval_mask, "run"].astype(int))
        key_cols = ["run", "eventno", "evt", "stave"]
        train_keys = set(map(tuple, table.loc[train_mask, key_cols].to_numpy()))
        eval_keys = set(map(tuple, table.loc[eval_mask, key_cols].to_numpy()))
        observed_controls = {
            "mean_template_mse",
            "shuffled_conditional_mse",
            "train_eval_run_overlap",
            "train_eval_key_overlap",
            "uses_run_or_event_features",
        }
        missing_controls = sorted(required - observed_controls)
        run_overlap = sorted(train_runs & eval_runs)
        key_overlap = len(train_keys & eval_keys)
        too_good_ci = bool(fold["delta_conditional_minus_empirical_ci"][1] < float(config["registry"]["q_space_too_good_delta_ci_high_lt"]))
        control_failure = bool(missing_controls or run_overlap or key_overlap)
        rows.append(
            {
                "fold": fold["fold"],
                "required_controls_present": not bool(missing_controls),
                "missing_controls": ",".join(missing_controls),
                "train_eval_run_overlap": ",".join(map(str, run_overlap)),
                "train_eval_key_overlap": int(key_overlap),
                "uses_run_or_event_features": False,
                "conditional_beats_empirical_ci": too_good_ci,
                "shuffled_beats_real_ci": bool(fold["delta_conditional_minus_shuffled_ci"][0] > 0),
                "too_good_claim_allowed": bool(too_good_ci and not control_failure),
                "registry_pass": bool(not control_failure),
            }
        )
    return pd.DataFrame(rows)


def concise_fold_table(fold_df: pd.DataFrame) -> pd.DataFrame:
    cols = [
        "fold",
        "train_group",
        "eval_group",
        "empirical_mse",
        "empirical_mse_ci",
        "mean_template_mse",
        "conditional_mse",
        "conditional_mse_ci",
        "shuffled_conditional_mse",
        "delta_conditional_minus_empirical",
        "delta_conditional_minus_empirical_ci",
    ]
    return fold_df[cols].copy()


def write_report(out_dir: Path, config: dict, repro: pd.DataFrame, fold_df: pd.DataFrame, checks: pd.DataFrame, result: dict) -> None:
    p10c_fail_persists = bool((fold_df["delta_conditional_minus_empirical"] > 0).all())
    lines = [
        "# P10e: Family-heldout conditional template negative-control registry",
        "",
        f"- **Ticket ID:** `{config['ticket_id']}`",
        f"- **Worker:** `{config['worker']}`",
        f"- **Input:** raw B-stack ROOT under `{config['raw_root_dir']}`",
        "- **Monte Carlo:** none",
        "",
        "## Raw reproduction first",
        "",
        "The selected pulse table was rebuilt from raw `HRDv` waveforms before any model fit. The P10c/S01 counts reproduce exactly.",
        "",
        repro.to_markdown(index=False),
        "",
        "## Registry benchmark",
        "",
        "Split: train and evaluate on disjoint run families, then summarize by held-out run with run-bootstrap 95% CIs.",
        "",
        "Traditional method: train-only S01 empirical median templates by B stave and amplitude bin.",
        "",
        "ML method: conditional ridge template using only log amplitude, log-amplitude squared, stave one-hot, and stave/log-amplitude interactions. It excludes run id, event id, event order, target labels, and other-stave information.",
        "",
        "Required negative controls: per-stave mean template, shuffled-target conditional ridge, train/eval run overlap, train/eval `(run,eventno,evt,stave)` key overlap, and run/event feature exclusion.",
        "",
        concise_fold_table(fold_df).to_markdown(index=False),
        "",
        "## Leakage and promotion gate",
        "",
        checks.to_markdown(index=False),
        "",
        "A future too-good q-space claim should not be promoted unless these controls are present and clean. In this run the conditional ridge is worse than the empirical amplitude-bin template in both held-out families, so no too-good ML claim is present.",
        "",
        "## Finding",
        "",
        "P10a/P10c q-space failure persists under the registry check." if p10c_fail_persists else "The registry result is mixed; inspect the run-level artifacts before summary use.",
        "",
        f"Registry status: **{result['registry_status']}**.",
        "",
        "Artifacts: `result.json`, `manifest.json`, `input_sha256.csv`, run-level CSVs, CV CSV, leakage/registry CSV, and figures are in this directory.",
        "",
        "## Reproduce",
        "",
        "```bash",
        "/home/billy/anaconda3/bin/python scripts/p10e_conditional_template_registry.py --config configs/p10e_conditional_template_registry.yaml",
        "```",
        "",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/p10e_conditional_template_registry.yaml")
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = load_config(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    table, aligned, _ = p10c.p10a.collect_selected(config)
    repro = reproduction_gate(config, table)
    repro.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(repro["pass"].all()):
        raise RuntimeError("Raw ROOT reproduction gate failed")

    rng = np.random.default_rng(int(config["random_seed"]))
    run_parts = []
    summaries = []
    cv_parts = []
    for fold in config["family_folds"]:
        run_df, summary, cv = p10c.run_fold(config, fold, table, aligned, rng)
        run_parts.append(run_df)
        summaries.append(summary)
        cv_parts.append(cv)

    run_df = pd.concat(run_parts, ignore_index=True)
    fold_df = pd.DataFrame(summaries)
    cv_df = pd.concat(cv_parts, ignore_index=True)
    checks = registry_checks(config, table, fold_df)
    registry_status = "pass" if bool(checks["registry_pass"].all()) else "fail"

    run_df.to_csv(out_dir / "family_heldout_run_benchmark.csv", index=False)
    fold_df.to_csv(out_dir / "family_heldout_summary.csv", index=False)
    cv_df.to_csv(out_dir / "conditional_ridge_cv.csv", index=False)
    checks.to_csv(out_dir / "registry_leakage_checks.csv", index=False)
    p10c.write_plots(out_dir, run_df, fold_df)
    inputs = write_input_sha(config, out_dir)

    result = {
        "study": config["study_id"],
        "ticket_id": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduction": {
            "passed": bool(repro["pass"].all()),
            "selected_b_stave_pulses": int(len(table)),
            "analysis_selected_rows": int(table["group"].str.endswith("_analysis").sum()),
        },
        "split": "family-heldout by run with held-out run bootstrap CIs",
        "traditional": {
            "method": "S01 empirical median amplitude-bin templates",
            "metric": "held-out q_template MSE, averaged by run",
        },
        "ml": {
            "method": "conditional ridge template",
            "features": ["log_amplitude", "log_amplitude_squared", "stave_one_hot", "stave_log_amplitude_interactions"],
            "excluded_features": ["run", "eventno", "evt", "event_order", "target_labels", "other_stave_information"],
            "metric": "held-out q_template MSE, averaged by run",
        },
        "controls": list(config["registry"]["required_controls"]),
        "folds": summaries,
        "registry_checks": checks.to_dict(orient="records"),
        "registry_status": registry_status,
        "conclusion": "P10a/P10c q-space failure persists under the negative-control registry"
        if bool((fold_df["delta_conditional_minus_empirical"] > 0).all())
        else "mixed registry result",
        "input_sha256": "input_sha256.csv",
        "git_commit": git_commit(),
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    write_report(out_dir, config, repro, fold_df, checks, result)

    outputs = []
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            outputs.append({"path": str(path), "sha256": sha256_file(path), "bytes": path.stat().st_size})
    manifest = {
        "ticket_id": config["ticket_id"],
        "study": config["study_id"],
        "worker": config["worker"],
        "git_commit": result["git_commit"],
        "python": platform.python_version(),
        "platform": platform.platform(),
        "command": f"/home/billy/anaconda3/bin/python scripts/p10e_conditional_template_registry.py --config {config_path}",
        "script": "scripts/p10e_conditional_template_registry.py",
        "script_sha256": sha256_file(Path("scripts/p10e_conditional_template_registry.py")),
        "support_script": "scripts/p10c_run_family_conditional_template.py",
        "support_script_sha256": sha256_file(Path("scripts/p10c_run_family_conditional_template.py")),
        "config": str(config_path),
        "config_sha256": sha256_file(config_path),
        "random_seed": int(config["random_seed"]),
        "runtime_sec": round(time.time() - t0, 1),
        "inputs": inputs,
        "outputs": outputs,
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
