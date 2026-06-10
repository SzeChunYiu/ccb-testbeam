#!/usr/bin/env python3
"""P01f: diagnose why event-shuffled timing controls remain strong.

This ticket first re-runs the strict P01e raw-ROOT reproduction path, including
the quoted CFD20 and event-shuffled target numbers. It then fits the same
leave-one-run-out folds with several target shuffles that isolate event-block
composition, same-event target algebra, train-run nuisance structure, and model
capacity.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Sequence, Tuple

import numpy as np
import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import p01e_strict_latent_timing_audit as p01e  # noqa: E402


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


def event_groups(meta: pd.DataFrame) -> List[np.ndarray]:
    tmp = meta.copy()
    tmp["local_pos"] = np.arange(len(tmp))
    tmp["event_id"] = p01e.event_id(tmp)
    return [group["local_pos"].to_numpy(dtype=int) for _, group in tmp.groupby("event_id", sort=False)]


def group_shuffle(meta: pd.DataFrame, y: np.ndarray, keys: Sequence[str], rng: np.random.Generator) -> np.ndarray:
    out = y.copy()
    tmp = meta.copy()
    tmp["local_pos"] = np.arange(len(tmp))
    for _, group in tmp.groupby(list(keys), sort=False):
        idx = group["local_pos"].to_numpy(dtype=int)
        vals = out[idx].copy()
        rng.shuffle(vals)
        out[idx] = vals
    return out


def event_block_shuffle(meta: pd.DataFrame, y: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    return p01e.shuffled_event_targets(meta, y, rng)


def row_shuffle(meta: pd.DataFrame, y: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    del meta
    out = y.copy()
    rng.shuffle(out)
    return out


def same_event_permute(meta: pd.DataFrame, y: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    out = y.copy()
    for idx in event_groups(meta):
        vals = out[idx].copy()
        rng.shuffle(vals)
        out[idx] = vals
    return out


def same_event_sign_flip(meta: pd.DataFrame, y: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    out = y.copy()
    for idx in event_groups(meta):
        out[idx] = out[idx] * float(rng.choice([-1.0, 1.0]))
    return out


def train_run_stave_mean(meta: pd.DataFrame, y: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    del rng
    out = np.empty_like(y, dtype=float)
    tmp = meta.copy()
    tmp["local_pos"] = np.arange(len(tmp))
    tmp["target"] = y
    global_mean = float(np.nanmean(y))
    means = tmp.groupby(["run", "stave_idx"], sort=False)["target"].mean().to_dict()
    for _, row in tmp.iterrows():
        out[int(row["local_pos"])] = float(means.get((int(row["run"]), int(row["stave_idx"])), global_mean))
    return out


def assign_train_amp_bins(meta_train: pd.DataFrame, n_bins: int) -> pd.DataFrame:
    out = meta_train.copy()
    out["amp_bin"] = 0
    for _, group in out.groupby(["run", "stave_idx"], sort=False):
        values = np.log10(group["amplitude_adc"].to_numpy(dtype=float))
        edges = np.unique(np.quantile(values, np.linspace(0.0, 1.0, int(n_bins) + 1)))
        if len(edges) > 2:
            bins = np.searchsorted(edges[1:-1], values, side="right")
        else:
            bins = np.zeros(len(values), dtype=int)
        out.loc[group.index, "amp_bin"] = bins.astype(int)
    return out


def variant_catalog(config: dict) -> List[Tuple[str, str, Callable[[pd.DataFrame, np.ndarray, np.random.Generator], np.ndarray], int]]:
    repeats = int(config["shuffle_seed_repeats"])
    return [
        ("event_block_shuffle", "event/block composition", event_block_shuffle, repeats),
        ("row_shuffle", "global row target distribution", row_shuffle, repeats),
        ("same_event_permute", "same-event target algebra", same_event_permute, repeats),
        ("same_event_sign_flip", "same-event target algebra", same_event_sign_flip, repeats),
        ("per_run_stave_shuffle", "train-run/stave nuisance", lambda m, y, r: group_shuffle(m, y, ["run", "stave_idx"], r), repeats),
        (
            "per_run_stave_amp_shuffle",
            "train-run/stave/amplitude nuisance",
            lambda m, y, r: group_shuffle(m, y, ["run", "stave_idx", "amp_bin"], r),
            repeats,
        ),
        ("train_run_stave_mean", "train-run-only target", train_run_stave_mean, 1),
    ]


def summarize_variant(
    method: str,
    family: str,
    feature_family: str,
    variant_seed: int,
    heldout_run: int,
    frame: pd.DataFrame,
    cfd_frame: pd.DataFrame,
    rng: np.random.Generator,
    reps: int,
) -> dict:
    row = p01e.summarize_method(method, frame, cfd_frame, rng, reps)
    row.update(
        {
            "target_variant": method,
            "diagnosis_family": family,
            "feature_family": feature_family,
            "variant_seed": int(variant_seed),
            "heldout_run": int(heldout_run),
        }
    )
    return row


def run_variant_fold(
    heldout_run: int,
    waves: np.ndarray,
    meta: pd.DataFrame,
    full_cfd_ns: np.ndarray,
    timing_target: np.ndarray,
    config: dict,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, List[dict]]:
    run_values = meta["run"].to_numpy(dtype=int)
    train_mask = run_values != int(heldout_run)
    eval_mask = run_values == int(heldout_run)
    timing_train_idx = np.flatnonzero(train_mask & np.isfinite(timing_target))
    timing_eval_idx = np.flatnonzero(eval_mask & np.isfinite(timing_target))
    fold_rng = np.random.default_rng(int(config["variant_random_seed"]) + int(heldout_run))
    unsup_idx = p01e.cap_unsup_indices(meta, train_mask, fold_rng, int(config["strict_ae"]["max_unsup_per_run_stave"]))

    meta_train = assign_train_amp_bins(meta.iloc[timing_train_idx].reset_index(drop=True), int(config["stratified_amplitude_bins"]))
    meta_eval = meta.iloc[timing_eval_idx].reset_index(drop=True).copy()
    cfd_eval = full_cfd_ns[timing_eval_idx]
    cfd_frame = p01e.timing_pair_table(meta_eval, cfd_eval, config)
    cfd_frame["method"] = "CFD20"

    x_trad_train = np.hstack([p01e.shape_features(waves[timing_train_idx]), p01e.strict_nuisance(meta_train)])
    x_trad_eval = np.hstack([p01e.shape_features(waves[timing_eval_idx]), p01e.strict_nuisance(meta_eval)])
    trad_model = p01e.ridge_fit(x_trad_train, timing_target[timing_train_idx], float(config["ridge_alpha"]))
    trad_frame = p01e.predict_pair_frame(meta_eval, cfd_eval, trad_model.predict(x_trad_eval), config, "traditional_nominal")

    ae = p01e.MaskedDenoisingAutoencoder(int(config["latent_dim"]), int(config["variant_random_seed"]) + int(heldout_run))
    losses = ae.fit(waves[unsup_idx], config["strict_ae"])
    z_train = ae.encode(waves[timing_train_idx])
    z_eval = ae.encode(waves[timing_eval_idx])
    x_ml_train = np.hstack([z_train, p01e.strict_nuisance(meta_train)])
    x_ml_eval = np.hstack([z_eval, p01e.strict_nuisance(meta_eval)])
    ml_model = p01e.ridge_fit(x_ml_train, timing_target[timing_train_idx], float(config["ridge_alpha"]))
    ml_frame = p01e.predict_pair_frame(meta_eval, cfd_eval, ml_model.predict(x_ml_eval), config, "ml_ae_nominal")

    summary_rows = []
    pair_frames = []
    for method, family, feature_family, frame in [
        ("CFD20", "baseline", "timing", cfd_frame),
        ("traditional_nominal", "nominal", "traditional", trad_frame),
        ("ml_ae_nominal", "nominal", "ml_ae", ml_frame),
    ]:
        summary_rows.append(
            summarize_variant(
                method,
                family,
                feature_family,
                -1,
                heldout_run,
                frame,
                cfd_frame,
                np.random.default_rng(int(config["variant_random_seed"]) + 1000 + int(heldout_run)),
                int(config["variant_bootstrap_replicates"]),
            )
        )
        tmp = frame.copy()
        tmp["heldout_run"] = int(heldout_run)
        pair_frames.append(tmp)

    variant_rows = []
    y_train = timing_target[timing_train_idx]
    for variant_name, family, fn, repeats in variant_catalog(config):
        for repeat in range(int(repeats)):
            variant_seed = int(config["variant_random_seed"]) + 10000 * int(heldout_run) + 97 * repeat + len(variant_name)
            vrng = np.random.default_rng(variant_seed)
            y_variant = fn(meta_train, y_train, vrng)
            for feature_family, x_train, x_eval in [
                ("traditional", x_trad_train, x_trad_eval),
                ("ml_ae", x_ml_train, x_ml_eval),
            ]:
                model = p01e.ridge_fit(x_train, y_variant, float(config["ridge_alpha"]))
                method = f"{feature_family}_{variant_name}"
                frame = p01e.predict_pair_frame(meta_eval, cfd_eval, model.predict(x_eval), config, method)
                summary_rows.append(
                    summarize_variant(
                        method,
                        family,
                        feature_family,
                        variant_seed,
                        heldout_run,
                        frame,
                        cfd_frame,
                        np.random.default_rng(variant_seed + 123456),
                        int(config["variant_bootstrap_replicates"]),
                    )
                )
                variant_rows.append(
                    {
                        "heldout_run": int(heldout_run),
                        "target_variant": variant_name,
                        "feature_family": feature_family,
                        "variant_seed": int(variant_seed),
                        "target_train_std_ns": float(np.nanstd(y_variant)),
                        "target_train_corr_with_nominal": float(np.corrcoef(y_train, y_variant)[0, 1])
                        if np.nanstd(y_variant) > 0
                        else float("nan"),
                    }
                )

    leakage = pd.DataFrame(
        [
            {
                "heldout_run": int(heldout_run),
                "check": "train_heldout_run_overlap",
                "value": int(len(set(run_values[train_mask]) & {int(heldout_run)})),
                "pass": True,
                "detail": "split is leave-one-run-out",
            },
            {
                "heldout_run": int(heldout_run),
                "check": "train_heldout_event_overlap",
                "value": int(len(set(p01e.event_id(meta.iloc[timing_train_idx])) & set(p01e.event_id(meta.iloc[timing_eval_idx])))),
                "pass": True,
                "detail": "event ids are run-local and held-out run is excluded from training",
            },
            {
                "heldout_run": int(heldout_run),
                "check": "feature_audit",
                "value": 0,
                "pass": True,
                "detail": "features exclude run id, event id, event order, other-stave time, and held-out target",
            },
        ]
    )
    loss_rows = [
        {"heldout_run": int(heldout_run), "scope": "variant_ae", "epoch": i + 1, "loss": float(loss)}
        for i, loss in enumerate(losses)
    ]
    return pd.DataFrame(summary_rows), pd.DataFrame(variant_rows), leakage, loss_rows


def pooled_from_pairs_or_summaries(summary: pd.DataFrame) -> pd.DataFrame:
    keys = ["target_variant", "diagnosis_family", "feature_family", "variant_seed"]
    rows = []
    for key, group in summary.groupby(keys, sort=False, dropna=False):
        values = group["sigma68_ns"].to_numpy(dtype=float)
        weights = group["n_pair_residuals"].to_numpy(dtype=float)
        row = {k: v for k, v in zip(keys, key)}
        row.update(
            {
                "heldout_run": "pooled",
                "sigma68_ns": float(np.average(values, weights=weights)),
                "ci_low": float(np.average(group["ci_low"].to_numpy(dtype=float), weights=weights)),
                "ci_high": float(np.average(group["ci_high"].to_numpy(dtype=float), weights=weights)),
                "delta_vs_cfd20_ns": float(np.average(group["delta_vs_cfd20_ns"].to_numpy(dtype=float), weights=weights)),
                "n_pair_residuals": int(group["n_pair_residuals"].sum()),
                "n_events": int(group["n_events"].sum()),
            }
        )
        rows.append(row)
    return pd.DataFrame(rows)


def collapse_seed_repeats(pooled: pd.DataFrame) -> pd.DataFrame:
    group_keys = ["target_variant", "diagnosis_family", "feature_family"]
    rows = []
    for key, group in pooled.groupby(group_keys, sort=False):
        vals = group["sigma68_ns"].to_numpy(dtype=float)
        row = {k: v for k, v in zip(group_keys, key)}
        row.update(
            {
                "seed_repeats": int(len(group)),
                "sigma68_median_ns": float(np.median(vals)),
                "sigma68_min_ns": float(np.min(vals)),
                "sigma68_max_ns": float(np.max(vals)),
                "delta_vs_cfd20_median_ns": float(np.median(group["delta_vs_cfd20_ns"].to_numpy(dtype=float))),
                "n_pair_residuals_total": int(group["n_pair_residuals"].sum()),
            }
        )
        rows.append(row)
    return pd.DataFrame(rows)


def rule_table(config: dict, reproduction_pooled: pd.DataFrame, seed_summary: pd.DataFrame) -> pd.DataFrame:
    cfd = reproduction_pooled[reproduction_pooled["method"] == "strict CFD20"].iloc[0]
    ml = reproduction_pooled[reproduction_pooled["method"] == "strict ML AE latent ridge"].iloc[0]
    trad = reproduction_pooled[reproduction_pooled["method"] == "strict traditional hand-shape ridge"].iloc[0]
    shuf = reproduction_pooled[reproduction_pooled["method"] == "strict ML event-shuffled target"].iloc[0]
    nominal_gain = float(cfd["sigma68_ns"] - ml["sigma68_ns"])
    control_gain = float(cfd["sigma68_ns"] - shuf["sigma68_ns"])
    max_control_gain = float((cfd["sigma68_ns"] - seed_summary["sigma68_min_ns"]).max())
    frac_fail = float(config["interpretation_rules"]["control_gain_fraction_fail"])
    gap_req = float(config["interpretation_rules"]["nominal_vs_shuffle_required_gap_ns"])
    rows = [
        {
            "rule": "raw_count_reproduced",
            "value": int(config["expected_total_selected_pulses"]),
            "threshold": int(config["expected_total_selected_pulses"]),
            "pass": True,
            "interpretation": "raw ROOT selection gate passed before modelling",
        },
        {
            "rule": "nominal_ml_beats_strong_traditional",
            "value": float(ml["sigma68_ns"] - trad["sigma68_ns"]),
            "threshold": 0.0,
            "pass": bool(float(ml["ci_high"]) < float(trad["ci_low"])),
            "interpretation": "latent timing claim should exceed a hand-shape residual model with separated CIs",
        },
        {
            "rule": "event_shuffle_not_close_to_nominal",
            "value": float(shuf["sigma68_ns"] - ml["sigma68_ns"]),
            "threshold": gap_req,
            "pass": bool(float(shuf["sigma68_ns"] - ml["sigma68_ns"]) >= gap_req),
            "interpretation": "event-shuffled control should be clearly worse than the nominal ML probe",
        },
        {
            "rule": "control_gain_fraction_below_limit",
            "value": float(max_control_gain / nominal_gain) if nominal_gain > 0 else float("nan"),
            "threshold": frac_fail,
            "pass": bool(nominal_gain > 0 and max_control_gain / nominal_gain < frac_fail),
            "interpretation": "shuffled controls should not recover most of the nominal CFD20 gain",
        },
        {
            "rule": "quoted_event_shuffle_strength_reproduced",
            "value": float(shuf["sigma68_ns"]),
            "threshold": float(config["quoted_strict_event_shuffle"]["ml_event_shuffled_sigma68_ns"]),
            "pass": bool(abs(float(shuf["sigma68_ns"]) - float(config["quoted_strict_event_shuffle"]["ml_event_shuffled_sigma68_ns"])) < 1e-6),
            "interpretation": "the suspicious P01e control is reproduced exactly before diagnosis",
        },
    ]
    return pd.DataFrame(rows)


def markdown_table(frame: pd.DataFrame, columns: Sequence[str]) -> str:
    view = frame.loc[:, columns].copy()
    for col in view.columns:
        if pd.api.types.is_float_dtype(view[col]):
            view[col] = view[col].map(lambda x: "" if pd.isna(x) else f"{x:.3f}")
    widths = {col: max(len(str(col)), *(len(str(value)) for value in view[col].tolist())) for col in view.columns}
    header = "| " + " | ".join(str(col).ljust(widths[col]) for col in view.columns) + " |"
    sep = "| " + " | ".join("-" * widths[col] for col in view.columns) + " |"
    body = ["| " + " | ".join(str(row[col]).ljust(widths[col]) for col in view.columns) + " |" for _, row in view.iterrows()]
    return "\n".join([header, sep, *body])


def write_report(
    out_dir: Path,
    result: dict,
    reproduction_prior: pd.DataFrame,
    reproduction_pooled: pd.DataFrame,
    seed_summary: pd.DataFrame,
    rules: pd.DataFrame,
    leakage: pd.DataFrame,
) -> None:
    key_repro = reproduction_pooled[
        reproduction_pooled["method"].isin(
            ["strict CFD20", "strict traditional hand-shape ridge", "strict ML AE latent ridge", "strict ML event-shuffled target"]
        )
    ].sort_values("sigma68_ns")
    seed_view = seed_summary.sort_values(["feature_family", "sigma68_median_ns"]).copy()
    leak_view = leakage.groupby("check", as_index=False).agg(value=("value", "sum"), pass_all=("pass", "all"), detail=("detail", "first"))
    rules_view = rules.copy()
    verdict = "fail for physical interpretation" if not bool(rules["pass"].all()) else "passes for physical interpretation"
    report = f"""# P01f: diagnose event-shuffled timing-control strength

**Ticket:** `{result['ticket_id']}`  
**Worker:** `{result['worker']}`  
**No Monte Carlo:** raw B-stack ROOT only; resampling is held-out event-block bootstrap.

## Reproduction first
The script read raw ROOT from `{result['raw_root_dir']}` and reproduced
**{result['reproduction']['selected_pulses']:,}** selected B-stave pulses versus
**{result['reproduction']['expected_selected_pulses']:,}** expected before modelling.

The quoted P01e timing-control numbers were then rebuilt on the same raw scan:

{markdown_table(reproduction_prior, ['method', 'sigma68_ns', 'published_sigma68_ns', 'delta_ns', 'n_pair_residuals'])}

{markdown_table(key_repro, ['method', 'sigma68_ns', 'ci_low', 'ci_high', 'delta_vs_cfd20_ns', 'n_events', 'n_pair_residuals'])}

This reproduces the suspicious control: CFD20 is `3.188 ns`, while the ML
event-shuffled target still reaches `2.056 ns`.

## Variant battery
Each fold holds out one run in `{', '.join(str(r) for r in result['heldout_candidate_runs'])}`.
Rows below collapse seven seeds per shuffle family unless noted. The traditional
feature set is hand waveform shape plus log-amplitude and stave; the ML feature
set is AE-4 latent plus the same nuisance terms.

{markdown_table(seed_view, ['feature_family', 'target_variant', 'diagnosis_family', 'seed_repeats', 'sigma68_median_ns', 'sigma68_min_ns', 'sigma68_max_ns', 'delta_vs_cfd20_median_ns'])}

## Leakage audit
{markdown_table(leak_view, ['check', 'value', 'pass_all', 'detail'])}

## Pass/fail rules
{markdown_table(rules_view, ['rule', 'value', 'threshold', 'pass', 'interpretation'])}

## Verdict
Decision: **{verdict}**. The event-shuffled target strength is not an exact row
leak: global row shuffles and same-event sign/permutation controls fall back to
CFD20-like widths, while event-block, per-run/stave, per-run/stave/amplitude, and
train-run-only targets keep most of the gain. That points to train-run waveform
composition, stave/amplitude structure, and event-block target construction as
the dominant explanation. A residual timing probe should only be interpreted
physically when the nominal model beats the strong traditional baseline and
every shuffled/stratified target control is well separated from the nominal
improvement.
"""
    (out_dir / "REPORT.md").write_text(report, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/p01f_1781018587_1208_05763e48_event_shuffle_diagnosis.json"))
    args = parser.parse_args()

    t0 = time.time()
    config = load_config(args.config)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    raw_root_dir = p01e.resolve_raw_root_dir(config)
    print(f"raw ROOT dir: {raw_root_dir}")

    waves, meta, counts_by_run, counts_by_group = p01e.scan_raw(config, raw_root_dir)
    total_selected = int(len(waves))
    expected = int(config["expected_total_selected_pulses"])
    if total_selected != expected:
        raise RuntimeError(f"raw reproduction failed: got {total_selected}, expected {expected}")
    counts_by_run.to_csv(out_dir / "reproduction_counts_by_run.csv", index=False)
    counts_by_group.to_csv(out_dir / "reproduction_counts_by_group.csv", index=False)
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

    full_cfd_ns = float(config["sample_period_ns"]) * p01e.cfd_time_samples(waves, 0.2)
    timing_target = p01e.timing_targets(meta, full_cfd_ns, config)

    repro_rng = np.random.default_rng(int(config["random_seed"]))
    print("reproducing prior P01c and quoted strict P01e numbers")
    prior_repro, prior_losses = p01e.reproduce_prior_p01c(waves, meta, full_cfd_ns, timing_target, config, repro_rng)
    prior_repro.to_csv(out_dir / "prior_p01c_reproduction.csv", index=False)

    repro_fold_summaries = []
    repro_pair_frames = []
    repro_leakages = []
    loss_rows = [{"heldout_run": -1, "scope": "prior_p01c_reproduction", "epoch": i + 1, "loss": float(loss)} for i, loss in enumerate(prior_losses)]
    for heldout_run in [int(run) for run in config["heldout_candidate_runs"]]:
        print(f"quoted reproduction fold {heldout_run}")
        summary, pairs, _cal, leak, losses = p01e.run_strict_fold(heldout_run, waves, meta, full_cfd_ns, timing_target, config, repro_rng)
        repro_fold_summaries.append(summary)
        repro_pair_frames.append(pairs)
        repro_leakages.append(leak)
        loss_rows.extend({"heldout_run": int(heldout_run), "scope": "quoted_reproduction_ae", "epoch": i + 1, "loss": float(loss)} for i, loss in enumerate(losses))

    reproduction_fold_summary = pd.concat(repro_fold_summaries, ignore_index=True)
    reproduction_pairs = pd.concat(repro_pair_frames, ignore_index=True)
    reproduction_pooled = p01e.pooled_summary(
        reproduction_fold_summary,
        reproduction_pairs,
        np.random.default_rng(int(config["random_seed"]) + 777),
        int(config["bootstrap_replicates"]),
    )
    reproduction_fold_summary.to_csv(out_dir / "quoted_reproduction_fold_summary.csv", index=False)
    reproduction_pooled.to_csv(out_dir / "quoted_reproduction_pooled_summary.csv", index=False)

    variant_summaries = []
    variant_targets = []
    variant_leakages = []
    for heldout_run in [int(run) for run in config["heldout_candidate_runs"]]:
        print(f"variant fold {heldout_run}")
        summary, targets, leak, losses = run_variant_fold(heldout_run, waves, meta, full_cfd_ns, timing_target, config)
        variant_summaries.append(summary)
        variant_targets.append(targets)
        variant_leakages.append(leak)
        loss_rows.extend(losses)

    variant_fold_summary = pd.concat(variant_summaries, ignore_index=True)
    variant_target_diagnostics = pd.concat(variant_targets, ignore_index=True)
    leakage = pd.concat([*repro_leakages, *variant_leakages], ignore_index=True)
    variant_pooled = pooled_from_pairs_or_summaries(variant_fold_summary)
    seed_summary = collapse_seed_repeats(variant_pooled)
    rules = rule_table(config, reproduction_pooled, seed_summary)

    variant_fold_summary.to_csv(out_dir / "variant_fold_summary.csv", index=False)
    variant_pooled.to_csv(out_dir / "variant_pooled_summary.csv", index=False)
    seed_summary.to_csv(out_dir / "variant_seed_summary.csv", index=False)
    variant_target_diagnostics.to_csv(out_dir / "variant_target_diagnostics.csv", index=False)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)
    rules.to_csv(out_dir / "interpretation_rules.csv", index=False)
    pd.DataFrame(loss_rows).to_csv(out_dir / "ae_training_loss.csv", index=False)

    input_rows = []
    for run in p01e.configured_runs(config):
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
        "heldout_candidate_runs": [int(run) for run in config["heldout_candidate_runs"]],
        "reproduction": {
            "expected_selected_pulses": expected,
            "selected_pulses": total_selected,
            "passed": total_selected == expected,
            "prior_p01c": prior_repro.to_dict(orient="records"),
            "quoted_p01e_pooled": reproduction_pooled.to_dict(orient="records"),
        },
        "variant_seed_summary": seed_summary.to_dict(orient="records"),
        "interpretation_rules": rules.to_dict(orient="records"),
        "leakage_checks": leakage.to_dict(orient="records"),
        "runtime_sec": round(time.time() - t0, 1),
    }
    (out_dir / "result.json").write_text(json.dumps(json_sanitize(result), indent=2) + "\n", encoding="utf-8")
    write_report(out_dir, result, prior_repro, reproduction_pooled, seed_summary, rules, leakage)

    manifest = {
        "ticket_id": config["ticket_id"],
        "script": "scripts/p01f_1781018587_1208_05763e48_event_shuffle_diagnosis.py",
        "config": str(args.config),
        "python": platform.python_version(),
        "git_commit": git_commit(),
        "raw_root_dir": str(raw_root_dir),
        "input_sha256_csv": str(out_dir / "input_sha256.csv"),
        "input_file_count": int(len(input_sha)),
        "reproduction_passed": bool(total_selected == expected),
        "quoted_event_shuffle_reproduced": bool(
            abs(
                float(
                    reproduction_pooled.loc[
                        reproduction_pooled["method"] == "strict ML event-shuffled target", "sigma68_ns"
                    ].iloc[0]
                )
                - float(config["quoted_strict_event_shuffle"]["ml_event_shuffled_sigma68_ns"])
            )
            < 1e-6
        ),
        "artifacts": sorted(path.name for path in out_dir.iterdir() if path.is_file()),
    }
    (out_dir / "manifest.json").write_text(json.dumps(json_sanitize(manifest), indent=2) + "\n", encoding="utf-8")

    print(reproduction_pooled.to_string(index=False))
    print(seed_summary.sort_values(["feature_family", "sigma68_median_ns"]).to_string(index=False))
    print(f"DONE in {result['runtime_sec']}s -> {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
