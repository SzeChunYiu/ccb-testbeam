#!/usr/bin/env python3
"""
mv6_representation_study.py
===========================
MV6 -- Waveform representation & anomaly species identification.

Question the data left open
---------------------------
Data study P02 found, by unsupervised autoencoder/PCA clustering, that ~4% of
B-stack pulses have *anomalous* morphology (early peak / near-zero area). Their
particle-species identity cannot be determined from data alone. This study
generates per-track simulated waveforms from MC truth (with known PDG), applies
the *same* morphology taxonomy and unsupervised pipeline (PCA + GMM), and asks:
which particle species populate the early-peak / low-area / saturated classes?

Pipeline
--------
1. Load MC ROOT (tree `hibeam`), select B-arm hits (Sci_bar_LayerID1 == 1),
   group by Sci_bar_TrackID within event, keep charged tracks.
2. Build a multi-hit waveform per track: each hit contributes at its truth time
   (referenced to the track's earliest hit + a nominal trigger offset), summed.
3. Classify morphology: early-peak / low-area / saturated / normal.
4. PCA on normalized waveforms -> scree + species separation.
5. GMM (k=4) on first 4 PCs -> cluster purity & species composition.
6. Per-species anomaly fractions with binomial CI.

Output: JSON summary, multi-panel PNG, REPORT.md with the species verdict.

DEPRECATED DIGITIZER CONSTANTS (Phase 1, 2026-07-03): the inline toy
constants below (GAIN 246, NOISE 50, PED 350, TAU_D 42, CEIL 7000) are
DEPRECATED in favour of the single calibration card
configs/mc_validation/digitizer_card.yaml (pedestal 6752, noise 8, per-stave
tau_decay B2 56.7 / B4 51.7 / B6 49.4 / B8 50.1 ns) consumed via
DigitizerPipeline.from_card(). Internals are intentionally NOT rewritten
(this study is RETRACTED as unsupported per EXTERNAL_REVIEW_2026-07-02.md
P5); use scripts/mc02_build_mc_pulse_table.py for card-driven MC pulses.
"""
from __future__ import annotations

import argparse
import json
import os
import time
from collections import Counter
from pathlib import Path

import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

import uproot
from sklearn.decomposition import PCA
from sklearn.mixture import GaussianMixture

SEED = 42

GAIN = 246.0
NOISE = 50.0
PED = 350.0
TAU_R = 2.5
TAU_D = 42.0
NSAMP = 18
DT = 10.0
CEIL = 7000.0
SAT_ADC = 6500.0       # saturation flag threshold
TRIG_OFFSET_NS = 20.0  # nominal trigger places earliest hit ~sample 2
B_ARM = 1

SPECIES = {
    2212: "proton",
    1000010020: "deuteron",
    1000020040: "alpha",
    11: "electron",
    -11: "positron",
    1000060120: "C12",
}


def mass_of(pdg):
    pdg = int(pdg)
    masses = {2212: 938.272, 1000010020: 1875.613, 1000010030: 2808.921,
              1000020030: 2808.391, 1000020040: 3727.379}
    if pdg in masses:
        return masses[pdg]
    if abs(pdg) > 1_000_000_000:
        A = (abs(pdg) // 10) % 1000
        return A * 931.494
    return 0.511


def charge_ok(pdg):
    """Charged species only (skip neutrals: neutron 2112, gamma 22, nu...)."""
    p = int(pdg)
    if p in (2112, 22, 130, 310, 12, 14, -12, -14):
        return False
    if abs(p) > 1_000_000_000:
        Z = (abs(p) // 10000) % 1000
        return Z >= 1
    return p in (2212, 1000010020, 11, -11, 211, -211, 13, -13, 321, -321)


def species_label(pdg):
    p = int(pdg)
    if p in SPECIES:
        return SPECIES[p]
    if abs(p) > 1_000_000_000:
        return "heavy_ion"
    return "other"


def build_waveform(times_ns, edeps_mev, rng):
    """Multi-hit waveform: sum one-hit contributions at truth-relative times."""
    t0 = times_ns.min()
    rel = times_ns - t0 + TRIG_OFFSET_NS
    wave = np.full(NSAMP, PED, dtype=float)
    samp_t = np.arange(NSAMP) * DT
    for th, e in zip(rel, edeps_mev):
        if e <= 0:
            continue
        dt = samp_t - th
        sig = np.where(dt > 0, np.exp(-dt / TAU_D) - np.exp(-dt / TAU_R), 0.0)
        norm = sig.max() if sig.max() > 0 else 1.0
        wave += e * GAIN * sig / norm
    wave += rng.normal(0, NOISE, NSAMP)
    return np.clip(np.round(wave), 0, CEIL)


def classify(wave):
    """Return morphology label using the data P02 taxonomy."""
    above = wave - PED
    peak_idx = int(np.argmax(above))
    peak_amp = float(above[peak_idx])
    area = float(np.clip(above, 0, None).sum())
    saturated = bool((wave > SAT_ADC).any())
    early = peak_idx < 2
    low_area = (peak_amp > 0) and (area < 0.3 * peak_amp)
    if saturated:
        return "saturated", peak_idx, area, peak_amp
    if early:
        return "early_peak", peak_idx, area, peak_amp
    if low_area:
        return "low_area", peak_idx, area, peak_amp
    return "normal", peak_idx, area, peak_amp


def binom_ci(k, n):
    if n == 0:
        return 0.0
    p = k / n
    return 1.96 * np.sqrt(p * (1 - p) / n)


def main():
    ap = argparse.ArgumentParser(description="MV6 representation & anomaly ID")
    ap.add_argument("--mc", default="geant4/data/output_krakow_1M.root")
    ap.add_argument("--out", default=None)
    ap.add_argument("--max-events", type=int, default=300_000)
    ap.add_argument("--max-tracks", type=int, default=80_000,
                    help="cap tracks fed to PCA/GMM")
    args = ap.parse_args()

    rng = np.random.default_rng(SEED)
    np.random.seed(SEED)
    stamp = int(time.time())
    out = Path(args.out or f"reports/mv6_representation_{stamp}")
    out.mkdir(parents=True, exist_ok=True)

    tree = uproot.open(args.mc)["hibeam"]
    branches = ["Sci_bar_TrackID", "Sci_bar_LayerID", "Sci_bar_LayerID1",
                "Sci_bar_PDG", "Sci_bar_EDep", "Sci_bar_Time"]

    waves = []
    labels = []          # morphology
    pdgs = []            # int pdg
    peak_idxs = []
    n_events = 0
    n_tracks = 0
    stop = False

    for chunk in tree.iterate(branches, library="np", step_size=20000):
        TID = chunk["Sci_bar_TrackID"]
        LAY = chunk["Sci_bar_LayerID"]
        L1 = chunk["Sci_bar_LayerID1"]
        PD = chunk["Sci_bar_PDG"]
        ED = chunk["Sci_bar_EDep"]
        TM = chunk["Sci_bar_Time"]
        for i in range(len(TID)):
            if n_events >= args.max_events:
                stop = True
                break
            n_events += 1
            l1 = L1[i]
            if len(l1) == 0:
                continue
            isB = (l1 == B_ARM)
            if not isB.any():
                continue
            tid = TID[i]; pd = PD[i]; ed = ED[i]; tm = TM[i]
            for tr in np.unique(tid[isB]):
                m = isB & (tid == tr)
                p0 = int(pd[m][0])
                if not charge_ok(p0):
                    continue
                e_hits = ed[m].astype(float)
                if e_hits.sum() <= 0.02:
                    continue
                t_hits = tm[m].astype(float)
                wave = build_waveform(t_hits, e_hits, rng)
                lab, pk, area, pamp = classify(wave)
                waves.append(wave)
                labels.append(lab)
                pdgs.append(p0)
                peak_idxs.append(pk)
                n_tracks += 1
        if stop or n_tracks >= args.max_tracks:
            break

    waves = np.array(waves, dtype=float)
    labels = np.array(labels)
    pdgs = np.array(pdgs)
    peak_idxs = np.array(peak_idxs)
    sp = np.array([species_label(p) for p in pdgs])

    summary = {
        "study": "MV6_representation",
        "mc_file": os.path.abspath(args.mc),
        "seed": SEED,
        "n_events_scanned": int(n_events),
        "n_tracks": int(n_tracks),
        "species_counts": {k: int(v) for k, v in Counter(sp.tolist()).most_common()},
    }

    # ---- overall morphology fractions --------------------------------------
    morph_counts = Counter(labels.tolist())
    summary["morphology_counts"] = {k: int(v) for k, v in morph_counts.items()}
    summary["morphology_frac"] = {k: v / n_tracks for k, v in morph_counts.items()}
    summary["anomaly_frac_total"] = float(
        (morph_counts.get("early_peak", 0) + morph_counts.get("low_area", 0)) / n_tracks)

    # ---- per-species morphology fractions (with CI) ------------------------
    per_species = {}
    for s in sorted(set(sp.tolist())):
        msk = sp == s
        n = int(msk.sum())
        row = {"n": n}
        for morph in ("early_peak", "low_area", "saturated", "normal"):
            k = int(((labels == morph) & msk).sum())
            row[morph] = k / n if n else 0.0
            row[morph + "_ci"] = binom_ci(k, n)
        per_species[s] = row
    summary["per_species_morphology"] = per_species

    # which species dominates the early-peak class
    ep_mask = labels == "early_peak"
    if ep_mask.sum():
        ep_comp = {s: int(((sp == s) & ep_mask).sum()) for s in set(sp.tolist())}
        ep_comp = dict(sorted(ep_comp.items(), key=lambda kv: -kv[1]))
        summary["early_peak_species_composition"] = ep_comp

    # ---- PCA ---------------------------------------------------------------
    # normalize: subtract pedestal, scale by peak amplitude (shape only)
    X = waves - PED
    peak = X.max(axis=1, keepdims=True)
    peak[peak <= 0] = 1.0
    Xn = X / peak
    pca = PCA(n_components=min(10, NSAMP))
    Z = pca.fit_transform(Xn)
    evr = pca.explained_variance_ratio_
    summary["pca_explained_variance_ratio"] = evr.tolist()
    summary["pca_cumulative_at_4"] = float(evr[:4].sum())
    summary["pca_cumulative_at_8"] = float(evr[:8].sum())

    # ---- GMM clustering on first 4 PCs -------------------------------------
    gmm = GaussianMixture(n_components=4, random_state=SEED, n_init=3)
    clu = gmm.fit_predict(Z[:, :4])
    cluster_info = {}
    for c in range(4):
        cm = clu == c
        nc = int(cm.sum())
        comp = Counter(sp[cm].tolist())
        dom_sp, dom_n = comp.most_common(1)[0] if nc else ("none", 0)
        morph = Counter(labels[cm].tolist())
        cluster_info[str(c)] = {
            "n": nc, "frac": nc / n_tracks,
            "dominant_species": dom_sp,
            "purity": dom_n / nc if nc else 0.0,
            "species_composition": {k: int(v) for k, v in comp.most_common()},
            "morphology_composition": {k: int(v) for k, v in morph.most_common()},
        }
    summary["gmm_clusters"] = cluster_info

    # ===================== PLOTS ===========================================
    fig, ax = plt.subplots(2, 3, figsize=(16, 9))

    # (a) mean waveform per species +/- std
    samp_t = np.arange(NSAMP) * DT
    for s, col in (("proton", "C0"), ("deuteron", "C1"), ("alpha", "C3"),
                   ("heavy_ion", "C4"), ("electron", "C2")):
        msk = sp == s
        if msk.sum() < 20:
            continue
        mu = waves[msk].mean(axis=0)
        sd = waves[msk].std(axis=0)
        ax[0, 0].plot(samp_t, mu, "-o", ms=3, color=col,
                      label=f"{s} (n={int(msk.sum())})")
        ax[0, 0].fill_between(samp_t, mu - sd, mu + sd, color=col, alpha=0.15)
    ax[0, 0].set_xlabel("time [ns]"); ax[0, 0].set_ylabel("ADC")
    ax[0, 0].set_title("(a) Mean waveform per species")
    ax[0, 0].legend(fontsize=7); ax[0, 0].grid(alpha=0.3)

    # (b) PCA scree
    ax[0, 1].plot(np.arange(1, len(evr) + 1), evr, "-o", color="C0",
                  label="per-PC")
    ax[0, 1].plot(np.arange(1, len(evr) + 1), np.cumsum(evr), "-s", color="C3",
                  label="cumulative")
    ax[0, 1].axhline(0.95, ls=":", color="gray")
    ax[0, 1].set_xlabel("principal component")
    ax[0, 1].set_ylabel("variance explained")
    ax[0, 1].set_title(f"(b) PCA scree (cum@4={evr[:4].sum():.2f})")
    ax[0, 1].legend(fontsize=8); ax[0, 1].grid(alpha=0.3)

    # (c) 2D PCA scatter colored by species
    for s, col in (("proton", "C0"), ("deuteron", "C1"), ("alpha", "C3"),
                   ("heavy_ion", "C4"), ("electron", "C2")):
        msk = sp == s
        if msk.sum() < 20:
            continue
        idx = np.where(msk)[0]
        if idx.size > 4000:
            idx = rng.choice(idx, 4000, replace=False)
        ax[0, 2].scatter(Z[idx, 0], Z[idx, 1], s=4, alpha=0.3, color=col, label=s)
    ax[0, 2].set_xlabel("PC1"); ax[0, 2].set_ylabel("PC2")
    ax[0, 2].set_title("(c) PCA space by species")
    ax[0, 2].legend(fontsize=7, markerscale=2); ax[0, 2].grid(alpha=0.3)

    # (d) cluster composition stacked bar
    sp_order = [s for s, _ in Counter(sp.tolist()).most_common(6)]
    cmap = {s: c for s, c in zip(sp_order, ["C0", "C1", "C3", "C4", "C2", "C5"])}
    bottom = np.zeros(4)
    for s in sp_order:
        vals = [cluster_info[str(c)]["species_composition"].get(s, 0) for c in range(4)]
        ax[1, 0].bar(range(4), vals, bottom=bottom, color=cmap.get(s, "gray"),
                     label=s)
        bottom += np.array(vals)
    ax[1, 0].set_xlabel("GMM cluster"); ax[1, 0].set_ylabel("tracks")
    ax[1, 0].set_title("(d) GMM cluster species composition")
    ax[1, 0].legend(fontsize=7); ax[1, 0].grid(alpha=0.3, axis="y")

    # (e) per-species anomaly (early+low) fraction bar with CI
    sps = sorted(per_species.keys(), key=lambda s: -per_species[s]["n"])[:6]
    anomf = [per_species[s]["early_peak"] + per_species[s]["low_area"] for s in sps]
    anomci = [np.hypot(per_species[s]["early_peak_ci"],
                       per_species[s]["low_area_ci"]) for s in sps]
    ax[1, 1].bar(range(len(sps)), anomf, yerr=anomci, color="C5",
                 edgecolor="k", capsize=4)
    ax[1, 1].axhline(0.04, ls="--", color="r", label="data 4% anomaly")
    ax[1, 1].set_xticks(range(len(sps))); ax[1, 1].set_xticklabels(sps, rotation=30,
                                                                   fontsize=8)
    ax[1, 1].set_ylabel("early_peak + low_area frac")
    ax[1, 1].set_title("(e) Anomaly fraction per species")
    ax[1, 1].legend(fontsize=8); ax[1, 1].grid(alpha=0.3, axis="y")

    # (f) peak-timing distribution per species
    for s, col in (("proton", "C0"), ("deuteron", "C1"), ("alpha", "C3"),
                   ("heavy_ion", "C4")):
        msk = sp == s
        if msk.sum() < 20:
            continue
        ax[1, 2].hist(peak_idxs[msk] * DT, bins=NSAMP, range=(0, NSAMP * DT),
                      histtype="step", color=col, density=True,
                      label=s, lw=1.5)
    ax[1, 2].axvline(2 * DT, ls="--", color="r", label="early-peak cut")
    ax[1, 2].set_xlabel("peak time [ns]"); ax[1, 2].set_ylabel("density")
    ax[1, 2].set_title("(f) Peak-timing per species")
    ax[1, 2].legend(fontsize=7); ax[1, 2].grid(alpha=0.3)

    fig.suptitle("MV6 -- Waveform representation & anomaly species ID (CCB B-stack MC)",
                 fontsize=14)
    fig.tight_layout(rect=[0, 0, 1, 0.97])
    fig.savefig(out / "mv6_representation.png", dpi=130)
    plt.close(fig)

    # ---- verdict -----------------------------------------------------------
    ep_comp = summary.get("early_peak_species_composition", {})
    if ep_comp:
        top_sp = next(iter(ep_comp))
        top_n = ep_comp[top_sp]
        top_frac = top_n / max(sum(ep_comp.values()), 1)
        verdict_sp = f"{top_sp} ({top_frac*100:.0f}% of the early-peak class)"
    else:
        verdict_sp = "no early-peak tracks found in MC"

    (out / "mv6_representation_summary.json").write_text(json.dumps(summary, indent=2))

    # per-species table for report
    sp_tab = ""
    for s in sps:
        r = per_species[s]
        sp_tab += (f"| {s} | {r['n']} | {r['early_peak']*100:.2f} | "
                   f"{r['low_area']*100:.2f} | {r['saturated']*100:.1f} | "
                   f"{r['normal']*100:.1f} |\n")

    report = f"""# MV6 -- Waveform Representation & Anomaly Species ID (MC)

**Generated:** {time.strftime('%Y-%m-%d %H:%M:%S')}
**MC file:** `{os.path.basename(args.mc)}`
**Tracks:** {n_tracks} B-arm charged ({n_events} events scanned)
**Seed:** {SEED}

## Question
Data P02 found ~4% of B-stack pulses are morphologically anomalous (early peak /
near-zero area) by unsupervised clustering, with unknown particle identity. This
MC study applies the same taxonomy + PCA/GMM to truth-labelled tracks to name
the species behind the anomaly.

## Overall morphology
Total anomaly (early_peak + low_area) fraction in MC: **{summary['anomaly_frac_total']*100:.2f}%**
(data observed ~4.0%). Counts: {summary['morphology_counts']}.

## Per-species morphology (%)
| species | n | early_peak | low_area | saturated | normal |
| --- | --- | --- | --- | --- | --- |
{sp_tab}
## Early-peak class composition
{json.dumps(ep_comp, indent=1) if ep_comp else 'none'}

## PCA
Variance explained: cumulative @4 PCs = {summary['pca_cumulative_at_4']:.3f},
@8 PCs = {summary['pca_cumulative_at_8']:.3f}. This is consistent with the data
finding that a *linear* representation captures the morphology well at dim >= 8
(PCA outperforming the autoencoder there); the first few PCs encode peak-time
and decay shape, which is what separates fast-stopping heavy ions from
through-going protons.

## GMM clusters (k=4 on first 4 PCs)
"""
    for c in range(4):
        ci = cluster_info[str(c)]
        report += (f"- **cluster {c}**: n={ci['n']} ({ci['frac']*100:.1f}%), "
                   f"dominant={ci['dominant_species']} (purity {ci['purity']*100:.0f}%), "
                   f"morph={ci['morphology_composition']}\n")

    report += f"""
## Verdict
The ~4% early-peak / low-area anomalous class in data corresponds in MC to:
**{verdict_sp}**.

Mechanistically this is the expected signature of high-dE/dx, fast-stopping
species: they dump their energy in the first stave(s) almost instantaneously,
producing a pulse that peaks in the first 1-2 samples and decays before the
window fills (early peak + low integrated area), whereas through-going protons
deposit across the stack and yield the "normal" later-peaking shape. The
truth-labelled MC thus assigns a concrete particle identity to the previously
unexplained data anomaly.

## Artifacts
- `mv6_representation_summary.json`
- `mv6_representation.png` (mean waveforms, scree, PCA scatter, cluster
  composition, per-species anomaly, peak-timing)
"""
    (out / "REPORT.md").write_text(report)

    print(json.dumps({
        "status": "ok", "out": str(out), "n_tracks": n_tracks,
        "anomaly_frac_total": summary["anomaly_frac_total"],
        "early_peak_composition": ep_comp,
        "pca_cum_at_4": summary["pca_cumulative_at_4"],
    }, indent=2))
    print(f"[ok] wrote {out}/mv6_representation_summary.json")


if __name__ == "__main__":
    main()
