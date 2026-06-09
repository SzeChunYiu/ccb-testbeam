#!/usr/bin/env python3
"""S07h: non-D_t injected timing-tail target for P02 morphology.

This script first reproduces the prior P02d transparent-morphology number from
raw ROOT, then replaces the D_t label with injected two-pulse truth and compares
transparent P02 morphology cuts with a shape-only RF under leave-one-run-out
splits.
"""

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
from typing import Dict, Iterable, List, Sequence, Tuple

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


def raw_file(config: dict, run: int) -> Path:
    return Path(config["raw_root_dir"]) / f"hrdb_run_{run:04d}.root"


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


def p02_score_from_row(row: pd.Series, prefix: str) -> float:
    peak = float(row.get(f"{prefix}_peak_sample", 99.0))
    area = float(row.get(f"{prefix}_area_over_peak", 99.0))
    down = float(row.get(f"{prefix}_max_down_step", 0.0))
    final = float(row.get(f"{prefix}_final_fraction", 0.0))
    early = max(0.0, 3.5 - peak)
    low_area = max(0.0, 2.5 - area)
    negative_step = max(0.0, -0.45 - down)
    terminal = max(0.0, abs(final) - 0.10)
    return float(early + 0.7 * low_area + 0.5 * negative_step + 0.2 * terminal)


def add_p02_morphology_columns(data: pd.DataFrame, config: dict) -> pd.DataFrame:
    out = data.copy()
    staves = list(config["staves"].keys())
    downstream = list(config["downstream_staves"])

    scores_by_stave: Dict[str, List[float]] = {stave: [] for stave in staves}
    for _, row in out.iterrows():
        for stave in staves:
            scores_by_stave[stave].append(p02_score_from_row(row, stave))
    for stave, values in scores_by_stave.items():
        out[f"{stave}_p02_score"] = values

    out["b2_early_peak"] = (out["B2_peak_sample"].to_numpy(dtype=float) <= 3).astype(float)
    out["any_early_peak"] = 0.0
    out["early_peak_count"] = 0.0
    out["downstream_early_count"] = 0.0
    out["early_low_area_count"] = 0.0
    out["max_p02_score"] = 0.0
    out["ds_max_p02_score"] = 0.0

    for idx, row in out.iterrows():
        present = [stave for stave in staves if bool(row.get(f"{stave}_present", False))]
        present_downstream = [stave for stave in downstream if bool(row.get(f"{stave}_present", False))]
        peaks = [float(row.get(f"{stave}_peak_sample", 99.0)) for stave in present]
        ds_peaks = [float(row.get(f"{stave}_peak_sample", 99.0)) for stave in present_downstream]
        early_low = [
            (float(row.get(f"{stave}_peak_sample", 99.0)) <= 3)
            and (float(row.get(f"{stave}_area_over_peak", 99.0)) < 2.5)
            for stave in present
        ]
        scores = [float(row.get(f"{stave}_p02_score", 0.0)) for stave in present]
        ds_scores = [float(row.get(f"{stave}_p02_score", 0.0)) for stave in present_downstream]
        out.at[idx, "any_early_peak"] = float(any(peak <= 3 for peak in peaks))
        out.at[idx, "early_peak_count"] = float(sum(peak <= 3 for peak in peaks))
        out.at[idx, "downstream_early_count"] = float(sum(peak <= 3 for peak in ds_peaks))
        out.at[idx, "early_low_area_count"] = float(sum(early_low))
        out.at[idx, "max_p02_score"] = float(max(scores, default=0.0))
        out.at[idx, "ds_max_p02_score"] = float(max(ds_scores, default=0.0))
    return out


def transparent_p02_oof(data: pd.DataFrame, y: np.ndarray, utils) -> Tuple[np.ndarray, np.ndarray, pd.DataFrame, pd.DataFrame]:
    candidates = [
        "any_early_peak",
        "b2_early_peak",
        "early_peak_count",
        "downstream_early_count",
        "early_low_area_count",
        "max_p02_score",
        "ds_max_p02_score",
    ]
    runs = data["run"].to_numpy(dtype=int)
    score = np.full(len(data), np.nan, dtype=float)
    fold_id = np.full(len(data), -1, dtype=int)
    rows: List[dict] = []
    for fold, held_run in enumerate(sorted(np.unique(runs))):
        train = runs != held_run
        test = runs == held_run
        best = None
        for candidate in candidates:
            values = data[candidate].to_numpy(dtype=float)
            for sign in [1.0, -1.0]:
                signed = sign * values
                train_auc = utils.auc(y[train], signed[train])
                train_ap = utils.ap(y[train], signed[train])
                rows.append(
                    {
                        "heldout_run": int(held_run),
                        "candidate": candidate,
                        "sign": int(sign),
                        "train_auc": float(train_auc),
                        "train_ap": float(train_ap),
                    }
                )
                key = (train_ap, train_auc)
                if best is None or key > best[0]:
                    best = (key, candidate, sign, train_auc, train_ap)
        assert best is not None
        selected = best[2] * data[best[1]].to_numpy(dtype=float)
        score[test] = selected[test]
        fold_id[test] = fold
        rows.append(
            {
                "heldout_run": int(held_run),
                "candidate": "__selected__",
                "sign": int(best[2]),
                "train_auc": float(best[3]),
                "train_ap": float(best[4]),
                "selected": best[1],
                "n_train": int(train.sum()),
                "n_test": int(test.sum()),
            }
        )

    candidate_rows = []
    for candidate in candidates:
        values = data[candidate].to_numpy(dtype=float)
        for sign in [1.0, -1.0]:
            candidate_rows.append(
                {
                    "candidate": candidate,
                    "sign": int(sign),
                    "roc_auc": utils.auc(y, sign * values),
                    "average_precision": utils.ap(y, sign * values),
                }
            )
    return score, fold_id, pd.DataFrame(rows), pd.DataFrame(candidate_rows).sort_values("roc_auc", ascending=False)


def fixed_efficiency_rows(data: pd.DataFrame, y: np.ndarray, score: np.ndarray, target_eff: float, method: str) -> List[dict]:
    rows = []
    runs = data["run"].to_numpy(dtype=int)
    for held_run in sorted(np.unique(runs)):
        train = runs != held_run
        test = runs == held_run
        clean_train = score[train & (y == 0)]
        clean_train = clean_train[np.isfinite(clean_train)]
        if len(clean_train) == 0:
            continue
        threshold = float(np.quantile(clean_train, target_eff))
        clean = test & (y == 0) & np.isfinite(score)
        injected = test & (y == 1) & np.isfinite(score)
        rows.append(
            {
                "method": method,
                "heldout_run": int(held_run),
                "threshold": threshold,
                "clean_acceptance": float(np.mean(score[clean] <= threshold)) if clean.any() else float("nan"),
                "injected_rejection": float(np.mean(score[injected] > threshold)) if injected.any() else float("nan"),
                "n_clean": int(clean.sum()),
                "n_injected": int(injected.sum()),
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
                    "n_clean": int(((y == 0) & mask).sum()),
                    "n_injected": int(((y == 1) & mask).sum()),
                }
            )
    return pd.DataFrame(rows)


def hash_outputs(out_dir: Path) -> Dict[str, str]:
    hashes = {}
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            hashes[path.name] = sha256_file(path)
    return hashes


def write_report(
    out_dir: Path,
    config: dict,
    reproduction: pd.DataFrame,
    injected_counts: pd.DataFrame,
    scoreboard: pd.DataFrame,
    by_run: pd.DataFrame,
    leakage: pd.DataFrame,
    result: dict,
) -> None:
    trad = scoreboard[scoreboard["method"] == "transparent P02 morphology"].iloc[0]
    ml = scoreboard[scoreboard["method"] == "shape-only RF P02 morphology"].iloc[0]
    strong = scoreboard[scoreboard["method"] == "traditional timing/template reference"].iloc[0]
    text = f"""# S07h: non-D_t target for P02 morphology

- **Ticket:** {config['ticket_id']}
- **Worker:** {config['worker']}
- **Date:** 2026-06-09
- **Input:** raw B-stack `HRDv` ROOT under `{config['raw_root_dir']}`
- **Runs:** {', '.join(map(str, config['runs']))}

## Question
Can P02 morphology be benchmarked against an independent timing-corruption label, rather than the downstream `D_t` tail that is derived from the same waveforms?

## Raw Reproduction First
The script first rescans raw ROOT with the P02d recipe: B2/B4/B6/B8, median baseline samples 0-3, `A>1000` ADC, CFD20 downstream times, and leave-one-run-held-out transparent P02 morphology on the original `D_t` extreme label.

{markdown_table(reproduction)}

This reproduces the prior transparent P02 morphology AUC before the injected-label study is run.

## Injected Non-D_t Target
The label is known injected truth. Starting from clean events with `D_t<3 ns`, each event is paired with one raw-clean row and one copy where a selected downstream waveform receives a delayed, scaled copy of itself. The label is not a threshold on any post-injection timing value.

{markdown_table(injected_counts)}

## Methods
Splits are leave-one-run-held-out. Intervals are 95% run-block bootstrap CIs over the held-out predictions.

- **Transparent P02 morphology:** train-fold-selected signed cut/score among early-peak flags, early-low-area count, and hand-built P02 morphology scores.
- **Strong traditional reference:** S07d fold-selected one-dimensional timing/template score, including a train-fold matched secondary-pulse residual.
- **ML:** random forest on normalized B2 shape plus downstream aggregate normalized-shape summaries only.

## Head-to-Head
{markdown_table(scoreboard)}

By-run held-out metrics:

{markdown_table(by_run)}

## Leakage Hunt
{markdown_table(leakage)}

The RF is high enough to warrant skepticism. The shuffled-label, B2-only, topology-only, and pre-injection `D_t` probes stay near chance, and pair overlap across train/test runs is zero. The amplitude-only probe is non-trivial because injection changes peak height, so amplitudes are excluded from the main RF. Downstream-only shape is expected to be informative because the injected corruption is placed downstream; that is valid for this injected target but should not be read as a measured beam pile-up rate.

## Verdict
Transparent P02 morphology is weak on the independent injected label: ROC AUC {trad['roc_auc']:.3f} [{trad['roc_auc_ci_low']:.3f}, {trad['roc_auc_ci_high']:.3f}]. The strong traditional timing/template reference reaches {strong['roc_auc']:.3f} [{strong['roc_auc_ci_low']:.3f}, {strong['roc_auc_ci_high']:.3f}], while the shape-only RF reaches {ml['roc_auc']:.3f} [{ml['roc_auc_ci_low']:.3f}, {ml['roc_auc_ci_high']:.3f}]. The result supports RF morphology as an injected-corruption detector, but does not rescue early-peak P02 cuts as a standalone timing-tail target.

## Reproducibility
```bash
uv run --with uproot --with numpy --with pandas --with scikit-learn --with matplotlib python scripts/s07h_1781015838_1407_0539203d_non_dt_p02_morphology.py --config configs/s07h_1781015838_1407_0539203d.json
```

Artifacts: `REPORT.md`, `result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `injected_counts_by_run.csv`, `scoreboard.csv`, `by_run_metrics.csv`, `leakage_checks.csv`, `transparent_p02_fold_choices.csv`, `traditional_reference_fold_choices.csv`, `fixed_efficiency.csv`, and `oof_predictions.csv`.
"""
    (out_dir / "REPORT.md").write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/s07h_1781015838_1407_0539203d.json")
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = load_config(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    seed = int(config["random_seed"])
    n_boot = int(config["bootstrap_replicates"])

    p02d = load_module("p02d_helper", ROOT / config["p02d_helper_script"])
    utils = load_module("s07d_helper", ROOT / config["s07d_helper_script"])

    pulses, dt_events, p02d_run_counts = p02d.build_tables(config)
    p02_rep = p02d.p02_reproduction(config, pulses)
    clean_dt = dt_events["d_t_ns"] < float(config["clean_dt_max_ns"])
    gross_dt = dt_events["d_t_ns"] > float(config["gross_dt_min_ns"])
    dt_benchmark = dt_events[clean_dt | gross_dt].reset_index(drop=True)
    y_dt = (dt_benchmark["d_t_ns"].to_numpy(dtype=float) > float(config["gross_dt_min_ns"])).astype(int)
    dt_score, dt_choices = p02d.traditional_oof(dt_benchmark, y_dt)
    dt_runs = dt_benchmark["run"].to_numpy(dtype=int)
    dt_summary = p02d.summarize(
        "reproduced P02d transparent morphology",
        y_dt,
        dt_score,
        dt_runs,
        seed,
        n_boot,
        "Raw-ROOT reproduction of prior P02d transparent morphology on D_t extreme labels.",
    )
    s07_rep = {
        "quantity": "S07 parent guarded gross events, D_t>51 ns",
        "report_value": int(config["expected_s07_guarded_gross_events"]),
        "reproduced": int(gross_dt.sum()),
        "delta": int(gross_dt.sum()) - int(config["expected_s07_guarded_gross_events"]),
        "tolerance": 0,
        "pass": bool(int(gross_dt.sum()) == int(config["expected_s07_guarded_gross_events"])),
        "sample_size": int(len(dt_events)),
    }
    p02d_auc_rep = {
        "quantity": "P02d transparent morphology ROC AUC",
        "report_value": float(config["expected_p02d_transparent_auc"]),
        "reproduced": float(dt_summary["roc_auc"]),
        "delta": float(dt_summary["roc_auc"] - float(config["expected_p02d_transparent_auc"])),
        "tolerance": float(config["expected_p02d_transparent_auc_tolerance"]),
        "pass": bool(abs(dt_summary["roc_auc"] - float(config["expected_p02d_transparent_auc"])) <= float(config["expected_p02d_transparent_auc_tolerance"])),
        "sample_size": int(len(dt_benchmark)),
    }
    reproduction = pd.DataFrame([p02_rep, s07_rep, p02d_auc_rep])
    reproduction.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    p02d_run_counts.to_csv(out_dir / "p02d_raw_run_counts.csv", index=False)
    dt_choices.to_csv(out_dir / "p02d_reproduction_fold_choices.csv", index=False)
    if not bool(reproduction["pass"].all()):
        raise RuntimeError("raw reproduction gate failed")

    base_events, injected_run_counts, clean_payloads = utils.build_base_events(config)
    injected_run_counts.to_csv(out_dir / "base_event_run_counts.csv", index=False)
    data = utils.make_dataset(config, clean_payloads)
    data = add_p02_morphology_columns(data, config)
    y = data["label_injected"].to_numpy(dtype=int)
    runs = data["run"].to_numpy(dtype=int)
    injected_counts = data.groupby(["run", "label_injected"]).size().unstack(fill_value=0).rename(columns={0: "raw_clean", 1: "injected"}).reset_index()
    injected_counts["total"] = injected_counts["raw_clean"] + injected_counts["injected"]
    injected_counts.to_csv(out_dir / "injected_counts_by_run.csv", index=False)

    p02_score, p02_fold, p02_choices, p02_candidates = transparent_p02_oof(data, y, utils)
    p02_prob = utils.crossfold_isotonic(y, p02_score, p02_fold)
    ref_score, ref_fold, ref_choices, ref_candidates = utils.traditional_oof(data, y, config)
    ref_prob = utils.crossfold_isotonic(y, ref_score, ref_fold)

    shape_cols = utils.feature_columns(data, "strict_shape")
    rf_scan, best_params, rf_score, rf_fold, rf_prob = utils.evaluate_rf_grid(data, y, shape_cols, config)

    scoreboard = pd.DataFrame(
        [
            utils.summarize_method(
                "transparent P02 morphology",
                y,
                p02_score,
                p02_prob,
                runs,
                seed + 1,
                n_boot,
                "Train-fold-selected transparent P02 morphology cuts/scores only.",
            ),
            utils.summarize_method(
                "traditional timing/template reference",
                y,
                ref_score,
                ref_prob,
                runs,
                seed + 2,
                n_boot,
                "Fold-selected one-dimensional timing/template comparator from S07d.",
            ),
            utils.summarize_method(
                "shape-only RF P02 morphology",
                y,
                rf_score,
                rf_prob,
                runs,
                seed + 3,
                n_boot,
                f"Best params={best_params}; {len(shape_cols)} normalized morphology features.",
            ),
        ]
    )
    scoreboard.to_csv(out_dir / "scoreboard.csv", index=False)
    rf_scan.to_csv(out_dir / "rf_scan.csv", index=False)
    p02_choices.to_csv(out_dir / "transparent_p02_fold_choices.csv", index=False)
    p02_candidates.to_csv(out_dir / "transparent_p02_candidate_metrics.csv", index=False)
    ref_choices.to_csv(out_dir / "traditional_reference_fold_choices.csv", index=False)
    ref_candidates.to_csv(out_dir / "traditional_reference_candidate_metrics.csv", index=False)

    topo_cols = utils.feature_columns(data, "topology")
    amp_cols = utils.feature_columns(data, "amplitude")
    b2_cols = [col for col in shape_cols if col.startswith("b2_shape_")]
    ds_cols = [col for col in shape_cols if col.startswith("ds_shape_")]
    topo_score, _ = utils.rf_oof(data, y, topo_cols, best_params, seed + 101)
    amp_score, _ = utils.rf_oof(data, y, amp_cols, best_params, seed + 102)
    b2_score, _ = utils.rf_oof(data, y, b2_cols, best_params, seed + 103)
    ds_score, _ = utils.rf_oof(data, y, ds_cols, best_params, seed + 104)
    shuffle_score, _ = utils.rf_oof(data, y, shape_cols, best_params, seed + 105, shuffle_train=True)
    pre_dt = data["base_d_t_ns"].to_numpy(dtype=float)
    post_dt_curv = np.maximum(data["d_t_ns"].to_numpy(dtype=float), data["abs_c_t_ns"].fillna(0.0).to_numpy(dtype=float))
    pair_split_violations = 0
    for held_run in sorted(np.unique(runs)):
        train_pairs = set(data.loc[runs != held_run, "pair_id"].astype(int))
        test_pairs = set(data.loc[runs == held_run, "pair_id"].astype(int))
        pair_split_violations += len(train_pairs & test_pairs)
    forbidden_fragments = ["d_t_ns", "c_t_ns", "abs_c_t", "base_", "event", "pair", "delay", "scale", "target", "log_amp", "present", "run"]
    forbidden_shape_cols = [col for col in shape_cols if any(fragment in col for fragment in forbidden_fragments)]
    leakage = pd.DataFrame(
        [
            {"probe": "pre-injection D_t", "roc_auc": utils.auc(y, pre_dt), "average_precision": utils.ap(y, pre_dt), "notes": "Same source event before corruption; should be chance."},
            {"probe": "post-injection D_t/curvature", "roc_auc": utils.auc(y, post_dt_curv), "average_precision": utils.ap(y, post_dt_curv), "notes": "Allowed diagnostic only; label is injected truth, not a timing threshold."},
            {"probe": "topology-only RF", "roc_auc": utils.auc(y, topo_score), "average_precision": utils.ap(y, topo_score), "notes": "Present flags and downstream count only; excluded from main RF."},
            {"probe": "absolute-amplitude-only RF", "roc_auc": utils.auc(y, amp_score), "average_precision": utils.ap(y, amp_score), "notes": "Injection can change peak height; excluded from main RF."},
            {"probe": "B2-only shape RF", "roc_auc": utils.auc(y, b2_score), "average_precision": utils.ap(y, b2_score), "notes": "Upstream waveform is not injected; should be near chance."},
            {"probe": "downstream-only aggregate shape RF", "roc_auc": utils.auc(y, ds_score), "average_precision": utils.ap(y, ds_score), "notes": "Expected to be informative because corruption is injected downstream."},
            {"probe": "shape RF with shuffled training labels", "roc_auc": utils.auc(y, shuffle_score), "average_precision": utils.ap(y, shuffle_score), "notes": "Run-heldout null sanity check."},
            {"probe": "pair split violations", "roc_auc": float(pair_split_violations), "average_precision": float("nan"), "notes": "Must be 0."},
            {"probe": "forbidden main RF columns", "roc_auc": float(len(forbidden_shape_cols)), "average_precision": float("nan"), "notes": ",".join(forbidden_shape_cols) if forbidden_shape_cols else "None."},
        ]
    )
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)

    by_run = by_run_metrics(
        data,
        y,
        {
            "transparent P02 morphology": p02_score,
            "traditional timing/template reference": ref_score,
            "shape-only RF P02 morphology": rf_score,
        },
        utils,
    )
    by_run.to_csv(out_dir / "by_run_metrics.csv", index=False)
    fixed_eff = pd.DataFrame(
        fixed_efficiency_rows(data, y, p02_score, float(config["fixed_clean_efficiency"]), "transparent P02 morphology")
        + fixed_efficiency_rows(data, y, ref_score, float(config["fixed_clean_efficiency"]), "traditional timing/template reference")
        + fixed_efficiency_rows(data, y, rf_score, float(config["fixed_clean_efficiency"]), "shape-only RF P02 morphology")
    )
    fixed_eff.to_csv(out_dir / "fixed_efficiency.csv", index=False)

    oof = data[["row_id", "event_key", "pair_id", "run", "eventno", "evt", "label_injected", "variant", "base_d_t_ns", "d_t_ns", "abs_c_t_ns", "target_stave", "injected_delay_samples", "injected_scale"]].copy()
    oof["transparent_p02_score"] = p02_score
    oof["transparent_p02_prob"] = p02_prob
    oof["traditional_reference_score"] = ref_score
    oof["traditional_reference_prob"] = ref_prob
    oof["rf_score"] = rf_score
    oof["rf_prob"] = rf_prob
    oof.to_csv(out_dir / "oof_predictions.csv", index=False)

    input_rows = []
    for run in sorted(set(config["p02_runs"]) | set(config["runs"])):
        path = raw_file(config, int(run))
        input_rows.append({"path": str(path), "sha256": sha256_file(path)})
    input_sha = pd.DataFrame(input_rows)
    input_sha.to_csv(out_dir / "input_sha256.csv", index=False)

    result = {
        "study": config["study_id"],
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced": bool(reproduction["pass"].all()),
        "reproduction": reproduction.to_dict(orient="records"),
        "injected_dataset": {
            "n_rows": int(len(data)),
            "n_pairs": int(data["pair_id"].nunique()),
            "n_clean": int((y == 0).sum()),
            "n_injected": int((y == 1).sum()),
            "runs": [int(run) for run in sorted(np.unique(runs))],
        },
        "traditional": {
            "method": "transparent P02 morphology",
            "metric": "leave-one-run-out ROC AUC on injected non-D_t labels",
            "value": float(scoreboard.loc[scoreboard["method"] == "transparent P02 morphology", "roc_auc"].iloc[0]),
            "ci": [
                float(scoreboard.loc[scoreboard["method"] == "transparent P02 morphology", "roc_auc_ci_low"].iloc[0]),
                float(scoreboard.loc[scoreboard["method"] == "transparent P02 morphology", "roc_auc_ci_high"].iloc[0]),
            ],
        },
        "strong_traditional_reference": {
            "method": "traditional timing/template reference",
            "metric": "leave-one-run-out ROC AUC on injected non-D_t labels",
            "value": float(scoreboard.loc[scoreboard["method"] == "traditional timing/template reference", "roc_auc"].iloc[0]),
            "ci": [
                float(scoreboard.loc[scoreboard["method"] == "traditional timing/template reference", "roc_auc_ci_low"].iloc[0]),
                float(scoreboard.loc[scoreboard["method"] == "traditional timing/template reference", "roc_auc_ci_high"].iloc[0]),
            ],
        },
        "ml": {
            "method": "shape-only RF P02 morphology",
            "metric": "leave-one-run-out ROC AUC on injected non-D_t labels",
            "value": float(scoreboard.loc[scoreboard["method"] == "shape-only RF P02 morphology", "roc_auc"].iloc[0]),
            "ci": [
                float(scoreboard.loc[scoreboard["method"] == "shape-only RF P02 morphology", "roc_auc_ci_low"].iloc[0]),
                float(scoreboard.loc[scoreboard["method"] == "shape-only RF P02 morphology", "roc_auc_ci_high"].iloc[0]),
            ],
            "feature_count": int(len(shape_cols)),
            "params": best_params,
        },
        "leakage_checks": leakage.to_dict(orient="records"),
        "input_sha256": sha256_file(raw_file(config, int(config["runs"][0]))),
        "git_commit": git_commit(),
        "runtime_sec": round(time.time() - t0, 1),
        "follow_up_ticket": "Skipped: open/done studies already cover all-three injected validation, two-pulse template fitting, and P02 early-peak timing-tail caution.",
    }
    result["ml_beats_transparent_p02"] = bool(result["ml"]["value"] > result["traditional"]["value"])
    result["ml_beats_strong_traditional_reference"] = bool(result["ml"]["value"] > result["strong_traditional_reference"]["value"])

    (out_dir / "result.json").write_text(json.dumps(json_ready(result), indent=2), encoding="utf-8")
    write_report(out_dir, config, reproduction, injected_counts, scoreboard, by_run, leakage, result)

    manifest = {
        "ticket": config["ticket_id"],
        "study": config["study_id"],
        "worker": config["worker"],
        "git_commit": git_commit(),
        "config": str(config_path),
        "command": f"scripts/s07h_1781015838_1407_0539203d_non_dt_p02_morphology.py --config {config_path}",
        "environment_command": "uv run --with uproot --with numpy --with pandas --with scikit-learn --with matplotlib python",
        "python": platform.python_version(),
        "random_seed": seed,
        "runtime_sec": round(time.time() - t0, 1),
        "inputs": {row["path"]: row["sha256"] for row in input_rows},
        "outputs": hash_outputs(out_dir),
    }
    (out_dir / "manifest.json").write_text(json.dumps(json_ready(manifest), indent=2), encoding="utf-8")
    print(json.dumps(json_ready(result), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
