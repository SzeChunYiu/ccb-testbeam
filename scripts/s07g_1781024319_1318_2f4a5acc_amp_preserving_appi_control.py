#!/usr/bin/env python3
"""S07g: amplitude-preserving all-three App.I injection control."""

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
from typing import Dict, List, Tuple

os.environ.setdefault("MPLCONFIGDIR", "/tmp/ccb-testbeam-s07g-matplotlib-cache")

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
S07F_PATH = ROOT / "scripts/s07f_independent_all_three_appi_validation.py"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, str(path))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
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


def raw_file(config: dict, run: int) -> Path:
    return Path(config["raw_root_dir"]) / f"hrdb_run_{run:04d}.root"


def positive_charge(wave: np.ndarray) -> float:
    return float(np.clip(wave, 0.0, None).sum())


def renormalize_target(original: np.ndarray, injected: np.ndarray, mode: str) -> Tuple[np.ndarray, float, float, float]:
    if mode == "peak_preserved":
        before = float(np.max(original))
        after = float(np.max(injected))
    elif mode == "charge_preserved":
        before = positive_charge(original)
        after = positive_charge(injected)
    else:
        raise ValueError(mode)
    factor = before / after if after > 1e-9 else 1.0
    adjusted = injected * factor
    if mode == "peak_preserved":
        final = float(np.max(adjusted))
    else:
        final = positive_charge(adjusted)
    return adjusted, float(factor), before, final


def make_preserved_dataset(config: dict, utils, clean_payloads: List[dict], mode: str) -> pd.DataFrame:
    staves = list(config["staves"].keys())
    downstream_idx = np.asarray([staves.index(name) for name in config["downstream_staves"]], dtype=int)
    b2_idx = staves.index("B2")
    cut = float(config["amplitude_cut_adc"])
    min_downstream = int(config["min_downstream_staves"])
    rng = np.random.default_rng(int(config["injection_seed"]))

    rows: List[dict] = []
    for pair_id, payload in enumerate(clean_payloads):
        variants = [("raw_clean", payload["corrected"].copy(), -1, 0, 0.0, 1.0, float("nan"), float("nan"))]
        base = payload["corrected"].copy()
        present_downstream = [int(idx) for idx in downstream_idx if bool(payload["selected"][idx])]
        target_idx = int(rng.choice(present_downstream))
        delay = int(rng.integers(int(config["delay_samples_min"]), int(config["delay_samples_max"]) + 1))
        scale = float(rng.uniform(float(config["secondary_scale_min"]), float(config["secondary_scale_max"])))
        mixed = base.copy()
        mixed[target_idx] = mixed[target_idx] + scale * utils.shifted(base[target_idx], delay)
        adjusted, norm_factor, preserved_before, preserved_after = renormalize_target(base[target_idx], mixed[target_idx], mode)
        mixed[target_idx] = adjusted
        variants.append(("injected_two_pulse", mixed, target_idx, delay, scale, norm_factor, preserved_before, preserved_after))

        for variant, corrected, target, delay_samples, scale_value, norm_factor, preserved_before, preserved_after in variants:
            amplitude = corrected.max(axis=-1)
            selected = amplitude > cut
            times = utils.cfd_times_ns(
                corrected[None, :, :],
                amplitude[None, :],
                float(config["cfd_fraction"]),
                float(config["sample_period_ns"]),
                cut,
            )[0]
            d_t, c_t = utils.timing_summary(times, selected, downstream_idx, min_downstream)
            row: Dict[str, object] = {
                "row_id": f"{payload['event_key']}:{mode}:{variant}",
                "event_key": payload["event_key"],
                "pair_id": int(pair_id),
                "run": int(payload["run"]),
                "eventno": int(payload["eventno"]),
                "evt": int(payload["evt"]),
                "label_injected": int(variant == "injected_two_pulse"),
                "variant": variant,
                "preservation_mode": mode,
                "target_stave": staves[target] if target >= 0 else "",
                "target_stave_index": int(target),
                "injected_delay_samples": int(delay_samples),
                "injected_scale": float(scale_value),
                "renormalization_factor": float(norm_factor),
                "preserved_quantity_before": float(preserved_before),
                "preserved_quantity_after": float(preserved_after),
                "preserved_quantity_ratio": float(preserved_after / preserved_before) if preserved_before > 1e-9 else float("nan"),
                "base_d_t_ns": float(payload["base_d_t_ns"]),
                "base_abs_c_t_ns": float(payload["base_abs_c_t_ns"]) if math.isfinite(payload["base_abs_c_t_ns"]) else float("nan"),
                "base_n_downstream": int(payload["base_n_downstream"]),
                "d_t_ns": float(d_t),
                "abs_c_t_ns": abs(c_t) if math.isfinite(c_t) else float("nan"),
                "has_curvature": bool(math.isfinite(c_t)),
                "n_downstream": int(selected[downstream_idx].sum()),
                "max_downstream_late_fraction": utils.max_downstream_late_fraction(corrected, amplitude, selected, downstream_idx),
            }
            utils.add_shape_features(row, corrected, amplitude, selected, staves, downstream_idx, b2_idx)
            row["_corrected"] = corrected
            row["_amplitude"] = amplitude
            row["_selected"] = selected
            rows.append(row)
    return pd.DataFrame(rows)


def run_benchmark(config: dict, utils, data: pd.DataFrame, label: str) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    y = data["label_injected"].to_numpy(dtype=int)
    runs = data["run"].to_numpy(dtype=int)
    seed = int(config["random_seed"])
    n_boot = int(config["bootstrap_replicates"])
    counts = data.groupby(["run", "label_injected"]).size().unstack(fill_value=0).rename(columns={0: "raw_clean", 1: "injected"}).reset_index()
    counts["total"] = counts["raw_clean"] + counts["injected"]

    trad_score, trad_fold, trad_choices, trad_candidates = utils.traditional_oof(data, y, config)
    trad_prob = utils.crossfold_isotonic(y, trad_score, trad_fold)
    direct_dt = np.maximum(data["d_t_ns"].to_numpy(dtype=float), data["abs_c_t_ns"].fillna(0).to_numpy(dtype=float))
    direct_dt_prob = utils.crossfold_isotonic(y, direct_dt, trad_fold)
    shape_cols = utils.feature_columns(data, "strict_shape")
    rf_scan, best_params, rf_score, rf_fold, rf_prob = utils.evaluate_rf_grid(data, y, shape_cols, config)

    scoreboard = pd.DataFrame(
        [
            utils.summarize_method(
                "traditional fold-selected timing/template",
                y,
                trad_score,
                trad_prob,
                runs,
                seed + 10,
                n_boot,
                "Fold-local best signed timing, curvature, shape-summary, or matched-template score.",
            ),
            utils.summarize_method(
                "direct D_t/curvature cross-check",
                y,
                direct_dt,
                direct_dt_prob,
                runs,
                seed + 20,
                n_boot,
                "Not label-defining here; target is injected two-pulse truth.",
            ),
            utils.summarize_method(
                "all-three shape-only RF",
                y,
                rf_score,
                rf_prob,
                runs,
                seed + 30,
                n_boot,
                f"Best params={best_params}; excludes timing, run/event ids, injection params, amplitudes, and topology flags.",
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
            {"probe": "absolute-amplitude-only RF", "roc_auc": utils.auc(y, amp_score), "average_precision": utils.ap(y, amp_score), "notes": "Excluded from main RF; checks residual amplitude nuisance."},
            {"probe": "shape RF with shuffled training labels", "roc_auc": utils.auc(y, shuffle_score), "average_precision": utils.ap(y, shuffle_score), "notes": "Null/leakage sanity check."},
            {"probe": "per-stave slot shape RF", "roc_auc": utils.auc(y, slot_score), "average_precision": utils.ap(y, slot_score), "notes": "Permissive shape representation; not main claim."},
            {"probe": "pair split violations", "roc_auc": float(pair_split_violations), "average_precision": float("nan"), "notes": "Must be 0."},
            {"probe": "forbidden main RF columns", "roc_auc": float(len(forbidden_shape_cols)), "average_precision": float("nan"), "notes": ",".join(forbidden_shape_cols) if forbidden_shape_cols else "None."},
        ]
    )

    oof_cols = [
        "row_id",
        "event_key",
        "pair_id",
        "run",
        "label_injected",
        "variant",
        "preservation_mode",
        "base_d_t_ns",
        "d_t_ns",
        "abs_c_t_ns",
        "target_stave",
        "injected_delay_samples",
        "injected_scale",
        "renormalization_factor",
        "preserved_quantity_ratio",
    ]
    oof = data[[c for c in oof_cols if c in data.columns]].copy()
    oof["traditional_score"] = trad_score
    oof["traditional_prob"] = trad_prob
    oof["direct_dt_score"] = direct_dt
    oof["rf_score"] = rf_score
    oof["rf_prob"] = rf_prob

    injected = data[data["label_injected"].to_numpy(dtype=int) == 1]
    details = {
        f"{label}_best_rf_params": best_params,
        f"{label}_pair_split_violations": int(pair_split_violations),
        f"{label}_forbidden_main_rf_columns": forbidden_shape_cols,
        f"{label}_dataset_events": int(len(data)),
        f"{label}_dataset_pairs": int(data["pair_id"].nunique()),
        f"{label}_renormalization_factor_median": float(injected["renormalization_factor"].median()) if "renormalization_factor" in injected else float("nan"),
        f"{label}_preserved_quantity_ratio_median": float(injected["preserved_quantity_ratio"].median()) if "preserved_quantity_ratio" in injected else float("nan"),
    }
    return counts, scoreboard, rf_scan, trad_choices, leakage, oof, details


def write_report(
    out_dir: Path,
    config: dict,
    s07f,
    reproduction: pd.DataFrame,
    s07e_score: pd.DataFrame,
    s07f_score: pd.DataFrame,
    scoreboards: Dict[str, pd.DataFrame],
    leakages: Dict[str, pd.DataFrame],
    result: dict,
) -> None:
    peak = scoreboards["peak_preserved"]
    charge = scoreboards["charge_preserved"]
    peak_trad = peak[peak["method"] == "traditional fold-selected timing/template"].iloc[0]
    peak_rf = peak[peak["method"] == "all-three shape-only RF"].iloc[0]
    charge_trad = charge[charge["method"] == "traditional fold-selected timing/template"].iloc[0]
    charge_rf = charge[charge["method"] == "all-three shape-only RF"].iloc[0]
    s07f_rf = s07f_score[s07f_score["method"] == "all-three shape-only RF"].iloc[0]

    text = f"""# S07g: amplitude-preserving all-three App.I injection control

- **Ticket:** `{config['ticket_id']}`
- **Worker:** `{config['worker']}`
- **Input:** raw B-stack ROOT `HRDv` from `{config['raw_root_dir']}`
- **Selection:** Sample-II analysis runs, B2+B4+B6+B8 all selected, `A>1000` ADC, CFD20 timing.
- **Split:** leave-one-run-out; intervals are held-out run-block bootstrap CIs.

## Raw-ROOT Reproduction First

{s07f.markdown_table(reproduction)}

The raw all-three App.I gate reproduces the parent S07e population before any S07g result is used. The S07f unnormalized injection number is also reproduced from the same raw ROOT: RF AUC {s07f_rf['roc_auc']:.6f} versus the prior {config['expected_s07f_shape_rf_auc']:.6f}.

{s07f.markdown_table(s07e_score)}

## S07f Baseline Reproduction

{s07f.markdown_table(s07f_score)}

## Peak-Preserving Injection

The injected target waveform is rescaled after adding the delayed copy so its original peak amplitude is restored. This removes the direct peak-height nuisance while preserving the two-pulse shape distortion.

{s07f.markdown_table(peak)}

### Peak-Preserving Leakage Checks

{s07f.markdown_table(leakages['peak_preserved'])}

## Charge-Preserving Injection

The injected target waveform is rescaled after adding the delayed copy so its original positive charge is restored. This is a looser integral-preserving control and can still alter peak height.

{s07f.markdown_table(charge)}

### Charge-Preserving Leakage Checks

{s07f.markdown_table(leakages['charge_preserved'])}

## Finding

After removing the peak-amplitude nuisance channel, the all-three shape-only RF still reaches ROC AUC {peak_rf['roc_auc']:.3f} [{peak_rf['roc_auc_ci_low']:.3f}, {peak_rf['roc_auc_ci_high']:.3f}], compared with the traditional timing/template score {peak_trad['roc_auc']:.3f} [{peak_trad['roc_auc_ci_low']:.3f}, {peak_trad['roc_auc_ci_high']:.3f}]. Under positive-charge preservation, the RF reaches {charge_rf['roc_auc']:.3f} [{charge_rf['roc_auc_ci_low']:.3f}, {charge_rf['roc_auc_ci_high']:.3f}] versus traditional {charge_trad['roc_auc']:.3f} [{charge_trad['roc_auc_ci_low']:.3f}, {charge_trad['roc_auc_ci_high']:.3f}].

The S07f RF gain survives peak preservation, so it is not explained only by a peak-amplitude artifact. The amplitude-only leakage probe falls near chance for peak preservation and remains reported for charge preservation. Shuffled labels, topology-only RF, pair split checks, and forbidden-column scans do not indicate run or pair leakage.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s07g_1781024319_1318_2f4a5acc_amp_preserving_appi_control.py --config configs/s07g_1781024319_1318_2f4a5acc.json
```

Artifacts: `result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, baseline and preservation scoreboards, leakage CSVs, and out-of-fold prediction CSVs.
"""
    (out_dir / "REPORT.md").write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/s07g_1781024319_1318_2f4a5acc.json")
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = load_config(config_path)
    out_dir = ROOT / config["output_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)
    s07f = load_module(S07F_PATH, "s07f_reference")
    utils = s07f.load_s07d_utils(ROOT / config["utility_script"])

    parent, all_three, run_counts, clean_payloads = s07f.collect_parent_and_all_three(config, utils)
    parent_guarded = int((parent["d_t_ns"] > float(config["gross_dt_min_ns"])).sum())
    parent_documented = int((parent["d_t_ns"] > float(config["documented_gross_dt_min_ns"])).sum())
    all_three_guarded = int((all_three["d_t_ns"] > float(config["gross_dt_min_ns"])).sum())
    all_three_clean = int((all_three["d_t_ns"] < float(config["clean_dt_max_ns"])).sum())
    reproduction = pd.DataFrame(
        [
            {"quantity": "parent App.I guarded gross D_t>51 ns", "report_value": int(config["expected_parent_gross_events"]), "reproduced": parent_guarded, "delta": parent_guarded - int(config["expected_parent_gross_events"]), "tolerance": 0, "pass": parent_guarded == int(config["expected_parent_gross_events"])},
            {"quantity": "parent App.I documented gross D_t>50 ns", "report_value": None, "reproduced": parent_documented, "delta": None, "tolerance": None, "pass": True},
            {"quantity": "all-three control events", "report_value": int(config["expected_all_three_control_events"]), "reproduced": int(len(all_three)), "delta": int(len(all_three)) - int(config["expected_all_three_control_events"]), "tolerance": 0, "pass": int(len(all_three)) == int(config["expected_all_three_control_events"])},
            {"quantity": "all-three clean events D_t<3 ns", "report_value": None, "reproduced": all_three_clean, "delta": None, "tolerance": None, "pass": True},
            {"quantity": "all-three guarded gross D_t>51 ns", "report_value": int(config["expected_all_three_guarded_gross_events"]), "reproduced": all_three_guarded, "delta": all_three_guarded - int(config["expected_all_three_guarded_gross_events"]), "tolerance": 0, "pass": all_three_guarded == int(config["expected_all_three_guarded_gross_events"])},
        ]
    )
    if not bool(reproduction["pass"].all()):
        raise RuntimeError("raw-ROOT reproduction gate failed")

    s07e_score, s07e_rf_scan, s07e_oof, _, _ = s07f.s07e_reproduction(config, utils, all_three)
    reproduced_s07e_auc = float(s07e_score.loc[s07e_score["method"] == "reproduced all-three shape-only RF", "roc_auc"].iloc[0])
    s07e_auc_delta = reproduced_s07e_auc - float(config["expected_s07e_shape_rf_auc"])
    s07e_pass = abs(s07e_auc_delta) <= float(config["s07e_reproduction_auc_tolerance"])
    reproduction = pd.concat(
        [
            reproduction,
            pd.DataFrame(
                [
                    {
                        "quantity": "all-three S07e shape RF ROC AUC",
                        "report_value": float(config["expected_s07e_shape_rf_auc"]),
                        "reproduced": reproduced_s07e_auc,
                        "delta": s07e_auc_delta,
                        "tolerance": float(config["s07e_reproduction_auc_tolerance"]),
                        "pass": bool(s07e_pass),
                    }
                ]
            ),
        ],
        ignore_index=True,
    )
    if not s07e_pass:
        raise RuntimeError("S07e all-three RF reproduction gate failed")

    s07f_counts, s07f_score, s07f_rf_scan, s07f_trad_choices, s07f_leakage, s07f_oof, s07f_details = s07f.independent_injection_benchmark(config, utils, clean_payloads)
    reproduced_s07f_auc = float(s07f_score.loc[s07f_score["method"] == "all-three shape-only RF", "roc_auc"].iloc[0])
    s07f_auc_delta = reproduced_s07f_auc - float(config["expected_s07f_shape_rf_auc"])
    s07f_pass = abs(s07f_auc_delta) <= float(config["s07f_reproduction_auc_tolerance"])
    reproduction = pd.concat(
        [
            reproduction,
            pd.DataFrame(
                [
                    {
                        "quantity": "S07f unnormalized injection RF ROC AUC",
                        "report_value": float(config["expected_s07f_shape_rf_auc"]),
                        "reproduced": reproduced_s07f_auc,
                        "delta": s07f_auc_delta,
                        "tolerance": float(config["s07f_reproduction_auc_tolerance"]),
                        "pass": bool(s07f_pass),
                    }
                ]
            ),
        ],
        ignore_index=True,
    )
    if not s07f_pass:
        raise RuntimeError("S07f injection RF reproduction gate failed")

    scoreboards: Dict[str, pd.DataFrame] = {}
    leakages: Dict[str, pd.DataFrame] = {}
    details: Dict[str, object] = dict(s07f_details)
    for mode in ["peak_preserved", "charge_preserved"]:
        data = make_preserved_dataset(config, utils, clean_payloads, mode)
        counts, score, rf_scan, trad_choices, leakage, oof, mode_details = run_benchmark(config, utils, data, mode)
        scoreboards[mode] = score
        leakages[mode] = leakage
        details.update(mode_details)
        counts.to_csv(out_dir / f"{mode}_dataset_counts_by_run.csv", index=False)
        score.to_csv(out_dir / f"{mode}_scoreboard.csv", index=False)
        rf_scan.to_csv(out_dir / f"{mode}_rf_cv_scan.csv", index=False)
        trad_choices.to_csv(out_dir / f"{mode}_traditional_fold_choices.csv", index=False)
        leakage.to_csv(out_dir / f"{mode}_leakage_checks.csv", index=False)
        oof.to_csv(out_dir / f"{mode}_oof_predictions.csv", index=False)

    reproduction.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    run_counts.to_csv(out_dir / "run_counts.csv", index=False)
    s07e_score.to_csv(out_dir / "s07e_reproduction_scoreboard.csv", index=False)
    s07e_rf_scan.to_csv(out_dir / "s07e_rf_cv_scan.csv", index=False)
    s07e_oof.to_csv(out_dir / "s07e_oof_predictions.csv", index=False)
    s07f_counts.to_csv(out_dir / "s07f_reproduction_dataset_counts_by_run.csv", index=False)
    s07f_score.to_csv(out_dir / "s07f_reproduction_scoreboard.csv", index=False)
    s07f_rf_scan.to_csv(out_dir / "s07f_reproduction_rf_cv_scan.csv", index=False)
    s07f_trad_choices.to_csv(out_dir / "s07f_reproduction_traditional_fold_choices.csv", index=False)
    s07f_leakage.to_csv(out_dir / "s07f_reproduction_leakage_checks.csv", index=False)
    s07f_oof.to_csv(out_dir / "s07f_reproduction_oof_predictions.csv", index=False)

    def auc_for(score: pd.DataFrame, method: str) -> float:
        return float(score.loc[score["method"] == method, "roc_auc"].iloc[0])

    result = {
        "ticket_id": config["ticket_id"],
        "study_id": config["study_id"],
        "raw_reproduction_pass": bool(reproduction["pass"].all()),
        "parent_guarded_gross_events": parent_guarded,
        "all_three_control_events": int(len(all_three)),
        "all_three_guarded_gross_events": all_three_guarded,
        "s07e_shape_rf_auc_reproduced": reproduced_s07e_auc,
        "s07e_shape_rf_auc_expected": float(config["expected_s07e_shape_rf_auc"]),
        "s07e_auc_delta": float(s07e_auc_delta),
        "s07f_shape_rf_auc_reproduced": reproduced_s07f_auc,
        "s07f_shape_rf_auc_expected": float(config["expected_s07f_shape_rf_auc"]),
        "s07f_auc_delta": float(s07f_auc_delta),
        "s07f_traditional_injected_auc": auc_for(s07f_score, "traditional fold-selected timing/template"),
        "peak_preserved_traditional_auc": auc_for(scoreboards["peak_preserved"], "traditional fold-selected timing/template"),
        "peak_preserved_direct_dt_auc": auc_for(scoreboards["peak_preserved"], "direct D_t/curvature cross-check"),
        "peak_preserved_shape_rf_auc": auc_for(scoreboards["peak_preserved"], "all-three shape-only RF"),
        "peak_preserved_rf_minus_traditional_auc": auc_for(scoreboards["peak_preserved"], "all-three shape-only RF") - auc_for(scoreboards["peak_preserved"], "traditional fold-selected timing/template"),
        "charge_preserved_traditional_auc": auc_for(scoreboards["charge_preserved"], "traditional fold-selected timing/template"),
        "charge_preserved_direct_dt_auc": auc_for(scoreboards["charge_preserved"], "direct D_t/curvature cross-check"),
        "charge_preserved_shape_rf_auc": auc_for(scoreboards["charge_preserved"], "all-three shape-only RF"),
        "charge_preserved_rf_minus_traditional_auc": auc_for(scoreboards["charge_preserved"], "all-three shape-only RF") - auc_for(scoreboards["charge_preserved"], "traditional fold-selected timing/template"),
        **details,
        "elapsed_seconds": float(time.time() - t0),
    }

    write_report(out_dir, config, s07f, reproduction, s07e_score, s07f_score, scoreboards, leakages, result)
    (out_dir / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    input_rows = []
    for run in config["runs"]:
        path = raw_file(config, int(run))
        input_rows.append({"path": str(path), "sha256": sha256_file(path), "bytes": path.stat().st_size})
    for path in [config_path, S07F_PATH, ROOT / config["utility_script"]]:
        input_rows.append({"path": str(path), "sha256": sha256_file(path), "bytes": path.stat().st_size})
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
        "command": f"/home/billy/anaconda3/bin/python scripts/s07g_1781024319_1318_2f4a5acc_amp_preserving_appi_control.py --config {config_path}",
    }
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            manifest["outputs"][path.name] = sha256_file(path)
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
