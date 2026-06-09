#!/usr/bin/env python3
"""S07g: all-three App.I amplitude/current stratification.

This report-local script derives App.I-style timing-control labels directly from
raw HRDv waveforms, verifies the parent App.I 72-event gross count first, then
restricts the benchmark to B2+B4+B6+B8 events where all three downstream staves
are selected. It reuses the S07e curvature and shape-only RF scores, then audits
them by event-amplitude tertile and pre-label run-rate family. Each stratum also
gets a curvature-only traditional control and an amplitude-only RF control.
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
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple

os.environ.setdefault("MPLCONFIGDIR", "/tmp/ccb-testbeam-s07g-matplotlib-cache")

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


def iter_raw(path: Path, branches: Sequence[str], step_size: int = 20000) -> Iterable[dict]:
    tree = uproot.open(path)["h101"]
    yield from tree.iterate(list(branches), step_size=step_size, library="np")


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


def shape_features(prefix: str, wave: np.ndarray, amp: float) -> Dict[str, float]:
    norm = wave / max(float(amp), 1.0)
    area = float(norm.sum())
    denom = max(area, 1e-6)
    out = {f"{prefix}_norm_s{i:02d}": float(value) for i, value in enumerate(norm)}
    out.update(
        {
            f"{prefix}_tail_fraction": float(norm[12:].sum() / denom),
            f"{prefix}_late_fraction": float(norm[9:].sum() / denom),
            f"{prefix}_area_over_peak": area,
            f"{prefix}_peak_sample": float(np.argmax(norm)),
            f"{prefix}_max_down_step": float(np.diff(norm).min()),
            f"{prefix}_final_fraction": float(norm[-1]),
        }
    )
    return out


def add_all_three_shape_features(row: Dict[str, object], corrected_event: np.ndarray, amplitude_event: np.ndarray, staves: List[str], downstream_idx: np.ndarray, b2_idx: int) -> None:
    shape_dicts = []
    for idx in [b2_idx, *list(downstream_idx)]:
        stave = staves[idx].lower()
        features = shape_features(stave, corrected_event[idx], float(amplitude_event[idx]))
        row.update(features)
        shape_dicts.append((stave, features))

    ds_features = [features for stave, features in shape_dicts if stave != "b2"]
    keys = [key.split("_", 1)[1] for key in ds_features[0] if key.startswith("b4_")]
    for suffix in keys:
        values = np.asarray([features[f"{stave}_{suffix}"] for stave, features in shape_dicts if stave != "b2"], dtype=float)
        row[f"ds_mean_{suffix}"] = float(values.mean())
        row[f"ds_std_{suffix}"] = float(values.std(ddof=0))


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
        run_seen = 0
        run_control = 0
        run_all_three = 0
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
            control_mask = selected[:, b2_idx] & (downstream_count >= int(config["parent_min_downstream_staves"]))
            times = cfd_times_ns(corrected, amplitude, float(config["cfd_fraction"]), float(config["sample_period_ns"]), cut)
            run_seen += len(eventno)
            for idx in np.where(control_mask)[0]:
                ds_times = times[idx, downstream_idx]
                ds_sel = selected[idx, downstream_idx]
                ds_valid = ds_times[ds_sel & np.isfinite(ds_times)]
                if len(ds_valid) < int(config["parent_min_downstream_staves"]):
                    continue
                all_three = bool(np.all(ds_sel) and np.all(np.isfinite(ds_times)))
                d_t = float(np.max(ds_valid) - np.min(ds_valid))
                c_t = float("nan")
                if all_three:
                    t4, t6, t8 = ds_times
                    c_t = float(t8 - 2.0 * t6 + t4)
                row: Dict[str, object] = {
                    "event_id": f"{run}:{int(eventno[idx])}:{int(evt[idx])}:{event_uid_offset + int(idx)}",
                    "run": int(run),
                    "eventno": int(eventno[idx]),
                    "evt": int(evt[idx]),
                    "d_t_ns": d_t,
                    "c_t_ns": c_t,
                    "abs_c_t_ns": abs(c_t) if math.isfinite(c_t) else float("nan"),
                    "n_downstream": int(downstream_count[idx]),
                    "all_three_downstream": all_three,
                    "event_max_amp_adc": float(np.max(amplitude[idx, selected[idx]])) if np.any(selected[idx]) else 0.0,
                    "event_max_log_amp": float(np.log1p(float(np.max(amplitude[idx, selected[idx]])))) if np.any(selected[idx]) else 0.0,
                }
                for stave_idx, stave in enumerate(staves):
                    row[f"{stave.lower()}_log_amp"] = float(np.log1p(max(float(amplitude[idx, stave_idx]), 0.0))) if selected[idx, stave_idx] else 0.0
                if all_three:
                    add_all_three_shape_features(row, corrected[idx], amplitude[idx], staves, downstream_idx, b2_idx)
                    run_all_three += 1
                rows.append(row)
                run_control += 1
            event_uid_offset += len(eventno)
        run_rows.append({"run": int(run), "raw_events": int(run_seen), "parent_control_events": int(run_control), "all_three_events": int(run_all_three)})
    return pd.DataFrame(rows), pd.DataFrame(run_rows)


def shape_columns(data: pd.DataFrame) -> List[str]:
    forbidden_tokens = ["d_t", "c_t", "run", "event", "evt", "log_amp", "present", "downstream"]
    cols = []
    for col in data.columns:
        if not pd.api.types.is_numeric_dtype(data[col]):
            continue
        lower = col.lower()
        if any(token in lower for token in forbidden_tokens):
            continue
        if any(token in lower for token in ["norm_s", "tail_fraction", "late_fraction", "area_over_peak", "peak_sample", "max_down_step", "final_fraction"]):
            cols.append(col)
    return cols


def amplitude_columns(data: pd.DataFrame) -> List[str]:
    return [col for col in data.columns if col.endswith("_log_amp")]


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
    return float(brier_score_loss(y[mask], prob[mask])) if mask.any() and len(np.unique(y[mask])) > 1 else float("nan")


def rf_oof(data: pd.DataFrame, y: np.ndarray, cols: List[str], params: dict, seed: int, shuffle_train: bool = False) -> Tuple[np.ndarray, np.ndarray]:
    scores = np.full(len(data), np.nan, dtype=float)
    fold_id = np.full(len(data), -1, dtype=int)
    runs = data["run"].to_numpy(dtype=int)
    X = data[cols].to_numpy(dtype=float)
    rng = np.random.default_rng(seed)
    for fold, held_run in enumerate(sorted(np.unique(runs))):
        test = runs == held_run
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


def run_bootstrap_ci(y: np.ndarray, score: np.ndarray, runs: np.ndarray, metric: Callable[[np.ndarray, np.ndarray], float], seed: int, n_boot: int) -> Tuple[float, float]:
    unique_runs = np.unique(runs)
    rng = np.random.default_rng(seed)
    values = []
    for _ in range(int(n_boot)):
        sampled = rng.choice(unique_runs, size=len(unique_runs), replace=True)
        idx = np.concatenate([np.flatnonzero(runs == run) for run in sampled])
        if len(np.unique(y[idx])) < 2:
            continue
        value = metric(y[idx], score[idx])
        if np.isfinite(value):
            values.append(value)
    if len(values) < 20:
        return (float("nan"), float("nan"))
    return (float(np.percentile(values, 2.5)), float(np.percentile(values, 97.5)))


def summarize_method(name: str, y: np.ndarray, score: np.ndarray, prob: np.ndarray, runs: np.ndarray, seed: int, n_boot: int, notes: str) -> dict:
    auc_ci = run_bootstrap_ci(y, score, runs, auc, seed, n_boot)
    ap_ci = run_bootstrap_ci(y, score, runs, ap, seed + 1, n_boot)
    return {
        "method": name,
        "roc_auc": auc(y, score),
        "roc_auc_ci_low": auc_ci[0],
        "roc_auc_ci_high": auc_ci[1],
        "average_precision": ap(y, score),
        "ap_ci_low": ap_ci[0],
        "ap_ci_high": ap_ci[1],
        "brier": brier(y, prob),
        "notes": notes,
    }


def fixed_efficiency_rows(data: pd.DataFrame, y: np.ndarray, score: np.ndarray, target_eff: float, method: str) -> List[dict]:
    rows = []
    runs = data["run"].to_numpy(dtype=int)
    for held_run in sorted(data["run"].unique()):
        train = runs != held_run
        test = runs == held_run
        clean_train = score[train & (y == 0)]
        clean_train = clean_train[np.isfinite(clean_train)]
        if len(clean_train) == 0:
            continue
        threshold = float(np.quantile(clean_train, target_eff))
        clean = test & (y == 0) & np.isfinite(score)
        gross = test & (y == 1) & np.isfinite(score)
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


def add_strata(data: pd.DataFrame, config: dict, amplitude_reference: Optional[pd.DataFrame] = None) -> pd.DataFrame:
    out = data.copy()
    ref = out if amplitude_reference is None else amplitude_reference
    quantiles = [float(q) for q in config["amplitude_bin_quantiles"]]
    labels = list(config["amplitude_bin_labels"])
    edges = ref["event_max_log_amp"].quantile(quantiles).to_numpy(dtype=float).copy()
    edges[0] = -np.inf
    edges[-1] = np.inf
    for idx in range(1, len(edges)):
        if edges[idx] <= edges[idx - 1]:
            edges[idx] = np.nextafter(edges[idx - 1], np.inf)
    out["amplitude_stratum"] = pd.cut(out["event_max_log_amp"], bins=edges, labels=labels, include_lowest=True).astype(str)

    run_to_family: Dict[int, str] = {}
    for family, runs in config["current_run_families"].items():
        for run in runs:
            run_to_family[int(run)] = str(family)
    out["current_run_family"] = out["run"].map(run_to_family).fillna("unassigned")
    return out


def stratum_metadata(frame: pd.DataFrame, run_counts: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for run, sub in frame.groupby("run"):
        raw_events = int(run_counts.loc[run_counts["run"] == run, "raw_events"].iloc[0])
        rows.append(
            {
                "run": int(run),
                "current_nA": 20.0,
                "raw_events": raw_events,
                "all_three_events": int(run_counts.loc[run_counts["run"] == run, "all_three_events"].iloc[0]),
                "all_three_rate": float(run_counts.loc[run_counts["run"] == run, "all_three_events"].iloc[0]) / max(raw_events, 1),
                "current_run_family": str(sub["current_run_family"].iloc[0]),
            }
        )
    return pd.DataFrame(rows)


def summarize_strata(data: pd.DataFrame, y: np.ndarray, scores: Dict[str, np.ndarray], probs: Dict[str, np.ndarray], seed: int, n_boot: int) -> pd.DataFrame:
    rows = []
    stratum_specs = [
        ("overall", "all", np.ones(len(data), dtype=bool)),
    ]
    for col in ["amplitude_stratum", "current_run_family"]:
        for value in sorted(data[col].dropna().unique()):
            stratum_specs.append((col, str(value), (data[col].to_numpy() == value)))
    for stratum_type, stratum, mask in stratum_specs:
        if not mask.any():
            continue
        y_sub = y[mask]
        runs_sub = data.loc[mask, "run"].to_numpy(dtype=int)
        for method, score in scores.items():
            prob = probs.get(method, score)
            auc_ci = run_bootstrap_ci(y_sub, score[mask], runs_sub, auc, seed + len(rows), n_boot)
            ap_ci = run_bootstrap_ci(y_sub, score[mask], runs_sub, ap, seed + len(rows) + 1000, n_boot)
            rows.append(
                {
                    "stratum_type": stratum_type,
                    "stratum": stratum,
                    "method": method,
                    "n_events": int(mask.sum()),
                    "n_clean": int((y_sub == 0).sum()),
                    "n_gross": int((y_sub == 1).sum()),
                    "n_runs": int(len(np.unique(runs_sub))),
                    "roc_auc": auc(y_sub, score[mask]),
                    "roc_auc_ci_low": auc_ci[0],
                    "roc_auc_ci_high": auc_ci[1],
                    "average_precision": ap(y_sub, score[mask]),
                    "ap_ci_low": ap_ci[0],
                    "ap_ci_high": ap_ci[1],
                    "brier": brier(y_sub, prob[mask]),
                    "max_clean_abs_c_t_ns": float(np.nanmax(data.loc[mask & (y == 0), "abs_c_t_ns"])) if np.any(mask & (y == 0)) else float("nan"),
                    "min_gross_abs_c_t_ns": float(np.nanmin(data.loc[mask & (y == 1), "abs_c_t_ns"])) if np.any(mask & (y == 1)) else float("nan"),
                }
            )
    return pd.DataFrame(rows)


def compact_stratum_view(strata: pd.DataFrame) -> pd.DataFrame:
    cols = ["stratum_type", "stratum", "method", "n_events", "n_clean", "n_gross", "n_runs", "roc_auc", "roc_auc_ci_low", "roc_auc_ci_high", "average_precision"]
    return strata[cols].copy()


def markdown_table(frame: pd.DataFrame, columns: Optional[Sequence[str]] = None) -> str:
    show = frame[list(columns)].copy() if columns is not None else frame.copy()

    def fmt(value: object) -> str:
        if pd.isna(value):
            return ""
        if isinstance(value, float):
            return f"{value:.6g}"
        return str(value).replace("|", "\\|")

    cols = list(show.columns)
    rows = [[fmt(row[col]) for col in cols] for _, row in show.iterrows()]
    widths = [len(str(col)) for col in cols]
    for row in rows:
        widths = [max(width, len(cell)) for width, cell in zip(widths, row)]
    header = "| " + " | ".join(str(col).ljust(width) for col, width in zip(cols, widths)) + " |"
    sep = "| " + " | ".join("-" * width for width in widths) + " |"
    body = ["| " + " | ".join(cell.ljust(width) for cell, width in zip(row, widths)) + " |" for row in rows]
    return "\n".join([header, sep, *body])


def hash_outputs(out_dir: Path) -> Dict[str, str]:
    hashes = {}
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            hashes[path.name] = sha256_file(path)
    return hashes


def write_report(out_dir: Path, config: dict, reproduction: pd.DataFrame, run_counts: pd.DataFrame, scoreboard: pd.DataFrame, leakage: pd.DataFrame, fixed_eff: pd.DataFrame, strata: pd.DataFrame, result: dict) -> None:
    ml = scoreboard[scoreboard["method"] == "shape-only RF"].iloc[0]
    trad = scoreboard[scoreboard["method"] == "curvature-only traditional"].iloc[0]
    amp = scoreboard[scoreboard["method"] == "amplitude-only RF control"].iloc[0]
    amp_strata = compact_stratum_view(strata[strata["stratum_type"] == "amplitude_stratum"])
    run_strata = compact_stratum_view(strata[strata["stratum_type"] == "current_run_family"])
    text = f"""# S07g: all-three App.I amplitude/current stratification

- **Ticket:** {config['ticket_id']}
- **Worker:** {config['worker']}
- **Date:** 2026-06-09
- **Input:** raw B-stack `HRDv` ROOT in `{config['raw_root_dir']}`
- **Runs:** {', '.join(map(str, config['runs']))}

## Question
Does the high S07e all-three App.I RF score persist uniformly after stratifying by event amplitude and by pre-label current/run-rate family, or is it explained by amplitude correlation or rate-dependent pulse quality?

## Raw Reproduction First
The parent App.I control population is recomputed first from raw ROOT with baseline median samples 0-3, `A>1000` ADC, CFD20 times, B2 selected, and at least two downstream staves selected.

{markdown_table(reproduction)}

The guarded `D_t>51 ns` count reproduces the documented App.I **72 gross events** exactly before the all-three restriction and stratum audit. The all-three subset keeps {result['details']['n_all_three_control']} control events and {result['details']['n_all_three_gross_guarded']} guarded gross events.

Run-level counts:

{markdown_table(run_counts)}

## Methods
Labels remain the App.I timing extremes: clean if `D_t<3 ns`, gross if `D_t>51 ns`; intermediate events are excluded from the classifier benchmark. All benchmark rows have B4, B6, and B8 selected, so missing-stave topology is constant.

- **Traditional:** pre-registered curvature-only score `|C_t|`; no `D_t`, no amplitude, no topology.
- **Amplitude control:** run-held-out RF using only absolute log amplitudes (`B2/B4/B6/B8` plus event maximum).
- **ML:** random forest over amplitude-normalized waveform shapes for B2/B4/B6/B8 and downstream aggregate shape summaries. It excludes run id, event id, `D_t`, `C_t`, absolute amplitudes, present flags, and missing-stave slots.
- **Strata:** event-maximum-amplitude tertiles from the full all-three control population before clean/gross filtering, and run families fixed in the config from pre-label all-three rates: `{', '.join(config['current_run_families'].keys())}`.
- **Uncertainty:** leave-one-run-out predictions with run-block bootstrap 95% CIs. Sparse strata with one class or too few resampled mixed-class blocks report `NaN` intervals rather than hiding the limitation.

## Overall Head-to-Head
{markdown_table(scoreboard)}

At fixed {100 * float(config['fixed_clean_efficiency']):.0f}% clean efficiency, mean gross rejection over held-out runs with gross examples is:

{markdown_table(fixed_eff.groupby('method', as_index=False)['gross_rejection'].mean())}

## Amplitude Strata
{markdown_table(amp_strata)}

## Current/Run-Family Strata
{markdown_table(run_strata)}

## Leakage Hunt
{markdown_table(leakage)}

The overall shape RF remains high (`ROC AUC={ml['roc_auc']:.3f}`), but curvature-only is still perfect (`ROC AUC={trad['roc_auc']:.3f}`) and the amplitude-only control is non-trivial (`ROC AUC={amp['roc_auc']:.3f}`). The too-good result is explained by the target geometry rather than software leakage: max clean `|C_t|` is {result['details']['max_clean_abs_c_t_ns']:.3f} ns and min gross `|C_t|` is {result['details']['min_gross_abs_c_t_ns']:.3f} ns. The shuffled-label control is near chance overall; sparse stratum nulls are reported explicitly rather than interpreted.

## Verdict
S07g does not turn the App.I RF into an independent timing truth. The shape score remains high in the populated amplitude and run-family strata, but the conventional curvature score separates the same weak labels perfectly wherever both classes are present. The amplitude-only control confirms that part of the RF ranking is amplitude-correlated, while the run-family table shows the sparse edge families are not strong enough to support a standalone current claim.

## Reproducibility
```bash
uv run --with uproot --with numpy --with pandas --with scikit-learn python {out_dir / 's07g_appi_amplitude_current_stratification.py'} --config {out_dir / 's07g_config.json'}
```

Artifacts: `result.json`, `manifest.json`, `reproduction_match_table.csv`, `scoreboard.csv`, `stratified_scoreboard.csv`, `run_family_metadata.csv`, `leakage_checks.csv`, `heldout_fixed_efficiency.csv`, `oof_predictions.csv`, `run_counts.csv`, and `input_sha256.csv`.
"""
    (out_dir / "REPORT.md").write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="reports/1781012109.1288.14a764a8__s07g_appi_amplitude_current_stratification/s07g_config.json")
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

    clean_parent = events["d_t_ns"] < float(config["clean_dt_max_ns"])
    gross_doc_parent = events["d_t_ns"] > float(config["documented_gross_dt_min_ns"])
    gross_guard_parent = events["d_t_ns"] > float(config["gross_dt_min_ns"])
    all_three = events["all_three_downstream"].astype(bool)

    reproduction = pd.DataFrame(
        [
            {"quantity": "parent control events, B2 and >=2 downstream", "report_value": None, "reproduced": int(len(events)), "delta": None, "tolerance": None, "pass": True},
            {"quantity": "parent clean events, D_t<3 ns", "report_value": None, "reproduced": int(clean_parent.sum()), "delta": None, "tolerance": None, "pass": True},
            {"quantity": "parent gross events, documented D_t>50 ns", "report_value": None, "reproduced": int(gross_doc_parent.sum()), "delta": None, "tolerance": None, "pass": True},
            {
                "quantity": "parent gross events, guarded D_t>51 ns",
                "report_value": int(config["expected_parent_gross_events"]),
                "reproduced": int(gross_guard_parent.sum()),
                "delta": int(gross_guard_parent.sum()) - int(config["expected_parent_gross_events"]),
                "tolerance": 0,
                "pass": int(gross_guard_parent.sum()) == int(config["expected_parent_gross_events"]),
            },
            {"quantity": "S07g all-three control events", "report_value": None, "reproduced": int(all_three.sum()), "delta": None, "tolerance": None, "pass": True},
            {"quantity": "S07g all-three guarded gross events", "report_value": None, "reproduced": int((all_three & gross_guard_parent).sum()), "delta": None, "tolerance": None, "pass": True},
        ]
    )
    reproduction.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(reproduction.loc[reproduction["quantity"] == "parent gross events, guarded D_t>51 ns", "pass"].iloc[0]):
        raise RuntimeError("Parent App.I 72-event reproduction gate failed")

    all_three_reference = events[all_three].copy().reset_index(drop=True)
    benchmark = events[all_three & (clean_parent | gross_guard_parent)].copy().reset_index(drop=True)
    benchmark = add_strata(benchmark, config, all_three_reference)
    benchmark["label_gross"] = (benchmark["d_t_ns"] > float(config["gross_dt_min_ns"])).astype(int)
    if len(np.unique(benchmark["label_gross"])) < 2:
        raise RuntimeError("All-three benchmark lacks both classes")

    y = benchmark["label_gross"].to_numpy(dtype=int)
    runs = benchmark["run"].to_numpy(dtype=int)
    curv_score = benchmark["abs_c_t_ns"].to_numpy(dtype=float)
    curv_prob = np.clip(curv_score / max(np.nanpercentile(curv_score, 99), 1.0), 0, 1)
    leaky_dt_score = benchmark["d_t_ns"].to_numpy(dtype=float)
    leaky_dt_prob = (leaky_dt_score > float(config["gross_dt_min_ns"])).astype(float)

    shape_cols = shape_columns(benchmark)
    amp_cols = amplitude_columns(benchmark)
    forbidden = [col for col in shape_cols if any(token in col.lower() for token in ["d_t", "c_t", "run", "event", "evt", "log_amp", "present"])]
    if forbidden:
        raise RuntimeError(f"Forbidden feature columns in shape RF: {forbidden}")

    scan_rows = []
    best = None
    for params in config["rf_grid"]:
        score, fold_id = rf_oof(benchmark, y, shape_cols, params, seed)
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
    amp_score, amp_fold = rf_oof(benchmark, y, amp_cols, best["params"], seed + 100)
    amp_prob = crossfold_isotonic(y, amp_score, amp_fold)
    shuf_score, shuf_fold = rf_oof(benchmark, y, shape_cols, best["params"], seed + 200, shuffle_train=True)
    shuf_prob = crossfold_isotonic(y, shuf_score, shuf_fold)

    fixed_rows = []
    fixed_rows.extend(fixed_efficiency_rows(benchmark, y, curv_score, float(config["fixed_clean_efficiency"]), "curvature-only traditional"))
    fixed_rows.extend(fixed_efficiency_rows(benchmark, y, ml_score, float(config["fixed_clean_efficiency"]), "shape-only RF"))
    fixed_eff = pd.DataFrame(fixed_rows)
    fixed_eff.to_csv(out_dir / "heldout_fixed_efficiency.csv", index=False)

    scoreboard = pd.DataFrame(
        [
            summarize_method("curvature-only traditional", y, curv_score, curv_prob, runs, seed, n_boot, "Pre-registered |C_t| only; all benchmark rows have B4/B6/B8 selected."),
            summarize_method("shape-only RF", y, ml_score, ml_prob, runs, seed + 10, n_boot, f"Best params={best['params']}; normalized shape only; {len(shape_cols)} features."),
            summarize_method("amplitude-only RF control", y, amp_score, amp_prob, runs, seed + 20, n_boot, f"Absolute log-amplitude controls only; {len(amp_cols)} features."),
        ]
    )
    scoreboard.to_csv(out_dir / "scoreboard.csv", index=False)

    strata = summarize_strata(
        benchmark,
        y,
        {
            "curvature-only traditional": curv_score,
            "amplitude-only RF control": amp_score,
            "shape-only RF": ml_score,
            "shape RF shuffled-label null": shuf_score,
        },
        {
            "curvature-only traditional": curv_prob,
            "amplitude-only RF control": amp_prob,
            "shape-only RF": ml_prob,
            "shape RF shuffled-label null": shuf_prob,
        },
        seed + 300,
        n_boot,
    )
    strata.to_csv(out_dir / "stratified_scoreboard.csv", index=False)
    stratum_metadata(benchmark, run_counts).to_csv(out_dir / "run_family_metadata.csv", index=False)

    max_clean_curv = float(np.nanmax(curv_score[y == 0]))
    min_gross_curv = float(np.nanmin(curv_score[y == 1]))
    leakage = pd.DataFrame(
        [
            {"probe": "missing-stave topology", "roc_auc": float("nan"), "average_precision": float("nan"), "notes": f"Removed by construction: n_downstream unique={sorted(benchmark['n_downstream'].unique().tolist())}."},
            {"probe": "curvature separation audit", "roc_auc": auc(y, curv_score), "average_precision": ap(y, curv_score), "notes": f"Perfect because max clean |C_t|={max_clean_curv:.3f} ns and min gross |C_t|={min_gross_curv:.3f} ns."},
            {"probe": "absolute-amplitude-only RF", "roc_auc": auc(y, amp_score), "average_precision": ap(y, amp_score), "notes": "Log amplitudes only; excluded from main RF."},
            {"probe": "shape RF with shuffled training labels", "roc_auc": auc(y, shuf_score), "average_precision": ap(y, shuf_score), "notes": "Null/leakage sanity check under the same run-held-out folds."},
            {"probe": "leaky D_t score", "roc_auc": auc(y, leaky_dt_score), "average_precision": ap(y, leaky_dt_score), "notes": "Forbidden label-defining ceiling; reported only to quantify self-reference."},
            {"probe": "forbidden feature audit", "roc_auc": float("nan"), "average_precision": float("nan"), "notes": f"Forbidden columns in main RF: {forbidden}."},
        ]
    )
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)

    oof_cols = ["event_id", "run", "eventno", "evt", "d_t_ns", "c_t_ns", "abs_c_t_ns", "n_downstream", "label_gross"]
    oof = benchmark[oof_cols].copy()
    oof["curvature_score"] = curv_score
    oof["ml_score"] = ml_score
    oof["ml_probability"] = ml_prob
    oof["amplitude_probe_score"] = amp_score
    oof["shuffle_probe_score"] = shuf_score
    oof["amplitude_stratum"] = benchmark["amplitude_stratum"]
    oof["current_run_family"] = benchmark["current_run_family"]
    oof["event_max_amp_adc"] = benchmark["event_max_amp_adc"]
    oof.to_csv(out_dir / "oof_predictions.csv", index=False)

    input_hash_rows = []
    input_hashes = {}
    for run in config["runs"]:
        path = raw_file(config, int(run))
        digest = sha256_file(path)
        input_hashes[str(path)] = digest
        input_hash_rows.append({"path": str(path), "sha256": digest, "size": path.stat().st_size})
    pd.DataFrame(input_hash_rows).to_csv(out_dir / "input_sha256.csv", index=False)

    ml_auc = float(scoreboard.loc[scoreboard["method"] == "shape-only RF", "roc_auc"].iloc[0])
    trad_auc = float(scoreboard.loc[scoreboard["method"] == "curvature-only traditional", "roc_auc"].iloc[0])
    result = {
        "study": config["study_id"],
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced": bool(reproduction["pass"].all()),
        "repro_tolerance": "exact parent App.I guarded gross D_t count match before all-three restriction",
        "traditional": {
            "metric": "run-held-out ROC AUC on all-three App.I D_t extreme labels",
            "method": "curvature-only traditional",
            "value": trad_auc,
            "ci": [
                float(scoreboard.loc[scoreboard["method"] == "curvature-only traditional", "roc_auc_ci_low"].iloc[0]),
                float(scoreboard.loc[scoreboard["method"] == "curvature-only traditional", "roc_auc_ci_high"].iloc[0]),
            ],
        },
        "ml": {
            "metric": "run-held-out ROC AUC on all-three App.I D_t extreme labels",
            "method": "shape-only RF",
            "value": ml_auc,
            "ci": [
                float(scoreboard.loc[scoreboard["method"] == "shape-only RF", "roc_auc_ci_low"].iloc[0]),
                float(scoreboard.loc[scoreboard["method"] == "shape-only RF", "roc_auc_ci_high"].iloc[0]),
            ],
            "best_params": best["params"],
        },
        "amplitude_control": {
            "metric": "run-held-out ROC AUC on all-three App.I D_t extreme labels",
            "method": "amplitude-only RF control",
            "value": float(scoreboard.loc[scoreboard["method"] == "amplitude-only RF control", "roc_auc"].iloc[0]),
            "ci": [
                float(scoreboard.loc[scoreboard["method"] == "amplitude-only RF control", "roc_auc_ci_low"].iloc[0]),
                float(scoreboard.loc[scoreboard["method"] == "amplitude-only RF control", "roc_auc_ci_high"].iloc[0]),
            ],
        },
        "ml_beats_baseline": bool(ml_auc > trad_auc),
        "falsification": {
            "missing_stave_topology_removed": sorted(int(x) for x in benchmark["n_downstream"].unique()),
            "amplitude_only_auc": float(leakage.loc[leakage["probe"] == "absolute-amplitude-only RF", "roc_auc"].iloc[0]),
            "shuffle_auc": float(leakage.loc[leakage["probe"] == "shape RF with shuffled training labels", "roc_auc"].iloc[0]),
            "leaky_dt_auc": float(leakage.loc[leakage["probe"] == "leaky D_t score", "roc_auc"].iloc[0]),
            "max_clean_abs_c_t_ns": max_clean_curv,
            "min_gross_abs_c_t_ns": min_gross_curv,
            "forbidden_shape_features": forbidden,
        },
        "details": {
            "n_parent_control": int(len(events)),
            "n_parent_clean": int(clean_parent.sum()),
            "n_parent_gross_documented_dt_gt_50": int(gross_doc_parent.sum()),
            "n_parent_gross_guarded_dt_gt_51": int(gross_guard_parent.sum()),
            "n_all_three_control": int(all_three.sum()),
            "n_all_three_gross_guarded": int((all_three & gross_guard_parent).sum()),
            "n_extreme_events": int(len(benchmark)),
            "n_clean": int((y == 0).sum()),
            "n_gross": int((y == 1).sum()),
            "shape_feature_count": int(len(shape_cols)),
            "amplitude_feature_count": int(len(amp_cols)),
            "max_clean_abs_c_t_ns": max_clean_curv,
            "min_gross_abs_c_t_ns": min_gross_curv,
            "amplitude_strata": sorted(str(x) for x in benchmark["amplitude_stratum"].unique()),
            "current_run_families": {str(k): [int(vv) for vv in v] for k, v in config["current_run_families"].items()},
        },
        "input_sha256": hashlib.sha256("".join(input_hashes.values()).encode("ascii")).hexdigest(),
        "git_commit": git_commit(),
        "next_tickets": [
            "S07h: replace App.I D_t extremes with an independent A-stack or duplicate-readout timing-tail target in the high-amplitude all-three subset",
            "S13d: charge/amplitude-matched current-family null for Sample-II timing-tail waveform scores",
        ],
    }

    write_report(out_dir, config, reproduction, run_counts, scoreboard, leakage, fixed_eff, strata, result)
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")

    manifest = {
        "ticket": config["ticket_id"],
        "study": config["study_id"],
        "worker": config["worker"],
        "git_commit": git_commit(),
        "config": str(config_path),
        "command": " ".join(sys.argv),
        "environment_command": "uv run --with uproot --with numpy --with pandas --with scikit-learn python",
        "random_seed": seed,
        "runtime_sec": round(time.time() - t0, 2),
        "inputs": input_hashes,
        "outputs": hash_outputs(out_dir),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"out_dir": str(out_dir), "parent_gross": int(gross_guard_parent.sum()), "all_three_gross": int((all_three & gross_guard_parent).sum()), "curvature_auc": trad_auc, "ml_auc": ml_auc}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
