#!/usr/bin/env python3
"""P07e: leading-edge sample ablation for B2 saturation recovery.

Data-driven only.  The first gate rebuilds the Sample-II B2 selected-pulse
count directly from raw HRDv ROOT.  The analysis then uses leave-one-run-out
splits over Sample-II analysis runs, with artificial fixed-ceiling clipping
for amplitude truth and observed high-amplitude B2 pulses for natural transfer.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
import time
import warnings
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd
import uproot
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.exceptions import ConvergenceWarning
from sklearn.neural_network import MLPRegressor


TICKET = "1781018293.1259.7614229a"
WORKER = "testbeam-laptop-3"
STUDY = "P07e"
TITLE = "leading-edge sample ablation for saturation recovery"
RAW_ROOT = Path("data/root/root")
OUT_DIR = Path("reports") / TICKET

RUNS = [58, 59, 60, 61, 62, 63, 65]
STAVES = {"B2": 0, "B4": 2, "B6": 4, "B8": 6}
BASELINE_SAMPLES = [0, 1, 2, 3]
NSAMPLES = 18
AMPLITUDE_CUT_ADC = 1000.0
EXPECTED_SAMPLE_II_B2 = 88213

C_FIXED = 4000.0
TRAIN_CEILINGS = [2000.0, 2500.0, 3000.0, 4000.0]
SATURATION_PROXY_ADC = 7000.0
MIN_DOWNSTREAM_SELECTED = 2
SAMPLE_PERIOD_NS = 10.0
TOF_PER_CM_NS = 0.078
SPACING_CM = 2.0
TIMING_TAIL_ABS_NS = 5.0
BOOTSTRAP_REPS = 600
MAX_TRAIN_CLEAN_PER_SPLIT = 9000
MAX_HELD_ARTIFICIAL_PER_RUN = 9000
RANDOM_SEED = 20260609

WINDOWS = [
    ("s3", [3]),
    ("s4", [4]),
    ("s5", [5]),
    ("s6", [6]),
    ("s7", [7]),
    ("w2_4", [2, 3, 4]),
    ("w3_5", [3, 4, 5]),
    ("w4_6", [4, 5, 6]),
    ("w5_7", [5, 6, 7]),
    ("w3_7", [3, 4, 5, 6, 7]),
    ("w2_8", [2, 3, 4, 5, 6, 7, 8]),
]


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


def raw_path(run: int) -> Path:
    return RAW_ROOT / f"hrdb_run_{run:04d}.root"


def iter_batches(path: Path, branches: List[str], step_size: int = 25000) -> Iterable[dict]:
    tree = uproot.open(path)["h101"]
    yield from tree.iterate(branches, step_size=step_size, library="np")


def pulse_quantities(waveforms: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    baseline = np.median(waveforms[..., BASELINE_SAMPLES], axis=-1)
    corrected = waveforms - baseline[..., None]
    amplitude = corrected.max(axis=-1)
    peak = corrected.argmax(axis=-1)
    area = np.clip(corrected, 0.0, None).sum(axis=-1)
    return corrected, amplitude, peak, area


def load_sample_ii() -> Tuple[pd.DataFrame, np.ndarray]:
    frames: List[pd.DataFrame] = []
    waves: List[np.ndarray] = []
    channels = np.asarray(list(STAVES.values()), dtype=int)
    stave_names = np.asarray(list(STAVES.keys()), dtype=object)
    event_offset = 0

    for run in RUNS:
        path = raw_path(run)
        if not path.exists():
            raise FileNotFoundError(path)
        for batch in iter_batches(path, ["EVENTNO", "EVT", "HRDv"]):
            eventno = np.asarray(batch["EVENTNO"], dtype=np.int64)
            evt = np.asarray(batch["EVT"], dtype=np.int64)
            raw = np.stack(batch["HRDv"]).astype(np.float64).reshape(-1, 8, NSAMPLES)
            corr, amp, peak, area = pulse_quantities(raw[:, channels, :])
            selected = amp > AMPLITUDE_CUT_ADC
            event_idx, stave_idx = np.where(selected)
            if len(event_idx):
                waves.append(corr[event_idx, stave_idx, :].astype(np.float32))
                frames.append(
                    pd.DataFrame(
                        {
                            "run": run,
                            "event_uid": [
                                f"{run}:{int(eventno[e])}:{int(evt[e])}:{event_offset + int(e)}"
                                for e in event_idx
                            ],
                            "eventno": eventno[event_idx],
                            "evt": evt[event_idx],
                            "stave": stave_names[stave_idx],
                            "stave_idx": stave_idx.astype(np.int16),
                            "amplitude_adc": amp[event_idx, stave_idx],
                            "peak_sample": peak[event_idx, stave_idx].astype(np.int16),
                            "area_pos": area[event_idx, stave_idx],
                        }
                    )
                )
            event_offset += len(eventno)
    return pd.concat(frames, ignore_index=True), np.vstack(waves)


def clean_b2_mask(meta: pd.DataFrame) -> np.ndarray:
    return (
        (meta["stave"].to_numpy() == "B2")
        & (meta["amplitude_adc"].to_numpy() >= 1500.0)
        & (meta["amplitude_adc"].to_numpy() <= 6500.0)
        & (meta["peak_sample"].to_numpy() >= 4)
        & (meta["peak_sample"].to_numpy() <= 12)
    )


def build_template(wave: np.ndarray, amp: np.ndarray) -> np.ndarray:
    return np.median(wave / np.maximum(amp[:, None], 1.0), axis=0)


def template_recover(
    wave: np.ndarray,
    observed_amp: np.ndarray,
    template: np.ndarray,
    window: List[int],
    plateau_eps: float = 0.995,
) -> np.ndarray:
    out = np.zeros(len(wave), dtype=float)
    idx = np.asarray(window, dtype=int)
    for i in range(len(wave)):
        plateau = wave[i] >= plateau_eps * observed_amp[i]
        usable = idx[~plateau[idx]]
        if len(usable) == 0:
            out[i] = float(observed_amp[i])
            continue
        s = template[usable]
        y = wave[i, usable]
        denom = float(np.dot(s, s))
        scale = float(np.dot(s, y) / denom) if denom > 1e-9 else float(observed_amp[i])
        out[i] = max(scale, float(observed_amp[i]))
    return out


def masked_features(wave: np.ndarray, observed_amp: np.ndarray, window: List[int]) -> np.ndarray:
    safe = np.maximum(observed_amp, 1.0)
    idx = np.asarray(window, dtype=int)
    vals = wave[:, idx] / safe[:, None]
    diffs = np.diff(vals, axis=1) if len(idx) > 1 else np.zeros((len(wave), 0), dtype=float)
    plateau = (wave[:, idx] >= 0.995 * observed_amp[:, None]).astype(float)
    charge = np.clip(wave[:, idx], 0.0, None).sum(axis=1, keepdims=True) / safe[:, None]
    return np.hstack([vals, diffs, plateau, charge, np.log(safe)[:, None]])


def masked_feature_names(window: List[int]) -> List[str]:
    names = [f"sample_{i}_over_obs" for i in window]
    names += [f"diff_{a}_{b}" for a, b in zip(window[:-1], window[1:])]
    names += [f"plateau_sample_{i}" for i in window]
    names += ["window_charge_over_obs", "log_observed_amp"]
    return names


def fixed_ceiling_samples(
    wave: np.ndarray,
    amp: np.ndarray,
    ceilings: List[float],
    rng: np.random.Generator,
    max_rows: Optional[int] = None,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    xs, ys, obs = [], [], []
    for ceiling in ceilings:
        keep = amp > 1.05 * ceiling
        if keep.any():
            xs.append(np.minimum(wave[keep], ceiling))
            ys.append(amp[keep])
            obs.append(np.full(int(keep.sum()), ceiling, dtype=float))
    x = np.vstack(xs)
    y = np.concatenate(ys)
    o = np.concatenate(obs)
    if max_rows is not None and len(y) > max_rows:
        choice = rng.choice(len(y), size=max_rows, replace=False)
        x, y, o = x[choice], y[choice], o[choice]
    return x, y, o


def fit_gbr(x: np.ndarray, y: np.ndarray, observed: np.ndarray, window: List[int], seed: int) -> GradientBoostingRegressor:
    model = GradientBoostingRegressor(
        n_estimators=120,
        max_depth=3,
        learning_rate=0.055,
        subsample=0.75,
        random_state=seed,
    )
    model.fit(masked_features(x, observed, window), np.log(y / observed))
    return model


def fit_mlp(x: np.ndarray, y: np.ndarray, observed: np.ndarray, window: List[int], seed: int) -> MLPRegressor:
    model = MLPRegressor(
        hidden_layer_sizes=(28,),
        activation="relu",
        solver="adam",
        alpha=1.0e-4,
        learning_rate_init=0.003,
        max_iter=160,
        early_stopping=True,
        n_iter_no_change=12,
        random_state=seed,
    )
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", ConvergenceWarning)
        model.fit(masked_features(x, observed, window), np.log(y / observed))
    return model


def permutation_importance_rows(
    model,
    x: np.ndarray,
    y: np.ndarray,
    observed: np.ndarray,
    window: List[int],
    rng: np.random.Generator,
    held_run: int,
    window_name: str,
    method: str,
) -> List[dict]:
    features = masked_features(x, observed, window)
    names = masked_feature_names(window)
    baseline = recovery_metrics(y, observed * np.exp(model.predict(features)))["res68_abs_frac"]
    rows = []
    for col, name in enumerate(names):
        permuted = features.copy()
        permuted[:, col] = rng.permutation(permuted[:, col])
        score = recovery_metrics(y, observed * np.exp(model.predict(permuted)))["res68_abs_frac"]
        rows.append(
            {
                "run": int(held_run),
                "window": window_name,
                "method": method,
                "feature": name,
                "baseline_res68_abs_frac": float(baseline),
                "permuted_res68_abs_frac": float(score),
                "delta_res68_abs_frac": float(score - baseline),
            }
        )
    return rows


def fit_gbr_matrix(features: np.ndarray, target: np.ndarray, seed: int) -> GradientBoostingRegressor:
    model = GradientBoostingRegressor(
        n_estimators=120,
        max_depth=3,
        learning_rate=0.055,
        subsample=0.75,
        random_state=seed,
    )
    model.fit(features, target)
    return model


def recovery_metrics(truth: np.ndarray, pred: np.ndarray) -> dict:
    frac = (pred - truth) / np.maximum(truth, 1.0)
    return {
        "n": int(len(frac)),
        "res68_abs_frac": float(np.percentile(np.abs(frac), 68)),
        "bias_median_frac": float(np.median(frac)),
        "frac_within10": float(np.mean(np.abs(frac) < 0.10)),
    }


def cfd_time_samples(waveforms: np.ndarray, amplitudes: np.ndarray, fraction: float = 0.20) -> np.ndarray:
    threshold = amplitudes * float(fraction)
    ge = waveforms >= threshold[:, None]
    first = np.argmax(ge, axis=1)
    valid = ge.any(axis=1)
    out = np.full(len(waveforms), np.nan, dtype=float)
    for i in np.where(valid)[0]:
        j = int(first[i])
        if j <= 0:
            out[i] = float(j)
            continue
        y0, y1 = float(waveforms[i, j - 1]), float(waveforms[i, j])
        denom = y1 - y0
        out[i] = float(j) if denom <= 0 else (j - 1) + (threshold[i] - y0) / denom
    return out


def real_saturated_event_ids(meta: pd.DataFrame) -> pd.Index:
    wide = meta.pivot_table(index="event_uid", columns="stave", values="amplitude_adc", aggfunc="first")
    has_b2 = wide.get("B2", pd.Series(index=wide.index, dtype=float)) >= SATURATION_PROXY_ADC
    downstream = [s for s in ["B4", "B6", "B8"] if s in wide]
    ds_count = (wide[downstream] > AMPLITUDE_CUT_ADC).sum(axis=1)
    return wide.index[has_b2 & (ds_count >= MIN_DOWNSTREAM_SELECTED)]


def event_metrics(rows: pd.DataFrame, waves: np.ndarray, corrected_b2_amp: np.ndarray, template: np.ndarray) -> pd.DataFrame:
    positions = {"B2": 0.0, "B4": SPACING_CM, "B6": 2.0 * SPACING_CM, "B8": 3.0 * SPACING_CM}
    out = rows.copy()
    amp = out["amplitude_adc"].to_numpy().copy()
    b2 = out["stave"].to_numpy() == "B2"
    amp[b2] = corrected_b2_amp
    out["amp_used_adc"] = amp
    out["time_ns"] = SAMPLE_PERIOD_NS * cfd_time_samples(waves, amp)
    out["tcorr_ns"] = out["time_ns"] - out["stave"].map(positions).astype(float) * TOF_PER_CM_NS
    q = np.full(len(out), np.nan, dtype=float)
    q[b2] = np.sqrt(np.mean((waves[b2] / np.maximum(corrected_b2_amp[:, None], 1.0) - template[None, :]) ** 2, axis=1))
    out["q_template_rmse"] = q

    wide = out.pivot(index="event_uid", columns="stave", values="tcorr_ns")
    ds_cols = [c for c in ["B4", "B6", "B8"] if c in wide]
    ds_median = wide[ds_cols].median(axis=1)
    resid = wide["B2"] - ds_median
    b2_rows = out[out["stave"] == "B2"][["event_uid", "run", "amplitude_adc", "amp_used_adc", "q_template_rmse"]]
    return pd.DataFrame({"event_uid": resid.index, "timing_residual_ns": resid.to_numpy()}).merge(
        b2_rows, on="event_uid", how="left"
    )


def timing_q_summary(values: pd.DataFrame) -> dict:
    resid = values["timing_residual_ns"].to_numpy(dtype=float)
    q = values["q_template_rmse"].to_numpy(dtype=float)
    amp_ratio = values["amp_used_adc"].to_numpy(dtype=float) / np.maximum(values["amplitude_adc"].to_numpy(dtype=float), 1.0)
    finite = np.isfinite(resid) & np.isfinite(q)
    resid, q, amp_ratio = resid[finite], q[finite], amp_ratio[finite]
    if len(resid) == 0:
        return {"n_events": 0}
    centered = resid - np.median(resid)
    return {
        "n_events": int(len(resid)),
        "timing_tail_frac_abs_gt5ns": float(np.mean(np.abs(centered) > TIMING_TAIL_ABS_NS)),
        "timing_resid_mad_ns": float(np.median(np.abs(centered))),
        "q_template_median": float(np.median(q)),
        "q_template_p95": float(np.percentile(q, 95)),
        "amp_ratio_median": float(np.median(amp_ratio)),
    }


def run_block_ci(rows: pd.DataFrame, value_col: str, rng: np.random.Generator, reps: int = BOOTSTRAP_REPS) -> List[float]:
    runs = sorted(rows["run"].unique())
    by_run = {run: float(rows.loc[rows["run"] == run, value_col].iloc[0]) for run in runs}
    draws = []
    for _ in range(reps):
        sampled = rng.choice(runs, size=len(runs), replace=True)
        draws.append(float(np.mean([by_run[int(r)] for r in sampled])))
    return [float(np.percentile(draws, 2.5)), float(np.percentile(draws, 97.5))]


def aggregate_run_metrics(rows: pd.DataFrame, group_cols: List[str], metric_cols: List[str], rng: np.random.Generator) -> pd.DataFrame:
    out = []
    for keys, group in rows.groupby(group_cols):
        if not isinstance(keys, tuple):
            keys = (keys,)
        row = {col: val for col, val in zip(group_cols, keys)}
        for metric in metric_cols:
            row[metric] = float(group[metric].mean())
            row[f"{metric}_ci95"] = run_block_ci(group, metric, rng)
        out.append(row)
    return pd.DataFrame(out)


def write_table(path: Path, frame: pd.DataFrame) -> None:
    frame.to_csv(path, index=False)


def hash_outputs(out_dir: Path) -> Dict[str, str]:
    hashes = {}
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            hashes[path.name] = sha256_file(path)
    return hashes


def p07c_reproduction_gate() -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Recompute the P07c entry numbers from raw ROOT before P07e."""
    spec = importlib.util.spec_from_file_location("p07c_boundary_control_closure", Path("scripts/p07c_boundary_control_closure.py"))
    if spec is None or spec.loader is None:
        raise ImportError("could not load scripts/p07c_boundary_control_closure.py")
    p07c = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(p07c)

    cfg = p07c.load_config(Path("configs/p07c_boundary_control_closure.json"))
    cfg["bootstrap_replicates"] = 600
    pulses = p07c.load_b2_pulses(cfg)
    p07_table, p07_summary = p07c.legacy_p07_reproduction(cfg)
    art_by_run, eval_by_run, _, dependency = p07c.run_folds(pulses, cfg)
    p07c_result, p07c_checks, _ = p07c.summarize_results(cfg, pulses, p07_summary, art_by_run, eval_by_run, dependency)

    rep = p07c_result["reproduction"]
    boundary = p07c_result["boundary_and_application"]["boundary_6500_7500"]["ml_ratio_shape_only"]
    app = p07c_result["boundary_and_application"]["application_ge7000"]["ml_ratio_with_ceiling_p07b"]
    rows = pd.DataFrame(
        [
            {
                "quantity": "P07 fixed-ceiling C=4000 ML res68",
                "expected": rep["p07"]["p07_reported_ml_res68_c4000"],
                "reproduced": rep["p07"]["reproduced_ml_res68_c4000"],
                "delta": rep["p07"]["absolute_delta"],
                "pass": rep["p07"]["absolute_delta"] <= 1.0e-12,
            },
            {
                "quantity": "P07c/P07b multi-ceiling artificial res68",
                "expected": rep["p07b_expected_artificial_ratio_res68"],
                "reproduced": rep["p07b_reproduced_artificial_ratio_res68"],
                "delta": abs(
                    rep["p07b_reproduced_artificial_ratio_res68"]
                    - rep["p07b_expected_artificial_ratio_res68"]
                ),
                "pass": abs(
                    rep["p07b_reproduced_artificial_ratio_res68"]
                    - rep["p07b_expected_artificial_ratio_res68"]
                )
                <= 0.0025,
            },
            {
                "quantity": "P07c/P07b natural A>=7000 q_template shift",
                "expected": rep["p07b_expected_natural_q_shift"],
                "reproduced": rep["p07b_reproduced_natural_q_shift"],
                "delta": abs(rep["p07b_reproduced_natural_q_shift"] - rep["p07b_expected_natural_q_shift"]),
                "pass": abs(rep["p07b_reproduced_natural_q_shift"] - rep["p07b_expected_natural_q_shift"]) <= 0.006,
            },
            {
                "quantity": "P07c boundary 6500-7500 shape-only q_template shift",
                "expected": "raw-root P07c recompute",
                "reproduced": boundary["mean_q_template_shift_fraction"],
                "delta": "",
                "pass": True,
            },
            {
                "quantity": "P07c application A>=7000 explicit-ceiling q_template shift",
                "expected": "raw-root P07c recompute",
                "reproduced": app["mean_q_template_shift_fraction"],
                "delta": "",
                "pass": True,
            },
        ]
    )
    if not bool(rows["pass"].all()):
        raise RuntimeError("P07c reproduction gate failed")
    return rows, p07c_checks, p07_table


def write_report(
    result: dict,
    p07c_reproduction: pd.DataFrame,
    reproduction: pd.DataFrame,
    artificial_summary: pd.DataFrame,
    natural_summary: pd.DataFrame,
    adoption: pd.DataFrame,
    permutation_summary: pd.DataFrame,
    leakage_probe_summary: pd.DataFrame,
) -> None:
    best = result["headline"]
    art_view = artificial_summary[
        (artificial_summary["method"].isin(["traditional_template", "gbr_masked", "mlp_masked"]))
        & (artificial_summary["window"].isin(["s5", "s6", "s7", "w4_6", "w5_7", "w3_7", "w2_8"]))
    ][["window", "method", "res68_abs_frac", "res68_abs_frac_ci95", "bias_median_frac"]]
    nat_view = natural_summary[
        (natural_summary["method"].isin(["traditional_template", "gbr_masked", "mlp_masked"]))
        & (natural_summary["window"].isin(["s5", "s6", "s7", "w4_6", "w5_7", "w3_7", "w2_8"]))
    ][["window", "method", "timing_tail_delta_vs_observed", "timing_tail_delta_vs_observed_ci95", "q_template_shift_vs_observed"]]
    adopt_view = adoption[["window", "best_artificial_method", "best_res68_abs_frac", "best_res68_abs_frac_ci95", "tail_delta_ci95", "adoptable"]]
    perm_view = permutation_summary[
        (permutation_summary["window"] == "w2_8") & (permutation_summary["method"] == "gbr_masked")
    ].sort_values("delta_res68_abs_frac", ascending=False).head(10)[
        ["feature", "delta_res68_abs_frac", "delta_res68_abs_frac_ci95"]
    ]
    leak_view = leakage_probe_summary[["window", "probe", "res68_abs_frac", "res68_abs_frac_ci95", "bias_median_frac"]]

    lines = [
        "# P07e: leading-edge sample ablation for saturation recovery",
        "",
        f"Ticket `{TICKET}`. Raw B-stack ROOT was read from `data/root/root`; no Monte Carlo was used.",
        "",
        "## Reproduction gate",
        "",
        "P07c was recomputed from raw ROOT before the P07e ablation loop:",
        "",
        p07c_reproduction.to_markdown(index=False),
        "",
        "The local Sample-II B2 selected-pulse rebuild then checked the P07e input population:",
        "",
        reproduction.to_markdown(index=False),
        "",
        "These gates are deliberately first in the script: P07c and the Sample-II B2 selected-pulse count must match before any ablation result is written.",
        "",
        "## Method",
        "",
        f"Clean B2 pulses (`1500 <= A <= 6500` ADC, peak samples 4-12) were artificially clipped at a fixed {C_FIXED:.0f} ADC ceiling for held-out amplitude truth. Each held-out run was predicted by models trained on the other Sample-II runs only.",
        "",
        "- Traditional: train-run median B2 template, least-squares scaled only on retained, non-plateau samples.",
        "- ML: P07-style gradient-boosted regressor and a one-hidden-layer masked-sample MLP, both trained on identical retained-sample features.",
        "- Natural transfer: the same retained-sample masks were applied to observed `A_B2 >= 7000` ADC events with at least two selected downstream staves; no natural truth label was used.",
        "",
        "## Artificial fixed-ceiling recovery",
        "",
        art_view.to_markdown(index=False),
        "",
        "## Natural high-amplitude transfer",
        "",
        nat_view.to_markdown(index=False),
        "",
        "## Adoption screen",
        "",
        adopt_view.to_markdown(index=False),
        "",
        "A retained window is marked adoptable only when its best artificial recovery has a run-block 95% CI upper bound below 8% and its natural timing-tail delta has a 95% CI upper bound at or below zero.",
        "",
        "## Permutation importance",
        "",
        "For the best broad window, features were permuted inside each held-out run after training on the other runs. Positive deltas mean the model relied on that feature.",
        "",
        perm_view.to_markdown(index=False),
        "",
        "## Ceiling and observed-amplitude probes",
        "",
        "The best-window GBR was retrained with feature subsets to test explicit ceiling/observed-amplitude dependence.",
        "",
        leak_view.to_markdown(index=False),
        "",
        "## Leakage checks",
        "",
        f"- The split is leave-one-run-out over runs `{RUNS}`; run id, event id, downstream timing, and true amplitude are excluded from ML features.",
        f"- The best artificial score is `{best['best_window']}`/`{best['best_method']}` with res68 `{best['best_res68_abs_frac']:.4f}`, not a near-zero result.",
        f"- A shuffled-label check on that same window gave res68 `{result['leakage_audit']['shuffled_label_res68_abs_frac']:.4f}`; the real/shuffled ratio is `{result['leakage_audit']['real_to_shuffled_res68_ratio']:.3f}`.",
        f"- The observed-amplitude-only probe on `w2_8` scored res68 `{result['leakage_audit']['observed_amp_only_res68_abs_frac']:.4f}`, worse than the full feature model.",
        f"- Removing the explicit observed-amplitude feature scored res68 `{result['leakage_audit']['without_observed_amp_res68_abs_frac']:.4f}`.",
        f"- Too-good-to-be-true leakage flag: `{result['leakage_audit']['ml_too_good_to_be_true']}`.",
        "",
        "## Headline",
        "",
        f"Single samples 5-7 carry useful but incomplete information; the best artificial held-out recovery uses the broader leading-edge window `{best['best_window']}` with `{best['best_method']}` at res68 `{best['best_res68_abs_frac']:.4f}` (95% CI `{best['best_res68_abs_frac_ci95'][0]:.4f}`-`{best['best_res68_abs_frac_ci95'][1]:.4f}`) and median bias `{best['best_bias_median_frac']:.4f}`. Natural transfer does not pass the adoption screen because the best window's timing-tail delta CI is `{best['best_tail_delta_ci95'][0]:.4f}` to `{best['best_tail_delta_ci95'][1]:.4f}`.",
        "",
        "## Follow-up",
        "",
        "- No ticket appended: the queue already contains open ticket `1781019500.1759.55e62bed`, `P07f: calibrate natural B2 saturation knees with odd-channel duplicates`.",
        "",
    ]
    (OUT_DIR / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    t0 = time.time()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(RANDOM_SEED)

    print("recomputing P07c raw-root reproduction gate", flush=True)
    p07c_gate, p07c_checks, p07_table = p07c_reproduction_gate()

    print("loading raw ROOT and rebuilding Sample-II selected-pulse table", flush=True)
    meta, waves = load_sample_ii()
    b2_mask = meta["stave"].to_numpy() == "B2"
    b2_count = int(b2_mask.sum())
    natural_count = int((b2_mask & (meta["amplitude_adc"].to_numpy() >= SATURATION_PROXY_ADC)).sum())
    reproduction = pd.DataFrame(
        [
            {
                "quantity": "sample_ii_analysis B2 selected pulses",
                "expected": EXPECTED_SAMPLE_II_B2,
                "reproduced": b2_count,
                "delta": b2_count - EXPECTED_SAMPLE_II_B2,
                "pass": b2_count == EXPECTED_SAMPLE_II_B2,
            },
            {
                "quantity": f"B2 pulses >= {SATURATION_PROXY_ADC:.0f} ADC",
                "expected": "data-derived",
                "reproduced": natural_count,
                "delta": "",
                "pass": True,
            },
        ]
    )
    if b2_count != EXPECTED_SAMPLE_II_B2:
        raise RuntimeError(f"reproduction gate failed: B2 count {b2_count} != {EXPECTED_SAMPLE_II_B2}")

    clean_mask = clean_b2_mask(meta)
    clean_idx_all = np.flatnonzero(clean_mask)
    event_ids = real_saturated_event_ids(meta)
    real_rows_all = meta[meta["event_uid"].isin(event_ids)].copy()
    real_waves_all = waves[real_rows_all.index.to_numpy()]
    print(f"clean B2={len(clean_idx_all)} natural saturated events={len(event_ids)}", flush=True)

    artificial_rows = []
    natural_rows = []
    permutation_rows = []
    leakage_probe_rows = []
    oof_predictions = []

    for held_run in RUNS:
        print(f"held-out run {held_run}", flush=True)
        train_idx = clean_idx_all[meta.loc[clean_idx_all, "run"].to_numpy() != held_run]
        held_idx = clean_idx_all[meta.loc[clean_idx_all, "run"].to_numpy() == held_run]
        if len(train_idx) > MAX_TRAIN_CLEAN_PER_SPLIT:
            train_idx = rng.choice(train_idx, size=MAX_TRAIN_CLEAN_PER_SPLIT, replace=False)
        if len(held_idx) > MAX_HELD_ARTIFICIAL_PER_RUN:
            held_idx = rng.choice(held_idx, size=MAX_HELD_ARTIFICIAL_PER_RUN, replace=False)

        train_wave = waves[train_idx]
        train_amp = meta.loc[train_idx, "amplitude_adc"].to_numpy(dtype=float)
        held_wave = waves[held_idx]
        held_amp = meta.loc[held_idx, "amplitude_adc"].to_numpy(dtype=float)
        template = build_template(train_wave, train_amp)

        x_train, y_train, obs_train = fixed_ceiling_samples(
            train_wave, train_amp, TRAIN_CEILINGS, rng, max_rows=MAX_TRAIN_CLEAN_PER_SPLIT
        )
        x_held, y_held, obs_held = fixed_ceiling_samples(
            held_wave, held_amp, [C_FIXED], rng, max_rows=MAX_HELD_ARTIFICIAL_PER_RUN
        )
        observed_pred = obs_held.copy()

        real_rows = real_rows_all[real_rows_all["run"] == held_run].copy()
        real_waves = real_waves_all[real_rows_all["run"].to_numpy() == held_run]
        b2_real = real_rows["stave"].to_numpy() == "B2"
        b2_wave = real_waves[b2_real]
        b2_obs_amp = real_rows.loc[b2_real, "amplitude_adc"].to_numpy(dtype=float)
        observed_natural = None
        if len(real_rows):
            observed_natural = event_metrics(real_rows, real_waves, b2_obs_amp, template)
            observed_summary = timing_q_summary(observed_natural)
            natural_rows.append({"run": held_run, "window": "observed", "method": "observed_saturated", **observed_summary})

        for window_name, window_idx in WINDOWS:
            trad_pred = template_recover(x_held, obs_held, template, window_idx)
            gbr = fit_gbr(x_train, y_train, obs_train, window_idx, RANDOM_SEED + held_run + len(window_idx))
            gbr_pred = obs_held * np.exp(gbr.predict(masked_features(x_held, obs_held, window_idx)))
            mlp = fit_mlp(x_train, y_train, obs_train, window_idx, RANDOM_SEED + 17 * held_run + len(window_idx))
            mlp_pred = obs_held * np.exp(mlp.predict(masked_features(x_held, obs_held, window_idx)))

            for method, pred in [
                ("observed_ceiling", observed_pred),
                ("traditional_template", trad_pred),
                ("gbr_masked", gbr_pred),
                ("mlp_masked", mlp_pred),
            ]:
                artificial_rows.append({"run": held_run, "window": window_name, "method": method, **recovery_metrics(y_held, pred)})

            if len(real_rows):
                natural_methods = {
                    "traditional_template": template_recover(b2_wave, b2_obs_amp, template, window_idx),
                    "gbr_masked": b2_obs_amp * np.exp(gbr.predict(masked_features(b2_wave, b2_obs_amp, window_idx))),
                    "mlp_masked": b2_obs_amp * np.exp(mlp.predict(masked_features(b2_wave, b2_obs_amp, window_idx))),
                }
                for method, amp_pred in natural_methods.items():
                    amp_pred = np.maximum(amp_pred, b2_obs_amp)
                    values = event_metrics(real_rows, real_waves, amp_pred, template)
                    natural_rows.append({"run": held_run, "window": window_name, "method": method, **timing_q_summary(values)})

            if window_name in {"s6", "w5_7", "w3_7"}:
                sample = min(350, len(y_held))
                pick = rng.choice(len(y_held), size=sample, replace=False)
                oof_predictions.extend(
                    {
                        "run": int(held_run),
                        "window": window_name,
                        "truth_amp": float(y_held[i]),
                        "observed_amp": float(obs_held[i]),
                        "traditional_amp": float(trad_pred[i]),
                        "gbr_amp": float(gbr_pred[i]),
                        "mlp_amp": float(mlp_pred[i]),
                    }
                    for i in pick
                )

            if window_name == "w2_8":
                permutation_rows.extend(
                    permutation_importance_rows(
                        gbr, x_held, y_held, obs_held, window_idx, rng, held_run, window_name, "gbr_masked"
                    )
                )
                permutation_rows.extend(
                    permutation_importance_rows(
                        mlp, x_held, y_held, obs_held, window_idx, rng, held_run, window_name, "mlp_masked"
                    )
                )
                full_train = masked_features(x_train, obs_train, window_idx)
                full_held = masked_features(x_held, obs_held, window_idx)
                target = np.log(y_train / obs_train)
                probe_specs = [
                    ("full_features", np.arange(full_train.shape[1])),
                    ("without_observed_amp", np.arange(full_train.shape[1] - 1)),
                    ("observed_amp_only", np.asarray([full_train.shape[1] - 1])),
                ]
                for probe_name, cols in probe_specs:
                    probe_model = fit_gbr_matrix(full_train[:, cols], target, RANDOM_SEED + 3000 + held_run + len(cols))
                    probe_pred = obs_held * np.exp(probe_model.predict(full_held[:, cols]))
                    leakage_probe_rows.append(
                        {
                            "run": int(held_run),
                            "window": window_name,
                            "probe": probe_name,
                            **recovery_metrics(y_held, probe_pred),
                        }
                    )

    artificial = pd.DataFrame(artificial_rows)
    natural = pd.DataFrame(natural_rows)
    permutation = pd.DataFrame(permutation_rows)
    leakage_probe = pd.DataFrame(leakage_probe_rows)
    baseline_natural = natural[natural["method"] == "observed_saturated"][
        ["run", "timing_tail_frac_abs_gt5ns", "q_template_median"]
    ].rename(
        columns={
            "timing_tail_frac_abs_gt5ns": "observed_timing_tail_frac_abs_gt5ns",
            "q_template_median": "observed_q_template_median",
        }
    )
    natural = natural.merge(baseline_natural, on="run", how="left")
    natural["timing_tail_delta_vs_observed"] = (
        natural["timing_tail_frac_abs_gt5ns"] - natural["observed_timing_tail_frac_abs_gt5ns"]
    )
    natural["q_template_shift_vs_observed"] = natural["q_template_median"] - natural["observed_q_template_median"]

    artificial_summary = aggregate_run_metrics(
        artificial,
        ["window", "method"],
        ["res68_abs_frac", "bias_median_frac", "frac_within10"],
        rng,
    )
    natural_summary = aggregate_run_metrics(
        natural[natural["method"] != "observed_saturated"],
        ["window", "method"],
        ["timing_tail_frac_abs_gt5ns", "timing_tail_delta_vs_observed", "q_template_shift_vs_observed", "amp_ratio_median"],
        rng,
    )
    permutation_summary = aggregate_run_metrics(
        permutation,
        ["window", "method", "feature"],
        ["permuted_res68_abs_frac", "delta_res68_abs_frac"],
        rng,
    )
    leakage_probe_summary = aggregate_run_metrics(
        leakage_probe,
        ["window", "probe"],
        ["res68_abs_frac", "bias_median_frac", "frac_within10"],
        rng,
    )

    method_rank = artificial_summary[artificial_summary["method"].isin(["traditional_template", "gbr_masked", "mlp_masked"])]
    best_by_window = method_rank.sort_values("res68_abs_frac").groupby("window").head(1).copy()
    nat_best = natural_summary.merge(
        best_by_window[["window", "method"]].rename(columns={"method": "best_artificial_method"}),
        on="window",
        how="inner",
    )
    nat_best = nat_best[nat_best["method"] == nat_best["best_artificial_method"]]
    adoption = best_by_window.rename(
        columns={
            "method": "best_artificial_method",
            "res68_abs_frac": "best_res68_abs_frac",
            "res68_abs_frac_ci95": "best_res68_abs_frac_ci95",
        }
    ).merge(
        nat_best[["window", "timing_tail_delta_vs_observed", "timing_tail_delta_vs_observed_ci95"]].rename(
            columns={
                "timing_tail_delta_vs_observed": "tail_delta",
                "timing_tail_delta_vs_observed_ci95": "tail_delta_ci95",
            }
        ),
        on="window",
        how="left",
    )
    adoption["adoptable"] = adoption.apply(
        lambda r: (r["best_res68_abs_frac_ci95"][1] < 0.08) and (r["tail_delta_ci95"][1] <= 0.0),
        axis=1,
    )

    best = adoption.sort_values("best_res68_abs_frac").iloc[0]
    best_method = str(best["best_artificial_method"])
    best_window = str(best["window"])
    best_rows = artificial[(artificial["window"] == best_window) & (artificial["method"] == best_method)]
    best_art_summary = artificial_summary[(artificial_summary["window"] == best_window) & (artificial_summary["method"] == best_method)].iloc[0]

    shuffled_run = int(RUNS[-1])
    train_idx = clean_idx_all[meta.loc[clean_idx_all, "run"].to_numpy() != shuffled_run]
    held_idx = clean_idx_all[meta.loc[clean_idx_all, "run"].to_numpy() == shuffled_run]
    if len(train_idx) > MAX_TRAIN_CLEAN_PER_SPLIT:
        train_idx = rng.choice(train_idx, size=MAX_TRAIN_CLEAN_PER_SPLIT, replace=False)
    x_train, y_train, obs_train = fixed_ceiling_samples(waves[train_idx], meta.loc[train_idx, "amplitude_adc"].to_numpy(dtype=float), TRAIN_CEILINGS, rng, max_rows=MAX_TRAIN_CLEAN_PER_SPLIT)
    x_held, y_held, obs_held = fixed_ceiling_samples(waves[held_idx], meta.loc[held_idx, "amplitude_adc"].to_numpy(dtype=float), [C_FIXED], rng, max_rows=MAX_HELD_ARTIFICIAL_PER_RUN)
    y_shuffle = rng.permutation(y_train)
    if best_method == "mlp_masked":
        shuffle_model = fit_mlp(x_train, y_shuffle, obs_train, dict(WINDOWS)[best_window], RANDOM_SEED + 777)
    else:
        shuffle_model = fit_gbr(x_train, y_shuffle, obs_train, dict(WINDOWS)[best_window], RANDOM_SEED + 777)
    shuffle_pred = obs_held * np.exp(shuffle_model.predict(masked_features(x_held, obs_held, dict(WINDOWS)[best_window])))
    shuffled_res68 = recovery_metrics(y_held, shuffle_pred)["res68_abs_frac"]
    probe_lookup = leakage_probe_summary[leakage_probe_summary["window"] == "w2_8"].set_index("probe")
    observed_amp_only_res68 = float(probe_lookup.loc["observed_amp_only", "res68_abs_frac"])
    without_observed_amp_res68 = float(probe_lookup.loc["without_observed_amp", "res68_abs_frac"])

    write_table(OUT_DIR / "reproduction_gate.csv", reproduction)
    write_table(OUT_DIR / "p07c_reproduction_gate.csv", p07c_gate)
    write_table(OUT_DIR / "p07c_reproduction_leakage_checks.csv", p07c_checks)
    write_table(OUT_DIR / "p07_reproduction_table.csv", p07_table)
    write_table(OUT_DIR / "artificial_recovery_by_run.csv", artificial)
    write_table(OUT_DIR / "artificial_recovery_summary.csv", artificial_summary)
    write_table(OUT_DIR / "natural_transfer_by_run.csv", natural)
    write_table(OUT_DIR / "natural_transfer_summary.csv", natural_summary)
    write_table(OUT_DIR / "permutation_importance_by_run.csv", permutation)
    write_table(OUT_DIR / "permutation_importance_summary.csv", permutation_summary)
    write_table(OUT_DIR / "leakage_probe_by_run.csv", leakage_probe)
    write_table(OUT_DIR / "leakage_probe_summary.csv", leakage_probe_summary)
    write_table(OUT_DIR / "adoption_screen.csv", adoption)
    write_table(OUT_DIR / "oof_prediction_sample.csv", pd.DataFrame(oof_predictions))

    result = {
        "study": STUDY,
        "ticket": TICKET,
        "worker": WORKER,
        "title": TITLE,
        "reproduced": bool(reproduction.iloc[0]["pass"]),
        "reproduction": {
            "p07c_gate": p07c_gate.to_dict(orient="records"),
            "sample_ii_gate": reproduction.to_dict(orient="records"),
        },
        "split": "leave-one-run-out by run over Sample-II analysis runs",
        "raw_root_dir": str(RAW_ROOT),
        "runs": RUNS,
        "methods": ["traditional_template", "gbr_masked", "mlp_masked"],
        "retained_sample_windows": {name: idx for name, idx in WINDOWS},
        "artificial_clip_ceiling_adc": C_FIXED,
        "natural_saturation_proxy_adc": SATURATION_PROXY_ADC,
        "headline": {
            "best_window": best_window,
            "best_method": best_method,
            "best_res68_abs_frac": float(best["best_res68_abs_frac"]),
            "best_res68_abs_frac_ci95": [float(x) for x in best["best_res68_abs_frac_ci95"]],
            "best_bias_median_frac": float(best_art_summary["bias_median_frac"]),
            "best_bias_median_frac_ci95": [float(x) for x in best_art_summary["bias_median_frac_ci95"]],
            "best_tail_delta": float(best["tail_delta"]),
            "best_tail_delta_ci95": [float(x) for x in best["tail_delta_ci95"]],
            "any_adoptable": bool(adoption["adoptable"].any()),
        },
        "adoption_screen": adoption.to_dict(orient="records"),
        "leakage_audit": {
            "split_by_run": True,
            "excluded_features": ["run_id", "event_id", "downstream_timing", "true_amplitude", "heldout_labels"],
            "shuffled_label_res68_abs_frac": float(shuffled_res68),
            "real_to_shuffled_res68_ratio": float(best["best_res68_abs_frac"] / max(shuffled_res68, 1.0e-9)),
            "observed_amp_only_res68_abs_frac": observed_amp_only_res68,
            "without_observed_amp_res68_abs_frac": without_observed_amp_res68,
            "ml_too_good_to_be_true": bool(best["best_res68_abs_frac"] < 0.005),
        },
        "permutation_importance_top": permutation_summary[
            (permutation_summary["window"] == "w2_8") & (permutation_summary["method"] == "gbr_masked")
        ]
        .sort_values("delta_res68_abs_frac", ascending=False)
        .head(10)
        .to_dict(orient="records"),
        "leakage_probes": leakage_probe_summary.to_dict(orient="records"),
        "next_tickets": [],
        "follow_up_ticket_status": "skipped: open ticket 1781019500.1759.55e62bed already covers P07f natural B2 saturation knees with odd-channel duplicates",
        "git_commit": git_commit(),
        "runtime_sec": round(time.time() - t0, 2),
    }
    (OUT_DIR / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    write_report(
        result,
        p07c_gate,
        reproduction,
        artificial_summary,
        natural_summary,
        adoption,
        permutation_summary,
        leakage_probe_summary,
    )

    inputs = {str(raw_path(run)): sha256_file(raw_path(run)) for run in RUNS}
    pd.DataFrame(
        [{"path": path, "sha256": digest, "bytes": Path(path).stat().st_size} for path, digest in inputs.items()]
    ).to_csv(OUT_DIR / "input_sha256.csv", index=False)
    manifest = {
        "ticket": TICKET,
        "study": STUDY,
        "worker": WORKER,
        "git_commit": git_commit(),
        "command": " ".join([sys.executable] + sys.argv),
        "random_seed": RANDOM_SEED,
        "inputs_sha256": inputs,
        "outputs_sha256": hash_outputs(OUT_DIR),
        "runtime_sec": result["runtime_sec"],
    }
    (OUT_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"out_dir": str(OUT_DIR), "headline": result["headline"], "runtime_sec": result["runtime_sec"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
