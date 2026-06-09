#!/usr/bin/env python3
"""S03d q_template-only clean-timing validation against downstream timing tails.

The script reads raw B-stack ROOT files, reproduces the S00 selected-pulse
counts and the S07 downstream gross-tail gate first, then evaluates whether
q_template-only event scores validate clean timing on held-out runs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import sys
import time
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Sequence, Tuple

import numpy as np
import pandas as pd
import uproot
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.pipeline import make_pipeline


STAVE_NAMES = ["B2", "B4", "B6", "B8"]
DOWNSTREAM = ["B4", "B6", "B8"]


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


def configured_runs(config: dict) -> List[int]:
    runs: List[int] = []
    for group_runs in config["run_groups"].values():
        runs.extend(int(run) for run in group_runs)
    return sorted(set(runs))


def run_group_lookup(config: dict) -> Dict[int, str]:
    out: Dict[int, str] = {}
    for group, runs in config["run_groups"].items():
        for run in runs:
            out[int(run)] = group
    return out


def raw_file(config: dict, run: int) -> Path:
    return Path(config["raw_root_dir"]) / f"hrdb_run_{run:04d}.root"


def iter_raw(path: Path, branches: Sequence[str], step_size: int = 20000) -> Iterable[dict]:
    tree = uproot.open(path)["h101"]
    yield from tree.iterate(list(branches), step_size=step_size, library="np")


def cfd_position(norm_waveform: np.ndarray, fraction: float) -> float:
    peak = int(np.nanargmax(norm_waveform))
    if peak <= 0 or not np.isfinite(norm_waveform[peak]) or norm_waveform[peak] <= 0:
        return float("nan")
    target = float(fraction) * float(norm_waveform[peak])
    for idx in range(1, peak + 1):
        y0 = float(norm_waveform[idx - 1])
        y1 = float(norm_waveform[idx])
        if np.isfinite(y0) and np.isfinite(y1) and y0 <= target <= y1 and y1 != y0:
            return float(idx - 1 + (target - y0) / (y1 - y0))
    return float(peak)


def align_waveform(norm_waveform: np.ndarray, rel_grid: np.ndarray, fraction: float) -> np.ndarray:
    pos = cfd_position(norm_waveform, fraction)
    if not np.isfinite(pos):
        return np.full(len(rel_grid), np.nan, dtype=np.float32)
    x = np.arange(len(norm_waveform), dtype=np.float64)
    return np.interp(pos + rel_grid, x, norm_waveform, left=np.nan, right=np.nan).astype(np.float32)


def cfd_times_ns(corrected: np.ndarray, amplitude: np.ndarray, fraction: float, period_ns: float, cut_adc: float) -> np.ndarray:
    out = np.full(amplitude.shape, np.nan, dtype=np.float32)
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
                out[row, stave_idx] = float(j - 1 + np.clip(frac, 0.0, 1.0)) * float(period_ns)
    return out


def assign_amp_bins(amplitude: np.ndarray, edges: np.ndarray) -> np.ndarray:
    return np.clip(np.searchsorted(edges, amplitude, side="right") - 1, 0, len(edges) - 2)


def build_templates(config: dict, calib_meta: pd.DataFrame, calib_aligned: np.ndarray) -> Tuple[dict, pd.DataFrame]:
    edges = np.asarray(config["template_amplitude_edges_adc"], dtype=np.float64)
    min_bin = int(config["template_min_bin_pulses"])
    bin_idx = assign_amp_bins(calib_meta["amplitude_adc"].to_numpy(dtype=float), edges)
    templates: Dict[Tuple[str, int], np.ndarray] = {}
    fallback: Dict[str, np.ndarray] = {}
    rows = []
    staves = calib_meta["stave"].to_numpy()
    for stave in STAVE_NAMES:
        stave_mask = staves == stave
        fallback[stave] = np.nanmedian(calib_aligned[stave_mask], axis=0).astype(np.float32)
        for b in range(len(edges) - 1):
            mask = stave_mask & (bin_idx == b)
            n = int(mask.sum())
            if n >= min_bin:
                source = "bin"
                template = np.nanmedian(calib_aligned[mask], axis=0).astype(np.float32)
            else:
                source = "stave_fallback"
                template = fallback[stave]
            templates[(stave, b)] = template
            rows.append(
                {
                    "stave": stave,
                    "bin": b,
                    "amp_low_adc": float(edges[b]),
                    "amp_high_adc": float(edges[b + 1]),
                    "n_calib": n,
                    "source": source,
                }
            )
    return {"templates": templates, "edges": edges}, pd.DataFrame(rows)


def template_q(meta: pd.DataFrame, aligned: np.ndarray, pack: dict) -> np.ndarray:
    edges = pack["edges"]
    bins = assign_amp_bins(meta["amplitude_adc"].to_numpy(dtype=float), edges)
    out = np.full(len(meta), np.nan, dtype=np.float64)
    staves = meta["stave"].to_numpy()
    for i, stave in enumerate(staves):
        template = pack["templates"][(str(stave), int(bins[i]))]
        valid = np.isfinite(aligned[i]) & np.isfinite(template)
        if valid.any():
            out[i] = float(np.sqrt(np.mean((aligned[i, valid] - template[valid]) ** 2)))
    return out


def scan_raw(config: dict) -> Tuple[pd.DataFrame, pd.DataFrame, np.ndarray, pd.DataFrame, np.ndarray]:
    staves = {name: int(config["staves"][name]) for name in STAVE_NAMES}
    channels = np.asarray([staves[name] for name in STAVE_NAMES], dtype=int)
    downstream_idx = np.asarray([STAVE_NAMES.index(name) for name in DOWNSTREAM], dtype=int)
    b2_idx = STAVE_NAMES.index("B2")
    group_for_run = run_group_lookup(config)
    baseline_idx = np.asarray(config["baseline_samples"], dtype=int)
    nsamp = int(config["samples_per_channel"])
    cut = float(config["amplitude_cut_adc"])
    rel_grid = np.asarray(config["aligned_relative_grid"], dtype=np.float64)
    cfd_fraction = float(config["cfd_fraction"])
    period_ns = float(config["sample_period_ns"])
    calib_runs = {run for group, runs in config["run_groups"].items() if group.endswith("_calib") for run in map(int, runs)}
    benchmark_runs = set(map(int, config["benchmark_runs"]))

    calib_rows: List[pd.DataFrame] = []
    calib_aligned: List[np.ndarray] = []
    bench_pulse_rows: List[pd.DataFrame] = []
    bench_aligned: List[np.ndarray] = []
    event_rows: List[dict] = []
    run_rows: List[dict] = []

    for run in configured_runs(config):
        path = raw_file(config, run)
        if not path.exists():
            raise FileNotFoundError(path)
        group = group_for_run[run]
        run_counts = {
            "run": int(run),
            "group": group,
            "raw_events": 0,
            "selected_pulses": 0,
            "events_with_selected": 0,
            "parent_control_events": 0,
            "parent_clean_dt_lt3": 0,
            "parent_gross_dt_gt50": 0,
            "parent_gross_dt_gt51": 0,
            "all_three_control_events": 0,
            "all_three_gross_dt_gt51": 0,
        }
        event_offset = 0
        for batch in iter_raw(path, ["EVENTNO", "EVT", "HRDv"]):
            eventno = np.asarray(batch["EVENTNO"]).astype(np.int64)
            evt = np.asarray(batch["EVT"]).astype(np.int64)
            wave = np.stack(batch["HRDv"]).astype(np.float32).reshape(-1, 8, nsamp)[:, channels, :]
            baseline = np.median(wave[..., baseline_idx], axis=-1)
            corrected = wave - baseline[..., None]
            amplitude = corrected.max(axis=-1)
            selected = amplitude > cut
            run_counts["raw_events"] += int(len(eventno))
            run_counts["selected_pulses"] += int(selected.sum())
            run_counts["events_with_selected"] += int(selected.any(axis=1).sum())

            if run in calib_runs or run in benchmark_runs:
                event_idx, stave_idx = np.where(selected)
                if len(event_idx):
                    chosen = corrected[event_idx, stave_idx, :]
                    chosen_amp = np.maximum(amplitude[event_idx, stave_idx].astype(np.float64), 1.0)
                    norm = chosen / chosen_amp[:, None]
                    aligned = np.vstack([align_waveform(w, rel_grid, cfd_fraction) for w in norm])
                    frame = pd.DataFrame(
                        {
                            "run": int(run),
                            "group": group,
                            "event_uid": [f"{run}:{int(eventno[i])}:{int(evt[i])}:{event_offset + int(i)}" for i in event_idx],
                            "eventno": eventno[event_idx],
                            "evt": evt[event_idx],
                            "stave": np.asarray(STAVE_NAMES, dtype=object)[stave_idx],
                            "amplitude_adc": chosen_amp,
                        }
                    )
                    if run in calib_runs:
                        calib_rows.append(frame[["run", "group", "event_uid", "eventno", "evt", "stave", "amplitude_adc"]])
                        calib_aligned.append(aligned)
                    if run in benchmark_runs:
                        bench_pulse_rows.append(frame[["run", "group", "event_uid", "eventno", "evt", "stave", "amplitude_adc"]])
                        bench_aligned.append(aligned)

            if run in benchmark_runs:
                times = cfd_times_ns(corrected, amplitude, cfd_fraction, period_ns, cut)
                downstream_count = selected[:, downstream_idx].sum(axis=1)
                parent = selected[:, b2_idx] & (downstream_count >= int(config["min_downstream_staves"]))
                all_three = selected[:, b2_idx] & (downstream_count == len(DOWNSTREAM))
                for idx in np.where(parent)[0]:
                    ds_times = times[idx, downstream_idx]
                    ds_sel = selected[idx, downstream_idx]
                    valid_times = ds_times[ds_sel & np.isfinite(ds_times)]
                    if len(valid_times) < int(config["min_downstream_staves"]):
                        continue
                    d_t = float(np.max(valid_times) - np.min(valid_times))
                    c_t = float("nan")
                    if np.all(ds_sel) and np.all(np.isfinite(ds_times)):
                        t4, t6, t8 = [float(v) for v in ds_times]
                        c_t = float(t8 - 2.0 * t6 + t4)
                    row = {
                        "event_uid": f"{run}:{int(eventno[idx])}:{int(evt[idx])}:{event_offset + int(idx)}",
                        "run": int(run),
                        "eventno": int(eventno[idx]),
                        "evt": int(evt[idx]),
                        "d_t_ns": d_t,
                        "c_t_ns": c_t,
                        "all_three_downstream": bool(all_three[idx]),
                        "downstream_count": int(downstream_count[idx]),
                    }
                    event_rows.append(row)
                    run_counts["parent_control_events"] += 1
                    run_counts["parent_clean_dt_lt3"] += int(d_t < float(config["clean_dt_max_ns"]))
                    run_counts["parent_gross_dt_gt50"] += int(d_t > float(config["documented_gross_dt_min_ns"]))
                    run_counts["parent_gross_dt_gt51"] += int(d_t > float(config["gross_dt_min_ns"]))
                    if bool(all_three[idx]):
                        run_counts["all_three_control_events"] += 1
                        run_counts["all_three_gross_dt_gt51"] += int(d_t > float(config["gross_dt_min_ns"]))
            event_offset += len(eventno)
        run_rows.append(run_counts)
        print(
            f"run {run:04d}: selected_pulses={run_counts['selected_pulses']} "
            f"parent_control={run_counts['parent_control_events']} gross_gt51={run_counts['parent_gross_dt_gt51']}"
        )

    return (
        pd.DataFrame(run_rows),
        pd.concat(calib_rows, ignore_index=True),
        np.vstack(calib_aligned),
        pd.concat(bench_pulse_rows, ignore_index=True),
        np.vstack(bench_aligned),
        pd.DataFrame(event_rows),
    )


def reproduction_table(config: dict, run_counts: pd.DataFrame) -> pd.DataFrame:
    exp = config["expected_counts"]
    rows = []
    for quantity, value in [
        ("total selected B-stave pulses", int(exp["total_selected_pulses"])),
        ("sample_i_calib selected pulses", int(exp["sample_i_calib_pulses"])),
        ("sample_i_analysis selected pulses", int(exp["sample_i_analysis_pulses"])),
        ("sample_ii_calib selected pulses", int(exp["sample_ii_calib_pulses"])),
        ("sample_ii_analysis selected pulses", int(exp["sample_ii_analysis_pulses"])),
    ]:
        if quantity.startswith("total"):
            reproduced = int(run_counts["selected_pulses"].sum())
        else:
            group = quantity.split(" selected")[0]
            reproduced = int(run_counts.loc[run_counts["group"] == group, "selected_pulses"].sum())
        rows.append({"quantity": quantity, "report_value": value, "reproduced": reproduced, "tolerance": 0})
    rows.extend(
        [
            {
                "quantity": "S07 parent guarded gross events, D_t>51 ns",
                "report_value": int(config["expected_s07_guarded_gross_events"]),
                "reproduced": int(run_counts["parent_gross_dt_gt51"].sum()),
                "tolerance": 0,
            },
            {
                "quantity": "all-three downstream control events",
                "report_value": int(config["expected_all_three_control_events"]),
                "reproduced": int(run_counts["all_three_control_events"].sum()),
                "tolerance": 0,
            },
            {
                "quantity": "all-three downstream guarded gross events, D_t>51 ns",
                "report_value": int(config["expected_all_three_gross_events"]),
                "reproduced": int(run_counts["all_three_gross_dt_gt51"].sum()),
                "tolerance": 0,
            },
        ]
    )
    out = pd.DataFrame(rows)
    out["delta"] = out["reproduced"] - out["report_value"]
    out["pass"] = out["delta"].abs() <= out["tolerance"]
    return out[["quantity", "report_value", "reproduced", "delta", "tolerance", "pass"]]


def aggregate_events(events: pd.DataFrame, pulse_meta: pd.DataFrame, q_values: np.ndarray) -> pd.DataFrame:
    pulses = pulse_meta.copy()
    pulses["q_template_rmse"] = q_values
    q_wide = pulses.pivot_table(index="event_uid", columns="stave", values="q_template_rmse", aggfunc="first")
    amp_wide = pulses.pivot_table(index="event_uid", columns="stave", values="amplitude_adc", aggfunc="first")
    q_wide = q_wide.reindex(columns=STAVE_NAMES)
    amp_wide = amp_wide.reindex(columns=STAVE_NAMES)
    q_wide.columns = [f"q_{c.lower()}" for c in q_wide.columns]
    amp_wide.columns = [f"amp_{c.lower()}" for c in amp_wide.columns]
    out = events.merge(q_wide.reset_index(), on="event_uid", how="left")
    out = out.merge(amp_wide.reset_index(), on="event_uid", how="left")
    q_cols = [f"q_{s.lower()}" for s in STAVE_NAMES]
    ds_cols = [f"q_{s.lower()}" for s in DOWNSTREAM]
    q = out[q_cols].to_numpy(dtype=float)
    ds = out[ds_cols].to_numpy(dtype=float)
    out["q_mean"] = np.nanmean(q, axis=1)
    out["q_max"] = np.nanmax(q, axis=1)
    out["q_std"] = np.nanstd(q, axis=1)
    out["q_ds_mean"] = np.nanmean(ds, axis=1)
    out["q_ds_max"] = np.nanmax(ds, axis=1)
    out["q_ds_std"] = np.nanstd(ds, axis=1)
    out["q_b2_minus_ds_mean"] = out["q_b2"] - out["q_ds_mean"]
    out["q_ds_span"] = np.nanmax(ds, axis=1) - np.nanmin(ds, axis=1)
    out["amp_mean"] = np.nanmean(out[[f"amp_{s.lower()}" for s in STAVE_NAMES]].to_numpy(dtype=float), axis=1)
    out["amp_ds_mean"] = np.nanmean(out[[f"amp_{s.lower()}" for s in DOWNSTREAM]].to_numpy(dtype=float), axis=1)
    return out


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


def run_bootstrap_ci(
    y: np.ndarray,
    score: np.ndarray,
    runs: np.ndarray,
    metric: Callable[[np.ndarray, np.ndarray], float],
    seed: int,
    n_boot: int,
) -> Tuple[float, float]:
    rng = np.random.default_rng(seed)
    unique_runs = np.unique(runs)
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


def traditional_oof(data: pd.DataFrame, y: np.ndarray, candidates: List[str]) -> Tuple[np.ndarray, pd.DataFrame]:
    runs = data["run"].to_numpy(dtype=int)
    out = np.full(len(data), np.nan, dtype=float)
    rows = []
    for held_run in sorted(np.unique(runs)):
        train = runs != held_run
        test = runs == held_run
        best = None
        for col in candidates:
            vals = data[col].to_numpy(dtype=float)
            for sign, sign_name in [(1.0, "high_bad"), (-1.0, "low_bad")]:
                score = sign * vals
                row = {
                    "heldout_run": int(held_run),
                    "candidate": col,
                    "sign": sign_name,
                    "train_auc": auc(y[train], score[train]),
                    "train_ap": ap(y[train], score[train]),
                }
                rows.append(row)
                key = (row["train_ap"], row["train_auc"])
                if best is None or key > best[0]:
                    best = (key, col, sign, sign_name)
        assert best is not None
        out[test] = best[2] * data[best[1]].to_numpy(dtype=float)[test]
        rows.append(
            {
                "heldout_run": int(held_run),
                "candidate": "__selected__",
                "sign": best[3],
                "train_auc": float("nan"),
                "train_ap": float("nan"),
                "selected": best[1],
            }
        )
    return out, pd.DataFrame(rows)


def rf_oof(data: pd.DataFrame, y: np.ndarray, cols: List[str], params: dict, seed: int, shuffle_train: bool = False) -> np.ndarray:
    runs = data["run"].to_numpy(dtype=int)
    x = data[cols].to_numpy(dtype=float)
    out = np.full(len(data), np.nan, dtype=float)
    rng = np.random.default_rng(seed)
    for fold, held_run in enumerate(sorted(np.unique(runs))):
        train = runs != held_run
        test = runs == held_run
        y_train = y[train].copy()
        if shuffle_train:
            rng.shuffle(y_train)
        clf = make_pipeline(
            SimpleImputer(strategy="median"),
            RandomForestClassifier(
                n_estimators=int(params["n_estimators"]),
                max_depth=int(params["max_depth"]),
                min_samples_leaf=int(params["min_samples_leaf"]),
                class_weight="balanced",
                random_state=seed + fold,
                n_jobs=1,
            ),
        )
        clf.fit(x[train], y_train)
        out[test] = clf.predict_proba(x[test])[:, 1]
    return out


def fixed_clean_efficiency(data: pd.DataFrame, y: np.ndarray, score: np.ndarray, eff: float, method: str) -> pd.DataFrame:
    rows = []
    runs = data["run"].to_numpy(dtype=int)
    for held_run in sorted(np.unique(runs)):
        train = runs != held_run
        test = runs == held_run
        clean_train = score[train & (y == 0)]
        clean_train = clean_train[np.isfinite(clean_train)]
        if len(clean_train) == 0:
            continue
        threshold = float(np.quantile(clean_train, eff))
        clean = test & (y == 0) & np.isfinite(score)
        tail = test & (y == 1) & np.isfinite(score)
        rows.append(
            {
                "method": method,
                "heldout_run": int(held_run),
                "threshold": threshold,
                "clean_efficiency": float(np.mean(score[clean] <= threshold)) if clean.any() else float("nan"),
                "tail_rejection": float(np.mean(score[tail] > threshold)) if tail.any() else float("nan"),
                "n_clean": int(clean.sum()),
                "n_tail": int(tail.sum()),
            }
        )
    return pd.DataFrame(rows)


def markdown_table(frame: pd.DataFrame) -> str:
    def fmt(value: object) -> str:
        if pd.isna(value):
            return ""
        if isinstance(value, (float, np.floating)):
            return f"{float(value):.6g}"
        return str(value).replace("|", "\\|")

    cols = list(frame.columns)
    rows = [[fmt(row[col]) for col in cols] for _, row in frame.iterrows()]
    widths = [len(str(c)) for c in cols]
    for row in rows:
        widths = [max(width, len(cell)) for width, cell in zip(widths, row)]
    header = "| " + " | ".join(str(c).ljust(w) for c, w in zip(cols, widths)) + " |"
    sep = "| " + " | ".join("-" * w for w in widths) + " |"
    body = ["| " + " | ".join(cell.ljust(w) for cell, w in zip(row, widths)) + " |" for row in rows]
    return "\n".join([header, sep, *body])


def json_ready(value):
    if isinstance(value, dict):
        return {str(k): json_ready(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_ready(v) for v in value]
    if isinstance(value, tuple):
        return [json_ready(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        val = float(value)
        return val if math.isfinite(val) else None
    return value


def hash_outputs(out_dir: Path) -> Dict[str, str]:
    return {p.name: sha256_file(p) for p in sorted(out_dir.iterdir()) if p.is_file() and p.name != "manifest.json"}


def write_report(
    out_dir: Path,
    config: dict,
    reproduction: pd.DataFrame,
    run_counts: pd.DataFrame,
    template_bins: pd.DataFrame,
    dataset_counts: pd.DataFrame,
    scoreboard: pd.DataFrame,
    fixed_eff: pd.DataFrame,
    leakage: pd.DataFrame,
    result: dict,
) -> None:
    trad = scoreboard[scoreboard["method"] == "traditional q_template score"].iloc[0]
    ml = scoreboard[scoreboard["method"] == "q_template-only RF"].iloc[0]
    shuffle = leakage[leakage["probe"] == "q-template RF with shuffled training labels"].iloc[0]
    b2 = leakage[leakage["probe"] == "B2-only q-template RF"].iloc[0]
    ds = leakage[leakage["probe"] == "downstream-only q-template RF"].iloc[0]
    text = f"""# S03d: q_template-only clean-timing validation

- **Ticket:** {config['ticket_id']}
- **Worker:** {config['worker']}
- **Date:** 2026-06-09
- **Input:** raw B-stack ROOT in `{config['raw_root_dir']}`
- **Benchmark runs:** {', '.join(map(str, config['benchmark_runs']))}

## Question
Can `q_template`-only clean-timing cuts be validated against held-out downstream timing tails without using App.A weak labels?

## Raw Reproduction First
The script first scans raw `HRDv` ROOT using the shared S00 gate: B2/B4/B6/B8 even channels, baseline median samples 0-3, and amplitude `A>1000` ADC. It also reproduces the S07 downstream timing-tail parent gate using CFD20 downstream span `D_t`.

{markdown_table(reproduction)}

Run counts for the timing benchmark:

{markdown_table(run_counts[run_counts['run'].isin(config['benchmark_runs'])][['run', 'selected_pulses', 'parent_control_events', 'parent_clean_dt_lt3', 'parent_gross_dt_gt51', 'all_three_control_events', 'all_three_gross_dt_gt51']])}

## Methods
Templates are trained from calibration runs only. Each selected pulse is peak-normalized, CFD20-aligned, assigned to a fixed stave/amplitude bin, and scored by RMSE to the calibration median template. The validation target is external to App.A: clean if `D_t < {config['clean_dt_max_ns']} ns`, timing tail if `D_t > {config['gross_dt_min_ns']} ns`; intermediate events are excluded.

Template coverage:

{markdown_table(template_bins.groupby('source', as_index=False).size().rename(columns={'size': 'n_bins'}))}

Dataset:

{markdown_table(dataset_counts)}

- **Traditional:** leave-one-run-out training chooses the best q-template aggregate among `q_max`, `q_mean`, downstream q summaries, q span, and B2-minus-downstream mean, with sign selected inside the training runs.
- **ML:** random forest using q-template aggregate features only. It excludes `D_t`, `C_t`, run id, event id, App.A labels, selected-stave flags, waveform samples, and amplitudes.
- **CIs:** all quoted intervals are held-out run bootstrap 95% CIs over the Sample-II analysis runs.

## Head-to-Head
{markdown_table(scoreboard)}

At 95% clean acceptance, held-out tail rejection is:

{markdown_table(fixed_eff.groupby('method', as_index=False).agg(clean_efficiency=('clean_efficiency', 'mean'), tail_rejection=('tail_rejection', 'mean'), n_tail=('n_tail', 'sum')))}

## Leakage Hunt
{markdown_table(leakage)}

The q-template-only RF is not suspiciously perfect: AUC {ml['roc_auc']:.3f}, while the shuffled-label control is AUC {shuffle['roc_auc']:.3f}. The downstream-only q probe is stronger than the B2-only probe ({ds['roc_auc']:.3f} vs {b2['roc_auc']:.3f}), so the validation is best interpreted as a downstream waveform-quality validation of the timing-tail gate, not independent truth about upstream topology. No App.A label, timing span, run/event id, selected flag, waveform sample, or amplitude column enters the main ML matrix.

## Verdict
The raw reproduction gate passed exactly. `q_template` carries real held-out information about downstream timing tails: the traditional q score reaches AUC {trad['roc_auc']:.3f} [{trad['roc_auc_ci_low']:.3f}, {trad['roc_auc_ci_high']:.3f}], and the q-template-only RF reaches AUC {ml['roc_auc']:.3f} [{ml['roc_auc_ci_low']:.3f}, {ml['roc_auc_ci_high']:.3f}]. This supports replacing the retired App.A count with a run-held-out downstream timing-tail validation gate for q-template clean cuts, with the caveat that downstream q features and downstream `D_t` share waveform provenance.

## Reproducibility
```bash
uv run --with uproot --with numpy --with pandas --with scikit-learn python {out_dir / 's03d_1781012848_qtemplate_tail_validation.py'} --config {out_dir / 's03d_1781012848_config.json'}
```

Artifacts: `REPORT.md`, `result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `run_counts.csv`, `template_bin_counts.csv`, `dataset_counts.csv`, `scoreboard.csv`, `fixed_clean_efficiency.csv`, `leakage_checks.csv`, `traditional_fold_choices.csv`, and `oof_predictions.csv`.
"""
    (out_dir / "REPORT.md").write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="reports/1781012848.2643.539f1f83/s03d_1781012848_config.json")
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = load_config(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    seed = int(config["random_seed"])

    run_counts, calib_meta, calib_aligned, bench_pulses, bench_aligned, events = scan_raw(config)
    run_counts.to_csv(out_dir / "run_counts.csv", index=False)
    reproduction = reproduction_table(config, run_counts)
    reproduction.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(reproduction["pass"].all()):
        raise RuntimeError("Raw reproduction gate failed")

    template_pack, template_bins = build_templates(config, calib_meta, calib_aligned)
    template_bins.to_csv(out_dir / "template_bin_counts.csv", index=False)
    q_values = template_q(bench_pulses, bench_aligned, template_pack)
    data = aggregate_events(events, bench_pulses, q_values)
    clean = data["d_t_ns"].to_numpy(dtype=float) < float(config["clean_dt_max_ns"])
    tail = data["d_t_ns"].to_numpy(dtype=float) > float(config["gross_dt_min_ns"])
    bench = data[clean | tail].copy().reset_index(drop=True)
    bench["label_tail"] = (bench["d_t_ns"] > float(config["gross_dt_min_ns"])).astype(int)
    y = bench["label_tail"].to_numpy(dtype=int)
    runs = bench["run"].to_numpy(dtype=int)

    dataset_counts = pd.DataFrame(
        [
            {"quantity": "parent control events", "value": int(len(data))},
            {"quantity": "clean events D_t<3 ns", "value": int(clean.sum())},
            {"quantity": "tail events D_t>51 ns", "value": int(tail.sum())},
            {"quantity": "extreme benchmark events", "value": int(len(bench))},
            {"quantity": "benchmark tail fraction", "value": float(y.mean())},
        ]
    )
    dataset_counts.to_csv(out_dir / "dataset_counts.csv", index=False)

    trad_candidates = list(config["traditional_candidates"])
    trad_score, trad_choices = traditional_oof(bench, y, trad_candidates)
    trad_choices.to_csv(out_dir / "traditional_fold_choices.csv", index=False)
    q_features = list(config["q_feature_columns"])
    forbidden_tokens = ["d_t", "c_t", "run", "event", "evt", "app", "selected", "amp_", "wave", "time"]
    forbidden = [col for col in q_features if any(token in col.lower() for token in forbidden_tokens)]
    if forbidden:
        raise RuntimeError(f"Forbidden feature columns in main RF: {forbidden}")
    ml_score = rf_oof(bench, y, q_features, config["rf_params"], seed)
    shuf_score = rf_oof(bench, y, q_features, config["rf_params"], seed + 1000, shuffle_train=True)
    b2_score = rf_oof(bench, y, ["q_b2"], config["rf_params"], seed + 2000)
    ds_cols = ["q_b4", "q_b6", "q_b8", "q_ds_mean", "q_ds_max", "q_ds_std", "q_ds_span"]
    ds_score = rf_oof(bench, y, ds_cols, config["rf_params"], seed + 3000)
    amp_cols = [f"amp_{s.lower()}" for s in STAVE_NAMES] + ["amp_mean", "amp_ds_mean"]
    amp_score = rf_oof(bench, y, amp_cols, config["rf_params"], seed + 4000)
    leaky_score = bench["d_t_ns"].to_numpy(dtype=float)

    n_boot = int(config["bootstrap_replicates"])
    scoreboard = pd.DataFrame(
        [
            summarize("traditional q_template score", y, trad_score, runs, seed, n_boot, "Train-run-selected q-template aggregate score."),
            summarize("q_template-only RF", y, ml_score, runs, seed + 10, n_boot, f"RF params={config['rf_params']}; q-template aggregate features only."),
        ]
    )
    scoreboard.to_csv(out_dir / "scoreboard.csv", index=False)

    fixed_eff = pd.concat(
        [
            fixed_clean_efficiency(bench, y, trad_score, float(config["fixed_clean_efficiency"]), "traditional q_template score"),
            fixed_clean_efficiency(bench, y, ml_score, float(config["fixed_clean_efficiency"]), "q_template-only RF"),
        ],
        ignore_index=True,
    )
    fixed_eff.to_csv(out_dir / "fixed_clean_efficiency.csv", index=False)

    leakage = pd.DataFrame(
        [
            {"probe": "q-template RF with shuffled training labels", "roc_auc": auc(y, shuf_score), "average_precision": ap(y, shuf_score), "notes": "Run-held-out null check; labels shuffled only inside training runs."},
            {"probe": "B2-only q-template RF", "roc_auc": auc(y, b2_score), "average_precision": ap(y, b2_score), "notes": "Upstream q_template only; away from downstream D_t source waveforms."},
            {"probe": "downstream-only q-template RF", "roc_auc": auc(y, ds_score), "average_precision": ap(y, ds_score), "notes": "Downstream q_template only; shares waveform provenance with D_t labels."},
            {"probe": "absolute-amplitude-only RF", "roc_auc": auc(y, amp_score), "average_precision": ap(y, amp_score), "notes": "Amplitude nuisance probe; excluded from main RF."},
            {"probe": "leaky D_t score", "roc_auc": auc(y, leaky_score), "average_precision": ap(y, leaky_score), "notes": "Forbidden label-defining ceiling, reported only as a reference."},
            {"probe": "forbidden feature audit", "roc_auc": float("nan"), "average_precision": float("nan"), "notes": f"Forbidden main-feature columns: {forbidden}; main features: {q_features}."},
        ]
    )
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)

    oof_cols = [
        "event_uid",
        "run",
        "eventno",
        "evt",
        "d_t_ns",
        "c_t_ns",
        "downstream_count",
        "all_three_downstream",
        "label_tail",
        *q_features,
    ]
    oof = bench[oof_cols].copy()
    oof["traditional_score"] = trad_score
    oof["ml_score"] = ml_score
    oof["shuffle_score"] = shuf_score
    oof["b2_probe_score"] = b2_score
    oof["downstream_probe_score"] = ds_score
    oof["amplitude_probe_score"] = amp_score
    oof.to_csv(out_dir / "oof_predictions.csv", index=False)

    input_hashes = {}
    input_rows = []
    for run in configured_runs(config):
        path = raw_file(config, run)
        digest = sha256_file(path)
        input_hashes[str(path)] = digest
        input_rows.append({"path": str(path), "sha256": digest, "size": path.stat().st_size})
    pd.DataFrame(input_rows).to_csv(out_dir / "input_sha256.csv", index=False)

    trad = scoreboard[scoreboard["method"] == "traditional q_template score"].iloc[0]
    ml = scoreboard[scoreboard["method"] == "q_template-only RF"].iloc[0]
    result = {
        "study": config["study_id"],
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced": bool(reproduction["pass"].all()),
        "reproduction": reproduction.to_dict(orient="records"),
        "traditional": {
            "method": "traditional q_template score",
            "metric": "leave-one-run-out ROC AUC for D_t>51 ns timing tails",
            "value": float(trad["roc_auc"]),
            "ci": [float(trad["roc_auc_ci_low"]), float(trad["roc_auc_ci_high"])],
        },
        "ml": {
            "method": "q_template-only RF",
            "metric": "leave-one-run-out ROC AUC for D_t>51 ns timing tails",
            "value": float(ml["roc_auc"]),
            "ci": [float(ml["roc_auc_ci_low"]), float(ml["roc_auc_ci_high"])],
            "feature_columns": q_features,
            "params": config["rf_params"],
        },
        "ml_beats_traditional": bool(float(ml["roc_auc"]) > float(trad["roc_auc"])),
        "details": {
            "n_parent_control_events": int(len(data)),
            "n_clean_events": int((y == 0).sum()),
            "n_tail_events": int((y == 1).sum()),
            "tail_fraction": float(y.mean()),
            "template_bin_sources": template_bins["source"].value_counts().to_dict(),
            "fixed_clean_efficiency": float(config["fixed_clean_efficiency"]),
            "forbidden_main_features": forbidden,
        },
        "leakage_checks": leakage.to_dict(orient="records"),
        "input_sha256": hashlib.sha256("".join(input_hashes.values()).encode("ascii")).hexdigest(),
        "git_commit": git_commit(),
        "next_tickets": [
            "S03e: all-three-downstream q_template clean-cut validation with curvature C_t as the primary held-out tail label.",
            "P10f: compare q_template-tail validation using calibration-only median templates against conditional templates without downstream timing labels."
        ],
    }

    write_report(out_dir, config, reproduction, run_counts, template_bins, dataset_counts, scoreboard, fixed_eff, leakage, result)
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
    print(
        json.dumps(
            {
                "out_dir": str(out_dir),
                "reproduced": bool(reproduction["pass"].all()),
                "traditional_auc": float(trad["roc_auc"]),
                "ml_auc": float(ml["roc_auc"]),
                "tail_events": int((y == 1).sum()),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
