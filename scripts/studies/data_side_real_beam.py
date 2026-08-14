#!/usr/bin/env python3
"""Data-side analysis on real CCB test-beam data.

The selected-pulse occupancy is descriptive. It does not identify an absolute
arrival rate, the legacy ``mu_max=0.38`` convention, or a detector-wide live
window. Consequently this producer reports an Rmax model sensitivity only and
fails closed on scientific authorization.
"""
from __future__ import annotations

import errno
import hashlib
import json
import os
import stat
import time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from ccb_mc_validation.raw_uproot_authorization import (
    open_verified_uproot,
    require_manifest_rows,
)

RAW_DIR = Path("/projects/hep/fs10/shared/nnbar/ccb_data/hrd/root")
CANON = Path("reports/1781028640.1299.266407ae/s00_selected_b_pulses.csv.gz")
REBUILT = Path("reports/studies/data_side/s00_rebuild/s00_selected_b_pulses.csv.gz")
OUT = Path("reports/studies/data_side")
OUT.mkdir(parents=True, exist_ok=True)
STAVE_CH = {"B2": 0, "B4": 2, "B6": 4, "B8": 6}
NSAMP = 16
SAMPLE_T = 10.0
BASELINE_IDX = [0, 1, 2, 3]
ACQ_WINDOW_NS = NSAMP * SAMPLE_T
AMPLITUDE_CUT = 1000.0
CFD_FRACTION = 0.20
SPACING_CM = 0.78
TOF_PER_CM = 0.078
MC_COMBINED_SIGMA68_NS = 0.089
MC_CFD_SIGMA68_NS = 0.151
MC_DEE_CORR = -0.533
TAU_CL011_NS = 124.79018394263471
MU_LEGACY = 0.38
RAW_INPUT_DIGEST_SCHEMA = "same-open-stream-v1"


class RawInputProvenanceError(RuntimeError):
    """Raised when raw-input identity cannot be bound to a stable byte stream."""


def sha256_file(path: Path, block_size: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def digest_raw_input(path: Path, block_size: int = 1 << 20) -> dict[str, object]:
    """Hash and count one stable regular-file stream from one open descriptor.

    The final path component must not be a symlink.  ``sha256`` and ``bytes``
    are derived from the exact same ``os.read`` stream, while descriptor
    identity and mutation-sensitive metadata are checked before and after the
    read.  The digest, not the mutable pathname, is the long-term content
    identity recorded by the manifest.
    """
    if block_size <= 0:
        raise ValueError("block_size must be positive")
    nofollow = getattr(os, "O_NOFOLLOW", None)
    if nofollow is None:
        raise RawInputProvenanceError(
            "raw provenance requires os.O_NOFOLLOW for fail-closed symlink policy"
        )
    try:
        descriptor = os.open(path, os.O_RDONLY | nofollow)
    except OSError as exc:
        if exc.errno == errno.ELOOP:
            raise RawInputProvenanceError(
                f"raw input final path component must not be a symlink: {path}"
            ) from exc
        raise

    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise RawInputProvenanceError(f"raw input is not a regular file: {path}")

        digest = hashlib.sha256()
        byte_count = 0
        while True:
            block = os.read(descriptor, block_size)
            if not block:
                break
            digest.update(block)
            byte_count += len(block)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)

    before_state = (
        before.st_dev,
        before.st_ino,
        before.st_nlink,
        before.st_size,
        before.st_mtime_ns,
        before.st_ctime_ns,
    )
    after_state = (
        after.st_dev,
        after.st_ino,
        after.st_nlink,
        after.st_size,
        after.st_mtime_ns,
        after.st_ctime_ns,
    )
    if before_state != after_state or byte_count != after.st_size:
        raise RawInputProvenanceError(
            f"raw input changed while being digested: {path}"
        )
    # Timestamp advancement of the unlinked inode is not observable on
    # every filesystem (LUNARC probe: identical ctime_ns after a mid-read
    # os.replace), so the fd-state tuple alone can miss a path
    # replacement on such filesystems. Re-resolve the path and require it
    # to still name the digested inode; fail closed if it vanished or was
    # rotated to a different inode instead.
    try:
        resolved = os.stat(path)
    except OSError as exc:
        raise RawInputProvenanceError(
            f"raw input vanished while being digested: {path} ({exc})"
        ) from exc
    if (resolved.st_dev, resolved.st_ino) != (after.st_dev, after.st_ino):
        raise RawInputProvenanceError(
            f"raw input changed while being digested: {path} (open fd ino {after.st_ino}, path now resolves to ino {resolved.st_ino})"
        )

    return {
        "sha256": digest.hexdigest(),
        "bytes": int(byte_count),
        "source_dev": int(after.st_dev),
        "source_ino": int(after.st_ino),
        "source_nlink": int(after.st_nlink),
        "source_mtime_ns": int(after.st_mtime_ns),
        "source_ctime_ns": int(after.st_ctime_ns),
    }


def collect_raw_input_digests(
    used_runs: list[int], raw_dir: Path | None = None
) -> tuple[list[dict[str, object]], list[int]]:
    """Return complete digest records and explicitly missing canonical runs.

    The returned digest list is never truncated for presentation. A provenance
    consumer must be able to verify every available input represented by the
    accompanying count rather than receiving a sample under a full-manifest
    field name. Every available row binds hash and byte count to one opened
    descriptor through :func:`digest_raw_input`.
    """
    root = RAW_DIR if raw_dir is None else raw_dir
    digests: list[dict[str, object]] = []
    missing_runs: list[int] = []
    for run in used_runs:
        path = root / f"hrdb_run_{run:04d}.root"
        try:
            digest_record = digest_raw_input(path)
        except FileNotFoundError:
            missing_runs.append(int(run))
            continue
        digests.append(
            {
                "run": int(run),
                "file": str(path),
                **digest_record,
            }
        )
    return digests, missing_runs


def cfd_time(corr, fraction=CFD_FRACTION, period=SAMPLE_T):
    """Return the rising-edge constant-fraction crossing time in ns."""
    amp = corr.max()
    if amp <= 0:
        return None
    threshold = fraction * amp
    above = np.where(corr >= threshold)[0]
    if len(above) == 0:
        return None
    index = above[0]
    if index == 0:
        return 0.0
    y0, y1 = corr[index - 1], corr[index]
    denominator = y1 - y0
    fraction_in_sample = (threshold - y0) / denominator if denominator > 0 else 0.0
    return (index - 1 + fraction_in_sample) * period


def data_provenance():
    rebuilt = pd.read_csv(REBUILT) if REBUILT.exists() else None
    canon = pd.read_csv(CANON)
    record = {
        "canonical_table": str(CANON),
        "canonical_rows": int(len(canon)),
        "canonical_count_CL001": 640737,
        "rebuilt_table": str(REBUILT),
        "rebuilt_rows": int(len(rebuilt)) if rebuilt is not None else None,
        "documented_dynamic_range_selected_s00c": 706373,
        "documented_median_first_four_selected_s00c": 640737,
        "raw_dir": str(RAW_DIR),
        "nsamp_per_channel": NSAMP,
        "layout": "channel-major (8,16); verified by exact baseline/amplitude match",
        "raw_input_digest_schema": RAW_INPUT_DIGEST_SCHEMA,
        "raw_input_digest_contract": (
            "sha256 and bytes come from one O_NOFOLLOW descriptor; "
            "fstat identity/size/mtime/ctime must remain stable during read"
        ),
    }
    if rebuilt is not None:
        rebuilt_keys = set(zip(rebuilt.run, rebuilt.eventno, rebuilt.stave))
        canon_keys = set(zip(canon.run, canon.eventno, canon.stave))
        record["composite_key_overlap"] = int(len(rebuilt_keys & canon_keys))
        record["rebuilt_only"] = int(len(rebuilt_keys - canon_keys))
        record["canonical_only"] = int(len(canon_keys - rebuilt_keys))
        event = canon[
            (canon.run == 31) & (canon.eventno == 391389) & (canon.stave == "B2")
        ]
        rebuilt_event = rebuilt[
            (rebuilt.run == 31)
            & (rebuilt.eventno == 391389)
            & (rebuilt.stave == "B2")
        ]
        if len(event) and len(rebuilt_event):
            record["event_31_391389_B2_canonical_amp"] = float(
                event.amplitude_adc.iloc[0]
            )
            record["event_31_391389_B2_rebuilt_amp"] = float(
                rebuilt_event.amplitude_adc.iloc[0]
            )
            record["event_31_391389_B2_baseline_match_exact"] = bool(
                abs(event.baseline_adc.iloc[0] - rebuilt_event.baseline_adc.iloc[0])
                < 1e-6
            )
    used_runs = sorted(canon.run.unique().tolist())
    record["canonical_run_range"] = [min(used_runs), max(used_runs)]
    record["n_runs_used"] = len(used_runs)
    digests, missing_runs = collect_raw_input_digests(used_runs)
    record["raw_input_sha256"] = digests
    record["raw_input_sha256_count"] = len(digests)
    record["raw_input_missing_runs"] = missing_runs
    record["raw_input_sha256_complete"] = not missing_runs
    (OUT / "provenance.json").write_text(json.dumps(record, indent=2))
    return record, canon


def deltae_e(canon):
    pivot = canon.pivot_table(
        index=["run", "eventno", "group"],
        columns="stave",
        values="amplitude_adc",
        aggfunc="first",
    ).reset_index()
    subset = pivot.dropna(subset=["B2", "B4"]).copy()
    subset["E_B2"] = subset["B2"]
    subset["dE_B4"] = subset["B4"]
    duplicates = subset.duplicated(subset=["run", "eventno"]).sum()
    corr = (
        float(np.corrcoef(subset["E_B2"], subset["dE_B4"])[0, 1])
        if len(subset) > 2
        else float("nan")
    )
    bins = np.quantile(subset["E_B2"], np.linspace(0, 1, 11))
    mids = []
    quantiles = []
    for lower, upper in zip(bins[:-1], bins[1:]):
        mask = (subset.E_B2 >= lower) & (subset.E_B2 < upper)
        if mask.sum() > 20:
            mids.append(0.5 * (lower + upper))
            quantiles.append(np.quantile(subset.dE_B4[mask], [0.16, 0.5, 0.84]))
    quantiles = np.asarray(quantiles)
    mids = np.asarray(mids)
    figure, axis = plt.subplots(figsize=(6.2, 5))
    axis.hexbin(subset.E_B2, subset.dE_B4, gridsize=70, mincnt=1, bins="log")
    axis.plot(mids, quantiles[:, 1], "w-", lw=2, label="median(dE|E)")
    axis.plot(mids, quantiles[:, 0], "w--", lw=1, alpha=0.7)
    axis.plot(mids, quantiles[:, 2], "w--", lw=1, alpha=0.7)
    axis.set_xlabel("E (B2 amplitude, ADC)")
    axis.set_ylabel("DeltaE (B4 amplitude, ADC)")
    axis.set_title(
        f"DATA DeltaE-E ({len(subset):,} events); corr={corr:+.2f}; "
        f"MC={MC_DEE_CORR:+.2f}; key duplicates={int(duplicates)}"
    )
    axis.legend(loc="upper right", fontsize=9)
    figure.tight_layout()
    figure.savefig(OUT / "VIS-DE-001-DATA_deltaE_E_real.png", dpi=170)
    plt.close(figure)
    return {
        "n_events_both_B2_B4": int(len(subset)),
        "corr_dE_E_data": corr,
        "corr_dE_E_mc": MC_DEE_CORR,
        "composite_key_duplicates": int(duplicates),
        "E_B2_wmedian_ADC": float(np.quantile(subset.E_B2, 0.5)),
        "dE_B4_wmedian_ADC": float(np.quantile(subset.dE_B4, 0.5)),
    }


def _coincidence_sets(canon):
    grouped = canon.groupby(["run", "eventno"]).stave.apply(set).reset_index()
    b4b6 = grouped[grouped.stave.apply(lambda value: {"B4", "B6"}.issubset(value))]
    b4b6b8 = grouped[
        grouped.stave.apply(lambda value: {"B4", "B6", "B8"}.issubset(value))
    ]
    return set(zip(b4b6.run, b4b6.eventno)), set(zip(b4b6b8.run, b4b6b8.eventno))


def timing(canon, provenance):
    """Measure sampling-limited B4-B6 timing from manifest-authorized raw bytes."""
    need_b4b6, need_b4b6b8 = _coincidence_sets(canon)
    by_run: dict[int, set[int]] = {}
    for run, event in need_b4b6 | need_b4b6b8:
        by_run.setdefault(int(run), set()).add(int(event))

    manifest_rows = provenance.get("raw_input_sha256")
    if not isinstance(manifest_rows, list):
        raise RawInputProvenanceError("raw_input_sha256 must be a complete row list")
    authorized_rows = require_manifest_rows(manifest_rows, by_run)

    records = []
    for run in sorted(by_run):
        path = RAW_DIR / f"hrdb_run_{run:04d}.root"
        wanted = by_run[run]
        with open_verified_uproot(path, authorized_rows[run]) as raw_file:
            tree = raw_file["h101"]
            for batch in tree.iterate(
                ["EVENTNO", "HRDv"], step_size=20000, library="np"
            ):
                event_numbers = np.asarray(batch["EVENTNO"]).astype(int)
                for index, event in enumerate(event_numbers):
                    if int(event) not in wanted:
                        continue
                    waveform = np.asarray(batch["HRDv"][index], dtype=float)
                    if waveform.size != 8 * NSAMP:
                        continue
                    waveform = waveform.reshape(8, NSAMP)
                    times = {}
                    maxima = {}
                    for stave, channel in STAVE_CH.items():
                        corrected = waveform[channel] - np.median(
                            waveform[channel, BASELINE_IDX]
                        )
                        maxima[stave] = int(corrected.argmax())
                        times[stave] = (
                            None
                            if corrected.max() < AMPLITUDE_CUT
                            else cfd_time(corrected)
                        )
                    records.append(
                        {
                            "run": run,
                            "eventno": int(event),
                            "B4_argmax": maxima["B4"],
                            "B6_argmax": maxima["B6"],
                            "B8_argmax": maxima["B8"],
                            **{f"{key}_t": value for key, value in times.items()},
                        }
                    )
    frame = pd.DataFrame(records)
    paired = frame.dropna(subset=["B4_t", "B6_t"])
    time_of_flight = SPACING_CM * TOF_PER_CM
    residual = (paired.B6_t - paired.B4_t - time_of_flight).to_numpy()
    sigma68 = 0.5 * (np.percentile(residual, 84) - np.percentile(residual, 16))
    clean = frame[
        frame.B4_argmax.between(3, 11) & frame.B6_argmax.between(3, 11)
    ].dropna(subset=["B4_t", "B6_t"])
    clean_residual = (clean.B6_t - clean.B4_t - time_of_flight).to_numpy()
    clean_sigma68 = (
        0.5 * (np.percentile(clean_residual, 84) - np.percentile(clean_residual, 16))
        if len(clean_residual) > 10
        else None
    )
    output = {
        "verdict": "INFEASIBLE_ON_RAW_FORMAT: sampling-limited, not detector resolution",
        "n_B4B6_with_times": int(len(paired)),
        "residual_sigma68_B4B6_ns_sampling_limited": float(sigma68),
        "B4_argmax_mode_sample": int(frame.B4_argmax.value_counts().idxmax()),
        "B6_argmax_modes_sample": sorted(
            frame.B6_argmax.value_counts().head(3).index.tolist()
        ),
        "clean_inwindow_subset_size": int(len(clean)),
        "clean_subset_sigma68_ns": (
            float(clean_sigma68) if clean_sigma68 is not None else None
        ),
        "sample_period_ns": SAMPLE_T,
        "acq_window_ns": ACQ_WINDOW_NS,
        "mc_combined_sigma68_ns_for_reference": MC_COMBINED_SIGMA68_NS,
        "canonical_B6_CL002_ns_was_mc_toy": 0.68,
        "raw_input_authorization": "manifest-bound-same-open-stream-v1",
        "raw_runs_authorized": sorted(by_run),
        "note": "Measured data-format limitation, not detector resolution.",
    }
    figure, axes = plt.subplots(1, 2, figsize=(11, 4.2))
    bins = np.arange(-0.5, 16.5, 1)
    axes[0].hist([frame.B4_argmax, frame.B6_argmax], bins=bins, label=["B4", "B6"])
    axes[0].set_xlabel("peak sample (of 16)")
    axes[0].set_ylabel("events")
    axes[0].legend()
    axes[1].hist(residual, bins=80)
    axes[1].set_xlabel("t_B6 - t_B4 - ToF (ns)")
    axes[1].set_ylabel("events")
    axes[1].set_title(f"sigma68={sigma68:.1f} ns; sampling dominated")
    figure.tight_layout()
    figure.savefig(OUT / "VIS-TIM-DATA_sampling_limited.png", dpi=170)
    plt.close(figure)
    return output


def rmax(canon):
    """Report occupancy and a non-authorizing legacy-model sensitivity.

    Selected-pulse multiplicity does not measure event-arrival rate, exposure,
    ``mu_max``, or detector-wide live time. Rmax withheld pending S-STAT-003.
    """
    events = canon.groupby(["run", "eventno"]).size().rename("n_pulses").reset_index()
    mean_occupancy = float(events.n_pulses.mean())
    fraction_ge3 = float((events.n_pulses >= 3).mean())
    model_sensitivity_mhz = MU_LEGACY / (TAU_CL011_NS * 1e-9) / 1e6
    output = {
        "mean_selected_pulses_per_event": mean_occupancy,
        "frac_events_ge3_pulses": fraction_ge3,
        "measured_occupancy_role": "DESCRIPTIVE_SELECTED_PULSE_MULTIPLICITY_ONLY",
        "rmax_authorized": False,
        "rmax_status": "BLOCKED",
        "accepted_rmax_mhz": None,
        "blocked_by": "S-STAT-003",
        "tau_eff_cl011_ns": TAU_CL011_NS,
        "mu_max_legacy_convention": MU_LEGACY,
        "model_sensitivity_only_mhz": model_sensitivity_mhz,
        "interpretation": (
            "Rmax withheld: occupancy does not measure event-arrival rate, exposure, "
            "mu_max, or a detector-wide live window. The numerical rate is a legacy "
            "duty-factor convention sensitivity only."
        ),
    }
    figure, axis = plt.subplots(figsize=(6.2, 4.2))
    axis.hist(events.n_pulses, bins=np.arange(0.5, 6.5, 1), density=True)
    axis.set_xlabel("selected B-stave pulses per event")
    axis.set_ylabel("fraction of events")
    axis.set_title(
        f"DATA selected-pulse occupancy (mean={mean_occupancy:.2f})\n"
        "Rmax withheld pending S-STAT-003"
    )
    figure.tight_layout()
    figure.savefig(OUT / "VIS-PU-DATA_occupancy_rmax.png", dpi=170)
    plt.close(figure)
    print("[rmax] Rmax withheld; model sensitivity only =", model_sensitivity_mhz, "MHz")
    return output


def main() -> int:
    started = time.time()
    provenance, canon = data_provenance()
    metrics = {
        "provenance_summary": {
            key: value for key, value in provenance.items() if key != "raw_input_sha256"
        },
        "VIS-DE-001-DATA": deltae_e(canon),
        "VIS-TIM-DATA": timing(canon, provenance),
        "VIS-PU-DATA": rmax(canon),
        "MC_anchors": {
            "combined_sigma68_ns": MC_COMBINED_SIGMA68_NS,
            "cfd_sigma68_ns": MC_CFD_SIGMA68_NS,
            "deltaE_E_corr": MC_DEE_CORR,
        },
        "elapsed_s": round(time.time() - started, 1),
    }
    (OUT / "metrics.json").write_text(json.dumps(metrics, indent=2))
    print(
        json.dumps(
            {key: value for key, value in metrics.items() if key != "provenance_summary"},
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())