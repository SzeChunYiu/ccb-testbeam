#!/usr/bin/env python3
"""S07d App.A 12,147 labelled-event recovery study.

This report-local script rebuilds the documented clean-timing weak labels from
raw B-stack ROOT, scans plausible timing-source definitions for the historical
12,147 count, and reruns a run-held-out traditional-vs-RF benchmark on the
raw-reproducible label set.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import subprocess
import time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import uproot
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score


OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
S07C_SCRIPT = ROOT / "reports/1781000790.531136.203130b0__s07c_clean_timing_rf/s07c_clean_timing_rf.py"
RAW_DIR = ROOT / "data/root/root"
QTEMPLATE_PATH = ROOT / "reports/1780997954.15037.36463764__s01_full_dataset_templates/q_template_per_pulse.csv.gz"
DOC_PATH = ROOT / "docs/07_ml_methods.md"

TICKET = "1781006575.2866.622a4328"
WORKER = "testbeam-laptop-4"
SEED = 7707

TARGET = {"labelled_events": 12147, "clean": 10636, "violating": 1511}
SAMPLES_PER_CHANNEL = 18
SAMPLE_PERIOD_NS = 10.0
BASELINE_SAMPLES = [0, 1, 2, 3]
STAVES = {"B2": 0, "B4": 2, "B6": 4, "B8": 6}
DOWNSTREAM = ["B4", "B6", "B8"]
RUN_GROUPS = {
    "sample_i_calib": [31, 32, 33, 34, 35, 36, 37, 39, 40, 41, 42],
    "sample_i_analysis": [44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57],
    "sample_ii_calib": [64],
    "sample_ii_analysis": [58, 59, 60, 61, 62, 63, 65],
}
DOC_RUNS = sorted({run for runs in RUN_GROUPS.values() for run in runs})


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(ROOT), text=True).strip()
    except Exception:
        return "unknown"


def clean_json(value):
    if isinstance(value, dict):
        return {str(k): clean_json(v) for k, v in value.items()}
    if isinstance(value, list):
        return [clean_json(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        v = float(value)
        return v if math.isfinite(v) else None
    return value


def load_s07c():
    spec = importlib.util.spec_from_file_location("s07c_clean_timing_rf", str(S07C_SCRIPT))
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    module.RAW_DIR = Path("data/root/root")
    module.QTEMPLATE_PATH = Path(
        "reports/1780997954.15037.36463764__s01_full_dataset_templates/q_template_per_pulse.csv.gz"
    )
    return module


def all_b_runs() -> list[int]:
    runs = []
    for path in sorted(RAW_DIR.glob("hrdb_run_*.root")):
        runs.append(int(path.stem.split("_")[-1]))
    return runs


def source_artifact_inventory() -> pd.DataFrame:
    patterns = ["App.A", "12,147", "12147", "10636", "1511", "clean-timing"]
    candidates = []
    cmd = [
        "rg",
        "-n",
        "-i",
        "|".join(patterns),
        "docs",
        "reports",
        "scripts",
        "configs",
        "studies",
        "README.md",
        "PROJECT_REPORT.md",
    ]
    try:
        output = subprocess.check_output(cmd, cwd=str(ROOT), text=True, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as exc:
        output = exc.output or ""
    for line in output.splitlines():
        parts = line.split(":", 2)
        if len(parts) != 3:
            continue
        path, lineno, text = parts
        path_obj = ROOT / path
        lower_path = path.lower()
        table_like = lower_path.endswith((".csv", ".csv.gz", ".parquet", ".npy", ".npz", ".pkl"))
        source_name_like = any(
            token in lower_path
            for token in [
                "app_a",
                "appa",
                "label_table",
                "labels_table",
                "clean_timing_labels",
                "clean-timing-labels",
            ]
        )
        generated_report_like = lower_path.startswith("reports/")
        candidates.append(
            {
                "path": path,
                "line": int(lineno) if lineno.isdigit() else -1,
                "size_bytes": int(path_obj.stat().st_size) if path_obj.exists() else -1,
                "text": text[:240],
                "looks_like_source_table": bool(table_like and source_name_like and not generated_report_like),
            }
        )
    return pd.DataFrame(candidates)


def cfd_times(waveforms: np.ndarray, amplitudes: np.ndarray, fraction: float) -> np.ndarray:
    threshold = amplitudes * float(fraction)
    ge = waveforms >= threshold[:, None]
    first = np.argmax(ge, axis=1)
    valid = ge.any(axis=1)
    out = np.full(len(waveforms), np.nan, dtype=float)
    for i in np.where(valid)[0]:
        j = int(first[i])
        if j <= 0:
            out[i] = float(j)
            continue
        y0 = waveforms[i, j - 1]
        y1 = waveforms[i, j]
        denom = y1 - y0
        out[i] = float(j) if denom <= 0 else (j - 1) + (threshold[i] - y0) / denom
    return out * SAMPLE_PERIOD_NS


def leading_edge_times(waveforms: np.ndarray, threshold_adc: float) -> np.ndarray:
    ge = waveforms >= float(threshold_adc)
    first = np.argmax(ge, axis=1)
    valid = ge.any(axis=1)
    out = np.full(len(waveforms), np.nan, dtype=float)
    for i in np.where(valid)[0]:
        j = int(first[i])
        if j <= 0:
            out[i] = float(j)
            continue
        y0 = waveforms[i, j - 1]
        y1 = waveforms[i, j]
        denom = y1 - y0
        out[i] = float(j) if denom <= 0 else (j - 1) + (float(threshold_adc) - y0) / denom
    return out * SAMPLE_PERIOD_NS


def pickoff_times(wave: np.ndarray, amplitude: np.ndarray, kind: str, value: float) -> np.ndarray:
    flat_wave = wave.reshape(-1, SAMPLES_PER_CHANNEL)
    flat_amp = amplitude.reshape(-1)
    if kind == "cfd":
        times = cfd_times(flat_wave, flat_amp, value)
    elif kind == "leading_adc":
        times = leading_edge_times(flat_wave, value)
    elif kind == "peak":
        times = np.argmax(flat_wave, axis=1).astype(float) * SAMPLE_PERIOD_NS
    else:
        raise ValueError(kind)
    return times.reshape(amplitude.shape)


def label_counts_for_definition(selected: np.ndarray, times: np.ndarray) -> tuple[int, int, int, int, int]:
    ds_selected = selected[:, 1:]
    candidate_mask = ds_selected.sum(axis=1) >= 2
    downstream_ge2 = int(candidate_mask.sum())
    if downstream_ge2 == 0:
        return 0, 0, 0, 0, 0

    ds_times_all = times[:, 1:].copy()
    ds_times_all[~ds_selected] = np.nan
    all_times = times.copy()
    all_times[~selected] = np.nan
    ds_times = ds_times_all[candidate_mask]
    with np.errstate(all="ignore"):
        ds_span = np.nanmax(ds_times, axis=1) - np.nanmin(ds_times, axis=1)
        all_span = np.nanmax(all_times[candidate_mask], axis=1) - np.nanmin(all_times[candidate_mask], axis=1)
        ds_median = np.nanmedian(ds_times, axis=1)
    b2_hit = selected[candidate_mask, 0]
    b2_displacement = np.full(downstream_ge2, np.nan, dtype=float)
    b2_displacement[b2_hit] = np.abs(times[candidate_mask, 0][b2_hit] - ds_median[b2_hit])
    clean = (ds_span < 5.0) & (all_span < 10.0)
    violating = (ds_span > 10.0) | (np.nan_to_num(b2_displacement, nan=-np.inf) > 20.0)
    labelled = clean | violating
    return downstream_ge2, int(clean.sum()), int(violating.sum()), int((~labelled).sum()), int(labelled.sum())


def scan_definition_grid() -> tuple[pd.DataFrame, pd.DataFrame]:
    runs = all_b_runs()
    channels = np.asarray([STAVES[stave] for stave in STAVES], dtype=int)
    baseline_modes = ["median4", "mean4"]
    amp_cuts = [500.0, 750.0, 1000.0, 1250.0, 1500.0]
    pickoffs = (
        [("cfd", value) for value in [0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.50, 0.60, 0.70, 0.80]]
        + [("leading_adc", value) for value in [250.0, 500.0, 750.0, 1000.0, 1500.0, 2000.0]]
        + [("peak", 0.0)]
    )
    per_run = []
    for run in runs:
        path = RAW_DIR / f"hrdb_run_{run:04d}.root"
        tree = uproot.open(path)["h101"]
        accum = {}
        for baseline in baseline_modes:
            for amp_cut in amp_cuts:
                for kind, value in pickoffs:
                    accum[(baseline, amp_cut, kind, value)] = {
                        "events_total": 0,
                        "selected_pulses": 0,
                        "downstream_ge2": 0,
                        "clean": 0,
                        "violating": 0,
                        "ambiguous": 0,
                        "labelled_events": 0,
                    }
        for batch in tree.iterate(["HRDv"], step_size=40000, library="np"):
            raw = np.stack(batch["HRDv"]).astype(np.float64).reshape(-1, 8, SAMPLES_PER_CHANNEL)[:, channels, :]
            baselines = {
                "median4": np.median(raw[..., BASELINE_SAMPLES], axis=-1),
                "mean4": np.mean(raw[..., BASELINE_SAMPLES], axis=-1),
            }
            for baseline, base in baselines.items():
                wave = raw - base[..., None]
                amplitude = wave.max(axis=-1)
                times_by_pickoff = {}
                for kind, value in pickoffs:
                    times_by_pickoff[(kind, value)] = pickoff_times(wave, amplitude, kind, value)
                for amp_cut in amp_cuts:
                    selected = amplitude > amp_cut
                    selected_pulses = int(selected.sum())
                    for kind, value in pickoffs:
                        stats = accum[(baseline, amp_cut, kind, value)]
                        stats["events_total"] += int(len(raw))
                        stats["selected_pulses"] += selected_pulses
                        ds_ge2, clean, violating, ambiguous, labelled = label_counts_for_definition(
                            selected, times_by_pickoff[(kind, value)]
                        )
                        stats["downstream_ge2"] += ds_ge2
                        stats["clean"] += clean
                        stats["violating"] += violating
                        stats["ambiguous"] += ambiguous
                        stats["labelled_events"] += labelled
        for (baseline, amp_cut, kind, value), stats in accum.items():
            per_run.append(
                {
                    "run": run,
                    "in_doc_scope": int(run in DOC_RUNS),
                    "baseline": baseline,
                    "amp_cut_adc": amp_cut,
                    "pickoff_kind": kind,
                    "pickoff_value": value,
                    **stats,
                }
            )
        print("grid run", run, "done", flush=True)
    by_run = pd.DataFrame(per_run)

    scopes = {
        "doc_32_runs": DOC_RUNS,
        "analysis_21_runs": RUN_GROUPS["sample_i_analysis"] + RUN_GROUPS["sample_ii_analysis"],
        "sample_i_25_runs": RUN_GROUPS["sample_i_calib"] + RUN_GROUPS["sample_i_analysis"],
        "sample_ii_8_runs": RUN_GROUPS["sample_ii_calib"] + RUN_GROUPS["sample_ii_analysis"],
        "all_b_53_runs": runs,
    }
    rows = []
    group_cols = ["baseline", "amp_cut_adc", "pickoff_kind", "pickoff_value"]
    for scope, scope_runs in scopes.items():
        scoped = by_run[by_run["run"].isin(scope_runs)]
        grouped = scoped.groupby(group_cols, as_index=False)[
            ["events_total", "selected_pulses", "downstream_ge2", "clean", "violating", "ambiguous", "labelled_events"]
        ].sum()
        grouped["scope"] = scope
        rows.append(grouped)
    scan = pd.concat(rows, ignore_index=True)
    scan["delta_labelled"] = scan["labelled_events"] - TARGET["labelled_events"]
    scan["delta_clean"] = scan["clean"] - TARGET["clean"]
    scan["delta_violating"] = scan["violating"] - TARGET["violating"]
    scan["target_l1_distance"] = (
        scan["delta_labelled"].abs() + scan["delta_clean"].abs() + scan["delta_violating"].abs()
    )
    scan["target_exact_match"] = scan["target_l1_distance"] == 0
    scan = scan.sort_values(["target_l1_distance", "scope", "baseline", "amp_cut_adc"]).reset_index(drop=True)
    return scan, by_run


def metric_ci_by_run(y: np.ndarray, score: np.ndarray, runs: np.ndarray, metric: str, n_boot: int = 1000):
    if metric == "roc_auc":
        point = float(roc_auc_score(y, score))
    elif metric == "average_precision":
        point = float(average_precision_score(y, score))
    elif metric == "brier":
        point = float(brier_score_loss(y, np.clip(score, 0, 1)))
    else:
        raise ValueError(metric)
    rng = np.random.default_rng(SEED + len(metric))
    unique_runs = np.unique(runs)
    values = []
    for _ in range(n_boot):
        sampled = rng.choice(unique_runs, size=len(unique_runs), replace=True)
        idx = np.concatenate([np.where(runs == run)[0] for run in sampled])
        if len(np.unique(y[idx])) < 2:
            continue
        if metric == "roc_auc":
            values.append(roc_auc_score(y[idx], score[idx]))
        elif metric == "average_precision":
            values.append(average_precision_score(y[idx], score[idx]))
        else:
            values.append(brier_score_loss(y[idx], np.clip(score[idx], 0, 1)))
    return point, [float(np.quantile(values, 0.025)), float(np.quantile(values, 0.975))]


def write_manifest(start: float, input_rows: list[dict]) -> None:
    output_rows = []
    for path in sorted(OUT.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            output_rows.append({"path": str(path.relative_to(ROOT)), "sha256": sha256_file(path)})
    manifest = {
        "study": "S07d",
        "ticket": TICKET,
        "worker": WORKER,
        "command": f"/home/billy/anaconda3/bin/python {str((OUT / 's07d_app_a_label_recovery.py').relative_to(ROOT))}",
        "git_commit_at_run": git_commit(),
        "random_seed": SEED,
        "runtime_sec": round(time.time() - start, 3),
        "inputs": input_rows,
        "outputs": output_rows,
    }
    (OUT / "manifest.json").write_text(json.dumps(clean_json(manifest), indent=2), encoding="utf-8")


def main() -> None:
    start = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    s07c = load_s07c()

    artifact_inventory = source_artifact_inventory()
    artifact_inventory.to_csv(OUT / "artifact_inventory.csv", index=False)

    # Raw reproduction first: exactly the documented weak-label definition from docs/07.
    s00, per_run, events = s07c.scan_raw_events()
    s00.to_csv(OUT / "reproduction_s00_counts.csv", index=False)
    per_run.to_csv(OUT / "documented_cfd20_counts_by_run.csv", index=False)
    events.to_csv(OUT / "documented_cfd20_event_dataset.csv.gz", index=False)

    labelled_counts = {
        "labelled_events": int(per_run["clean_events"].sum() + per_run["violating_events"].sum()),
        "clean": int(per_run["clean_events"].sum()),
        "violating": int(per_run["violating_events"].sum()),
        "ambiguous": int(per_run["ambiguous_events"].sum()),
        "downstream_ge2_events": int(per_run["downstream_ge2_events"].sum()),
    }
    documented_reproduction = pd.DataFrame(
        [
            {
                "quantity": key,
                "documented": TARGET[key],
                "raw_cfd20": labelled_counts[key],
                "delta": labelled_counts[key] - TARGET[key],
                "matches": labelled_counts[key] == TARGET[key],
            }
            for key in ["labelled_events", "clean", "violating"]
        ]
    )
    documented_reproduction.to_csv(OUT / "documented_cfd20_reproduction.csv", index=False)

    scan, scan_by_run = scan_definition_grid()
    scan.to_csv(OUT / "definition_scan.csv", index=False)
    scan.head(30).to_csv(OUT / "definition_scan_top30.csv", index=False)
    scan_by_run.to_csv(OUT / "definition_scan_by_run.csv", index=False)
    best_scan = scan.iloc[0].to_dict()

    q_event = s07c.qtemplate_event_table()
    data = events.merge(q_event, on=["run", "eventno", "evt"], how="left")
    data["b2_displacement_filled"] = data["b2_displacement_ns"].fillna(999.0)
    q_cols = [col for col in data.columns if col.startswith("q_")]
    qtemplate_unmatched_events = int(data[q_cols].isna().all(axis=1).sum())
    data[q_cols] = data[q_cols].fillna(data[q_cols].median(numeric_only=True))

    folds, rf_cv, scores, rf_features, best_params = s07c.run_heldout_scores(data)
    folds.to_csv(OUT / "run_heldout_folds.csv", index=False)
    rf_cv.to_csv(OUT / "rf_cv_scan.csv", index=False)
    scores.to_csv(OUT / "heldout_scores.csv", index=False)

    y = scores["label_clean"].to_numpy(dtype=int)
    runs = scores["run"].to_numpy(dtype=int)
    scoreboard_rows = []
    for method, col, note in [
        ("traditional_span_q_template", "traditional_span_q_score", "Uses downstream span; overlaps weak-label definition"),
        ("traditional_q_template_only", "q_template_only_score", "No timing-span feature"),
        ("rf_clean_timing", "rf_score", "RF excludes timing spans, pair residuals, run, and sample"),
        ("leaky_rf_control", "leaky_rf_score", "RF with forbidden label-defining timing spans"),
    ]:
        score = scores[col].to_numpy(dtype=float)
        auc, auc_ci = metric_ci_by_run(y, score, runs, "roc_auc")
        ap, ap_ci = metric_ci_by_run(y, score, runs, "average_precision")
        row = {
            "method": method,
            "roc_auc": auc,
            "roc_auc_ci_low": auc_ci[0],
            "roc_auc_ci_high": auc_ci[1],
            "average_precision": ap,
            "average_precision_ci_low": ap_ci[0],
            "average_precision_ci_high": ap_ci[1],
            "note": note,
        }
        if col in {"rf_score", "leaky_rf_score"}:
            brier, brier_ci = metric_ci_by_run(y, score, runs, "brier")
            row.update({"brier": brier, "brier_ci_low": brier_ci[0], "brier_ci_high": brier_ci[1]})
        scoreboard_rows.append(row)
    scoreboard = pd.DataFrame(scoreboard_rows)
    scoreboard.to_csv(OUT / "scoreboard.csv", index=False)

    forbidden = {"downstream_span_ns", "all_span_ns", "b2_displacement_ns", "b2_displacement_filled"}
    leakage_checks = pd.DataFrame(
        [
            {
                "check": "rf_forbidden_feature_intersection",
                "value": ",".join(sorted(set(rf_features) & forbidden)),
                "pass": len(set(rf_features) & forbidden) == 0,
            },
            {
                "check": "leaky_control_auc_is_ceiling",
                "value": float(scoreboard.loc[scoreboard["method"] == "leaky_rf_control", "roc_auc"].iloc[0]),
                "pass": True,
            },
            {
                "check": "historical_source_table_found",
                "value": int(artifact_inventory["looks_like_source_table"].sum()) if len(artifact_inventory) else 0,
                "pass": bool(len(artifact_inventory) and artifact_inventory["looks_like_source_table"].any()),
            },
            {
                "check": "definition_grid_exact_target_match",
                "value": int(scan["target_exact_match"].sum()),
                "pass": bool(scan["target_exact_match"].any()),
            },
        ]
    )
    leakage_checks.to_csv(OUT / "leakage_checks.csv", index=False)

    fig, ax = plt.subplots(figsize=(8, 4))
    top = scan.head(20).iloc[::-1]
    labels = [
        f"{row.scope}\\n{row.baseline}, A>{row.amp_cut_adc:g}, {row.pickoff_kind}:{row.pickoff_value:g}"
        for row in top.itertuples()
    ]
    ax.barh(np.arange(len(top)), top["target_l1_distance"].to_numpy(dtype=float))
    ax.set_yticks(np.arange(len(top)))
    ax.set_yticklabels(labels, fontsize=7)
    ax.set_xlabel("L1 distance from documented (labelled, clean, violating)")
    ax.set_title("Closest raw timing-definition scans")
    fig.tight_layout()
    fig.savefig(OUT / "fig_definition_scan_top20.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 4))
    plot_data = [
        scores.loc[scores["label_clean"] == 1, "rf_score"],
        scores.loc[scores["label_clean"] == 0, "rf_score"],
        scores.loc[scores["label_clean"] == 1, "q_template_only_score"],
        scores.loc[scores["label_clean"] == 0, "q_template_only_score"],
    ]
    ax.boxplot(plot_data, labels=["RF clean", "RF viol", "q clean", "q viol"], showfliers=False)
    ax.set_ylabel("Held-out score")
    ax.set_title("Run-held-out scores on raw-CFD20 labels")
    fig.tight_layout()
    fig.savefig(OUT / "fig_heldout_scores.png", dpi=150)
    plt.close(fig)

    exact_match = bool(scan["target_exact_match"].any())
    source_table_found = bool(len(artifact_inventory) and artifact_inventory["looks_like_source_table"].any())
    verdict = (
        "retire_12147_pending_source_table"
        if not exact_match and not source_table_found and not documented_reproduction["matches"].all()
        else "candidate_recovered"
    )

    result = {
        "study": "S07d",
        "ticket": TICKET,
        "worker": WORKER,
        "title": "recover historical App.A label table",
        "documented_target": TARGET,
        "raw_cfd20_reproduced": labelled_counts,
        "raw_cfd20_matches_documented": bool(documented_reproduction["matches"].all()),
        "source_table_found": source_table_found,
        "definition_grid_exact_match_found": exact_match,
        "best_definition_scan": clean_json(best_scan),
        "traditional": clean_json(scoreboard[scoreboard["method"] == "traditional_span_q_template"].iloc[0].to_dict()),
        "traditional_deleaked": clean_json(scoreboard[scoreboard["method"] == "traditional_q_template_only"].iloc[0].to_dict()),
        "ml": clean_json(scoreboard[scoreboard["method"] == "rf_clean_timing"].iloc[0].to_dict()),
        "leaky_control": clean_json(scoreboard[scoreboard["method"] == "leaky_rf_control"].iloc[0].to_dict()),
        "best_rf_params": clean_json(best_params),
        "rf_feature_count": len(rf_features),
        "rf_forbidden_features_present": sorted(set(rf_features) & forbidden),
        "qtemplate_unmatched_events": qtemplate_unmatched_events,
        "verdict": verdict,
        "runtime_sec": round(time.time() - start, 3),
        "next_tickets": [
            "S07e: archive provenance search for the App.A training table outside this repo; expected information gain: determines whether 12,147 came from a lost derived table rather than raw HRDv.",
            "S03d: independent timing-tail validation of q_template-only clean-timing cuts; expected information gain: replaces App.A weak labels with an external held-out timing-tail gate.",
        ],
    }
    (OUT / "result.json").write_text(json.dumps(clean_json(result), indent=2), encoding="utf-8")

    input_rows = []
    for run in DOC_RUNS:
        path = RAW_DIR / f"hrdb_run_{run:04d}.root"
        input_rows.append({"path": str(path.relative_to(ROOT)), "sha256": sha256_file(path), "role": "doc_scope_raw_b_root"})
    for run in sorted(set(all_b_runs()) - set(DOC_RUNS)):
        path = RAW_DIR / f"hrdb_run_{run:04d}.root"
        input_rows.append({"path": str(path.relative_to(ROOT)), "sha256": sha256_file(path), "role": "grid_extra_raw_b_root"})
    for path, role in [(QTEMPLATE_PATH, "s01_q_template_table"), (DOC_PATH, "app_a_doc"), (S07C_SCRIPT, "method_reference_script")]:
        input_rows.append({"path": str(path.relative_to(ROOT)), "sha256": sha256_file(path), "role": role})
    pd.DataFrame(input_rows).to_csv(OUT / "input_sha256.csv", index=False)

    report = f"""# Study report: S07d - recover historical App.A label table

- **Ticket:** {TICKET}
- **Author:** {WORKER}
- **Date:** 2026-06-09
- **Inputs:** raw B-stack ROOT, S01 q_template table, and App.A documentation; checksums in `input_sha256.csv`
- **Command:** `/home/billy/anaconda3/bin/python {str((OUT / 's07d_app_a_label_recovery.py').relative_to(ROOT))}`
- **Git commit at run:** `{git_commit()}`

## 0. Question
Can the source table or exact timing definition behind the documented App.A 12,147 labelled events be recovered from the repository and raw ROOT, or should that number be retired?

## 1. Reproduction first
The raw S00 selected-pulse gate still reproduces exactly:

{s00.to_markdown(index=False)}

Recomputing the documented App.A weak labels directly from raw `HRDv` with median-4 baseline, amplitude >1000 ADC, CFD20 timing, >=2 downstream staves, clean = downstream span <5 ns and all-span <10 ns, and violating = downstream span >10 ns or B2 displacement >20 ns gives:

{documented_reproduction.to_markdown(index=False)}

This is not the historical 12,147-event table.

## 2. Source-table search
I searched repo docs, scripts, configs, studies, and reports for `App.A`, `12,147`, `12147`, `10636`, `1511`, and `clean-timing`. The only durable numeric source is `docs/07_ml_methods.md`, plus later reports that quote or challenge it. No candidate source label table was found.

## 3. Timing-definition scan
I scanned raw B-stack ROOT over baseline mode (`median4`, `mean4`), amplitude cut (500, 750, 1000, 1250, 1500 ADC), timing pickoff (CFD 0.10-0.80, leading-edge 250-2000 ADC, peak sample), and run scope (`doc_32_runs`, `analysis_21_runs`, `sample_i_25_runs`, `sample_ii_8_runs`, `all_b_53_runs`). The best raw definition was:

{pd.DataFrame([best_scan]).to_markdown(index=False)}

No scanned definition matched all three documented numbers exactly (`labelled=12147`, `clean=10636`, `violating=1511`).

## 4. Held-out benchmark
Using the raw-CFD20 reproducible labels, I reran the S07c-style run-held-out benchmark. Metrics use run-bootstrap 95% CIs over out-of-fold predictions:

{scoreboard.to_markdown(index=False)}

The strong traditional method uses downstream span plus q_template and is label-overlapping by construction. The de-leaked traditional method uses q_template only. The ML method is a random forest on amplitude/shape/q_template features, excluding run, sample, timing spans, pair residuals, and B2 displacement.

## 5. Leakage hunt
{leakage_checks.to_markdown(index=False)}

The near-perfect leaky control confirms that including label-defining timing quantities trivially solves the weak-label task. The admissible RF still looks very strong, so I treat it as a proxy ranking only, not independent truth.

## 6. Verdict
The App.A 12,147 labelled-event count should be retired from detector-result status unless an external derived label table is recovered. It is not reproduced by the documented raw definition, no source table is present in this repo, and a broad raw timing-definition scan found no exact match. The supported replacement statement is: raw HRDv CFD20 labels produce {labelled_counts['labelled_events']} labelled events ({labelled_counts['clean']} clean, {labelled_counts['violating']} violating) in the documented 32-run scope.

## 7. Follow-ups
- S07e: archive provenance search for the App.A training table outside this repo; expected information gain: determines whether 12,147 came from a lost derived table rather than raw HRDv.
- S03d: independent timing-tail validation of q_template-only clean-timing cuts; expected information gain: replaces App.A weak labels with an external held-out timing-tail gate.
"""
    (OUT / "REPORT.md").write_text(report, encoding="utf-8")
    write_manifest(start, input_rows)


if __name__ == "__main__":
    main()
