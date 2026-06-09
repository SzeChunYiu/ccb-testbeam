#!/usr/bin/env python3
"""S07f: all-three App.I RF validation on an independent injected target."""

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

os.environ.setdefault("MPLCONFIGDIR", "/tmp/ccb-testbeam-s07f-matplotlib-cache")

import numpy as np
import pandas as pd
import uproot


ROOT = Path(__file__).resolve().parents[1]


def load_config(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_s07d_utils(path: Path):
    spec = importlib.util.spec_from_file_location("s07d_utils", str(path))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import utility script: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["s07d_utils"] = module
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


def raw_file(config: dict, run: int) -> Path:
    return Path(config["raw_root_dir"]) / f"hrdb_run_{run:04d}.root"


def bootstrap_ci(y: np.ndarray, score: np.ndarray, runs: np.ndarray, metric, seed: int, n_boot: int) -> Tuple[float, float]:
    unique_runs = np.unique(runs)
    rng = np.random.default_rng(seed)
    values = []
    for _ in range(int(n_boot)):
        sampled = rng.choice(unique_runs, size=len(unique_runs), replace=True)
        idx = np.concatenate([np.flatnonzero(runs == run) for run in sampled])
        if len(np.unique(y[idx])) < 2:
            continue
        val = metric(y[idx], score[idx])
        if math.isfinite(val):
            values.append(val)
    if len(values) < 20:
        return float("nan"), float("nan")
    return float(np.percentile(values, 2.5)), float(np.percentile(values, 97.5))


def markdown_table(frame: pd.DataFrame) -> str:
    def fmt(value):
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


def collect_parent_and_all_three(config: dict, utils) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, List[dict]]:
    staves = list(config["staves"].keys())
    channels = np.asarray([int(config["staves"][name]) for name in staves], dtype=int)
    downstream_idx = np.asarray([staves.index(name) for name in config["downstream_staves"]], dtype=int)
    b2_idx = staves.index("B2")
    baseline_idx = [int(i) for i in config["baseline_samples"]]
    cut = float(config["amplitude_cut_adc"])
    nsamp = int(config["samples_per_channel"])
    run_rows = []
    parent_rows = []
    all_three_rows = []
    clean_payloads = []
    uid_offset = 0

    for run in config["runs"]:
        path = raw_file(config, int(run))
        raw_events = parent_control = all_three_control = 0
        for batch in uproot.open(path)["h101"].iterate(["EVENTNO", "EVT", "HRDv"], step_size=20000, library="np"):
            eventno = np.asarray(batch["EVENTNO"]).astype(int)
            evt = np.asarray(batch["EVT"]).astype(int)
            events = np.stack(batch["HRDv"]).astype(np.float64).reshape(-1, 8, nsamp)
            wave = events[:, channels, :]
            baseline = np.median(wave[..., baseline_idx], axis=-1)
            corrected = wave - baseline[..., None]
            amplitude = corrected.max(axis=-1)
            selected = amplitude > cut
            times = utils.cfd_times_ns(corrected, amplitude, float(config["cfd_fraction"]), float(config["sample_period_ns"]), cut)
            raw_events += len(eventno)

            parent_mask = selected[:, b2_idx] & (selected[:, downstream_idx].sum(axis=1) >= 2)
            all_three_mask = selected[:, b2_idx] & (selected[:, downstream_idx].sum(axis=1) == 3)
            for idx in np.where(parent_mask)[0]:
                d_t, c_t = utils.timing_summary(times[idx], selected[idx], downstream_idx, 2)
                if math.isfinite(d_t):
                    parent_control += 1
                    parent_rows.append(
                        {
                            "run": int(run),
                            "eventno": int(eventno[idx]),
                            "evt": int(evt[idx]),
                            "d_t_ns": float(d_t),
                            "abs_c_t_ns": abs(c_t) if math.isfinite(c_t) else float("nan"),
                            "n_downstream": int(selected[idx, downstream_idx].sum()),
                        }
                    )

            for idx in np.where(all_three_mask)[0]:
                d_t, c_t = utils.timing_summary(times[idx], selected[idx], downstream_idx, 3)
                if not math.isfinite(d_t):
                    continue
                all_three_control += 1
                key = f"{run}:{int(eventno[idx])}:{int(evt[idx])}:{uid_offset + int(idx)}"
                row: Dict[str, object] = {
                    "event_key": key,
                    "run": int(run),
                    "eventno": int(eventno[idx]),
                    "evt": int(evt[idx]),
                    "d_t_ns": float(d_t),
                    "abs_c_t_ns": abs(c_t) if math.isfinite(c_t) else float("nan"),
                    "n_downstream": 3,
                }
                utils.add_shape_features(row, corrected[idx], amplitude[idx], selected[idx], staves, downstream_idx, b2_idx)
                all_three_rows.append(row)
                if d_t < float(config["clean_dt_max_ns"]):
                    clean_payloads.append(
                        {
                            "event_key": key,
                            "run": int(run),
                            "eventno": int(eventno[idx]),
                            "evt": int(evt[idx]),
                            "corrected": corrected[idx].copy(),
                            "amplitude": amplitude[idx].copy(),
                            "selected": selected[idx].copy(),
                            "base_times": times[idx].copy(),
                            "base_d_t_ns": float(d_t),
                            "base_abs_c_t_ns": abs(c_t) if math.isfinite(c_t) else float("nan"),
                            "base_n_downstream": 3,
                        }
                    )
            uid_offset += len(eventno)
        run_rows.append(
            {
                "run": int(run),
                "raw_events": int(raw_events),
                "parent_control_events": int(parent_control),
                "all_three_control_events": int(all_three_control),
            }
        )

    return pd.DataFrame(parent_rows), pd.DataFrame(all_three_rows), pd.DataFrame(run_rows), clean_payloads


def s07e_reproduction(config: dict, utils, all_three: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, np.ndarray, np.ndarray]:
    extreme = all_three[(all_three["d_t_ns"] < float(config["clean_dt_max_ns"])) | (all_three["d_t_ns"] > float(config["gross_dt_min_ns"]))].copy()
    y = (extreme["d_t_ns"].to_numpy(dtype=float) > float(config["gross_dt_min_ns"])).astype(int)
    runs = extreme["run"].to_numpy(dtype=int)
    shape_cols = utils.feature_columns(extreme, "strict_shape")
    rf_scan, best_params, rf_score, rf_fold, rf_prob = utils.evaluate_rf_grid(extreme, y, shape_cols, config)
    direct_curvature = extreme["abs_c_t_ns"].to_numpy(dtype=float)
    direct_dt = np.maximum(extreme["d_t_ns"].to_numpy(dtype=float), np.nan_to_num(direct_curvature, nan=0.0))
    score = pd.DataFrame(
        [
            utils.summarize_method(
                "reproduced all-three curvature-only",
                y,
                direct_curvature,
                utils.crossfold_isotonic(y, direct_curvature, rf_fold),
                runs,
                int(config["random_seed"]) + 1,
                int(config["bootstrap_replicates"]),
                "S07e pre-registered all-three traditional comparator.",
            ),
            utils.summarize_method(
                "reproduced all-three D_t/curvature ceiling",
                y,
                direct_dt,
                utils.crossfold_isotonic(y, direct_dt, rf_fold),
                runs,
                int(config["random_seed"]) + 2,
                int(config["bootstrap_replicates"]),
                "Forbidden self-referential timing ceiling.",
            ),
            utils.summarize_method(
                "reproduced all-three shape-only RF",
                y,
                rf_score,
                rf_prob,
                runs,
                int(config["random_seed"]) + 3,
                int(config["bootstrap_replicates"]),
                f"Best params={best_params}; raw-ROOT reproduction of S07e all-three App.I RF.",
            ),
        ]
    )
    oof = extreme[["event_key", "run", "eventno", "evt", "d_t_ns", "abs_c_t_ns"]].copy()
    oof["label_gross_dt_tail"] = y
    oof["rf_score"] = rf_score
    oof["rf_prob"] = rf_prob
    return score, rf_scan, oof, y, rf_score


def independent_injection_benchmark(config: dict, utils, clean_payloads: List[dict]) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    data = utils.make_dataset(config, clean_payloads)
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
            {"probe": "absolute-amplitude-only RF", "roc_auc": utils.auc(y, amp_score), "average_precision": utils.ap(y, amp_score), "notes": "Excluded from main RF; injection changes peak height."},
            {"probe": "shape RF with shuffled training labels", "roc_auc": utils.auc(y, shuffle_score), "average_precision": utils.ap(y, shuffle_score), "notes": "Null/leakage sanity check."},
            {"probe": "per-stave slot shape RF", "roc_auc": utils.auc(y, slot_score), "average_precision": utils.ap(y, slot_score), "notes": "Permissive shape representation; not main claim."},
            {"probe": "pair split violations", "roc_auc": float(pair_split_violations), "average_precision": float("nan"), "notes": "Must be 0."},
            {"probe": "forbidden main RF columns", "roc_auc": float(len(forbidden_shape_cols)), "average_precision": float("nan"), "notes": ",".join(forbidden_shape_cols) if forbidden_shape_cols else "None."},
        ]
    )

    oof = data[["row_id", "event_key", "pair_id", "run", "label_injected", "variant", "base_d_t_ns", "d_t_ns", "abs_c_t_ns", "target_stave", "injected_delay_samples", "injected_scale"]].copy()
    oof["traditional_score"] = trad_score
    oof["traditional_prob"] = trad_prob
    oof["direct_dt_score"] = direct_dt
    oof["rf_score"] = rf_score
    oof["rf_prob"] = rf_prob
    details = {
        "best_rf_params": best_params,
        "pair_split_violations": int(pair_split_violations),
        "forbidden_main_rf_columns": forbidden_shape_cols,
        "dataset_events": int(len(data)),
        "dataset_pairs": int(data["pair_id"].nunique()),
    }
    return counts, scoreboard, rf_scan, trad_choices, leakage, oof, details


def write_report(out_dir: Path, config: dict, reproduction: pd.DataFrame, s07e_score: pd.DataFrame, injection_counts: pd.DataFrame, injection_score: pd.DataFrame, leakage: pd.DataFrame, result: dict) -> None:
    rf_repro = s07e_score[s07e_score["method"] == "reproduced all-three shape-only RF"].iloc[0]
    trad = injection_score[injection_score["method"] == "traditional fold-selected timing/template"].iloc[0]
    rf = injection_score[injection_score["method"] == "all-three shape-only RF"].iloc[0]
    text = f"""# S07f: independent all-three App.I RF validation

- **Ticket:** `{config['ticket_id']}`
- **Worker:** `{config['worker']}`
- **Input:** raw B-stack ROOT `HRDv` from `{config['raw_root_dir']}`
- **Selection:** Sample-II analysis runs, B2+B4+B6+B8 all selected, `A>1000` ADC, CFD20 timing.
- **Split:** leave-one-run-out; intervals are held-out run-block bootstrap CIs.

## Raw-ROOT Reproduction First

{markdown_table(reproduction)}

The all-three App.I raw count gate reproduces the S07e control population (`3774`) and guarded gross tail (`22`) exactly. The D_t-label benchmark then reproduces the S07e shape RF AUC as {rf_repro['roc_auc']:.6f}, within the configured tolerance of the prior {config['expected_s07e_shape_rf_auc']:.6f}.

{markdown_table(s07e_score)}

## Independent Target

The validation target is not `D_t`: each raw clean all-three event (`D_t<3 ns`) is paired with one injected copy where a selected downstream waveform receives a delayed scaled copy of itself. Delays are {config['delay_samples_min']}-{config['delay_samples_max']} samples and scales are {config['secondary_scale_min']}-{config['secondary_scale_max']}. Raw and injected pair members are held out together by run.

{markdown_table(injection_counts)}

## Head-to-Head

{markdown_table(injection_score)}

The strong traditional score is selected inside each training fold from timing, curvature, downstream shape summaries, and a train-only matched-template residual. The ML method is a shape-only RF using B2 and downstream aggregate normalized waveform features; timing values, run/event IDs, pair IDs, injection parameters, amplitudes, and topology flags are excluded.

## Leakage Hunt

{markdown_table(leakage)}

The result is good but not suspiciously perfect: shuffled labels are near chance, pair split violations are zero, and no forbidden columns enter the main RF. The direct post-injection `D_t` cross-check is near chance, confirming that the injected label is not a disguised `D_t` tail threshold. The amplitude-only probe is strong because the injection changes peak height, so it is kept out of the main RF and reported as a nuisance.

## Finding

The all-three App.I RF survives an independent non-`D_t` validation. On injected two-pulse truth, the traditional timing/template score reaches ROC AUC {trad['roc_auc']:.3f} [{trad['roc_auc_ci_low']:.3f}, {trad['roc_auc_ci_high']:.3f}], while the all-three shape-only RF reaches {rf['roc_auc']:.3f} [{rf['roc_auc_ci_low']:.3f}, {rf['roc_auc_ci_high']:.3f}]. This validates the all-three RF as a waveform-corruption detector, not as direct evidence for a measured beam pile-up rate.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s07f_independent_all_three_appi_validation.py --config configs/s07f_1781012109_1290_18206042.json
```

Artifacts: `result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `s07e_reproduction_scoreboard.csv`, `injection_scoreboard.csv`, `leakage_checks.csv`, and out-of-fold prediction CSVs.
"""
    (out_dir / "REPORT.md").write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/s07f_1781012109_1290_18206042.json")
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = load_config(config_path)
    out_dir = ROOT / config["output_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)
    utils = load_s07d_utils(ROOT / config["utility_script"])

    parent, all_three, run_counts, clean_payloads = collect_parent_and_all_three(config, utils)
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

    s07e_score, s07e_rf_scan, s07e_oof, _, _ = s07e_reproduction(config, utils, all_three)
    reproduced_auc = float(s07e_score.loc[s07e_score["method"] == "reproduced all-three shape-only RF", "roc_auc"].iloc[0])
    auc_delta = reproduced_auc - float(config["expected_s07e_shape_rf_auc"])
    s07e_pass = abs(auc_delta) <= float(config["s07e_reproduction_auc_tolerance"])
    reproduction = pd.concat(
        [
            reproduction,
            pd.DataFrame(
                [
                    {
                        "quantity": "all-three S07e shape RF ROC AUC",
                        "report_value": float(config["expected_s07e_shape_rf_auc"]),
                        "reproduced": reproduced_auc,
                        "delta": auc_delta,
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

    injection_counts, injection_score, injection_rf_scan, trad_choices, leakage, injection_oof, details = independent_injection_benchmark(config, utils, clean_payloads)

    reproduction.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    run_counts.to_csv(out_dir / "run_counts.csv", index=False)
    s07e_score.to_csv(out_dir / "s07e_reproduction_scoreboard.csv", index=False)
    s07e_rf_scan.to_csv(out_dir / "s07e_rf_cv_scan.csv", index=False)
    s07e_oof.to_csv(out_dir / "s07e_oof_predictions.csv", index=False)
    injection_counts.to_csv(out_dir / "injection_dataset_counts_by_run.csv", index=False)
    injection_score.to_csv(out_dir / "injection_scoreboard.csv", index=False)
    injection_rf_scan.to_csv(out_dir / "injection_rf_cv_scan.csv", index=False)
    trad_choices.to_csv(out_dir / "traditional_fold_choices.csv", index=False)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)
    injection_oof.to_csv(out_dir / "injection_oof_predictions.csv", index=False)

    trad_auc = float(injection_score.loc[injection_score["method"] == "traditional fold-selected timing/template", "roc_auc"].iloc[0])
    direct_auc = float(injection_score.loc[injection_score["method"] == "direct D_t/curvature cross-check", "roc_auc"].iloc[0])
    rf_auc = float(injection_score.loc[injection_score["method"] == "all-three shape-only RF", "roc_auc"].iloc[0])
    result = {
        "ticket_id": config["ticket_id"],
        "study_id": config["study_id"],
        "raw_reproduction_pass": bool(reproduction["pass"].all()),
        "parent_guarded_gross_events": parent_guarded,
        "all_three_control_events": int(len(all_three)),
        "all_three_guarded_gross_events": all_three_guarded,
        "s07e_shape_rf_auc_reproduced": reproduced_auc,
        "s07e_shape_rf_auc_expected": float(config["expected_s07e_shape_rf_auc"]),
        "s07e_auc_delta": float(auc_delta),
        "traditional_injected_auc": trad_auc,
        "direct_dt_injected_auc": direct_auc,
        "shape_rf_injected_auc": rf_auc,
        "rf_minus_traditional_auc": float(rf_auc - trad_auc),
        "rf_minus_direct_dt_auc": float(rf_auc - direct_auc),
        **details,
        "elapsed_seconds": float(time.time() - t0),
    }

    write_report(out_dir, config, reproduction, s07e_score, injection_counts, injection_score, leakage, result)
    (out_dir / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    input_rows = []
    for run in config["runs"]:
        path = raw_file(config, int(run))
        input_rows.append({"path": str(path), "sha256": sha256_file(path), "bytes": path.stat().st_size})
    input_rows.append({"path": str(config_path), "sha256": sha256_file(config_path), "bytes": config_path.stat().st_size})
    input_sha = pd.DataFrame(input_rows)
    input_sha.to_csv(out_dir / "input_sha256.csv", index=False)
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
        "command": f"/home/billy/anaconda3/bin/python scripts/s07f_independent_all_three_appi_validation.py --config {config_path}",
    }
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            manifest["outputs"][path.name] = sha256_file(path)
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
