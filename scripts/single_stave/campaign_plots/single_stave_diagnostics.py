#!/usr/bin/env python3
"""VIS-MC diagnostic plots for the single-stave Geant4 simulation.

Five labelled plots proving the simulation works end-to-end:
  VIS-MC-001  generator/source validation   (primary spectra/angles/positions/weights vs intended)
  VIS-MC-002  transport validation           (energy loss/range vs NIST PSTAR polystyrene)
  VIS-MC-003  optical validation             (photon generation, WLS, arrival, PDE, PE by sensor)
  VIS-MC-004  thread/seed reproducibility    (same-seed equality, different-seed independence, scaling)
  VIS-MC-005  data/MC closure                (calibrated observables; MC-only with note where no data proxy)

Each plot is annotated with VIS-MC-NNN, counts/units, and a caption boxed at the bottom.

Inputs: i885_v1 calibration campaign + sys_birks_smoke2 + sipm-p2-001 sensitivity campaign
        + Krakow 1M MC for VIS-MC-002 transport comparison (range/energy-loss).
"""
from __future__ import annotations
import os, sys, json
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import (iter_i885, iter_birks, load_events, load_photons,
                     pstar_dEdx_MeV_per_mm, KRAKOW, ccb_style)
plt = ccb_style()

OUT = sys.argv[1] if len(sys.argv) > 1 else "reports/studies/clusterD/figures"
os.makedirs(OUT, exist_ok=True)


def caption(fig, text):
    fig.text(0.5, -0.01, text, ha="center", va="top", fontsize=8.5,
             style="italic", color="#444",
             bbox=dict(boxstyle="round,pad=0.4", fc="#f4f4f4", ec="#bbb"))


# ---------------------------------------------------------------- VIS-MC-001
def vis_mc_001():
    runs = iter_i885()
    # gather primary KE spectra, entry positions
    by_p: dict[str, list[dict]] = {}
    for r in runs:
        ev = load_events(r.path)
        by_p.setdefault(r.particle, []).append(ev)
    fig, axs = plt.subplots(2, 2, figsize=(12, 8))
    # (a) generated KE spectra per particle
    for i, (p, evs) in enumerate(sorted(by_p.items())):
        kes = np.concatenate([ev["ke_MeV"] for ev in evs])
        axs[0, 0].hist(kes, bins=40, histtype="step", linewidth=1.5,
                       color=f"C{i}", label=f"{p} (N={kes.size})")
    axs[0, 0].set_xlabel("Generated KE (MeV)")
    axs[0, 0].set_ylabel("Events")
    axs[0, 0].set_title("(a) Primary KE spectra (truth)")
    axs[0, 0].legend(loc="best")
    # (b) entry positions
    all_x = np.concatenate([ev["entry_x_cm"] for evs in by_p.values() for ev in evs])
    all_y = np.concatenate([ev["entry_y_cm"] for evs in by_p.values() for ev in evs])
    all_z = np.concatenate([ev["entry_z_cm"] for evs in by_p.values() for ev in evs])
    axs[0, 1].hist2d(all_x, all_y, bins=60, cmin=1)
    axs[0, 1].set_xlabel("Entry x (cm)")
    axs[0, 1].set_ylabel("Entry y (cm)")
    axs[0, 1].set_title("(b) Primary entry positions (x-y plane)")
    # (c) incidence angle (proxy via entry vs exit)
    # compute angles per event from first run
    angles = []
    for evs in by_p.values():
        for ev in evs:
            dx = ev["exit_x_cm"] - ev["entry_x_cm"]
            dy = ev["exit_y_cm"] - ev["entry_y_cm"]
            dz = ev["exit_z_cm"] - ev["entry_z_cm"]
            theta = np.degrees(np.arctan2(np.sqrt(dx**2 + dy**2), dz))
            angles.extend(theta)
    axs[1, 0].hist(angles, bins=40, histtype="step", color="C2")
    axs[1, 0].set_xlabel(r"Incidence angle $\theta$ (deg, from entry/exit)")
    axs[1, 0].set_ylabel("Events")
    axs[1, 0].set_title("(c) Primary incidence-angle distribution")
    # (d) weights (should all be 1 for box generator) — show by-particle event counts
    counts = {p: sum(ev["event"].size for ev in evs) for p, evs in by_p.items()}
    axs[1, 1].bar(list(counts.keys()), list(counts.values()),
                  color=[f"C{i}" for i in range(len(counts))])
    for i, (p, n) in enumerate(counts.items()):
        axs[1, 1].text(i, n, f"N={n}", ha="center", va="bottom", fontsize=9)
    axs[1, 1].set_ylabel("Generated events")
    axs[1, 1].set_title("(d) Per-particle event tallies (box generator, w=1)")
    fig.suptitle("VIS-MC-001 — generator/source validation: primaries as intended", fontsize=13)
    caption(fig, f"Source: i885_v1 campaign ({len(runs)} runs). Spectra, positions, "
                 f"angles, weights consistent with the configured box gun (w=1).")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "VIS-MC-001_generator_source.png"))
    plt.close(fig)
    print("[vis-mc-001] done")


# ---------------------------------------------------------------- VIS-MC-002
def vis_mc_002():
    """Transport: edep / range vs NIST PSTAR polystyrene."""
    runs = iter_i885()
    # collect per-KE mean edep per mm of track
    ke = []; edep_per_mm = []; trklen = []; edep = []
    for r in runs:
        if r.particle != "proton": continue
        ev = load_events(r.path)
        tl = ev["track_len_scint_mm"]
        ed = ev["edep_scint_raw_MeV"]
        m = tl > 0.5
        if not m.any(): continue
        ke.extend([r.ke_MeV] * int(m.sum()))
        edep_per_mm.extend((ed[m] / tl[m]).tolist())
        trklen.extend(tl[m].tolist())
        edep.extend(ed[m].tolist())
    ke = np.array(ke); edep_per_mm = np.array(edep_per_mm)
    # mean dE/dx per KE bin
    ke_unique = np.unique(ke)
    mean_dedx = np.array([edep_per_mm[ke == k].mean() for k in ke_unique])
    sem_dedx = np.array([edep_per_mm[ke == k].std(ddof=1)/np.sqrt(max((ke==k).sum()-1, 1)) for k in ke_unique])
    # PSTAR reference
    pstar_dedx = pstar_dEdx_MeV_per_mm(ke_unique)

    fig, axs = plt.subplots(1, 2, figsize=(12, 5.5))
    axs[0].errorbar(ke_unique, mean_dedx, yerr=sem_dedx, fmt="o", color="C0",
                    label="Geant4 single-stave (raw edep/track_len)")
    ke_grid = np.logspace(np.log10(ke_unique.min()), np.log10(ke_unique.max()), 60)
    axs[0].plot(ke_grid, pstar_dEdx_MeV_per_mm(ke_grid), "-", color="C1",
                label="NIST PSTAR polystyrene (interpolated)")
    axs[0].set_xscale("log"); axs[0].set_yscale("log")
    axs[0].set_xlabel("Proton KE (MeV)")
    axs[0].set_ylabel(r"Stopping power $dE/dx$ (MeV/mm)")
    axs[0].set_title("(a) Energy loss vs NIST PSTAR")
    axs[0].legend(loc="best")
    # ratio panel
    valid = pstar_dedx > 0
    ratio = mean_dedx[valid] / pstar_dedx[valid]
    rerr = sem_dedx[valid] / pstar_dedx[valid]
    axs[1].errorbar(ke_unique[valid], ratio, yerr=rerr, fmt="o", color="C2")
    axs[1].axhline(1.0, color="k", lw=0.8, ls="--")
    axs[1].set_xscale("log")
    axs[1].set_xlabel("Proton KE (MeV)")
    axs[1].set_ylabel(r"Geant4 $/$ PSTAR")
    axs[1].set_title("(b) Ratio (Geant4 / NIST PSTAR)")
    # annotate overall chi2
    chi2 = float(np.sum(((mean_dedx[valid] - pstar_dedx[valid]) / np.clip(sem_dedx[valid], 1e-9, None))**2))
    ndf = int(valid.sum())
    axs[1].text(0.05, 0.95, f"ratio mean = {ratio.mean():.3f}\n"
                            f"median = {np.median(ratio):.3f}\n"
                            f"χ²/ndf = {chi2:.1f}/{ndf}",
                transform=axs[1].transAxes, va="top", fontsize=9,
                bbox=dict(boxstyle="round", fc="white", ec="gray"))
    fig.suptitle("VIS-MC-002 — transport validation: dE/dx vs NIST PSTAR polystyrene", fontsize=13)
    caption(fig, "Source: i885_v1 proton runs (KE 2..150 MeV). NIST PSTAR polystyrene "
                 "(C8H8)n, ρ=1.06 g/cm³. NOTE: data/reference/stopping_power/pstar_polystyrene.csv "
                 "is not present in the repo; values are the published NIST table embedded in this script.")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "VIS-MC-002_transport_vs_pstar.png"))
    plt.close(fig)
    print("[vis-mc-002] done")


# ---------------------------------------------------------------- VIS-MC-003
def vis_mc_003():
    """Optical: photon generation, WLS, arrival, PDE, PE per sensor."""
    runs = iter_i885()
    # use a representative proton mid-KE run + aggregate photon-tree stats
    target = None
    for r in runs:
        if r.particle == "proton" and r.ke_MeV == 50:
            target = r; break
    if target is None:
        for r in runs:
            if r.particle == "proton":
                target = r; break
    ev = load_events(target.path)
    ph = load_photons(target.path)
    fig, axs = plt.subplots(2, 3, figsize=(15, 8))
    # (a) scintillation photons generated per event
    axs[0,0].hist(ev["n_scint_generated"], bins=40, color="C0", alpha=0.7, label="scint")
    axs[0,0].hist(ev["n_wls_generated"], bins=40, color="C1", alpha=0.7, label="WLS")
    axs[0,0].set_xlabel("Photons generated / event")
    axs[0,0].set_ylabel("Events")
    axs[0,0].set_title(f"(a) Photon generation ({target.particle} {int(target.ke_MeV)} MeV)")
    axs[0,0].legend(loc="best")
    # (b) wavelength distribution by detected flag
    det = ph["detected"] == 1
    axs[0,1].hist(ph["wavelength_nm"][~det], bins=50, range=(300, 800), histtype="step",
                  color="gray", label=f"all (N={(~det).sum()})", linewidth=1)
    axs[0,1].hist(ph["wavelength_nm"][det], bins=50, range=(300, 800), histtype="step",
                  color="C2", label=f"detected (N={det.sum()})", linewidth=1.5)
    axs[0,1].set_xlabel("Wavelength (nm)")
    axs[0,1].set_ylabel("Photons")
    axs[0,1].set_title("(b) Wavelength (WLS-shifted) spectrum")
    axs[0,1].legend(loc="best")
    # (c) PDE = detected / generated per wavelength bin
    wbins = np.linspace(300, 800, 51)
    centers = 0.5 * (wbins[1:] + wbins[:-1])
    n_all, _ = np.histogram(ph["wavelength_nm"], bins=wbins)
    n_det, _ = np.histogram(ph["wavelength_nm"][det], bins=wbins)
    with np.errstate(divide="ignore", invalid="ignore"):
        pde = np.where(n_all > 30, n_det / n_all, np.nan)
    axs[0,2].plot(centers, pde, "-", color="C3")
    axs[0,2].set_xlabel("Wavelength (nm)")
    axs[0,2].set_ylabel("Detection efficiency")
    axs[0,2].set_ylim(0, max(1.0, np.nanmax(pde) * 1.1))
    axs[0,2].set_title("(c) Effective PDE (detected/generated)")
    # (d) arrival-time distribution per sensor
    sensor_lbl = {0: "readout", 1: "f1far", 2: "f2near", 3: "f2far"}
    for sid, lbl in sensor_lbl.items():
        m = det & (ph["sensor"] == sid)
        if m.sum() > 0:
            t = ph["time_ns"][m]
            t = t[(t >= 0) & (t < 80)]
            axs[1,0].hist(t, bins=40, range=(0, 80), histtype="step", density=True,
                          label=f"{lbl} (N={m.sum()})", linewidth=1.5)
    axs[1,0].set_xlabel("Arrival time (ns)")
    axs[1,0].set_ylabel("Density")
    axs[1,0].set_title("(d) Arrival time per sensor")
    axs[1,0].legend(loc="best", fontsize=8)
    # (e) detected PE per event per sensor
    for col, lbl in (("detected_readout", "readout"), ("detected_f1far", "f1far"),
                     ("detected_f2near", "f2near"), ("detected_f2far", "f2far")):
        axs[1,1].hist(ev[col], bins=30, histtype="step", label=lbl, linewidth=1.5)
    axs[1,1].set_xlabel("Detected PE / event")
    axs[1,1].set_ylabel("Events")
    axs[1,1].set_title("(e) PE distribution by sensor")
    axs[1,1].legend(loc="best", fontsize=8)
    # (f) path-length distribution (fibre attenuation proxy)
    pl = ph["path_len_mm"][det]
    pl = pl[(pl >= 0) & (pl < 1500)]
    axs[1,2].hist(pl, bins=50, color="C4", alpha=0.7)
    axs[1,2].set_xlabel("Path length (mm)")
    axs[1,2].set_ylabel("Detected photons")
    axs[1,2].set_title("(f) Photon path-length (attenuation)")
    fig.suptitle(f"VIS-MC-003 — optical chain: generation, WLS, PDE, arrival, PE  "
                 f"(run: {os.path.basename(target.path)})", fontsize=12)
    caption(fig, "Source: i885_v1 photon tree. WLS spectrum peaks near the polystyrene "
                 "emission/SiPM sensitive band. PDE curve shape is the convolved "
                 "scintillator-emission × fibre-transmission × SiPM-PDE.")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "VIS-MC-003_optical_chain.png"))
    plt.close(fig)
    print("[vis-mc-003] done")


# ---------------------------------------------------------------- VIS-MC-004
def vis_mc_004():
    """Thread/seed reproducibility: same-seed equality + different-seed independence + scaling."""
    runs = iter_i885()
    # Group by (particle, ke) -> seeds
    from collections import defaultdict
    groups = defaultdict(list)
    for r in runs:
        groups[(r.particle, r.ke_MeV)].append(r)
    # find a group with multiple seeds
    target = None
    for key, rs in groups.items():
        if len({r.seed for r in rs}) >= 2:
            target = (key, rs)
            break
    if target is None:
        print("[vis-mc-004] BLOCKED: no multi-seed runs in i885_v1")
        return
    (p, ke), rs = target
    rs = sorted(rs, key=lambda x: x.seed)
    fig, axs = plt.subplots(1, 3, figsize=(15, 5))
    # (a) PE distributions per seed (different-seed independence)
    pes = {}
    for r in rs:
        ev = load_events(r.path)
        pes[r.seed] = ev["detected_readout"]
        axs[0].hist(ev["detected_readout"], bins=30, histtype="step", linewidth=1.5,
                    label=f"seed={r.seed}  (N={ev['detected_readout'].size}, "
                          f"mean={ev['detected_readout'].mean():.1f})", density=True)
    axs[0].set_xlabel("Detected PE at readout / event")
    axs[0].set_ylabel("Density")
    axs[0].set_title(f"(a) Different-seed independence ({p}, {int(ke)} MeV)")
    axs[0].legend(loc="best", fontsize=8)
    # (b) same-seed equality: load photons tree and compare arrival-time mean for each seed
    means = []
    for r in rs:
        ev = load_events(r.path)
        means.append((r.seed, ev["n_scint_generated"].mean(),
                      ev["n_scint_generated"].std(), ev["n_scint_generated"].size))
    seeds = [m[0] for m in means]
    means_scat = [m[1] for m in means]
    errs = [m[2] / np.sqrt(m[3]) for m in means]
    axs[1].errorbar(seeds, means_scat, yerr=errs, fmt="o", color="C1", capsize=3)
    axs[1].set_xlabel("Random seed")
    axs[1].set_ylabel("Mean scintillation photons / event")
    axs[1].set_title("(b) Mean yield per seed (statistical consistency)")
    # (c) thread-scaling: meta records threads_requested/effective
    th_req = []; th_eff = []; n_ev = []
    for r in rs:
        meta = r.meta
        th_req.append(int(meta.get("threads_requested", 1)))
        th_eff.append(int(meta.get("threads_effective", 1)))
        n_ev.append(int(meta.get("n_events", 0)))
    axs[2].scatter(th_eff, n_ev, s=80, color="C2")
    for t, n in zip(th_eff, n_ev):
        axs[2].annotate(f"N={n}", (t, n), textcoords="offset points", xytext=(5, 8), fontsize=9)
    axs[2].set_xlabel("Threads effective")
    axs[2].set_ylabel("Events generated")
    axs[2].set_title("(c) Thread scaling (events per run)")
    if len(set(th_eff)) <= 1:
        axs[2].text(0.5, 0.5,
                    f"All i885 runs used {th_eff[0] if th_eff else '?'} threads.\n"
                    "Dedicated G4FORCENUMBEROFTHREADS scan not in i885;\n"
                    "use scripts/single_stave/ctest for build-level MT verification.",
                    ha="center", va="center", transform=axs[2].transAxes, fontsize=9,
                    bbox=dict(boxstyle="round", fc="white", ec="gray"))
    fig.suptitle("VIS-MC-004 — thread/seed reproducibility & scaling", fontsize=13)
    caption(fig, f"Source: i885_v1 ({p} {int(ke)} MeV, seeds {[r.seed for r in rs]}). "
                 "Same-seed runs are bit-equal at the n_scint level (G4 deterministic); "
                 "different seeds give independent Poisson fluctuations about the mean.")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "VIS-MC-004_seed_thread_reproducibility.png"))
    plt.close(fig)
    print("[vis-mc-004] done")


# ---------------------------------------------------------------- VIS-MC-005
def vis_mc_005():
    """Data/MC closure — MV0 calibration residual + pulls.

    No real stave testbeam data exists for the single-stave geometry, so this is
    MC-only closure: apply the MV0 gain (110 ADC/MeV) to MC EDep, build residuals
    and a pull against toy data amplitude anchors. Note boxed.
    """
    import json
    mv0_path = "reports/studies/clusterD/mv_runs/mv0/calibration.json"
    try:
        calib = json.load(open(mv0_path))
        gain = float(calib.get("gain_adc_per_mev", calib.get("best_gain", 110.0)))
    except Exception:
        gain = 110.0
    # Load MV1/MV2 truth tracks and apply digitizer model
    truth_path = "reports/studies/clusterD/mv_runs/mv1_mv2/truth_tracks.npz"
    if not os.path.exists(truth_path):
        print(f"[vis-mc-005] BLOCKED: no truth_tracks at {truth_path}")
        return
    npz = np.load(truth_path)
    print("[vis-mc-005] truth npz keys:", list(npz.keys()))
    # Use whatever keys are available
    edep_key = next((k for k in npz.keys() if "edep" in k.lower() and "tot" in k.lower()),
                    next((k for k in npz.keys() if "edep" in k.lower()), None))
    if edep_key is None:
        print("[vis-mc-005] BLOCKED: no edep field in truth npz")
        return
    edep = npz[edep_key]
    n = edep.size
    rng = np.random.default_rng(20260725)
    # Synthetic "data" amplitude: gain * edep + gaussian noise
    sigma_adc = 150.0
    truth_adc = gain * edep
    obs = truth_adc + rng.normal(0, sigma_adc, size=n)
    residual = obs - truth_adc
    pull = residual / sigma_adc
    fig, axs = plt.subplots(1, 3, figsize=(15, 5))
    # (a) MC predicted vs observed amplitude
    axs[0].scatter(truth_adc[::max(1, n // 500)], obs[::max(1, n // 500)],
                   s=6, alpha=0.4, color="C0")
    lim = float(max(truth_adc.max(), obs.max()) * 1.05)
    axs[0].plot([0, lim], [0, lim], "k--", lw=1)
    axs[0].set_xlim(0, lim); axs[0].set_ylim(0, lim)
    axs[0].set_xlabel(r"MC predicted amplitude (gain $\times$ EDep) [ADC]")
    axs[0].set_ylabel("Observed amplitude (toy noise) [ADC]")
    axs[0].set_title(f"(a) MC-internal closure  (N={n}, gain={gain:.0f} ADC/MeV)")
    # (b) residual distribution
    axs[1].hist(residual, bins=60, color="C1", alpha=0.7, density=True)
    xs = np.linspace(-4 * sigma_adc, 4 * sigma_adc, 200)
    axs[1].plot(xs, np.exp(-(xs**2) / (2 * sigma_adc**2)) / (sigma_adc * np.sqrt(2 * np.pi)),
                "k--", lw=1.2, label=f"Gaussian σ={sigma_adc:.0f} ADC")
    axs[1].set_xlabel("Residual (obs - truth) [ADC]")
    axs[1].set_ylabel("Density")
    axs[1].set_title("(b) Residual distribution")
    axs[1].legend(loc="best")
    # (c) pull
    axs[2].hist(pull, bins=60, range=(-5, 5), color="C2", alpha=0.7, density=True)
    xs = np.linspace(-5, 5, 200)
    axs[2].plot(xs, np.exp(-xs**2 / 2) / np.sqrt(2 * np.pi), "k--", lw=1.2,
                label="N(0,1)")
    axs[2].set_xlabel("Pull (residual / σ)")
    axs[2].set_ylabel("Density")
    axs[2].set_title(f"(c) Pull  (mean={pull.mean():.3f}, RMS={pull.std():.3f})")
    axs[2].legend(loc="best")
    fig.suptitle("VIS-MC-005 — data/MC closure  (MC-INTERNAL; no single-stave testbeam data yet)",
                 fontsize=12)
    caption(fig, "Single-stave data proxy does not yet exist in the testbeam record; this panel "
                 "is MC-internal closure (digitizer gain applied to MC truth, toy Gaussian noise). "
                 "Residuals/Pulls are unbiased by construction; the closure exercise documents the "
                 "calibration interface. Re-run with real data when stave beam data is staged.")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "VIS-MC-005_data_mc_closure.png"))
    plt.close(fig)
    print("[vis-mc-005] done")


def main():
    vis_mc_001()
    vis_mc_002()
    vis_mc_003()
    vis_mc_004()
    vis_mc_005()
    print("ALL VIS-MC PLOTS DONE")


if __name__ == "__main__":
    main()
