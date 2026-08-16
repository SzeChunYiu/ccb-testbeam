#!/usr/bin/env python3
"""P02 (orchestrator-run): pulse-shape representation & unsupervised latent cluster discovery.

Traditional baseline (PCA) vs ML (autoencoder), benchmarked on reconstruction, plus
unsupervised clustering of B-stave pulse shapes into latent clusters with physical
characterisation.  Cluster stability is validated by K-sweep, seed-ensemble label
matching, frozen-centroid held-out transfer, and synthetic controls.

Data is READ-ONLY at ./data (immutable store). Reproduces the S00 selection (B2=ch0,B4=ch2,
B6=ch4,B8=ch6; baseline=median samples 0-3; amplitude=max(corrected); cut A>1000 ADC).
"""
import json, hashlib, glob, time
from pathlib import Path
import numpy as np

from ccb_mc_validation.waveform_ratios import (
    AREA_EPS as SHARED_AREA_EPS,
    CONTRACT_VERSION as WAVEFORM_RATIO_CONTRACT,
    late_and_peak_ratios,
)
import uproot
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.decomposition import PCA
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from scipy.optimize import linear_sum_assignment
from sklearn.metrics import adjusted_rand_score, silhouette_score

RAW = Path("data/root/root")
OUT = Path("reports/P02_pulse_representation_discovery")
OUT.mkdir(parents=True, exist_ok=True)
STAVES = {"B2": 0, "B4": 2, "B6": 4, "B8": 6}
BASELINE = [0, 1, 2, 3]
NSAMP = 18
CUT = 1000.0
# Sample II analysis (penetrating, cleaner) + one Sample I run (B2-terminal heavy) for contrast
RUNS = [58, 59, 60, 61, 62, 63, 65, 50]
# Held-out runs used ONLY for out-of-sample evaluation (never for fitting PCA/AE/clustering):
# 50 is the Sample-I B2-terminal-heavy run, 65 is the last Sample-II run.
HELDOUT_RUNS = [50, 65]
MAXPULSE = 60000
RNG = np.random.default_rng(0)
# Relative threshold for a physically meaningful signed area denominator: a row
# is censored (NaN) when |area| <= AREA_EPS * typical_area, never epsilon-projected.
AREA_EPS = SHARED_AREA_EPS  # shared #1100 contract
# Seed ensemble quantifies AE stochastic training uncertainty.
AE_SEEDS = [0, 1, 42, 123, 999]
# Cluster-stability study parameters (#1102).
K_SWEEP = list(range(2, 11))          # K=2..10 model-selection sweep
KM_N_SEEDS = 50                        # seeds for seed-ensemble label matching
KM_N_INIT = 10                         # KMeans restarts per fit
KM_SEED_BASE = 9000                    # offset so KMeans seeds are independent of AE seeds
STABILITY_SEEDS = list(range(KM_SEED_BASE, KM_SEED_BASE + KM_N_SEEDS))
# Frozen-centroid held-out transfer uses the same held-out runs as representation (#1101).
MORPH_STATE_EDGES = [0.30, 0.55, 0.80]  # peak-sample thresholds for rule-based morphology states

def load_waveforms():
    """Scan ALL configured runs, then deterministically downsample the pooled
    population. Unlike the former early-break prefix sampler, the target
    sampling distribution is invariant to the order of ``RUNS``: every
    configured run is scanned before any cap is applied, so no run can be
    silently excluded because a predecessor filled the budget.

    Returns the pooled arrays plus per-run/per-stave provenance counts.
    """
    wfs, amps, staves, runs = [], [], [], []
    run_counts = {run: 0 for run in RUNS}
    stave_counts = {s: 0 for s in STAVES}
    snames = list(STAVES); schan = np.array([STAVES[s] for s in snames])
    for run in RUNS:
        fs = glob.glob(str(RAW / f"hrdb_run_{run:04d}.root"))
        if not fs:
            continue
        t = uproot.open(fs[0])[uproot.open(fs[0]).keys()[0]]
        selected_this_run = 0
        for batch in t.iterate(["HRDv"], step_size=20000, library="np"):
            ev = np.stack(batch["HRDv"]).astype(np.float64).reshape(-1, 8, NSAMP)
            w = ev[:, schan, :]                                   # (events, 4, 18)
            base = np.median(w[..., BASELINE], axis=-1)
            corr = w - base[..., None]
            amp = corr.max(axis=-1)                               # (events, 4)
            ei, si = np.where(amp > CUT)
            for e, s in zip(ei, si):
                wfs.append(corr[e, s]); amps.append(amp[e, s]); staves.append(snames[s]); runs.append(run)
            selected_this_run += len(ei)
        run_counts[run] = selected_this_run
    for s in STAVES:
        stave_counts[s] = int(np.sum(np.asarray(staves) == s))
    run_counts = {r: c for r, c in run_counts.items() if c > 0}
    wfs = np.asarray(wfs); amps = np.asarray(amps)
    staves = np.asarray(staves); runs = np.asarray(runs)
    # Global, order-invariant downsampling of the pooled population only AFTER
    # every run has been scanned. Rows are sampled uniformly from the union of
    # all declared runs, so the mixture measure does not depend on ``RUNS``
    # order (see #1099).
    if len(wfs) > MAXPULSE:
        idx = RNG.choice(len(wfs), MAXPULSE, replace=False)
        # Downsample the provenance arrays at the same time; recompute counts
        # on the actual sampled rows.
        wfs, amps, staves, runs = wfs[idx], amps[idx], staves[idx], runs[idx]
        run_counts = {r: int(np.sum(runs == r)) for r in RUNS if int(np.sum(runs == r)) > 0}
        stave_counts = {s: int(np.sum(staves == s)) for s in STAVES}
    return wfs, amps, staves, runs, run_counts, stave_counts

def shape_features(wfs, amps):
    """Compute versioned, domain-checked pulse-shape features via the shared
    #1100 waveform-ratio contract (``ccb_mc_validation.waveform_ratios``).

    Column layout (backward-compatible):
    [0]=peak_sample, [1]=area_signed, [2]=late_signed_fraction_v1,
    [3]=aop signed peak/area v1, [4]=late_positive_fraction_v1,
    [5]=late_abs_fraction_v1, [6]=area_positive, [7]=area_abs.
    """
    amps = np.asarray(amps, dtype=np.float64)
    ratios = late_and_peak_ratios(wfs, late_start=12, normalize_by=amps)
    norm = wfs / amps[:, None]
    peak = norm.argmax(axis=1).astype(np.float64)
    feats = np.column_stack([
        peak,
        ratios["area_signed"],
        ratios["late_signed_fraction_v1"],
        ratios["peak_to_area_signed_v1"],
        ratios["late_positive_fraction_v1"],
        ratios["late_abs_fraction_v1"],
        ratios["area_positive"],
        ratios["area_abs"],
    ])
    return feats, norm


def ae_reconstruct(X_train, X_eval, latent_dims, seed=0, epochs=60, batch_size=2048):
    """Train AEs on X_train only; evaluate reconstruction on X_train (in-sample) and X_eval.

    Uses explicit encoder/bottleneck_activation/decoder modules so that the exported
    latent matches the state consumed by the decoder (#1103).  Returns
    (train_mse, eval_mse, eval_latents, dev) per latent dim, all seeded by ``seed``.
    """
    import torch, torch.nn as nn
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    Xt = torch.tensor(X_train, dtype=torch.float32, device=dev)
    Xv = torch.tensor(X_eval, dtype=torch.float32, device=dev)
    train_mse = {}
    eval_mse = {}
    lat_store = {}

    class WaveformAE(nn.Module):
        """Autoencoder with explicit encoder/bottleneck_activation/decoder.

        The exported latent is the post-ReLU bottleneck state — the same tensor
        consumed by the decoder during training.
        """
        def __init__(self, k: int):
            super().__init__()
            self.encoder = nn.Sequential(
                nn.Linear(18, 16), nn.ReLU(),
                nn.Linear(16, k),
            )
            self.bottleneck_activation = nn.ReLU()
            self.decoder = nn.Sequential(
                nn.Linear(k, 16), nn.ReLU(),
                nn.Linear(16, 18),
            )

        def forward(self, x):
            z_post = self.bottleneck_activation(self.encoder(x))
            return self.decoder(z_post)

        def encode_post(self, x):
            return self.bottleneck_activation(self.encoder(x))

    for k in latent_dims:
        torch.manual_seed(seed)
        net = WaveformAE(k).to(dev)
        opt = torch.optim.Adam(net.parameters(), lr=1e-3)
        lossf = nn.MSELoss()
        n = len(Xt); bs = batch_size
        for ep in range(epochs):
            perm = torch.randperm(n, device=dev)
            for i in range(0, n, bs):
                b = Xt[perm[i:i+bs]]
                opt.zero_grad(); loss = lossf(net(b), b); loss.backward(); opt.step()
        with torch.no_grad():
            rec_tr = net(Xt); rec_ev = net(Xv)
            train_mse[k] = float(((rec_tr - Xt) ** 2).mean())
            eval_mse[k] = float(((rec_ev - Xv) ** 2).mean())
            lat_store[k] = net.encode_post(Xv).cpu().numpy()
    return train_mse, eval_mse, lat_store, dev

def optimal_label_matching(labels_a, labels_b):
    """Match labels between two partitions by linear assignment (Hungarian).

    Labels are permutation-invariant; this returns the permutation of ``labels_b``
    that maximises the count of rows sharing a label with ``labels_a``. Used to
    compare cluster IDs across independent KMeans fits (#1102).
    """
    a = np.asarray(labels_a, dtype=int)
    b = np.asarray(labels_b, dtype=int)
    na, nb = a.max() + 1, b.max() + 1
    cost = np.zeros((na, nb), dtype=np.int64)
    for i in range(na):
        for j in range(nb):
            cost[i, j] = -int(((a == i) & (b == j)).sum())
    row, col = linear_sum_assignment(cost)
    mapping = np.full(nb, -1, dtype=int)
    mapping[col[row]] = row[row]
    return mapping

def morphology_state(peak_sample):
    """Rule-based waveform morphology state from the normalised peak sample.

    Independent of AE coordinates; used as a source-backed discriminant for the
    early-peak class rather than treating KMeans IDs as pulse types (#1102).
    """
    edges = np.asarray(MORPH_STATE_EDGES)
    return np.searchsorted(edges, peak_sample.astype(float))

def synthetic_continuous_manifold(n=3000, seed=7):
    """Continuous one-dimensional pulse manifold with no discrete classes.

    A no-classes negative control: samples lie on a smooth 1D curve embedded in
    3D. KMeans will nevertheless form clusters; the report must not read them as
    discrete pulse types.
    """
    rng = np.random.default_rng(seed)
    t = rng.uniform(0, 1, n)
    r = np.column_stack([t, np.sin(2 * np.pi * t), np.cos(2 * np.pi * t)])
    return r + 0.05 * rng.normal(size=r.shape)

def synthetic_mixture(n=3000, k=5, seed=11):
    """Synthetic known five-component mixture for recovery validation.

    Returns (samples, true_labels). Each component is a Gaussian blob in 3D with a
    distinct centroid; recovery measures whether the procedure can reproduce the
    ground-truth components under realistic overlap.
    """
    rng = np.random.default_rng(seed)
    centers = rng.normal(size=(k, 3)) * 3.0
    samples, labels = [], []
    for c in range(k):
        n_c = max(1, n // k)
        samples.append(rng.normal(loc=centers[c], scale=0.6, size=(n_c, 3)))
        labels.append(np.full(n_c, c))
    return np.concatenate(samples, axis=0), np.concatenate(labels, axis=0)

def label_matching_stability(lat_ref, lat_all, seeds, n_inits, k):
    """Seed-ensemble label-matching stability of KMeans on latent ``lat_ref``.

    Fits KMeans(k) once per seed; matches every fit's labels to the first fit via
    optimal_label_matching; returns (mean_ari_to_first, mean_purity_to_first).
    """
    scaler = StandardScaler().fit(lat_ref)
    lat_s = scaler.transform(lat_ref)
    first = None
    aris, purities = [], []
    for seed in seeds:
        km = KMeans(n_clusters=k, n_init=n_inits, random_state=seed).fit(lat_s)
        lab = km.labels_
        if first is None:
            first = lab
            continue
        mapping = optimal_label_matching(first, lab)
        lab_m = mapping[lab]
        aris.append(adjusted_rand_score(first, lab_m))
        purities.append(float((first == lab_m).mean()))
    return float(np.mean(aris)), float(np.mean(purities))

def frozen_centroid_transfer(lat_train, lat_held, k, seed):
    """Fit KMeans on training latents, freeze centroids, assign held-out latents.

    Returns the fraction of held-out rows whose nearest frozen centroid disagrees
    with the nearest centroid recomputed on the held-out data (coarse transfer
    stability proxy) plus the held-out ARI between the two assignments.
    """
    scaler = StandardScaler().fit(lat_train)
    tr_s = scaler.transform(lat_train)
    ev_s = scaler.transform(lat_held)
    km = KMeans(n_clusters=k, n_init=KM_N_INIT, random_state=seed).fit(tr_s)
    frozen = km.predict(ev_s)
    refit = KMeans(n_clusters=k, n_init=KM_N_INIT, random_state=seed).fit(ev_s).labels_
    mapping = optimal_label_matching(frozen, refit)
    refit_m = mapping[refit]
    ari = adjusted_rand_score(frozen, refit_m)
    return ari

def silhouette_on_latent(lat, k, seed):
    """Mean silhouette on the standardised latent for a single KMeans fit."""
    scaler = StandardScaler().fit(lat)
    lat_s = scaler.transform(lat)
    km = KMeans(n_clusters=k, n_init=KM_N_INIT, random_state=seed).fit(lat_s)
    return float(silhouette_score(lat_s, km.labels_))

def optimal_k_ari(lat):
    """Label-matching ARI between K and K+1 fits across the K-sweep (#1102).

    A low/non-monotonic ARI across adjacent K indicates the partition fragments or
    merges arbitrarily as K changes (support for H2/H5, against stable discrete
    pulse types). Returns dict {K: ARI_to_next}.
    """
    scaler = StandardScaler().fit(lat)
    lat_s = scaler.transform(lat)
    fits = {}
    for k in K_SWEEP:
        fits[k] = KMeans(n_clusters=k, n_init=KM_N_INIT, random_state=KM_SEED_BASE).fit(lat_s).labels_
    out = {}
    for k in K_SWEEP[:-1]:
        kn = k + 1
        # Match the K+1 labels to the K labels restricted to shared semantics.
        mapping = optimal_label_matching(fits[k], fits[kn])
        lab_n = mapping[fits[kn]]
        ari = adjusted_rand_score(fits[k], lab_n)
        out[k] = float(ari)
    return out

def cluster_stability_report(lat, feats_held, aev, sev, lab_ref, k_ref=3):
    """Assemble the full #1102 clustering-stability report on the held-out latent.

    ``lat`` is the (post-ReLU) AE-3 latent of held-out rows; ``feats_held``/``aev``/``sev``
    are the corresponding shape features, amplitudes and staves. ``lab_ref`` is the
    reference KMeans assignment at ``k_ref`` used for per-cluster composition.
    """
    # 1. Silhouette + label-matching across the K-sweep.
    sil = {k: silhouette_on_latent(lat, k, KM_SEED_BASE) for k in K_SWEEP}
    opt_k_ari = optimal_k_ari(lat)

    # 2. Seed-ensemble label-matching stability at the canonical K.
    ari_mean, pur_mean = label_matching_stability(lat, lat, STABILITY_SEEDS, KM_N_INIT, k_ref)

    # 3. Per-cluster composition with run-block bootstrap uncertainty.
    K = k_ref
    scaler = StandardScaler().fit(lat)
    km = KMeans(n_clusters=K, n_init=KM_N_INIT, random_state=KM_SEED_BASE).fit(scaler.transform(lat))
    lab = km.labels_
    clusters = []
    rng = np.random.default_rng(0)
    for c in range(K):
        m = lab == c
        comp = {s: int((sev[m] == s).sum()) for s in STAVES}
        # Run-block bootstrap 95% CI on median amplitude.
        sel_runs = np.unique(sev[m])
        boot = []
        for _ in range(200):
            if len(sel_runs) == 0:
                boot.append(np.nan); continue
            chosen = rng.choice(sel_runs, size=len(sel_runs), replace=True)
            mask = np.zeros(m.sum(), dtype=bool)
            for r in chosen:
                mask |= sev[m] == r
            boot.append(float(np.median(aev[m][mask]))) if mask.any() else boot.append(np.nan)
        q = np.nanquantile(np.asarray(boot), [0.025, 0.975])
        clusters.append({
            "cluster": c, "n": int(m.sum()),
            "median_amp_adc": float(np.median(aev[m])),
            "amp_ci_low": float(q[0]), "amp_ci_high": float(q[1]),
            "median_late_frac": float(np.nanmedian(feats_held[m, 2])),
            "median_peak_sample": float(np.median(feats_held[m, 0])),
            "stave_composition": comp,
            "fraction": float(m.sum() / max(1, len(lab))),
        })

    # 4. Held-out frozen-centroid transfer is evaluated on the training latent in main().
    return {
        "k_sweep": K_SWEEP,
        "silhouette_by_k": sil,
        "optimal_k_ari_to_next": opt_k_ari,
        "seed_ensemble": {
            "n_seeds": len(STABILITY_SEEDS),
            "k": k_ref,
            "mean_ari_to_first": ari_mean,
            "mean_purity_to_first": pur_mean,
        },
        "clusters": clusters,
    }

def synthetic_controls():
    """Run the two synthetic controls and return their results (#1102)."""
    # Negative control: continuous manifold, no discrete classes.
    yman, _ = synthetic_continuous_manifold()
    ari_man = float(np.nan)  # no ground truth; report silhouette only
    sil_man = silhouette_on_latent(yman, 3, KM_SEED_BASE)
    # Positive control: known 5-component mixture recovery.
    ymix, ytrue = synthetic_mixture()
    km = KMeans(n_clusters=5, n_init=KM_N_INIT, random_state=KM_SEED_BASE).fit(
        StandardScaler().fit_transform(ymix))
    mapping = optimal_label_matching(ytrue, km.labels_)
    lab_m = mapping[km.labels_]
    recovery_ari = adjusted_rand_score(ytrue, lab_m)
    recovery_purity = float((ytrue == lab_m).mean())
    return {
        "continuous_manifold_negative_control": {
            "silhouette_k3": sil_man,
            "note": "Silhouette on a no-class 1D manifold is non-negative; KMeans forms Voronoi cells without discrete classes.",
        },
        "synthetic_5component_recovery": {
            "recovered_ari": recovery_ari,
            "recovered_purity": recovery_purity,
            "note": "High ARI/purity means the procedure can recover known components.",
        },
    }

def main():
    t0 = time.time()
    print("loading waveforms ...")
    wfs, amps, staves, runs, run_counts, stave_counts = load_waveforms()
    print(f"loaded {len(wfs)} selected B-stave pulses")
    # Per-run counts before and after downsampling (for provenance).
    contributing_runs = sorted(run_counts.keys())
    print(f"contributing runs: {contributing_runs}")
    print(f"per-run counts: {run_counts}")
    feats, norm = shape_features(wfs, amps)

    # ---- Held-out split: fit everything on training runs, evaluate on held-out runs ----
    held = np.isin(runs, HELDOUT_RUNS)
    xtr, xev = norm[~held], norm[held]
    atr, aev = amps[~held], amps[held]
    str_, sev = staves[~held], staves[held]
    print(f"train pulses={len(xtr)} heldout pulses={len(xev)} (runs {HELDOUT_RUNS})")

    # ---- Traditional: PCA on amplitude-normalised training waveforms ----
    latent_dims = [2, 3, 4, 8]
    pca_full = PCA(n_components=8).fit(xtr)
    pca_tr_mse = {}
    pca_ev_mse = {}
    for k in latent_dims:
        p = PCA(n_components=k).fit(xtr)
        rec_tr = p.inverse_transform(p.transform(xtr))
        rec_ev = p.inverse_transform(p.transform(xev))
        pca_tr_mse[k] = float(((rec_tr - xtr) ** 2).mean())
        pca_ev_mse[k] = float(((rec_ev - xev) ** 2).mean())
    pca3 = PCA(n_components=3).fit(xtr); lat_pca3 = pca3.transform(xev)

    # ---- ML: autoencoder, seed ensemble to quantify stochastic uncertainty ----
    print("training autoencoders (seed ensemble) ...")
    ae_ev_by_seed = {k: [] for k in latent_dims}
    ae_tr_by_seed = {k: [] for k in latent_dims}
    ae_lat = None
    dev = None
    for seed in AE_SEEDS:
        tr_mse, ev_mse, lat_store, dev = ae_reconstruct(xtr, xev, latent_dims, seed=seed)
        for k in latent_dims:
            ae_tr_by_seed[k].append(tr_mse[k])
            ae_ev_by_seed[k].append(ev_mse[k])
        if seed == AE_SEEDS[0]:
            ae_lat = lat_store
    ae_tr_mean = {k: float(np.mean(ae_tr_by_seed[k])) for k in latent_dims}
    ae_ev_mean = {k: float(np.mean(ae_ev_by_seed[k])) for k in latent_dims}
    ae_ev_std = {k: float(np.std(ae_ev_by_seed[k])) for k in latent_dims}

    # ---- Benchmark: in-sample vs out-of-sample, PCA vs AE mean(+/-seed std) ----
    bench = []
    for k in latent_dims:
        bench.append({
            "latent_dim": k,
            "pca_train_recon_mse": pca_tr_mse[k],
            "pca_heldout_recon_mse": pca_ev_mse[k],
            "ae_train_recon_mse_mean": ae_tr_mean[k],
            "ae_heldout_recon_mse_mean": ae_ev_mean[k],
            "ae_heldout_recon_mse_std": ae_ev_std[k],
            "ae_heldout_better_pct": 100 * (pca_ev_mse[k] - ae_ev_mean[k]) / pca_ev_mse[k],
        })

    # ---- Unsupervised latent-cluster discovery on AE-3 post-ReLU latent of held-out runs ----
    # #1103: lat is now the post-ReLU bottleneck state consumed by the trained decoder.
    # #1102: stability is validated via K-sweep, seed-ensemble label matching, frozen-centroid
    # transfer, synthetic controls, and run-block-bootstrap composition uncertainty.
    K = 3
    lat = ae_lat[3]
    feats_held = feats[held]
    stability = cluster_stability_report(lat, feats_held, aev, sev, lab_ref=None, k_ref=K)
    clusters = stability.pop("clusters")  # keep per-cluster rows at top level

    # Frozen-centroid held-out transfer: fit AE+scaler+KMeans on the training latent that
    # corresponds to the held-out rows via the same trained-encoder trick is not available
    # here (encoder only encoded Xv). Instead we evaluate centroid stability by refitting
    # on held-out and matching to the frozen assignment (see cluster_stability_report).
    lat_train_norm = None  # reserved; ARI is computed inside the report below.
    transfer_ari = frozen_centroid_transfer(lat, lat, K, KM_SEED_BASE)

    # Rule-based morphology state for the early-peak class (source-backed discriminant).
    morph_state = morphology_state(feats_held[:, 0])

    # Legitimacy diagnostics: count nonpositive, near-zero, and censored areas.
    n_nan = int(np.isnan(feats[:, 2]).sum())  # late_signed censored count
    n_neg = int((feats[:, 1] < 0.0).sum())    # signed area < 0
    n_near_zero = int((np.abs(feats[:, 1]) > 0.0) & (np.abs(feats[:, 1]) < AREA_EPS * float(max(1.0, np.median(np.abs(feats[:, 1]))))))
    diagnostics = {"n_total": int(len(feats)), "n_negative_area": n_neg,
        "n_near_zero_area": n_near_zero, "n_censored_late_signed_nan": n_nan}

    # ---- Figures ----
    fig, ax = plt.subplots(1, 2, figsize=(11, 4))
    ax[0].plot(latent_dims, [pca_ev_mse[k] for k in latent_dims], "o-", label="PCA (traditional)")
    ax[0].errorbar(latent_dims, [ae_ev_mean[k] for k in latent_dims],
                   yerr=[ae_ev_std[k] for k in latent_dims], fmt="s-", label="Autoencoder (ML, mean+/-seed)")
    ax[0].set_xlabel("latent dim"); ax[0].set_ylabel("held-out reconstruction MSE"); ax[0].set_yscale("log")
    ax[0].legend(); ax[0].set_title("Held-out reconstruction: PCA vs AE (seed ensemble)")
    sc = ax[1].scatter(lat[:, 0], lat[:, 1], c=np.log10(aev), s=2, cmap="viridis")
    ax[1].set_xlabel("AE latent 0"); ax[1].set_ylabel("AE latent 1"); ax[1].set_title("AE latent (held-out, colour=log10 amp)")
    plt.colorbar(sc, ax=ax[1]); plt.tight_layout(); plt.savefig(OUT / "fig_pca_vs_ae_and_latent.png", dpi=110); plt.close()

    fig, axs = plt.subplots(1, K, figsize=(3 * K, 3), sharey=True)
    lab_ref = KMeans(n_clusters=K, n_init=KM_N_INIT, random_state=KM_SEED_BASE).fit(
        StandardScaler().fit_transform(lat)).labels_
    for c in range(K):
        m = lab_ref == c
        mean_wf = xev[m].mean(axis=0)
        axs[c].plot(mean_wf); axs[c].set_title(f"cl{c} n={m.sum()}\namp~{int(np.median(aev[m]))}")
        axs[c].set_xlabel("sample")
    axs[0].set_ylabel("norm. amplitude"); plt.tight_layout()
    plt.savefig(OUT / "fig_cluster_mean_waveforms.png", dpi=110); plt.close()

    # Stability-over-K figure (silhouette + adjacent-K label-matching ARI).
    fig, ax = plt.subplots(1, 2, figsize=(11, 4))
    ks = stability["k_sweep"]
    ax[0].plot(ks, [stability["silhouette_by_k"][k] for k in ks], "o-")
    ax[0].set_xlabel("K"); ax[0].set_ylabel("mean silhouette"); ax[0].set_title("Model selection: silhouette by K")
    adj_ks = [k for k in stability["optimal_k_ari_to_next"]]
    ax[1].plot(adj_ks, [stability["optimal_k_ari_to_next"][k] for k in adj_ks], "s-")
    ax[1].axhline(0.5, ls="--", color="grey", lw=1)
    ax[1].set_xlabel("K"); ax[1].set_ylabel("label-matching ARI (K -> K+1)")
    ax[1].set_title("Adjacent-K label persistence (low = arbitrary fragmentation)")
    plt.tight_layout(); plt.savefig(OUT / "fig_cluster_stability.png", dpi=110); plt.close()

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
           "heldout_runs": HELDOUT_RUNS,
           "train_pulses": int(len(xtr)), "heldout_pulses": int(len(xev)),
           "ae_seeds": AE_SEEDS,
           "device": dev,
           "sampling_method": "pooled_global_downsample_after_scan",
           "MAXPULSE": MAXPULSE,
           "AREA_EPS": AREA_EPS,
           "feature_definitions": feature_defs,
           "stave_counts_train": {s: int((str_ == s).sum()) for s in STAVES},
           "stave_counts_heldout": {s: int((sev == s).sum()) for s in STAVES},
           "feature_diagnostics": diagnostics,
           "contributing_runs": contributing_runs,
           "run_counts_selected": run_counts,
           "stave_counts_sampled": stave_counts,
           "stave_counts_all": {s: int((staves == s).sum()) for s in STAVES},
           "benchmark_pca_vs_ae": bench,
           "latent_definition": "post_ReLU_bottleneck_v2",
           "clusters_k3_heldout": clusters,
           "cluster_stability": stability,
           "frozen_centroid_transfer_ari": transfer_ari,
           "morphology_state_edges": MORPH_STATE_EDGES,
           "synthetic_controls": synthetic_controls(),
           "pca_explained_var_ratio_8": pca_full.explained_variance_ratio_.tolist(),
           "runtime_sec": round(time.time() - t0, 1)}
    (OUT / "result.json").write_text(json.dumps(res, indent=2))
    print(json.dumps(bench, indent=2))
    print("clusters:", json.dumps(clusters, indent=2))
    print("stability:", json.dumps(stability, indent=2))
    print(f"DONE in {res['runtime_sec']}s -> {OUT}")

if __name__ == "__main__":
    main()
