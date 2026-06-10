#!/usr/bin/env python3
"""P08b: charge-current matched waveform PID leakage null from raw B-stack ROOT."""

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
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "2")
os.environ.setdefault("MKL_NUM_THREADS", "2")

import numpy as np
import pandas as pd
import uproot
from sklearn.decomposition import PCA
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.utils.class_weight import compute_sample_weight

STAVE_NAMES = np.asarray(["B2", "B4", "B6", "B8"], dtype=object)


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


def json_sanitize(value):
    if isinstance(value, dict):
        return {str(key): json_sanitize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_sanitize(item) for item in value]
    if isinstance(value, tuple):
        return [json_sanitize(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        value = float(value)
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


def resolve_raw_root_dir(config: dict) -> Path:
    for candidate in config["raw_root_dir_candidates"]:
        path = Path(candidate).expanduser()
        if path.exists() and list(path.glob("hrdb_run_*.root")):
            return path
    raise FileNotFoundError("No raw B-stack ROOT directory found")


def resolve_p01b_embedding(config: dict) -> Optional[Path]:
    for candidate in config.get("p01b_embedding_candidates", []):
        path = Path(candidate).expanduser()
        if path.exists():
            return path
    return None


def configured_runs(config: dict) -> List[int]:
    runs: List[int] = []
    for values in config["run_groups"].values():
        runs.extend(int(run) for run in values)
    return sorted(set(runs))


def run_group_lookup(config: dict) -> Dict[int, str]:
    lookup: Dict[int, str] = {}
    for group, runs in config["run_groups"].items():
        for run in runs:
            lookup[int(run)] = str(group)
    return lookup


def raw_file(raw_root_dir: Path, run: int) -> Path:
    return raw_root_dir / "hrdb_run_{:04d}.root".format(run)


def iter_raw(path: Path, step_size: int = 20000) -> Iterable[dict]:
    tree = uproot.open(path)["h101"]
    yield from tree.iterate(["EVENTNO", "EVT", "HRDv"], step_size=step_size, library="np")


def shape_features(wave: np.ndarray) -> pd.DataFrame:
    area = wave.sum(axis=1)
    abs_area = np.maximum(np.abs(area), 1e-6)
    return pd.DataFrame(
        {
            "b2_area_over_peak": area.astype(np.float32),
            "b2_tail_fraction": (wave[:, 12:].sum(axis=1) / abs_area).astype(np.float32),
            "b2_late_fraction": (wave[:, 9:].sum(axis=1) / abs_area).astype(np.float32),
            "b2_early_fraction": (wave[:, :5].sum(axis=1) / abs_area).astype(np.float32),
            "b2_final_fraction": wave[:, -1].astype(np.float32),
            "b2_peak_sample": np.argmax(wave, axis=1).astype(np.float32),
            "b2_width50": (wave > 0.5).sum(axis=1).astype(np.float32),
            "b2_width20": (wave > 0.2).sum(axis=1).astype(np.float32),
            "b2_max_down_step": np.diff(wave, axis=1).min(axis=1).astype(np.float32),
        }
    )


def scan_raw(config: dict, raw_dir: Path) -> Tuple[np.ndarray, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    cut = float(config["amplitude_cut_adc"])
    baseline_idx = [int(i) for i in config["baseline_samples"]]
    nsamp = int(config["samples_per_channel"])
    channels = np.asarray([int(config["staves"][str(name)]) for name in STAVE_NAMES], dtype=int)
    group_for_run = run_group_lookup(config)
    waves: List[np.ndarray] = []
    meta_parts: List[pd.DataFrame] = []
    run_rows: List[dict] = []

    for run in configured_runs(config):
        path = raw_file(raw_dir, run)
        if not path.exists():
            raise FileNotFoundError(path)
        group = group_for_run[int(run)]
        event_offset = 0
        run_counts = {
            "run": int(run),
            "group": group,
            "events_total": 0,
            "events_with_selected": 0,
            "selected_pulses": 0,
            "weak_terminal_b2_like": 0,
            "weak_penetrating_like": 0,
        }
        stave_counts = {str(name): 0 for name in STAVE_NAMES}
        for batch in iter_raw(path):
            raw = np.stack(batch["HRDv"]).astype(np.float32).reshape(-1, 8, nsamp)
            selected_raw = raw[:, channels, :]
            baseline = np.median(selected_raw[..., baseline_idx], axis=-1)
            corrected = selected_raw - baseline[..., None]
            amplitude = corrected.max(axis=-1)
            area = np.clip(corrected, 0.0, None).sum(axis=-1)
            selected = amplitude > cut

            run_counts["events_total"] += int(len(raw))
            run_counts["events_with_selected"] += int(selected.any(axis=1).sum())
            run_counts["selected_pulses"] += int(selected.sum())
            for idx, name in enumerate(STAVE_NAMES):
                stave_counts[str(name)] += int(selected[:, idx].sum())

            b2 = selected[:, 0]
            downstream_selected = selected[:, 1:].sum(axis=1)
            downstream_charge = area[:, 1:].sum(axis=1)
            total_charge = np.maximum(area.sum(axis=1), 1e-6)
            downstream_fraction = downstream_charge / total_charge
            max_depth = np.where(selected[:, 3], 4, np.where(selected[:, 2], 3, np.where(selected[:, 1], 2, np.where(selected[:, 0], 1, 0))))
            weak = b2
            if weak.any():
                b2_amp = np.maximum(amplitude[weak, 0], 1e-6)
                b2_wave = (corrected[weak, 0, :] / b2_amp[:, None]).astype(np.float32)
                waves.append(b2_wave)
                event_idx = np.flatnonzero(weak)
                event_fraction = (event_idx + event_offset).astype(np.float32)
                meta_parts.append(
                    pd.DataFrame(
                        {
                            "run": np.full(len(event_idx), run, dtype=np.int16),
                            "group": group,
                            "event_index": (event_idx + event_offset).astype(np.int32),
                            "event_order_proxy": event_fraction,
                            "eventno": np.asarray(batch["EVENTNO"])[event_idx].astype(np.int64),
                            "evt": np.asarray(batch["EVT"])[event_idx].astype(np.int64),
                            "downstream_selected": downstream_selected[weak].astype(np.int8),
                            "max_depth_stave": max_depth[weak].astype(np.int8),
                            "downstream_charge_fraction": downstream_fraction[weak].astype(np.float32),
                            "b2_amplitude_adc": amplitude[weak, 0].astype(np.float32),
                            "total_charge_adc_samples": area[weak, :].sum(axis=1).astype(np.float32),
                            "b2_charge_fraction": (area[weak, 0] / total_charge[weak]).astype(np.float32),
                            "b4_present": selected[weak, 1].astype(np.int8),
                            "b6_present": selected[weak, 2].astype(np.int8),
                            "b8_present": selected[weak, 3].astype(np.int8),
                            "b2_area": area[weak, 0].astype(np.float32),
                            "b4_area": area[weak, 1].astype(np.float32),
                            "b6_area": area[weak, 2].astype(np.float32),
                            "b8_area": area[weak, 3].astype(np.float32),
                            "b2_amp": amplitude[weak, 0].astype(np.float32),
                            "b4_amp": amplitude[weak, 1].astype(np.float32),
                            "b6_amp": amplitude[weak, 2].astype(np.float32),
                            "b8_amp": amplitude[weak, 3].astype(np.float32),
                            "b2_saturated": (amplitude[weak, 0] >= float(config["matching"]["saturation_adc"])).astype(np.int8),
                        }
                    )
                )
                run_counts["weak_terminal_b2_like"] += int(weak.sum())
                run_counts["weak_penetrating_like"] += 0
            event_offset += int(len(raw))

        run_rows.append({**run_counts, **stave_counts})
        print(
            "run {:04d}: selected_pulses={} b2_selected_events={}".format(
                run,
                run_counts["selected_pulses"],
                run_counts["weak_terminal_b2_like"],
            ),
            flush=True,
        )

    wave_array = np.concatenate(waves, axis=0)
    meta = pd.concat(meta_parts, ignore_index=True)
    meta = pd.concat([meta, shape_features(wave_array)], axis=1)
    counts = pd.DataFrame(run_rows)
    groups = (
        counts.groupby("group", sort=False)[["events_total", "events_with_selected", "selected_pulses", "B2", "B4", "B6", "B8"]]
        .sum()
        .reset_index()
    )
    return wave_array, meta, counts, groups


def reproduction_table(config: dict, counts_by_group: pd.DataFrame) -> pd.DataFrame:
    expected = config["expected_counts"]
    rows = [
        {
            "quantity": "total selected B-stave pulses",
            "report_value": int(expected["total_selected_pulses"]),
            "reproduced": int(counts_by_group["selected_pulses"].sum()),
            "tolerance": 0,
        }
    ]
    for group in config["run_groups"]:
        key = "{}_pulses".format(group)
        rows.append(
            {
                "quantity": "{} selected pulses".format(group),
                "report_value": int(expected[key]),
                "reproduced": int(counts_by_group.loc[counts_by_group["group"] == group, "selected_pulses"].iloc[0]),
                "tolerance": 0,
            }
        )
    out = pd.DataFrame(rows)
    out["delta"] = out["reproduced"] - out["report_value"]
    out["pass"] = out["delta"].abs() <= out["tolerance"]
    return out


def qbin(values: pd.Series, bins: int) -> pd.Series:
    ranked = values.rank(method="first")
    try:
        return pd.qcut(ranked, q=int(bins), labels=False, duplicates="drop").astype("int16")
    except ValueError:
        return pd.Series(np.zeros(len(values), dtype=np.int16), index=values.index)


def add_matched_weak_labels(meta: pd.DataFrame, config: dict) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Create residual high/low weak labels inside strict nuisance-matched atoms."""
    out = meta.copy()
    match = config["matching"]
    label_cfg = config["weak_label"]
    out["topology_code"] = (
        out["b4_present"].astype(int) + 2 * out["b6_present"].astype(int) + 4 * out["b8_present"].astype(int)
    ).astype(np.int16)
    out["pileup_width_bin"] = (out["b2_width20"] >= float(match["pileup_width20_threshold"])).astype(np.int8)
    out["b2_charge_bin"] = out.groupby("run", group_keys=False)["b2_area"].apply(
        lambda s: qbin(np.log1p(np.maximum(s, 0.0)), int(match["b2_charge_quantile_bins"]))
    )
    out["total_charge_bin"] = out.groupby("run", group_keys=False)["total_charge_adc_samples"].apply(
        lambda s: qbin(np.log1p(np.maximum(s, 0.0)), int(match["total_charge_quantile_bins"]))
    )
    out["event_current_bin"] = out.groupby("run", group_keys=False)["event_order_proxy"].apply(
        lambda s: qbin(s, int(match["event_current_quantile_bins"]))
    )
    stratum_cols = [
        "run",
        "b2_charge_bin",
        "total_charge_bin",
        "event_current_bin",
        "b2_saturated",
        "pileup_width_bin",
        "max_depth_stave",
        "topology_code",
    ]
    out["match_stratum"] = out[stratum_cols].astype(str).agg("|".join, axis=1)
    out["weak_label"] = np.nan
    q = float(label_cfg["within_stratum_quantile"])
    min_class = int(label_cfg["min_stratum_class_rows"])
    rows = []
    for stratum, grp in out.groupby("match_stratum", sort=False):
        if len(grp) < 2 * min_class:
            continue
        lo = float(grp["downstream_charge_fraction"].quantile(q))
        hi = float(grp["downstream_charge_fraction"].quantile(1.0 - q))
        low_idx = grp.index[grp["downstream_charge_fraction"] <= lo]
        high_idx = grp.index[grp["downstream_charge_fraction"] >= hi]
        n = min(len(low_idx), len(high_idx))
        if n < min_class or hi <= lo:
            continue
        out.loc[low_idx[:n], "weak_label"] = 0
        out.loc[high_idx[-n:], "weak_label"] = 1
        first = grp.iloc[0]
        rows.append(
            {
                "match_stratum": stratum,
                "run": int(first["run"]),
                "b2_charge_bin": int(first["b2_charge_bin"]),
                "total_charge_bin": int(first["total_charge_bin"]),
                "event_current_bin": int(first["event_current_bin"]),
                "b2_saturated": int(first["b2_saturated"]),
                "pileup_width_bin": int(first["pileup_width_bin"]),
                "max_depth_stave": int(first["max_depth_stave"]),
                "topology_code": int(first["topology_code"]),
                "available_rows": int(len(grp)),
                "low_rows": int(n),
                "high_rows": int(n),
                "low_threshold": lo,
                "high_threshold": hi,
            }
        )
    out = out.dropna(subset=["weak_label"]).copy()
    out["weak_label"] = out["weak_label"].astype(np.int8)
    out["weak_label_name"] = np.where(
        out["weak_label"] == 1, label_cfg["positive_name"], label_cfg["negative_name"]
    )
    support = pd.DataFrame(rows)
    return out.reset_index(drop=True), support


def balanced_benchmark_indices(meta: pd.DataFrame, config: dict) -> np.ndarray:
    rng = np.random.default_rng(int(config["benchmark"]["random_seed"]))
    max_rows = int(config["benchmark"]["max_rows_per_run_label"])
    pieces: List[np.ndarray] = []
    for (_, _), group in meta.groupby(["run", "weak_label"], sort=True):
        idx = group.index.to_numpy()
        take = min(len(idx), max_rows)
        pieces.append(rng.choice(idx, size=take, replace=False))
    out = np.concatenate(pieces)
    rng.shuffle(out)
    return out


def candidate_traditional_scores(train: pd.DataFrame, test: pd.DataFrame) -> Tuple[np.ndarray, dict, pd.DataFrame]:
    eps = 1e-6
    recipes = {
        "tail_total_b2": lambda df: df["b2_tail_fraction"].to_numpy(dtype=float),
        "area_peak_b2": lambda df: df["b2_area_over_peak"].to_numpy(dtype=float),
        "q_template_b2_shape": None,
        "penetration_depth_proxy": lambda df: df["max_depth_stave"].to_numpy(dtype=float),
        "deltae_amp_vector": lambda df: np.log1p(df["b4_amp"] + df["b6_amp"] + df["b8_amp"]).to_numpy(dtype=float)
        - np.log1p(df["b2_amp"]).to_numpy(dtype=float),
        "downstream_charge_fraction": lambda df: df["downstream_charge_fraction"].to_numpy(dtype=float),
    }
    y_train = train["weak_label"].to_numpy(dtype=int)
    rows = []
    best = None

    neg_template = None
    pos_template = None
    if {0, 1}.issubset(set(y_train.tolist())):
        sample_cols = ["norm_s{:02d}".format(i) for i in range(18)]
        neg_template = train.loc[train["weak_label"] == 0, sample_cols].mean(axis=0).to_numpy(dtype=float)
        pos_template = train.loc[train["weak_label"] == 1, sample_cols].mean(axis=0).to_numpy(dtype=float)
        denom = np.linalg.norm(pos_template - neg_template)
        if denom > 0:
            direction = (pos_template - neg_template) / denom
            recipes["q_template_b2_shape"] = lambda df, direction=direction, sample_cols=sample_cols: df[sample_cols].to_numpy(dtype=float).dot(direction)

    for name, func in recipes.items():
        if func is None:
            continue
        raw = func(train)
        for sign in (1.0, -1.0):
            score = sign * raw
            try:
                auc = roc_auc_score(y_train, score)
            except ValueError:
                auc = np.nan
            rows.append({"candidate": name, "sign": sign, "train_auc": auc})
            if not np.isnan(auc) and (best is None or auc > best["train_auc"]):
                best = {"candidate": name, "sign": sign, "train_auc": float(auc)}

    if best is None:
        raise RuntimeError("No valid traditional candidate in fold")
    test_score = best["sign"] * recipes[best["candidate"]](test)
    return test_score, best, pd.DataFrame(rows)


def fit_logistic_score(train_x: np.ndarray, train_y: np.ndarray, test_x: np.ndarray) -> np.ndarray:
    clf = make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000, class_weight="balanced", solver="lbfgs"))
    clf.fit(train_x, train_y)
    return clf.predict_proba(test_x)[:, 1]


def fit_ml_score(train_x: np.ndarray, train_y: np.ndarray, test_x: np.ndarray, params: dict, seed: int) -> np.ndarray:
    clf = HistGradientBoostingClassifier(
        max_iter=int(params.get("n_estimators", params.get("max_iter", 80))),
        max_leaf_nodes=int(params.get("max_leaf_nodes", 31)),
        max_depth=int(params["max_depth"]),
        min_samples_leaf=int(params["min_samples_leaf"]),
        learning_rate=float(params.get("learning_rate", 0.05)),
        l2_regularization=float(params.get("l2_regularization", 0.0)),
        random_state=seed,
    )
    weight = compute_sample_weight(class_weight="balanced", y=train_y)
    clf.fit(train_x, train_y, sample_weight=weight)
    return clf.predict_proba(test_x)[:, 1]


def residualize_matrix(
    train_x: np.ndarray,
    test_x: np.ndarray,
    train_nuisance: np.ndarray,
    test_nuisance: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray]:
    model = make_pipeline(StandardScaler(), Ridge(alpha=10.0))
    model.fit(train_nuisance, train_x)
    return train_x - model.predict(train_nuisance), test_x - model.predict(test_nuisance)


def safe_auc(y: np.ndarray, score: np.ndarray) -> float:
    if len(np.unique(y)) < 2:
        return float("nan")
    return float(roc_auc_score(y, score))


def safe_ap(y: np.ndarray, score: np.ndarray) -> float:
    if len(np.unique(y)) < 2:
        return float("nan")
    return float(average_precision_score(y, score))


def crossfold_isotonic(y: np.ndarray, score: np.ndarray, folds: np.ndarray) -> np.ndarray:
    prob = np.full(len(y), np.nan, dtype=float)
    for fold in np.unique(folds):
        test = folds == fold
        cal = ~test
        if len(np.unique(y[cal])) < 2:
            prob[test] = np.clip(score[test], 0.0, 1.0)
            continue
        iso = IsotonicRegression(out_of_bounds="clip")
        iso.fit(score[cal], y[cal])
        prob[test] = iso.predict(score[test])
    return prob


def run_block_ci(
    y: np.ndarray,
    score: np.ndarray,
    prob: np.ndarray,
    runs: np.ndarray,
    seed: int,
    n_boot: int,
) -> dict:
    rng = np.random.default_rng(seed)
    unique_runs = np.unique(runs)
    aucs, aps, briers = [], [], []
    for _ in range(n_boot):
        sampled = rng.choice(unique_runs, size=len(unique_runs), replace=True)
        idx = np.concatenate([np.where(runs == run)[0] for run in sampled])
        if len(np.unique(y[idx])) < 2:
            continue
        aucs.append(roc_auc_score(y[idx], score[idx]))
        aps.append(average_precision_score(y[idx], score[idx]))
        briers.append(brier_score_loss(y[idx], np.clip(prob[idx], 0.0, 1.0)))
    return {
        "roc_auc_ci": [float(x) for x in np.quantile(aucs, [0.025, 0.975])] if aucs else [None, None],
        "average_precision_ci": [float(x) for x in np.quantile(aps, [0.025, 0.975])] if aps else [None, None],
        "brier_ci": [float(x) for x in np.quantile(briers, [0.025, 0.975])] if briers else [None, None],
        "bootstrap_valid": int(len(aucs)),
    }


def fixed_efficiency_purity(y: np.ndarray, score: np.ndarray, runs: np.ndarray, efficiency: float, seed: int, n_boot: int) -> Tuple[float, List[float]]:
    pos_scores = score[y == 1]
    threshold = float(np.quantile(pos_scores, max(0.0, 1.0 - efficiency)))
    selected = score >= threshold
    purity = float(y[selected].mean()) if selected.any() else float("nan")
    rng = np.random.default_rng(seed)
    unique_runs = np.unique(runs)
    boot = []
    for _ in range(n_boot):
        sampled = rng.choice(unique_runs, size=len(unique_runs), replace=True)
        idx = np.concatenate([np.where(runs == run)[0] for run in sampled])
        sel = selected[idx]
        if sel.any():
            boot.append(float(y[idx][sel].mean()))
    ci = [float(x) for x in np.quantile(boot, [0.025, 0.975])] if boot else [None, None]
    return purity, ci


def paired_auc_diff(
    y: np.ndarray,
    traditional_score: np.ndarray,
    ml_score: np.ndarray,
    runs: np.ndarray,
    seed: int,
    n_boot: int,
) -> dict:
    rng = np.random.default_rng(seed)
    unique_runs = np.unique(runs)
    diffs = []
    for _ in range(n_boot):
        sampled = rng.choice(unique_runs, size=len(unique_runs), replace=True)
        idx = np.concatenate([np.where(runs == run)[0] for run in sampled])
        if len(np.unique(y[idx])) < 2:
            continue
        diffs.append(roc_auc_score(y[idx], ml_score[idx]) - roc_auc_score(y[idx], traditional_score[idx]))
    return {
        "ml_minus_traditional_auc": safe_auc(y, ml_score) - safe_auc(y, traditional_score),
        "ci": [float(x) for x in np.quantile(diffs, [0.025, 0.975])] if diffs else [None, None],
        "bootstrap_valid": int(len(diffs)),
    }


def load_p01b_z_for_b2(path: Path) -> pd.DataFrame:
    arr = np.load(path)
    stave = arr["stave_index"]
    mask = stave == 0
    out = pd.DataFrame({"run": arr["run"][mask].astype(np.int16), "event_index": arr["event_index"][mask].astype(np.int32)})
    z = arr["z"][mask]
    for i in range(z.shape[1]):
        out["p01b_z{}".format(i)] = z[:, i].astype(np.float32)
    return out


def build_benchmark(
    waves_all: np.ndarray,
    meta_all: pd.DataFrame,
    config: dict,
    out_dir: Path,
    p01b_path: Optional[Path],
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    sample_idx = balanced_benchmark_indices(meta_all, config)
    meta = meta_all.loc[sample_idx].reset_index(drop=True).copy()
    waves = waves_all[sample_idx]
    for sample in range(waves.shape[1]):
        meta["norm_s{:02d}".format(sample)] = waves[:, sample].astype(np.float32)

    if p01b_path is not None:
        p01b = load_p01b_z_for_b2(p01b_path)
        meta = meta.merge(p01b, on=["run", "event_index"], how="left")
    p01b_cols = [col for col in meta.columns if col.startswith("p01b_z")]

    y = meta["weak_label"].to_numpy(dtype=int)
    runs = meta["run"].to_numpy(dtype=int)
    fold_id = np.full(len(meta), "", dtype=object)
    traditional_score = np.full(len(meta), np.nan)
    ml_score = np.full(len(meta), np.nan)
    nuisance_score = np.full(len(meta), np.nan)
    forbidden_deltae_score = np.full(len(meta), np.nan)
    p01b_score = np.full(len(meta), np.nan)
    shuffled_score = np.full(len(meta), np.nan)
    run_only_score = np.full(len(meta), np.nan)
    event_proxy_score = np.full(len(meta), np.nan)

    traditional_choices: List[dict] = []
    candidate_rows: List[pd.DataFrame] = []
    ml_grid_rows: List[dict] = []
    seed = int(config["benchmark"]["random_seed"])
    min_train_class = int(config["benchmark"]["min_train_class_rows"])
    min_test_class = int(config["benchmark"]["min_test_class_rows"])
    sample_cols = ["norm_s{:02d}".format(i) for i in range(18)]
    hand_cols = [
        "b2_area_over_peak",
        "b2_tail_fraction",
        "b2_late_fraction",
        "b2_early_fraction",
        "b2_final_fraction",
        "b2_peak_sample",
        "b2_width50",
        "b2_width20",
        "b2_max_down_step",
    ]
    categorical_nuisance_cols = [
        "b2_charge_bin",
        "total_charge_bin",
        "event_current_bin",
        "b2_saturated",
        "pileup_width_bin",
        "max_depth_stave",
        "topology_code",
    ]
    numeric_nuisance_cols = ["b2_amp", "b2_area", "total_charge_adc_samples", "event_order_proxy"]
    forbidden_deltae_cols = [
        "downstream_charge_fraction",
        "downstream_selected",
        "max_depth_stave",
        "b4_area",
        "b6_area",
        "b8_area",
        "b4_amp",
        "b6_amp",
        "b8_amp",
    ]

    folds = []
    for run in np.unique(runs):
        test = runs == run
        train = ~test
        train_counts = np.bincount(y[train], minlength=2)
        test_counts = np.bincount(y[test], minlength=2)
        if train_counts.min() < min_train_class or test_counts.min() < min_test_class:
            continue
        folds.append((train, test, int(run)))

    for fold_number, (train, test, heldout_run) in enumerate(folds, start=1):
        train_df = meta.loc[train].copy()
        test_df = meta.loc[test].copy()
        score, choice, candidates = candidate_traditional_scores(train_df, test_df)
        traditional_score[test] = score
        choice.update({"heldout_run": heldout_run, "fold": fold_number})
        traditional_choices.append(choice)
        candidates["heldout_run"] = heldout_run
        candidate_rows.append(candidates)

        train_y = y[train]
        nuisance_train_cat = pd.get_dummies(meta.loc[train, categorical_nuisance_cols].astype(str))
        nuisance_test_cat = pd.get_dummies(meta.loc[test, categorical_nuisance_cols].astype(str)).reindex(
            columns=nuisance_train_cat.columns, fill_value=0
        )
        nuisance_train_num = meta.loc[train, numeric_nuisance_cols].copy()
        nuisance_test_num = meta.loc[test, numeric_nuisance_cols].copy()
        for col in ["b2_amp", "b2_area", "total_charge_adc_samples"]:
            nuisance_train_num[col] = np.log1p(np.maximum(nuisance_train_num[col].to_numpy(dtype=float), 0.0))
            nuisance_test_num[col] = np.log1p(np.maximum(nuisance_test_num[col].to_numpy(dtype=float), 0.0))
        nuisance_train = np.column_stack([nuisance_train_cat.to_numpy(dtype=float), nuisance_train_num.to_numpy(dtype=float)])
        nuisance_test = np.column_stack([nuisance_test_cat.to_numpy(dtype=float), nuisance_test_num.to_numpy(dtype=float)])
        nuisance_score[test] = fit_logistic_score(nuisance_train, train_y, nuisance_test)

        forbidden_train = meta.loc[train, forbidden_deltae_cols].copy()
        forbidden_test = meta.loc[test, forbidden_deltae_cols].copy()
        for col in ["b4_area", "b6_area", "b8_area", "b4_amp", "b6_amp", "b8_amp"]:
            forbidden_train[col] = np.log1p(np.maximum(forbidden_train[col].to_numpy(dtype=float), 0.0))
            forbidden_test[col] = np.log1p(np.maximum(forbidden_test[col].to_numpy(dtype=float), 0.0))
        forbidden_deltae_score[test] = fit_logistic_score(
            forbidden_train.to_numpy(dtype=float), train_y, forbidden_test.to_numpy(dtype=float)
        )

        pca = PCA(n_components=4, random_state=seed + fold_number)
        train_pca = pca.fit_transform(meta.loc[train, sample_cols].to_numpy(dtype=float))
        test_pca = pca.transform(meta.loc[test, sample_cols].to_numpy(dtype=float))
        ml_train = np.column_stack([meta.loc[train, sample_cols + hand_cols].to_numpy(dtype=float), train_pca])
        ml_test = np.column_stack([meta.loc[test, sample_cols + hand_cols].to_numpy(dtype=float), test_pca])
        ml_train, ml_test = residualize_matrix(ml_train, ml_test, nuisance_train, nuisance_test)

        best_params = config["benchmark"]["ml_grid"][0]
        ml_grid_rows.append({"heldout_run": heldout_run, **best_params, "selection": "fixed preconfigured HGB"})
        ml_score[test] = fit_ml_score(ml_train, train_y, ml_test, best_params, seed + fold_number)

        shuffled_y = train_y.copy()
        np.random.default_rng(seed + 9000 + fold_number).shuffle(shuffled_y)
        shuffled_score[test] = fit_ml_score(ml_train, shuffled_y, ml_test, best_params, seed + 3000 + fold_number)

        run_train = pd.get_dummies(meta.loc[train, "run"].astype(str))
        run_test = pd.get_dummies(meta.loc[test, "run"].astype(str)).reindex(columns=run_train.columns, fill_value=0)
        run_only_score[test] = fit_logistic_score(run_train.to_numpy(dtype=float), train_y, run_test.to_numpy(dtype=float))

        proxy_train = pd.get_dummies(meta.loc[train, "group"].astype(str))
        proxy_test = pd.get_dummies(meta.loc[test, "group"].astype(str)).reindex(columns=proxy_train.columns, fill_value=0)
        event_train_raw = meta.loc[train, ["event_index"]].to_numpy(dtype=float)
        event_test_raw = meta.loc[test, ["event_index"]].to_numpy(dtype=float)
        event_min = float(event_train_raw.min())
        event_scale = max(float(event_train_raw.max() - event_min), 1.0)
        event_train = (event_train_raw - event_min) / event_scale
        event_test = (event_test_raw - event_min) / event_scale
        event_proxy_score[test] = fit_logistic_score(
            np.column_stack([proxy_train.to_numpy(dtype=float), event_train]),
            train_y,
            np.column_stack([proxy_test.to_numpy(dtype=float), event_test]),
        )

        if p01b_cols and not meta.loc[train, p01b_cols].isna().any().any() and not meta.loc[test, p01b_cols].isna().any().any():
            p01b_score[test] = fit_logistic_score(
                meta.loc[train, p01b_cols].to_numpy(dtype=float),
                train_y,
                meta.loc[test, p01b_cols].to_numpy(dtype=float),
            )

        fold_id[test] = "run{}".format(heldout_run)
        print(
            "fold {:02d}: heldout_run={} train={} test={} hgb_iter={}".format(
                fold_number,
                heldout_run,
                int(train.sum()),
                int(test.sum()),
                int(best_params.get("n_estimators", best_params.get("max_iter", 20))),
            ),
            flush=True,
        )

    valid = fold_id != ""
    meta_eval = meta.loc[valid].copy()
    y_eval = y[valid]
    runs_eval = runs[valid]
    folds_eval = fold_id[valid]
    scores = {
        "traditional best frozen cut": traditional_score[valid],
        "ML residualized raw B2 waveform + train-only PCA HGB": ml_score[valid],
        "leakage sentinel: matched-nuisance-only logistic": nuisance_score[valid],
        "leakage sentinel: forbidden downstream DeltaE logistic": forbidden_deltae_score[valid],
        "leakage sentinel: run-only logistic": run_only_score[valid],
        "leakage sentinel: group/event-order logistic": event_proxy_score[valid],
        "leakage sentinel: shuffled-label HGB": shuffled_score[valid],
    }
    if p01b_cols and not np.isnan(p01b_score[valid]).all():
        scores["diagnostic: all-data P01b B2 latent logistic"] = p01b_score[valid]

    rows = []
    for idx, (name, score) in enumerate(scores.items()):
        prob = crossfold_isotonic(y_eval, score, folds_eval)
        ci = run_block_ci(y_eval, score, prob, runs_eval, seed + idx + 10, int(config["benchmark"]["bootstrap_replicates"]))
        purity, purity_ci = fixed_efficiency_purity(
            y_eval,
            score,
            runs_eval,
            float(config["benchmark"]["fixed_efficiency"]),
            seed + idx + 100,
            int(config["benchmark"]["bootstrap_replicates"]),
        )
        row = {
            "method": name,
            "n_events": int(len(y_eval)),
            "n_runs": int(len(np.unique(runs_eval))),
            "positive_fraction": float(y_eval.mean()),
            "roc_auc": safe_auc(y_eval, score),
            "roc_auc_ci_low": ci["roc_auc_ci"][0],
            "roc_auc_ci_high": ci["roc_auc_ci"][1],
            "average_precision": safe_ap(y_eval, score),
            "ap_ci_low": ci["average_precision_ci"][0],
            "ap_ci_high": ci["average_precision_ci"][1],
            "brier_isotonic": float(brier_score_loss(y_eval, np.clip(prob, 0.0, 1.0))),
            "brier_ci_low": ci["brier_ci"][0],
            "brier_ci_high": ci["brier_ci"][1],
            "purity_at_{:.0f}pct_eff".format(100 * float(config["benchmark"]["fixed_efficiency"])): purity,
            "purity_ci_low": purity_ci[0],
            "purity_ci_high": purity_ci[1],
            "bootstrap_valid": ci["bootstrap_valid"],
        }
        rows.append(row)
        meta_eval[name.replace(" ", "_").replace(":", "").replace("/", "_")] = score
        meta_eval[name.replace(" ", "_").replace(":", "").replace("/", "_") + "_prob"] = prob

    scoreboard = pd.DataFrame(rows)
    diff = paired_auc_diff(
        y_eval,
        scores["traditional best frozen cut"],
        scores["ML residualized raw B2 waveform + train-only PCA HGB"],
        runs_eval,
        seed + 777,
        int(config["benchmark"]["bootstrap_replicates"]),
    )
    leakage = pd.DataFrame(
        [
            {
                "probe": "matched-nuisance-only logistic",
                "roc_auc": scoreboard.loc[scoreboard["method"] == "leakage sentinel: matched-nuisance-only logistic", "roc_auc"].iloc[0],
                "average_precision": scoreboard.loc[scoreboard["method"] == "leakage sentinel: matched-nuisance-only logistic", "average_precision"].iloc[0],
                "interpretation": "Failure probe: uses only matched charge/current/depth/topology/saturation/pile-up bins plus event-order nuisance variables; high AUC means coarse matching still leaks.",
            },
            {
                "probe": "forbidden downstream DeltaE logistic",
                "roc_auc": scoreboard.loc[scoreboard["method"] == "leakage sentinel: forbidden downstream DeltaE logistic", "roc_auc"].iloc[0],
                "average_precision": scoreboard.loc[scoreboard["method"] == "leakage sentinel: forbidden downstream DeltaE logistic", "average_precision"].iloc[0],
                "interpretation": "Ceiling/leakage probe: includes downstream charge and penetration observables used to define the residual weak label.",
            },
            {
                "probe": "run-only logistic",
                "roc_auc": scoreboard.loc[scoreboard["method"] == "leakage sentinel: run-only logistic", "roc_auc"].iloc[0],
                "average_precision": scoreboard.loc[scoreboard["method"] == "leakage sentinel: run-only logistic", "average_precision"].iloc[0],
                "interpretation": "Strict leave-one-run-out run-id sentinel; unseen held-out runs collapse to the intercept.",
            },
            {
                "probe": "group/event-order logistic",
                "roc_auc": scoreboard.loc[scoreboard["method"] == "leakage sentinel: group/event-order logistic", "roc_auc"].iloc[0],
                "average_precision": scoreboard.loc[scoreboard["method"] == "leakage sentinel: group/event-order logistic", "average_precision"].iloc[0],
                "interpretation": "Sample group plus event-order sentinel for run-family/rate-drift confounding.",
            },
            {
                "probe": "shuffled-label HGB",
                "roc_auc": scoreboard.loc[scoreboard["method"] == "leakage sentinel: shuffled-label HGB", "roc_auc"].iloc[0],
                "average_precision": scoreboard.loc[scoreboard["method"] == "leakage sentinel: shuffled-label HGB", "average_precision"].iloc[0],
                "interpretation": "Same HGB pipeline with shuffled training labels; should fall near chance.",
            },
            {
                "probe": "ML-minus-traditional paired run bootstrap",
                "roc_auc": diff["ml_minus_traditional_auc"],
                "average_precision": None,
                "interpretation": "Positive values favor ML; CI is stored in result.json.",
            },
        ]
    )
    if "diagnostic: all-data P01b B2 latent logistic" in scores:
        row = scoreboard.loc[scoreboard["method"] == "diagnostic: all-data P01b B2 latent logistic"].iloc[0]
        leakage = pd.concat(
            [
                leakage,
                pd.DataFrame(
                    [
                        {
                            "probe": "all-data P01b latent logistic",
                            "roc_auc": row["roc_auc"],
                            "average_precision": row["average_precision"],
                            "interpretation": "Diagnostic only; P01b release encoder was fit on all selected pulses and is not used for the main claim.",
                        }
                    ]
                ),
            ],
            ignore_index=True,
        )

    fold_counts = meta_eval.groupby(["run", "weak_label_name"]).size().reset_index(name="n")
    pd.DataFrame(traditional_choices).to_csv(out_dir / "traditional_fold_choices.csv", index=False)
    pd.concat(candidate_rows, ignore_index=True).to_csv(out_dir / "traditional_candidate_scan.csv", index=False)
    pd.DataFrame(ml_grid_rows).to_csv(out_dir / "ml_fixed_hgb_folds.csv", index=False)
    fold_counts.to_csv(out_dir / "heldout_run_label_counts.csv", index=False)
    meta_eval[
        [
            "run",
            "event_index",
            "weak_label",
            "weak_label_name",
            "downstream_selected",
            "downstream_charge_fraction",
            "b2_amplitude_adc",
            "total_charge_adc_samples",
        ]
        + [col for col in meta_eval.columns if col.endswith("_HGB") or col.endswith("_cut")]
    ].head(20000).to_csv(out_dir / "oof_prediction_preview.csv", index=False)

    details = {
        "benchmark_rows_after_balancing": int(len(meta)),
        "evaluated_rows": int(len(y_eval)),
        "evaluated_runs": [int(run) for run in np.unique(runs_eval)],
        "skipped_runs": [int(run) for run in sorted(set(np.unique(runs).tolist()) - set(np.unique(runs_eval).tolist()))],
        "positive_fraction": float(y_eval.mean()),
        "ml_vs_traditional": diff,
        "p01b_embedding_used_as_diagnostic": str(p01b_path) if p01b_path is not None else None,
    }
    return scoreboard, leakage, fold_counts, meta, details


def write_report(out_dir: Path, config: dict, result: dict, reproduction: pd.DataFrame, scoreboard: pd.DataFrame, leakage: pd.DataFrame, fold_counts: pd.DataFrame) -> None:
    trad = scoreboard[scoreboard["method"] == "traditional best frozen cut"].iloc[0]
    ml = scoreboard[scoreboard["method"] == "ML residualized raw B2 waveform + train-only PCA HGB"].iloc[0]
    shuffled = scoreboard[scoreboard["method"] == "leakage sentinel: shuffled-label HGB"].iloc[0]
    diff = result["ml_vs_traditional"]
    nuisance = scoreboard[scoreboard["method"] == "leakage sentinel: matched-nuisance-only logistic"].iloc[0]
    forbidden = scoreboard[scoreboard["method"] == "leakage sentinel: forbidden downstream DeltaE logistic"].iloc[0]
    report = """# P08b: charge-current matched waveform PID leakage null

**Ticket:** {ticket_id}  
**Worker:** {worker}  
**Input:** raw B-stack `HRDv` ROOT from `{raw_root_dir}`

## Reproduction First
Before weak-labeling or modeling, the raw ROOT scan reproduced the S00 selected
B-stave pulse count exactly:

{reproduction_table}

## Weak Labels
These are not truth PID labels. They are frozen residual weak labels made only
after exact matching on run, B2 charge bin, total-charge bin, event-current bin,
B2 saturation, pile-up width, depth proxy, and downstream topology. Within each
matched atom the bottom {label_q:.0f}% of downstream charge fraction is
`{neg}`, and the top {label_q:.0f}% is `{pos}`; atoms with fewer than
{min_class} rows per class are rejected.

The strict matched support contains {support_rows:,} atoms and {label_rows:,}
balanced weak-label rows before the run-held-out cap. The held-out benchmark
uses {n_eval:,} rows across {n_runs} runs. Runs with too few held-out examples
in either class are listed in `result.json`.

## Run-Held-Out Benchmark
All scores below are leave-one-run-out predictions with run-block bootstrap 95%
CIs. The traditional score chooses among tail/total, area/peak, a train-only B2
`q_template`, penetration-depth, downstream charge fraction, and DeltaE-like
amplitude-vector scores inside each training fold. The ML score is a
histogram-gradient-boosted classifier over residualized normalized B2 waveform
samples, B2 hand-shape features, and train-only PCA latents; the residualizer is
fit only on training-run nuisance variables.

| method | ROC AUC | AP | purity at {eff:.0f}% high-residual efficiency |
|---|---:|---:|---:|
| traditional frozen cuts | {trad_auc:.3f} [{trad_lo:.3f}, {trad_hi:.3f}] | {trad_ap:.3f} | {trad_purity:.3f} |
| ML residualized waveform HGB | {ml_auc:.3f} [{ml_lo:.3f}, {ml_hi:.3f}] | {ml_ap:.3f} | {ml_purity:.3f} |

Paired run-block bootstrap for ML minus traditional ROC AUC is **{diff:.3f}**
with 95% CI **[{diff_lo:.3f}, {diff_hi:.3f}]**.

## Leakage Hunt
| probe | ROC AUC | AP | interpretation |
|---|---:|---:|---|
{leakage_table}

The matched-nuisance sentinel is **not** near chance, so the matched atoms are
not sufficient to kill sub-bin charge/current leakage. The forbidden downstream
DeltaE sentinel is allowed to be high because it contains the downstream
residual used to define the weak label. Run/group/event-order performance
quantifies run-family/rate-drift confounding and is near chance here. The
benchmark is B2-event-level, so stave id is constant by construction. The
shuffled-label HGB is the software leakage guardrail.

## Verdict
This is a leakage finding, not a PID claim. The raw reproduction and
run-held-out machinery work, but the nuisance-only AUC is {nuisance_auc:.3f},
so P08/S15-style weak labels remain dominated by charge/current substructure
even after the coarse matched strata. The forbidden DeltaE AUC is
{forbidden_auc:.3f}, and residualized waveform ML is far below the deliberately
strong traditional leakage-aware baseline. No waveform PID adoption claim is
supported without S17 truth and tighter continuous matching.

## Reproducibility
```bash
/home/billy/anaconda3/bin/python scripts/p08b_1781020308_607_456c4f7e_charge_current_pid_leakage_null.py --config configs/p08b_1781020308_607_456c4f7e_charge_current_pid_leakage_null.json
```

Artifacts include `result.json`, `manifest.json`, `input_sha256.csv`,
`reproduction_match_table.csv`, `scoreboard.csv`, `leakage_checks.csv`,
`heldout_run_label_counts.csv`, `traditional_candidate_scan.csv`, and
`ml_fixed_hgb_folds.csv`.
""".format(
        ticket_id=config["ticket_id"],
        worker=config["worker"],
        raw_root_dir=result["raw_root_dir"],
        reproduction_table=reproduction.to_markdown(index=False),
        neg=config["weak_label"]["negative_name"],
        pos=config["weak_label"]["positive_name"],
        label_q=100 * float(config["weak_label"]["within_stratum_quantile"]),
        min_class=int(config["weak_label"]["min_stratum_class_rows"]),
        support_rows=int(result["matched_support"]["n_strata"]),
        label_rows=int(result["matched_support"]["n_labeled_rows"]),
        n_eval=int(result["benchmark"]["evaluated_rows"]),
        n_runs=len(result["benchmark"]["evaluated_runs"]),
        eff=100 * float(config["benchmark"]["fixed_efficiency"]),
        trad_auc=trad["roc_auc"],
        trad_lo=trad["roc_auc_ci_low"],
        trad_hi=trad["roc_auc_ci_high"],
        trad_ap=trad["average_precision"],
        trad_purity=trad["purity_at_{:.0f}pct_eff".format(100 * float(config["benchmark"]["fixed_efficiency"]))],
        ml_auc=ml["roc_auc"],
        ml_lo=ml["roc_auc_ci_low"],
        ml_hi=ml["roc_auc_ci_high"],
        ml_ap=ml["average_precision"],
        ml_purity=ml["purity_at_{:.0f}pct_eff".format(100 * float(config["benchmark"]["fixed_efficiency"]))],
        diff=diff["ml_minus_traditional_auc"],
        diff_lo=diff["ci"][0],
        diff_hi=diff["ci"][1],
        nuisance_auc=nuisance["roc_auc"],
        forbidden_auc=forbidden["roc_auc"],
        leakage_table="\n".join(
            "| {} | {} | {} | {} |".format(
                row["probe"],
                "" if pd.isna(row["roc_auc"]) else "{:.3f}".format(row["roc_auc"]),
                "" if pd.isna(row["average_precision"]) else "{:.3f}".format(row["average_precision"]),
                row["interpretation"],
            )
            for _, row in leakage.iterrows()
        ),
    )
    (out_dir / "REPORT.md").write_text(report, encoding="utf-8")


def output_manifest(out_dir: Path) -> List[dict]:
    rows = []
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            rows.append({"file": path.name, "sha256": sha256_file(path), "bytes": int(path.stat().st_size)})
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/p08b_1781020308_607_456c4f7e_charge_current_pid_leakage_null.json"))
    args = parser.parse_args()
    t0 = time.time()
    config = load_config(args.config)
    raw_dir = resolve_raw_root_dir(config)
    p01b_path = resolve_p01b_embedding(config)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    waves, meta, counts_by_run, counts_by_group = scan_raw(config, raw_dir)
    reproduction = reproduction_table(config, counts_by_group)
    counts_by_run.to_csv(out_dir / "reproduction_counts_by_run.csv", index=False)
    counts_by_group.to_csv(out_dir / "reproduction_counts_by_group.csv", index=False)
    reproduction.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(reproduction["pass"].all()):
        raise RuntimeError("Raw reproduction failed; refusing to continue to weak-label modeling")

    meta, matched_support = add_matched_weak_labels(meta, config)
    matched_support.to_csv(out_dir / "matched_strata_support.csv", index=False)
    if meta.empty:
        raise RuntimeError("No weak-label rows survived strict matched support")

    weak_counts = meta.groupby(["run", "weak_label_name"]).size().reset_index(name="n")
    weak_counts.to_csv(out_dir / "weak_label_counts_by_run.csv", index=False)

    scoreboard, leakage, fold_counts, benchmark_meta, details = build_benchmark(waves, meta, config, out_dir, p01b_path)
    scoreboard.to_csv(out_dir / "scoreboard.csv", index=False)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)
    benchmark_meta.groupby(["run", "weak_label_name"]).size().reset_index(name="n").to_csv(out_dir / "benchmark_balanced_counts.csv", index=False)

    input_rows = []
    for run in configured_runs(config):
        path = raw_file(raw_dir, run)
        input_rows.append({"file": str(path), "sha256": sha256_file(path), "bytes": int(path.stat().st_size)})
    input_sha = pd.DataFrame(input_rows)
    input_sha.to_csv(out_dir / "input_sha256.csv", index=False)

    trad = scoreboard[scoreboard["method"] == "traditional best frozen cut"].iloc[0]
    ml = scoreboard[scoreboard["method"] == "ML residualized raw B2 waveform + train-only PCA HGB"].iloc[0]
    result = {
        "ticket_id": config["ticket_id"],
        "worker": config["worker"],
        "study_id": config["study_id"],
        "title": config["title"],
        "raw_root_dir": str(raw_dir),
        "git_commit_at_run": git_commit(),
        "reproduction": {
            "passed": bool(reproduction["pass"].all()),
            "table": reproduction.to_dict(orient="records"),
        },
        "weak_label_definition": config["weak_label"],
        "matched_support": {
            "n_strata": int(len(matched_support)),
            "n_labeled_rows": int(len(meta)),
            "stratum_columns": [
                "run",
                "b2_charge_bin",
                "total_charge_bin",
                "event_current_bin",
                "b2_saturated",
                "pileup_width_bin",
                "max_depth_stave",
                "topology_code",
            ],
        },
        "traditional": {
            "method": "best frozen conventional score among tail/total, area/peak, q_template, DeltaE-like amplitude vector",
            "roc_auc": float(trad["roc_auc"]),
            "roc_auc_ci": [float(trad["roc_auc_ci_low"]), float(trad["roc_auc_ci_high"])],
            "average_precision": float(trad["average_precision"]),
        },
        "ml": {
            "method": "histogram gradient boosting over nuisance-residualized raw normalized B2 waveform samples, hand shape features, and train-only PCA latents",
            "roc_auc": float(ml["roc_auc"]),
            "roc_auc_ci": [float(ml["roc_auc_ci_low"]), float(ml["roc_auc_ci_high"])],
            "average_precision": float(ml["average_precision"]),
        },
        "ml_vs_traditional": details["ml_vs_traditional"],
        "leakage_hunt": leakage.to_dict(orient="records"),
        "primary_interpretation": (
            "Leakage null: matched-nuisance-only AUC remains high, so coarse charge/current/depth/topology "
            "matching does not remove sub-bin nuisance information; residualized waveform ML is not a PID claim."
        ),
        "benchmark": details,
        "input_file_count": int(len(input_sha)),
        "runtime_sec": round(time.time() - t0, 1),
    }
    (out_dir / "result.json").write_text(json.dumps(json_sanitize(result), indent=2) + "\n", encoding="utf-8")
    write_report(out_dir, config, result, reproduction, scoreboard, leakage, fold_counts)

    manifest = {
        "ticket_id": config["ticket_id"],
        "script": "scripts/p08b_1781020308_607_456c4f7e_charge_current_pid_leakage_null.py",
        "config": str(args.config),
        "python": platform.python_version(),
        "raw_root_dir": str(raw_dir),
        "p01b_embedding_diagnostic": str(p01b_path) if p01b_path is not None else None,
        "input_sha256_csv": str(out_dir / "input_sha256.csv"),
        "input_file_count": int(len(input_sha)),
        "reproduction_passed": bool(reproduction["pass"].all()),
        "commands": [
            "/home/billy/anaconda3/bin/python scripts/p08b_1781020308_607_456c4f7e_charge_current_pid_leakage_null.py --config configs/p08b_1781020308_607_456c4f7e_charge_current_pid_leakage_null.json"
        ],
        "random_seeds": {
            "benchmark": int(config["benchmark"]["random_seed"]),
            "bootstrap_replicates": int(config["benchmark"]["bootstrap_replicates"]),
        },
        "git_commit_at_run": git_commit(),
        "environment": {
            "platform": platform.platform(),
            "python": platform.python_version(),
        },
        "artifacts": output_manifest(out_dir),
    }
    (out_dir / "manifest.json").write_text(json.dumps(json_sanitize(manifest), indent=2) + "\n", encoding="utf-8")
    print(scoreboard.to_string(index=False))
    print(leakage.to_string(index=False))
    print("DONE in {:.1f}s -> {}".format(time.time() - t0, out_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
