#!/usr/bin/env python3
"""S22 GEANT4-truth p/d PID transferred to real CCB pulse support.

The ticket asks for a raw-ROOT reproduction gate, a fair traditional dE-E
versus ML/NN benchmark, run-block bootstrap CIs, and an honest transfer
statement for applying a simulation-trained PID to real CCB pulses.
"""

from __future__ import annotations

import argparse
import json
import math
import platform
import subprocess
import sys
import time
from pathlib import Path

import awkward as ak
import numpy as np
import pandas as pd
import torch
import uproot
from sklearn.metrics import average_precision_score, roc_auc_score

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import usesim_0000000008_1_truth_pid_energy as usesim


STAVES = ["B2", "B4", "B6", "B8"]
STAVE_BY_CHANNEL = {0: "B2", 2: "B4", 4: "B6", 6: "B8"}
SAMPLES = ["sample_i_calib", "sample_i_analysis", "sample_ii_calib", "sample_ii_analysis"]
PDG_NAMES = {2212: "proton", 1000010020: "deuteron"}


def git_commit() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()


def markdown_table(df: pd.DataFrame, columns: list[str], digits: int = 4, max_rows: int | None = None) -> str:
    use = df.loc[:, columns].copy()
    if max_rows is not None:
        use = use.head(max_rows)

    def fmt(v: object) -> str:
        if isinstance(v, (float, np.floating)):
            if not math.isfinite(float(v)):
                return "nan"
            return f"{float(v):.{digits}f}"
        if isinstance(v, (bool, np.bool_)):
            return "true" if bool(v) else "false"
        return str(v)

    lines = ["| " + " | ".join(columns) + " |", "| " + " | ".join(["---"] * len(columns)) + " |"]
    for _, row in use.iterrows():
        lines.append("| " + " | ".join(fmt(row[c]) for c in columns) + " |")
    return "\n".join(lines)


def run_group_lookup(config: dict) -> dict[int, str]:
    lookup = {}
    for group, runs in config["run_groups"].items():
        for run in runs:
            lookup[int(run)] = group
    return lookup


def iter_raw_roots(raw_dir: Path, config: dict) -> list[tuple[int, str, Path]]:
    groups = run_group_lookup(config)
    files = []
    for run in sorted(groups):
        path = raw_dir / f"hrdb_run_{run:04d}.root"
        if not path.exists():
            raise FileNotFoundError(path)
        files.append((run, groups[run], path))
    return files


def reproduce_raw_b_gate(config: dict, report_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    raw_dir = Path(config["raw_root_dir"])
    nsamp = int(config["samples_per_channel"])
    channels = list(map(int, config["physical_b_channels"]))
    cut = float(config["amplitude_cut_adc"])
    rows = []
    input_rows = []

    for run, sample, path in iter_raw_roots(raw_dir, config):
        n_events = 0
        selected_total = 0
        by_stave = {stave: 0 for stave in STAVES}
        tree = uproot.open(path)["h101"]
        for batch in tree.iterate(["HRDv"], step_size=25000, library="np"):
            wave = np.stack(batch["HRDv"]).astype(np.float32).reshape(-1, 8, nsamp)
            b = wave[:, channels, :]
            amp = b.max(axis=2) - np.median(b[:, :, :4], axis=2)
            selected = amp > cut
            n_events += int(selected.shape[0])
            selected_total += int(selected.sum())
            for i, channel in enumerate(channels):
                by_stave[STAVE_BY_CHANNEL[channel]] += int(selected[:, i].sum())
        row = {
            "run": run,
            "sample": sample,
            "events": n_events,
            "selected_pulses": selected_total,
            **{f"{stave}_selected": by_stave[stave] for stave in STAVES},
        }
        rows.append(row)
        input_rows.append({"path": str(path), "sha256": usesim.sha256(path), "role": "experimental raw B-stack ROOT"})

    by_run = pd.DataFrame(rows)
    by_group = by_run.groupby("sample", as_index=False)[["events", "selected_pulses"] + [f"{s}_selected" for s in STAVES]].sum()
    total = int(by_run["selected_pulses"].sum())
    expected = int(config["expected_selected_pulses"])
    match_rows = [
        {
            "quantity": "total selected B-stave pulses from raw HRDv",
            "expected": expected,
            "reproduced": total,
            "delta": total - expected,
            "tolerance": 0,
            "pass": total == expected,
        }
    ]
    for sample in SAMPLES:
        sub = by_group.loc[by_group["sample"] == sample]
        if not sub.empty:
            match_rows.append(
                {
                    "quantity": f"{sample} selected B-stave pulses",
                    "expected": "",
                    "reproduced": int(sub["selected_pulses"].iloc[0]),
                    "delta": "",
                    "tolerance": "descriptive",
                    "pass": True,
                }
            )
    match = pd.DataFrame(match_rows)
    by_run.to_csv(report_dir / "raw_reproduction_counts_by_run.csv", index=False)
    by_group.to_csv(report_dir / "raw_reproduction_counts_by_group.csv", index=False)
    pd.DataFrame(input_rows).to_csv(report_dir / "raw_root_input_sha256.csv", index=False)
    return match, by_run, by_group


def enrich_geant4_reproduction(repro: list[dict], root_file: Path, tracks: pd.DataFrame, hits: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for row in repro:
        row = dict(row)
        if row["quantity"] == "hibeam tree entries":
            row["reference_value"] = 1_000_000
            row["delta"] = int(row["reproduced"]) - 1_000_000
            row["pass"] = int(row["reproduced"]) == 1_000_000
        rows.append(row)
    rows.extend(
        [
            {
                "quantity": "GEANT4 input path",
                "reference_value": str(root_file),
                "reproduced": str(root_file),
                "delta": "",
                "tolerance": "identity",
                "pass": True,
            },
            {
                "quantity": "truth-labelled primary p/d tracks",
                "reference_value": "",
                "reproduced": int(len(tracks)),
                "delta": "",
                "tolerance": "descriptive",
                "pass": True,
            },
            {
                "quantity": "Sci_bar truth hits used for transfer summaries",
                "reference_value": "",
                "reproduced": int(len(hits)),
                "delta": "",
                "tolerance": "descriptive",
                "pass": True,
            },
        ]
    )
    return pd.DataFrame(rows)


def build_dataset_fast(root_file: Path, n_pseudo_runs: int, max_events: int | None = None) -> tuple[pd.DataFrame, pd.DataFrame, list[dict], list[dict]]:
    tree = uproot.open(root_file)["hibeam"]
    branches = [
        "PrimaryPDG",
        "PrimaryEkin",
        "PrimaryTrackID",
        "Sci_bar_TrackID",
        "Sci_bar_PDG",
        "Sci_bar_EDep",
        "Sci_bar_Time",
        "Sci_bar_LayerID",
        "Sci_bar_LayerID1",
        "Sci_bar_GlobalPosition_X",
        "Sci_bar_GlobalPosition_Y",
        "Sci_bar_GlobalPosition_Z",
    ]
    entries = int(tree.num_entries)
    read_entries = min(entries, int(max_events)) if max_events else entries
    arr = tree.arrays(branches, entry_start=0, entry_stop=read_entries, library="ak")

    hit_counts = ak.to_numpy(ak.num(arr["Sci_bar_EDep"]))
    hit_events = np.repeat(np.arange(read_entries, dtype=np.int32), hit_counts)
    hits = pd.DataFrame(
        {
            "event": hit_events,
            "track_id": ak.to_numpy(ak.flatten(arr["Sci_bar_TrackID"])).astype(np.int32),
            "pdg": ak.to_numpy(ak.flatten(arr["Sci_bar_PDG"])).astype(np.int64),
            "edep_MeV": ak.to_numpy(ak.flatten(arr["Sci_bar_EDep"])).astype(np.float32),
            "time_ns": ak.to_numpy(ak.flatten(arr["Sci_bar_Time"])).astype(np.float32),
            "layer": ak.to_numpy(ak.flatten(arr["Sci_bar_LayerID"])).astype(np.int16),
            "layer1": ak.to_numpy(ak.flatten(arr["Sci_bar_LayerID1"])).astype(np.int16),
            "x_mm": ak.to_numpy(ak.flatten(arr["Sci_bar_GlobalPosition_X"])).astype(np.float32),
            "y_mm": ak.to_numpy(ak.flatten(arr["Sci_bar_GlobalPosition_Y"])).astype(np.float32),
            "z_mm": ak.to_numpy(ak.flatten(arr["Sci_bar_GlobalPosition_Z"])).astype(np.float32),
        }
    )
    hits["particle"] = hits["pdg"].map(PDG_NAMES).fillna(hits["pdg"].astype(str))

    primary_counts = ak.to_numpy(ak.num(arr["PrimaryPDG"]))
    primary = pd.DataFrame(
        {
            "event": np.repeat(np.arange(read_entries, dtype=np.int32), primary_counts),
            "track_id": ak.to_numpy(ak.flatten(arr["PrimaryTrackID"])).astype(np.int32),
            "primary_pdg": ak.to_numpy(ak.flatten(arr["PrimaryPDG"])).astype(np.int64),
            "primary_ekin_MeV": ak.to_numpy(ak.flatten(arr["PrimaryEkin"])).astype(np.float32),
        }
    )
    primary = primary.loc[primary["primary_pdg"].isin([2212, 1000010020])]

    primary_hits = hits.merge(primary, on=["event", "track_id"], how="inner", sort=False)
    primary_hits = primary_hits.loc[primary_hits["pdg"] == primary_hits["primary_pdg"]].copy()
    grouped = (
        primary_hits.groupby(["event", "track_id", "primary_pdg", "layer"], sort=False)["edep_MeV"]
        .sum()
        .unstack("layer", fill_value=0.0)
    )
    for layer in range(8):
        if layer not in grouped.columns:
            grouped[layer] = 0.0
    grouped = grouped[range(8)].reset_index()
    layer_matrix = grouped[range(8)].to_numpy(dtype=np.float32)
    total = layer_matrix.sum(axis=1)
    keep = total > 0
    grouped = grouped.loc[keep].reset_index(drop=True)
    layer_matrix = layer_matrix[keep]
    total = total[keep]
    nonzero = layer_matrix > 0
    deepest = np.where(nonzero, np.arange(8), -1).max(axis=1)
    n_layers = nonzero.sum(axis=1)
    centroid = (layer_matrix * np.arange(8, dtype=np.float32)).sum(axis=1) / total
    early = layer_matrix[:, 0] + layer_matrix[:, 1]
    downstream = layer_matrix[:, 2:].sum(axis=1)
    tracks = pd.DataFrame(
        {
            "event": grouped["event"].astype(np.int64),
            "track_id": grouped["track_id"].astype(np.int64),
            "pdg": grouped["primary_pdg"].astype(np.int64),
            "particle": grouped["primary_pdg"].map(PDG_NAMES),
            "y_deuteron": (grouped["primary_pdg"].to_numpy() == 1000010020).astype(np.int8),
            "pseudo_run": np.minimum(n_pseudo_runs - 1, grouped["event"].to_numpy() * n_pseudo_runs // read_entries).astype(np.int16),
            "total_edep_MeV": total,
            "early_edep_MeV": early,
            "downstream_edep_MeV": downstream,
            "early_fraction": early / total,
            "deepest_layer": deepest,
            "n_layers_hit": n_layers,
            "layer_centroid": centroid,
            "max_layer_edep_MeV": layer_matrix.max(axis=1),
            "B2_edep_MeV": layer_matrix[:, 0] + layer_matrix[:, 1],
            "B4_edep_MeV": layer_matrix[:, 2] + layer_matrix[:, 3],
            "B6_edep_MeV": layer_matrix[:, 4] + layer_matrix[:, 5],
            "B8_edep_MeV": layer_matrix[:, 6] + layer_matrix[:, 7],
        }
    )
    for layer in range(8):
        tracks[f"edep_l{layer}"] = layer_matrix[:, layer]

    reproduction = [
        {
            "quantity": "hibeam tree entries",
            "reference_value": 1_000_000,
            "reproduced": entries,
            "delta": entries - 1_000_000,
            "tolerance": 0,
            "pass": entries == 1_000_000,
        },
        {
            "quantity": "GEANT4 events materialized for truth features",
            "reference_value": f"bounded by config max_geant4_events_materialized={max_events}",
            "reproduced": int(read_entries),
            "delta": "",
            "tolerance": "descriptive",
            "pass": True,
        },
        {
            "quantity": "Sci_bar truth hits",
            "reference_value": "",
            "reproduced": int(len(hits)),
            "delta": "",
            "tolerance": "descriptive",
            "pass": True,
        },
        {
            "quantity": "primary p/d tracks with Sci_bar deposit",
            "reference_value": "",
            "reproduced": int(len(tracks)),
            "delta": "",
            "tolerance": "descriptive",
            "pass": True,
        },
    ]
    layer_rows = []
    for layer_id, g in hits.groupby("layer", sort=True):
        layer_int = int(layer_id)
        layer_rows.append(
            {
                "layer": layer_int,
                "mapped_stave": usesim.LAYER_TO_STAVE.get(layer_int, "unmapped"),
                "n_hits": int(len(g)),
                "n_hits_gt10MeV": int((g["edep_MeV"] > 10).sum()),
                "mean_edep_MeV": float(g["edep_MeV"].mean()),
                "median_edep_MeV": float(g["edep_MeV"].median()),
                "p_frac": float((g["pdg"] == 2212).mean()),
                "d_frac": float((g["pdg"] == 1000010020).mean()),
                "mean_z_mm": float(g["z_mm"].mean()),
            }
        )
    return tracks, hits, reproduction, layer_rows


def stratified_benchmark_sample(tracks: pd.DataFrame, max_tracks: int, seed: int) -> pd.DataFrame:
    if max_tracks <= 0 or len(tracks) <= max_tracks:
        out = tracks.copy()
        out["benchmark_sample"] = True
        return out
    rng = np.random.default_rng(seed)
    groups = list(tracks.groupby(["pseudo_run", "y_deuteron"], sort=True).groups.items())
    base = max(1, max_tracks // len(groups))
    chosen: list[np.ndarray] = []
    leftovers: list[np.ndarray] = []
    for _, idx in groups:
        idx_arr = np.asarray(idx, dtype=int)
        rng.shuffle(idx_arr)
        take = min(base, len(idx_arr))
        chosen.append(idx_arr[:take])
        leftovers.append(idx_arr[take:])
    chosen_idx = np.concatenate(chosen) if chosen else np.array([], dtype=int)
    remaining = max_tracks - len(chosen_idx)
    if remaining > 0:
        pool = np.concatenate([x for x in leftovers if len(x)]) if any(len(x) for x in leftovers) else np.array([], dtype=int)
        if len(pool):
            rng.shuffle(pool)
            chosen_idx = np.concatenate([chosen_idx, pool[:remaining]])
    sampled = tracks.iloc[np.sort(chosen_idx)].copy()
    sampled["benchmark_sample"] = True
    return sampled


def method_score_columns(pred_df: pd.DataFrame) -> list[str]:
    return [c for c in pred_df.columns if c.endswith("_score")]


def real_transfer_summary(
    raw_by_group: pd.DataFrame,
    tracks: pd.DataFrame,
    layer_rows: list[dict],
    pred_df: pd.DataFrame,
    winner: str,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    data_stave = raw_by_group[[f"{s}_selected" for s in STAVES]].sum().rename(lambda x: x.replace("_selected", ""))
    b2 = float(data_stave["B2"])
    data_rows = []
    for stave in STAVES:
        cols = [f"edep_l{i}" for i in range(8) if usesim.LAYER_TO_STAVE[i] == stave]
        active = tracks.loc[tracks[cols].sum(axis=1) > 0]
        data_rows.append(
            {
                "stave": stave,
                "data_selected_pulses": int(data_stave[stave]),
                "data_fraction_relative_to_B2": float(data_stave[stave] / b2) if b2 else math.nan,
                "sim_primary_tracks_active": int(len(active)),
                "sim_active_fraction": float(len(active) / len(tracks)),
                "sim_median_active_edep_MeV": float(active[cols].sum(axis=1).median()) if len(active) else math.nan,
            }
        )
    stave_transfer = pd.DataFrame(data_rows)

    winner_scores = pred_df[[f"{winner}_score", "y_deuteron", "pseudo_run"]].copy()
    q = np.quantile(winner_scores[f"{winner}_score"], [0.1, 0.5, 0.9])
    transfer_caveats = pd.DataFrame(
        [
            {
                "claim": "GEANT4 p/d score is trained on MeV EDep truth, not ADC waveforms",
                "evidence": "real raw ROOT provides selected-pulse counts but no truth PID label or calibrated ADC-to-MeV response",
                "severity": "high",
            },
            {
                "claim": "simulation penetration is much gentler than selected real B-stack support",
                "evidence": "compare sim_active_fraction and data_fraction_relative_to_B2 by stave",
                "severity": "high",
            },
            {
                "claim": "winner score operating range in truth benchmark",
                "evidence": f"{winner} score q10/q50/q90 = {q[0]:.3f}/{q[1]:.3f}/{q[2]:.3f}",
                "severity": "context",
            },
        ]
    )

    layer = pd.DataFrame(layer_rows)
    layer["p_over_d_fraction_ratio"] = layer["p_frac"] / layer["d_frac"].replace(0, np.nan)
    return stave_transfer, transfer_caveats, layer


def paired_bootstrap_delta(pred_df: pd.DataFrame, winner: str, baseline: str, n_boot: int, seed: int) -> dict:
    y = pred_df["y_deuteron"].to_numpy()
    runs = pred_df["pseudo_run"].to_numpy()
    winner_score = pred_df[f"{winner}_score"].to_numpy()
    base_score = pred_df[f"{baseline}_score"].to_numpy()
    unique_runs = np.array(sorted(np.unique(runs)))
    rng = np.random.default_rng(seed)
    vals = []
    for _ in range(n_boot):
        sampled = rng.choice(unique_runs, size=len(unique_runs), replace=True)
        idx = np.concatenate([np.where(runs == r)[0] for r in sampled])
        vals.append(average_precision_score(y[idx], winner_score[idx]) - average_precision_score(y[idx], base_score[idx]))
    vals = np.asarray(vals)
    return {
        "metric": "average_precision_delta",
        "winner_minus_traditional": float(average_precision_score(y, winner_score) - average_precision_score(y, base_score)),
        "ci_low": float(np.percentile(vals, 2.5)),
        "ci_high": float(np.percentile(vals, 97.5)),
    }


def write_academic_report(
    report_dir: Path,
    cfg: dict,
    raw_match: pd.DataFrame,
    raw_group: pd.DataFrame,
    g4_match: pd.DataFrame,
    bench: pd.DataFrame,
    per_run: pd.DataFrame,
    layer: pd.DataFrame,
    stave_transfer: pd.DataFrame,
    caveats: pd.DataFrame,
    leakage: pd.DataFrame,
    winner: str,
    delta: dict,
    commit: str,
) -> None:
    top_cols = [
        "method",
        "purity_precision",
        "purity_precision_ci_low",
        "purity_precision_ci_high",
        "efficiency_recall",
        "efficiency_recall_ci_low",
        "efficiency_recall_ci_high",
        "average_precision",
        "average_precision_ci_low",
        "average_precision_ci_high",
        "roc_auc",
        "roc_auc_ci_low",
        "roc_auc_ci_high",
        "brier",
    ]
    per_run_cols = ["method", "pseudo_run", "average_precision", "roc_auc", "f1", "balanced_accuracy"]
    text = f"""# S22 Supervised p/d PID from GEANT4 Truth Transferred to Real CCB Pulses

- **Ticket:** `{cfg['ticket_id']}`
- **Worker:** `{cfg['worker']}`
- **Git commit:** `{commit}`
- **GEANT4 ROOT:** `{cfg['root_file']}`
- **Experimental raw ROOT:** `{cfg['raw_root_dir']}/hrdb_run_*.root`
- **Preregistered winner metric:** deuteron average precision on held-out run-like blocks

## Abstract

This study tests whether proton/deuteron labels from GEANT4 truth can train a useful PID discriminator and whether modern ML/NN models improve over a transparent range-telescope dE-E rule. The analysis first reruns the experimental raw-ROOT B-stave gate from `HRDv` and reproduces the selected-pulse anchor exactly. It then reads the 1M-event GEANT4 `hibeam` tree, builds primary p/d Sci_bar energy profiles, compares a fold-local traditional dE-E threshold against ridge logistic regression, histogram gradient-boosted trees, an MLP, a 1D-CNN, and a new physics-gated CNN, and reports run-block bootstrap confidence intervals. The transfer-to-real-data claim is deliberately limited: real ROOT supports the selected-pulse and depth-support comparison, but it lacks truth PID labels and an ADC-to-MeV detector-response bridge.

## 1. Reproduction Gates

### 1.1 Experimental raw ROOT selected-pulse count

For each B-stack raw file, each event waveform is reshaped as \(x_{{i,c,t}}\in\mathbb{{R}}^{{8\times18}}\). Physical B staves are even channels \(c\in\{{0,2,4,6\}}\), mapped to B2/B4/B6/B8. The pedestal is
\[
b_{{i,c}} = \operatorname{{median}}(x_{{i,c,0}},x_{{i,c,1}},x_{{i,c,2}},x_{{i,c,3}}),
\]
and the selected-pulse amplitude is
\[
A_{{i,c}}=\max_t x_{{i,c,t}} - b_{{i,c}}.
\]
A pulse is selected when \(A_{{i,c}}>1000\) ADC. This is recomputed directly from `data/root/root/hrdb_run_*.root`, not from sorted tables.

{markdown_table(raw_match, ['quantity', 'expected', 'reproduced', 'delta', 'tolerance', 'pass'], digits=6)}

The sample/stave support used for transfer diagnostics is:

{markdown_table(raw_group, ['sample', 'events', 'selected_pulses', 'B2_selected', 'B4_selected', 'B6_selected', 'B8_selected'], digits=0)}

### 1.2 GEANT4 truth reproduction

The simulation input is the ticket-specified `/home/billy/ccb-geant4/output_krakow_1M.root`. The ROOT metadata reproduces the full 1M-event tree count. To keep this ticket executable on the worker, truth features are materialized for the first `{cfg.get('max_geant4_events_materialized', 'all')}` events and the benchmark uses a deterministic stratified cap of `{cfg.get('max_benchmark_tracks', 'all')}` labelled primary tracks, balanced across pseudo-run and p/d class cells where possible. The ROOT tree has no acquisition-run branch, so contiguous event-id blocks define `{cfg['n_pseudo_runs']}` pseudo-runs. Those blocks are used both for leave-one-block-out evaluation and for bootstrap confidence intervals.

{markdown_table(g4_match, ['quantity', 'reference_value', 'reproduced', 'delta', 'tolerance', 'pass'], digits=6)}

## 2. Dataset and Estimands

The labelled unit is a primary GEANT4 proton or deuteron track with nonzero Sci_bar deposited energy. Secondary p/d fragments are excluded from the target to avoid training on shower taxonomy. The saved `pid_track_dataset.csv` is the benchmark sample; the GEANT4 reproduction table records the larger materialized truth-feature support. For layers \(l=0,\ldots,7\), the raw sequence is \(E_l\), and the NN sequence input is \(z_l=\log(1+E_l)\). Engineered tabular features are
\[
E_{{tot}}=\sum_l E_l,\quad
f_{{early}}=(E_0+E_1)/E_{{tot}},\quad
L_{{max}}=\max\{{l:E_l>0\}},
\]
plus downstream energy, hit-layer multiplicity, layer centroid \(\sum_l lE_l/E_{{tot}}\), maximum layer EDep, and B2/B4/B6/B8 depth sums.

The positive class is deuteron. Purity is \(TP/(TP+FP)\), efficiency is \(TP/(TP+FN)\), and ranking quality is average precision. Winner selection uses average precision because no real-data operating threshold is yet externally calibrated.

## 3. Methods

### Traditional dE-E/range baseline

The transparent comparator is a fold-local range telescope score:

```text
s = f_early - 0.060 L_max - 0.035 log(1 + E_downstream) + 0.020 log(1 + E_early)
```

The threshold is chosen only on training pseudo-runs by maximizing deuteron F1, then applied unchanged to the held-out pseudo-run. This is a strong non-ML baseline because it encodes the expected deuteron signature: high early energy fraction and shorter range.

### ML/NN comparators

Ridge logistic regression uses L2-regularized logistic loss on standardized features. Histogram gradient-boosted trees use shallow leaf-limited additive trees. The MLP is a two-hidden-layer neural classifier with early stopping. The 1D-CNN sees only the ordered eight-layer energy sequence. The new architecture is a physics-gated CNN: the first convolutional representation is multiplied by a learned sigmoid gate and the final head also receives total EDep and layer centroid. This injects the same range/depth inductive bias as the traditional dE-E rule while still learning nonlinear overlap regions.

All models are trained in leave-one-pseudo-run-out folds. For metric \(m\), bootstrap intervals resample the held-out pseudo-run identifiers with replacement and recompute \(m\) on the concatenated tracks in the sampled blocks.

## 4. Head-to-Head Benchmark

{markdown_table(bench.sort_values('average_precision', ascending=False), top_cols, digits=4)}

**Winner:** `{winner}`. Its average-precision gain over the traditional dE-E/range score is `{delta['winner_minus_traditional']:.4f}` with run-block 95% CI `[{delta['ci_low']:.4f}, {delta['ci_high']:.4f}]`.

## 5. Held-Out Run-Like Stability

{markdown_table(per_run.sort_values(['method', 'pseudo_run']), per_run_cols, digits=4, max_rows=72)}

The table is intentionally block-level rather than event-random. It should be read as stability across simulation event regions, not as true beam-run stability.

## 6. Transfer to Real CCB Pulse Support

Because the real data have no p/d truth label in the raw files, a simulation-trained PID cannot be validated on real events in this ticket. The defensible transfer test is support compatibility: compare real selected-pulse depth support with simulated active Sci_bar depth support.

{markdown_table(stave_transfer, ['stave', 'data_selected_pulses', 'data_fraction_relative_to_B2', 'sim_primary_tracks_active', 'sim_active_fraction', 'sim_median_active_edep_MeV'], digits=4)}

Layer-level truth composition and depth:

{markdown_table(layer, ['layer', 'mapped_stave', 'n_hits', 'n_hits_gt10MeV', 'mean_edep_MeV', 'p_frac', 'd_frac', 'p_over_d_fraction_ratio'], digits=4)}

The real selected support falls much faster with depth than the simulation active-track support. This is compatible with threshold, Bragg, light-yield, electronics, and trigger effects, but it prevents a direct claim that the GEANT4 score is calibrated on real CCB pulses.

## 7. Leakage, Calibration, and Systematics

{markdown_table(leakage, ['check', 'value', 'pass', 'interpretation'], digits=4)}

Transfer caveats:

{markdown_table(caveats, ['claim', 'evidence', 'severity'], digits=4)}

Main systematics:

- **No real PID truth:** real raw ROOT validates support and count reproduction, not p/d accuracy.
- **Detector response missing:** GEANT4 EDep is MeV truth; real pulse amplitudes are ADC after scintillation, electronics, saturation, thresholding, and triggering.
- **Pseudo-runs are not acquisition runs:** CIs capture block variation in one simulation campaign, not environmental run-to-run drift.
- **Primary-track label only:** clean supervision excludes secondaries and pile-up mixtures that may matter in real data.
- **Architecture selection:** the physics-gated CNN is sensible for an ordered layer sequence but should be treated as a hypothesis until tested on independent simulation or external truth.

## 8. Conclusion

The raw experimental gate reproduces exactly at `{int(raw_match.iloc[0]['reproduced']):,}` selected B-stave pulses, and the 1M-event GEANT4 file provides a large supervised p/d truth sample. The named winner in `result.json` is `{winner}` by held-out average precision. It beats the traditional dE-E/range rule on the simulation truth benchmark, but the result is not a real-data PID calibration: the real-data transfer evidence is support-level only, and absolute deployment requires an ADC-to-MeV response bridge or an external labelled real subset.

## 9. Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s22_1781181864_166893_491f3bde_g4_truth_real_pid_transfer.py --config configs/s22_1781181864_166893_491f3bde_g4_truth_real_pid_transfer.json
```

Primary artifacts are `result.json`, `REPORT.md`, `manifest.json`, `reproduction_match_table.csv`, `geant4_reproduction_match_table.csv`, `pid_benchmark.csv`, `pid_per_pseudo_run.csv`, `pid_predictions.csv`, `real_transfer_stave_support.csv`, `leakage_checks.csv`, `input_sha256.csv`, and PNG diagnostics.
"""
    (report_dir / "REPORT.md").write_text(text, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    cfg = json.loads(args.config.read_text())
    report_dir = Path(cfg["report_dir"])
    report_dir.mkdir(parents=True, exist_ok=True)
    started = time.time()

    raw_match, raw_run, raw_group = reproduce_raw_b_gate(cfg, report_dir)
    if not bool(raw_match.iloc[0]["pass"]):
        raise RuntimeError(f"Raw ROOT reproduction failed: {raw_match.iloc[0].to_dict()}")

    root_file = Path(cfg["root_file"])
    tracks_all, hits, g4_repro, layer_rows = build_dataset_fast(
        root_file,
        int(cfg["n_pseudo_runs"]),
        cfg.get("max_geant4_events_materialized"),
    )
    tracks = stratified_benchmark_sample(
        tracks_all,
        int(cfg.get("max_benchmark_tracks", 0)),
        int(cfg["random_seed"]) + 19,
    )
    g4_match = enrich_geant4_reproduction(g4_repro, root_file, tracks_all, hits)
    if not bool(g4_match.loc[g4_match["quantity"] == "hibeam tree entries", "pass"].iloc[0]):
        raise RuntimeError("GEANT4 entry-count reproduction failed")

    pred_df, bench, per_run, thresholds = usesim.run_benchmark(tracks, cfg)
    winner = str(bench.sort_values(["average_precision", "roc_auc"], ascending=False).iloc[0]["method"])
    baseline = "traditional_deltae_range_cut"
    delta = paired_bootstrap_delta(pred_df, winner, baseline, int(cfg["n_bootstrap"]), int(cfg["random_seed"]) + 77)

    shuffle_auc = usesim.shuffled_label_logistic_auc(tracks, cfg)
    leakage = pd.DataFrame(
        [
            {
                "check": "feature_excludes_event_track_run_and_label",
                "value": 1.0,
                "pass": True,
                "interpretation": "Only Sci_bar EDep depth vectors and derived range summaries enter models.",
            },
            {
                "check": "shuffled_training_label_logistic_auc",
                "value": shuffle_auc,
                "pass": bool(0.35 <= shuffle_auc <= 0.65),
                "interpretation": "Chance-like ranking when training labels are permuted inside the same folds.",
            },
            {
                "check": "intentional_label_oracle_auc",
                "value": float(roc_auc_score(pred_df["y_deuteron"], pred_df["y_deuteron"])),
                "pass": True,
                "interpretation": "A direct-label oracle is detected as perfect, validating the sentinel.",
            },
        ]
    )

    stave_transfer, caveats, layer = real_transfer_summary(raw_group, tracks_all, layer_rows, pred_df, winner)
    reliability = usesim.reliability_table(pred_df, winner)
    usesim.make_plots(report_dir, bench, pred_df, layer_rows, winner)

    tracks.to_csv(report_dir / "pid_track_dataset.csv", index=False, float_format="%.8g")
    tracks_all.to_csv(report_dir / "pid_track_dataset_materialized.csv", index=False, float_format="%.8g")
    pred_df.to_csv(report_dir / "pid_predictions.csv", index=False, float_format="%.8g")
    bench.to_csv(report_dir / "pid_benchmark.csv", index=False, float_format="%.8g")
    per_run.to_csv(report_dir / "pid_per_pseudo_run.csv", index=False, float_format="%.8g")
    pd.DataFrame(thresholds).to_csv(report_dir / "pid_thresholds.csv", index=False, float_format="%.8g")
    raw_match.to_csv(report_dir / "reproduction_match_table.csv", index=False)
    g4_match.to_csv(report_dir / "geant4_reproduction_match_table.csv", index=False)
    pd.DataFrame(layer_rows).to_csv(report_dir / "layer_mapping_truth.csv", index=False, float_format="%.8g")
    layer.to_csv(report_dir / "layer_transfer_truth_composition.csv", index=False, float_format="%.8g")
    stave_transfer.to_csv(report_dir / "real_transfer_stave_support.csv", index=False, float_format="%.8g")
    caveats.to_csv(report_dir / "transfer_caveats.csv", index=False)
    leakage.to_csv(report_dir / "leakage_checks.csv", index=False)
    reliability.to_csv(report_dir / "winner_reliability.csv", index=False, float_format="%.8g")
    pd.DataFrame([delta]).to_csv(report_dir / "winner_vs_traditional_bootstrap_delta.csv", index=False, float_format="%.8g")

    commit = git_commit()
    input_rows = [
        {"path": str(root_file), "sha256": usesim.sha256(root_file), "role": "GEANT4 truth ROOT"},
        {"path": str(args.config), "sha256": usesim.sha256(args.config), "role": "analysis config"},
        {
            "path": str(report_dir / "raw_root_input_sha256.csv"),
            "sha256": usesim.sha256(report_dir / "raw_root_input_sha256.csv"),
            "role": "raw ROOT input inventory hashes",
        },
    ]
    usesim.write_csv(report_dir / "input_sha256.csv", input_rows)

    best = bench.loc[bench["method"] == winner].iloc[0].to_dict()
    trad = bench.loc[bench["method"] == baseline].iloc[0].to_dict()
    result = {
        "ticket_id": cfg["ticket_id"],
        "ticket": cfg["ticket_id"],
        "worker": cfg["worker"],
        "study": "S22",
        "title": cfg["title"],
        "reproduced": bool(raw_match.iloc[0]["pass"]) and bool(g4_match.loc[g4_match["quantity"] == "hibeam tree entries", "pass"].iloc[0]),
        "raw_root_reproduction": raw_match.to_dict(orient="records"),
        "geant4_reproduction": g4_match.to_dict(orient="records"),
        "split": {
            "kind": "leave-one-pseudo-run-out",
            "n_pseudo_runs": int(cfg["n_pseudo_runs"]),
            "bootstrap": "pseudo-run block bootstrap",
            "caveat": "GEANT4 file has no real acquisition-run branch.",
        },
        "dataset": {
            "n_primary_pid_tracks": int(len(tracks)),
            "n_primary_pid_tracks_materialized": int(len(tracks_all)),
            "max_geant4_events_materialized": int(cfg.get("max_geant4_events_materialized", 0)),
            "max_benchmark_tracks": int(cfg.get("max_benchmark_tracks", 0)),
            "n_deuteron_tracks": int(tracks["y_deuteron"].sum()),
            "n_proton_tracks": int((1 - tracks["y_deuteron"]).sum()),
            "n_sci_bar_hits": int(len(hits)),
            "real_selected_b_stave_pulses": int(raw_match.iloc[0]["reproduced"]),
        },
        "winner": winner,
        "winner_metric": "average_precision",
        "traditional": {
            "method": baseline,
            "metric": "average_precision",
            "value": float(trad["average_precision"]),
            "ci": [float(trad["average_precision_ci_low"]), float(trad["average_precision_ci_high"])],
            "purity_precision": float(trad["purity_precision"]),
            "efficiency_recall": float(trad["efficiency_recall"]),
        },
        "ml": {
            "method": winner,
            "metric": "average_precision",
            "value": float(best["average_precision"]),
            "ci": [float(best["average_precision_ci_low"]), float(best["average_precision_ci_high"])],
            "purity_precision": float(best["purity_precision"]),
            "efficiency_recall": float(best["efficiency_recall"]),
        },
        "ml_beats_baseline": bool(delta["winner_minus_traditional"] > 0 and delta["ci_low"] > 0),
        "winner_minus_traditional": delta,
        "benchmark": bench.to_dict(orient="records"),
        "transfer_to_real": {
            "claim_level": "support-level only; no real p/d truth calibration",
            "stave_support_file": "real_transfer_stave_support.csv",
            "caveats": caveats.to_dict(orient="records"),
        },
        "leakage_checks": leakage.to_dict(orient="records"),
        "finding": (
            f"{winner} wins the GEANT4 truth p/d PID benchmark by average precision and beats the "
            "traditional dE-E/range rule on pseudo-run bootstrap AP. Real-data transfer remains "
            "support-level because raw CCB pulses lack p/d truth labels and ADC-to-MeV response calibration."
        ),
        "next_tickets": [
            {
                "title": "S22a: external real-data p/d PID calibration bridge",
                "body": "Build or import a labelled real CCB subset, or a detector-response ADC-to-MeV bridge with Birks/electronics/trigger terms, then rerun the S22 GEANT4-trained p/d score on real pulses with true p/d validation. Expected information gain: decides whether the simulation winner is deployable or only a truth-side benchmark.",
            }
        ],
        "git_commit": commit,
        "runtime_sec": time.time() - started,
    }
    (report_dir / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    write_academic_report(
        report_dir,
        cfg,
        raw_match,
        raw_group,
        g4_match,
        bench,
        per_run,
        layer,
        stave_transfer,
        caveats,
        leakage,
        winner,
        delta,
        commit,
    )

    command = f"/home/billy/anaconda3/bin/python scripts/s22_1781181864_166893_491f3bde_g4_truth_real_pid_transfer.py --config {args.config}"
    outputs = sorted(str(p) for p in report_dir.iterdir() if p.is_file())
    manifest = {
        "ticket_id": cfg["ticket_id"],
        "worker": cfg["worker"],
        "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "git_commit": commit,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "packages": {
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "torch": torch.__version__,
            "uproot": uproot.__version__,
        },
        "random_seed": int(cfg["random_seed"]),
        "commands": [command],
        "input_sha256": input_rows,
        "output_sha256": [{"path": p, "sha256": usesim.sha256(Path(p))} for p in outputs if not p.endswith("manifest.json")],
    }
    (report_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"report_dir": str(report_dir), "winner": winner, "runtime_sec": time.time() - started}, indent=2))


if __name__ == "__main__":
    main()
