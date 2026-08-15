#!/usr/bin/env python3
"""#1303 optical-stage accounting over the regenerated 5-point calibration grid.

Reads stave_<species>_<E>MeV_x0_y0_th0_ph0_s1.root (+ .meta.json receipts) from
the regenerated campaign dir and produces the stage-resolved response tables and
figures the paper requires (ch08 contract + #1322 figure package):

  tables/1303_stage_accounting.csv   per point x channel: mean stage counts and
                                     conditional efficiencies with explicit
                                     denominators
  tables/1303_pe_per_mev.csv         per point: PE/MeV on BOTH denominators
                                     (E_vis = edep_scint_MeV, Birks-visible,
                                     historical definition; E_raw =
                                     edep_scint_raw_MeV, unquenched) with
                                     bootstrap CIs
  figures/1303_stage_accounting.pdf  per-point stage waterfalls (log scale)
  figures/1303_pe_per_mev.pdf        PE/MeV vs kinetic energy, both
                                     denominators, superseded July values as
                                     open markers
  figures/1303_edep_vs_pe.pdf        regenerated calibration scatter + pooled
                                     fit (supersedes gated G4CAL-01)
  1303_summary.json                  numbers + per-point provenance (commit,
                                     geometry/physics/optical hashes, model
                                     assumption flags from meta.json)

Status label for all outputs: MC_MODEL_DEPENDENT. The stage chain is
n_scint_generated -> n_wls_generated -> arrival_<ch> -> detected_<ch> ->
pe_sat_<ch> (independent diagnostic draw, #1084) with adc_<ch> the ccb-sipm-core
response branch. No absolute light-yield claim is made (hardware constants
remain MANUFACTURER_REPRESENTATIVE / unverified; see meta flags carried through).
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import uproot  # noqa: E402

CHANNELS = ("readout", "f1far", "f2near", "f2far")
STAGES = ("n_scint_generated", "n_wls_generated")  # per-channel stages below
HISTORICAL_SUPERSEDED = {  # July grid values from issue #1303 (GATED, superseded)
    ("proton", 60): {"pe": 282.0, "pe_per_mev": 9.85},
    ("proton", 100): {"pe": 177.0, "pe_per_mev": 10.9},
    ("proton", 140): {"pe": 140.0, "pe_per_mev": 11.0},
    ("deuteron", 70): {"pe": 432.0, "pe_per_mev": 8.7},
    ("deuteron", 110): {"pe": 276.0, "pe_per_mev": 9.6},
}
SPECIES_COLORS = {"proton": "tab:blue", "deuteron": "tab:orange"}
BOOT_N = 500
BOOT_SEED = 20260814


def parse_meta(meta_path: str) -> dict:
    with open(meta_path) as fh:
        return json.load(fh)


def load_point(root_path: str) -> dict:
    m = re.match(r".*stave_(\w+)_(\d+)MeV_.*_s(\d+)\.root$", root_path)
    if m is None:
        raise ValueError(f"unparseable filename: {root_path}")
    species, ke, seed = m.group(1), int(m.group(2)), int(m.group(3))
    with uproot.open(root_path) as f:
        t = f["events"]
        keep = ["edep_scint_MeV", "edep_scint_raw_MeV", "primary_edep_scint_MeV",
                "primary_edep_scint_raw_MeV", "track_len_scint_mm",
                "primary_track_len_scint_mm"]
        for st in STAGES:
            keep.append(st)
        for ch in CHANNELS:
            keep += [f"arrival_{ch}", f"detected_{ch}", f"pe_sat_{ch}", f"adc_{ch}"]
        arr = t.arrays(keep, library="np")
    return {"species": species, "ke_MeV": ke, "seed": seed, "n": t.num_entries,
            "data": arr}


def ratio_bootstrap(pe: np.ndarray, ed: np.ndarray, n_boot: int = BOOT_N,
                    seed: int = BOOT_SEED) -> dict:
    """Bootstrap CI for mean(pe)/mean(ed) (per-event iid resampling)."""
    rng = np.random.default_rng(seed)
    n = len(pe)
    idx = rng.integers(0, n, size=(n_boot, n))
    draws = pe[idx].mean(axis=1) / ed[idx].mean(axis=1)
    return {"mean": float(pe.mean() / ed.mean()),
            "ci16": float(np.percentile(draws, 16)),
            "ci84": float(np.percentile(draws, 84)),
            "pe_mean": float(pe.mean()), "ed_mean": float(ed.mean())}


def point_stats(pt: dict) -> dict:
    d = pt["data"]
    evis, eraw = d["edep_scint_MeV"], d["edep_scint_raw_MeV"]
    out: dict = {
        "species": pt["species"], "ke_MeV": pt["ke_MeV"], "seed": pt["seed"],
        "n_events": pt["n"],
        "E_vis_mean_MeV": float(evis.mean()), "E_raw_mean_MeV": float(eraw.mean()),
        "E_vis_sem": float(evis.std(ddof=1) / np.sqrt(len(evis))),
        "E_raw_sem": float(eraw.std(ddof=1) / np.sqrt(len(eraw))),
        "quench_ratio_Evis_over_Eraw": float(evis.sum() / eraw.sum()),
        "pe_per_mev_E_vis": ratio_bootstrap(d["detected_readout"], evis),
        "pe_per_mev_E_raw": ratio_bootstrap(d["detected_readout"], eraw),
        "channels": {},
    }
    for ch in CHANNELS:
        det, arrv, pes, adc = (d[f"detected_{ch}"], d[f"arrival_{ch}"],
                               d[f"pe_sat_{ch}"], d[f"adc_{ch}"])
        out["channels"][ch] = {
            "scint_generated_mean": float(d["n_scint_generated"].mean()),
            "wls_generated_mean": float(d["n_wls_generated"].mean()),
            "arrival_mean": float(arrv.mean()),
            "detected_mean": float(det.mean()),
            "pe_sat_mean": float(pes.mean()),
            "adc_mean": float(adc.mean()),
            "eps_wls_capture": float(d["n_wls_generated"].sum()
                                     / d["n_scint_generated"].sum()),
            "eps_transport": float(arrv.sum() / d["n_wls_generated"].sum()),
            "eps_detect_given_arrival": float(det.sum() / arrv.sum()),
            "pe_sat_over_detected": float(pes.sum() / det.sum()) if det.sum() else None,
            "adc_over_detected": float(adc.sum() / det.sum()) if det.sum() else None,
        }
    return out


def stage_accounting_figure(stats: list[dict], outdir: str) -> None:
    fig, axes = plt.subplots(1, len(stats), figsize=(3.1 * len(stats), 4.0),
                             sharey=False)
    for ax, s in zip(np.atleast_1d(axes), stats):
        c = s["channels"]["readout"]
        labels = ["scint\nngen", "WLS\nngen", "arrival\nreadout",
                  "detected\nreadout", "pe_sat\nreadout"]
        vals = [c["scint_generated_mean"], c["wls_generated_mean"],
                c["arrival_mean"], c["detected_mean"], c["pe_sat_mean"]]
        bars = ax.bar(range(5), vals, color="tab:blue", alpha=0.75)
        ax.set_yscale("log")
        ax.set_xticks(range(5), labels, fontsize=6)
        ax.set_title(f"{s['species']} {s['ke_MeV']} MeV\n(n={s['n_events']:,})",
                     fontsize=9)
        ax.tick_params(labelsize=7)
        for b, v in zip(bars, vals):
            ax.text(b.get_x() + b.get_width() / 2, v * 1.15, f"{v:.3g}",
                    ha="center", fontsize=6)
        ax.text(0.02, 0.02,
                (f"eps_WLS={c['eps_wls_capture']:.3f}\n"
                 f"eps_tr={c['eps_transport']:.3f}\n"
                 f"eps_det={c['eps_detect_given_arrival']:.3f}"),
                transform=ax.transAxes, fontsize=6.5, va="bottom",
                bbox=dict(fc="white", alpha=0.7, ec="none"))
        ax.set_ylabel("mean per event (log)", fontsize=8)
    fig.suptitle("Optical stage accounting, regenerated grid (#1303) — readout channel; "
                 "MC_MODEL_DEPENDENT", fontsize=11)
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    for ext in ("png", "pdf"):
        fig.savefig(os.path.join(outdir, f"1303_stage_accounting.{ext}"), dpi=180)
    plt.close(fig)


def pe_per_mev_figure(stats: list[dict], outdir: str) -> None:
    fig, ax = plt.subplots(figsize=(7.0, 4.6))
    for species, color in SPECIES_COLORS.items():
        pts = sorted([s for s in stats if s["species"] == species],
                     key=lambda s: s["ke_MeV"])
        if not pts:
            continue
        for denom, marker, ls in (("pe_per_mev_E_vis", "o", "-"),
                                  ("pe_per_mev_E_raw", "^", "--")):
            x = [p["ke_MeV"] for p in pts]
            y = [p[denom]["mean"] for p in pts]
            lo = [p[denom]["mean"] - p[denom]["ci16"] for p in pts]
            hi = [p[denom]["ci84"] - p[denom]["mean"] for p in pts]
            lbl = (f"{species}, PE/E_vis (Birks)" if denom == "pe_per_mev_E_vis"
                   else f"{species}, PE/E_raw (unquenched)")
            ax.errorbar(x, y, yerr=[lo, hi], marker=marker, ls=ls, color=color,
                        ms=5, lw=1.3, capsize=3, label=lbl)
        hx = [p["ke_MeV"] for p in pts]
        hy = [HISTORICAL_SUPERSEDED.get((species, p["ke_MeV"]), {}).get("pe_per_mev")
              for p in pts]
        ax.scatter(hx, hy, marker="x", color=color, alpha=0.6, s=42,
                   label=f"{species} July grid (SUPERSEDED, gated)" if species == "proton"
                   else None)
    ax.set_xlabel("primary kinetic energy [MeV]", fontsize=9)
    ax.set_ylabel("detected PE per MeV (readout channel)", fontsize=9)
    ax.set_title("Regenerated light-collection scale vs July grid (#1303); "
                 "68% bootstrap CIs; MC_MODEL_DEPENDENT", fontsize=10)
    ax.tick_params(labelsize=8)
    ax.legend(fontsize=7, loc="best")
    fig.tight_layout()
    for ext in ("png", "pdf"):
        fig.savefig(os.path.join(outdir, f"1303_pe_per_mev.{ext}"), dpi=180)
    plt.close(fig)


def pooled_cal(stats_meta: list[tuple[dict, dict]], outdir: str) -> dict:
    """Pooled E_vis/PE fit across all events (supersedes gated G4CAL-01)."""
    ed_all, pe_all, sp_all = [], [], []
    for pt, _meta in stats_meta:
        d = pt["data"]
        ed_all.append(d["edep_scint_MeV"])
        pe_all.append(d["detected_readout"])
        sp_all.append(np.full(int(pt["n"]), pt["species"]))
    ed = np.concatenate(ed_all)
    pe = np.concatenate(pe_all)
    sp = np.concatenate(sp_all)
    m, b = np.polyfit(ed, pe, 1)
    resid = pe - (m * ed + b)
    r2 = 1.0 - np.var(resid) / np.var(pe)
    fig, ax = plt.subplots(figsize=(6.4, 4.6))
    for species, mk in (("proton", "o"), ("deuteron", "s")):
        s = sp == species
        if s.any():
            ax.scatter(ed[s], pe[s], s=4, alpha=0.25, marker=mk,
                       color=SPECIES_COLORS[species], label=species, linewidths=0)
    xs = np.linspace(ed.min(), ed.max(), 60)
    ax.plot(xs, m * xs + b, "k-", lw=1.5,
            label=f"pooled fit: {m:.1f} PE/MeV_Evis (r2={r2:.3f})")
    ax.set_xlabel(r"$E_{\rm vis}$ = edep_scint (Birks-visible) [MeV]", fontsize=9)
    ax.set_ylabel("detected photoelectrons (readout)", fontsize=9)
    ax.set_title("Regenerated single-stave calibration (supersedes gated G4CAL-01); "
                 "MC_MODEL_DEPENDENT", fontsize=10)
    ax.legend(fontsize=8)
    ax.tick_params(labelsize=8)
    fig.tight_layout()
    for ext in ("png", "pdf"):
        fig.savefig(os.path.join(outdir, f"1303_edep_vs_pe.{ext}"), dpi=180)
    plt.close(fig)
    return {"slope_PE_per_MeV_E_vis": float(m), "offset_PE": float(b),
            "r2": float(r2), "n_events": int(len(ed))}


def write_tables(stats: list[dict], outdir_tables: str) -> None:
    os.makedirs(outdir_tables, exist_ok=True)
    import csv
    stage_path = os.path.join(outdir_tables, "1303_stage_accounting.csv")
    with open(stage_path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["species", "ke_MeV", "channel", "n_events",
                    "scint_gen_mean", "wls_gen_mean", "arrival_mean",
                    "detected_mean", "pe_sat_mean", "adc_mean",
                    "eps_wls_capture", "eps_transport",
                    "eps_detect_given_arrival", "pe_sat_over_detected",
                    "adc_over_detected"])
        for s in stats:
            for ch, c in s["channels"].items():
                w.writerow([s["species"], s["ke_MeV"], ch, s["n_events"],
                            c["scint_generated_mean"], c["wls_generated_mean"],
                            c["arrival_mean"], c["detected_mean"],
                            c["pe_sat_mean"], c["adc_mean"],
                            c["eps_wls_capture"], c["eps_transport"],
                            c["eps_detect_given_arrival"],
                            c["pe_sat_over_detected"], c["adc_over_detected"]])
    ppm_path = os.path.join(outdir_tables, "1303_pe_per_mev.csv")
    with open(ppm_path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["species", "ke_MeV", "n_events", "E_vis_mean_MeV",
                    "E_raw_mean_MeV", "quench_ratio",
                    "pe_per_mev_E_vis", "ci16_E_vis", "ci84_E_vis",
                    "pe_per_mev_E_raw", "ci16_E_raw", "ci84_E_raw",
                    "july_pe_per_mev_SUPERSEDED"])
        for s in stats:
            hv, hr = s["pe_per_mev_E_vis"], s["pe_per_mev_E_raw"]
            w.writerow([s["species"], s["ke_MeV"], s["n_events"],
                        s["E_vis_mean_MeV"], s["E_raw_mean_MeV"],
                        s["quench_ratio_Evis_over_Eraw"],
                        hv["mean"], hv["ci16"], hv["ci84"],
                        hr["mean"], hr["ci16"], hr["ci84"],
                        HISTORICAL_SUPERSEDED.get(
                            (s["species"], s["ke_MeV"]), {}).get("pe_per_mev")])


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--grid-dir", required=True,
                    help="directory of stave_*.root + .meta.json (#1303 regen)")
    ap.add_argument("--output", required=True, help="bundle output directory")
    args = ap.parse_args()

    os.makedirs(os.path.join(args.output, "figures"), exist_ok=True)
    os.makedirs(os.path.join(args.output, "tables"), exist_ok=True)

    roots = sorted(glob.glob(os.path.join(args.grid_dir, "stave_*.root")))
    pts, metas, stats = [], [], []
    for r in roots:
        meta_path = r + ".meta.json"
        if not os.path.exists(meta_path):
            print(f"SKIP (no meta receipt): {os.path.basename(r)}")
            continue
        pt = load_point(r)
        meta = parse_meta(meta_path)
        if pt["n"] < meta.get("n_events_requested", pt["n"]):
            print(f"SKIP (incomplete: {pt['n']}/{meta['n_events_requested']}): "
                  f"{os.path.basename(r)}")
            continue
        pts.append(pt)
        metas.append(meta)
        stats.append(point_stats(pt))
        print(f"OK {os.path.basename(r)}: n={pt['n']}")

    if len(stats) < 2:
        raise SystemExit("fewer than 2 complete points — aborting")

    figdir = os.path.join(args.output, "figures")
    stage_accounting_figure(stats, figdir)
    pe_per_mev_figure(stats, figdir)
    pooled = pooled_cal(list(zip(pts, metas)), figdir)
    write_tables(stats, os.path.join(args.output, "tables"))

    prov = []
    for pt, meta in zip(pts, metas):
        prov.append({
            "file": os.path.basename(pt["_path"]) if "_path" in pt else None,
            "species": pt["species"], "ke_MeV": pt["ke_MeV"],
            "git_commit": meta.get("git_commit"),
            "geometry_hash": meta.get("geometry_hash"),
            "physics_hash": meta.get("physics_hash"),
            "optical_hash": meta.get("optical_hash"),
            "strict_optical": meta.get("strict_optical"),
            "authorising_absolute_light_yield_claims":
                meta.get("authorising_absolute_light_yield_claims"),
            "model_status_flags": {k: meta.get(k) for k in (
                "wls_fluorescence_status", "tio2_reflection_model_status",
                "scintillator_material_status", "hrd_fibre_count_status",
                "attenuation_identifiability_status", "y11_direct_scint_status",
                "step_size_convergence_status")},
        })
    summary = {
        "schema": "ccb-paper-1303-optical-stage-accounting/1",
        "status_label": "MC_MODEL_DEPENDENT",
        "grid_dir": args.grid_dir,
        "n_points": len(stats),
        "points": stats,
        "pooled_calibration_E_vis": pooled,
        "provenance": prov,
        "superseded_july_values": ({"|".join(map(str, k)): v for k, v in
                                    HISTORICAL_SUPERSEDED.items()}),
        "notes": ("PE/MeV reported on both denominators: E_vis (Birks-visible, "
                  "historical definition) and E_raw (unquenched). pe_sat_* is an "
                  "independent diagnostic draw (#1084), adc_* is the ccb-sipm-core "
                  "response branch. No absolute light-yield claim."),
    }
    with open(os.path.join(args.output, "1303_summary.json"), "w") as fh:
        json.dump(summary, fh, indent=1)
    print("WROTE", args.output)


if __name__ == "__main__":
    main()
