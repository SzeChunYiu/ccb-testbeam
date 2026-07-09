#!/usr/bin/env python3
"""P08e: truth-anchored PID action-band closure.

The experimental ROOT files do not contain particle truth. This ticket-local
study therefore uses the externally motivated beamline/range proxy documented in
the analysis notes: terminal high-ionisation B2 events are deuteron-enriched,
whereas B2 events with downstream B4/B6/B8 support are proton-enriched. The proxy
is deliberately treated as an enriched action-band closure target, not a PID
adoption label.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Optional

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
P08D_PATH = ROOT / "scripts/p08d_1781072388_710_65f565af_depth_matched_pulse_shape_pid_null.py"
DEFAULT_CONFIG = ROOT / "configs/p08e_1781155463_1105_04ad315d_truth_anchored_pid_action_band_closure.json"


def import_p08d():
    spec = importlib.util.spec_from_file_location("p08d_depth_matched_pid_null", str(P08D_PATH))
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["p08d_depth_matched_pid_null"] = module
    spec.loader.exec_module(module)
    return module


P08D = import_p08d()


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return "unknown"


def clean_json(value):
    if isinstance(value, dict):
        return {str(k): clean_json(v) for k, v in value.items()}
    if isinstance(value, list):
        return [clean_json(v) for v in value]
    if isinstance(value, tuple):
        return [clean_json(v) for v in value]
    if isinstance(value, np.ndarray):
        return clean_json(value.tolist())
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        v = float(value)
        return v if math.isfinite(v) else None
    return value


def load_config(path: Path) -> dict:
    cfg = P08D.load_config(path)
    cfg["config_path"] = str(path)
    return cfg


def add_beamline_proxy_labels(meta: pd.DataFrame, config: dict, out_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    cfg = config["beamline_proxy"]
    out = meta.copy()
    out["weak_label"] = np.nan
    out["proxy_label_family"] = "unlabeled_middle_support"
    support_rows = []
    q = float(cfg["terminal_b2_area_quantile"])
    min_class = int(cfg["min_atom_class_rows"])
    for run, grp in out.groupby("run", sort=True):
        terminal = (grp["depth_idx"].to_numpy(dtype=int) == int(cfg["terminal_depth_idx"])) & (
            grp["downstream_selected"].to_numpy(dtype=int) == 0
        )
        penetrating = (grp["depth_idx"].to_numpy(dtype=int) >= int(cfg["penetrating_min_depth_idx"])) & (
            grp["downstream_charge_fraction"].to_numpy(dtype=float) >= float(cfg["penetrating_min_downstream_charge_fraction"])
        )
        if terminal.sum() == 0 or penetrating.sum() == 0:
            continue
        area_cut = float(np.nanquantile(grp.loc[terminal, "b2_area"].to_numpy(dtype=float), q))
        pos_idx = grp.index[terminal & (grp["b2_area"].to_numpy(dtype=float) >= area_cut)]
        neg_idx = grp.index[penetrating]
        n = min(len(pos_idx), len(neg_idx))
        if n < min_class:
            continue
        pos_take = pos_idx[:n]
        neg_take = neg_idx[:n]
        out.loc[pos_take, "weak_label"] = 1
        out.loc[pos_take, "proxy_label_family"] = cfg["positive_name"]
        out.loc[neg_take, "weak_label"] = 0
        out.loc[neg_take, "proxy_label_family"] = cfg["negative_name"]
        support_rows.append(
            {
                "run": int(run),
                "positive_rows": int(n),
                "negative_rows": int(n),
                "terminal_available": int(terminal.sum()),
                "penetrating_available": int(penetrating.sum()),
                "terminal_b2_area_cut": area_cut,
            }
        )
    labeled = out.dropna(subset=["weak_label"]).copy().reset_index(drop=True)
    labeled["weak_label"] = labeled["weak_label"].astype(np.int8)
    labeled["weak_label_name"] = labeled["proxy_label_family"]
    support = pd.DataFrame(support_rows)
    support.to_csv(out_dir / "beamline_proxy_label_support.csv", index=False)
    labeled.groupby(["run", "weak_label_name"]).size().reset_index(name="n").to_csv(
        out_dir / "beamline_proxy_label_counts_by_run.csv", index=False
    )
    if labeled.empty:
        raise RuntimeError("No beamline-proxy labels survived support cuts")
    return labeled, support


def table(df: pd.DataFrame, cols: list[str], max_rows: int = 80) -> str:
    if df.empty:
        return "_No rows._"
    return df.loc[:, cols].head(max_rows).to_markdown(index=False)


def ci_pair(row: pd.Series, prefix: str) -> str:
    lo = row.get(prefix + "_ci_low")
    hi = row.get(prefix + "_ci_high")
    if pd.isna(lo) or pd.isna(hi):
        return ""
    return f" [{lo:.4f}, {hi:.4f}]"


def write_report(
    out_dir: Path,
    config: dict,
    result: dict,
    reproduction: pd.DataFrame,
    proxy_support: pd.DataFrame,
    audit: pd.DataFrame,
    composition: pd.DataFrame,
    scoreboard: pd.DataFrame,
    deltas: pd.DataFrame,
) -> None:
    main_methods = [
        "traditional_charge_depth_logistic",
        "ML_ridge_waveform",
        "ML_gradient_boosted_trees",
        "ML_mlp",
        "NN_1d_cnn",
        "NN_action_gated_residual_ensemble_new",
    ]
    main_scores = scoreboard[
        scoreboard["method"].isin(main_methods)
        & scoreboard["action_mask"].isin(
            [
                "all_pre_action",
                "p04s_dropout_phase_accept",
                "s14g_traditional_accept",
                "s14g_new_residual_accept",
                "p07j_traditional_correct",
                "s14g_traditional_and_p04s_accept",
                "s14g_traditional_p04s_and_p07j_correct",
            ]
        )
    ].copy()
    winner = result["winner"]
    report = f"""# P08e: Truth-Anchored PID Action-Band Closure

**Ticket:** `{config['ticket_id']}`  
**Worker:** `{config['worker']}`  
**Date:** 2026-07-10  
**Raw ROOT directory:** `{result['raw_root_dir']}`  
**Config:** `{config['config_path']}`  
**Git commit:** `{result['git_commit_at_run']}`

## Abstract

This study repeats the P08d action-mask stability test on an externally anchored
PID proxy rather than on the P08b duplicate-readout weak label. The experimental
ROOT files do not contain event-level particle truth, so the target is a
beamline/range enriched proxy: terminal, high-ionisation B2 events define a
deuteron-enriched class and downstream-penetrating B2+B4/B6/B8 events define a
proton-enriched class. The target is therefore suitable for action-band closure
and model ranking, but it is not a hidden truth PID label.

The named `result.json` winner is **{winner['method']}** on the pre-action
run-held-out benchmark, with ROC AUC {winner['roc_auc']:.4f}
[{winner['roc_auc_ci'][0]:.4f}, {winner['roc_auc_ci'][1]:.4f}], average precision
{winner['average_precision']:.4f}, and ECE {winner['ece']:.4f}. The strongest
traditional comparator is `traditional_charge_depth_logistic`; all ML/NN gains
are interpreted relative to that range-telescope baseline and to the action-only
control.

## 1. Raw-ROOT Reproduction Gate

For every configured B-stack run, the script reads raw `h101/HRDv`, reshapes each
event into 8 channels by 18 samples, subtracts the median of samples 0--3, and
counts B2/B4/B6/B8 selected pulses with even-readout amplitude above 1000 ADC.
The benchmark is blocked unless these counts reproduce the canonical report
numbers exactly:

{reproduction.to_markdown(index=False)}

## 2. Beamline Proxy Label

Let `d_i` be the deepest selected B-stave for event `i`, `f_i` the downstream
charge fraction in B4+B6+B8, and `A_i` the B2 positive charge. Within each run,
the positive proxy is

`y_i = 1` if `d_i = 0`, no downstream stave is selected, and
`A_i >= Q_run,{config['beamline_proxy']['terminal_b2_area_quantile']:.2f}(A | d=0)`.

The negative proxy is

`y_i = 0` if `d_i >= 1` and `f_i >= {config['beamline_proxy']['penetrating_min_downstream_charge_fraction']:.3f}`.

Each run is class-balanced by truncating to the smaller class. This creates an
externally motivated, run-local enriched proxy while avoiding a pure Sample I-vs-II
run-family label.

{table(proxy_support, ['run', 'positive_rows', 'negative_rows', 'terminal_available', 'penetrating_available', 'terminal_b2_area_cut'], max_rows=80)}

## 3. Action-Band Inputs

S14g and P07j action decisions are merged by `(run,eventno)`. The missing P04s
dropout-phase action band is reconstructed from raw B2 waveform features with
leave-one-run-held-out thresholds on downward steps, late-tail excess,
final-sample dropout, abnormal width, and edge-phase peaks.

{table(audit, ['source', 'available', 'rows_loaded', 'note'] if 'note' in audit.columns else ['source', 'available', 'rows_loaded'])}

## 4. Methods

The traditional comparator is a class-balanced logistic range-telescope model,

`logit p(y=1|z) = beta_0 + beta^T z`,

where `z` contains depth, multiplicity, topology, downstream charge fraction,
PSTAR calibrated even-readout residuals, B2/B4/B6/B8 charges, and saturation
flags. This is intentionally strong because the proxy itself is range/ionisation
anchored.

The learned panel uses complete held-out runs for evaluation:

- `ML_ridge_waveform`: L2 linear waveform classifier with probability calibration.
- `ML_gradient_boosted_trees`: histogram GBT on normalized waveform and hand-shape features.
- `ML_mlp`: two-layer ReLU classifier on the same waveform/shape panel.
- `NN_1d_cnn`: compact temporal CNN on the 18 normalized B2 samples.
- `NN_action_gated_residual_ensemble_new`: ticket-local architecture that concatenates
  waveform shape, calibrated charge residuals, and action-mask indicators in a
  residual HGB gate.

Controls include charge-only, depth-only, action-only, run-family-only, and
shuffled-label probes.

## 5. Metrics

Metrics are computed on out-of-fold predictions from complete held-out runs.
Confidence intervals resample complete runs with replacement. The expected
calibration error is

`ECE = sum_b (n_b/N) | mean(y_b) - mean(p_b) |`,

and fixed-efficiency purity uses the score threshold retaining 80% of positive
proxy labels.

## 6. Action-Mask Composition

{table(composition.sort_values('support_fraction', ascending=False), ['action_mask', 'n', 'support_fraction', 'support_loss', 'positive_fraction', 'action_band_label_shift', 'charge_log_median_shift', 'depth_mean_shift', 'runs'])}

## 7. Main Benchmark

{table(main_scores.sort_values(['action_mask', 'roc_auc'], ascending=[True, False]), ['action_mask', 'method', 'n', 'roc_auc', 'roc_auc_ci_low', 'roc_auc_ci_high', 'average_precision', 'purity_at_80pct_eff', 'ece'], max_rows=100)}

## 8. ML Minus Traditional

{table(deltas.sort_values(['action_mask', 'roc_auc_minus_traditional'], ascending=[True, False]), ['action_mask', 'method', 'roc_auc_minus_traditional', 'average_precision_minus_traditional', 'purity_at_80pct_eff_minus_traditional', 'ece_minus_traditional'], max_rows=100)}

## 9. Systematics And Caveats

- The target is an enriched beamline/range proxy, not event-level truth. It can
  close action-band behavior but cannot authorize PID adoption by itself.
- Because the positive proxy is terminal high-ionisation B2 and the negative
  proxy is downstream penetration, the traditional range-telescope comparator is
  expected to be very strong. ML wins must beat that baseline and pass controls.
- The reconstructed P04s band is transparent and train-run thresholded, but it is
  not a byte-identical canonical P04s artifact.
- Run-block bootstrap intervals quantify sensitivity to the available runs, not
  to future detector configurations or material-budget alternatives.
- Action masks can change class composition. Support loss, charge shift, and
  depth shift are therefore reported as systematics, not merely as efficiency.

## 10. Verdict

{result['finding']}

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/p08e_1781155463_1105_04ad315d_truth_anchored_pid_action_band_closure.py --config configs/p08e_1781155463_1105_04ad315d_truth_anchored_pid_action_band_closure.json
```

Artifacts: `result.json`, `manifest.json`, `input_sha256.csv`,
`reproduction_match_table.csv`, `beamline_proxy_label_support.csv`,
`beamline_proxy_label_counts_by_run.csv`, `benchmark_balanced_counts.csv`,
`action_source_audit.csv`, `action_mask_composition.csv`, `scoreboard_by_mask.csv`,
`ml_minus_traditional.csv`, `fold_summary.csv`, and `oof_pid_scores.csv.gz`.
"""
    (out_dir / "REPORT.md").write_text(report, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    t0 = time.time()
    config = load_config(args.config)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    waves, meta, counts_by_run, counts_by_group, reproduction, calibration, raw_dir = P08D.load_p08b_population(config, out_dir)
    labeled, proxy_support = add_beamline_proxy_labels(meta, config, out_dir)
    labeled, audit = P08D.merge_action_bands(labeled, config, out_dir)
    sample_idx = P08D.balanced_indices(labeled, config)
    bench = P08D.add_sample_columns(labeled.loc[sample_idx].reset_index(drop=True), waves)
    bench.groupby(["run", "weak_label_name"]).size().reset_index(name="n").to_csv(out_dir / "benchmark_balanced_counts.csv", index=False)

    pred, folds = P08D.fit_oof_scores(bench, config, out_dir)
    composition, scoreboard, deltas = P08D.summarize_masks(bench, pred, config, out_dir)

    nominal = scoreboard[scoreboard["action_mask"] == "all_pre_action"].copy()
    primary_methods = [
        "traditional_charge_depth_logistic",
        "ML_ridge_waveform",
        "ML_gradient_boosted_trees",
        "ML_mlp",
        "NN_1d_cnn",
        "NN_action_gated_residual_ensemble_new",
    ]
    primary = nominal[nominal["method"].isin(primary_methods)].sort_values(
        ["roc_auc", "average_precision"], ascending=False
    )
    winner_row = primary.iloc[0]
    trad = nominal[nominal["method"] == "traditional_charge_depth_logistic"].iloc[0]
    action_only = nominal[nominal["method"] == "control_action_only"].iloc[0]
    run_family = nominal[nominal["method"] == "control_run_family_only"].iloc[0]
    shuffled = nominal[nominal["method"] == "control_shuffled_label_hgb"].iloc[0]
    strongest_ml = primary[primary["method"] != "traditional_charge_depth_logistic"].iloc[0]
    finding = (
        "The pre-action beamline-proxy winner is {winner} with AUC {auc:.4f}; "
        "the strong traditional range-telescope comparator has AUC {trad_auc:.4f}. "
        "The best learned-minus-traditional AUC delta is {delta:.4f} for {ml}. "
        "Action-only AUC is {action_auc:.4f}, run-family-only AUC is {run_auc:.4f}, "
        "and shuffled-label AUC is {shuffle_auc:.4f}. The result closes the action-band "
        "stability check for an externally anchored enriched proxy, but it remains "
        "below the standard for a PID adoption claim because no event-level data truth exists."
    ).format(
        winner=str(winner_row["method"]),
        auc=float(winner_row["roc_auc"]),
        trad_auc=float(trad["roc_auc"]),
        delta=float(strongest_ml["roc_auc"] - trad["roc_auc"]),
        ml=str(strongest_ml["method"]),
        action_auc=float(action_only["roc_auc"]),
        run_auc=float(run_family["roc_auc"]),
        shuffle_auc=float(shuffled["roc_auc"]),
    )

    input_rows = []
    p08b_config = P08D.P08B.load_config(Path(config["p08b_config"]))
    for run in P08D.P08B.configured_runs(p08b_config):
        path = P08D.P08B.raw_file(raw_dir, run)
        input_rows.append({"file": str(path), "sha256": P08D.sha256_file(path), "bytes": int(path.stat().st_size)})
    pd.DataFrame(input_rows).to_csv(out_dir / "input_sha256.csv", index=False)

    result = {
        "ticket_id": config["ticket_id"],
        "worker": config["worker"],
        "study_id": config["study_id"],
        "title": config["title"],
        "raw_root_dir": str(raw_dir),
        "git_commit_at_run": git_commit(),
        "reproduction": {"passed": bool(reproduction["pass"].all()), "table": reproduction.to_dict(orient="records")},
        "beamline_proxy": config["beamline_proxy"],
        "beamline_proxy_support": {
            "n_labeled_rows": int(len(labeled)),
            "n_runs": int(labeled["run"].nunique()),
            "support_rows": proxy_support.to_dict(orient="records"),
        },
        "benchmark": {
            "evaluated_rows": int(len(bench)),
            "evaluated_runs": [int(x) for x in sorted(bench["run"].unique())],
            "split": "leave-one-run-out by complete run",
            "bootstrap_replicates": int(config["benchmark"]["bootstrap_replicates"]),
            "fixed_efficiency": float(config["benchmark"]["fixed_efficiency"]),
        },
        "action_source_audit": audit.to_dict(orient="records"),
        "action_mask_composition": composition.to_dict(orient="records"),
        "winner_method": str(winner_row["method"]),
        "winner": {
            "action_mask": str(winner_row["action_mask"]),
            "method": str(winner_row["method"]),
            "roc_auc": float(winner_row["roc_auc"]),
            "roc_auc_ci": [float(winner_row["roc_auc_ci_low"]), float(winner_row["roc_auc_ci_high"])],
            "average_precision": float(winner_row["average_precision"]),
            "purity_at_80pct_eff": float(winner_row["purity_at_80pct_eff"]),
            "ece": float(winner_row["ece"]),
        },
        "traditional": {
            "method": "traditional_charge_depth_logistic",
            "roc_auc": float(trad["roc_auc"]),
            "roc_auc_ci": [float(trad["roc_auc_ci_low"]), float(trad["roc_auc_ci_high"])],
            "average_precision": float(trad["average_precision"]),
            "ece": float(trad["ece"]),
        },
        "best_ml_vs_traditional": {
            "method": str(strongest_ml["method"]),
            "roc_auc_minus_traditional": float(strongest_ml["roc_auc"] - trad["roc_auc"]),
            "ap_minus_traditional": float(strongest_ml["average_precision"] - trad["average_precision"]),
        },
        "controls": {
            "action_only_auc": float(action_only["roc_auc"]),
            "run_family_only_auc": float(run_family["roc_auc"]),
            "shuffled_label_auc": float(shuffled["roc_auc"]),
        },
        "finding": finding,
        "next_tickets": [],
        "runtime_sec": round(time.time() - t0, 1),
        "command": "/home/billy/anaconda3/bin/python scripts/p08e_1781155463_1105_04ad315d_truth_anchored_pid_action_band_closure.py --config {}".format(args.config),
    }
    (out_dir / "result.json").write_text(json.dumps(clean_json(result), indent=2) + "\n", encoding="utf-8")
    write_report(out_dir, config, result, reproduction, proxy_support, audit, composition, scoreboard, deltas)
    manifest = {
        "ticket_id": config["ticket_id"],
        "script": "scripts/p08e_1781155463_1105_04ad315d_truth_anchored_pid_action_band_closure.py",
        "config": str(args.config),
        "python": platform.python_version(),
        "git_commit": git_commit(),
        "raw_root_dir": str(raw_dir),
        "reproduction_passed": bool(reproduction["pass"].all()),
        "artifacts": P08D.output_manifest(out_dir),
    }
    (out_dir / "manifest.json").write_text(json.dumps(clean_json(manifest), indent=2) + "\n", encoding="utf-8")
    print("P08e complete: winner={}".format(result["winner_method"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
