#!/usr/bin/env python3
"""S27 — Early-peak class leakage BUDGET (reviewer M8 / B-M8).

The 4.4% early-peak class (peak_sample <= 3, per P02/P03f) is real in data and
its cause is deferred (C12 ruled out, MV6b). This study bounds the systematic
each headline observable carries from that class:

  (i)  timing residual sigma68 — downstream (B4/B6/B8) per-pair CFD20 residuals,
       included vs excluded (any pulse of the pair early-peak);
  (ii) tau_eff live-time — S10b 10% tail-crossing on selected single pulses,
       included vs excluded;
  (iii) pile-up / current excess — the early-peak class's fractional share of
       the selected-pulse count and of the integrated pulse area (charge/current
       proxy), from the canonical s00 pulse table.

Deliverable: per-observable leakage bound. If the standard A>1000 + valid-CFD
selection already suppresses the class, that is shown quantitatively instead.

Selection matches the canonical anchor: baseline = median(samples 0-3),
amplitude = max(waveform - baseline) > 1000 ADC; downstream staves B4/B6/B8;
early-peak := peak_sample = argmax(corrected) <= 3.

Timing/tau_eff read the raw analysis runs (via the s22 loader pipeline);
counts/area read the canonical s00 table. Heavy IO is lazy so the reduction
helpers stay importable.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
import sys
import time
from pathlib import Path

import numpy as np

ROOT_DIR = Path(__file__).resolve().parents[1]

STAVES = ("B4", "B6", "B8")
DOWNSTREAM_PAIRS = (("B4", "B6"), ("B4", "B8"), ("B6", "B8"))
AMPLITUDE_CUT_ADC = 1000.0
EARLY_PEAK_MAX_SAMPLE = 3
SPACING_NS = 10.0
N_SAMPLES = 18
RANDOM_SEED = 20260705
N_BOOT = 300
TAU_GRID_NS = np.arange(-30.0, 165.1, 5.0)
DATA_TAU_EFF_NS = 124.79


def sigma68(values: np.ndarray) -> float:
    v = np.asarray(values, dtype=float)
    v = v[np.isfinite(v)]
    if v.size == 0:
        return float("nan")
    q16, q84 = np.percentile(v, [16.0, 84.0])
    return float(0.5 * (q84 - q16))


def _load_s22():
    path = ROOT_DIR / "scripts" / "s22_timing_vs_amplitude.py"
    spec = importlib.util.spec_from_file_location("s22_timing_vs_amplitude", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["s22_timing_vs_amplitude"] = module
    spec.loader.exec_module(module)
    return module


def load_run_pulses(s22, raw_dir: Path, run: int, max_events: int = 0):
    """Per-pulse downstream table with early-peak tag + corrected waveforms.

    Returns per-(event,stave) selected pulses (A>1000) for B4/B6/B8: run,
    eventno, stave, amplitude, cfd time, peak_sample, and the baseline-
    subtracted waveform (for the tau_eff estimator). Also returns the per-event
    downstream time/peak arrays for building pairs.
    """
    stave_names = list(s22.STAVE_CHANNELS.keys())  # B2,B4,B6,B8
    channels = np.asarray([s22.STAVE_CHANNELS[s] for s in stave_names])
    idx = {s: stave_names.index(s) for s in STAVES}
    per_stave = {s: {"amp": [], "time": [], "peak": [], "wave": [], "event": []} for s in STAVES}
    ev_rows = []  # dicts with per-event downstream times/amps/peaks/valid
    n_seen = 0
    for batch in s22.iter_raw(s22.raw_file(raw_dir, run), ["EVENTNO", "HRDv"]):
        eventno = np.asarray(batch["EVENTNO"]).astype(np.int64)
        flat = np.stack(batch["HRDv"]).astype(np.float64)
        events = flat.reshape(-1, 8, s22.SAMPLES_PER_CHANNEL)[:, channels, :]
        baseline = np.median(events[..., s22.BASELINE_SAMPLES], axis=-1)
        corrected = events - baseline[..., None]
        amplitude = corrected.max(axis=-1)
        peak_sample = corrected.argmax(axis=-1)
        n_ev, n_st, nsamp = corrected.shape
        t, valid = s22.cfd20_rising_edge(corrected.reshape(-1, nsamp), amplitude.reshape(-1))
        t = t.reshape(n_ev, n_st)
        valid = valid.reshape(n_ev, n_st)
        for s in STAVES:
            j = idx[s]
            sel = (amplitude[:, j] > AMPLITUDE_CUT_ADC) & valid[:, j]
            if sel.any():
                per_stave[s]["amp"].append(amplitude[sel, j])
                per_stave[s]["time"].append(t[sel, j])
                per_stave[s]["peak"].append(peak_sample[sel, j])
                per_stave[s]["wave"].append(corrected[sel, j, :])
                per_stave[s]["event"].append(eventno[sel] if len(eventno) == n_ev else np.flatnonzero(sel))
        # per-event downstream arrays (for pairs)
        ev_rows.append({
            "run": np.full(n_ev, run),
            "amp": {s: amplitude[:, idx[s]] for s in STAVES},
            "time": {s: t[:, idx[s]] for s in STAVES},
            "peak": {s: peak_sample[:, idx[s]] for s in STAVES},
            "valid": {s: valid[:, idx[s]] for s in STAVES},
        })
        n_seen += n_ev
        if max_events and n_seen >= max_events:
            break
    out_ps = {}
    for s in STAVES:
        d = per_stave[s]
        out_ps[s] = {
            "amp": np.concatenate(d["amp"]) if d["amp"] else np.array([]),
            "time": np.concatenate(d["time"]) if d["time"] else np.array([]),
            "peak": np.concatenate(d["peak"]) if d["peak"] else np.array([]),
            "wave": np.concatenate(d["wave"]) if d["wave"] else np.zeros((0, N_SAMPLES)),
            "run": np.full(sum(len(x) for x in d["amp"]), run) if d["amp"] else np.array([]),
        }
    return out_ps, ev_rows


def build_pairs(ev_rows):
    """Downstream pair residuals with early-peak tags, per-(pair,run) centered."""
    import pandas as pd
    frames = []
    for chunk in ev_rows:
        run = chunk["run"]
        for a, b in DOWNSTREAM_PAIRS:
            m = (chunk["amp"][a] > AMPLITUDE_CUT_ADC) & (chunk["amp"][b] > AMPLITUDE_CUT_ADC) \
                & chunk["valid"][a] & chunk["valid"][b]
            if not m.any():
                continue
            # TOF/cable offsets are removed by the per-(pair,run) median centering below.
            frames.append(pd.DataFrame({
                "run": run[m],
                "pair": f"{a}-{b}",
                "resid": chunk["time"][b][m] - chunk["time"][a][m],
                "early": (chunk["peak"][a][m] <= EARLY_PEAK_MAX_SAMPLE)
                         | (chunk["peak"][b][m] <= EARLY_PEAK_MAX_SAMPLE),
            }))
    df = pd.concat(frames, ignore_index=True)
    # per-(pair,run) median centering (removes cable delay/TOF/run offsets)
    df["resid_c"] = df["resid"] - df.groupby(["pair", "run"])["resid"].transform("median")
    return df


def timing_leakage(pairs_df, rng, n_boot=N_BOOT):
    """sigma68 of centered downstream residuals: all vs early-peak-excluded."""
    vals_all = pairs_df["resid_c"].to_numpy()
    keep = ~pairs_df["early"].to_numpy()
    s_all = sigma68(vals_all)
    s_clean = sigma68(vals_all[keep])
    s_early = sigma68(vals_all[~keep]) if (~keep).any() else float("nan")

    # bootstrap the shift (resample within run)
    runs = pairs_df["run"].to_numpy()
    order = np.argsort(runs, kind="stable")
    v, k, r = vals_all[order], keep[order], runs[order]
    uniq, starts = np.unique(r, return_index=True)
    bnds = list(starts) + [len(r)]
    shifts = []
    for _ in range(n_boot):
        idxs = []
        for i in range(len(uniq)):
            seg = np.arange(bnds[i], bnds[i + 1])
            idxs.append(seg[rng.integers(0, len(seg), size=len(seg))])
        bi = np.concatenate(idxs)
        shifts.append(sigma68(v[bi]) - sigma68(v[bi][k[bi]]))
    return {
        "sigma68_all_ns": float(s_all),
        "sigma68_early_excluded_ns": float(s_clean),
        "sigma68_early_only_ns": float(s_early),
        "shift_ns": float(s_all - s_clean),
        "shift_ci_ns": [float(np.percentile(shifts, 2.5)), float(np.percentile(shifts, 97.5))],
        "n_pairs": int(len(vals_all)),
        "n_early_pairs": int((~keep).sum()),
        "early_pair_fraction": float((~keep).mean()),
    }


def cfd_samples(wave, amp, frac=0.20):
    thr = amp * frac
    ge = wave >= thr[:, None]
    first = np.argmax(ge, axis=1)
    valid = ge.any(axis=1)
    out = np.full(len(wave), np.nan)
    for i in np.where(valid)[0]:
        j = int(first[i])
        if j <= 0:
            out[i] = float(j); continue
        y0, y1 = float(wave[i, j - 1]), float(wave[i, j])
        d = y1 - y0
        out[i] = float(j) if d <= 0 else (j - 1) + (float(thr[i]) - y0) / d
    return out


def _exp_tail(t, c, a, tau):
    return c + a * np.exp(-t / tau)


def fit_live10(grid, y, threshold=0.10):
    from scipy.optimize import curve_fit
    valid = np.isfinite(y)
    if valid.sum() < 8:
        return math.nan, math.nan
    pi = int(np.nanargmax(y))
    pt = float(grid[pi])
    tail = valid & (grid >= pt) & (grid <= 155.0)
    if tail.sum() < 6:
        return math.nan, math.nan
    x = grid[tail] - pt
    yy = y[tail]
    try:
        popt, _ = curve_fit(_exp_tail, x, yy, p0=(0.01, max(float(np.nanmax(yy)), 0.2), 55.0),
                            bounds=([-0.1, 0.0, 5.0], [0.2, 2.0, 500.0]), maxfev=20000)
        c, a, tau = [float(v) for v in popt]
        cross = math.nan if (threshold <= c or a <= 0) else pt + tau * math.log(a / (threshold - c))
        return cross, tau
    except Exception:
        return math.nan, math.nan


def tau_eff_group(waves, amps, rng, max_align=6000):
    """Pooled live10 from aligned median template of one pulse population."""
    if len(waves) < 80:
        return math.nan
    cfd = cfd_samples(waves, amps, 0.20)
    good = np.isfinite(cfd)
    waves, amps, cfd = waves[good], amps[good], cfd[good]
    norm = waves / np.maximum(amps, 1.0)[:, None]
    take = min(len(waves), max_align)
    pick = rng.choice(len(waves), size=take, replace=False)
    aligned = np.empty((take, len(TAU_GRID_NS)))
    for r, i in enumerate(pick):
        st = (np.arange(N_SAMPLES, dtype=float) - cfd[i]) * SPACING_NS
        aligned[r] = np.interp(TAU_GRID_NS, st, norm[i], left=np.nan, right=np.nan)
    cross, _tau = fit_live10(TAU_GRID_NS, np.nanmedian(aligned, axis=0))
    return cross


def tau_eff_leakage(per_stave_all, rng, n_boot=N_BOOT):
    """Composition-weighted live10: all vs early-peak-excluded."""
    def pooled(exclude_early):
        vals, weights = [], []
        for s in STAVES:
            d = per_stave_all[s]
            m = np.ones(len(d["amp"]), dtype=bool)
            if exclude_early:
                m &= d["peak"] > EARLY_PEAK_MAX_SAMPLE
            if m.sum() < 80:
                continue
            live = tau_eff_group(d["wave"][m], d["amp"][m], rng)
            if np.isfinite(live):
                vals.append(live); weights.append(m.sum())
        return float(np.average(vals, weights=weights)) if vals else math.nan

    t_all = pooled(False)
    t_clean = pooled(True)
    return {
        "tau_eff_all_ns": t_all,
        "tau_eff_early_excluded_ns": t_clean,
        "shift_ns": float(t_all - t_clean) if np.isfinite(t_all) and np.isfinite(t_clean) else math.nan,
        "data_tau_eff_ns": DATA_TAU_EFF_NS,
    }


def pileup_current_budget(s00_table_path: Path):
    """Early-peak share of selected count and integrated area (current proxy)."""
    import pandas as pd
    df = pd.read_csv(s00_table_path)
    df = df[df["amplitude_adc"] > AMPLITUDE_CUT_ADC]
    early = df["peak_sample"] <= EARLY_PEAK_MAX_SAMPLE
    out = {"overall": {
        "n_selected": int(len(df)),
        "early_count_fraction": float(early.mean()),
        "early_area_fraction": float(df.loc[early, "area_adc_samples"].sum() / df["area_adc_samples"].sum()),
        "early_mean_area": float(df.loc[early, "area_adc_samples"].mean()),
        "nonearly_mean_area": float(df.loc[~early, "area_adc_samples"].mean()),
    }}
    by_stave = {}
    for s, g in df.groupby("stave"):
        e = g["peak_sample"] <= EARLY_PEAK_MAX_SAMPLE
        by_stave[str(s)] = {
            "n_selected": int(len(g)),
            "early_count_fraction": float(e.mean()),
            "early_area_fraction": float(g.loc[e, "area_adc_samples"].sum() / g["area_adc_samples"].sum()),
        }
    out["by_stave"] = by_stave
    # area excess: how much extra "current" the early class carries vs its count share
    o = out["overall"]
    o["area_to_count_excess"] = float(o["early_area_fraction"] / o["early_count_fraction"]) \
        if o["early_count_fraction"] > 0 else math.nan
    return out


def make_figure(out_dir, timing, tau, pileup):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    matplotlib.rcParams.update({
        "font.family": "sans-serif", "font.sans-serif": ["Arial", "DejaVu Sans"],
        "pdf.fonttype": 42, "svg.fonttype": "none", "font.size": 7,
        "axes.spines.right": False, "axes.spines.top": False, "legend.frameon": False,
    })
    fig, (ax_a, ax_b, ax_c) = plt.subplots(1, 3, figsize=(7.2, 2.6))

    # a: timing sigma68 all vs excluded
    xs = ["all", "early\nexcluded", "early\nonly"]
    ys = [timing["sigma68_all_ns"], timing["sigma68_early_excluded_ns"], timing["sigma68_early_only_ns"]]
    ax_a.bar(xs, ys, color=["#2f5f8a", "#4f8fbf", "#a63d40"])
    ax_a.set_ylabel("downstream pair sigma68 (ns)")
    ax_a.set_title(f"a  timing (shift {timing['shift_ns']:+.3f} ns)", loc="left")

    # b: tau_eff all vs excluded
    xs = ["all", "early excl."]
    ys = [tau["tau_eff_all_ns"], tau["tau_eff_early_excluded_ns"]]
    ax_b.bar(xs, ys, color=["#2f5f8a", "#4f8fbf"])
    ax_b.axhline(DATA_TAU_EFF_NS, color="k", ls="--", lw=0.8)
    ax_b.set_ylabel("live10 tau_eff (ns)")
    ax_b.set_title(f"b  tau_eff (shift {tau['shift_ns']:+.2f} ns)", loc="left")
    ax_b.set_ylim(min(ys) * 0.9 if np.isfinite(ys).all() else 0, None)

    # c: early-peak count vs area fraction per stave
    staves = list(pileup["by_stave"].keys())
    cf = [pileup["by_stave"][s]["early_count_fraction"] * 100 for s in staves]
    af = [pileup["by_stave"][s]["early_area_fraction"] * 100 for s in staves]
    x = np.arange(len(staves))
    ax_c.bar(x - 0.18, cf, 0.36, color="#2f5f8a", label="count %")
    ax_c.bar(x + 0.18, af, 0.36, color="#c9776f", label="area %")
    ax_c.set_xticks(x, staves)
    ax_c.set_ylabel("early-peak share (%)")
    ax_c.set_title("c  pile-up/current budget", loc="left")
    ax_c.legend(fontsize=5.5)

    fig.tight_layout()
    fig.savefig(out_dir / "fig_s27_earlypeak_budget.png", dpi=400)
    fig.savefig(out_dir / "fig_s27_earlypeak_budget.pdf")
    plt.close(fig)


def git_commit():
    import subprocess
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True, cwd=str(ROOT_DIR)).strip()
    except Exception:
        return "unknown"


def write_report(out_dir, summary):
    t, ta, p = summary["timing"], summary["tau_eff"], summary["pileup_current"]
    o = p["overall"]
    lines = [
        "# S27 — Early-peak class leakage budget (B-M8)",
        "",
        f"- Generated: {summary['generated_utc']}",
        f"- Git commit: `{summary['git_commit']}`",
        f"- Early-peak definition: peak_sample = argmax(baseline-subtracted) <= {EARLY_PEAK_MAX_SAMPLE} (P02/P03f).",
        f"- Selection: A>1000 ADC, valid CFD20; downstream B4/B6/B8.",
        f"- Timing/tau_eff on raw analysis runs {summary['runs']}; counts/area from the canonical s00 table.",
        "",
        "## Per-observable leakage bounds",
        "",
        "| observable | with early-peak | early-peak excluded | leakage |",
        "|---|---|---|---|",
        f"| (i) downstream pair sigma68 (ns) | {t['sigma68_all_ns']:.3f} | "
        f"{t['sigma68_early_excluded_ns']:.3f} | {t['shift_ns']:+.3f} "
        f"[{t['shift_ci_ns'][0]:+.3f}, {t['shift_ci_ns'][1]:+.3f}] |",
        f"| (ii) live10 tau_eff (ns) | {ta['tau_eff_all_ns']:.2f} | "
        f"{ta['tau_eff_early_excluded_ns']:.2f} | {ta['shift_ns']:+.2f} |",
        f"| (iii) pile-up/current: early-peak count share | {o['early_count_fraction']*100:.2f}% | — | "
        f"area share {o['early_area_fraction']*100:.2f}% |",
        "",
        f"- Early-peak pulses are {t['early_pair_fraction']*100:.2f}% of downstream pairs and "
        f"{o['early_count_fraction']*100:.2f}% of selected pulses (A>1000). The standard A>1000 + valid-CFD "
        "selection does NOT remove them; the bounds above quantify what each headline carries.",
        f"- Current/charge proxy: the early class carries {o['early_area_fraction']*100:.2f}% of the "
        f"integrated selected-pulse area (area/count excess factor {o['area_to_count_excess']:.2f} — "
        f">1 means early-peak pulses are on average {'larger' if o['area_to_count_excess']>1 else 'smaller'} in area).",
        "",
        "## Interpretation",
        "",
        f"- **Timing:** excluding the early-peak class moves the downstream pair sigma68 by "
        f"{t['shift_ns']:+.3f} ns (95% CI [{t['shift_ci_ns'][0]:+.3f}, {t['shift_ci_ns'][1]:+.3f}]). "
        "This is the systematic the timing headline carries from the unexplained class.",
        f"- **tau_eff:** the live-time shifts by {ta['shift_ns']:+.2f} ns when the class is excluded "
        f"(data anchor {DATA_TAU_EFF_NS} ns).",
        f"- **Pile-up/current:** the class is {o['early_count_fraction']*100:.2f}% of counts and "
        f"{o['early_area_fraction']*100:.2f}% of integrated area — the fractional bound on any "
        "occupancy-/current-derived quantity.",
        "",
        "## Caveats",
        "- peak_sample<=3 is a coarse (10 ns sampling) morphological tag, not a physical class label;",
        "  it over- and under-counts the true instrumental population at the edges.",
        "- Timing/tau_eff are measured on the staged analysis runs (44-63,65); the canonical s00 table",
        "  spans the full dataset (calibration runs included) for the count/area budget.",
        "- The cause of the class remains open (C12 excluded, MV6b); this budget bounds its leakage, it",
        "  does not identify it.",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--raw-dir", default="data/root/root")
    ap.add_argument("--s00-table", required=True, help="canonical s00 selected pulse table (.csv.gz)")
    ap.add_argument("--out", default=None)
    ap.add_argument("--max-events", type=int, default=0)
    args = ap.parse_args()
    t0 = time.time()

    s22 = _load_s22()
    raw_dir = Path(args.raw_dir)
    out_dir = Path(args.out) if args.out else ROOT_DIR / "reports" / f"s27_earlypeak_budget_{int(time.time())}"
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(RANDOM_SEED)

    runs = [r for r in sorted(set(s22.SAMPLE_RUNS["sample_I"] + s22.SAMPLE_RUNS["sample_II"]))
            if s22.raw_file(raw_dir, r).exists()]
    print(f"[s27] runs present: {runs}", flush=True)

    per_stave = {s: {"amp": [], "time": [], "peak": [], "wave": []} for s in STAVES}
    all_ev_rows = []
    for r in runs:
        ps, ev = load_run_pulses(s22, raw_dir, r, max_events=args.max_events)
        for s in STAVES:
            for k in ("amp", "time", "peak", "wave"):
                per_stave[s][k].append(ps[s][k])
        all_ev_rows.extend(ev)
        print(f"[s27] run {r}: B4={len(ps['B4']['amp'])} B6={len(ps['B6']['amp'])} B8={len(ps['B8']['amp'])}", flush=True)
    per_stave_all = {s: {k: (np.concatenate(v) if len(v) and sum(len(x) for x in v) else
                           (np.zeros((0, N_SAMPLES)) if k == "wave" else np.array([])))
                        for k, v in per_stave[s].items()} for s in STAVES}

    pairs_df = build_pairs(all_ev_rows)
    timing = timing_leakage(pairs_df, rng)
    print(f"[s27] timing shift={timing['shift_ns']:+.3f} ns", flush=True)
    tau = tau_eff_leakage(per_stave_all, rng)
    print(f"[s27] tau_eff shift={tau['shift_ns']:+.2f} ns", flush=True)
    pileup = pileup_current_budget(Path(args.s00_table))
    print(f"[s27] early count frac={pileup['overall']['early_count_fraction']:.4f}", flush=True)

    summary = {
        "study": "S27",
        "title": "early-peak class leakage budget",
        "git_commit": git_commit(),
        "generated_utc": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        "early_peak_max_sample": EARLY_PEAK_MAX_SAMPLE,
        "amplitude_cut_adc": AMPLITUDE_CUT_ADC,
        "runs": runs,
        "s00_table": str(args.s00_table),
        "timing": timing,
        "tau_eff": tau,
        "pileup_current": pileup,
        "runtime_sec": round(time.time() - t0, 1),
    }
    (out_dir / "s27_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    make_figure(out_dir, timing, tau, pileup)
    write_report(out_dir, summary)
    print(json.dumps({"out_dir": str(out_dir), "timing_shift_ns": timing["shift_ns"],
                      "tau_eff_shift_ns": tau["shift_ns"],
                      "early_count_fraction": pileup["overall"]["early_count_fraction"],
                      "early_area_fraction": pileup["overall"]["early_area_fraction"],
                      "runtime_sec": summary["runtime_sec"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
