#!/usr/bin/env python3
"""Issue #885 campaign plotting for the CCB single-stave Geant4 outputs.

Reads the per-point ROOT files written by slurm/submit_calibration.sh (one
immutable config -> stave_<part>_<E>MeV_x<hx>_s<seed>.root + .meta.json) and
produces the issue's requested plots:

  P1 KE vs Birks-visible light produced      (mean edep_scint_MeV)
  P2 KE vs scintillation photons produced    (mean n_scint_generated)
  P3 deposited energy vs light produced      (edep_scint_raw vs edep_scint, Birks linearity)
  P4 KE vs SiPM-collected light              (mean pe_sat_readout, the readout channel)
  P5 calibration curves                      (pe_sat_readout vs KE, linear fit per particle)
  P6 attenuation                             (pe_sat_readout vs distance from readout, 30/80 MeV)
  P7 timing                                  (mean photon arrival time at readout vs distance)
  P8 stopping power proxy                    (mean track_len_scint_mm vs KE)

Works on whatever subset of files has landed: titles are stamped with the
config coverage (N_expected estimated from sibling seeds, or --expected).

Config (particle, energy, hit_x, seed) is parsed from the FILENAME (the driver
names files deterministically); ke_MeV/particle in the events tree are used as
a cross-check. distance_from_readout = READOUT_END_X_CM - hit_x (readout SiPM
at +x end, kStaveHalfX=25 cm -- both CLI-overridable, no magic numbers).

Usage:
  python3 scripts/single_stave/plot_i885_campaign.py \
      --indir /projects/hep/fs10/shared/nnbar/billy/ccb-runs/i885_v1 \
      --outdir geant4/single_stave/results/i885_v1 \
      [--expected 72] [--readout-end-x-cm 25.0]
"""
from __future__ import annotations
import argparse, glob, json, re, sys
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
import tempfile, os
os.environ.setdefault("MPLCONFIGDIR", tempfile.gettempdir())
matplotlib.use("Agg")
import matplotlib.pyplot as plt

FNAME_RE = re.compile(r"stave_(proton|deuteron)_(\d+)MeV_x(-?\d+(?:\.\d+)?)_s(\d+)\.root$")
COLORS = {"proton": "#1f77b4", "deuteron": "#d62728"}
MARKERS = {"proton": "o", "deuteron": "s"}


def sem(x):
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    n = len(x)
    if n < 2:
        return float("nan")
    return float(np.std(x, ddof=1) / np.sqrt(n))


def agg(df, col):
    """Return (mean, sem, n) of col over all rows in df."""
    s = df[col].to_numpy(dtype=float)
    s = s[np.isfinite(s)]
    if len(s) == 0:
        return float("nan"), float("nan"), 0
    return float(np.mean(s)), sem(s), len(s)


def read_events(root_path):
    import uproot  # lazy import; only needed when files exist
    with uproot.open(root_path) as f:
        if "events" not in f:
            return None
        df = f["events"].arrays(library="pd")
    return df


def read_readout_times(root_path):
    """Mean + spread of arrival time_ns at the readout sensor (detected only)."""
    try:
        import uproot
    except Exception:
        return None
    try:
        with uproot.open(root_path) as f:
            if "photons" not in f:
                return None
            # only need readout-sensor detected photons: sensor==0, detected==1
            df = f["photons"].arrays(["sensor", "detected", "time_ns"],
                                     library="pd")
    except Exception:
        return None
    sel = df[(df["sensor"] == 0) & (df["detected"] == 1)]["time_ns"].to_numpy(dtype=float)
    sel = sel[np.isfinite(sel)]
    if len(sel) == 0:
        return None
    return float(np.mean(sel)), float(np.std(sel)), len(sel)


def collect(indir, readout_end_x_cm, want_timing):
    rows = []
    timing = []
    # only read COMPLETE files: RunAction writes the .meta.json sidecar LAST, so a
    # .root without its sibling .meta.json is still being written and would crash
    # uproot. This makes the plotter safe to run while the array is still draining.
    for root in sorted(glob.glob(str(Path(indir) / "*.root"))):
        if not Path(root + ".meta.json").is_file():
            continue
        m = FNAME_RE.search(Path(root).name)
        if not m:
            continue
        part, e, hx, seed = m.group(1), int(m.group(2)), float(m.group(3)), int(m.group(4))
        df = read_events(root)
        if df is None or len(df) == 0:
            print(f"  SKIP (no events tree): {root}", file=sys.stderr)
            continue
        nev = len(df)
        for col in ["edep_scint_MeV", "edep_scint_raw_MeV", "n_scint_generated",
                    "pe_sat_readout", "detected_readout", "arrival_readout",
                    "track_len_scint_mm", "exit_x_cm", "exit_z_cm"]:
            if col not in df.columns:
                df[col] = np.nan
        em, es, _ = agg(df, "edep_scint_MeV")
        rm, rs, _ = agg(df, "edep_scint_raw_MeV")
        nsm, nss, _ = agg(df, "n_scint_generated")
        pm, ps, _ = agg(df, "pe_sat_readout")
        drm, drs, _ = agg(df, "detected_readout")
        tlm, tls, _ = agg(df, "track_len_scint_mm")
        rows.append(dict(particle=part, energy_MeV=e, hit_x_cm=hx, seed=seed,
                         dist_from_readout_cm=readout_end_x_cm - hx,
                         n_events=nev,
                         edep_scint_MeV_mean=em, edep_scint_MeV_sem=es,
                         edep_scint_raw_MeV_mean=rm, edep_scint_raw_MeV_sem=rs,
                         n_scint_generated_mean=nsm, n_scint_generated_sem=nss,
                         pe_sat_readout_mean=pm, pe_sat_readout_sem=ps,
                         detected_readout_mean=drm, detected_readout_sem=drs,
                         track_len_scint_mm_mean=tlm, track_len_scint_mm_sem=tls))
        if want_timing:
            tr = read_readout_times(root)
            if tr:
                timing.append(dict(particle=part, energy_MeV=e, hit_x_cm=hx,
                                   dist_from_readout_cm=readout_end_x_cm - hx,
                                   seed=seed,
                                   mean_time_ns=tr[0], std_time_ns=tr[1],
                                   n_detected_readout=tr[2]))
    if not rows:
        sys.exit(f"no readable stave_*.root outputs found in {indir}")
    return pd.DataFrame(rows), (pd.DataFrame(timing) if timing else None)


def linfit(x, y, w=None):
    x = np.asarray(x, dtype=float); y = np.asarray(y, dtype=float)
    m = np.isfinite(x) & np.isfinite(y)
    x, y = x[m], y[m]
    if len(x) < 2:
        return None
    a, b = np.polyfit(x, y, 1)
    yp = a * x + b
    ss_res = float(np.sum((y - yp) ** 2))
    ss_tot = float(np.sum((y - np.mean(y)) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")
    return dict(slope=float(a), intercept=float(b), r2=r2, n=len(x))


def save(fig, path):
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)
    print("  wrote", path)



def write_summary(df, fits, out, readout_end_x_cm, hx0, expected):
    """Data-driven SUMMARY.md so the PR self-updates when the array completes."""
    g = df.groupby(["particle", "energy_MeV"]).agg(
        vis=("edep_scint_MeV_mean", "mean"), raw=("edep_scint_raw_MeV_mean", "mean"),
        pe=("pe_sat_readout_mean", "mean"), tl=("track_len_scint_mm_mean", "mean"),
        nsc=("n_scint_generated_mean", "mean")).reset_index()
    g["quench"] = g.vis / g.raw
    n_main = len(df[df["hit_x_cm"] == hx0])
    species = sorted(g["particle"].unique())
    e_range = f"{int(g.energy_MeV.min())}-{int(g.energy_MeV.max())}"
    status = (f"COMPLETE ({n_main} main-grid files)" if (not expected or n_main >= expected)
              else f"PARTIAL ({n_main}/{expected} main-grid files)")
    lines = []
    lines.append("# Issue #885 -- single-stave proton/deuteron calibration campaign (v1)\n")
    lines.append(f"Status: **{status}** -- auto-regenerated by `plot_i885_campaign.py --summary`. "
                 f"Covered: {', '.join(species)} @ {e_range} MeV (see `i885_per_config.csv` for every point).\n")
    lines.append("## Campaign (`slurm/points_i885_campaign.csv`, 72 points)\n")
    lines.append("- particles: proton, deuteron")
    lines.append("- KE @ hit_x=0: 2,5,8,12,20,30,50,80,120,150 MeV")
    lines.append("- attenuation/timing: 30 & 80 MeV at entry 5/10/30/45 cm from +x readout (hit_x=25-d)")
    lines.append("- 2 seeds (101,102) x 500 ev/point; readout SiPM at +x end (kStaveHalfX=25 cm)\n")
    lines.append("## Seed-averaged physics (this run)\n")
    lines.append("| species | KE (MeV) | raw edep (MeV) | Birks-visible (MeV) | quench vis/raw | track len (mm) | SiPM pe |")
    lines.append("|---------|---------:|---------------:|--------------------:|---------------:|---------------:|--------:|")
    for _, r in g.sort_values(["particle", "energy_MeV"]).iterrows():
        lines.append(f"| {r.particle} | {int(r.energy_MeV)} | {r.raw:.3f} | {r.vis:.3f} | {r.quench:.3f} | {r.tl:.3f} | {r.pe:.1f} |")
    lines.append("")
    if {"proton", "deuteron"}.issubset(set(species)):
        ke_min = max(int(g[g.particle=="proton"].energy_MeV.min()), int(g[g.particle=="deuteron"].energy_MeV.min()))
        try:
            p2 = g[(g.particle=="proton")&(g.energy_MeV==ke_min)].iloc[0]
            d2 = g[(g.particle=="deuteron")&(g.energy_MeV==ke_min)].iloc[0]
            lines.append(f"At {ke_min} MeV the **deuteron is quenched more than the proton** "
                         f"(quench {d2.quench:.3f} vs {p2.quench:.3f}, d/p={d2.quench/p2.quench:.2f}) -- "
                         "its higher dE/dx Bragg deposit suppresses more scintillation, the reason "
                         "separate p/d calibration curves are required.\n")
        except Exception:
            pass
    lines.append("## Calibration fits (`i885_fits.json`)\n")
    for k, v in (fits or {}).items():
        if k.startswith("pe_sat"):
            lines.append(f"- `{k}`: slope={v.get('slope'):.4g} intercept={v.get('intercept'):.4g} R^2={v.get('r2'):.4f} n={v.get('n')}")
    lines.append("\n## Plots: P1 KE vs Birks-visible; P2 scint photons; P3 raw vs Birks light; "
                 "P4 SiPM pe vs KE; P5/P5b calibration fits; P6 attenuation; P7 timing; P8 track length.\n")
    lines.append("## Regenerate\n```bash\n# GCC/12.3.0 + Geant4/11.2.2 + SciPy-bundle loaded, from geant4/single_stave/")
    lines.append(f"python3 ../../scripts/single_stave/plot_i885_campaign.py --indir <ccb-runs/i885_v1> "
                 "--outdir results/i885_v1 --expected 72 --summary")
    lines.append("```")
    (Path(out) / "SUMMARY.md").write_text("\n".join(lines))
    print("  wrote", Path(out) / "SUMMARY.md")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--indir", required=True, help="dir of stave_*.root outputs")
    ap.add_argument("--outdir", required=True, help="dir for plots + csv + json")
    ap.add_argument("--expected", type=int, default=0, help="expected #files (for PARTIAL stamp; 0=guess)")
    ap.add_argument("--readout-end-x-cm", type=float, default=25.0,
                    help="x of the +x readout end (= kStaveHalfX). dist = this - hit_x")
    ap.add_argument("--no-timing", action="store_true", help="skip photons-tree timing (faster)")
    ap.add_argument("--summary", action="store_true", help="(re)write SUMMARY.md from the collected data")
    args = ap.parse_args()

    out = Path(args.outdir); out.mkdir(parents=True, exist_ok=True)
    df, timing = collect(args.indir, args.readout_end_x_cm, want_timing=not args.no_timing)
    df.to_csv(out / "i885_per_config.csv", index=False)
    print(f"collected {len(df)} configs across {int(df['n_events'].sum())} events")

    # default-hit-x scan = the KE-scan subset (hit_x == its mode, typically 0)
    hx0 = float(df["hit_x_cm"].mode().iloc[0])
    scan = df[df["hit_x_cm"] == hx0].copy()
    if args.expected:
        partial = f"PARTIAL {len(scan)//2}/{args.expected//2}" if (len(scan) // 2) < (args.expected // 2) else "COMPLETE"
    else:
        partial = f"{len(scan)} configs"
    fits = {}

    # P1 KE vs Birks-visible light produced
    fig, ax = plt.subplots(figsize=(6.5, 4.8))
    for p in ["proton", "deuteron"]:
        g = scan[scan["particle"] == p].sort_values("energy_MeV")
        if not len(g):
            continue
        ax.errorbar(g["energy_MeV"], g["edep_scint_MeV_mean"], yerr=g["edep_scint_MeV_sem"],
                    c=COLORS[p], marker=MARKERS[p], ls="-", lw=1.3, capsize=3, label=f"{p} ({len(g)} files)")
    ax.set_xlabel("kinetic energy (MeV)")
    ax.set_ylabel("Birks-visible light, edep_scint_MeV")
    ax.set_title(f"P1  KE vs Birks-visible light produced  [{partial}]")
    ax.legend(); ax.grid(alpha=0.3)
    save(fig, out / "P1_KE_vs_Birks_visible_light.png")

    # P2 KE vs scintillation photons produced
    fig, ax = plt.subplots(figsize=(6.5, 4.8))
    for p in ["proton", "deuteron"]:
        g = scan[scan["particle"] == p].sort_values("energy_MeV")
        if not len(g):
            continue
        ax.errorbar(g["energy_MeV"], g["n_scint_generated_mean"], yerr=g["n_scint_generated_sem"],
                    c=COLORS[p], marker=MARKERS[p], ls="-", lw=1.3, capsize=3, label=p)
    ax.set_xlabel("kinetic energy (MeV)")
    ax.set_ylabel("scintillation photons generated (n_scint_generated)")
    ax.set_title(f"P2  KE vs scintillation light produced  [{partial}]")
    ax.legend(); ax.grid(alpha=0.3)
    save(fig, out / "P2_KE_vs_scint_photons.png")

    # P3 deposited energy (raw) vs Birks-visible light
    fig, ax = plt.subplots(figsize=(6.5, 4.8))
    for p in ["proton", "deuteron"]:
        g = scan[scan["particle"] == p]
        if not len(g):
            continue
        ax.errorbar(g["edep_scint_raw_MeV_mean"], g["edep_scint_MeV_mean"],
                    xerr=g["edep_scint_raw_MeV_sem"], yerr=g["edep_scint_MeV_sem"],
                    c=COLORS[p], marker=MARKERS[p], ls="", capsize=3, label=p)
    lims = [0, max(scan["edep_scint_raw_MeV_mean"].max(), scan["edep_scint_MeV_mean"].max()) * 1.05]
    ax.plot(lims, lims, "k--", lw=0.8, alpha=0.5, label="y=x (no quenching)")
    ax.set_xlabel("deposited energy, edep_scint_raw_MeV (unquenched)")
    ax.set_ylabel("Birks-visible light, edep_scint_MeV")
    ax.set_title(f"P3  deposited energy vs Birks-visible light  [{partial}]")
    ax.legend(); ax.grid(alpha=0.3)
    save(fig, out / "P3_raw_edep_vs_Birks_light.png")

    # P4 KE vs SiPM-collected light (readout channel)
    fig, ax = plt.subplots(figsize=(6.5, 4.8))
    for p in ["proton", "deuteron"]:
        g = scan[scan["particle"] == p].sort_values("energy_MeV")
        if not len(g):
            continue
        ax.errorbar(g["energy_MeV"], g["pe_sat_readout_mean"], yerr=g["pe_sat_readout_sem"],
                    c=COLORS[p], marker=MARKERS[p], ls="-", lw=1.3, capsize=3, label=p)
    ax.set_xlabel("kinetic energy (MeV)")
    ax.set_ylabel("SiPM collected photoelectrons (pe_sat_readout)")
    ax.set_title(f"P4  KE vs SiPM-collected light (readout)  [{partial}]")
    ax.legend(); ax.grid(alpha=0.3)
    save(fig, out / "P4_KE_vs_SiPM_pe.png")

    # P5 calibration curves: pe_sat_readout vs KE, linear fit per particle
    fig, ax = plt.subplots(figsize=(6.5, 4.8))
    for p in ["proton", "deuteron"]:
        g = scan[scan["particle"] == p].sort_values("energy_MeV")
        if len(g) < 2:
            continue
        seedmean = g.groupby("energy_MeV").agg(
            y=("pe_sat_readout_mean", "mean"), ye=("pe_sat_readout_sem", "mean")).reset_index()
        ax.errorbar(seedmean["energy_MeV"], seedmean["y"], yerr=seedmean["ye"],
                    c=COLORS[p], marker=MARKERS[p], ls="", capsize=3, label=f"{p} data")
        f = linfit(g["energy_MeV"], g["pe_sat_readout_mean"])
        if f:
            fits[f"pe_sat_readout_vs_KE_{p}"] = f
            xs = np.linspace(g["energy_MeV"].min(), g["energy_MeV"].max(), 50)
            ax.plot(xs, f["slope"] * xs + f["intercept"], c=COLORS[p], lw=1.2,
                    label=f"{p} fit: {f['slope']:.3g}·KE+{f['intercept']:.3g}  R²={f['r2']:.3f}")
    ax.set_xlabel("kinetic energy (MeV)")
    ax.set_ylabel("SiPM collected photoelectrons (pe_sat_readout)")
    ax.set_title(f"P5  calibration: SiPM pe vs KE  [{partial}]")
    ax.legend(fontsize=8); ax.grid(alpha=0.3)
    save(fig, out / "P5_calibration_pe_vs_KE.png")

    # P5b Birks-visible light vs KE calibration
    fig, ax = plt.subplots(figsize=(6.5, 4.8))
    for p in ["proton", "deuteron"]:
        g = scan[scan["particle"] == p].sort_values("energy_MeV")
        if len(g) < 2:
            continue
        seedmean = g.groupby("energy_MeV").agg(
            y=("edep_scint_MeV_mean", "mean"), ye=("edep_scint_MeV_sem", "mean")).reset_index()
        ax.errorbar(seedmean["energy_MeV"], seedmean["y"], yerr=seedmean["ye"],
                    c=COLORS[p], marker=MARKERS[p], ls="", capsize=3, label=f"{p} data")
        f = linfit(g["energy_MeV"], g["edep_scint_MeV_mean"])
        if f:
            fits[f"edep_scint_MeV_vs_KE_{p}"] = f
            xs = np.linspace(g["energy_MeV"].min(), g["energy_MeV"].max(), 50)
            ax.plot(xs, f["slope"] * xs + f["intercept"], c=COLORS[p], lw=1.2,
                    label=f"{p}: {f['slope']:.3g}·KE+{f['intercept']:.3g}  R²={f['r2']:.3f}")
    ax.set_xlabel("kinetic energy (MeV)")
    ax.set_ylabel("Birks-visible light (edep_scint_MeV)")
    ax.set_title(f"P5b  calibration: Birks light vs KE  [{partial}]")
    ax.legend(fontsize=8); ax.grid(alpha=0.3)
    save(fig, out / "P5b_calibration_Birks_vs_KE.png")

    # P6 attenuation: pe_sat_readout vs distance from readout (30, 80 MeV)
    att_energies = sorted([e for e in df["energy_MeV"].unique()
                           if e in (30, 80) and len(df[(df["energy_MeV"] == e) & (df["hit_x_cm"] != hx0)]) > 0])
    if att_energies:
        fig, ax = plt.subplots(figsize=(6.5, 4.8))
        for p in ["proton", "deuteron"]:
            for e in att_energies:
                g = df[(df["particle"] == p) & (df["energy_MeV"] == e)].copy()
                seedmean = g.groupby("dist_from_readout_cm").agg(
                    y=("pe_sat_readout_mean", "mean"), ye=("pe_sat_readout_sem", "mean")).reset_index().sort_values("dist_from_readout_cm")
                ax.errorbar(seedmean["dist_from_readout_cm"], seedmean["y"], yerr=seedmean["ye"],
                            c=COLORS[p], marker=MARKERS[p], ls="-", lw=1.1, capsize=2,
                            label=f"{p} {e} MeV")
        ax.set_xlabel("distance from readout end (cm)")
        ax.set_ylabel("SiPM collected photoelectrons (pe_sat_readout)")
        ax.set_title(f"P6  attenuation: SiPM pe vs distance from readout  [{partial}]")
        ax.legend(fontsize=8); ax.grid(alpha=0.3)
        save(fig, out / "P6_attenuation.png")

    # P7 timing: mean arrival time at readout vs distance (photons tree)
    if timing is not None and len(timing):
        fig, ax = plt.subplots(figsize=(6.5, 4.8))
        for p in ["proton", "deuteron"]:
            for e in att_energies or [30, 80]:
                g = timing[(timing["particle"] == p) & (timing["energy_MeV"] == e)]
                if not len(g):
                    continue
                seedmean = g.groupby("dist_from_readout_cm")["mean_time_ns"].mean().reset_index().sort_values("dist_from_readout_cm")
                ax.plot(seedmean["dist_from_readout_cm"], seedmean["mean_time_ns"],
                        c=COLORS[p], marker=MARKERS[p], ls="-", lw=1.1, label=f"{p} {e} MeV")
        ax.set_xlabel("distance from readout end (cm)")
        ax.set_ylabel("mean photon arrival time at readout (ns)")
        ax.set_title(f"P7  timing: arrival time vs distance from readout  [{partial}]")
        ax.legend(fontsize=8); ax.grid(alpha=0.3)
        save(fig, out / "P7_timing_vs_distance.png")
    else:
        print("  (no timing data; skipping P7)")

    # P8 stopping proxy: track_len_scint_mm vs KE
    fig, ax = plt.subplots(figsize=(6.5, 4.8))
    for p in ["proton", "deuteron"]:
        g = scan[scan["particle"] == p].sort_values("energy_MeV")
        if not len(g):
            continue
        ax.errorbar(g["energy_MeV"], g["track_len_scint_mm_mean"], yerr=g["track_len_scint_mm_sem"],
                    c=COLORS[p], marker=MARKERS[p], ls="-", lw=1.3, capsize=3, label=p)
    ax.set_xlabel("kinetic energy (MeV)")
    ax.set_ylabel("track length in scintillator (mm)")
    ax.set_title(f"P8  stopping proxy: scint track length vs KE  [{partial}]")
    ax.legend(); ax.grid(alpha=0.3)
    save(fig, out / "P8_track_length_vs_KE.png")

    with open(out / "i885_fits.json", "w") as f:
        json.dump({"fits": fits, "readout_end_x_cm": args.readout_end_x_cm,
                   "default_hit_x_cm": hx0, "n_configs": int(len(df)),
                   "n_events_total": int(df["n_events"].sum())}, f, indent=2)
    print("  wrote", out / "i885_fits.json")
    if args.summary:
        write_summary(df, fits, out, args.readout_end_x_cm, hx0, args.expected)
    print("DONE")


if __name__ == "__main__":
    main()
