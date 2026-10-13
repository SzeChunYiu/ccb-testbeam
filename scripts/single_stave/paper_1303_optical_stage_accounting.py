#!/usr/bin/env python3
"""#1303 optical-stage accounting over the regenerated calibration grid.

The tables and numerical estimands are unchanged. Publication figures are
purposefully minimal: no issue IDs, governance labels, repeated numerical
textboxes, or superseded-history overlays are printed inside the scientific
artwork. Those details remain in the source tables, summary JSON and manuscript
captions.

Outputs:
  tables/1303_stage_accounting.csv
  tables/1303_pe_per_mev.csv
  figures/1303_stage_accounting.pdf
  figures/1303_pe_per_mev.pdf
  figures/1303_edep_vs_pe.pdf
  1303_summary.json
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import uproot

CHANNELS = ("readout", "f1far", "f2near", "f2far")
STAGES = ("n_scint_generated", "n_wls_generated")
HISTORICAL_SUPERSEDED = {
    ("proton", 60): {"pe": 282.0, "pe_per_mev": 9.85},
    ("proton", 100): {"pe": 177.0, "pe_per_mev": 10.9},
    ("proton", 140): {"pe": 140.0, "pe_per_mev": 11.0},
    ("deuteron", 70): {"pe": 432.0, "pe_per_mev": 8.7},
    ("deuteron", 110): {"pe": 276.0, "pe_per_mev": 9.6},
}
SPECIES_COLORS = {"proton": "#4477AA", "deuteron": "#CC6677"}
BOOT_N = 500
BOOT_SEED = 20260814


def parse_meta(meta_path: str) -> dict:
    with open(meta_path, encoding="utf-8") as fh:
        return json.load(fh)


def load_point(root_path: str) -> dict:
    match = re.match(r".*stave_(\w+)_(\d+)MeV_.*_s(\d+)\.root$", root_path)
    if match is None:
        raise ValueError(f"unparseable filename: {root_path}")
    species, ke, seed = match.group(1), int(match.group(2)), int(match.group(3))
    with uproot.open(root_path) as root_file:
        tree = root_file["events"]
        keep = [
            "edep_scint_MeV", "edep_scint_raw_MeV", "primary_edep_scint_MeV",
            "primary_edep_scint_raw_MeV", "track_len_scint_mm",
            "primary_track_len_scint_mm",
        ]
        keep.extend(STAGES)
        for channel in CHANNELS:
            keep += [
                f"arrival_{channel}", f"detected_{channel}",
                f"pe_sat_{channel}", f"adc_{channel}",
            ]
        arr = tree.arrays(keep, library="np")
        n_entries = int(tree.num_entries)
    return {
        "_path": root_path,
        "species": species,
        "ke_MeV": ke,
        "seed": seed,
        "n": n_entries,
        "data": arr,
    }


def ratio_bootstrap(pe: np.ndarray, ed: np.ndarray, n_boot: int = BOOT_N,
                    seed: int = BOOT_SEED) -> dict:
    rng = np.random.default_rng(seed)
    n = len(pe)
    idx = rng.integers(0, n, size=(n_boot, n))
    draws = pe[idx].mean(axis=1) / ed[idx].mean(axis=1)
    return {
        "mean": float(pe.mean() / ed.mean()),
        "ci16": float(np.percentile(draws, 16)),
        "ci84": float(np.percentile(draws, 84)),
        "pe_mean": float(pe.mean()),
        "ed_mean": float(ed.mean()),
    }


def point_stats(pt: dict) -> dict:
    data = pt["data"]
    evis = data["edep_scint_MeV"]
    eraw = data["edep_scint_raw_MeV"]
    out: dict = {
        "species": pt["species"],
        "ke_MeV": pt["ke_MeV"],
        "seed": pt["seed"],
        "n_events": pt["n"],
        "E_vis_mean_MeV": float(evis.mean()),
        "E_raw_mean_MeV": float(eraw.mean()),
        "E_vis_sem": float(evis.std(ddof=1) / np.sqrt(len(evis))),
        "E_raw_sem": float(eraw.std(ddof=1) / np.sqrt(len(eraw))),
        "quench_ratio_Evis_over_Eraw": float(evis.sum() / eraw.sum()),
        "pe_per_mev_E_vis": ratio_bootstrap(data["detected_readout"], evis),
        "pe_per_mev_E_raw": ratio_bootstrap(data["detected_readout"], eraw),
        "channels": {},
    }
    for channel in CHANNELS:
        detected = data[f"detected_{channel}"]
        arrival = data[f"arrival_{channel}"]
        pe_sat = data[f"pe_sat_{channel}"]
        adc = data[f"adc_{channel}"]
        out["channels"][channel] = {
            "scint_generated_mean": float(data["n_scint_generated"].mean()),
            "wls_generated_mean": float(data["n_wls_generated"].mean()),
            "arrival_mean": float(arrival.mean()),
            "detected_mean": float(detected.mean()),
            "pe_sat_mean": float(pe_sat.mean()),
            "adc_mean": float(adc.mean()),
            "eps_wls_capture": float(data["n_wls_generated"].sum()
                                     / data["n_scint_generated"].sum()),
            "eps_transport": float(arrival.sum() / data["n_wls_generated"].sum()),
            "eps_detect_given_arrival": float(detected.sum() / arrival.sum()),
            "pe_sat_over_detected": (
                float(pe_sat.sum() / detected.sum()) if detected.sum() else None
            ),
            "adc_over_detected": (
                float(adc.sum() / detected.sum()) if detected.sum() else None
            ),
        }
    return out


def _clean_axes(ax) -> None:
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.tick_params(direction="out", length=3, width=0.8, labelsize=8)
    ax.grid(axis="y", alpha=0.15, lw=0.6)


def _save(fig, outdir: str, stem: str) -> None:
    fig.tight_layout()
    for ext in ("png", "pdf"):
        fig.savefig(os.path.join(outdir, f"{stem}.{ext}"), dpi=220,
                    bbox_inches="tight")
    plt.close(fig)


def stage_accounting_figure(stats: list[dict], outdir: str) -> None:
    """One response-chain panel; no repeated waterfall textboxes.

    Each curve is normalised to that operating point's scintillation-photon
    mean. This makes the figure about survival through the response chain,
    while the absolute means and exact conditional efficiencies remain in the
    source table.
    """
    stage_labels = ["Scintillation", "WLS emission", "Sensor arrival",
                    "Detected", "After occupancy"]
    x = np.arange(len(stage_labels))
    fig, ax = plt.subplots(figsize=(6.4, 4.1))
    for stat in sorted(stats, key=lambda s: (s["species"], s["ke_MeV"])):
        c = stat["channels"]["readout"]
        values = np.array([
            c["scint_generated_mean"], c["wls_generated_mean"],
            c["arrival_mean"], c["detected_mean"], c["pe_sat_mean"],
        ], dtype=float)
        fractions = values / values[0]
        label = f"{stat['species']} {stat['ke_MeV']} MeV"
        ax.plot(x, fractions, marker="o", ms=4.5, lw=1.2,
                color=SPECIES_COLORS[stat["species"]],
                alpha=0.72 if stat["species"] == "proton" else 0.9,
                label=label)
    ax.set_yscale("log")
    ax.set_xticks(x, stage_labels, rotation=18, ha="right")
    ax.set_ylabel("Mean population / scintillation photons")
    ax.legend(frameon=False, fontsize=7, ncol=2, loc="best")
    _clean_axes(ax)
    _save(fig, outdir, "1303_stage_accounting")


def pe_per_mev_figure(stats: list[dict], outdir: str) -> None:
    """Current-model PE/MeV values only; historical superseded points stay out."""
    fig, ax = plt.subplots(figsize=(6.2, 4.0))
    for species, color in SPECIES_COLORS.items():
        points = sorted(
            [s for s in stats if s["species"] == species],
            key=lambda s: s["ke_MeV"],
        )
        if not points:
            continue
        for denom, marker, linestyle, label_suffix in (
            ("pe_per_mev_E_vis", "o", "-", r"$E_{\rm vis}$"),
            ("pe_per_mev_E_raw", "s", "--", r"$E_{\rm raw}$"),
        ):
            x = [p["ke_MeV"] for p in points]
            y = [p[denom]["mean"] for p in points]
            lo = [p[denom]["mean"] - p[denom]["ci16"] for p in points]
            hi = [p[denom]["ci84"] - p[denom]["mean"] for p in points]
            ax.errorbar(
                x, y, yerr=[lo, hi], marker=marker, ls=linestyle,
                color=color, ms=5, lw=1.2, capsize=2.5,
                label=f"{species}: {label_suffix}",
            )
    ax.set_xlabel("Primary kinetic energy [MeV]")
    ax.set_ylabel("Detected PE per MeV")
    ax.legend(frameon=False, fontsize=8, ncol=2, loc="best")
    _clean_axes(ax)
    _save(fig, outdir, "1303_pe_per_mev")


def pooled_cal(stats_meta: list[tuple[dict, dict]], outdir: str) -> dict:
    """Pooled E_vis/PE calibration; fit metrics returned for the caption/table."""
    ed_all, pe_all, species_all = [], [], []
    for point, _meta in stats_meta:
        data = point["data"]
        ed_all.append(data["edep_scint_MeV"])
        pe_all.append(data["detected_readout"])
        species_all.append(np.full(int(point["n"]), point["species"]))
    ed = np.concatenate(ed_all)
    pe = np.concatenate(pe_all)
    species_arr = np.concatenate(species_all)
    slope, intercept = np.polyfit(ed, pe, 1)
    residual = pe - (slope * ed + intercept)
    r2 = 1.0 - np.var(residual) / np.var(pe)

    fig, ax = plt.subplots(figsize=(6.1, 4.0))
    # Dense event clouds are rendered as small transparent points; the fit
    # parameters are deliberately left to the caption/source table.
    for species, marker in (("proton", "o"), ("deuteron", "s")):
        select = species_arr == species
        if select.any():
            ax.scatter(
                ed[select], pe[select], s=5, alpha=0.16, marker=marker,
                color=SPECIES_COLORS[species], label=species, linewidths=0,
                rasterized=True,
            )
    xs = np.linspace(ed.min(), ed.max(), 100)
    ax.plot(xs, slope * xs + intercept, color="0.15", lw=1.4, label="pooled linear fit")
    ax.set_xlabel(r"Birks-visible deposited energy $E_{\rm vis}$ [MeV]")
    ax.set_ylabel("Detected photoelectrons")
    ax.legend(frameon=False, fontsize=8, loc="best")
    _clean_axes(ax)
    _save(fig, outdir, "1303_edep_vs_pe")
    return {
        "slope_PE_per_MeV_E_vis": float(slope),
        "offset_PE": float(intercept),
        "r2": float(r2),
        "n_events": int(len(ed)),
    }


def write_tables(stats: list[dict], outdir_tables: str) -> None:
    os.makedirs(outdir_tables, exist_ok=True)
    import csv

    stage_path = os.path.join(outdir_tables, "1303_stage_accounting.csv")
    with open(stage_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow([
            "species", "ke_MeV", "channel", "n_events",
            "scint_gen_mean", "wls_gen_mean", "arrival_mean",
            "detected_mean", "pe_sat_mean", "adc_mean",
            "eps_wls_capture", "eps_transport",
            "eps_detect_given_arrival", "pe_sat_over_detected",
            "adc_over_detected",
        ])
        for stat in stats:
            for channel, c in stat["channels"].items():
                writer.writerow([
                    stat["species"], stat["ke_MeV"], channel, stat["n_events"],
                    c["scint_generated_mean"], c["wls_generated_mean"],
                    c["arrival_mean"], c["detected_mean"], c["pe_sat_mean"],
                    c["adc_mean"], c["eps_wls_capture"], c["eps_transport"],
                    c["eps_detect_given_arrival"], c["pe_sat_over_detected"],
                    c["adc_over_detected"],
                ])

    ppm_path = os.path.join(outdir_tables, "1303_pe_per_mev.csv")
    with open(ppm_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow([
            "species", "ke_MeV", "n_events", "E_vis_mean_MeV",
            "E_raw_mean_MeV", "quench_ratio", "pe_per_mev_E_vis",
            "ci16_E_vis", "ci84_E_vis", "pe_per_mev_E_raw",
            "ci16_E_raw", "ci84_E_raw", "july_pe_per_mev_SUPERSEDED",
        ])
        for stat in stats:
            vis = stat["pe_per_mev_E_vis"]
            raw = stat["pe_per_mev_E_raw"]
            writer.writerow([
                stat["species"], stat["ke_MeV"], stat["n_events"],
                stat["E_vis_mean_MeV"], stat["E_raw_mean_MeV"],
                stat["quench_ratio_Evis_over_Eraw"],
                vis["mean"], vis["ci16"], vis["ci84"],
                raw["mean"], raw["ci16"], raw["ci84"],
                HISTORICAL_SUPERSEDED.get(
                    (stat["species"], stat["ke_MeV"]), {}
                ).get("pe_per_mev"),
            ])


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--grid-dir", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    os.makedirs(os.path.join(args.output, "figures"), exist_ok=True)
    os.makedirs(os.path.join(args.output, "tables"), exist_ok=True)

    roots = sorted(glob.glob(os.path.join(args.grid_dir, "stave_*.root")))
    points, metas, stats = [], [], []
    for root_path in roots:
        meta_path = root_path + ".meta.json"
        if not os.path.exists(meta_path):
            print(f"SKIP (no meta receipt): {os.path.basename(root_path)}")
            continue
        point = load_point(root_path)
        meta = parse_meta(meta_path)
        requested = int(meta.get("n_events_requested", point["n"]))
        if point["n"] < requested:
            print(
                f"SKIP (incomplete: {point['n']}/{requested}): "
                f"{os.path.basename(root_path)}"
            )
            continue
        points.append(point)
        metas.append(meta)
        stats.append(point_stats(point))
        print(f"OK {os.path.basename(root_path)}: n={point['n']}")

    if len(stats) < 2:
        raise SystemExit("fewer than 2 complete points — aborting")

    figdir = os.path.join(args.output, "figures")
    stage_accounting_figure(stats, figdir)
    pe_per_mev_figure(stats, figdir)
    pooled = pooled_cal(list(zip(points, metas)), figdir)
    write_tables(stats, os.path.join(args.output, "tables"))

    provenance = []
    for point, meta in zip(points, metas):
        provenance.append({
            "file": os.path.basename(point["_path"]),
            "species": point["species"],
            "ke_MeV": point["ke_MeV"],
            "git_commit": meta.get("git_commit"),
            "geometry_hash": meta.get("geometry_hash"),
            "physics_hash": meta.get("physics_hash"),
            "optical_hash": meta.get("optical_hash"),
            "strict_optical": meta.get("strict_optical"),
            "authorising_absolute_light_yield_claims": meta.get(
                "authorising_absolute_light_yield_claims"
            ),
            "model_status_flags": {
                key: meta.get(key) for key in (
                    "wls_fluorescence_status", "tio2_reflection_model_status",
                    "scintillator_material_status", "hrd_fibre_count_status",
                    "attenuation_identifiability_status", "y11_direct_scint_status",
                    "step_size_convergence_status",
                )
            },
        })

    summary = {
        "schema": "ccb-paper-1303-optical-stage-accounting/2",
        "status_label": "MC_MODEL_DEPENDENT",
        "grid_dir": args.grid_dir,
        "n_points": len(stats),
        "points": stats,
        "pooled_calibration_E_vis": pooled,
        "provenance": provenance,
        "superseded_july_values": {
            "|".join(map(str, key)): value
            for key, value in HISTORICAL_SUPERSEDED.items()
        },
        "rendering": {
            "status_text_inside_figures": False,
            "per_panel_efficiency_textboxes": False,
            "historical_superseded_points_in_primary_figure": False,
        },
        "notes": (
            "PE/MeV reported on both denominators: E_vis (Birks-visible) and "
            "E_raw (unquenched). Historical July values remain in this JSON/table "
            "for provenance but are omitted from the primary current-model plot. "
            "No absolute light-yield claim."
        ),
    }
    with open(os.path.join(args.output, "1303_summary.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=1)
    print("WROTE", args.output)


if __name__ == "__main__":
    main()
