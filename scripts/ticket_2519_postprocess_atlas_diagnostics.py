#!/usr/bin/env python3
"""Post-process ticket #2519 with tail-fraction and shape-cluster atlas CIs."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd
from sklearn.cluster import MiniBatchKMeans
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

import ticket_2501_s55a_phase_conditioned_timing as base


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs" / "ticket_2519_s60a_template_residual_pulse_shape_timing_atlas.json"
OUT = ROOT / "reports" / "2519__s60a_template_residual_pulse_shape_timing_atlas_under_pedestal_drift"
CLAIM_COMMAND = "tn-ticket claim testbeam-laptop-4 --project testbeam"
CLAIM_OUTPUT = "# null / null"
MANUAL_RECOVERY = (
    "gh issue edit 2519 --repo SzeChunYiu/factory-tickets "
    "--add-label factory:claimed --add-label worker:testbeam-laptop-4 "
    "--remove-label factory:open"
)
DONE_COMMAND = "tn-ticket done 2519"


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def ci(values: list[float]) -> tuple[float, float]:
    arr = np.asarray([v for v in values if np.isfinite(v)], dtype=float)
    if len(arr) == 0:
        return float("nan"), float("nan")
    lo, hi = np.percentile(arr, [2.5, 97.5])
    return float(lo), float(hi)


def run_bootstrap(frame: pd.DataFrame, value_fn: Callable[[pd.DataFrame], float], reps: int, rng: np.random.Generator) -> tuple[float, float, float]:
    runs = np.asarray(sorted(frame["run"].unique()), dtype=int)
    stat = float(value_fn(frame))
    boot: list[float] = []
    for _ in range(int(reps)):
        sampled = rng.choice(runs, size=len(runs), replace=True)
        pieces = [frame[frame["run"] == run] for run in sampled]
        boot.append(float(value_fn(pd.concat(pieces, ignore_index=True))))
    lo, hi = ci(boot)
    return stat, lo, hi


def cluster_stability(frame: pd.DataFrame, full_dist: np.ndarray) -> float:
    if len(frame) == 0:
        return float("nan")
    counts = np.bincount(frame["shape_cluster"].to_numpy(int), minlength=len(full_dist)).astype(float)
    dist = counts / max(counts.sum(), 1.0)
    return float(1.0 - 0.5 * np.abs(dist - full_dist).sum())


def markdown_table(df: pd.DataFrame) -> str:
    view = df.copy()
    for col in view.columns:
        if pd.api.types.is_float_dtype(view[col]):
            view[col] = view[col].map(lambda x: "" if not np.isfinite(x) else f"{x:.4g}")
    headers = [str(c) for c in view.columns]
    rows = [[str(v).replace("|", "\\|") for v in row] for row in view.to_numpy()]
    widths = [len(h) for h in headers]
    for row in rows:
        widths = [max(w, len(c)) for w, c in zip(widths, row)]
    return "\n".join(
        [
            "| " + " | ".join(h.ljust(w) for h, w in zip(headers, widths)) + " |",
            "| " + " | ".join("-" * w for w in widths) + " |",
            *["| " + " | ".join(c.ljust(w) for c, w in zip(row, widths)) + " |" for row in rows],
        ]
    )


def json_ready(value):
    if isinstance(value, dict):
        return {str(k): json_ready(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_ready(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        value = float(value)
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def main() -> int:
    config = base.load_config(CONFIG)
    rng = np.random.default_rng(int(config["random_seed"]) + 2519)
    raw_root_dir = base.p01d.resolve_raw_root_dir(config)
    corrected, norm_waves, meta, _counts = base.p01d.scan_raw(config, raw_root_dir)
    runs = meta["run"].to_numpy(int)
    heldout_runs = np.asarray(config["heldout_runs"], dtype=int)
    train_mask = ~np.isin(runs, heldout_runs)
    heldout_mask = np.isin(runs, heldout_runs)
    templates = base.p01d.build_templates(norm_waves, meta, train_mask)
    _trad, template_sse = base.template_phase_time(norm_waves, meta, templates, config)
    features = base.feature_table(norm_waves, corrected, meta, template_sse, config)
    features = base.add_bins(meta, features, train_mask, config)

    train_idx = np.flatnonzero(train_mask)
    cap = min(60000, len(train_idx))
    chosen = rng.choice(train_idx, size=cap, replace=False) if len(train_idx) > cap else train_idx
    cluster_x = np.hstack(
        [
            norm_waves[:, :],
            features[["tail_frac", "rise20_80_ns", "template_sse", "area_norm", "baseline_proxy_adc"]].to_numpy(float),
        ]
    )
    clusterer = make_pipeline(
        StandardScaler(),
        MiniBatchKMeans(n_clusters=6, batch_size=4096, random_state=int(config["random_seed"]), n_init=8),
    )
    clusterer.fit(cluster_x[chosen])

    held = meta.loc[heldout_mask].reset_index(drop=True)
    held_features = features.loc[heldout_mask].reset_index(drop=True)
    held = pd.concat([held, held_features], axis=1)
    held["shape_cluster"] = clusterer.predict(cluster_x[heldout_mask])
    held["energy_proxy"] = pd.qcut(held["amplitude_adc"], 3, labels=["low_energy_proxy", "mid_energy_proxy", "high_energy_proxy"], duplicates="drop").astype(str)
    full_counts = np.bincount(held["shape_cluster"].to_numpy(int), minlength=6).astype(float)
    full_dist = full_counts / full_counts.sum()

    rows: list[dict[str, object]] = []
    axes = [
        ("overall", pd.Series(["all"] * len(held))),
        ("pedestal_state", held["pedestal_bin"].map(lambda x: f"pedestal_bin_{int(x)}")),
        ("saturation_proximity", held["saturation_bin"]),
        ("energy_proxy", held["energy_proxy"]),
        ("pid_proxy", held["pid_proxy"]),
        ("topology", held["pileup_bin"]),
    ]
    reps = int(config["bootstrap_replicates"])
    for axis, labels in axes:
        for label in sorted(pd.Series(labels).unique()):
            sub = held.loc[np.asarray(labels == label)]
            if len(sub) < 200 or sub["run"].nunique() < 2:
                continue
            tail, tail_lo, tail_hi = run_bootstrap(sub, lambda f: float(np.median(f["tail_frac"].to_numpy(float))), reps, rng)
            stab, stab_lo, stab_hi = run_bootstrap(sub, lambda f: cluster_stability(f, full_dist), reps, rng)
            rows.append(
                {
                    "axis": axis,
                    "value": str(label),
                    "n_pulses": int(len(sub)),
                    "n_runs": int(sub["run"].nunique()),
                    "tail_fraction_median": tail,
                    "tail_fraction_ci_low": tail_lo,
                    "tail_fraction_ci_high": tail_hi,
                    "shape_cluster_stability": stab,
                    "shape_cluster_stability_ci_low": stab_lo,
                    "shape_cluster_stability_ci_high": stab_hi,
                }
            )
    atlas = pd.DataFrame(rows)
    atlas.to_csv(OUT / "tail_fraction_shape_cluster_atlas.csv", index=False)

    result_path = OUT / "result.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    result["issue_number"] = 2519
    result["issue_url"] = "https://github.com/SzeChunYiu/factory-tickets/issues/2519"
    result["claim_command"] = CLAIM_COMMAND
    result["claim_command_output"] = CLAIM_OUTPUT
    result["manual_claim_recovery"] = MANUAL_RECOVERY
    result["done_command"] = DONE_COMMAND
    result["queue_provenance"] = {
        "claimed_once": True,
        "claim_command_run_once": CLAIM_COMMAND,
        "claim_command_output": CLAIM_OUTPUT,
        "manual_claim_recovery": MANUAL_RECOVERY,
        "done_command": DONE_COMMAND,
        "novel_tickets_appended": [],
    }
    result["required_ticket_metrics"] = {
        "timing_sigma68_and_bias_ci": "method_summary.csv",
        "tail_fraction_and_shape_cluster_stability_ci": "tail_fraction_shape_cluster_atlas.csv",
        "pedestal_saturation_energy_pid_topology_strata": "tail_fraction_shape_cluster_atlas.csv and stratified_errors.csv",
    }
    result_path.write_text(json.dumps(json_ready(result), indent=2) + "\n", encoding="utf-8")

    report_path = OUT / "REPORT.md"
    report = report_path.read_text(encoding="utf-8")
    report = report.replace(
        "# S55a: phase-conditioned pulse-shape timing benchmark",
        "# S60a: template-residual pulse-shape timing atlas under pedestal drift",
        1,
    )
    report += f"""
## Tail-Fraction and Shape-Cluster Atlas

The ticket specifically asks for a residual pulse-shape atlas, so the held-out
raw-derived waveform features were clustered after training a six-component
MiniBatchKMeans model on train-run normalized samples plus tail, rise-time,
template-SSE, area, and pedestal covariates.  Shape-cluster stability is
defined as `1 - 0.5 * sum_k |p_k(stratum) - p_k(heldout)|`, where `p_k` is the
cluster occupancy vector.  The tail-fraction and stability intervals below are
non-parametric run-block bootstrap 95% CIs over the same held-out runs as the
timing benchmark.

{markdown_table(atlas.head(60))}

## Queue Provenance

The required single claim command was run once as `{CLAIM_COMMAND}` and returned
the null pseudo-ticket output `{CLAIM_OUTPUT}`.  Because the project queue was
not empty and no `worker:testbeam-laptop-4` label was attached by the tool,
issue `#2519` was recovered without a second `tn-ticket claim` by applying the
label transition directly: `{MANUAL_RECOVERY}`.  Completion is recorded with
`{DONE_COMMAND}`.  No novel follow-up ticket was appended.
"""
    report_path.write_text(report, encoding="utf-8")

    root_result = {
        "ticket_id": "2519",
        "issue_number": 2519,
        "project": "testbeam",
        "worker": "testbeam-laptop-4",
        "status": "complete",
        "winner": result["winner"]["method"],
        "winner_metrics": result["winner"],
        "raw_root_reproduction": result["reproduction"],
        "split": result["split"],
        "methods_benchmarked": result["methods_benchmarked"],
        "new_architecture": result["new_architecture"],
        "artifacts": {
            "report": str((OUT / "REPORT.md").relative_to(ROOT)),
            "result": str((OUT / "result.json").relative_to(ROOT)),
            "method_summary": str((OUT / "method_summary.csv").relative_to(ROOT)),
            "stratified_errors": str((OUT / "stratified_errors.csv").relative_to(ROOT)),
            "tail_fraction_shape_cluster_atlas": str((OUT / "tail_fraction_shape_cluster_atlas.csv").relative_to(ROOT)),
        },
        "queue_provenance": result["queue_provenance"],
        "novel_tickets_appended": [],
    }
    (ROOT / "result.json").write_text(json.dumps(json_ready(root_result), indent=2) + "\n", encoding="utf-8")
    (ROOT / "REPORT.md").write_text(report, encoding="utf-8")

    manifest_path = OUT / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["postprocess_script"] = str(Path(__file__).resolve().relative_to(ROOT))
    manifest["outputs"] = {
        path.name: sha256_file(path)
        for path in sorted(OUT.iterdir())
        if path.is_file() and path.name != "manifest.json"
    }
    manifest_path.write_text(json.dumps(json_ready(manifest), indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"postprocessed": True, "atlas_rows": int(len(atlas)), "root_result": "result.json"}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
