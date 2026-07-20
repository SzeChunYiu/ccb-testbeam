#!/usr/bin/env python3
"""
mv4_timing_study.py
===================
MV4 -- timing-resolution MC study for the CCB test-beam B-stack.

STATUS: TOY_DIAGNOSTIC (was labelled MV4/PRODUCTION).
    This script is a *toy-digitizer diagnostic*, not a production result. It
    stays a diagnostic until it is re-run on LUNARC against the CURRENT v2
    data-driven calibration (mv0 calibration.json) AND real measured data
    anchors (loaded via --data-anchors). The hard-coded gain (246 ADC/MeV) and
    the hard-coded data anchors (1.85 / 1.50 ns, +/-0.10 ns) are LABELLED
    FALLBACKS only; using them prints a WARNING to stderr, and --strict turns
    a missing calibration/anchor file into a hard error (nonzero exit) so a
    "production" run can never silently fall back. See scripts/MV4_TIMING_README.md.

Pipeline (per B-arm charged truth track):
  1. group hits by track; collect (time_ns, EDep, LayerID, PDG)
  2. simulate the N-sample ADC waveform from the calibrated digitizer model
     (gain, noise, pedestal, tau_rise, tau_decay), integrating the unit-peak
     scintillation shape over each sample bin, with a deterministic sub-sample
     phase + noise seeded per track (no global RNG state)
  3. CFD20 pick-off (20% of peak, linear interpolation between samples) -> t_cfd
  4. truth time = earliest hit time of the track (placed at a known window offset)
  5. residual  delta_t = t_cfd - t_truth ; sigma68 = (p84-p16)/2
  6. analytic amplitude timewalk correction  delta_t = A + B/amp (1/A form,
     fixed 2026-07-01 per MV4b), fit on half the tracks, applied to the other
     half; report corrected sigma68
  7. report a battery of metrics (sigma68, RMS, Gaussian-core sigma, tail
     fraction, chi2/ndf) globally and sliced by species / stave / sample / run /
     amplitude / topology, plus a leave-one-run-out (LORO) / per-run spread.

Outputs (--out dir):
  result.json              full machine-readable summary (primary artifact)
  mv4_summary.json         legacy alias of result.json
  mv4_slice_metrics.csv    per-slice metric table
  mv4_waveform_examples.png, mv4_residuals.png, mv4_sigma_vs_amp.png,
  mv4_data_vs_mc.png, mv4_pull.png
  REPORT.md

Runs OFFLINE with --synthetic N (built-in toy truth generator; no ROOT / uproot).
For real input pass --mc <root> and (for a production-grade run)
--calibration <mv0 calibration.json> --data-anchors <anchors.json> --strict.
"""
import argparse
import csv
import json
import os
import sys
from datetime import datetime, timezone
from functools import lru_cache

import numpy as np

try:
    from scipy.optimize import curve_fit
except Exception:  # pragma: no cover - scipy is a hard dep, guard for import clarity
    curve_fit = None

B_ARM = 1
PROTON, DEUTERON = 2212, 1000010020
LAYER_TO_STAVE = {0: "B2", 1: "B2", 2: "B4", 3: "B4", 4: "B6", 5: "B6", 6: "B8", 7: "B8"}

# ---------------------------------------------------------------------------
# LABELLED FALLBACKS -- NOT production values.
# Fallback #1: digitizer gain. Production MUST load the current v2 calibration
#              from an mv0 calibration.json via --calibration and propagate its
#              uncertainty. 246 is a placeholder that WARNS when used.
DEFAULT_GAIN_ADC_PER_MEV = 246.0
# Fallback #2: data anchors + their uncertainty. Production MUST load the exact
#              measured result files + CIs via --data-anchors. These WARN when used.
FALLBACK_DATA_ANCHORS = {
    "source": "fallback",
    "S02_raw_sigma68_ns": 1.85,
    "S03_corrected_sigma68_ns": 1.50,
    "raw_unc_ns": 0.10,
    "corrected_unc_ns": 0.10,
    "raw_ci68_ns": None,
    "corrected_ci68_ns": None,
    "note": "HARD-CODED FALLBACK anchors (S02/S03 assumption); not measured. "
            "Load real anchors with --data-anchors.",
}
# ---------------------------------------------------------------------------

DEFAULTS = dict(gain_adc_per_mev=DEFAULT_GAIN_ADC_PER_MEV, noise_adc_rms=50.0,
                pedestal_adc=350.0, tau_rise_ns=2.5, tau_decay_ns=42.0,
                n_samples=18, sample_spacing_ns=10.0, adc_ceiling=7000.0)
PRE_OFFSET_NS = 40.0   # window offset where the earliest hit is placed
N_SUBPOINTS = 5        # sub-bin integration points
MIN_SLICE_N = 20       # minimum tracks in a slice to report metrics
SLICE_DIMS = ("species", "stave", "sample", "run", "amplitude", "topology")


def _warn(msg):
    print(f"[mv4] WARNING: {msg}", file=sys.stderr)


@lru_cache(maxsize=None)
def charge(pdg):
    pdg = int(pdg); a = abs(pdg)
    if a > 1_000_000_000:
        return (a // 10_000) % 1000
    return {2212: 1, 2112: 0, 22: 0, 11: 1, 13: 1, 211: 1, 321: 1}.get(a, 0)


def species_label(pdg):
    p = int(pdg)
    if p == PROTON:
        return "proton"
    if p == DEUTERON:
        return "deuteron"
    return f"pdg_{p}"


# ===========================================================================
# Metrics -- pure functions on a 1-D array of residuals (ns).
# ===========================================================================
def sigma68(x):
    """Robust 68% half-width: (p84 - p16) / 2."""
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    if x.size < 5:
        return float("nan")
    lo, hi = np.percentile(x, [16, 84])
    return float((hi - lo) / 2.0)


def rms(x):
    """Full RMS spread = standard deviation about the mean (non-robust)."""
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    if x.size < 2:
        return float("nan")
    return float(np.sqrt(np.mean((x - np.mean(x)) ** 2)))


def _gauss(x, amp, mu, sig):
    return amp * np.exp(-0.5 * ((x - mu) / sig) ** 2)


def gaussian_core_sigma(x, n_clip=3.0, iters=3, nbins=60):
    """Sigma of a Gaussian fitted to the sigma-clipped core of the histogram.

    Iteratively restricts to |x - mu| < n_clip*sigma and least-squares fits a
    Gaussian to the binned core, returning the fitted sigma. Falls back to the
    core standard deviation if the fit cannot converge.
    """
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    if x.size < 20:
        return float("nan")
    mu = float(np.median(x))
    sig = sigma68(x)
    if not np.isfinite(sig) or sig <= 0:
        sig = float(np.std(x)) or 1.0
    for _ in range(iters):
        lo, hi = mu - n_clip * sig, mu + n_clip * sig
        core = x[(x >= lo) & (x <= hi)]
        if core.size < 10:
            break
        counts, edges = np.histogram(core, bins=nbins)
        centers = 0.5 * (edges[:-1] + edges[1:])
        if curve_fit is not None and counts.max() > 0:
            try:
                popt, _ = curve_fit(_gauss, centers, counts,
                                    p0=[float(counts.max()), mu, sig], maxfev=10000)
                mu, sig = float(popt[1]), abs(float(popt[2]))
                continue
            except Exception:
                pass
        mu, sig = float(np.mean(core)), float(np.std(core))
    return float(abs(sig))


def tail_fraction(x, n_sigma=3.0):
    """Fraction of entries beyond n_sigma robust widths of the median."""
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    if x.size < 5:
        return float("nan")
    mu = float(np.median(x))
    s = sigma68(x)
    if not np.isfinite(s) or s <= 0:
        s = float(np.std(x))
    if s <= 0:
        return 0.0
    return float(np.mean(np.abs(x - mu) > n_sigma * s))


def chi2_ndf(x, nbins=40, core_clip=4.0):
    """chi2, ndf, chi2/ndf of a Gaussian fit to the core histogram (Poisson).

    Returns (chi2, ndf, chi2_over_ndf). ndf = (bins with content) - 3 fit params.
    """
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    if x.size < 30 or curve_fit is None:
        return float("nan"), 0, float("nan")
    mu = float(np.median(x))
    sig = sigma68(x)
    if not np.isfinite(sig) or sig <= 0:
        sig = float(np.std(x)) or 1.0
    lo, hi = mu - core_clip * sig, mu + core_clip * sig
    xc = x[(x >= lo) & (x <= hi)]
    if xc.size < 30:
        return float("nan"), 0, float("nan")
    counts, edges = np.histogram(xc, bins=nbins, range=(lo, hi))
    centers = 0.5 * (edges[:-1] + edges[1:])
    try:
        popt, _ = curve_fit(_gauss, centers, counts,
                            p0=[float(counts.max()), mu, abs(sig)], maxfev=10000)
    except Exception:
        return float("nan"), 0, float("nan")
    exp = _gauss(centers, *popt)
    mask = counts >= 1
    obs = counts[mask].astype(float)
    ex = np.clip(exp[mask], 1e-9, None)
    chi2 = float(np.sum((obs - ex) ** 2 / ex))
    ndf = int(mask.sum() - 3)
    cn = chi2 / ndf if ndf > 0 else float("nan")
    return chi2, ndf, cn


def metric_row(x, tail_nsigma=3.0):
    """All metrics for one residual array, as a flat dict."""
    x = np.asarray(x, dtype=float)
    c2, ndf, cn = chi2_ndf(x)
    return {
        "n": int(np.isfinite(x).sum()),
        "sigma68_ns": sigma68(x),
        "rms_ns": rms(x),
        "core_sigma_ns": gaussian_core_sigma(x),
        "tail_frac": tail_fraction(x, n_sigma=tail_nsigma),
        "chi2": c2, "ndf": ndf, "chi2_ndf": cn,
    }


def boot_sigma68(x, n_boot=200, seed=12345):
    """Plain (i.i.d.) bootstrap standard error of sigma68."""
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    if x.size < 20:
        return float("nan")
    rng = np.random.default_rng(seed)
    vals = [sigma68(rng.choice(x, size=x.size, replace=True)) for _ in range(n_boot)]
    return float(np.nanstd(vals))


def boot_sigma68_blocks(x, blocks, n_boot=200, seed=12345):
    """Block/run-level bootstrap: resample whole runs with replacement.

    Respects run structure -- correlated within-run residuals are not broken up
    by the resample, giving an honest (usually larger) standard error.
    """
    x = np.asarray(x, dtype=float)
    blocks = np.asarray(blocks)
    m = np.isfinite(x)
    x, blocks = x[m], blocks[m]
    uniq = np.unique(blocks)
    if uniq.size < 2 or x.size < 20:
        return float("nan")
    idx_by = {b: np.where(blocks == b)[0] for b in uniq}
    rng = np.random.default_rng(seed)
    vals = []
    for _ in range(n_boot):
        chosen = rng.choice(uniq, size=uniq.size, replace=True)
        take = np.concatenate([idx_by[b] for b in chosen])
        vals.append(sigma68(x[take]))
    return float(np.nanstd(vals))


def loro_spread(x, runs, metric=sigma68):
    """Leave-one-run-out + per-run spread of a metric."""
    x = np.asarray(x, dtype=float)
    runs = np.asarray(runs)
    uniq = np.unique(runs)
    if uniq.size < 2:
        return None
    per_run, loo = [], []
    for r in uniq:
        mask = runs == r
        per_run.append({"run": str(r), "n": int(mask.sum()),
                        "sigma68_ns": metric(x[mask])})
        loo.append(metric(x[~mask]))
    loo = np.asarray(loo, dtype=float)
    per_vals = np.asarray([p["sigma68_ns"] for p in per_run], dtype=float)
    return {
        "n_runs": int(uniq.size),
        "metric_full_ns": float(metric(x)),
        "leave_one_run_out": {
            "values_ns": [float(v) for v in loo],
            "mean_ns": float(np.nanmean(loo)),
            "std_ns": float(np.nanstd(loo)),
            "min_ns": float(np.nanmin(loo)),
            "max_ns": float(np.nanmax(loo)),
        },
        "per_run": per_run,
        "per_run_spread_std_ns": float(np.nanstd(per_vals)),
    }


# ===========================================================================
# Digitizer (toy) -- unchanged physics: unit-peak scintillation shape + CFD20.
# ===========================================================================
class Digitizer:
    def __init__(self, p):
        self.gain = p["gain_adc_per_mev"]
        self.noise = p["noise_adc_rms"]
        self.ped = p["pedestal_adc"]
        self.tr = p["tau_rise_ns"]
        self.td = p["tau_decay_ns"]
        self.ns = int(p["n_samples"])
        self.dt = p["sample_spacing_ns"]
        self.ceiling = p["adc_ceiling"]
        t_peak = (self.tr * self.td / (self.td - self.tr)) * np.log(self.td / self.tr)
        self.norm = np.exp(-t_peak / self.td) - np.exp(-t_peak / self.tr)
        self.centers = np.arange(self.ns) * self.dt
        self.suboff = np.linspace(-self.dt / 2, self.dt / 2, N_SUBPOINTS)
        self.subgrid = self.centers[:, None] + self.suboff[None, :]

    def _unit_shape(self, t):
        out = np.zeros_like(t)
        m = t > 0
        out[m] = (np.exp(-t[m] / self.td) - np.exp(-t[m] / self.tr)) / self.norm
        return out

    def waveform(self, hit_times, hit_amps, rng):
        wf = np.full(self.ns, self.ped, dtype=float)
        for a, amp in zip(hit_times, hit_amps):
            contrib = self._unit_shape(self.subgrid - a).mean(axis=1)
            wf += amp * contrib
        wf += rng.normal(0.0, self.noise, self.ns)
        np.clip(wf, None, self.ceiling, out=wf)
        return wf

    def cfd20(self, wf):
        w = wf - self.ped
        peak = float(w.max())
        if peak <= 0:
            return float("nan"), peak
        thr = 0.20 * peak
        above = np.where(w >= thr)[0]
        if above.size == 0:
            return float("nan"), peak
        j = int(above[0])
        if j == 0:
            return float(self.centers[0]), peak
        w0, w1 = w[j - 1], w[j]
        if w1 == w0:
            return float(self.centers[j]), peak
        frac = (thr - w0) / (w1 - w0)
        t_cfd = self.centers[j - 1] + frac * self.dt
        return float(t_cfd), peak


# ===========================================================================
# Calibration + data-anchor loaders (LABELLED FALLBACKS, --strict aware).
# ===========================================================================
def load_digitizer_params(calib_path, strict=False):
    """Return (params dict, calib_meta dict).

    calib_meta.source is "loaded" (file read) or "fallback" (246 default).
    --strict makes a missing/absent calibration file a hard error (nonzero exit).
    Propagates the calibration gain uncertainty when the file provides it.
    """
    p = dict(DEFAULTS)
    meta = {"source": "fallback", "path": None,
            "gain_adc_per_mev": p["gain_adc_per_mev"],
            "gain_adc_per_mev_unc": None, "gain_rel_unc": None,
            "pedestal_note": "digitizer default kept (data DAQ baseline is not a "
                             "toy DC level)"}
    if calib_path and os.path.exists(calib_path):
        with open(calib_path) as fh:
            cj = json.load(fh)
        c = cj.get("calibration", cj)
        if not c.get("gain_adc_per_mev"):
            msg = f"calibration file {calib_path} has no calibration.gain_adc_per_mev"
            if strict:
                print(f"[mv4] STRICT ERROR: {msg}", file=sys.stderr)
                raise SystemExit(3)
            _warn(msg + "; using FALLBACK gain 246 ADC/MeV")
            return p, meta
        p["gain_adc_per_mev"] = float(c["gain_adc_per_mev"])
        gunc = c.get("gain_adc_per_mev_unc")
        if gunc is None:
            # derive a coarse uncertainty from the gain scan grid spacing if present
            scan = cj.get("gain_scan_fine") or cj.get("gain_scan_grid") or cj.get("gain_scan")
            try:
                gs = sorted(float(s["gain"]) for s in scan) if scan else None
                if gs and len(gs) > 1:
                    gunc = float(np.median(np.diff(gs)))
            except Exception:
                gunc = None
        meta.update(source="loaded", path=os.path.abspath(calib_path),
                    gain_adc_per_mev=p["gain_adc_per_mev"],
                    gain_adc_per_mev_unc=(float(gunc) if gunc is not None else None),
                    gain_rel_unc=(float(gunc) / p["gain_adc_per_mev"]
                                  if gunc else None))
        print(f"[mv4] loaded calibration: gain={p['gain_adc_per_mev']:.1f} ADC/MeV"
              f" (unc={meta['gain_adc_per_mev_unc']})")
        return p, meta
    # no file
    msg = ("no calibration file (--calibration) provided/found; production runs "
           "MUST load the current v2 mv0 calibration.json")
    if strict:
        print(f"[mv4] STRICT ERROR: {msg}", file=sys.stderr)
        raise SystemExit(3)
    _warn(msg + f"; using FALLBACK gain {DEFAULT_GAIN_ADC_PER_MEV} ADC/MeV")
    return p, meta


def load_data_anchors(anchors_path, strict=False):
    """Return an anchors dict (source='loaded'|<path> or 'fallback')."""
    if anchors_path and os.path.exists(anchors_path):
        with open(anchors_path) as fh:
            aj = json.load(fh)

        def _pick(node, *keys):
            for k in keys:
                if isinstance(node, dict) and k in node and node[k] is not None:
                    return node[k]
            return None

        raw_node = aj.get("S02_raw", aj.get("raw", aj))
        cor_node = aj.get("S03_corrected", aj.get("corrected", aj))
        raw = _pick(raw_node, "sigma68_ns", "sigma68", "value")
        cor = _pick(cor_node, "sigma68_ns", "sigma68", "value")
        if raw is None or cor is None:
            msg = f"anchors file {anchors_path} missing raw/corrected sigma68"
            if strict:
                print(f"[mv4] STRICT ERROR: {msg}", file=sys.stderr)
                raise SystemExit(4)
            _warn(msg + "; using FALLBACK anchors")
            return dict(FALLBACK_DATA_ANCHORS)
        out = {
            "source": os.path.abspath(anchors_path),
            "S02_raw_sigma68_ns": float(raw),
            "S03_corrected_sigma68_ns": float(cor),
            "raw_unc_ns": float(_pick(raw_node, "unc_ns", "unc", "sigma") or 0.0) or None,
            "corrected_unc_ns": float(_pick(cor_node, "unc_ns", "unc", "sigma") or 0.0) or None,
            "raw_ci68_ns": _pick(raw_node, "ci68", "ci68_ns"),
            "corrected_ci68_ns": _pick(cor_node, "ci68", "ci68_ns"),
            "note": "loaded from --data-anchors",
        }
        print(f"[mv4] loaded data anchors from {out['source']}: "
              f"raw={out['S02_raw_sigma68_ns']} corr={out['S03_corrected_sigma68_ns']}")
        return out
    msg = ("no data-anchors file (--data-anchors) provided/found; production runs "
           "MUST load the exact measured result files + CIs")
    if strict:
        print(f"[mv4] STRICT ERROR: {msg}", file=sys.stderr)
        raise SystemExit(4)
    _warn(msg + "; using HARD-CODED FALLBACK anchors (1.85/1.50 ns, +/-0.10)")
    return dict(FALLBACK_DATA_ANCHORS)


# ===========================================================================
# Truth-record construction (ROOT or synthetic) + digitization.
# ===========================================================================
def make_synthetic_records(n, seed):
    """Deterministic toy truth tracks; no ROOT needed. Same seed -> same records."""
    rng = np.random.default_rng(seed)
    runs = [f"run{r}" for r in range(5)]
    staves = ["B2", "B4", "B6", "B8"]
    samples = ["I", "II"]
    recs = []
    for _ in range(int(n)):
        pdg = PROTON if rng.random() < 0.7 else DEUTERON
        nh = 1 if rng.random() < 0.6 else int(rng.integers(2, 4))
        if nh > 1:
            dts = np.sort(np.concatenate(([0.0], rng.uniform(0.5, 6.0, nh - 1))))
        else:
            dts = np.array([0.0])
        base = 2.5 if pdg == PROTON else 4.0
        edeps = np.clip(rng.lognormal(mean=np.log(base), sigma=0.4, size=nh), 0.3, None)
        recs.append({
            "pdg": int(pdg),
            "run": runs[int(rng.integers(0, len(runs)))],
            "stave": staves[int(rng.integers(0, len(staves)))],
            "sample": samples[int(rng.integers(0, len(samples)))],
            "hit_times": dts.astype(float),   # relative to earliest hit (0)
            "edeps": edeps.astype(float),
            "seed": int(rng.integers(1, 2 ** 31 - 1)),
        })
    return recs


def read_root_records(mc_path, tree_name, max_tracks, max_events):
    """Build truth records from a ROOT file (uproot imported lazily)."""
    import uproot
    br = ["Sci_bar_TrackID", "Sci_bar_LayerID1", "Sci_bar_PDG", "Sci_bar_EDep", "Sci_bar_Time"]
    recs = []
    tree = uproot.open(mc_path)[tree_name]
    stop = max_events if max_events and max_events > 0 else None
    ev_global = 0
    done = False
    for ch in tree.iterate(br, step_size="200 MB", library="np", entry_stop=stop):
        TID = ch["Sci_bar_TrackID"]; L1 = ch["Sci_bar_LayerID1"]
        PD = ch["Sci_bar_PDG"]; ED = ch["Sci_bar_EDep"]; TM = ch["Sci_bar_Time"]
        for i in range(len(L1)):
            eid = ev_global; ev_global += 1
            l1 = L1[i]
            if len(l1) == 0:
                continue
            isB = l1 == B_ARM
            if not isB.any():
                continue
            tid = TID[i]; pd = PD[i]; ed = ED[i]; tm = TM[i]
            for tr in np.unique(tid[isB]):
                m = isB & (tid == tr)
                p0 = int(pd[m][0])
                if charge(p0) < 1:
                    continue
                times = tm[m].astype(float)
                edeps = ed[m].astype(float)
                if edeps.sum() <= 0 or not np.isfinite(times).all():
                    continue
                t0 = float(times.min())
                # stave from the first B-arm layer of this track (LayerID1 == B_ARM
                # only tells us B-arm; LayerID granular stave map is diagnostic here)
                recs.append({
                    "pdg": p0,
                    "run": os.path.basename(mc_path),
                    "stave": LAYER_TO_STAVE.get(int(np.atleast_1d(l1[isB & (tid == tr)])[0]), "Bx"),
                    "sample": "all",
                    "hit_times": (times - t0).astype(float),
                    "edeps": edeps.astype(float),
                    "seed": eid * 100003 + (int(tr) & 0xFFFF),
                })
                if len(recs) >= max_tracks:
                    done = True
                    break
            if done:
                break
        if done:
            break
    return recs, ev_global


def digitize(records, dig, capture_examples=True):
    """Run every truth record through the digitizer + CFD20.

    Returns dict of aligned arrays and an examples dict for the waveform plot.
    """
    residual, amp_adc = [], []
    pdg_a, run_a, stave_a, sample_a, nhit_a = [], [], [], [], []
    examples = {}
    for rec in records:
        rng = np.random.default_rng(int(rec["seed"]))
        phase = float(rng.uniform(0.0, dig.dt))
        t_truth = PRE_OFFSET_NS + phase
        arr = np.asarray(rec["hit_times"], dtype=float) + t_truth
        amps = np.asarray(rec["edeps"], dtype=float) * dig.gain
        wf = dig.waveform(arr, amps, rng)
        t_cfd, peak = dig.cfd20(wf)
        if not np.isfinite(t_cfd) or peak < 5 * dig.noise:
            continue
        residual.append(t_cfd - t_truth)
        amp_adc.append(peak)
        pdg_a.append(int(rec["pdg"]))
        run_a.append(str(rec["run"]))
        stave_a.append(str(rec["stave"]))
        sample_a.append(str(rec["sample"]))
        nhit_a.append(int(np.asarray(rec["hit_times"]).size))
        if (capture_examples and rec["pdg"] in (PROTON, DEUTERON)
                and rec["pdg"] not in examples and peak > 8 * dig.noise):
            examples[rec["pdg"]] = (dig.centers.copy(), wf.copy(), t_cfd, t_truth, peak)
    return {
        "residual": np.asarray(residual, dtype=float),
        "amp_adc": np.asarray(amp_adc, dtype=float),
        "pdg": np.asarray(pdg_a, dtype=int),
        "run": np.asarray(run_a, dtype=object),
        "stave": np.asarray(stave_a, dtype=object),
        "sample": np.asarray(sample_a, dtype=object),
        "n_hits": np.asarray(nhit_a, dtype=int),
        "examples": examples,
    }


def fit_timewalk(residual, amp_adc):
    """Analytic 1/A timewalk: median-per-amp-bin fit on the even-index half.

    Returns (A, B, corrected, fit_mask, app_mask). Preserves the MV4b-fixed 1/A
    functional form (dt = A + B/amp), fit on even-index tracks and applied to all.
    """
    x = 1.0 / np.clip(amp_adc, 1.0, None)
    n = residual.size
    fit_mask = np.arange(n) % 2 == 0
    app_mask = ~fit_mask
    af, rf = amp_adc[fit_mask], residual[fit_mask]
    edges = np.unique(np.percentile(af, np.linspace(0, 100, 11))) if af.size else np.array([])
    bx, by = [], []
    for a, b in zip(edges[:-1], edges[1:]):
        mb = (af >= a) & (af < b)
        if mb.sum() >= 30:
            bx.append(float(np.median(1.0 / np.clip(af[mb], 1.0, None))))
            by.append(float(np.median(rf[mb])))
    if len(bx) >= 2:
        B, A = np.polyfit(np.asarray(bx), np.asarray(by), 1)  # median_res = B*x + A
    else:
        B, A = 0.0, float(np.median(rf)) if rf.size else 0.0
    corrected = residual - (A + B * x)
    return float(A), float(B), corrected, fit_mask, app_mask


# ===========================================================================
# Slicing.
# ===========================================================================
def _amp_bin_labels(amp_adc, nq=4):
    """Quantile amplitude-bin label per track (string)."""
    amp_adc = np.asarray(amp_adc, dtype=float)
    if amp_adc.size == 0:
        return np.array([], dtype=object)
    qs = np.unique(np.percentile(amp_adc, np.linspace(0, 100, nq + 1)))
    if qs.size < 2:
        return np.array(["amp_all"] * amp_adc.size, dtype=object)
    idx = np.clip(np.digitize(amp_adc, qs[1:-1], right=False), 0, qs.size - 2)
    return np.array([f"amp_q{k + 1}" for k in idx], dtype=object)


def build_slice_columns(data):
    """Return dict of per-track slice-label arrays for each SLICE_DIM."""
    n = data["residual"].size
    cols = {
        "species": np.array([species_label(p) for p in data["pdg"]], dtype=object),
        "stave": data["stave"],
        "sample": data["sample"],
        "run": data["run"],
        "amplitude": _amp_bin_labels(data["amp_adc"]),
        "topology": np.array(["single" if h == 1 else "multi" for h in data["n_hits"]],
                             dtype=object),
    }
    assert all(v.size == n for v in cols.values())
    return cols


def build_slices(residual, corrected, cols, dims, tail_nsigma=3.0):
    """Per-slice metric tables. Returns (nested dict, flat CSV rows)."""
    out, rows = {}, []
    for dim in dims:
        labels = cols.get(dim)
        if labels is None:
            continue
        groups = []
        for val in sorted(set(map(str, labels))):
            mask = np.array([str(v) == val for v in labels])
            if mask.sum() < MIN_SLICE_N:
                continue
            rm = metric_row(residual[mask], tail_nsigma)
            cm = metric_row(corrected[mask], tail_nsigma)
            row = {
                "slice_dim": dim, "slice_value": val, "n": int(mask.sum()),
                "raw_sigma68_ns": rm["sigma68_ns"], "corr_sigma68_ns": cm["sigma68_ns"],
                "raw_rms_ns": rm["rms_ns"], "corr_rms_ns": cm["rms_ns"],
                "raw_core_sigma_ns": rm["core_sigma_ns"], "corr_core_sigma_ns": cm["core_sigma_ns"],
                "raw_tail_frac": rm["tail_frac"], "corr_tail_frac": cm["tail_frac"],
                "raw_chi2_ndf": rm["chi2_ndf"], "corr_chi2_ndf": cm["chi2_ndf"],
            }
            groups.append(row)
            rows.append(row)
        out[dim] = groups
    return out, rows


# ===========================================================================
# Main.
# ===========================================================================
def build_parser():
    ap = argparse.ArgumentParser(
        description="MV4 toy-digitizer timing-resolution diagnostic (TOY_DIAGNOSTIC).")
    src = ap.add_argument_group("input (choose ROOT or synthetic)")
    src.add_argument("--mc", default=None, help="ROOT MC file (requires uproot).")
    src.add_argument("--synthetic", type=int, default=0, metavar="N",
                     help="Generate N toy truth tracks offline (no ROOT). "
                          "Mutually usable instead of --mc.")
    ap.add_argument("--out", required=True, help="Output directory.")
    ap.add_argument("--tree", default="hibeam", help="ROOT tree name.")
    ap.add_argument("--calibration", "--calib", dest="calibration", default=None,
                    help="mv0 calibration.json to LOAD the v2 gain from. "
                         "Absent -> labelled fallback (warns; errors under --strict).")
    ap.add_argument("--data-anchors", dest="data_anchors", default=None,
                    help="JSON of measured data anchors + CIs. Absent -> labelled "
                         "fallback (warns; errors under --strict).")
    ap.add_argument("--strict", action="store_true",
                    help="Error (nonzero exit) instead of silently using a "
                         "hard-coded calibration/anchor fallback.")
    ap.add_argument("--slice-by", default="species,amplitude",
                    help=f"Comma list from {','.join(SLICE_DIMS)} (or 'all').")
    ap.add_argument("--bootstrap-blocks", action="store_true",
                    help="Use run/block-level resampling for the sigma68 error.")
    ap.add_argument("--tail-nsigma", type=float, default=3.0,
                    help="Robust-width multiple defining the tail fraction.")
    ap.add_argument("--seed", type=int, default=20260720,
                    help="Master RNG seed (synthetic truth + bootstraps).")
    ap.add_argument("--max-tracks", type=int, default=80000)
    ap.add_argument("--max-events", type=int, default=0)
    ap.add_argument("--min-tracks", type=int, default=100,
                    help="Abort if fewer usable tracks than this.")
    return ap


def parse_slice_dims(s):
    if not s:
        return []
    if s.strip().lower() == "all":
        return list(SLICE_DIMS)
    dims, bad = [], []
    for tok in s.split(","):
        tok = tok.strip()
        if not tok:
            continue
        if tok not in SLICE_DIMS:
            bad.append(tok)
        elif tok not in dims:
            dims.append(tok)
    if bad:
        raise SystemExit(f"[mv4] unknown --slice-by dims {bad}; valid: {list(SLICE_DIMS)}")
    return dims


def main(argv=None):
    ap = build_parser()
    args = ap.parse_args(argv)
    if not args.mc and not args.synthetic:
        raise SystemExit("[mv4] provide --mc <root> or --synthetic <N>")
    slice_dims = parse_slice_dims(args.slice_by)
    os.makedirs(args.out, exist_ok=True)
    print(f"[mv4] start={datetime.now(timezone.utc).isoformat()}")

    # --- load calibration + anchors FIRST so --strict fails fast (before compute) ---
    params, calib_meta = load_digitizer_params(args.calibration, strict=args.strict)
    anchors = load_data_anchors(args.data_anchors, strict=args.strict)
    dig = Digitizer(params)

    # --- truth records ---
    if args.synthetic:
        mode = "synthetic"
        records = make_synthetic_records(args.synthetic, args.seed)
        ev_global = len(records)
        print(f"[mv4] synthetic truth tracks generated={len(records)} seed={args.seed}")
    else:
        mode = "root"
        print(f"[mv4] mc={args.mc}")
        records, ev_global = read_root_records(args.mc, args.tree, args.max_tracks,
                                               args.max_events)

    data = digitize(records, dig)
    residual, amp_adc = data["residual"], data["amp_adc"]
    print(f"[mv4] usable tracks={residual.size} (scanned={ev_global}, mode={mode})")
    if residual.size < args.min_tracks:
        raise SystemExit(f"[mv4] too few usable tracks ({residual.size} < "
                         f"{args.min_tracks}); aborting")

    # --- timewalk + corrected ---
    A, B, corrected, fit_mask, app_mask = fit_timewalk(residual, amp_adc)

    raw_sigma = sigma68(residual)
    raw_metrics = metric_row(residual, args.tail_nsigma)
    corr_metrics_test = metric_row(corrected[app_mask], args.tail_nsigma)
    corr_metrics_all = metric_row(corrected, args.tail_nsigma)
    corr_sigma_test = corr_metrics_test["sigma68_ns"]

    if args.bootstrap_blocks:
        raw_unc = boot_sigma68_blocks(residual, data["run"], seed=args.seed)
        corr_unc = boot_sigma68_blocks(corrected[app_mask], data["run"][app_mask],
                                       seed=args.seed + 1)
        boot_kind = "block/run-level"
    else:
        raw_unc = boot_sigma68(residual, seed=args.seed)
        corr_unc = boot_sigma68(corrected[app_mask], seed=args.seed + 1)
        boot_kind = "iid"
    if not np.isfinite(raw_unc):
        raw_unc = boot_sigma68(residual, seed=args.seed)
    if not np.isfinite(corr_unc):
        corr_unc = boot_sigma68(corrected[app_mask], seed=args.seed + 1)

    print(f"[mv4] timewalk fit: A={A:.3f} ns  B={B:.2f} ns*ADC (1/A form)")
    print(f"[mv4] sigma68 raw={raw_sigma:.3f}+/-{raw_unc:.3f} "
          f"corrected(test)={corr_sigma_test:.3f}+/-{corr_unc:.3f}")

    # --- slices + LORO ---
    cols = build_slice_columns(data)
    slices, slice_rows = build_slices(residual, corrected, cols, slice_dims, args.tail_nsigma)
    loro = loro_spread(residual, data["run"])
    loro_corr = loro_spread(corrected, data["run"])

    # --- sigma68 vs amplitude (for the validation plot) ---
    qs = np.unique(np.percentile(amp_adc, np.linspace(0, 100, 9)))
    centers_amp, sig_raw_bin, sig_corr_bin, sig_raw_err, sig_corr_err = [], [], [], [], []
    for a, b in zip(qs[:-1], qs[1:]):
        mb = (amp_adc >= a) & (amp_adc < b)
        if mb.sum() < 30:
            continue
        centers_amp.append(float(0.5 * (a + b)))
        sig_raw_bin.append(sigma68(residual[mb]))
        sig_corr_bin.append(sigma68(corrected[mb]))
        sig_raw_err.append(boot_sigma68(residual[mb], n_boot=100, seed=args.seed))
        sig_corr_err.append(boot_sigma68(corrected[mb], n_boot=100, seed=args.seed))

    # --- pulls vs (loaded or fallback) data anchors ---
    data_raw = anchors["S02_raw_sigma68_ns"]
    data_corr = anchors["S03_corrected_sigma68_ns"]
    data_raw_unc = anchors.get("raw_unc_ns") or 0.0
    data_corr_unc = anchors.get("corrected_unc_ns") or 0.0

    def pull(mc, mc_unc, dat, dat_unc):
        comb = float(np.sqrt(mc_unc ** 2 + dat_unc ** 2))
        return ((mc - dat) / comb if comb > 0 else float("nan")), comb
    pull_raw, comb_raw = pull(raw_sigma, raw_unc, data_raw, data_raw_unc)
    pull_corr, comb_corr = pull(corr_sigma_test, corr_unc, data_corr, data_corr_unc)

    # --- optional gain-uncertainty propagation (re-digitize at gain +/- unc) ---
    gain_prop = None
    if calib_meta.get("gain_adc_per_mev_unc"):
        rel = calib_meta["gain_rel_unc"]
        band = {}
        for tag, scale in (("gain_lo", 1.0 - rel), ("gain_hi", 1.0 + rel)):
            pp = dict(params); pp["gain_adc_per_mev"] = params["gain_adc_per_mev"] * scale
            d2 = digitize(records, Digitizer(pp), capture_examples=False)
            band[tag] = {"gain_adc_per_mev": pp["gain_adc_per_mev"],
                         "raw_sigma68_ns": sigma68(d2["residual"]),
                         "n": int(d2["residual"].size)}
        gain_prop = {"rel_unc": rel, "central_raw_sigma68_ns": raw_sigma, **band}

    summary = {
        "study_id": "MV4",
        "status": "TOY_DIAGNOSTIC",
        "status_note": ("Toy-digitizer diagnostic. Remains TOY_DIAGNOSTIC until "
                        "re-run on LUNARC with the current v2 mv0 calibration "
                        "(--calibration) AND measured data anchors (--data-anchors)."),
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "mode": mode,
        "seed": int(args.seed),
        "mc_file": os.path.abspath(args.mc) if args.mc else None,
        "n_tracks": int(residual.size),
        "n_events_scanned": int(ev_global),
        "calibration_source": calib_meta["source"],
        "calibration": calib_meta,
        "data_anchors_source": anchors["source"],
        "data_anchors": anchors,
        "digitizer_params": params,
        "timewalk_fit": {
            "A_ns": A, "B_ns_ADC": B,
            "timewalk_functional_form": "1/A (MV4b-fixed 2026-07-01, was 1/sqrt(A))",
        },
        "bootstrap_kind": boot_kind,
        "metrics_global": {
            "raw": raw_metrics,
            "corrected_test_half": corr_metrics_test,
            "corrected_all": corr_metrics_all,
            "raw_sigma68_unc_ns": raw_unc,
            "corrected_sigma68_unc_ns": corr_unc,
        },
        # legacy-compatible block
        "sigma68_ns": {
            "raw": raw_sigma, "raw_unc": raw_unc,
            "corrected_test_half": corr_sigma_test, "corrected_unc": corr_unc,
            "corrected_all": corr_metrics_all["sigma68_ns"],
        },
        "residual_median_ns": float(np.median(residual)),
        "pull": {"raw": pull_raw, "raw_combined_unc": comb_raw,
                 "corrected": pull_corr, "corrected_combined_unc": comb_corr},
        "improvement_factor": float(raw_sigma / corr_sigma_test) if corr_sigma_test else None,
        "gain_propagation": gain_prop,
        "slices": slices,
        "slice_dims": slice_dims,
        "loro_raw": loro,
        "loro_corrected": loro_corr,
        "n_proton": int((data["pdg"] == PROTON).sum()),
        "n_deuteron": int((data["pdg"] == DEUTERON).sum()),
    }
    with open(os.path.join(args.out, "result.json"), "w") as fh:
        json.dump(summary, fh, indent=2)
    with open(os.path.join(args.out, "mv4_summary.json"), "w") as fh:
        json.dump(summary, fh, indent=2)
    print(f"[mv4] wrote {args.out}/result.json (+ mv4_summary.json)")

    # --- slice CSV ---
    csv_path = os.path.join(args.out, "mv4_slice_metrics.csv")
    fields = ["slice_dim", "slice_value", "n",
              "raw_sigma68_ns", "corr_sigma68_ns", "raw_rms_ns", "corr_rms_ns",
              "raw_core_sigma_ns", "corr_core_sigma_ns", "raw_tail_frac",
              "corr_tail_frac", "raw_chi2_ndf", "corr_chi2_ndf"]
    with open(csv_path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for row in slice_rows:
            w.writerow({k: row.get(k) for k in fields})
    print(f"[mv4] wrote {csv_path} ({len(slice_rows)} slice rows)")

    # --- plots ---
    _make_plots(args.out, dig, data["examples"], residual, corrected, raw_sigma,
                corr_sigma_test, centers_amp, sig_raw_bin, sig_corr_bin,
                sig_raw_err, sig_corr_err, raw_unc, corr_unc,
                data_raw, data_corr, data_raw_unc, data_corr_unc, pull_raw, pull_corr)

    _write_report(args, summary, params, calib_meta, anchors, residual, corrected,
                  raw_sigma, raw_unc, corr_sigma_test, corr_unc, A, B, pull_raw,
                  pull_corr, data_raw, data_corr, loro, slice_rows)
    print(f"[mv4] done={datetime.now(timezone.utc).isoformat()}")
    return 0


def _make_plots(out, dig, examples, residual, corrected, raw_sigma, corr_sigma_test,
                centers_amp, sig_raw_bin, sig_corr_bin, sig_raw_err, sig_corr_err,
                raw_unc, corr_unc, data_raw, data_corr, data_raw_unc, data_corr_unc,
                pull_raw, pull_corr):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axs = plt.subplots(1, 2, figsize=(12, 4.8))
    for ax, (p0, lab) in zip(axs, [(PROTON, "proton"), (DEUTERON, "deuteron")]):
        if p0 in examples:
            c, wf, t_cfd, t_truth, peak = examples[p0]
            ax.plot(c, wf, "o-", color="C0", ms=4, label="ADC samples")
            ax.axhline(dig.ped + 0.20 * peak, color="C2", ls=":", label="20% CFD thr")
            ax.axvline(t_cfd, color="C3", ls="--", label=f"t_cfd={t_cfd:.1f}")
            ax.axvline(t_truth, color="k", ls="-.", lw=1, label=f"t_truth={t_truth:.1f}")
            ax.set_title(f"{lab}  peak={peak:.0f} ADC")
        else:
            ax.set_title(f"{lab} (no example)")
        ax.set_xlabel("time [ns]"); ax.set_ylabel("ADC")
        ax.legend(fontsize=8)
    fig.suptitle("MV4 simulated waveforms with CFD20 pick-off")
    fig.tight_layout(); fig.savefig(os.path.join(out, "mv4_waveform_examples.png"), dpi=130)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 5))
    rng_lo, rng_hi = np.percentile(residual, [1, 99])
    bins = np.linspace(rng_lo, rng_hi, 70)
    ax.hist(residual, bins=bins, histtype="step", color="C0", lw=1.8,
            label=f"raw  sigma68={raw_sigma:.2f} ns")
    ax.hist(corrected + np.median(residual), bins=bins, histtype="step", color="C3", lw=1.8,
            label=f"timewalk-corr  sigma68={corr_sigma_test:.2f} ns")
    ax.set_xlabel("t_cfd - t_truth [ns]"); ax.set_ylabel("tracks")
    ax.set_title("MV4 timing residual (TOY_DIAGNOSTIC)"); ax.legend()
    fig.tight_layout(); fig.savefig(os.path.join(out, "mv4_residuals.png"), dpi=130)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 5))
    if centers_amp:
        ax.errorbar(centers_amp, sig_raw_bin, yerr=sig_raw_err, fmt="o-", color="C0",
                    label="raw", capsize=3)
        ax.errorbar(centers_amp, sig_corr_bin, yerr=sig_corr_err, fmt="s-", color="C3",
                    label="timewalk-corr", capsize=3)
    ax.set_xlabel("pulse amplitude [ADC]"); ax.set_ylabel("sigma68 [ns]")
    ax.set_title("MV4 sigma68 vs amplitude"); ax.legend()
    fig.tight_layout(); fig.savefig(os.path.join(out, "mv4_sigma_vs_amp.png"), dpi=130)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 5))
    labels = ["raw CFD20", "timewalk-corr"]
    mc_vals = [raw_sigma, corr_sigma_test]; mc_errs = [raw_unc, corr_unc]
    data_vals = [data_raw, data_corr]; data_errs = [data_raw_unc, data_corr_unc]
    xpos = np.arange(len(labels)); w = 0.35
    ax.bar(xpos - w / 2, mc_vals, w, yerr=mc_errs, capsize=4, color="C0", label="MC")
    ax.bar(xpos + w / 2, data_vals, w, yerr=data_errs, capsize=4, color="C1",
           label="data anchors")
    ax.set_xticks(xpos); ax.set_xticklabels(labels)
    ax.set_ylabel("sigma68 [ns]"); ax.set_title("MV4 MC vs data timing resolution"); ax.legend()
    fig.tight_layout(); fig.savefig(os.path.join(out, "mv4_data_vs_mc.png"), dpi=130)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.bar(labels, [pull_raw, pull_corr], color=["C0", "C3"])
    for sgma, c in [(1, "gray"), (2, "lightgray")]:
        ax.axhspan(-sgma, sgma, color=c, alpha=0.25, zorder=0)
    ax.axhline(0, color="k", lw=1)
    ax.set_ylabel("pull  (MC - data)/combined_unc")
    ax.set_title("MV4 MC-vs-data pull (bands: +/-1, +/-2 sigma)")
    fig.tight_layout(); fig.savefig(os.path.join(out, "mv4_pull.png"), dpi=130)
    plt.close(fig)


def _write_report(args, summary, params, calib_meta, anchors, residual, corrected,
                  raw_sigma, raw_unc, corr_sigma_test, corr_unc, A, B, pull_raw,
                  pull_corr, data_raw, data_corr, loro, slice_rows):
    def verdict(p):
        ap_ = abs(p)
        return "PASS" if ap_ < 2 else ("TENSION" if ap_ < 3 else "FAIL")
    L = []
    L.append("# MV4 -- Timing-Resolution Toy Diagnostic\n")
    L.append("- status: **TOY_DIAGNOSTIC** (was MV4/PRODUCTION)")
    L.append(f"- calibration source: **{calib_meta['source']}**"
             + (f" (`{calib_meta['path']}`)" if calib_meta.get("path") else
                " -- FALLBACK gain 246 ADC/MeV (WARNED)"))
    L.append(f"- data anchors source: **{anchors['source']}**")
    L.append(f"- mode: {summary['mode']}  seed: {summary['seed']}")
    L.append(f"- generated: {summary['generated_utc']}")
    L.append(f"- tracks used: {residual.size} "
             f"(proton {summary['n_proton']}, deuteron {summary['n_deuteron']})")
    L.append(f"- digitizer: gain={params['gain_adc_per_mev']:.0f} ADC/MeV, "
             f"noise={params['noise_adc_rms']:.0f} ADC, ped={params['pedestal_adc']:.0f}, "
             f"tau_rise={params['tau_rise_ns']}, tau_decay={params['tau_decay_ns']} ns\n")
    if calib_meta["source"] == "fallback" or anchors["source"] == "fallback":
        L.append("> WARNING: this run used HARD-CODED FALLBACK values (gain and/or "
                 "data anchors). It is a diagnostic only. Re-run with --calibration "
                 "and --data-anchors (and --strict) for a production result.\n")
    L.append("## Reproduce")
    L.append("```")
    L.append(f"{os.path.basename(__file__)} --mc <root> --out <dir> "
             f"--calibration <mv0 calibration.json> --data-anchors <anchors.json> "
             f"--strict --slice-by {args.slice_by}")
    L.append("```\n")
    L.append("## Global metrics (raw / timewalk-corrected test-half)")
    rm = summary["metrics_global"]["raw"]; cm = summary["metrics_global"]["corrected_test_half"]
    L.append("| metric | raw | corrected |")
    L.append("|---|---|---|")
    for key, lab in [("sigma68_ns", "sigma68 [ns]"), ("rms_ns", "RMS [ns]"),
                     ("core_sigma_ns", "Gaussian-core sigma [ns]"),
                     ("tail_frac", f"tail frac (>{args.tail_nsigma}sig)"),
                     ("chi2_ndf", "chi2/ndf")]:
        L.append(f"| {lab} | {rm[key]:.4g} | {cm[key]:.4g} |")
    L.append(f"| sigma68 unc [ns] | {raw_unc:.4g} | {corr_unc:.4g} |")
    L.append(f"\n- improvement factor (raw/corr sigma68): {summary['improvement_factor']}")
    L.append(f"- timewalk fit: A={A:.3f} ns, B={B:.2f} ns*ADC (1/A form)\n")
    if loro:
        L.append("## LORO / per-run spread (raw sigma68)")
        lo = loro["leave_one_run_out"]
        L.append(f"- runs: {loro['n_runs']}  full sigma68={loro['metric_full_ns']:.3f} ns")
        L.append(f"- leave-one-run-out sigma68: mean={lo['mean_ns']:.3f}, "
                 f"std={lo['std_ns']:.3f}, min={lo['min_ns']:.3f}, max={lo['max_ns']:.3f} ns")
        L.append(f"- per-run sigma68 spread (std): {loro['per_run_spread_std_ns']:.3f} ns\n")
    L.append("## Slices")
    if slice_rows:
        L.append("| dim | value | n | raw sig68 | corr sig68 | raw tail | corr tail |")
        L.append("|---|---|---|---|---|---|---|")
        for r in slice_rows:
            L.append(f"| {r['slice_dim']} | {r['slice_value']} | {r['n']} | "
                     f"{r['raw_sigma68_ns']:.3f} | {r['corr_sigma68_ns']:.3f} | "
                     f"{r['raw_tail_frac']:.3f} | {r['corr_tail_frac']:.3f} |")
        L.append("\n(full per-slice metrics incl. RMS, core-sigma, chi2/ndf in "
                 "`mv4_slice_metrics.csv`)\n")
    else:
        L.append("- (no slices requested / all groups below MIN_SLICE_N)\n")
    L.append("## Comparison to data anchors")
    L.append("| stage | MC sigma68 [ns] | data sigma68 [ns] | pull | verdict |")
    L.append("|---|---|---|---|---|")
    L.append(f"| raw CFD20 | {raw_sigma:.2f}+/-{raw_unc:.2f} | {data_raw:.2f} | "
             f"{pull_raw:+.2f} | {verdict(pull_raw)} |")
    L.append(f"| timewalk-corr | {corr_sigma_test:.2f}+/-{corr_unc:.2f} | {data_corr:.2f} | "
             f"{pull_corr:+.2f} | {verdict(pull_corr)} |\n")
    L.append("## Open questions / caveats")
    L.append("- STATUS is TOY_DIAGNOSTIC until re-run on LUNARC with the v2 "
             "calibration and measured anchors.")
    L.append("- Absolute residual offset is set by the (arbitrary) window "
             "placement; only the spread (sigma68) is physical.")
    L.append("- Noise/tau taken from the digitizer card; an MV0-style data-driven "
             "pulse-shape fit would remove the remaining modeling freedom.")
    with open(os.path.join(args.out, "REPORT.md"), "w") as fh:
        fh.write("\n".join(L) + "\n")
    print(f"[mv4] wrote {args.out}/REPORT.md")


if __name__ == "__main__":
    raise SystemExit(main())
