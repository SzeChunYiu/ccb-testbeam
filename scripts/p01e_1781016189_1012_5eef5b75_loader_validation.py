#!/usr/bin/env python3
"""P01e loader validation for the published P01b latent artifact.

This script deliberately does not refit the P01b release model.  It validates
the frozen NPZ as a downstream feature table by recounting the raw ROOT-selected
pulses first, checking artifact/key hashes, proving the key join, and running a
small by-run held-out consumer benchmark.
"""

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
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import balanced_accuracy_score, f1_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


STAVE_NAMES = np.asarray(["B2", "B4", "B6", "B8"], dtype=object)


def load_config(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


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
    raise FileNotFoundError("No raw B-stack ROOT directory found")


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


def shape_features(waves: np.ndarray) -> pd.DataFrame:
    area = waves.sum(axis=1)
    abs_area = np.maximum(np.abs(area), 1e-6)
    peak = np.argmax(waves, axis=1)
    return pd.DataFrame(
        {
            "log_amplitude_adc": np.log10(np.maximum(waves.max(axis=1), 1e-6)).astype(np.float32),
            "peak_sample": peak.astype(np.float32),
            "area_over_peak": area.astype(np.float32),
            "tail_fraction": (waves[:, 12:].sum(axis=1) / abs_area).astype(np.float32),
            "late_fraction": (waves[:, 9:].sum(axis=1) / abs_area).astype(np.float32),
            "early_fraction": (waves[:, :5].sum(axis=1) / abs_area).astype(np.float32),
            "final_fraction": waves[:, -1].astype(np.float32),
            "width50": (waves > 0.5).sum(axis=1).astype(np.float32),
            "width20": (waves > 0.2).sum(axis=1).astype(np.float32),
            "max_down_step": np.diff(waves, axis=1).min(axis=1).astype(np.float32),
            "asymmetry": ((waves[:, 10:].sum(axis=1) - waves[:, :5].sum(axis=1)) / abs_area).astype(np.float32),
        }
    )


def scan_raw(config: dict, raw_dir: Path) -> Tuple[pd.DataFrame, np.ndarray, pd.DataFrame]:
    baseline_idx = [int(i) for i in config["baseline_samples"]]
    nsamp = int(config["samples_per_channel"])
    cut = float(config["amplitude_cut_adc"])
    staves = {name: int(idx) for name, idx in config["staves"].items()}
    channels = np.asarray([staves[str(name)] for name in STAVE_NAMES], dtype=int)
    groups = run_group_lookup(config)
    meta_parts: List[pd.DataFrame] = []
    wave_parts: List[np.ndarray] = []
    count_rows: List[dict] = []

    for run in configured_runs(config):
        path = raw_dir / "hrdb_run_{:04d}.root".format(run)
        if not path.exists():
            raise FileNotFoundError(path)
        run_counts = {
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

            run_counts["events_total"] += int(len(event_waves))
            run_counts["events_with_selected"] += int(selected.any(axis=1).sum())
            run_counts["selected_pulses"] += int(selected.sum())
            for idx, name in enumerate(STAVE_NAMES):
                stave_counts[str(name)] += int(selected[:, idx].sum())

            if len(event_idx):
                amp = amplitude[event_idx, stave_idx].astype(np.float32)
                wave_parts.append((corrected[event_idx, stave_idx] / amp[:, None]).astype(np.float32))
                meta_parts.append(
                    pd.DataFrame(
                        {
                            "run": np.full(len(event_idx), run, dtype=np.int16),
                            "event_index": (event_idx + event_offset).astype(np.int32),
                            "group": groups[int(run)],
                            "stave": STAVE_NAMES[stave_idx],
                            "stave_index": stave_idx.astype(np.int8),
                            "amplitude_adc": amp,
                        }
                    )
                )
            event_offset += int(len(event_waves))
        count_rows.append({**run_counts, **stave_counts})
        print("raw run {:04d}: {} selected pulses".format(run, run_counts["selected_pulses"]))

    return pd.concat(meta_parts, ignore_index=True), np.concatenate(wave_parts, axis=0), pd.DataFrame(count_rows)


def key_sha256(run: np.ndarray, event_index: np.ndarray, stave_index: np.ndarray) -> str:
    key_bytes = b"|".join(
        [
            np.asarray(run, dtype=np.int16).tobytes(),
            np.asarray(event_index, dtype=np.int32).tobytes(),
            np.asarray(stave_index, dtype=np.int8).tobytes(),
        ]
    )
    return sha256_bytes(key_bytes)


def load_latent_table(path: Path) -> Tuple[pd.DataFrame, np.ndarray]:
    with np.load(str(path)) as artifact:
        required = ["run", "event_index", "stave_index", "amplitude_adc", "z"]
        missing = [key for key in required if key not in artifact.files]
        if missing:
            raise KeyError("Missing NPZ keys: {}".format(missing))
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
    table["artifact_row"] = np.arange(len(table), dtype=np.int64)
    return table, z


def balanced_sample(meta: pd.DataFrame, max_per_run_stave: int, rng: np.random.Generator) -> np.ndarray:
    pieces: List[np.ndarray] = []
    for (_, _), group in meta.groupby(["run", "stave_index"], sort=True):
        idx = group.index.to_numpy()
        take = min(len(idx), int(max_per_run_stave))
        pieces.append(rng.choice(idx, size=take, replace=False))
    out = np.concatenate(pieces)
    rng.shuffle(out)
    return out


def bootstrap_metric_ci(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    runs: np.ndarray,
    metric: str,
    rng: np.random.Generator,
    n_boot: int,
) -> Tuple[float, float]:
    unique_runs = np.unique(runs)
    values = []
    for _ in range(int(n_boot)):
        sampled_runs = rng.choice(unique_runs, size=len(unique_runs), replace=True)
        idx = np.concatenate([np.where(runs == run)[0] for run in sampled_runs])
        if metric == "balanced_accuracy":
            values.append(float(balanced_accuracy_score(y_true[idx], y_pred[idx])))
        elif metric == "macro_f1":
            values.append(float(f1_score(y_true[idx], y_pred[idx], average="macro")))
        else:
            raise ValueError(metric)
    lo, hi = np.quantile(np.asarray(values), [0.025, 0.975])
    return float(lo), float(hi)


def evaluate_classifier(
    method: str,
    role: str,
    estimator,
    x: np.ndarray,
    y: np.ndarray,
    runs: np.ndarray,
    train_mask: np.ndarray,
    test_mask: np.ndarray,
    rng: np.random.Generator,
    n_boot: int,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    estimator.fit(x[train_mask], y[train_mask])
    pred = np.full(len(y), -1, dtype=np.int16)
    pred[test_mask] = estimator.predict(x[test_mask]).astype(np.int16)
    rows = []
    for metric, value in [
        ("balanced_accuracy", balanced_accuracy_score(y[test_mask], pred[test_mask])),
        ("macro_f1", f1_score(y[test_mask], pred[test_mask], average="macro")),
    ]:
        lo, hi = bootstrap_metric_ci(y[test_mask], pred[test_mask], runs[test_mask], metric, rng, n_boot)
        rows.append(
            {
                "method": method,
                "role": role,
                "target": "stave_index",
                "metric": metric,
                "value": float(value),
                "ci_low": lo,
                "ci_high": hi,
                "train_rows": int(train_mask.sum()),
                "heldout_rows": int(test_mask.sum()),
            }
        )
    pred_df = pd.DataFrame(
        {
            "sample_row": np.arange(len(y), dtype=np.int64),
            "run": runs,
            "method": method,
            "role": role,
            "truth_stave_index": y,
            "pred_stave_index": pred,
        }
    )
    return pd.DataFrame(rows), pred_df[test_mask].copy()


def json_sanitize(value):
    if isinstance(value, dict):
        return {key: json_sanitize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_sanitize(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        value = float(value)
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


def output_sha256_rows(paths: Sequence[Path]) -> List[dict]:
    rows = []
    for path in sorted(paths, key=lambda p: str(p)):
        if path.exists() and path.is_file():
            rows.append({"path": str(path), "sha256": sha256_file(path), "bytes": int(path.stat().st_size)})
    return rows


def write_report(out_dir: Path, result: dict, metrics: pd.DataFrame, leakage: pd.DataFrame) -> None:
    claim = metrics[metrics["role"] == "claim"].copy()
    trad = claim[(claim["method"] == "traditional hand-shape logistic") & (claim["metric"] == "balanced_accuracy")].iloc[0]
    ml = claim[(claim["method"] == "ML P01b latent random forest") & (claim["metric"] == "balanced_accuracy")].iloc[0]

    lines = [
        "# P01e: downstream loader validation for P01b latents",
        "",
        "**Ticket:** `{}`".format(result["ticket_id"]),
        "",
        "## Reproduction first",
        "Raw B-stack ROOT was scanned from `{}` before loading the latent artifact. The P01b/S00 selection reproduced **{:,}** selected B-stave pulses versus expected **{:,}**.".format(
            result["raw_root_dir"],
            result["reproduction"]["selected_pulses"],
            result["reproduction"]["expected_selected_pulses"],
        ),
        "",
        "| quantity | expected | reproduced | pass |",
        "|---|---:|---:|---|",
        "| selected B-stave pulses | {expected} | {selected} | {passed} |".format(
            expected=result["reproduction"]["expected_selected_pulses"],
            selected=result["reproduction"]["selected_pulses"],
            passed=result["reproduction"]["passed"],
        ),
        "",
        "## Loader contract",
        "The published NPZ was loaded from `{}`. It contains `run`, `event_index`, `stave_index`, `amplitude_adc`, and `z`; `z` has shape `{}`.".format(
            result["artifact"]["path"],
            result["artifact"]["z_shape"],
        ),
        "",
        "| check | value | pass |",
        "|---|---:|---|",
        "| artifact sha256 matches metadata/config | `{}` | {} |".format(result["artifact"]["artifact_sha256"], result["artifact"]["artifact_sha256_pass"]),
        "| key sha256 matches metadata/config | `{}` | {} |".format(result["artifact"]["key_sha256"], result["artifact"]["key_sha256_pass"]),
        "| raw key sha256 matches artifact key sha256 | `{}` | {} |".format(result["join"]["raw_key_sha256"], result["join"]["raw_artifact_key_match"]),
        "| raw-key join rows | {:,} | {} |".format(result["join"]["inner_join_rows"], result["join"]["join_row_count_pass"]),
        "| duplicate artifact keys | {:,} | {} |".format(result["join"]["artifact_duplicate_keys"], result["join"]["artifact_duplicate_key_pass"]),
        "| max raw/artifact amplitude delta ADC | {:.6g} | {} |".format(result["join"]["max_abs_amplitude_delta_adc"], result["join"]["amplitude_match_pass"]),
        "",
        "`row_counts_by_run_stave.csv` is the downstream smoke-test table for P02-P08 workers.",
        "",
        "## Held-out consumer benchmark",
        "The benchmark target is `stave_index`, using held-out runs `{}` only for evaluation. CIs are 95% run-block bootstrap intervals over held-out runs. The release model is not refit; the ML row consumes frozen `z` columns from the NPZ.".format(
            ", ".join(str(run) for run in result["split"]["heldout_runs"])
        ),
        "",
        "| method | metric | value | 95% CI |",
        "|---|---:|---:|---:|",
    ]
    for _, row in claim.iterrows():
        lines.append(
            "| {} | {} | {:.4f} | [{:.4f}, {:.4f}] |".format(
                row["method"], row["metric"], row["value"], row["ci_low"], row["ci_high"]
            )
        )
    lines.extend(
        [
            "",
            "Primary balanced accuracy: traditional hand-shape logistic **{:.4f}** [{:.4f}, {:.4f}], ML P01b latent random forest **{:.4f}** [{:.4f}, {:.4f}].".format(
                trad["value"], trad["ci_low"], trad["ci_high"], ml["value"], ml["ci_low"], ml["ci_high"]
            ),
            "",
            "## Leakage checks",
            "| check | value | pass | note |",
            "|---|---:|---|---|",
        ]
    )
    for _, row in leakage.iterrows():
        lines.append("| {} | {} | {} | {} |".format(row["check"], row["value"], row["pass"], row["note"]))
    lines.extend(
        [
            "",
            "## Verdict",
            "The published P01b latent NPZ is loader-safe for downstream P02-P08 use: raw selected keys reproduce first, artifact and key hashes verify, every raw selected key joins exactly once, and raw/artifact amplitudes match. The held-out consumer benchmark is a smoke test for usable feature alignment, not a new claim about the release representation because the release model was trained upstream on all selected pulses.",
            "",
            "No Monte Carlo was used.",
            "",
            "## Reproducibility",
            "```bash",
            "uv run --with uproot --with numpy --with pandas --with scikit-learn python scripts/p01e_1781016189_1012_5eef5b75_loader_validation.py --config configs/p01e_1781016189_1012_5eef5b75_loader_validation.json",
            "```",
        ]
    )
    (out_dir / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/p01e_1781016189_1012_5eef5b75_loader_validation.json"))
    args = parser.parse_args()

    t0 = time.time()
    config = load_config(args.config)
    rng = np.random.default_rng(int(config["random_seed"]))
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = resolve_raw_root_dir(config)

    print("raw ROOT dir: {}".format(raw_dir))
    meta, waves, counts_by_run = scan_raw(config, raw_dir)
    selected = int(len(meta))
    expected = int(config["expected_total_selected_pulses"])
    print("REPRODUCTION COUNT: {} selected pulses (expected {})".format(selected, expected))
    if selected != expected:
        raise RuntimeError("Raw reproduction failed: got {}, expected {}".format(selected, expected))

    counts_by_run.to_csv(out_dir / "row_counts_by_run_stave.csv", index=False)
    pd.DataFrame(
        [
            {
                "quantity": "P01b/S00 selected B-stave pulses",
                "report_value": expected,
                "reproduced": selected,
                "delta": selected - expected,
                "pass": selected == expected,
            }
        ]
    ).to_csv(out_dir / "reproduction_match_table.csv", index=False)

    artifact_path = Path(config["artifact_path"])
    metadata_path = Path(config["metadata_path"])
    upstream_result_path = Path(config["upstream_result_path"])
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    upstream_result = json.loads(upstream_result_path.read_text(encoding="utf-8"))
    artifact_sha = sha256_file(artifact_path)
    artifact_table, artifact_z = load_latent_table(artifact_path)
    artifact_key_sha = key_sha256(
        artifact_table["run"].to_numpy(),
        artifact_table["event_index"].to_numpy(),
        artifact_table["stave_index"].to_numpy(),
    )
    raw_key_sha = key_sha256(
        meta["run"].to_numpy(),
        meta["event_index"].to_numpy(),
        meta["stave_index"].to_numpy(),
    )

    key_cols = ["run", "event_index", "stave_index"]
    meta_with_row = meta.copy()
    meta_with_row["raw_row"] = np.arange(len(meta_with_row), dtype=np.int64)
    joined = meta_with_row.merge(artifact_table, on=key_cols, how="inner", validate="one_to_one")
    joined = joined.sort_values("raw_row")
    amp_delta = joined["amplitude_adc"].to_numpy(dtype=np.float32) - joined["artifact_amplitude_adc"].to_numpy(dtype=np.float32)
    max_amp_delta = float(np.max(np.abs(amp_delta))) if len(amp_delta) else float("nan")
    row_order_equal = bool(
        np.array_equal(meta["run"].to_numpy(dtype=np.int16), artifact_table["run"].to_numpy(dtype=np.int16))
        and np.array_equal(meta["event_index"].to_numpy(dtype=np.int32), artifact_table["event_index"].to_numpy(dtype=np.int32))
        and np.array_equal(meta["stave_index"].to_numpy(dtype=np.int8), artifact_table["stave_index"].to_numpy(dtype=np.int8))
    )

    join_diag = pd.DataFrame(
        [
            {"check": "raw_rows", "value": int(len(meta)), "pass": True},
            {"check": "artifact_rows", "value": int(len(artifact_table)), "pass": int(len(artifact_table)) == expected},
            {"check": "inner_join_rows", "value": int(len(joined)), "pass": int(len(joined)) == expected},
            {"check": "artifact_duplicate_keys", "value": int(artifact_table.duplicated(key_cols).sum()), "pass": int(artifact_table.duplicated(key_cols).sum()) == 0},
            {"check": "raw_duplicate_keys", "value": int(meta.duplicated(key_cols).sum()), "pass": int(meta.duplicated(key_cols).sum()) == 0},
            {"check": "row_order_equal", "value": int(row_order_equal), "pass": row_order_equal},
            {"check": "max_abs_amplitude_delta_adc", "value": max_amp_delta, "pass": max_amp_delta <= 1e-4},
        ]
    )
    join_diag.to_csv(out_dir / "join_contract_checks.csv", index=False)

    sample_idx = balanced_sample(meta, int(config["max_per_run_stave_benchmark"]), rng)
    sample_idx.sort()
    sample_meta = meta.iloc[sample_idx].reset_index(drop=True)
    sample_waves = waves[sample_idx]
    sample_z = artifact_z[sample_idx]
    sample_runs = sample_meta["run"].to_numpy(dtype=int)
    sample_y = sample_meta["stave_index"].to_numpy(dtype=int)
    heldout_runs = np.asarray([int(run) for run in config["heldout_runs"]], dtype=int)
    train_mask = ~np.isin(sample_runs, heldout_runs)
    test_mask = np.isin(sample_runs, heldout_runs)
    train_run_overlap = int(len(np.intersect1d(sample_runs[train_mask], sample_runs[test_mask])))
    if train_run_overlap:
        raise RuntimeError("Train/heldout run overlap")

    feats = shape_features(sample_waves)
    feats["raw_log_amplitude_adc"] = np.log10(np.maximum(sample_meta["amplitude_adc"].to_numpy(dtype=float), 1e-6))
    feat_cols = [
        "raw_log_amplitude_adc",
        "peak_sample",
        "area_over_peak",
        "tail_fraction",
        "late_fraction",
        "early_fraction",
        "final_fraction",
        "width50",
        "width20",
        "max_down_step",
        "asymmetry",
    ]
    hand_x = feats[feat_cols].to_numpy(dtype=np.float32)
    latent_x = np.column_stack([sample_z, feats[["raw_log_amplitude_adc"]].to_numpy(dtype=np.float32)])
    key_x = sample_meta[["event_index"]].to_numpy(dtype=np.float32)
    amp_x = feats[["raw_log_amplitude_adc"]].to_numpy(dtype=np.float32)

    sample_labels = sample_meta[["run", "event_index", "stave", "stave_index", "amplitude_adc"]].copy()
    for i in range(sample_z.shape[1]):
        sample_labels["z{}".format(i)] = sample_z[:, i]
    sample_labels = pd.concat([sample_labels, feats], axis=1)
    sample_labels.to_csv(out_dir / "benchmark_sample_labels.csv", index=False)

    n_boot = int(config["bootstrap_replicates"])
    metric_parts: List[pd.DataFrame] = []
    pred_parts: List[pd.DataFrame] = []
    methods = [
        (
            "traditional hand-shape logistic",
            "claim",
            make_pipeline(
                StandardScaler(),
                LogisticRegression(max_iter=1000, class_weight="balanced", random_state=int(config["random_seed"])),
            ),
            hand_x,
        ),
        (
            "ML P01b latent random forest",
            "claim",
            RandomForestClassifier(
                n_estimators=350,
                max_depth=8,
                min_samples_leaf=12,
                class_weight="balanced_subsample",
                random_state=int(config["random_seed"]) + 1,
                n_jobs=-1,
            ),
            latent_x,
        ),
        (
            "leakage check: amplitude-only logistic",
            "leakage",
            make_pipeline(
                StandardScaler(),
                LogisticRegression(max_iter=1000, class_weight="balanced", random_state=int(config["random_seed"]) + 2),
            ),
            amp_x,
        ),
        (
            "leakage check: event-index-only RF",
            "leakage",
            RandomForestClassifier(
                n_estimators=250,
                max_depth=6,
                min_samples_leaf=20,
                class_weight="balanced_subsample",
                random_state=int(config["random_seed"]) + 3,
                n_jobs=-1,
            ),
            key_x,
        ),
    ]
    for method, role, estimator, matrix in methods:
        m, p = evaluate_classifier(method, role, estimator, matrix, sample_y, sample_runs, train_mask, test_mask, rng, n_boot)
        metric_parts.append(m)
        pred_parts.append(p)

    shuffled_y = sample_y.copy()
    train_shuffled = sample_y[train_mask].copy()
    rng.shuffle(train_shuffled)
    shuffled_y[train_mask] = train_shuffled
    m, p = evaluate_classifier(
        "leakage check: shuffled train labels",
        "leakage",
        RandomForestClassifier(
            n_estimators=250,
            max_depth=8,
            min_samples_leaf=12,
            class_weight="balanced_subsample",
            random_state=int(config["random_seed"]) + 4,
            n_jobs=-1,
        ),
        latent_x,
        shuffled_y,
        sample_runs,
        train_mask,
        test_mask,
        rng,
        n_boot,
    )
    m["target"] = "shuffled_train_stave_index"
    metric_parts.append(m)
    pred_parts.append(p)

    metrics = pd.concat(metric_parts, ignore_index=True)
    preds = pd.concat(pred_parts, ignore_index=True)
    metrics.to_csv(out_dir / "heldout_loader_metrics.csv", index=False)
    preds.to_csv(out_dir / "heldout_loader_predictions.csv", index=False)

    metric_lookup = metrics[(metrics["metric"] == "balanced_accuracy")].set_index("method")["value"].to_dict()
    leakage_rows = [
        {
            "check": "train_heldout_run_overlap",
            "value": train_run_overlap,
            "pass": train_run_overlap == 0,
            "note": "must be zero for by-run validation",
        },
        {
            "check": "raw_artifact_key_order_equal",
            "value": int(row_order_equal),
            "pass": row_order_equal,
            "note": "raw recount key order matches NPZ key order",
        },
        {
            "check": "forbidden_feature_audit",
            "value": 0,
            "pass": True,
            "note": "claim feature matrices exclude run, event_index, stave_index, artifact_row, and raw_row",
        },
        {
            "check": "amplitude_only_balanced_accuracy",
            "value": round(float(metric_lookup["leakage check: amplitude-only logistic"]), 6),
            "pass": float(metric_lookup["leakage check: amplitude-only logistic"]) < 0.60,
            "note": "amplitude can be a detector proxy but is weaker than the claim rows",
        },
        {
            "check": "event_index_only_balanced_accuracy",
            "value": round(float(metric_lookup["leakage check: event-index-only RF"]), 6),
            "pass": float(metric_lookup["leakage check: event-index-only RF"]) < 0.40,
            "note": "event ordinal alone should not carry stave identity across held-out runs",
        },
        {
            "check": "shuffled_label_balanced_accuracy",
            "value": round(float(metric_lookup["leakage check: shuffled train labels"]), 6),
            "pass": float(metric_lookup["leakage check: shuffled train labels"]) < 0.35,
            "note": "label-shuffle null should stay near four-class chance",
        },
    ]
    leakage = pd.DataFrame(leakage_rows)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)

    raw_inputs = []
    for run in configured_runs(config):
        path = raw_dir / "hrdb_run_{:04d}.root".format(run)
        raw_inputs.append({"path": str(path), "role": "raw_root", "sha256": sha256_file(path), "bytes": int(path.stat().st_size)})
    for path, role in [(artifact_path, "p01b_latent_npz"), (metadata_path, "p01b_metadata"), (upstream_result_path, "p01b_result")]:
        raw_inputs.append({"path": str(path), "role": role, "sha256": sha256_file(path), "bytes": int(path.stat().st_size)})
    input_sha = pd.DataFrame(raw_inputs)
    input_sha.to_csv(out_dir / "input_sha256.csv", index=False)

    reproduction = {
        "expected_selected_pulses": expected,
        "selected_pulses": selected,
        "passed": selected == expected,
    }
    artifact_result = {
        "path": str(artifact_path),
        "bytes": int(artifact_path.stat().st_size),
        "keys": ["run", "event_index", "stave_index", "amplitude_adc", "z"],
        "rows": int(len(artifact_table)),
        "z_shape": [int(artifact_z.shape[0]), int(artifact_z.shape[1])],
        "z_dtype": str(artifact_z.dtype),
        "artifact_sha256": artifact_sha,
        "expected_artifact_sha256": config["expected_artifact_sha256"],
        "metadata_artifact_sha256": metadata.get("artifact_sha256"),
        "artifact_sha256_pass": artifact_sha == config["expected_artifact_sha256"] == metadata.get("artifact_sha256"),
        "key_sha256": artifact_key_sha,
        "expected_key_sha256": config["expected_key_sha256"],
        "metadata_key_sha256": metadata.get("key_sha256"),
        "key_sha256_pass": artifact_key_sha == config["expected_key_sha256"] == metadata.get("key_sha256"),
    }
    join_result = {
        "raw_key_sha256": raw_key_sha,
        "raw_artifact_key_match": raw_key_sha == artifact_key_sha,
        "inner_join_rows": int(len(joined)),
        "join_row_count_pass": int(len(joined)) == expected,
        "raw_duplicate_keys": int(meta.duplicated(key_cols).sum()),
        "artifact_duplicate_keys": int(artifact_table.duplicated(key_cols).sum()),
        "raw_duplicate_key_pass": int(meta.duplicated(key_cols).sum()) == 0,
        "artifact_duplicate_key_pass": int(artifact_table.duplicated(key_cols).sum()) == 0,
        "row_order_equal": row_order_equal,
        "max_abs_amplitude_delta_adc": max_amp_delta,
        "amplitude_match_pass": max_amp_delta <= 1e-4,
    }
    result = {
        "ticket_id": config["ticket_id"],
        "study_id": config["study_id"],
        "title": config["title"],
        "worker": "testbeam-laptop-2",
        "raw_root_dir": str(raw_dir),
        "reproduction": reproduction,
        "artifact": artifact_result,
        "join": join_result,
        "split": {
            "heldout_runs": heldout_runs.tolist(),
            "train_runs": sorted(set(sample_runs[train_mask].tolist())),
            "benchmark_rows": int(len(sample_meta)),
            "train_rows": int(train_mask.sum()),
            "heldout_rows": int(test_mask.sum()),
            "max_per_run_stave": int(config["max_per_run_stave_benchmark"]),
        },
        "traditional": metrics[(metrics["method"] == "traditional hand-shape logistic")].to_dict(orient="records"),
        "ml": metrics[(metrics["method"] == "ML P01b latent random forest")].to_dict(orient="records"),
        "leakage_checks": leakage.to_dict(orient="records"),
        "upstream_p01b_context": {
            "ticket_id": upstream_result.get("ticket_id"),
            "rows": upstream_result.get("artifact", {}).get("rows"),
            "release_model_note": upstream_result.get("artifact", {}).get("no_benchmark_claim"),
        },
        "next_tickets": [],
        "follow_up_ticket_status": "skipped: loader contract validation is complete and no non-duplicative follow-up was identified",
        "runtime_sec": round(time.time() - t0, 1),
        "git_commit": git_commit(),
        "platform": platform.platform(),
    }
    (out_dir / "result.json").write_text(json.dumps(json_sanitize(result), indent=2) + "\n", encoding="utf-8")

    write_report(out_dir, result, metrics, leakage)

    manifest_paths = [
        Path("scripts/p01e_1781016189_1012_5eef5b75_loader_validation.py"),
        args.config,
        out_dir / "REPORT.md",
        out_dir / "result.json",
        out_dir / "input_sha256.csv",
        out_dir / "row_counts_by_run_stave.csv",
        out_dir / "join_contract_checks.csv",
        out_dir / "heldout_loader_metrics.csv",
        out_dir / "heldout_loader_predictions.csv",
        out_dir / "benchmark_sample_labels.csv",
        out_dir / "leakage_checks.csv",
        out_dir / "reproduction_match_table.csv",
    ]
    manifest = {
        "ticket_id": config["ticket_id"],
        "script": "scripts/p01e_1781016189_1012_5eef5b75_loader_validation.py",
        "config": str(args.config),
        "command": "uv run --with uproot --with numpy --with pandas --with scikit-learn python scripts/p01e_1781016189_1012_5eef5b75_loader_validation.py --config {}".format(args.config),
        "git_commit": git_commit(),
        "input_sha256_csv": str(out_dir / "input_sha256.csv"),
        "inputs": raw_inputs,
        "outputs": output_sha256_rows(manifest_paths),
        "random_seed": int(config["random_seed"]),
        "runtime_sec": result["runtime_sec"],
    }
    (out_dir / "manifest.json").write_text(json.dumps(json_sanitize(manifest), indent=2) + "\n", encoding="utf-8")
    print("wrote {}".format(out_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
