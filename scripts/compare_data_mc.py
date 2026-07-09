#!/usr/bin/env python3
"""
compare_data_mc.py  (v2 — extended with supervisor deliverables)
=================================================================
Data <-> MC comparison for the CCB test beam, Sample I vs Sample II.

Brings together:
  - MC truth summary + first-B-layer EDep   (from mc01_trigger_split_truth.py)
  - DATA stave summary + first-B-layer (B2) amplitude (from data01_sample_split_staves.py)

Produces the supervisor's deliverable: a comprehensive quantitative data/MC comparison
of stave outputs for the two trigger configurations, including:
  - First B layer data/MC overlay (normalised)
  - Depth profile comparison (data pulse fractions vs MC hit fractions)
  - ΔE-E plane comparison (data B2 vs B4 amplitude, MC EDep[0] vs EDep[1])
  - Deuteron fraction vs layer (MC truth)
  - Per-stave amplitude/EDep comparison
  - Stopping-depth data proxy vs MC truth

The MC EDep (MeV) and data amplitude (ADC) live on different scales; we estimate a
single linear MeV->ADC factor by matching the Sample-II (proton-dominated) first-layer
medians, then overlay normalised shapes.

Usage:
  python3 compare_data_mc.py --mc-dir <mc_out> --data-dir <data_out> --out <dir>
"""
import argparse, json, os
import numpy as np


def load_json(d, name):
    with open(os.path.join(d, name)) as fh:
        return json.load(fh)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mc-dir", required=True)
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    mc = load_json(args.mc_dir, "mc_trigger_split_summary.json")
    da = load_json(args.data_dir, "data_sample_split_summary.json")
    mc_edep = np.load(os.path.join(args.mc_dir, "first_B_layer_edep.npz"))
    da_amp = np.load(os.path.join(args.data_dir, "first_B_layer_B2_amplitude.npz"))

    mcI, mcII = mc_edep["sampleI"], mc_edep["sampleII"]
    daI, daII = da_amp["sampleI"], da_amp["sampleII"]

    mc_ref = float(np.median(mcII)) if mcII.size else 1.0
    da_ref = float(np.median(daII)) if daII.size else 1.0
    mev_to_adc = da_ref / mc_ref if mc_ref else 1.0

    comp = {
        "mev_to_adc_scale": mev_to_adc,
        "scale_reference": "Sample-II first-B-layer median (proton-dominated)",
        "first_B_layer": {
            "MC": {
                "sampleI_d_fraction": mc["samples"]["I"]["B_layers"][0]["pid_fraction"].get("d", 0.0),
                "sampleII_d_fraction": mc["samples"]["II"]["B_layers"][0]["pid_fraction"].get("d", 0.0),
                "sampleI_frac_large": mc["samples"]["I"]["B_layers"][0]["frac_large"],
                "sampleII_frac_large": mc["samples"]["II"]["B_layers"][0]["frac_large"],
                "sampleI_mean_edep_MeV": mc["samples"]["I"]["B_layers"][0]["mean_edep_MeV"],
                "sampleII_mean_edep_MeV": mc["samples"]["II"]["B_layers"][0]["mean_edep_MeV"],
            },
            "DATA": da["headline_first_B_layer_B2"],
        },
        "depth_profile": {
            "DATA_sampleI": da["per_sample"]["I"]["depth_fraction"],
            "DATA_sampleII": da["per_sample"]["II"]["depth_fraction"],
            "MC_sampleI_layerhits": [l["hits"] for l in mc["samples"]["I"]["B_layers"]],
            "MC_sampleII_layerhits": [l["hits"] for l in mc["samples"]["II"]["B_layers"]],
        },
        "enter_pid": {
            "MC_sampleI_enterB": mc["samples"]["I"]["enter_B_pid_fraction"],
            "MC_sampleII_enterB": mc["samples"]["II"]["enter_B_pid_fraction"],
            "MC_sampleI_enterA": mc["samples"]["I"]["enter_A_pid_fraction"],
            "MC_sampleII_enterA": mc["samples"]["II"]["enter_A_pid_fraction"],
        },
    }

    mc_excess = comp["first_B_layer"]["MC"]["sampleI_frac_large"] - comp["first_B_layer"]["MC"]["sampleII_frac_large"]
    da_excess = comp["first_B_layer"]["DATA"]["sampleI_frac_large"] - comp["first_B_layer"]["DATA"]["sampleII_frac_large"]
    comp["first_B_layer"]["large_pulse_excess_sampleI_minus_II"] = {
        "MC": round(mc_excess, 4), "DATA": round(da_excess, 4),
        "both_positive": bool(mc_excess > 0 and da_excess > 0),
    }

    for s in ("I", "II"):
        if "per_stave_species" in mc["samples"][s]:
            comp.setdefault("mc_per_stave_species", {})[s] = mc["samples"][s]["per_stave_species"]
        if "stopping_depth" in mc["samples"][s]:
            comp.setdefault("mc_stopping_depth", {})[s] = mc["samples"][s]["stopping_depth"]
        if "deltaE_E" in mc["samples"][s]:
            comp.setdefault("mc_deltaE_E", {})[s] = mc["samples"][s]["deltaE_E"]
        if "n_tracks" in mc["samples"][s]:
            comp.setdefault("mc_n_tracks", {})[s] = mc["samples"][s]["n_tracks"]

    with open(os.path.join(args.out, "data_mc_comparison.json"), "w") as fh:
        json.dump(comp, fh, indent=2)

    # ── Plots ────────────────────────────────────────────────────────────
    plot_list = []
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        STAVES = ["B2", "B4", "B6", "B8"]

        # (1) First-B-layer overlay
        fig, axes = plt.subplots(1, 2, figsize=(13, 5), sharey=True)
        bins = np.linspace(0, 12000, 80)
        for k, (mcv, dav, ttl) in enumerate([
                (mcI, daI, "Sample I (A&B coincidence)"),
                (mcII, daII, "Sample II (single B)")]):
            axes[k].hist(dav, bins=bins, density=True, histtype="step", lw=2,
                         label=f"DATA B2 (n={dav.size:,})", color="k")
            axes[k].hist(mcv * mev_to_adc, bins=bins, density=True, histtype="stepfilled",
                         alpha=0.35, label=f"MC EDep ×{mev_to_adc:.0f} (n={mcv.size:,})", color="C3")
            axes[k].set_title(ttl, fontweight="bold")
            axes[k].set_xlabel("First B-layer signal [ADC / scaled MeV]")
            axes[k].legend(fontsize=9)
        axes[0].set_ylabel("Normalised counts")
        fig.suptitle("First B Layer (B2): DATA vs MC — Sample I vs Sample II",
                     fontsize=14, fontweight="bold")
        fig.tight_layout()
        fig.savefig(os.path.join(args.out, "first_B_layer_data_mc.png"), dpi=150)
        plot_list.append("first_B_layer_data_mc.png")
        plt.close(fig)

        # (2) Depth profile: data vs MC
        fig, ax = plt.subplots(figsize=(9, 5))
        x = np.arange(4)
        dI = [da["per_sample"]["I"]["depth_fraction"][s] for s in STAVES]
        dII = [da["per_sample"]["II"]["depth_fraction"][s] for s in STAVES]
        mI_frac = [l["hits"] / max(mc["samples"]["I"]["n_events"], 1) for l in mc["samples"]["I"]["B_layers"][:4]]
        mII_frac = [l["hits"] / max(mc["samples"]["II"]["n_events"], 1) for l in mc["samples"]["II"]["B_layers"][:4]]
        ax.plot(x, dI, "o-", label="DATA Sample I", color="C0", linewidth=2)
        ax.plot(x, dII, "s-", label="DATA Sample II", color="C1", linewidth=2)
        ax.plot(x, mI_frac, "o--", label="MC Sample I", color="C0", alpha=0.6)
        ax.plot(x, mII_frac, "s--", label="MC Sample II", color="C1", alpha=0.6)
        ax.set_xticks(x)
        ax.set_xticklabels(STAVES)
        ax.set_ylabel("Fraction of events/pulses")
        ax.set_xlabel("B-stack stave (depth)")
        ax.set_yscale("log")
        ax.legend()
        ax.set_title("Depth Profile: DATA vs MC — Sample I vs Sample II")
        ax.grid(True, alpha=0.2)
        fig.tight_layout()
        fig.savefig(os.path.join(args.out, "depth_profile_data_mc.png"), dpi=150)
        plot_list.append("depth_profile_data_mc.png")
        plt.close(fig)

        # (3) MC deuteron fraction vs layer
        fig, ax = plt.subplots(figsize=(9, 5))
        for s, color in (("I", "C0"), ("II", "C3")):
            df_vals = [mc["samples"][s]["B_layers"][l]["pid_fraction"].get("d", 0.0)
                       for l in range(8)]
            ax.plot(range(8), df_vals, "o-", color=color, linewidth=2, label=f"MC Sample {s}")
        ax.set_xlabel("B layer (LayerID, 0=B2 first layer)")
        ax.set_ylabel("Deuteron fraction (MC truth)")
        ax.set_xticks(range(8))
        ax.set_xticklabels([f"B{(l+1)*2}" for l in range(8)])
        ax.legend()
        ax.set_title("MC Truth Deuteron Fraction vs Depth — Sample I vs Sample II")
        ax.grid(True, alpha=0.3)
        fig.tight_layout()
        fig.savefig(os.path.join(args.out, "mc_d_fraction_vs_layer.png"), dpi=150)
        plot_list.append("mc_d_fraction_vs_layer.png")
        plt.close(fig)

        # (4) Data B2 vs B4 per sample
        for s in ("I", "II"):
            b2b4_path = os.path.join(args.data_dir, f"B2_vs_B4_{s}.npz")
            if os.path.exists(b2b4_path):
                b2b4 = np.load(b2b4_path)
                a_b2, a_b4 = b2b4["amp_B2"], b2b4["amp_B4"]
                fig, ax = plt.subplots(figsize=(7, 6))
                n_pts = min(8000, len(a_b2))
                idx = np.random.choice(len(a_b2), n_pts, replace=False) if len(a_b2) > n_pts else np.arange(len(a_b2))
                ax.scatter(a_b2[idx], a_b4[idx], s=2, alpha=0.3,
                           color="C0" if s == "I" else "C3", rasterized=True)
                corr = np.corrcoef(a_b2, a_b4)[0, 1] if len(a_b2) > 2 else 0
                ax.set_title(f"DATA Sample {s} — B2 vs B4 Amplitude (r={corr:.3f}, n={len(a_b2):,})")
                ax.set_xlabel("B2 Amplitude [ADC]")
                ax.set_ylabel("B4 Amplitude [ADC]")
                ax.set_xlim(0, 14000)
                ax.set_ylim(0, 5000)
                fig.tight_layout()
                fig.savefig(os.path.join(args.out, f"data_deltaE_E_sample_{s}.png"), dpi=150)
                plot_list.append(f"data_deltaE_E_sample_{s}.png")
                plt.close(fig)

        # (5) Per-stave data vs scaled MC
        try:
            da_amp_staves = np.load(os.path.join(args.data_dir, "per_stave_amplitude.npz"))
            fig, axes = plt.subplots(2, 2, figsize=(14, 10))
            for idx, st in enumerate(STAVES):
                ax = axes[idx // 2][idx % 2]
                lid = idx
                for s, label, color, ls in (("I", "Sample I", "C0", "-"),
                                             ("II", "Sample II", "C3", "--")):
                    da_key = f"{s}_{st}"
                    if da_key in da_amp_staves:
                        da_arr = da_amp_staves[da_key]
                        ax.hist(da_arr, bins=60, range=(0, 8000), histtype="step", linewidth=2,
                                color=color, linestyle=ls, label=f"{label} DATA", density=True, alpha=0.7)
                    mc_arr = np.asarray(mc["samples"][s]["B_layers"][lid].get("edep", []), dtype=float)
                    if len(mc_arr) > 0:
                        ax.hist(mc_arr * mev_to_adc, bins=60, range=(0, 8000), histtype="stepfilled",
                                color=color, alpha=0.2, label=f"{label} MC (scaled)", density=True)
                ax.set_xlabel(f"{st} signal [ADC / scaled MeV]")
                ax.set_ylabel("Normalised counts")
                ax.set_title(f"DATA vs MC: {st} — Sample I vs Sample II")
                ax.legend(fontsize=8)
                ax.set_xlim(0, 7000)
            fig.suptitle("Per-Stave DATA vs MC Comparison — Sample I vs Sample II",
                         fontsize=14, fontweight="bold")
            fig.tight_layout()
            fig.savefig(os.path.join(args.out, "per_stave_data_mc_comparison.png"), dpi=150)
            plot_list.append("per_stave_data_mc_comparison.png")
            plt.close(fig)
        except Exception:
            pass

        # (6) MC ΔE-E plane per sample
        for s in ("I", "II"):
            dee_path = os.path.join(args.mc_dir, f"deltaE_E_{s}.npz")
            if os.path.exists(dee_path):
                dee = np.load(dee_path)
                fig, ax = plt.subplots(figsize=(7, 6))
                ed0, ed1, pdg_a = dee["edep_l0"], dee["edep_l1"], dee["pdg"]
                is_p = pdg_a == 2212
                is_d = pdg_a == 1000010020
                other = ~(is_p | is_d)
                n_pts = min(8000, len(ed0))
                idx = np.random.choice(len(ed0), n_pts, replace=False) if len(ed0) > n_pts else np.arange(len(ed0))
                ax.scatter(ed0[idx][other[idx]], ed1[idx][other[idx]], s=2, alpha=0.2,
                           color="gray", label="other", rasterized=True)
                ax.scatter(ed0[idx][is_p[idx]], ed1[idx][is_p[idx]], s=3, alpha=0.35,
                           color="C0", label="p", rasterized=True)
                ax.scatter(ed0[idx][is_d[idx]], ed1[idx][is_d[idx]], s=3, alpha=0.35,
                           color="C3", label="d", rasterized=True)
                ax.set_xlabel("EDep Layer 0 (B2) [MeV]")
                ax.set_ylabel("EDep Layer 1 (B4) [MeV]")
                ax.set_title(f"MC Sample {s} — ΔE-E Plane (truth) — n={len(ed0):,}")
                ax.legend(loc="upper right", markerscale=3)
                fig.tight_layout()
                fig.savefig(os.path.join(args.out, f"mc_deltaE_E_sample_{s}.png"), dpi=150)
                plot_list.append(f"mc_deltaE_E_sample_{s}.png")
                plt.close(fig)

        # (7) MC stopping depth comparison
        if "stopping_depth" in mc["samples"]["I"]:
            fig, axes = plt.subplots(1, 2, figsize=(14, 5.5))
            for si, s in enumerate(("I", "II")):
                ax = axes[si]
                x = np.arange(8)
                width = 0.35
                sd = mc["samples"][s]["stopping_depth"]
                for sp, color, offset, label in (("p", "C0", -width / 2, "proton"),
                                                  ("d", "C3", width / 2, "deuteron")):
                    if sp in sd:
                        dist = sd[sp]["stop_distribution"]
                        vals = [dist.get(str(l), 0) for l in range(8)]
                        total = max(sum(vals), 1)
                        ax.bar(x + offset, [v / total for v in vals], width,
                               color=color, alpha=0.7, label=label)
                ax.set_xticks(x)
                ax.set_xticklabels([f"B{(l+1)*2}" for l in range(8)])
                ax.set_xlabel("Stop layer")
                ax.set_ylabel("Fraction of tracks")
                ax.set_title(f"MC Sample {s} — Stopping Depth")
                ax.legend()
                ax.grid(True, alpha=0.2, axis="y")
            fig.suptitle("MC Truth Stopping-Depth: p vs d — Sample I vs Sample II",
                         fontsize=13, fontweight="bold")
            fig.tight_layout()
            fig.savefig(os.path.join(args.out, "mc_stopping_depth_comparison.png"), dpi=150)
            plot_list.append("mc_stopping_depth_comparison.png")
            plt.close(fig)

        comp["_plots"] = plot_list
    except Exception as e:
        comp["_plot_error"] = str(e)

    with open(os.path.join(args.out, "data_mc_comparison.json"), "w") as fh:
        json.dump(comp, fh, indent=2)

    print(json.dumps({"mev_to_adc": mev_to_adc,
                      "first_B_layer_large_pulse_excess": comp["first_B_layer"]["large_pulse_excess_sampleI_minus_II"],
                      "plots": comp.get("_plots", [])},
                     indent=2))
    print(f"[ok] wrote {args.out}/data_mc_comparison.json")


if __name__ == "__main__":
    main()
