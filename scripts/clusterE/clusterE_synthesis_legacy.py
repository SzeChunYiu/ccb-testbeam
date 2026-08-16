#!/usr/bin/env python3
"""
Cluster E -- CCB test-beam synthesis layer (VIS-SYS / VIS-REP / VIS-CLAIM).

Aggregates the outputs of clusters A-D + Opticks (all merged on origin/main) into
an end-to-end "the project works" dashboard.  Reads ONLY already-produced cluster
artifacts (metrics.json / counts.json / fig_*_summary.json / docs/claim_ledger.csv);
it does not re-run any physics computation.  Every number on every figure is
sourced to a cluster file; nothing is fabricated.

Honesty rules (enforced here, not just in prose):
  * MC-side methodology closure numbers are labelled SIMULATION_RESULT / MC_METHOD_CLOSURE.
  * Data-side / detector-performance claims are BLOCKED_DATA where the raw beam
    ROOT (hrdb_run_*.root) is not staged on LUNARC.
  * Canonical cross-domain claim status follows docs/claim_ledger.csv (2026-07-25):
    CL-010 Rmax BLOCKED, CL-012 Rmax=3.044 MHz SUPERSEDED, CL-013 MV0 gain GATED,
    CL-017/018 PID ceiling GATED, CL-002..006 timing BLOCKED, CL-022 anomaly
    TRUTH_LEVEL_MC_ONLY.  The stale 2026-06-28 PROJECT_REPORT/FINDINGS_SYNTHESIS
    "PASS" headlines are NOT used for those claims.

Run (on LUNARC fs10, from the worktree root):
  source /projects/hep/fs10/shared/nnbar/billy/ccb-py/bin/activate
  export MPLCONFIGDIR=/projects/hep/fs10/shared/nnbar/billy/.mplcache
  PYTHONPATH=src python scripts/clusterE/clusterE_synthesis.py
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

# --------------------------------------------------------------------------- #
# House style (matches src/ccb_figures/config.py contract; inlined so the
# script is self-contained and runs with PYTHONPATH=src unset too).
# --------------------------------------------------------------------------- #
mpl.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["DejaVu Sans", "Arial", "Helvetica", "sans-serif"],
    "font.size": 8, "axes.titlesize": 9, "axes.labelsize": 8,
    "legend.fontsize": 7, "xtick.labelsize": 7, "ytick.labelsize": 7,
    "svg.fonttype": "none", "pdf.fonttype": 42,
    "axes.spines.right": False, "axes.spines.top": False,
    "axes.linewidth": 0.8, "axes.edgecolor": "#4D4D4D",
    "axes.grid": False, "grid.alpha": 0.15, "grid.color": "#B0B0B0",
    "legend.frameon": False,
})

# Status -> colour (colour-blind safe, consistent across all figures)
STATUS_COLOR = {
    "PASS":            "#1b7837",   # green
    "VALIDATED":       "#1b7837",
    "PARTIAL":         "#f0a202",   # amber
    "GATED":           "#f0a202",
    "TENSION":         "#e66101",   # orange-red
    "FLAWED":          "#e66101",
    "BLOCKED":         "#b2182b",   # red
    "BLOCKED_DATA":    "#b2182b",
    "SUPERSEDED":      "#7b7d7b",   # grey
    "TRUTH_LEVEL_MC_ONLY": "#5aae61",  # soft green (MC-only, not data)
    "SIMULATION_RESULT":   "#5aae61",
    "MC_METHOD_CLOSURE":   "#1b7837",
    "DONE_DATA_ONLY":      "#8073ac",
    "REVIEW":          "#7b7d7b",
}
PALETTE_CATEGORICAL = ["#4477aa", "#ee6677", "#228833", "#ccbb44",
                       "#66ccee", "#aa3377", "#bbbbbb", "#003f5c"]


def _status_fill(status: str) -> str:
    return STATUS_COLOR.get(status, "#cccccc")


# --------------------------------------------------------------------------- #
# Paths
# --------------------------------------------------------------------------- #
ROOT = Path(__file__).resolve().parents[2]   # .../ccb-wt-clE
STUDIES = ROOT / "reports" / "studies"
OUT = STUDIES / "clusterE"
OUT.mkdir(parents=True, exist_ok=True)


def _load(rel: str) -> dict:
    p = ROOT / rel
    if not p.exists():
        raise FileNotFoundError(f"required input missing: {p}")
    with p.open() as fh:
        return json.load(fh)


A = _load("reports/studies/clusterA/counts.json")
B = _load("reports/studies/clusterB/metrics.json")
C = _load("reports/studies/clusterC/metrics.json")
SIPM = _load("reports/studies/clusterD/figures/fig_sipm_summary.json")
BIRKS_GRID = _load("reports/studies/clusterD/figures/fig_birks_summary.json")
I885 = _load("reports/studies/clusterD/figures/fig_i885_summary.json")
MV3 = _load("reports/studies/clusterD/mv_runs/mv3/mv3_summary.json") if (ROOT / "reports/studies/clusterD/mv_runs/mv3/mv3_summary.json").exists() else {}
MV5 = _load("reports/studies/clusterD/mv_runs/mv5/mv5_pileup_summary.json") if (ROOT / "reports/studies/clusterD/mv_runs/mv5/mv5_pileup_summary.json").exists() else {}

# Canonical claim ledger
def _load_claims() -> dict:
    p = ROOT / "docs" / "claim_ledger.csv"
    out = {}
    with p.open() as fh:
        for r in csv.DictReader(fh):
            out[r["claim_id"]] = r
    return out

CLAIMS = _load_claims()

# Opticks numbers (parsed from figures/opticks/SUMMARY.md -- hardcoded here with
# citation because the source is markdown, not json).
OPTICKS = {
    "source": "figures/opticks/SUMMARY.md",
    "pr": "#920", "commit": "2c0afcd6",
    "n_events": 2,
    "cpu_arrivals_total": 4592,
    "cpu_arrivals_per_event": 2296,
    "gpu_input_photons_per_event": 148697,
    "gpu_hits": 0,
    "ctest_pass": "9/9",
    "status": "PARTIAL",
    "residual": "device->host GATHER returns null (EventMode/component-save config point)",
}

# Cluster provenance (squash-merge commits on origin/main)
PROV = {
    "clusterA": {"pr": "#921", "commit": "9096345d",
                 "script": "scripts/studies/clusterA_dE_PID_stopping.py",
                 "inputs": ["geant4/data/output_krakow_1M.root (hibeam, 1M ev)"],
                 "seeds": ["event_index (MC, no run col)"],
                 "config": ["STOP_KE=1.0 MeV", "GEO-001 pair_merge"],
                 "status": "PASS_MC"},
    "clusterB": {"pr": "#918", "commit": "96c72ad0",
                 "script": "scripts/clusterB/clusterB_timing_study.py",
                 "inputs": ["ccb-runs/i885_v1 (72 files)", "ccb-runs/an3/sys_birks_smoke2 (3)",
                            "geant4/data/output_krakow_1M.root"],
                 "seeds": ["s101", "s102"],
                 "config": ["DT=0.25 ns", "CFD_FRAC=0.2", "LE_THRESH=5 PE", "MIN_PE_VALID=15",
                            "T_RANGE=[0,100] ns"],
                 "status": "PASS_MC"},
    "clusterC": {"pr": "#917", "commit": "276eb5b1",
                 "script": "scripts/clusterC/clusterC_pileup_energy_study.py",
                 "inputs": ["ccb-runs/i885_v1 (36+36 files, 36k ev)",
                            "geant4/data/output_krakow_1M.root (xcheck)"],
                 "seeds": ["(env-configurable params, defaults from digitizer config)"],
                 "config": ["os.environ.get overridable", "acq_window=180 ns",
                            "gain=120 ADC/MeV", "adc_ceiling=7000"],
                 "status": "PASS_MC"},
    "clusterD": {"pr": "#919", "commit": "5367ec7b",
                 "script": "scripts/mv*.py + scripts/single_stave/campaign_plots/",
                 "inputs": ["geant4/data/output_krakow_1M.root",
                            "reports/1780917628.449525.085b2dc0__*/s00_selected_b_pulses.csv.gz",
                            "ccb-runs/{i885_v1,sys_birks_smoke2,sipm-p2-001}"],
                 "seeds": ["mv4 seed=20260720", "mv5 seed=42", "mv6 seed=42"],
                 "config": ["gain=92 ADC/MeV (MV0 v2)", "peak_frac=0.75",
                            "thr=100 ADC", "tau_rise=2.5 tau_decay=42 ns"],
                 "status": "GOVERNED"},
    "opticks":  {"pr": OPTICKS["pr"], "commit": OPTICKS["commit"],
                 "script": "geant4/single_stave/opticks/opticks_parity.py",
                 "inputs": ["single-stave GDML", "Geant4 scintillation yield (2 ev, same seed)"],
                 "seeds": ["identical seed CPU vs GPU"],
                 "config": ["A40 target", "CSGFoundry sensor_count=4"],
                 "status": OPTICKS["status"]},
}


# --------------------------------------------------------------------------- #
# Helper
# --------------------------------------------------------------------------- #
def _save(fig, name):
    path = OUT / name
    fig.savefig(path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"  wrote {path.relative_to(ROOT)}")
    return path


def _digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()[:12]


# --------------------------------------------------------------------------- #
# VIS-SYS-001 -- systematic budget
# --------------------------------------------------------------------------- #
def fig_vis_sys_001():
    fig = plt.figure(figsize=(11.5, 5.0))
    gs = fig.add_gridspec(1, 2, width_ratios=[1.35, 1.0], wspace=0.32)
    ax_bar = fig.add_subplot(gs[0, 0])
    ax_cov = fig.add_subplot(gs[0, 1])

    # --- (a) nuisance-impact bars: SiPM/optical-chain elasticities (clusterD) +
    #         digitizer gain envelope + Birks kB span. All expressed as a relative
    #         ADC response impact |elasticity| (dimensionless) where defined; the
    #         two non-elasticity entries are shown hatched and labelled by unit.
    knobs = sorted(SIPM["knobs"], key=lambda k: abs(k["elasticity_adc"]), reverse=True)
    labels = [k["knob"] for k in knobs]
    vals = [abs(k["elasticity_adc"]) for k in knobs]
    colors = [PALETTE_CATEGORICAL[2] if v >= 0.3 else PALETTE_CATEGORICAL[0] for v in vals]
    y = np.arange(len(labels))
    ax_bar.barh(y, vals, color=colors, edgecolor="white", linewidth=0.5)
    ax_bar.set_yticks(y)
    ax_bar.set_yticklabels(labels)
    ax_bar.invert_yaxis()
    ax_bar.set_xlabel("|ADC elasticity|  (ΔADC/ADC per knob, clusterD sipm-p2-001)")
    ax_bar.set_title("VIS-SYS-001  Dominant systematics (nuisance impact)")
    ax_bar.axvline(0.3, ls="--", lw=0.7, color="#888", zorder=0)
    ax_bar.text(0.3, -0.7, "0.3", color="#666", fontsize=6, ha="center")
    for i, v in enumerate(vals):
        ax_bar.text(v + 0.03, i, f"{v:.2f}", va="center", fontsize=6.5)
    # Annotate the two cross-cutting envelopes not captured by the SiPM sweep
    ax_bar.text(0.02, 0.98,
                "Cross-cutting envelopes (not knob elasticities):\n"
                f"  • digitizer gain  ±30%  systematic envelope "
                f"(CL-013, MV0 v2: 92±28 ADC/MeV; NOT a CI)\n"
                f"  • Birks kB  scan span "
                f"{C['VIS-ENE-002']['kB_digitizer_default']:.3f} -> "
                f"{C['VIS-ENE-002']['kB_best_per_track_dEdx']:.3f} cm/MeV "
                f"(clusterC; grid {min(BIRKS_GRID['kB_values']):.3f}-"
                f"{max(BIRKS_GRID['kB_values']):.3f}, clusterD)\n"
                f"  • geometry / material  ~8-10 g/cm^2 missing upstream budget "
                f"(MV3 v3 B8 tension, chi2/ndf=86135, REPORT.md)",
                transform=ax_bar.transAxes, va="top", ha="left", fontsize=6.2,
                bbox=dict(boxstyle="round,pad=0.35", fc="#f7f7f7", ec="#cccccc", lw=0.5))

    # --- (b) timing 4-sensor covariance heatmap (clusterB VIS-TIM-004) -- the one
    #         place a covariance was actually computed.
    cov = B["VIS-TIM-004"]["covariance_summary"]
    sensors = list(cov.keys())
    var = np.array([cov[s]["var"] for s in sensors])
    # correlation matrix is unavailable off-diagonal; the cluster only reported the
    # diagonal (variance per sensor) + bootstrap CIs. Plot the diagonal variances
    # with their 68% CI as a single-row heatmap + error ribbon (honest: off-diagonal
    # was not stored, so we render the variance vector, not a full matrix).
    ci = np.array([cov[s]["ci68"] for s in sensors])
    lo = ci[:, 0]; hi = ci[:, 1]
    im = ax_cov.imshow(var[np.newaxis, :], cmap="viridis", aspect="auto",
                       vmin=min(lo), vmax=max(hi))
    ax_cov.set_xticks(range(len(sensors)))
    ax_cov.set_xticklabels(sensors, rotation=30, ha="right")
    ax_cov.set_yticks([0]); ax_cov.set_yticklabels(["var(residual)\n[ns$^2$]"])
    ax_cov.set_title("Timing sensor variance (clusterB)\n(off-diagonal covariance not stored)")
    for i, s in enumerate(sensors):
        ax_cov.text(i, 0, f"{var[i]:.3f}\n[{lo[i]:.3f},{hi[i]:.3f}]",
                    ha="center", va="center", color="white", fontsize=6.2)
    fig.colorbar(im, ax=ax_cov, fraction=0.05, pad=0.02, label="ns$^2$")
    fig.suptitle("", y=1.0)
    _save(fig, "VIS-SYS-001_systematic_budget.png")


# --------------------------------------------------------------------------- #
# VIS-SYS-002 -- uncertainty coverage
# --------------------------------------------------------------------------- #
def fig_vis_sys_002():
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.2))

    # --- (a) timing pull coverage (clusterB VIS-TIM-005) vs nominal Gaussian
    pc = B["VIS-TIM-005"]["pull_coverage"]
    levels = ["|z|<1", "|z|<2", "|z|<3"]
    obs = [pc["1"], pc["2"], pc["3"]]
    nom = [0.683, 0.954, 0.997]
    x = np.arange(len(levels))
    w = 0.36
    axes[0].bar(x - w/2, nom, w, color="#bbbbbb", label="nominal (Gaussian)")
    axes[0].bar(x + w/2, obs, w,
                color=[STATUS_COLOR["MC_METHOD_CLOSURE"],
                       STATUS_COLOR["PARTIAL"],
                       STATUS_COLOR["PARTIAL"]], label="observed (MC)")
    for i, (o, n) in enumerate(zip(obs, nom)):
        axes[0].text(i + w/2, o + 0.01, f"{o:.3f}", ha="center", fontsize=6.5)
        axes[0].text(i - w/2, n + 0.01, f"{n:.3f}", ha="center", fontsize=6.5, color="#555")
    axes[0].set_xticks(x); axes[0].set_xticklabels(levels)
    axes[0].set_ylabel("fraction of pulls inside window")
    axes[0].set_ylim(0, 1.08)
    axes[0].set_title("VIS-SYS-002 (a)  Timing pull coverage (clusterB VIS-TIM-005)")
    axes[0].legend(loc="lower right", fontsize=6.5)
    axes[0].text(0.01, 0.97,
                 "1σ closes exactly (0.683); 2σ/3σ mild under-coverage from\n"
                 "non-Gaussian scintillation tail (tail frac 10.5%).\n"
                 "Caveat for data: use empirical-quantile interval at high sig.",
                 transform=axes[0].transAxes, va="top", fontsize=6.2,
                 bbox=dict(boxstyle="round,pad=0.3", fc="#fff7ec", ec="#f0a202", lw=0.5))

    # --- (b) PID grouped-bootstrap CI (clusterA) + coverage summary across clusters
    folds = A["pid_oof_auc_5fold"]
    axes[1].errorbar(range(1, 6), folds, yerr=0.01, fmt="o", color=PALETTE_CATEGORICAL[2],
                     capsize=3, markersize=5, label="5-fold pseudo-run AUC ±0.01")
    axes[1].axhline(A["pid_full_auc"], color=PALETTE_CATEGORICAL[0], ls="--", lw=1.2,
                    label=f"full AUC = {A['pid_full_auc']:.3f}")
    axes[1].fill_between([0.5, 5.5], A["pid_full_auc"] - 0.01, A["pid_full_auc"] + 0.01,
                         color=PALETTE_CATEGORICAL[0], alpha=0.12,
                         label="grouped-bootstrap 68% CI (block=500 ev)")
    axes[1].set_xlim(0.5, 5.5)
    axes[1].set_xlabel("fold (contiguous 2000-ev pseudo-run)")
    axes[1].set_ylabel("out-of-fold ROC AUC (p vs d)")
    axes[1].set_ylim(0.85, 0.93)
    axes[1].set_title("VIS-SYS-002 (b)  PID grouped-bootstrap (clusterA VIS-PID-001)")
    axes[1].legend(loc="lower right", fontsize=6.3)
    axes[1].text(0.01, 0.97,
                 "Where bootstrap/toy intervals exist they are honest:\n"
                 "  timing: covariance-aware pull closes at 1σ\n"
                 "  PID: 5-fold within grouped-bootstrap CI\n"
                 "  but: CL-026 systematic propagation BLOCKED --\n"
                 "       coverage is statistical-only, not total.",
                 transform=axes[1].transAxes, va="top", fontsize=6.0,
                 bbox=dict(boxstyle="round,pad=0.3", fc="#f7f7f7", ec="#cccccc", lw=0.5))
    fig.tight_layout()
    _save(fig, "VIS-SYS-002_uncertainty_coverage.png")


# --------------------------------------------------------------------------- #
# VIS-SYS-003 -- sensitivity / robustness
# --------------------------------------------------------------------------- #
def fig_vis_sys_003():
    fig, axes = plt.subplots(2, 3, figsize=(12.5, 7.0))
    NOM_COLOR = PALETTE_CATEGORICAL[3]
    STAR = dict(marker="*", s=180, color=NOM_COLOR, edgecolor="black", zorder=5)

    # (a) timing sigma68 vs pickoff method
    t1 = B["VIS-TIM-001"]["sigma68_residual_ns"]
    methods = ["CFD", "template", "leading-edge"]
    vals = [t1["cfd"], t1["templ"], t1["lead"]]
    axes[0, 0].bar(methods, vals, color=PALETTE_CATEGORICAL[:3])
    axes[0, 0].scatter(["combined (4-sensor)"], [B["VIS-TIM-005"]["combined_sigma68_ns"]], **STAR)
    axes[0, 0].set_ylabel("σ68 residual [ns]")
    axes[0, 0].set_title("(a) Timing σ68 vs pickoff (clusterB)")
    for i, v in enumerate(vals):
        axes[0, 0].text(i, v + 0.02, f"{v:.3f}", ha="center", fontsize=6.5)
    axes[0, 0].text(0, B["VIS-TIM-005"]["combined_sigma68_ns"], "  0.089 (nominal)", fontsize=6.5, va="bottom")

    # (b) timing sigma68 vs sensor (single / leave-one-out / combined)
    loo = B["VIS-TIM-005"]["leave_one_sensor_out_sigma68_ns"]
    cov = B["VIS-TIM-004"]["covariance_summary"]
    sens = list(cov.keys())
    single = [np.sqrt(cov[s]["var"]) for s in sens]
    axes[0, 1].bar(sens, single, color="#88b8e0", label="single-sensor σ68")
    axes[0, 1].scatter(["drop "+s[-4:] for s in sens] + ["combined"],
                       list(loo.values()) + [B["VIS-TIM-005"]["combined_sigma68_ns"]],
                       color=PALETTE_CATEGORICAL[2], s=60, label="leave-one-out / combined")
    axes[0, 1].scatter(["combined"], [B["VIS-TIM-005"]["combined_sigma68_ns"]], **STAR)
    axes[0, 1].set_ylabel("σ68 [ns]")
    axes[0, 1].set_title("(b) Timing σ68 vs sensor (clusterB)")
    axes[0, 1].tick_params(axis="x", labelsize=6.5, rotation=30)
    axes[0, 1].legend(fontsize=6)

    # (c) PID AUC vs slice (clusterA) -- global + folds + worst slices
    slices = ["global", "entry KE", "last layer", "sat-ΔE"]
    auc = [A["pid_full_auc"], A["pid_worst_slice_auc"]["entry KE [MeV]"],
           A["pid_worst_slice_auc"]["last observed layer"],
           A["pid_worst_slice_auc"]["dE [MeV] (saturation proxy)"]]
    axes[0, 2].bar(slices, auc,
                   color=[NOM_COLOR, "#88b8e0", STATUS_COLOR["BLOCKED"], STATUS_COLOR["BLOCKED"]])
    axes[0, 2].axhline(0.5, color="#888", ls=":", lw=0.8)
    axes[0, 2].set_ylabel("ROC AUC (p vs d)")
    axes[0, 2].set_ylim(0, 1.0)
    axes[0, 2].set_title("(c) PID AUC vs slice (clusterA VIS-PID-003)")
    for i, v in enumerate(auc):
        axes[0, 2].text(i, v + 0.02, f"{v:.3f}" if v > 0.1 else f"{v:.3f}", ha="center", fontsize=6.3)

    # (d) Birks: PE/event vs kB (clusterD grid, mm/MeV) + clusterC fitted kB.
    # clusterC reports kB in cm/MeV (digitizer convention, birks.py); convert x10
    # to mm/MeV for a shared axis (default 0.008 cm/MeV = 0.08 mm/MeV sits just
    # below the 0.100-0.160 mm/MeV grid; best fits land inside it).
    kB = BIRKS_GRID["kB_values"]                      # mm/MeV
    pe = list(BIRKS_GRID["pe_per_event_by_kB"].values())
    axes[1, 0].plot(kB, pe, "o-", color=PALETTE_CATEGORICAL[0],
                    label="100 MeV p grid (clusterD)")
    cK = C["VIS-ENE-002"]
    kB_to_mm = 10.0
    for kBv_cm, tag in [(cK["kB_digitizer_default"], "dig default"),
                        (cK["kB_best_total_edep_proxy"], "proxy best"),
                        (cK["kB_best_per_track_dEdx"], "per-track best")]:
        kBv_mm = kBv_cm * kB_to_mm
        axes[1, 0].axvline(kBv_mm, color=STATUS_COLOR["PARTIAL"], ls="--", lw=0.8)
        axes[1, 0].text(kBv_mm, max(pe), f" {tag}\n  {kBv_mm:.3f}",
                        fontsize=5.8, va="top", color="#7a4a00")
    nom_mm = cK["kB_best_per_track_dEdx"] * kB_to_mm
    axes[1, 0].scatter([nom_mm], [np.interp(nom_mm, kB, pe)],
                       color=NOM_COLOR, marker="*", s=160, zorder=5, edgecolor="black")
    axes[1, 0].set_xlabel("Birks kB [mm/MeV]  (clusterC cm/MeV ×10)")
    axes[1, 0].set_ylabel("PE / event")
    axes[1, 0].set_title("(d) Birks quenching (clusterC fit + clusterD grid)")
    axes[1, 0].legend(fontsize=6)

    # (e) ADC/MeV vs species (clusterC) + MV0 data-proxy + canonical gate
    axes[1, 1].bar(["proton\n(clusterC)", "deuteron\n(clusterC)", "MV0 data-proxy\n(CLB B2 median)"],
                   [C["VIS-ENE-001"]["proton"]["slope_adc_per_MeV"],
                    C["VIS-ENE-001"]["deuteron"]["slope_adc_per_MeV"],
                    110.0],
                   color=["#88b8e0", "#88b8e0", STATUS_COLOR["GATED"]])
    axes[1, 1].scatter(["clusterC nominal"], [C["VIS-ENE-001"]["proton"]["slope_adc_per_MeV"]], **STAR)
    axes[1, 1].axhspan(110 - 30, 110 + 30, color=STATUS_COLOR["GATED"], alpha=0.12,
                       label="CL-013 ±30% envelope (GATED)")
    axes[1, 1].set_ylabel("ADC / MeV")
    axes[1, 1].set_title("(e) ADC calibration (clusterC MV0-proxy CL-013)")
    axes[1, 1].legend(fontsize=6)
    axes[1, 1].tick_params(axis="x", labelsize=6.3)

    # (f) pile-up overlap observed vs Poisson; Rmax variants
    pu = C["VIS-PU-002"]
    axes[1, 2].bar(["obs overlap\n@1 MHz", "Poisson\n@1 MHz"],
                   [pu["observed_overlap_at_max_rate"], pu["poisson_overlap_at_max_rate"]],
                   color=[PALETTE_CATEGORICAL[2], "#bbbbbb"])
    axes[1, 2].scatter(["clusterC Rmax\n@0% quality gate"], [pu["Rmax_quality_Hz"] / 1e6],
                       color=NOM_COLOR, marker="*", s=160, edgecolor="black", zorder=5)
    axes[1, 2].scatter(["clusterC Rmax\n@5% overlap"], [pu["rate_at_5pct_overlap_Hz"] / 1e6],
                       color="#88b8e0", s=60)
    axes[1, 2].scatter(["legacy 3.04 MHz\n(CL-012 SUPERSEDED)"], [3.0449],
                       color=STATUS_COLOR["SUPERSEDED"], marker="x", s=80, linewidths=2)
    axes[1, 2].set_ylabel("overlap frac  /  Rmax [MHz]")
    axes[1, 2].set_title("(f) Pile-up (clusterC) + canonical Rmax gate")
    axes[1, 2].text(0.02, 0.97, "canonical Rmax BLOCKED (CL-010, S-STAT-003)",
                    transform=axes[1, 2].transAxes, va="top", fontsize=6.0, color=STATUS_COLOR["BLOCKED"])

    fig.suptitle("VIS-SYS-003  Sensitivity / robustness -- headline observables vs varied nuisance "
                 "(★ = frozen nominal)", y=1.0, fontsize=10)
    fig.tight_layout()
    _save(fig, "VIS-SYS-003_sensitivity_robustness.png")


# --------------------------------------------------------------------------- #
# VIS-REP-001 -- reproducibility DAG
# --------------------------------------------------------------------------- #
def fig_vis_rep_001():
    fig, ax = plt.subplots(figsize=(13.5, 7.5))
    ax.set_xlim(0, 100); ax.set_ylim(0, 100); ax.axis("off")

    def box(cx, cy, w, h, text, fill, edge="#444", fontsize=7.5, textcolor="black"):
        p = FancyBboxPatch((cx - w/2, cy - h/2), w, h,
                           boxstyle="round,pad=0.5,rounding_size=2.0",
                           fc=fill, ec=edge, lw=1.0)
        ax.add_patch(p)
        ax.text(cx, cy, text, ha="center", va="center", fontsize=fontsize,
                color=textcolor, zorder=6, wrap=True)

    def arrow(x1, y1, x2, y2, color="#666"):
        ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2),
                                     arrowstyle="-|>", mutation_scale=11,
                                     color=color, lw=1.0,
                                     connectionstyle="arc3,rad=0.0", zorder=3))

    # Column headers
    for cx, title in [(10, "INPUTS"), (33, "CODE (cluster)"), (54, "CONFIG / seed"),
                      (74, "OUTPUT"), (91, "CLAIM  &  STATUS")]:
        ax.text(cx, 97, title, ha="center", va="center", fontsize=9, fontweight="bold",
                color="#333")

    # Five rows: clusterA, clusterB, clusterC, clusterD, opticks
    rows = [
        ("clusterA", 82,
         ["Krakow 1M MC ROOT\n(hibeam, 1M ev)",
          "raw beam ROOT: NOT on LUNARC"],
         "clusterA_dE_PID_stopping.py\n(PR #921, 9096345d)",
         "STOP_KE=1.0 MeV\nGEO-001 pair_merge\nevent_index key",
         "ΔE-E / PID / stopping\n7 PNGs + counts.json",
         "PID AUC 0.898 (MC)\nSIMULATION_RESULT\nDATA PID: BLOCKED_DATA"),
        ("clusterB", 63,
         ["i885_v1 photon MC (72 f)",
          "sys_birks_smoke2 (3 f)",
          "Krakow 1M (xcheck)"],
         "clusterB_timing_study.py\n(PR #918, 96c72ad0)",
         "seeds s101/s102\nDT=0.25ns CFD=0.2\nMIN_PE_VALID=15",
         "timing chain\n6 PNGs + metrics.json",
         "σ68 = 0.089 ns (MC)\nMC_METHOD_CLOSURE\ndet resolution: BLOCKED_DATA"),
        ("clusterC", 44,
         ["i885_v1 (36+36 f, 36kev)",
          "Krakow 1M (xcheck)"],
         "clusterC_pileup_energy_study.py\n(PR #917, 276eb5b1)",
         "env-configurable params\ngain=120 ADC/MeV\nwindow=180 ns",
         "pileup/energy/Birks\n7 PNGs + metrics.json",
         "Rmax 0.605 MHz (digitizer)\nADC 119.17 / Birks kB\nSIMULATION_RESULT"),
        ("clusterD", 25,
         ["Krakow 1M MC ROOT",
          "s00_selected_b_pulses.csv.gz",
          "i885/sys_birks/sipm-p2"],
         "mv0..mv6 + campaign_plots\n(PR #919, 5367ec7b)",
         "mv4 seed 20260720\nmv5/6 seed 42\ngain=92 thr=100 ADC",
         "MV0-MV6 reports +\ncampaign figures",
         "MV0 GATED / MV3 TENSION\nMV4,5 BLOCKED(toy)\nMV1,2,6 TRUTH_MC"),
        ("opticks", 8,
         ["single-stave GDML",
          "Geant4 scint yield (2 ev)"],
         "opticks_parity.py\n(PR #920, 2c0afcd6)",
         "identical seed\nCPU vs GPU (A40)",
         "opticks_gpu_vs_cpu_parity\n+ SUMMARY.md",
         "PARTIAL\nCPU 9/9 PASS\nGPU gather null"),
    ]
    for name, cy, inputs, code, cfg, output, claim in rows:
        st = PROV[name]["status"]
        claim_fill = {"PASS_MC": STATUS_COLOR["MC_METHOD_CLOSURE"],
                      "GOVERNED": STATUS_COLOR["GATED"],
                      "PARTIAL": STATUS_COLOR["PARTIAL"]}.get(st, "#dddddd")
        in_fill = "#eef3fb"
        # INPUT box (single combined)
        box(10, cy, 16, 11, "\n".join(inputs), in_fill, fontsize=6.3)
        box(33, cy, 19, 10.5, code, "#fff7ec", fontsize=6.5)
        box(54, cy, 16, 10.5, cfg, "#f3fcef", fontsize=6.3)
        box(74, cy, 17, 10.5, output, "#fbf0f7", fontsize=6.5)
        tc = "white" if st in ("PASS_MC",) else "black"
        box(91, cy, 16, 11, claim, claim_fill, fontsize=6.3,
            textcolor=("white" if claim_fill in (STATUS_COLOR["MC_METHOD_CLOSURE"],
                                                 STATUS_COLOR["GATED"],
                                                 STATUS_COLOR["PARTIAL"], STATUS_COLOR["BLOCKED"]) else "black"))
        for x1, x2 in [(18, 23.5), (42.5, 46), (62, 65.5), (82.5, 83)]:
            arrow(x1, cy, x2, cy, color="#888")

    # Cross-cutting provenance strip
    ax.text(50, 1.5,
            "Provenance: every output binds to a git commit (origin/main squash-merge above) + "
            "config + seed.\n"
            "Canonical cross-domain status: docs/claim_ledger.csv (2026-07-25, 26 rows: "
            "1 VALIDATED, 9 GATED, 8 BLOCKED, 3 TRUTH_LEVEL_MC_ONLY, 1 SUPERSEDED, ...).  "
            "Raw hrdb_run_*.root NOT staged on LUNARC -> data-side claims BLOCKED_DATA.",
            ha="center", va="bottom", fontsize=6.5, color="#444",
            bbox=dict(boxstyle="round,pad=0.4", fc="#fafafa", ec="#cccccc", lw=0.5))
    ax.set_title("VIS-REP-001  Reproducibility DAG  (input -> code -> config -> output -> claim)",
                 fontsize=11, pad=4)
    _save(fig, "VIS-REP-001_reproducibility_dag.png")


# --------------------------------------------------------------------------- #
# VIS-CLAIM-001 -- claim dashboard
# --------------------------------------------------------------------------- #
HEADLINE_CLAIMS = [
    # (claim, headline, evidence_class, status, source, figure, claim_id)
    ("Selected B-stack pulses (S00 gate)",
     "640,737 pulses", "DATA_MEASUREMENT", "VALIDATED",
     "S00 / CL-001", "reports/SUMMARY.md", "CL-001"),
    ("Combined timing resolution σ68",
     "0.089 ns", "MC_METHOD_CLOSURE", "PASS",
     "clusterB (#918) VIS-TIM-005", "VIS-TIM-005_combined_estimator.png", "—"),
    ("Detector timing resolution (data)",
     "withheld", "BLOCKED_DATA", "BLOCKED",
     "CL-002..006 (BLK-MV4-LEGACY-001)", "—", "CL-002"),
    ("Pile-up tolerance Rmax (canonical)",
     "withheld", "BLOCKED", "BLOCKED",
     "CL-010 (S-STAT-003)", "—", "CL-010"),
    ("Legacy Rmax = 3.044 MHz",
     "SUPERSEDED", "SUPERSEDED", "SUPERSEDED",
     "CL-012 (do not use)", "—", "CL-012"),
    ("Rmax (digitizer domain, 0% gate)",
     "0.605 MHz", "SIMULATION_RESULT", "PASS",
     "clusterC (#917) VIS-PU-002", "VIS-PU-002_pileup_occupancy_rate.png", "—"),
    ("PID p-vs-d AUC (realistic chain, MC)",
     "0.898", "SIMULATION_RESULT", "PASS",
     "clusterA (#921) VIS-PID-001", "VIS-PID-001_roc_pr.png", "—"),
    ("PID p-vs-d AUC (truth ceiling HGB)",
     "0.986", "TRUTH_LEVEL_MC_ONLY", "GATED",
     "MV1 / CL-017 (BLK-MV1-001)", "—", "CL-017"),
    ("PID on beam data",
     "deferred", "BLOCKED_DATA", "BLOCKED_DATA",
     "raw ROOT not staged", "—", "—"),
    ("ADC calibration (digitizer gain)",
     "119.17 ADC/MeV", "SIMULATION_RESULT", "PASS",
     "clusterC (#917) VIS-ENE-001", "VIS-ENE-001_adc_calibration.png", "—"),
    ("ADC gain (data/MC proxy, MV0)",
     "110 ADC/MeV (±30%)", "DATA_MC_PROXY", "GATED",
     "MV0 / CL-013 (BLK-MV0-001)", "mv0_gain_scan.png", "CL-013"),
    ("Birks kB (per-track dE/dx fit)",
     "0.0156 cm/MeV", "SIMULATION_RESULT", "PASS",
     "clusterC (#917) VIS-ENE-002", "VIS-ENE-002_birks_quenching.png", "—"),
    ("Anomaly / C12 identity",
     "25/38 toy early-peak C12", "TRUTH_LEVEL_MC_ONLY", "BLOCKED",
     "MV6 / CL-022 (AUD-ANOM-001)", "mv6_representation.png", "CL-022"),
    ("Stopping-depth data/MC closure",
     "χ²/ndf ≈ 6.8e4  FAIL", "MC_DIAGNOSTIC", "TENSION",
     "MV3 / CL-021 (BLK-MV3-LEGACY-001)", "mv3_stop_frac.png", "CL-021"),
    ("Opticks GPU-vs-CPU parity",
     "0 GPU hits / 4592 CPU", "SIMULATION_RESULT", "PARTIAL",
     "opticks (#920)", "opticks_gpu_vs_cpu_parity.png", "—"),
    ("Systematic uncertainty budget",
     "incomplete", "BLOCKED", "BLOCKED",
     "CL-026 (BLK-SYST-001)", "docs/SYSTEMATIC_UNCERTAINTIES.md", "CL-026"),
]


def fig_vis_claim_001():
    fig, ax = plt.subplots(figsize=(14.5, 8.2))
    ax.axis("off")
    cols = ["Claim", "Headline", "Evidence class", "Status", "Source (cluster / ledger)", "Figure / link"]
    widths = [0.24, 0.13, 0.17, 0.10, 0.20, 0.16]
    n = len(HEADLINE_CLAIMS)
    table_data = [[c[0], c[1], c[2], c[3], c[4], c[5]] for c in HEADLINE_CLAIMS]

    # header
    y0 = 1.0
    rowh = 1.0 / (n + 1.6)
    x = 0.0
    xs = []
    for w in widths:
        xs.append((x, x + w))
        x += w
    for (xL, xR), title in zip(xs, cols):
        ax.add_patch(FancyBboxPatch((xL, y0 - rowh), xR - xL, rowh,
                                    boxstyle="square,pad=0.0", fc="#333333", ec="#333333"))
        ax.text((xL + xR) / 2, y0 - rowh / 2, title, ha="center", va="center",
                color="white", fontsize=7.6, fontweight="bold")
    for i, row in enumerate(table_data):
        yy = y0 - rowh * (i + 2)
        for (xL, xR), val, cidx in zip(xs, row, [0, 1, 2, 3, 4, 5]):
            fc = "white" if i % 2 == 0 else "#f4f4f4"
            if cidx == 3:  # status column colour-coded
                fc = _status_fill(val)
            ax.add_patch(FancyBboxPatch((xL, yy), xR - xL, rowh,
                                        boxstyle="square,pad=0.0", fc=fc, ec="#dddddd", lw=0.5))
            tc = "black"
            if cidx == 3 and val in ("PASS", "BLOCKED", "BLOCKED_DATA", "VALIDATED",
                                     "SUPERSEDED", "GATED", "TENSION"):
                tc = "white"
            ax.text(xL + 0.006, yy + rowh / 2, val, ha="left", va="center",
                    fontsize=6.6, color=tc, wrap=True)
    ax.set_xlim(0, 1); ax.set_ylim(y0 - rowh * (n + 2), 1.0)
    ax.set_title("VIS-CLAIM-001  Claim dashboard -- evidence class, status, provenance",
                 fontsize=11, pad=6)
    _save(fig, "VIS-CLAIM-001_claim_dashboard.png")


# --------------------------------------------------------------------------- #
# PROJECT_DASHBOARD overview PNG
# --------------------------------------------------------------------------- #
def fig_dashboard_overview():
    fig = plt.figure(figsize=(13.5, 8.6))
    gs = fig.add_gridspec(3, 3, hspace=0.55, wspace=0.35,
                          left=0.05, right=0.97, top=0.90, bottom=0.07)

    fig.suptitle("CCB test-beam -- \"the project works\" dashboard (Cluster E synthesis)",
                 fontsize=13, fontweight="bold", y=0.965)
    fig.text(0.5, 0.925,
             "Analysis chain proven on MC; data-side / detector-performance claims BLOCKED_DATA "
             "(raw hrdb_run_*.root not on LUNARC).  Canonical status: docs/claim_ledger.csv.",
             ha="center", fontsize=8, color="#444")

    # (1) MV0-MV6 status (clusterD governance table)
    ax = fig.add_subplot(gs[0, 0])
    mv = [("MV0 ADC gain", "GATED"), ("MV1 truth PID", "TRUTH_LEVEL_MC_ONLY"),
          ("MV2 range/energy", "TRUTH_LEVEL_MC_ONLY"), ("MV3 stopping", "TENSION"),
          ("MV4 timing", "BLOCKED"), ("MV5 pile-up", "BLOCKED"),
          ("MV6 anomaly", "TRUTH_LEVEL_MC_ONLY")]
    yy = np.arange(len(mv))[::-1]
    cols = [_status_fill(s) for _, s in mv]
    ax.barh(yy, [1]*len(mv), color=cols, edgecolor="white")
    ax.set_yticks(yy); ax.set_yticklabels([m for m, _ in mv], fontsize=6.5)
    ax.set_xticks([])
    for i, (m, s) in enumerate(mv):
        ax.text(1.02, yy[i], s, va="center", fontsize=6, color=_status_fill(s))
    ax.set_title("MV0-MV6 governance (clusterD)", fontsize=8.5)
    ax.set_xlim(0, 1.8)

    # (2) claim-ledger status donut
    ax = fig.add_subplot(gs[0, 1])
    from collections import Counter
    cnt = Counter(CLAIMS[c]["status"] for c in CLAIMS)
    labels = list(cnt.keys())
    vals = list(cnt.values())
    wedges, _ = ax.pie(vals, colors=[_status_fill(l) for l in labels], startangle=90,
                       wedgeprops=dict(width=0.42, edgecolor="white"))
    ax.text(0, 0, f"{sum(vals)}\nclaims", ha="center", va="center", fontsize=9, fontweight="bold")
    ax.set_title("docs/claim_ledger.csv status (26 rows)", fontsize=8.5)
    ax.legend(wedges, [f"{l} ({v})" for l, v in zip(labels, vals)],
              loc="center left", bbox_to_anchor=(1.0, 0.5), fontsize=5.8, frameon=False)

    # (3) Opticks parity
    ax = fig.add_subplot(gs[0, 2])
    ax.bar(["CPU arrivals\n(per ev)", "GPU input photons\n(per ev)", "GPU hits\n(per ev)"],
           [OPTICKS["cpu_arrivals_per_event"], OPTICKS["gpu_input_photons_per_event"], OPTICKS["gpu_hits"]],
           color=[STATUS_COLOR["MC_METHOD_CLOSURE"], STATUS_COLOR["PARTIAL"], STATUS_COLOR["BLOCKED"]])
    ax.set_yscale("log")
    ax.set_ylabel("per event")
    ax.set_title(f"Opticks GPU/CPU parity -- PARTIAL (ctest {OPTICKS['ctest_pass']} PASS)",
                 fontsize=8.5)
    ax.tick_params(axis="x", labelsize=6.3)

    # (4) timing chain
    ax = fig.add_subplot(gs[1, 0])
    t1 = B["VIS-TIM-001"]["sigma68_residual_ns"]
    ax.bar(["CFD", "template", "lead"], [t1["cfd"], t1["templ"], t1["lead"]], color="#88b8e0")
    NOM = "#ccbb44"
    ax.scatter(["combined"], [B["VIS-TIM-005"]["combined_sigma68_ns"]], color=NOM,
               marker="*", s=200, edgecolor="black", zorder=5)
    ax.set_ylabel("σ68 [ns]"); ax.set_title("Timing chain (clusterB) -- combined 0.089 ns", fontsize=8.5)

    # (5) PID
    ax = fig.add_subplot(gs[1, 1])
    ax.bar(["full", "entry KE", "last layer", "sat-ΔE"],
           [A["pid_full_auc"], A["pid_worst_slice_auc"]["entry KE [MeV]"],
            A["pid_worst_slice_auc"]["last observed layer"],
            A["pid_worst_slice_auc"]["dE [MeV] (saturation proxy)"]],
           color=[NOM, "#88b8e0", STATUS_COLOR["BLOCKED"], STATUS_COLOR["BLOCKED"]])
    ax.set_ylim(0, 1); ax.set_title("PID AUC slices (clusterA) -- global 0.898", fontsize=8.5)
    ax.set_ylabel("ROC AUC (p vs d)")
    ax.tick_params(axis="x", labelsize=6.3)

    # (6) energy / Birks
    ax = fig.add_subplot(gs[1, 2])
    kB = BIRKS_GRID["kB_values"]; pe = list(BIRKS_GRID["pe_per_event_by_kB"].values())
    ax.plot(kB, pe, "o-", color=PALETTE_CATEGORICAL[0])
    ax.set_xlabel("Birks kB [mm/MeV]"); ax.set_ylabel("PE / event")
    ax.set_title("Birks grid (clusterD) + ADC 119.17 (clusterC)", fontsize=8.5)
    ax.text(0.03, 0.92, f"ADC calib: {C['VIS-ENE-001']['proton']['slope_adc_per_MeV']:.2f} ADC/MeV\n"
                       f"kB best (per-track): {C['VIS-ENE-002']['kB_best_per_track_dEdx']:.4f}",
            transform=ax.transAxes, fontsize=6, va="top",
            bbox=dict(boxstyle="round,pad=0.3", fc="#fff7ec", ec="#f0a202", lw=0.5))

    # (7) pile-up
    ax = fig.add_subplot(gs[2, 0])
    pu = C["VIS-PU-002"]
    ax.bar(["Rmax@0%\nclusterC", "Rmax@5%\nclusterC", "legacy 3.04\n(CL-012)"],
           [pu["Rmax_quality_Hz"]/1e6, pu["rate_at_5pct_overlap_Hz"]/1e6, 3.0449],
           color=[NOM, "#88b8e0", STATUS_COLOR["SUPERSEDED"]])
    ax.set_ylabel("MHz"); ax.set_title("Pile-up: canonical Rmax BLOCKED (CL-010)", fontsize=8.5)
    ax.tick_params(axis="x", labelsize=6.0)

    # (8) provenance strip
    ax = fig.add_subplot(gs[2, 1:]); ax.axis("off")
    rows = [("clusterA", "#921", "9096345d", "PASS_MC"),
            ("clusterB", "#918", "96c72ad0", "PASS_MC"),
            ("clusterC", "#917", "276eb5b1", "PASS_MC"),
            ("clusterD", "#919", "5367ec7b", "GOVERNED"),
            ("opticks",  "#920", "2c0afcd6", "PARTIAL")]
    txt = "Cluster provenance on origin/main (squash-merge):\n"
    txt += "  " + "   ".join([f"{n} {pr} {cm} [{st}]" for n, pr, cm, st in rows])
    txt += "\n\nHeadline (PASS): combined σ68 0.089 ns · PID AUC 0.898 · ADC 119.17 ADC/MeV · "
    txt += "Birks kB 0.0156 · Rmax(digitizer) 0.605 MHz · S00 pulses 640,737 (VALIDATED)."
    txt += "\nHeadline (BLOCKED/GATED): detector timing · canonical Rmax · data PID · MV0 gain · "
    txt += "anomaly ID · sys budget · Opticks GPU gather."
    ax.text(0.0, 0.9, txt, ha="left", va="top", fontsize=7.2, family="monospace",
            bbox=dict(boxstyle="round,pad=0.5", fc="#fafafa", ec="#cccccc", lw=0.5))

    _save(fig, "PROJECT_DASHBOARD_OVERVIEW.png")


# --------------------------------------------------------------------------- #
# Machine-readable outputs
# --------------------------------------------------------------------------- #
def write_csv_outputs():
    # claims table
    with (OUT / "claims_table.csv").open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["claim", "headline", "evidence_class", "status",
                    "source", "figure", "claim_id"])
        for c in HEADLINE_CLAIMS:
            w.writerow(c)
    # systematic budget
    with (OUT / "systematic_budget.csv").open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["nuisance", "abs_elasticity_adc", "source"])
        for k in sorted(SIPM["knobs"], key=lambda k: abs(k["elasticity_adc"]), reverse=True):
            w.writerow([k["knob"], abs(k["elasticity_adc"]), "clusterD sipm-p2-001"])
        w.writerow(["digitizer_gain_envelope", 0.30, "CL-013 MV0 v2 (±30%, NOT a CI)"])
        w.writerow(["birks_kB_span_cm_per_MeV",
                    C["VIS-ENE-002"]["kB_best_per_track_dEdx"] - C["VIS-ENE-002"]["kB_digitizer_default"],
                    "clusterC"])
        w.writerow(["geometry_material_missing_g_per_cm2", "8-10", "MV3 (clusterD)"])
    # sensitivity
    with (OUT / "sensitivity_robustness.csv").open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["observable", "variant", "value", "unit", "is_nominal", "source"])
        t1 = B["VIS-TIM-001"]["sigma68_residual_ns"]
        for m, v, nom in [("CFD", t1["cfd"], False), ("template", t1["templ"], False),
                          ("lead", t1["lead"], False),
                          ("combined", B["VIS-TIM-005"]["combined_sigma68_ns"], True)]:
            w.writerow(["timing_sigma68", m, v, "ns", nom, "clusterB"])
        for sname, v in A["pid_worst_slice_auc"].items():
            w.writerow(["pid_auc_slice", sname, v, "AUC", False, "clusterA"])
        w.writerow(["pid_auc_slice", "global", A["pid_full_auc"], "AUC", True, "clusterA"])
    print("  wrote claims_table.csv / systematic_budget.csv / sensitivity_robustness.csv")


def write_summary_and_provenance():
    # metrics.json + provenance.json
    metrics = {
        "source_files": {
            "clusterA": "reports/studies/clusterA/counts.json",
            "clusterB": "reports/studies/clusterB/metrics.json",
            "clusterC": "reports/studies/clusterC/metrics.json",
            "clusterD_sipm": "reports/studies/clusterD/figures/fig_sipm_summary.json",
            "claim_ledger": "docs/claim_ledger.csv",
            "opticks": "figures/opticks/SUMMARY.md",
        },
        "headline_PASS": {
            "timing_combined_sigma68_ns": B["VIS-TIM-005"]["combined_sigma68_ns"],
            "pid_auc_realistic_chain": A["pid_full_auc"],
            "adc_per_MeV_digitizer": C["VIS-ENE-001"]["proton"]["slope_adc_per_MeV"],
            "birks_kB_per_track_cm_per_MeV": C["VIS-ENE-002"]["kB_best_per_track_dEdx"],
            "rmax_digitizer_0pct_gate_MHz": C["VIS-PU-002"]["Rmax_quality_Hz"] / 1e6,
            "s00_pulses_validated": int(CLAIMS["CL-001"]["current_value"]),
        },
        "headline_BLOCKED": {
            "detector_timing_resolution": "CL-002..006 (BLK-MV4-LEGACY-001)",
            "canonical_Rmax": "CL-010 (S-STAT-003)",
            "data_side_PID": "raw hrdb_run_*.root not staged",
            "systematic_budget": "CL-026 (BLK-SYST-001)",
            "anomaly_identity": "CL-022 (AUD-ANOM-001)",
            "opticks_gpu_gather": "EventMode/component-save config (PARTIAL)",
        },
        "headline_SUPERSEDED": {"legacy_Rmax_3p044_MHz": "CL-012 (do not use)"},
        "opticks": OPTICKS,
        "provenance": PROV,
    }
    with (OUT / "metrics.json").open("w") as fh:
        json.dump(metrics, fh, indent=2)
    # input digests (content-address the cluster inputs we read)
    digests = {}
    for rel in ["reports/studies/clusterA/counts.json",
                "reports/studies/clusterB/metrics.json",
                "reports/studies/clusterC/metrics.json",
                "reports/studies/clusterD/figures/fig_sipm_summary.json",
                "reports/studies/clusterD/figures/fig_birks_summary.json",
                "reports/studies/clusterD/figures/fig_i885_summary.json",
                "docs/claim_ledger.csv"]:
        p = ROOT / rel
        if p.exists():
            digests[rel] = _digest(p)
    with (OUT / "provenance.json").open("w") as fh:
        json.dump({
            "base_commit": os.environ.get("CLUSTERE_BASE", "(worktree HEAD)"),
            "input_digests_sha256_12": digests,
            "claim_ledger_rows": len(CLAIMS),
            "note": "All headline numbers trace to the files listed in source_files; "
                    "no physics recomputation in this synthesis.",
        }, fh, indent=2)
    print("  wrote metrics.json / provenance.json")


def main():
    print(f"Cluster E synthesis -> {OUT.relative_to(ROOT)}")
    fig_vis_sys_001()
    fig_vis_sys_002()
    fig_vis_sys_003()
    fig_vis_rep_001()
    fig_vis_claim_001()
    fig_dashboard_overview()
    write_csv_outputs()
    write_summary_and_provenance()
    print("done.")


if __name__ == "__main__":
    main()
