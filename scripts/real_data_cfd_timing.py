#!/usr/bin/env python3
"""Pair-only CFD timing study for LUNARC fs10 HRD waveforms.

Event identity is (run,event_id). B6-B8 pair widths are not converted to an
individual-stave resolution without an explicit deconvolution model.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import uproot

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import s02_timing_pickoff as s02  # noqa: E402
from real_data_cfd_contract import (  # noqa: E402
    EVENT_KEY_COLUMNS,
    POLICY,
    pair_only_inference_contract,
    pair_residual_vector,
    residual_plot_record,
    select_in_time_rows,
)

VERSION = "2.0.0"
DATA_DIR = Path(os.environ.get(
    "CCB_DATA_DIR", "/projects/hep/fs10/shared/nnbar/ccb_data/hrd/root"))
OUT_DIR = Path(os.environ.get("CCB_OUTDIR", "reports/real_data_cfd_timing"))
SAMPLES = int(os.environ.get("CCB_SAMPLES_PER_CHANNEL", "16"))
N_CHANNELS = int(os.environ.get("CCB_N_CHANNELS", "8"))
BASELINE = [int(x) for x in os.environ.get("CCB_BASELINE_SAMPLES", "0,1,2,3").split(",")]
PERIOD_NS = float(os.environ.get("CCB_SAMPLE_PERIOD_NS", "10.0"))
AMP_CUT = float(os.environ.get("CCB_AMPLITUDE_CUT_ADC", "1000.0"))
FRACTIONS = [float(x) for x in os.environ.get(
    "CCB_CFD_FRACTIONS", "0.1,0.2,0.3,0.4,0.5").split(",")]
SPACING_CM = float(os.environ.get("CCB_SPACING_CM", "2.0"))
TOF_PER_CM_NS = float(os.environ.get("CCB_TOF_PER_CM_NS", "0.078"))
INTIME_TOL = float(os.environ.get("CCB_INTIME_TOL", "1.5"))
BOOTSTRAP_N = int(os.environ.get("CCB_BOOTSTRAP_N", "400"))
RNG_SEED = int(os.environ.get("CCB_RNG_SEED", "20260723"))
STAVE_CHANNEL = {"B2": 0, "B6": 4, "B8": 6}
PAIR = ("B6", "B8")
RUNS_SAMPLE_II = [int(x) for x in os.environ.get(
    "CCB_RUNS_SAMPLE_II", "58,59,60,61,62,63,65").split(",")]
RUNS_TASK = [int(x) for x in os.environ.get(
    "CCB_RUNS_TASK", "19,20,23,24,25,26,27,28,29,30").split(",")]


def log(message: str) -> None:
    print(f"[real-cfd] {message}", flush=True)


def atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent,
        prefix=f".{path.name}.", suffix=".tmp", delete=False)
    temp = Path(handle.name)
    try:
        with handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
    except Exception:
        temp.unlink(missing_ok=True)
        raise


def load_waveforms(runs: list[int], staves: list[str]) -> pd.DataFrame:
    channels = np.asarray([STAVE_CHANNEL[s] for s in staves])
    frames = []
    for run in runs:
        path = DATA_DIR / f"hrdb_run_{run:04d}.root"
        if not path.exists():
            log(f"run {run}: missing, skip")
            continue
        tree = uproot.open(path)["h101"]
        if tree.num_entries == 0:
            log(f"run {run}: empty, skip")
            continue
        for batch in tree.iterate(["EVENTNO", "HRDv"], step_size=20000, library="np"):
            event = np.asarray(batch["EVENTNO"], dtype=np.int64)
            allw = np.stack(batch["HRDv"]).astype(float).reshape(-1, N_CHANNELS, SAMPLES)
            wave = allw[:, channels, :]
            baseline = np.median(wave[:, :, BASELINE], axis=-1)
            corrected = wave - baseline[:, :, None]
            amp = corrected.max(axis=-1)
            peak = corrected.argmax(axis=-1)
            event_i, stave_i = np.where(amp > AMP_CUT)
            if len(event_i) == 0:
                continue
            frames.append(pd.DataFrame({
                "run": run, "event_id": event[event_i],
                "stave": [staves[i] for i in stave_i],
                "amplitude_adc": amp[event_i, stave_i],
                "peak_sample": peak[event_i, stave_i],
                "waveform": [corrected[i, j].astype(np.float32)
                             for i, j in zip(event_i, stave_i, strict=True)],
            }))
    if not frames:
        raise RuntimeError(f"No data for runs {runs}")
    return pd.concat(frames, ignore_index=True)


def pulse_shape(df: pd.DataFrame, staves: list[str]) -> dict[str, dict]:
    wave = np.vstack(df["waveform"].to_numpy())
    amp = df["amplitude_adc"].to_numpy()
    output = {}
    for stave in staves:
        mask = df["stave"].to_numpy() == stave
        if not mask.any():
            output[stave] = {"n": 0}
            continue
        above = (wave[mask] > 0.1 * amp[mask, None]).sum(axis=1)
        output[stave] = {
            "n": int(mask.sum()), "amp_median_adc": float(np.median(amp[mask])),
            "samples_above_10pct_median": float(np.median(above)),
            "frac_ge3_above_10pct": float(np.mean(above >= 3)),
        }
    return output


def tof_map() -> dict[str, float]:
    return {"B6": 2 * SPACING_CM * TOF_PER_CM_NS,
            "B8": 3 * SPACING_CM * TOF_PER_CM_NS}


def _required_finite(name: str, value: float) -> float:
    number = float(value)
    if not np.isfinite(number):
        raise ValueError(f"{name} must be finite")
    return number


def _optional_finite(value: float) -> float | None:
    number = float(value)
    return number if np.isfinite(number) else None


def pair_result(df, column, offsets, rng) -> dict | None:
    vector = pair_residual_vector(df, column, *PAIR, tof_map(), offsets, PERIOD_NS)
    if not len(vector):
        return None
    fit = s02.core_fit(vector)
    ci = s02.bootstrap_ci(vector, rng, BOOTSTRAP_N)
    q16, q84 = np.quantile(vector, [0.16, 0.84])
    median = np.median(vector)
    return {
        "n": int(len(vector)),
        "median_ns": _required_finite("median_ns", median),
        "q16_ns": _required_finite("q16_ns", q16),
        "q84_ns": _required_finite("q84_ns", q84),
        "sigma68_ns": _required_finite("sigma68_ns", s02.sigma68(vector)),
        "ci68_ns": [
            _required_finite("ci68_low_ns", ci[0]),
            _required_finite("ci68_high_ns", ci[1]),
        ],
        "core_sigma_ns": _optional_finite(fit["core_sigma_ns"]),
        "core_chi2_ndf": _optional_finite(fit["chi2_ndf"]),
        "tail_frac_gt5ns": _required_finite(
            "tail_frac_gt5ns", np.mean(np.abs(vector - median) > 5)
        ),
        "full_rms_ns": _required_finite("full_rms_ns", s02.full_rms(vector)),
    }


def evaluate(df, offsets, rng) -> list[dict]:
    wave = np.vstack(df["waveform"].to_numpy())
    amp = df["amplitude_adc"].to_numpy()
    rows = []
    for fraction in FRACTIONS:
        column = f"t_cfd{int(round(fraction * 100)):02d}"
        df[column] = PERIOD_NS * s02.cfd_time_samples(wave, amp, fraction)
        result = pair_result(df, column, offsets, rng)
        if result:
            result.update(method=column, fraction=fraction)
            rows.append(result)
    try:
        templates = s02.build_templates(df, list(PAIR))
        df["t_template"] = PERIOD_NS * s02.template_phase_time(
            df, templates, np.arange(-1.5, 1.55, 0.05))
        result = pair_result(df, "t_template", offsets, rng)
        if result:
            result.update(method="template", fraction=None)
            rows.append(result)
    except Exception as error:
        log(f"template skipped: {error}")
    return rows


def residual_payload(df, offsets) -> list[tuple[str, np.ndarray, dict]]:
    requested = [f"t_cfd{int(round(FRACTIONS[0] * 100)):02d}", "t_cfd20"]
    output = []
    for column in requested:
        if column not in df:
            continue
        vector = pair_residual_vector(df, column, *PAIR, tof_map(), offsets, PERIOD_NS)
        if not len(vector):
            continue
        centered, record = residual_plot_record(vector, column)
        output.append((column, centered, record.to_dict()))
    return output


def make_figures(df, rows, offsets, tag) -> tuple[list[str], list[dict]]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    figures = []
    wave = np.vstack(df["waveform"].to_numpy())
    amp = df["amplitude_adc"].to_numpy()
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    for stave in sorted(df.stave.unique()):
        sub = df[df.stave == stave]
        w = np.vstack(sub.waveform.to_numpy())[:400]
        amplitudes = sub.amplitude_adc.to_numpy()[:400]
        peaks = sub.peak_sample.to_numpy()[:400]
        aligned = [x[int(p)-4:int(p)+5] / max(a, 1.0)
                   for x, a, p in zip(w, amplitudes, peaks, strict=True)
                   if int(p) - 4 >= 0 and int(p) + 5 <= SAMPLES]
        if aligned:
            axes[0].plot(np.arange(-4, 5) * PERIOD_NS, np.mean(aligned, axis=0),
                         marker="o", label=f"{stave} (n={len(sub)})")
        mask = df.stave.to_numpy() == stave
        above = (wave[mask] > 0.1 * amp[mask, None]).sum(axis=1)
        axes[1].hist(above, bins=np.arange(-0.5, SAMPLES + 1.5), alpha=0.6, label=stave)
    axes[0].set(xlabel="time from peak (ns)", ylabel="amplitude / peak",
                title=f"Peak-aligned mean pulse [{tag}]")
    axes[1].set(xlabel="samples above 10% of peak", ylabel="pulses",
                title="Pulse width (CFD applicability)")
    for axis in axes:
        axis.grid(alpha=0.3)
        axis.legend()
    fig.tight_layout()
    path = OUT_DIR / f"pulse_shape_{tag}.png"
    fig.savefig(path, dpi=120)
    plt.close(fig)
    figures.append(str(path))

    payload = residual_payload(df, offsets)
    metadata = [item[2] for item in payload]
    fig, axes = plt.subplots(1, 2, figsize=(12, 4))
    for method, centered, meta in payload:
        axes[0].hist(centered, bins=80, range=tuple(meta["full_range_ns"]),
                     alpha=0.45, label=f"{method} (n={meta['n_total']})")
        axes[1].hist(centered, bins=80, range=tuple(meta["core_range_ns"]), alpha=0.45,
                     label=(f"{method}: shown={meta['core_displayed']}, "
                            f"under={meta['core_underflow']}, over={meta['core_overflow']}"))
        for axis in axes:
            axis.axvline(meta["q16_centered_ns"], color="k", ls=":", lw=0.8)
            axis.axvline(meta["q84_centered_ns"], color="k", ls=":", lw=0.8)
    axes[0].set_title(f"Median-centered full residual range [{tag}]")
    axes[1].set_title(f"Median-centered core view [{tag}]")
    for axis in axes:
        axis.set(xlabel=f"{'-'.join(PAIR)} residual minus median (ns)", ylabel="events")
        axis.axvline(0, color="k", lw=0.5)
        axis.grid(alpha=0.3)
        axis.legend(fontsize=8)
    fig.tight_layout()
    path = OUT_DIR / f"residuals_{tag}.png"
    fig.savefig(path, dpi=120)
    plt.close(fig)
    figures.append(str(path))

    cfd = [row for row in rows if row["fraction"] is not None]
    fig, axis = plt.subplots(figsize=(6, 4))
    if cfd:
        x = [row["fraction"] for row in cfd]
        axis.errorbar(x, [row["sigma68_ns"] for row in cfd],
                      yerr=[[row["sigma68_ns"]-row["ci68_ns"][0] for row in cfd],
                            [row["ci68_ns"][1]-row["sigma68_ns"] for row in cfd]],
                      marker="o", label="pair sigma68")
        core = [
            np.nan if row["core_sigma_ns"] is None else row["core_sigma_ns"]
            for row in cfd
        ]
        axis.plot(x, core, marker="s", label="Gaussian core sigma")
        axis.set(xlabel="CFD fraction", ylabel=f"{'-'.join(PAIR)} pair width (ns)",
                 title=f"CFD fraction sensitivity [{tag}]")
        axis.grid(alpha=0.3)
        axis.legend()
    fig.tight_layout()
    path = OUT_DIR / f"sigma_vs_fraction_{tag}.png"
    fig.savefig(path, dpi=120)
    plt.close(fig)
    figures.append(str(path))
    return figures, metadata


def run_tag(runs, tag, rng) -> dict:
    data = load_waveforms(runs, ["B2", "B6", "B8"])
    intime, offsets, count = select_in_time_rows(data, list(PAIR), INTIME_TOL)
    rows = evaluate(intime, offsets, rng)
    best = min((r for r in rows if np.isfinite(r["sigma68_ns"])),
               default=None, key=lambda r: r["sigma68_ns"])
    if best:
        log(f"{tag}: B6-B8 pair sigma68={best['sigma68_ns']:.3f} ns; "
            "individual-stave inference not authorized")
    figures, visual = make_figures(intime, rows, offsets, tag)
    return {
        "tag": tag, "runs": runs, "event_key": list(EVENT_KEY_COLUMNS),
        "n_pulses": int(len(data)),
        "pulses_by_stave": {k: int(v) for k, v in data.groupby("stave").size().items()},
        "pulse_shape": pulse_shape(data, ["B2", "B6", "B8"]),
        "per_stave_median_peak_sample": offsets,
        "n_intime_pair_events": count, "intime_tol_samples": INTIME_TOL,
        "evaluation": rows, "best_pair_sigma68": best,
        "single_stave_inference": pair_only_inference_contract(),
        "residual_visualization": visual, "figures": figures,
    }


def report_text(result: dict) -> str:
    best = result["sample_II"].get("best_pair_sigma68")
    headline = "No finite pair result."
    if best:
        headline = (f"B6-B8 pair sigma68 = {best['sigma68_ns']:.3f} ns "
                    f"[{best['method']}, CI {best['ci68_ns'][0]:.3f}-"
                    f"{best['ci68_ns'][1]:.3f} ns].")
    return f"""# Real-Data CFD Timing: Pair-Residual Study

{headline}

**Individual-stave inference is not authorized.** Pair sigma68 / sqrt(2) is not
used because equal variances, zero covariance, and a quadrature law for sigma68
were not demonstrated. Comparisons with CL-002 are contextual only.

Event key: `{list(EVENT_KEY_COLUMNS)}`. Residual plots are median-centered and
contain full-range and core panels with q16/q84 and tail counts.

Policy: `{POLICY}`.

A content-addressed ROOT rerun is required before accepting any pair metric.
"""


def main() -> int:
    start = time.time()
    rng = np.random.default_rng(RNG_SEED)
    result = {
        "schema": "ccb-real-data-cfd-timing/2", "producer_version": VERSION,
        "study": "real_data_cfd_timing", "policy": POLICY,
        "acceptance": {"status": "PAIR_ONLY_PENDING_CONTENT_ADDRESSED_RERUN",
                       "individual_stave_authorized": False},
        "params": {"samples_per_channel": SAMPLES, "n_channels": N_CHANNELS,
                   "baseline_samples": BASELINE, "sample_period_ns": PERIOD_NS,
                   "amplitude_cut_adc": AMP_CUT, "cfd_fractions": FRACTIONS,
                   "intime_tol_samples": INTIME_TOL, "bootstrap_n": BOOTSTRAP_N,
                   "stave_channel_lunarc": STAVE_CHANNEL, "clean_pair": list(PAIR),
                   "event_key": list(EVENT_KEY_COLUMNS), "rng_seed": RNG_SEED},
        "data_dir": str(DATA_DIR), "single_stave_inference": pair_only_inference_contract(),
        "sample_II": run_tag(RUNS_SAMPLE_II, "sample_II", rng),
        "task_runs": run_tag(RUNS_TASK, "task_runs", rng),
        "runtime_sec": round(time.time() - start, 1),
    }
    atomic_text(OUT_DIR / "result.json",
                json.dumps(result, indent=2, allow_nan=False) + "\n")
    atomic_text(OUT_DIR / "REPORT.md", report_text(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
