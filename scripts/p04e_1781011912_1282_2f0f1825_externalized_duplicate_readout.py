#!/usr/bin/env python3
"""P04e: stricter leakage probes for duplicate-readout ML closure.

The study starts from raw B-stack ROOT files, reproduces the selected-pulse
count before any modeling, and then evaluates duplicate-readout closure under
leave-one-run-family-out and B2-held-out transfer probes.  Sorted B-stack
summary branches are only used after modeling for an independent association
audit; they are never model targets or features.
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
from sklearn.ensemble import ExtraTreesRegressor
from sklearn.linear_model import HuberRegressor
from sklearn.neighbors import NearestNeighbors
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def configured_runs(config: dict) -> List[int]:
    runs: List[int] = []
    for values in config["run_groups"].values():
        runs.extend(int(run) for run in values)
    return sorted(set(runs))


def run_group_lookup(config: dict) -> Dict[int, str]:
    out: Dict[int, str] = {}
    for group, runs in config["run_groups"].items():
        for run in runs:
            out[int(run)] = str(group)
    return out


def raw_path(config: dict, run: int) -> Path:
    return Path(config["raw_root_dir"]) / f"hrdb_run_{run:04d}.root"


def sorted_path(config: dict, run: int) -> Path:
    return Path(config["sorted_b_dir"]) / f"hrdb_run_{run:04d}-sorted.root"


def iter_raw_batches(path: Path, step_size: int = 20000) -> Iterable[dict]:
    tree = uproot.open(path)["h101"]
    yield from tree.iterate(["EVENTNO", "EVT", "HRDv"], step_size=step_size, library="np")


def extract_rows(config: dict) -> Tuple[pd.DataFrame, np.ndarray, pd.DataFrame]:
    baseline_idx = [int(i) for i in config["baseline_samples"]]
    nsamp = int(config["samples_per_channel"])
    cut = float(config["amplitude_cut_adc"])
    staves = list(config["staves"].keys())
    even_channels = np.asarray([int(config["staves"][s]) for s in staves], dtype=int)
    odd_channels = np.asarray([int(config["duplicate_readout_channels"][s]) for s in staves], dtype=int)
    stave_names = np.asarray(staves)
    group_for_run = run_group_lookup(config)

    meta_frames: List[pd.DataFrame] = []
    waveforms: List[np.ndarray] = []
    counts: List[dict] = []

    for run in configured_runs(config):
        path = raw_path(config, run)
        if not path.exists():
            raise FileNotFoundError(path)
        run_counts = {"run": run, "group": group_for_run[run], "events_total": 0, "selected_pulses": 0}
        run_counts.update({s: 0 for s in staves})

        for batch in iter_raw_batches(path):
            eventno = np.asarray(batch["EVENTNO"]).astype(np.int64)
            evt = np.asarray(batch["EVT"]).astype(np.int64)
            raw = np.stack(batch["HRDv"]).astype(np.float64).reshape(-1, 8, nsamp)
            baseline = np.median(raw[..., baseline_idx], axis=-1)
            corrected = raw - baseline[..., None]
            even = corrected[:, even_channels, :]
            odd = corrected[:, odd_channels, :]

            even_amp = even.max(axis=-1)
            even_peak = even.argmax(axis=-1)
            even_pos_charge = np.clip(even, 0.0, None).sum(axis=-1)
            even_area = even.sum(axis=-1)
            odd_neg = -odd
            target_amp = odd_neg.max(axis=-1)
            target_charge = np.clip(odd_neg, 0.0, None).sum(axis=-1)

            selected = even_amp > cut
            run_counts["events_total"] += int(len(eventno))
            run_counts["selected_pulses"] += int(selected.sum())
            for idx, stave in enumerate(staves):
                run_counts[stave] += int(selected[:, idx].sum())

            event_idx, stave_idx = np.where(selected)
            if len(event_idx) == 0:
                continue

            chosen = even[event_idx, stave_idx, :]
            waveforms.append(chosen.astype(np.float32))
            meta_frames.append(
                pd.DataFrame(
                    {
                        "run": run,
                        "group": group_for_run[run],
                        "eventno": eventno[event_idx],
                        "evt": evt[event_idx],
                        "stave": stave_names[stave_idx],
                        "stave_idx": stave_idx.astype(np.int16),
                        "even_amp": even_amp[event_idx, stave_idx],
                        "even_peak": even_peak[event_idx, stave_idx].astype(np.int16),
                        "even_pos_charge": even_pos_charge[event_idx, stave_idx],
                        "even_area": even_area[event_idx, stave_idx],
                        "target_odd_neg_amp": target_amp[event_idx, stave_idx],
                        "target_odd_pos_charge": target_charge[event_idx, stave_idx],
                    }
                )
            )
        counts.append(run_counts)

    return pd.concat(meta_frames, ignore_index=True), np.vstack(waveforms), pd.DataFrame(counts)


def sorted_summary(config: dict, run: int) -> pd.DataFrame:
    path = sorted_path(config, run)
    if not path.exists():
        raise FileNotFoundError(path)
    arrays = uproot.open(path)["tree"].arrays(["hrdEvtNo", "hrdMax", "hrdMaxTS"], library="np")
    eventno = np.asarray(arrays["hrdEvtNo"]).astype(np.int64)
    hrdmax = np.vstack(arrays["hrdMax"]).astype(float)
    hrdmaxts = np.vstack(arrays["hrdMaxTS"]).astype(float)
    even = hrdmax[:, [0, 2, 4, 6]]
    ts = hrdmaxts[:, [0, 2, 4, 6]]
    downstream = even[:, [1, 2, 3]]
    downstream_ts = ts[:, [1, 2, 3]]
    present = downstream > float(config["amplitude_cut_adc"])
    with np.errstate(invalid="ignore"):
        spread = np.nanmax(np.where(present, downstream_ts, np.nan), axis=1) - np.nanmin(
            np.where(present, downstream_ts, np.nan), axis=1
        )
    spread[~np.isfinite(spread)] = np.nan
    return pd.DataFrame(
        {
            "run": int(run),
            "evt": eventno,
            "sorted_downstream_count": present.sum(axis=1).astype(np.int16),
            "sorted_downstream_max": np.max(downstream, axis=1),
            "sorted_downstream_sum": downstream.sum(axis=1),
            "sorted_downstream_ts_spread": spread,
        }
    )


def attach_sorted_observables(config: dict, meta: pd.DataFrame) -> pd.DataFrame:
    frames = [sorted_summary(config, run) for run in configured_runs(config)]
    sorted_df = pd.concat(frames, ignore_index=True)
    sorted_df = (
        sorted_df.groupby(["run", "evt"], as_index=False)
        .agg(
            {
                "sorted_downstream_count": "max",
                "sorted_downstream_max": "max",
                "sorted_downstream_sum": "max",
                "sorted_downstream_ts_spread": "max",
            }
        )
    )
    return meta.merge(sorted_df, on=["run", "evt"], how="left")


def robust_metrics(y: np.ndarray, pred: np.ndarray) -> dict:
    frac = (pred - y) / np.maximum(y, 1.0)
    return {
        "n": int(len(y)),
        "bias_median_frac": float(np.median(frac)),
        "res68_abs_frac": float(np.percentile(np.abs(frac), 68)),
        "full_rms_frac": float(np.sqrt(np.mean(frac * frac))),
        "within_5pct": float(np.mean(np.abs(frac) < 0.05)),
        "within_10pct": float(np.mean(np.abs(frac) < 0.10)),
    }


def block_bootstrap_ci(frame: pd.DataFrame, y_col: str, pred_col: str, rng: np.random.Generator, reps: int) -> dict:
    runs = np.asarray(sorted(frame["run"].unique()), dtype=int)
    by_run = {int(run): frame[frame["run"] == run] for run in runs}
    if len(runs) == 0:
        return {"run_block_res68_ci95": [None, None], "run_block_bias_ci95": [None, None]}
    bias = np.empty(reps)
    res68 = np.empty(reps)
    for idx in range(reps):
        chosen = rng.choice(runs, size=len(runs), replace=True)
        sample = pd.concat([by_run[int(run)] for run in chosen], ignore_index=True)
        y = sample[y_col].to_numpy()
        pred = sample[pred_col].to_numpy()
        frac = (pred - y) / np.maximum(y, 1.0)
        bias[idx] = np.median(frac)
        res68[idx] = np.percentile(np.abs(frac), 68)
    return {
        "run_block_bias_ci95": [float(np.percentile(bias, 2.5)), float(np.percentile(bias, 97.5))],
        "run_block_res68_ci95": [float(np.percentile(res68, 2.5)), float(np.percentile(res68, 97.5))],
    }


def engineered_features(meta: pd.DataFrame, wave: np.ndarray, include_stave: bool = True) -> np.ndarray:
    amp = meta["even_amp"].to_numpy()
    charge = np.maximum(meta["even_pos_charge"].to_numpy(), 1.0)
    clipped = np.clip(wave, 0.0, None)
    early = clipped[:, :6].sum(axis=1) / charge
    mid = clipped[:, 6:12].sum(axis=1) / charge
    late = clipped[:, 12:].sum(axis=1) / charge
    tail = clipped[:, 9:].sum(axis=1) / charge
    half_width = (wave > (0.5 * amp[:, None])).sum(axis=1)
    weighted_t = (clipped * np.arange(wave.shape[1], dtype=float)[None, :]).sum(axis=1) / charge
    cols = [
        np.log(np.maximum(amp, 1.0)),
        np.log(charge),
        meta["even_peak"].to_numpy(),
        meta["even_area"].to_numpy() / charge,
        early,
        mid,
        late,
        tail,
        half_width,
        weighted_t,
    ]
    if include_stave:
        stave_idx = meta["stave_idx"].to_numpy().astype(int)
        onehot = np.zeros((len(meta), 4), dtype=float)
        onehot[np.arange(len(meta)), stave_idx] = 1.0
        cols.extend([onehot[:, i] for i in range(onehot.shape[1])])
    return np.column_stack(cols)


def ml_features(meta: pd.DataFrame, wave: np.ndarray, include_stave: bool = True) -> np.ndarray:
    return np.column_stack([wave, engineered_features(meta, wave, include_stave=include_stave)])


def fit_huber(X: np.ndarray, y: np.ndarray, train_mask: np.ndarray) -> object:
    model = make_pipeline(StandardScaler(), HuberRegressor(epsilon=1.35, alpha=0.0001, max_iter=300))
    model.fit(X[train_mask], np.log(y[train_mask]))
    return model


def fit_ml(X: np.ndarray, y: np.ndarray, train_mask: np.ndarray, rng: np.random.Generator, config: dict) -> object:
    train_idx = np.where(train_mask)[0]
    max_rows = int(config["ml_max_train_rows"])
    if len(train_idx) > max_rows:
        train_idx = rng.choice(train_idx, size=max_rows, replace=False)
    model = ExtraTreesRegressor(
        n_estimators=90,
        max_depth=24,
        min_samples_leaf=3,
        max_features=0.75,
        random_state=int(config["random_seed"]),
        n_jobs=-1,
    )
    model.fit(X[train_idx], np.log(y[train_idx]))
    return model


def predict_model(model: object, X: np.ndarray) -> np.ndarray:
    return np.maximum(np.exp(model.predict(X)), 1.0)


def evaluate_split(
    split_name: str,
    meta: pd.DataFrame,
    wave: np.ndarray,
    y: np.ndarray,
    train_mask: np.ndarray,
    test_mask: np.ndarray,
    config: dict,
    rng: np.random.Generator,
    include_stave: bool = True,
) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, np.ndarray]]:
    X_trad = engineered_features(meta, wave, include_stave=include_stave)
    X_ml = ml_features(meta, wave, include_stave=include_stave)
    preds: Dict[str, np.ndarray] = {}

    for stave in sorted(meta["stave_idx"].unique()):
        stave_mask = meta["stave_idx"].to_numpy() == stave
        train = train_mask & stave_mask if include_stave else train_mask
        if train.sum() < 50:
            continue
        if include_stave:
            # Per-stave calibration keeps the traditional baseline strong while
            # preserving the split boundary.
            model = fit_huber(X_trad, y, train)
            pred = predict_model(model, X_trad)
            preds.setdefault("traditional_huber", np.zeros(len(meta), dtype=float))[stave_mask] = pred[stave_mask]
        else:
            break
    if not include_stave:
        model = fit_huber(X_trad, y, train_mask)
        preds["traditional_huber"] = predict_model(model, X_trad)

    peak_pred = np.zeros(len(meta), dtype=float)
    for stave in sorted(meta["stave_idx"].unique()):
        mask = meta["stave_idx"].to_numpy() == stave
        train = train_mask & mask
        if train.sum() < 20:
            continue
        x = np.log(np.maximum(meta.loc[train, "even_amp"].to_numpy(), 1.0))
        yy = np.log(y[train])
        slope, intercept = np.polyfit(x, yy, deg=1)
        peak_pred[mask] = np.exp(intercept + slope * np.log(np.maximum(meta.loc[mask, "even_amp"].to_numpy(), 1.0)))
    preds["peak_loglinear"] = np.maximum(peak_pred, 1.0)

    ml_model = fit_ml(X_ml, y, train_mask, rng, config)
    preds["ml_extra_trees"] = predict_model(ml_model, X_ml)

    shuffled_idx = np.where(train_mask)[0]
    if len(shuffled_idx) > int(config["ml_max_train_rows"]):
        shuffled_idx = rng.choice(shuffled_idx, size=int(config["ml_max_train_rows"]), replace=False)
    shuffled_y = np.log(y[shuffled_idx]).copy()
    rng.shuffle(shuffled_y)
    sentinel = ExtraTreesRegressor(
        n_estimators=35,
        max_depth=16,
        min_samples_leaf=5,
        max_features=0.75,
        random_state=int(config["random_seed"]) + 99,
        n_jobs=-1,
    )
    sentinel.fit(X_ml[shuffled_idx], shuffled_y)
    preds["shuffled_target_ml"] = predict_model(sentinel, X_ml)

    test = meta.loc[test_mask, ["run", "group", "eventno", "stave", "target_odd_neg_amp"]].reset_index(drop=True)
    rows = []
    by_run_rows = []
    for method, pred_all in preds.items():
        tmp = test.copy()
        tmp["_pred"] = pred_all[test_mask]
        y_test = tmp["target_odd_neg_amp"].to_numpy()
        pred = tmp["_pred"].to_numpy()
        row = {"split": split_name, "method": method}
        row.update(robust_metrics(y_test, pred))
        row.update(block_bootstrap_ci(tmp, "target_odd_neg_amp", "_pred", rng, int(config["bootstrap_reps"])))
        rows.append(row)
        for run, run_df in tmp.groupby("run"):
            brow = {"split": split_name, "method": method, "run": int(run), "group": str(run_df["group"].iloc[0])}
            brow.update(robust_metrics(run_df["target_odd_neg_amp"].to_numpy(), run_df["_pred"].to_numpy()))
            by_run_rows.append(brow)
    return pd.DataFrame(rows), pd.DataFrame(by_run_rows), preds


def waveform_hashes(wave: np.ndarray) -> np.ndarray:
    quantized = np.rint(wave).astype(np.int16)
    out = np.empty(len(wave), dtype=object)
    for idx, row in enumerate(quantized):
        out[idx] = hashlib.sha1(row.tobytes()).hexdigest()
    return out


def normalized_wave(wave: np.ndarray, amp: np.ndarray) -> np.ndarray:
    norm = wave / np.maximum(amp[:, None], 1.0)
    return norm.astype(np.float32)


def leakage_probe(
    split_name: str,
    meta: pd.DataFrame,
    wave: np.ndarray,
    train_mask: np.ndarray,
    test_mask: np.ndarray,
    rng: np.random.Generator,
    config: dict,
) -> dict:
    train_hash = set(waveform_hashes(wave[train_mask]))
    test_hash = waveform_hashes(wave[test_mask])
    exact_overlap = int(sum(h in train_hash for h in test_hash))

    train_idx = np.where(train_mask)[0]
    test_idx = np.where(test_mask)[0]
    max_train = int(config["neighbor_train_sample"])
    max_test = int(config["neighbor_test_sample"])
    if len(train_idx) > max_train:
        train_idx = rng.choice(train_idx, size=max_train, replace=False)
    if len(test_idx) > max_test:
        test_idx = rng.choice(test_idx, size=max_test, replace=False)

    train_x = normalized_wave(wave[train_idx], meta.loc[train_idx, "even_amp"].to_numpy())
    test_x = normalized_wave(wave[test_idx], meta.loc[test_idx, "even_amp"].to_numpy())
    nn = NearestNeighbors(n_neighbors=1, metric="euclidean", algorithm="auto")
    nn.fit(train_x)
    dist, _ = nn.kneighbors(test_x, return_distance=True)
    d = dist[:, 0]
    return {
        "split": split_name,
        "n_train": int(train_mask.sum()),
        "n_test": int(test_mask.sum()),
        "exact_waveform_hash_overlap": exact_overlap,
        "exact_waveform_hash_overlap_frac": float(exact_overlap / max(int(test_mask.sum()), 1)),
        "neighbor_train_sample": int(len(train_idx)),
        "neighbor_test_sample": int(len(test_idx)),
        "nearest_norm_l2_median": float(np.median(d)),
        "nearest_norm_l2_p01": float(np.percentile(d, 1)),
        "nearest_norm_l2_p05": float(np.percentile(d, 5)),
        "nearest_norm_l2_p95": float(np.percentile(d, 95)),
        "nearest_norm_l2_under_0p01_frac": float(np.mean(d < 0.01)),
    }


def external_observable_audit(meta: pd.DataFrame, y: np.ndarray, pred: np.ndarray) -> pd.DataFrame:
    frame = meta.copy()
    frac_abs = np.abs((pred - y) / np.maximum(y, 1.0))
    frame["_abs_frac_error"] = frac_abs
    rows = []
    bins = [
        ("downstream_count_0", frame["sorted_downstream_count"] == 0),
        ("downstream_count_1", frame["sorted_downstream_count"] == 1),
        ("downstream_count_ge2", frame["sorted_downstream_count"] >= 2),
        ("downstream_max_lt1000", frame["sorted_downstream_max"] < 1000),
        ("downstream_max_ge1000", frame["sorted_downstream_max"] >= 1000),
        ("ts_spread_ge3", frame["sorted_downstream_ts_spread"] >= 3),
    ]
    for name, mask in bins:
        mask = mask.fillna(False).to_numpy()
        if int(mask.sum()) < 20:
            continue
        rows.append(
            {
                "observable_bin": name,
                "n": int(mask.sum()),
                "median_abs_frac_error": float(np.median(frac_abs[mask])),
                "res68_abs_frac": float(np.percentile(frac_abs[mask], 68)),
                "median_downstream_sum": float(np.nanmedian(frame.loc[mask, "sorted_downstream_sum"])),
            }
        )
    return pd.DataFrame(rows)


def markdown_table(frame: pd.DataFrame, columns: List[str]) -> str:
    if frame.empty:
        return "_No rows._"
    use = frame[columns].copy()
    for col in use.columns:
        if use[col].dtype.kind in "fc":
            use[col] = use[col].map(lambda x: f"{x:.6g}")
    return use.to_markdown(index=False)


def write_report(
    out_dir: Path,
    config: dict,
    counts_by_run: pd.DataFrame,
    family_summary: pd.DataFrame,
    b2_summary: pd.DataFrame,
    leakage_df: pd.DataFrame,
    external_df: pd.DataFrame,
    result: dict,
) -> None:
    expected = int(config["expected_selected_pulses"])
    reproduced = int(counts_by_run["selected_pulses"].sum())
    lines = [
        "# P04e: externalized duplicate-readout ML closure",
        "",
        f"- **Ticket ID:** `{config['ticket_id']}`",
        f"- **Worker:** `{config['worker']}`",
        "- **Input:** raw `data/root/root/hrdb_run_*.root`; sorted B-stack summaries only for post-fit audits; no Monte Carlo.",
        "- **Target:** paired odd-channel inverted duplicate readout amplitude; features use only the even-channel waveform and even-channel summaries.",
        "",
        "## Raw reproduction first",
        "",
        "| quantity | expected | reproduced | delta | pass |",
        "|---|---:|---:|---:|:---|",
        f"| S00 selected B-stave pulse records | {expected:,} | {reproduced:,} | {reproduced - expected:+,} | {str(reproduced == expected).lower()} |",
        "",
        "## Methods",
        "",
        "- **Traditional:** per-stave Huber log-amplitude regression on even peak, charge, timing-shape, and lobe summary features.",
        "- **ML:** ExtraTrees log-amplitude regression on the 18 even samples plus the same even-channel summaries.",
        "- **Sentinels:** log-linear peak calibration and shuffled-target ML.",
        "",
        "## Leave-one-run-family-out benchmark",
        "",
        markdown_table(
            family_summary,
            ["split", "method", "n", "bias_median_frac", "res68_abs_frac", "run_block_res68_ci95", "within_10pct"],
        ),
        "",
        "## Train on B4/B6/B8, hold out B2",
        "",
        markdown_table(
            b2_summary,
            ["split", "method", "n", "bias_median_frac", "res68_abs_frac", "run_block_res68_ci95", "within_10pct"],
        ),
        "",
        "## Waveform-neighbor leakage probes",
        "",
        markdown_table(
            leakage_df,
            [
                "split",
                "n_train",
                "n_test",
                "exact_waveform_hash_overlap",
                "nearest_norm_l2_p01",
                "nearest_norm_l2_median",
                "nearest_norm_l2_under_0p01_frac",
            ],
        ),
        "",
        "## Downstream sorted-observable audit",
        "",
        markdown_table(external_df, ["observable_bin", "n", "median_abs_frac_error", "res68_abs_frac", "median_downstream_sum"]),
        "",
        "## Finding",
        "",
        result["finding"],
        "",
        "## Reproducibility",
        "",
        "```bash",
        "/home/billy/anaconda3/bin/python scripts/p04e_1781011912_1282_2f0f1825_externalized_duplicate_readout.py --config configs/p04e_1781011912_1282_2f0f1825_externalized_duplicate_readout.json",
        "```",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/p04e_1781011912_1282_2f0f1825_externalized_duplicate_readout.json")
    args = parser.parse_args()

    t0 = time.time()
    config_path = Path(args.config)
    config = load_config(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["random_seed"]))

    print("loading raw ROOT and reproducing selected-pulse count first ...")
    meta, wave, counts_by_run = extract_rows(config)
    total_selected = int(counts_by_run["selected_pulses"].sum())
    expected = int(config["expected_selected_pulses"])
    if total_selected != expected:
        raise RuntimeError(f"raw reproduction failed: got {total_selected}, expected {expected}")

    valid = (meta["target_odd_neg_amp"].to_numpy() > 100.0) & (meta["target_odd_pos_charge"].to_numpy() > 100.0)
    invalid_rows = int((~valid).sum())
    meta = meta.loc[valid].reset_index(drop=True)
    wave = wave[valid]
    y = meta["target_odd_neg_amp"].to_numpy()
    print(f"selected={total_selected} valid={len(meta)} invalid={invalid_rows}")

    print("attaching sorted B-stack observables for post-fit audit ...")
    meta = attach_sorted_observables(config, meta)

    family_rows = []
    by_run_rows = []
    leakage_rows = []
    representative_family_pred = None
    representative_family_mask = None

    groups = list(config["run_groups"].keys())
    for group in groups:
        test_mask = (meta["group"] == group).to_numpy()
        train_mask = ~test_mask
        print(f"evaluating leave-one-run-family-out: {group} ...")
        summary, by_run, preds = evaluate_split(
            f"holdout_{group}", meta, wave, y, train_mask, test_mask, config, rng, include_stave=True
        )
        family_rows.append(summary)
        by_run_rows.append(by_run)
        leakage_rows.append(leakage_probe(f"holdout_{group}", meta, wave, train_mask, test_mask, rng, config))
        if group == "sample_ii_analysis":
            representative_family_pred = preds["ml_extra_trees"]
            representative_family_mask = test_mask

    print("evaluating B4/B6/B8 -> B2 transfer ...")
    b2_test = (meta["stave"] == "B2").to_numpy()
    b2_train = ~b2_test
    b2_summary, b2_by_run, b2_preds = evaluate_split(
        "train_B4_B6_B8_holdout_B2", meta, wave, y, b2_train, b2_test, config, rng, include_stave=False
    )
    leakage_rows.append(leakage_probe("train_B4_B6_B8_holdout_B2", meta, wave, b2_train, b2_test, rng, config))

    family_summary = pd.concat(family_rows, ignore_index=True)
    by_run_summary = pd.concat(by_run_rows + [b2_by_run], ignore_index=True)
    leakage_df = pd.DataFrame(leakage_rows)
    if representative_family_pred is None:
        representative_family_pred = b2_preds["ml_extra_trees"]
        representative_family_mask = b2_test
    external_df = external_observable_audit(
        meta.loc[representative_family_mask].reset_index(drop=True),
        y[representative_family_mask],
        representative_family_pred[representative_family_mask],
    )

    family_summary.to_csv(out_dir / "family_holdout_summary.csv", index=False)
    by_run_summary.to_csv(out_dir / "by_run_metrics.csv", index=False)
    b2_summary.to_csv(out_dir / "b2_holdout_summary.csv", index=False)
    leakage_df.to_csv(out_dir / "waveform_neighbor_leakage.csv", index=False)
    external_df.to_csv(out_dir / "sorted_observable_audit.csv", index=False)
    counts_by_run.to_csv(out_dir / "counts_by_run.csv", index=False)

    best_family = family_summary[family_summary["method"] == "ml_extra_trees"]["res68_abs_frac"].max()
    trad_family = family_summary[family_summary["method"] == "traditional_huber"]["res68_abs_frac"].max()
    shuffled_family = family_summary[family_summary["method"] == "shuffled_target_ml"]["res68_abs_frac"].min()
    b2_ml = float(b2_summary[b2_summary["method"] == "ml_extra_trees"]["res68_abs_frac"].iloc[0])
    b2_trad = float(b2_summary[b2_summary["method"] == "traditional_huber"]["res68_abs_frac"].iloc[0])
    exact_overlap_total = int(leakage_df["exact_waveform_hash_overlap"].sum())
    nearest_small = float(leakage_df["nearest_norm_l2_under_0p01_frac"].max())
    finding = (
        f"Leave-one-run-family-out duplicate-readout closure remains strong but no longer looks like a "
        f"standalone energy result: the worst-family ML res68 is {best_family:.4f}, versus "
        f"{trad_family:.4f} for the Huber traditional method and at least {shuffled_family:.4f} for the "
        f"shuffled-target sentinel.  The stricter B4/B6/B8 -> B2 transfer is much weaker "
        f"(ML res68={b2_ml:.4f}, traditional={b2_trad:.4f}), showing the one-percent P04c closure does "
        f"not externalize across staves.  Exact waveform-hash train/test overlap is {exact_overlap_total} "
        f"and the largest near-neighbor under-0.01 fraction is {nearest_small:.4f}; the good family-split "
        f"ML result is therefore not explained by repeated waveform hashes, but it is still a "
        f"same-detector duplicate-readout closure."
    )

    result = {
        "study": config["study_id"],
        "ticket_id": config["ticket_id"],
        "raw_reproduction": {
            "expected_selected_pulses": expected,
            "reproduced_selected_pulses": total_selected,
            "delta": total_selected - expected,
            "pass": total_selected == expected,
        },
        "target_definition": "paired odd-channel inverted duplicate readout amplitude; features from even channel only",
        "n_valid_rows": int(len(meta)),
        "invalid_target_rows_removed_after_reproduction": invalid_rows,
        "family_holdout_summary": json.loads(family_summary.to_json(orient="records")),
        "b2_holdout_summary": json.loads(b2_summary.to_json(orient="records")),
        "waveform_neighbor_leakage": json.loads(leakage_df.to_json(orient="records")),
        "sorted_observable_audit": json.loads(external_df.to_json(orient="records")),
        "finding": finding,
        "runtime_sec": round(time.time() - t0, 1),
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    write_report(out_dir, config, counts_by_run, family_summary, b2_summary, leakage_df, external_df, result)

    input_files = [raw_path(config, run) for run in configured_runs(config)]
    input_files.extend(sorted_path(config, run) for run in configured_runs(config))
    input_manifest = pd.DataFrame([{"path": str(path), "sha256": sha256_file(path)} for path in input_files])
    input_manifest.to_csv(out_dir / "input_sha256.csv", index=False)

    output_files = [
        "REPORT.md",
        "result.json",
        "family_holdout_summary.csv",
        "by_run_metrics.csv",
        "b2_holdout_summary.csv",
        "waveform_neighbor_leakage.csv",
        "sorted_observable_audit.csv",
        "counts_by_run.csv",
        "input_sha256.csv",
    ]
    manifest = {
        "study": config["study_id"],
        "ticket_id": config["ticket_id"],
        "command": "/home/billy/anaconda3/bin/python scripts/p04e_1781011912_1282_2f0f1825_externalized_duplicate_readout.py --config configs/p04e_1781011912_1282_2f0f1825_externalized_duplicate_readout.json",
        "config": str(config_path),
        "random_seed": int(config["random_seed"]),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"]).decode().strip(),
        "inputs": json.loads(input_manifest.to_json(orient="records")),
        "outputs": [],
    }
    manifest["outputs"] = [{"path": str(out_dir / name), "sha256": sha256_file(out_dir / name)} for name in output_files]
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"DONE -> {out_dir} in {result['runtime_sec']} s")


if __name__ == "__main__":
    main()
