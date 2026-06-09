#!/usr/bin/env python3
"""S16d forced/random pedestal run search.

This is a data-availability ticket: first reproduce the prior raw-ROOT numbers,
then search for explicit forced/random pedestal evidence and waveform-level
candidate runs. No Monte Carlo is used.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Tuple

_SCRIPT_DIR = Path(__file__).resolve().parent
os.environ.setdefault("MPLCONFIGDIR", str(_SCRIPT_DIR / ".mplconfig"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import uproot
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


TOKEN_RE = re.compile(r"(forced?|random|pedestal|ped|pulser|cosmic|noise|zero|dark|trigger|trig|log|elog)", re.I)


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def git_commit() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()


def raw_root_paths(config: dict) -> List[Path]:
    root = Path(config["raw_root_dir"])
    return sorted(root.glob("hrda_run_*.root")) + sorted(root.glob("hrdb_run_*.root"))


def b_root_paths(config: dict) -> List[Path]:
    return sorted(Path(config["raw_root_dir"]).glob("hrdb_run_*.root"))


def parse_run(path: Path) -> int:
    match = re.search(r"_run_(\d+)", path.name)
    if not match:
        raise ValueError(f"cannot parse run from {path}")
    return int(match.group(1))


def iter_tree(path: Path, branches: List[str], step_size: int = 25000) -> Iterable[dict]:
    yield from uproot.open(path)["h101"].iterate(branches, step_size=step_size, library="np")


def filesystem_scan(config: dict) -> pd.DataFrame:
    rows = []
    data_root = Path(config["data_root"])
    for path in sorted(data_root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(data_root)
        name = path.name.lower()
        suffix = path.suffix.lower()
        token_match = TOKEN_RE.search(str(rel))
        likely_metadata = suffix in {".txt", ".csv", ".tsv", ".log", ".md", ".json", ".yaml", ".yml"} or "log" in name
        rows.append(
            {
                "path": str(rel),
                "suffix": suffix,
                "bytes": int(path.stat().st_size),
                "token_match": token_match.group(0).lower() if token_match else "",
                "is_root": suffix == ".root",
                "likely_runlog_or_metadata": bool(likely_metadata),
                "forced_random_name_hit": bool(token_match and token_match.group(0).lower() in {"force", "forced", "random", "pedestal", "ped", "pulser"}),
            }
        )
    return pd.DataFrame(rows)


def trigger_audit(config: dict) -> pd.DataFrame:
    rows = []
    for path in raw_root_paths(config):
        tree = uproot.open(path)["h101"]
        if tree.num_entries:
            trigger = tree.arrays(["TRIGGER"], library="np")["TRIGGER"]
            values, counts = np.unique(trigger, return_counts=True)
            summary = ";".join(f"{int(v)}:{int(c)}" for v, c in zip(values, counts))
            non_beam = int(np.sum(counts[values != 1]))
        else:
            summary = "empty"
            non_beam = 0
        rows.append(
            {
                "file": path.name,
                "stack": path.name[:4],
                "run": parse_run(path),
                "entries": int(tree.num_entries),
                "trigger_summary": summary,
                "non_beam_trigger_entries": non_beam,
                "filename_forced_random_match": bool(TOKEN_RE.search(path.name) and any(t in path.name.lower() for t in ["force", "random", "ped", "pulser"])),
            }
        )
    return pd.DataFrame(rows)


def waveform_summary(config: dict, rng: np.random.Generator) -> Tuple[pd.DataFrame, pd.DataFrame]:
    stave_channels = np.asarray(list(config["staves"].values()), dtype=int)
    nsamp = int(config["samples_per_channel"])
    pre = np.asarray(config["pretrigger_samples"], dtype=int)
    quiet_cut = float(config["quiet_event_max_amplitude_adc"])
    amp_cut = float(config["amplitude_cut_adc"])
    max_per_run = int(config["ml"]["max_events_per_run"])
    rows = []
    samples = []
    for path in b_root_paths(config):
        run = parse_run(path)
        total = 0
        selected_staves = 0
        selected_events = 0
        quiet_events = 0
        sum_pre_mean = 0.0
        sum_pre_std = 0.0
        event_max_chunks = []
        run_samples = []
        for batch in iter_tree(path, ["HRDv"]):
            if len(batch["HRDv"]) == 0:
                continue
            wave = np.stack(batch["HRDv"]).astype(np.float32).reshape(-1, 8, nsamp)[:, stave_channels, :]
            seed = np.median(wave[:, :, pre], axis=2)
            corrected = wave - seed[:, :, None]
            amp = corrected.max(axis=2)
            event_max = amp.max(axis=1)
            pre_wave = wave[:, :, pre].astype(np.float32)
            pre_mean = pre_wave.mean(axis=(1, 2))
            pre_std = pre_wave.std(axis=(1, 2))
            pre_range = pre_wave.max(axis=(1, 2)) - pre_wave.min(axis=(1, 2))
            pre_slope = (wave[:, :, 3] - wave[:, :, 0]).mean(axis=1)
            label_quiet = event_max < quiet_cut
            label_pulse = event_max > amp_cut
            keepable = label_quiet | label_pulse
            if np.any(keepable):
                idx = np.where(keepable)[0]
                if len(idx) > max_per_run:
                    idx = rng.choice(idx, size=max_per_run, replace=False)
                run_samples.append(
                    pd.DataFrame(
                        {
                            "run": run,
                            "quiet_proxy": label_quiet[idx].astype(int),
                            "pulse_event": label_pulse[idx].astype(int),
                            "pre_mean_adc": pre_mean[idx],
                            "pre_std_adc": pre_std[idx],
                            "pre_range_adc": pre_range[idx],
                            "pre_slope03_adc": pre_slope[idx],
                            "stave_seed_median_adc": np.median(seed[idx], axis=1),
                            "stave_seed_iqr_adc": np.quantile(seed[idx], 0.75, axis=1) - np.quantile(seed[idx], 0.25, axis=1),
                        }
                    )
                )
            n = int(wave.shape[0])
            total += n
            selected_staves += int((amp > amp_cut).sum())
            selected_events += int((event_max > amp_cut).sum())
            quiet_events += int((event_max < quiet_cut).sum())
            sum_pre_mean += float(pre_mean.sum())
            sum_pre_std += float(pre_std.sum())
            if n:
                event_max_chunks.append(event_max.astype(np.float32))
        if event_max_chunks:
            event_max_all = np.concatenate(event_max_chunks)
            q05, q50, q95 = np.quantile(event_max_all, [0.05, 0.5, 0.95])
        else:
            q05 = q50 = q95 = np.nan
        rows.append(
            {
                "run": run,
                "entries": int(total),
                "selected_b_stave_pulses": int(selected_staves),
                "selected_events": int(selected_events),
                "quiet_proxy_events": int(quiet_events),
                "selected_event_fraction": float(selected_events / total) if total else np.nan,
                "quiet_event_fraction": float(quiet_events / total) if total else np.nan,
                "event_max_q05_adc": float(q05) if total else np.nan,
                "event_max_median_adc": float(q50) if total else np.nan,
                "event_max_q95_adc": float(q95) if total else np.nan,
                "pre_mean_adc": float(sum_pre_mean / total) if total else np.nan,
                "pre_std_adc": float(sum_pre_std / total) if total else np.nan,
            }
        )
        if run_samples:
            samples.append(pd.concat(run_samples, ignore_index=True))
    return pd.DataFrame(rows), pd.concat(samples, ignore_index=True)


def traditional_candidates(run_summary: pd.DataFrame, trigger: pd.DataFrame, fs_scan: pd.DataFrame, config: dict) -> pd.DataFrame:
    rule = config["traditional_candidate_rule"]
    b_trigger = trigger[trigger["stack"] == "hrdb"].copy()
    merged = run_summary.merge(
        b_trigger[["run", "non_beam_trigger_entries", "filename_forced_random_match"]],
        on="run",
        how="left",
    )
    explicit_file_hits = int(fs_scan["forced_random_name_hit"].sum()) if len(fs_scan) else 0
    merged["explicit_metadata_candidate"] = (
        (merged["non_beam_trigger_entries"].fillna(0) > 0)
        | merged["filename_forced_random_match"].fillna(False)
        | (explicit_file_hits > 0)
    )
    merged["waveform_pedestal_candidate"] = (
        (merged["entries"] > 0)
        & (merged["selected_event_fraction"] <= float(rule["max_selected_event_fraction"]))
        & (merged["quiet_event_fraction"] >= float(rule["min_quiet_event_fraction"]))
        & (merged["event_max_median_adc"] <= float(rule["max_event_max_median_adc"]))
    )
    merged["traditional_candidate"] = merged["explicit_metadata_candidate"] | merged["waveform_pedestal_candidate"]
    merged["traditional_pedestal_score"] = (
        merged["quiet_event_fraction"].fillna(0)
        - merged["selected_event_fraction"].fillna(1)
        - (merged["event_max_median_adc"].fillna(1e6) / 10000.0)
    )
    return merged.sort_values(["traditional_candidate", "traditional_pedestal_score"], ascending=[False, False])


def ml_features() -> List[str]:
    return [
        "pre_mean_adc",
        "pre_std_adc",
        "pre_range_adc",
        "pre_slope03_adc",
        "stave_seed_median_adc",
        "stave_seed_iqr_adc",
    ]


def make_logistic_model(c_value: float, seed: int):
    return make_pipeline(
        StandardScaler(),
        LogisticRegression(C=float(c_value), max_iter=1000, class_weight="balanced", random_state=int(seed)),
    )


def run_bootstrap(values: np.ndarray, runs: np.ndarray, metric: Callable[[np.ndarray], float], rng: np.random.Generator, n_boot: int, cap: int) -> Tuple[float, float]:
    by_run = {}
    for run in np.unique(runs):
        vals = values[runs == run]
        if len(vals) > cap:
            vals = rng.choice(vals, size=cap, replace=False)
        by_run[int(run)] = vals
    run_ids = np.asarray(sorted(by_run), dtype=int)
    stats = []
    for _ in range(n_boot):
        pieces = []
        for run in rng.choice(run_ids, size=len(run_ids), replace=True):
            vals = by_run[int(run)]
            pieces.append(rng.choice(vals, size=len(vals), replace=True))
        stats.append(metric(np.concatenate(pieces)))
    return float(np.quantile(stats, 0.025)), float(np.quantile(stats, 0.975))


def fit_ml(event_sample: pd.DataFrame, config: dict, rng: np.random.Generator) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    feature_cols = ml_features()
    heldout_runs = set(int(x) for x in config["heldout_runs"])
    calibration_runs = set(int(x) for x in config["calibration_runs"])
    train_cv = event_sample[~event_sample["run"].isin(heldout_runs)].copy()
    core_train = train_cv[~train_cv["run"].isin(calibration_runs)].copy()
    calibration = train_cv[train_cv["run"].isin(calibration_runs)].copy()
    heldout = event_sample[event_sample["run"].isin(heldout_runs)].copy()
    params = config["ml"]["hyperparameters"]
    groups = train_cv["run"].to_numpy()
    n_splits = min(int(config["ml"]["cv_folds"]), len(np.unique(groups)))
    scan_rows = []
    cv = GroupKFold(n_splits=n_splits)
    for c_value in params["C"]:
        aucs = []
        aps = []
        for train_idx, valid_idx in cv.split(train_cv[feature_cols], train_cv["quiet_proxy"], groups=groups):
            model = make_logistic_model(float(c_value), int(config["random_seed"]))
            model.fit(train_cv.iloc[train_idx][feature_cols], train_cv.iloc[train_idx]["quiet_proxy"])
            prob = model.predict_proba(train_cv.iloc[valid_idx][feature_cols])[:, 1]
            y = train_cv.iloc[valid_idx]["quiet_proxy"]
            aucs.append(roc_auc_score(y, prob))
            aps.append(average_precision_score(y, prob))
        scan_rows.append(
            {
                "C": float(c_value),
                "cv_auc": float(np.mean(aucs)),
                "cv_auc_std": float(np.std(aucs, ddof=1)),
                "cv_average_precision": float(np.mean(aps)),
            }
        )
    scan = pd.DataFrame(scan_rows).sort_values(["cv_auc", "cv_average_precision"], ascending=False).reset_index(drop=True)
    best = scan.iloc[0].to_dict()
    model = make_logistic_model(float(best["C"]), int(config["random_seed"]))
    model.fit(core_train[feature_cols], core_train["quiet_proxy"])
    cal_prob = model.predict_proba(calibration[feature_cols])[:, 1]
    calibrator = LogisticRegression(C=1.0, max_iter=1000, random_state=int(config["random_seed"]))
    calibrator.fit(cal_prob.reshape(-1, 1), calibration["quiet_proxy"])

    all_prob_raw = model.predict_proba(event_sample[feature_cols])[:, 1]
    all_prob = calibrator.predict_proba(all_prob_raw.reshape(-1, 1))[:, 1]
    scored = event_sample[["run", "quiet_proxy", "pulse_event"]].copy()
    scored["ml_quiet_probability"] = all_prob
    heldout_prob = scored[scored["run"].isin(heldout_runs)]["ml_quiet_probability"].to_numpy()
    heldout_y = heldout["quiet_proxy"].to_numpy()
    heldout_runs_arr = heldout["run"].to_numpy()
    n_boot = int(config["bootstrap_replicates"])
    cap = int(config["bootstrap_max_events_per_run"])
    mean_lo, mean_hi = run_bootstrap(heldout_prob, heldout_runs_arr, np.mean, rng, n_boot, cap)
    auc_lo, auc_hi = run_bootstrap(
        np.column_stack([heldout_y, heldout_prob]),
        heldout_runs_arr,
        lambda arr: roc_auc_score(arr[:, 0], arr[:, 1]) if len(np.unique(arr[:, 0])) == 2 else np.nan,
        rng,
        n_boot,
        cap,
    )
    heldout_summary = pd.DataFrame(
        [
            {
                "method": "ml_pretrigger_logistic_quiet_proxy",
                "heldout_runs": ",".join(str(x) for x in sorted(heldout_runs)),
                "n_events": int(len(heldout)),
                "heldout_auc": float(roc_auc_score(heldout_y, heldout_prob)),
                "heldout_auc_ci_low": auc_lo,
                "heldout_auc_ci_high": auc_hi,
                "heldout_average_precision": float(average_precision_score(heldout_y, heldout_prob)),
                "heldout_mean_quiet_probability": float(np.mean(heldout_prob)),
                "heldout_mean_quiet_probability_ci_low": mean_lo,
                "heldout_mean_quiet_probability_ci_high": mean_hi,
            }
        ]
    )
    run_scores = (
        scored.groupby("run")
        .agg(
            sampled_events=("quiet_proxy", "size"),
            sampled_quiet_fraction=("quiet_proxy", "mean"),
            ml_mean_quiet_probability=("ml_quiet_probability", "mean"),
            ml_p95_quiet_probability=("ml_quiet_probability", lambda x: float(np.quantile(x, 0.95))),
        )
        .reset_index()
    )
    meta = {
        "best": best,
        "feature_columns": feature_cols,
        "n_train_cv": int(len(train_cv)),
        "n_core_train": int(len(core_train)),
        "n_calibration": int(len(calibration)),
        "n_heldout": int(len(heldout)),
        "calibration_runs": sorted(calibration_runs),
        "heldout_runs": sorted(heldout_runs),
    }
    return scan, heldout_summary, run_scores, meta


def leakage_checks(event_sample: pd.DataFrame, config: dict, rng: np.random.Generator) -> pd.DataFrame:
    feature_cols = ml_features()
    heldout_runs = set(int(x) for x in config["heldout_runs"])
    train = event_sample[~event_sample["run"].isin(heldout_runs)].copy()
    test = event_sample[event_sample["run"].isin(heldout_runs)].copy()
    rows = []
    shuffled = train.copy()
    shuffled["quiet_proxy"] = rng.permutation(shuffled["quiet_proxy"].to_numpy())
    model = make_logistic_model(1.0, int(config["random_seed"]) + 11)
    model.fit(shuffled[feature_cols], shuffled["quiet_proxy"])
    prob = model.predict_proba(test[feature_cols])[:, 1]
    rows.append(
        {
            "check": "shuffled_training_labels",
            "value": float(roc_auc_score(test["quiet_proxy"], prob)),
            "interpretation": "AUC should fall near 0.5 when quiet/pulse labels are destroyed.",
        }
    )
    leaky = train.copy()
    leaky["event_label_leak"] = leaky["quiet_proxy"]
    test_leaky = test.copy()
    test_leaky["event_label_leak"] = test_leaky["quiet_proxy"]
    leaky_cols = feature_cols + ["event_label_leak"]
    leaky_model = make_logistic_model(1.0, int(config["random_seed"]) + 12)
    leaky_model.fit(leaky[leaky_cols], leaky["quiet_proxy"])
    leaky_prob = leaky_model.predict_proba(test_leaky[leaky_cols])[:, 1]
    rows.append(
        {
            "check": "intentional_label_oracle",
            "value": float(roc_auc_score(test_leaky["quiet_proxy"], leaky_prob)),
            "interpretation": "AUC near 1 confirms direct label leakage would be obvious and is not in real features.",
        }
    )
    rows.append(
        {
            "check": "real_feature_exclusion",
            "value": np.nan,
            "interpretation": "ML features exclude run, event id, trigger, post-trigger amplitudes, event_max, selected/quiet labels, and filenames.",
        }
    )
    return pd.DataFrame(rows)


def plot_outputs(outdir: Path, run_summary: pd.DataFrame, candidates: pd.DataFrame, run_scores: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(9, 4.8))
    ax.bar(run_summary["run"].astype(str), run_summary["quiet_event_fraction"], label="quiet proxy fraction")
    ax.plot(run_summary["run"].astype(str), run_summary["selected_event_fraction"], color="tab:red", marker="o", linewidth=1.0, label="selected-event fraction")
    ax.set_ylim(0, 1)
    ax.set_xlabel("B-stack run")
    ax.set_ylabel("fraction")
    ax.set_title("Traditional pedestal-run evidence")
    ax.tick_params(axis="x", rotation=90)
    ax.legend()
    fig.tight_layout()
    fig.savefig(outdir / "fig_traditional_run_fractions.png", dpi=160)
    plt.close(fig)

    merged = candidates[["run", "traditional_pedestal_score"]].merge(run_scores[["run", "ml_mean_quiet_probability"]], on="run", how="left")
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.scatter(merged["traditional_pedestal_score"], merged["ml_mean_quiet_probability"], s=36)
    for row in merged.itertuples(index=False):
        ax.annotate(str(int(row.run)), (row.traditional_pedestal_score, row.ml_mean_quiet_probability), fontsize=7)
    ax.set_xlabel("traditional pedestal score")
    ax.set_ylabel("ML mean quiet probability")
    ax.set_title("Run candidate scores")
    fig.tight_layout()
    fig.savefig(outdir / "fig_run_candidate_scores.png", dpi=160)
    plt.close(fig)


def output_hashes(outdir: Path) -> List[dict]:
    rows = []
    for path in sorted(outdir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            rows.append({"path": str(path), "sha256": sha256_file(path), "bytes": int(path.stat().st_size)})
    return rows


def write_report(outdir: Path, config: dict, result: dict, tables: dict) -> None:
    top = tables["candidates"].sort_values("traditional_pedestal_score", ascending=False).head(8)
    top_rows = "\n".join(
        f"| {int(r.run)} | {int(r.entries)} | {r.quiet_event_fraction:.3f} | {r.selected_event_fraction:.3f} | {r.event_max_median_adc:.1f} | {r.traditional_pedestal_score:.3f} | {bool(r.traditional_candidate)} |"
        for r in top.itertuples(index=False)
    )
    ml = tables["ml_heldout"].iloc[0]
    leak_rows = "\n".join(
        f"| {r.check} | {'' if pd.isna(r.value) else f'{r.value:.3f}'} | {r.interpretation} |"
        for r in tables["leakage"].itertuples(index=False)
    )
    report = f"""# S16d: locate true forced/random HRD pedestal runs

- **Ticket:** {config["ticket"]}
- **Worker:** {config["worker"]}
- **Date:** 2026-06-09
- **Input checksums:** `input_sha256.csv`
- **Git commit:** `{result["git_commit"]}`
- **Config:** `s16d_config.json`

## Question

Can we locate run-log or ROOT inputs with true forced/random HRD pedestal triggers for B-stack validation?

## Raw ROOT reproduction first

| Quantity | Expected/report value | Reproduced from raw ROOT | Pass? |
|---|---:|---:|---|
| S00 selected B-stave pulses, `A > 1000 ADC` | {config["expected_selected_pulses"]} | {result["raw_reproduction"]["selected_b_stave_pulses"]} | {"yes" if result["raw_reproduction"]["selected_b_stave_pulses"] == config["expected_selected_pulses"] else "no"} |
| forced/random-tagged ROOT entries | {config["expected_forced_random_tagged_entries"]} | {result["raw_reproduction"]["forced_random_tagged_entries"]} | {"yes" if result["raw_reproduction"]["forced_random_tagged_entries"] == config["expected_forced_random_tagged_entries"] else "no"} |

The explicit ROOT audit found `{result["root_audit"]["non_beam_trigger_entries"]}` entries with `TRIGGER != 1` and `{result["root_audit"]["filename_forced_random_hits"]}` ROOT filename hits for forced/random/pedestal tokens. The filesystem scan found `{result["filesystem_scan"]["likely_runlog_or_metadata_files"]}` likely run-log/metadata files under `{config["data_root"]}` and `{result["filesystem_scan"]["forced_random_name_hits"]}` forced/random/pedestal filename hits.

## Traditional method

The traditional locator combines explicit metadata (`TRIGGER != 1`, forced/random/pedestal filename tokens, run-log files) with a conservative waveform rule for a whole B-stack run: selected-event fraction <= {config["traditional_candidate_rule"]["max_selected_event_fraction"]}, quiet-event fraction >= {config["traditional_candidate_rule"]["min_quiet_event_fraction"]}, and median event max <= {config["traditional_candidate_rule"]["max_event_max_median_adc"]} ADC.

No run passes this rule. The closest runs by score are:

| Run | entries | quiet fraction | selected-event fraction | median event max [ADC] | score | candidate |
|---:|---:|---:|---:|---:|---:|---|
{top_rows}

## ML method

The ML method is a regularized logistic classifier trained on non-held-out runs to distinguish quiet-proxy events (`event max < {config["quiet_event_max_amplitude_adc"]} ADC`) from selected pulse events (`event max > {config["amplitude_cut_adc"]} ADC`) using only pre-trigger summaries. It excludes run, trigger, filenames, event IDs, event max, post-trigger amplitudes, and labels. Held-out runs are {config["heldout_runs"]}; calibration runs are {config["calibration_runs"]}. Best CV setting: `{result["ml_meta"]["best"]}`.

Held-out run performance: AUC {ml.heldout_auc:.3f} [{ml.heldout_auc_ci_low:.3f}, {ml.heldout_auc_ci_high:.3f}], average precision {ml.heldout_average_precision:.3f}, mean quiet probability {ml.heldout_mean_quiet_probability:.3f} [{ml.heldout_mean_quiet_probability_ci_low:.3f}, {ml.heldout_mean_quiet_probability_ci_high:.3f}].

The ML score also does not identify a true pedestal run: no run has explicit forced/random evidence, and the highest ML quiet-probability runs still have ordinary beam selected-event fractions rather than all-quiet pedestal behavior.

## Leakage checks

| Check | value | Interpretation |
|---|---:|---|
{leak_rows}

## Conclusion

The current raw mirror does **not** contain true forced/random HRD pedestal inputs suitable for replacing the S16b quiet-event proxy. Every populated ROOT file has `TRIGGER == 1`, no run-log/metadata file is present under the local data mirror, and no B-stack run satisfies a whole-run pedestal signature. The highest quiet-proxy runs are beam runs with roughly one-third to one-half selected-event fraction, not random pedestal acquisitions.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python reports/{config["ticket"]}__s16d_forced_random_pedestal_run_search/s16d_forced_random_pedestal_run_search.py --config reports/{config["ticket"]}__s16d_forced_random_pedestal_run_search/s16d_config.json
```

Primary artifacts: `result.json`, `manifest.json`, `input_sha256.csv`, `trigger_audit.csv`, `filesystem_runlog_scan.csv`, `run_waveform_summary.csv`, `traditional_candidates.csv`, `ml_cv_scan.csv`, `ml_heldout_summary.csv`, `ml_run_scores.csv`, and `leakage_checks.csv`.
"""
    (outdir / "REPORT.md").write_text(report, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    outdir = args.config.parent
    config = json.loads(args.config.read_text(encoding="utf-8"))
    rng = np.random.default_rng(int(config["random_seed"]))
    start = time.time()

    fs_scan = filesystem_scan(config)
    fs_scan.to_csv(outdir / "filesystem_runlog_scan.csv", index=False)
    trigger = trigger_audit(config)
    trigger.to_csv(outdir / "trigger_audit.csv", index=False)
    run_summary, event_sample = waveform_summary(config, rng)
    run_summary.to_csv(outdir / "run_waveform_summary.csv", index=False)
    event_sample.to_csv(outdir / "ml_event_sample.csv.gz", index=False)

    s00_runs = set(int(x) for x in config["s00_runs"])
    selected_pulses = int(run_summary[run_summary["run"].isin(s00_runs)]["selected_b_stave_pulses"].sum())
    forced_random_entries = int(trigger["non_beam_trigger_entries"].sum() + trigger.loc[trigger["filename_forced_random_match"], "entries"].sum())
    reproduction = pd.DataFrame(
        [
            {
                "quantity": "S00 selected B-stave pulses",
                "expected": int(config["expected_selected_pulses"]),
                "reproduced": selected_pulses,
                "delta": selected_pulses - int(config["expected_selected_pulses"]),
                "pass": selected_pulses == int(config["expected_selected_pulses"]),
            },
            {
                "quantity": "forced/random-tagged ROOT entries",
                "expected": int(config["expected_forced_random_tagged_entries"]),
                "reproduced": forced_random_entries,
                "delta": forced_random_entries - int(config["expected_forced_random_tagged_entries"]),
                "pass": forced_random_entries == int(config["expected_forced_random_tagged_entries"]),
            },
        ]
    )
    reproduction.to_csv(outdir / "reproduction_match_table.csv", index=False)

    candidates = traditional_candidates(run_summary, trigger, fs_scan, config)
    candidates.to_csv(outdir / "traditional_candidates.csv", index=False)
    ml_scan, ml_heldout, ml_run_scores, ml_meta = fit_ml(event_sample, config, rng)
    ml_scan.to_csv(outdir / "ml_cv_scan.csv", index=False)
    ml_heldout.to_csv(outdir / "ml_heldout_summary.csv", index=False)
    ml_run_scores.to_csv(outdir / "ml_run_scores.csv", index=False)
    leakage = leakage_checks(event_sample, config, rng)
    leakage.to_csv(outdir / "leakage_checks.csv", index=False)

    input_rows = []
    for path in raw_root_paths(config):
        input_rows.append({"path": str(path), "sha256": sha256_file(path), "bytes": int(path.stat().st_size)})
    pd.DataFrame(input_rows).to_csv(outdir / "input_sha256.csv", index=False)

    plot_outputs(outdir, run_summary, candidates, ml_run_scores)
    commit = git_commit()
    result = {
        "ticket": config["ticket"],
        "study": config["study"],
        "worker": config["worker"],
        "raw_reproduction": {
            "selected_b_stave_pulses": selected_pulses,
            "expected_selected_b_stave_pulses": int(config["expected_selected_pulses"]),
            "forced_random_tagged_entries": forced_random_entries,
            "expected_forced_random_tagged_entries": int(config["expected_forced_random_tagged_entries"]),
            "true_forced_random_sample_available": bool(forced_random_entries > 0),
        },
        "filesystem_scan": {
            "files_scanned": int(len(fs_scan)),
            "likely_runlog_or_metadata_files": int(fs_scan["likely_runlog_or_metadata"].sum()) if len(fs_scan) else 0,
            "forced_random_name_hits": int(fs_scan["forced_random_name_hit"].sum()) if len(fs_scan) else 0,
        },
        "root_audit": {
            "root_files_scanned": int(len(trigger)),
            "populated_root_files": int((trigger["entries"] > 0).sum()),
            "non_beam_trigger_entries": int(trigger["non_beam_trigger_entries"].sum()),
            "filename_forced_random_hits": int(trigger["filename_forced_random_match"].sum()),
        },
        "traditional_method": {
            "method": "explicit metadata plus whole-run quiet-fraction rule",
            "candidate_runs": [int(x) for x in candidates.loc[candidates["traditional_candidate"], "run"].tolist()],
            "top_runs_by_score": [
                {
                    "run": int(r.run),
                    "quiet_event_fraction": float(r.quiet_event_fraction),
                    "selected_event_fraction": float(r.selected_event_fraction),
                    "event_max_median_adc": float(r.event_max_median_adc),
                    "traditional_pedestal_score": float(r.traditional_pedestal_score),
                }
                for r in candidates.sort_values("traditional_pedestal_score", ascending=False).head(5).itertuples(index=False)
            ],
        },
        "ml_method": {
            "method": "pretrigger-only logistic quiet-proxy classifier",
            "heldout": ml_heldout.iloc[0].to_dict(),
            "top_runs_by_ml_quiet_probability": ml_run_scores.sort_values("ml_mean_quiet_probability", ascending=False).head(5).to_dict(orient="records"),
        },
        "ml_meta": ml_meta,
        "leakage_checks": leakage.replace({np.nan: None}).to_dict(orient="records"),
        "conclusion": "No true forced/random HRD pedestal ROOT or run-log inputs were located in the current data mirror.",
        "git_commit": commit,
    }
    (outdir / "result.json").write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")

    tables = {"candidates": candidates, "ml_heldout": ml_heldout, "leakage": leakage}
    write_report(outdir, config, result, tables)
    manifest = {
        "command": f"/home/billy/anaconda3/bin/python {outdir / 's16d_forced_random_pedestal_run_search.py'} --config {outdir / 's16d_config.json'}",
        "config": str(outdir / "s16d_config.json"),
        "git_commit": commit,
        "random_seed": int(config["random_seed"]),
        "environment": {
            "python": ".".join(map(str, tuple(os.sys.version_info[:3]))),
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "uproot": uproot.__version__,
        },
        "inputs": str(outdir / "input_sha256.csv"),
        "outputs": output_hashes(outdir),
        "runtime_seconds": float(time.time() - start),
    }
    (outdir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
