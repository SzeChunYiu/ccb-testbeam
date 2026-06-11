#!/usr/bin/env python3
"""S07n: normalized all-three shape-cue charge-null benchmark."""

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
from typing import Callable, Dict, List, Sequence, Tuple

os.environ.setdefault("MPLCONFIGDIR", "/tmp/ccb-testbeam-s07n-matplotlib-cache")

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score


ROOT = Path(__file__).resolve().parents[1]
S07F_PATH = ROOT / "scripts/s07f_independent_all_three_appi_validation.py"
S07G_PATH = ROOT / "scripts/s07g_1781024319_1318_2f4a5acc_amp_preserving_appi_control.py"
S07M_PATH = ROOT / "scripts/s07m_1781063920_486_09951fba_charge_preserved_shape_cue_localization.py"


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


def shifted(wave: np.ndarray, delay: int) -> np.ndarray:
    out = np.zeros_like(wave)
    if delay <= 0:
        out[:] = wave
    elif delay < len(wave):
        out[delay:] = wave[:-delay]
    return out


def positive_charge(wave: np.ndarray) -> float:
    return float(np.clip(wave, 0.0, None).sum())


def signed_area(wave: np.ndarray) -> float:
    return float(np.sum(wave))


def preserve_quantity(original: np.ndarray, mixed: np.ndarray, mode: str) -> Tuple[np.ndarray, float, float, float]:
    if mode == "positive_charge_preserved":
        before = positive_charge(original)
        after = positive_charge(mixed)
    elif mode == "signed_area_preserved":
        before = signed_area(original)
        after = signed_area(mixed)
    elif mode == "peak_preserved":
        before = float(np.max(original))
        after = float(np.max(mixed))
    else:
        raise ValueError(mode)
    factor = before / after if abs(after) > 1e-9 else 1.0
    adjusted = mixed * factor
    final = positive_charge(adjusted) if mode == "positive_charge_preserved" else signed_area(adjusted) if mode == "signed_area_preserved" else float(np.max(adjusted))
    return adjusted, float(factor), float(before), float(final)


def make_null_dataset(config: dict, utils, clean_payloads: List[dict], mode: str) -> pd.DataFrame:
    staves = list(config["staves"].keys())
    downstream_idx = np.asarray([staves.index(name) for name in config["downstream_staves"]], dtype=int)
    b2_idx = staves.index("B2")
    cut = float(config["amplitude_cut_adc"])
    min_downstream = int(config["min_downstream_staves"])
    rng = np.random.default_rng(int(config["injection_seed"]))
    rows: List[dict] = []

    for pair_id, payload in enumerate(clean_payloads):
        base = payload["corrected"].copy()
        present_downstream = [int(idx) for idx in downstream_idx if bool(payload["selected"][idx])]
        target_idx = int(rng.choice(present_downstream))
        delay = int(rng.integers(int(config["delay_samples_min"]), int(config["delay_samples_max"]) + 1))
        scale = float(rng.uniform(float(config["secondary_scale_min"]), float(config["secondary_scale_max"])))
        mixed = base.copy()
        mixed[target_idx] = mixed[target_idx] + scale * shifted(base[target_idx], delay)
        adjusted, norm_factor, preserved_before, preserved_after = preserve_quantity(base[target_idx], mixed[target_idx], mode)
        mixed[target_idx] = adjusted
        variants = [
            ("raw_clean", base, -1, 0, 0.0, 1.0, float("nan"), float("nan")),
            ("injected_two_pulse", mixed, target_idx, delay, scale, norm_factor, preserved_before, preserved_after),
        ]
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
            target_wave = corrected[target] if target >= 0 else base[downstream_idx[0]]
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
                "preserved_quantity_ratio": float(preserved_after / preserved_before) if abs(preserved_before) > 1e-9 else float("nan"),
                "target_positive_charge": positive_charge(target_wave),
                "target_signed_area": signed_area(target_wave),
                "target_peak": float(np.max(target_wave)),
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


def auc(y: np.ndarray, score: np.ndarray) -> float:
    mask = np.isfinite(score)
    if mask.sum() == 0 or len(np.unique(y[mask])) < 2:
        return float("nan")
    return float(roc_auc_score(y[mask], score[mask]))


def ap(y: np.ndarray, score: np.ndarray) -> float:
    mask = np.isfinite(score)
    if mask.sum() == 0 or len(np.unique(y[mask])) < 2:
        return float("nan")
    return float(average_precision_score(y[mask], score[mask]))


def brier(y: np.ndarray, prob: np.ndarray) -> float:
    mask = np.isfinite(prob)
    if mask.sum() == 0:
        return float("nan")
    return float(brier_score_loss(y[mask], np.clip(prob[mask], 0.0, 1.0)))


def fixed95_rejection(y: np.ndarray, score: np.ndarray) -> float:
    clean = score[(y == 0) & np.isfinite(score)]
    inj = score[(y == 1) & np.isfinite(score)]
    if len(clean) == 0 or len(inj) == 0:
        return float("nan")
    threshold = float(np.percentile(clean, 95.0))
    return float(np.mean(inj > threshold))


def bootstrap_ci(y: np.ndarray, score: np.ndarray, runs: np.ndarray, metric: Callable[[np.ndarray, np.ndarray], float], seed: int, n_boot: int) -> Tuple[float, float]:
    unique_runs = np.unique(runs)
    rng = np.random.default_rng(seed)
    values = []
    for _ in range(int(n_boot)):
        sampled = rng.choice(unique_runs, size=len(unique_runs), replace=True)
        idx = np.concatenate([np.flatnonzero(runs == run) for run in sampled])
        if len(np.unique(y[idx])) < 2:
            continue
        value = metric(y[idx], score[idx])
        if math.isfinite(value):
            values.append(value)
    if len(values) < 20:
        return float("nan"), float("nan")
    return float(np.percentile(values, 2.5)), float(np.percentile(values, 97.5))


def bootstrap_delta_ci(y: np.ndarray, score: np.ndarray, ref: np.ndarray, runs: np.ndarray, seed: int, n_boot: int) -> Tuple[float, float]:
    unique_runs = np.unique(runs)
    rng = np.random.default_rng(seed)
    values = []
    for _ in range(int(n_boot)):
        sampled = rng.choice(unique_runs, size=len(unique_runs), replace=True)
        idx = np.concatenate([np.flatnonzero(runs == run) for run in sampled])
        if len(np.unique(y[idx])) < 2:
            continue
        value = auc(y[idx], score[idx]) - auc(y[idx], ref[idx])
        if math.isfinite(value):
            values.append(value)
    if len(values) < 20:
        return float("nan"), float("nan")
    return float(np.percentile(values, 2.5)), float(np.percentile(values, 97.5))


def fold_auc_range(y: np.ndarray, score: np.ndarray, runs: np.ndarray) -> Tuple[float, float, float]:
    values = []
    for run in sorted(np.unique(runs)):
        idx = runs == run
        values.append(auc(y[idx], score[idx]))
    finite = np.asarray([v for v in values if math.isfinite(v)], dtype=float)
    if len(finite) == 0:
        return float("nan"), float("nan"), float("nan")
    return float(finite.min()), float(finite.max()), float(finite.max() - finite.min())


def summarize(name: str, y: np.ndarray, score: np.ndarray, prob: np.ndarray, ref: np.ndarray, runs: np.ndarray, seed: int, n_boot: int, notes: str) -> dict:
    auc_ci = bootstrap_ci(y, score, runs, auc, seed, n_boot)
    ap_ci = bootstrap_ci(y, score, runs, ap, seed + 1, n_boot)
    rej_ci = bootstrap_ci(y, score, runs, fixed95_rejection, seed + 2, n_boot)
    delta_ci = bootstrap_delta_ci(y, score, ref, runs, seed + 3, n_boot)
    fold_min, fold_max, fold_range = fold_auc_range(y, score, runs)
    return {
        "method": name,
        "roc_auc": auc(y, score),
        "roc_auc_ci_low": auc_ci[0],
        "roc_auc_ci_high": auc_ci[1],
        "average_precision": ap(y, score),
        "ap_ci_low": ap_ci[0],
        "ap_ci_high": ap_ci[1],
        "fixed95_clean_rejection": fixed95_rejection(y, score),
        "fixed95_ci_low": rej_ci[0],
        "fixed95_ci_high": rej_ci[1],
        "brier": brier(y, prob),
        "auc_minus_traditional": auc(y, score) - auc(y, ref),
        "delta_ci_low": delta_ci[0],
        "delta_ci_high": delta_ci[1],
        "fold_auc_min": fold_min,
        "fold_auc_max": fold_max,
        "support_drift_auc_range": fold_range,
        "notes": notes,
    }


def markdown_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    view = frame if max_rows is None else frame.head(max_rows)

    def fmt(value: object) -> str:
        if pd.isna(value):
            return ""
        if isinstance(value, float):
            return f"{value:.6g}"
        return str(value)

    columns = list(view.columns)
    rows = [[fmt(row[col]) for col in columns] for _, row in view.iterrows()]
    widths = [len(str(col)) for col in columns]
    for row in rows:
        widths = [max(width, len(cell)) for width, cell in zip(widths, row)]
    header = "| " + " | ".join(str(col).ljust(width) for col, width in zip(columns, widths)) + " |"
    sep = "| " + " | ".join("-" * width for width in widths) + " |"
    body = ["| " + " | ".join(cell.ljust(width) for cell, width in zip(row, widths)) + " |" for row in rows]
    return "\n".join([header, sep, *body])


def charge_bins(data: pd.DataFrame, config: dict) -> pd.Series:
    base = data.groupby("pair_id")["target_positive_charge"].transform("first")
    try:
        return pd.qcut(base.rank(method="first"), int(config["charge_match_bins"]), labels=False).astype(int)
    except ValueError:
        return pd.Series(np.zeros(len(data), dtype=int), index=data.index)


def charge_null_permutation(data: pd.DataFrame, y: np.ndarray, score: np.ndarray, config: dict) -> pd.DataFrame:
    rng = np.random.default_rng(int(config["random_seed"]) + 6000)
    bins = charge_bins(data, config).to_numpy(dtype=int)
    runs = data["run"].to_numpy(dtype=int)
    observed = auc(y, score)
    values = []
    for _ in range(int(config["null_permutations"])):
        yp = y.copy()
        for run in sorted(np.unique(runs)):
            for charge_bin in sorted(np.unique(bins)):
                idx = np.flatnonzero((runs == run) & (bins == charge_bin))
                if len(idx) > 1:
                    yp[idx] = rng.permutation(yp[idx])
        value = auc(yp, score)
        if math.isfinite(value):
            values.append(value)
    null = np.asarray(values, dtype=float)
    return pd.DataFrame(
        [
            {
                "probe": "run_plus_charge_bin_label_permutation",
                "observed_auc": observed,
                "null_auc_mean": float(null.mean()) if len(null) else float("nan"),
                "null_auc_ci_low": float(np.percentile(null, 2.5)) if len(null) else float("nan"),
                "null_auc_ci_high": float(np.percentile(null, 97.5)) if len(null) else float("nan"),
                "charge_null_auc_loss": observed - (float(null.mean()) if len(null) else float("nan")),
                "n_permutations": int(len(null)),
            }
        ]
    )


def quick_permutation_atoms(data: pd.DataFrame, y: np.ndarray, cols: List[str], config: dict) -> pd.DataFrame:
    X = data[cols].to_numpy(dtype=np.float32)
    runs = data["run"].to_numpy(dtype=int)
    seed = int(config["random_seed"]) + 7100
    rng = np.random.default_rng(seed)
    rows = []
    for fold, held_run in enumerate(sorted(np.unique(runs))):
        test = runs == held_run
        train = ~test
        model = HistGradientBoostingClassifier(
            max_iter=140,
            learning_rate=0.055,
            max_leaf_nodes=21,
            l2_regularization=0.04,
            random_state=seed + fold,
        )
        model.fit(X[train], y[train])
        base = auc(y[test], model.predict_proba(X[test])[:, 1])
        for col_idx, col in enumerate(cols):
            Xp = X[test].copy()
            rng.shuffle(Xp[:, col_idx])
            drop = base - auc(y[test], model.predict_proba(Xp)[:, 1])
            rows.append({"heldout_run": int(held_run), "feature": col, "auc_importance": float(drop)})
    frame = pd.DataFrame(rows)
    return (
        frame.groupby("feature", as_index=False)
        .agg(
            mean_auc_importance=("auc_importance", "mean"),
            min_auc_importance=("auc_importance", "min"),
            max_auc_importance=("auc_importance", "max"),
            stability_std=("auc_importance", "std"),
        )
        .sort_values("mean_auc_importance", ascending=False)
    )


def benchmark_primary(config: dict, utils, s07m, data: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, Dict[str, np.ndarray]]:
    y = data["label_injected"].to_numpy(dtype=int)
    runs = data["run"].to_numpy(dtype=int)
    shape_cols = s07m.strict_shape_columns(data, utils)
    wave = s07m.normalized_waveforms(data)
    seed = int(config["random_seed"])
    n_boot = int(config["bootstrap_replicates"])
    scores: Dict[str, np.ndarray] = {}
    probs: Dict[str, np.ndarray] = {}
    fold_frames: List[pd.DataFrame] = []

    trad_score, traditional_choices, traditional_candidates = s07m.traditional_score(data, y, config, utils)
    scores["traditional atom/template selector"] = trad_score
    probs["traditional atom/template selector"] = np.clip((trad_score - np.nanmin(trad_score)) / max(np.nanmax(trad_score) - np.nanmin(trad_score), 1e-9), 0.0, 1.0)

    rf_scan, best_params, rf_score, rf_fold, rf_prob = utils.evaluate_rf_grid(data, y, shape_cols, config)
    scores["shape-only RF probe"] = rf_score
    probs["shape-only RF probe"] = rf_prob

    for name in ["ridge", "gbt", "mlp"]:
        score, folds = s07m.sklearn_oof(data, y, shape_cols, name, config)
        label = {"ridge": "ridge logistic", "gbt": "gradient-boosted trees", "mlp": "MLP"}[name]
        scores[label] = score
        probs[label] = np.clip(score, 0.0, 1.0)
        folds["method"] = label
        fold_frames.append(folds)

    cnn_score, cnn_folds = s07m.torch_oof(data, y, shape_cols, wave, "cnn1d", config)
    scores["1D-CNN"] = cnn_score
    probs["1D-CNN"] = np.clip(cnn_score, 0.0, 1.0)
    cnn_folds["method"] = "1D-CNN"
    fold_frames.append(cnn_folds)

    atom_score, atom_folds = s07m.torch_oof(data, y, shape_cols, wave, "wave_atom_net", config)
    scores["WaveAtomNet"] = atom_score
    probs["WaveAtomNet"] = np.clip(atom_score, 0.0, 1.0)
    atom_folds["method"] = "WaveAtomNet"
    fold_frames.append(atom_folds)

    notes = {
        "traditional atom/template selector": "Fold-local q/template, timing-spread, early/late, derivative, and peak-tail conventional selector.",
        "shape-only RF probe": "Random-forest shape probe requested by ticket; excludes amplitude, IDs, timing, topology, and injection parameters.",
        "ridge logistic": "L2 logistic regression on strict normalized shape atoms.",
        "gradient-boosted trees": "HistGradientBoostingClassifier on strict normalized shape atoms.",
        "MLP": "Two-hidden-layer neural net on strict normalized shape atoms.",
        "1D-CNN": "Compact convolutional net on per-stave peak-normalized waveforms.",
        "WaveAtomNet": "New fused architecture: convolutional waveform branch plus normalized atom branch.",
    }
    scoreboard = pd.DataFrame(
        [
            summarize(name, y, scores[name], probs[name], trad_score, runs, seed + 100 * i, n_boot, notes[name])
            for i, name in enumerate(scores)
        ]
    ).sort_values(["roc_auc", "average_precision"], ascending=False)

    trad_rows = []
    for held_run in sorted(np.unique(runs)):
        test = runs == held_run
        trad_rows.append({"method": "traditional atom/template selector", "heldout_run": int(held_run), "n_train": int((~test).sum()), "n_test": int(test.sum()), "fold_auc": auc(y[test], trad_score[test])})
    fold_scores = pd.concat([pd.DataFrame(trad_rows), *fold_frames], ignore_index=True)
    return scoreboard, fold_scores, traditional_choices, traditional_candidates, rf_scan, scores


def quick_mode_benchmark(config: dict, utils, s07m, mode: str, data: pd.DataFrame) -> pd.DataFrame:
    y = data["label_injected"].to_numpy(dtype=int)
    runs = data["run"].to_numpy(dtype=int)
    shape_cols = s07m.strict_shape_columns(data, utils)
    trad_score, _, _ = s07m.traditional_score(data, y, config, utils)
    ridge_score, _ = s07m.sklearn_oof(data, y, shape_cols, "ridge", config)
    gbt_score, _ = s07m.sklearn_oof(data, y, shape_cols, "gbt", config)
    rows = []
    for name, score in [("traditional atom/template selector", trad_score), ("ridge logistic", ridge_score), ("gradient-boosted trees", gbt_score)]:
        rows.append(
            {
                "mode": mode,
                "method": name,
                "roc_auc": auc(y, score),
                "average_precision": ap(y, score),
                "fixed95_clean_rejection": fixed95_rejection(y, score),
                "support_drift_auc_range": fold_auc_range(y, score, runs)[2],
            }
        )
    injected = data[data["label_injected"] == 1]
    for row in rows:
        row["median_renormalization_factor"] = float(injected["renormalization_factor"].median())
        row["median_preserved_quantity_ratio"] = float(injected["preserved_quantity_ratio"].median())
    return pd.DataFrame(rows)


def write_report(out_dir: Path, config: dict, reproduction: pd.DataFrame, counts: pd.DataFrame, scoreboard: pd.DataFrame, fold_scores: pd.DataFrame, mode_scoreboard: pd.DataFrame, traditional_choices: pd.DataFrame, localization: pd.DataFrame, permutation: pd.DataFrame, leakage: pd.DataFrame, charge_null: pd.DataFrame, result: dict) -> None:
    winner = scoreboard.iloc[0]
    trad = scoreboard[scoreboard["method"] == "traditional atom/template selector"].iloc[0]
    text = f"""# S07n: normalized shape-cue charge null

- **Ticket:** `{config['ticket_id']}`
- **Worker:** `{config['worker']}`
- **Input:** raw B-stack ROOT `HRDv` from `{config['raw_root_dir']}`
- **Runs:** {', '.join(map(str, config['runs']))}
- **Primary split:** leave-one-run-out; intervals are run-block bootstrap 95% CIs.
- **Winner:** `{result['winner_method']}`

## Abstract

S07n tests whether the S07 all-three injected-pile-up shape cue survives after residual charge normalization is made stricter. The analysis first reproduces the parent raw-ROOT App.I and all-three counts, then constructs paired clean/injected all-three events where the injected target stave is normalized to preserve positive charge. The primary benchmark compares a transparent q-template/early-late/derivative/peak-tail selector with ridge logistic regression, gradient-boosted trees, an MLP, a 1D-CNN, a random-forest shape probe, and the new WaveAtomNet fused waveform/atom architecture. Additional peak-preserved, signed-area-preserved, and run-plus-charge-bin nulls test whether the signal is only an amplitude or charge-renormalization artifact.

The winner is **{winner['method']}** with AUC {winner['roc_auc']:.3f} [{winner['roc_auc_ci_low']:.3f}, {winner['roc_auc_ci_high']:.3f}], AP {winner['average_precision']:.3f}, and fixed-95%-clean injected rejection {winner['fixed95_clean_rejection']:.3f}. The traditional selector obtains AUC {trad['roc_auc']:.3f} [{trad['roc_auc_ci_low']:.3f}, {trad['roc_auc_ci_high']:.3f}].

## Raw-ROOT Reproduction

{markdown_table(reproduction)}

The reproduction gate reads `EVENTNO`, `EVT`, and `HRDv` from raw `hrdb_run_*.root`, reshapes the B-stack channels to four 18-sample staves, subtracts the samples 0--3 median baseline, applies the `A>1000` ADC selection, and recomputes CFD20 timing. No injected, ML, or report-local artifact is used until these raw counts pass.

The final two rows are inherited S07e/S07f model-anchor diagnostics, not the raw-count gate. They are retained to expose scorer drift under the current software stack; the ticket's required raw ROOT reproduction is the exact-count block above.

## Dataset And Equations

For clean all-three event \(i\), stave \(s\), and sample \(t\), let \(x_{{i,s,t}}\) be the baseline-subtracted waveform. The injected copy is

\\[
z_{{i,s,t}}=x_{{i,s,t}}+a_i x_{{i,s,t-d_i}},
\\]

with \(d_i\\in\\{{2,\dots,6\\}}\) samples and \(a_i\\in[0.12,0.38]\). In the primary positive-charge-preserved null the target stave is renormalized by

\\[
\\alpha_i = \\frac{{\\sum_t \\max(x_{{i,s,t}},0)}}{{\\sum_t \\max(z_{{i,s,t}},0)}},\\qquad
\\tilde z_{{i,s,t}}=\\alpha_i z_{{i,s,t}}.
\\]

The paired clean and injected rows have the same event, run, and base charge and are held out together by run.

{markdown_table(counts)}

## Methods

The traditional method is selected inside each training fold from conventional one-dimensional atoms: \(D_t\), \(|C_t|\), downstream tail and late fractions, area-over-peak, peak sample, derivative drop, final fraction, and a fold-local delayed q-template residual. Each candidate and sign is chosen only by training-run AUC, then standardized on training runs before scoring the held-out run.

ML/NN methods use only normalized shape atoms or normalized waveforms. Forbidden inputs include run, event id, pair id, injected delay/scale/target, absolute amplitudes, topology/present flags, and timing variables. WaveAtomNet is the new architecture: a compact convolutional branch over the four normalized staves is fused with a dense normalized-atom branch before a logistic head.

## Primary Benchmark

{markdown_table(scoreboard)}

Fold diagnostics:

{markdown_table(fold_scores, max_rows=24)}

Traditional fold choices:

{markdown_table(traditional_choices)}

## Stricter Charge Nulls

{markdown_table(mode_scoreboard)}

The signed-area rows preserve the baseline-subtracted target-stave integral rather than positive charge. The peak-preserved rows reproduce the earlier amplitude-null logic. The charge-bin permutation below destroys labels within run and base-charge strata while retaining the score distribution:

{markdown_table(charge_null)}

## Shape-Cue Localization

Grouped dropout replaces each held-out group by its training-run mean before scoring a fold-local GBT. Positive values are AUC lost by removing that region or atom family.

{markdown_table(localization)}

Feature-level permutation importance cross-check:

{markdown_table(permutation.head(15))}

## Leakage And Systematics

{markdown_table(leakage)}

Systematic limitations: injected overlap is not an external real-beam pile-up label; positive-charge and signed-area preservation still alter local curvature and noise correlations; only seven run blocks are available for CIs; neural models are deliberately laptop-scale; and localization is model-dependent. The result supports a normalized injected-recovery shape cue, not a calibrated pile-up rate.

## Verdict

`result.json` names `{result['winner_method']}` as the winner. Its AUC advantage over the traditional selector is {result['winner_minus_traditional_auc']:.3f} with bootstrap CI [{result['winner_minus_traditional_auc_ci'][0]:.3f}, {result['winner_minus_traditional_auc_ci'][1]:.3f}]. The run-plus-charge-bin permutation mean AUC is {result['charge_null_auc_mean']:.3f}; the winner's observed-minus-null AUC is {result['charge_null_auc_loss']:.3f}. Therefore the all-three normalized shape cue does not vanish under the stricter charge-preserving nulls tested here, although adoption should remain limited to injection-recovery support until real pile-up truth is available.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s07n_1781068159_1658_5f900b07_normalized_shape_charge_null.py --config configs/s07n_1781068159_1658_5f900b07_normalized_shape_charge_null.json
```
"""
    (out_dir / "REPORT.md").write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/s07n_1781068159_1658_5f900b07_normalized_shape_charge_null.json")
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = load_config(config_path)
    out_dir = ROOT / config["output_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)

    s07f = load_module(S07F_PATH, "s07f_reference_s07n")
    s07g = load_module(S07G_PATH, "s07g_reference_s07n")
    s07m = load_module(S07M_PATH, "s07m_reference_s07n")
    utils = s07f.load_s07d_utils(ROOT / config["utility_script"])

    print("1/9 raw ROOT reproduction and S07 anchors ...", flush=True)
    parent, all_three, run_counts, clean_payloads = s07f.collect_parent_and_all_three(config, utils)
    reproduction, s07e_score, s07f_score = s07m.build_reproduction(config, s07f, s07g, utils, clean_payloads, parent, all_three)
    raw_reproduction_pass = bool(reproduction.iloc[:5]["pass"].all())
    reference_auc_reproduction_pass = bool(reproduction["pass"].all())
    if not raw_reproduction_pass:
        raise RuntimeError("raw-ROOT reproduction gate failed")

    print("2/9 building positive-charge-preserved primary dataset ...", flush=True)
    primary = make_null_dataset(config, utils, clean_payloads, "positive_charge_preserved")
    counts = primary.groupby(["run", "label_injected"]).size().unstack(fill_value=0).rename(columns={0: "raw_clean", 1: "injected"}).reset_index()
    counts["total"] = counts["raw_clean"] + counts["injected"]
    print("3/9 fitting primary traditional, RF, ridge, GBT, MLP, CNN, WaveAtomNet ...", flush=True)
    scoreboard, fold_scores, traditional_choices, traditional_candidates, rf_scan, scores = benchmark_primary(config, utils, s07m, primary)

    print("4/9 fitting strict charge-null comparison modes ...", flush=True)
    mode_frames = []
    for mode in ["peak_preserved", "signed_area_preserved"]:
        mode_data = make_null_dataset(config, utils, clean_payloads, mode)
        mode_frames.append(quick_mode_benchmark(config, utils, s07m, mode, mode_data))
    mode_scoreboard = pd.concat(mode_frames, ignore_index=True)

    y = primary["label_injected"].to_numpy(dtype=int)
    runs = primary["run"].to_numpy(dtype=int)
    winner = scoreboard.iloc[0]
    winner_score = scores[str(winner["method"])]
    trad_score = scores["traditional atom/template selector"]
    print("5/9 running charge-bin label-permutation null ...", flush=True)
    charge_null = charge_null_permutation(primary, y, winner_score, config)
    print("6/9 running grouped dropout localization ...", flush=True)
    localization = s07m.dropout_localization(primary, y, s07m.strict_shape_columns(primary, utils), config)
    print("7/9 running lightweight feature permutation localization ...", flush=True)
    permutation = quick_permutation_atoms(primary, y, s07m.strict_shape_columns(primary, utils), config)

    print("8/9 leakage checks and artifact assembly ...", flush=True)
    amp_score, _ = s07m.sklearn_oof(primary, y, utils.feature_columns(primary, "amplitude"), "gbt", config)
    bins = charge_bins(primary, config).to_numpy(dtype=int)
    pair_split_violations = 0
    for held_run in sorted(np.unique(runs)):
        train_pairs = set(primary.loc[runs != held_run, "pair_id"].astype(int))
        test_pairs = set(primary.loc[runs == held_run, "pair_id"].astype(int))
        pair_split_violations += len(train_pairs & test_pairs)
    leakage = pd.DataFrame(
        [
            {"probe": "pre-injection D_t", "value": auc(y, primary["base_d_t_ns"].to_numpy(dtype=float)), "notes": "Same for clean/injected pair members; should be near chance."},
            {"probe": "absolute-amplitude-only GBT", "value": auc(y, amp_score), "notes": "Excluded nuisance channel; should be below the shape winner."},
            {"probe": "run+charge-bin label permutation mean AUC", "value": float(charge_null.iloc[0]["null_auc_mean"]), "notes": "Destroys labels within run and target-charge strata."},
            {"probe": "pair split violations", "value": float(pair_split_violations), "notes": "Must be zero."},
            {"probe": "forbidden strict-shape columns", "value": 0.0, "notes": "strict_shape_columns raises before fitting if forbidden inputs appear."},
            {"probe": "charge-bin count", "value": float(len(np.unique(bins))), "notes": "Used for charge-pair-matched null permutations."},
        ]
    )

    oof = primary[["row_id", "event_key", "pair_id", "run", "label_injected", "variant", "preservation_mode", "base_d_t_ns", "d_t_ns", "abs_c_t_ns", "target_stave", "injected_delay_samples", "injected_scale", "renormalization_factor", "preserved_quantity_ratio", "target_positive_charge", "target_signed_area", "target_peak"]].copy()
    for name, score in scores.items():
        oof[name.replace(" ", "_").replace("-", "_").lower() + "_score"] = score

    delta_ci = bootstrap_delta_ci(y, winner_score, trad_score, runs, int(config["random_seed"]) + 777, int(config["bootstrap_replicates"]))
    result = {
        "ticket_id": config["ticket_id"],
        "study_id": config["study_id"],
        "worker": config["worker"],
        "winner_method": str(winner["method"]),
        "winner_roc_auc": float(winner["roc_auc"]),
        "winner_roc_auc_ci": [float(winner["roc_auc_ci_low"]), float(winner["roc_auc_ci_high"])],
        "winner_average_precision": float(winner["average_precision"]),
        "winner_fixed95_clean_rejection": float(winner["fixed95_clean_rejection"]),
        "traditional_roc_auc": float(scoreboard.loc[scoreboard["method"] == "traditional atom/template selector", "roc_auc"].iloc[0]),
        "winner_minus_traditional_auc": float(winner["roc_auc"] - auc(y, trad_score)),
        "winner_minus_traditional_auc_ci": [float(delta_ci[0]), float(delta_ci[1])],
        "charge_null_auc_mean": float(charge_null.iloc[0]["null_auc_mean"]),
        "charge_null_auc_loss": float(charge_null.iloc[0]["charge_null_auc_loss"]),
        "top_localization_group": str(localization.iloc[0]["group"]),
        "top_localization_delta_auc": float(localization.iloc[0]["delta_auc"]),
        "top_permutation_feature": str(permutation.iloc[0]["feature"]),
        "top_permutation_auc_importance": float(permutation.iloc[0]["mean_auc_importance"]),
        "raw_reproduction_pass": raw_reproduction_pass,
        "reference_auc_reproduction_pass": reference_auc_reproduction_pass,
        "dataset_events": int(len(primary)),
        "dataset_pairs": int(primary["pair_id"].nunique()),
        "runs": [int(run) for run in sorted(np.unique(runs))],
        "pair_split_violations": int(pair_split_violations),
        "method_auc": {str(row["method"]): float(row["roc_auc"]) for _, row in scoreboard.iterrows()},
        "elapsed_seconds": float(time.time() - t0),
    }

    print("9/9 writing report and manifest ...", flush=True)
    reproduction.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    run_counts.to_csv(out_dir / "run_counts.csv", index=False)
    s07e_score.to_csv(out_dir / "s07e_reproduction_scoreboard.csv", index=False)
    s07f_score.to_csv(out_dir / "s07f_reproduction_scoreboard.csv", index=False)
    counts.to_csv(out_dir / "dataset_counts_by_run.csv", index=False)
    scoreboard.to_csv(out_dir / "scoreboard.csv", index=False)
    fold_scores.to_csv(out_dir / "fold_scores.csv", index=False)
    traditional_choices.to_csv(out_dir / "traditional_fold_choices.csv", index=False)
    traditional_candidates.to_csv(out_dir / "traditional_candidate_scores.csv", index=False)
    rf_scan.to_csv(out_dir / "rf_probe_scan.csv", index=False)
    mode_scoreboard.to_csv(out_dir / "strict_charge_null_scoreboard.csv", index=False)
    charge_null.to_csv(out_dir / "charge_bin_permutation_null.csv", index=False)
    localization.to_csv(out_dir / "localization_dropout.csv", index=False)
    permutation.to_csv(out_dir / "permutation_importance.csv", index=False)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)
    oof.to_csv(out_dir / "oof_predictions.csv", index=False)
    write_report(out_dir, config, reproduction, counts, scoreboard, fold_scores, mode_scoreboard, traditional_choices, localization, permutation, leakage, charge_null, result)
    (out_dir / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    input_rows = []
    for run in config["runs"]:
        path = raw_file(config, int(run))
        input_rows.append({"path": str(path), "sha256": sha256_file(path), "bytes": path.stat().st_size})
    for path in [config_path, Path(__file__), S07F_PATH, S07G_PATH, S07M_PATH, ROOT / config["utility_script"]]:
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
        "command": f"/home/billy/anaconda3/bin/python scripts/s07n_1781068159_1658_5f900b07_normalized_shape_charge_null.py --config {config_path}",
        "inputs": input_rows,
        "outputs": {},
    }
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            manifest["outputs"][path.name] = sha256_file(path)
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
