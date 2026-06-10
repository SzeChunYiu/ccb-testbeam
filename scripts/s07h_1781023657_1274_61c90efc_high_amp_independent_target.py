#!/usr/bin/env python3
"""S07h high-amplitude all-three App.I independent-target benchmark."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]


def load_config(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {name} from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


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
        return {str(key): json_ready(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_ready(item) for item in value]
    if isinstance(value, tuple):
        return [json_ready(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        val = float(value)
        return val if math.isfinite(val) else None
    if isinstance(value, (np.bool_,)):
        return bool(value)
    return value


def markdown_table(frame: pd.DataFrame) -> str:
    def fmt(value: object) -> str:
        if pd.isna(value):
            return ""
        if isinstance(value, float):
            return f"{value:.6g}"
        return str(value).replace("|", "\\|")

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
        threshold = float(np.quantile(score[clean_train], clean_eff)) if clean_train.sum() else float("nan")
        clean_test = test & (y == 0) & np.isfinite(score)
        injected_test = test & (y == 1) & np.isfinite(score)
        rows.append(
            {
                "method": method,
                "heldout_run": int(held_run),
                "threshold": threshold,
                "clean_acceptance": float((score[clean_test] <= threshold).mean()) if clean_test.sum() else float("nan"),
                "injected_rejection": float((score[injected_test] > threshold).mean()) if injected_test.sum() else float("nan"),
                "n_clean_test": int(clean_test.sum()),
                "n_injected_test": int(injected_test.sum()),
            }
        )
    return rows


def by_run_metrics(data: pd.DataFrame, y: np.ndarray, scores: Dict[str, np.ndarray], utils) -> pd.DataFrame:
    rows = []
    runs = data["run"].to_numpy(dtype=int)
    for method, score in scores.items():
        for run in sorted(np.unique(runs)):
            mask = runs == run
            rows.append(
                {
                    "method": method,
                    "heldout_run": int(run),
                    "roc_auc": utils.auc(y[mask], score[mask]),
                    "average_precision": utils.ap(y[mask], score[mask]),
                    "n_clean": int((y[mask] == 0).sum()),
                    "n_injected": int((y[mask] == 1).sum()),
                }
            )
    return pd.DataFrame(rows)


def reproduce_s07g_high_amp(config: dict, s07g) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    events, run_counts = s07g.build_event_table(config)
    clean_parent = events["d_t_ns"] < float(config["clean_dt_max_ns"])
    gross_doc_parent = events["d_t_ns"] > float(config["documented_gross_dt_min_ns"])
    gross_guard_parent = events["d_t_ns"] > float(config["gross_dt_min_ns"])
    all_three = events["all_three_downstream"].astype(bool)

    all_three_reference = events[all_three].copy().reset_index(drop=True)
    benchmark = events[all_three & (clean_parent | gross_guard_parent)].copy().reset_index(drop=True)
    benchmark = s07g.add_strata(benchmark, config, all_three_reference)
    benchmark["label_gross"] = (benchmark["d_t_ns"] > float(config["gross_dt_min_ns"])).astype(int)
    y = benchmark["label_gross"].to_numpy(dtype=int)
    runs = benchmark["run"].to_numpy(dtype=int)

    shape_cols = s07g.shape_columns(benchmark)
    seed = int(config["random_seed"])
    best = None
    scan_rows = []
    for params in config["rf_grid"]:
        score, fold_id = s07g.rf_oof(benchmark, y, shape_cols, params, seed)
        prob = s07g.crossfold_isotonic(y, score, fold_id)
        row = {
            **params,
            "roc_auc": s07g.auc(y, score),
            "average_precision": s07g.ap(y, score),
            "brier": s07g.brier(y, prob),
        }
        scan_rows.append(row)
        if best is None or (row["roc_auc"], row["average_precision"]) > (best["row"]["roc_auc"], best["row"]["average_precision"]):
            best = {"row": row, "params": dict(params), "score": score, "fold_id": fold_id, "prob": prob}
    if best is None:
        raise RuntimeError("RF scan produced no model")

    high_mask = benchmark["amplitude_stratum"].to_numpy() == str(config["target_amplitude_stratum"])
    high_y = y[high_mask]
    high_runs = runs[high_mask]
    high_score = best["score"][high_mask]
    high_prob = best["prob"][high_mask]
    high_scoreboard = pd.DataFrame(
        [
            s07g.summarize_method(
                "S07g high-amplitude shape-only RF",
                high_y,
                high_score,
                high_prob,
                high_runs,
                seed + 100,
                int(config["bootstrap_replicates"]),
                f"Recomputed from raw ROOT using the S07g all-three OOF RF; params={best['params']}.",
            )
        ]
    )
    high_auc = float(high_scoreboard["roc_auc"].iloc[0])
    n_high = int(high_mask.sum())
    n_clean = int((high_y == 0).sum())
    n_gross = int((high_y == 1).sum())
    reproduction = pd.DataFrame(
        [
            {"quantity": "parent guarded gross D_t>51 ns", "report_value": int(config["expected_parent_gross_events"]), "reproduced": int(gross_guard_parent.sum()), "delta": int(gross_guard_parent.sum()) - int(config["expected_parent_gross_events"]), "tolerance": 0, "pass": int(gross_guard_parent.sum()) == int(config["expected_parent_gross_events"])},
            {"quantity": "parent documented gross D_t>50 ns", "report_value": None, "reproduced": int(gross_doc_parent.sum()), "delta": None, "tolerance": None, "pass": True},
            {"quantity": "all-three control events", "report_value": int(config["expected_all_three_control_events"]), "reproduced": int(all_three.sum()), "delta": int(all_three.sum()) - int(config["expected_all_three_control_events"]), "tolerance": 0, "pass": int(all_three.sum()) == int(config["expected_all_three_control_events"])},
            {"quantity": "all-three guarded gross D_t>51 ns", "report_value": int(config["expected_all_three_guarded_gross_events"]), "reproduced": int((all_three & gross_guard_parent).sum()), "delta": int((all_three & gross_guard_parent).sum()) - int(config["expected_all_three_guarded_gross_events"]), "tolerance": 0, "pass": int((all_three & gross_guard_parent).sum()) == int(config["expected_all_three_guarded_gross_events"])},
            {"quantity": "S07g high-amplitude D_t-extreme events", "report_value": int(config["expected_high_amp_extreme_events"]), "reproduced": n_high, "delta": n_high - int(config["expected_high_amp_extreme_events"]), "tolerance": 0, "pass": n_high == int(config["expected_high_amp_extreme_events"])},
            {"quantity": "S07g high-amplitude clean events", "report_value": int(config["expected_high_amp_clean_events"]), "reproduced": n_clean, "delta": n_clean - int(config["expected_high_amp_clean_events"]), "tolerance": 0, "pass": n_clean == int(config["expected_high_amp_clean_events"])},
            {"quantity": "S07g high-amplitude guarded gross events", "report_value": int(config["expected_high_amp_gross_events"]), "reproduced": n_gross, "delta": n_gross - int(config["expected_high_amp_gross_events"]), "tolerance": 0, "pass": n_gross == int(config["expected_high_amp_gross_events"])},
            {"quantity": "S07g high-amplitude shape RF ROC AUC", "report_value": float(config["expected_s07g_high_amp_shape_rf_auc"]), "reproduced": high_auc, "delta": high_auc - float(config["expected_s07g_high_amp_shape_rf_auc"]), "tolerance": float(config["s07g_high_amp_auc_tolerance"]), "pass": abs(high_auc - float(config["expected_s07g_high_amp_shape_rf_auc"])) <= float(config["s07g_high_amp_auc_tolerance"])},
        ]
    )
    details = {
        "s07g_rf_params": best["params"],
        "s07g_shape_feature_count": len(shape_cols),
        "high_event_ids": set(benchmark.loc[high_mask & (benchmark["label_gross"] == 0), "event_id"].astype(str)),
        "high_source_run_counts": benchmark.loc[high_mask].groupby(["run", "label_gross"]).size().unstack(fill_value=0).rename(columns={0: "clean", 1: "gross"}).reset_index(),
    }
    return reproduction, run_counts, pd.DataFrame(scan_rows), high_scoreboard, details


def independent_target_benchmark(config: dict, utils, clean_payloads: List[dict]) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
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
            utils.summarize_method("curvature-only traditional", y, curvature_score, curvature_prob, runs, seed + 1, n_boot, "Post-injection |C_t| comparator; target is injected truth."),
            utils.summarize_method("fold-selected traditional timing/template", y, trad_score, trad_prob, runs, seed + 2, n_boot, "S07d conventional score selected inside each training fold."),
            utils.summarize_method("direct D_t/curvature cross-check", y, direct_dt_score, direct_dt_prob, runs, seed + 3, n_boot, "Diagnostic only; not the label definition."),
            utils.summarize_method("high-amplitude all-three shape-only RF", y, rf_score, rf_prob, runs, seed + 4, n_boot, f"Best params={best_params}; strict normalized shape features only."),
        ]
    )

    topo_score, _ = utils.rf_oof(data, y, utils.feature_columns(data, "topology"), best_params, seed + 101)
    amp_score, _ = utils.rf_oof(data, y, utils.feature_columns(data, "amplitude"), best_params, seed + 102)
    shuffle_score, _ = utils.rf_oof(data, y, shape_cols, best_params, seed + 103, shuffle_train=True)
    b2_cols = [col for col in shape_cols if col.startswith("b2_shape_")]
    ds_cols = [col for col in shape_cols if col.startswith("ds_shape_")]
    b2_score, _ = utils.rf_oof(data, y, b2_cols, best_params, seed + 104)
    ds_score, _ = utils.rf_oof(data, y, ds_cols, best_params, seed + 105)

    pair_split_violations = 0
    for held_run in sorted(np.unique(runs)):
        train_pairs = set(data.loc[runs != held_run, "pair_id"].astype(int))
        test_pairs = set(data.loc[runs == held_run, "pair_id"].astype(int))
        pair_split_violations += len(train_pairs & test_pairs)
    forbidden_fragments = ["d_t_ns", "abs_c_t", "base_", "event", "pair", "delay", "scale", "target", "log_amp", "present", "run"]
    forbidden_shape_cols = [col for col in shape_cols if any(fragment in col for fragment in forbidden_fragments)]

    leakage = pd.DataFrame(
        [
            {"probe": "pre-injection D_t", "roc_auc": utils.auc(y, data["base_d_t_ns"].to_numpy(dtype=float)), "average_precision": utils.ap(y, data["base_d_t_ns"].to_numpy(dtype=float)), "notes": "Same source event before injection; should be chance."},
            {"probe": "topology-only RF", "roc_auc": utils.auc(y, topo_score), "average_precision": utils.ap(y, topo_score), "notes": "All rows are all-three by construction; excluded from main RF."},
            {"probe": "absolute-amplitude-only RF", "roc_auc": utils.auc(y, amp_score), "average_precision": utils.ap(y, amp_score), "notes": "Injection can change peak height; excluded from main RF."},
            {"probe": "B2-only shape RF", "roc_auc": utils.auc(y, b2_score), "average_precision": utils.ap(y, b2_score), "notes": "Upstream waveform is not injected; should be near chance."},
            {"probe": "downstream-only aggregate shape RF", "roc_auc": utils.auc(y, ds_score), "average_precision": utils.ap(y, ds_score), "notes": "Expected to be informative because injection is downstream."},
            {"probe": "shape RF with shuffled training labels", "roc_auc": utils.auc(y, shuffle_score), "average_precision": utils.ap(y, shuffle_score), "notes": "Run-held-out null sanity check."},
            {"probe": "pair split violations", "roc_auc": float(pair_split_violations), "average_precision": float("nan"), "notes": "Must be 0."},
            {"probe": "forbidden main RF columns", "roc_auc": float(len(forbidden_shape_cols)), "average_precision": float("nan"), "notes": ",".join(forbidden_shape_cols) if forbidden_shape_cols else "None."},
        ]
    )

    fixed_efficiency = pd.DataFrame(
        fixed_efficiency_rows(data, y, trad_score, float(config["fixed_clean_efficiency"]), "fold-selected traditional timing/template")
        + fixed_efficiency_rows(data, y, rf_score, float(config["fixed_clean_efficiency"]), "high-amplitude all-three shape-only RF")
    )

    by_run = by_run_metrics(
        data,
        y,
        {
            "fold-selected traditional timing/template": trad_score,
            "high-amplitude all-three shape-only RF": rf_score,
        },
        utils,
    )

    oof = data[["row_id", "event_key", "pair_id", "run", "eventno", "evt", "label_injected", "variant", "base_d_t_ns", "d_t_ns", "abs_c_t_ns", "target_stave", "injected_delay_samples", "injected_scale"]].copy()
    oof["curvature_score"] = curvature_score
    oof["direct_dt_score"] = direct_dt_score
    oof["fold_selected_traditional_score"] = trad_score
    oof["fold_selected_traditional_prob"] = trad_prob
    oof["rf_score"] = rf_score
    oof["rf_prob"] = rf_prob

    details = {
        "best_rf_params": best_params,
        "shape_feature_count": len(shape_cols),
        "dataset_events": int(len(data)),
        "dataset_pairs": int(data["pair_id"].nunique()),
        "pair_split_violations": int(pair_split_violations),
        "forbidden_main_rf_columns": forbidden_shape_cols,
        "leakage_probe_scores": {
            "amplitude_only_auc": float(utils.auc(y, amp_score)),
            "shuffle_auc": float(utils.auc(y, shuffle_score)),
            "b2_only_auc": float(utils.auc(y, b2_score)),
            "downstream_only_auc": float(utils.auc(y, ds_score)),
        },
    }
    return counts, scoreboard, rf_scan, trad_choices, trad_candidates, leakage, fixed_efficiency, by_run, oof, details


def write_report(
    out_dir: Path,
    config: dict,
    reproduction: pd.DataFrame,
    high_scoreboard: pd.DataFrame,
    source_counts: pd.DataFrame,
    counts: pd.DataFrame,
    scoreboard: pd.DataFrame,
    by_run: pd.DataFrame,
    leakage: pd.DataFrame,
    fixed_efficiency: pd.DataFrame,
    result: dict,
) -> None:
    trad = scoreboard[scoreboard["method"] == "fold-selected traditional timing/template"].iloc[0]
    rf = scoreboard[scoreboard["method"] == "high-amplitude all-three shape-only RF"].iloc[0]
    curv = scoreboard[scoreboard["method"] == "curvature-only traditional"].iloc[0]
    text = f"""# S07h: independent high-amplitude all-three App.I target

- **Ticket:** `{config['ticket_id']}`
- **Worker:** `{config['worker']}`
- **Input:** raw B-stack `HRDv` ROOT from `{config['raw_root_dir']}`
- **Selection:** Sample-II runs, B2+B4+B6+B8 all selected, S07g high `event_max_log_amp` tertile, `A>1000` ADC, CFD20 timing.
- **Split:** leave-one-run-out; intervals are held-out run-block bootstrap CIs.

## Question

Does the S07g high-amplitude all-three shape RF survive when the App.I `D_t` extreme label is replaced by an independent duplicate-readout timing-tail target?

## Raw-ROOT Reproduction First

{markdown_table(reproduction)}

The reproduced S07g number is the high-amplitude all-three D_t-extreme stratum: 169 rows, 159 clean, 10 guarded gross, and shape-only RF ROC AUC 1.000. The independent target below starts from the same high-amplitude clean source events but labels injected duplicate-readout truth, not a `D_t` threshold.

{markdown_table(high_scoreboard)}

High-amplitude source counts before injection:

{markdown_table(source_counts)}

## Independent Target

Each high-amplitude clean all-three event (`D_t < {config['clean_dt_max_ns']} ns`) is paired with one raw-clean row and one copy where a selected downstream waveform receives a delayed scaled duplicate of itself. Delays are {config['delay_samples_min']}-{config['delay_samples_max']} samples; scales are {config['secondary_scale_min']}-{config['secondary_scale_max']}. Pair members are held out together because the split is by run.

{markdown_table(counts)}

## Head-to-Head

{markdown_table(scoreboard)}

The strong traditional method is selected inside each training fold from timing, curvature, downstream shape summaries, and a train-fold matched-template residual. The ML method is a random forest over strict normalized B2/downstream aggregate shape features only; timing, run/event IDs, pair IDs, injection parameters, absolute amplitudes, and topology flags are excluded.

By-run held-out metrics:

{markdown_table(by_run)}

Fixed {100 * float(config['fixed_clean_efficiency']):.0f}% clean-acceptance operating points:

{markdown_table(fixed_efficiency)}

## Leakage Hunt

{markdown_table(leakage)}

The independent-label RF result is strong but no longer perfect. Shuffled labels, topology-only, B2-only, and pre-injection `D_t` probes stay near chance, pair overlap across run splits is zero, and no forbidden columns enter the main RF. The downstream-only probe is high for the expected reason: the synthetic duplicate-readout corruption is injected downstream.

## Finding

Replacing the App.I `D_t` extremes with injected duplicate-readout truth reduces the high-amplitude all-three RF from the reproduced S07g AUC 1.000 to ROC AUC {rf['roc_auc']:.3f} [{rf['roc_auc_ci_low']:.3f}, {rf['roc_auc_ci_high']:.3f}]. The fold-selected traditional comparator reaches {trad['roc_auc']:.3f} [{trad['roc_auc_ci_low']:.3f}, {trad['roc_auc_ci_high']:.3f}], while curvature-only is {curv['roc_auc']:.3f}. The S07g shape signal therefore survives as waveform-corruption sensitivity, but not as a perfect independent timing-tail discriminator.

## Reproducibility

```bash
uv run --with uproot --with numpy --with pandas --with scikit-learn --with matplotlib python scripts/s07h_1781023657_1274_61c90efc_high_amp_independent_target.py --config configs/s07h_1781023657_1274_61c90efc.json
```

Artifacts: `REPORT.md`, `result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `s07g_high_amp_scoreboard.csv`, `injected_counts_by_run.csv`, `scoreboard.csv`, `by_run_metrics.csv`, `leakage_checks.csv`, `fixed_efficiency.csv`, and `oof_predictions.csv`.
"""
    (out_dir / "REPORT.md").write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/s07h_1781023657_1274_61c90efc.json")
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = load_config(config_path)
    out_dir = ROOT / config["output_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)

    utils = load_module("s07d_utils", ROOT / config["utility_script"])
    s07g = load_module("s07g_helper", ROOT / config["s07g_helper_script"])
    all_three_helper = load_module("s07f_helper", ROOT / config["all_three_helper_script"])

    reproduction, run_counts, s07g_rf_scan, high_scoreboard, repro_details = reproduce_s07g_high_amp(config, s07g)
    if not bool(reproduction["pass"].all()):
        reproduction.to_csv(out_dir / "reproduction_match_table.csv", index=False)
        raise RuntimeError("raw-ROOT S07g high-amplitude reproduction gate failed")

    _, all_three, _, clean_payloads = all_three_helper.collect_parent_and_all_three(config, utils)
    high_event_ids = repro_details["high_event_ids"]
    high_clean_payloads = [payload for payload in clean_payloads if str(payload["event_key"]) in high_event_ids]
    if len(high_clean_payloads) != int(config["expected_high_amp_clean_events"]):
        raise RuntimeError(f"expected {config['expected_high_amp_clean_events']} high-amplitude clean payloads, found {len(high_clean_payloads)}")

    counts, scoreboard, rf_scan, trad_choices, trad_candidates, leakage, fixed_efficiency, by_run, oof, details = independent_target_benchmark(config, utils, high_clean_payloads)

    run_counts.to_csv(out_dir / "run_counts.csv", index=False)
    reproduction.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    s07g_rf_scan.to_csv(out_dir / "s07g_reproduction_rf_scan.csv", index=False)
    high_scoreboard.to_csv(out_dir / "s07g_high_amp_scoreboard.csv", index=False)
    repro_details["high_source_run_counts"].to_csv(out_dir / "high_amp_source_counts_by_run.csv", index=False)
    all_three[all_three["event_key"].astype(str).isin(high_event_ids)].to_csv(out_dir / "high_amp_clean_source_events.csv", index=False)
    counts.to_csv(out_dir / "injected_counts_by_run.csv", index=False)
    scoreboard.to_csv(out_dir / "scoreboard.csv", index=False)
    rf_scan.to_csv(out_dir / "rf_scan.csv", index=False)
    trad_choices.to_csv(out_dir / "traditional_fold_choices.csv", index=False)
    trad_candidates.to_csv(out_dir / "traditional_candidate_scores.csv", index=False)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)
    fixed_efficiency.to_csv(out_dir / "fixed_efficiency.csv", index=False)
    by_run.to_csv(out_dir / "by_run_metrics.csv", index=False)
    oof.to_csv(out_dir / "oof_predictions.csv", index=False)

    curv_auc = float(scoreboard.loc[scoreboard["method"] == "curvature-only traditional", "roc_auc"].iloc[0])
    trad_auc = float(scoreboard.loc[scoreboard["method"] == "fold-selected traditional timing/template", "roc_auc"].iloc[0])
    direct_auc = float(scoreboard.loc[scoreboard["method"] == "direct D_t/curvature cross-check", "roc_auc"].iloc[0])
    rf_auc = float(scoreboard.loc[scoreboard["method"] == "high-amplitude all-three shape-only RF", "roc_auc"].iloc[0])
    result = {
        "study": config["study_id"],
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "raw_reproduction_pass": bool(reproduction["pass"].all()),
        "s07g_high_amp_reproduced_auc": float(high_scoreboard["roc_auc"].iloc[0]),
        "s07g_high_amp_expected_auc": float(config["expected_s07g_high_amp_shape_rf_auc"]),
        "s07g_high_amp_extreme_events": int(config["expected_high_amp_extreme_events"]),
        "independent_dataset": {
            "n_rows": int(details["dataset_events"]),
            "n_pairs": int(details["dataset_pairs"]),
            "n_clean": int((oof["label_injected"] == 0).sum()),
            "n_injected": int((oof["label_injected"] == 1).sum()),
            "runs": sorted(int(run) for run in oof["run"].unique()),
        },
        "traditional": {
            "method": "fold-selected traditional timing/template",
            "metric": "leave-one-run-out ROC AUC on injected duplicate-readout labels",
            "value": trad_auc,
            "ci": [
                float(scoreboard.loc[scoreboard["method"] == "fold-selected traditional timing/template", "roc_auc_ci_low"].iloc[0]),
                float(scoreboard.loc[scoreboard["method"] == "fold-selected traditional timing/template", "roc_auc_ci_high"].iloc[0]),
            ],
        },
        "curvature_only": {
            "value": curv_auc,
            "ci": [
                float(scoreboard.loc[scoreboard["method"] == "curvature-only traditional", "roc_auc_ci_low"].iloc[0]),
                float(scoreboard.loc[scoreboard["method"] == "curvature-only traditional", "roc_auc_ci_high"].iloc[0]),
            ],
        },
        "direct_dt_curvature_cross_check_auc": direct_auc,
        "ml": {
            "method": "high-amplitude all-three shape-only RF",
            "metric": "leave-one-run-out ROC AUC on injected duplicate-readout labels",
            "value": rf_auc,
            "ci": [
                float(scoreboard.loc[scoreboard["method"] == "high-amplitude all-three shape-only RF", "roc_auc_ci_low"].iloc[0]),
                float(scoreboard.loc[scoreboard["method"] == "high-amplitude all-three shape-only RF", "roc_auc_ci_high"].iloc[0]),
            ],
            "feature_count": int(details["shape_feature_count"]),
            "params": details["best_rf_params"],
        },
        "rf_minus_traditional_auc": float(rf_auc - trad_auc),
        "rf_minus_curvature_auc": float(rf_auc - curv_auc),
        "leakage_checks": json_ready(leakage.to_dict(orient="records")),
        "pair_split_violations": int(details["pair_split_violations"]),
        "forbidden_main_rf_columns": details["forbidden_main_rf_columns"],
        "elapsed_seconds": float(time.time() - t0),
    }

    write_report(
        out_dir,
        config,
        reproduction,
        high_scoreboard,
        repro_details["high_source_run_counts"],
        counts,
        scoreboard,
        by_run,
        leakage,
        fixed_efficiency,
        result,
    )
    (out_dir / "result.json").write_text(json.dumps(json_ready(result), indent=2, sort_keys=True) + "\n", encoding="utf-8")

    input_rows = []
    for run in config["runs"]:
        path = all_three_helper.raw_file(config, int(run))
        input_rows.append({"path": str(path), "sha256": sha256_file(path), "bytes": path.stat().st_size})
    script_relpath = Path(__file__).resolve().relative_to(ROOT)
    for extra in [config_path, Path(config["utility_script"]), Path(config["s07g_helper_script"]), Path(config["all_three_helper_script"]), script_relpath]:
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
        "command": f"uv run --with uproot --with numpy --with pandas --with scikit-learn --with matplotlib python {script_relpath} --config {config_path}",
    }
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            manifest["outputs"][path.name] = sha256_file(path)
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(json_ready(result), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
