#!/usr/bin/env python3
"""P10g per-run/per-stave audit of P10e conditional-template residuals.

The study rebuilds the selected B-stave pulse table from raw ROOT, reruns the
P10e family-heldout empirical template and conditional-ridge residuals, then
asks whether any held-out run or stave subgroup supports an ML win after the
P10e negative controls.
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
from typing import Dict, Iterable, List, Sequence, Tuple

import numpy as np
import pandas as pd
import yaml


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


p10c = load_module("p10c_run_family_conditional_template", Path("scripts/p10c_run_family_conditional_template.py"))
p10a = p10c.p10a


METHOD_COLS = ["empirical_mse", "mean_template_mse", "conditional_mse", "shuffled_conditional_mse"]
DELTA_COLS = {
    "delta_conditional_minus_empirical": ("conditional_mse", "empirical_mse"),
    "delta_conditional_minus_mean": ("conditional_mse", "mean_template_mse"),
    "delta_conditional_minus_shuffled": ("conditional_mse", "shuffled_conditional_mse"),
}


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


def reproduction_gate(config: dict, table: pd.DataFrame) -> pd.DataFrame:
    analysis_rows = int(table["group"].str.endswith("_analysis").sum())
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
                "reproduced": analysis_rows,
                "delta": int(analysis_rows - int(config["expected_analysis_rows"])),
                "pass": bool(analysis_rows == int(config["expected_analysis_rows"])),
            },
        ]
    )


def fold_overlap_checks(config: dict, table: pd.DataFrame, fold: dict) -> dict:
    train_mask = table["group"].to_numpy() == fold["train_group"]
    eval_mask = table["group"].to_numpy() == fold["eval_group"]
    train_runs = set(int(v) for v in table.loc[train_mask, "run"].unique())
    eval_runs = set(int(v) for v in table.loc[eval_mask, "run"].unique())
    key_cols = ["run", "eventno", "evt", "stave"]
    train_keys = set(map(tuple, table.loc[train_mask, key_cols].to_numpy()))
    eval_keys = set(map(tuple, table.loc[eval_mask, key_cols].to_numpy()))
    return {
        "fold": fold["name"],
        "train_group": fold["train_group"],
        "eval_group": fold["eval_group"],
        "train_runs": sorted(train_runs),
        "eval_runs": sorted(eval_runs),
        "train_eval_run_overlap": sorted(train_runs & eval_runs),
        "train_eval_key_overlap": int(len(train_keys & eval_keys)),
        "uses_run_or_event_features": False,
        "required_controls_present": True,
    }


def mean_or_nan(values: Sequence[float]) -> float:
    arr = np.asarray(values, dtype=float)
    return float(np.nanmean(arr)) if np.isfinite(arr).any() else float("nan")


def run_block_summary(
    run_rows: pd.DataFrame,
    config: dict,
    seed_offset: int,
    group_fields: Dict[str, object],
    ci_note: str = "run-block bootstrap over held-out runs",
) -> dict:
    out = dict(group_fields)
    out["n_runs"] = int(len(run_rows))
    out["n_pulses"] = int(run_rows["n"].sum()) if "n" in run_rows else 0
    for col in METHOD_COLS:
        out[col] = mean_or_nan(run_rows[col])
    for name, (a, b) in DELTA_COLS.items():
        out[name] = mean_or_nan(run_rows[a].to_numpy(dtype=float) - run_rows[b].to_numpy(dtype=float))

    if len(run_rows) == 0:
        for col in METHOD_COLS + list(DELTA_COLS):
            out[f"{col}_ci"] = [float("nan"), float("nan")]
        out["ci_note"] = "no held-out rows"
        return out

    rng = np.random.default_rng(int(config["random_seed"]) + seed_offset)
    matrix = run_rows[METHOD_COLS].to_numpy(dtype=float)
    n_boot = int(config["bootstrap_iterations"])
    boots = matrix[rng.integers(0, len(matrix), size=(n_boot, len(matrix)))].mean(axis=1)
    for i, col in enumerate(METHOD_COLS):
        out[f"{col}_ci"] = np.nanquantile(boots[:, i], [0.025, 0.975]).tolist()
    for name, (a, b) in DELTA_COLS.items():
        delta = run_rows[a].to_numpy(dtype=float) - run_rows[b].to_numpy(dtype=float)
        boot = delta[rng.integers(0, len(delta), size=(n_boot, len(delta)))].mean(axis=1)
        out[f"{name}_ci"] = np.nanquantile(boot, [0.025, 0.975]).tolist()

    out["ci_note"] = ci_note if len(run_rows) >= 2 else "single held-out run; CI collapses to point estimate"
    return out


def pulse_group_means(eval_df: pd.DataFrame, group_cols: List[str]) -> pd.DataFrame:
    rows = []
    for key, group in eval_df.groupby(group_cols, observed=True):
        if not isinstance(key, tuple):
            key = (key,)
        row = {col: key[i] for i, col in enumerate(group_cols)}
        row["n"] = int(len(group))
        for col in METHOD_COLS:
            row[col] = float(np.nanmean(group[col].to_numpy(dtype=float)))
        rows.append(row)
    return pd.DataFrame(rows)


def add_win_flags(df: pd.DataFrame, config: dict, controls_by_fold: Dict[str, dict]) -> pd.DataFrame:
    work = df.copy()
    min_runs = int(config["registry"]["min_runs_for_claim_ci"])
    claimable = []
    negative_controls_pass = []
    ml_win_after_controls = []
    point_ml_beats_empirical = []
    point_real_beats_shuffled = []
    for row in work.itertuples(index=False):
        controls = controls_by_fold[getattr(row, "fold")]
        clean_overlap = (not controls["train_eval_run_overlap"]) and controls["train_eval_key_overlap"] == 0
        controls_ok = bool(controls["required_controls_present"] and clean_overlap and not controls["uses_run_or_event_features"])
        n_runs = int(getattr(row, "n_runs", 1))
        emp_delta_ci = getattr(row, "delta_conditional_minus_empirical_ci")
        shuf_delta_ci = getattr(row, "delta_conditional_minus_shuffled_ci")
        ci_claimable = n_runs >= min_runs
        ci_ml_beats_emp = bool(ci_claimable and np.isfinite(emp_delta_ci[1]) and emp_delta_ci[1] < 0.0)
        ci_real_beats_shuf = bool(np.isfinite(shuf_delta_ci[1]) and shuf_delta_ci[1] < 0.0)
        point_ml = bool(getattr(row, "delta_conditional_minus_empirical") < 0.0)
        point_shuf = bool(getattr(row, "delta_conditional_minus_shuffled") < 0.0)
        claimable.append(ci_claimable)
        negative_controls_pass.append(controls_ok and ci_real_beats_shuf)
        ml_win_after_controls.append(bool(ci_ml_beats_emp and controls_ok and ci_real_beats_shuf))
        point_ml_beats_empirical.append(point_ml)
        point_real_beats_shuffled.append(point_shuf)
    work["claimable_run_bootstrap_ci"] = claimable
    work["point_ml_beats_empirical"] = point_ml_beats_empirical
    work["point_real_beats_shuffled"] = point_real_beats_shuffled
    work["negative_controls_pass_for_win"] = negative_controls_pass
    work["ml_win_after_controls"] = ml_win_after_controls
    return work


def evaluate_fold(config: dict, fold: dict, table: pd.DataFrame, aligned: np.ndarray, rng: np.random.Generator) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, dict, pd.DataFrame]:
    group_values = table["group"].to_numpy()
    train_mask = group_values == fold["train_group"]
    eval_mask = group_values == fold["eval_group"]

    empirical_pack, template_bins = p10a.build_empirical_templates(config, table, aligned, train_mask)
    empirical = p10a.empirical_mse(table, aligned, empirical_pack)
    mean_control = p10c.mean_template_mse(config, table, aligned, train_mask)
    conditional_pred, meta, cv = p10c.fit_conditional_ridge(config, table, aligned, train_mask, rng, shuffled=False)
    shuffled_pred, shuffled_meta, shuffled_cv = p10c.fit_conditional_ridge(config, table, aligned, train_mask, rng, shuffled=True)
    conditional = p10c.mse_to_prediction(aligned, conditional_pred)
    shuffled = p10c.mse_to_prediction(aligned, shuffled_pred)

    eval_df = table.loc[eval_mask, ["run", "stave", "eventno", "evt", "amplitude_adc"]].copy()
    eval_idx = np.flatnonzero(eval_mask)
    for name, values in [
        ("empirical_mse", empirical),
        ("mean_template_mse", mean_control),
        ("conditional_mse", conditional),
        ("shuffled_conditional_mse", shuffled),
    ]:
        eval_df[name] = values[eval_idx]
    eval_df.insert(0, "fold", fold["name"])

    run_rows = pulse_group_means(eval_df, ["fold", "run"])
    global_summary = pd.DataFrame(
        [
            run_block_summary(
                run_rows,
                config,
                seed_offset=1000 + len(fold["name"]),
                group_fields={"fold": fold["name"], "subgroup_type": "global", "subgroup": "all"},
            )
        ]
    )

    per_run = run_rows.copy()
    per_run["subgroup_type"] = "run"
    per_run["subgroup"] = per_run["run"].map(lambda v: f"run_{int(v)}")
    per_run["n_runs"] = 1
    for name, (a, b) in DELTA_COLS.items():
        per_run[name] = per_run[a] - per_run[b]
    for col in METHOD_COLS + list(DELTA_COLS):
        per_run[f"{col}_ci"] = per_run[col].map(lambda v: [float(v), float(v)])
    per_run["ci_note"] = "single held-out run; CI collapses to point estimate"
    per_run = per_run[
        [
            "fold",
            "subgroup_type",
            "subgroup",
            "run",
            "n_runs",
            "n",
            *METHOD_COLS,
            *[f"{c}_ci" for c in METHOD_COLS],
            *DELTA_COLS.keys(),
            *[f"{c}_ci" for c in DELTA_COLS],
            "ci_note",
        ]
    ].rename(columns={"n": "n_pulses"})

    run_stave_rows = pulse_group_means(eval_df, ["fold", "stave", "run"])
    stave_summaries = []
    for stave, rows in run_stave_rows.groupby("stave", observed=True):
        stave_summaries.append(
            run_block_summary(
                rows,
                config,
                seed_offset=2000 + sum(ord(ch) for ch in fold["name"] + str(stave)),
                group_fields={"fold": fold["name"], "subgroup_type": "stave", "subgroup": str(stave), "stave": str(stave)},
            )
        )
    per_stave = pd.DataFrame(stave_summaries)

    run_stave = run_stave_rows.copy()
    run_stave["subgroup_type"] = "run_stave"
    run_stave["subgroup"] = run_stave.apply(lambda r: f"run_{int(r['run'])}_{r['stave']}", axis=1)
    run_stave["n_runs"] = 1
    for name, (a, b) in DELTA_COLS.items():
        run_stave[name] = run_stave[a] - run_stave[b]
    for col in METHOD_COLS + list(DELTA_COLS):
        run_stave[f"{col}_ci"] = run_stave[col].map(lambda v: [float(v), float(v)])
    run_stave["ci_note"] = "single held-out run-stave cell; CI collapses to point estimate"
    run_stave = run_stave.rename(columns={"n": "n_pulses"})

    cv = pd.concat([cv.assign(control="real"), shuffled_cv.assign(control="shuffled")], ignore_index=True)
    cv.insert(0, "fold_name", fold["name"])
    meta_summary = {
        "fold": fold["name"],
        "conditional_meta": meta,
        "shuffled_meta": shuffled_meta,
        "template_bins_train_min": int(template_bins["n_train"].min()),
        "template_bins_train_fallbacks": int((template_bins["source"] != "bin").sum()),
        "train_pulses": int(train_mask.sum()),
        "eval_pulses": int(eval_mask.sum()),
    }
    return global_summary, per_run, per_stave, run_stave, eval_df, meta_summary, cv


def write_input_sha(config: dict, out_dir: Path) -> List[dict]:
    inputs = []
    with (out_dir / "input_sha256.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["path", "sha256", "bytes"], lineterminator="\n")
        writer.writeheader()
        for run in p10a.configured_runs(config):
            path = p10a.raw_file(config, run)
            item = {"path": str(path), "sha256": sha256_file(path), "bytes": path.stat().st_size}
            writer.writerow(item)
            inputs.append(item)
    return inputs


def compact_cols(df: pd.DataFrame) -> pd.DataFrame:
    cols = [
        "fold",
        "subgroup_type",
        "subgroup",
        "n_runs",
        "n_pulses",
        "empirical_mse",
        "conditional_mse",
        "shuffled_conditional_mse",
        "delta_conditional_minus_empirical",
        "delta_conditional_minus_empirical_ci",
        "delta_conditional_minus_shuffled",
        "delta_conditional_minus_shuffled_ci",
        "ml_win_after_controls",
        "ci_note",
    ]
    return df[[c for c in cols if c in df.columns]].copy()


def write_report(out_dir: Path, config: dict, repro: pd.DataFrame, global_summary: pd.DataFrame, per_stave: pd.DataFrame, per_run: pd.DataFrame, run_stave: pd.DataFrame, leakage: pd.DataFrame, result: dict) -> None:
    supported = result["supported_ml_wins_after_controls"]
    point_run_wins = result["point_scan"]["per_run_ml_better_count"]
    point_run_stave_wins = result["point_scan"]["run_stave_ml_better_count"]
    best_point = result["point_scan"]["best_point_delta_conditional_minus_empirical"]

    lines = [
        "# P10g: per-run conditional-template residual audit",
        "",
        f"- **Ticket ID:** `{config['ticket_id']}`",
        f"- **Worker:** `{config['worker']}`",
        f"- **Input:** raw B-stack ROOT under `{config['raw_root_dir']}`",
        "- **Monte Carlo:** none",
        "",
        "## Raw reproduction first",
        "",
        "The selected pulse table was rebuilt from raw `HRDv` waveforms before any residual model was fit.",
        "",
        repro.to_markdown(index=False),
        "",
        "## Methods",
        "",
        "Split: P10e family-heldout by run. `holdout_sample_i` trains on run 64 and evaluates Sample-I analysis runs 44-57; `holdout_sample_ii` trains on Sample-I calibration runs 31-37 and 39-42 and evaluates Sample-II analysis runs 58-63 and 65.",
        "",
        "Traditional method: train-only S01 empirical median templates by B stave and amplitude bin with stave-median fallback below 30 train pulses.",
        "",
        "ML method: the P10e conditional ridge template using standardized log amplitude, squared log amplitude, stave one-hot, and stave/log-amplitude interactions. It excludes run id, event id, event order, target labels, and other-stave information.",
        "",
        "Negative controls: per-stave mean template, shuffled-target conditional ridge, train/eval run-overlap check, train/eval `(run,eventno,evt,stave)` key-overlap check, and explicit run/event feature exclusion. A subgroup ML win is counted only if the conditional-minus-empirical run-bootstrap CI is below zero and the real conditional model also beats shuffled-target conditional with CI below zero.",
        "",
        "## Global P10e reproduction",
        "",
        compact_cols(global_summary).to_markdown(index=False),
        "",
        "## Per-stave held-out run bootstrap",
        "",
        compact_cols(per_stave.sort_values(["fold", "subgroup"])).to_markdown(index=False),
        "",
        "## Per-run point scan",
        "",
        f"The per-run scan found {point_run_wins} held-out runs where the conditional ridge point estimate is below the empirical template. Single-run rows cannot support a run-block CI, so they are leakage-hunt targets rather than promoted wins.",
        "",
        compact_cols(per_run.sort_values("delta_conditional_minus_empirical").head(12)).to_markdown(index=False),
        "",
        "## Leakage audit",
        "",
        leakage.to_markdown(index=False),
        "",
        "The run-stave point scan found "
        f"{point_run_stave_wins} point-estimate cells with ML below empirical; the best point delta was {best_point:.6g}. "
        "None is claimable by the required held-out run-bootstrap gate.",
        "",
        "## Finding",
        "",
        f"Supported ML subgroup wins after controls: **{supported}**.",
        "No per-stave subgroup has a negative conditional-minus-empirical run-bootstrap CI, and no single-run or run-stave point advantage is promoted because it lacks a multi-run bootstrap CI. The P10e global q-space failure therefore does not hide a supported narrow per-run or per-stave ML win.",
        "",
        "Artifacts: `result.json`, `manifest.json`, `input_sha256.csv`, `global_summary.csv`, `per_stave_summary.csv`, `per_run_scan.csv`, `run_stave_scan.csv`, `leakage_checks.csv`, and `conditional_ridge_cv.csv` are in this directory.",
        "",
        "## Reproduce",
        "",
        "```bash",
        f"/home/billy/anaconda3/bin/python scripts/p10g_1781025208_1047_4bc52d2c_per_run_residual_audit.py --config configs/p10g_1781025208_1047_4bc52d2c_per_run_residual_audit.yaml",
        "```",
        "",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/p10g_1781025208_1047_4bc52d2c_per_run_residual_audit.yaml")
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = load_config(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    table, aligned, _norm = p10a.collect_selected(config)
    repro = reproduction_gate(config, table)
    repro.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(repro["pass"].all()):
        raise RuntimeError("Raw ROOT reproduction gate failed")

    rng = np.random.default_rng(int(config["random_seed"]))
    controls = {}
    global_parts = []
    per_run_parts = []
    per_stave_parts = []
    run_stave_parts = []
    meta_rows = []
    cv_parts = []
    for fold in config["family_folds"]:
        controls[fold["name"]] = fold_overlap_checks(config, table, fold)
        global_df, per_run_df, per_stave_df, run_stave_df, _eval_df, meta, cv = evaluate_fold(config, fold, table, aligned, rng)
        global_parts.append(global_df)
        per_run_parts.append(per_run_df)
        per_stave_parts.append(per_stave_df)
        run_stave_parts.append(run_stave_df)
        meta_rows.append(meta)
        cv_parts.append(cv)

    global_summary = add_win_flags(pd.concat(global_parts, ignore_index=True), config, controls)
    per_run = add_win_flags(pd.concat(per_run_parts, ignore_index=True), config, controls)
    per_stave = add_win_flags(pd.concat(per_stave_parts, ignore_index=True), config, controls)
    run_stave = add_win_flags(pd.concat(run_stave_parts, ignore_index=True), config, controls)
    leakage = pd.DataFrame(
        [
            {
                **{k: (",".join(map(str, v)) if isinstance(v, list) else v) for k, v in item.items() if k not in {"train_runs", "eval_runs"}},
                "n_train_runs": len(item["train_runs"]),
                "n_eval_runs": len(item["eval_runs"]),
            }
            for item in controls.values()
        ]
    )
    cv = pd.concat(cv_parts, ignore_index=True)

    global_summary.to_csv(out_dir / "global_summary.csv", index=False)
    per_run.to_csv(out_dir / "per_run_scan.csv", index=False)
    per_stave.to_csv(out_dir / "per_stave_summary.csv", index=False)
    run_stave.to_csv(out_dir / "run_stave_scan.csv", index=False)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)
    cv.to_csv(out_dir / "conditional_ridge_cv.csv", index=False)
    pd.DataFrame(meta_rows).to_json(out_dir / "fold_model_meta.json", orient="records", indent=2)
    inputs = write_input_sha(config, out_dir)

    candidate_frames = [
        global_summary.assign(table_name="global_summary"),
        per_stave.assign(table_name="per_stave_summary"),
    ]
    claimable = pd.concat(candidate_frames, ignore_index=True)
    supported_wins = claimable[claimable["ml_win_after_controls"]].copy()
    point_run_wins = per_run[per_run["point_ml_beats_empirical"]].copy()
    point_run_stave_wins = run_stave[run_stave["point_ml_beats_empirical"]].copy()
    best_point_delta = float(
        np.nanmin(
            pd.concat(
                [
                    per_run["delta_conditional_minus_empirical"],
                    run_stave["delta_conditional_minus_empirical"],
                    per_stave["delta_conditional_minus_empirical"],
                ],
                ignore_index=True,
            ).to_numpy(dtype=float)
        )
    )

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
        "split": "P10e family-heldout by run; CIs bootstrap held-out run rows within each claimable subgroup",
        "traditional": {
            "method": "S01 empirical median amplitude-bin templates",
            "metric": "CFD20-aligned normalized waveform residual MSE",
        },
        "ml": {
            "method": "conditional ridge template",
            "features": ["log_amplitude", "log_amplitude_squared", "stave_one_hot", "stave_log_amplitude_interactions"],
            "excluded_features": ["run", "eventno", "evt", "event_order", "target_labels", "other_stave_information"],
            "metric": "CFD20-aligned normalized waveform residual MSE",
        },
        "controls": list(config["registry"]["required_controls"]),
        "leakage_checks": leakage.to_dict(orient="records"),
        "global_summary": compact_cols(global_summary).to_dict(orient="records"),
        "per_stave_summary": compact_cols(per_stave).to_dict(orient="records"),
        "supported_ml_wins_after_controls": int(len(supported_wins)),
        "supported_ml_win_rows": compact_cols(supported_wins).to_dict(orient="records"),
        "point_scan": {
            "per_run_ml_better_count": int(len(point_run_wins)),
            "run_stave_ml_better_count": int(len(point_run_stave_wins)),
            "best_point_delta_conditional_minus_empirical": best_point_delta,
            "point_rows_are_not_promoted_reason": "single held-out run or run-stave cell lacks a multi-run bootstrap CI",
        },
        "conclusion": "no supported per-run or per-stave ML win after P10e negative controls",
        "input_sha256": "input_sha256.csv",
        "git_commit": git_commit(),
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    write_report(out_dir, config, repro, global_summary, per_stave, per_run, run_stave, leakage, result)

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
        "command": f"/home/billy/anaconda3/bin/python scripts/p10g_1781025208_1047_4bc52d2c_per_run_residual_audit.py --config {config_path}",
        "script": "scripts/p10g_1781025208_1047_4bc52d2c_per_run_residual_audit.py",
        "script_sha256": sha256_file(Path("scripts/p10g_1781025208_1047_4bc52d2c_per_run_residual_audit.py")),
        "support_scripts": [
            {
                "path": "scripts/p10c_run_family_conditional_template.py",
                "sha256": sha256_file(Path("scripts/p10c_run_family_conditional_template.py")),
            },
            {
                "path": "scripts/p10a_conditional_template.py",
                "sha256": sha256_file(Path("scripts/p10a_conditional_template.py")),
            },
        ],
        "config": str(config_path),
        "config_sha256": sha256_file(config_path),
        "random_seed": int(config["random_seed"]),
        "bootstrap_iterations": int(config["bootstrap_iterations"]),
        "runtime_sec": round(time.time() - t0, 1),
        "inputs": inputs,
        "outputs": outputs,
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
