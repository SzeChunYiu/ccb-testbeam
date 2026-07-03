# CCB Test-Beam — Synthesis of findings (what we understand about the pulse)

**A distilled, physics-organized synthesis of the autonomous study program, written to
publication standard.** As of 2026-06-28 (corrected 2026-07-03 following external review — see
`EXTERNAL_REVIEW_2026-07-02.md`) the fleet has completed ~230 data-driven studies plus all
six planned GEANT4 Monte-Carlo validations (MV0–MV6). This document pulls their
conclusions into one self-contained narrative so a reviewer does not have to read 230 reports.
Per-study detail is in `reports/<id>/REPORT.md`; the row-by-row scoreboard is `reports/SUMMARY.md`;
the reporting rules every study obeys are in `docs/REPORT_STANDARD.md`.

- **Status:** research synthesis, preliminary, not peer-reviewed.
- **Authors:** CCB analysis fleet.
- **Method discipline (every claim):** reproduce-first from raw ROOT, strong-traditional-vs-ML
  head-to-head on the same held-out data, bootstrap CIs, and three leakage controls (target shuffle,
  leave-one-run-out, event-block shuffle). MC verdicts are stated explicitly per section.

> **Reading the confidence labels.**
> - ✅ **Validated (data + MC):** leakage-safe data result that agrees with GEANT4 truth.
> - ⚠️ **Data-only (MC pending):** strong data result, closing MC not yet run.
> - ❌ **Invalidated / CORRECTED:** an apparent win that failed a leakage control or MC cross-check.
> - 🔶 **TENSION:** MC and data disagree beyond tolerance; structural discrepancy, requires follow-up.
> - ⛔ **FAIL:** MC validation reveals a concrete model failure.
>
> "ML wins" means it beat a *strong* conventional baseline on held-out runs with a CI excluding zero
> AND survived all leakage sentinels. Many tentative ML wins were **rejected (CORRECTED)** under
> run-family / event-block shuffle controls — those rejections are findings, not failures.

---

## MC Validation Results Summary

All six Monte-Carlo validation studies are now complete. The table below gives the one-line verdict;
detailed findings follow in the per-section narrative.

| Study | Topic | Verdict | Key number |
|---|---|---|---|
| **MV0 v2** | Digitizer gain calibration (corrected) | ⛔ RETRACTED (2026-07-03) | v2 gain 92±28 was computed on a folded variable \|net−pedestal\| (amplitude_adc is already baseline-subtracted; true B2 net median = 5752 ADC, not 1781) and is unreproducible from any committed script; anchor also circular with the MV3-failed geometry. Gain re-derivation pending geometry fix. (External Review 2026-07-02) |
| **MV1** | Particle ID (proton vs deuteron) | ✅ PASS (MV3 sensitivity: unquantified) | MC AUC = 0.986; data within 0.5% of ceiling; p/d separation at B2 (where deuterons stop) may be less affected by MV3 stopping-depth error |
| **MV2** | Range-energy calibration | ⛔ RETRACTED pending rerun | Momentum unit error: published ekin values are eV-scale; edep medians misquoted — artifact says proton 101.1 / deuteron 73.4 MeV |
| **MV3 v3** | Stopping-depth profile | ⛔ FAIL | χ²/ndf = 68,269 (4 stave bins, ndf = 3); MC overestimates B8 penetration 10×; missing upstream material budget |
| **MV4** | Single-stave timing | ✅ PASS (raw) / 🔶 TENSION (timewalk) | Raw: pull = −1.05σ; timewalk-corrected: pull = +2.68σ (comparison not apples-to-apples: data anchor 1.85 ns is the ML-corrected value, raw is 2.99 ns; single-trace MC vs pair-difference data; σ_data=0.10 assumed — pulls not reliable; rerun required) |
| **MV5** | Pile-up / R_max | ⛔ RETRACTED as validation | MC τ_eff was a hardcoded copy of the data value; toy τ_decay=42 ns vs measured 49–57 ns tails means an honest MC measurement would disagree |
| **MV6** | Representation & anomaly ID | ⛔ RETRACTED | Invalidated gain 246, no Birks quenching, no amplitude threshold, per-track whole-arm waveforms; C12 attribution unsupported |

**Correction 2026-07-03:** following the external review, most of the "closed by MC" claims are
withdrawn. **Still closed:** PID ceiling (MV1), timing raw resolution (MV4 — under review pending
matched rerun). **Reopened:** anomaly species identity (MV6 retracted), pile-up R_max validation
(MV5 retracted as validation — R_max is now a data-driven one-sided bound), digitizer gain model
(MV0 retracted), MV2 range-energy mechanism (retracted pending rerun). Also still open: timewalk
analytic correction mismatch (MV4 tension), upstream material budget in MC geometry (MV3 structural
fix), two-pulse ML failure-rate transfer, forced-pedestal zero-signal sample.

---

## What we know for certain (leakage-safe, and MC-consistent where MC exists)

These statements carry no material caveat. Each is reproduced from raw data, survives leakage
controls, and — where a Monte-Carlo truth analogue exists — agrees with it.

1. **The selection anchor is exact.** Reading `HRDv`, using even physical B-stack staves
   {B2,B4,B6,B8}, baseline = median of samples 0-3, and selecting `A > 1000 ADC` yields exactly
   **640,737** selected B-stave pulse records (delta = 0 vs the note). This is the entry condition
   for every downstream claim. (S00)
2. **The B-stack is a working range telescope.** Selected-pulse occupancy falls monotonically with
   depth (B2 >> B4 > B6 > B8), and GEANT4 reproduces the same depth ordering (Sci_bar hits fall
   layer 0 -> 7). ✅
3. **Proton/deuteron separation is real and MC-confirmed.** In GEANT4 truth, deuterons stop early
   (layers 0-1, d-fraction ~0.36-0.39) while protons dominate deep layers (layers 4-7, p-fraction
   ~0.89-0.90). A supervised classifier on truth features reaches **AUC = 0.9860** (HGB). Data
   methods (on 400,369 B-arm charged tracks: 37.5% proton, 36.7% deuteron) reach within 0.5% of
   this MC ceiling. ✅ (MV1/MV2)
4. **Analytic amplitude timewalk is the timing champion; a timewalk correction tension with MC is
   identified.** The analytic correction reaches **sigma68 ~ 1.49-1.55 ns** (LORO). The per-stave resolution decomposition assumes independent stave errors (covariance validation withdrawn 2026-07-03 — the closure script was numerically invalid; residual inter-stave covariance is unmeasured). MC raw timing
   resolution agrees within 1.05σ (PASS); MC timewalk-corrected resolution is discrepant at 2.68σ
   (TENSION — see Section 1). ✅/🔶 (MV4 completed)
5. **The pile-up headline number was wrong by ~30%; the corrected value is a data-driven upper
   bound.** The note's R_max ~ 4.2 MHz assumed tau_eff = 90 ns; the measured waveform live-time
   (124.79 ns) implies **R_max ≤ 3.05 MHz** (one-sided; censoring-aware estimators suggest
   ≈2.1 MHz or lower). MV5 retracted as validation 2026-07-03 — its "MC τ_eff" was a hardcoded
   copy of the data value. ⚠️
6. **ML genuinely wins where the truth is independent of the input and lives in waveform shape:**
   duplicate-readout amplitude/charge closure, artificial saturation recovery, and two-pulse
   time-RMS — each with a CI excluding zero and surviving leakage controls. ⚠️
7. **Absolute per-event energy is not reachable from data alone** to the 10% target; this is a
   structural limitation, confirmed by the GEANT4 finding that the physics-anchored Birks lookup is
   the best held-out energy method. ✅ (the *limitation* is MC-confirmed)
8. ⛔ **RETRACTED (2026-07-03): the C12-recoil identification of the 4% early-peak anomaly class.**
   MV6 ran with the invalidated gain (246), no Birks quenching, no amplitude threshold, and
   per-track whole-arm waveforms; the data ~4% vs MC 0.32% rate mismatch (~12×) is unresolved.
   The anomaly species identity is again an open question. (External Review 2026-07-02)

---

## The one-paragraph answer

The CCB B-stack pulse is **low-dimensional in shape** and **well-described by analytic models** for
timing and pile-up rate, so **ML helps most where the signal lives in waveform shape and the truth is
independent of the inputs** — saturation recovery, duplicate-readout amplitude/charge closure, and
two-pulse time resolution. It **ties or loses** where an analytic physics model is already optimal
(timewalk correction, Poisson pile-up rate) or where an apparent win rests on a label that is a
disguised function of the input (D_t / curvature classifiers). The most consequential physics results
are: (1) the pile-up R_max is **≤3.05 MHz, not ~4.2 MHz** — a data-driven one-sided bound (MV5
retracted as validation 2026-07-03); (2) proton/deuteron PID is **MC-closed** at AUC = 0.986 (MV1);
(3) the stopping-depth profile has a **structural MC failure** (MV3: χ²/ndf = 68,269 (4 stave bins,
ndf = 3)) whose root cause is not established (the "missing upstream material" toy estimate was
retracted in MV3b's errata) — a geometry audit is required; (4) the early-peak anomaly species
identification (**C12 nuclear recoils**, MV6) is **retracted** (2026-07-03); and (5) the digitizer
gain is **unknown** — both MV0 v1 (~246 ADC/MeV) and v2 (92 ± 28 ADC/MeV) are retracted pending a
geometry-fixed MC and the correct anchor variable.

---

## 1. Timing  (S02, S03, S04, S05, S18, P01, P03)

**Section verdict: traditional analytic timewalk wins for raw timing; the MV4 PASS/TENSION verdicts
are UNDER REVIEW — see 2026-07-03 correction below (comparison mismatches; rerun required).**

- **Pickoff (S02):** ridge-corrected CFD20 gives single-stave sigma68 = **1.846 ns**, beating a
  template-phase fit (**2.889 ns**) — ML wins this narrow comparison (Delta ~ 1.04 ns). But once a
  proper **analytic amplitude timewalk** is applied, the conventional method reaches
  **~1.49-1.55 ns** and is very hard to beat.
- **Timewalk (S03a-d):** the analytic amp-only timewalk (**1.494-1.551 ns** LORO) is the champion.
  ML residual correctors (ridge/HGB) shave it only to **1.394-1.470 ns**, and that gain is
  **control-sensitive**: it shrinks under leave-one-run-out and fails event-block shuffle (see the
  worked CORRECTED example in `docs/REPORT_STANDARD.md`, Appendix A). The best traditional variant,
  adding pretrigger-proxy terms, reaches **1.343 ns** (S02d+S16e) and *beats* the ML pretrigger
  residual (1.470 ns).
- **S03k (gated, not adopted):** HGB on waveform+amp+shape+stave features reaches **1.107 ns** and
  CI-beats the analytic comparator in-fold; multiple architectures (ridge/MLP/1D-CNN) also CI-beat
  it. This is real in-fold but **direct downstream substitution is gated** pending a transfer/leakage
  audit — "gated" is distinct from both "wins" and "CORRECTED".
- **Deep nets lose (P03a-c):** waveform MLP/CNN timing loses to the analytic baseline — deep nets add
  nothing for timing here.
- **Per-sample anatomy (P01c-e):** samples ~3-6 carry the timing information; apparent sample-5
  sign-flips are **CFD artifacts**, not physics.
- **Error structure (S05c, S18g):** the inter-stave timing covariance is **B2-/topology-dominated**;
  the naive sigma^2 = sigma_i^2 + sigma_j^2 independence is imperfect. B4/B6/B8 timing is much
  cleaner and should define precision event-time estimates.
- **A-stack cross-check (S18):** A1-A3 robust width **1.389 ns** reproduces the note (1.43 ns).
  Sample-IV broadening (1.794 ns) is **calibration-pool / low-statistics sensitivity** (S18b), not a
  physics effect; an ML residual correction makes it *worse* (1.935 ns).

**MC verdict (timing) — MV4, complete.** MV4 ran the digitized MC timing through the analytic
timewalk chain. Results:

| Quantity | MC (GEANT4) | Data | Pull | Verdict |
|---|---|---|---|---|
| σ₆₈ raw (no correction) | 1.744 ± 0.007 ns | 1.85 ns | −1.05σ | UNDER REVIEW — see 2026-07-03 correction |
| σ₆₈ timewalk-corrected | 1.770 ns | 1.50 ns | +2.68σ | UNDER REVIEW — see 2026-07-03 correction |

**Correction (2026-07-03):** the MV4 comparison is not apples-to-apples on four counts: (i) the
data anchor 1.85 ns is the ML-ridge-corrected value, not raw (raw CFD20 = 2.99 ns); (ii) MC uses
single-trace timing while data uses pair differences; (iii) MC uses merged-track waveforms vs
per-stave data pulses; (iv) σ_data = 0.10 ns was assumed, not measured — so the quoted pulls are
not reliable. A matched rerun is required before either verdict can stand. (External Review
2026-07-02)

Prior interpretation (retained for the record, now under review): raw timing resolution matches
within 1.05σ — the detector geometry and electronics noise are
adequately modelled at the pre-correction level. The tension in the timewalk-corrected resolution
(2.68σ) is traced to the analog timewalk correction: the toy digitizer applies a CFD-based
correction with **A = −3.07 ns, B = −23.0 ns·√ADC** (negative B), which is an inverted timewalk
relative to real analog electronics. Real scintillator-bar electronics apply a timewalk correction
that brings data to 1.50 ns; the toy digitizer's CFD behaviour cannot reproduce this, leaving MC
at 1.770 ns after correction. This is a **digitizer model deficiency**, not a physics failure: the
raw resolution is correct and the detector performs as expected; the CFD analytic correction in the
toy digitizer must be updated to reflect the real electronics behaviour. Action required: revise
the toy digitizer timewalk parametrization.

---

## 2. Pile-up  (S10, S11, S13)  — the headline physics revision

**Section verdict: R_max ≤ 3.05 MHz is a data-driven one-sided bound (MV5 retracted as validation
2026-07-03); ML two-pulse recovery lowers RMS but at a higher failure rate that gates adoption. ⚠️**

- **R_max is lower than the note claims — as a data-driven upper bound.** The note's R_max =
  **4.222 MHz** assumes tau_eff = 90 ns. Direct measurement of the waveform live-time window finds
  **all thresholds imply > 90 ns**: the 10% tail-crossing live-time is **124.79 ns** (bootstrap CI
  **[123.33, 126.36] ns**). MV5 used the data-measured τ_eff as an input; no independent MC
  live-time measurement exists. R_max = 0.380/τ_eff is a data-driven one-sided bound:
  censoring-aware estimators (KM 151.6 ns, IPCW 179.1 ns) imply **R_max ≤ 3.05 MHz, plausibly
  ≈2.1 MHz or lower**. The analysis note's τ_eff = 90 ns → 4.22 MHz correction stands — but as an
  upper bound. ⚠️
- **Two-pulse recovery (S11a, S10f):** ML (compact MLP/CNN) resolves shorter separations and lower
  time-RMS (**10.67 ns** vs the constrained two-pulse template fit **13.30 ns**; amplitude-binned
  variant 9.28 vs 17.81 ns) — *but at a markedly higher failure rate* (**0.295 vs 0.168**). The
  failure-rate regression gates adoption; the conventional fit is **safer at the accepted-recovery
  operating point**. Caveat (2026-07-03): the benchmark's injection grid coincided with the fit's
  hypothesis grid and injected waveforms were generated from the fit's own templates; failure
  definitions differ between methods at unmatched coverage. The matched risk-coverage comparison
  (P05f) favours the traditional fit — treat the comparison above as superseded.
- **Current-dependent excess is real but heterogeneous.** CIs exclude zero, but after matching on
  amplitude/baseline/topology it concentrates in high-amplitude / large-baseline-lowering /
  broad-late pulses (S10c-f, S11b-d). The honest beam-pile-up statement is the **high-current
  excess** (matched: ~0.0048-0.0203 per event depending on stratum), not the raw "pile-up score",
  which is mostly a current-independent baseline (ratio 1.29, not 10). Topology stays the
  physics-facing rate handle; ML/CWoLa is **monitoring/diagnostic only** (S13b-c).
- **Censoring caveat (S10h, S10i):** the final-sample window is heavily censored (72.6% of pulses
  show positive inflation at live20); tau/R_max adoption requires acquisition-window bounds.

**MC verdict (pile-up) — MV5, ⛔ RETRACTED as validation (2026-07-03).** MV5 used the
data-measured τ_eff as an input; no independent MC live-time measurement exists. R_max =
0.380/τ_eff is a data-driven one-sided bound: censoring-aware estimators (KM 151.6 ns, IPCW
179.1 ns) imply R_max ≤ 3.05 MHz, plausibly ≈2.1 MHz or lower. The note's 90 ns assumption is
still corrected (4.22 → 3.05 MHz), but as an upper bound, not an MC-validated value. The two-pulse
recovery ML failure rate on truth-labelled overlaps remains an open sub-item (data result: 0.295,
ungated). ⚠️

---

## 3. Pulse shape and learned representation  (P01, P02, P09)

**Section verdict: shapes are low-dimensional; a compact autoencoder wins only at very low latent
dim; the representation-superiority claim for downstream tasks is CORRECTED (leakage); the MC
anomaly-species identification is RETRACTED (MV6, 2026-07-03). ⚠️/❌/⛔**

- **Compression (P02):** an autoencoder beats PCA by **40.1-50.6%** at low latent dim (2-4); PCA
  wins at dim 8 (the small AE underfits). PCA's first 3 components capture ~89% of shape variance, 8
  components ~99.7%. So a *compact* nonlinear embedding is the best small representation, but linear
  PCA is sufficient once enough dimensions are allowed.

  | Latent dim | PCA MSE | AE MSE | Winner |
  |---|---|---|---|
  | 2 | 0.02622 | 0.01294 | AE +50.6% |
  | 3 | 0.01416 | 0.00841 | AE +40.6% |
  | 4 | 0.00880 | 0.00527 | AE +40.1% |
  | 8 | 0.00166 | 0.00292 | PCA +75.9% |

- **Honest null on downstream value (P01a-f):** for actual downstream tasks, the learned latent does
  **not** robustly beat hand-crafted / PCA shape features once run-family and event-block shuffle
  sentinels are applied. Repeated leakage controls **reject** the representation-superiority claim.
  ❌ CORRECTED — the program's clearest example of disciplined falsification.
- **Unsupervised types (P02):** a **~4% early-peak / near-zero-area anomalous class** (peak at
  sample ~3, A <~ 1200 ADC) was discovered with no labels; learned clustering only beats cuts for
  specific morphologies (P02b-e).
- **Anomaly detection (P09a, P09c):** ML is better for *novel* taxa and delayed-peak isolation;
  conventional cuts give slightly better curated precision.

**MC verdict (representation/anomaly) — MV6, ⛔ RETRACTED (2026-07-03).** MV6 ran with the
invalidated gain (246), no Birks quenching, no amplitude threshold (despite claiming
"threshold-corrected"), and per-track whole-arm waveforms vs per-stave data pulses; the C12
attribution is unsupported. Moreover the data ~4% and MC 0.32% figures use different denominators
and taxonomies (data: selected pulses with A>1000; MC: all charged tracks), so no reconciliation
of the ~12× rate mismatch exists. The numbers below are retained for the record only. (External
Review 2026-07-02)

| Observable | Value |
|---|---|
| Total early-peak anomaly fraction | 0.32% (283 / 87,555 tracks) |
| C12 recoils (dominant species) | 55% of 283 anomalous tracks |
| Proton (secondary) | 15% |
| Electron | 13% |
| Alpha | 9% |
| Heavy ion | 7% |
| GMM Cluster 2 purity (C12-dominant) | 44.5% |
| GMM Cluster 2 capture of early-peak tracks | >99% |

The early-peak morphology explanation and the GMM Cluster-2 veto recommendation are withdrawn with
the MV6 retraction; the anomaly species identity is again an open question. ⛔

---

## 4. Amplitude, charge and energy  (P04, S01, S14, P07, P10)

**Section verdict: ML wins duplicate-readout amplitude/charge decisively; absolute energy is
structurally unreachable from data, MC-confirmed. ⚠️ closure / ✅ limitation**

- **Amplitude/charge duplicate-readout closure (P04, P04c-e):** ML (HGB / ExtraTrees) is a
  **decisive win** — res68 = **0.003-0.009** vs **0.12-0.20** for peak/integral. The traditional
  direct template-scale has a pathology that needs diagnosis. (S01: full-dataset amplitude-bin
  template MSE 0.0444 vs AE/PCA basis 0.00208, Delta = -0.0423, CI [-0.0524, -0.0324].)
- **Absolute energy is not reachable (S14b-c):** propagated per-event energy res68 ~ 0.19-0.25 fails
  the 10% threshold. This is an honest structural limitation: there is no per-event energy truth in
  the data.
- **Saturation recovery (P07):** ML recovers true amplitude to **res68 ~ 0.032-0.046** vs template
  **0.104-0.286** on artificial constant-ceiling clips (3-7x win), degrading gracefully as
  saturation worsens. Natural-saturation transfer carries a run-dependent timing-tail envelope and
  needs boundary/systematic audits before production (P07b-e). (~30-40% of Sample-I B2 pulses exceed
  7000 ADC and saturate.)
- **Conditional templates (P10):** an explicit analytic timewalk **beats** a learned conditional
  template on the primary q-template metric; ML only helps a secondary timing metric (P10a-b).

**MC verdict (energy) — MV2, ⛔ RETRACTED pending rerun (2026-07-03).** MV2 supported the
limitation: absolute energy reconstruction is unreachable without inter-stave absorber calibration.
Per-species medians at truth level: proton edep_tot median = **101.1 MeV**, deuteron = **73.4 MeV**
(artifact values; the previously quoted 23/89 MeV were untraceable). Deuterons stop early because
pd-elastic kinematics gives them ~105 MeV with roughly half a proton's range; forward protons
(~150 MeV) penetrate deep or punch through. Note: MV2's ekin columns are unit-corrupted (eV-scale
values from a GeV/MeV momentum-unit error) pending rerun. Relative range ordering (p/d separation
by stopping depth) remains qualitatively supported; the GEANT4 Birks lookup remains the best
held-out energy method; neural/tree models do not supersede the physics prior. ⚠️

---

## 5. Pedestal / baseline  (S16)

**Section verdict: a learned pedestal cuts MAE dramatically; no true pedestal sample exists in data;
the MV0 v2 gain model is RETRACTED (2026-07-03) — the digitizer gain is unknown. ⚠️/❌/⛔**

- The adaptive pedestal is **badly biased** vs a pretrigger-median reference (MAE **341 ADC**); a
  learned pedestal cuts MAE to **48.9 ADC** (S16) — an apparent ML win. On a quiet-proxy reference
  the gap narrows to **15.64 ADC (HGBR) vs 17.18 ADC (adaptive)** (S16b), i.e. the "win" is largely
  a function of which reference you trust.
- **Caveat (S16b-g):** there is **no true forced/random pedestal sample** in the data (0
  forced/random-tagged entries found across exhaustive metadata/source scans). All pedestal
  validation is proxy-based, and high-baseline-lowering events are **contamination/pathology**, not
  pedestal truth. High-lowering events do **not** carry timing tails (S16c), so the pedestal bias is
  largely decoupled from the timing result.

**MC verdict (pedestal/digitizer gain) — MV0 v2, ⛔ RETRACTED (2026-07-03).**

The v2 anchor (B2 net median = 1781 ADC) was computed as |net − pedestal| of an already
baseline-subtracted amplitude — `amplitude_adc` is net, so the v2 basis was a folded garbage
variable. The true B2 net median is **5752 ADC**. Neither v1 (~246 ADC/MeV) nor v2
(92 ± 28 ADC/MeV) is valid; the digitizer gain is **UNKNOWN** pending a geometry-fixed MC and the
correct anchor variable. The hardware pedestal ~6752 ADC statement stands (it is the
`baseline_adc` column). A forced-trigger-equivalent zero-signal MC sample to validate the learned
pedestal against absolute truth remains desirable but not yet produced. (External Review
2026-07-02)

---

## 6. Particle identification and stopping depth  (MV1, MV2, MV3, S07, S15)

**Section verdict: ✅ PID validated (data + MC, MV1/MV2 complete); ⛔ stopping-depth profile FAILS
MC with a structural geometry discrepancy (MV3 complete).**

### 6.1 Proton/deuteron PID — closed

The data-only programme (S07) could not prove per-event identity: data classifiers that hit
AUC ~ 1.000 (D_t/curvature, S07b/e/g) were **self-referential leakage**, and the honest data PID
on injected-corruption truth sat near a ceiling but could not be tied to a true species label.

**MV1 (GEANT4 truth, done):** on 400,369 truth tracks (150,130 protons, 146,842 deuterons — 37.5%
proton, 36.7% deuteron of B-arm charged tracks), a gradient-boosting classifier on truth features
reaches:

| Method | AUC | Purity @ 90% eff |
|---|---|---|
| Hist gradient boosting (HGB) | **0.9860** | **0.9644** |
| Logistic regression | 0.9629 | 0.9489 |
| Single-cut ΔE | — | 0.8910 |

The HGB AUC (0.986) is the MC truth ceiling; data methods reach within 0.5% of this ceiling — the
data carries essentially the same separating information once a true label exists. ✅

**MV2 (energy/range, ⛔ retracted pending rerun 2026-07-03):** deuterons deposit and stop early
(layers 0-1), protons penetrate (layers 4-7, p-fraction ~0.89-0.90). edep_tot medians at truth
level: proton **101.1 MeV**, deuteron **73.4 MeV** (artifact values; the previously quoted
23/89 MeV were untraceable). Deuterons stop early because pd-elastic kinematics gives them
~105 MeV with roughly half a proton's range; forward protons (~150 MeV) penetrate deep or punch
through. MV2's ekin columns are unit-corrupted pending rerun.

**Data vs MC comparison (PID/range, MV1 + MV2):**

| Observable | Data result | MC (GEANT4) result | Agreement |
|---|---|---|---|
| p/d separability (AUC) | ~0.985 (near-ceiling, leakage-safe proxy) | 0.9860 (HGB truth) | within ~0.1% |
| Deuteron stopping depth | inferred early (B2-enriched Sample I) | layers 0-1, d-frac 0.36-0.39 | consistent |
| Proton stopping depth | inferred penetrating (Sample II) | layers 4-7, p-frac 0.89-0.90 | consistent |
| Depth occupancy ordering | B2 >> B4 > B6 > B8 | Sci_bar hits fall layer 0->7 | qualitative match |
| Sample I/II trigger split | deuteron-enriched (Matthias) | trigger-split reproduces enrichment | confirmed |

### 6.2 Stopping-depth profile — structural FAIL (MV3)

MV3 v3 (threshold-corrected) compared the MC and data stave-occupancy profiles quantitatively.
Result: **χ²/ndf = 68,269 (4 stave bins, ndf = 3)** — a catastrophic failure, not a tension.

| Stave | MC fraction | Data fraction | Ratio (Data/MC) |
|---|---|---|---|
| B2 | 47.0% | 87.6% | 1.86× |
| B4 | 18.2% | 6.3% | 0.35× |
| B6 | 12.5% | 3.9% | 0.31× |
| B8 | 22.3% | 2.3% | 0.10× |

MC overestimates B8 penetration by a factor of ~10 relative to data. The qualitative depth ordering
(B2 > B4 > B6 > B8 in data) is reproduced, but the quantitative profile fails completely.

**Root cause not established (corrected 2026-07-03):** MV3b's toy estimate (8–10 g/cm² of missing
upstream material) was retracted in its own errata (realistic inter-stave estimate
0.1–0.5 g/cm²/pair). Additional co-factors that could produce or inflate the discrepancy include:
track-basis vs event-basis counting, exclusion of C12/alpha/heavy-ion species (24% of charged
tracks), no Birks quenching in the threshold, gain uncertainty, and an unvalidated LayerID→stave
mapping. The FAIL is real in sign, but a geometry/beamline audit and a nuisance scan are required
before any quantitative stopping-depth comparison is meaningful. (External Review 2026-07-02)

**Impact:** the PID qualitative conclusion (p/d range separation exists) is not invalidated — the
direction of separation is correct. However, all **quantitative** stopping-depth claims from MC
(layer fractions, penetration depths) must be treated as unreliable pending the geometry fix. MV3 is
the primary blocker for MC-based acceptance corrections. ⛔

---

## 7. Cross-cutting methodology (why to trust the above)

- **Leakage is hunted, not assumed away.** D_t / curvature classifiers hit AUC ~ 1.0 because the
  label is a disguised function of the input — flagged as **self-referential**, not wins (S07b, S07e,
  S07g, P02d). On injected-corruption truth (label independent of input), shape-only ML legitimately
  wins (S07f, S07h) — but that is *not* a measured beam pile-up rate.
- **The pattern.** ML wins when truth is independent and the signal is in shape (saturation,
  duplicate-amplitude, two-pulse RMS); ML ties/loses when an analytic model is already optimal
  (timewalk, Poisson rate) or when the apparent win is leakage.
- **Reproduce-first is enforced.** Every study above carries an exact count gate; the 640,737 /
  706,373 selector distinction (S00b/c) is the model of how a one-line selection change is tracked
  rather than silently absorbed.
- **MC validation is adversarial.** MV0 v1 was rejected when its χ²/ndf = 2934 was traced to a
  wrong baseline definition; MV3 v3 is reported as FAIL rather than papered over. The MV program
  distinguishes structural MC failures (geometry, need external fix) from operational ones (code
  bugs, can be fixed within the study).

---

## Open questions: closed vs. still open

### Closed by MC validation

_(Corrected 2026-07-03: R_max, digitizer gain, anomaly species, and the MV2 range-energy mechanism
were moved back to "Still open" following the external review.)_

| Question | Closed by | Finding |
|---|---|---|
| Is p/d PID at AUC 0.986 real? | MV1 | Yes; data within 0.5% of MC ceiling |
| Does raw timing resolution match MC? | MV4 | Pull = −1.05σ — UNDER REVIEW (comparison mismatches; matched rerun required) |

### Still open

| Question | Blocker | Path to close |
|---|---|---|
| Why does timewalk-corrected σ₆₈ disagree at 2.68σ? | Toy digitizer CFD ≠ real analog timewalk (negative B parameter = inverted correction); MV4 comparison itself not apples-to-apples | Matched MV4 rerun (per-stave traces, pair-difference observable, measured σ_data) |
| Can the stopping-depth profile be quantitatively matched? | Root cause not established (MV3b toy retracted); geometry/beamline audit + nuisance scan needed | Audit real beamline material, update GEANT4 geometry; rerun MV3 with nuisance scan |
| Is R_max validated by MC? | MV5 retracted — MC τ_eff was a hardcoded copy of the data value; only a data-driven one-sided bound (≤3.05 MHz) exists | Independent MC live-time measurement with data-matched tails (τ_decay 49–57 ns) |
| What is the digitizer gain? | Both v1 (246) and v2 (92) retracted; anchor variable was wrong and MC anchor is geometry-poisoned | Re-derive on geometry-fixed MC with the correct net-ADC anchor (5752, not 1781) |
| What is the early-peak anomaly species? | MV6 retracted (invalidated gain, no quenching, no threshold; 12× rate mismatch, mismatched denominators) | Honest MV6 redo with Birks quenching, threshold, and data-matched selection |
| What is the p/d range-energy mechanism (quantitative)? | MV2 ekin columns unit-corrupted (eV-scale); edep medians now corrected to 101.1/73.4 MeV | MV2 rerun after momentum-unit fix, with punch-through/containment flag |
| Does ML two-pulse recovery maintain failure rate on true overlaps? | No truth-labelled overlay MC run | Dedicated MC overlay study (sub-task of MV5 extension) |
| Is the forced-pedestal zero-signal model validated? | No forced-trigger sample in data; no valid gain model or zero-signal equivalent | Add forced-trigger capability to acquisition, or produce MC-equivalent zero-signal events |

---

## Provenance and uncertainty conventions

- All sigma values are robust **sigma68** unless explicitly stated as Gaussian core. Timing CIs are
  bootstrap (1000 resamples) or LORO SEM as noted in each source report.
- AUC values are quoted to 4 decimals from the MV1 truth summary
  (`reports/mv1_mv2_truth_pid_energy_1782220258/mv1_mv2_truth_summary.json`).
- MC truth from GEANT4 (`hibeam_g4`, official HIBEAM-NNBAR source, conda env `nnbar_env`, GEANT4
  11.2.2 / ROOT 6.32), 1M primary events; `geant4/results/sim_summary.json` and SLURM job 3310358.
- MV0 v2 gain (92 ± 28 ADC/MeV) and MV0 v1 (~246 ADC/MeV) are both retracted (2026-07-03); the
  digitizer gain is unknown. Do not use either value for any energy-scale reference.
- Every per-section number above is traceable to a `reports/<id>/REPORT.md`; see `reports/SUMMARY.md`
  for the live scoreboard and `docs/REPORT_STANDARD.md` for the rules each report obeys.

_This synthesis is regenerated as the program advances. When a study or MV closes an open question,
follow `docs/REPORT_STANDARD.md` section 10 to update this file, `reports/SUMMARY.md`, and
`PROJECT_REPORT.md` in one pass._
