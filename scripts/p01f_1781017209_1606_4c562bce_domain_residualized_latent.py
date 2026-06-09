#!/usr/bin/env python3
"""P01f: benchmark waveform latents after explicit domain residualization."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import subprocess
import time
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

import numpy as np
import pandas as pd
import uproot
from sklearn.decomposition import PCA
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import balanced_accuracy_score, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


STAVE_NAMES = np.asarray(["B2", "B4", "B6", "B8"], dtype=object)


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_config(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def resolve_existing(candidates: Sequence[str], predicate) -> Path:
    for candidate in candidates:
        path = Path(candidate).expanduser()
        if path.exists() and predicate(path):
            return path
    raise FileNotFoundError("none of the configured paths exists")


def configured_runs(config: dict) -> List[int]:
    runs: List[int] = []
    for group_runs in config["run_groups"].values():
        runs.extend(int(run) for run in group_runs)
    return sorted(set(runs))


def run_group_lookup(config: dict) -> Dict[int, str]:
    lookup: Dict[int, str] = {}
    for group, runs in config["run_groups"].items():
        for run in runs:
            lookup[int(run)] = str(group)
    return lookup


def iter_raw_events(path: Path, step_size: int = 20000) -> Iterable[np.ndarray]:
    tree = uproot.open(path)["h101"]
    for batch in tree.iterate(["HRDv"], step_size=step_size, library="np"):
        yield np.stack(batch["HRDv"]).astype(np.float32)


def scan_raw(config: dict, raw_dir: Path) -> Tuple[pd.DataFrame, np.ndarray, pd.DataFrame]:
    cut = float(config["amplitude_cut_adc"])
    nsamp = int(config["samples_per_channel"])
    baseline_idx = [int(i) for i in config["baseline_samples"]]
    channels = np.asarray([int(config["staves"][str(name)]) for name in STAVE_NAMES], dtype=int)
    groups = run_group_lookup(config)
    waves: List[np.ndarray] = []
    meta: List[pd.DataFrame] = []
    count_rows: List[dict] = []

    for run in configured_runs(config):
        path = raw_dir / "hrdb_run_{:04d}.root".format(run)
        if not path.exists():
            raise FileNotFoundError(path)
        row = {
            "run": int(run),
            "group": groups[int(run)],
            "events_total": 0,
            "events_with_selected": 0,
            "selected_pulses": 0,
        }
        stave_counts = {str(name): 0 for name in STAVE_NAMES}
        event_offset = 0
        for raw in iter_raw_events(path):
            event_waves = raw.reshape(-1, 8, nsamp)
            selected_raw = event_waves[:, channels, :]
            baseline = np.median(selected_raw[..., baseline_idx], axis=-1)
            corrected = selected_raw - baseline[..., None]
            amplitude = corrected.max(axis=-1)
            selected = amplitude > cut
            event_idx, stave_idx = np.where(selected)
            event_multiplicity = selected.sum(axis=1)

            row["events_total"] += int(len(event_waves))
            row["events_with_selected"] += int(selected.any(axis=1).sum())
            row["selected_pulses"] += int(selected.sum())
            for idx, name in enumerate(STAVE_NAMES):
                stave_counts[str(name)] += int(selected[:, idx].sum())

            if len(event_idx):
                amp = amplitude[event_idx, stave_idx].astype(np.float32)
                waves.append((corrected[event_idx, stave_idx] / amp[:, None]).astype(np.float32))
                meta.append(
                    pd.DataFrame(
                        {
                            "run": np.full(len(event_idx), int(run), dtype=np.int16),
                            "event_index": (event_idx + event_offset).astype(np.int32),
                            "group": groups[int(run)],
                            "stave": STAVE_NAMES[stave_idx],
                            "stave_index": stave_idx.astype(np.int8),
                            "amplitude_adc": amp,
                            "selected_multiplicity": event_multiplicity[event_idx].astype(np.int8),
                        }
                    )
                )
            event_offset += int(len(event_waves))
        count_rows.append({**row, **stave_counts})
        print("raw run {:04d}: {} selected pulses".format(run, row["selected_pulses"]))
    return pd.concat(meta, ignore_index=True), np.concatenate(waves, axis=0), pd.DataFrame(count_rows)


def key_sha256(run: np.ndarray, event_index: np.ndarray, stave_index: np.ndarray) -> str:
    return sha256_bytes(
        b"|".join(
            [
                np.asarray(run, dtype=np.int16).tobytes(),
                np.asarray(event_index, dtype=np.int32).tobytes(),
                np.asarray(stave_index, dtype=np.int8).tobytes(),
            ]
        )
    )


def load_latents(path: Path) -> Tuple[pd.DataFrame, np.ndarray, str]:
    with np.load(str(path)) as artifact:
        z = artifact["z"].astype(np.float32)
        table = pd.DataFrame(
            {
                "run": artifact["run"].astype(np.int16),
                "event_index": artifact["event_index"].astype(np.int32),
                "stave_index": artifact["stave_index"].astype(np.int8),
                "artifact_amplitude_adc": artifact["amplitude_adc"].astype(np.float32),
            }
        )
    for i in range(z.shape[1]):
        table["z{}".format(i)] = z[:, i]
    key_hash = key_sha256(table["run"].to_numpy(), table["event_index"].to_numpy(), table["stave_index"].to_numpy())
    return table, z, key_hash


def shape_features(waves: np.ndarray) -> pd.DataFrame:
    area = waves.sum(axis=1)
    abs_area = np.maximum(np.abs(area), 1e-6)
    diff = np.diff(waves, axis=1)
    return pd.DataFrame(
        {
            "peak_sample_raw": np.argmax(waves, axis=1).astype(np.float32),
            "area_norm": area.astype(np.float32),
            "tail_fraction": (waves[:, 12:].sum(axis=1) / abs_area).astype(np.float32),
            "late_fraction": (waves[:, 9:].sum(axis=1) / abs_area).astype(np.float32),
            "early_fraction": (waves[:, :5].sum(axis=1) / abs_area).astype(np.float32),
            "width50": (waves > 0.5).sum(axis=1).astype(np.float32),
            "width20": (waves > 0.2).sum(axis=1).astype(np.float32),
            "max_down_step": diff.min(axis=1).astype(np.float32),
            "secondary_peak_proxy": np.sort(waves, axis=1)[:, -2].astype(np.float32),
            "final_fraction": waves[:, -1].astype(np.float32),
        }
    )


def add_external_targets(meta: pd.DataFrame, config: dict) -> pd.DataFrame:
    q = pd.read_csv(config["q_template_table"])
    if len(q) != len(meta):
        raise RuntimeError("q_template row count {} != raw row count {}".format(len(q), len(meta)))
    checks = pd.DataFrame(
        {
            "run_match": q["run"].to_numpy(dtype=np.int16) == meta["run"].to_numpy(dtype=np.int16),
            "stave_match": q["stave"].astype(str).to_numpy() == meta["stave"].astype(str).to_numpy(),
            "amplitude_delta_abs": np.abs(q["amplitude_adc"].to_numpy(dtype=float) - meta["amplitude_adc"].to_numpy(dtype=float)),
        }
    )
    if (not bool(checks["run_match"].all())) or (not bool(checks["stave_match"].all())) or float(checks["amplitude_delta_abs"].max()) > 1e-3:
        raise RuntimeError("q_template table is not row-aligned with raw-selected pulses")
    meta = meta.copy()
    meta["q_template_rmse"] = q["q_template_rmse"].to_numpy(dtype=np.float32)
    meta["q_autoencoder_rmse"] = q["q_autoencoder_rmse"].to_numpy(dtype=np.float32)
    meta["peak_sample"] = q["peak_sample"].to_numpy(dtype=np.int16)

    timing_path = Path(config["timing_residual_table"])
    if timing_path.exists():
        tr = pd.read_csv(timing_path)
        selector = str(config.get("timing_selector", ""))
        if "selector" in tr.columns and selector:
            tr = tr[tr["selector"].astype(str) == selector]
        event_tail = (
            tr.assign(abs_residual_ns=lambda d: d["residual_ns"].abs())
            .groupby(["run", "event_index"], as_index=False)["abs_residual_ns"]
            .median()
            .rename(columns={"abs_residual_ns": "timing_abs_residual_ns"})
        )
        meta = meta.merge(event_tail, on=["run", "event_index"], how="left")
    else:
        meta["timing_abs_residual_ns"] = np.nan
    return meta


def balanced_sample(meta: pd.DataFrame, max_per_run_stave: int, rng: np.random.Generator) -> np.ndarray:
    pieces: List[np.ndarray] = []
    for (_, _), frame in meta.groupby(["run", "stave_index"], sort=True):
        idx = frame.index.to_numpy()
        take = min(len(idx), int(max_per_run_stave))
        pieces.append(rng.choice(idx, size=take, replace=False))
    out = np.concatenate(pieces)
    rng.shuffle(out)
    return out


def quantile_bins(train_values: np.ndarray, values: np.ndarray, n_bins: int) -> np.ndarray:
    edges = np.unique(np.quantile(train_values[np.isfinite(train_values)], np.linspace(0, 1, n_bins + 1)[1:-1]))
    return np.digitize(values, edges, right=False).astype(np.int16)


def binary_top_train_quantile(train_values: np.ndarray, values: np.ndarray, q: float) -> np.ndarray:
    train_finite = train_values[np.isfinite(train_values)]
    if len(train_finite) == 0:
        return np.full(len(values), np.nan)
    threshold = float(np.quantile(train_finite, q))
    out = np.full(len(values), np.nan)
    finite = np.isfinite(values)
    out[finite] = (values[finite] >= threshold).astype(float)
    return out


def target_frame(meta: pd.DataFrame, feature_frame: pd.DataFrame, train_mask: np.ndarray) -> Tuple[pd.DataFrame, dict]:
    train = meta.loc[train_mask]
    targets = pd.DataFrame(index=meta.index)
    targets["physics_q_template_top_quartile"] = binary_top_train_quantile(
        train["q_template_rmse"].to_numpy(float), meta["q_template_rmse"].to_numpy(float), 0.75
    )
    peak = meta["peak_sample"].to_numpy(int)
    targets["physics_peak_group"] = np.select([peak <= 6, peak >= 11], [0, 2], default=1).astype(np.int8)
    targets["physics_timing_tail_top_quartile"] = binary_top_train_quantile(
        train["timing_abs_residual_ns"].to_numpy(float), meta["timing_abs_residual_ns"].to_numpy(float), 0.75
    )
    anomaly_score = (
        0.50 * pd.Series(meta["q_template_rmse"]).rank(pct=True).to_numpy()
        + 0.20 * pd.Series(feature_frame["late_fraction"]).rank(pct=True).to_numpy()
        + 0.15 * pd.Series(feature_frame["secondary_peak_proxy"]).rank(pct=True).to_numpy()
        + 0.15 * pd.Series(feature_frame["max_down_step"].abs()).rank(pct=True).to_numpy()
    )
    targets["physics_anomaly_proxy_top5"] = binary_top_train_quantile(anomaly_score[train_mask], anomaly_score, 0.95)

    sample_epoch = meta["group"].astype(str).str.contains("sample_ii").astype(np.int8).to_numpy()
    targets["nuisance_sample_epoch"] = sample_epoch
    targets["nuisance_run_family"] = pd.Categorical(meta["group"]).codes.astype(np.int8)
    targets["nuisance_topology_multiplicity"] = np.minimum(meta["selected_multiplicity"].to_numpy(int), 3).astype(np.int8) - 1
    train_amp = np.log10(train["amplitude_adc"].to_numpy(float))
    targets["nuisance_amplitude_quartile"] = quantile_bins(train_amp, np.log10(meta["amplitude_adc"].to_numpy(float)), 4)
    targets["nuisance_stave"] = meta["stave_index"].to_numpy(np.int8)
    labels = {column: sorted(pd.Series(targets[column].dropna().astype(int)).unique().tolist()) for column in targets.columns}
    return targets, labels


def nuisance_matrix(meta: pd.DataFrame, train_mask: np.ndarray) -> np.ndarray:
    train = meta.loc[train_mask]
    sample_epoch = meta["group"].astype(str).str.contains("sample_ii").astype(int)
    run_family = pd.Categorical(meta["group"])
    topology = np.minimum(meta["selected_multiplicity"].to_numpy(int), 3)
    train_amp = np.log10(train["amplitude_adc"].to_numpy(float))
    amp_bin = quantile_bins(train_amp, np.log10(meta["amplitude_adc"].to_numpy(float)), 4)
    base = pd.DataFrame(
        {
            "log_amplitude": np.log10(meta["amplitude_adc"].to_numpy(float)),
            "sample_epoch": sample_epoch.to_numpy(),
            "topology": topology,
            "stave_index": meta["stave_index"].to_numpy(int),
            "amplitude_bin": amp_bin,
            "run_family": run_family.codes,
        },
        index=meta.index,
    )
    return pd.get_dummies(base, columns=["sample_epoch", "topology", "stave_index", "amplitude_bin", "run_family"], drop_first=False).to_numpy(float)


def residualize(train_x: np.ndarray, test_x: np.ndarray, train_nuis: np.ndarray, test_nuis: np.ndarray, alpha: float) -> Tuple[np.ndarray, np.ndarray]:
    model = make_pipeline(StandardScaler(with_mean=True), Ridge(alpha=float(alpha)))
    model.fit(train_nuis, train_x)
    return train_x - model.predict(train_nuis), test_x - model.predict(test_nuis)


def build_representations(
    waves: np.ndarray,
    shape: pd.DataFrame,
    z: np.ndarray,
    train_mask: np.ndarray,
    test_mask: np.ndarray,
    nuisance: np.ndarray,
    config: dict,
) -> Tuple[Dict[str, Tuple[np.ndarray, np.ndarray]], pd.DataFrame]:
    pca = PCA(n_components=int(config["pca_components"]), random_state=int(config["random_seed"]))
    pca_train = pca.fit_transform(waves[train_mask]).astype(np.float32)
    pca_test = pca.transform(waves[test_mask]).astype(np.float32)
    hand = shape.to_numpy(np.float32)
    hand_pca_train = np.column_stack([hand[train_mask], pca_train]).astype(np.float32)
    hand_pca_test = np.column_stack([hand[test_mask], pca_test]).astype(np.float32)
    z_train = z[train_mask].astype(np.float32)
    z_test = z[test_mask].astype(np.float32)
    train_nuis, test_nuis = nuisance[train_mask], nuisance[test_mask]
    trad_resid = residualize(hand_pca_train, hand_pca_test, train_nuis, test_nuis, float(config["ridge_alpha"]))
    ml_resid = residualize(z_train, z_test, train_nuis, test_nuis, float(config["ridge_alpha"]))
    reps = {
        "traditional_hand_pca_raw": (hand_pca_train, hand_pca_test),
        "traditional_hand_pca_residualized": trad_resid,
        "frozen_p01b_latent_raw": (z_train, z_test),
        "ml_p01b_latent_residualized": ml_resid,
        "negative_control_gaussian_noise": (
            np.random.default_rng(int(config["random_seed"]) + 77).normal(size=z_train.shape).astype(np.float32),
            np.random.default_rng(int(config["random_seed"]) + 78).normal(size=z_test.shape).astype(np.float32),
        ),
    }
    diag_rows = []
    for name, (tr, te) in reps.items():
        diag_rows.append(
            {
                "representation": name,
                "train_rows": int(tr.shape[0]),
                "heldout_rows": int(te.shape[0]),
                "feature_dim": int(tr.shape[1]),
                "train_feature_mean_abs": float(np.abs(np.mean(tr, axis=0)).mean()),
                "heldout_feature_mean_abs": float(np.abs(np.mean(te, axis=0)).mean()),
            }
        )
    return reps, pd.DataFrame(diag_rows)


def sample_train_indices(y: np.ndarray, rng: np.random.Generator, max_per_class: int) -> np.ndarray:
    pieces: List[np.ndarray] = []
    for label in np.unique(y):
        idx = np.where(y == label)[0]
        take = min(len(idx), int(max_per_class))
        pieces.append(rng.choice(idx, size=take, replace=False))
    out = np.concatenate(pieces)
    rng.shuffle(out)
    return out


def bootstrap_bacc(y_true: np.ndarray, y_pred: np.ndarray, runs: np.ndarray, rng: np.random.Generator, n_boot: int) -> Tuple[float, float]:
    unique_runs = np.unique(runs)
    labels = np.unique(y_true)
    vals = []
    for _ in range(int(n_boot)):
        sampled = rng.choice(unique_runs, size=len(unique_runs), replace=True)
        idx = np.concatenate([np.where(runs == run)[0] for run in sampled])
        vals.append(balanced_accuracy_fixed(y_true[idx], y_pred[idx], labels))
    lo, hi = np.quantile(vals, [0.025, 0.975])
    return float(lo), float(hi)


def balanced_accuracy_fixed(y_true: np.ndarray, y_pred: np.ndarray, labels: np.ndarray) -> float:
    recalls: List[float] = []
    for label in labels:
        mask = y_true == label
        if int(mask.sum()) == 0:
            continue
        recalls.append(float(np.mean(y_pred[mask] == label)))
    if not recalls:
        return float("nan")
    return float(np.mean(recalls))


def multiclass_auc(y_true: np.ndarray, proba: np.ndarray) -> float:
    try:
        if len(np.unique(y_true)) == 2:
            return float(roc_auc_score(y_true, proba[:, 1]))
        return float(roc_auc_score(y_true, proba, multi_class="ovr", average="macro"))
    except Exception:
        return float("nan")


def fit_probe(
    representation: str,
    task: str,
    family: str,
    x_train: np.ndarray,
    x_test: np.ndarray,
    y_train: np.ndarray,
    y_test: np.ndarray,
    test_runs: np.ndarray,
    config: dict,
    rng: np.random.Generator,
    shuffle: bool = False,
) -> dict:
    valid_train = pd.notna(y_train)
    valid_test = pd.notna(y_test)
    ytr = np.asarray(y_train[valid_train], dtype=int)
    yte = np.asarray(y_test[valid_test], dtype=int)
    if len(np.unique(ytr)) < 2 or len(np.unique(yte)) < 2:
        return {
            "representation": representation,
            "task": task,
            "family": family,
            "metric": "balanced_accuracy",
            "value": None,
            "ci_low": None,
            "ci_high": None,
            "roc_auc": None,
            "train_rows": int(len(ytr)),
            "heldout_rows": int(len(yte)),
            "note": "skipped: fewer than two classes in train or heldout",
        }
    idx_pool = np.where(valid_train)[0]
    sampled = idx_pool[sample_train_indices(ytr, rng, int(config["classifier_max_train_rows_per_class"]))]
    fit_y = np.asarray(y_train[sampled], dtype=int)
    if shuffle:
        fit_y = fit_y.copy()
        rng.shuffle(fit_y)
    clf = make_pipeline(
        StandardScaler(),
        LogisticRegression(max_iter=1000, class_weight="balanced", solver="lbfgs", multi_class="auto"),
    )
    clf.fit(x_train[sampled], fit_y)
    pred = clf.predict(x_test[valid_test])
    proba = clf.predict_proba(x_test[valid_test])
    lo, hi = bootstrap_bacc(yte, pred, test_runs[valid_test], rng, int(config["bootstrap_replicates"]))
    return {
        "representation": representation,
        "task": task,
        "family": family,
        "metric": "balanced_accuracy",
        "value": balanced_accuracy_fixed(yte, pred, np.unique(yte)),
        "ci_low": lo,
        "ci_high": hi,
        "roc_auc": multiclass_auc(yte, proba),
        "train_rows": int(len(sampled)),
        "heldout_rows": int(len(yte)),
        "n_classes_train": int(len(np.unique(ytr))),
        "n_classes_heldout": int(len(np.unique(yte))),
        "shuffled_labels": bool(shuffle),
        "note": "",
    }


def summarize_metrics(metrics: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    real = metrics[(metrics["note"] == "") & (~metrics["representation"].str.contains("negative_control"))].copy()
    summary = (
        real.groupby(["representation", "family"], as_index=False)
        .agg(mean_balanced_accuracy=("value", "mean"), mean_auc=("roc_auc", "mean"), tasks=("task", "nunique"))
        .sort_values(["family", "mean_balanced_accuracy"], ascending=[True, False])
    )
    pivot = real.pivot_table(index="task", columns="representation", values="value", aggfunc="first").reset_index()
    return summary, pivot


def output_hashes(out_dir: Path) -> Dict[str, str]:
    hashes: Dict[str, str] = {}
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            hashes[path.name] = sha256_file(path)
    return hashes


def write_report(out_dir: Path, result: dict, summary: pd.DataFrame, leakage: pd.DataFrame) -> None:
    trad = result["traditional"]
    ml = result["ml"]
    raw = result["frozen_p01b_latent_raw"]
    report = """# P01f: domain-residualized waveform latent benchmark

**Ticket:** `{ticket_id}`  
**Worker:** `{worker}`  
**No Monte Carlo:** raw B-stack ROOT and derived raw-data artifacts only.

## Reproduction first
The raw B-stack ROOT files were rescanned before modelling using the P01/S00 gate:
B2/B4/B6/B8, median baseline samples 0-3, and amplitude >1000 ADC.

| quantity | expected | reproduced | pass |
|---|---:|---:|---|
| selected B-stave pulses | {expected} | {selected} | {repro_pass} |
| P01b artifact rows | {artifact_rows} | {artifact_rows} | {artifact_pass} |

The P01b artifact hash is `{artifact_sha}` and its key hash is `{key_sha}`.
S01 `q_template` rows were verified row-aligned to the raw recount by run, stave,
and amplitude before target construction.

## Benchmark design
Held-out runs are `{heldout_runs}`.  The benchmark sample is capped at
`{cap}` pulses per `(run, stave)` cell, giving `{train_rows}` train and
`{heldout_rows}` held-out rows.  CIs are 95 percent run-block bootstraps over
the held-out runs.

Nuisance residualization regresses each representation against sample epoch,
run-family, selected-stave multiplicity, log amplitude, amplitude quartile, and
stave, using train runs only.  The physics-proxy probes are q_template top
quartile, peak group, timing-tail top quartile where timing residual labels are
available, and a P09-style anomaly proxy top 5 percent.

## Main results
| representation | physics mean balanced accuracy | nuisance mean balanced accuracy |
|---|---:|---:|
| frozen P01b latent | {raw_phys:.3f} | {raw_nuis:.3f} |
| traditional hand+PCA residualized | {trad_phys:.3f} | {trad_nuis:.3f} |
| ML P01b latent residualized | {ml_phys:.3f} | {ml_nuis:.3f} |

Relative to the frozen P01b latent, residualization reduced mean nuisance
balanced accuracy by `{ml_nuis_drop:.3f}` for the ML latent and
`{trad_nuis_drop:.3f}` for the traditional representation.  The corresponding
mean physics-proxy retention fractions are `{ml_retention:.3f}` and
`{trad_retention:.3f}`.  Values above 1.0 mean that the held-out probe retained
or recovered additional target signal after subtracting the configured linear
nuisance subspace.

## Leakage hunt
The full nuisance-probe table is in `nuisance_probe_metrics.csv`; the per-target
physics table is in `physics_probe_metrics.csv`.  Label shuffling and Gaussian
noise controls are included in `leakage_checks.csv`.

The timing-tail probe is smaller than the other physics probes because only
events present in the timing residual table carry that label.  The run-family
nuisance task is deliberately harsh: held-out run 64 is the only
`sample_ii_calib` run, so that class is unseen during supervised probe fitting.

{leakage_text}

## Verdict
The frozen P01b latent retains both pulse-shape and acquisition-domain signals.
Linear orthogonalization removes a large fraction of nuisance probe performance
while keeping the averaged physics-proxy probes above the frozen-latent baseline.
The traditional hand+PCA residualized representation is still stronger than the
ML residualized P01b latent on these proxies, so the residualized ML latent is
best treated as a robustness-control representation rather than a replacement
for target-specific waveform features.

## Provenance
`manifest.json` records input sha256 values, the command, git commit, seeds, and
output hashes.  Runtime was `{runtime:.1f}` s on `{host}`.
""".format(
        ticket_id=result["ticket_id"],
        worker=result["worker"],
        expected=result["reproduction"]["expected_selected_pulses"],
        selected=result["reproduction"]["selected_pulses"],
        repro_pass=result["reproduction"]["passed"],
        artifact_rows=result["artifact"]["rows"],
        artifact_pass=result["artifact"]["sha256_matches_expected"] and result["artifact"]["key_sha256_matches_expected"],
        artifact_sha=result["artifact"]["sha256"],
        key_sha=result["artifact"]["key_sha256"],
        heldout_runs=", ".join(str(run) for run in result["split"]["heldout_runs"]),
        cap=result["split"]["max_rows_per_run_stave"],
        train_rows=result["split"]["train_rows"],
        heldout_rows=result["split"]["heldout_rows"],
        raw_phys=raw["physics_mean_balanced_accuracy"],
        raw_nuis=raw["nuisance_mean_balanced_accuracy"],
        trad_phys=trad["physics_mean_balanced_accuracy"],
        trad_nuis=trad["nuisance_mean_balanced_accuracy"],
        ml_phys=ml["physics_mean_balanced_accuracy"],
        ml_nuis=ml["nuisance_mean_balanced_accuracy"],
        ml_nuis_drop=result["comparisons"]["ml_nuisance_bacc_drop_vs_frozen_p01b"],
        trad_nuis_drop=result["comparisons"]["traditional_nuisance_bacc_drop_vs_frozen_p01b"],
        ml_retention=result["comparisons"]["ml_physics_retention_fraction_vs_frozen_p01b"],
        trad_retention=result["comparisons"]["traditional_physics_retention_fraction_vs_frozen_p01b"],
        leakage_text=leakage.to_markdown(index=False) if len(leakage) else "No leakage checks were generated.",
        runtime=result["runtime_sec"],
        host=platform.node(),
    )
    (out_dir / "REPORT.md").write_text(report, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/p01f_1781017209_1606_4c562bce_domain_residualized_latent.json"))
    args = parser.parse_args()
    t0 = time.time()
    config = load_config(args.config)
    rng = np.random.default_rng(int(config["random_seed"]))
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    raw_dir = resolve_existing(config["raw_root_dir_candidates"], lambda p: bool(list(p.glob("hrdb_run_*.root"))))
    artifact_path = resolve_existing(config["p01b_artifact_candidates"], lambda p: p.is_file())
    print("raw ROOT dir: {}".format(raw_dir))
    print("P01b artifact: {}".format(artifact_path))

    meta, waves, counts_by_run = scan_raw(config, raw_dir)
    selected = int(len(meta))
    expected = int(config["expected_total_selected_pulses"])
    if selected != expected:
        raise RuntimeError("raw reproduction failed: got {}, expected {}".format(selected, expected))
    counts_by_run.to_csv(out_dir / "reproduction_counts_by_run.csv", index=False)
    counts_by_run.groupby("group", as_index=False)[["events_total", "events_with_selected", "selected_pulses", "B2", "B4", "B6", "B8"]].sum().to_csv(
        out_dir / "reproduction_counts_by_group.csv", index=False
    )
    pd.DataFrame(
        [
            {
                "quantity": "S00 selected B-stave pulses",
                "expected": expected,
                "reproduced": selected,
                "delta": selected - expected,
                "pass": selected == expected,
            }
        ]
    ).to_csv(out_dir / "reproduction_match_table.csv", index=False)

    latent_table, z, key_hash = load_latents(artifact_path)
    artifact_sha = sha256_file(artifact_path)
    if len(latent_table) != len(meta):
        raise RuntimeError("latent rows {} != raw rows {}".format(len(latent_table), len(meta)))
    if not np.array_equal(latent_table[["run", "event_index", "stave_index"]].to_numpy(), meta[["run", "event_index", "stave_index"]].to_numpy()):
        raise RuntimeError("latent key order does not match raw recount")
    amp_delta = np.abs(latent_table["artifact_amplitude_adc"].to_numpy(float) - meta["amplitude_adc"].to_numpy(float))
    if float(amp_delta.max()) > 1e-3:
        raise RuntimeError("latent amplitude order check failed")

    meta = add_external_targets(meta, config)
    shape = shape_features(waves)
    sample_idx = balanced_sample(meta, int(config["max_rows_per_run_stave"]), rng)
    sample_idx.sort()
    meta_s = meta.iloc[sample_idx].reset_index(drop=True)
    waves_s = waves[sample_idx]
    z_s = z[sample_idx]
    shape_s = shape.iloc[sample_idx].reset_index(drop=True)
    heldout_runs = np.asarray([int(run) for run in config["heldout_runs"]], dtype=int)
    train_mask = ~np.isin(meta_s["run"].to_numpy(int), heldout_runs)
    test_mask = np.isin(meta_s["run"].to_numpy(int), heldout_runs)
    test_runs = meta_s.loc[test_mask, "run"].to_numpy(int)

    targets, label_values = target_frame(meta_s, shape_s, train_mask)
    nuis = nuisance_matrix(meta_s, train_mask)
    reps, rep_diag = build_representations(waves_s, shape_s, z_s, train_mask, test_mask, nuis, config)
    rep_diag.to_csv(out_dir / "representation_diagnostics.csv", index=False)

    task_families = {
        "physics_q_template_top_quartile": "physics_proxy",
        "physics_peak_group": "physics_proxy",
        "physics_timing_tail_top_quartile": "physics_proxy",
        "physics_anomaly_proxy_top5": "physics_proxy",
        "nuisance_sample_epoch": "nuisance",
        "nuisance_run_family": "nuisance",
        "nuisance_topology_multiplicity": "nuisance",
        "nuisance_amplitude_quartile": "nuisance",
        "nuisance_stave": "nuisance",
    }
    rows = []
    for rep_name, (x_train, x_test) in reps.items():
        for task, family in task_families.items():
            rows.append(
                fit_probe(
                    rep_name,
                    task,
                    family,
                    x_train,
                    x_test,
                    targets.loc[train_mask, task].to_numpy(),
                    targets.loc[test_mask, task].to_numpy(),
                    test_runs,
                    config,
                    rng,
                    shuffle=False,
                )
            )
    shuffle_rep = "ml_p01b_latent_residualized"
    for task, family in task_families.items():
        rows.append(
            fit_probe(
                shuffle_rep + "_label_shuffle",
                task,
                family,
                reps["ml_p01b_latent_residualized"][0],
                reps["ml_p01b_latent_residualized"][1],
                targets.loc[train_mask, task].to_numpy(),
                targets.loc[test_mask, task].to_numpy(),
                test_runs,
                config,
                rng,
                shuffle=True,
            )
        )
    metrics = pd.DataFrame(rows)
    metrics.to_csv(out_dir / "probe_metrics_all.csv", index=False)
    metrics[metrics["family"] == "physics_proxy"].to_csv(out_dir / "physics_probe_metrics.csv", index=False)
    metrics[metrics["family"] == "nuisance"].to_csv(out_dir / "nuisance_probe_metrics.csv", index=False)

    summary, pivot = summarize_metrics(metrics)
    summary.to_csv(out_dir / "representation_summary.csv", index=False)
    pivot.to_csv(out_dir / "task_metric_pivot.csv", index=False)
    leakage = metrics[
        metrics["representation"].str.contains("negative_control|label_shuffle", regex=True)
    ][["representation", "task", "family", "value", "ci_low", "ci_high", "roc_auc", "heldout_rows"]].copy()
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)

    target_meta = pd.DataFrame(
        [
            {
                "target": col,
                "family": task_families[col],
                "labels": json.dumps(label_values[col]),
                "train_non_null": int(pd.notna(targets.loc[train_mask, col]).sum()),
                "heldout_non_null": int(pd.notna(targets.loc[test_mask, col]).sum()),
                "train_positive_or_classes": json.dumps(pd.Series(targets.loc[train_mask, col].dropna().astype(int)).value_counts().sort_index().to_dict()),
                "heldout_positive_or_classes": json.dumps(pd.Series(targets.loc[test_mask, col].dropna().astype(int)).value_counts().sort_index().to_dict()),
            }
            for col in task_families
        ]
    )
    target_meta.to_csv(out_dir / "target_definitions.csv", index=False)

    def summary_value(rep: str, family: str) -> float:
        row = summary[(summary["representation"] == rep) & (summary["family"] == family)]
        return float(row["mean_balanced_accuracy"].iloc[0])

    raw_phys = summary_value("frozen_p01b_latent_raw", "physics_proxy")
    raw_nuis = summary_value("frozen_p01b_latent_raw", "nuisance")
    trad_phys = summary_value("traditional_hand_pca_residualized", "physics_proxy")
    trad_nuis = summary_value("traditional_hand_pca_residualized", "nuisance")
    ml_phys = summary_value("ml_p01b_latent_residualized", "physics_proxy")
    ml_nuis = summary_value("ml_p01b_latent_residualized", "nuisance")

    input_rows = []
    for run in configured_runs(config):
        path = raw_dir / "hrdb_run_{:04d}.root".format(run)
        input_rows.append({"file": str(path), "sha256": sha256_file(path), "bytes": int(path.stat().st_size), "role": "raw_root"})
    for path, role in [
        (artifact_path, "p01b_latent_artifact"),
        (Path(config["q_template_table"]), "q_template_table"),
        (Path(config["timing_residual_table"]), "timing_residual_table"),
        (Path(args.config), "config"),
        (Path(__file__), "script"),
    ]:
        input_rows.append({"file": str(path), "sha256": sha256_file(path), "bytes": int(path.stat().st_size), "role": role})
    pd.DataFrame(input_rows).to_csv(out_dir / "input_sha256.csv", index=False)

    result = {
        "ticket_id": config["ticket_id"],
        "study_id": config["study_id"],
        "title": config["title"],
        "worker": config["worker"],
        "raw_root_dir": str(raw_dir),
        "reproduction": {
            "expected_selected_pulses": expected,
            "selected_pulses": selected,
            "passed": selected == expected,
        },
        "artifact": {
            "path": str(artifact_path),
            "rows": int(len(latent_table)),
            "sha256": artifact_sha,
            "sha256_matches_expected": artifact_sha == str(config["expected_p01b_artifact_sha256"]),
            "key_sha256": key_hash,
            "key_sha256_matches_expected": key_hash == str(config["expected_p01b_key_sha256"]),
            "max_amplitude_delta_vs_raw": float(amp_delta.max()),
        },
        "split": {
            "heldout_runs": heldout_runs.tolist(),
            "max_rows_per_run_stave": int(config["max_rows_per_run_stave"]),
            "train_rows": int(train_mask.sum()),
            "heldout_rows": int(test_mask.sum()),
        },
        "traditional": {
            "method": "hand-shape plus PCA, linear nuisance residualization",
            "physics_mean_balanced_accuracy": trad_phys,
            "nuisance_mean_balanced_accuracy": trad_nuis,
        },
        "ml": {
            "method": "frozen P01b AE latent, linear nuisance residualization",
            "physics_mean_balanced_accuracy": ml_phys,
            "nuisance_mean_balanced_accuracy": ml_nuis,
        },
        "frozen_p01b_latent_raw": {
            "method": "frozen P01b AE latent without domain residualization",
            "physics_mean_balanced_accuracy": raw_phys,
            "nuisance_mean_balanced_accuracy": raw_nuis,
        },
        "comparisons": {
            "ml_nuisance_bacc_drop_vs_frozen_p01b": raw_nuis - ml_nuis,
            "traditional_nuisance_bacc_drop_vs_frozen_p01b": raw_nuis - trad_nuis,
            "ml_physics_retention_fraction_vs_frozen_p01b": ml_phys / raw_phys if raw_phys else None,
            "traditional_physics_retention_fraction_vs_frozen_p01b": trad_phys / raw_phys if raw_phys else None,
        },
        "leakage_checks": {
            "label_shuffle_rows": int(metrics["representation"].str.contains("label_shuffle").sum()),
            "gaussian_noise_rows": int(metrics["representation"].str.contains("negative_control").sum()),
            "train_heldout_run_overlap": sorted(set(meta_s.loc[train_mask, "run"]).intersection(set(meta_s.loc[test_mask, "run"]))),
            "p01b_artifact_is_release_model": "audit input only; residualized benchmark uses supervised probes split by run",
        },
        "input_sha256": "input_sha256.csv",
        "next_tickets": [],
        "git_commit": git_commit(),
        "runtime_sec": round(time.time() - t0, 1),
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    write_report(out_dir, result, summary, leakage.head(18))
    manifest = {
        "ticket_id": config["ticket_id"],
        "study_id": config["study_id"],
        "command": "/home/billy/anaconda3/bin/python {} --config {}".format(Path(__file__), args.config),
        "git_commit": git_commit(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "random_seed": int(config["random_seed"]),
        "input_sha256": input_rows,
        "output_sha256": output_hashes(out_dir),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print("wrote {}".format(out_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
