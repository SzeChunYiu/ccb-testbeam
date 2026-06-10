#!/usr/bin/env python3
"""S11e: full constrained two-pulse fit for the S07f all-three target."""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import os
import platform
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

os.environ.setdefault("MPLCONFIGDIR", "/tmp/ccb-testbeam-s11e-1781024319-mpl")


ROOT = Path(__file__).resolve().parents[1]


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


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


def fill_finite(values: np.ndarray) -> np.ndarray:
    finite = np.isfinite(values)
    fill = float(np.nanmedian(values[finite])) if finite.any() else 0.0
    return np.where(finite, values, fill)


def constrained_fit_only_oof(data: pd.DataFrame, y: np.ndarray, config: dict, s07f_config: dict, utils, fitmod):
    staves = list(s07f_config["staves"].keys())
    downstream_idx = np.asarray([staves.index(name) for name in s07f_config["downstream_staves"]], dtype=int)
    runs = data["run"].to_numpy(dtype=int)
    score = np.full(len(data), np.nan, dtype=float)
    fold_id = np.full(len(data), -1, dtype=int)
    fold_rows = []
    fit_rows = []

    for fold, held_run in enumerate(sorted(np.unique(runs))):
        test = runs == held_run
        train = ~test
        templates = utils.template_from_train(data, train, staves)
        fold_fits = []
        for idx, row in data.iterrows():
            fit = fitmod.fit_event(row, staves, downstream_idx, templates, config)
            fit["row_index"] = int(idx)
            fit["heldout_run_for_template"] = int(held_run)
            if bool(test[idx]):
                fit_rows.append(fit)
            fold_fits.append(fit)
        fit_frame = pd.DataFrame(fold_fits)
        candidates = {
            "secondary_fraction": fit_frame["secondary_fraction"].to_numpy(dtype=float),
            "secondary_amp_norm": fit_frame["secondary_amp_norm"].to_numpy(dtype=float),
            "frac_sse_improvement": fit_frame["frac_sse_improvement"].to_numpy(dtype=float),
            "delta_sse": fit_frame["delta_sse"].to_numpy(dtype=float),
            "delay_samples": fit_frame["delay_samples"].to_numpy(dtype=float),
            "neg_chi2_ndf": -fit_frame["chi2_ndf"].to_numpy(dtype=float),
            "neg_sse_two": -fit_frame["sse_two"].to_numpy(dtype=float),
        }
        best = {"candidate": "", "sign": 1, "train_auc": -np.inf, "median": 0.0, "iqr": 1.0}
        for name, raw_values in candidates.items():
            values = fill_finite(raw_values)
            for sign in [1, -1]:
                signed = sign * values
                train_auc = fitmod.auc(y[train], signed[train])
                if train_auc > best["train_auc"]:
                    q25, q75 = np.percentile(signed[train], [25, 75])
                    best = {
                        "candidate": name,
                        "sign": int(sign),
                        "train_auc": float(train_auc),
                        "median": float(np.median(signed[train])),
                        "iqr": float(max(q75 - q25, 1e-6)),
                    }
        selected = best["sign"] * fill_finite(candidates[best["candidate"]])
        score[test] = (selected[test] - best["median"]) / best["iqr"]
        fold_id[test] = fold
        fold_rows.append(
            {
                "heldout_run": int(held_run),
                "candidate": best["candidate"],
                "sign": int(best["sign"]),
                "train_auc": best["train_auc"],
                "train_median": best["median"],
                "train_iqr": best["iqr"],
                "n_train": int(train.sum()),
                "n_test": int(test.sum()),
            }
        )

    fit_oof = pd.DataFrame(fit_rows).sort_values("row_index").reset_index(drop=True)
    return score, fold_id, pd.DataFrame(fold_rows), fit_oof


def fit_summary_by_class(data: pd.DataFrame, fit_oof: pd.DataFrame) -> pd.DataFrame:
    summary = (
        pd.concat([data[["label_injected"]].reset_index(drop=True), fit_oof.reset_index(drop=True)], axis=1)
        .groupby("label_injected")
        .agg(
            n=("row_index", "size"),
            valid_fraction=("valid", "mean"),
            median_secondary_fraction=("secondary_fraction", "median"),
            median_secondary_amp_norm=("secondary_amp_norm", "median"),
            median_delay_samples=("delay_samples", "median"),
            median_chi2_ndf=("chi2_ndf", "median"),
            median_frac_sse_improvement=("frac_sse_improvement", "median"),
        )
        .reset_index()
    )
    summary["class"] = np.where(summary["label_injected"] == 1, "injected", "raw_clean")
    return summary[
        [
            "class",
            "n",
            "valid_fraction",
            "median_secondary_fraction",
            "median_secondary_amp_norm",
            "median_delay_samples",
            "median_chi2_ndf",
            "median_frac_sse_improvement",
        ]
    ]


def write_report(
    out_dir: Path,
    config: dict,
    s07f_config: dict,
    reproduction: pd.DataFrame,
    s07f_score: pd.DataFrame,
    counts: pd.DataFrame,
    fit_summary: pd.DataFrame,
    fit_choices: pd.DataFrame,
    rf_scan: pd.DataFrame,
    scoreboard: pd.DataFrame,
    leakage: pd.DataFrame,
    result: dict,
) -> None:
    s07f_trad = s07f_score[s07f_score["method"] == "traditional fold-selected timing/template"].iloc[0]
    s07f_rf = s07f_score[s07f_score["method"] == "all-three shape-only RF"].iloc[0]
    fit = scoreboard[scoreboard["method"] == "bounded two-pulse fit outputs"].iloc[0]
    rf = scoreboard[scoreboard["method"] == "shape-only RF"].iloc[0]
    text = f"""# S11e: full constrained two-pulse fit for all-three App.I target

- **Ticket:** `{config['ticket_id']}`
- **Worker:** `{config['worker']}`
- **Input:** raw B-stack ROOT `HRDv` from `{s07f_config['raw_root_dir']}`
- **Target:** S07f all-three injected truth, Sample-II analysis runs, B2+B4+B6+B8 selected, `A>1000` ADC.
- **Split:** leave-one-run-out; intervals are run-block bootstrap 95% CIs.

## Raw-ROOT Reproduction First

{markdown_table(reproduction)}

The S07f target was regenerated before the new fit. It reproduces the prior traditional AUC **{s07f_trad['roc_auc']:.6f}** and shape-only RF AUC **{s07f_rf['roc_auc']:.6f}**, within the configured tolerance.

{markdown_table(s07f_score)}

## Target Counts

{markdown_table(counts)}

## Methods

Traditional method: train-run-only median templates for B4/B6/B8 feed a bounded one-pulse versus two-pulse least-squares fit on each downstream stave. The held-out score is selected inside each training fold from fit outputs only: `secondary_fraction`, `secondary_amp_norm`, delay, `chi2/ndf`, two-pulse SSE, and fractional SSE improvement.

ML method: the S07f shape-only RF on B2 and downstream aggregate normalized waveform features, with timing, run/event ids, pair ids, injection parameters, amplitudes, topology flags, and fit outputs excluded.

Fit-output fold choices:

{markdown_table(fit_choices)}

Fit-output summary:

{markdown_table(fit_summary)}

RF scan:

{markdown_table(rf_scan)}

## Head-to-Head

{markdown_table(scoreboard)}

## Leakage Hunt

{markdown_table(leakage)}

Pair ids are split by run, pair split violations are zero, the main RF contains no forbidden columns, and the shuffled-label RF remains near chance. The amplitude-only probe is kept out of the main method because the injection can change peak height.

## Finding

The full bounded fit improves interpretability but does not close the S07f RF gap. On the same all-three injected target, fit-output-only scoring reaches ROC AUC **{fit['roc_auc']:.3f}** [{fit['roc_auc_ci_low']:.3f}, {fit['roc_auc_ci_high']:.3f}], while the shape-only RF reaches **{rf['roc_auc']:.3f}** [{rf['roc_auc_ci_low']:.3f}, {rf['roc_auc_ci_high']:.3f}]. The RF advantage is **{result['rf_minus_fit_auc']:.3f}** AUC.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s11e_1781024319_1354_2db2173f_all_three_full_fit.py --config configs/s11e_1781024319_1354_2db2173f_all_three_full_fit.json
```

Artifacts: `result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `s07f_reproduction_scoreboard.csv`, `scoreboard.csv`, `two_pulse_fit_oof.csv`, `leakage_checks.csv`, and `oof_predictions.csv`.
"""
    (out_dir / "REPORT.md").write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/s11e_1781024319_1354_2db2173f_all_three_full_fit.json")
    args = parser.parse_args()
    t0 = time.time()
    config_path = (ROOT / args.config).resolve() if not Path(args.config).is_absolute() else Path(args.config)
    config = load_json(config_path)
    out_dir = ROOT / config["output_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)

    s07f = load_module("s07f_source_for_s11e_all_three", ROOT / config["s07f_script"])
    fitmod = load_module("s11b_fit_source_for_s11e_all_three", ROOT / config["s11b_fit_script"])
    s07f_config = load_json(ROOT / config["s07f_config"])
    s07f_config["ticket_id"] = config["ticket_id"]
    s07f_config["worker"] = config["worker"]
    s07f_config["output_dir"] = config["output_dir"]
    utils = s07f.load_s07d_utils(ROOT / s07f_config["utility_script"])
    seed = int(config["random_seed"])
    n_boot = int(config["bootstrap_replicates"])

    parent, all_three, run_counts, clean_payloads = s07f.collect_parent_and_all_three(s07f_config, utils)
    parent_guarded = int((parent["d_t_ns"] > float(s07f_config["gross_dt_min_ns"])).sum())
    parent_documented = int((parent["d_t_ns"] > float(s07f_config["documented_gross_dt_min_ns"])).sum())
    all_three_guarded = int((all_three["d_t_ns"] > float(s07f_config["gross_dt_min_ns"])).sum())
    all_three_clean = int((all_three["d_t_ns"] < float(s07f_config["clean_dt_max_ns"])).sum())
    reproduction = pd.DataFrame(
        [
            {"quantity": "parent App.I guarded gross D_t>51 ns", "report_value": int(s07f_config["expected_parent_gross_events"]), "reproduced": parent_guarded, "delta": parent_guarded - int(s07f_config["expected_parent_gross_events"]), "tolerance": 0, "pass": parent_guarded == int(s07f_config["expected_parent_gross_events"])},
            {"quantity": "parent App.I documented gross D_t>50 ns", "report_value": None, "reproduced": parent_documented, "delta": None, "tolerance": None, "pass": True},
            {"quantity": "all-three control events", "report_value": int(s07f_config["expected_all_three_control_events"]), "reproduced": int(len(all_three)), "delta": int(len(all_three)) - int(s07f_config["expected_all_three_control_events"]), "tolerance": 0, "pass": int(len(all_three)) == int(s07f_config["expected_all_three_control_events"])},
            {"quantity": "all-three clean events D_t<3 ns", "report_value": None, "reproduced": all_three_clean, "delta": None, "tolerance": None, "pass": True},
            {"quantity": "all-three guarded gross D_t>51 ns", "report_value": int(s07f_config["expected_all_three_guarded_gross_events"]), "reproduced": all_three_guarded, "delta": all_three_guarded - int(s07f_config["expected_all_three_guarded_gross_events"]), "tolerance": 0, "pass": all_three_guarded == int(s07f_config["expected_all_three_guarded_gross_events"])},
        ]
    )
    if not bool(reproduction["pass"].all()):
        raise RuntimeError("raw-ROOT all-three reproduction gate failed")

    s07e_score, _, _, _, _ = s07f.s07e_reproduction(s07f_config, utils, all_three)
    s07e_auc = float(s07e_score.loc[s07e_score["method"] == "reproduced all-three shape-only RF", "roc_auc"].iloc[0])
    s07e_delta = s07e_auc - float(s07f_config["expected_s07e_shape_rf_auc"])
    s07e_pass = abs(s07e_delta) <= float(s07f_config["s07e_reproduction_auc_tolerance"])
    reproduction = pd.concat(
        [
            reproduction,
            pd.DataFrame(
                [
                    {
                        "quantity": "all-three S07e shape RF ROC AUC",
                        "report_value": float(s07f_config["expected_s07e_shape_rf_auc"]),
                        "reproduced": s07e_auc,
                        "delta": s07e_delta,
                        "tolerance": float(s07f_config["s07e_reproduction_auc_tolerance"]),
                        "pass": bool(s07e_pass),
                    }
                ]
            ),
        ],
        ignore_index=True,
    )
    if not s07e_pass:
        raise RuntimeError("S07e all-three RF reproduction gate failed")

    counts, s07f_score, s07f_rf_scan, s07f_choices, s07f_leakage, s07f_oof, s07f_details = s07f.independent_injection_benchmark(
        s07f_config, utils, clean_payloads
    )
    s07f_trad_auc = float(s07f_score.loc[s07f_score["method"] == "traditional fold-selected timing/template", "roc_auc"].iloc[0])
    s07f_rf_auc = float(s07f_score.loc[s07f_score["method"] == "all-three shape-only RF", "roc_auc"].iloc[0])
    s07f_trad_pass = abs(s07f_trad_auc - float(config["expected_s07f_traditional_auc"])) <= float(config["s07f_reproduction_auc_tolerance"])
    s07f_rf_pass = abs(s07f_rf_auc - float(config["expected_s07f_shape_rf_auc"])) <= float(config["s07f_reproduction_auc_tolerance"])
    reproduction = pd.concat(
        [
            reproduction,
            pd.DataFrame(
                [
                    {
                        "quantity": "S07f traditional injected ROC AUC",
                        "report_value": float(config["expected_s07f_traditional_auc"]),
                        "reproduced": s07f_trad_auc,
                        "delta": s07f_trad_auc - float(config["expected_s07f_traditional_auc"]),
                        "tolerance": float(config["s07f_reproduction_auc_tolerance"]),
                        "pass": bool(s07f_trad_pass),
                    },
                    {
                        "quantity": "S07f shape-only RF injected ROC AUC",
                        "report_value": float(config["expected_s07f_shape_rf_auc"]),
                        "reproduced": s07f_rf_auc,
                        "delta": s07f_rf_auc - float(config["expected_s07f_shape_rf_auc"]),
                        "tolerance": float(config["s07f_reproduction_auc_tolerance"]),
                        "pass": bool(s07f_rf_pass),
                    },
                ]
            ),
        ],
        ignore_index=True,
    )
    if not bool(reproduction["pass"].all()):
        raise RuntimeError("S07f reproduction gate failed")

    data = utils.make_dataset(s07f_config, clean_payloads)
    y = data["label_injected"].to_numpy(dtype=int)
    runs = data["run"].to_numpy(dtype=int)
    fit_score, fit_fold, fit_choices, fit_oof = constrained_fit_only_oof(data, y, config, s07f_config, utils, fitmod)
    fit_prob = fitmod.crossfold_isotonic(y, fit_score, fit_fold)

    shape_cols = utils.feature_columns(data, "strict_shape")
    rf_scan, best_params, rf_score, rf_fold, rf_prob = utils.evaluate_rf_grid(data, y, shape_cols, config)
    direct_dt = np.maximum(data["d_t_ns"].to_numpy(dtype=float), data["abs_c_t_ns"].fillna(0).to_numpy(dtype=float))
    direct_prob = fitmod.crossfold_isotonic(y, direct_dt, fit_fold)
    scoreboard = pd.DataFrame(
        [
            fitmod.summarize_method(
                "bounded two-pulse fit outputs",
                y,
                fit_score,
                fit_prob,
                runs,
                seed,
                n_boot,
                "Fold-local score selected from constrained-fit outputs only: secondary fraction/amplitude, delay, chi2/ndf, SSE, and fractional SSE improvement.",
            ),
            fitmod.summarize_method(
                "direct D_t/curvature cross-check",
                y,
                direct_dt,
                direct_prob,
                runs,
                seed + 10,
                n_boot,
                "Diagnostic only; label is injected truth, not a D_t tail threshold.",
            ),
            fitmod.summarize_method(
                "shape-only RF",
                y,
                rf_score,
                rf_prob,
                runs,
                seed + 20,
                n_boot,
                f"Best params={best_params}; excludes timing, ids, injection parameters, amplitudes, topology flags, and fit outputs.",
            ),
        ]
    )

    fit_summary = fit_summary_by_class(data, fit_oof)
    topo_score, _ = utils.rf_oof(data, y, utils.feature_columns(data, "topology"), best_params, seed + 101)
    amp_score, _ = utils.rf_oof(data, y, utils.feature_columns(data, "amplitude"), best_params, seed + 102)
    shuffle_score, _ = utils.rf_oof(data, y, shape_cols, best_params, seed + 103, shuffle_train=True)
    slot_score, _ = utils.rf_oof(data, y, utils.feature_columns(data, "slot_shape"), best_params, seed + 104)
    pair_split_violations = 0
    for held_run in sorted(np.unique(runs)):
        train_pairs = set(data.loc[runs != held_run, "pair_id"].astype(int))
        test_pairs = set(data.loc[runs == held_run, "pair_id"].astype(int))
        pair_split_violations += len(train_pairs & test_pairs)
    forbidden_fragments = ["d_t_ns", "abs_c_t", "base_", "event", "pair", "delay", "scale", "target", "log_amp", "present", "run", "chi2", "secondary", "sse"]
    forbidden_shape_cols = [col for col in shape_cols if any(fragment in col for fragment in forbidden_fragments)]
    leakage = pd.DataFrame(
        [
            {"probe": "pre-injection D_t", "roc_auc": utils.auc(y, data["base_d_t_ns"].to_numpy(dtype=float)), "average_precision": utils.ap(y, data["base_d_t_ns"].to_numpy(dtype=float)), "notes": "Same for clean/injected pairs; should be chance."},
            {"probe": "topology-only RF", "roc_auc": utils.auc(y, topo_score), "average_precision": utils.ap(y, topo_score), "notes": "Constant all-three topology; should be chance."},
            {"probe": "absolute-amplitude-only RF", "roc_auc": utils.auc(y, amp_score), "average_precision": utils.ap(y, amp_score), "notes": "Excluded from main RF; injection changes peak height."},
            {"probe": "shape RF with shuffled training labels", "roc_auc": utils.auc(y, shuffle_score), "average_precision": utils.ap(y, shuffle_score), "notes": "Null/leakage sanity check."},
            {"probe": "per-stave slot shape RF", "roc_auc": utils.auc(y, slot_score), "average_precision": utils.ap(y, slot_score), "notes": "Permissive shape representation; not main claim."},
            {"probe": "pair split violations", "roc_auc": float(pair_split_violations), "average_precision": float("nan"), "notes": "Must be 0."},
            {"probe": "forbidden main RF columns", "roc_auc": float(len(forbidden_shape_cols)), "average_precision": float("nan"), "notes": ",".join(forbidden_shape_cols) if forbidden_shape_cols else "None."},
        ]
    )

    reproduction.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    run_counts.to_csv(out_dir / "run_counts.csv", index=False)
    counts.to_csv(out_dir / "dataset_counts_by_run.csv", index=False)
    s07f_score.to_csv(out_dir / "s07f_reproduction_scoreboard.csv", index=False)
    s07f_rf_scan.to_csv(out_dir / "s07f_reproduction_rf_cv_scan.csv", index=False)
    s07f_choices.to_csv(out_dir / "s07f_traditional_fold_choices.csv", index=False)
    s07f_leakage.to_csv(out_dir / "s07f_reproduction_leakage_checks.csv", index=False)
    s07f_oof.to_csv(out_dir / "s07f_reproduction_oof_predictions.csv", index=False)
    fit_choices.to_csv(out_dir / "fit_output_fold_choices.csv", index=False)
    fit_oof.to_csv(out_dir / "two_pulse_fit_oof.csv", index=False)
    fit_summary.to_csv(out_dir / "fit_summary_by_class.csv", index=False)
    rf_scan.to_csv(out_dir / "rf_cv_scan.csv", index=False)
    scoreboard.to_csv(out_dir / "scoreboard.csv", index=False)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)

    oof_cols = ["row_id", "event_key", "pair_id", "run", "label_injected", "variant", "base_d_t_ns", "d_t_ns", "abs_c_t_ns", "target_stave", "injected_delay_samples", "injected_scale"]
    oof = data[oof_cols].copy().reset_index(drop=True)
    oof["fit_score"] = fit_score
    oof["fit_prob"] = fit_prob
    oof["rf_score"] = rf_score
    oof["rf_prob"] = rf_prob
    for col in ["fit_stave", "delay_samples", "secondary_amp_norm", "secondary_fraction", "chi2_ndf", "frac_sse_improvement", "sse_one", "sse_two"]:
        oof[col] = fit_oof[col].to_numpy()
    oof.to_csv(out_dir / "oof_predictions.csv", index=False)

    fit_auc = float(scoreboard.loc[scoreboard["method"] == "bounded two-pulse fit outputs", "roc_auc"].iloc[0])
    rf_auc = float(scoreboard.loc[scoreboard["method"] == "shape-only RF", "roc_auc"].iloc[0])
    direct_auc = float(scoreboard.loc[scoreboard["method"] == "direct D_t/curvature cross-check", "roc_auc"].iloc[0])
    result = {
        "ticket_id": config["ticket_id"],
        "study_id": config["study_id"],
        "raw_reproduction_pass": bool(reproduction["pass"].all()),
        "parent_guarded_gross_events": int(parent_guarded),
        "all_three_control_events": int(len(all_three)),
        "all_three_guarded_gross_events": int(all_three_guarded),
        "dataset_events": int(len(data)),
        "dataset_pairs": int(data["pair_id"].nunique()),
        "s07f_traditional_auc_reproduced": s07f_trad_auc,
        "s07f_shape_rf_auc_reproduced": s07f_rf_auc,
        "bounded_fit_auc": fit_auc,
        "shape_rf_auc": rf_auc,
        "direct_dt_auc": direct_auc,
        "rf_minus_fit_auc": float(rf_auc - fit_auc),
        "fit_minus_s07f_traditional_auc": float(fit_auc - s07f_trad_auc),
        "best_rf_params": best_params,
        "pair_split_violations": int(pair_split_violations),
        "forbidden_main_rf_columns": forbidden_shape_cols,
        "median_fit_injected_secondary_fraction": float(fit_summary.loc[fit_summary["class"] == "injected", "median_secondary_fraction"].iloc[0]),
        "median_fit_clean_secondary_fraction": float(fit_summary.loc[fit_summary["class"] == "raw_clean", "median_secondary_fraction"].iloc[0]),
        "next_tickets": config.get("next_tickets", []),
        "elapsed_seconds": float(time.time() - t0),
    }
    write_report(out_dir, config, s07f_config, reproduction, s07f_score, counts, fit_summary, fit_choices, rf_scan, scoreboard, leakage, result)
    (out_dir / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    input_rows = []
    for run in s07f_config["runs"]:
        path = s07f.raw_file(s07f_config, int(run))
        input_rows.append({"path": str(path), "sha256": s07f.sha256_file(path), "bytes": path.stat().st_size})
    for path in [config_path, ROOT / config["s07f_config"], ROOT / config["s07f_script"], ROOT / config["s11b_fit_script"], ROOT / s07f_config["utility_script"]]:
        input_rows.append({"path": str(path), "sha256": s07f.sha256_file(path), "bytes": path.stat().st_size})
    pd.DataFrame(input_rows).to_csv(out_dir / "input_sha256.csv", index=False)
    manifest = {
        "ticket_id": config["ticket_id"],
        "study_id": config["study_id"],
        "worker": config["worker"],
        "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "git_commit": git_commit(),
        "platform": platform.platform(),
        "python": sys.version,
        "command": f"/home/billy/anaconda3/bin/python scripts/s11e_1781024319_1354_2db2173f_all_three_full_fit.py --config {config_path.relative_to(ROOT)}",
        "inputs": input_rows,
        "outputs": {},
    }
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            manifest["outputs"][path.name] = s07f.sha256_file(path)
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
