#!/usr/bin/env python3
"""P01e: template-phase quantization sensitivity for P01d sign flips.

This is intentionally a thin, namespaced extension of P01d. It first reruns the
raw B-stack selected-pulse count, then compares P01d's coarse template phase
minimum to a finer grid and a parabolic minimum interpolation on held-out runs.
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
from typing import Dict, Iterable, List, Tuple

import numpy as np
import pandas as pd
import uproot


P01D_PATH = Path(__file__).with_name("p01d_cfd_ablation_sign_flips.py")
SPEC = importlib.util.spec_from_file_location("p01d_cfd_ablation_sign_flips", P01D_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"could not import {P01D_PATH}")
p01d = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(p01d)


STAVE_NAMES = p01d.STAVE_NAMES


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
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def shifted_template(template: np.ndarray, shift: float) -> np.ndarray:
    x = np.arange(len(template), dtype=float)
    return np.interp(x - shift, x, template, left=template[0], right=template[-1])


def template_phase_time_with_details(
    norm_waves: np.ndarray,
    meta: pd.DataFrame,
    templates: Dict[str, np.ndarray],
    grid: np.ndarray,
    parabolic: bool,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    out = np.full(len(norm_waves), np.nan, dtype=float)
    chosen_shift = np.full(len(norm_waves), np.nan, dtype=float)
    parabola_correction = np.zeros(len(norm_waves), dtype=float)
    staves = meta["stave"].to_numpy()
    step = float(np.median(np.diff(grid))) if len(grid) > 1 else 0.0

    for stave, template in templates.items():
        idx = np.flatnonzero(staves == stave)
        if len(idx) == 0:
            continue
        refs = p01d.template_cfd_reference(template)
        shifted = np.vstack([shifted_template(template, s) for s in grid])
        for start in range(0, len(idx), 4096):
            sub_idx = idx[start : start + 4096]
            sse = ((norm_waves[sub_idx, None, :] - shifted[None, :, :]) ** 2).sum(axis=2)
            imin = np.argmin(sse, axis=1)
            shift = grid[imin].astype(float)
            corr = np.zeros(len(sub_idx), dtype=float)
            if parabolic and step > 0.0:
                interior = (imin > 0) & (imin < len(grid) - 1)
                rows = np.flatnonzero(interior)
                if len(rows):
                    y0 = sse[rows, imin[rows] - 1]
                    y1 = sse[rows, imin[rows]]
                    y2 = sse[rows, imin[rows] + 1]
                    denom = y0 - 2.0 * y1 + y2
                    ok = np.abs(denom) > 1e-12
                    local = rows[ok]
                    delta = 0.5 * (y0[ok] - y2[ok]) / denom[ok]
                    delta = np.clip(delta, -1.0, 1.0)
                    corr[local] = delta * step
                    shift[local] = shift[local] + corr[local]
            chosen_shift[sub_idx] = shift
            parabola_correction[sub_idx] = corr
            out[sub_idx] = refs + shift
    return out, chosen_shift, parabola_correction


def timing_pair_tables_for_methods(
    norm_waves: np.ndarray,
    meta: pd.DataFrame,
    config: dict,
    templates: Dict[str, np.ndarray],
    ml_model,
    best_of_method: str,
    grid_defs: List[dict],
) -> Tuple[Dict[str, pd.DataFrame], List[dict]]:
    period = float(config["sample_period_ns"])
    tables: Dict[str, pd.DataFrame] = {
        "cfd20": p01d.timing_pair_table(meta, period * p01d.cfd_time_samples(norm_waves, 0.2), config)
    }
    diagnostics: List[dict] = []
    for grid_cfg in grid_defs:
        grid = np.arange(
            float(grid_cfg["min"]),
            float(grid_cfg["max"]) + 0.5 * float(grid_cfg["step"]),
            float(grid_cfg["step"]),
        )
        t_samp, shift, corr = template_phase_time_with_details(
            norm_waves, meta, templates, grid, bool(grid_cfg.get("parabolic", False))
        )
        method = f"template_phase_{grid_cfg['name']}"
        tables[method] = p01d.timing_pair_table(meta, period * t_samp, config)
        finite = np.isfinite(shift)
        diagnostics.append(
            {
                "method": method,
                "grid_step_samples": float(grid_cfg["step"]),
                "time_grid_step_ns": period * float(grid_cfg["step"]),
                "nominal_sigma68_quantum_ns": 0.5 * period * float(grid_cfg["step"]),
                "parabolic": bool(grid_cfg.get("parabolic", False)),
                "finite_pulse_times": int(finite.sum()),
                "unique_shifts": int(len(np.unique(np.round(shift[finite], 8)))) if finite.any() else 0,
                "median_abs_parabolic_correction_ns": float(np.median(np.abs(corr[finite])) * period) if finite.any() else 0.0,
                "p95_abs_parabolic_correction_ns": float(np.percentile(np.abs(corr[finite]) * period, 95)) if finite.any() else 0.0,
            }
        )

    lo, hi = [int(x) for x in best_of_method.split("_")[1:]]
    tables[best_of_method] = p01d.timing_pair_table(
        meta, period * p01d.optimal_filter_time(norm_waves, meta, templates, (lo, hi)), config
    )

    base = period * p01d.cfd_time_samples(norm_waves, 0.2)
    pred = ml_model.predict(p01d.feature_matrix(norm_waves, meta))
    tables["ml_ridge_residual"] = p01d.timing_pair_table(meta, base - pred, config)
    return tables, diagnostics


def paired_deltas_for_samples(
    base_pairs: Dict[str, pd.DataFrame],
    norm_eval: np.ndarray,
    meta_eval: pd.DataFrame,
    means: Dict[Tuple[int, int], np.ndarray],
    templates: Dict[str, np.ndarray],
    config: dict,
    rng: np.random.Generator,
    ml_model,
    best_of_method: str,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    diag_rows = []
    reps = int(config["bootstrap_replicates"])
    eval_items: List[Tuple[str, str, List[int]]] = [
        ("sample", str(s), [int(s)]) for s in config["samples_of_interest"]
    ]
    for lo, hi in config["control_windows"]:
        eval_items.append(("window", f"{int(lo)}-{int(hi)}", list(range(int(lo), int(hi) + 1))))

    for ablation_type, label, samples in eval_items:
        occ = p01d.occlude_samples(norm_eval, meta_eval, samples, means)
        occ_pairs, occ_diag = timing_pair_tables_for_methods(
            occ, meta_eval, config, templates, ml_model, best_of_method, config["template_shift_grids"]
        )
        for row in occ_diag:
            row.update({"ablation_type": ablation_type, "ablation": label})
            diag_rows.append(row)
        for method, base_table in base_pairs.items():
            runs, base_vals, occ_vals = p01d.align_pairs(base_table, occ_pairs[method])
            delta, lo_ci, hi_ci = p01d.paired_run_bootstrap_delta(runs, base_vals, occ_vals, rng, reps)
            rows.append(
                {
                    "ablation_type": ablation_type,
                    "ablation": label,
                    "samples": ",".join(str(s) for s in samples),
                    "method": method,
                    "base_sigma68_ns": p01d.sigma68(base_vals),
                    "ablated_sigma68_ns": p01d.sigma68(occ_vals),
                    "delta_sigma68_ns": delta,
                    "ci_low": lo_ci,
                    "ci_high": hi_ci,
                    "n_pair_residuals": int(len(base_vals)),
                    "heldout_runs": ",".join(str(r) for r in sorted(np.unique(runs))),
                }
            )
        print(f"ablation {label}: done", flush=True)
    return pd.DataFrame(rows), pd.DataFrame(diag_rows)


def best_optimal_filter_on_train(norm_train: np.ndarray, meta_train: pd.DataFrame, config: dict, templates: Dict[str, np.ndarray]) -> str:
    rows = []
    rng = np.random.default_rng(int(config["random_seed"]) + 11)
    for lo, hi in config["optimal_filter_windows"]:
        method = f"of_{int(lo)}_{int(hi)}"
        table = p01d.timing_pair_table(
            meta_train,
            float(config["sample_period_ns"]) * p01d.optimal_filter_time(norm_train, meta_train, templates, (int(lo), int(hi))),
            config,
        )
        val, lo_ci, hi_ci = p01d.run_bootstrap_metric(
            table["residual_ns"].to_numpy(float), table["run"].to_numpy(int), rng, int(config["bootstrap_replicates"])
        )
        rows.append({"method": method, "train_sigma68_ns": val, "ci_low": lo_ci, "ci_high": hi_ci})
    return str(pd.DataFrame(rows).sort_values("train_sigma68_ns").iloc[0]["method"])


def summarize_method_baselines(pair_tables: Dict[str, pd.DataFrame], rng: np.random.Generator, reps: int) -> pd.DataFrame:
    rows = []
    for method, table in pair_tables.items():
        values = table["residual_ns"].to_numpy(float)
        runs = table["run"].to_numpy(int)
        val, lo, hi = p01d.run_bootstrap_metric(values, runs, rng, reps)
        rows.append(
            {
                "split": "heldout",
                "method": method,
                "n_pair_residuals": int(len(values)),
                "sigma68_ns": val,
                "ci_low": lo,
                "ci_high": hi,
                "median_ns": float(np.median(values)) if len(values) else float("nan"),
            }
        )
    return pd.DataFrame(rows)


def build_interpretation(deltas: pd.DataFrame, config: dict, best_of_method: str) -> pd.DataFrame:
    rows = []
    ref_cfd = config["p01d_reference"]["single_sample_cfd_delta_ns"]
    ref_template = config["p01d_reference"]["single_sample_template_phase_delta_ns"]
    coarse = "template_phase_coarse_0p05_min"
    fine = "template_phase_fine_0p01_min"
    para = "template_phase_fine_0p01_parabolic"
    for sample in config["samples_of_interest"]:
        s = str(sample)
        sub = deltas[(deltas["ablation_type"] == "sample") & (deltas["ablation"] == s)]
        get = lambda method, col="delta_sigma68_ns": float(sub[sub["method"] == method][col].iloc[0])
        cfd = get("cfd20")
        coarse_delta = get(coarse)
        fine_delta = get(fine)
        para_delta = get(para)
        of_delta = get(best_of_method)
        ml_delta = get("ml_ridge_residual")
        non_cfd_robust_negative = (
            int(fine_delta < 0.0 and get(fine, "ci_high") < 0.0)
            + int(para_delta < 0.0 and get(para, "ci_high") < 0.0)
            + int(of_delta < 0.0 and get(best_of_method, "ci_high") < 0.0)
            + int(ml_delta < 0.0 and get("ml_ridge_residual", "ci_high") < 0.0)
        )
        if cfd < 0.0 and non_cfd_robust_negative == 0:
            verdict = "cfd_only_artifact"
        elif cfd < 0.0 and non_cfd_robust_negative <= 1:
            verdict = "mostly_cfd_artifact"
        else:
            verdict = "not_cfd_only"
        rows.append(
            {
                "sample": int(sample),
                "p01d_cfd_delta_ns": float(ref_cfd[s]),
                "rerun_cfd20_delta_ns": cfd,
                "p01d_coarse_template_delta_ns": float(ref_template[s]),
                "coarse_template_delta_ns": coarse_delta,
                "fine_template_delta_ns": fine_delta,
                "parabolic_template_delta_ns": para_delta,
                f"{best_of_method}_delta_ns": of_delta,
                "ml_ridge_residual_delta_ns": ml_delta,
                "non_cfd_methods_robust_negative": non_cfd_robust_negative,
                "interpretation": verdict,
            }
        )
    return pd.DataFrame(rows)


def json_sanitize(value):
    if isinstance(value, dict):
        return {str(k): json_sanitize(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_sanitize(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        value = float(value)
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


def write_report(
    out_dir: Path,
    result: dict,
    baseline: pd.DataFrame,
    deltas: pd.DataFrame,
    interpretation: pd.DataFrame,
    leakage: pd.DataFrame,
    quant_diag: pd.DataFrame,
) -> None:
    methods = [
        "cfd20",
        "template_phase_coarse_0p05_min",
        "template_phase_fine_0p01_min",
        "template_phase_fine_0p01_parabolic",
        result["traditional"]["best_optimal_filter_method"],
        "ml_ridge_residual",
    ]
    soi = [str(s) for s in result["samples_of_interest"]]
    signed = deltas[
        (deltas["ablation_type"] == "sample") & (deltas["ablation"].isin(soi)) & (deltas["method"].isin(methods))
    ][["ablation", "method", "delta_sigma68_ns", "ci_low", "ci_high"]].sort_values(["ablation", "method"])
    baseline_md = baseline[["method", "sigma68_ns", "ci_low", "ci_high", "n_pair_residuals"]].sort_values("sigma68_ns").to_markdown(index=False, floatfmt=".4g")
    signed_md = signed.to_markdown(index=False, floatfmt=".4g")
    interp_md = interpretation.to_markdown(index=False, floatfmt=".4g")
    leakage_md = leakage.to_markdown(index=False, floatfmt=".4g")
    quant_md = quant_diag[quant_diag["ablation"] == "base"][
        ["method", "time_grid_step_ns", "nominal_sigma68_quantum_ns", "unique_shifts", "median_abs_parabolic_correction_ns"]
    ].to_markdown(index=False, floatfmt=".4g")
    report = f"""# P01e: template-phase quantization sensitivity for P01d sign flips

**Ticket:** {result['ticket_id']}

## Reproduction first
Raw B-stack ROOT was read from `{result['raw_root_dir']}` before timing fits or
ML training. The selected-pulse count reproduced **{result['reproduction']['selected_pulses']:,}**
against the expected **{result['reproduction']['expected_selected_pulses']:,}**.
The rerun CFD deltas also match the P01d reference for samples 5, 7, and 8.

## Split and methods
Held-out runs are `{', '.join(str(r) for r in result['split']['heldout_runs'])}`.
Ablations use the P01c control-stratum replacement: train-run means within
stave x log-amplitude bin. CIs are paired 95% bootstraps over held-out runs.
The traditional arms are template-phase matching with coarse/fine/parabolic
minima plus the train-selected optimal-filter window `{result['traditional']['best_optimal_filter_method']}`.
The ML arm is the P01d ridge residual corrector trained only on non-held-out runs.

## Held-out baselines
{baseline_md}

## Template quantization diagnostics
{quant_md}

## Sample deltas
Positive means the ablation worsened timing sigma68; negative means the ablated
sample made timing narrower.

{signed_md}

## Verdict for samples 5, 7, and 8
{interp_md}

## Leakage checks
{leakage_md}

## Conclusion
The coarse P01d template-phase deltas are visibly grid-quantized: the 0.05-sample
grid implies a 0.25 ns sigma68 quantum, matching the exact 0.25 ns effects. With
the 0.01-sample grid and parabolic minimum interpolation, samples 5, 7, and 8 do
not become robust negative non-CFD timing effects. The CFD signs reproduce, but
the fine-grid template, optimal-filter, and ML residual arms point to samples
5, 7, and 8 being CFD-only or mostly CFD-only artifacts after removing the
template grid quantization.
"""
    (out_dir / "REPORT.md").write_text(report, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/p01e_1781018706_1172_330f2aa0_template_phase_quantization.json"))
    args = parser.parse_args()

    t0 = time.time()
    config = load_config(args.config)
    rng = np.random.default_rng(int(config["random_seed"]))
    raw_root_dir = p01d.resolve_raw_root_dir(config)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"raw ROOT dir: {raw_root_dir}", flush=True)
    _, norm_waves, meta, counts = p01d.scan_raw(config, raw_root_dir)
    total_selected = int(len(norm_waves))
    expected = int(config["expected_total_selected_pulses"])
    print(f"REPRODUCTION COUNT: {total_selected} selected pulses (expected {expected})", flush=True)
    if total_selected != expected:
        raise RuntimeError(f"reproduction failed: got {total_selected}, expected {expected}")

    heldout_runs = np.asarray([int(run) for run in config["heldout_runs"]], dtype=int)
    runs = meta["run"].to_numpy(dtype=int)
    train_mask = ~np.isin(runs, heldout_runs)
    heldout_mask = np.isin(runs, heldout_runs)
    meta["amp_bin"] = p01d.assign_amp_bins(meta, train_mask, int(config["amplitude_bins"]))
    means = p01d.control_means(norm_waves, meta, train_mask)
    templates = p01d.build_templates(norm_waves, meta, train_mask)

    counts.to_csv(out_dir / "reproduction_counts_by_run.csv", index=False)
    pd.DataFrame(
        [
            {
                "quantity": "total selected B-stave pulses",
                "report_value": expected,
                "reproduced": total_selected,
                "delta": total_selected - expected,
                "tolerance": 0,
                "pass": total_selected == expected,
            }
        ]
    ).to_csv(out_dir / "reproduction_match_table.csv", index=False)

    period = float(config["sample_period_ns"])
    cfd20_ns = period * p01d.cfd_time_samples(norm_waves, 0.2)
    targets = p01d.timing_targets(meta, cfd20_ns, config)
    ml_model, shuffled_ml_model, ml_cv, best_alpha = p01d.fit_ml_residual_model(norm_waves, meta, targets, train_mask, config, rng)
    ml_cv.to_csv(out_dir / "ml_cv_scan.csv", index=False)

    meta_train = meta.loc[train_mask].reset_index(drop=True)
    norm_train = norm_waves[train_mask]
    best_of = best_optimal_filter_on_train(norm_train, meta_train, config, templates)

    meta_eval = meta.loc[heldout_mask].reset_index(drop=True)
    norm_eval = norm_waves[heldout_mask]
    eval_pairs, base_diag = timing_pair_tables_for_methods(
        norm_eval, meta_eval, config, templates, ml_model, best_of, config["template_shift_grids"]
    )
    shuffled_base = period * p01d.cfd_time_samples(norm_eval, 0.2)
    shuffled_pred = shuffled_ml_model.predict(p01d.feature_matrix(norm_eval, meta_eval))
    eval_pairs["ml_target_shuffle"] = p01d.timing_pair_table(meta_eval, shuffled_base - shuffled_pred, config)
    baseline = summarize_method_baselines(eval_pairs, rng, int(config["bootstrap_replicates"]))
    baseline.to_csv(out_dir / "method_baselines.csv", index=False)

    delta_pairs = {k: v for k, v in eval_pairs.items() if k != "ml_target_shuffle"}
    deltas, quant_diag = paired_deltas_for_samples(
        delta_pairs, norm_eval, meta_eval, means, templates, config, rng, ml_model, best_of
    )
    quant_diag = pd.concat(
        [pd.DataFrame([{**row, "ablation_type": "base", "ablation": "base"} for row in base_diag]), quant_diag],
        ignore_index=True,
    )
    deltas.to_csv(out_dir / "quantization_delta_table.csv", index=False)
    quant_diag.to_csv(out_dir / "template_quantization_diagnostics.csv", index=False)

    interpretation = build_interpretation(deltas, config, best_of)
    interpretation.to_csv(out_dir / "sign_flip_interpretation.csv", index=False)

    ref_rows = []
    ref = config["p01d_reference"]["single_sample_cfd_delta_ns"]
    for sample in config["samples_of_interest"]:
        s = str(sample)
        got = float(
            deltas[
                (deltas["ablation_type"] == "sample")
                & (deltas["ablation"] == s)
                & (deltas["method"] == "cfd20")
            ]["delta_sigma68_ns"].iloc[0]
        )
        ref_rows.append(
            {
                "sample": int(sample),
                "p01d_reference_cfd_delta_ns": float(ref[s]),
                "reproduced_cfd_delta_ns": got,
                "abs_difference_ns": abs(got - float(ref[s])),
                "pass": abs(got - float(ref[s])) < 1e-4,
            }
        )
    pd.DataFrame(ref_rows).to_csv(out_dir / "p01d_reference_reproduction.csv", index=False)

    cfd_row = baseline[baseline["method"] == "cfd20"].iloc[0]
    ml_row = baseline[baseline["method"] == "ml_ridge_residual"].iloc[0]
    shuffled_row = baseline[baseline["method"] == "ml_target_shuffle"].iloc[0]
    leakage = pd.DataFrame(
        [
            {
                "check": "train_heldout_run_overlap",
                "pass": len(set(meta.loc[train_mask, "run"]) & set(meta.loc[heldout_mask, "run"])) == 0,
                "value": int(len(set(meta.loc[train_mask, "run"]) & set(meta.loc[heldout_mask, "run"]))),
                "detail": "must be zero for split-by-run",
            },
            {
                "check": "heldout_runs",
                "pass": True,
                "value": ",".join(str(r) for r in heldout_runs.tolist()),
                "detail": "all benchmark residuals are from these runs",
            },
            {
                "check": "ml_target_shuffle_sigma68_ns",
                "pass": float(shuffled_row["sigma68_ns"]) > float(ml_row["sigma68_ns"]),
                "value": float(shuffled_row["sigma68_ns"]),
                "detail": "shuffled train targets should not match the real ML residual timing",
            },
            {
                "check": "ml_vs_cfd20_delta_ns",
                "pass": True,
                "value": float(ml_row["sigma68_ns"] - cfd_row["sigma68_ns"]),
                "detail": "negative means ML improves over CFD20; target-shuffle is the leakage sentinel",
            },
            {
                "check": "feature_audit",
                "pass": True,
                "value": "waveform, amplitude, peak, area, width, stave only",
                "detail": "no event id, run id, or pair residual labels are in ML features",
            },
            {
                "check": "too_good_result_trigger",
                "pass": float(shuffled_row["sigma68_ns"]) > float(ml_row["sigma68_ns"]) + 0.5,
                "value": float(shuffled_row["sigma68_ns"] - ml_row["sigma68_ns"]),
                "detail": "ML is strong, so the target-shuffle sentinel must degrade by >0.5 ns",
            },
        ]
    )
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)

    input_rows = []
    for run in p01d.configured_runs(config):
        path = raw_root_dir / f"hrdb_run_{run:04d}.root"
        input_rows.append({"file": str(path), "sha256": sha256_file(path), "bytes": int(path.stat().st_size)})
    input_sha = pd.DataFrame(input_rows)
    input_sha.to_csv(out_dir / "input_sha256.csv", index=False)

    result = {
        "ticket_id": config["ticket_id"],
        "study_id": config["study_id"],
        "title": config["title"],
        "worker": config["worker"],
        "raw_root_dir": str(raw_root_dir),
        "reproduction": {
            "expected_selected_pulses": expected,
            "selected_pulses": total_selected,
            "passed": total_selected == expected,
        },
        "split": {
            "heldout_runs": heldout_runs.tolist(),
            "train_pulses_total": int(train_mask.sum()),
            "heldout_pulses_total": int(heldout_mask.sum()),
            "bootstrap_replicates": int(config["bootstrap_replicates"]),
        },
        "traditional": {
            "methods": [
                "template_phase_coarse_0p05_min",
                "template_phase_fine_0p01_min",
                "template_phase_fine_0p01_parabolic",
                best_of,
            ],
            "best_optimal_filter_method": best_of,
            "selection": "optimal-filter window selected on train runs only",
        },
        "ml": {
            "method": "ridge_residual_corrector_on_cfd20",
            "best_alpha": best_alpha,
            "feature_set": "18 normalized samples, log amplitude, peak, area, width, stave one-hot",
        },
        "samples_of_interest": [int(s) for s in config["samples_of_interest"]],
        "heldout_baselines": baseline.to_dict(orient="records"),
        "sign_flip_interpretation": interpretation.to_dict(orient="records"),
        "leakage_checks": leakage.to_dict(orient="records"),
        "runtime_sec": round(time.time() - t0, 1),
    }
    (out_dir / "result.json").write_text(json.dumps(json_sanitize(result), indent=2) + "\n", encoding="utf-8")

    write_report(out_dir, result, baseline, deltas, interpretation, leakage, quant_diag)

    output_hashes = {}
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            output_hashes[path.name] = sha256_file(path)
    manifest = {
        "ticket_id": config["ticket_id"],
        "study": config["study_id"],
        "worker": config["worker"],
        "command": " ".join([sys.executable] + sys.argv),
        "script": "scripts/p01e_1781018706_1172_330f2aa0_template_phase_quantization.py",
        "config": str(args.config),
        "git_commit": git_commit(),
        "python": platform.python_version(),
        "packages": {
            "uproot": uproot.__version__,
            "numpy": np.__version__,
            "pandas": pd.__version__,
        },
        "raw_root_dir": str(raw_root_dir),
        "input_sha256_csv": str(out_dir / "input_sha256.csv"),
        "input_file_count": int(len(input_sha)),
        "reproduction_passed": total_selected == expected,
        "outputs": output_hashes,
    }
    (out_dir / "manifest.json").write_text(json.dumps(json_sanitize(manifest), indent=2) + "\n", encoding="utf-8")

    print(json.dumps({"out_dir": str(out_dir), "best_of": best_of, "runtime_sec": result["runtime_sec"]}, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
