#!/usr/bin/env python3
"""P02 (orchestrator-run): pulse-shape representation & unsupervised pulse-type discovery.

Traditional baseline (PCA) vs ML (autoencoder), benchmarked on reconstruction, plus
unsupervised clustering of B-stave pulse shapes with physical characterisation.

Data is READ-ONLY at ./data (immutable store). Reproduces the S00 selection (B2=ch0,B4=ch2,
B6=ch4,B8=ch6; baseline=median samples 0-3; amplitude=max(corrected); cut A>1000 ADC).
"""
import json, hashlib, glob, time
from pathlib import Path
import numpy as np
import uproot
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.decomposition import PCA
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

RAW = Path("data/root/root")
OUT = Path("reports/P02_pulse_representation_discovery")
OUT.mkdir(parents=True, exist_ok=True)
STAVES = {"B2": 0, "B4": 2, "B6": 4, "B8": 6}
BASELINE = [0, 1, 2, 3]
NSAMP = 18
CUT = 1000.0
# Sample II analysis (penetrating, cleaner) + one Sample I run (B2-terminal heavy) for contrast
RUNS = [58, 59, 60, 61, 62, 63, 65, 50]
MAXPULSE = 60000
RNG = np.random.default_rng(0)
# Relative threshold for a physically meaningful signed area denominator: a row
# is censored (NaN) when |area| <= AREA_EPS * typical_area, never epsilon-projected.
AREA_EPS = 1e-3

def load_waveforms():
    wfs, amps, staves, runs = [], [], [], []
    snames = list(STAVES); schan = np.array([STAVES[s] for s in snames])
    for run in RUNS:
        fs = glob.glob(str(RAW / f"hrdb_run_{run:04d}.root"))
        if not fs:
            continue
        t = uproot.open(fs[0])[uproot.open(fs[0]).keys()[0]]
        for batch in t.iterate(["HRDv"], step_size=20000, library="np"):
            ev = np.stack(batch["HRDv"]).astype(np.float64).reshape(-1, 8, NSAMP)
            w = ev[:, schan, :]                                   # (events, 4, 18)
            base = np.median(w[..., BASELINE], axis=-1)
            corr = w - base[..., None]
            amp = corr.max(axis=-1)                               # (events, 4)
            ei, si = np.where(amp > CUT)
            for e, s in zip(ei, si):
                wfs.append(corr[e, s]); amps.append(amp[e, s]); staves.append(snames[s]); runs.append(run)
        if len(wfs) > MAXPULSE:
            break
    wfs = np.asarray(wfs); amps = np.asarray(amps)
    staves = np.asarray(staves); runs = np.asarray(runs)
    if len(wfs) > MAXPULSE:
        idx = RNG.choice(len(wfs), MAXPULSE, replace=False)
        wfs, amps, staves, runs = wfs[idx], amps[idx], staves[idx], runs[idx]
    return wfs, amps, staves, runs

def shape_features(wfs, amps):
    """Compute versioned, domain-checked pulse-shape features on the
    amplitude-normalised waveform ``norm = wfs / amps``.

    The former implementation projected every nonpositive ``area`` to ``+1e-6``
    via ``np.maximum(area, 1e-6)``, turning ordinary negative tails into
    O(10^6) pseudo-values (see #1100).  Instead we:

    * keep the *signed* area as-is (``area_signed``) and never substitute a
      small positive denominator;
    * define a validity mask ``ok`` for a physically meaningful signed area,
      ``|area| > AREA_EPS * max(1, area_scale)``;
    * set the ratio features to NaN (typed invalid, not a fabricated number)
      wherever the denominator is invalid;
    * expose the positive-charge and absolute-area fractions as separate,
      versioned features so the measurand is explicit.

    Column layout of the returned feature matrix (kept backward-compatible):
    [0]=peak_sample, [1]=area_signed, [2]=late_signed_fraction_v1,
    [3]=aop signed peak/area v1, [4]=late_positive_fraction_v1,
    [5]=late_abs_fraction_v1, [6]=area_positive, [7]=area_abs.
    """
    norm = wfs / amps[:, None]
    peak = norm.argmax(axis=1)
    area_signed = norm.sum(axis=1)
    area_positive = np.maximum(norm, 0.0).sum(axis=1)
    area_abs = np.abs(norm).sum(axis=1)
    tail_signed = norm[:, 12:].sum(axis=1)
    tail_positive = np.maximum(norm[:, 12:], 0.0).sum(axis=1)
    tail_abs = np.abs(norm[:, 12:]).sum(axis=1)

    # Valid signed-area denominator: magnitude well above floating-point noise,
    # scaled relative to the typical per-pulse area. Rows failing this are
    # censored (NaN) rather than epsilon-projected.
    area_scale = np.median(np.abs(area_signed))
    ok = np.abs(area_signed) > AREA_EPS * max(1.0, float(area_scale))

    late_signed = np.full(len(norm), np.nan, dtype=np.float64)
    aop = np.full(len(norm), np.nan, dtype=np.float64)
    late_signed[ok] = tail_signed[ok] / area_signed[ok]
    # peak/area: peak-normed waveform has peak==1, so aop = 1/area_signed.
    aop[ok] = 1.0 / area_signed[ok]
    # Measurand-explict secondary fractions, valid for any area_positive>0.
    late_positive = tail_positive / np.maximum(area_positive, np.finfo(np.float64).eps)
    late_abs = tail_abs / np.maximum(area_abs, np.finfo(np.float64).eps)

    feats = np.column_stack([
        peak.astype(np.float64), area_signed, late_signed, aop,
        late_positive, late_abs, area_positive, area_abs,
    ])
    return feats, norm

def ae_reconstruct(X, latent_dims, epochs=60):
    import torch, torch.nn as nn
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    Xt = torch.tensor(X, dtype=torch.float32, device=dev)
    out = {}
    lat_store = {}
    for k in latent_dims:
        torch.manual_seed(0)
        net = nn.Sequential(nn.Linear(18, 16), nn.ReLU(), nn.Linear(16, k),
                            nn.ReLU(), nn.Linear(k, 16), nn.ReLU(), nn.Linear(16, 18)).to(dev)
        enc = net[:3]
        opt = torch.optim.Adam(net.parameters(), lr=1e-3)
        lossf = nn.MSELoss()
        n = len(Xt); bs = 2048
        for ep in range(epochs):
            perm = torch.randperm(n, device=dev)
            for i in range(0, n, bs):
                b = Xt[perm[i:i+bs]]
                opt.zero_grad(); loss = lossf(net(b), b); loss.backward(); opt.step()
        with torch.no_grad():
            rec = net(Xt); mse = float(((rec - Xt) ** 2).mean())
            lat = enc(Xt).cpu().numpy()
        out[k] = mse; lat_store[k] = lat
    return out, lat_store, dev

def main():
    t0 = time.time()
    print("loading waveforms ...")
    wfs, amps, staves, runs = load_waveforms()
    print(f"loaded {len(wfs)} selected B-stave pulses")
    feats, norm = shape_features(wfs, amps)

    # ---- Traditional: PCA on amplitude-normalised waveforms ----
    latent_dims = [2, 3, 4, 8]
    pca_mse = {}
    pca_full = PCA(n_components=8).fit(norm)
    for k in latent_dims:
        p = PCA(n_components=k).fit(norm)
        rec = p.inverse_transform(p.transform(norm))
        pca_mse[k] = float(((rec - norm) ** 2).mean())
    pca3 = PCA(n_components=3).fit(norm); lat_pca3 = pca3.transform(norm)

    # ---- ML: autoencoder ----
    print("training autoencoders ...")
    ae_mse, ae_lat, dev = ae_reconstruct(norm, latent_dims)

    # ---- Benchmark table ----
    bench = [{"latent_dim": k, "pca_recon_mse": pca_mse[k], "ae_recon_mse": ae_mse[k],
              "ae_better_pct": 100 * (pca_mse[k] - ae_mse[k]) / pca_mse[k]} for k in latent_dims]

    # ---- Unsupervised clustering (k=5) on AE-3 latent, characterise ----
    K = 5
    lat = ae_lat[3]
    km = KMeans(n_clusters=K, n_init=10, random_state=0).fit(StandardScaler().fit_transform(lat))
    lab = km.labels_
    clusters = []
    for c in range(K):
        m = lab == c
        comp = {s: int((staves[m] == s).sum()) for s in STAVES}
        clusters.append({"cluster": c, "n": int(m.sum()),
                         "median_amp_adc": float(np.median(amps[m])),
                         "median_late_frac": float(np.nanmedian(feats[m, 2])),
                         "median_peak_sample": float(np.median(feats[m, 0])),
                         "stave_composition": comp})
    # Legitimacy diagnostics: count nonpositive, near-zero, and censored areas.
    n_nan = int(np.isnan(feats[:, 2]).sum())  # late_signed censored count
    n_neg = int((feats[:, 1] < 0.0).sum())    # signed area < 0
    n_near_zero = int((np.abs(feats[:, 1]) > 0.0) & (np.abs(feats[:, 1]) < AREA_EPS * float(max(1.0, np.median(np.abs(feats[:, 1]))))))
    diagnostics = {"n_total": int(len(feats)), "n_negative_area": n_neg,
        "n_near_zero_area": n_near_zero, "n_censored_late_signed_nan": n_nan}

    # ---- Figures ----
    fig, ax = plt.subplots(1, 2, figsize=(11, 4))
    for k in latent_dims:
        pass
    ax[0].plot(latent_dims, [pca_mse[k] for k in latent_dims], "o-", label="PCA (traditional)")
    ax[0].plot(latent_dims, [ae_mse[k] for k in latent_dims], "s-", label="Autoencoder (ML)")
    ax[0].set_xlabel("latent dim"); ax[0].set_ylabel("reconstruction MSE"); ax[0].set_yscale("log")
    ax[0].legend(); ax[0].set_title("Reconstruction: PCA vs AE")
    sc = ax[1].scatter(lat[:, 0], lat[:, 1], c=np.log10(amps), s=2, cmap="viridis")
    ax[1].set_xlabel("AE latent 0"); ax[1].set_ylabel("AE latent 1"); ax[1].set_title("AE latent (colour=log10 amp)")
    plt.colorbar(sc, ax=ax[1]); plt.tight_layout(); plt.savefig(OUT / "fig_pca_vs_ae_and_latent.png", dpi=110); plt.close()

    fig, axs = plt.subplots(1, K, figsize=(3 * K, 3), sharey=True)
    for c in range(K):
        m = lab == c
        mean_wf = norm[m].mean(axis=0)
        axs[c].plot(mean_wf); axs[c].set_title(f"cl{c} n={m.sum()}\namp~{int(np.median(amps[m]))}")
        axs[c].set_xlabel("sample")
    axs[0].set_ylabel("norm. amplitude"); plt.tight_layout()
    plt.savefig(OUT / "fig_cluster_mean_waveforms.png", dpi=110); plt.close()

    # ---- Save results + manifest ----
    feature_defs = {
        "0": "peak_sample (argmax, integer sample index)",
        "1": "area_signed (signed integral of normalised waveform)",
        "2": "late_signed_fraction_v1 (tail_signed / area_signed, NaN where |area_signed| <= AREA_EPS * area_scale)",
        "3": "aop_signed_peak_over_area_v1 (1.0 / area_signed, NaN where denominator invalid)",
        "4": "late_positive_fraction_v1 (sum max(norm,0)[12:] / sum max(norm,0))",
        "5": "late_abs_fraction_v1 (sum |norm|[12:] / sum |norm|)",
        "6": "area_positive (sum max(norm, 0))",
        "7": "area_abs (sum |norm|)",
    }
    res = {"study": "P02", "n_pulses": int(len(wfs)), "runs": RUNS,
           "device": dev,
           "sampling_method": "pooled_global_downsample_after_scan",
           "MAXPULSE": MAXPULSE,
           "AREA_EPS": AREA_EPS,
           "feature_definitions": feature_defs,
           "stave_counts": {s: int((staves == s).sum()) for s in STAVES},
           "feature_diagnostics": diagnostics,
           "benchmark_pca_vs_ae": bench,
           "clusters_k5": clusters,
           "pca_explained_var_ratio_8": pca_full.explained_variance_ratio_.tolist(),
           "runtime_sec": round(time.time() - t0, 1)}
    (OUT / "result.json").write_text(json.dumps(res, indent=2))
    print(json.dumps(bench, indent=2))
    print("clusters:", json.dumps(clusters, indent=2))
    print(f"DONE in {res['runtime_sec']}s -> {OUT}")

if __name__ == "__main__":
    main()
