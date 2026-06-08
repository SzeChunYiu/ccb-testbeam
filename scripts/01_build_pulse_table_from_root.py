#!/usr/bin/env python3
"""Rebuild the S00 selected B-stack pulse table from reduced raw ROOT files."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import uproot
import yaml


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def configured_runs(config: dict) -> List[int]:
    runs: List[int] = []
    for values in config["run_groups"].values():
        runs.extend(int(run) for run in values)
    return sorted(set(runs))


def run_group_lookup(config: dict) -> Dict[int, str]:
    lookup: Dict[int, str] = {}
    for group, runs in config["run_groups"].items():
        for run in runs:
            lookup[int(run)] = group
    return lookup


def raw_file(raw_root_dir: Path, run: int) -> Path:
    return raw_root_dir / f"hrdb_run_{run:04d}.root"


def sorted_file(sorted_b_dir: Path, run: int) -> Path:
    return sorted_b_dir / f"hrdb_run_{run:04d}-sorted.root"


def pulse_quantities(waveforms: np.ndarray, baseline_indices: List[int]) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    baseline = np.median(waveforms[..., baseline_indices], axis=-1)
    corrected = waveforms - baseline[..., None]
    amplitude = corrected.max(axis=-1)
    peak_sample = corrected.argmax(axis=-1)
    area = corrected.sum(axis=-1)
    return baseline, amplitude, peak_sample, area


def iter_raw_events(path: Path, step_size: int = 10000) -> Iterable[dict]:
    tree = uproot.open(path)["h101"]
    branches = ["EVENTNO", "EVT", "HRDv"]
    yield from tree.iterate(branches, step_size=step_size, library="np")


def init_count_dict() -> dict:
    return {
        "events_with_selected": 0,
        "selected_pulses": 0,
        "staves": defaultdict(int),
        "events_total": 0,
    }


def scan_raw(config: dict) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, dict], pd.DataFrame, pd.DataFrame]:
    raw_root_dir = Path(config["raw_root_dir"])
    cut = float(config["amplitude_cut_adc"])
    baseline_indices = [int(i) for i in config["baseline_samples"]]
    samples_per_channel = int(config["samples_per_channel"])
    staves = {name: int(idx) for name, idx in config["staves"].items()}
    group_for_run = run_group_lookup(config)
    rng = np.random.default_rng(int(config["ml_check"]["random_seed"]))

    counts_by_run: List[dict] = []
    counts_by_group: Dict[str, dict] = defaultdict(init_count_dict)
    selected_frames: List[pd.DataFrame] = []
    ml_frames: List[pd.DataFrame] = []
    max_sample = int(config["ml_check"]["max_train_per_class"]) + int(config["ml_check"]["max_test_per_class"])
    stave_names = list(staves.keys())
    stave_channels = np.asarray([staves[name] for name in stave_names], dtype=int)
    stave_grid = np.asarray(stave_names)

    for run in configured_runs(config):
        path = raw_file(raw_root_dir, run)
        if not path.exists():
            raise FileNotFoundError(f"Configured run {run} is missing: {path}")

        group = group_for_run[run]
        run_counts = init_count_dict()
        for batch in iter_raw_events(path):
            event_numbers = np.asarray(batch["EVENTNO"])
            evt_numbers = np.asarray(batch["EVT"])
            all_events = np.stack(batch["HRDv"]).astype(np.float64).reshape(-1, 8, samples_per_channel)
            waveforms = all_events[:, stave_channels, :]
            baseline, amplitude, peak_sample, area = pulse_quantities(waveforms, baseline_indices)
            selected_mask = amplitude > cut
            event_selected = selected_mask.any(axis=1)

            run_counts["events_total"] += int(len(event_numbers))
            counts_by_group[group]["events_total"] += int(len(event_numbers))
            run_counts["events_with_selected"] += int(event_selected.sum())
            counts_by_group[group]["events_with_selected"] += int(event_selected.sum())
            run_counts["selected_pulses"] += int(selected_mask.sum())
            counts_by_group[group]["selected_pulses"] += int(selected_mask.sum())
            for idx, stave in enumerate(stave_names):
                stave_count = int(selected_mask[:, idx].sum())
                run_counts["staves"][stave] += stave_count
                counts_by_group[group]["staves"][stave] += stave_count

            event_idx, stave_idx = np.where(selected_mask)
            if len(event_idx):
                selected_frames.append(
                    pd.DataFrame(
                        {
                            "run": run,
                            "group": group,
                            "eventno": event_numbers[event_idx].astype(int),
                            "evt": evt_numbers[event_idx].astype(int),
                            "stave": stave_grid[stave_idx],
                            "channel": stave_channels[stave_idx].astype(int),
                            "baseline_adc": baseline[event_idx, stave_idx],
                            "amplitude_adc": amplitude[event_idx, stave_idx],
                            "peak_sample": peak_sample[event_idx, stave_idx].astype(int),
                            "area_adc_samples": area[event_idx, stave_idx],
                        }
                    )
                )

            flat_selected = selected_mask.ravel()
            # Keep a bounded random sample for the ML sanity check; the final cap is applied
            # after all runs so held-out runs remain represented.
            keep_probability = np.where(flat_selected, 0.20, 0.05)
            keep = rng.random(flat_selected.shape[0]) < keep_probability
            if keep.any():
                flat_stave = np.tile(np.arange(len(stave_names)), len(event_numbers))
                flat_event = np.repeat(np.arange(len(event_numbers)), len(stave_names))
                kept_event = flat_event[keep]
                kept_stave = flat_stave[keep]
                ml_frames.append(
                    pd.DataFrame(
                        {
                            "run": run,
                            "stave": stave_grid[kept_stave],
                            "amplitude_adc": amplitude[kept_event, kept_stave],
                            "area_adc_samples": area[kept_event, kept_stave],
                            "peak_sample": peak_sample[kept_event, kept_stave].astype(int),
                            "baseline_adc": baseline[kept_event, kept_stave],
                            "selected": flat_selected[keep].astype(int),
                        }
                    )
                )

        row = {
            "run": run,
            "group": group,
            "events_total": run_counts["events_total"],
            "events_with_selected": run_counts["events_with_selected"],
            "selected_pulses": run_counts["selected_pulses"],
        }
        row.update({stave: int(run_counts["staves"][stave]) for stave in staves})
        counts_by_run.append(row)

    group_rows = []
    for group in config["run_groups"]:
        counts = counts_by_group[group]
        row = {
            "group": group,
            "events_total": counts["events_total"],
            "events_with_selected": counts["events_with_selected"],
            "selected_pulses": counts["selected_pulses"],
        }
        row.update({stave: int(counts["staves"][stave]) for stave in staves})
        group_rows.append(row)

    selected = pd.concat(selected_frames, ignore_index=True) if selected_frames else pd.DataFrame()
    ml_rows = pd.concat(ml_frames, ignore_index=True) if ml_frames else pd.DataFrame()
    capped = []
    for selected_value, subset in ml_rows.groupby("selected"):
        n = min(len(subset), max_sample)
        capped.append(subset.sample(n=n, random_state=int(config["ml_check"]["random_seed"]) + int(selected_value)))
    ml_rows = pd.concat(capped, ignore_index=True)
    return pd.DataFrame(counts_by_run), pd.DataFrame(group_rows), counts_by_group, selected, ml_rows


def compare_expected(config: dict, counts_by_group: pd.DataFrame) -> pd.DataFrame:
    expected = config["expected_counts"]
    rows = [
        {
            "quantity": "total selected B-stave pulses",
            "report_value": int(expected["total_selected_pulses"]),
            "reproduced": int(counts_by_group["selected_pulses"].sum()),
            "tolerance": 0,
        }
    ]
    for group, group_expected in expected["groups"].items():
        row = counts_by_group[counts_by_group["group"] == group].iloc[0]
        if "events" in group_expected:
            rows.append(
                {
                    "quantity": f"{group} events with selected pulse",
                    "report_value": int(group_expected["events"]),
                    "reproduced": int(row["events_with_selected"]),
                    "tolerance": 0,
                }
            )
        if "pulses" in group_expected:
            rows.append(
                {
                    "quantity": f"{group} selected pulses",
                    "report_value": int(group_expected["pulses"]),
                    "reproduced": int(row["selected_pulses"]),
                    "tolerance": 0,
                }
            )
        for stave, value in group_expected.get("staves", {}).items():
            rows.append(
                {
                    "quantity": f"{group} {stave} selected pulses",
                    "report_value": int(value),
                    "reproduced": int(row[stave]),
                    "tolerance": 0,
                }
            )

    result = pd.DataFrame(rows)
    result["delta"] = result["reproduced"] - result["report_value"]
    result["pass"] = result["delta"].abs() <= result["tolerance"]
    return result[["quantity", "report_value", "reproduced", "delta", "tolerance", "pass"]]


def sorted_crosscheck(config: dict) -> pd.DataFrame:
    """Count hrdMax in sorted files for even channels only."""
    sorted_b_dir = Path(config["sorted_b_dir"])
    cut = float(config["amplitude_cut_adc"])
    staves = {name: int(idx) for name, idx in config["staves"].items()}
    rows = []
    for run in configured_runs(config):
        path = sorted_file(sorted_b_dir, run)
        if not path.exists():
            raise FileNotFoundError(f"Configured run {run} is missing: {path}")
        counts = defaultdict(int)
        events_with_selected = 0
        tree = uproot.open(path)["tree"]
        for batch in tree.iterate(["hrdMax"], step_size=10000, library="np"):
            for values in batch["hrdMax"]:
                arr = np.asarray(values, dtype=float)
                selected = 0
                for stave, channel in staves.items():
                    if arr[channel] > cut:
                        counts[stave] += 1
                        selected += 1
                if selected:
                    events_with_selected += 1
        row = {"run": run, "events_with_selected": events_with_selected, "selected_pulses": sum(counts.values())}
        row.update({stave: int(counts[stave]) for stave in staves})
        rows.append(row)
    return pd.DataFrame(rows)


def run_ml_check(config: dict, ml_rows: pd.DataFrame, out_dir: Path) -> pd.DataFrame:
    from sklearn.calibration import CalibratedClassifierCV, calibration_curve
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
    from sklearn.model_selection import StratifiedKFold, cross_val_score
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    heldout = set(int(run) for run in config["ml_check"]["heldout_runs"])
    train = ml_rows[~ml_rows["run"].isin(heldout)].copy()
    test = ml_rows[ml_rows["run"].isin(heldout)].copy()
    features = ["amplitude_adc", "area_adc_samples", "peak_sample", "baseline_adc"]
    c_values = [float(value) for value in config["ml_check"]["regularization_c"]]
    cv = StratifiedKFold(n_splits=int(config["ml_check"]["cv_folds"]), shuffle=True, random_state=int(config["ml_check"]["random_seed"]))

    cv_rows = []
    for c_value in c_values:
        model = make_pipeline(StandardScaler(), LogisticRegression(C=c_value, max_iter=1000, solver="lbfgs"))
        scores = cross_val_score(model, train[features], train["selected"], cv=cv, scoring="roc_auc")
        cv_rows.append({"C": c_value, "cv_roc_auc_mean": float(scores.mean()), "cv_roc_auc_std": float(scores.std(ddof=1))})
    best_c = max(cv_rows, key=lambda row: row["cv_roc_auc_mean"])["C"]

    base = make_pipeline(StandardScaler(), LogisticRegression(C=best_c, max_iter=1000, solver="lbfgs"))
    calibrated = CalibratedClassifierCV(base, cv=3, method="isotonic")
    calibrated.fit(train[features], train["selected"])
    probability = calibrated.predict_proba(test[features])[:, 1]
    predicted = probability >= 0.5
    y_test = test["selected"].to_numpy()
    deterministic = test["amplitude_adc"].to_numpy() > float(config["amplitude_cut_adc"])

    rng = np.random.default_rng(int(config["ml_check"]["random_seed"]))
    boot = []
    for _ in range(300):
        idx = rng.integers(0, len(test), len(test))
        boot.append(float(np.mean(predicted[idx] == y_test[idx])))
    lo, hi = np.quantile(boot, [0.025, 0.975])

    ml_summary = pd.DataFrame(
        [
            {
                "method": "traditional threshold",
                "heldout_runs": ",".join(str(run) for run in sorted(heldout)),
                "metric": "selection accuracy",
                "value": float(np.mean(deterministic == y_test)),
                "ci_low": 1.0,
                "ci_high": 1.0,
                "roc_auc": 1.0,
                "average_precision": 1.0,
                "brier": 0.0,
                "notes": "Deterministic A>1000 ADC rule.",
            },
            {
                "method": "calibrated logistic regression",
                "heldout_runs": ",".join(str(run) for run in sorted(heldout)),
                "metric": "selection accuracy",
                "value": float(np.mean(predicted == y_test)),
                "ci_low": float(lo),
                "ci_high": float(hi),
                "roc_auc": float(roc_auc_score(y_test, probability)),
                "average_precision": float(average_precision_score(y_test, probability)),
                "brier": float(brier_score_loss(y_test, probability)),
                "notes": f"Run-split sanity check; C={best_c}. Not used for the gate count.",
            },
        ]
    )
    pd.DataFrame(cv_rows).to_csv(out_dir / "ml_cv_scan.csv", index=False)
    ml_summary.to_csv(out_dir / "ml_benchmark.csv", index=False)

    frac_pos, mean_pred = calibration_curve(y_test, probability, n_bins=10, strategy="quantile")
    fig, ax = plt.subplots(figsize=(5, 4))
    ax.plot([0, 1], [0, 1], color="black", lw=1, linestyle="--")
    ax.plot(mean_pred, frac_pos, marker="o")
    ax.set_xlabel("Mean predicted probability")
    ax.set_ylabel("Observed selected fraction")
    ax.set_title("S00 ML sanity-check calibration")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_ml_reliability.png", dpi=160)
    plt.close(fig)

    return ml_summary


def write_checksums(config: dict, out_dir: Path) -> pd.DataFrame:
    files = []
    for path in sorted(Path("data/raw").glob("**/*")):
        if path.is_file():
            files.append(path)
    for run in configured_runs(config):
        files.append(raw_file(Path(config["raw_root_dir"]), run))
        files.append(sorted_file(Path(config["sorted_b_dir"]), run))

    rows = []
    for path in files:
        rows.append({"file": str(path), "sha256": sha256_file(path), "bytes": path.stat().st_size})
    df = pd.DataFrame(rows)
    df.to_csv(out_dir / "input_sha256.csv", index=False)
    return df


def make_figures(counts_by_run: pd.DataFrame, selected: pd.DataFrame, out_dir: Path) -> None:
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.bar(counts_by_run["run"].astype(str), counts_by_run["selected_pulses"], color="#3b6ea8")
    ax.set_xlabel("Run")
    ax.set_ylabel("Selected B-stave pulses")
    ax.set_title("S00 selected pulses by run")
    ax.tick_params(axis="x", labelrotation=90)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_counts_by_run.png", dpi=160)
    plt.close(fig)

    group_staves = selected.groupby(["group", "stave"]).size().unstack(fill_value=0)
    fig, ax = plt.subplots(figsize=(8, 4))
    group_staves.plot(kind="bar", ax=ax)
    ax.set_xlabel("Run group")
    ax.set_ylabel("Selected pulses")
    ax.set_title("S00 selected pulses by group and stave")
    ax.tick_params(axis="x", labelrotation=30)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_counts_by_group_stave.png", dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 4))
    for stave, subset in selected.groupby("stave"):
        values = np.log10(subset["amplitude_adc"].to_numpy())
        ax.hist(values, bins=60, histtype="step", linewidth=1.4, label=stave)
    ax.set_xlabel("log10(amplitude ADC)")
    ax.set_ylabel("Selected pulses")
    ax.set_title("S00 selected-pulse amplitude distributions")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_dir / "fig_amplitude_distributions.png", dpi=160)
    plt.close(fig)


def write_manifest(out_dir: Path, config_path: Path, comparison: pd.DataFrame, selected_path: Path) -> None:
    manifest = {
        "config": str(config_path),
        "count_match_passed": bool(comparison["pass"].all()),
        "selected_pulse_table": str(selected_path),
        "artifacts": sorted(path.name for path in out_dir.iterdir() if path.is_file()),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="configs/s00_reproduction.yaml", type=Path)
    parser.add_argument("--skip-ml", action="store_true", help="Skip the run-split ML sanity check.")
    parser.add_argument("--skip-sha256", action="store_true", help="Skip checksum manifest generation.")
    args = parser.parse_args()

    config = load_config(args.config)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    selected_path = Path(config["pulse_table_path"])
    selected_path.parent.mkdir(parents=True, exist_ok=True)

    counts_by_run, counts_by_group, _, selected, ml_rows = scan_raw(config)
    comparison = compare_expected(config, counts_by_group)
    sorted_counts = sorted_crosscheck(config)
    sorted_compare = counts_by_run[["run", "selected_pulses", "B2", "B4", "B6", "B8"]].merge(
        sorted_counts[["run", "selected_pulses", "B2", "B4", "B6", "B8"]],
        on="run",
        suffixes=("_raw", "_sorted_even"),
    )

    counts_by_run.to_csv(out_dir / "counts_by_run.csv", index=False)
    counts_by_group.to_csv(out_dir / "counts_by_group.csv", index=False)
    comparison.to_csv(out_dir / "count_match_table.csv", index=False)
    sorted_compare.to_csv(out_dir / "sorted_even_channel_crosscheck.csv", index=False)
    selected.to_csv(selected_path, index=False, compression="gzip")
    make_figures(counts_by_run, selected, out_dir)

    if not args.skip_ml:
        run_ml_check(config, ml_rows, out_dir)
    if not args.skip_sha256:
        write_checksums(config, out_dir)
    write_manifest(out_dir, args.config, comparison, selected_path)

    print(comparison.to_string(index=False))
    print(f"\nselected pulse table: {selected_path}")
    print(f"report artifacts: {out_dir}")
    return 0 if bool(comparison["pass"].all()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
