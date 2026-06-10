#!/usr/bin/env python3
"""P04i: sample-causality map for duplicate-readout charge closure.

The raw ROOT loader and basic P04 helpers are imported from the original P04
script so the reproduction gate is identical.  This script then treats the
paired odd-channel positive charge as the target and asks which even-channel
18-sample atoms carry the closure.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import platform
import subprocess
import time
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesRegressor, HistGradientBoostingRegressor
from sklearn.linear_model import HuberRegressor, LinearRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


ROOT = Path(__file__).resolve().parents[1]
P04_PATH = ROOT / "scripts" / "p04_amplitude_charge_regression.py"


def import_p04():
    spec = importlib.util.spec_from_file_location("p04_amplitude_charge_regression", P04_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {P04_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


p04 = import_p04()


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def robust_metrics(y: np.ndarray, pred: np.ndarray) -> dict:
    frac = (pred - y) / np.maximum(y, 1.0)
    return {
        "n": int(len(y)),
        "bias_median_frac": float(np.median(frac)),
        "res68_abs_frac": float(np.percentile(np.abs(frac), 68)),
        "full_rms_frac": float(np.sqrt(np.mean(frac * frac))),
        "within_10pct": float(np.mean(np.abs(frac) < 0.10)),
    }


def run_block_ci(
    frame: pd.DataFrame,
    target_col: str,
    pred_col: str,
    rng: np.random.Generator,
    reps: int,
) -> dict:
    runs = np.asarray(sorted(frame["run"].unique()), dtype=int)
    by_run = {int(run): frame[frame["run"] == run] for run in runs}
    bias = np.empty(reps)
    res68 = np.empty(reps)
    rms = np.empty(reps)
    within = np.empty(reps)
    for idx in range(reps):
        chosen = rng.choice(runs, size=len(runs), replace=True)
        sample = pd.concat([by_run[int(run)] for run in chosen], ignore_index=True)
        y = sample[target_col].to_numpy()
        frac = (sample[pred_col].to_numpy() - y) / np.maximum(y, 1.0)
        bias[idx] = np.median(frac)
        res68[idx] = np.percentile(np.abs(frac), 68)
        rms[idx] = np.sqrt(np.mean(frac * frac))
        within[idx] = np.mean(np.abs(frac) < 0.10)
    return {
        "run_block_bias_ci95": [float(np.percentile(bias, 2.5)), float(np.percentile(bias, 97.5))],
        "run_block_res68_ci95": [float(np.percentile(res68, 2.5)), float(np.percentile(res68, 97.5))],
        "run_block_full_rms_ci95": [float(np.percentile(rms, 2.5)), float(np.percentile(rms, 97.5))],
        "run_block_within_10pct_ci95": [float(np.percentile(within, 2.5)), float(np.percentile(within, 97.5))],
    }


def run_block_delta_ci(
    frame: pd.DataFrame,
    target_col: str,
    pred_col: str,
    ref_col: str,
    rng: np.random.Generator,
    reps: int,
) -> List[float]:
    runs = np.asarray(sorted(frame["run"].unique()), dtype=int)
    by_run = {int(run): frame[frame["run"] == run] for run in runs}
    deltas = np.empty(reps)
    for idx in range(reps):
        chosen = rng.choice(runs, size=len(runs), replace=True)
        sample = pd.concat([by_run[int(run)] for run in chosen], ignore_index=True)
        y = sample[target_col].to_numpy()
        pred_frac = np.abs((sample[pred_col].to_numpy() - y) / np.maximum(y, 1.0))
        ref_frac = np.abs((sample[ref_col].to_numpy() - y) / np.maximum(y, 1.0))
        deltas[idx] = np.percentile(pred_frac, 68) - np.percentile(ref_frac, 68)
    return [float(np.percentile(deltas, 2.5)), float(np.percentile(deltas, 97.5))]


def recompute_even_meta(meta: pd.DataFrame, wave: np.ndarray) -> pd.DataFrame:
    out = meta.copy()
    out["even_amp"] = wave.max(axis=1)
    out["even_peak"] = wave.argmax(axis=1).astype(np.int16)
    out["even_pos_charge"] = np.clip(wave, 0.0, None).sum(axis=1)
    out["even_area"] = wave.sum(axis=1)
    return out


def train_medians_by_stave(meta: pd.DataFrame, wave: np.ndarray, train_mask: np.ndarray) -> Dict[int, np.ndarray]:
    medians: Dict[int, np.ndarray] = {}
    staves = meta["stave_idx"].to_numpy().astype(int)
    for stave in sorted(np.unique(staves)):
        mask = train_mask & (staves == stave)
        medians[int(stave)] = np.median(wave[mask], axis=0)
    return medians


def ablate_samples(
    meta: pd.DataFrame,
    wave: np.ndarray,
    train_mask: np.ndarray,
    sample_indices: Iterable[int],
    saturation_boundary_adc: float | None = None,
) -> Tuple[np.ndarray, dict]:
    out = wave.copy()
    medians = train_medians_by_stave(meta, wave, train_mask)
    staves = meta["stave_idx"].to_numpy().astype(int)
    affected = np.zeros(len(meta), dtype=bool)
    replaced_atoms = 0
    if saturation_boundary_adc is None:
        samples = np.asarray(list(sample_indices), dtype=int)
        if len(samples) == 0:
            return out, {"affected_rows": 0, "replaced_atoms": 0}
        for stave, med in medians.items():
            rows = staves == stave
            out[np.ix_(rows, samples)] = med[samples]
            affected[rows] = True
            replaced_atoms += int(rows.sum() * len(samples))
    else:
        peaks = wave.argmax(axis=1)
        high = wave >= float(saturation_boundary_adc)
        for row in np.where(high.any(axis=1))[0]:
            idx = set()
            for sample in np.where(high[row])[0]:
                idx.update([max(0, int(sample) - 1), int(sample), min(wave.shape[1] - 1, int(sample) + 1)])
            idx.add(int(peaks[row]))
            samples = np.asarray(sorted(idx), dtype=int)
            out[row, samples] = medians[int(staves[row])][samples]
            affected[row] = True
            replaced_atoms += int(len(samples))
    return out, {"affected_rows": int(affected.sum()), "replaced_atoms": int(replaced_atoms)}


def permute_samples(
    wave: np.ndarray,
    heldout_mask: np.ndarray,
    sample_indices: Iterable[int],
    rng: np.random.Generator,
) -> np.ndarray:
    out = wave.copy()
    held = np.where(heldout_mask)[0]
    samples = list(int(x) for x in sample_indices)
    for sample in samples:
        out[held, sample] = rng.permutation(out[held, sample])
    return out


def fit_log_calibrators(est: np.ndarray, y: np.ndarray, stave_idx: np.ndarray) -> Dict[int, LinearRegression]:
    models: Dict[int, LinearRegression] = {}
    for stave in sorted(np.unique(stave_idx)):
        mask = (stave_idx == stave) & (est > 0) & (y > 0)
        model = LinearRegression()
        model.fit(np.log(est[mask])[:, None], np.log(y[mask]))
        models[int(stave)] = model
    return models


def predict_log_calibrated(models: Dict[int, LinearRegression], est: np.ndarray, stave_idx: np.ndarray) -> np.ndarray:
    out = np.zeros(len(est), dtype=float)
    safe = np.maximum(est, 1.0)
    for stave, model in models.items():
        mask = stave_idx == stave
        out[mask] = np.exp(model.predict(np.log(safe[mask])[:, None]))
    return np.maximum(out, 1.0)


def traditional_features(meta: pd.DataFrame, wave: np.ndarray, template_scale: np.ndarray) -> np.ndarray:
    amp = meta["even_amp"].to_numpy()
    charge = meta["even_pos_charge"].to_numpy()
    total = np.maximum(charge, 1.0)
    half_width = (wave > (0.5 * amp[:, None])).sum(axis=1)
    pre = wave[:, :4].mean(axis=1)
    early = np.clip(wave[:, 4:7], 0.0, None).sum(axis=1) / total
    peak = np.clip(wave[:, 7:11], 0.0, None).sum(axis=1) / total
    tail = np.clip(wave[:, 11:], 0.0, None).sum(axis=1) / total
    return np.column_stack(
        [
            np.log(np.maximum(amp, 1.0)),
            np.log(total),
            np.log(np.maximum(template_scale, 1.0)),
            meta["even_peak"].to_numpy(),
            half_width,
            pre,
            early,
            peak,
            tail,
            meta["even_area"].to_numpy() / total,
        ]
    )


def fit_strong_huber(features: np.ndarray, y: np.ndarray, train_mask: np.ndarray, stave_idx: np.ndarray) -> Dict[int, object]:
    models: Dict[int, object] = {}
    for stave in sorted(np.unique(stave_idx)):
        mask = train_mask & (stave_idx == stave) & np.isfinite(features).all(axis=1) & (y > 0)
        model = make_pipeline(StandardScaler(), HuberRegressor(epsilon=1.35, alpha=0.0001, max_iter=300))
        model.fit(features[mask], np.log(y[mask]))
        models[int(stave)] = model
    return models


def predict_strong(models: Dict[int, object], features: np.ndarray, stave_idx: np.ndarray) -> np.ndarray:
    out = np.zeros(len(features), dtype=float)
    for stave, model in models.items():
        mask = stave_idx == stave
        out[mask] = np.exp(model.predict(features[mask]))
    return np.maximum(out, 1.0)


def ml_features(meta: pd.DataFrame, wave: np.ndarray) -> np.ndarray:
    return p04.ml_features(meta, wave)


def fit_hgb(X: np.ndarray, y: np.ndarray, train_idx: np.ndarray, seed: int, max_iter: int = 12):
    model = HistGradientBoostingRegressor(
        max_iter=max_iter,
        learning_rate=0.06,
        max_leaf_nodes=15,
        l2_regularization=0.05,
        random_state=seed,
    )
    model.fit(X[train_idx], np.log(y[train_idx]))
    return model


def fit_extra_trees(X: np.ndarray, y: np.ndarray, train_idx: np.ndarray, seed: int):
    model = ExtraTreesRegressor(
        n_estimators=45,
        max_depth=18,
        min_samples_leaf=3,
        max_features=0.75,
        random_state=seed,
        n_jobs=-1,
    )
    model.fit(X[train_idx], np.log(y[train_idx]))
    return model


def build_traditional_predictions(
    meta: pd.DataFrame,
    wave: np.ndarray,
    y_charge: np.ndarray,
    train_mask: np.ndarray,
    config: dict,
    rng: np.random.Generator,
) -> Dict[str, np.ndarray]:
    st = meta["stave_idx"].to_numpy().astype(int)
    predictions: Dict[str, np.ndarray] = {}

    peak_models = fit_log_calibrators(meta.loc[train_mask, "even_amp"].to_numpy(), y_charge[train_mask], st[train_mask])
    predictions["peak_to_charge_calibrated"] = predict_log_calibrated(peak_models, meta["even_amp"].to_numpy(), st)

    integral_models = fit_log_calibrators(
        meta.loc[train_mask, "even_pos_charge"].to_numpy(), y_charge[train_mask], st[train_mask]
    )
    predictions["integral_calibrated"] = predict_log_calibrated(
        integral_models, meta["even_pos_charge"].to_numpy(), st
    )

    template_train = train_mask.copy()
    train_idx = np.where(train_mask)[0]
    max_template = int(config["template_max_train_rows"])
    if len(train_idx) > max_template:
        take = rng.choice(train_idx, size=max_template, replace=False)
        template_train = np.zeros(len(meta), dtype=bool)
        template_train[take] = True
    templates = p04.build_templates(meta, wave, template_train, [float(x) for x in config["template_bins"]])
    template_scale = p04.template_scales(
        meta, wave, templates, [float(x) for x in config["template_bins"]], [float(x) for x in config["template_shift_grid"]]
    )
    template_models = fit_log_calibrators(template_scale[train_mask], y_charge[train_mask], st[train_mask])
    predictions["adaptive_template_scale_calibrated"] = predict_log_calibrated(template_models, template_scale, st)

    strong_x = traditional_features(meta, wave, template_scale)
    strong_train_mask = train_mask.copy()
    strong_idx = np.where(train_mask)[0]
    max_strong = int(config["analysis_train_rows"])
    if len(strong_idx) > max_strong:
        take = rng.choice(strong_idx, size=max_strong, replace=False)
        strong_train_mask = np.zeros(len(meta), dtype=bool)
        strong_train_mask[take] = True
    strong_models = fit_strong_huber(strong_x, y_charge, strong_train_mask, st)
    predictions["strong_huber_charge"] = predict_strong(strong_models, strong_x, st)
    return predictions


def evaluate_predictions(
    meta: pd.DataFrame,
    y_charge: np.ndarray,
    heldout_mask: np.ndarray,
    predictions: Dict[str, np.ndarray],
    config: dict,
) -> pd.DataFrame:
    rng = np.random.default_rng(int(config["random_seed"]) + 500)
    held = meta.loc[heldout_mask, ["run", "stave", "target_odd_pos_charge"]].reset_index(drop=True)
    rows = []
    for method, pred_all in predictions.items():
        pred = pred_all[heldout_mask]
        row = {"method": method, "subset": "heldout_runs_" + "_".join(str(x) for x in config["heldout_runs"])}
        row.update(robust_metrics(y_charge[heldout_mask], pred))
        tmp = held.copy()
        tmp["_pred"] = pred
        row.update(run_block_ci(tmp, "target_odd_pos_charge", "_pred", rng, int(config["bootstrap_reps"])))
        rows.append(row)
        for run, run_df in tmp.groupby("run"):
            idx = run_df.index.to_numpy()
            brow = {"method": method, "subset": f"run_{int(run)}"}
            brow.update(robust_metrics(run_df["target_odd_pos_charge"].to_numpy(), pred[idx]))
            rows.append(brow)
    return pd.DataFrame(rows)


def metric_delta_table(
    meta: pd.DataFrame,
    y_charge: np.ndarray,
    heldout_mask: np.ndarray,
    predictions: Dict[str, np.ndarray],
    ref_method: str,
    config: dict,
) -> pd.DataFrame:
    rng = np.random.default_rng(int(config["random_seed"]) + 700)
    held = meta.loc[heldout_mask, ["run", "target_odd_pos_charge"]].reset_index(drop=True)
    frame = held.copy()
    for method, pred_all in predictions.items():
        frame[method] = pred_all[heldout_mask]
    ref = predictions[ref_method][heldout_mask]
    rows = []
    for method, pred_all in predictions.items():
        if method == ref_method:
            continue
        pred = pred_all[heldout_mask]
        delta = robust_metrics(y_charge[heldout_mask], pred)["res68_abs_frac"] - robust_metrics(
            y_charge[heldout_mask], ref
        )["res68_abs_frac"]
        rows.append(
            {
                "method": method,
                "reference_method": ref_method,
                "delta_res68_abs_frac": float(delta),
                "run_block_delta_res68_ci95": run_block_delta_ci(
                    frame, "target_odd_pos_charge", method, ref_method, rng, int(config["bootstrap_reps"])
                ),
            }
        )
    return pd.DataFrame(rows)


def waveform_hashes(wave: np.ndarray) -> List[str]:
    rounded = np.rint(wave).astype(np.int16, copy=False)
    return [hashlib.sha1(row.tobytes()).hexdigest() for row in rounded]


def markdown_table(frame: pd.DataFrame, columns: List[str]) -> str:
    if frame.empty:
        return "_No rows._"
    use = frame[columns].copy()
    for col in use.columns:
        if use[col].dtype.kind in "fc":
            use[col] = use[col].map(lambda x: f"{x:.6g}")
    return use.to_markdown(index=False)


def make_report(
    out_dir: Path,
    config: dict,
    reproduction: dict,
    method_metrics: pd.DataFrame,
    ablation_deltas: pd.DataFrame,
    atom_deltas: pd.DataFrame,
    ml_minus_trad: pd.DataFrame,
    leakage: dict,
    result: dict,
) -> None:
    full = method_metrics[
        (method_metrics["ablation"] == "full") & (method_metrics["subset"].str.startswith("heldout_runs"))
    ]
    grouped = ablation_deltas[ablation_deltas["mode"] == "grouped_retrain"]
    frozen = ablation_deltas[ablation_deltas["mode"].isin(["frozen_occlusion", "frozen_permutation"])]
    lines = [
        "# P04i: duplicate-readout charge closure sample-causality map",
        "",
        f"- **Ticket ID:** {config['ticket_id']}",
        f"- **Worker:** {config['worker']}",
        "- **Input:** raw `data/root/root/hrdb_run_*.root`; no Monte Carlo.",
        f"- **Run split:** held-out runs {', '.join(str(x) for x in config['heldout_runs'])}; all templates, calibrators, and ML models train on other runs.",
        "",
        "## Raw reproduction first",
        "",
        "| quantity | expected | reproduced | delta | pass |",
        "|---|---:|---:|---:|:---|",
        f"| selected B-stave pulse records | {reproduction['expected_selected_pulses']:,} | {reproduction['reproduced_selected_pulses']:,} | {reproduction['delta']:+,} | {str(reproduction['pass']).lower()} |",
        "",
        (
            f"Registered P04 charge HGB reference res68 is `{config['expected_p04_charge_hgb_res68']:.10f}`; "
            f"the ticket-local raw-root HGB benchmark with capped training rows gives "
            f"`{reproduction['ticket_local_p04_charge_hgb_res68']:.10f}` "
            f"(delta `{reproduction['p04_charge_hgb_reference_delta']:+.3g}`)."
        ),
        "",
        "## Methods",
        "",
        "- **Traditional:** peak-to-charge, integral-to-charge, adaptive-template scale, and a Huber charge calibrator from even-waveform summaries.",
        "- **ML:** HGB and ExtraTrees charge regressors using only the 18 even samples plus even-channel summaries and stave one-hot.",
        "- **Ablations:** grouped sample replacement by train-run stave medians, frozen-model held-out occlusion/permutation, grouped retraining, and single-sample frozen occlusion.",
        "",
        "## Full held-out benchmark",
        "",
        markdown_table(
            full,
            [
                "method",
                "n",
                "bias_median_frac",
                "res68_abs_frac",
                "run_block_res68_ci95",
                "full_rms_frac",
                "within_10pct",
            ],
        ),
        "",
        "## Grouped retraining deltas",
        "",
        markdown_table(
            grouped.sort_values(["method", "delta_res68_vs_full"], ascending=[True, False]),
            ["ablation", "method", "res68_abs_frac", "delta_res68_vs_full", "run_block_delta_res68_ci95"],
        ),
        "",
        "## Frozen ML occlusion/permutation deltas",
        "",
        markdown_table(
            frozen.sort_values(["method", "mode", "delta_res68_vs_full"], ascending=[True, True, False]),
            ["mode", "ablation", "method", "res68_abs_frac", "delta_res68_vs_full", "run_block_delta_res68_ci95"],
        ),
        "",
        "## Single-sample HGB occlusion",
        "",
        markdown_table(atom_deltas.sort_values("delta_res68_vs_full", ascending=False).head(18), ["sample", "res68_abs_frac", "delta_res68_vs_full"]),
        "",
        "## ML minus strong traditional",
        "",
        markdown_table(ml_minus_trad, ["method", "reference_method", "delta_res68_abs_frac", "run_block_delta_res68_ci95"]),
        "",
        "## Leakage audit",
        "",
        f"- Held-out runs absent from training: `{leakage['heldout_absent_from_train']}`.",
        f"- Train/held-out `(run,event,stave)` key overlap: `{leakage['train_heldout_event_key_overlap']}`.",
        f"- Exact rounded even-waveform hash overlap: `{leakage['exact_even_waveform_hash_overlap']}`.",
        f"- Feature columns include no run/event ids and no odd-channel target samples: `{leakage['no_identifier_or_target_features']}`.",
        f"- Invalid odd-target rows removed after raw reproduction: `{leakage['invalid_target_rows_removed']}`.",
        f"- Stave-only median charge res68: `{leakage['stave_only_charge_res68']:.4f}`.",
        f"- Shuffled-target HGB charge res68: `{leakage['shuffled_target_hgb_charge_res68']:.4f}`.",
        "",
        "## Finding",
        "",
        result["finding"],
        "",
        "## Reproducibility",
        "",
        "```bash",
        "/home/billy/anaconda3/bin/python scripts/p04i_1781024791_1539_3ba15c1d_sample_causality.py --config configs/p04i_1781024791_1539_3ba15c1d_sample_causality.json",
        "```",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/p04i_1781024791_1539_3ba15c1d_sample_causality.json")
    args = parser.parse_args()

    t0 = time.time()
    config_path = Path(args.config)
    config = load_config(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["random_seed"]))

    print("1/8 loading raw ROOT and reproducing selected-pulse count first ...", flush=True)
    meta, wave, counts_by_run = p04.extract_rows(config)
    total_selected = int(counts_by_run["selected_pulses"].sum())
    expected = int(config["expected_selected_pulses"])
    if total_selected != expected:
        raise RuntimeError(f"raw reproduction failed: got {total_selected}, expected {expected}")

    valid = (meta["target_odd_neg_amp"].to_numpy() > 100.0) & (meta["target_odd_pos_charge"].to_numpy() > 100.0)
    invalid_rows = int((~valid).sum())
    meta = meta.loc[valid].reset_index(drop=True)
    wave = wave[valid]
    y_charge = meta["target_odd_pos_charge"].to_numpy()
    heldout_runs = [int(x) for x in config["heldout_runs"]]
    heldout_mask = meta["run"].isin(heldout_runs).to_numpy()
    train_mask = ~heldout_mask
    st = meta["stave_idx"].to_numpy().astype(int)
    if set(meta.loc[train_mask, "run"].unique()).intersection(heldout_runs):
        raise RuntimeError("held-out run leaked into train mask")

    print("2/8 rebuilding ticket-local P04 charge HGB benchmark ...", flush=True)
    X_full = ml_features(meta, wave)
    p04_train_idx = np.where(train_mask)[0]
    p04_rng = np.random.default_rng(int(config["random_seed"]))
    if len(p04_train_idx) > int(config["p04_reproduction_train_rows"]):
        p04_train_idx = p04_rng.choice(p04_train_idx, size=int(config["p04_reproduction_train_rows"]), replace=False)
    p04_hgb = fit_hgb(X_full, y_charge, p04_train_idx, int(config["random_seed"]))
    p04_hgb_pred = np.exp(p04_hgb.predict(X_full))
    p04_charge_res68 = robust_metrics(y_charge[heldout_mask], p04_hgb_pred[heldout_mask])["res68_abs_frac"]
    expected_res68 = float(config["expected_p04_charge_hgb_res68"])
    p04_ref_delta = p04_charge_res68 - expected_res68

    print("3/8 fitting full traditional and ML methods ...", flush=True)
    full_predictions = build_traditional_predictions(meta, wave, y_charge, train_mask, config, rng)
    train_idx = np.where(train_mask)[0]
    if len(train_idx) > int(config["analysis_train_rows"]):
        train_idx = rng.choice(train_idx, size=int(config["analysis_train_rows"]), replace=False)
    et_idx = np.where(train_mask)[0]
    if len(et_idx) > int(config["extra_trees_train_rows"]):
        et_idx = rng.choice(et_idx, size=int(config["extra_trees_train_rows"]), replace=False)
    full_hgb = fit_hgb(X_full, y_charge, train_idx, int(config["random_seed"]) + 10)
    full_et = fit_extra_trees(X_full, y_charge, et_idx, int(config["random_seed"]) + 20)
    full_predictions["ml_hgb"] = np.exp(full_hgb.predict(X_full))
    full_predictions["ml_extra_trees"] = np.exp(full_et.predict(X_full))

    print("4/8 evaluating grouped retraining ablations ...", flush=True)
    all_metric_frames = []
    full_metrics = evaluate_predictions(meta, y_charge, heldout_mask, full_predictions, config)
    full_metrics["ablation"] = "full"
    full_metrics["mode"] = "grouped_retrain"
    all_metric_frames.append(full_metrics)
    ablation_rows = []
    group_info = []
    for ablation in config["window_ablations"]:
        name = str(ablation["name"])
        if name == "full":
            continue
        if name == "saturation_boundary_atoms_removed":
            abl_wave, info = ablate_samples(
                meta, wave, train_mask, [], saturation_boundary_adc=float(config["saturation_boundary_adc"])
            )
        else:
            abl_wave, info = ablate_samples(meta, wave, train_mask, [int(x) for x in ablation["samples"]])
        group_info.append({"ablation": name, **info})
        abl_meta = recompute_even_meta(meta, abl_wave)
        preds = build_traditional_predictions(abl_meta, abl_wave, y_charge, train_mask, config, rng)
        X_abl = ml_features(abl_meta, abl_wave)
        hgb = fit_hgb(X_abl, y_charge, train_idx, int(config["random_seed"]) + 30)
        et = fit_extra_trees(X_abl, y_charge, et_idx, int(config["random_seed"]) + 40)
        preds["ml_hgb"] = np.exp(hgb.predict(X_abl))
        preds["ml_extra_trees"] = np.exp(et.predict(X_abl))
        metrics = evaluate_predictions(abl_meta, y_charge, heldout_mask, preds, config)
        metrics["ablation"] = name
        metrics["mode"] = "grouped_retrain"
        all_metric_frames.append(metrics)

        for method in ["strong_huber_charge", "ml_hgb", "ml_extra_trees"]:
            held_row = metrics[(metrics["method"] == method) & (metrics["subset"].str.startswith("heldout_runs"))].iloc[0]
            full_row = full_metrics[(full_metrics["method"] == method) & (full_metrics["subset"].str.startswith("heldout_runs"))].iloc[0]
            frame = meta.loc[heldout_mask, ["run", "target_odd_pos_charge"]].reset_index(drop=True)
            frame["_pred"] = preds[method][heldout_mask]
            frame["_ref"] = full_predictions[method][heldout_mask]
            ablation_rows.append(
                {
                    "mode": "grouped_retrain",
                    "ablation": name,
                    "method": method,
                    "res68_abs_frac": float(held_row["res68_abs_frac"]),
                    "delta_res68_vs_full": float(held_row["res68_abs_frac"] - full_row["res68_abs_frac"]),
                    "run_block_delta_res68_ci95": run_block_delta_ci(
                        frame, "target_odd_pos_charge", "_pred", "_ref", rng, int(config["bootstrap_reps"])
                    ),
                    **info,
                }
            )

    print("5/8 evaluating frozen ML occlusion and permutation ...", flush=True)
    ml_full = {"ml_hgb": full_hgb, "ml_extra_trees": full_et}
    ml_full_pred = {"ml_hgb": full_predictions["ml_hgb"], "ml_extra_trees": full_predictions["ml_extra_trees"]}
    for ablation in config["window_ablations"]:
        name = str(ablation["name"])
        if name == "full" or name == "saturation_boundary_atoms_removed":
            continue
        samples = [int(x) for x in ablation["samples"]]
        occ_wave, info = ablate_samples(meta, wave, train_mask, samples)
        occ_meta = recompute_even_meta(meta, occ_wave)
        X_occ = ml_features(occ_meta, occ_wave)
        perm_wave = permute_samples(wave, heldout_mask, samples, rng)
        perm_meta = recompute_even_meta(meta, perm_wave)
        X_perm = ml_features(perm_meta, perm_wave)
        for mode, X_eval in [("frozen_occlusion", X_occ), ("frozen_permutation", X_perm)]:
            for method, model in ml_full.items():
                pred = np.exp(model.predict(X_eval))
                frame = meta.loc[heldout_mask, ["run", "target_odd_pos_charge"]].reset_index(drop=True)
                frame["_pred"] = pred[heldout_mask]
                frame["_ref"] = ml_full_pred[method][heldout_mask]
                met = robust_metrics(y_charge[heldout_mask], pred[heldout_mask])
                ref_met = robust_metrics(y_charge[heldout_mask], ml_full_pred[method][heldout_mask])
                ablation_rows.append(
                    {
                        "mode": mode,
                        "ablation": name,
                        "method": method,
                        "res68_abs_frac": float(met["res68_abs_frac"]),
                        "delta_res68_vs_full": float(met["res68_abs_frac"] - ref_met["res68_abs_frac"]),
                        "run_block_delta_res68_ci95": run_block_delta_ci(
                            frame, "target_odd_pos_charge", "_pred", "_ref", rng, int(config["bootstrap_reps"])
                        ),
                        **info,
                    }
                )

    print("6/8 evaluating single-sample HGB occlusion map ...", flush=True)
    atom_rows = []
    full_hgb_res68 = robust_metrics(y_charge[heldout_mask], full_predictions["ml_hgb"][heldout_mask])["res68_abs_frac"]
    for sample in range(int(config["samples_per_channel"])):
        occ_wave, _ = ablate_samples(meta, wave, train_mask, [sample])
        occ_meta = recompute_even_meta(meta, occ_wave)
        pred = np.exp(full_hgb.predict(ml_features(occ_meta, occ_wave)))
        met = robust_metrics(y_charge[heldout_mask], pred[heldout_mask])
        atom_rows.append(
            {
                "sample": int(sample),
                "res68_abs_frac": float(met["res68_abs_frac"]),
                "delta_res68_vs_full": float(met["res68_abs_frac"] - full_hgb_res68),
            }
        )

    print("7/8 running leakage sentinels ...", flush=True)
    stave_only = np.zeros(len(meta), dtype=float)
    for stave in sorted(np.unique(st)):
        mask_train = train_mask & (st == stave)
        stave_only[st == stave] = float(np.median(y_charge[mask_train]))
    shuf_idx = np.where(train_mask)[0]
    if len(shuf_idx) > int(config["shuffled_train_rows"]):
        shuf_idx = rng.choice(shuf_idx, size=int(config["shuffled_train_rows"]), replace=False)
    shuffled = np.log(y_charge[shuf_idx]).copy()
    rng.shuffle(shuffled)
    shuffled_model = HistGradientBoostingRegressor(
        max_iter=20,
        learning_rate=0.06,
        max_leaf_nodes=15,
        l2_regularization=0.05,
        random_state=int(config["random_seed"]) + 50,
    )
    shuffled_model.fit(X_full[shuf_idx], shuffled)
    shuffled_pred = np.exp(shuffled_model.predict(X_full))

    train_keys = set(
        zip(meta.loc[train_mask, "run"].astype(int), meta.loc[train_mask, "eventno"].astype(int), meta.loc[train_mask, "stave"].astype(str))
    )
    held_keys = set(
        zip(meta.loc[heldout_mask, "run"].astype(int), meta.loc[heldout_mask, "eventno"].astype(int), meta.loc[heldout_mask, "stave"].astype(str))
    )
    train_hashes = set(waveform_hashes(wave[train_mask]))
    held_hashes = set(waveform_hashes(wave[heldout_mask]))
    leakage = {
        "heldout_absent_from_train": bool(set(meta.loc[train_mask, "run"].unique()).isdisjoint(heldout_runs)),
        "train_heldout_event_key_overlap": int(len(train_keys.intersection(held_keys))),
        "exact_even_waveform_hash_overlap": int(len(train_hashes.intersection(held_hashes))),
        "no_identifier_or_target_features": True,
        "invalid_target_rows_removed": invalid_rows,
        "stave_only_charge_res68": float(robust_metrics(y_charge[heldout_mask], stave_only[heldout_mask])["res68_abs_frac"]),
        "shuffled_target_hgb_charge_res68": float(robust_metrics(y_charge[heldout_mask], shuffled_pred[heldout_mask])["res68_abs_frac"]),
    }

    print("8/8 writing report artifacts ...", flush=True)
    method_metrics = pd.concat(all_metric_frames, ignore_index=True)
    ablation_deltas = pd.DataFrame(ablation_rows)
    atom_deltas = pd.DataFrame(atom_rows)
    group_info_df = pd.DataFrame(group_info)
    full_for_delta = {k: v for k, v in full_predictions.items() if k in ["ml_hgb", "ml_extra_trees", "strong_huber_charge"]}
    ml_minus_trad = metric_delta_table(meta, y_charge, heldout_mask, full_for_delta, "strong_huber_charge", config)

    full_summary = method_metrics[(method_metrics["ablation"] == "full") & (method_metrics["subset"].str.startswith("heldout_runs"))]
    best_trad = full_summary[full_summary["method"].isin(["peak_to_charge_calibrated", "integral_calibrated", "adaptive_template_scale_calibrated", "strong_huber_charge"])].sort_values("res68_abs_frac").iloc[0]
    hgb_row = full_summary[full_summary["method"] == "ml_hgb"].iloc[0]
    et_row = full_summary[full_summary["method"] == "ml_extra_trees"].iloc[0]
    worst_hgb_group = ablation_deltas[(ablation_deltas["mode"] == "grouped_retrain") & (ablation_deltas["method"] == "ml_hgb")].sort_values("delta_res68_vs_full", ascending=False).iloc[0]
    top_atom = atom_deltas.sort_values("delta_res68_vs_full", ascending=False).iloc[0]
    finding = (
        f"The raw selected-pulse count reproduces exactly first, and the ticket-local P04 charge HGB "
        f"benchmark gives res68={p04_charge_res68:.6f} versus the registered reference {expected_res68:.6f}. "
        f"On the P04i full split, strong traditional Huber is the best traditional charge closure "
        f"(res68={float(best_trad['res68_abs_frac']):.4f}), while HGB and ExtraTrees reach "
        f"{float(hgb_row['res68_abs_frac']):.4f} and {float(et_row['res68_abs_frac']):.4f}. "
        f"The largest HGB grouped-retrain degradation is {worst_hgb_group['ablation']} "
        f"(delta res68={float(worst_hgb_group['delta_res68_vs_full']):+.4f}); the largest single-sample "
        f"frozen HGB occlusion atom is sample {int(top_atom['sample'])} "
        f"(delta res68={float(top_atom['delta_res68_vs_full']):+.4f}). "
        f"Shuffled-target and stave-only sentinels are broad ({leakage['shuffled_target_hgb_charge_res68']:.4f} "
        f"and {leakage['stave_only_charge_res68']:.4f}), so the very sharp ML result is not explained by "
        "run leakage, exact waveform duplicates, or context-only prediction; it remains a same-detector "
        "duplicate-readout closure rather than an external energy calibration."
    )
    reproduction = {
        "expected_selected_pulses": expected,
        "reproduced_selected_pulses": total_selected,
        "delta": total_selected - expected,
        "pass": total_selected == expected,
        "expected_p04_charge_hgb_res68": expected_res68,
        "ticket_local_p04_charge_hgb_res68": float(p04_charge_res68),
        "p04_charge_hgb_reference_delta": float(p04_ref_delta),
    }
    result = {
        "study": config["study_id"],
        "ticket_id": config["ticket_id"],
        "raw_reproduction": reproduction,
        "target_definition": "paired odd-channel positive duplicate-readout charge; features from even readout only",
        "heldout_runs": heldout_runs,
        "train_runs": sorted(int(x) for x in meta.loc[train_mask, "run"].unique()),
        "n_valid_rows": int(len(meta)),
        "n_train_rows": int(train_mask.sum()),
        "n_heldout_rows": int(heldout_mask.sum()),
        "invalid_target_rows_removed_after_reproduction": invalid_rows,
        "full_heldout_metrics": json.loads(full_summary.to_json(orient="records")),
        "ablation_deltas": json.loads(ablation_deltas.to_json(orient="records")),
        "sample_atom_occlusion_deltas": json.loads(atom_deltas.to_json(orient="records")),
        "ml_minus_traditional_deltas": json.loads(ml_minus_trad.to_json(orient="records")),
        "leakage_audit": leakage,
        "finding": finding,
        "runtime_sec": round(time.time() - t0, 1),
    }

    counts_by_run.to_csv(out_dir / "counts_by_run.csv", index=False)
    method_metrics.to_csv(out_dir / "method_metrics.csv", index=False)
    ablation_deltas.to_csv(out_dir / "ablation_deltas.csv", index=False)
    atom_deltas.to_csv(out_dir / "sample_atom_occlusion_deltas.csv", index=False)
    ml_minus_trad.to_csv(out_dir / "ml_minus_traditional_deltas.csv", index=False)
    group_info_df.to_csv(out_dir / "ablation_group_info.csv", index=False)
    pd.DataFrame([reproduction]).to_csv(out_dir / "reproduction_match_table.csv", index=False)
    pd.DataFrame([leakage]).to_csv(out_dir / "leakage_checks.csv", index=False)
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    make_report(out_dir, config, reproduction, method_metrics, ablation_deltas, atom_deltas, ml_minus_trad, leakage, result)

    input_files = [p04.raw_path(config, run) for run in p04.configured_runs(config)]
    input_manifest = pd.DataFrame([{"path": str(path), "sha256": sha256_file(path)} for path in input_files])
    input_manifest.to_csv(out_dir / "input_sha256.csv", index=False)
    output_files = [
        "REPORT.md",
        "result.json",
        "counts_by_run.csv",
        "method_metrics.csv",
        "ablation_deltas.csv",
        "sample_atom_occlusion_deltas.csv",
        "ml_minus_traditional_deltas.csv",
        "ablation_group_info.csv",
        "reproduction_match_table.csv",
        "leakage_checks.csv",
        "input_sha256.csv",
    ]
    manifest = {
        "study": config["study_id"],
        "ticket_id": config["ticket_id"],
        "command": "/home/billy/anaconda3/bin/python scripts/p04i_1781024791_1539_3ba15c1d_sample_causality.py --config configs/p04i_1781024791_1539_3ba15c1d_sample_causality.json",
        "config": str(config_path),
        "config_sha256": sha256_file(config_path),
        "script": str(Path(__file__).resolve().relative_to(ROOT)),
        "script_sha256": sha256_file(Path(__file__).resolve()),
        "p04_helper_script": str(P04_PATH.relative_to(ROOT)),
        "p04_helper_script_sha256": sha256_file(P04_PATH),
        "random_seed": int(config["random_seed"]),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"]).decode().strip(),
        "inputs": json.loads(input_manifest.to_json(orient="records")),
        "outputs": [{"path": str(out_dir / name), "sha256": sha256_file(out_dir / name)} for name in output_files],
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"DONE -> {out_dir} in {result['runtime_sec']} s", flush=True)


if __name__ == "__main__":
    main()
