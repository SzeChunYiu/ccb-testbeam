#!/usr/bin/env python3
"""#618 species / penetration deliverables from the corrected deltaE-E event tables.

Inputs (produced by scripts/single_stave/paper_956_deltaE_E_publication.py over the
authorising regenerated MC root):
  <bundle>/deltaE_E_events_mc.csv.gz   (truth species, per-layer edep, 4-layer/full sums)
  <bundle>/deltaE_E_events_data.csv.gz (amplitude proxies + saturation flags)

Outputs into <bundle>/:
  figures/618_mc_truth_full_<sample>.png/.pdf       4 panels: p, d, p+d, all
  figures/618_mc_truth_4layer_<sample>.png/.pdf     4 panels: p, d, p+d, all
  figures/618_data_amplitude_I_II.png/.pdf          Sample I + II, identical ranges
  figures/618_penetration_<sample>.png/.pdf         L_stop hists: p, d, p+d norm, all
  tables/618_penetration_stability.csv              L_stop vs threshold (0/0.02/0.05/0.1/0.5 MeV)
  618_summary.json                                 counts, saturation fractions, L_stop stats

Contracts:
  - MC truth: dE = Edep(B2); E_full = unique downstream physical layers;
    E_4layer = Edep(B4)+Edep(B6)+Edep(B8) (data-matched mask).
  - Data: dE = amp(B2); E = amp(B4)+amp(B6)+amp(B8); amplitude proxies, NOT calibrated
    energy. B2 saturation marked via the analysis-contract saturation flag (waveform
    clip detection); NO numeric ADC saturation level is drawn - the hardware transfer
    threshold is unbound (#1014/#1073).
  - L_stop = deepest physical layer index (0..7) with edep > threshold; default
    0.02 MeV, stability checked at 0 / 0.05 / 0.1 / 0.5 MeV.
  - Unweighted event counts (generator reweighting is documented in the campaign
    manifest; shapes here are descriptive truth topology).
"""
from __future__ import annotations

import argparse
import csv
import gzip
import json
import math
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

SPECIES_COLORS = {"p": "tab:blue", "d": "tab:orange", "t": "tab:green",
                  "alpha": "tab:red", "other": "tab:gray"}
DEFAULT_THRESHOLDS = [0.0, 0.02, 0.05, 0.1, 0.5]
L_STOP_NONE = 8  # sentinel: no layer above threshold
LAYER_LABELS = [f"L{i}" for i in range(8)] + ["none"]


def _read_table(path: str):
    import pandas as pd
    if path.endswith(".parquet"):
        return pd.read_parquet(path)
    opener = gzip.open if path.endswith(".gz") else open
    with opener(path, "rt", newline="") as fh:
        import io
        return pd.read_csv(io.StringIO(fh.read()))


def load_mc(path: str) -> dict[str, dict[str, np.ndarray]]:
    df = _read_table(path)
    out: dict[str, dict[str, np.ndarray]] = {}
    for sample in ("I", "II"):
        sel = df[df["sample"] == sample]
        out[sample] = {
            "species": sel["truth_species"].astype(str).to_numpy(),
            "dE": sel["deltaE_mc_mev"].to_numpy(dtype=float),
            "E4": sel["E_mc_4layer_mev"].to_numpy(dtype=float),
            "Efull": sel["E_mc_full_mev"].to_numpy(dtype=float),
            "layers": sel[[f"edep_layer_{i}" for i in range(8)]].to_numpy(dtype=float),
            "rB4": sel["readout_B4"].to_numpy(dtype=float),
            "rB6": sel["readout_B6"].to_numpy(dtype=float),
            "rB8": sel["readout_B8"].to_numpy(dtype=float),
        }
    return out


def load_data(path: str) -> dict[str, dict[str, np.ndarray]]:
    df = _read_table(path)
    if df["saturation_B2"].dtype == bool:
        sat = df["saturation_B2"].to_numpy(dtype=bool)
    else:
        sat = df["saturation_B2"].astype(str).isin(("True", "1", "true")).to_numpy()
    out: dict[str, dict[str, np.ndarray]] = {}
    for sample in ("I", "II"):
        sel = df[df["sample"] == sample]
        idx = sel.index
        out[sample] = {
            "dE": sel["amp_B2"].to_numpy(dtype=float),
            "E": sel["E_data_adc"].to_numpy(dtype=float),
            "sat_B2": sat[idx.to_numpy()],
            "stop": sel["stopping_layer"].to_numpy(),
            "pass_B4": sel["threshold_pass_B4"].astype(bool).to_numpy(),
            "pass_B6": sel["threshold_pass_B6"].astype(bool).to_numpy(),
            "pass_B8": sel["threshold_pass_B8"].astype(bool).to_numpy(),
        }
    return out


def scatter_panels(ax_grid, x_all, y_all, species, title_suffix: str, xlabel: str, ylabel: str,
                   lims=None) -> None:
    combos = [("p", "proton truth"), ("d", "deuteron truth"),
              (("p", "d"), "p + d, colour-coded"), (None, "all particles")]
    for ax, (spec, label) in zip(ax_grid.flat, combos):
        if spec is None:
            mask = np.ones(len(species), dtype=bool)
            ax.scatter(x_all[mask], y_all[mask], s=1.5, c="tab:gray", alpha=0.25, linewidths=0)
        elif isinstance(spec, tuple):
            for s in spec:
                mask = species == s
                ax.scatter(x_all[mask], y_all[mask], s=1.5, c=SPECIES_COLORS[s],
                           alpha=0.3, linewidths=0, label=s)
            ax.legend(markerscale=6, fontsize=7, loc="upper right", framealpha=0.6)
        else:
            mask = species == spec
            ax.scatter(x_all[mask], y_all[mask], s=1.5, c=SPECIES_COLORS[spec],
                       alpha=0.3, linewidths=0)
            ax.set_title(f"{label}  (n={int(mask.sum()):,})", fontsize=9)
        if not isinstance(spec, (tuple, type(None))):
            pass
        if isinstance(spec, tuple) or spec is None:
            ax.set_title(label, fontsize=9)
        ax.set_xlabel(xlabel, fontsize=8)
        ax.set_ylabel(ylabel, fontsize=8)
        ax.tick_params(labelsize=7)
        if lims is not None:
            ax.set_xlim(lims[0])
            ax.set_ylim(lims[1])


def mc_figure(mc: dict, sample: str, mode: str, outdir: str) -> dict:
    y = mc["dE"]
    x = mc["E4"] if mode == "4layer" else mc["Efull"]
    ylabel = r"$\Delta E_{\rm MC}$ = Edep(B2) [MeV]"
    xlabel = (r"$E_{\rm MC,4}$ = Edep(B4)+Edep(B6)+Edep(B8) [MeV]" if mode == "4layer"
              else r"$E_{\rm MC,full}$ = $\Sigma$ downstream layers [MeV]")
    fig, axes = plt.subplots(2, 2, figsize=(9.5, 8.0))
    scatter_panels(axes, x, y, mc["species"], "", xlabel, ylabel)
    fig.suptitle(rf"MC truth $\Delta$E--E Sample {sample} "
                 rf"({'data-matched 4-layer' if mode == '4layer' else 'full downstream sum'}), "
                 rf"unweighted event counts", fontsize=11)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    for ext in ("png", "pdf"):
        fig.savefig(os.path.join(outdir, f"618_mc_truth_{mode}_{sample}.{ext}"), dpi=170)
    plt.close(fig)
    return {"n_events": int(len(y)),
            "n_p": int((mc["species"] == "p").sum()),
            "n_d": int((mc["species"] == "d").sum())}


def data_figure(data: dict, outdir: str) -> dict:
    xr = (0.0, max(np.percentile(data["I"]["E"], 99.5), np.percentile(data["II"]["E"], 99.5)))
    yr = (0.0, max(np.percentile(data["I"]["dE"], 99.5), np.percentile(data["II"]["dE"], 99.5)))
    lims = (xr, yr)
    stats = {}
    fig, axes = plt.subplots(1, 2, figsize=(10.0, 4.8))
    for ax, sample in zip(axes, ("I", "II")):
        d = data[sample]
        sat_frac = float(d["sat_B2"].mean())
        ax.scatter(d["E"][~d["sat_B2"]], d["dE"][~d["sat_B2"]], s=2.0, c="tab:blue",
                   alpha=0.25, linewidths=0, label="not flagged")
        ax.scatter(d["E"][d["sat_B2"]], d["dE"][d["sat_B2"]], s=2.0, c="crimson",
                   alpha=0.35, linewidths=0, label="B2 saturation-flagged")
        ax.set_xlim(xr)
        ax.set_ylim(yr)
        ax.set_xlabel(r"$E_{\rm data}$ = A(B4)+A(B6)+A(B8) [ADC amp proxy]", fontsize=8)
        ax.set_ylabel(r"$\Delta E_{\rm data}$ = A(B2) [ADC amp proxy]", fontsize=8)
        ax.set_title(f"Sample {sample}  (n={len(d['dE']):,}; B2 sat-flagged {sat_frac:.1%})",
                     fontsize=9)
        ax.tick_params(labelsize=7)
        ax.legend(markerscale=6, fontsize=7, loc="upper right", framealpha=0.6)
        stats[sample] = {"n_events": int(len(d["dE"])), "b2_saturation_fraction": sat_frac}
    fig.suptitle("Beam-data amplitude analogue (identical axes; NOT calibrated energy; "
                 "saturation shown as analysis-contract flag, no numeric hardware level)",
                 fontsize=10)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    for ext in ("png", "pdf"):
        fig.savefig(os.path.join(outdir, f"618_data_amplitude_I_II.{ext}"), dpi=170)
    plt.close(fig)
    return stats


def l_stop(layers: np.ndarray, threshold: float) -> np.ndarray:
    """Deepest layer index (0..7) with edep > threshold; 8 = none above threshold."""
    above = layers > threshold
    any_above = above.any(axis=1)
    deepest = np.where(any_above, 7 - np.argmax(above[:, ::-1], axis=1), L_STOP_NONE)
    return deepest


def penetration_figure(mc: dict, sample: str, outdir: str) -> dict:
    fig, axes = plt.subplots(2, 2, figsize=(9.5, 7.6))
    stop = l_stop(mc["layers"], 0.02)
    combos = [("p", "proton truth"), ("d", "deuteron truth"),
              (("p", "d"), "p + d, shape-normalized"), (None, "all particles")]
    stats = {}
    bins = np.arange(-0.5, 9.5, 1.0)
    for ax, (spec, label) in zip(axes.flat, combos):
        if spec is None:
            mask = np.ones(len(stop), dtype=bool)
            ax.hist(stop[mask], bins=bins, color="tab:gray", alpha=0.8)
        elif isinstance(spec, tuple):
            for s in spec:
                mask = mc["species"] == s
                w = np.ones(int(mask.sum())) / max(int(mask.sum()), 1)
                ax.hist(stop[mask], bins=bins, weights=w, histtype="step", lw=1.8,
                        color=SPECIES_COLORS[s], label=f"{s} (norm)")
            ax.legend(fontsize=7, loc="upper left", framealpha=0.6)
        else:
            mask = mc["species"] == spec
            ax.hist(stop[mask], bins=bins, color=SPECIES_COLORS[spec], alpha=0.8)
        ax.set_xticks(range(9))
        ax.set_xticklabels(LAYER_LABELS, fontsize=7)
        ax.set_xlabel(r"$L_{\rm stop}$: deepest layer with Edep $>$ 0.02 MeV", fontsize=8)
        ax.set_ylabel("events" if not isinstance(spec, tuple) else "fraction", fontsize=8)
        ax.set_title(label, fontsize=9)
        ax.tick_params(labelsize=7)
        if spec is not None and not isinstance(spec, tuple):
            mask = mc["species"] == spec
            stats[str(spec)] = {"mean": float(stop[mask].mean()),
                                "frac_none": float((stop[mask] == L_STOP_NONE).mean())}
    fig.suptitle(f"MC penetration depth, Sample {sample} (unweighted)", fontsize=11)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    for ext in ("png", "pdf"):
        fig.savefig(os.path.join(outdir, f"618_penetration_{sample}.{ext}"), dpi=170)
    plt.close(fig)
    return stats


def reaching_fractions(mc: dict, threshold: float) -> dict:
    """Dave (#618): per-species fraction of events reaching B4/B6/B8 (readout-layer
    edep > threshold) and the deepest-active-stave fraction (L_stop < sentinel)."""
    stop = l_stop(mc["layers"], threshold)
    out: dict = {}
    for spec in ("p", "d", "all"):
        mask = np.ones(len(stop), dtype=bool) if spec == "all" else mc["species"] == spec
        n = int(mask.sum())
        out[spec] = {
            "n": n,
            "frac_reach_B4": round(float((mc["rB4"][mask] > threshold).mean()), 6) if n else None,
            "frac_reach_B6": round(float((mc["rB6"][mask] > threshold).mean()), 6) if n else None,
            "frac_reach_B8": round(float((mc["rB8"][mask] > threshold).mean()), 6) if n else None,
            "frac_deepest_active": round(float((stop[mask] != L_STOP_NONE).mean()), 6) if n else None,
        }
    return out


def data_penetration_figure(data: dict, outdir: str) -> dict:
    """Dave (#618): data Sample I vs II penetration overlay. Uses the producer's
    stopping_layer (threshold-pass logic upstream) — no new ADC cut introduced here;
    fractions reaching B4/B6/B8 use the producer's threshold_pass flags."""
    fig, ax = plt.subplots(figsize=(7.0, 4.6))
    known_order = ("B2", "B4", "B6", "B8")
    all_labels = sorted({str(v) for v in np.concatenate(
        [data["I"]["stop"].astype(str), data["II"]["stop"].astype(str)])})
    ordered = [x for x in known_order if x in all_labels] + \
              [x for x in all_labels if x not in known_order]
    pos = {lab: i for i, lab in enumerate(ordered)}
    stats = {}
    for sample, color in (("I", "tab:blue"), ("II", "tab:red")):
        stop = data[sample]["stop"].astype(str)
        vals, counts = np.unique(stop, return_counts=True)
        frac = counts / max(len(stop), 1)
        marker = "o" if sample == "I" else "s"
        ax.plot([pos[str(v)] for v in vals], frac, marker=marker, ms=5, lw=1.4,
                color=color, label=f"Sample {sample}  (n={len(stop):,})")
        d = data[sample]
        stats[sample] = {
            "n_events": int(len(stop)),
            "frac_reach_B4": round(float(d["pass_B4"].mean()), 6),
            "frac_reach_B6": round(float(d["pass_B6"].mean()), 6),
            "frac_reach_B8": round(float(d["pass_B8"].mean()), 6),
            "stopping_layer_values": {str(v): round(float(f), 6)
                                      for v, f in zip(vals, frac)},
        }
    ax.set_xticks(range(len(ordered)))
    ax.set_xticklabels(ordered, fontsize=8)
    ax.set_xlabel(r"stopping layer (producer threshold-pass logic, B-stack)", fontsize=9)
    ax.set_ylabel("fraction of events", fontsize=9)
    ax.set_title("Beam-data penetration: Sample I vs II overlay (amplitude domain)", fontsize=10)
    ax.tick_params(labelsize=8)
    ax.legend(fontsize=8)
    fig.tight_layout()
    for ext in ("png", "pdf"):
        fig.savefig(os.path.join(outdir, f"618_data_penetration_I_II.{ext}"), dpi=170)
    plt.close(fig)
    return stats


def stability_table(mc_all: dict, outdir_tables: str) -> list[dict]:
    rows = []
    for sample in ("I", "II"):
        mc = mc_all[sample]
        for thr in DEFAULT_THRESHOLDS:
            stop = l_stop(mc["layers"], thr)
            for spec in ("p", "d", "all"):
                mask = np.ones(len(stop), dtype=bool) if spec == "all" else mc["species"] == spec
                vals = stop[mask]
                rows.append({
                    "sample": sample, "threshold_mev": thr, "species": spec,
                    "n": int(mask.sum()),
                    "l_stop_mean": round(float(vals.mean()), 4),
                    "l_stop_median": float(np.median(vals)),
                    "frac_none_above_threshold": round(float((vals == L_STOP_NONE).mean()), 6),
                })
    os.makedirs(outdir_tables, exist_ok=True)
    path = os.path.join(outdir_tables, "618_penetration_stability.csv")
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    return rows


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bundle", required=True,
                    help="paper_956_deltaE_E bundle directory (event CSVs)")
    args = ap.parse_args()

    def table_path(name: str) -> str:
        for ext in (".csv.gz", ".parquet"):
            path = os.path.join(args.bundle, name + ext)
            if os.path.exists(path):
                return path
        raise FileNotFoundError(os.path.join(args.bundle, name + ".{csv.gz,parquet}"))

    mc_all = load_mc(table_path("deltaE_E_events_mc"))
    data = load_data(table_path("deltaE_E_events_data"))
    figdir = os.path.join(args.bundle, "figures")
    tabdir = os.path.join(args.bundle, "tables")
    os.makedirs(figdir, exist_ok=True)

    summary: dict = {"bundle": args.bundle, "mc": {}, "data": {}, "penetration": {}}
    for sample in ("I", "II"):
        summary["mc"][sample] = {
            "full": mc_figure(mc_all[sample], sample, "full", figdir),
            "4layer": mc_figure(mc_all[sample], sample, "4layer", figdir),
        }
        summary["penetration"][sample] = penetration_figure(mc_all[sample], sample, figdir)
        summary["mc"][sample]["reaching_fractions"] = reaching_fractions(mc_all[sample], 0.02)
    summary["data"] = data_figure(data, figdir)
    summary["data"]["penetration"] = data_penetration_figure(data, figdir)
    summary["penetration_stability_rows"] = len(
        stability_table(mc_all, tabdir))
    summary["l_stop_contract"] = ("deepest layer (0..7) with edep > threshold; "
                                  "default 0.02 MeV; stability at 0/0.05/0.1/0.5 MeV; "
                                  "sentinel 'none' = no layer above threshold")
    with open(os.path.join(args.bundle, "618_summary.json"), "w") as fh:
        json.dump(summary, fh, indent=1)
    print(json.dumps({k: summary[k] for k in ("mc", "data")}, indent=1)[:1500])
    print("FIGURES:", sorted(os.listdir(figdir)))


if __name__ == "__main__":
    main()
