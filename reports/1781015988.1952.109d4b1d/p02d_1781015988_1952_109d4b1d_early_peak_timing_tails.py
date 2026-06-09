#!/usr/bin/env python3
"""P02d: early-peak pulse topology versus downstream timing tails.

This report-local script reads raw B-stack ROOT files, reproduces the P02
early-peak rate and S07 guarded gross timing-tail count first, then benchmarks
transparent P02-like morphology scores against a run-held-out RF morphology
score on the downstream S02/S07-style timing tail label.  D_t, C_t, run id,
event id, absolute amplitudes, and selected-stave flags are excluded from the
main ML feature matrix.
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
from typing import Callable, Dict, Iterable, List, Sequence, Tuple

os.environ.setdefault("MPLCONFIGDIR", "/tmp/ccb-testbeam-p02d-mpl")

import numpy as np
import pandas as pd
import uproot
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import average_precision_score, roc_auc_score


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
                out[row, stave_idx] = 0.0
            else:
                y0 = float(wave[row, j - 1])
                y1 = float(wave[row, j])
                denom = y1 - y0
                frac = 0.0 if denom <= 0 else (float(threshold[row]) - y0) / denom
                out[row, stave_idx] = (j - 1 + frac) * float(period_ns)
    return out


def pulse_features(norm: np.ndarray) -> Dict[str, float]:
    area = float(norm.sum())
    abs_area = max(abs(area), 1e-6)
    peak = int(np.argmax(norm))
    return {
        "peak_sample": float(peak),
        "area_over_peak": area,
        "tail_fraction": float(norm[12:].sum() / abs_area),
        "late_fraction": float(norm[9:].sum() / abs_area),
        "early_fraction": float(norm[:5].sum() / abs_area),
        "final_fraction": float(norm[-1]),
        "width50": float((norm > 0.5).sum()),
        "width20": float((norm > 0.2).sum()),
        "max_down_step": float(np.diff(norm).min()),
        "asymmetry": float((norm[10:].sum() - norm[:5].sum()) / abs_area),
    }


def p02_score_from_features(feat: Dict[str, float]) -> float:
    early = max(0.0, 3.5 - feat["peak_sample"])
    low_area = max(0.0, 2.5 - feat["area_over_peak"])
    negative_step = max(0.0, -0.45 - feat["max_down_step"])
    terminal = max(0.0, abs(feat["final_fraction"]) - 0.10)
    return float(early + 0.7 * low_area + 0.5 * negative_step + 0.2 * terminal)


def add_prefix(row: Dict[str, object], prefix: str, feat: Dict[str, float], norm: np.ndarray) -> None:
    for key, value in feat.items():
        row[f"{prefix}_{key}"] = float(value)
    for idx, value in enumerate(norm):
        row[f"{prefix}_norm_s{idx:02d}"] = float(value)


def add_downstream_aggregates(row: Dict[str, object], ds_feats: List[Dict[str, float]], ds_norms: List[np.ndarray]) -> None:
    if not ds_feats:
        return
    keys = list(ds_feats[0].keys())
    for key in keys:
        vals = np.asarray([feat[key] for feat in ds_feats], dtype=float)
        row[f"ds_mean_{key}"] = float(vals.mean())
        row[f"ds_std_{key}"] = float(vals.std(ddof=0))
    norms = np.vstack(ds_norms)
    for idx in range(norms.shape[1]):
        vals = norms[:, idx]
        row[f"ds_mean_norm_s{idx:02d}"] = float(vals.mean())
        row[f"ds_std_norm_s{idx:02d}"] = float(vals.std(ddof=0))


def build_tables(config: dict) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    staves = list(config["staves"].keys())
    channels = np.asarray([int(config["staves"][name]) for name in staves], dtype=int)
    downstream_idx = np.asarray([staves.index(name) for name in config["downstream_staves"]], dtype=int)
    b2_idx = staves.index("B2")
    baseline_idx = [int(i) for i in config["baseline_samples"]]
    cut = float(config["amplitude_cut_adc"])
    nsamp = int(config["samples_per_channel"])
    all_runs = sorted(set(config["p02_runs"]) | set(config["benchmark_runs"]))

    p02_parts: List[pd.DataFrame] = []
    event_rows: List[dict] = []
    run_rows: List[dict] = []
    event_uid_offset = 0

    for run in all_runs:
        path = raw_file(config, int(run))
        if not path.exists():
            raise FileNotFoundError(path)
        run_seen = 0
        run_selected_pulses = 0
        run_parent_control = 0
        run_parent_clean = 0
        run_parent_gross_doc = 0
        run_parent_gross_guard = 0
        p02_peak_parts: List[np.ndarray] = []

        for batch in iter_raw(path, ["EVENTNO", "EVT", "HRDv"]):
            eventno = np.asarray(batch["EVENTNO"]).astype(int)
            evt = np.asarray(batch["EVT"]).astype(int)
            events = np.stack(batch["HRDv"]).astype(np.float64).reshape(-1, 8, nsamp)
            wave = events[:, channels, :]
            baseline = np.median(wave[..., baseline_idx], axis=-1)
            corrected = wave - baseline[..., None]
            amplitude = corrected.max(axis=-1)
            selected = amplitude > cut
            run_seen += len(eventno)
            run_selected_pulses += int(selected.sum())

            if int(run) in set(config["p02_runs"]):
                event_idx, stave_idx = np.where(selected)
                if len(event_idx):
                    amp = amplitude[event_idx, stave_idx]
                    norm = corrected[event_idx, stave_idx] / amp[:, None]
                    p02_peak_parts.append(np.argmax(norm, axis=1).astype(np.int16))

            if int(run) not in set(config["benchmark_runs"]):
                event_uid_offset += len(eventno)
                continue

            downstream_count = selected[:, downstream_idx].sum(axis=1)
            control_mask = selected[:, b2_idx] & (downstream_count >= int(config["min_downstream_staves"]))
            times = cfd_times_ns(corrected, amplitude, float(config["cfd_fraction"]), float(config["sample_period_ns"]), cut)

            for idx in np.where(control_mask)[0]:
                ds_times = times[idx, downstream_idx]
                ds_sel = selected[idx, downstream_idx]
                ds_valid = ds_times[ds_sel & np.isfinite(ds_times)]
                if len(ds_valid) < int(config["min_downstream_staves"]):
                    continue
                d_t = float(np.max(ds_valid) - np.min(ds_valid))
                c_t = float("nan")
                if np.all(ds_sel) and np.all(np.isfinite(ds_times)):
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
                    "downstream_count": int(downstream_count[idx]),
                    "all_three_downstream": bool(np.all(ds_sel)),
                }
                for stave_idx, stave in enumerate(staves):
                    row[f"{stave.lower()}_selected"] = bool(selected[idx, stave_idx])
                    row[f"{stave.lower()}_log_amp"] = float(np.log1p(max(amplitude[idx, stave_idx], 0.0))) if selected[idx, stave_idx] else 0.0

                selected_feats: List[Dict[str, float]] = []
                selected_scores: List[float] = []
                ds_feats: List[Dict[str, float]] = []
                ds_norms: List[np.ndarray] = []
                for stave_idx, stave in enumerate(staves):
                    if not selected[idx, stave_idx]:
                        continue
                    amp = max(float(amplitude[idx, stave_idx]), 1.0)
                    norm = corrected[idx, stave_idx] / amp
                    feat = pulse_features(norm)
                    score = p02_score_from_features(feat)
                    selected_feats.append(feat)
                    selected_scores.append(score)
                    if stave == "B2":
                        add_prefix(row, "b2", feat, norm)
                        row["b2_p02_score"] = score
                    else:
                        ds_feats.append(feat)
                        ds_norms.append(norm)
                add_downstream_aggregates(row, ds_feats, ds_norms)
                row["any_early_peak"] = float(any(feat["peak_sample"] <= 3 for feat in selected_feats))
                row["b2_early_peak"] = float(row.get("b2_peak_sample", 99.0) <= 3)
                row["early_peak_count"] = float(sum(feat["peak_sample"] <= 3 for feat in selected_feats))
                row["downstream_early_count"] = float(sum(feat["peak_sample"] <= 3 for feat in ds_feats))
                row["early_low_area_count"] = float(sum((feat["peak_sample"] <= 3) and (feat["area_over_peak"] < 2.5) for feat in selected_feats))
                row["min_peak_sample"] = float(min(feat["peak_sample"] for feat in selected_feats))
                row["min_area_over_peak"] = float(min(feat["area_over_peak"] for feat in selected_feats))
                row["max_p02_score"] = float(max(selected_scores))
                row["ds_max_p02_score"] = float(max([p02_score_from_features(feat) for feat in ds_feats], default=0.0))
                event_rows.append(row)
                run_parent_control += 1
                run_parent_clean += int(d_t < float(config["clean_dt_max_ns"]))
                run_parent_gross_doc += int(d_t > float(config["documented_gross_dt_min_ns"]))
                run_parent_gross_guard += int(d_t > float(config["gross_dt_min_ns"]))
            event_uid_offset += len(eventno)

        if p02_peak_parts:
            p02_parts.append(pd.DataFrame({"run": int(run), "peak_sample": np.concatenate(p02_peak_parts)}))
        run_rows.append(
            {
                "run": int(run),
                "raw_events": int(run_seen),
                "selected_pulses": int(run_selected_pulses),
                "parent_control_events": int(run_parent_control),
                "parent_clean_dt_lt3": int(run_parent_clean),
                "parent_gross_dt_gt50": int(run_parent_gross_doc),
                "parent_gross_dt_gt51": int(run_parent_gross_guard),
            }
        )
        print(f"run {run:04d}: selected_pulses={run_selected_pulses} parent_control={run_parent_control} gross_gt51={run_parent_gross_guard}")

    return pd.concat(p02_parts, ignore_index=True), pd.DataFrame(event_rows), pd.DataFrame(run_rows)


def p02_reproduction(config: dict, pulses: pd.DataFrame) -> dict:
    rng = np.random.default_rng(0)
    parts: List[np.ndarray] = []
    total = 0
    for run in config["p02_runs"]:
        idx = pulses.index[pulses["run"].to_numpy() == int(run)].to_numpy()
        parts.append(idx)
        total += len(idx)
        if total > int(config["p02_sample_size"]):
            break
    sample_idx = np.concatenate(parts)
    if len(sample_idx) > int(config["p02_sample_size"]):
        sample_idx = rng.choice(sample_idx, size=int(config["p02_sample_size"]), replace=False)
    peak = pulses.loc[sample_idx, "peak_sample"].to_numpy()
    rate = float(np.mean(peak <= 3))
    return {
        "quantity": "P02 early-peak pulse rate, peak_sample<=3",
        "report_value": float(config["expected_p02_early_peak_rate"]),
        "reproduced": rate,
        "delta": rate - float(config["expected_p02_early_peak_rate"]),
        "tolerance": 0.002,
        "pass": bool(len(sample_idx) == int(config["p02_sample_size"]) and abs(rate - float(config["expected_p02_early_peak_rate"])) <= 0.002),
        "sample_size": int(len(sample_idx)),
    }


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


def summarize(name: str, y: np.ndarray, score: np.ndarray, runs: np.ndarray, seed: int, n_boot: int, notes: str) -> dict:
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
        "notes": notes,
    }


def traditional_oof(data: pd.DataFrame, y: np.ndarray) -> Tuple[np.ndarray, pd.DataFrame]:
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
    rows = []
    for held_run in sorted(np.unique(runs)):
        train = runs != held_run
        test = runs == held_run
        best = None
        for candidate in candidates:
            cand_score = data[candidate].to_numpy(dtype=float)
            row = {"heldout_run": int(held_run), "candidate": candidate, "train_auc": auc(y[train], cand_score[train]), "train_ap": ap(y[train], cand_score[train])}
            rows.append(row)
            key = (row["train_ap"], row["train_auc"])
            if best is None or key > best[0]:
                best = (key, candidate)
        assert best is not None
        score[test] = data[best[1]].to_numpy(dtype=float)[test]
        rows.append({"heldout_run": int(held_run), "candidate": "__selected__", "train_auc": float("nan"), "train_ap": float("nan"), "selected": best[1]})
    return score, pd.DataFrame(rows)


def rf_oof(data: pd.DataFrame, y: np.ndarray, cols: List[str], params: dict, seed: int, shuffle_train: bool = False) -> np.ndarray:
    runs = data["run"].to_numpy(dtype=int)
    x = data[cols].to_numpy(dtype=float)
    x = np.nan_to_num(x, nan=0.0, posinf=0.0, neginf=0.0)
    score = np.full(len(data), np.nan, dtype=float)
    rng = np.random.default_rng(seed)
    for fold, held_run in enumerate(sorted(np.unique(runs))):
        train = runs != held_run
        test = runs == held_run
        y_train = y[train].copy()
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
        clf.fit(x[train], y_train)
        score[test] = clf.predict_proba(x[test])[:, 1]
    return score


def shape_columns(data: pd.DataFrame) -> List[str]:
    forbidden = ["d_t", "c_t", "run", "event", "evt", "log_amp", "selected", "downstream_count", "all_three"]
    allowed_tokens = ["b2_", "ds_mean_", "ds_std_", "early_", "min_peak", "min_area", "p02_score"]
    cols = []
    for col in data.columns:
        lower = col.lower()
        if not pd.api.types.is_numeric_dtype(data[col]):
            continue
        if any(token in lower for token in forbidden):
            continue
        if any(token in lower for token in allowed_tokens):
            cols.append(col)
    return sorted(set(cols))


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


def markdown_table(frame: pd.DataFrame, columns: Sequence[str] = None) -> str:
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
    return value


def write_report(out_dir: Path, config: dict, reproduction: pd.DataFrame, run_counts: pd.DataFrame, scoreboard: pd.DataFrame, leakage: pd.DataFrame, association: pd.DataFrame, result: dict) -> None:
    trad = scoreboard[scoreboard["method"] == "transparent P02 morphology"].iloc[0]
    ml = scoreboard[scoreboard["method"] == "shape-only RF morphology"].iloc[0]
    b2_probe = leakage[leakage["probe"] == "B2-only shape RF"].iloc[0]
    ds_probe = leakage[leakage["probe"] == "downstream-only shape RF"].iloc[0]
    text = f"""# P02d: early-peak topology versus timing tails

- **Ticket:** {config['ticket_id']}
- **Worker:** {config['worker']}
- **Date:** 2026-06-09
- **Input:** raw B-stack `HRDv` ROOT in `{config['raw_root_dir']}`
- **Runs:** P02 sample {', '.join(map(str, config['p02_runs']))}; timing benchmark {', '.join(map(str, config['benchmark_runs']))}

## Question
Does the reproducible P02 early-peak/low-area pulse topology predict downstream S02/S07 timing-tail behavior when `D_t` is used only as the held-out evaluation label and never as a model feature?

## Raw Reproduction First
Selection follows the shared raw ROOT rule: B2/B4/B6/B8 from `HRDv`, baseline median samples 0-3, amplitude `A>1000` ADC, and CFD20 times for downstream timing.

{markdown_table(reproduction)}

Run-level timing counts:

{markdown_table(run_counts[run_counts['run'].isin(config['benchmark_runs'])])}

The P02 early-peak rate is reproduced on the same 60,000-pulse recipe used by P02/P02b. The S07 guarded gross-tail count reproduces the documented 72-event count before any modeling.

## Methods
The benchmark uses S02/S07 App.I-style downstream timing extremes: clean if `D_t<3 ns`, gross if `D_t>51 ns`; intermediate events are excluded. Predictions are leave-one-run-held-out across the seven Sample-II analysis runs, with run-block bootstrap CIs.

- **Traditional:** a strong transparent P02 morphology baseline. For each held-out run, the train folds choose among early-peak flags/counts, early-low-area count, and a hand-built P02 morphology score. No timing variables, run id, event id, or absolute amplitudes are used.
- **ML:** random forest over amplitude-normalized B2 shape plus selected-downstream mean/std shape summaries. It excludes `D_t`, `C_t`, run id, event id, absolute amplitudes, and selected-stave flags.
- **Leakage checks:** topology-only, absolute-amplitude-only, shuffled-label RF, forbidden-feature audit, and a leaky `D_t` ceiling.

## Early-Peak Association
{markdown_table(association)}

## Head-to-Head
{markdown_table(scoreboard)}

## Leakage Hunt
{markdown_table(leakage)}

The RF is strong enough to require skepticism. The shuffled-label control is near chance, and the forbidden-feature audit found no `D_t`, `C_t`, run/event, amplitude, or selected-flag columns in the main RF matrix. However, the downstream-only waveform probe is also very high (AUC {ds_probe['roc_auc']:.3f}), while B2-only is much lower (AUC {b2_probe['roc_auc']:.3f}). Since `D_t` is computed from the same downstream waveforms, this is a label-source self-reference risk rather than an independent validation of pulse topology. The amplitude-only and topology-only probes are also non-trivial, so the morphology result should be read as a timing-tail proxy, not independent timing truth.

## Verdict
The original P02 early-peak flags do **not** validate as a positive timing-tail selector: `any_early_peak` is anti-enriched in gross events and has AUC {result['details']['early_peak_auc']:.3f}. A broader transparent downstream morphology score is modestly predictive, AUC {trad['roc_auc']:.3f} [{trad['roc_auc_ci_low']:.3f}, {trad['roc_auc_ci_high']:.3f}]. The shape-only RF reaches AUC {ml['roc_auc']:.3f} [{ml['roc_auc_ci_low']:.3f}, {ml['roc_auc_ci_high']:.3f}], but the downstream-only leakage probe shows this is largely a morphology reconstruction of the timing-label source. Use P02d as a caution: early-peak topology itself is not the timing-tail driver, and high RF scores on `D_t` labels are not independent timing evidence.

## Reproducibility
```bash
uv run --with uproot --with numpy --with pandas --with scikit-learn python {out_dir / config['script_name']} --config {out_dir / config['config_name']}
```

Artifacts: `REPORT.md`, `result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `run_counts.csv`, `association_table.csv`, `scoreboard.csv`, `leakage_checks.csv`, `traditional_fold_choices.csv`, `fixed_efficiency.csv`, and `oof_predictions.csv`.
"""
    (out_dir / "REPORT.md").write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="reports/1781015988.1952.109d4b1d/p02d_1781015988_1952_109d4b1d_config.json")
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = load_config(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    seed = int(config["random_seed"])

    pulses, events, run_counts = build_tables(config)
    run_counts.to_csv(out_dir / "run_counts.csv", index=False)

    p02_rep = p02_reproduction(config, pulses)
    clean_parent = events["d_t_ns"] < float(config["clean_dt_max_ns"])
    gross_doc_parent = events["d_t_ns"] > float(config["documented_gross_dt_min_ns"])
    gross_guard_parent = events["d_t_ns"] > float(config["gross_dt_min_ns"])
    s07_rep = {
        "quantity": "S07 parent guarded gross events, D_t>51 ns",
        "report_value": int(config["expected_s07_guarded_gross_events"]),
        "reproduced": int(gross_guard_parent.sum()),
        "delta": int(gross_guard_parent.sum()) - int(config["expected_s07_guarded_gross_events"]),
        "tolerance": 0,
        "pass": bool(int(gross_guard_parent.sum()) == int(config["expected_s07_guarded_gross_events"])),
        "sample_size": int(len(events)),
    }
    reproduction = pd.DataFrame([p02_rep, s07_rep])
    reproduction.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(reproduction["pass"].all()):
        raise RuntimeError("Raw reproduction gate failed")

    benchmark = events[clean_parent | gross_guard_parent].copy().reset_index(drop=True)
    benchmark["label_gross"] = (benchmark["d_t_ns"] > float(config["gross_dt_min_ns"])).astype(int)
    y = benchmark["label_gross"].to_numpy(dtype=int)
    runs = benchmark["run"].to_numpy(dtype=int)
    if len(np.unique(y)) < 2:
        raise RuntimeError("Benchmark lacks both timing classes")

    trad_score, trad_choices = traditional_oof(benchmark, y)
    trad_choices.to_csv(out_dir / "traditional_fold_choices.csv", index=False)
    cols = shape_columns(benchmark)
    forbidden = [col for col in cols if any(token in col.lower() for token in ["d_t", "c_t", "run", "event", "evt", "log_amp", "selected", "downstream_count"])]
    if forbidden:
        raise RuntimeError(f"Forbidden feature columns in main RF: {forbidden}")
    ml_score = rf_oof(benchmark, y, cols, config["rf_params"], seed)

    topology_cols = [col for col in benchmark.columns if col.endswith("_selected")] + ["downstream_count", "all_three_downstream"]
    amp_cols = [col for col in benchmark.columns if col.endswith("_log_amp")]
    topo_score = rf_oof(benchmark, y, topology_cols, config["rf_params"], seed + 100)
    amp_score = rf_oof(benchmark, y, amp_cols, config["rf_params"], seed + 200)
    shuf_score = rf_oof(benchmark, y, cols, config["rf_params"], seed + 300, shuffle_train=True)
    b2_cols = [col for col in cols if col.startswith("b2_")]
    ds_cols = [col for col in cols if col.startswith("ds_") or col in ["downstream_early_count", "ds_max_p02_score"]]
    b2_score = rf_oof(benchmark, y, b2_cols, config["rf_params"], seed + 400)
    ds_score = rf_oof(benchmark, y, ds_cols, config["rf_params"], seed + 500)
    leaky_dt_score = benchmark["d_t_ns"].to_numpy(dtype=float)

    n_boot = int(config["bootstrap_replicates"])
    scoreboard = pd.DataFrame(
        [
            summarize("transparent P02 morphology", y, trad_score, runs, seed, n_boot, "Train-fold-selected transparent early-peak/low-area morphology score."),
            summarize("shape-only RF morphology", y, ml_score, runs, seed + 10, n_boot, f"Fixed RF params={config['rf_params']}; {len(cols)} normalized morphology features."),
        ]
    )
    scoreboard.to_csv(out_dir / "scoreboard.csv", index=False)

    association_rows = []
    for name, col in [("any_early_peak", "any_early_peak"), ("b2_early_peak", "b2_early_peak"), ("early_low_area_count>0", "early_low_area_count")]:
        flag = benchmark[col].to_numpy(dtype=float) > 0
        gross_with = float(y[flag].mean()) if flag.any() else float("nan")
        gross_without = float(y[~flag].mean()) if (~flag).any() else float("nan")
        association_rows.append(
            {
                "flag": name,
                "n_flagged": int(flag.sum()),
                "gross_rate_flagged": gross_with,
                "gross_rate_unflagged": gross_without,
                "enrichment": gross_with / gross_without if gross_without and np.isfinite(gross_without) else float("nan"),
                "auc_as_score": auc(y, flag.astype(float)),
            }
        )
    association = pd.DataFrame(association_rows)
    association.to_csv(out_dir / "association_table.csv", index=False)

    leakage = pd.DataFrame(
        [
            {"probe": "topology-only RF", "roc_auc": auc(y, topo_score), "average_precision": ap(y, topo_score), "notes": "Selected-stave flags and downstream count only; excluded from main RF."},
            {"probe": "absolute-amplitude-only RF", "roc_auc": auc(y, amp_score), "average_precision": ap(y, amp_score), "notes": "Log amplitudes only; excluded from main RF."},
            {"probe": "B2-only shape RF", "roc_auc": auc(y, b2_score), "average_precision": ap(y, b2_score), "notes": "Upstream B2 normalized shape only; tests whether the result survives away from D_t source waveforms."},
            {"probe": "downstream-only shape RF", "roc_auc": auc(y, ds_score), "average_precision": ap(y, ds_score), "notes": "Downstream normalized shape only; high values are label-source self-reference risk because D_t is derived from these waveforms."},
            {"probe": "shape RF with shuffled training labels", "roc_auc": auc(y, shuf_score), "average_precision": ap(y, shuf_score), "notes": "Run-held-out null/leakage sanity check."},
            {"probe": "leaky D_t score", "roc_auc": auc(y, leaky_dt_score), "average_precision": ap(y, leaky_dt_score), "notes": "Forbidden label-defining ceiling; reported only as a leakage reference."},
            {"probe": "forbidden feature audit", "roc_auc": float("nan"), "average_precision": float("nan"), "notes": f"Forbidden columns in main RF: {forbidden}."},
        ]
    )
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)

    fixed_rows = []
    fixed_rows.extend(fixed_efficiency_rows(benchmark, y, trad_score, float(config["fixed_clean_efficiency"]), "transparent P02 morphology"))
    fixed_rows.extend(fixed_efficiency_rows(benchmark, y, ml_score, float(config["fixed_clean_efficiency"]), "shape-only RF morphology"))
    fixed_eff = pd.DataFrame(fixed_rows)
    fixed_eff.to_csv(out_dir / "fixed_efficiency.csv", index=False)

    oof_cols = ["event_id", "run", "eventno", "evt", "d_t_ns", "c_t_ns", "abs_c_t_ns", "downstream_count", "all_three_downstream", "label_gross", "any_early_peak", "b2_early_peak", "early_peak_count", "early_low_area_count"]
    oof = benchmark[oof_cols].copy()
    oof["traditional_score"] = trad_score
    oof["ml_score"] = ml_score
    oof["topology_probe_score"] = topo_score
    oof["amplitude_probe_score"] = amp_score
    oof["b2_shape_probe_score"] = b2_score
    oof["downstream_shape_probe_score"] = ds_score
    oof["shuffle_probe_score"] = shuf_score
    oof.to_csv(out_dir / "oof_predictions.csv", index=False)

    input_hash_rows = []
    input_hashes = {}
    for run in sorted(set(config["p02_runs"]) | set(config["benchmark_runs"])):
        path = raw_file(config, int(run))
        digest = sha256_file(path)
        input_hashes[str(path)] = digest
        input_hash_rows.append({"path": str(path), "sha256": digest, "size": path.stat().st_size})
    pd.DataFrame(input_hash_rows).to_csv(out_dir / "input_sha256.csv", index=False)

    result = {
        "study": config["study_id"],
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced": bool(reproduction["pass"].all()),
        "reproduction": reproduction.to_dict(orient="records"),
        "traditional": {
            "method": "transparent P02 morphology",
            "metric": "leave-one-run-out ROC AUC on S02/S07 downstream D_t extreme timing-tail labels",
            "value": float(scoreboard.loc[scoreboard["method"] == "transparent P02 morphology", "roc_auc"].iloc[0]),
            "ci": [
                float(scoreboard.loc[scoreboard["method"] == "transparent P02 morphology", "roc_auc_ci_low"].iloc[0]),
                float(scoreboard.loc[scoreboard["method"] == "transparent P02 morphology", "roc_auc_ci_high"].iloc[0]),
            ],
        },
        "ml": {
            "method": "shape-only RF morphology",
            "metric": "leave-one-run-out ROC AUC on S02/S07 downstream D_t extreme timing-tail labels",
            "value": float(scoreboard.loc[scoreboard["method"] == "shape-only RF morphology", "roc_auc"].iloc[0]),
            "ci": [
                float(scoreboard.loc[scoreboard["method"] == "shape-only RF morphology", "roc_auc_ci_low"].iloc[0]),
                float(scoreboard.loc[scoreboard["method"] == "shape-only RF morphology", "roc_auc_ci_high"].iloc[0]),
            ],
            "feature_count": int(len(cols)),
            "params": config["rf_params"],
        },
        "ml_beats_traditional": bool(scoreboard.loc[scoreboard["method"] == "shape-only RF morphology", "roc_auc"].iloc[0] > scoreboard.loc[scoreboard["method"] == "transparent P02 morphology", "roc_auc"].iloc[0]),
        "leakage_checks": leakage.to_dict(orient="records"),
        "details": {
            "n_parent_control": int(len(events)),
            "n_parent_clean": int(clean_parent.sum()),
            "n_parent_gross_dt_gt50": int(gross_doc_parent.sum()),
            "n_parent_gross_dt_gt51": int(gross_guard_parent.sum()),
            "n_extreme_events": int(len(benchmark)),
            "n_clean": int((y == 0).sum()),
            "n_gross": int((y == 1).sum()),
            "early_peak_auc": float(association.loc[association["flag"] == "any_early_peak", "auc_as_score"].iloc[0]),
            "early_peak_gross_enrichment": float(association.loc[association["flag"] == "any_early_peak", "enrichment"].iloc[0]),
            "shape_feature_count": int(len(cols)),
            "forbidden_shape_features": forbidden,
        },
        "input_sha256": hashlib.sha256("".join(input_hashes.values()).encode("ascii")).hexdigest(),
        "git_commit": git_commit(),
        "next_tickets": [],
    }

    write_report(out_dir, config, reproduction, run_counts, scoreboard, leakage, association, result)
    (out_dir / "result.json").write_text(json.dumps(json_ready(result), indent=2, allow_nan=False), encoding="utf-8")

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
    (out_dir / "manifest.json").write_text(json.dumps(json_ready(manifest), indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({"out_dir": str(out_dir), "p02_early_rate": p02_rep["reproduced"], "s07_gross_gt51": s07_rep["reproduced"], "traditional_auc": result["traditional"]["value"], "ml_auc": result["ml"]["value"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
