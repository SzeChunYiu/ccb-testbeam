#!/usr/bin/env python3
"""S26 — Two-pulse overlay REALISM: trigger-phase jitter + cross-stave overlays
(reviewer M7 / B-M7).

The mc03/s24 benchmark pinned pulse 1 at 50 ns and used single-stave overlays.
Trigger phase is the manuscript's leading early-peak hypothesis, so a benchmark
with no phase jitter cannot be representative. This study regenerates the
truth-labelled overlays in three configurations and re-runs the SAME matched-
coverage benchmark (single failure definition, failure@80% coverage, common-
subset sigma68) to report how the trad-vs-ML verdict and the numbers move:

  * pinned_same   : pulse 1 at 50 ns, both pulses same stave (mc03/s24 analogue)
  * jitter_same   : pulse 1 phase drawn uniformly over one 10 ns sample
                    (peak lands ~40-60 ns), both pulses same stave
  * jitter_cross  : phase jitter AND cross-stave (pulse 1 in stave i digitized
                    with stave i's kernel, pulse 2 in stave j!=i with stave j's
                    kernel, summed) — the host template (stave i) mismatches
                    pulse 2, a realistic stress the pinned single-stave case
                    never sees.

Truth groups reuse the mc03 pool machinery; digitization sums per-constituent
card-kernel analog waveforms on the 6752 ADC pedestal with the card's 8 ADC RMS
noise (identical for all three configs so the comparison is apples-to-apples).
The traditional fit (s24 card-kernel template, host stave) and the compact ML
(s24 HGB on the raw 18 samples) are the exact s24 methods.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR / "src"))

STAVES = ("B2", "B4", "B6", "B8")
RATES_MHZ = (0.5, 1.5, 3.0)
OVERLAP_FRACTION = 0.7
T1_NOMINAL_NS = 50.0
PHASE_HALF_NS = 5.0          # t1 ~ Uniform(45, 55): peak lands ~40-60 ns
MIN_TRUE_AMP_ADC = 1000.0
SEED = 20260705
N_RECORDS_PER_RATE = 30000
POOL_CAP = 100_000
CONFIGS = ("pinned_same", "jitter_same", "jitter_cross")


def _load_script(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def draw_dt(rng, mean_ns, dt_max_ns):
    u = rng.random()
    trunc = -np.expm1(-dt_max_ns / mean_ns)
    return float(-mean_ns * np.log1p(-u * trunc))


def digitize_sum(mc03, group1, params1, t1, group2, params2, t2, pedestal, noise_rms, ceiling, rng):
    """Sum per-constituent card-kernel analog waveforms + pedestal + noise."""
    w = mc03.analog_waveform_adc(group1["edep"], group1["trel"] + t1, params1)
    if group2 is not None:
        w = w + mc03.analog_waveform_adc(group2["edep"], group2["trel"] + t2, params2)
    wf = pedestal + w + rng.normal(0.0, noise_rms, size=w.shape)
    saturated = bool(np.any(wf >= ceiling))
    return np.clip(wf, 0.0, ceiling), saturated


def generate_config(config, rng_master, pools, dig_params, mc03, pedestal, noise_rms, ceiling,
                    n_records, window_ns):
    """Build a truth-labelled overlay DataFrame + waveform array for one config."""
    import pandas as pd
    stave_names = [s for s in STAVES if any(len(p) for p in pools[s])]
    weights = np.array([sum(len(p) for p in pools[s]) for s in stave_names], dtype=float)
    weights /= weights.sum()

    rows, waves = [], []
    config_idx = CONFIGS.index(config)
    for rate in RATES_MHZ:
        rng = np.random.default_rng(np.random.SeedSequence([SEED, config_idx, int(rate * 1000)]))
        mean_ns = 1000.0 / rate
        for i in range(n_records):
            host = stave_names[int(rng.choice(len(stave_names), p=weights))]
            parity = int(rng.integers(0, 2))
            split = "train" if parity == 0 else "eval"
            bucket1 = pools[host][parity]
            g1 = bucket1[int(rng.integers(0, len(bucket1)))]
            # trigger phase
            if config == "pinned_same":
                t1 = T1_NOMINAL_NS
            else:
                t1 = T1_NOMINAL_NS - PHASE_HALF_NS + rng.random() * (2 * PHASE_HALF_NS)
            is_overlap = int(rng.random() < OVERLAP_FRACTION)
            g2, params2, dt, t2 = None, None, float("nan"), float("nan")
            if is_overlap:
                if config == "jitter_cross":
                    others = [s for s in stave_names if s != host]
                    donor = others[int(rng.integers(0, len(others)))]
                else:
                    donor = host
                bucket2 = pools[donor][parity]
                g2 = bucket2[int(rng.integers(0, len(bucket2)))]
                params2 = dig_params[donor]
                dt_max = window_ns - t1
                dt = draw_dt(rng, mean_ns, dt_max)
                t2 = t1 + dt
            wf, sat = digitize_sum(mc03, g1, dig_params[host], t1, g2, params2, t2,
                                   pedestal, noise_rms, ceiling, rng)
            waves.append(wf)
            rows.append({
                "rate_mhz": rate, "split": split, "stave": host, "is_overlap": is_overlap,
                "t1_true_ns": t1, "dt_true_ns": dt, "saturated": int(sat),
            })
    df = pd.DataFrame(rows)
    return df, np.asarray(waves, dtype=np.float64)


def benchmark(s24, df, waveforms, card, rng, n_boot=400):
    """The s24 matched-coverage benchmark on one config's sample."""
    import pandas as pd
    trad = s24.run_traditional_fit(df, waveforms, card, chunk=256)
    ml = s24.run_ml(df, waveforms)
    d = pd.concat([df.reset_index(drop=True), trad.reset_index(drop=True), ml.reset_index(drop=True)], axis=1)

    train_neg = (d["split"] == "train") & (d["is_overlap"] == 0)
    thetas = {
        "trad": s24.detection_threshold(d.loc[train_neg, "trad_score"].to_numpy()),
        "ml": s24.detection_threshold(d.loc[train_neg, "ml_score"].to_numpy()),
    }
    eval_mask = d["split"] == "eval"
    fail_rows, common_rows = [], []
    for rate in RATES_MHZ:
        pos = d[eval_mask & (d["rate_mhz"] == rate) & (d["is_overlap"] == 1)]
        dt_true = pos["dt_true_ns"].to_numpy(dtype=float)
        conf = {"trad": pos["trad_score"].to_numpy(float), "ml": pos["ml_score"].to_numpy(float)}
        dt_rec = {"trad": pos["trad_dt_ns"].to_numpy(float), "ml": pos["ml_dt_ns"].to_numpy(float)}
        for method in ("trad", "ml"):
            res = s24.evaluate_method(method, conf[method], dt_rec[method], dt_true,
                                      thetas[method], rng=rng, n_boot=n_boot)
            res["rate_mhz"] = rate
            fail_rows.append(res)
        tau_t = np.quantile(np.where(np.isfinite(conf["trad"]), conf["trad"], -np.inf), 1 - s24.TARGET_COVERAGE)
        tau_m = np.quantile(conf["ml"], 1 - s24.TARGET_COVERAGE)
        common = ((np.where(np.isfinite(conf["trad"]), conf["trad"], -np.inf) >= tau_t)
                  & (conf["ml"] >= tau_m)
                  & (conf["trad"] >= thetas["trad"]) & (conf["ml"] >= thetas["ml"])
                  & np.isfinite(dt_rec["trad"]) & np.isfinite(dt_rec["ml"]))
        err_t = dt_rec["trad"][common] - dt_true[common]
        err_m = dt_rec["ml"][common] - dt_true[common]
        common_rows.append({
            "rate_mhz": rate, "n_common": int(common.sum()),
            "sigma68_trad_ns": s24.sigma68(err_t), "sigma68_ml_ns": s24.sigma68(err_m),
        })
    return {"thetas": thetas, "failure_at_coverage": fail_rows, "common_subset": common_rows}


def verdict(fail_rows):
    """Trad vs ML at matched 80% coverage, pooled over rates (lower failure wins)."""
    import numpy as _np
    tf = _np.mean([r["failure_at_80pct_coverage"] for r in fail_rows if r["method"] == "trad"])
    mf = _np.mean([r["failure_at_80pct_coverage"] for r in fail_rows if r["method"] == "ml"])
    return {"trad_mean_failure": float(tf), "ml_mean_failure": float(mf),
            "winner": "trad" if tf < mf else "ml", "margin": float(abs(tf - mf))}


def make_figure(out_dir, results):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    matplotlib.rcParams.update({
        "font.family": "sans-serif", "font.sans-serif": ["Arial", "DejaVu Sans"],
        "pdf.fonttype": 42, "svg.fonttype": "none", "font.size": 7,
        "axes.spines.right": False, "axes.spines.top": False, "legend.frameon": False,
    })
    fig, (ax_a, ax_b) = plt.subplots(1, 2, figsize=(7.2, 3.0))
    x = np.arange(len(CONFIGS))
    tf = [results[c]["verdict"]["trad_mean_failure"] for c in CONFIGS]
    mf = [results[c]["verdict"]["ml_mean_failure"] for c in CONFIGS]
    ax_a.bar(x - 0.18, tf, 0.36, color="#5D6D7E", label="template fit")
    ax_a.bar(x + 0.18, mf, 0.36, color="#D55E00", label="compact ML")
    ax_a.set_xticks(x, [c.replace("_", "\n") for c in CONFIGS])
    ax_a.set_ylabel("mean failure @ 80% coverage")
    ax_a.set_title("a  trad vs ML verdict by config", loc="left")
    ax_a.legend(fontsize=6)

    for c, mk in zip(CONFIGS, ("o", "s", "^")):
        rates = [r["rate_mhz"] for r in results[c]["benchmark"]["common_subset"]]
        st = [r["sigma68_trad_ns"] for r in results[c]["benchmark"]["common_subset"]]
        sm = [r["sigma68_ml_ns"] for r in results[c]["benchmark"]["common_subset"]]
        ax_b.plot(rates, st, mk + "-", color="#5D6D7E", ms=3, lw=0.9)
        ax_b.plot(rates, sm, mk + "--", color="#D55E00", ms=3, lw=0.9, label=c)
    ax_b.set_xlabel("rate (MHz)")
    ax_b.set_ylabel("dt sigma68 (ns), common subset")
    ax_b.set_title("b  dt resolution (solid trad / dashed ML)", loc="left")
    ax_b.legend(fontsize=5.5)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_s26_overlay_realism.png", dpi=400)
    fig.savefig(out_dir / "fig_s26_overlay_realism.pdf")
    plt.close(fig)


def git_commit():
    import subprocess
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True, cwd=str(ROOT_DIR)).strip()
    except Exception:
        return "unknown"


def write_report(out_dir, summary):
    lines = [
        "# S26 — Two-pulse overlay realism: phase jitter + cross-stave (B-M7)",
        "",
        f"- Generated: {summary['generated_utc']}",
        f"- Git commit: `{summary['git_commit']}`",
        f"- Records/rate/config: {summary['n_records_per_rate']}; rates {list(RATES_MHZ)} MHz; "
        f"overlap fraction {OVERLAP_FRACTION}.",
        f"- Phase jitter: t1 ~ Uniform({T1_NOMINAL_NS-PHASE_HALF_NS:.0f}, {T1_NOMINAL_NS+PHASE_HALF_NS:.0f}) ns "
        "(peak lands ~40-60 ns). Cross-stave: pulse 2 donor stave != host, digitized with the donor kernel.",
        "",
        "## Verdict at matched 80% coverage (mean over rates)",
        "",
        "| config | trad failure | ML failure | winner | margin |",
        "|---|---|---|---|---|",
    ]
    for c in CONFIGS:
        v = summary["results"][c]["verdict"]
        lines.append(f"| {c} | {v['trad_mean_failure']:.4f} | {v['ml_mean_failure']:.4f} | "
                     f"**{v['winner']}** | {v['margin']:.4f} |")
    lines += ["", "## Failure @ 80% coverage and common-subset sigma68, per rate", ""]
    for c in CONFIGS:
        lines.append(f"### {c}")
        lines.append("| rate (MHz) | trad fail [CI] | ML fail [CI] | sigma68 trad | sigma68 ML | n common |")
        lines.append("|---|---|---|---|---|---|")
        fr = summary["results"][c]["benchmark"]["failure_at_coverage"]
        cs = {r["rate_mhz"]: r for r in summary["results"][c]["benchmark"]["common_subset"]}
        for rate in RATES_MHZ:
            tr = next(r for r in fr if r["method"] == "trad" and r["rate_mhz"] == rate)
            ml = next(r for r in fr if r["method"] == "ml" and r["rate_mhz"] == rate)
            cc = cs[rate]
            lines.append(
                f"| {rate:g} | {tr['failure_at_80pct_coverage']:.4f} "
                f"[{tr.get('failure_ci_low', float('nan')):.4f}, {tr.get('failure_ci_high', float('nan')):.4f}] | "
                f"{ml['failure_at_80pct_coverage']:.4f} "
                f"[{ml.get('failure_ci_low', float('nan')):.4f}, {ml.get('failure_ci_high', float('nan')):.4f}] | "
                f"{cc['sigma68_trad_ns']:.3f} | {cc['sigma68_ml_ns']:.3f} | {cc['n_common']} |")
        lines.append("")
    lines += [
        "## How the verdict moved vs the pinned single-stave result",
        "",
        summary["movement_text"],
        "",
        "## Caveats",
        "- Digitization sums per-constituent card-kernel analog waveforms + pedestal (6752) + 8 ADC RMS",
        "  noise; identical across configs so the comparison is internal and apples-to-apples. It omits",
        "  the pipeline's per-hit transport smear (0.5 ns << 10 ns), so absolute numbers differ slightly",
        "  from s24; only the config-to-config movement is interpreted.",
        "- Gain is the card placeholder (297 ADC/MeV, arbitrary scale); the A>1000-equivalent boundary is",
        "  not a physical energy. Kernel-family circularity (fit template shares the card kernel) persists",
        "  for the traditional method; the cross-stave config partially breaks it (donor kernel != host).",
        "- Stave/amplitude weights inherit the un-triggered MC truth population (MV3 spectrum discrepancy).",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--mc", required=True)
    ap.add_argument("--out", default=None)
    ap.add_argument("--card", default=None)
    ap.add_argument("--n-records", type=int, default=N_RECORDS_PER_RATE)
    ap.add_argument("--pool-cap", type=int, default=POOL_CAP)
    ap.add_argument("--max-events", type=int, default=0)
    ap.add_argument("--step-size", type=int, default=20000)
    ap.add_argument("--n-boot", type=int, default=400)
    args = ap.parse_args()
    t0 = time.time()

    import uproot
    from ccb_mc_validation.constants import COINC_NS_DEFAULT
    from ccb_mc_validation.digitizer.pipeline import DEFAULT_CARD_PATH, load_digitizer_card

    mc03 = _load_script("mc03_build_overlay_sample", ROOT_DIR / "scripts" / "mc03_build_overlay_sample.py")
    s24 = _load_script("s24_two_pulse_honest_benchmark", ROOT_DIR / "scripts" / "s24_two_pulse_honest_benchmark.py")

    card_path = args.card or str(DEFAULT_CARD_PATH)
    card = load_digitizer_card(card_path)
    dig = card["digitizer"]
    pedestal = float(dig["pedestal_adc"])
    noise_rms = float(dig["noise_adc_rms"])
    ceiling = float(dig["adc_ceiling"])
    dig_params = mc03.stave_digitizer_params(card)
    n_samples = int(dig["n_samples"])
    window_ns = n_samples * float(dig["sample_spacing_ns"])

    out_dir = Path(args.out) if args.out else ROOT_DIR / "reports" / f"s26_overlay_realism_{int(time.time())}"
    out_dir.mkdir(parents=True, exist_ok=True)

    # ---- build truth pools (mc03 machinery) ----
    pools = {s: [[], []] for s in STAVES}
    n_seen = {s: [0, 0] for s in STAVES}
    pool_rng = np.random.default_rng(np.random.SeedSequence([SEED, 7]))
    tree = uproot.open(args.mc)["hibeam"]
    entry_stop = tree.num_entries if args.max_events <= 0 else min(args.max_events, tree.num_entries)
    n_scanned = 0
    for arrays in tree.iterate(list(mc03.mc02.TRUTH_BRANCHES), step_size=args.step_size,
                               entry_stop=entry_stop, library="np"):
        mc03.collect_pool_chunk(arrays, event_offset=n_scanned, mapping="paired",
                                coinc_ns=COINC_NS_DEFAULT, min_amp_adc=MIN_TRUE_AMP_ADC,
                                dig_params=dig_params, pools=pools, n_seen=n_seen,
                                rng=pool_rng, pool_cap=args.pool_cap)
        n_scanned += len(arrays["Sci_bar_LayerID"])
    print(f"[s26] pools ready: { {s: [len(p) for p in pools[s]] for s in STAVES} }", flush=True)

    rng = np.random.default_rng(SEED + 99)
    results = {}
    for config in CONFIGS:
        df, waves = generate_config(config, rng, pools, dig_params, mc03, pedestal, noise_rms,
                                    ceiling, args.n_records, window_ns)
        bench = benchmark(s24, df, waves, card, rng, n_boot=args.n_boot)
        results[config] = {"benchmark": bench, "verdict": verdict(bench["failure_at_coverage"])}
        v = results[config]["verdict"]
        print(f"[s26] {config}: winner={v['winner']} trad={v['trad_mean_failure']:.4f} "
              f"ml={v['ml_mean_failure']:.4f} ({time.time()-t0:.0f}s)", flush=True)

    vp = results["pinned_same"]["verdict"]
    vj = results["jitter_same"]["verdict"]
    vc = results["jitter_cross"]["verdict"]
    movement = (
        f"Pinned single-stave: winner **{vp['winner']}** (trad {vp['trad_mean_failure']:.4f} vs "
        f"ML {vp['ml_mean_failure']:.4f}). Adding phase jitter: winner **{vj['winner']}** "
        f"(trad {vj['trad_mean_failure']:.4f} vs ML {vj['ml_mean_failure']:.4f}). "
        f"Adding cross-stave overlays too: winner **{vc['winner']}** "
        f"(trad {vc['trad_mean_failure']:.4f} vs ML {vc['ml_mean_failure']:.4f}). "
        + ("The matched-coverage verdict is STABLE across the realism axes."
           if vp['winner'] == vj['winner'] == vc['winner']
           else "The matched-coverage verdict FLIPS under the realism axes — the pinned single-stave "
                "result is not representative.")
    )

    summary = {
        "study": "S26",
        "title": "two-pulse overlay realism (phase jitter + cross-stave)",
        "git_commit": git_commit(),
        "generated_utc": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        "mc_file": str(Path(args.mc).resolve()),
        "card": card_path,
        "n_records_per_rate": int(args.n_records),
        "rates_mhz": list(RATES_MHZ),
        "phase_jitter_ns": [T1_NOMINAL_NS - PHASE_HALF_NS, T1_NOMINAL_NS + PHASE_HALF_NS],
        "pools": {s: [len(p) for p in pools[s]] for s in STAVES},
        "results": results,
        "movement_text": movement,
        "runtime_sec": round(time.time() - t0, 1),
    }
    (out_dir / "s26_summary.json").write_text(json.dumps(summary, indent=2, default=float), encoding="utf-8")
    make_figure(out_dir, results)
    write_report(out_dir, summary)
    print(json.dumps({"out_dir": str(out_dir),
                      "verdicts": {c: results[c]["verdict"]["winner"] for c in CONFIGS},
                      "runtime_sec": summary["runtime_sec"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
