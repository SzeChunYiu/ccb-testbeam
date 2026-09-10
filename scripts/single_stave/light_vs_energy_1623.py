#!/usr/bin/env python3
"""Issue #1623 -- single-stave deposited energy -> scintillation -> photoelectrons.

Reads the `events` ntuple of every ROOT file produced by the #1623 campaign,
builds one event-level table with the derived geometry/quenching quantities,
writes it out (parquet + gzipped CSV) and produces the requested plots.

Everything downstream of the ROOT files is derived here; nothing is assumed
about the detector response that is not in the simulation output.

Column semantics (producer: geant4/single_stave/src/RunAction.cc)
  edep_scint_raw_MeV      unquenched deposit, all non-optical tracks
  edep_scint_MeV          Birks-quenched (visible) deposit, same tracks
  n_scint_generated       scintillation photons created in the event
  arrival_readout         photons reaching the physical readout (fibre 1, +x)
  detected_readout        photoelectrons after PDE x coupling at that sensor
  adc_readout             peak ADC above baseline from the SiPM response model
  primary_stopped         1 if the primary terminated inside the scintillator
Geometry: bar 50.0 x 5.18 x 2.0 cm, readout at x = +25.0 cm, WLS fibres along x
at y = +/-1.0 cm; the instrumented readout is the fibre at y = +1.0 cm.
"""
from __future__ import annotations

import argparse
import glob
import json
import math
import pathlib
import re
import sys

import numpy as np
import pandas as pd
import uproot
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

READOUT_END_X_CM = 25.0
FIBRE_Y_CM = 1.0
STAVE_HALF_Z_CM = 1.0

SPECIES_ORDER = ["proton", "deuteron", "mu-", "mu+", "pi+", "pi-"]
SPECIES_COLOR = {
    "proton": "#1f77b4",
    "deuteron": "#d62728",
    "mu-": "#2ca02c",
    "mu+": "#17becf",
    "pi+": "#9467bd",
    "pi-": "#8c564b",
}
PDG_NAME = {2212: "proton", 1000010020: "deuteron", 13: "mu-", -13: "mu+",
            211: "pi+", -211: "pi-"}

BRANCHES = [
    "event", "ke_MeV",
    "edep_scint_MeV", "edep_scint_raw_MeV", "track_len_scint_mm",
    "primary_edep_scint_MeV", "primary_edep_scint_raw_MeV",
    "primary_track_len_scint_mm", "primary_pdg",
    "entry_x_cm", "entry_y_cm", "entry_z_cm",
    "exit_x_cm", "exit_y_cm", "exit_z_cm",
    "n_scint_generated", "n_wls_generated", "n_cerenkov_generated",
    "arrival_readout", "detected_readout", "pe_sat_readout", "adc_readout",
    "gen_x_cm", "gen_y_cm", "dir_ux", "dir_uy", "dir_uz",
    "primary_exit_x_cm", "primary_exit_y_cm", "primary_exit_z_cm",
    "primary_ke_end_MeV", "primary_stopped",
    "n_optical_killed_time", "n_optical_killed_steps",
]

FNAME_RE = re.compile(
    r"stave_(?P<part>[A-Za-z0-9]+)_(?P<ene>[0-9.]+)MeV_(?P<sample>[AB])_s(?P<seed>\d+)\.root$"
)
NAME_FIX = {"muminus": "mu-", "muplus": "mu+", "piplus": "pi+", "piminus": "pi-"}


# --------------------------------------------------------------------------- io
def load(paths: list[str]) -> pd.DataFrame:
    """Read every campaign file FAIL-CLOSED.

    A campaign task that died at the wall limit leaves a truncated or empty
    ROOT file behind; silently skipping it would quietly shrink the sample and
    bias every median in this report. Each file must therefore carry its
    producer sidecar and its row count must match the sidecar's `n_events`.
    """
    frames = []
    problems: list[str] = []
    for path in paths:
        f = uproot.open(path)
        if "events" not in f:
            problems.append(f"{pathlib.Path(path).name}: no `events` tree")
            continue
        tree = f["events"]
        meta_path = pathlib.Path(path + ".meta.json")
        if not meta_path.exists():
            problems.append(f"{pathlib.Path(path).name}: missing {meta_path.name}")
            continue
        meta = json.loads(meta_path.read_text())
        want = int(meta.get("n_events", -1))
        got = int(tree.num_entries)
        if want < 0:
            problems.append(f"{pathlib.Path(path).name}: sidecar has no n_events")
            continue
        if want != got:
            problems.append(
                f"{pathlib.Path(path).name}: sidecar n_events={want} but tree has {got} rows"
            )
            continue
        if int(meta.get("n_events_requested", want)) != want:
            problems.append(
                f"{pathlib.Path(path).name}: requested "
                f"{meta.get('n_events_requested')} events, produced {want}"
            )
            continue
        have = [b for b in BRANCHES if b in tree.keys()]
        missing = [b for b in BRANCHES if b not in tree.keys()]
        if missing:
            raise SystemExit(
                f"{path}: events tree is missing required #1623 branches {missing}. "
                "Rerun the producer built from the #1623 branch."
            )
        df = tree.arrays(have, library="pd")
        m = FNAME_RE.search(pathlib.Path(path).name)
        if m is None:
            raise SystemExit(f"unparseable campaign filename: {path}")
        part = NAME_FIX.get(m["part"], m["part"])
        df["species"] = part
        df["sample"] = m["sample"]
        df["seed"] = int(m["seed"])
        df["ke_setting_MeV"] = float(m["ene"])
        df["source_file"] = pathlib.Path(path).name
        df["optical_max_time_ns"] = float(meta.get("optical_max_time_ns", 0.0))
        df["optical_max_steps"] = int(meta.get("optical_max_steps", 0))
        frames.append(df)
    if problems:
        print("INPUT CLOSURE FAILED -- refusing to analyse an incomplete campaign:",
              file=sys.stderr)
        for pb in problems:
            print(f"  {pb}", file=sys.stderr)
        sys.exit(3)
    if not frames:
        raise SystemExit("no usable input files")
    return pd.concat(frames, ignore_index=True)


def derive(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    # species cross-check against the recorded primary PDG
    pdg_name = d["primary_pdg"].map(PDG_NAME)
    bad = pdg_name.notna() & (pdg_name != d["species"])
    if bad.any():
        raise SystemExit(
            f"species/PDG mismatch in {int(bad.sum())} events "
            f"(filename says {sorted(d.loc[bad,'species'].unique())}, "
            f"ntuple PDG says {sorted(pdg_name[bad].unique())})"
        )

    d["edep_raw_MeV"] = d["edep_scint_raw_MeV"]
    d["edep_vis_MeV"] = d["edep_scint_MeV"]
    with np.errstate(divide="ignore", invalid="ignore"):
        d["birks_ratio"] = d["edep_vis_MeV"] / d["edep_raw_MeV"]
        # path-averaged stopping power of the PRIMARY through the scintillator
        d["dedx_MeV_per_mm"] = (
            d["primary_edep_scint_raw_MeV"] / d["primary_track_len_scint_mm"]
        )
        d["pe_per_MeV"] = d["detected_readout"] / d["edep_raw_MeV"]
        d["pe_per_MeV_vis"] = d["detected_readout"] / d["edep_vis_MeV"]
        d["scint_per_MeV"] = d["n_scint_generated"] / d["edep_raw_MeV"]
        d["collection_frac"] = d["arrival_readout"] / d["n_scint_generated"]

    # geometry relative to the instrumented readout
    d["dist_to_sipm_cm"] = READOUT_END_X_CM - d["entry_x_cm"]
    d["dist_to_readout_fibre_cm"] = (d["entry_y_cm"] - FIBRE_Y_CM).abs()
    d["dist_to_nearest_fibre_cm"] = np.minimum(
        (d["entry_y_cm"] - FIBRE_Y_CM).abs(), (d["entry_y_cm"] + FIBRE_Y_CM).abs()
    )
    d["theta_deg"] = np.degrees(np.arccos(np.clip(d["dir_uz"], -1.0, 1.0)))
    d["path_mm"] = d["primary_track_len_scint_mm"]
    d["fate"] = np.where(d["primary_stopped"] == 1, "stopped", "punch-through")
    return d


# ------------------------------------------------------------------ statistics
def band(x, y, edges):
    """median and 16/84% band of y in bins of x. Returns centres, med, lo, hi, n."""
    idx = np.digitize(x, edges) - 1
    c, med, lo, hi, n = [], [], [], [], []
    for i in range(len(edges) - 1):
        sel = idx == i
        k = int(sel.sum())
        if k < 8:
            continue
        yy = y[sel]
        c.append(0.5 * (edges[i] + edges[i + 1]))
        med.append(np.median(yy))
        lo.append(np.percentile(yy, 16))
        hi.append(np.percentile(yy, 84))
        n.append(k)
    return (np.array(c), np.array(med), np.array(lo), np.array(hi), np.array(n))


def profile_plot(ax, d, xcol, ycol, edges, species=None, label_suffix=""):
    species = species or [s for s in SPECIES_ORDER if s in set(d["species"])]
    for sp in species:
        sel = d["species"] == sp
        x = d.loc[sel, xcol].to_numpy(float)
        y = d.loc[sel, ycol].to_numpy(float)
        ok = np.isfinite(x) & np.isfinite(y)
        if ok.sum() < 8:
            continue
        c, med, lo, hi, _ = band(x[ok], y[ok], edges)
        if c.size == 0:
            continue
        col = SPECIES_COLOR.get(sp, None)
        ax.plot(c, med, "-o", ms=3.5, color=col, label=f"{sp}{label_suffix}")
        ax.fill_between(c, lo, hi, color=col, alpha=0.18, linewidth=0)


def savefig(fig, out: pathlib.Path, name: str) -> str:
    p = out / name
    fig.tight_layout()
    fig.savefig(p, dpi=150)
    plt.close(fig)
    print(f"  wrote {p.name}")
    return p.name


# ----------------------------------------------------------------------- plots
def make_plots(d: pd.DataFrame, out: pathlib.Path, sample_label: str) -> list[str]:
    written = []
    sp_present = [s for s in SPECIES_ORDER if s in set(d["species"])]
    e_edges = np.concatenate([np.arange(0, 20, 1.0), np.arange(20, 105, 2.5)])

    # 1. N_scint vs Edep
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.4))
    profile_plot(axes[0], d, "edep_raw_MeV", "n_scint_generated", e_edges, sp_present)
    axes[0].set_xlabel(r"$E_{\rm dep}$ (raw, unquenched) [MeV]")
    axes[1].set_xlabel(r"$E_{\rm dep}$ (Birks-visible) [MeV]")
    profile_plot(axes[1], d, "edep_vis_MeV", "n_scint_generated", e_edges, sp_present)
    for ax in axes:
        ax.set_ylabel(r"$N_{\rm scint}$ generated")
        ax.grid(alpha=0.3)
        ax.legend(fontsize=8)
    fig.suptitle(f"Scintillation photons vs deposited energy -- {sample_label}", fontsize=11)
    written.append(savefig(fig, out, "01_nscint_vs_edep.png"))

    # 2. arrivals and PE vs Edep
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.4))
    profile_plot(axes[0], d, "edep_raw_MeV", "arrival_readout", e_edges, sp_present)
    axes[0].set_ylabel(r"$N_{\rm SiPM}$ photons at the readout")
    profile_plot(axes[1], d, "edep_raw_MeV", "detected_readout", e_edges, sp_present)
    axes[1].set_ylabel(r"$N_{\rm pe}$ detected")
    for ax in axes:
        ax.set_xlabel(r"$E_{\rm dep}$ (raw) [MeV]")
        ax.grid(alpha=0.3)
        ax.legend(fontsize=8)
    fig.suptitle(f"Light reaching the readout vs deposited energy -- {sample_label}", fontsize=11)
    written.append(savefig(fig, out, "02_npe_vs_edep.png"))

    # 3. light yield per MeV vs Edep -- the non-linearity, directly.
    #    Split by primary fate: at one deposit a stopping primary and a
    #    punch-through one have very different dE/dx and so very different
    #    quenching, and pooling them makes the curve a function of the energy
    #    grid rather than of the detector.
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.4), sharey=True)
    for ax, fate in zip(axes, ("stopped", "punch-through")):
        sub = d[d["fate"] == fate]
        if len(sub) == 0:
            continue
        profile_plot(ax, sub, "edep_raw_MeV", "pe_per_MeV", e_edges, sp_present)
        ax.set_xlabel(r"$E_{\rm dep}$ (raw) [MeV]")
        ax.grid(alpha=0.3)
        ax.legend(fontsize=8)
        ax.set_title(f"primary {fate} in the bar  (n={len(sub)})", fontsize=10)
    axes[0].set_ylabel(r"$N_{\rm pe}/E_{\rm dep}$ [pe / MeV]")
    fig.suptitle(f"Light yield per deposited MeV -- {sample_label}", fontsize=11)
    written.append(savefig(fig, out, "03_lightyield_per_MeV_vs_edep.png"))

    # 4. vs dE/dx
    dd = d[np.isfinite(d["dedx_MeV_per_mm"]) & (d["dedx_MeV_per_mm"] > 0)]
    dedx_edges = np.logspace(np.log10(0.1), np.log10(60), 40)
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.4))
    profile_plot(axes[0], dd, "dedx_MeV_per_mm", "pe_per_MeV", dedx_edges, sp_present)
    axes[0].set_ylabel(r"$N_{\rm pe}/E_{\rm dep}$ [pe / MeV]")
    profile_plot(axes[1], dd, "dedx_MeV_per_mm", "birks_ratio", dedx_edges, sp_present)
    axes[1].set_ylabel(r"$E_{\rm vis}/E_{\rm dep}$ (Birks factor)")
    for ax in axes:
        ax.set_xscale("log")
        ax.set_xlabel(r"path-averaged $dE/dx$ of the primary [MeV/mm]")
        ax.grid(alpha=0.3, which="both")
        ax.legend(fontsize=8)
    fig.suptitle(f"Quenching vs stopping power -- {sample_label}", fontsize=11)
    written.append(savefig(fig, out, "04_yield_and_birks_vs_dedx.png"))

    # 5. Birks factor vs Edep, split by fate for the same reason as plot 3.
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.4), sharey=True)
    for ax, fate in zip(axes, ("stopped", "punch-through")):
        sub = d[d["fate"] == fate]
        if len(sub) == 0:
            continue
        profile_plot(ax, sub, "edep_raw_MeV", "birks_ratio", e_edges, sp_present)
        ax.set_xlabel(r"$E_{\rm dep}$ (raw) [MeV]")
        ax.grid(alpha=0.3)
        ax.legend(fontsize=8)
        ax.set_title(f"primary {fate} in the bar  (n={len(sub)})", fontsize=10)
    axes[0].set_ylabel(r"$E_{\rm vis}/E_{\rm dep}$")
    fig.suptitle(f"Birks-quenched fraction vs deposit -- {sample_label}", fontsize=11)
    written.append(savefig(fig, out, "05_birks_ratio_vs_edep.png"))

    # 6. position dependence in fixed deposit bands
    bands = [(3, 6), (10, 13), (20, 25), (40, 46)]
    for tag, xcol, xlabel, edges in [
        ("long", "dist_to_sipm_cm", "distance from hit to the SiPM end [cm]",
         np.arange(0, 50.1, 2.5)),
        ("trans", "dist_to_readout_fibre_cm",
         "transverse distance from hit to the readout WLS fibre [cm]",
         np.arange(0, 3.7, 0.2)),
    ]:
        fig, ax = plt.subplots(figsize=(6.8, 4.6))
        for (lo, hi) in bands:
            sel = (d["edep_raw_MeV"] >= lo) & (d["edep_raw_MeV"] < hi)
            if sel.sum() < 50:
                continue
            x = d.loc[sel, xcol].to_numpy(float)
            y = d.loc[sel, "detected_readout"].to_numpy(float)
            c, med, blo, bhi, _ = band(x, y, edges)
            if c.size == 0:
                continue
            line, = ax.plot(c, med, "-o", ms=3.5,
                            label=rf"$E_{{\rm dep}}\in[{lo},{hi})$ MeV  (n={int(sel.sum())})")
            ax.fill_between(c, blo, bhi, color=line.get_color(), alpha=0.18, linewidth=0)
        ax.set_xlabel(xlabel)
        ax.set_ylabel(r"$N_{\rm pe}$ detected")
        ax.grid(alpha=0.3)
        ax.legend(fontsize=8)
        ax.set_title(f"Light collection vs hit position -- {sample_label}", fontsize=11)
        written.append(savefig(fig, out, f"06_position_{tag}.png"))

    # 7. proton vs deuteron -- the headline comparison
    if {"proton", "deuteron"} <= set(sp_present):
        fig, axes = plt.subplots(1, 2, figsize=(11, 4.4))
        for sp, win in [("proton", (11, 12)), ("deuteron", (42, 45))]:
            sel = ((d["species"] == sp) & (d["edep_raw_MeV"] >= win[0])
                   & (d["edep_raw_MeV"] < win[1]))
            if sel.sum() < 10:
                continue
            axes[0].hist(d.loc[sel, "detected_readout"], bins=60, histtype="step",
                         density=True, color=SPECIES_COLOR[sp], linewidth=1.6,
                         label=rf"{sp}, $E_{{\rm dep}}\in[{win[0]},{win[1]})$ MeV "
                               f"(n={int(sel.sum())})")
        axes[0].set_xlabel(r"$N_{\rm pe}$ detected")
        axes[0].set_ylabel("normalised events")
        axes[0].legend(fontsize=8)
        axes[0].grid(alpha=0.3)
        axes[0].set_title("B2-like deposit windows", fontsize=10)

        for sp in ("proton", "deuteron"):
            sel = d["species"] == sp
            for fate, ls in (("stopped", "-"), ("punch-through", "--")):
                s2 = sel & (d["fate"] == fate)
                if s2.sum() < 30:
                    continue
                x = d.loc[s2, "edep_raw_MeV"].to_numpy(float)
                y = d.loc[s2, "detected_readout"].to_numpy(float)
                c, med, lo, hi, _ = band(x, y, e_edges)
                if c.size == 0:
                    continue
                axes[1].plot(c, med, ls, color=SPECIES_COLOR[sp], marker="o", ms=3,
                             label=f"{sp} ({fate})")
                axes[1].fill_between(c, lo, hi, color=SPECIES_COLOR[sp],
                                     alpha=0.12, linewidth=0)
        axes[1].set_xlabel(r"$E_{\rm dep}$ (raw) [MeV]")
        axes[1].set_ylabel(r"$N_{\rm pe}$ detected")
        axes[1].legend(fontsize=8)
        axes[1].grid(alpha=0.3)
        axes[1].set_title("stopping vs punch-through", fontsize=10)
        fig.suptitle(f"Proton vs deuteron response -- {sample_label}", fontsize=11)
        written.append(savefig(fig, out, "07_proton_vs_deuteron.png"))

    # 8. ADC-equivalent
    if d["adc_readout"].abs().sum() > 0:
        fig, ax = plt.subplots(figsize=(6.4, 4.6))
        profile_plot(ax, d, "edep_raw_MeV", "adc_readout", e_edges, sp_present)
        ax.set_xlabel(r"$E_{\rm dep}$ (raw) [MeV]")
        ax.set_ylabel("peak ADC above baseline")
        ax.grid(alpha=0.3)
        ax.legend(fontsize=8)
        ax.set_title(f"ADC-equivalent signal -- {sample_label}", fontsize=11)
        written.append(savefig(fig, out, "08_adc_vs_edep.png"))
    return written


# ---------------------------------------------------------------- headline stats
def _window_stats(d: pd.DataFrame, sp: str, win, fate: str | None) -> dict:
    sel = ((d["species"] == sp) & (d["edep_raw_MeV"] >= win[0])
           & (d["edep_raw_MeV"] < win[1]))
    if fate is not None:
        sel = sel & (d["fate"] == fate)
    n = int(sel.sum())
    if n == 0:
        return {"n": 0}
    s = d.loc[sel]
    return {
        "n": n,
        "edep_raw_median_MeV": float(s["edep_raw_MeV"].median()),
        "edep_vis_median_MeV": float(s["edep_vis_MeV"].median()),
        "birks_ratio_median": float(s["birks_ratio"].median()),
        "n_scint_median": float(s["n_scint_generated"].median()),
        "n_arrival_median": float(s["arrival_readout"].median()),
        "n_pe_median": float(s["detected_readout"].median()),
        "n_pe_p16": float(s["detected_readout"].quantile(0.16)),
        "n_pe_p84": float(s["detected_readout"].quantile(0.84)),
        "adc_median": float(s["adc_readout"].median()),
        "stopped_fraction": float((s["primary_stopped"] == 1).mean()),
        "ke_setting_median_MeV": float(s["ke_setting_MeV"].median()),
    }


def _ratios(p: dict, dd: dict) -> dict | None:
    if not p.get("n") or not dd.get("n"):
        return None
    return {
        "edep_raw": dd["edep_raw_median_MeV"] / p["edep_raw_median_MeV"],
        "edep_visible": dd["edep_vis_median_MeV"] / p["edep_vis_median_MeV"],
        "n_scint": dd["n_scint_median"] / p["n_scint_median"],
        "n_arrival": dd["n_arrival_median"] / p["n_arrival_median"],
        "n_pe": dd["n_pe_median"] / p["n_pe_median"],
        "adc": (dd["adc_median"] / p["adc_median"]) if p["adc_median"] else None,
    }


def compression_report(d: pd.DataFrame, p_win, d_win) -> dict:
    """Deuteron/proton response ratio at the quoted B2 deposit windows.

    Split by primary fate. A given raw-deposit window is fed by two physically
    different populations -- a low-energy primary that ranges out in the bar and
    a high-energy one that punches through -- with very different dE/dx and so
    very different Birks quenching. Pooling them makes the ratio a function of
    the energy-grid weights rather than of the detector, so the fate-resolved
    pairs are reported alongside the pooled one. In the CCB the B2 deuteron
    stops and the B2 proton punches through: `matched_b2` is that pair.
    """
    out = {"proton_window_MeV": list(p_win), "deuteron_window_MeV": list(d_win)}
    for sp, win, key in (("proton", p_win, "proton"), ("deuteron", d_win, "deuteron")):
        out[key] = _window_stats(d, sp, win, None)
        out[f"{key}_stopped"] = _window_stats(d, sp, win, "stopped")
        out[f"{key}_punch_through"] = _window_stats(d, sp, win, "punch-through")
    out["ratios_deuteron_over_proton"] = _ratios(out["proton"], out["deuteron"])
    out["ratios_matched_b2_stoppingD_over_punchthroughP"] = _ratios(
        out["proton_punch_through"], out["deuteron_stopped"]
    )
    out["ratios_both_stopped"] = _ratios(out["proton_stopped"], out["deuteron_stopped"])
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--inputs", nargs="+", required=True, help="ROOT files or globs")
    ap.add_argument("--out", required=True, help="output directory")
    ap.add_argument("--proton-window", nargs=2, type=float, default=[11.0, 12.0],
                    help="raw-Edep window quoted for protons in B2 [MeV]")
    ap.add_argument("--deuteron-window", nargs=2, type=float, default=[42.0, 45.0],
                    help="raw-Edep window quoted for deuterons in B2 [MeV]")
    args = ap.parse_args()

    paths: list[str] = []
    for p in args.inputs:
        paths.extend(sorted(glob.glob(p)))
    if not paths:
        raise SystemExit("no input files matched")
    print(f"reading {len(paths)} ROOT files")

    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    d = derive(load(paths))
    print(f"events: {len(d)}")

    # event-level deliverables
    keep = [c for c in d.columns if c != "source_file"] + ["source_file"]
    d[keep].to_parquet(out / "events_1623.parquet", index=False)
    d[keep].to_csv(out / "events_1623.csv.gz", index=False, compression="gzip")
    print(f"  wrote events_1623.parquet / events_1623.csv.gz ({len(d)} rows)")

    # per-point summary
    g = d.groupby(["species", "sample", "ke_setting_MeV"], as_index=False).agg(
        n=("event", "size"),
        edep_raw_median=("edep_raw_MeV", "median"),
        edep_raw_p16=("edep_raw_MeV", lambda s: s.quantile(0.16)),
        edep_raw_p84=("edep_raw_MeV", lambda s: s.quantile(0.84)),
        edep_vis_median=("edep_vis_MeV", "median"),
        birks_ratio_median=("birks_ratio", "median"),
        dedx_median=("dedx_MeV_per_mm", "median"),
        path_mm_median=("path_mm", "median"),
        n_scint_median=("n_scint_generated", "median"),
        arrival_median=("arrival_readout", "median"),
        pe_median=("detected_readout", "median"),
        pe_p16=("detected_readout", lambda s: s.quantile(0.16)),
        pe_p84=("detected_readout", lambda s: s.quantile(0.84)),
        pe_per_MeV_median=("pe_per_MeV", "median"),
        adc_median=("adc_readout", "median"),
        stopped_frac=("primary_stopped", "mean"),
    )
    g.to_csv(out / "summary_by_point.csv", index=False)
    print(f"  wrote summary_by_point.csv ({len(g)} points)")

    figures = {}
    report = {
        "n_events": int(len(d)),
        "n_files": len(paths),
        "species": sorted(set(d["species"])),
        "samples": sorted(set(d["sample"])),
        "geometry": {
            "readout_end_x_cm": READOUT_END_X_CM,
            "readout_fibre_y_cm": FIBRE_Y_CM,
            "stave_half_z_cm": STAVE_HALF_Z_CM,
        },
    }
    for sample, label in (("A", "distributed sample"), ("B", "central reference")):
        sub = d[d["sample"] == sample]
        if len(sub) == 0:
            continue
        sub_out = out / f"sample_{sample}"
        sub_out.mkdir(exist_ok=True)
        print(f"sample {sample} ({label}): {len(sub)} events")
        figures[sample] = make_plots(sub, sub_out, label)
        report[f"compression_sample_{sample}"] = compression_report(
            sub, args.proton_window, args.deuteron_window
        )
    killed_time = int(d["n_optical_killed_time"].sum()) if "n_optical_killed_time" in d else 0
    killed_steps = int(d["n_optical_killed_steps"].sum()) if "n_optical_killed_steps" in d else 0
    gen_total = int(d["n_scint_generated"].sum() + d["n_wls_generated"].sum()
                    + d["n_cerenkov_generated"].sum())
    report["optical_transport_guard"] = {
        "optical_max_time_ns": sorted(set(d.get("optical_max_time_ns", pd.Series([0.0])))),
        "optical_max_steps": sorted(set(d.get("optical_max_steps", pd.Series([0])))),
        "photons_killed_by_time": killed_time,
        "photons_killed_by_steps": killed_steps,
        "optical_photons_generated": gen_total,
        "killed_fraction": (killed_time + killed_steps) / gen_total if gen_total else 0.0,
        "events_with_any_kill": int(
            ((d.get("n_optical_killed_time", 0) > 0)
             | (d.get("n_optical_killed_steps", 0) > 0)).sum()
        ),
    }
    report["figures"] = figures
    (out / "report_1623.json").write_text(json.dumps(report, indent=2))
    print(f"  wrote report_1623.json")

    for sample in ("A", "B"):
        key = f"compression_sample_{sample}"
        if key not in report:
            continue
        blk = report[key]
        print(f"\n== sample {sample}: deuteron/proton at the B2 deposit windows ==")
        for pop in ("proton", "proton_punch_through", "proton_stopped",
                    "deuteron", "deuteron_stopped", "deuteron_punch_through"):
            st = blk.get(pop, {})
            if st.get("n"):
                print(f"   {pop:26s} n={st['n']:6d} Edep={st['edep_raw_median_MeV']:6.2f} MeV "
                      f"Evis={st['edep_vis_median_MeV']:6.2f} birks={st['birks_ratio_median']:.3f} "
                      f"Npe={st['n_pe_median']:8.1f}")
            else:
                print(f"   {pop:26s} n=0")
        for rk in ("ratios_deuteron_over_proton",
                   "ratios_matched_b2_stoppingD_over_punchthroughP",
                   "ratios_both_stopped"):
            r = blk.get(rk)
            if not r:
                continue
            print(f"   -- {rk} --")
            for k, v in r.items():
                print(f"      {k:14s} {v:.3f}" if v is not None else f"      {k:14s} n/a")


if __name__ == "__main__":
    main()
