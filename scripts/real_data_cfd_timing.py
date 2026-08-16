#!/usr/bin/env python3
"""Pair-only CFD timing study for LUNARC fs10 HRD waveforms.

Event identity is (run,event_id). B6-B8 pair widths are not converted to an
individual-stave resolution without an explicit deconvolution model.

Wave-A contract upgrades (lane05):
- #1004 fail-closed run population in authorising mode
- #1003 report unconditioned + peak-time-conditioned residuals
- #1061 leave-one-run-out templates (no self-inclusion)
- #1060/#1063 canonical digital_cfd with left-censor status
- #1059 first_local_peak amplitude mode for CFD fractions
- #1062 same-sample method minimum labelled exploratory-only
- #954 locked channel polarity before amplitude/timing
"""
from __future__ import annotations

import hashlib
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
import digital_cfd
from ccb_mc_validation.timing.template_phase_grid import (
    default_template_phase_grid,
    template_phase_grid_contract,
)
from ccb_mc_validation.timing.qtemplate_contract import qtemplate_provenance
  # noqa: E402
import s02_timing_pickoff as s02  # noqa: E402
from channel_polarity import apply_polarity, load_polarity_map  # noqa: E402
from real_data_cfd_contract import (  # noqa: E402
    EVENT_KEY_COLUMNS,
    POLICY,
    RunPopulationReport,
    apply_intime_mask,
    assert_run_population_complete,
    pair_only_inference_contract,
    pair_residual_vector,
    peak_offset_dictionary,
    residual_plot_record,
    select_complete_pair_rows,
    select_in_time_rows,
)

VERSION = "3.0.0"
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
AUTHORISING = os.environ.get("CCB_CFD_AUTHORISING", "1").strip() not in {"0", "false", "False"}
CFD_AMPLITUDE_MODE = os.environ.get("CCB_CFD_AMPLITUDE_MODE", "first_local_peak")
POLARITY_PATH = Path(os.environ.get(
    "CCB_CHANNEL_POLARITY_PATH",
    str(HERE.parent / "configs" / "channel_polarity_v2.json"),
))
CALIBRATION_RUNS = [
    int(x) for x in os.environ.get("CCB_CALIBRATION_RUNS", "").split(",") if x.strip()
]


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


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_waveforms(
    runs: list[int],
    staves: list[str],
    *,
    authorising: bool = AUTHORISING,
) -> tuple[pd.DataFrame, RunPopulationReport, dict]:
    """Load HRD waveforms with polarity lock and explicit run-population ledger (#1004, #954)."""
    polarity_map = load_polarity_map(POLARITY_PATH)
    channels = np.asarray([STAVE_CHANNEL[s] for s in staves])
    channel_polarity = np.asarray(
        [polarity_map.polarity_for_channel(int(ch)) for ch in channels],
        dtype=float,
    )

    frames: list[pd.DataFrame] = []
    resolved: list[int] = []
    missing: list[int] = []
    empty: list[int] = []
    failed: list[int] = []
    events_per_run: dict[int, int] = {}
    pulses_per_run: dict[int, int] = {}
    input_hashes: dict[str, str] = {}

    for run in runs:
        path = DATA_DIR / f"hrdb_run_{run:04d}.root"
        if not path.exists():
            log(f"run {run}: missing")
            missing.append(int(run))
            continue
        try:
            input_hashes[str(path)] = _file_sha256(path)
            tree = uproot.open(path)["h101"]
            if tree.num_entries == 0:
                log(f"run {run}: empty")
                empty.append(int(run))
                continue
            run_events = 0
            run_pulses = 0
            for batch in tree.iterate(["EVENTNO", "HRDv"], step_size=20000, library="np"):
                event = np.asarray(batch["EVENTNO"], dtype=np.int64)
                allw = np.stack(batch["HRDv"]).astype(float).reshape(-1, N_CHANNELS, SAMPLES)
                wave = allw[:, channels, :]
                baseline = np.median(wave[:, :, BASELINE], axis=-1)
                corrected = wave - baseline[:, :, None]
                corrected = apply_polarity(corrected, channel_polarity)
                amp = corrected.max(axis=-1)
                peak = corrected.argmax(axis=-1)
                event_i, stave_i = np.where(amp > AMP_CUT)
                run_events += int(len(event))
                if len(event_i) == 0:
                    continue
                run_pulses += int(len(event_i))
                frames.append(pd.DataFrame({
                    "run": run,
                    "event_id": event[event_i],
                    "stave": [staves[i] for i in stave_i],
                    "amplitude_adc": amp[event_i, stave_i],
                    "peak_sample": peak[event_i, stave_i],
                    "waveform": [
                        corrected[i, j].astype(np.float32)
                        for i, j in zip(event_i, stave_i, strict=True)
                    ],
                }))
            if run_events == 0:
                empty.append(int(run))
                continue
            resolved.append(int(run))
            events_per_run[int(run)] = run_events
            pulses_per_run[int(run)] = run_pulses
        except Exception as error:  # noqa: BLE001 — ledger must record failures
            log(f"run {run}: failed ({error})")
            failed.append(int(run))

    report = RunPopulationReport(
        requested_runs=tuple(int(r) for r in runs),
        resolved_runs=tuple(resolved),
        missing_runs=tuple(missing),
        empty_runs=tuple(empty),
        failed_runs=tuple(failed),
        excluded_by_policy=tuple(),
        events_per_run=events_per_run,
        pulses_per_run=pulses_per_run,
        authorising=bool(authorising),
        mode="authorising" if authorising else "exploratory_permissive",
    )
    assert_run_population_complete(report)
    if not frames:
        raise RuntimeError(f"No data for runs {runs}; population={report.to_dict()}")
    polarity_meta = {
        "path": str(POLARITY_PATH),
        "version": polarity_map.version,
        "status": polarity_map.status,
        "applied_channels": {
            stave: {
                "channel": int(STAVE_CHANNEL[stave]),
                "polarity": int(polarity_map.polarity_for_channel(STAVE_CHANNEL[stave])),
            }
            for stave in staves
        },
        "input_sha256": input_hashes,
    }
    return pd.concat(frames, ignore_index=True), report, polarity_meta


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
            "n": int(mask.sum()),
            "amp_median_adc": float(np.median(amp[mask])),
            "samples_above_10pct_median": float(np.median(above)),
            "frac_ge3_above_10pct": float(np.mean(above >= 3)),
        }
    return output


def tof_ns_by_stave() -> dict[str, float]:
    return {
        "B6": 2 * SPACING_CM * TOF_PER_CM_NS,
        "B8": 3 * SPACING_CM * TOF_PER_CM_NS,
    }


def _required_finite(name: str, value: float) -> float:
    number = float(value)
    if not np.isfinite(number):
        raise ValueError(f"{name} must be finite")
    return number


def _optional_finite(value: float) -> float | None:
    number = float(value)
    return number if np.isfinite(number) else None


def pair_result(df, column, offsets, rng) -> dict | None:
    vector = pair_residual_vector(df, column, *PAIR, tof_ns_by_stave(), offsets, PERIOD_NS)
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


def _assign_cfd_columns(df: pd.DataFrame) -> dict[str, dict]:
    wave = np.vstack(df["waveform"].to_numpy())
    amp = df["amplitude_adc"].to_numpy()
    status_summary: dict[str, dict] = {}
    if CFD_AMPLITUDE_MODE == "first_local_peak":
        selector_diag = digital_cfd.first_local_peak_diagnostics(wave)
        statuses = np.asarray(selector_diag["statuses"], dtype=object)
        status_summary["first_local_peak_selector"] = {
            "profile_id": selector_diag["profile_id"],
            "evidence_status": selector_diag["evidence_status"],
            "authorising_component_identity": selector_diag[
                "authorising_component_identity"
            ],
            "global_fraction_floor": selector_diag["global_fraction_floor"],
            "n_fallback_global": int(
                np.count_nonzero(statuses == digital_cfd.SELECT_FALLBACK_GLOBAL)
            ),
            "n_local_selected": int(
                np.count_nonzero(
                    statuses == digital_cfd.SELECT_LOCAL_ABOVE_GLOBAL_FLOOR
                )
            ),
            "n_invalid": int(
                np.count_nonzero(statuses == digital_cfd.SELECT_INVALID)
            ),
        }
    for fraction in FRACTIONS:
        column = f"t_cfd{int(round(fraction * 100)):02d}"
        times, statuses = digital_cfd.cfd_time_samples(
            wave,
            amp,
            fraction,
            amplitude_mode=CFD_AMPLITUDE_MODE,  # type: ignore[arg-type]
            return_status=True,
        )
        df[column] = PERIOD_NS * times
        unique, counts = np.unique(statuses.astype(str), return_counts=True)
        status_summary[column] = {
            "fraction": fraction,
            "amplitude_mode": CFD_AMPLITUDE_MODE,
            "status_counts": {str(k): int(v) for k, v in zip(unique, counts, strict=True)},
            "n_finite": int(np.isfinite(times).sum()),
            "n_left_censored": int(
                np.count_nonzero(statuses == digital_cfd.NO_CROSSING_IN_WINDOW)
            ),
        }
    return status_summary


def _template_phase_loro(df: pd.DataFrame) -> tuple[np.ndarray, dict]:
    """Leave-one-run-out template phase (#1061). No event scores a self-included template."""
    out = np.full(len(df), np.nan, dtype=float)
    runs = sorted(int(r) for r in df["run"].unique())
    grid_contract = template_phase_grid_contract(sample_period_ns=PERIOD_NS)
    meta = {
        "policy": "LEAVE_ONE_RUN_OUT",
        "authorising_for_in_sample_template": False,
        "n_runs": len(runs),
        "grid_samples": grid_contract["grid_step_samples"],
        "grid_note": grid_contract["note"],
        "template_phase_grid": grid_contract,
        "qtemplate": qtemplate_provenance(),
        "per_run": {},
    }
    grid = default_template_phase_grid(grid_contract["grid_step_samples"])
    if len(runs) < 2:
        meta["status"] = "BLOCKED_SINGLE_RUN_CANNOT_LORO"
        return out, meta
    for heldout in runs:
        train = df[df["run"] != heldout]
        test_idx = np.flatnonzero(df["run"].to_numpy() == heldout)
        if len(train) == 0 or len(test_idx) == 0:
            meta["per_run"][str(heldout)] = {"status": "SKIPPED_EMPTY"}
            continue
        templates = s02.build_templates(train, list(PAIR))
        test_df = df.iloc[test_idx].copy()
        phases = s02.template_phase_time(test_df, templates, grid)
        out[test_idx] = phases
        meta["per_run"][str(heldout)] = {
            "status": "OK",
            "n_train_pulses": int(len(train)),
            "n_test_pulses": int(len(test_idx)),
            "template_peak": {
                stave: float(np.max(templates[stave])) for stave in PAIR if stave in templates
            },
        }
    meta["status"] = "OK"
    df["t_template"] = PERIOD_NS * out
    return out, meta


def evaluate(df, offsets, rng) -> tuple[list[dict], dict]:
    cfd_status = _assign_cfd_columns(df)
    rows: list[dict] = []
    for fraction in FRACTIONS:
        column = f"t_cfd{int(round(fraction * 100)):02d}"
        result = pair_result(df, column, offsets, rng)
        if result:
            result.update(
                method=column,
                fraction=fraction,
                conditioning="as_provided_dataframe",
            )
            rows.append(result)
    template_meta: dict = {"status": "SKIPPED"}
    try:
        _, template_meta = _template_phase_loro(df)
        result = pair_result(df, "t_template", offsets, rng)
        if result:
            result.update(
                method="template_loro",
                fraction=None,
                conditioning="as_provided_dataframe",
            )
            rows.append(result)
    except Exception as error:  # noqa: BLE001
        log(f"template skipped: {error}")
        template_meta = {"status": "ERROR", "error": str(error)}
    return rows, {"cfd_status": cfd_status, "template": template_meta}


def residual_payload(df, offsets) -> list[tuple[str, np.ndarray, dict]]:
    requested = [f"t_cfd{int(round(FRACTIONS[0] * 100)):02d}", "t_cfd20"]
    if "t_template" in df.columns:
        requested.append("t_template")
    output = []
    for column in requested:
        if column not in df:
            continue
        vector = pair_residual_vector(df, column, *PAIR, tof_ns_by_stave(), offsets, PERIOD_NS)
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
        aligned = [
            x[int(p) - 4:int(p) + 5] / max(a, 1.0)
            for x, a, p in zip(w, amplitudes, peaks, strict=True)
            if int(p) - 4 >= 0 and int(p) + 5 <= SAMPLES
        ]
        if aligned:
            axes[0].plot(
                np.arange(-4, 5) * PERIOD_NS,
                np.mean(aligned, axis=0),
                marker="o",
                label=f"{stave} (n={len(sub)})",
            )
        mask = df.stave.to_numpy() == stave
        above = (wave[mask] > 0.1 * amp[mask, None]).sum(axis=1)
        axes[1].hist(above, bins=np.arange(-0.5, SAMPLES + 1.5), alpha=0.6, label=stave)
    axes[0].set(
        xlabel="time from peak (ns)",
        ylabel="amplitude / peak",
        title=f"Peak-aligned mean pulse [{tag}]",
    )
    axes[1].set(
        xlabel="samples above 10% of peak",
        ylabel="pulses",
        title="Pulse width (CFD applicability)",
    )
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
        axes[0].hist(
            centered,
            bins=80,
            range=tuple(meta["full_range_ns"]),
            alpha=0.45,
            label=f"{method} (n={meta['n_total']})",
        )
        axes[1].hist(
            centered,
            bins=80,
            range=tuple(meta["core_range_ns"]),
            alpha=0.45,
            label=(
                f"{method}: shown={meta['core_displayed']}, "
                f"under={meta['core_underflow']}, over={meta['core_overflow']}"
            ),
        )
        for axis in axes:
            axis.axvline(meta["q16_centered_ns"], color="k", ls=":", lw=0.8)
            axis.axvline(meta["q84_centered_ns"], color="k", ls=":", lw=0.8)
    axes[0].set_title(f"Median-centered full residual range [{tag}]")
    axes[1].set_title(f"Median-centered core view [{tag}]")
    for axis in axes:
        axis.set(
            xlabel=f"{'-'.join(PAIR)} residual minus median (ns)",
            ylabel="events",
        )
        axis.axvline(0, color="k", lw=0.5)
        axis.grid(alpha=0.3)
        axis.legend(fontsize=8)
    fig.tight_layout()
    path = OUT_DIR / f"residuals_{tag}.png"
    fig.savefig(path, dpi=120)
    plt.close(fig)
    figures.append(str(path))

    cfd = [row for row in rows if row.get("fraction") is not None]
    fig, axis = plt.subplots(figsize=(6, 4))
    if cfd:
        x = [row["fraction"] for row in cfd]
        axis.errorbar(
            x,
            [row["sigma68_ns"] for row in cfd],
            yerr=[
                [row["sigma68_ns"] - row["ci68_ns"][0] for row in cfd],
                [row["ci68_ns"][1] - row["sigma68_ns"] for row in cfd],
            ],
            marker="o",
            label="pair sigma68",
        )
        core = [
            np.nan if row["core_sigma_ns"] is None else row["core_sigma_ns"]
            for row in cfd
        ]
        axis.plot(x, core, marker="s", label="Gaussian core sigma")
        axis.set(
            xlabel="CFD fraction",
            ylabel=f"{'-'.join(PAIR)} pair width (ns)",
            title=f"CFD fraction sensitivity [{tag}]",
        )
        axis.grid(alpha=0.3)
        axis.legend()
    fig.tight_layout()
    path = OUT_DIR / f"sigma_vs_fraction_{tag}.png"
    fig.savefig(path, dpi=120)
    plt.close(fig)
    figures.append(str(path))
    return figures, metadata


def _method_selection_record(rows: list[dict]) -> dict:
    finite = [r for r in rows if np.isfinite(r.get("sigma68_ns", np.nan))]
    best = min(finite, default=None, key=lambda r: r["sigma68_ns"])
    return {
        "policy": "SAME_SAMPLE_MINIMUM_EXPLORATORY_ONLY",
        "authorising": False,
        "audit_issue": 1062,
        "selected_exploratory_minimum": best,
        "n_candidates": len(rows),
        "note": (
            "The minimum sigma68 across CFD fractions/template on the same events "
            "is exploratory only and must not be promoted as detector resolution."
        ),
    }


def run_tag(runs, tag, rng) -> dict:
    data, population, polarity_meta = load_waveforms(runs, ["B2", "B6", "B8"])

    # Timing-independent complete-pair population (#1003)
    complete, n_complete = select_complete_pair_rows(data, list(PAIR))

    if CALIBRATION_RUNS:
        cal = data[data["run"].isin(CALIBRATION_RUNS)]
        if cal.empty:
            raise RuntimeError(f"calibration runs {CALIBRATION_RUNS} produced no pulses")
        offsets = peak_offset_dictionary(complete, list(PAIR), calibration_df=cal)
        offset_source = {"policy": "FROZEN_CALIBRATION_RUNS", "runs": CALIBRATION_RUNS}
    else:
        offsets = peak_offset_dictionary(complete, list(PAIR))
        offset_source = {
            "policy": "SAME_POPULATION_MEDIAN_DIAGNOSTIC",
            "authorising": False,
            "note": "Set CCB_CALIBRATION_RUNS to freeze offsets for held-out evaluation (#1003/#962).",
        }

    uncond_rows, uncond_meta = evaluate(complete.copy(), offsets, rng)
    for row in uncond_rows:
        row["conditioning"] = "complete_pair_amplitude_only"

    intime, n_intime = apply_intime_mask(complete, list(PAIR), offsets, INTIME_TOL)
    # Also keep select_in_time_rows import used for regression compatibility path
    _ = select_in_time_rows
    cond_rows, cond_meta = evaluate(intime.copy(), offsets, rng)
    for row in cond_rows:
        row["conditioning"] = "peak_time_preselected"

    acceptance = {
        "n_complete_pair_events": n_complete,
        "n_peak_time_selected_events": n_intime,
        "acceptance_fraction": (
            float(n_intime) / float(n_complete) if n_complete else float("nan")
        ),
        "intime_tol_samples": INTIME_TOL,
        "label": "peak-time-preselected clean class (not unconditional timing)",
        "audit_issue": 1003,
    }

    figures, visual = make_figures(intime, cond_rows, offsets, tag)
    method_selection = _method_selection_record(cond_rows)

    if method_selection["selected_exploratory_minimum"]:
        best = method_selection["selected_exploratory_minimum"]
        log(
            f"{tag}: exploratory same-sample min pair sigma68="
            f"{best['sigma68_ns']:.3f} ns [{best['method']}]; "
            "not authorising; individual-stave inference not authorized"
        )

    return {
        "tag": tag,
        "runs_requested": list(runs),
        "runs_resolved": list(population.resolved_runs),
        "run_population": population.to_dict(),
        "polarity": polarity_meta,
        "event_key": list(EVENT_KEY_COLUMNS),
        "n_pulses": int(len(data)),
        "pulses_by_stave": {k: int(v) for k, v in data.groupby("stave").size().items()},
        "pulse_shape": pulse_shape(data, ["B2", "B6", "B8"]),
        "per_stave_median_peak_sample": offsets,
        "peak_offset_source": offset_source,
        "selection": acceptance,
        "evaluation_unconditioned": uncond_rows,
        "evaluation_unconditioned_meta": uncond_meta,
        "evaluation": cond_rows,
        "evaluation_conditioned_meta": cond_meta,
        "method_selection": method_selection,
        "best_pair_sigma68": method_selection["selected_exploratory_minimum"],
        "best_pair_sigma68_authorising": False,
        "single_stave_inference": pair_only_inference_contract(),
        "tof_model": {
            "per_stave_ns": tof_ns_by_stave(),
            "proxy": "fixed spacing * TOF_PER_CM_NS",
            "status": "UNVALIDATED_SPECIES_ENERGY_PRIOR",
            "audit_issue": 967,
        },
        "residual_visualization": visual,
        "figures": figures,
    }


def report_text(result: dict) -> str:
    sample = result["sample_II"]
    best = sample.get("best_pair_sigma68")
    sel = sample.get("selection", {})
    headline = "No finite pair result."
    if best:
        headline = (
            f"Exploratory same-sample minimum B6-B8 pair sigma68 = "
            f"{best['sigma68_ns']:.3f} ns [{best['method']}] on the "
            f"peak-time-preselected class "
            f"(acceptance {sel.get('acceptance_fraction', float('nan')):.3f}). "
            "Not an unconditional or authorising detector-resolution claim."
        )
    pop = sample.get("run_population", {})
    return f"""# Real-Data CFD Timing: Pair-Residual Study

{headline}

**Individual-stave inference is not authorized.** Pair sigma68 / sqrt(2) is not
used because equal variances, zero covariance, and a quadrature law for sigma68
were not demonstrated.

Selection (#1003): unconditioned complete-pair and peak-time-conditioned
evaluations are both recorded. Peak-time preselection is an explicit
conditioning class, not an unbiased timing width.

Run population (#1004): authorising mode requires exact requested-run
completeness. Resolved runs: `{pop.get('resolved_runs')}`.

Templates (#1061): leave-one-run-out; no self-included template scoring.

CFD (#1060/#1059/#1063): canonical `digital_cfd` with
`NO_CROSSING_IN_WINDOW` left-censor status and `{CFD_AMPLITUDE_MODE}`
amplitude mode.

Polarity (#954): locked via `{result['params'].get('channel_polarity_path')}`.

Event key: `{list(EVENT_KEY_COLUMNS)}`. Policy: `{POLICY}`.
"""


def main() -> int:
    start = time.time()
    rng = np.random.default_rng(RNG_SEED)
    result = {
        "schema": "ccb-real-data-cfd-timing/3",
        "producer_version": VERSION,
        "study": "real_data_cfd_timing",
        "policy": POLICY,
        "acceptance": {
            "status": "PAIR_ONLY_CONTRACT_V3_SELECTION_AND_LEAKAGE_GUARDS",
            "individual_stave_authorized": False,
            "same_sample_method_minimum_authorized": False,
            "peak_time_preselection_is_conditioning": True,
        },
        "params": {
            "samples_per_channel": SAMPLES,
            "n_channels": N_CHANNELS,
            "baseline_samples": BASELINE,
            "sample_period_ns": PERIOD_NS,
            "amplitude_cut_adc": AMP_CUT,
            "cfd_fractions": FRACTIONS,
            "cfd_amplitude_mode": CFD_AMPLITUDE_MODE,
            "intime_tol_samples": INTIME_TOL,
            "bootstrap_n": BOOTSTRAP_N,
            "stave_channel_lunarc": STAVE_CHANNEL,
            "clean_pair": list(PAIR),
            "event_key": list(EVENT_KEY_COLUMNS),
            "rng_seed": RNG_SEED,
            "authorising": AUTHORISING,
            "channel_polarity_path": str(POLARITY_PATH),
            "calibration_runs": CALIBRATION_RUNS,
        },
        "data_dir": str(DATA_DIR),
        "single_stave_inference": pair_only_inference_contract(),
        "sample_II": run_tag(RUNS_SAMPLE_II, "sample_II", rng),
        "task_runs": run_tag(RUNS_TASK, "task_runs", rng),
        "runtime_sec": round(time.time() - start, 1),
    }
    atomic_text(
        OUT_DIR / "result.json",
        json.dumps(result, indent=2, allow_nan=False) + "\n",
    )
    atomic_text(OUT_DIR / "REPORT.md", report_text(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
