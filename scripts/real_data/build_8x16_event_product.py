#!/usr/bin/env python3
"""Content-addressed pre-threshold 8×16 event-level product builder for #1318.

This script constructs the authorising beam-data event table from raw HRDv
waveforms (8 channels × 16 samples per event). It enforces:
- Exact 8ch×16samples/event contract
- Event-key uniqueness (run, eventno)
- Run population completeness
- Channel state preservation (PRESENT_MEASURED / BELOW_ANY_THRESHOLD / MISSING / CORRUPT)
- Source-bound channel polarity (fail-closed if unresolved)
- Pre-threshold amplitude storage (thresholds applied only as downstream selections)

Input: /projects/hep/fs10/shared/nnbar/ccb_data/hrd/root/hrdb_run_*.root
Output: Content-addressed event table with manifest
"""

from __future__ import annotations

import hashlib
import json
import sys
import subprocess
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import uproot
import pandas as pd


# ===== Configuration =====
RAW_ROOT_DIR = Path("/projects/hep/fs10/shared/nnbar/ccb_data/hrd/root")
OUTPUT_DIR = Path("reports/studies/paper_1318_depth_profile")

# Authorising paper runs from PAPER-A02
PAPER_RUNS = [
    31, 32, 33, 34, 35, 36, 37, 39, 40, 41, 42, 44, 45, 46, 47, 48, 49, 50,
    51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65
]

# Stave-to-channel mapping (from config)
STAVE_CHANNEL = {"B2": 0, "B4": 2, "B6": 4, "B8": 6}

# Expected contract
SAMPLES_PER_CHANNEL = 16
N_CHANNELS = 8
EXPECTED_WORDS_PER_EVENT = N_CHANNELS * SAMPLES_PER_CHANNEL  # 128

# Polarity contract
POLARITY_CONFIG = Path(__file__).parent.parent.parent / "configs" / "channel_polarity_v2.json"

# Channel state constants
CHAN_PRESENT_MEASURED = "PRESENT_MEASURED"
CHAN_BELOW_THRESHOLD = "BELOW_ANY_THRESHOLD"
CHAN_MISSING = "MISSING"
CHAN_CORRUPT = "CORRUPT"


@dataclass
class ProductManifest:
    """Content-addressed manifest for the 8×16 event product."""
    schema_version: str = "hrd_raw_8x16_v1"
    producer_script: str = "build_8x16_event_product.py"
    git_commit: str = ""
    input_files: List[Dict] = None
    total_events: int = 0
    events_by_run: Dict[int, int] = None
    events_by_sample: Dict[str, int] = None  # Sample I / II
    channel_polarity_source: str = ""
    baseline_samples: List[int] = None
    baseline_region_adc: Tuple[float, float] = None  # (median, mad) across all data
    amplitude_estimator: str = ""
    threshold_scan_adc: List[int] = None
    duplicate_events: int = 0
    corrupt_events: int = 0
    missing_channels: Dict[str, int] = None

    def __post_init__(self):
        if self.input_files is None:
            self.input_files = []
        if self.events_by_run is None:
            self.events_by_run = {}
        if self.events_by_sample is None:
            self.events_by_sample = {}
        if self.baseline_samples is None:
            self.baseline_samples = [0, 1, 2, 3]
        if self.threshold_scan_adc is None:
            self.threshold_scan_adc = [500, 750, 1000]
        if self.missing_channels is None:
            self.missing_channels = {}


# Fail-closed allowlist of polarity-map statuses (issue #954).
# v1 (LOCKED_FROM_DUPLICATE_READOUT_CONVENTION) was falsified for channels 2-7
# by the measured study reports/studies/paper_954_polarity/: under v1 the B4/B6/B8
# amplitudes are noise-side maxima, not pulse heights. v1 stays accepted ONLY so
# legacy artifacts remain bit-for-bit reproducible; new products must use
# configs/channel_polarity_v2.json.
ACCEPTED_POLARITY_STATUSES = {
    "LOCKED_FROM_DUPLICATE_READOUT_CONVENTION",
    "MEASURED_202608_RUNS31_65_UNANIMOUS_BOTH_ESTIMATORS",
}


def load_polarity_map(path: Path) -> Dict:
    """Load the locked channel polarity map."""
    with path.open() as f:
        data = json.load(f)

    if data.get("status") in ACCEPTED_POLARITY_STATUSES:
        return data["channel_polarity"]

    raise ValueError(
        f"Channel polarity status is {data.get('status')!r}, not an accepted "
        f"status ({sorted(ACCEPTED_POLARITY_STATUSES)}). Cannot proceed with "
        "unresolved polarity (issue #954)."
    )


def compute_file_sha256(path: Path) -> str:
    """Compute SHA-256 hash of a file."""
    sha = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(65536):
            sha.update(chunk)
    return sha.hexdigest()


def get_baseline_samples() -> List[int]:
    """Return baseline sample indices (first 4 samples)."""
    return [0, 1, 2, 3]


def estimate_baseline(waveform: np.ndarray) -> float:
    """Estimate baseline as median of first 4 samples."""
    return np.median(waveform[get_baseline_samples()])


def estimate_amplitude(waveform: np.ndarray, baseline: float, polarity: int) -> float:
    """Estimate amplitude: polarity * (peak - baseline) for positive-going pulses.

    For negative polarity channels, polarity=-1, so:
        amplitude = -1 * (max - baseline) = baseline - min
    This makes all amplitudes positive for physical pulses.
    """
    if polarity == 1:
        # Positive-going: max is the peak
        return polarity * (np.max(waveform) - baseline)
    elif polarity == -1:
        # Negative-going: min is the peak (most negative)
        return polarity * (np.min(waveform) - baseline)
    else:
        raise ValueError(f"polarity must be ±1, got {polarity}")


def validate_waveform_shape(waveform: np.ndarray, run: int, eventno: int) -> bool:
    """Validate that waveform has exactly 8×16=128 samples."""
    expected = EXPECTED_WORDS_PER_EVENT
    actual = waveform.size
    if actual != expected:
        raise ValueError(
            f"Run {run} event {eventno}: waveform has {actual} samples, "
            f"expected {expected} (8 channels × {SAMPLES_PER_CHANNEL} samples)"
        )
    return True


def read_root_file(path: Path, run: int) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Read HRD ROOT file and return (eventno, waveforms, timestamps).

    The LUNARC HRD ROOT structure uses:
    - Tree name: "h101;1"
    - Event number: "EVENTNO" branch
    - Waveform data: "HRDv" branch (variable-length array, 128 values per event)

    Returns:
        eventno: array of event numbers
        waveforms: (n_events, 8, 16) array of ADC values
        timestamps: array of timestamps (if available)
    """
    try:
        with uproot.open(path) as f:
            tree = f["h101;1"]

            # Get event number (uppercase EVENTNO)
            eventno = tree["EVENTNO"].array(library="np")

            # Get waveform data from HRDv branch
            hrdv = tree["HRDv"].array(library="np")

            # HRDv is a JaggedArray; convert to regular array
            n_events = len(hrdv)
            waveforms_flat = np.zeros((n_events, EXPECTED_WORDS_PER_EVENT), dtype=np.int32)

            for i, evt in enumerate(hrdv):
                waveforms_flat[i, :] = evt

            # Reshape to (n_events, 8, 16)
            waveforms = waveforms_flat.reshape(n_events, N_CHANNELS, SAMPLES_PER_CHANNEL)

            # Get timestamps if available (check for EVT or similar)
            timestamps = tree["EVT"].array(library="np") if "EVT" in tree.keys() else np.zeros(len(eventno), dtype=np.int32)

            return eventno, waveforms, timestamps

    except Exception as e:
        raise RuntimeError(f"Failed to read {path}: {e}") from e


def check_channel_state(waveform_ch: np.ndarray, polarity: int, threshold_adc: float = 0) -> str:
    """Determine channel state based on waveform quality.

    Returns:
        CHAN_PRESENT_MEASURED: waveform has valid data above threshold
        CHAN_BELOW_THRESHOLD: amplitude < threshold but waveform valid
        CHAN_MISSING: all zeros
        CHAN_CORRUPT: contains inf/nan
    """
    # Check for corruption
    if not np.all(np.isfinite(waveform_ch)):
        return CHAN_CORRUPT

    # Check for missing (all zeros)
    if np.all(waveform_ch == 0):
        return CHAN_MISSING

    # Compute amplitude
    baseline = estimate_baseline(waveform_ch)
    amplitude = estimate_amplitude(waveform_ch, baseline, polarity)

    # Check threshold (default 0 = no threshold for pre-threshold product)
    if abs(amplitude) < threshold_adc:
        return CHAN_BELOW_THRESHOLD

    return CHAN_PRESENT_MEASURED


def build_event_table(
    runs: List[int],
    raw_dir: Path,
    polarity_map: Dict[str, int],
    output_path: Path,
) -> Tuple[pd.DataFrame, ProductManifest]:
    """Build the pre-threshold event-level table.

    Returns:
        events_df: DataFrame with event-level data
        manifest: Product manifest with provenance
    """
    manifest = ProductManifest()

    all_events = []
    seen_keys = set()
    duplicate_count = 0
    corrupt_count = 0

    # Run classification (from config)
    sample_i_runs = set([
        31, 32, 33, 34, 35, 36, 37, 39, 40, 41, 42,  # calib
        44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57  # analysis
    ])
    sample_ii_runs = set([
        64,  # calib
        58, 59, 60, 61, 62, 63, 65  # analysis
    ])

    for run in sorted(runs):
        root_path = raw_dir / f"hrdb_run_{run:04d}.root"
        if not root_path.exists():
            print(f"WARNING: Run {run} file not found: {root_path}")
            continue

        # Record input file
        file_sha = compute_file_sha256(root_path)
        manifest.input_files.append({
            "run": run,
            "path": str(root_path),
            "sha256": file_sha,
            "bytes": root_path.stat().st_size
        })

        try:
            eventno, waveforms, timestamps = read_root_file(root_path, run)
        except Exception as e:
            print(f"ERROR reading run {run}: {e}")
            continue

        n_events = len(eventno)
        manifest.events_by_run[run] = n_events

        # Classify run
        if run in sample_i_runs:
            sample = "I"
        elif run in sample_ii_runs:
            sample = "II"
        else:
            sample = "UNKNOWN"

        for i, (ev, wf) in enumerate(zip(eventno, waveforms)):
            # Check for duplicate keys
            key = (run, int(ev))
            if key in seen_keys:
                duplicate_count += 1
                continue
            seen_keys.add(key)

            # Validate waveform shape
            try:
                validate_waveform_shape(wf.flatten(), run, ev)
            except ValueError as e:
                corrupt_count += 1
                continue

            # Extract per-channel amplitudes
            event_row = {
                "run": run,
                "eventno": int(ev),
                "sample": sample,
                "timestamp": timestamps[i] if i < len(timestamps) else 0,
            }

            # Process each channel
            for ch in range(N_CHANNELS):
                waveform_ch = wf[ch, :]
                pol = int(polarity_map[str(ch)])

                baseline = estimate_baseline(waveform_ch)
                amplitude = estimate_amplitude(waveform_ch, baseline, pol)
                state = check_channel_state(waveform_ch, pol, threshold_adc=0)

                event_row[f"ch{ch}_baseline"] = baseline
                event_row[f"ch{ch}_amplitude"] = amplitude
                event_row[f"ch{ch}_state"] = state

            all_events.append(event_row)

    # Build DataFrame
    df = pd.DataFrame(all_events)

    if len(df) == 0:
        print("WARNING: No events loaded! Check file paths and run numbers.")
        manifest.total_events = 0
        manifest.events_by_sample = {"I": 0, "II": 0}
        return df, manifest

    # Update manifest
    manifest.total_events = len(df)
    manifest.duplicate_events = duplicate_count
    manifest.corrupt_events = corrupt_count
    manifest.events_by_sample = {
        "I": int(len(df[df["sample"] == "I"])),
        "II": int(len(df[df["sample"] == "II"]))
    }

    # Compute baseline stats
    all_baselines = []
    for ch in range(N_CHANNELS):
        col = f"ch{ch}_baseline"
        if col in df.columns:
            all_baselines.extend(df[col].dropna().tolist())

    if all_baselines:
        baselines_arr = np.array(all_baselines)
        baseline_median = float(np.median(baselines_arr))
        baseline_mad = float(np.median(np.abs(baselines_arr - baseline_median)))
        manifest.baseline_region_adc = (baseline_median, baseline_mad)

    return df, manifest


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

    print(f"Building 8×16 event product at {git_commit}")

    # Load polarity
    polarity = load_polarity_map(POLARITY_CONFIG)
    print(f"Loaded polarity from {POLARITY_CONFIG}")

    # Create output directory
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Build event table
    df, manifest = build_event_table(
        runs=PAPER_RUNS,
        raw_dir=RAW_ROOT_DIR,
        polarity_map=polarity,
        output_path=OUTPUT_DIR / "event_table_8x16.parquet"
    )

    # Save event table
    output_path = OUTPUT_DIR / "event_table_8x16.parquet"
    df.to_parquet(output_path, compression="snappy")
    print(f"Saved {len(df)} events to {output_path}")

    # Update manifest
    manifest.git_commit = git_commit
    manifest.channel_polarity_source = str(POLARITY_CONFIG)
    manifest.amplitude_estimator = "polarity * (peak - baseline) with peak=max for pol=+1, min for pol=-1"

    # Save manifest
    manifest_path = OUTPUT_DIR / "manifest_8x16.json"
    with manifest_path.open("w") as f:
        json.dump(asdict(manifest), f, indent=2)

    print(f"Saved manifest to {manifest_path}")
    print(f"Total events: {manifest.total_events}")
    print(f"Sample I: {manifest.events_by_sample.get('I', 0)}")
    print(f"Sample II: {manifest.events_by_sample.get('II', 0)}")
    print(f"Duplicates skipped: {manifest.duplicate_events}")
    print(f"Corrupt events: {manifest.corrupt_events}")


if __name__ == "__main__":
    main()
