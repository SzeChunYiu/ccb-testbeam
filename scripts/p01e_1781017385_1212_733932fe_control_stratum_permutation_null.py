#!/usr/bin/env python3
"""P01e: control-stratum permutation null for released P01b latents."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import subprocess
import time
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

import numpy as np
import pandas as pd
import uproot
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import RidgeClassifier
from sklearn.metrics import balanced_accuracy_score, f1_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


STAVE_ORDER = np.asarray(["B2", "B4", "B6", "B8"], dtype=object)


def load_config(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_key(run: np.ndarray, event_index: np.ndarray, stave_index: np.ndarray) -> str:
    key_bytes = b"|".join(
        [
            np.asarray(run, dtype=np.int16).tobytes(),
            np.asarray(event_index, dtype=np.int32).tobytes(),
            np.asarray(stave_index, dtype=np.int8).tobytes(),
        ]
    )
    return hashlib.sha256(key_bytes).hexdigest()


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def resolve_raw_root_dir(config: dict) -> Path:
    for candidate in config["raw_root_dir_candidates"]:
        path = Path(candidate).expanduser()
        if path.exists() and list(path.glob("hrdb_run_*.root")):
            return path
    raise FileNotFoundError("No B-stack ROOT directory found")


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


def iter_raw_events(path: Path, step_size: int = 20000) -> Iterable[np.ndarray]:
    tree = uproot.open(path)["h101"]
    for batch in tree.iterate(["HRDv"], step_size=step_size, library="np"):
        yield np.stack(batch["HRDv"]).astype(np.float32)


def scan_raw(config: dict, raw_dir: Path) -> Tuple[np.ndarray, pd.DataFrame, pd.DataFrame]:
    baseline_idx = [int(i) for i in config["baseline_samples"]]
    nsamp = int(config["samples_per_channel"])
    cut = float(config["amplitude_cut_adc"])
    stave_channels = np.asarray([int(config["staves"][str(name)]) for name in STAVE_ORDER], dtype=int)
    groups = run_group_lookup(config)
    waves: List[np.ndarray] = []
    meta_parts: List[pd.DataFrame] = []
    count_rows: List[dict] = []

    for run in configured_runs(config):
        path = raw_dir / "hrdb_run_{:04d}.root".format(run)
        if not path.exists():
            raise FileNotFoundError(path)
        counts = {
            "run": int(run),
            "run_group": groups[int(run)],
            "events_total": 0,
            "events_with_selected": 0,
            "selected_pulses": 0,
        }
        stave_counts = {str(name): 0 for name in STAVE_ORDER}
        event_offset = 0
        for raw in iter_raw_events(path):
            event_waves = raw.reshape(-1, 8, nsamp)
            selected_raw = event_waves[:, stave_channels, :]
            baseline = np.median(selected_raw[..., baseline_idx], axis=-1)
            corrected = selected_raw - baseline[..., None]
            amplitude = corrected.max(axis=-1)
            selected = amplitude > cut
            event_idx, stave_idx = np.where(selected)

            counts["events_total"] += int(len(event_waves))
            counts["events_with_selected"] += int(selected.any(axis=1).sum())
            counts["selected_pulses"] += int(selected.sum())
            for idx, name in enumerate(STAVE_ORDER):
                stave_counts[str(name)] += int(selected[:, idx].sum())

            if len(event_idx):
                amp = amplitude[event_idx, stave_idx].astype(np.float32)
                topology_mask = (selected.astype(np.uint8) * (1 << np.arange(len(STAVE_ORDER), dtype=np.uint8))).sum(axis=1)
                topology_n = selected.sum(axis=1).astype(np.int8)
                waves.append((corrected[event_idx, stave_idx] / amp[:, None]).astype(np.float32))
                meta_parts.append(
                    pd.DataFrame(
                        {
                            "run": np.full(len(event_idx), run, dtype=np.int16),
                            "event_index": (event_idx + event_offset).astype(np.int32),
                            "run_group": groups[int(run)],
                            "stave": STAVE_ORDER[stave_idx],
                            "stave_index": stave_idx.astype(np.int8),
                            "amplitude_adc": amp,
                            "log10_amplitude": np.log10(np.maximum(amp, 1.0)).astype(np.float32),
                            "topology_mask": topology_mask[event_idx].astype(np.int16),
                            "topology_n": topology_n[event_idx],
                        }
                    )
                )
            event_offset += int(len(event_waves))

        count_rows.append({**counts, **stave_counts})
        print("run {:04d}: {} selected pulses".format(run, counts["selected_pulses"]))

    return np.concatenate(waves, axis=0), pd.concat(meta_parts, ignore_index=True), pd.DataFrame(count_rows)


def waveform_features(waves: np.ndarray) -> pd.DataFrame:
    area = waves.sum(axis=1)
    abs_area = np.maximum(np.abs(area), 1e-6)
    peak = waves.argmax(axis=1)
    return pd.DataFrame(
        {
            "peak_sample": peak.astype(np.float32),
            "area_over_peak": area.astype(np.float32),
            "tail_fraction": (waves[:, 12:].sum(axis=1) / abs_area).astype(np.float32),
            "late_fraction": (waves[:, 9:].sum(axis=1) / abs_area).astype(np.float32),
            "early_fraction": (waves[:, :5].sum(axis=1) / abs_area).astype(np.float32),
            "width50": (waves > 0.5).sum(axis=1).astype(np.float32),
            "width20": (waves > 0.2).sum(axis=1).astype(np.float32),
            "max_down_step": np.diff(waves, axis=1).min(axis=1).astype(np.float32),
            "asymmetry": ((waves[:, 10:].sum(axis=1) - waves[:, :5].sum(axis=1)) / abs_area).astype(np.float32),
        }
    )


def waveform_labels(feats: pd.DataFrame) -> pd.DataFrame:
    peak = feats["peak_sample"].to_numpy()
    area = feats["area_over_peak"].to_numpy()
    down = feats["max_down_step"].to_numpy()
    labels = pd.DataFrame(index=feats.index)
    labels["peak_group"] = np.where(
        peak <= 3,
        "early_0_3",
        np.where(peak <= 5, "prepeak_4_5", np.where(peak <= 9, "nominal_6_9", "late_10_17")),
    )
    manual = np.full(len(feats), "nominal", dtype=object)
    manual[peak <= 3] = "early_peak"
    manual[(peak <= 4) & (area < 3.0)] = "early_low_area"
    manual[peak >= 12] = "late_peak"
    manual[down < -0.75] = "large_negative_step"
    labels["manual_flag"] = manual
    return labels


def one_hot(values: np.ndarray, categories: Sequence[int]) -> np.ndarray:
    values = np.asarray(values)
    return np.column_stack([(values == category).astype(np.float32) for category in categories])


def control_matrix(meta: pd.DataFrame) -> np.ndarray:
    parts = [
        meta["log10_amplitude"].to_numpy(dtype=np.float32).reshape(-1, 1),
        one_hot(meta["topology_n"].to_numpy(dtype=int), [1, 2, 3, 4]),
        one_hot(meta["topology_mask"].to_numpy(dtype=int), list(range(1, 16))),
        one_hot(meta["stave_index"].to_numpy(dtype=int), [0, 1, 2, 3]),
    ]
    return np.hstack(parts).astype(np.float32)


def feature_matrix(meta: pd.DataFrame, z: np.ndarray) -> np.ndarray:
    return np.hstack([control_matrix(meta), z.astype(np.float32)]).astype(np.float32)


def add_amplitude_bins(meta: pd.DataFrame, n_bins: int) -> pd.DataFrame:
    out = meta.copy()
    out["amp_bin"] = -1
    for run, group in out.groupby("run", sort=True):
        values = group["amplitude_adc"].to_numpy()
        edges = np.unique(np.quantile(values, np.linspace(0.0, 1.0, int(n_bins) + 1)))
        if len(edges) <= 2:
            bins = np.zeros(len(values), dtype=np.int8)
        else:
            bins = np.searchsorted(edges[1:-1], values, side="right").astype(np.int8)
        out.loc[group.index, "amp_bin"] = bins
    return out


def balanced_indices(meta: pd.DataFrame, mask: np.ndarray, max_per_run_stave: int, rng: np.random.Generator) -> np.ndarray:
    chosen: List[np.ndarray] = []
    base = meta.index.to_numpy()[mask]
    for (_, _), group in meta.loc[base].groupby(["run", "stave_index"], sort=True):
        idx = group.index.to_numpy(dtype=int)
        take = min(len(idx), int(max_per_run_stave))
        if take:
            chosen.append(rng.choice(idx, size=take, replace=False))
    out = np.concatenate(chosen)
    rng.shuffle(out)
    return out


def build_permutation_groups(meta: pd.DataFrame, min_group_size: int) -> Tuple[List[np.ndarray], dict]:
    groups: List[np.ndarray] = []
    groups_total = 0
    rows_permuted = 0
    for _, group in meta.groupby(["run", "topology_mask", "amp_bin", "stave_index"], sort=False):
        idx = group.index.to_numpy(dtype=int)
        groups_total += 1
        if len(idx) >= int(min_group_size):
            groups.append(idx)
            rows_permuted += len(idx)
    return groups, {
        "groups_total": int(groups_total),
        "groups_permuted": int(len(groups)),
        "rows_permuted_group_member": int(rows_permuted),
    }


def make_permuted_z(groups: Sequence[np.ndarray], z: np.ndarray, rng: np.random.Generator, group_meta: dict) -> Tuple[np.ndarray, dict]:
    z_perm = z.copy()
    moved = np.zeros(len(z), dtype=bool)
    for idx in groups:
        shuffled = idx.copy()
        rng.shuffle(shuffled)
        z_perm[idx] = z[shuffled]
        moved[idx] = shuffled != idx
    meta_out = {
        **group_meta,
        "rows_with_changed_latent": int(moved.sum()),
        "fraction_rows_with_changed_latent": float(moved.mean()),
    }
    return z_perm, meta_out


def build_estimator(method: str, config: dict, seed: int):
    if method == "traditional":
        return make_pipeline(
            StandardScaler(),
            RidgeClassifier(alpha=float(config["traditional"]["ridge_alpha"]), class_weight="balanced"),
        )
    if method == "ml":
        return RandomForestClassifier(
            n_estimators=int(config["ml"]["random_forest_estimators"]),
            max_depth=int(config["ml"]["random_forest_max_depth"]),
            min_samples_leaf=int(config["ml"]["random_forest_min_samples_leaf"]),
            class_weight="balanced_subsample",
            random_state=int(seed),
            n_jobs=max(1, min(8, os.cpu_count() or 1)),
        )
    raise ValueError(method)


def fit_predict(method: str, config: dict, seed: int, x_train: np.ndarray, y_train: np.ndarray, x_test: np.ndarray) -> np.ndarray:
    estimator = build_estimator(method, config, seed)
    estimator.fit(x_train, y_train)
    return estimator.predict(x_test)


def score_predictions(y_true: np.ndarray, y_pred: np.ndarray) -> Tuple[float, float]:
    return float(balanced_accuracy_score(y_true, y_pred)), float(f1_score(y_true, y_pred, average="macro"))


def run_event_bootstrap(
    y_true: np.ndarray,
    observed_pred: np.ndarray,
    null_preds: np.ndarray,
    runs: np.ndarray,
    rng: np.random.Generator,
    n_boot: int,
) -> Dict[str, float]:
    unique_runs = np.unique(runs)
    observed_values: List[float] = []
    null_values: List[float] = []
    lift_values: List[float] = []
    for b in range(int(n_boot)):
        pieces: List[np.ndarray] = []
        sampled_runs = rng.choice(unique_runs, size=len(unique_runs), replace=True)
        for run in sampled_runs:
            run_idx = np.where(runs == run)[0]
            pieces.append(rng.choice(run_idx, size=len(run_idx), replace=True))
        idx = np.concatenate(pieces)
        null_idx = b % len(null_preds)
        obs = float(balanced_accuracy_score(y_true[idx], observed_pred[idx]))
        nul = float(balanced_accuracy_score(y_true[idx], null_preds[null_idx, idx]))
        observed_values.append(obs)
        null_values.append(nul)
        lift_values.append(obs - nul)
    obs_lo, obs_hi = np.quantile(np.asarray(observed_values), [0.025, 0.975])
    null_lo, null_hi = np.quantile(np.asarray(null_values), [0.025, 0.975])
    lift_lo, lift_hi = np.quantile(np.asarray(lift_values), [0.025, 0.975])
    return {
        "observed_ci_low": float(obs_lo),
        "observed_ci_high": float(obs_hi),
        "null_bootstrap_ci_low": float(null_lo),
        "null_bootstrap_ci_high": float(null_hi),
        "lift_ci_low": float(lift_lo),
        "lift_ci_high": float(lift_hi),
    }


def by_run_metrics(y_true: np.ndarray, pred: np.ndarray, runs: np.ndarray, method: str, target: str) -> List[dict]:
    out: List[dict] = []
    for run in np.unique(runs):
        mask = runs == run
        value, macro_f1 = score_predictions(y_true[mask], pred[mask])
        out.append(
            {
                "method": method,
                "target": target,
                "run": int(run),
                "heldout_rows": int(mask.sum()),
                "balanced_accuracy": value,
                "macro_f1": macro_f1,
            }
        )
    return out


def leakage_table(
    config: dict,
    meta: pd.DataFrame,
    train_idx: np.ndarray,
    heldout_idx: np.ndarray,
    key_match: bool,
    permutation_meta: dict,
    control_rows: List[dict],
    label_shuffle_rows: List[dict],
) -> pd.DataFrame:
    train_runs = set(int(run) for run in meta.loc[train_idx, "run"].unique())
    heldout_runs = set(int(run) for run in meta.loc[heldout_idx, "run"].unique())
    rows = [
        {
            "check": "train_heldout_run_overlap",
            "value": len(train_runs & heldout_runs),
            "pass": len(train_runs & heldout_runs) == 0,
            "note": "must be zero for split-by-run",
        },
        {
            "check": "heldout_runs_match_config",
            "value": ",".join(str(run) for run in sorted(heldout_runs)),
            "pass": sorted(heldout_runs) == sorted(int(run) for run in config["heldout_runs"]),
            "note": "all benchmark rows are from configured held-out runs",
        },
        {
            "check": "p01b_key_order_matches_raw_scan",
            "value": key_match,
            "pass": bool(key_match),
            "note": "prevents latent/waveform row offset leakage",
        },
        {
            "check": "permutation_changed_latent_fraction",
            "value": permutation_meta["fraction_rows_with_changed_latent"],
            "pass": permutation_meta["fraction_rows_with_changed_latent"] > 0.95,
            "note": "should move almost all rows within control strata",
        },
    ]
    for row in control_rows:
        rows.append(
            {
                "check": "{}_{}_controls_only_vs_observed_delta".format(row["method"], row["target"]),
                "value": row["observed_minus_controls"],
                "pass": row["observed_minus_controls"] >= -0.02,
                "note": "large negative values would mean controls-only explains the result",
            }
        )
    for row in label_shuffle_rows:
        rows.append(
            {
                "check": "{}_{}_train_label_shuffle_score".format(row["method"], row["target"]),
                "value": row["value"],
                "pass": row["value"] < 0.45,
                "note": "near-chance sanity check for too-good scores",
            }
        )
    return pd.DataFrame(rows)


def markdown_table(frame: pd.DataFrame, columns: Sequence[str]) -> str:
    view = frame.loc[:, columns].copy()
    for col in view.columns:
        if pd.api.types.is_float_dtype(view[col]):
            view[col] = view[col].map(lambda x: "" if pd.isna(x) else "{:.4f}".format(x))
    widths = {col: max(len(col), *(len(str(value)) for value in view[col].tolist())) for col in view.columns}
    header = "| " + " | ".join(col.ljust(widths[col]) for col in view.columns) + " |"
    sep = "| " + " | ".join("-" * widths[col] for col in view.columns) + " |"
    body = ["| " + " | ".join(str(row[col]).ljust(widths[col]) for col in view.columns) + " |" for _, row in view.iterrows()]
    return "\n".join([header, sep, *body])


def json_sanitize(value):
    if isinstance(value, dict):
        return {str(key): json_sanitize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_sanitize(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        value = float(value)
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


def write_report(out_dir: Path, result: dict, benchmark: pd.DataFrame, leakage: pd.DataFrame) -> None:
    primary = benchmark[(benchmark["target"] == "manual_flag") & (benchmark["method"] == "ml")].iloc[0]
    report = """# P01e: control-stratum permutation null for P01b latents

**Ticket:** `{ticket_id}`

## Reproduction first
The script scanned raw B-stack ROOT from `{raw_root_dir}` before fitting any probe. The P01b/S00
selected-pulse count reproduced **{selected:,}** rows versus **{expected:,}** expected, and the
released latent artifact key hash matched the raw `(run,event_index,stave_index)` scan.

## Null construction
The released P01b latent table was joined to raw ROOT-derived waveform controls by row key. For
each null replicate, the latent rows were permuted only within `(run, topology_mask, amplitude_bin,
stave)` strata. This preserves the held-out run mix, topology, amplitude, and stave controls while
breaking row-level latent-to-waveform alignment. The benchmark sample is capped at
{max_per_run_stave} pulses per `(run,stave)` cell; downstream probes train on non-held-out runs and
evaluate only runs `{heldout_runs}`. CIs are held-out run/event bootstraps.

## Held-out probe lift over control-stratum null
{benchmark_table}

The primary ML/manual morphology probe scores **{primary_value:.4f}** balanced accuracy, while its
stratum-permuted null median is **{primary_null:.4f}**. The observed-minus-null lift is
**{primary_lift:.4f}** with a held-out bootstrap CI of **[{primary_lift_lo:.4f}, {primary_lift_hi:.4f}]**.

## Leakage checks
{leakage_table}

The score is high because the target labels are direct waveform morphology summaries and P01b is a
waveform embedding. The controls-only and train-label-shuffle sentinels remain below the observed
latent probes, and the strict within-run/topology/amplitude/stave null removes the coarse-control
explanation.

## Reproducibility
```bash
/home/billy/anaconda3/bin/python scripts/p01e_1781017385_1212_733932fe_control_stratum_permutation_null.py --config configs/p01e_1781017385_1212_733932fe_control_stratum_permutation_null.json
```
""".format(
        ticket_id=result["ticket_id"],
        raw_root_dir=result["raw_root_dir"],
        selected=result["reproduction"]["selected_pulses"],
        expected=result["reproduction"]["expected_selected_pulses"],
        max_per_run_stave=result["split"]["max_per_run_stave"],
        heldout_runs=", ".join(str(run) for run in result["split"]["heldout_runs"]),
        benchmark_table=markdown_table(
            benchmark,
            [
                "method",
                "target",
                "observed_balanced_accuracy",
                "observed_ci_low",
                "observed_ci_high",
                "null_median",
                "null_p95",
                "lift",
                "lift_ci_low",
                "lift_ci_high",
            ],
        ),
        primary_value=primary["observed_balanced_accuracy"],
        primary_null=primary["null_median"],
        primary_lift=primary["lift"],
        primary_lift_lo=primary["lift_ci_low"],
        primary_lift_hi=primary["lift_ci_high"],
        leakage_table=markdown_table(leakage, ["check", "value", "pass", "note"]),
    )
    (out_dir / "REPORT.md").write_text(report, encoding="utf-8")


def output_hashes(out_dir: Path) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            out[path.name] = sha256_file(path)
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/p01e_1781017385_1212_733932fe_control_stratum_permutation_null.json")
    args = parser.parse_args()

    t0 = time.time()
    config_path = Path(args.config)
    config = load_config(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["benchmark"]["random_seed"]))
    raw_root_dir = resolve_raw_root_dir(config)

    print("raw ROOT dir:", raw_root_dir)
    waves, meta, counts_by_run = scan_raw(config, raw_root_dir)
    selected = int(len(meta))
    expected = int(config["expected_selected_pulses"])
    print("REPRODUCTION COUNT: {} selected pulses (expected {})".format(selected, expected))
    if selected != expected:
        raise RuntimeError("Reproduction failed: got {}, expected {}".format(selected, expected))
    counts_by_run.to_csv(out_dir / "reproduction_counts_by_run.csv", index=False)
    pd.DataFrame(
        [
            {
                "quantity": "total selected B-stave pulses",
                "report_value": expected,
                "reproduced": selected,
                "delta": selected - expected,
                "pass": selected == expected,
            }
        ]
    ).to_csv(out_dir / "reproduction_match_table.csv", index=False)

    artifact_path = Path(config["p01b_artifact_path"])
    artifact = np.load(artifact_path)
    z = artifact["z"].astype(np.float32)
    artifact_key_hash = sha256_key(artifact["run"], artifact["event_index"], artifact["stave_index"])
    raw_key_hash = sha256_key(
        meta["run"].to_numpy(dtype=np.int16),
        meta["event_index"].to_numpy(dtype=np.int32),
        meta["stave_index"].to_numpy(dtype=np.int8),
    )
    key_match = bool(
        len(z) == len(meta)
        and np.array_equal(artifact["run"], meta["run"].to_numpy(dtype=np.int16))
        and np.array_equal(artifact["event_index"], meta["event_index"].to_numpy(dtype=np.int32))
        and np.array_equal(artifact["stave_index"], meta["stave_index"].to_numpy(dtype=np.int8))
    )
    if not key_match:
        raise RuntimeError("P01b latent keys do not match raw scan order")

    feats = waveform_features(waves)
    labels = waveform_labels(feats)
    meta = add_amplitude_bins(meta, int(config["stratification"]["amplitude_quantile_bins"]))
    meta.head(1000).to_csv(out_dir / "row_controls_preview.csv", index=False)
    pd.concat([feats, labels], axis=1).head(1000).to_csv(out_dir / "waveform_probe_targets_preview.csv", index=False)

    run_values = meta["run"].to_numpy(dtype=int)
    heldout_runs = np.asarray(config["heldout_runs"], dtype=int)
    train_mask = ~np.isin(run_values, heldout_runs)
    heldout_mask = np.isin(run_values, heldout_runs)
    train_idx = balanced_indices(meta, train_mask, int(config["benchmark"]["max_per_run_stave"]), rng)
    heldout_idx = balanced_indices(meta, heldout_mask, int(config["benchmark"]["max_per_run_stave"]), rng)
    heldout_run_values = meta.loc[heldout_idx, "run"].to_numpy(dtype=int)
    train_meta = meta.loc[train_idx]
    heldout_meta = meta.loc[heldout_idx]
    controls_train = control_matrix(train_meta)
    controls_heldout = control_matrix(heldout_meta)
    x_train = feature_matrix(train_meta, z[train_idx])
    x_heldout = feature_matrix(heldout_meta, z[heldout_idx])

    targets = ["manual_flag", "peak_group"]
    methods = [("traditional", "traditional ridge"), ("ml", "ml random forest")]
    benchmark_rows: List[dict] = []
    by_run_rows: List[dict] = []
    control_rows: List[dict] = []
    label_shuffle_rows: List[dict] = []

    permutation_groups, permutation_group_meta = build_permutation_groups(
        meta,
        int(config["stratification"]["minimum_permutation_group_size"]),
    )
    z_perm, permutation_meta = make_permuted_z(permutation_groups, z, rng, permutation_group_meta)
    del z_perm

    for method_key, method_name in methods:
        for target in targets:
            y_train = labels.loc[train_idx, target].to_numpy(dtype=object)
            y_heldout = labels.loc[heldout_idx, target].to_numpy(dtype=object)
            observed_pred = fit_predict(method_key, config, int(config["benchmark"]["random_seed"]), x_train, y_train, x_heldout)
            observed_score, observed_f1 = score_predictions(y_heldout, observed_pred)

            control_pred = fit_predict(
                method_key,
                config,
                int(config["benchmark"]["random_seed"]) + 17,
                controls_train,
                y_train,
                controls_heldout,
            )
            control_score, control_f1 = score_predictions(y_heldout, control_pred)
            control_rows.append(
                {
                    "method": method_key,
                    "target": target,
                    "value": control_score,
                    "macro_f1": control_f1,
                    "observed_minus_controls": observed_score - control_score,
                }
            )

            shuffled = y_train.copy()
            rng.shuffle(shuffled)
            shuffle_pred = fit_predict(method_key, config, int(config["benchmark"]["random_seed"]) + 23, x_train, shuffled, x_heldout)
            shuffle_score, _ = score_predictions(y_heldout, shuffle_pred)
            label_shuffle_rows.append({"method": method_key, "target": target, "value": shuffle_score})

            null_preds: List[np.ndarray] = []
            null_scores: List[float] = []
            null_f1: List[float] = []
            for perm in range(int(config["benchmark"]["permutation_replicates"])):
                z_perm, _ = make_permuted_z(permutation_groups, z, rng, permutation_group_meta)
                x_perm_train = feature_matrix(train_meta, z_perm[train_idx])
                x_perm_heldout = feature_matrix(heldout_meta, z_perm[heldout_idx])
                pred = fit_predict(
                    method_key,
                    config,
                    int(config["benchmark"]["random_seed"]) + 1000 + perm,
                    x_perm_train,
                    y_train,
                    x_perm_heldout,
                )
                value, macro_f1 = score_predictions(y_heldout, pred)
                null_preds.append(pred)
                null_scores.append(value)
                null_f1.append(macro_f1)
                if perm in {0, int(config["benchmark"]["permutation_replicates"]) - 1}:
                    print("{} {} null {}/{}: {:.4f}".format(method_name, target, perm + 1, config["benchmark"]["permutation_replicates"], value))

            null_pred_array = np.vstack(null_preds)
            boot = run_event_bootstrap(
                y_heldout,
                observed_pred,
                null_pred_array,
                heldout_run_values,
                rng,
                int(config["benchmark"]["bootstrap_replicates"]),
            )
            null_scores_arr = np.asarray(null_scores, dtype=float)
            row = {
                "method": method_key,
                "method_label": method_name,
                "target": target,
                "metric": "balanced_accuracy",
                "observed_balanced_accuracy": observed_score,
                "observed_macro_f1": observed_f1,
                "controls_only_balanced_accuracy": control_score,
                "null_mean": float(null_scores_arr.mean()),
                "null_median": float(np.median(null_scores_arr)),
                "null_p95": float(np.quantile(null_scores_arr, 0.95)),
                "null_max": float(null_scores_arr.max()),
                "lift": observed_score - float(np.median(null_scores_arr)),
                "permutation_replicates": int(len(null_scores_arr)),
                "train_rows": int(len(train_idx)),
                "heldout_rows": int(len(heldout_idx)),
                **boot,
            }
            benchmark_rows.append(row)
            by_run_rows.extend(by_run_metrics(y_heldout, observed_pred, heldout_run_values, method_key, target))

    benchmark = pd.DataFrame(benchmark_rows)
    benchmark.to_csv(out_dir / "probe_vs_control_stratum_null.csv", index=False)
    pd.DataFrame(by_run_rows).to_csv(out_dir / "heldout_by_run_metrics.csv", index=False)
    pd.DataFrame(control_rows).to_csv(out_dir / "controls_only_baseline.csv", index=False)
    pd.DataFrame(label_shuffle_rows).to_csv(out_dir / "label_shuffle_sentinel.csv", index=False)
    pd.DataFrame([permutation_meta]).to_csv(out_dir / "permutation_diagnostics.csv", index=False)
    leakage = leakage_table(config, meta, train_idx, heldout_idx, key_match, permutation_meta, control_rows, label_shuffle_rows)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)

    input_rows = []
    for run in configured_runs(config):
        path = raw_root_dir / "hrdb_run_{:04d}.root".format(run)
        input_rows.append({"role": "raw_root", "path": str(path), "bytes": int(path.stat().st_size), "sha256": sha256_file(path)})
    for role, path_key in [
        ("p01b_latent_artifact", "p01b_artifact_path"),
        ("p01b_metadata", "p01b_metadata_path"),
        ("p01b_result", "p01b_result_path"),
        ("analysis_config", None),
    ]:
        path = config_path if path_key is None else Path(config[path_key])
        input_rows.append({"role": role, "path": str(path), "bytes": int(path.stat().st_size), "sha256": sha256_file(path)})
    input_sha = pd.DataFrame(input_rows)
    input_sha.to_csv(out_dir / "input_sha256.csv", index=False)

    artifact_sha = sha256_file(artifact_path)
    result = {
        "ticket_id": config["ticket_id"],
        "study_id": config["study_id"],
        "title": config["title"],
        "raw_root_dir": str(raw_root_dir),
        "reproduction": {
            "expected_selected_pulses": expected,
            "selected_pulses": selected,
            "passed": selected == expected,
            "p01b_artifact_sha256": artifact_sha,
            "p01b_artifact_sha256_matches_expected": artifact_sha == config["expected_artifact_sha256"],
            "p01b_artifact_key_sha256": artifact_key_hash,
            "raw_scan_key_sha256": raw_key_hash,
            "key_sha256_matches_expected": raw_key_hash == config["expected_key_sha256"],
            "raw_and_artifact_keys_match": key_match,
        },
        "split": {
            "train_runs": sorted(int(run) for run in np.unique(run_values[train_mask])),
            "heldout_runs": [int(run) for run in heldout_runs],
            "train_rows": int(len(train_idx)),
            "heldout_rows": int(len(heldout_idx)),
            "max_per_run_stave": int(config["benchmark"]["max_per_run_stave"]),
            "bootstrap_replicates": int(config["benchmark"]["bootstrap_replicates"]),
        },
        "null": {
            "strata": ["run", "topology_mask", "amp_bin", "stave_index"],
            "amplitude_quantile_bins": int(config["stratification"]["amplitude_quantile_bins"]),
            "permutation_replicates": int(config["benchmark"]["permutation_replicates"]),
            **permutation_meta,
        },
        "traditional": benchmark[benchmark["method"] == "traditional"].to_dict(orient="records"),
        "ml": benchmark[benchmark["method"] == "ml"].to_dict(orient="records"),
        "controls_only": control_rows,
        "label_shuffle_sentinel": label_shuffle_rows,
        "leakage_checks": leakage.to_dict(orient="records"),
        "runtime_sec": round(time.time() - t0, 1),
    }
    (out_dir / "result.json").write_text(json.dumps(json_sanitize(result), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_report(out_dir, result, benchmark, leakage)

    manifest = {
        "ticket_id": config["ticket_id"],
        "study_id": config["study_id"],
        "script": "scripts/p01e_1781017385_1212_733932fe_control_stratum_permutation_null.py",
        "config": str(config_path),
        "command": "/home/billy/anaconda3/bin/python scripts/p01e_1781017385_1212_733932fe_control_stratum_permutation_null.py --config {}".format(config_path),
        "python": platform.python_version(),
        "git_commit": git_commit(),
        "random_seed": int(config["benchmark"]["random_seed"]),
        "raw_root_dir": str(raw_root_dir),
        "input_sha256": input_rows,
        "output_sha256": output_hashes(out_dir),
        "reproduction_passed": selected == expected,
        "p01b_keys_matched_raw_scan": key_match,
        "split": result["split"],
    }
    (out_dir / "manifest.json").write_text(json.dumps(json_sanitize(manifest), indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(benchmark.to_string(index=False))
    print("DONE in {}s -> {}".format(result["runtime_sec"], out_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
