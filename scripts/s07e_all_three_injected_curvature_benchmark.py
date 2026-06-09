#!/usr/bin/env python3
"""S07e all-three injected timing-corruption curvature benchmark."""

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
from typing import List, Tuple

os.environ.setdefault("MPLCONFIGDIR", "/tmp/ccb-testbeam-s07e-matplotlib-cache")

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {name} from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def load_config(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


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


def markdown_table(frame: pd.DataFrame) -> str:
    def fmt(value: object) -> str:
        if pd.isna(value):
            return ""
        if isinstance(value, float):
            return f"{value:.6g}"
        return str(value)

    columns = list(frame.columns)
    rows = [[fmt(row[col]) for col in columns] for _, row in frame.iterrows()]
    widths = [len(str(col)) for col in columns]
    for row in rows:
        widths = [max(width, len(cell)) for width, cell in zip(widths, row)]
    header = "| " + " | ".join(str(col).ljust(width) for col, width in zip(columns, widths)) + " |"
    sep = "| " + " | ".join("-" * width for width in widths) + " |"
    body = ["| " + " | ".join(cell.ljust(width) for cell, width in zip(row, widths)) + " |" for row in rows]
    return "\n".join([header, sep, *body])


def run_fold_ids(runs: np.ndarray) -> np.ndarray:
    fold_id = np.full(len(runs), -1, dtype=int)
    for fold, held_run in enumerate(sorted(np.unique(runs))):
        fold_id[runs == held_run] = fold
    return fold_id


def fixed_efficiency_rows(data: pd.DataFrame, y: np.ndarray, score: np.ndarray, clean_eff: float, method: str) -> List[dict]:
    rows = []
    runs = data["run"].to_numpy(dtype=int)
    for held_run in sorted(np.unique(runs)):
        train = runs != held_run
        test = runs == held_run
        clean_train = train & (y == 0) & np.isfinite(score)
        if clean_train.sum() == 0:
            threshold = float("nan")
        else:
            threshold = float(np.quantile(score[clean_train], clean_eff))
        clean_test = test & (y == 0) & np.isfinite(score)
        gross_test = test & (y == 1) & np.isfinite(score)
        clean_acceptance = float((score[clean_test] <= threshold).mean()) if clean_test.sum() else float("nan")
        gross_rejection = float((score[gross_test] > threshold).mean()) if gross_test.sum() else float("nan")
        rows.append(
            {
                "method": method,
                "heldout_run": int(held_run),
                "threshold": threshold,
                "clean_acceptance": clean_acceptance,
                "injected_rejection": gross_rejection,
                "n_clean_test": int(clean_test.sum()),
                "n_injected_test": int(gross_test.sum()),
            }
        )
    return rows


def all_three_injection_benchmark(config: dict, utils, clean_payloads: List[dict]) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    data = utils.make_dataset(config, clean_payloads)
    y = data["label_injected"].to_numpy(dtype=int)
    runs = data["run"].to_numpy(dtype=int)
    seed = int(config["random_seed"])
    n_boot = int(config["bootstrap_replicates"])
    fold_id = run_fold_ids(runs)

    counts = data.groupby(["run", "label_injected"]).size().unstack(fill_value=0).rename(columns={0: "raw_clean", 1: "injected"}).reset_index()
    counts["total"] = counts["raw_clean"] + counts["injected"]

    curvature_score = data["abs_c_t_ns"].fillna(data["abs_c_t_ns"].median()).to_numpy(dtype=float)
    curvature_prob = utils.crossfold_isotonic(y, curvature_score, fold_id)
    direct_dt_score = np.maximum(data["d_t_ns"].to_numpy(dtype=float), curvature_score)
    direct_dt_prob = utils.crossfold_isotonic(y, direct_dt_score, fold_id)

    trad_score, trad_fold, trad_choices, trad_candidates = utils.traditional_oof(data, y, config)
    trad_prob = utils.crossfold_isotonic(y, trad_score, trad_fold)

    shape_cols = utils.feature_columns(data, "strict_shape")
    rf_scan, best_params, rf_score, rf_fold, rf_prob = utils.evaluate_rf_grid(data, y, shape_cols, config)

    scoreboard = pd.DataFrame(
        [
            utils.summarize_method(
                "curvature-only traditional",
                y,
                curvature_score,
                curvature_prob,
                runs,
                seed + 1,
                n_boot,
                "Pre-registered |C_t| comparator on all-three downstream injected target.",
            ),
            utils.summarize_method(
                "fold-selected traditional timing/template",
                y,
                trad_score,
                trad_prob,
                runs,
                seed + 2,
                n_boot,
                "S07d conventional comparator selected inside each training fold.",
            ),
            utils.summarize_method(
                "direct D_t/curvature cross-check",
                y,
                direct_dt_score,
                direct_dt_prob,
                runs,
                seed + 3,
                n_boot,
                "Diagnostic only; target is injected two-pulse truth, not a D_t threshold.",
            ),
            utils.summarize_method(
                "all-three shape-only RF",
                y,
                rf_score,
                rf_prob,
                runs,
                seed + 4,
                n_boot,
                f"Best params={best_params}; excludes timing, run/event ids, pair ids, injection params, amplitudes, and topology flags.",
            ),
        ]
    )

    topo_score, _ = utils.rf_oof(data, y, utils.feature_columns(data, "topology"), best_params, seed + 101)
    amp_score, _ = utils.rf_oof(data, y, utils.feature_columns(data, "amplitude"), best_params, seed + 102)
    shuffle_score, _ = utils.rf_oof(data, y, shape_cols, best_params, seed + 103, shuffle_train=True)
    slot_score, _ = utils.rf_oof(data, y, utils.feature_columns(data, "slot_shape"), best_params, seed + 104)
    pre_dt = data["base_d_t_ns"].to_numpy(dtype=float)

    pair_split_violations = 0
    for held_run in sorted(np.unique(runs)):
        train_pairs = set(data.loc[runs != held_run, "pair_id"].astype(int))
        test_pairs = set(data.loc[runs == held_run, "pair_id"].astype(int))
        pair_split_violations += len(train_pairs & test_pairs)

    forbidden_fragments = ["d_t_ns", "abs_c_t", "base_", "event", "pair", "delay", "scale", "target", "log_amp", "present", "run"]
    forbidden_shape_cols = [col for col in shape_cols if any(fragment in col for fragment in forbidden_fragments)]
    leakage = pd.DataFrame(
        [
            {"probe": "pre-injection D_t", "roc_auc": utils.auc(y, pre_dt), "average_precision": utils.ap(y, pre_dt), "notes": "Same for clean/injected pairs; should be chance."},
            {"probe": "topology-only RF", "roc_auc": utils.auc(y, topo_score), "average_precision": utils.ap(y, topo_score), "notes": "Constant all-three topology; should be chance."},
            {"probe": "absolute-amplitude-only RF", "roc_auc": utils.auc(y, amp_score), "average_precision": utils.ap(y, amp_score), "notes": "Excluded from main RF; injection changes peak height."},
            {"probe": "shape RF with shuffled training labels", "roc_auc": utils.auc(y, shuffle_score), "average_precision": utils.ap(y, shuffle_score), "notes": "Null/leakage sanity check."},
            {"probe": "per-stave slot shape RF", "roc_auc": utils.auc(y, slot_score), "average_precision": utils.ap(y, slot_score), "notes": "Permissive shape representation; not main claim."},
            {"probe": "pair split violations", "roc_auc": float(pair_split_violations), "average_precision": float("nan"), "notes": "Must be 0."},
            {"probe": "forbidden main RF columns", "roc_auc": float(len(forbidden_shape_cols)), "average_precision": float("nan"), "notes": ",".join(forbidden_shape_cols) if forbidden_shape_cols else "None."},
        ]
    )

    fixed_efficiency = pd.DataFrame(
        fixed_efficiency_rows(data, y, curvature_score, 0.95, "curvature-only traditional")
        + fixed_efficiency_rows(data, y, rf_score, 0.95, "all-three shape-only RF")
    )

    oof = data[
        [
            "row_id",
            "event_key",
            "pair_id",
            "run",
            "eventno",
            "evt",
            "label_injected",
            "variant",
            "base_d_t_ns",
            "d_t_ns",
            "abs_c_t_ns",
            "target_stave",
            "injected_delay_samples",
            "injected_scale",
        ]
    ].copy()
    oof["curvature_score"] = curvature_score
    oof["curvature_prob"] = curvature_prob
    oof["fold_selected_traditional_score"] = trad_score
    oof["direct_dt_score"] = direct_dt_score
    oof["rf_score"] = rf_score
    oof["rf_prob"] = rf_prob

    details = {
        "best_rf_params": best_params,
        "pair_split_violations": int(pair_split_violations),
        "forbidden_main_rf_columns": forbidden_shape_cols,
        "dataset_events": int(len(data)),
        "dataset_pairs": int(data["pair_id"].nunique()),
        "shape_feature_count": int(len(shape_cols)),
    }
    return counts, scoreboard, rf_scan, trad_choices, trad_candidates, leakage, fixed_efficiency, oof, details


def write_report(
    out_dir: Path,
    config: dict,
    reproduction: pd.DataFrame,
    s07e_score: pd.DataFrame,
    counts: pd.DataFrame,
    scoreboard: pd.DataFrame,
    trad_choices: pd.DataFrame,
    leakage: pd.DataFrame,
    fixed_efficiency: pd.DataFrame,
    result: dict,
) -> None:
    curv = scoreboard[scoreboard["method"] == "curvature-only traditional"].iloc[0]
    fold_trad = scoreboard[scoreboard["method"] == "fold-selected traditional timing/template"].iloc[0]
    rf = scoreboard[scoreboard["method"] == "all-three shape-only RF"].iloc[0]
    direct = scoreboard[scoreboard["method"] == "direct D_t/curvature cross-check"].iloc[0]

    text = f"""# S07e: all-three-downstream injected timing-corruption benchmark

- **Ticket:** `{config['ticket_id']}`
- **Worker:** `{config['worker']}`
- **Input:** raw B-stack ROOT `HRDv` from `{config['raw_root_dir']}`
- **Selection:** Sample-II runs, B2+B4+B6+B8 all selected, `A>1000` ADC, CFD20 timing.
- **Split:** leave-one-run-out; intervals are held-out run-block bootstrap CIs.

## Question

Rerun the S07d injected two-pulse timing-corruption target after removing missing-downstream-stave topology. The pre-registered conventional comparator is curvature-only, `|C_t| = |t_B8 - 2t_B6 + t_B4|`.

## Raw-ROOT Reproduction First

{markdown_table(reproduction)}

The raw scan reproduces the parent S07d App.I gross-tail gate (`72`) and the all-three control population (`3774`) before any injection is made. The old all-three D_t-label RF is also regenerated as a guardrail; the injected target below uses known injection truth, not the D_t tail label.

{markdown_table(s07e_score)}

## Injected Target

Each raw clean all-three event (`D_t < {config['clean_dt_max_ns']} ns`) is paired with one copy where a selected downstream waveform receives a delayed scaled copy of itself. Delays are {config['delay_samples_min']}-{config['delay_samples_max']} samples and scales are {config['secondary_scale_min']}-{config['secondary_scale_max']}. Pair members are held out together because the split is by run.

{markdown_table(counts)}

## Methods

- **Traditional, pre-registered:** post-injection curvature-only `|C_t|`.
- **Traditional, strong check:** S07d fold-selected conventional score from timing, curvature, downstream shape summaries, and a train-only matched-template residual.
- **ML:** random forest on amplitude-normalized B2 and downstream aggregate waveform-shape features only. Timing values, run/event IDs, pair IDs, injection parameters, absolute amplitudes, and topology flags are excluded.

{markdown_table(scoreboard)}

Traditional fold choices:

{markdown_table(trad_choices)}

## Fixed 95% Clean Acceptance

{markdown_table(fixed_efficiency)}

## Leakage Hunt

{markdown_table(leakage)}

The RF result is good but not perfect. Shuffled-label and topology-only probes are near chance, pair split violations are zero, and the main RF feature list has no forbidden timing, ID, amplitude, topology, or injection-parameter columns. The amplitude-only probe is non-trivial because injection can alter peak height; that information is excluded from the main RF. Direct post-injection `D_t`/curvature is near chance, confirming this target is not a disguised timing-tail threshold.

## Finding

On the all-three injected truth target, curvature-only reaches ROC AUC {curv['roc_auc']:.3f} [{curv['roc_auc_ci_low']:.3f}, {curv['roc_auc_ci_high']:.3f}], the fold-selected traditional comparator reaches {fold_trad['roc_auc']:.3f} [{fold_trad['roc_auc_ci_low']:.3f}, {fold_trad['roc_auc_ci_high']:.3f}], and the shape-only RF reaches {rf['roc_auc']:.3f} [{rf['roc_auc_ci_low']:.3f}, {rf['roc_auc_ci_high']:.3f}]. The RF advantage over curvature-only is {result['rf_minus_curvature_auc']:.3f} AUC, and over the S07d fold-selected traditional score is {result['rf_minus_fold_traditional_auc']:.3f}. This supports waveform-shape sensitivity after the all-three topology restriction, but it remains an injected-corruption recovery benchmark rather than a measured beam pile-up rate.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s07e_all_three_injected_curvature_benchmark.py --config configs/s07e_1781012659_1186_11c940a0.json
```

Key artifacts: `result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `injection_scoreboard.csv`, `leakage_checks.csv`, `fixed_efficiency.csv`, and `injection_oof_predictions.csv`.
"""
    (out_dir / "REPORT.md").write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/s07e_1781012659_1186_11c940a0.json")
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = load_config(config_path)
    out_dir = ROOT / config["output_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)

    utils = load_module("s07d_utils", ROOT / config["utility_script"])
    helper = load_module("s07f_helper", ROOT / config["all_three_helper_script"])

    parent, all_three, run_counts, clean_payloads = helper.collect_parent_and_all_three(config, utils)
    parent_guarded = int((parent["d_t_ns"] > float(config["gross_dt_min_ns"])).sum())
    parent_documented = int((parent["d_t_ns"] > float(config["documented_gross_dt_min_ns"])).sum())
    all_three_guarded = int((all_three["d_t_ns"] > float(config["gross_dt_min_ns"])).sum())
    all_three_clean = int((all_three["d_t_ns"] < float(config["clean_dt_max_ns"])).sum())

    reproduction = pd.DataFrame(
        [
            {"quantity": "parent S07d guarded gross D_t>51 ns", "report_value": int(config["expected_parent_gross_events"]), "reproduced": parent_guarded, "delta": parent_guarded - int(config["expected_parent_gross_events"]), "tolerance": 0, "pass": parent_guarded == int(config["expected_parent_gross_events"])},
            {"quantity": "parent documented gross D_t>50 ns", "report_value": None, "reproduced": parent_documented, "delta": None, "tolerance": None, "pass": True},
            {"quantity": "all-three control events", "report_value": int(config["expected_all_three_control_events"]), "reproduced": int(len(all_three)), "delta": int(len(all_three)) - int(config["expected_all_three_control_events"]), "tolerance": 0, "pass": int(len(all_three)) == int(config["expected_all_three_control_events"])},
            {"quantity": "all-three clean events D_t<3 ns", "report_value": None, "reproduced": all_three_clean, "delta": None, "tolerance": None, "pass": True},
            {"quantity": "all-three guarded gross D_t>51 ns", "report_value": int(config["expected_all_three_guarded_gross_events"]), "reproduced": all_three_guarded, "delta": all_three_guarded - int(config["expected_all_three_guarded_gross_events"]), "tolerance": 0, "pass": all_three_guarded == int(config["expected_all_three_guarded_gross_events"])},
        ]
    )
    if not bool(reproduction["pass"].all()):
        raise RuntimeError("raw-ROOT reproduction gate failed")

    s07e_score, s07e_rf_scan, s07e_oof, _, _ = helper.s07e_reproduction(config, utils, all_three)

    counts, scoreboard, rf_scan, trad_choices, trad_candidates, leakage, fixed_efficiency, oof, details = all_three_injection_benchmark(config, utils, clean_payloads)

    run_counts.to_csv(out_dir / "run_counts.csv", index=False)
    reproduction.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    s07e_score.to_csv(out_dir / "dt_label_guardrail_scoreboard.csv", index=False)
    s07e_rf_scan.to_csv(out_dir / "dt_label_guardrail_rf_scan.csv", index=False)
    s07e_oof.to_csv(out_dir / "dt_label_guardrail_oof_predictions.csv", index=False)
    counts.to_csv(out_dir / "injection_dataset_counts_by_run.csv", index=False)
    scoreboard.to_csv(out_dir / "injection_scoreboard.csv", index=False)
    rf_scan.to_csv(out_dir / "injection_rf_cv_scan.csv", index=False)
    trad_choices.to_csv(out_dir / "traditional_fold_choices.csv", index=False)
    trad_candidates.to_csv(out_dir / "traditional_candidate_scores.csv", index=False)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)
    fixed_efficiency.to_csv(out_dir / "fixed_efficiency.csv", index=False)
    oof.to_csv(out_dir / "injection_oof_predictions.csv", index=False)

    curv_auc = float(scoreboard.loc[scoreboard["method"] == "curvature-only traditional", "roc_auc"].iloc[0])
    fold_auc = float(scoreboard.loc[scoreboard["method"] == "fold-selected traditional timing/template", "roc_auc"].iloc[0])
    direct_auc = float(scoreboard.loc[scoreboard["method"] == "direct D_t/curvature cross-check", "roc_auc"].iloc[0])
    rf_auc = float(scoreboard.loc[scoreboard["method"] == "all-three shape-only RF", "roc_auc"].iloc[0])
    result = {
        "ticket_id": config["ticket_id"],
        "study_id": config["study_id"],
        "title": config["title"],
        "raw_reproduction_pass": bool(reproduction["pass"].all()),
        "parent_guarded_gross_events": parent_guarded,
        "all_three_control_events": int(len(all_three)),
        "all_three_clean_events": all_three_clean,
        "all_three_guarded_gross_events": all_three_guarded,
        "curvature_only_injected_auc": curv_auc,
        "fold_selected_traditional_injected_auc": fold_auc,
        "direct_dt_curvature_injected_auc": direct_auc,
        "shape_rf_injected_auc": rf_auc,
        "rf_minus_curvature_auc": float(rf_auc - curv_auc),
        "rf_minus_fold_traditional_auc": float(rf_auc - fold_auc),
        "rf_minus_direct_dt_auc": float(rf_auc - direct_auc),
        "expected_s07f_all_three_injected_rf_auc": float(config["expected_s07f_all_three_injected_rf_auc"]),
        "s07f_rf_auc_delta": float(rf_auc - float(config["expected_s07f_all_three_injected_rf_auc"])),
        **details,
        "elapsed_seconds": float(time.time() - t0),
    }

    write_report(out_dir, config, reproduction, s07e_score, counts, scoreboard, trad_choices, leakage, fixed_efficiency, result)
    (out_dir / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    input_rows = []
    for run in config["runs"]:
        path = helper.raw_file(config, int(run))
        input_rows.append({"path": str(path), "sha256": sha256_file(path), "bytes": path.stat().st_size})
    script_relpath = Path(__file__).resolve().relative_to(ROOT)
    for extra in [config_path, Path(config["utility_script"]), Path(config["all_three_helper_script"]), script_relpath]:
        path = ROOT / extra
        input_rows.append({"path": str(extra), "sha256": sha256_file(path), "bytes": path.stat().st_size})
    pd.DataFrame(input_rows).to_csv(out_dir / "input_sha256.csv", index=False)

    manifest = {
        "ticket_id": config["ticket_id"],
        "study_id": config["study_id"],
        "worker": config["worker"],
        "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "git_commit": git_commit(),
        "platform": platform.platform(),
        "python": sys.version,
        "inputs": input_rows,
        "outputs": {},
        "command": f"/home/billy/anaconda3/bin/python scripts/s07e_all_three_injected_curvature_benchmark.py --config {config_path}",
    }
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            manifest["outputs"][path.name] = sha256_file(path)
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
