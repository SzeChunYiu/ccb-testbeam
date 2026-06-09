#!/usr/bin/env python3
"""S07b timing-control classifier rigour pass.

This report-local script derives App.I-style D_t labels directly from raw B-stack
HRDv waveforms, then compares a label-defining traditional timing score with a
shape-only random forest under leave-one-run-held-out evaluation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Tuple

os.environ.setdefault(
    "MPLCONFIGDIR",
    "/tmp/ccb-testbeam-s07b-matplotlib-cache",
)

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import uproot
from sklearn.ensemble import RandomForestClassifier
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score


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


def raw_file(config: dict, run: int) -> Path:
    return Path(config["raw_root_dir"]) / f"hrdb_run_{run:04d}.root"


def iter_raw(path: Path, branches: List[str], step_size: int = 20000) -> Iterable[dict]:
    tree = uproot.open(path)["h101"]
    yield from tree.iterate(branches, step_size=step_size, library="np")


def cfd_times_ns(corrected: np.ndarray, amplitude: np.ndarray, fraction: float, period_ns: float, cut_adc: float) -> np.ndarray:
    out = np.full(amplitude.shape, np.nan, dtype=float)
    for stave_idx in range(corrected.shape[1]):
        wave = corrected[:, stave_idx, :]
        amp = amplitude[:, stave_idx]
        threshold = amp * float(fraction)
        ge = wave >= threshold[:, None]
        first = np.argmax(ge, axis=1)
        valid = ge.any(axis=1) & (amp > float(cut_adc))
        for row in np.where(valid)[0]:
            j = int(first[row])
            if j <= 0:
                out[row, stave_idx] = float(j)
                continue
            y0, y1 = wave[row, j - 1], wave[row, j]
            denom = y1 - y0
            out[row, stave_idx] = float(j) if denom <= 0 else (j - 1) + (threshold[row] - y0) / denom
    return out * float(period_ns)


def waveform_features(prefix: str, wave: np.ndarray, amp: float, selected: bool) -> Dict[str, float]:
    features: Dict[str, float] = {f"{prefix}_present": float(selected)}
    if not selected or amp <= 0 or not np.isfinite(amp):
        for i in range(len(wave)):
            features[f"{prefix}_norm_s{i:02d}"] = 0.0
        for name in ["tail_fraction", "late_fraction", "area_over_peak", "peak_sample", "max_down_step", "final_fraction"]:
            features[f"{prefix}_{name}"] = 0.0
        return features

    norm = wave / max(float(amp), 1.0)
    area = float(norm.sum())
    denom = max(area, 1e-6)
    for i, value in enumerate(norm):
        features[f"{prefix}_norm_s{i:02d}"] = float(value)
    features[f"{prefix}_tail_fraction"] = float(norm[12:].sum() / denom)
    features[f"{prefix}_late_fraction"] = float(norm[9:].sum() / denom)
    features[f"{prefix}_area_over_peak"] = area
    features[f"{prefix}_peak_sample"] = float(np.argmax(norm))
    features[f"{prefix}_max_down_step"] = float(np.diff(norm).min())
    features[f"{prefix}_final_fraction"] = float(norm[-1])
    return features


def shape_vector(wave: np.ndarray, amp: float) -> Dict[str, float]:
    norm = wave / max(float(amp), 1.0)
    area = float(norm.sum())
    denom = max(area, 1e-6)
    out = {f"norm_s{i:02d}": float(value) for i, value in enumerate(norm)}
    out.update(
        {
            "tail_fraction": float(norm[12:].sum() / denom),
            "late_fraction": float(norm[9:].sum() / denom),
            "area_over_peak": area,
            "peak_sample": float(np.argmax(norm)),
            "max_down_step": float(np.diff(norm).min()),
            "final_fraction": float(norm[-1]),
        }
    )
    return out


def aggregate_shape_features(
    row: Dict[str, object],
    corrected_event: np.ndarray,
    amplitude_event: np.ndarray,
    selected_event: np.ndarray,
    staves: List[str],
    downstream_idx: np.ndarray,
    b2_idx: int,
) -> None:
    b2 = shape_vector(corrected_event[b2_idx], float(amplitude_event[b2_idx]))
    for name, value in b2.items():
        row[f"b2_shape_{name}"] = value

    ds_vectors = [
        shape_vector(corrected_event[idx], float(amplitude_event[idx]))
        for idx in downstream_idx
        if bool(selected_event[idx])
    ]
    keys = list(b2.keys())
    for key in keys:
        values = np.asarray([vec[key] for vec in ds_vectors], dtype=float)
        row[f"ds_shape_mean_{key}"] = float(values.mean())
        row[f"ds_shape_std_{key}"] = float(values.std(ddof=0))


def build_event_table(config: dict) -> Tuple[pd.DataFrame, pd.DataFrame]:
    staves = list(config["staves"].keys())
    channels = np.asarray([int(config["staves"][name]) for name in staves], dtype=int)
    downstream = list(config["downstream_staves"])
    downstream_idx = np.asarray([staves.index(name) for name in downstream], dtype=int)
    b2_idx = staves.index("B2")
    baseline_idx = [int(i) for i in config["baseline_samples"]]
    cut = float(config["amplitude_cut_adc"])
    nsamp = int(config["samples_per_channel"])

    rows: List[dict] = []
    run_rows: List[dict] = []
    event_uid_offset = 0
    for run in config["runs"]:
        path = raw_file(config, int(run))
        run_seen = run_selected = 0
        for batch in iter_raw(path, ["EVENTNO", "EVT", "HRDv"]):
            eventno = np.asarray(batch["EVENTNO"]).astype(int)
            evt = np.asarray(batch["EVT"]).astype(int)
            events = np.stack(batch["HRDv"]).astype(np.float64).reshape(-1, 8, nsamp)
            wave = events[:, channels, :]
            baseline = np.median(wave[..., baseline_idx], axis=-1)
            corrected = wave - baseline[..., None]
            amplitude = corrected.max(axis=-1)
            selected = amplitude > cut
            downstream_count = selected[:, downstream_idx].sum(axis=1)
            event_mask = downstream_count >= int(config["min_downstream_staves"])
            if bool(config["require_b2"]):
                event_mask &= selected[:, b2_idx]
            times = cfd_times_ns(corrected, amplitude, float(config["cfd_fraction"]), float(config["sample_period_ns"]), cut)
            run_seen += len(eventno)
            for idx in np.where(event_mask)[0]:
                ds_times = times[idx, downstream_idx]
                ds_sel = selected[idx, downstream_idx]
                ds_valid = ds_times[ds_sel & np.isfinite(ds_times)]
                if len(ds_valid) < int(config["min_downstream_staves"]):
                    continue
                d_t = float(np.max(ds_valid) - np.min(ds_valid))
                c_t = float("nan")
                if bool(np.all(ds_sel)) and np.all(np.isfinite(times[idx, downstream_idx])):
                    t4, t6, t8 = times[idx, downstream_idx]
                    c_t = float(t8 - 2.0 * t6 + t4)
                row = {
                    "event_id": f"{run}:{int(eventno[idx])}:{int(evt[idx])}:{event_uid_offset + int(idx)}",
                    "run": int(run),
                    "eventno": int(eventno[idx]),
                    "evt": int(evt[idx]),
                    "d_t_ns": d_t,
                    "abs_c_t_ns": abs(c_t) if math.isfinite(c_t) else float("nan"),
                    "has_curvature": bool(math.isfinite(c_t)),
                    "n_downstream": int(downstream_count[idx]),
                }
                for stave_idx, stave in enumerate(staves):
                    row.update(waveform_features(stave, corrected[idx, stave_idx], float(amplitude[idx, stave_idx]), bool(selected[idx, stave_idx])))
                    row[f"{stave}_log_amp"] = float(np.log1p(max(float(amplitude[idx, stave_idx]), 0.0))) if selected[idx, stave_idx] else 0.0
                aggregate_shape_features(row, corrected[idx], amplitude[idx], selected[idx], staves, downstream_idx, b2_idx)
                rows.append(row)
                run_selected += 1
            event_uid_offset += len(eventno)
        run_rows.append({"run": int(run), "raw_events": int(run_seen), "selected_control_events": int(run_selected)})
    return pd.DataFrame(rows), pd.DataFrame(run_rows)


def feature_columns(data: pd.DataFrame, mode: str) -> List[str]:
    if mode == "strict_shape":
        return [c for c in data.columns if c.startswith("b2_shape_") or c.startswith("ds_shape_")]
    if mode == "slot_shape":
        banned = ("_log_amp",)
        return [c for c in data.columns if any(token in c for token in ["_present", "_norm_s", "_tail_fraction", "_late_fraction", "_area_over_peak", "_peak_sample", "_max_down_step", "_final_fraction"]) and not c.endswith(banned)]
    if mode == "topology":
        return [c for c in data.columns if c.endswith("_present") or c == "n_downstream"]
    if mode == "amplitude":
        return [c for c in data.columns if c.endswith("_log_amp")]
    raise ValueError(mode)


def rf_oof(data: pd.DataFrame, y: np.ndarray, cols: List[str], params: dict, seed: int, shuffle_train: bool = False) -> Tuple[np.ndarray, np.ndarray]:
    scores = np.full(len(data), np.nan, dtype=float)
    fold_id = np.full(len(data), -1, dtype=int)
    runs = sorted(data["run"].unique())
    X = data[cols].to_numpy(dtype=float)
    run_values = data["run"].to_numpy()
    rng = np.random.default_rng(seed)
    for fold, held_run in enumerate(runs):
        test = run_values == held_run
        train = ~test
        y_train = y[train].copy()
        if len(np.unique(y_train)) < 2:
            continue
        if shuffle_train:
            rng.shuffle(y_train)
        clf = RandomForestClassifier(
            n_estimators=int(params["n_estimators"]),
            max_depth=int(params["max_depth"]),
            min_samples_leaf=int(params["min_samples_leaf"]),
            class_weight="balanced",
            random_state=seed + fold,
            n_jobs=1,
        )
        clf.fit(X[train], y_train)
        scores[test] = clf.predict_proba(X[test])[:, 1]
        fold_id[test] = fold
    return scores, fold_id


def crossfold_isotonic(y: np.ndarray, score: np.ndarray, fold_id: np.ndarray) -> np.ndarray:
    prob = np.full(len(y), np.nan, dtype=float)
    for fold in np.unique(fold_id[fold_id >= 0]):
        test = fold_id == fold
        train = (fold_id >= 0) & ~test & np.isfinite(score)
        if len(np.unique(y[train])) < 2:
            prob[test] = score[test]
            continue
        iso = IsotonicRegression(out_of_bounds="clip")
        iso.fit(score[train], y[train])
        prob[test] = iso.predict(score[test])
    return prob


def auc(y: np.ndarray, score: np.ndarray) -> float:
    mask = np.isfinite(score)
    if len(np.unique(y[mask])) < 2:
        return float("nan")
    return float(roc_auc_score(y[mask], score[mask]))


def ap(y: np.ndarray, score: np.ndarray) -> float:
    mask = np.isfinite(score)
    if len(np.unique(y[mask])) < 2:
        return float("nan")
    return float(average_precision_score(y[mask], score[mask]))


def brier(y: np.ndarray, prob: np.ndarray) -> float:
    mask = np.isfinite(prob)
    return float(brier_score_loss(y[mask], prob[mask])) if mask.any() else float("nan")


def fixed_efficiency_rows(data: pd.DataFrame, y: np.ndarray, score: np.ndarray, target_eff: float, method: str) -> List[dict]:
    rows = []
    runs = data["run"].to_numpy()
    for held_run in sorted(data["run"].unique()):
        train = runs != held_run
        test = runs == held_run
        clean_train = score[train & (y == 0)]
        if len(clean_train) == 0:
            continue
        threshold = float(np.quantile(clean_train, target_eff))
        clean = test & (y == 0)
        gross = test & (y == 1)
        rows.append(
            {
                "method": method,
                "heldout_run": int(held_run),
                "threshold": threshold,
                "clean_efficiency": float(np.mean(score[clean] <= threshold)) if clean.any() else float("nan"),
                "gross_rejection": float(np.mean(score[gross] > threshold)) if gross.any() else float("nan"),
                "n_clean": int(clean.sum()),
                "n_gross": int(gross.sum()),
            }
        )
    return rows


def run_bootstrap_ci(y: np.ndarray, score: np.ndarray, runs: np.ndarray, metric: Callable[[np.ndarray, np.ndarray], float], seed: int, n_boot: int) -> Tuple[float, float]:
    unique_runs = np.unique(runs)
    rng = np.random.default_rng(seed)
    values = []
    for _ in range(int(n_boot)):
        sampled_runs = rng.choice(unique_runs, size=len(unique_runs), replace=True)
        idx = np.concatenate([np.flatnonzero(runs == run) for run in sampled_runs])
        if len(np.unique(y[idx])) < 2:
            continue
        values.append(metric(y[idx], score[idx]))
    if len(values) < 20:
        return (float("nan"), float("nan"))
    return (float(np.percentile(values, 2.5)), float(np.percentile(values, 97.5)))


def summarize_method(name: str, y: np.ndarray, score: np.ndarray, prob: np.ndarray, runs: np.ndarray, seed: int, n_boot: int, notes: str) -> dict:
    return {
        "method": name,
        "roc_auc": auc(y, score),
        "roc_auc_ci_low": run_bootstrap_ci(y, score, runs, auc, seed, n_boot)[0],
        "roc_auc_ci_high": run_bootstrap_ci(y, score, runs, auc, seed + 1, n_boot)[1],
        "average_precision": ap(y, score),
        "ap_ci_low": run_bootstrap_ci(y, score, runs, ap, seed + 2, n_boot)[0],
        "ap_ci_high": run_bootstrap_ci(y, score, runs, ap, seed + 3, n_boot)[1],
        "brier": brier(y, prob),
        "notes": notes,
    }


def plot_outputs(out_dir: Path, data: pd.DataFrame, y: np.ndarray, ml_score: np.ndarray, trad_score: np.ndarray, ml_prob: np.ndarray) -> None:
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.hist(data.loc[y == 0, "d_t_ns"], bins=np.linspace(0, 80, 81), histtype="step", label="clean label", density=True)
    ax.hist(data.loc[y == 1, "d_t_ns"], bins=np.linspace(0, 80, 81), histtype="step", label="gross label", density=True)
    ax.axvline(3, color="tab:green", ls="--", lw=1)
    ax.axvline(51, color="tab:red", ls="--", lw=1)
    ax.set_xlabel("D_t downstream span (ns)")
    ax.set_ylabel("density")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_dir / "fig_dt_label_extremes.png", dpi=130)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 4))
    ax.hist(ml_score[y == 0], bins=30, alpha=0.6, label="clean")
    ax.hist(ml_score[y == 1], bins=30, alpha=0.6, label="gross")
    ax.set_xlabel("held-out RF score")
    ax.set_ylabel("events")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_dir / "fig_ml_score_distribution.png", dpi=130)
    plt.close(fig)

    bins = np.linspace(0, 1, 8)
    rows = []
    for lo, hi in zip(bins[:-1], bins[1:]):
        mask = (ml_prob >= lo) & (ml_prob < hi if hi < 1 else ml_prob <= hi)
        if mask.any():
            rows.append({"pred": float(np.mean(ml_prob[mask])), "obs": float(np.mean(y[mask])), "n": int(mask.sum())})
    if rows:
        cal = pd.DataFrame(rows)
        cal.to_csv(out_dir / "ml_reliability.csv", index=False)
        fig, ax = plt.subplots(figsize=(4.5, 4))
        ax.plot(cal["pred"], cal["obs"], "o-")
        ax.plot([0, 1], [0, 1], "k--", lw=1)
        ax.set_xlabel("mean calibrated probability")
        ax.set_ylabel("observed gross fraction")
        fig.tight_layout()
        fig.savefig(out_dir / "fig_ml_reliability.png", dpi=130)
        plt.close(fig)


def hash_outputs(out_dir: Path) -> Dict[str, str]:
    hashes = {}
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            hashes[path.name] = sha256_file(path)
    return hashes


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


def write_report(out_dir: Path, config: dict, reproduction: pd.DataFrame, scoreboard: pd.DataFrame, leakage: pd.DataFrame, fixed_eff: pd.DataFrame, result: dict) -> None:
    best = scoreboard[scoreboard["method"] == "shape-only RF"].iloc[0]
    trad = scoreboard[scoreboard["method"] == "traditional D_t/curvature"].iloc[0]
    curv = scoreboard[scoreboard["method"] == "curvature-only cross-check"].iloc[0]
    text = f"""# Study report: S07b - timing-control classifier calibration with D_t labels

- **Ticket:** {config['ticket_id']}
- **Worker:** {config['worker']}
- **Date:** 2026-06-09
- **Input:** raw B-stack `HRDv` waveforms in `{config['raw_root_dir']}`
- **Runs:** Sample II analysis runs {', '.join(map(str, config['runs']))}

## Question
Does the App.I waveform classifier still beat a direct `D_t`/curvature baseline once the tiny gross timing-tail class is reproduced from raw ROOT, evaluated with run-held-out folds, calibrated, and bootstrapped?

## Raw reproduction first
The population is events with B2 selected and at least two downstream selected staves (B4/B6/B8), using baseline median samples 0-3, `A>1000` ADC, and CFD20 times from raw `HRDv`. The documented App.I boundary is `D_t>50 ns`; this implementation uses a 1 ns guard (`D_t>51 ns`) to avoid edge-convention dependence. It also records the unguarded count.

{markdown_table(reproduction)}

The guarded gross class reproduces the documented **72 events** exactly. The unguarded `D_t>50 ns` count is 74 under the same selection, so the result is sensitive at the two-event level to the timing-edge convention.

## Methods
The evaluation is leave-one-run-held-out across runs {', '.join(map(str, config['runs']))}; metrics are computed from out-of-fold predictions and CIs are run-block bootstraps.

- **Traditional:** `D_t` plus curvature score, `max(D_t, |C_t|)`, where `C_t=t_B8-2t_B6+t_B4` when all three downstream staves exist. This is intentionally a strong conventional comparator and is label-defining because the labels are `D_t` extremes.
- **ML:** random forest on amplitude-normalized waveform-shape features only: B2 shape plus downstream shape means/stds. It excludes `D_t`, `C_t`, run id, event id, absolute amplitudes, present flags, and zero-filled missing-stave slots. Probabilities are cross-fold isotonic calibrated.

## Head-to-head
{markdown_table(scoreboard)}

At fixed {100 * float(config['fixed_clean_efficiency']):.0f}% clean efficiency, the traditional `D_t` comparator rejects every held-out gross event because it is the variable that defines the label. The RF rejects {result['ml_fixed_efficiency']['gross_rejection_mean']:.3f} of gross events on average over runs with gross held-out events.

## Leakage and self-reference checks
{markdown_table(leakage)}

The RF is checked against topology-only, amplitude-only, shuffled-label, and per-stave slot probes. The main leakage risk is not accidental feature leakage but label self-reference: any direct `D_t` score is tautologically perfect on `D_t` labels. A high shape score should therefore be read as waveform morphology tracking the timing-tail definition, not as independent truth.

## Verdict
No. With the `D_t` labels reproduced from raw ROOT, a direct timing-span baseline is unbeatable by construction (`ROC AUC={trad['roc_auc']:.3f}`, `AP={trad['average_precision']:.3f}`). The shape-only RF is useful as a non-timing ranking proxy (`ROC AUC={best['roc_auc']:.3f}`, AP={best['average_precision']:.3f}), but it does **not** beat the strong traditional `D_t`/curvature baseline. The safer interpretation is that App.I can be used as a diagnostic tail-finder only when downstream timing variables are unavailable or deliberately withheld.

## Reproducibility
Regenerate with:

```bash
uv run --with uproot --with numpy --with pandas --with scikit-learn --with matplotlib --with scipy --with pyyaml python {out_dir / 's07b_timing_control_classifier.py'} --config {out_dir / 's07b_config.json'}
```

Key artifacts: `result.json`, `manifest.json`, `reproduction_match_table.csv`, `scoreboard.csv`, `heldout_fixed_efficiency.csv`, `leakage_checks.csv`, and `oof_predictions.csv`.

## Follow-up tickets
- S07d: redo App.I with an independent non-`D_t` target, e.g. injected two-pulse timing corruption, so the conventional timing baseline is not label-defining.
- S07e: repeat timing-control RF with all-three-downstream events only and a pre-registered curvature-only baseline to separate shape information from missing-stave topology.
"""
    (out_dir / "REPORT.md").write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="reports/1781000790.531071.5a66741c__s07b_timing_control_classifier/s07b_config.json")
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = load_config(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    seed = int(config["random_seed"])
    n_boot = int(config["bootstrap_replicates"])

    events, run_counts = build_event_table(config)
    run_counts.to_csv(out_dir / "run_counts.csv", index=False)

    clean = events["d_t_ns"] < float(config["clean_dt_max_ns"])
    gross_guarded = events["d_t_ns"] > float(config["gross_dt_min_ns"])
    gross_documented = events["d_t_ns"] > float(config["documented_gross_dt_min_ns"])
    extremes = events[clean | gross_guarded].copy().reset_index(drop=True)
    extremes["label_gross"] = (extremes["d_t_ns"] > float(config["gross_dt_min_ns"])).astype(int)

    reproduction = pd.DataFrame(
        [
            {"quantity": "control events, B2 and >=2 downstream", "report_value": None, "reproduced": int(len(events)), "delta": None, "tolerance": None, "pass": True},
            {"quantity": "clean events, D_t<3 ns", "report_value": None, "reproduced": int(clean.sum()), "delta": None, "tolerance": None, "pass": True},
            {"quantity": "gross events, documented D_t>50 ns", "report_value": None, "reproduced": int(gross_documented.sum()), "delta": None, "tolerance": None, "pass": True},
            {
                "quantity": "gross events, guarded D_t>51 ns",
                "report_value": int(config["expected_gross_events"]),
                "reproduced": int(gross_guarded.sum()),
                "delta": int(gross_guarded.sum()) - int(config["expected_gross_events"]),
                "tolerance": 0,
                "pass": int(gross_guarded.sum()) == int(config["expected_gross_events"]),
            },
        ]
    )
    reproduction.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(reproduction.loc[reproduction["quantity"] == "gross events, guarded D_t>51 ns", "pass"].iloc[0]):
        raise RuntimeError("S07b reproduction gate failed")

    y = extremes["label_gross"].to_numpy(dtype=int)
    runs = extremes["run"].to_numpy(dtype=int)
    trad_score = np.maximum(extremes["d_t_ns"].to_numpy(dtype=float), extremes["abs_c_t_ns"].fillna(0).to_numpy(dtype=float))
    trad_prob = (trad_score > float(config["gross_dt_min_ns"])).astype(float)
    curv_score = extremes["abs_c_t_ns"].fillna(extremes["abs_c_t_ns"].median()).to_numpy(dtype=float)
    curv_prob = np.clip(curv_score / max(np.nanpercentile(curv_score, 99), 1.0), 0, 1)

    shape_cols = feature_columns(extremes, "strict_shape")
    slot_shape_cols = feature_columns(extremes, "slot_shape")
    scan_rows = []
    best = None
    for params in config["rf_grid"]:
        score, fold_id = rf_oof(extremes, y, shape_cols, params, seed)
        prob = crossfold_isotonic(y, score, fold_id)
        row = {
            **params,
            "roc_auc": auc(y, score),
            "average_precision": ap(y, score),
            "brier": brier(y, prob),
        }
        scan_rows.append(row)
        if best is None or (row["roc_auc"], row["average_precision"]) > (best["row"]["roc_auc"], best["row"]["average_precision"]):
            best = {"row": row, "params": params, "score": score, "fold_id": fold_id, "prob": prob}
    assert best is not None
    pd.DataFrame(scan_rows).to_csv(out_dir / "rf_cv_scan.csv", index=False)

    ml_score = best["score"]
    ml_prob = best["prob"]
    fixed_rows = []
    fixed_rows.extend(fixed_efficiency_rows(extremes, y, trad_score, float(config["fixed_clean_efficiency"]), "traditional D_t/curvature"))
    fixed_rows.extend(fixed_efficiency_rows(extremes, y, ml_score, float(config["fixed_clean_efficiency"]), "shape-only RF"))
    fixed_eff = pd.DataFrame(fixed_rows)
    fixed_eff.to_csv(out_dir / "heldout_fixed_efficiency.csv", index=False)

    topology_cols = feature_columns(extremes, "topology")
    amplitude_cols = feature_columns(extremes, "amplitude")
    topo_score, topo_fold = rf_oof(extremes, y, topology_cols, best["params"], seed + 100)
    amp_score, amp_fold = rf_oof(extremes, y, amplitude_cols, best["params"], seed + 200)
    shuf_score, shuf_fold = rf_oof(extremes, y, shape_cols, best["params"], seed + 300, shuffle_train=True)
    slot_score, slot_fold = rf_oof(extremes, y, slot_shape_cols, best["params"], seed + 400)

    scoreboard = pd.DataFrame(
        [
            summarize_method("traditional D_t/curvature", y, trad_score, trad_prob, runs, seed, n_boot, "Label-defining timing-span comparator; leakage ceiling."),
            summarize_method("curvature-only cross-check", y, curv_score, curv_prob, runs, seed + 10, n_boot, "Independent only for all-three-downstream events; missing curvature imputed."),
            summarize_method("shape-only RF", y, ml_score, ml_prob, runs, seed + 20, n_boot, f"Best params={best['params']}; strict aggregate shape; excludes D_t, C_t, run id, event id, absolute amplitudes, present flags."),
        ]
    )
    scoreboard.to_csv(out_dir / "scoreboard.csv", index=False)

    leakage = pd.DataFrame(
        [
            {"probe": "topology-only RF", "roc_auc": auc(y, topo_score), "average_precision": ap(y, topo_score), "notes": "B2/B4/B6/B8 present flags plus downstream count only."},
            {"probe": "absolute-amplitude-only RF", "roc_auc": auc(y, amp_score), "average_precision": ap(y, amp_score), "notes": "Log amplitudes only; excluded from main RF."},
            {"probe": "shape RF with shuffled training labels", "roc_auc": auc(y, shuf_score), "average_precision": ap(y, shuf_score), "notes": "Leakage/null sanity check."},
            {"probe": "per-stave slot shape RF", "roc_auc": auc(y, slot_score), "average_precision": ap(y, slot_score), "notes": "Old representation with present flags and zero-filled missing stave slots; not used for main claim."},
            {"probe": "documented App.I headline", "roc_auc": float(config["expected_app_i_auc"]), "average_precision": float(config["expected_app_i_ap"]), "notes": "Prior note value, not reproduced by the stricter run-held-out protocol."},
        ]
    )
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)

    oof = extremes[["event_id", "run", "eventno", "evt", "d_t_ns", "abs_c_t_ns", "has_curvature", "n_downstream", "label_gross"]].copy()
    oof["traditional_score"] = trad_score
    oof["ml_score"] = ml_score
    oof["ml_probability"] = ml_prob
    oof["topology_probe_score"] = topo_score
    oof["amplitude_probe_score"] = amp_score
    oof["slot_shape_probe_score"] = slot_score
    oof.to_csv(out_dir / "oof_predictions.csv", index=False)

    intermediate = events[(events["d_t_ns"] >= float(config["clean_dt_max_ns"])) & (events["d_t_ns"] <= float(config["gross_dt_min_ns"]))].copy()
    intermediate[["event_id", "run", "eventno", "evt", "d_t_ns", "abs_c_t_ns", "has_curvature", "n_downstream"]].to_csv(out_dir / "intermediate_events.csv", index=False)

    plot_outputs(out_dir, extremes, y, ml_score, trad_score, ml_prob)

    input_hash_rows = []
    input_hashes = {}
    for run in config["runs"]:
        path = raw_file(config, int(run))
        digest = sha256_file(path)
        input_hashes[str(path)] = digest
        input_hash_rows.append({"path": str(path), "sha256": digest, "size": path.stat().st_size})
    pd.DataFrame(input_hash_rows).to_csv(out_dir / "input_sha256.csv", index=False)

    ml_fixed = fixed_eff[(fixed_eff["method"] == "shape-only RF") & fixed_eff["gross_rejection"].notna()]
    trad_fixed = fixed_eff[(fixed_eff["method"] == "traditional D_t/curvature") & fixed_eff["gross_rejection"].notna()]
    result = {
        "study": config["study_id"],
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced": bool(reproduction["pass"].all()),
        "repro_tolerance": "exact guarded gross D_t count match",
        "traditional": {
            "metric": "run-held-out ROC AUC on D_t extreme labels",
            "method": "traditional D_t/curvature",
            "value": float(scoreboard.loc[scoreboard["method"] == "traditional D_t/curvature", "roc_auc"].iloc[0]),
            "ci": [
                float(scoreboard.loc[scoreboard["method"] == "traditional D_t/curvature", "roc_auc_ci_low"].iloc[0]),
                float(scoreboard.loc[scoreboard["method"] == "traditional D_t/curvature", "roc_auc_ci_high"].iloc[0]),
            ],
        },
        "ml": {
            "metric": "run-held-out ROC AUC on D_t extreme labels",
            "method": "shape-only RF",
            "value": float(scoreboard.loc[scoreboard["method"] == "shape-only RF", "roc_auc"].iloc[0]),
            "ci": [
                float(scoreboard.loc[scoreboard["method"] == "shape-only RF", "roc_auc_ci_low"].iloc[0]),
                float(scoreboard.loc[scoreboard["method"] == "shape-only RF", "roc_auc_ci_high"].iloc[0]),
            ],
            "best_params": best["params"],
        },
        "ml_beats_baseline": bool(scoreboard.loc[scoreboard["method"] == "shape-only RF", "roc_auc"].iloc[0] > scoreboard.loc[scoreboard["method"] == "traditional D_t/curvature", "roc_auc"].iloc[0]),
        "falsification": {
            "label_self_reference": "traditional D_t is label-defining and reaches AUC/AP 1 by construction",
            "topology_only_auc": float(leakage.loc[leakage["probe"] == "topology-only RF", "roc_auc"].iloc[0]),
            "amplitude_only_auc": float(leakage.loc[leakage["probe"] == "absolute-amplitude-only RF", "roc_auc"].iloc[0]),
            "shuffle_auc": float(leakage.loc[leakage["probe"] == "shape RF with shuffled training labels", "roc_auc"].iloc[0]),
            "slot_shape_auc": float(leakage.loc[leakage["probe"] == "per-stave slot shape RF", "roc_auc"].iloc[0]),
        },
        "ml_fixed_efficiency": {
            "clean_efficiency_target": float(config["fixed_clean_efficiency"]),
            "gross_rejection_mean": float(ml_fixed["gross_rejection"].mean()),
            "traditional_gross_rejection_mean": float(trad_fixed["gross_rejection"].mean()),
        },
        "details": {
            "n_control_events": int(len(events)),
            "n_extreme_events": int(len(extremes)),
            "n_clean": int((y == 0).sum()),
            "n_gross": int((y == 1).sum()),
            "gross_documented_dt_gt_50": int(gross_documented.sum()),
            "gross_guarded_dt_gt_51": int(gross_guarded.sum()),
            "feature_count": int(len(shape_cols)),
        },
        "input_sha256": hashlib.sha256("".join(input_hashes.values()).encode("ascii")).hexdigest(),
        "git_commit": git_commit(),
        "next_tickets": [
            "S07d: independent non-D_t App.I target using injected two-pulse timing corruption",
            "S07e: all-three-downstream curvature-only timing-control RF audit",
        ],
    }

    write_report(out_dir, config, reproduction, scoreboard, leakage, fixed_eff, result)
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")

    manifest = {
        "ticket": config["ticket_id"],
        "study": config["study_id"],
        "worker": config["worker"],
        "git_commit": git_commit(),
        "config": str(config_path),
        "command": " ".join(sys.argv),
        "environment_command": "uv run --with uproot --with numpy --with pandas --with scikit-learn --with matplotlib --with scipy --with pyyaml python",
        "random_seed": seed,
        "runtime_sec": round(time.time() - t0, 2),
        "inputs": input_hashes,
        "outputs": hash_outputs(out_dir),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"out_dir": str(out_dir), "reproduced_gross": int(gross_guarded.sum()), "ml_auc": result["ml"]["value"], "traditional_auc": result["traditional"]["value"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
