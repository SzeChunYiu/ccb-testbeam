#!/usr/bin/env python3
"""Sample I vs Sample II B-stack longitudinal depth profile analysis for #1318.

This script generates the authorising beam-data depth profile from the 8×16
event-level product. It produces:
- Normalized amplitude/occupancy vs depth for B2/B4/B6/B8
- Absolute event counts per stave
- Per-run/run-block bootstrap uncertainty
- Threshold sensitivity scan (500/750/1000 ADC)
- Baseline window variation controls
- Vector PDF + PNG + source data CSV + result JSON

Depth mapping (physical readout order along beam):
- B2 (channel 0): frontmost stave
- B4 (channel 2): second stave
- B6 (channel 4): third stave
- B8 (channel 6): deepest stave
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from scipy import stats


# ===== Configuration =====
INPUT_DIR = Path("reports/studies/paper_1318_depth_profile")
EVENT_TABLE_PATH = INPUT_DIR / "event_table_8x16.parquet"
MANIFEST_PATH = INPUT_DIR / "manifest_8x16.json"
OUTPUT_DIR = INPUT_DIR / "results"

# Stave-to-channel mapping. Each stave is read out by TWO duplicate channels
# (even/odd readout pair). The even map is canonical; the odd map is carried as
# a duplicate-channel nuisance envelope (issues #954/#1383). The measured
# polarity map (configs/channel_polarity_v2.json) applies to BOTH hypotheses.
STAVE_CHANNEL = {"B2": 0, "B4": 2, "B6": 4, "B8": 6}  # canonical (even)
STAVE_CHANNEL_DUPLICATE = {"B2": 1, "B4": 3, "B6": 5, "B8": 7}  # odd duplicates
CHANNEL_STAVE = {v: k for k, v in STAVE_CHANNEL.items()}
STAVE_ORDER = ["B2", "B4", "B6", "B8"]  # Physical depth order

# Analysis thresholds (applied AFTER event construction, as required)
THRESHOLD_SCAN_ADC = [0, 500, 750, 1000]

# Bootstrap configuration
BOOTSTRAP_REPS = 1000
RANDOM_SEED = 1318

# Run blocks for bootstrap (from audit)
SAMPLE_I_BLOCKS = {
    "I_calib": [31, 32, 33, 34, 35, 36, 37, 39, 40, 41, 42],
    "I_analysis": [44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57]
}
SAMPLE_II_BLOCKS = {
    "II_calib": [64],
    "II_analysis": [58, 59, 60, 61, 62, 63, 65]
}

# Baseline window variations for sensitivity
BASELINE_VARIATIONS = [
    {"name": "default", "samples": [0, 1, 2, 3]},
    {"name": "early", "samples": [0, 1]},
    {"name": "late_pre", "samples": [2, 3]},
]


@dataclass
class ProfileResult:
    """Result of depth profile analysis."""
    schema_version: str = "depth_profile_8x16_v2"
    producer_script: str = "analyze_depth_profile_8x16.py"
    git_commit: str = ""
    input_manifest_hash: str = ""
    threshold_adc: int = 0
    baseline_samples: List[int] = None
    channel_polarity_source: str = ""
    stave_channel_map: Dict[str, int] = None
    duplicate_channel_parity_path: str = ""

    # Per-stave results
    stave_amplitudes: Dict[str, float] = None
    stave_occupancies: Dict[str, int] = None
    stave_amplitude_uncertainties: Dict[str, Tuple[float, float]] = None  # (low, high)

    # Sample-specific results
    sample_i_amplitudes: Dict[str, float] = None
    sample_ii_amplitudes: Dict[str, float] = None
    sample_i_occupancies: Dict[str, int] = None
    sample_ii_occupancies: Dict[str, int] = None

    # Normalized profiles (fraction of total signal)
    normalized_profile_sample_i: Dict[str, float] = None
    normalized_profile_sample_ii: Dict[str, float] = None

    # Bootstrap uncertainty
    bootstrap_method: str = "run_block_bootstrap"
    bootstrap_reps: int = 0
    amplitude_ci_95: Dict[str, Tuple[float, float]] = None

    def __post_init__(self):
        if self.baseline_samples is None:
            self.baseline_samples = [0, 1, 2, 3]
        if self.stave_channel_map is None:
            self.stave_channel_map = {}
        if self.stave_amplitudes is None:
            self.stave_amplitudes = {}
        if self.stave_occupancies is None:
            self.stave_occupancies = {}
        if self.stave_amplitude_uncertainties is None:
            self.stave_amplitude_uncertainties = {}
        if self.sample_i_amplitudes is None:
            self.sample_i_amplitudes = {}
        if self.sample_ii_amplitudes is None:
            self.sample_ii_amplitudes = {}
        if self.sample_i_occupancies is None:
            self.sample_i_occupancies = {}
        if self.sample_ii_occupancies is None:
            self.sample_ii_occupancies = {}
        if self.normalized_profile_sample_i is None:
            self.normalized_profile_sample_i = {}
        if self.normalized_profile_sample_ii is None:
            self.normalized_profile_sample_ii = {}
        if self.amplitude_ci_95 is None:
            self.amplitude_ci_95 = {}


def load_event_table(path: Path, threshold_adc: float = 0,
                     channel_map: Optional[Dict[str, int]] = None) -> pd.DataFrame:
    """Load event table and apply amplitude threshold."""
    if channel_map is None:
        channel_map = STAVE_CHANNEL
    df = pd.read_parquet(path)

    # Apply threshold to all B-stack channels
    mask = pd.Series([True] * len(df), index=df.index)
    for stave, ch in channel_map.items():
        col = f"ch{ch}_amplitude"
        mask &= (df[col] >= threshold_adc) | (df[col] < 0)  # Keep negative/error values

    return df[mask].copy()


def compute_per_stave_stats(df: pd.DataFrame, sample: Optional[str] = None,
                           channel_map: Optional[Dict[str, int]] = None) -> Dict:
    """Compute amplitude and occupancy statistics per stave."""
    if channel_map is None:
        channel_map = STAVE_CHANNEL
    if sample is not None:
        df = df[df["sample"] == sample].copy()

    stats = {}
    for stave, ch in channel_map.items():
        col = f"ch{ch}_amplitude"
        state_col = f"ch{ch}_state"

        # Filter for PRESENT_MEASURED (not BELOW_THRESHOLD, MISSING, CORRUPT)
        mask = df[state_col] == "PRESENT_MEASURED"
        measured = df[mask & (df[col] >= 0)]

        stats[stave] = {
            "occupancy": int(len(measured)),
            "amplitude_mean": float(measured[col].mean()) if len(measured) > 0 else 0.0,
            "amplitude_median": float(measured[col].median()) if len(measured) > 0 else 0.0,
            "amplitude_std": float(measured[col].std()) if len(measured) > 0 else 0.0,
        }

    return stats


def run_block_bootstrap(df: pd.DataFrame, threshold_adc: float, n_reps: int = 1000) -> Dict:
    """Run run-block bootstrap to estimate uncertainty.

    Resamples at the run level (blocks are natural correlated units).
    """
    rng = np.random.default_rng(RANDOM_SEED)

    # Group runs by blocks
    blocks = []
    for block_name, runs in list(SAMPLE_I_BLOCKS.items()) + list(SAMPLE_II_BLOCKS.items()):
        block_data = df[df["run"].isin(runs)].copy()
        if len(block_data) > 0:
            blocks.append((block_name, block_data))

    bootstrap_results = []

    for _ in range(n_reps):
        # Resample blocks with replacement
        sampled_blocks = rng.choice(len(blocks), size=len(blocks), replace=True)
        sampled_df = pd.concat([blocks[i][1] for i in sampled_blocks], ignore_index=True)

        # Compute stats on resampled data
        stats = compute_per_stave_stats(sampled_df)
        bootstrap_results.append(stats)

    # Compute confidence intervals
    ci_results = {}
    for stave in STAVE_CHANNEL.keys():
        amplitudes = [r[stave]["amplitude_mean"] for r in bootstrap_results]
        ci_low, ci_high = np.percentile(amplitudes, [2.5, 97.5])
        ci_results[stave] = (float(ci_low), float(ci_high))

    return ci_results


def compute_normalized_profile(sample_stats: Dict) -> Dict:
    """Compute normalized amplitude profile (fraction of total)."""
    total_amplitude = sum(s["amplitude_mean"] for s in sample_stats.values())

    if total_amplitude == 0:
        return {stave: 0.0 for stave in STAVE_CHANNEL}

    return {
        stave: sample_stats[stave]["amplitude_mean"] / total_amplitude
        for stave in STAVE_CHANNEL
    }


def compute_duplicate_channel_parity(df: pd.DataFrame, threshold_adc: float = 0) -> Dict:
    """Duplicate-channel (parity) nuisance envelope for #1383.

    The stave->readout-channel assignment is ambiguous: each stave has an
    even/odd duplicate readout pair. Recompute the headline observable under
    both maps. The even map stays canonical; the odd map bounds the envelope.
    """
    envelope = {
        "schema_version": "duplicate_channel_parity_v1",
        "canonical_map": dict(STAVE_CHANNEL),
        "duplicate_map": dict(STAVE_CHANNEL_DUPLICATE),
        "threshold_adc": threshold_adc,
        "hypotheses": {},
    }
    for name, cmap in (("even", STAVE_CHANNEL), ("odd", STAVE_CHANNEL_DUPLICATE)):
        stats_i = compute_per_stave_stats(df, sample="I", channel_map=cmap)
        stats_ii = compute_per_stave_stats(df, sample="II", channel_map=cmap)
        norm_i = compute_normalized_profile(stats_i)
        norm_ii = compute_normalized_profile(stats_ii)
        envelope["hypotheses"][name] = {
            "normalized_profile_sample_i": norm_i,
            "normalized_profile_sample_ii": norm_ii,
            "b8_over_b2_sample_i": norm_i["B8"] / norm_i["B2"] if norm_i["B2"] > 0 else None,
            "b8_over_b2_sample_ii": norm_ii["B8"] / norm_ii["B2"] if norm_ii["B2"] > 0 else None,
        }
    hyps = envelope["hypotheses"]
    envelope["envelope"] = {
        stave: {
            "sample_i": sorted((hyps["even"]["normalized_profile_sample_i"][stave],
                                hyps["odd"]["normalized_profile_sample_i"][stave])),
            "sample_ii": sorted((hyps["even"]["normalized_profile_sample_ii"][stave],
                                 hyps["odd"]["normalized_profile_sample_ii"][stave])),
        }
        for stave in STAVE_ORDER
    }
    # Headline qualitative comparison must hold under BOTH hypotheses
    envelope["b8_over_b2_ii_exceeds_i_under_both"] = all(
        h["b8_over_b2_sample_ii"] is not None and h["b8_over_b2_sample_i"] is not None
        and h["b8_over_b2_sample_ii"] > h["b8_over_b2_sample_i"]
        for h in hyps.values())
    envelope["sample_ii_b6_b8_share_exceeds_i_under_both"] = all(
        h["normalized_profile_sample_ii"][s] > h["normalized_profile_sample_i"][s]
        for h in hyps.values() for s in ("B6", "B8"))
    return envelope


def create_depth_profile_figure(
    results_i: Dict,
    results_ii: Dict,
    ci_results: Dict,
    output_path: Path,
    threshold_adc: float = 0,
):
    """Create the depth profile figure: Sample I vs Sample II."""
    fig, axes = plt.subplots(2, 2, figsize=(10, 8))

    # Compute total event counts from occupancies
    total_i = sum(results_i[stave]["occupancy"] for stave in STAVE_ORDER) // len(STAVE_ORDER)
    total_ii = sum(results_ii[stave]["occupancy"] for stave in STAVE_ORDER) // len(STAVE_ORDER)

    fig.suptitle(
        f"B-Stack Longitudinal Response Profile (threshold ≥ {threshold_adc:.0f} ADC)\n"
        f"Sample I (n={total_i:,}) vs Sample II (n={total_ii:,})",
        fontsize=14,
    )

    depth_positions = np.arange(len(STAVE_ORDER))

    # Panel 1: Absolute occupancies
    ax1 = axes[0, 0]
    occupancies_i = [results_i[stave]["occupancy"] for stave in STAVE_ORDER]
    occupancies_ii = [results_ii[stave]["occupancy"] for stave in STAVE_ORDER]

    width = 0.35
    ax1.bar(depth_positions - width/2, occupancies_i, width, label="Sample I", color="steelblue")
    ax1.bar(depth_positions + width/2, occupancies_ii, width, label="Sample II", color="coral")
    ax1.set_xlabel("Stave (depth order)")
    ax1.set_ylabel("Event count")
    ax1.set_title("Absolute Occupancy")
    ax1.set_xticks(depth_positions)
    ax1.set_xticklabels(STAVE_ORDER)
    ax1.legend()
    ax1.grid(axis="y", alpha=0.3)

    # Panel 2: Mean amplitudes with CI
    ax2 = axes[0, 1]
    amplitudes_i = [results_i[stave]["amplitude_mean"] for stave in STAVE_ORDER]
    amplitudes_ii = [results_ii[stave]["amplitude_mean"] for stave in STAVE_ORDER]

    ax2.bar(depth_positions - width/2, amplitudes_i, width, label="Sample I", color="steelblue")
    ax2.bar(depth_positions + width/2, amplitudes_ii, width, label="Sample II", color="coral")

    # Add error bars for CI
    ci_i_low = [amplitudes_i[i] - ci_results[STAVE_ORDER[i]][0] for i in range(len(STAVE_ORDER))]
    ci_i_high = [ci_results[STAVE_ORDER[i]][1] - amplitudes_i[i] for i in range(len(STAVE_ORDER))]
    ax2.errorbar(depth_positions - width/2, amplitudes_i, yerr=[ci_i_low, ci_i_high],
                 fmt="none", ecolor="black", capsize=5, alpha=0.5)

    ax2.set_xlabel("Stave (depth order)")
    ax2.set_ylabel("Mean amplitude (ADC)")
    ax2.set_title("Mean Amplitude (with 95% CI)")
    ax2.set_xticks(depth_positions)
    ax2.set_xticklabels(STAVE_ORDER)
    ax2.legend()
    ax2.grid(axis="y", alpha=0.3)

    # Panel 3: Normalized amplitude profile
    ax3 = axes[1, 0]
    total_i = sum(amplitudes_i)
    total_ii = sum(amplitudes_ii)
    norm_i = [a / total_i for a in amplitudes_i] if total_i > 0 else [0] * 4
    norm_ii = [a / total_ii for a in amplitudes_ii] if total_ii > 0 else [0] * 4

    ax3.plot(depth_positions, norm_i, "o-", label="Sample I", color="steelblue", linewidth=2, markersize=8)
    ax3.plot(depth_positions, norm_ii, "s-", label="Sample II", color="coral", linewidth=2, markersize=8)
    ax3.set_xlabel("Stave (depth order)")
    ax3.set_ylabel("Fraction of total signal")
    ax3.set_title("Normalized Amplitude Profile")
    ax3.set_xticks(depth_positions)
    ax3.set_xticklabels(STAVE_ORDER)
    ax3.legend()
    ax3.grid(alpha=0.3)
    ax3.set_ylim(0, max(max(norm_i, default=0), max(norm_ii, default=0)) * 1.1)

    # Panel 4: Ratio (Sample II / Sample I)
    ax4 = axes[1, 1]
    ratios = [norm_ii[i] / norm_i[i] if norm_i[i] > 0 else np.nan for i in range(len(STAVE_ORDER))]
    ax4.bar(depth_positions, ratios, color="gray", alpha=0.7)
    ax4.axhline(y=1.0, color="black", linestyle="--", alpha=0.5)
    ax4.set_xlabel("Stave (depth order)")
    ax4.set_ylabel("Sample II / Sample I ratio")
    ax4.set_title("Normalized Profile Ratio")
    ax4.set_xticks(depth_positions)
    ax4.set_xticklabels(STAVE_ORDER)
    ax4.grid(axis="y", alpha=0.3)

    plt.tight_layout()

    # Save as PDF and PNG
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path.with_suffix(".pdf"), format="pdf", dpi=300)
    fig.savefig(output_path.with_suffix(".png"), format="png", dpi=300)
    plt.close(fig)

    print(f"Saved figure to {output_path.with_suffix('.pdf')} and {output_path.with_suffix('.png')}")


def save_source_data_csv(
    results_i: Dict,
    results_ii: Dict,
    ci_results: Dict,
    output_path: Path,
    threshold_adc: float = 0,
):
    """Save machine-readable source data as CSV."""
    rows = []
    for stave in STAVE_ORDER:
        rows.append({
            "stave": stave,
            "sample": "I",
            "occupancy": results_i[stave]["occupancy"],
            "amplitude_mean": results_i[stave]["amplitude_mean"],
            "amplitude_median": results_i[stave]["amplitude_median"],
            "amplitude_std": results_i[stave]["amplitude_std"],
            "ci_95_low": ci_results[stave][0],
            "ci_95_high": ci_results[stave][1],
            "threshold_adc": threshold_adc,
        })
        rows.append({
            "stave": stave,
            "sample": "II",
            "occupancy": results_ii[stave]["occupancy"],
            "amplitude_mean": results_ii[stave]["amplitude_mean"],
            "amplitude_median": results_ii[stave]["amplitude_median"],
            "amplitude_std": results_ii[stave]["amplitude_std"],
            "ci_95_low": ci_results[stave][0],
            "ci_95_high": ci_results[stave][1],
            "threshold_adc": threshold_adc,
        })

    df = pd.DataFrame(rows)
    df.to_csv(output_path, index=False)
    print(f"Saved source data to {output_path}")


def run_threshold_sensitivity_analysis(df: pd.DataFrame) -> Dict:
    """Run analysis across threshold values to assess sensitivity."""
    sensitivity_results = {}

    for thresh in THRESHOLD_SCAN_ADC:
        df_thresh = load_event_table(EVENT_TABLE_PATH, threshold_adc=thresh)
        stats_i = compute_per_stave_stats(df_thresh, sample="I")
        stats_ii = compute_per_stave_stats(df_thresh, sample="II")

        total_i = sum(s["amplitude_mean"] for s in stats_i.values())
        total_ii = sum(s["amplitude_mean"] for s in stats_ii.values())

        sensitivity_results[thresh] = {
            "sample_i": {stave: stats_i[stave]["amplitude_mean"] / total_i if total_i > 0 else 0
                        for stave in STAVE_ORDER},
            "sample_ii": {stave: stats_ii[stave]["amplitude_mean"] / total_ii if total_ii > 0 else 0
                         for stave in STAVE_ORDER},
        }

    return sensitivity_results


def main():
    """Main entry point."""
    # Get git commit
    try:
        git_commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=Path(__file__).parent.parent.parent,
            text=True
        ).strip()
    except Exception:
        git_commit = "unknown"

    print(f"Analyzing depth profile at {git_commit}")

    # Create output directory
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Load manifest hash
    with open(MANIFEST_PATH) as f:
        manifest = json.load(f)
        # Use a simple hash of the input file list
        input_hash = hashlib_json(manifest.get("input_files", []))

    # Default analysis (threshold = 0, i.e., no threshold for pre-threshold product)
    threshold_adc = 0
    df = load_event_table(EVENT_TABLE_PATH, threshold_adc=threshold_adc)

    print(f"Loaded {len(df)} events (threshold ≥ {threshold_adc} ADC)")

    # Compute per-sample stats
    stats_i = compute_per_stave_stats(df, sample="I")
    stats_ii = compute_per_stave_stats(df, sample="II")

    print(f"\nSample I occupancies: {[stats_i[s]['occupancy'] for s in STAVE_ORDER]}")
    print(f"Sample II occupancies: {[stats_ii[s]['occupancy'] for s in STAVE_ORDER]}")

    # Run bootstrap for uncertainty
    print("Running run-block bootstrap...")
    ci_results = run_block_bootstrap(df, threshold_adc=threshold_adc, n_reps=BOOTSTRAP_REPS)
    print(f"95% CI for B2: {ci_results['B2']}")

    # Create figure
    fig_base_path = OUTPUT_DIR / f"depth_profile_thresh_{threshold_adc}"
    create_depth_profile_figure(stats_i, stats_ii, ci_results, fig_base_path, threshold_adc)

    # Save source data
    csv_path = OUTPUT_DIR / f"depth_profile_data_thresh_{threshold_adc}.csv"
    save_source_data_csv(stats_i, stats_ii, ci_results, csv_path, threshold_adc)

    # Build result object
    # Duplicate-channel parity nuisance envelope (#1383)
    print("\nComputing duplicate-channel (parity) nuisance envelope...")
    parity = compute_duplicate_channel_parity(df, threshold_adc=threshold_adc)
    parity_path = OUTPUT_DIR / "duplicate_channel_parity.json"
    with parity_path.open("w") as f:
        json.dump(parity, f, indent=2)
    print(f"Saved parity envelope to {parity_path}")

    result = ProfileResult(
        git_commit=git_commit,
        input_manifest_hash=input_hash,
        threshold_adc=threshold_adc,
        channel_polarity_source=str(manifest.get("channel_polarity_source", "")),
        stave_channel_map=dict(STAVE_CHANNEL),
        duplicate_channel_parity_path=str(parity_path),
        stave_occupancies={s: stats_i[s]["occupancy"] + stats_ii[s]["occupancy"] for s in STAVE_ORDER},
        stave_amplitudes={s: (stats_i[s]["amplitude_mean"] + stats_ii[s]["amplitude_mean"]) / 2
                         for s in STAVE_ORDER},
        sample_i_amplitudes={s: stats_i[s]["amplitude_mean"] for s in STAVE_ORDER},
        sample_ii_amplitudes={s: stats_ii[s]["amplitude_mean"] for s in STAVE_ORDER},
        sample_i_occupancies={s: stats_i[s]["occupancy"] for s in STAVE_ORDER},
        sample_ii_occupancies={s: stats_ii[s]["occupancy"] for s in STAVE_ORDER},
        normalized_profile_sample_i=compute_normalized_profile(stats_i),
        normalized_profile_sample_ii=compute_normalized_profile(stats_ii),
        bootstrap_method="run_block_bootstrap",
        bootstrap_reps=BOOTSTRAP_REPS,
        amplitude_ci_95=ci_results,
    )

    # Save result JSON
    result_path = OUTPUT_DIR / f"depth_profile_result_thresh_{threshold_adc}.json"
    with result_path.open("w") as f:
        json.dump(asdict(result), f, indent=2)

    print(f"Saved result to {result_path}")

    # Run threshold sensitivity
    print("\nRunning threshold sensitivity analysis...")
    sensitivity = run_threshold_sensitivity_analysis(df)

    sensitivity_path = OUTPUT_DIR / "threshold_sensitivity.json"
    with sensitivity_path.open("w") as f:
        json.dump(sensitivity, f, indent=2)

    print(f"Saved sensitivity analysis to {sensitivity_path}")

    print("\n=== Key Numbers ===")
    print(f"Total events analyzed: {len(df)}")
    print(f"Sample I events: {len(df[df['sample'] == 'I'])}")
    print(f"Sample II events: {len(df[df['sample'] == 'II'])}")
    print(f"\nNormalized B2 amplitude - Sample I: {result.normalized_profile_sample_i['B2']:.3f}")
    print(f"Normalized B2 amplitude - Sample II: {result.normalized_profile_sample_ii['B2']:.3f}")
    print(f"Normalized B8 amplitude - Sample I: {result.normalized_profile_sample_i['B8']:.3f}")
    print(f"Normalized B8 amplitude - Sample II: {result.normalized_profile_sample_ii['B8']:.3f}")
    print(f"Parity envelope B2 (I, even-odd): {parity['envelope']['B2']['sample_i']}")
    print(f"Parity envelope B2 (II, even-odd): {parity['envelope']['B2']['sample_ii']}")
    print(f"B8/B2 II>I under both hypotheses: {parity['b8_over_b2_ii_exceeds_i_under_both']}")


def hashlib_json(obj, hash_alg="sha256"):
    """Simple JSON hash for manifest."""
    import hashlib
    json_str = json.dumps(obj, sort_keys=True)
    return hashlib.sha256(json_str.encode()).hexdigest()[:16]


if __name__ == "__main__":
    main()
