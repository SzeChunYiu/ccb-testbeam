# Master study plan

This is the prioritised list of everything we can study on the CCB test-beam data. It is the
source from which `tn-ticket`s (`project:testbeam`) are cut. Each study becomes one or more
tickets; each ticket produces a report in `reports/` following
[`STUDY_TEMPLATE.md`](STUDY_TEMPLATE.md).

## Governing principles (non-negotiable)

1. **Reproduce before you extend.** No new result is trusted until the corresponding number in
   the existing notes is reproduced **from the raw ROOT files** by an independent script and
   shown to match (state the tolerance). If it does not match, that discrepancy *is* the
   finding — stop and report it.
2. **Both methods, always.** Every quantity is studied with a **traditional (non-ML) method**
   *and* an **ML method**, reported as a **fair head-to-head benchmark** on the same held-out
   data with the same metric. ML must beat a *strong* baseline to be adopted — not a strawman.
3. **Atomic decomposition.** Break every result into the smallest verifiable steps (one cut,
   one fit, one correction, one feature) and understand each before combining. Each step gets
   its own validation plot/number.
4. **Honest uncertainty.** Report statistical *and* systematic uncertainties, χ²/ndf, bootstrap
   CIs (especially for small classes), and full distributions — not just a core σ.
5. **Provenance.** Pin every result to an input checksum, a git commit, and a config file.

## Phases

- **Phase 0 — Foundation & reproduction** (S00–S01): data integrity + reproduce the pipeline.
  **Gate: nothing in Phase 1+ starts until S00 reproduces the headline counts.**
- **Phase 1 — Atomic understanding** (S02–S07, S10–S13, S18): reproduce + dissect every existing
  result, traditional vs ML, to the finest level.
- **Phase 2 — Extension** (S08–S09, S14–S17): new methods (deep learning, simulation, PID,
  energy calibration) that go beyond the notes.

Difficulty/where: **[L]** laptop-fine, **[G]** needs LUNARC GPU, **[C]** CPU-heavy → LUNARC node.

---

## Phase 0 — Foundation & reproduction

### S00 — Data integrity & pipeline reproduction  [L]  (gate; no deps)
- **Reproduce:** rebuild the selected-pulse table from raw ROOT; confirm **640,737** B-stave
  pulses (A>1000 ADC), per-run and per-stave counts (Tables 1–4), and regenerate ≥3 headline
  figures. Reconcile the **two notes' discrepancies** (calib split run 61 vs 64; stave spacing
  2 cm vs 4 cm). Record sha256 of every archive + ROOT file in `DATA.md`; mirror to LUNARC.
- **Deliverable:** `scripts/01_build_pulse_table_from_root.py`, a `configs/` cut definition,
  a reproduction report with a count-match table, checksums.

### S01 — Amplitude-adaptive template & q_template on the full dataset  [C]  (dep: S00)
- **Reproduce/Complete:** build s_i(j;A) per stave/amplitude bin from pooled calibration;
  evaluate **q_template for every selected pulse** (the notes never did this on the full set).
- **Traditional vs ML:** template = median-combine (traditional). ML cross-check = a small
  autoencoder/PCA basis of pulse shapes; compare reconstruction residuals.
- **Deliverable:** template library, per-pulse q_template column, distributions per stave/sample.

---

## Phase 1 — Atomic understanding

### S02 — Timing pickoff: CFD vs OF vs template  [L]  (dep: S00)
- **Atomic steps:** scan CFD fraction (10–50%), OF fit window, template-phase fit.
- **Traditional:** CFD20, CFD@best-fraction, leading-edge, OF, full-template fit — all on the
  *same* pulses.
- **ML:** a regressor (then S08 CNN) predicting sub-sample time from the waveform.
- **Benchmark:** single-stave timing resolution (from same-particle residuals) per method, with
  CIs. Question answered: *which pickoff is actually best, and does ML beat OF?*

### S03 — Timewalk correction: closure & held-out-run  [L]  (dep: S00, S02)
- **Reproduce:** the analytic f_i(A,x) timewalk; show before/after residual-vs-amplitude flatness.
- **Atomic:** held-out-run closure test; per-feature ablation of x_i.
- **Traditional vs ML:** analytic/polynomial timewalk **vs** the App. A.4 ridge residual
  correction (with α scanned, CV). Benchmark on held-out runs by residual RMS + bias-vs-amplitude.

### S04 — Same-particle timing resolution  [L]  (dep: S00, S03)
- **Reproduce:** per-stave σ (Table 19: B6≈0.68–0.75 ns, …), combined σ_comb≈0.54 ns (Table 40);
  reconcile vs the older v41 note.
- **Atomic / rigour:** report **narrow-core σ, robust width, AND full RMS** together; supply the
  missing **χ²/ndf**; tail fractions; bootstrap CIs.
- **Both methods:** variance-decomposition (traditional) vs an ML per-event resolution estimate;
  benchmark calibration of the predicted σ (pull distribution should be unit-width).

### S05 — Stave-error independence & two-ended projection  [L]  (dep: S04)
- **Atomic:** test σ_ij²=σ_i²+σ_j² independence assumption (look for correlated clock/electronics
  via cross-correlations); decompose correlated vs uncorrelated timing components.
- **Deliverable:** a defensible two-ended √2 projection with the correlated fraction quantified.

### S06 — Resolution vs amplitude/energy + absolute time scale  [L]  (dep: S04)
- **Atomic:** σ(A) per stave; map onto reconstructed energy (needs S14 for MeV).
- **Both methods:** parametric σ(A) fit (traditional) vs ML σ-prediction; validate the absolute
  TOF/time scale against an independent handle.

### S07 — ML rigour pass (cross-cutting)  [L]  (dep: S00; applies to A.2, A.4, B, H, I)
- **Atomic:** add probability **calibration** (isotonic/logistic) + reliability diagrams;
  **scan all hyperparameters** with CV; report PR curves + bootstrap CIs for imbalanced classes;
  build the **fair traditional baseline** (cuts on Δt_B / q_template / D_t) for every classifier.
- **Deliverable:** a "ML-vs-baseline scoreboard" table reused by S03/S08/S09/S11/S12/S13.

### S10 — Pile-up rate model & current-dependent excess  [L]  (dep: S00)
- **Reproduce:** occupancy model, R_max≈4.2 MHz (Table 47); current ratio 1.29; 9.2% excess.
- **Atomic:** test the **τ_eff=90 ns** assumption against a measured shaping/live time; isolate
  the genuine beam-pile-up component from the current-independent baseline rigorously.
- **Both methods:** analytic Poisson model (traditional) vs ML pile-up score scaling.

### S11 — Pile-up recovery: constrained two-pulse fit vs ML  [L→C]  (dep: S01, S02)
- **Build the missing traditional method:** the constrained **two-pulse template fit** (App. B.5
  recommendation, never implemented).
- **ML:** App. B injection-trained recovery (and later S08 CNN).
- **Benchmark:** on injected pile-up, recovered-time RMS and charge bias vs true, as a function
  of pulse separation and amplitude ratio. *When is ML worth it over the fit?*

### S12 — Timing-control-region classifier rigour  [L]  (dep: S07)
- **Reproduce:** App. I (D_t<3 ns vs D_t>50 ns; AUC 0.958 / AP 0.614).
- **Atomic:** **bootstrap** the 72-event positive class; quantify label self-referentiality;
  cross-check with the independent curvature C_t/σ_C.
- **Both methods:** a plain **D_t cut** (traditional) vs the shape-only RF; benchmark tail
  rejection at fixed efficiency.

### S13 — Current-scaling & weak supervision (CWoLa)  [L]  (dep: S07, S10)
- **Reproduce:** App. H weak current classifier (AUC 0.676), run-transfer folds.
- **Both methods:** the raw multi-stave/downstream-fraction current comparison (1.56% vs 2.68%)
  and f(I)=f₀+kI fit (traditional) **vs** the CWoLa classifier. Does ML add information beyond
  the simple rate comparison?

### S18 — A-stack independent reproduction (Sample III/IV)  [L]  (dep: S00)
- **Reproduce:** A1–A3 residual robust width 1.43 ns / core σ 1.41 ns (Tables 25–26); a smaller,
  cleaner warm-up for the atomic-reproduction methodology. Cross-check the B-stack timing scale.

---

## Phase 2 — Extension (beyond the notes)

### S08 — Waveform-level deep model (1D CNN/autoencoder)  [G]  (dep: S02, S11)
- Train a 1-D CNN for sub-sample time + pile-up/dropout flags directly from the 18-sample
  waveform; autoencoder for denoising/recovery (cf. NEDA/HPGe literature).
- **Benchmark:** vs OF/template timing (S02) and vs the two-pulse fit (S11). LUNARC GPU.

### S09 — Event-level GNN over the 4-stave graph  [G]  (dep: S04, S07)
- Graph = {B2,B4,B6,B8} nodes with pulse features + edges; predict clean-timing probability and
  a calibrated event time + per-event σ.
- **Benchmark:** vs the RF clean-timing classifier (App. A) and the inverse-variance combined
  time (S04). This is the natural home for the user's "basic ML ideas" — make them rigorous.

### S14 — Energy calibration (PSTAR/GEANT4 + Birks)  [C]  (dep: S00)
- Replace the 2-parameter power-law range model with **PSTAR/GEANT4** range-energy; model
  **Birks quenching**; propagate systematics. Enables MeV-scale σ(E) in S06.

### S15 — Event-by-event ΔE–E particle ID (p vs d)  [L]  (dep: S14)
- **Traditional:** ΔE–E band cuts / penetration-depth logic.
- **ML:** classifier on the amplitude vector + shape. **Benchmark** purity/efficiency — and
  honestly assess that there is **no truth label** without S17.

### S16 — Pedestal/baseline validation  [L]  (dep: S00)
- Validate the adaptive positivity-constrained pedestal against an **independent** pedestal
  estimate (forced-trigger / pre-trigger samples / empty waveforms). The "0% below tolerance"
  is true by construction and is **not** a validation — provide a real one.

### S17 — GEANT4 simulation of the CCB setup (stretch)  [C/G]  (dep: S00, S14)
- Build a GEANT4 model of target + stacks to generate **truth-labelled** waveforms. This is the
  only route to validate every data-driven/weak-label method against ground truth, and to turn
  "proxies" into calibrated probabilities. Large effort; leverages the user's existing Geant4
  repos.

---

## ML Pulse-Characterisation Program (P-series)

A dedicated, comprehensive programme to characterise the pulse **with ML, each benchmarked
against a strong traditional method** (the governing rules still apply: reproduce-first where a
report number exists, both methods, atomic, falsification, provenance). Inputs are the 18-sample
waveforms (~640k pulses, 4 B-staves, no MC truth). Most models are tiny (18-dim input) and run
on the **laptop GPU**; only the largest sweeps need LUNARC. All depend on S00; representation
work depends on S01.

### P01 — Self-supervised waveform representation  [L/G]  (dep: S00)
Pretrain on ALL ~640k waveforms with **masked-sample modelling** (predict held-out samples) and
a **denoising autoencoder/VAE** → a learned latent embedding of pulse shape. *Traditional
baseline:* PCA / the hand-crafted shape vector (tail, late, area/peak, plateau, q_template).
*Benchmark:* downstream usefulness (linear-probe on P03/P05 tasks) and reconstruction error.
This embedding feeds P02–P08.

### P02 — Unsupervised pulse-type discovery  [L]  (dep: P01)
Cluster the latent space (HDBSCAN/GMM) to discover pulse classes (clean / late / overlap /
dropout / saturated / glitch) **without labels**. *Traditional:* cuts on shape variables.
*Benchmark:* cluster purity vs the data-driven topology labels (Δt_B classes, D_t, jagged flag);
do the clusters recover known physics and surface anything new?

### P03 — Deep timing regression + per-pulse uncertainty  [L/G]  (dep: S02)
1-D CNN (and a small transformer) predicting sub-sample time **and a calibrated σ** from the
waveform. *Traditional:* CFD/OF/template (S02). *Benchmark:* single-stave resolution from
same-particle residuals, and pull-width of the predicted σ. Extends/realises S08.

### P04 — Amplitude / deposited-charge regression  [L]  (dep: S00)
ML estimate of true amplitude/charge from the waveform, robust to shape change. *Traditional:*
peak / integral / template-fit amplitude. *Benchmark:* resolution & bias vs amplitude, esp. the
non-linear high-amplitude B2 regime.

### P05 — Pile-up detection & two-pulse decomposition (deep)  [L/G]  (dep: S11, P01)
CNN classifier (pile-up vs clean) **and** a decomposition head predicting the two constituent
pulses' (t, A). *Traditional:* the constrained two-pulse template fit (S11) and the injection
classifiers (App. B). *Benchmark on injected pile-up:* recovered-time RMS and charge bias vs
separation & amplitude ratio — *when does deep decomposition beat the fit?* Core user interest.

### P06 — Dropout / jagged detection & recovery  [L]  (dep: P01)
CNN to flag dropout/jagged pulses and reconstruct the intact waveform (autoencoder inpainting).
*Traditional:* the rule-based jagged mask (§3) + interpolation. *Benchmark:* recovered timing on
injected dropouts, split by leading-edge-preserved vs destroyed (honest "unrecoverable" class).

### P07 — Saturation recovery for high-amplitude B2  [L]  (dep: S01)
~30–40% of Sample-I B2 pulses exceed 7000 ADC. Reconstruct true amplitude from the unsaturated
rising edge. *Traditional:* template/rising-edge extrapolation. *ML:* regression from the
unsaturated samples. *Benchmark:* on pulses artificially clipped from clean ones.

### P08 — Pulse-shape discrimination for particle ID (p vs d)  [L/G]  (dep: S15, P01)
Different dE/dx (proton vs deuteron) → different ionisation quenching → different pulse shape.
Test whether the **waveform alone** carries PID information. *Traditional:* charge-comparison PSD
(tail/total), ΔE–E band cuts. *ML:* classifier on the waveform/latent. *Benchmark:* purity vs
efficiency — and be explicit there is **no truth label** without S17 (GEANT4).

### P09 — Anomaly / glitch detection  [L]  (dep: P01)
Autoencoder reconstruction-error and isolation-forest to surface rare/pathological pulses
(electronics glitches, double-peaks, baseline excursions) for inspection. *Traditional:* outlier
cuts on shape vars. *Benchmark:* flagged-set precision by manual/curated review.

### P10 — Conditional generative pulse templates  [L]  (dep: S01)
Learn the amplitude-adaptive template family with a conditional model (cVAE/normalising flow over
log A, stave). *Traditional:* the median-combine amplitude-binned template (S01). *Benchmark:*
template-match quality q_template and timing-fit residuals using learned vs empirical templates.

### P11 — Learned baseline/pedestal estimation  [L]  (dep: S16)
ML pedestal from pre-trigger samples vs the adaptive positivity-constrained pedestal (S16).
*Benchmark:* against an independent forced-trigger pedestal sample; bias on low-amplitude pulses.

> All P-series outputs feed the event-level GNN (S09) and the timing/pile-up results (S04/S10–13).
> P-series models are small; default to the **laptop GPU**, escalate only P01/P03/P05/P08 sweeps
> to LUNARC. Data is **read-only** at `./data` for every one of these.

---

## Dependency sketch

```
S00 ─┬─ S01 ─ S11 ─ S08
     ├─ S02 ─ S03 ─ S04 ─┬─ S05
     │                   ├─ S06 ── (S14)
     │                   └─ S09
     ├─ S07 ─┬─ S12
     │       └─ S13
     ├─ S10 ─ S13
     ├─ S18
     ├─ S16
     └─ S14 ─ S15 ─ (S17)
```

## Ticket cutting
Phase 0 (S00, S01) ships first and is the **gate**. Each study may split into atomic sub-tickets
(e.g. S04a reproduce counts, S04b χ²/full-RMS, S04c bootstrap CIs). Keep tickets small enough to
finish in one agent session. The orchestrator (Claude) maintains this file as the single source
of truth and synthesises `reports/` into a rolling summary.

## Newly cut atomic directions (2026-06-09)

The latest reports deepen the pulse programme but also narrow the next questions. S02/S07 found
ML gains for timing residual correction and current/topology classification, but S00b turns
selector/baseline semantics into a measurable systematic and S02b/S03a now show that analytic or
template timewalk closure must be tested across leave-one-run-out splits before adopting a ridge
correction. S07b proves the D_t timing-control labels are self-referential; S07c shows shape RF can
beat q_template-only on weak clean-timing labels, but the historical App.A table must be recovered
or retired before that label family is trusted. S10 and S18 show strong traditional baselines still
win or tie when the physics control is tight; S16 shows the baseline estimator is much better than
a naive pretrigger median but still biased; P01 shows representation learning needs
leakage-controlled downstream value beyond reconstruction; P04 is a strong duplicate-readout
amplitude/charge closure, not an absolute energy calibration; P10a says conditional templates need
explicit timewalk terms before their timing gain can be trusted. P02/P07 expose high-value
pulse-shape and saturation follow-ups.

Live queue decision: `tn-ticket list --project testbeam` reports `open=29 claimed=3 done=22
failed=7`, so no new tickets were appended in this cycle. The exact legacy positional command
`tn-ticket list testbeam` reports the default queue (`open=4 claimed=0 done=0 failed=6`) because
the shim does not treat the positional argument as a project; for testbeam steering, use
`--project testbeam`.

Latest integration note: S10b reproduced the S10 `R_max=4.222 MHz` assumption but measured a
template-tail live10 window of 124.79 ns (95% CI [123.33,126.36]), with a leakage-audited ridge
cross-check at 123.19 ns. The 90 ns value must therefore be treated as an occupancy assumption,
not as the measured waveform live-time; S10c/S10d should now test threshold stability and
two-pulse resolvability rather than repeat the same tail fit. The S16b closure report found that
the best traditional early-sample predictor (MAE 169.34 ADC) still beats the ridge closure
estimator within CIs, while the forced-trigger validation report found zero true forced/random
tagged entries and only a quiet-event proxy where ML reaches MAE 15.64 ADC. Baseline work should
now split into true no-pulse data acquisition/search and timing-tail propagation of pre-trigger
activity proxies; another proxy-only pedestal benchmark is lower value.

Ready queue additions:

- **P02b — Cluster topology stability across runs and staves.** Test whether P02 pulse clusters
  are stable morphologies or run/stave artifacts. Traditional: shape cuts + PCA/GMM. ML: AE
  latent HDBSCAN/GMM. Metric: held-out AMI and topology purity with paired bootstrap CIs.
- **P03a — 18-sample CNN timing versus S02 ridge-corrected CFD.** Freeze the S02 best baseline
  and test whether waveform-deep timing adds information. Traditional: S02 CFD/template plus
  residual correction. ML: tiny 1D CNN/MLP with calibrated per-pulse σ. Metric: pairwise sigma68,
  full RMS, and pull width with paired bootstrap CIs.
- **P07b — Natural B2 saturation recovery impact on charge and timing tails.** Transfer the P07
  artificial-clipping result to real saturated B2 pulses. Traditional: rising-edge/template
  extrapolation. ML: P07 regressor. Metric: fractional amplitude bias/res68 plus q_template and
  timing-tail shifts with run-stratified bootstrap CIs.
- **S10c — Pile-up excess stratified by amplitude, baseline, and pulse topology.** Decide whether
  the S10 high-current excess is beam pile-up or a detector-pathology subpopulation. Traditional:
  Poisson/downstream excess in matched strata. ML: calibrated pile-up/current scores in the same
  strata. Metric: high-minus-low excess and score deltas with stratified bootstrap CIs.
- **S10d — Two-pulse template resolvability live-time from raw pulses.** Convert S10b's measured
  tail window into an operational pile-up separability threshold. Traditional: constrained
  two-pulse template fits over injected separations and amplitude ratios. ML: calibrated
  pile-up/recovery score on the same injections. Metric: minimum resolvable separation, recovered
  charge bias, and time RMS with run-held-out bootstrap CIs.
- **S16d — Dropout and baseline-excursion recovery stress test.** Separate recoverable baseline
  failures from veto-only pulse classes. Traditional: S16 baseline diagnostics, jagged/dropout
  masks, interpolation. ML: denoising/inpainting regressor plus unrecoverable classifier. Metric:
  detection AP, waveform MSE, and S02 timing residual recovery with bootstrap CIs.
- **S16e — Pre-trigger activity proxy in timing residual tails.** Test whether early waveform
  contamination explains the long timing tails seen by S02/S03/S04. Traditional: add fixed
  pre-trigger/baseline-lowering nuisance terms to the analytic timewalk model. ML: leakage-audited
  residual model using only pre-trigger summaries and pulse-shape diagnostics. Metric: sigma68,
  full RMS, and high-quantile tail reduction with paired run-block bootstrap CIs.
- **S11a — Constrained two-pulse template-fit injection benchmark.** Build the missing strong
  pile-up recovery baseline before deep decomposition. Traditional: bounded two-pulse S01 template
  fit with S02 timing initialisation. ML: compact injection-trained overlap regressor/classifier.
  Metric: recovered-time RMS, charge bias/res68, detection AP, and failure rate versus separation
  and amplitude ratio with paired bootstrap CIs.
- **P01c — Per-sample pulse-shape importance map.** Identify which of the 18 samples carry
  independent shape, timing, amplitude, saturation, and baseline information after stave/amplitude
  controls. Traditional: template/PCA leave-one-sample ablations. ML: masked-AE occlusion and
  latent-probe importance. Metric: per-sample deltas in reconstruction MSE, timing sigma68,
  amplitude res68, and topology-probe balanced accuracy with paired bootstrap CIs.
- **P09a — Rare waveform anomaly taxonomy and precision audit.** Surface rare waveform classes
  before they contaminate timing, charge, PID, or energy studies. Traditional: robust outlier cuts
  on q_template, peak sample, late fraction, baseline residual, saturation count, and timing span.
  ML: AE/PCA latent density and reconstruction-error models. Metric: top-k curated precision,
  timing-tail/saturation/dropout enrichment, and run/stave duplicate-rate with bootstrap CIs.
