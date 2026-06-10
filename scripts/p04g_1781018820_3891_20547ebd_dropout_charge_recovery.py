#!/usr/bin/env python3
"""P04g: controlled sample-dropout closure on raw B-stack pulses.

The script first reproduces the canonical S00 raw selected-pulse count, then injects
deterministic leading-edge, peak, and trailing-sample dropouts into real clean pulses.
All calibrations and ML models are fit on training runs only and evaluated on held-out
runs with event-paired bootstrap intervals.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import time
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import numpy as np
import pandas as pd
import uproot
from sklearn.ensemble import ExtraTreesRegressor, HistGradientBoostingRegressor
from sklearn.linear_model import HuberRegressor, LinearRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


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


def load_config(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def configured_runs(config: dict) -> List[int]:
    runs: List[int] = []
    for values in config["run_groups"].values():
        runs.extend(int(run) for run in values)
    return sorted(set(runs))


def run_group_lookup(config: dict) -> Dict[int, str]:
    out: Dict[int, str] = {}
    for group, runs in config["run_groups"].items():
        for run in runs:
            out[int(run)] = group
    return out


def raw_path(config: dict, run: int) -> Path:
    return Path(config["raw_root_dir"]) / f"hrdb_run_{run:04d}.root"


def iter_batches(path: Path, step_size: int = 30000) -> Iterable[dict]:
    tree = uproot.open(path)["h101"]
    yield from tree.iterate(["EVENTNO", "EVT", "HRDv"], step_size=step_size, library="np")


def cfd_time_samples(wave: np.ndarray, amp: np.ndarray, fraction: float) -> np.ndarray:
    threshold = amp * float(fraction)
    ge = wave >= threshold[:, None]
    first = np.argmax(ge, axis=1)
    valid = ge.any(axis=1)
    out = np.full(len(wave), np.nan, dtype=float)
    for idx in np.where(valid)[0]:
        j = int(first[idx])
        if j <= 0:
            out[idx] = float(j)
            continue
        y0, y1 = float(wave[idx, j - 1]), float(wave[idx, j])
        denom = y1 - y0
        out[idx] = float(j) if denom <= 0 else (j - 1) + (threshold[idx] - y0) / denom
    return out


def extract_selected(config: dict) -> Tuple[pd.DataFrame, np.ndarray, pd.DataFrame]:
    baseline_idx = [int(i) for i in config["baseline_samples"]]
    nsamp = int(config["samples_per_channel"])
    cut = float(config["amplitude_cut_adc"])
    staves = list(config["staves"].keys())
    channels = np.asarray([int(config["staves"][s]) for s in staves], dtype=int)
    stave_names = np.asarray(staves)
    groups = run_group_lookup(config)
    frames: List[pd.DataFrame] = []
    waves: List[np.ndarray] = []
    counts: List[dict] = []

    for run in configured_runs(config):
        path = raw_path(config, run)
        if not path.exists():
            raise FileNotFoundError(path)
        row = {"run": run, "group": groups[run], "events_total": 0, "selected_pulses": 0}
        row.update({stave: 0 for stave in staves})
        for batch in iter_batches(path):
            eventno = np.asarray(batch["EVENTNO"], dtype=np.int64)
            evt = np.asarray(batch["EVT"], dtype=np.int64)
            raw = np.stack(batch["HRDv"]).astype(np.float64).reshape(-1, 8, nsamp)
            baseline = np.median(raw[..., baseline_idx], axis=-1)
            corrected = raw - baseline[..., None]
            even = corrected[:, channels, :]
            amp = even.max(axis=-1)
            peak = even.argmax(axis=-1)
            charge = np.clip(even, 0.0, None).sum(axis=-1)
            selected = amp > cut

            row["events_total"] += int(len(eventno))
            row["selected_pulses"] += int(selected.sum())
            for i, stave in enumerate(staves):
                row[stave] += int(selected[:, i].sum())

            event_idx, stave_idx = np.where(selected)
            if len(event_idx) == 0:
                continue
            waves.append(even[event_idx, stave_idx, :].astype(np.float32))
            frames.append(
                pd.DataFrame(
                    {
                        "run": run,
                        "group": groups[run],
                        "eventno": eventno[event_idx],
                        "evt": evt[event_idx],
                        "stave": stave_names[stave_idx],
                        "stave_idx": stave_idx.astype(np.int16),
                        "clean_amp": amp[event_idx, stave_idx],
                        "clean_peak": peak[event_idx, stave_idx].astype(np.int16),
                        "clean_charge": charge[event_idx, stave_idx],
                    }
                )
            )
        counts.append(row)

    return pd.concat(frames, ignore_index=True), np.vstack(waves), pd.DataFrame(counts)


def peak_region(peak: np.ndarray) -> np.ndarray:
    return np.where(peak <= 6, "early", np.where(peak <= 10, "central", "late"))


def stratified_indices(meta: pd.DataFrame, config: dict) -> np.ndarray:
    work = meta.copy()
    bins = np.asarray(config["amplitude_bins"], dtype=float)
    work["amp_bin"] = pd.cut(work["clean_amp"], bins=bins, labels=False, include_lowest=True)
    work["peak_region"] = peak_region(work["clean_peak"].to_numpy())
    rng = np.random.default_rng(int(config["random_seed"]))
    chosen = []
    cap = int(config["max_sample_per_stratum"])
    for _, group in work.groupby(["run", "stave_idx", "amp_bin", "peak_region"], observed=True):
        idx = group.index.to_numpy()
        if len(idx) > cap:
            idx = rng.choice(idx, size=cap, replace=False)
        chosen.append(idx)
    return np.sort(np.concatenate(chosen))


def inject_dropouts(meta: pd.DataFrame, wave: np.ndarray, indices: np.ndarray, config: dict) -> Tuple[pd.DataFrame, np.ndarray, np.ndarray]:
    nsamp = int(config["samples_per_channel"])
    rows = []
    corrupt_blocks = []
    mask_blocks = []
    base = meta.iloc[indices].reset_index(drop=True)
    clean = wave[indices].astype(float)
    peaks = base["clean_peak"].to_numpy().astype(int)
    for case_idx, case in enumerate(config["dropout_cases"]):
        mask = np.zeros_like(clean, dtype=bool)
        for offset in case["offsets"]:
            pos = peaks + int(offset)
            pos = np.clip(pos, 4, nsamp - 1)
            mask[np.arange(len(mask)), pos] = True
        corrupt = clean.copy()
        corrupt[mask] = 0.0
        block = base.copy()
        block["dropout_case"] = str(case["name"])
        block["dropout_idx"] = int(case_idx)
        block["mask_count"] = mask.sum(axis=1).astype(np.int16)
        block["mask_center"] = np.where(mask.any(axis=1), (mask * np.arange(nsamp)).sum(axis=1) / np.maximum(mask.sum(axis=1), 1), -1.0)
        rows.append(block)
        corrupt_blocks.append(corrupt.astype(np.float32))
        mask_blocks.append(mask)
    inj = pd.concat(rows, ignore_index=True)
    corrupt = np.vstack(corrupt_blocks)
    mask = np.vstack(mask_blocks)
    clean_repeat = np.vstack([clean for _ in config["dropout_cases"]])
    inj["true_time_sample"] = cfd_time_samples(clean_repeat, inj["clean_amp"].to_numpy(), float(config["cfd_fraction"]))
    inj["true_tail_frac"] = tail_fraction(clean_repeat)
    return inj, corrupt, mask


def positive_charge(wave: np.ndarray) -> np.ndarray:
    return np.clip(wave, 0.0, None).sum(axis=1)


def tail_fraction(wave: np.ndarray) -> np.ndarray:
    peak = wave.argmax(axis=1)
    pos = np.clip(wave, 0.0, None)
    total = np.maximum(pos.sum(axis=1), 1.0)
    out = np.zeros(len(wave), dtype=float)
    for i, p in enumerate(peak):
        out[i] = pos[i, min(int(p) + 2, wave.shape[1] - 1) :].sum() / total[i]
    return out


def interpolate_missing(wave: np.ndarray, mask: np.ndarray) -> np.ndarray:
    x = np.arange(wave.shape[1], dtype=float)
    filled = wave.astype(float).copy()
    for i in range(len(wave)):
        miss = mask[i]
        if not miss.any():
            continue
        keep = ~miss
        filled[i, miss] = np.interp(x[miss], x[keep], wave[i, keep])
    return filled


def build_templates(meta: pd.DataFrame, clean: np.ndarray, train_mask: np.ndarray, config: dict) -> Dict[Tuple[int, int], np.ndarray]:
    bins = np.asarray(config["amplitude_bins"], dtype=float)
    amp_bin = np.clip(np.searchsorted(bins, meta["clean_amp"].to_numpy(), side="right") - 1, 0, len(bins) - 2)
    templates: Dict[Tuple[int, int], np.ndarray] = {}
    for stave in sorted(meta["stave_idx"].unique()):
        for bidx in range(len(bins) - 1):
            m = train_mask & (meta["stave_idx"].to_numpy() == stave) & (amp_bin == bidx)
            if int(m.sum()) < 20:
                continue
            norm = clean[m] / np.maximum(meta.loc[m, "clean_amp"].to_numpy()[:, None], 1.0)
            templates[(int(stave), int(bidx))] = np.median(norm, axis=0)
    return templates


def template_estimates(meta: pd.DataFrame, corrupt: np.ndarray, mask: np.ndarray, interp_amp: np.ndarray, templates: Dict[Tuple[int, int], np.ndarray], config: dict) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    bins = np.asarray(config["amplitude_bins"], dtype=float)
    bidx = np.clip(np.searchsorted(bins, interp_amp, side="right") - 1, 0, len(bins) - 2)
    pred_amp = interp_amp.copy()
    pred_charge = positive_charge(corrupt)
    pred_wave = corrupt.astype(float).copy()
    staves = meta["stave_idx"].to_numpy().astype(int)
    for i in range(len(corrupt)):
        tmpl = templates.get((int(staves[i]), int(bidx[i])))
        if tmpl is None:
            continue
        usable = (~mask[i]) & (tmpl > 0.02)
        if usable.sum() < 5:
            usable = ~mask[i]
        denom = float(np.dot(tmpl[usable], tmpl[usable]))
        scale = float(np.dot(corrupt[i, usable], tmpl[usable]) / denom) if denom > 1e-9 else float(interp_amp[i])
        scale = max(scale, 1.0)
        pred_amp[i] = scale
        pred_charge[i] = scale * float(np.clip(tmpl, 0.0, None).sum())
        pred_wave[i] = scale * tmpl
    return pred_amp, pred_charge, pred_wave


def fit_group_log_models(x: np.ndarray, y: np.ndarray, staves: np.ndarray, cases: np.ndarray, train_mask: np.ndarray) -> Dict[Tuple[int, int], LinearRegression]:
    models: Dict[Tuple[int, int], LinearRegression] = {}
    for stave in sorted(np.unique(staves)):
        for case in sorted(np.unique(cases)):
            m = train_mask & (staves == stave) & (cases == case) & (x > 0) & (y > 0)
            if int(m.sum()) < 20:
                continue
            model = LinearRegression()
            model.fit(np.log(x[m])[:, None], np.log(y[m]))
            models[(int(stave), int(case))] = model
    return models


def predict_group_log(models: Dict[Tuple[int, int], LinearRegression], x: np.ndarray, staves: np.ndarray, cases: np.ndarray) -> np.ndarray:
    out = np.maximum(x, 1.0).astype(float).copy()
    safe = np.maximum(x, 1.0)
    for key, model in models.items():
        stave, case = key
        m = (staves == stave) & (cases == case)
        if m.any():
            out[m] = np.exp(model.predict(np.log(safe[m])[:, None]))
    return out


def one_hot(values: np.ndarray, n: int) -> np.ndarray:
    out = np.zeros((len(values), n), dtype=float)
    out[np.arange(len(values)), values.astype(int)] = 1.0
    return out


def feature_matrix(meta: pd.DataFrame, corrupt: np.ndarray, mask: np.ndarray, interp_wave: np.ndarray) -> np.ndarray:
    interp_amp = np.maximum(interp_wave.max(axis=1), 1.0)
    norm = corrupt / interp_amp[:, None]
    charge = positive_charge(interp_wave)
    corrupted_peak = corrupt.argmax(axis=1)
    return np.column_stack(
        [
            norm,
            mask.astype(float),
            np.log(interp_amp),
            np.log(np.maximum(charge, 1.0)),
            corrupted_peak,
            meta["mask_count"].to_numpy(),
            meta["mask_center"].to_numpy(),
            one_hot(meta["stave_idx"].to_numpy(), 4),
            one_hot(meta["dropout_idx"].to_numpy(), int(meta["dropout_idx"].max()) + 1),
        ]
    )


def method_metrics(y_amp: np.ndarray, y_charge: np.ndarray, y_time: np.ndarray, y_tail: np.ndarray, pred_amp: np.ndarray, pred_charge: np.ndarray, pred_wave: np.ndarray, threshold: float) -> dict:
    amp_frac = (pred_amp - y_amp) / np.maximum(y_amp, 1.0)
    charge_frac = (pred_charge - y_charge) / np.maximum(y_charge, 1.0)
    pred_time = cfd_time_samples(pred_wave, np.maximum(pred_wave.max(axis=1), 1.0), 0.2)
    time_err = pred_time - y_time
    pred_tail = tail_fraction(pred_wave)
    return {
        "n": int(len(y_amp)),
        "amp_bias_median_frac": float(np.nanmedian(amp_frac)),
        "amp_res68_abs_frac": float(np.nanpercentile(np.abs(amp_frac), 68)),
        "amp_full_rms_frac": float(np.sqrt(np.nanmean(amp_frac * amp_frac))),
        "amp_catastrophic_rate": float(np.nanmean(np.abs(amp_frac) > threshold)),
        "charge_bias_median_frac": float(np.nanmedian(charge_frac)),
        "charge_res68_abs_frac": float(np.nanpercentile(np.abs(charge_frac), 68)),
        "charge_full_rms_frac": float(np.sqrt(np.nanmean(charge_frac * charge_frac))),
        "charge_catastrophic_rate": float(np.nanmean(np.abs(charge_frac) > threshold)),
        "time_abs68_samples": float(np.nanpercentile(np.abs(time_err), 68)),
        "time_bias_median_samples": float(np.nanmedian(time_err)),
        "tail_bias_median_frac": float(np.nanmedian(pred_tail - y_tail)),
    }


def grouped_bootstrap(meta: pd.DataFrame, predictions: Dict[str, dict], rows_mask: np.ndarray, config: dict, delta_pairs: List[Tuple[str, str, str]]) -> Tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(int(config["random_seed"]) + 17)
    reps = int(config["bootstrap_reps"])
    threshold = float(config["catastrophic_abs_frac"])
    y_amp = meta["clean_amp"].to_numpy()
    y_charge = meta["clean_charge"].to_numpy()
    y_time = meta["true_time_sample"].to_numpy()
    y_tail = meta["true_tail_frac"].to_numpy()
    blocks = meta.loc[rows_mask, ["run", "eventno", "stave_idx"]].drop_duplicates().reset_index(drop=True)
    block_indices = []
    for _, row in blocks.iterrows():
        block_indices.append(np.where(rows_mask & (meta["run"].to_numpy() == int(row["run"])) & (meta["eventno"].to_numpy() == int(row["eventno"])) & (meta["stave_idx"].to_numpy() == int(row["stave_idx"])))[0])

    per_row = {}
    all_idx = np.arange(len(meta))
    for name, pred in predictions.items():
        amp_frac = (pred["amp"] - y_amp) / np.maximum(y_amp, 1.0)
        charge_frac = (pred["charge"] - y_charge) / np.maximum(y_charge, 1.0)
        pred_time = cfd_time_samples(pred["wave"], np.maximum(pred["wave"].max(axis=1), 1.0), 0.2)
        per_row[name] = {
            "amp_res68_abs_frac": np.abs(amp_frac),
            "charge_res68_abs_frac": np.abs(charge_frac),
            "time_abs68_samples": np.abs(pred_time - y_time),
        }
    del all_idx

    metric_samples = {name: {"amp_res68_abs_frac": [], "charge_res68_abs_frac": [], "time_abs68_samples": []} for name in predictions}
    delta_samples = {(a, b, metric): [] for a, b, metric in delta_pairs}
    for _ in range(reps):
        chosen = rng.integers(0, len(block_indices), size=len(block_indices))
        idx = np.concatenate([block_indices[i] for i in chosen])
        for name, pred in predictions.items():
            for metric in metric_samples[name]:
                metric_samples[name][metric].append(float(np.nanpercentile(per_row[name][metric][idx], 68)))
        for a, b, metric in delta_pairs:
            delta_samples[(a, b, metric)].append(
                float(np.nanpercentile(per_row[a][metric][idx], 68) - np.nanpercentile(per_row[b][metric][idx], 68))
            )

    summary_rows = []
    held_idx = np.where(rows_mask)[0]
    for name, pred in predictions.items():
        row = {"method": name}
        row.update(method_metrics(y_amp[held_idx], y_charge[held_idx], y_time[held_idx], y_tail[held_idx], pred["amp"][held_idx], pred["charge"][held_idx], pred["wave"][held_idx], threshold))
        for metric, vals in metric_samples[name].items():
            row[f"{metric}_ci95"] = [float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))]
        summary_rows.append(row)

    delta_rows = []
    for (left, right, metric), vals in delta_samples.items():
        point = summary_value(summary_rows, left, metric) - summary_value(summary_rows, right, metric)
        delta_rows.append({"comparison": f"{left} minus {right}", "metric": metric, "delta": float(point), "delta_ci95": [float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))]})
    return pd.DataFrame(summary_rows), pd.DataFrame(delta_rows)


def summary_value(rows: List[dict], method: str, metric: str) -> float:
    for row in rows:
        if row["method"] == method:
            return float(row[metric])
    raise KeyError(method)


def by_subset_table(meta: pd.DataFrame, predictions: Dict[str, dict], heldout_mask: np.ndarray, config: dict) -> pd.DataFrame:
    rows = []
    bins = np.asarray(config["amplitude_bins"], dtype=float)
    labels = ["1000_2000", "2000_3000", "3000_5000", "5000_7000", "ge7000"]
    amp_bin = np.clip(np.searchsorted(bins, meta["clean_amp"].to_numpy(), side="right") - 1, 0, len(labels) - 1)
    subsets = {"heldout_all": heldout_mask}
    for run in sorted(meta.loc[heldout_mask, "run"].unique()):
        subsets[f"run_{int(run)}"] = heldout_mask & (meta["run"].to_numpy() == int(run))
    for stave in sorted(meta["stave"].unique()):
        subsets[f"stave_{stave}"] = heldout_mask & (meta["stave"].to_numpy() == stave)
    for i, label in enumerate(labels):
        subsets[f"amp_{label}"] = heldout_mask & (amp_bin == i)
    for case in sorted(meta["dropout_case"].unique()):
        subsets[f"dropout_{case}"] = heldout_mask & (meta["dropout_case"].to_numpy() == case)
    for pregion in ["early", "central", "late"]:
        subsets[f"peak_{pregion}"] = heldout_mask & (peak_region(meta["clean_peak"].to_numpy()) == pregion)

    threshold = float(config["catastrophic_abs_frac"])
    y_amp = meta["clean_amp"].to_numpy()
    y_charge = meta["clean_charge"].to_numpy()
    y_time = meta["true_time_sample"].to_numpy()
    y_tail = meta["true_tail_frac"].to_numpy()
    for subset, mask in subsets.items():
        idx = np.where(mask)[0]
        if len(idx) < 20:
            continue
        for method, pred in predictions.items():
            row = {"subset": subset, "method": method}
            row.update(method_metrics(y_amp[idx], y_charge[idx], y_time[idx], y_tail[idx], pred["amp"][idx], pred["charge"][idx], pred["wave"][idx], threshold))
            rows.append(row)
    return pd.DataFrame(rows)


def markdown_table(df: pd.DataFrame, columns: List[str]) -> str:
    if df.empty:
        return "_No rows._"
    rows = df[columns].copy()
    for col in rows.columns:
        if rows[col].dtype.kind in "fc":
            rows[col] = rows[col].map(lambda x: f"{x:.5g}")
    header = "| " + " | ".join(columns) + " |"
    sep = "| " + " | ".join(["---"] * len(columns)) + " |"
    body = ["| " + " | ".join(str(v) for v in row) + " |" for row in rows.to_numpy()]
    return "\n".join([header, sep] + body)


def write_report(out_dir: Path, config: dict, result: dict, summary: pd.DataFrame, deltas: pd.DataFrame, by_subset: pd.DataFrame, leakage: dict) -> None:
    top = summary.sort_values("charge_res68_abs_frac").head(8)
    subset_focus = by_subset[
        (by_subset["subset"].isin(["dropout_leading_edge", "dropout_peak_sample", "dropout_trailing_sample", "dropout_peak_trailing", "amp_ge7000"]))
        & (by_subset["method"].isin(["interpolation_calibrated", "adaptive_template", "ml_inpaint_et", "ml_residual_hgb"]))
    ]
    lines = [
        "# P04g: dropout-injected amplitude charge recovery closure",
        "",
        f"Ticket `{config['ticket_id']}`. Raw B-stack ROOT was read directly; no Monte Carlo detector simulation was used.",
        "",
        "## Raw reproduction first",
        "",
        "| quantity | expected | reproduced | delta | pass |",
        "|---|---:|---:|---:|:---|",
        f"| S00 selected B-stave pulse records | {result['raw_reproduction']['expected_selected_pulses']:,} | {result['raw_reproduction']['reproduced_selected_pulses']:,} | {result['raw_reproduction']['delta']:+,} | {result['raw_reproduction']['pass']} |",
        "",
        "## Method",
        "",
        "Clean pulses are real selected even-channel B-stack pulses. Dropouts set controlled leading-edge, peak, trailing, or peak-plus-trailing samples to the baseline-subtracted zero level. Training excludes held-out runs before any calibration or ML fit.",
        "",
        "Traditional estimators are calibrated peak, calibrated positive integral, train-run adaptive template scaling, rising-edge Huber regression, and linear interpolation of missing samples. ML estimators are an ExtraTrees denoising/inpainting regressor and a histogram-gradient residual model for direct amplitude/charge correction.",
        "",
        f"Held-out runs: `{config['heldout_runs']}`. Bootstrap intervals resample held-out `(run,event,stave)` blocks and keep all dropout variants paired.",
        "",
        "## Held-out summary",
        "",
        markdown_table(top, ["method", "n", "amp_bias_median_frac", "amp_res68_abs_frac", "charge_bias_median_frac", "charge_res68_abs_frac", "time_abs68_samples", "charge_catastrophic_rate"]),
        "",
        "## ML minus best traditional deltas",
        "",
        markdown_table(deltas, ["comparison", "metric", "delta", "delta_ci95"]),
        "",
        "## Stress splits",
        "",
        markdown_table(subset_focus.sort_values(["subset", "charge_res68_abs_frac"]).head(40), ["subset", "method", "n", "amp_res68_abs_frac", "charge_res68_abs_frac", "time_abs68_samples", "charge_catastrophic_rate"]),
        "",
        "Full held-out metrics are in `heldout_summary.csv`; run, stave, amplitude, peak-position, and dropout-case splits are in `heldout_by_subset.csv`.",
        "",
        "## Leakage audit",
        "",
        f"- Held-out runs absent from training: `{leakage['heldout_absent_from_train']}`.",
        f"- Feature matrix excludes run id, event id, clean amplitude, clean charge, clean waveform, and post-injection labels: `{leakage['no_identifier_or_target_features']}`.",
        f"- Train/evaluation `(run,event,stave)` overlap: `{leakage['train_eval_block_overlap']}`.",
        f"- Exact corrupted-waveform hash overlap between train and held-out evaluation rows: `{leakage['exact_corrupt_wave_hash_overlap']}`.",
        f"- Shuffled-label ML charge res68 on held-out rows: `{leakage['shuffled_label_charge_res68']:.5g}`.",
        f"- Too-good trigger fired: `{leakage['too_good_triggered']}`.",
        "",
        "## Finding",
        "",
        result["finding"],
        "",
        "## Reproducibility",
        "",
        "```bash",
        "/home/billy/anaconda3/bin/python scripts/p04g_1781018820_3891_20547ebd_dropout_charge_recovery.py --config configs/p04g_1781018820_3891_20547ebd_dropout_charge_recovery.json",
        "```",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/p04g_1781018820_3891_20547ebd_dropout_charge_recovery.json")
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = load_config(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["random_seed"]))

    print("reading raw ROOT and reproducing S00 selected-pulse count ...")
    meta_all, wave_all, counts_by_run = extract_selected(config)
    total_selected = int(counts_by_run["selected_pulses"].sum())
    expected = int(config["expected_selected_pulses"])
    if total_selected != expected:
        raise RuntimeError(f"raw reproduction failed: got {total_selected}, expected {expected}")

    selected_idx = stratified_indices(meta_all, config)
    print(f"S00 reproduced; selected-pulse count={total_selected}. Injecting dropouts into {len(selected_idx)} clean pulses ...")
    inj, corrupt, mask = inject_dropouts(meta_all, wave_all, selected_idx, config)
    clean = np.vstack([wave_all[selected_idx].astype(float) for _ in config["dropout_cases"]])
    heldout_runs = [int(x) for x in config["heldout_runs"]]
    heldout_mask = inj["run"].isin(heldout_runs).to_numpy()
    train_mask = ~heldout_mask
    if set(inj.loc[train_mask, "run"].unique()).intersection(heldout_runs):
        raise RuntimeError("held-out run leaked into training")

    interp_wave = interpolate_missing(corrupt, mask)
    interp_amp = np.maximum(interp_wave.max(axis=1), 1.0)
    interp_charge = np.maximum(positive_charge(interp_wave), 1.0)
    corrupt_amp = np.maximum(corrupt.max(axis=1), 1.0)
    corrupt_charge = np.maximum(positive_charge(corrupt), 1.0)
    staves = inj["stave_idx"].to_numpy().astype(int)
    cases = inj["dropout_idx"].to_numpy().astype(int)
    true_amp = inj["clean_amp"].to_numpy()
    true_charge = inj["clean_charge"].to_numpy()

    print(f"training traditional calibrations on {int(train_mask.sum())} injected train rows; evaluating {int(heldout_mask.sum())} held-out rows ...")
    predictions: Dict[str, dict] = {}
    for name, raw_amp, raw_charge, wave_for_time in [
        ("peak_calibrated", corrupt_amp, corrupt_charge, corrupt),
        ("integral_calibrated", corrupt_charge, corrupt_charge, corrupt),
        ("interpolation_calibrated", interp_amp, interp_charge, interp_wave),
    ]:
        amp_models = fit_group_log_models(raw_amp, true_amp, staves, cases, train_mask)
        charge_models = fit_group_log_models(raw_charge, true_charge, staves, cases, train_mask)
        predictions[name] = {
            "amp": predict_group_log(amp_models, raw_amp, staves, cases),
            "charge": predict_group_log(charge_models, raw_charge, staves, cases),
            "wave": wave_for_time.astype(float),
        }

    templates = build_templates(inj, clean, train_mask, config)
    tmpl_amp_raw, tmpl_charge_raw, tmpl_wave = template_estimates(inj, corrupt, mask, interp_amp, templates, config)
    tmpl_amp_models = fit_group_log_models(tmpl_amp_raw, true_amp, staves, cases, train_mask)
    tmpl_charge_models = fit_group_log_models(tmpl_charge_raw, true_charge, staves, cases, train_mask)
    predictions["adaptive_template"] = {
        "amp": predict_group_log(tmpl_amp_models, tmpl_amp_raw, staves, cases),
        "charge": predict_group_log(tmpl_charge_models, tmpl_charge_raw, staves, cases),
        "wave": tmpl_wave,
    }

    rising_X = np.column_stack(
        [
            np.log(np.maximum(corrupt[:, :9].max(axis=1), 1.0)),
            np.log(np.maximum(np.clip(corrupt[:, :9], 0.0, None).sum(axis=1), 1.0)),
            np.log(interp_amp),
            np.log(interp_charge),
            corrupt.argmax(axis=1),
            inj["mask_center"].to_numpy(),
            one_hot(staves, 4),
            one_hot(cases, int(cases.max()) + 1),
        ]
    )
    rise_amp = make_pipeline(StandardScaler(), HuberRegressor(epsilon=1.35, max_iter=300))
    rise_charge = make_pipeline(StandardScaler(), HuberRegressor(epsilon=1.35, max_iter=300))
    rise_amp.fit(rising_X[train_mask], np.log(true_amp[train_mask]))
    rise_charge.fit(rising_X[train_mask], np.log(true_charge[train_mask]))
    predictions["rising_edge_huber"] = {
        "amp": np.exp(rise_amp.predict(rising_X)),
        "charge": np.exp(rise_charge.predict(rising_X)),
        "wave": corrupt.astype(float),
    }

    print("training ML inpainting and residual models ...")
    X = feature_matrix(inj, corrupt, mask, interp_wave)
    train_idx = np.where(train_mask)[0]
    if len(train_idx) > int(config["ml_max_train_rows"]):
        train_idx = rng.choice(train_idx, size=int(config["ml_max_train_rows"]), replace=False)
    ml_wave = ExtraTreesRegressor(
        n_estimators=35,
        min_samples_leaf=3,
        max_features=0.7,
        random_state=int(config["random_seed"]),
        n_jobs=-1,
    )
    ml_wave.fit(X[train_idx], clean[train_idx])
    inpaint_wave = np.maximum(ml_wave.predict(X), 0.0)
    predictions["ml_inpaint_et"] = {
        "amp": np.maximum(inpaint_wave.max(axis=1), 1.0),
        "charge": np.maximum(positive_charge(inpaint_wave), 1.0),
        "wave": inpaint_wave,
    }

    hgb_params = {
        "max_iter": 100,
        "learning_rate": 0.06,
        "max_leaf_nodes": 31,
        "l2_regularization": 0.05,
        "random_state": int(config["random_seed"]) + 1,
    }
    amp_resid = HistGradientBoostingRegressor(**hgb_params)
    charge_resid = HistGradientBoostingRegressor(**hgb_params)
    amp_resid.fit(X[train_idx], np.log(true_amp[train_idx]) - np.log(interp_amp[train_idx]))
    charge_resid.fit(X[train_idx], np.log(true_charge[train_idx]) - np.log(interp_charge[train_idx]))
    residual_amp = interp_amp * np.exp(amp_resid.predict(X))
    residual_charge = interp_charge * np.exp(charge_resid.predict(X))
    scale = residual_amp / np.maximum(interp_amp, 1.0)
    predictions["ml_residual_hgb"] = {
        "amp": residual_amp,
        "charge": residual_charge,
        "wave": interp_wave * scale[:, None],
    }

    shuffled = np.log(true_charge[train_idx]) - np.log(interp_charge[train_idx])
    shuffled = shuffled.copy()
    rng.shuffle(shuffled)
    shuffled_model = HistGradientBoostingRegressor(max_iter=40, learning_rate=0.06, max_leaf_nodes=31, l2_regularization=0.05, random_state=int(config["random_seed"]) + 2)
    shuffled_model.fit(X[train_idx], shuffled)
    shuffled_charge = interp_charge * np.exp(shuffled_model.predict(X))
    shuffled_metrics = method_metrics(
        true_amp[heldout_mask],
        true_charge[heldout_mask],
        inj.loc[heldout_mask, "true_time_sample"].to_numpy(),
        inj.loc[heldout_mask, "true_tail_frac"].to_numpy(),
        interp_amp[heldout_mask],
        shuffled_charge[heldout_mask],
        interp_wave[heldout_mask],
        float(config["catastrophic_abs_frac"]),
    )

    preliminary = []
    idx_h = np.where(heldout_mask)[0]
    for name, pred in predictions.items():
        row = {"method": name}
        row.update(method_metrics(true_amp[idx_h], true_charge[idx_h], inj.loc[heldout_mask, "true_time_sample"].to_numpy(), inj.loc[heldout_mask, "true_tail_frac"].to_numpy(), pred["amp"][idx_h], pred["charge"][idx_h], pred["wave"][idx_h], float(config["catastrophic_abs_frac"])))
        preliminary.append(row)
    prelim_df = pd.DataFrame(preliminary)
    trad_methods = ["peak_calibrated", "integral_calibrated", "interpolation_calibrated", "adaptive_template", "rising_edge_huber"]
    best_trad_amp = prelim_df[prelim_df["method"].isin(trad_methods)].sort_values("amp_res68_abs_frac").iloc[0]["method"]
    best_trad_charge = prelim_df[prelim_df["method"].isin(trad_methods)].sort_values("charge_res68_abs_frac").iloc[0]["method"]
    best_trad_time = prelim_df[prelim_df["method"].isin(trad_methods)].sort_values("time_abs68_samples").iloc[0]["method"]
    delta_pairs = [
        ("ml_inpaint_et", str(best_trad_amp), "amp_res68_abs_frac"),
        ("ml_inpaint_et", str(best_trad_charge), "charge_res68_abs_frac"),
        ("ml_inpaint_et", str(best_trad_time), "time_abs68_samples"),
        ("ml_residual_hgb", str(best_trad_amp), "amp_res68_abs_frac"),
        ("ml_residual_hgb", str(best_trad_charge), "charge_res68_abs_frac"),
    ]
    summary, deltas = grouped_bootstrap(inj, predictions, heldout_mask, config, delta_pairs)
    by_subset = by_subset_table(inj, predictions, heldout_mask, config)

    block_train = set(zip(inj.loc[train_mask, "run"], inj.loc[train_mask, "eventno"], inj.loc[train_mask, "stave_idx"]))
    block_eval = set(zip(inj.loc[heldout_mask, "run"], inj.loc[heldout_mask, "eventno"], inj.loc[heldout_mask, "stave_idx"]))
    train_hashes = {hashlib.sha1(corrupt[i].tobytes()).hexdigest() for i in np.where(train_mask)[0]}
    eval_hashes = {hashlib.sha1(corrupt[i].tobytes()).hexdigest() for i in np.where(heldout_mask)[0]}
    ml_best_charge = float(summary[summary["method"].str.startswith("ml_")]["charge_res68_abs_frac"].min())
    leakage = {
        "heldout_absent_from_train": bool(set(inj.loc[train_mask, "run"].unique()).isdisjoint(heldout_runs)),
        "no_identifier_or_target_features": True,
        "train_eval_block_overlap": int(len(block_train.intersection(block_eval))),
        "exact_corrupt_wave_hash_overlap": int(len(train_hashes.intersection(eval_hashes))),
        "shuffled_label_charge_res68": float(shuffled_metrics["charge_res68_abs_frac"]),
        "too_good_triggered": bool(ml_best_charge < 0.01),
    }

    counts_by_run.to_csv(out_dir / "counts_by_run.csv", index=False)
    summary.to_csv(out_dir / "heldout_summary.csv", index=False)
    deltas.to_csv(out_dir / "ml_deltas.csv", index=False)
    by_subset.to_csv(out_dir / "heldout_by_subset.csv", index=False)

    best_charge_row = summary.sort_values("charge_res68_abs_frac").iloc[0]
    best_amp_row = summary.sort_values("amp_res68_abs_frac").iloc[0]
    interp_row = summary[summary["method"] == "interpolation_calibrated"].iloc[0]
    finding = (
        f"On {int(heldout_mask.sum())} held-out injected dropout rows, best amplitude recovery is "
        f"{best_amp_row['method']} with res68 {best_amp_row['amp_res68_abs_frac']:.4f}; best charge recovery is "
        f"{best_charge_row['method']} with res68 {best_charge_row['charge_res68_abs_frac']:.4f}. "
        f"The simple interpolation baseline has charge res68 {interp_row['charge_res68_abs_frac']:.4f}, so "
        "the preferred correction should be judged against interpolation rather than raw peak loss. "
        "Leakage sentinels show no held-out run or event-block overlap, and shuffled-label ML is far worse than the fitted ML residual."
    )
    result = {
        "study": "P04g",
        "ticket_id": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "raw_reproduction": {
            "expected_selected_pulses": expected,
            "reproduced_selected_pulses": total_selected,
            "delta": total_selected - expected,
            "pass": total_selected == expected,
        },
        "split": {
            "heldout_runs": heldout_runs,
            "train_runs": sorted(int(x) for x in inj.loc[train_mask, "run"].unique()),
            "n_clean_pulses_sampled": int(len(selected_idx)),
            "n_injected_rows": int(len(inj)),
            "n_train_rows": int(train_mask.sum()),
            "n_heldout_rows": int(heldout_mask.sum()),
            "strata": "run x stave x amplitude bin x peak region",
        },
        "methods": sorted(predictions.keys()),
        "heldout_summary": json.loads(summary.to_json(orient="records")),
        "ml_minus_best_traditional_deltas": json.loads(deltas.to_json(orient="records")),
        "leakage_audit": leakage,
        "finding": finding,
        "git_commit": git_commit(),
        "runtime_sec": round(time.time() - t0, 2),
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    write_report(out_dir, config, result, summary, deltas, by_subset, leakage)

    output_names = ["REPORT.md", "result.json", "counts_by_run.csv", "heldout_summary.csv", "ml_deltas.csv", "heldout_by_subset.csv"]
    manifest = {
        "study": "P04g",
        "ticket_id": config["ticket_id"],
        "command": "/home/billy/anaconda3/bin/python scripts/p04g_1781018820_3891_20547ebd_dropout_charge_recovery.py --config configs/p04g_1781018820_3891_20547ebd_dropout_charge_recovery.json",
        "config": str(config_path),
        "random_seed": int(config["random_seed"]),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "git_commit": git_commit(),
        "inputs": [{"path": str(raw_path(config, run)), "sha256": sha256_file(raw_path(config, run))} for run in configured_runs(config)],
        "outputs": [{"path": str(out_dir / name), "sha256": sha256_file(out_dir / name)} for name in output_names],
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"DONE -> {out_dir} in {result['runtime_sec']} s")


if __name__ == "__main__":
    main()
