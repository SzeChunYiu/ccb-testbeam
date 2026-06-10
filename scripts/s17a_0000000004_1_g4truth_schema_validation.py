#!/usr/bin/env python3
"""Summarise hibeam_g4 Krakow truth output for ticket 0000000004.1.g4truth.

The script expects a ROOT file produced by hibeam_g4 with WriteTree=1. It writes
schema and compact validation tables under the report directory.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
from pathlib import Path

import awkward as ak
import numpy as np
import pandas as pd
import uproot


PDG_LABELS = {
    11: "electron",
    22: "gamma",
    2112: "neutron",
    2212: "proton",
    1000010020: "deuteron",
    1000010030: "triton",
    1000020030: "helium3",
    1000020040: "alpha",
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def quantiles(values: np.ndarray) -> dict:
    if len(values) == 0:
        return {"q05": math.nan, "q16": math.nan, "median": math.nan, "q84": math.nan, "q95": math.nan}
    q05, q16, q50, q84, q95 = np.percentile(values, [5, 16, 50, 84, 95])
    return {"q05": q05, "q16": q16, "median": q50, "q84": q84, "q95": q95}


def bootstrap_ci_diff(a: np.ndarray, b: np.ndarray, seed: int, n_boot: int) -> tuple[float, float, float]:
    rng = np.random.default_rng(seed)
    if len(a) == 0 or len(b) == 0:
        return math.nan, math.nan, math.nan
    point = float(np.mean(a) - np.mean(b))
    draws = np.empty(n_boot, dtype=float)
    for i in range(n_boot):
        aa = a[rng.integers(0, len(a), len(a))]
        bb = b[rng.integers(0, len(b), len(b))]
        draws[i] = np.mean(aa) - np.mean(bb)
    lo, hi = np.percentile(draws, [2.5, 97.5])
    return point, float(lo), float(hi)


def write_rows(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("")
        return
    keys = list(rows[0].keys())
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=keys, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def parse_run_log(path: Path) -> dict:
    text = path.read_text(errors="replace") if path.exists() else ""
    elapsed = re.search(r"Elapsed \(wall clock\) time .*: ([^\n]+)", text)
    max_rss = re.search(r"Maximum resident set size \(kbytes\): ([0-9]+)", text)
    processed = re.search(r"Total events processed: ([0-9]+)", text)
    command_not_found = "COMMAND NOT FOUND" in text
    return {
        "log": str(path),
        "exists": path.exists(),
        "command_not_found": command_not_found,
        "processed_events": int(processed.group(1)) if processed else 0,
        "elapsed": elapsed.group(1).strip() if elapsed else "",
        "max_rss_kb": int(max_rss.group(1)) if max_rss else 0,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True, type=Path)
    ap.add_argument("--report-dir", required=True, type=Path)
    ap.add_argument("--original-log", type=Path)
    ap.add_argument("--patched-log", type=Path)
    ap.add_argument("--seed", type=int, default=1700041)
    ap.add_argument("--n-boot", type=int, default=2000)
    args = ap.parse_args()

    args.report_dir.mkdir(parents=True, exist_ok=True)
    tree = uproot.open(args.root)["hibeam"]

    schema_rows = []
    for name in tree.keys():
        branch = tree[name]
        prefix = name.split("_", 1)[0] if "_" in name else "Primary"
        schema_rows.append(
            {
                "branch": name,
                "detector_group": prefix,
                "typename": branch.typename,
                "interpretation": str(branch.interpretation),
            }
        )
    write_rows(args.report_dir / "truth_schema.csv", schema_rows)

    branches = [
        "PrimaryPDG",
        "PrimaryEkin",
        "Sci_bar_PDG",
        "Sci_bar_EDep",
        "Sci_bar_Time",
        "Sci_bar_LayerID",
        "Sci_bar_LayerID1",
        "Sci_bar_LayerID2",
        "Sci_bar_TrackID",
    ]
    arr = tree.arrays(branches, library="ak")
    entries = int(tree.num_entries)

    primary_pdg = ak.to_numpy(ak.flatten(arr["PrimaryPDG"]))
    primary_ekin = ak.to_numpy(ak.flatten(arr["PrimaryEkin"]))
    primary_rows = []
    for pdg in sorted(np.unique(primary_pdg)):
        vals = primary_ekin[primary_pdg == pdg]
        qs = quantiles(vals)
        primary_rows.append(
            {
                "pdg": int(pdg),
                "particle": PDG_LABELS.get(int(pdg), str(int(pdg))),
                "n_primary_particles": int(len(vals)),
                "mean_ekin_MeV": float(np.mean(vals)),
                **{k + "_ekin_MeV": float(v) for k, v in qs.items()},
            }
        )
    write_rows(args.report_dir / "primary_truth_summary.csv", primary_rows)

    counts = ak.num(arr["Sci_bar_EDep"])
    event_ids = np.repeat(np.arange(entries), ak.to_numpy(counts))
    sci = pd.DataFrame(
        {
            "event": event_ids,
            "pdg": ak.to_numpy(ak.flatten(arr["Sci_bar_PDG"])).astype(int),
            "edep_MeV": ak.to_numpy(ak.flatten(arr["Sci_bar_EDep"])),
            "time_ns": ak.to_numpy(ak.flatten(arr["Sci_bar_Time"])),
            "layer": ak.to_numpy(ak.flatten(arr["Sci_bar_LayerID"])).astype(int),
            "layer1": ak.to_numpy(ak.flatten(arr["Sci_bar_LayerID1"])).astype(int),
            "layer2": ak.to_numpy(ak.flatten(arr["Sci_bar_LayerID2"])).astype(int),
            "track_id": ak.to_numpy(ak.flatten(arr["Sci_bar_TrackID"])).astype(int),
        }
    )
    sci["particle"] = sci["pdg"].map(lambda x: PDG_LABELS.get(int(x), str(int(x))))
    sci.to_csv(args.report_dir / "sci_bar_hit_sample.csv", index=False, float_format="%.8g")

    pid_summary = (
        sci.groupby(["pdg", "particle"], dropna=False)
        .agg(
            n_hits=("edep_MeV", "size"),
            n_events=("event", "nunique"),
            sum_edep_MeV=("edep_MeV", "sum"),
            mean_hit_edep_MeV=("edep_MeV", "mean"),
            median_hit_edep_MeV=("edep_MeV", "median"),
            mean_time_ns=("time_ns", "mean"),
        )
        .reset_index()
        .sort_values(["sum_edep_MeV", "n_hits"], ascending=False)
    )
    pid_summary.to_csv(args.report_dir / "sci_bar_pid_summary.csv", index=False, float_format="%.8g")

    layer_summary = (
        sci.groupby(["pdg", "particle", "layer1", "layer2"], dropna=False)
        .agg(
            n_hits=("edep_MeV", "size"),
            n_events=("event", "nunique"),
            sum_edep_MeV=("edep_MeV", "sum"),
            mean_hit_edep_MeV=("edep_MeV", "mean"),
            median_hit_edep_MeV=("edep_MeV", "median"),
        )
        .reset_index()
        .sort_values(["pdg", "layer1", "layer2"])
    )
    layer_summary.to_csv(args.report_dir / "sci_bar_layer_pid_summary.csv", index=False, float_format="%.8g")

    event_pid = (
        sci.groupby(["event", "pdg", "particle"], dropna=False)
        .agg(total_edep_MeV=("edep_MeV", "sum"), n_hits=("edep_MeV", "size"))
        .reset_index()
    )
    event_pid_summary = (
        event_pid.groupby(["pdg", "particle"], dropna=False)
        .agg(
            n_events=("event", "nunique"),
            mean_total_edep_MeV=("total_edep_MeV", "mean"),
            median_total_edep_MeV=("total_edep_MeV", "median"),
            q16_total_edep_MeV=("total_edep_MeV", lambda x: np.percentile(x, 16)),
            q84_total_edep_MeV=("total_edep_MeV", lambda x: np.percentile(x, 84)),
            mean_n_hits=("n_hits", "mean"),
        )
        .reset_index()
        .sort_values("mean_total_edep_MeV", ascending=False)
    )
    event_pid_summary.to_csv(args.report_dir / "event_pid_edep_summary.csv", index=False, float_format="%.8g")

    p_event = event_pid.loc[event_pid["pdg"] == 2212, "total_edep_MeV"].to_numpy()
    d_event = event_pid.loc[event_pid["pdg"] == 1000010020, "total_edep_MeV"].to_numpy()
    diff, diff_lo, diff_hi = bootstrap_ci_diff(d_event, p_event, args.seed, args.n_boot)
    p_hits = sci.loc[sci["pdg"] == 2212, "edep_MeV"].to_numpy()
    d_hits = sci.loc[sci["pdg"] == 1000010020, "edep_MeV"].to_numpy()
    hit_diff, hit_lo, hit_hi = bootstrap_ci_diff(d_hits, p_hits, args.seed + 1, args.n_boot)

    validation_rows = [
        {
            "metric": "root_tree_entries",
            "value": entries,
            "ci_low": "",
            "ci_high": "",
            "interpretation": "Recorded hibeam tree entries in patched 100k run.",
        },
        {
            "metric": "primary_proton_count",
            "value": int(np.sum(primary_pdg == 2212)),
            "ci_low": "",
            "ci_high": "",
            "interpretation": "One primary proton is stored per recorded tree entry.",
        },
        {
            "metric": "primary_deuteron_count",
            "value": int(np.sum(primary_pdg == 1000010020)),
            "ci_low": "",
            "ci_high": "",
            "interpretation": "One primary deuteron is stored per recorded tree entry.",
        },
        {
            "metric": "sci_bar_hits",
            "value": int(len(sci)),
            "ci_low": "",
            "ci_high": "",
            "interpretation": "All Sci_bar truth hits in the patched run.",
        },
        {
            "metric": "deuteron_minus_proton_event_total_edep_MeV",
            "value": diff,
            "ci_low": diff_lo,
            "ci_high": diff_hi,
            "interpretation": "Positive means deuteron-tagged Sci_bar events are more ionising than proton-tagged events.",
        },
        {
            "metric": "deuteron_minus_proton_hit_edep_MeV",
            "value": hit_diff,
            "ci_low": hit_lo,
            "ci_high": hit_hi,
            "interpretation": "Positive means deuteron Sci_bar hits deposit more energy per hit than proton hits.",
        },
        {
            "metric": "fraction_tree_entries_with_sci_bar_hit",
            "value": float(sci["event"].nunique() / entries) if entries else math.nan,
            "ci_low": "",
            "ci_high": "",
            "interpretation": "Acceptance into the sensitive Sci_bar truth branches.",
        },
    ]
    write_rows(args.report_dir / "validation_metrics.csv", validation_rows)

    run_rows = []
    if args.original_log:
        row = parse_run_log(args.original_log)
        row["run_kind"] = "provided_macro_1M"
        row["root_output"] = "output_krakow.root"
        row["root_exists"] = (args.original_log.parent.parent / "run" / "output_krakow.root").exists()
        run_rows.append(row)
    if args.patched_log:
        row = parse_run_log(args.patched_log)
        row["run_kind"] = "patched_no_csfile_100k"
        row["root_output"] = str(args.root)
        row["root_exists"] = args.root.exists()
        run_rows.append(row)
    write_rows(args.report_dir / "run_feasibility.csv", run_rows)

    metadata = {
        "root_file": str(args.root),
        "root_sha256": sha256(args.root),
        "tree": "hibeam",
        "tree_entries": entries,
        "n_branches": len(schema_rows),
        "n_sci_bar_hits": int(len(sci)),
        "seed": args.seed,
        "n_boot": args.n_boot,
    }
    (args.report_dir / "validation_metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")


if __name__ == "__main__":
    main()
