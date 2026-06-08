# Study report: P02 — Pulse-shape representation & unsupervised pulse-type discovery

- **Study ID:** P02 (orchestrator-run, while the codex fleet was paused on a Codex usage limit)
- **Author:** Claude (orchestrator)
- **Date:** 2026-06-08
- **Depends on:** S00 (selection definition)
- **Input:** raw `data/root/root/hrdb_run_{58..63,65,50}.root` (immutable store; sha256 in `manifest.json`)
- **Code:** `scripts/p02_pulse_representation.py`

## 0. Question
Can a learned representation of the 18-sample B-stave waveform (a) compress pulse shape better
than the traditional linear method (PCA), and (b) reveal pulse *types* without labels? Both
methods are benchmarked head-to-head.

## 1. Reproduction / selection consistency
Selection follows S00 exactly: B-staves **B2=ch0, B4=ch2, B6=ch4, B8=ch6** of the
`HRDv` branch reshaped `(events, 8, 18)`; baseline = median of samples 0–3; amplitude =
max(baseline-subtracted); cut **A > 1000 ADC**. The selected sample is strongly **B2-dominated**
(B2 40,572 / B4 10,977 / B6 5,992 / B8 2,459 of 60,000), consistent with the report's
penetration picture (Sample II analysis runs + one Sample I run). Full count reproduction is
S00's job (done, 640,737); here the selection rule is reused, not re-validated.

## 2. Traditional method — PCA
PCA on amplitude-normalised waveforms. Pulse shape is **low-dimensional**: explained-variance
ratio of the first 8 PCs = **[0.639, 0.155, 0.095, 0.042, 0.028, 0.015, 0.008, 0.005]** — the
first **3 PCs capture 89%** and 8 PCs capture **99.7%** of the shape variance. So a handful of
linear modes already describe most of the pulse shape.

## 3. ML method — autoencoder
A small fully-connected autoencoder (18→16→k→16→18, ReLU, Adam, 60 epochs, GPU) trained to
reconstruct the normalised waveform, for latent dims k ∈ {2,3,4,8}. Same data as PCA. The
encoder's k-dim bottleneck is the learned representation. (Train/test split not applied here —
this is an unsupervised reconstruction/representation study; for a predictive claim a by-run
split would be required.)

## 4. Head-to-head benchmark (reconstruction MSE, lower = better)

| Latent dim | PCA (traditional) | Autoencoder (ML) | AE vs PCA |
|---|---|---|---|
| 2 | 0.02622 | 0.01294 | **AE 50.6% better** |
| 3 | 0.01416 | 0.00841 | **AE 40.6% better** |
| 4 | 0.00880 | 0.00527 | **AE 40.1% better** |
| 8 | 0.00166 | 0.00292 | **PCA 75.9% better** |

**Verdict.** The nonlinear AE compresses pulse shape **40–51% better than PCA at low latent
dims (2–4)** — worth it when you need a *compact* embedding (e.g. to feed a downstream
classifier or a 2-D map). But at dim 8 the linear PCA is already near-perfect (MSE 0.0017,
99.7% variance) and the small AE *underfits* (it would need more capacity/epochs to match). So
**ML wins for compact representations; the simpler traditional method wins once enough linear
dimensions are allowed.** (`fig_pca_vs_ae_and_latent.png`, left.)

## 5. Unsupervised pulse-type discovery
KMeans (k=5) on the AE-3 latent, characterised by amplitude / peak position / stave
(`fig_cluster_mean_waveforms.png`):
- **Clusters 2 & 3 (≈82%):** normal pulses, peak at sample **7–8**, positive late-charge; split
  mainly by amplitude (median ≈ 4400 vs 2680 ADC).
- **Clusters 1 & 4 (≈4.4%, ~2,640 pulses):** a distinct **early-peak class (peak at sample 3)**,
  low amplitude (≲1200 ADC), with near-zero / pathological integrated area. These are isolated
  purely from waveform shape — candidate **baseline-threshold / noise / bipolar artifacts**.
  This is a concrete, label-free lead for the anomaly study **P09** and a quality flag the
  timing studies should exclude.

## 6. Threats to validity
- **No truth labels** — cluster "meaning" is inferred from amplitude/peak/stave, not ground
  truth. Honest until a GEANT4 truth set (S17) exists.
- **Feature artifact (found & reported):** the `late_fraction = tail/area` feature diverges for
  the near-zero-area early-peak class (area → 0). That divergence is itself the signal that this
  class is morphologically different; the cluster split does **not** depend on that feature (it
  uses the AE latent).
- **Sampling:** 60k of the available pulses, B2-dominated; results may shift for a downstream-only
  or per-run-balanced sample. AE not hyperparameter-scanned (fixed 60 epochs, one architecture).
- No train/test split (unsupervised reconstruction); a predictive use must add a by-run split.

## 7. Findings & next steps
- Pulse shape is **low-dimensional** (3 PCs ≈ 89%); a 2–4-dim **AE embedding beats PCA by ~40–50%**
  and is the recommended compact representation to feed P03 (timing), P05 (pile-up), P08 (PID).
- The unsupervised AE **discovered a ~4% early-peak/low-area anomalous class** with no labels →
  spin up **P09** (anomaly detection) on it; the timing pipeline should flag/exclude it.
- Next: (a) fix the `late_fraction` feature for zero-area pulses; (b) scan AE capacity/epochs to
  confirm it can match PCA at dim 8; (c) by-run split + linear-probe to quantify the embedding's
  downstream value (P01 proper).

## 8. Reproducibility
`cd <clone> && python3 scripts/p02_pulse_representation.py` → writes `result.json`, the two
figures, and this report's numbers. Inputs + code hash in `manifest.json`.
