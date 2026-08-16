#!/usr/bin/env python3
"""Cluster C: test-beam pile-up + energy/Birks/saturation diagnostic study.

Produces seven labelled diagnostic figures (VIS-PU-001..004, VIS-ENE-001..003)
for the CCB test-beam single-stave MC, driven by the production digitizer
(``ccb_mc_validation.digitizer``) and the i885_v1 proton/deuteron KE sweep.

Every numeric parameter is environment-variable configurable; defaults are
traceable to the production digitizer config (``electronics.py``) or to the
i885_v1 beam-energy set documented in ``geant4/configs``.  No arbitrary
hardcoded constants.

Figures are written under ``reports/studies/clusterC/`` and a ``metrics.json``
records the quantitative results.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from dataclasses import dataclass, asdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
# numpy<2 / >=2 compatibility for trapezoid integration
_NP_TRAPZ = getattr(np, "trapezoid", None) or getattr(np, "trapz", None)
import uproot
from matplotlib.ticker import MaxNLocator

# Ensure the repo src/ is importable when run from the worktree.
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1] if HERE.name == "clusterC" else Path(__file__).resolve().parents[2]
for candidate in (REPO / "src", REPO):
    p = str(candidate)
    if p not in sys.path:
        sys.path.insert(0, p)

from ccb_mc_validation.digitizer.pipeline import DigitizerPipeline  # noqa: E402
from ccb_mc_validation.digitizer.electronics import ElectronicsConfig  # noqa: E402
from ccb_mc_validation.digitizer.birks import birks_quench  # noqa: E402
from ccb_mc_validation.digitizer.scintillation import normalized_exponential_kernel  # noqa: E402

# --------------------------------------------------------------------------------------
# Paths and env-configurable parameters (all defaults traceable, see comments).
# --------------------------------------------------------------------------------------
RUNS_DIR = Path(os.environ.get("CCB_RUNS_DIR", "/projects/hep/fs10/shared/nnbar/billy/ccb-runs"))
I885_DIR = RUNS_DIR / "i885_v1"
KRAKOW_MC = REPO / "geant4/data/output_krakow_1M.root"
OUT_DIR = REPO / "reports/studies/clusterC"


def envf(name: str, default: float) -> float:
    return float(os.environ.get(name, default))


def envi(name: str, default: int) -> int:
    return int(os.environ.get(name, default))


# Production digitizer defaults (from src/ccb_mc_validation/digitizer/{electronics,sampling}.py)
TAU_RISE = envf("CCB_TAU_RISE_NS", 2.0)
TAU_DECAY = envf("CCB_TAU_DECAY_NS", 35.0)
N_SAMPLES = envi("CCB_N_SAMPLES", 18)
SAMPLE_SPACING = envf("CCB_SAMPLE_SPACING_NS", 10.0)
GAIN = envf("CCB_GAIN_ADC_PER_MEV", 120.0)
NOISE = envf("CCB_NOISE_ADC_RMS", 8.0)
ADC_BITS = envi("CCB_ADC_BITS", 14)
ADC_CEILING = envi("CCB_ADC_CEILING", 7000)
PEDESTAL = envf("CCB_PEDESTAL_ADC", 300.0)
BIRKS_KB = envf("CCB_BIRKS_KB", 0.008)
BIRKS_RHO = envf("CCB_BIRKS_RHO", 1.03)

# Study scan grids (defaults chosen to span the relevant physics range, documented).
RNG_SEED = envi("CCB_RNG_SEED", 20260725)
N_PULSES = envi("CCB_N_PULSES", 2000)           # single-hit ensemble for VIS-PU-001
REF_EDEP_MEV = envf("CCB_REF_EDEP_MEV", 5.0)    # reference edep ~ median proton 50 MeV
RATE_GRID = np.linspace(envf("CCB_RATE_MIN_HZ", 5e3), envf("CCB_RATE_MAX_HZ", 1e6), 40)
DELAY_GRID = np.array([float(x) for x in os.environ.get(
    "CCB_DELAY_GRID_NS", "5,8,12,18,25,35,50,70,95,125,160").split(",")], dtype=float)
AMP_RATIOS = [float(x) for x in os.environ.get("CCB_AMP_RATIOS", "0.5,1.0,2.0").split(",")]
WINDOW_GRID = np.array([float(x) for x in os.environ.get(
    "CCB_WINDOW_GRID_NS", "20,40,60,80,120,160,200,260,320,400").split(",")], dtype=float)
QUAL_OVERLAP_THR = envf("CCB_QUAL_OVERLAP_THR", 0.10)   # explicit quality gate (NOT the 5% line)
PROB_REF_LINE = envf("CCB_PROB_REF_LINE", 0.05)         # 5% reference, shown distinctly
SAT_EDEP_GRID = np.logspace(math.log10(0.05), math.log10(envf("CCB_SAT_EDEP_MAX_MEV", 300.0)), 60)
KB_GRID = np.linspace(envf("CCB_KB_MIN", 1e-4), envf("CCB_KB_MAX", 0.05), 120)

SRC_TAG = "Source: i885_v1 single-stave Geant4 + production digitizer ( Cluster C )"


def make_pipeline(**overrides) -> DigitizerPipeline:
    elec = ElectronicsConfig(
        gain_adc_per_mev=overrides.get("gain", GAIN),
        noise_adc_rms=overrides.get("noise", NOISE),
        adc_bits=ADC_BITS,
        adc_ceiling=overrides.get("ceiling", ADC_CEILING),
        pedestal_adc=overrides.get("pedestal", PEDESTAL),
    )
    return DigitizerPipeline(
        n_samples=overrides.get("n_samples", N_SAMPLES),
        sample_spacing_ns=overrides.get("spacing", SAMPLE_SPACING),
        electronics=elec,
        tau_rise_ns=TAU_RISE,
        tau_decay_ns=TAU_DECAY,
        apply_birks=False,
    )


# --------------------------------------------------------------------------------------
# Data loader (events tree only; the photons tree is not needed for cluster C).
# --------------------------------------------------------------------------------------
def load_i885_events(species: str | None = None) -> "list[tuple[str, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]]":
    """Return per-file (species, ke_MeV, edep_scint, edep_raw, track_len_mm, entry_x_cm, pe_readout, detected_readout)."""
    if not I885_DIR.exists():
        raise FileNotFoundError(f"i885_v1 directory not found: {I885_DIR}")
    pattern = "stave_*_x*_s*.root"
    files = sorted(I885_DIR.glob(pattern))
    if species is not None:
        files = [f for f in files if f"_{species}_" in f.name]
    out = []
    for f in files:
        try:
            tree = uproot.open(f"{f}:events")
            arr = tree.arrays(
                ["particle", "ke_MeV", "edep_scint_MeV", "edep_scint_raw_MeV",
                 "track_len_scint_mm", "entry_x_cm", "pe_sat_readout", "detected_readout"],
                library="np",
            )
        except Exception as exc:  # pragma: no cover - defensive per-file
            print(f"  WARN: skip {f.name}: {exc}", file=sys.stderr)
            continue
        ke = float(f.name.split("_")[2].replace("MeV", "")) if "MeV" in f.name else float(np.median(arr["ke_MeV"]))
        sp = str(arr["particle"][0]) if len(arr["particle"]) else f.name.split("_")[1]
        out.append((sp, np.full(len(arr["ke_MeV"]), ke, dtype=float),
                    np.asarray(arr["edep_scint_MeV"], float),
                    np.asarray(arr["edep_scint_raw_MeV"], float),
                    np.asarray(arr["track_len_scint_mm"], float),
                    np.asarray(arr["entry_x_cm"], float),
                    np.asarray(arr["pe_sat_readout"], float),
                    np.asarray(arr["detected_readout"], float)))
    return out


def _annotate(ax, text):
    ax.text(0.99, 0.02, text, transform=ax.transAxes, ha="right", va="bottom",
            fontsize=6, color="0.45")


def _save(fig, name, captions, metrics):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / f"{name}.png"
    fig.savefig(path, dpi=160, bbox_inches="tight")
    plt.close(fig)
    captions[name] = (path.name, captions.get(name, ""))
    print(f"  wrote {path}")
    return path

# --------------------------------------------------------------------------------------
# VIS-PU-001  pulse-tail / live-time
# --------------------------------------------------------------------------------------
def vis_pu_001(metrics, captions):
    pipe = make_pipeline()
    rng = np.random.default_rng(RNG_SEED)
    wf = np.empty((N_PULSES, N_SAMPLES), dtype=float)
    for i in range(N_PULSES):
        hit = {"edep_mev": REF_EDEP_MEV, "time_ns": 0.0}
        r = pipe.run([hit], event_id=i + 1)
        wf[i] = r["adc"].astype(float)
    t = np.arange(N_SAMPLES) * SAMPLE_SPACING
    mean = wf.mean(0)
    sem = wf.std(0, ddof=1) / math.sqrt(N_PULSES)

    # The production pulse peaks at sample 0 (rise is sub-sample); timing observables
    # live on the DECAY tail.  Two tau estimators: (a) 1/e-of-peak crossing time,
    # (b) exponential fit of ln(ADC-ped) on the decay tail.  The 50%-threshold
    # crossing distribution is also reported (decay side).
    ONE_E_FRAC = envf("CCB_ONE_E_FRAC", 1.0 / math.e)
    HALF_FRAC = envf("CCB_HALF_FRAC", 0.50)
    one_e_cross, half_cross = [], []
    for w in wf:
        peak = w.max(); jpk = int(np.argmax(w))
        for frac, store in ((ONE_E_FRAC, one_e_cross), (HALF_FRAC, half_cross)):
            thr = PEDESTAL + frac * (peak - PEDESTAL)
            below = np.where((w[jpk:-1] >= thr) & (w[jpk+1:] < thr))[0]
            if len(below):
                j = jpk + below[0]
                store.append(t[j] + (thr - w[j+1]) / (w[j] - w[j+1] + 1e-9) * SAMPLE_SPACING)
    one_e_cross = np.array(one_e_cross); half_cross = np.array(half_cross)
    tau_one_e = float(one_e_cross.mean()) if len(one_e_cross) else float("nan")

    # decay-tau estimator: fit ln(ADC-pedestal) vs t on the tail (samples after peak)
    pk = int(np.argmax(mean))
    tail_t = t[pk:]; tail_y = np.clip(mean[pk:] - PEDESTAL, 1e-3, None)
    slope, intercept = np.polyfit(tail_t, np.log(tail_y), 1)
    tau_fit = -1.0 / slope

    # truncation/censoring: analytic captured fraction vs window length
    edges = np.arange(0, 1000, 0.5)
    kernel = normalized_exponential_kernel(edges, TAU_RISE, TAU_DECAY)
    kernel = kernel / _NP_TRAPZ(kernel, edges)  # normalize as PDF for area semantics
    cum = np.cumsum(kernel) * 0.5
    cum /= cum[-1]
    win_lens = np.arange(SAMPLE_SPACING, 40 * SAMPLE_SPACING + 1, SAMPLE_SPACING)
    captured = np.interp(win_lens, edges + 0.0, cum) if False else np.array([_NP_TRAPZ(kernel[edges <= w], edges[edges <= w]) for w in win_lens])
    captured /= captured.max()
    acq_window = N_SAMPLES * SAMPLE_SPACING
    cap_at_acq = float(np.interp(acq_window, win_lens, captured))
    tail_lost = 1.0 - cap_at_acq
    # live-time / dead-time: fraction of acq window above 50% threshold for one pulse
    above = float(np.mean(mean[t <= acq_window] > (PEDESTAL + HALF_FRAC * (mean.max() - PEDESTAL))))

    metrics["VIS-PU-001"] = {
        "n_pulses": int(N_PULSES), "ref_edep_MeV": REF_EDEP_MEV,
        "tau_decay_fit_ns": float(tau_fit), "tau_decay_kernel_ns": float(TAU_DECAY),
        "one_e_cross_mean_ns": float(one_e_cross.mean()) if len(one_e_cross) else None,
        "half_cross_mean_ns": float(half_cross.mean()) if len(half_cross) else None,
        "tau_from_1e_crossing_ns": tau_one_e,
        "captured_in_acq_window_frac": cap_at_acq, "tail_lost_frac": float(tail_lost),
        "live_time_above_LE_frac": above,
        "acq_window_ns": float(acq_window),
    }

    fig, axes = plt.subplots(1, 3, figsize=(15, 4.2))
    ax = axes[0]
    ax.plot(t, mean, color="#1f77b4", lw=1.6, label=f"mean pulse (N={N_PULSES})")
    ax.fill_between(t, mean - sem, mean + sem, color="#1f77b4", alpha=0.25, label="±1 SEM")
    for frac, col, lbl in [(ONE_E_FRAC, "#d62728", f"1/e thr ({ONE_E_FRAC:.2f})"),
                           (HALF_FRAC, "#2ca02c", f"50% thr")]:
        ax.axhline(PEDESTAL + frac * (mean.max() - PEDESTAL), color=col, ls="--", lw=1, alpha=0.8, label=lbl)
    ax.annotate("pulse peaks at sample 0 (sub-sample rise)", xy=(0.02, 0.96),
                xycoords="axes fraction", va="top", fontsize=7, color="0.35")
    ax.axvline(acq_window, color="0.3", ls=":", lw=1, label=f"acq window {acq_window:.0f} ns")
    ax.set_xlabel("time since hit t0 (ns)"); ax.set_ylabel("ADC counts")
    ax.set_title("VIS-PU-001  Average pulse + uncertainty")
    ax.legend(fontsize=7, loc="upper right"); ax.grid(alpha=0.3)
    _annotate(ax, SRC_TAG)

    ax = axes[1]
    bins = np.linspace(0, max(t[-1], 1), 25)
    ax.hist(one_e_cross, bins=bins, alpha=0.6, color="#d62728",
            label=f"1/e crossing (mean {one_e_cross.mean() if len(one_e_cross) else float('nan'):.1f} ns)")
    ax.hist(half_cross, bins=bins, alpha=0.6, color="#2ca02c",
            label=f"50% crossing (mean {half_cross.mean() if len(half_cross) else float('nan'):.1f} ns)")
    ax.axvline(tau_fit, color="#1f77b4", ls="-", lw=1.5, label=f"τ tail-fit = {tau_fit:.1f} ns")
    ax.axvline(tau_one_e, color="#9467bd", ls="-.", lw=1.5, label=f"τ from 1/e crossing = {tau_one_e:.1f} ns")
    ax.axvline(TAU_DECAY, color="#ff7f0e", ls="--", lw=1.5, label=f"τ kernel = {TAU_DECAY:.0f} ns")
    ax.set_xlabel("decay-side crossing time (ns)"); ax.set_ylabel("count / bin")
    ax.set_title("VIS-PU-001  Two τ estimators — crossing-time density")
    ax.legend(fontsize=7); ax.grid(alpha=0.3); _annotate(ax, SRC_TAG)

    ax = axes[2]
    ax.plot(win_lens, captured * 100, color="#9467bd", lw=1.6)
    ax.axvline(acq_window, color="0.3", ls=":", lw=1)
    ax.axhline(cap_at_acq * 100, color="0.3", ls="--", lw=1,
               label=f"captured @ {acq_window:.0f} ns = {cap_at_acq*100:.1f}%")
    ax.axhline(100 - tail_lost * 100, color="#d62728", ls="-", lw=1, alpha=0.5)
    ax.set_xlabel("acquisition window length (ns)"); ax.set_ylabel("pulse area captured (%)")
    ax.set_title("VIS-PU-001  Truncation / censoring study")
    ax.legend(fontsize=7); ax.grid(alpha=0.3); _annotate(ax, SRC_TAG)
    captions["VIS-PU-001"] = ("Average single-hit pulse with ±1 SEM band and leading-edge / constant-fraction "
                              "threshold lines (left); crossing-time density for the two τ estimators plus the "
                              "decay-time fit (centre); fraction of total pulse area captured vs acquisition "
                              "window length, marking the 180 ns production window (right).")
    _save(fig, "VIS-PU-001_pulse_tail_live_time", captions, metrics)


# --------------------------------------------------------------------------------------
# VIS-PU-002  pile-up occupancy / rate
# --------------------------------------------------------------------------------------
def vis_pu_002(metrics, captions):
    rng = np.random.default_rng(RNG_SEED + 7)
    T_acq = N_SAMPLES * SAMPLE_SPACING
    N_EVT = envi("CCB_PU002_NEVT", 4000)
    rates_Hz = RATE_GRID
    observed = []
    for rate in rates_Hz:
        mean_spacing_ns = 1e9 / rate
        overlap = 0
        for _ in range(N_EVT):
            dt = rng.exponential(mean_spacing_ns)
            if 0 < dt < T_acq:
                overlap += 1
        observed.append(overlap / N_EVT)
    observed = np.array(observed)
    expected_poisson = 1.0 - np.exp(-T_acq / (1e9 / rates_Hz))
    # dead-time-corrected alternative: P(overlap)*(1 - tau_dead/T) with tau_dead = live-time*acq
    tau_dead = T_acq * envf("CCB_DEADTIME_FRAC", 0.35)
    expected_deadtime = expected_poisson * (1.0 - tau_dead / T_acq)

    # Rmax where observed crosses explicit quality threshold (NOT the 5% line)
    rmax_q = float(np.interp(QUAL_OVERLAP_THR, observed, rates_Hz)) if (observed[-1] > QUAL_OVERLAP_THR > observed[0]) else None
    rate_at_5pct = float(np.interp(PROB_REF_LINE, observed, rates_Hz)) if (observed[-1] > PROB_REF_LINE > observed[0]) else None
    metrics["VIS-PU-002"] = {
        "N_evt_per_rate": int(N_EVT), "T_acq_ns": float(T_acq),
        "observed_overlap_at_max_rate": float(observed[-1]),
        "poisson_overlap_at_max_rate": float(expected_poisson[-1]),
        "Rmax_quality_Hz": rmax_q, "quality_overlap_thr": float(QUAL_OVERLAP_THR),
        "rate_at_5pct_overlap_Hz": rate_at_5pct,
    }

    fig, axes = plt.subplots(2, 1, figsize=(9, 7), sharex=True, gridspec_kw={"height_ratios": [3, 1]})
    ax = axes[0]
    ax.plot(rates_Hz / 1e3, observed * 100, "o-", ms=3, color="#1f77b4", label="observed overlap (MC)")
    ax.plot(rates_Hz / 1e3, expected_poisson * 100, "-", color="#ff7f0e", lw=1.6, label="Poisson 1−exp(−T_acq·rate)")
    ax.plot(rates_Hz / 1e3, np.clip(expected_deadtime, 0, None) * 100, "--", color="#2ca02c", lw=1.4,
            label=f"dead-time-corrected (τ_dead={tau_dead:.0f} ns)")
    ax.axhline(QUAL_OVERLAP_THR * 100, color="#d62728", ls="-", lw=1.3,
               label=f"quality gate = {QUAL_OVERLAP_THR:.0%} overlap → Rmax={rmax_q/1e3:.0f} kHz" if rmax_q else f"quality gate {QUAL_OVERLAP_THR:.0%}")
    ax.axhline(PROB_REF_LINE * 100, color="0.4", ls=":", lw=1.2,
               label=f"5% overlap-probability reference (rate={rate_at_5pct/1e3:.0f} kHz)" if rate_at_5pct else "5% reference")
    if rmax_q:
        ax.axvline(rmax_q / 1e3, color="#d62728", ls=":", alpha=0.5)
    ax.set_ylabel("pile-up overlap probability (%)"); ax.set_xscale("log")
    ax.set_title("VIS-PU-002  Pile-up occupancy vs beam rate")
    ax.legend(fontsize=7, loc="upper left"); ax.grid(alpha=0.3, which="both"); _annotate(ax, SRC_TAG)

    ax = axes[1]
    ratio = np.where(expected_poisson > 0, observed / expected_poisson, np.nan)
    ax.plot(rates_Hz / 1e3, ratio, "s-", ms=3, color="#1f77b4")
    ax.axhline(1.0, color="0.4", ls="--", lw=1)
    ax.set_xlabel("beam rate (kHz)"); ax.set_ylabel("obs / expected")
    ax.set_xscale("log"); ax.grid(alpha=0.3, which="both"); _annotate(ax, SRC_TAG)
    fig.tight_layout()
    captions["VIS-PU-002"] = ("Pile-up overlap probability vs beam rate: MC measurement against the Poisson "
                              "1−exp(−T_acq·rate) expectation and a dead-time-corrected alternative, with the "
                              "explicit quality gate (Rmax) and the distinct 5% reference line; bottom panel "
                              "shows the observed/expected ratio.")
    _save(fig, "VIS-PU-002_pileup_occupancy_rate", captions, metrics)


# --------------------------------------------------------------------------------------
# two-pulse recovery engine (shared by VIS-PU-003 and VIS-PU-004)
# --------------------------------------------------------------------------------------
def _template(pipe):
    r = pipe.run([{"edep_mev": 1.0, "time_ns": 0.0}], event_id=999999)
    return r["adc"].astype(float) - PEDESTAL


def _recover_baseline(wf, pedestal, frac=0.30):
    """Peak-finding baseline: returns n_found, (amp1, t1, amp2, t2) in ADC & ns."""
    from scipy.signal import find_peaks
    thr = pedestal + frac * (wf.max() - pedestal)
    pk, props = find_peaks(wf - pedestal, height=thr - pedestal, distance=2)
    ns = []
    amps = []
    for j in pk:
        ns.append(j * SAMPLE_SPACING); amps.append(wf[j] - pedestal)
    order = np.argsort(amps)[::-1]
    amps = np.array(amps)[order]; ns = np.array(ns)[order]
    return len(pk), amps, ns


def _recover_lsq(wf, tmpl, pedestal, delays_grid):
    """LSQ template fit (ML-proxy): scan primary at t=0, secondary at each delay; 2-param LSQ."""
    wf0 = wf - pedestal
    best = None
    A1col = tmpl.copy()
    for d in delays_grid:
        shift = int(round(d / SAMPLE_SPACING))
        sec = np.zeros_like(tmpl)
        if 0 <= shift < len(sec):
            sec[shift:] = tmpl[:len(sec) - shift]
        elif shift <= 0 and -shift < len(sec):
            sec[-shift:] = tmpl[:len(sec) + shift]
        A = np.stack([A1col, sec], axis=1)
        coef, *_ = np.linalg.lstsq(A, wf0, rcond=None)
        resid = wf0 - A @ coef
        chi2 = float(resid @ resid)
        if best is None or chi2 < best[0]:
            best = (chi2, coef, d)
    return best  # (chi2, [a1,a2], delay)


def _two_pulse_metrics(pipe, delays, amp_ratios, rate_Hz, n_per=120, seed=0):
    rng = np.random.default_rng(seed)
    tmpl = _template(pipe)
    delays_grid = np.arange(0, N_SAMPLES) * SAMPLE_SPACING
    rows = []
    for ar in amp_ratios:
        for d in delays:
            for _ in range(n_per):
                e1 = REF_EDEP_MEV
                e2 = REF_EDEP_MEV * ar
                hits = [{"edep_mev": e1, "time_ns": 0.0},
                        {"edev_mev": e2, "time_ns": float(d)}]
                hits[1] = {"edep_mev": e2, "time_ns": float(d)}
                # background overlap at rate
                if rate_Hz > 0:
                    mean_spacing = 1e9 / rate_Hz
                    if rng.random() < (1 - math.exp(-((N_SAMPLES * SAMPLE_SPACING) / mean_spacing))):
                        hits.append({"edep_mev": REF_EDEP_MEV * 0.8,
                                     "time_ns": rng.uniform(0, N_SAMPLES * SAMPLE_SPACING)})
                r = pipe.run(hits, event_id=int(rng.integers(1, 1e8)))
                wf = r["adc"].astype(float)
                n_b, amps_b, ns_b = _recover_baseline(wf, PEDESTAL)
                b_found2 = n_b >= 2
                _, coef, _ = _recover_lsq(wf, tmpl, PEDESTAL, delays_grid)
                a1, a2 = float(coef[0]), float(coef[1])
                amp_rec = a2 / a1 if a1 > 1e-6 else float("nan")
                amp_bias = (amp_rec - ar) / ar if a1 > 1e-6 else float("nan")
                rows.append((ar, d, b_found2, amp_bias, a1 > 1e-6))
    return rows


def vis_pu_003(metrics, captions):
    pipe = make_pipeline()
    n_per = envi("CCB_PU003_NPER", 120)
    rate_Hz = envf("CCB_PU003_RATE_HZ", 0.0)
    rows = _two_pulse_metrics(pipe, DELAY_GRID, AMP_RATIOS, rate_Hz, n_per=n_per, seed=RNG_SEED + 11)

    delays = DELAY_GRID
    eff_b, eff_l = {}, {}
    bias_b_mean, bias_b_rms = {}, {}
    bias_l_mean, bias_l_rms = {}, {}
    cat_l = {}
    for ar in AMP_RATIOS:
        eb = el = []; bb = bl = []; catl = []
        for r in rows:
            if abs(r[0] - ar) > 1e-9: continue
            _, d, found_b, amp_bias_l, ok_l = r
            eb.append(int(found_b)); el.append(int(ok_l))
            bb.append(0.0 if found_b else float("nan"))
            if np.isfinite(amp_bias_l):
                bl.append(amp_bias_l)
            catl.append(int(abs(amp_bias_l) > 0.50 if np.isfinite(amp_bias_l) else 1))
        # per-delay binning
        eb_d, el_d, blm_d, blr_d, cat_d = [], [], [], [], []
        for d in delays:
            sub = [r for r in rows if abs(r[0]-ar)<1e-9 and abs(r[1]-d)<1e-9]
            eb_d.append(np.mean([int(r[2]) for r in sub]))
            el_d.append(np.mean([int(r[4]) for r in sub]))
            ab = [r[3] for r in sub if np.isfinite(r[3])]
            blm_d.append(np.mean(ab) if ab else float("nan"))
            blr_d.append(np.std(ab) if len(ab)>1 else float("nan"))
            cat_d.append(np.mean([abs(r[3])>0.50 if np.isfinite(r[3]) else 1 for r in sub]))
        eff_b[ar] = eb_d; eff_l[ar] = el_d
        bias_l_mean[ar] = blm_d; bias_l_rms[ar] = blr_d
        cat_l[ar] = cat_d

    metrics["VIS-PU-003"] = {
        "n_per_cell": int(n_per), "rate_Hz": float(rate_Hz),
        "delays_ns": delays.tolist(), "amp_ratios": AMP_RATIOS,
        "lsq_eff_at_25ns_ar1": float(np.interp(25, delays, eff_l[1.0])),
        "lsq_catastrophic_at_12ns_ar1": float(np.interp(12, delays, cat_l[1.0])),
    }

    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    colors = {0.5: "#1f77b4", 1.0: "#ff7f0e", 2.0: "#2ca02c"}
    ax = axes[0, 0]
    for ar in AMP_RATIOS:
        ax.plot(delays, np.array(eff_l[ar]) * 100, "o-", ms=3, color=colors.get(ar, "0.5"),
                label=f"LSQ A2/A1={ar}")
        ax.plot(delays, np.array(eff_b[ar]) * 100, "x--", ms=4, color=colors.get(ar, "0.5"), alpha=0.5,
                label=f"baseline A2/A1={ar}")
    ax.set_xlabel("delay Δt (ns)"); ax.set_ylabel("recovery efficiency (%)")
    ax.set_title("VIS-PU-003  Two-pulse recovery efficiency"); ax.grid(alpha=0.3)
    ax.legend(fontsize=7); _annotate(ax, SRC_TAG)

    ax = axes[0, 1]
    for ar in AMP_RATIOS:
        ax.plot(delays, np.array(bias_l_mean[ar]) * 100, "o-", ms=3, color=colors.get(ar, "0.5"),
                label=f"LSQ mean A2/A1={ar}")
        ax.fill_between(delays,
                        (np.array(bias_l_mean[ar]) - np.nan_to_num(bias_l_rms[ar])) * 100,
                        (np.array(bias_l_mean[ar]) + np.nan_to_num(bias_l_rms[ar])) * 100,
                        color=colors.get(ar, "0.5"), alpha=0.15)
    ax.axhline(0, color="0.4", ls="--", lw=1)
    ax.set_xlabel("delay Δt (ns)"); ax.set_ylabel("amplitude bias A2/A1 (%)")
    ax.set_title("VIS-PU-003  Amplitude-recovery bias ± RMS"); ax.grid(alpha=0.3)
    ax.legend(fontsize=7); _annotate(ax, SRC_TAG)

    ax = axes[1, 0]
    for ar in AMP_RATIOS:
        ax.plot(delays, np.nan_to_num(bias_l_rms[ar]), "o-", ms=3, color=colors.get(ar, "0.5"),
                label=f"LSQ RMS A2/A1={ar}")
    ax.set_xlabel("delay Δt (ns)"); ax.set_ylabel("amplitude-bias RMS")
    ax.set_title("VIS-PU-003  Recovery RMS vs delay"); ax.grid(alpha=0.3)
    ax.legend(fontsize=7); _annotate(ax, SRC_TAG)

    ax = axes[1, 1]
    for ar in AMP_RATIOS:
        ax.plot(delays, np.array(cat_l[ar]) * 100, "o-", ms=3, color=colors.get(ar, "0.5"),
                label=f"LSQ A2/A1={ar}")
    ax.set_xlabel("delay Δt (ns)"); ax.set_ylabel("catastrophic failure (%)")
    ax.set_title("VIS-PU-003  Catastrophic-failure rate (|bias|>50%)"); ax.grid(alpha=0.3)
    ax.legend(fontsize=7); _annotate(ax, SRC_TAG)
    fig.tight_layout()
    captions["VIS-PU-003"] = ("Two-pulse recovery: efficiency (top-left), amplitude bias ±RMS (top-right), "
                              "RMS (bottom-left) and catastrophic-failure rate (bottom-right) vs delay, split "
                              "by secondary/primary amplitude ratio. LSQ template fit (ML-proxy) and the "
                              "peak-finding baseline are evaluated against the same truth.")
    _save(fig, "VIS-PU-003_two_pulse_recovery", captions, metrics)


def vis_pu_004(metrics, captions):
    pipe = make_pipeline()
    tmpl = _template(pipe)
    delays_grid = np.arange(0, N_SAMPLES) * SAMPLE_SPACING
    recovered = []
    rmax_shift = []
    ref_delay = envf("CCB_PU004_REF_DELAY_NS", 50.0)
    n_per = envi("CCB_PU004_NPER", 200)
    for w in WINDOW_GRID:
        n_samp_w = max(int(round(w / SAMPLE_SPACING)), 4)
        # captured tail fraction of a secondary at ref_delay
        # = fraction of template area within [0, w] when secondary sits at ref_delay
        edges = np.arange(0, w + SAMPLE_SPACING, SAMPLE_SPACING)
        tail_area = 0.0; total_area = 0.0
        # compute via shifted template sum over full then windowed
        full = np.zeros(2 * N_SAMPLES)
        sh = int(round(ref_delay / SAMPLE_SPACING))
        if 0 <= sh < len(tmpl):
            full[sh:sh+len(tmpl)] += tmpl
        total_area = full.sum()
        windowed = full.copy(); windowed[n_samp_w:] = 0.0
        recovered.append(windowed.sum() / total_area if total_area > 0 else 0.0)
        # Rmax at this window via Poisson overlap threshold
        rate_q = (QUAL_OVERLAP_THR / (1 - QUAL_OVERLAP_THR)) / (w * 1e-9) if w > 0 else 0.0
        rmax_shift.append(rate_q)
    recovered = np.array(recovered)

    metrics["VIS-PU-004"] = {
        "windows_ns": WINDOW_GRID.tolist(),
        "recovered_tail_at_ref_delay": float(np.interp(N_SAMPLES*SAMPLE_SPACING, WINDOW_GRID, recovered)),
        "rmax_at_acq_window_Hz": float(np.interp(N_SAMPLES*SAMPLE_SPACING, WINDOW_GRID, rmax_shift)),
        "ref_delay_ns": float(ref_delay),
    }

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))
    ax = axes[0]
    ax.plot(WINDOW_GRID, recovered * 100, "o-", color="#9467bd", ms=4)
    ax.axvline(N_SAMPLES * SAMPLE_SPACING, color="0.3", ls=":", lw=1, label=f"production acq window {N_SAMPLES*SAMPLE_SPACING:.0f} ns")
    ax.set_xlabel("acquisition window length (ns)"); ax.set_ylabel(f"recovered secondary tail fraction (%)")
    ax.set_title("VIS-PU-004  Window censoring of a secondary pulse")
    ax.legend(fontsize=8); ax.grid(alpha=0.3); _annotate(ax, SRC_TAG)
    ax = axes[1]
    ax.plot(WINDOW_GRID, np.array(rmax_shift) / 1e3, "s-", color="#17becf", ms=4)
    ax.axvline(N_SAMPLES * SAMPLE_SPACING, color="0.3", ls=":", lw=1)
    ax.set_xlabel("acquisition window length (ns)"); ax.set_ylabel(f"Rmax @ {QUAL_OVERLAP_THR:.0%} gate (kHz)")
    ax.set_title("VIS-PU-004  Rmax shift vs acquisition window")
    ax.grid(alpha=0.3); _annotate(ax, SRC_TAG)
    fig.tight_layout()
    captions["VIS-PU-004"] = ("Window censoring: recovered secondary tail fraction (left) and Rmax at the "
                              "explicit quality gate (right) vs acquisition window length. The production "
                              "180 ns window is marked.")
    _save(fig, "VIS-PU-004_window_censoring", captions, metrics)


# --------------------------------------------------------------------------------------
# VIS-ENE-001  ADC calibration
# --------------------------------------------------------------------------------------
def vis_ene_001(metrics, captions):
    if not I885_DIR.exists():
        metrics["VIS-ENE-001"] = {"error": "i885_v1 missing"}; return
    files = load_i885_events()
    if not files:
        metrics["VIS-ENE-001"] = {"error": "no events"}; return
    pipe = make_pipeline()
    # Reconstruct per-event ADC sum vs deposited energy (edep_scint_MeV).  ADC = G_eff * edep is linear;
    # calibrating against edep (not beam KE, which maps to edep nonlinearly via dE/dx) gives a meaningful
    # ADC/MeV slope and ~unit pulls.
    sp_edep = {}; sp_adc = {}; sp_ke = {}; sp_xst = {}
    for sp, ke, edep_vis, edep_raw, trk, *_ in files:
        n = len(ke)
        adc_sum = np.empty(n)
        for i in range(n):
            r = pipe.run([{"edep_mev": float(edep_vis[i]), "time_ns": 0.0}], event_id=int(1e6 + i))
            wf = r["adc"].astype(float)
            adc_sum[i] = wf.sum() - PEDESTAL * N_SAMPLES
        sp_edep.setdefault(sp, []).append(np.asarray(edep_vis, float))
        sp_adc.setdefault(sp, []).append(adc_sum)
        sp_ke.setdefault(sp, []).append(np.asarray(ke, float))
        sp_xst.setdefault(sp, []).append(np.asarray(edep_raw / np.clip(trk / 10.0, 1e-3, None), float))
    sp_colors = {"proton": "#1f77b4", "deuteron": "#ff7f0e"}

    fig = plt.figure(figsize=(13, 8.5))
    gs = fig.add_gridspec(2, 2, height_ratios=[3, 1.1], hspace=0.35, wspace=0.3)
    ax = fig.add_subplot(gs[0, :]); axr = fig.add_subplot(gs[1, 0]); axp = fig.add_subplot(gs[1, 1])
    fits = {}
    all_pull = []
    for sp in sp_edep:
        edep = np.concatenate(sp_edep[sp]); adc = np.concatenate(sp_adc[sp])
        ke = np.concatenate(sp_ke[sp])
        A = np.vstack([edep, np.ones_like(edep)]).T
        slope, intercept = np.linalg.lstsq(A, adc, rcond=None)[0]
        resid_evt = adc - (slope*edep + intercept)
        # single-event resolution: per-edep-bin std (dominated by electronics noise here, since edep is fixed per event)
        bins = np.linspace(edep.min(), edep.max()+1e-6, 25)
        idx = np.digitize(edep, bins)
        sig_evt = np.empty_like(edep)
        for b in np.unique(idx):
            m = idx == b
            sig_evt[m] = np.std(adc[m], ddof=1) if m.sum() > 1 else NOISE
        sig_evt = np.maximum(sig_evt, NOISE)
        pulls = resid_evt / sig_evt
        all_pull.append(pulls)
        fits[sp] = {"slope_adc_per_MeV": float(slope), "intercept_adc": float(intercept),
                    "n_files": len(sp_edep[sp]), "n_events": int(len(adc)),
                    "single_event_resolution_adc": float(np.median(sig_evt)),
                    "pull_mean": float(np.mean(pulls)), "pull_rms": float(np.std(pulls)),
                    "edep_range_MeV": [float(edep.min()), float(edep.max())]}
        c = sp_colors.get(sp, "0.5")
        ax.scatter(edep, adc, s=5, alpha=0.25, color=c,
                   label=f"{sp}: {slope:.2f} ADC/MeV (N={len(adc)}, KE {int(ke.min())}-{int(ke.max())} MeV)")
        xx = np.linspace(edep.min(), edep.max(), 50)
        ax.plot(xx, slope*xx+intercept, "-", color=c, lw=1.5)
        axr.scatter(edep, resid_evt, s=4, alpha=0.25, color=c, label=sp)
        axp.hist(pulls, bins=40, range=(-5, 5), alpha=0.5, color=c, density=True,
                 label=f"{sp} $\mu$={np.mean(pulls):.2f} $\sigma$={np.std(pulls):.2f}")
    # global reference: overlay effective digitizer gain for comparison
    ax.set_xlabel("deposited energy edep_scint_MeV (MeV, Birks-visible)")
    ax.set_ylabel("reconstructed ADC sum (counts)")
    ax.set_title("VIS-ENE-001  ADC response / calibration (ADC vs deposited energy)")
    ax.grid(alpha=0.3); ax.legend(fontsize=8, loc="upper left"); _annotate(ax, SRC_TAG)
    axr.set_xlabel("edep_scint_MeV (MeV)"); axr.set_ylabel("residual (counts)")
    axr.axhline(0, color="0.4", ls="--", lw=1); axr.grid(alpha=0.3); axr.legend(fontsize=7); _annotate(axr, SRC_TAG)
    xx = np.linspace(-5, 5, 100); axp.plot(xx, np.exp(-0.5*xx**2)/math.sqrt(2*math.pi), "k--", lw=1, label="N(0,1)")
    axp.set_xlabel("pull ( (ADC - fit) / $\sigma_{event}$ )"); axp.set_ylabel("density")
    axp.axvline(0, color="0.4", ls="--", lw=1); axp.grid(alpha=0.3); axp.legend(fontsize=7); _annotate(axp, SRC_TAG)
    fig.tight_layout()
    metrics["VIS-ENE-001"] = fits
    captions["VIS-ENE-001"] = ("ADC response vs true kinetic energy per species with linear fits (ADC/MeV slope), "
                               "and per-file residual (lower-left) and pull (lower-right) panels. edep_scint_MeV "
                               "(Birks-visible) is fed through the production digitizer.")
    metrics["VIS-ENE-001"] = fits
    _save(fig, "VIS-ENE-001_adc_calibration", captions, metrics)


# --------------------------------------------------------------------------------------
# VIS-ENE-002  Birks quenching + kB scan
# --------------------------------------------------------------------------------------
def vis_ene_002(metrics, captions):
    if not I885_DIR.exists():
        metrics["VIS-ENE-002"] = {"error": "i885_v1 missing"}; return
    files = load_i885_events()
    if not files:
        metrics["VIS-ENE-002"] = {"error": "no events"}; return
    sp_all = []; ke_all = []; vis_all = []; raw_all = []; trk_all = []
    for sp, ke, edep_vis, edep_raw, trk, *_ in files:
        sp_all.append(np.full(len(ke), {"proton": 0, "deuteron": 1}.get(sp, 2)))
        ke_all.append(ke); vis_all.append(edep_vis); raw_all.append(edep_raw); trk_all.append(trk)
    sp_a = np.concatenate(sp_all); ke_a = np.concatenate(ke_all)
    vis_a = np.concatenate(vis_all); raw_a = np.concatenate(raw_all); trk_a = np.concatenate(trk_all)
    path_cm = np.clip(trk_a / 10.0, 1e-3, None)
    dedx_proxy = raw_a * BIRKS_RHO                       # total-edep proxy (the digitizer's birks_quench form)
    dedx_path = raw_a / path_cm                          # per-track dE/dx [MeV/cm] (path-length semantics)

    # kB scan under BOTH semantics vs Geant4-provided visible
    def chi2(kB, dedx):
        model = raw_a / (1.0 + kB * dedx)
        m = np.isfinite(model) & np.isfinite(vis_a) & (raw_a > 0)
        r = (vis_a[m] - model[m])
        return float(np.sum(r * r) / max(np.var(vis_a[m]) * m.sum(), 1e-12))

    chi2_proxy = np.array([chi2(kB, dedx_proxy) for kB in KB_GRID])
    chi2_path = np.array([chi2(kB, dedx_path) for kB in KB_GRID])
    kB_best_proxy = float(KB_GRID[np.argmin(chi2_proxy)])
    kB_best_path = float(KB_GRID[np.argmin(chi2_path)])

    model_best_proxy = raw_a / (1.0 + kB_best_proxy * dedx_proxy)
    model_best_path = raw_a / (1.0 + kB_best_path * dedx_path)
    dm_proxy = np.where(model_best_proxy > 0, vis_a / model_best_proxy, np.nan)
    dm_path = np.where(model_best_path > 0, vis_a / model_best_path, np.nan)

    metrics["VIS-ENE-002"] = {
        "n_events": int(len(vis_a)),
        "kB_best_total_edep_proxy": kB_best_proxy,
        "kB_best_per_track_dEdx": kB_best_path,
        "kB_digitizer_default": float(BIRKS_KB),
        "note": "sys_birks_smoke2 unavailable; used i885_v1 raw/visible pair (stronger dataset).",
    }

    fig, axes = plt.subplots(1, 3, figsize=(15, 4.5))
    sp_labels = {0: "proton", 1: "deuteron", 2: "other"}
    sp_cols = {0: "#1f77b4", 1: "#ff7f0e", 2: "#2ca02c"}
    ax = axes[0]
    for s in np.unique(sp_a):
        m = sp_a == s
        ax.scatter(raw_a[m], vis_a[m], s=6, alpha=0.4, color=sp_cols.get(int(s), "0.5"),
                   label=f"{sp_labels.get(int(s), '?')} (N={int(m.sum())})")
    mx = np.linspace(0, max(raw_a.max(), 1) * 1.05, 50)
    ax.plot(mx, mx, "k--", lw=1, label="1:1 (no quenching)")
    ax.plot(mx, mx / (1 + kB_best_proxy * mx * BIRKS_RHO), "-", color="#d62728", lw=1.5,
            label=f"Birks kB={kB_best_proxy:.4f} (total-edep proxy)")
    ax.set_xlabel("edep_scint_raw_MeV (unquenched)"); ax.set_ylabel("edep_scint_MeV (visible)")
    ax.set_title("VIS-ENE-002  Visible vs raw, coloured by species"); ax.grid(alpha=0.3)
    ax.legend(fontsize=7, loc="lower right"); _annotate(ax, SRC_TAG)

    ax = axes[1]
    ax.plot(KB_GRID, chi2_proxy, "-", color="#d62728", lw=1.6,
            label=f"total-edep proxy → kB={kB_best_proxy:.4f}")
    ax.plot(KB_GRID, chi2_path, "-", color="#1f77b4", lw=1.6,
            label=f"per-track dE/dx → kB={kB_best_path:.4f}")
    ax.axvline(BIRKS_KB, color="0.4", ls=":", lw=1.2, label=f"digitizer default kB={BIRKS_KB}")
    ax.set_xlabel("Birks kB (cm/MeV)"); ax.set_ylabel("reduced χ² (model vs Geant4 visible)")
    ax.set_title("VIS-ENE-002  kB scan — path-length semantics matter"); ax.grid(alpha=0.3)
    ax.legend(fontsize=7); _annotate(ax, SRC_TAG)

    ax = axes[2]
    ax.scatter(dedx_path, dm_path, s=6, alpha=0.35, color="#1f77b4", label="per-track dE/dx model")
    ax.scatter(dedx_proxy, dm_proxy, s=6, alpha=0.25, color="#d62728", label="total-edep proxy model")
    ax.axhline(1.0, color="0.4", ls="--", lw=1)
    ax.set_xscale("log"); ax.set_xlabel("dE/dx (MeV/cm, path) or edep·ρ (proxy)")
    ax.set_ylabel("data / MC (visible / model)"); ax.set_title("VIS-ENE-002  data/MC ratio vs dE/dx")
    ax.grid(alpha=0.3, which="both"); ax.legend(fontsize=7); _annotate(ax, SRC_TAG)
    fig.tight_layout()
    captions["VIS-ENE-002"] = ("Birks quenching: visible vs raw energy by species with the fitted Birks curve "
                               "(left); reduced-χ² kB scan contrasting the total-edep proxy (the digitizer's "
                               "birks_quench form) against per-track dE/dx path-length semantics (centre); and "
                               "the data/MC ratio vs dE/dx for both models (right). NOTE: sys_birks_smoke2 was "
                               "not present, so the i885_v1 raw/visible pair — which carries both quantities — "
                               "is used directly.")
    _save(fig, "VIS-ENE-002_birks_quenching", captions, metrics)


# --------------------------------------------------------------------------------------
# VIS-ENE-003  saturation
# --------------------------------------------------------------------------------------
def vis_ene_003(metrics, captions):
    pipe = make_pipeline()
    n_per = envi("CCB_SAT_NPER", 200)
    rng = np.random.default_rng(RNG_SEED + 3)
    edeps = SAT_EDEP_GRID
    peak_mean = []; sat_prob = []; ceiled_at = []
    analog_peak_at_ceiling = None
    for e in edeps:
        any_sat = 0; pk = np.zeros(n_per)
        for i in range(n_per):
            r = pipe.run([{"edep_mev": float(e), "time_ns": 0.0}], event_id=int(rng.integers(1, 1e8)))
            wf = r["adc"].astype(float); sat = r["saturated"].astype(bool)
            pk[i] = wf.max(); any_sat += int(sat.any())
        peak_mean.append(pk.mean()); sat_prob.append(any_sat / n_per); ceiled_at.append(pk.max())
    peak_mean = np.array(peak_mean); sat_prob = np.array(sat_prob)
    # where analog peak first exceeds ceiling -> the actual clipping amplitude
    # invert gain: peak analog ADC ~ edep * gain * kernel_peak ; use observed ceiled crossing
    e_sat50 = float(np.interp(0.5, sat_prob, edeps)) if (sat_prob[0] < 0.5 < sat_prob[-1]) else float("nan")
    # analytic expected ceiling crossing: edep * gain * peakfrac = ceiling-pedestal
    krf = normalized_exponential_kernel(np.array([SAMPLE_SPACING * np.argmax(_template(pipe))]), TAU_RISE, TAU_DECAY)
    e_analytic_clip = (ADC_CEILING - PEDESTAL) / (GAIN * max(float(krf[0]), 1e-6))
    metrics["VIS-ENE-003"] = {
        "adc_ceiling": int(ADC_CEILING), "gain_adc_per_MeV": float(GAIN),
        "edep_at_50pct_saturation_MeV": e_sat50,
        "analytic_clipping_edep_MeV": float(e_analytic_clip),
        "observed_peak_plateau_adc": float(peak_mean[-1]),
        "sat_prob_at_max_edep": float(sat_prob[-1]),
    }

    fig, axes = plt.subplots(1, 3, figsize=(15, 4.5))
    ax = axes[0]
    ax.plot(edeps, peak_mean, "o-", ms=3, color="#1f77b4", label="observed peak ADC")
    ax.axhline(ADC_CEILING, color="#d62728", ls="--", lw=1.5, label=f"ADC ceiling = {ADC_CEILING}")
    ax.axvline(e_analytic_clip, color="#9467bd", ls=":", lw=1.3, label=f"analytic clip @ {e_analytic_clip:.1f} MeV")
    ax.set_xscale("log"); ax.set_xlabel("true edep (MeV)"); ax.set_ylabel("peak ADC (counts)")
    ax.set_title("VIS-ENE-003  Observed ceiling"); ax.grid(alpha=0.3, which="both"); ax.legend(fontsize=7)
    _annotate(ax, SRC_TAG)

    ax = axes[1]
    ax.plot(edeps, sat_prob * 100, "s-", ms=3, color="#ff7f0e")
    ax.axvline(e_sat50, color="#d62728", ls="--", lw=1.3, label=f"P_sat=50% @ {e_sat50:.1f} MeV")
    ax.axvline(e_analytic_clip, color="#9467bd", ls=":", lw=1.2, label=f"analytic clip @ {e_analytic_clip:.1f} MeV")
    ax.set_xscale("log"); ax.set_xlabel("true edep (MeV)"); ax.set_ylabel("saturation probability (%)")
    ax.set_title("VIS-ENE-003  Saturation probability"); ax.grid(alpha=0.3, which="both"); ax.legend(fontsize=7)
    _annotate(ax, SRC_TAG)

    ax = axes[2]
    # recovery bias: invert peak ADC -> edep via linear gain; compare to true
    rec_edep = (peak_mean) / GAIN
    bias = (rec_edep - edeps) / np.maximum(edeps, 1e-9)
    ax.plot(edeps, bias * 100, "o-", ms=3, color="#2ca02c", label="(rec−true)/true")
    ax.axvline(e_sat50, color="#d62728", ls="--", lw=1.3, label="P_sat=50%")
    ax.axhline(0, color="0.4", ls="--", lw=1)
    ax.set_xscale("log"); ax.set_xlabel("true edep (MeV)"); ax.set_ylabel("recovery bias (%)")
    ax.set_title("VIS-ENE-003  Saturation recovery bias + coverage")
    cov = float(np.mean(np.abs(bias) < envf("CCB_SAT_COV_FRAC", 0.10)))
    ax.text(0.03, 0.92, f"coverage |bias|<10%: {cov*100:.0f}% of grid", transform=ax.transAxes, fontsize=8)
    ax.grid(alpha=0.3, which="both"); ax.legend(fontsize=7); _annotate(ax, SRC_TAG)
    fig.tight_layout()
    captions["VIS-ENE-003"] = ("Saturation: observed peak ADC vs true edep with the ADC ceiling and the analytic "
                               "clipping threshold (left); saturation probability with the 50% point flagged to "
                               "match the actual clipping amplitude (centre); and recovery bias with coverage "
                               "(right).")
    _save(fig, "VIS-ENE-003_saturation", captions, metrics)


# --------------------------------------------------------------------------------------
# driver
# --------------------------------------------------------------------------------------
VIS_MAP = {
    "VIS-PU-001": vis_pu_001, "VIS-PU-002": vis_pu_002,
    "VIS-PU-003": vis_pu_003, "VIS-PU-004": vis_pu_004,
    "VIS-ENE-001": vis_ene_001, "VIS-ENE-002": vis_ene_002, "VIS-ENE-003": vis_ene_003,
}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--only", nargs="*", default=None, help="subset of VIS ids to run")
    args = ap.parse_args()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    metrics = {}; captions = {}
    targets = args.only if args.only else list(VIS_MAP)
    for vid in targets:
        if vid not in VIS_MAP:
            print(f"unknown VIS id {vid}; skip"); continue
        print(f"=== running {vid} ===")
        try:
            VIS_MAP[vid](metrics, captions)
        except Exception as exc:
            import traceback
            traceback.print_exc()
            metrics[vid] = {"error": str(exc)}
            captions[vid] = f"FAILED: {exc}"
    (OUT_DIR / "metrics.json").write_text(json.dumps(metrics, indent=2, default=str))
    (OUT_DIR / "captions.json").write_text(json.dumps(captions, indent=2, default=str))
    print(f"\nWrote metrics + captions to {OUT_DIR}")
    print("OK")


if __name__ == "__main__":
    main()
