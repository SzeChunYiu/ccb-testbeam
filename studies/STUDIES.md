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
selector/baseline semantics into a measurable systematic. S02b/S02c/S03c now show that analytic
timewalk closure is stable across Sample-II leave-one-run-out splits, while per-run drift and
monotonic binned variants do not improve the strong traditional baseline. S07b/S07e prove the D_t
timing-control labels are self-referential; S07c remains useful only as a weak-label screen until
the historical App.A table is recovered or retired. S10 and S18 show strong traditional baselines
still win or tie when the physics control is tight; S16 shows the baseline estimator is much
better than a naive pretrigger median but still biased. P09a adds rare early-pretrigger,
baseline-excursion, delayed-peak, and broad-mismatch taxa that must now be propagated into timing,
pile-up, charge, PID, and energy studies. P04/P04c are strong duplicate-readout amplitude/charge
closures, but P04b shows that transfer to an external charge-energy proxy is much weaker. P10b
shows explicit timewalk terms beat the conditional template, so learned templates need
physics-aware phase structure before adoption.

Live queue decision: the exact requested command `tn-ticket list testbeam` now reports
`open=6 claimed=0 done=0 failed=6`, which is below the 18-ready floor because the shim treats
`testbeam` as a positional default-queue argument. The required append path was still honoured
with `--project testbeam`: project-aware `tn-ticket list --project testbeam` now reports
`open=70 claimed=4 done=50 failed=9` after this pass appended five more non-duplicate ready
tickets under `project:testbeam`: P05b failure-aware two-pulse abstention calibration, S16g
quiet-run pseudo-pedestal calibration, S00d dynamic-selector pulse taxonomy audit, P09c
delayed-peak dropout propagation audit, and S14c saturation-corrected charge proxy energy
ordering. The discrepancy is a shim/argument parsing issue, not a scientific queue shortage.

Latest integration note: S10b reproduced the S10 `R_max=4.222 MHz` assumption but measured a
template-tail live10 window of 124.79 ns (95% CI [123.33,126.36]), with a leakage-audited ridge
cross-check at 123.19 ns. The 90 ns value must therefore be treated as an occupancy assumption,
not as the measured waveform live-time; S10c confirms the threshold dependence, and S10d shows
ML can improve two-pulse injected time RMS and resolvable delay only while increasing failure
rate, so P05b must make recovery risk explicit. S16d found no true forced/random pedestal source
in the current mirror; S16g should therefore calibrate quiet-run pseudo-pedestals as diagnostics,
not as truth. S16e improved S02b timing closure with pre-trigger proxies, but the tail CIs still
require leave-one-run-out veto validation before adoption. S02c shows selector semantics can move
timing closure, while S03b q_template-only weak labels need pair-residual validation. P03a
reproduced the frozen S02 ridge
baseline at sigma68 1.846 ns, but the best analytic amp-only timewalk reached 1.495 ns while the
tiny heteroskedastic MLP was 1.927 ns; P03b/P03c should separate waveform-only instability from
wrong-target training. S18b found the leave-one-run-out traditional A-stack width at 1.471 ns and
the ridge residual correction worse at 1.935 ns. S16c found RF nuisance correction reduces tails
diagnostically but high adaptive-lowering events do not explain the held-out S02 timing tails.
S11a now provides the missing constrained two-pulse benchmark and shows ML can improve injected
overlap time RMS while increasing failure rate, so the next pile-up step must optimize recovery
and abstention together. P07b transfers saturation recovery to natural B2 pulses and improves a
timing-tail proxy, but the q_template shift demands sample-level ablations and boundary controls
before adoption. S10c shows the current excess is heterogeneous after amplitude/baseline/topology
matching, making charge-energy proxy transfer the next rate-model test. P01a/P01b/P02b show
representation artifacts are useful only under strict leakage sentinels; P02b finds small,
target-specific cluster stability gains rather than a universal morphology win. S05a finds no
secure A-stack external-control reduction, keeping B-stack covariance modeling as the safer path.
S03b now shows per-stave monotonic amplitude-binned timewalk is worse than the S03a amp-only
baseline on the held-out run, so timing work should move to physically signed priors and
multi-run stability rather than finer unconstrained binning. P01c completes the sample-importance
map: samples 3-5 dominate traditional timing sensitivity and sample 5 is the top combined
importance point, giving P07e and P03c a concrete sample-window prior. S02c confirms run-drift
terms are not the missing timewalk ingredient, while S03c confirms analytic closure stability
across Sample-II runs. S07e repeats the App.I lesson in the all-three-downstream subset:
curvature-only traditional labeling is effectively perfect, so shape RFs must move to independent
targets. P04b/P04c split the charge story into a very strong duplicate-readout ML closure and a
much weaker external charge-energy transfer. P09a turns anomaly detection into a usable taxonomy,
making anomaly propagation the next atomic bridge across timing, charge, pile-up, baseline, and
PID. Saturation recovery now has enough P04/P07/S14 context for S14c to test energy ordering
before any GEANT4 truth claim.

Completed since last steering cycle:

- **P03a — 18-sample CNN timing versus S02 ridge-corrected CFD.** Result: the waveform MLP loses
  to both frozen S02 ridge and analytic timewalk; keep P03b/P03c focused on run stability,
  waveform-only leakage audits, CNN-vs-MLP architecture, and analytic residual targets.
- **S18b — Quantify Sample IV A-stack timing broadening.** Result: broadening is consistent with
  low-statistics/calibration-definition sensitivity; next A-stack work should probe calibration
  pools, robust core fits, and B-stack covariance transfer.
- **S16c — Pedestal-lowering nuisance propagation into timing residuals.** Result: adaptive
  lowering is a weak diagnostic, not the primary timing-tail mechanism; next baseline work should
  test Sample-I propagation, true forced/random sources, and full timing-tail tables.
- **P01a/P01b — Controlled waveform probes and reusable embedding artifact.** Result: topology
  sentinels dominate naive probe targets; the all-data embedding is released as a usable artifact
  but carries no benchmark claim after refitting on all selected rows.
- **P02b — Cluster topology stability across runs and staves.** Result: AE clusters give only a
  small q_template-bin AMI gain and do not broadly beat hand/PCA morphology, so downstream uses
  must stay target-specific and leakage-audited.
- **P07b — Natural B2 saturation recovery impact on charge and timing tails.** Result: artificial
  clipping remains a strong ML win, while natural saturated pulses need boundary and sample-window
  audits before recovered charge can feed energy/PID.
- **S10c/S11a/S05a — Stratified pile-up, two-pulse injection recovery, and A-stack controls.**
  Result: pile-up excess is heterogeneous after matching; ML improves S11a injected time RMS but
  raises failure rate; A-stack controls do not provide a secure B-stack covariance gain.
- **S03b/P01c — Monotonic amplitude-binned timewalk and per-sample pulse importance.** Result:
  monotonic binned timewalk does not improve on S03a amp-only, while the sample map localises
  timing/saturation leverage to the early peak window, especially samples 3-6.
- **S02c/S03c — Drift nuisance and multi-run timewalk stability.** Result: explicit analytic
  timewalk is stable across Sample-II leave-one-run-out splits; drift and binned variants should
  be treated as diagnostics unless they beat the analytic baseline with paired CIs.
- **S07e — All-three-downstream curvature-only timing-control audit.** Result: the traditional
  curvature/D_t target reaches AUC 1.000 while shape RF is lower, so future control classifiers
  need independent, non-D_t labels.
- **P04b/P04c/P10b/P09a — Charge, template phase, and anomaly updates.** Result: duplicate
  readout remains an ML-friendly closure but external charge-energy transfer is weaker; explicit
  timewalk beats conditional template timing; rare waveform taxonomy is ready for propagation
  studies rather than adoption claims.
- **S02c/S03b/S10c/S10d/S16d/S16e — Newest selector, timing-tail, pile-up, and pedestal reports.**
  Result: dynamic-selector semantics shift timing closure; q_template weak labels improve with ML
  but need pair-residual proof; live-time thresholds remain above 90 ns; ML two-pulse recovery
  needs abstention because failures rise; no true forced/random pedestal source is present; and
  pre-trigger proxies improve timing closure without settling tail causality.

Active ready queue highlights:

- **P03b — Leave-one-run-out waveform MLP timing stability.** Test whether the P03a failure is a
  run-transfer problem or a waveform-only information limit. Traditional: frozen S02/analytic
  timewalk per held-out run. ML: same 18-sample MLP with identical leakage guard. Metric: sigma68,
  full RMS, pull width, and run-to-run spread with paired bootstrap CIs.
- **P03c — CNN versus MLP timing with analytic residual targets.** Test whether a slightly richer
  waveform model can learn only the residual left by analytic timewalk. Traditional: analytic
  amp-only/timewalk closure. ML: compact 1D CNN and MLP residual correctors. Metric: residual
  sigma68, full RMS, calibration pull width, and paired delta CIs.
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
- **P09a — Rare waveform anomaly taxonomy and precision audit.** Surface rare waveform classes
  before they contaminate timing, charge, PID, or energy studies. Traditional: robust outlier cuts
  on q_template, peak sample, late fraction, baseline residual, saturation count, and timing span.
  ML: AE/PCA latent density and reconstruction-error models. Metric: top-k curated precision,
  timing-tail/saturation/dropout enrichment, and run/stave duplicate-rate with bootstrap CIs.
- **P05a — CNN two-pulse decomposition against S11a injections.** Test whether a compact waveform
  CNN can keep S11a's ML time-RMS gain while reducing the failure-rate regression. Traditional:
  frozen bounded S01 two-pulse fit. ML: CNN detection plus two-pulse time/amplitude heads. Metric:
  constituent time RMS, charge bias/res68, detection AP, and failure rate with paired bootstrap CIs.
- **P07e — Leading-edge sample ablation for saturation recovery.** Identify which unsaturated B2
  samples carry recoverable amplitude information. Traditional: rising-edge/template ablations.
  ML: P07 regressor and masked-sample MLP under identical masks. Metric: amplitude res68/bias,
  q_template shift, and timing-tail fraction with paired bootstrap CIs.
- **S10e — Pile-up excess transfer to charge-energy proxies.** Replace binary downstream occupancy
  with P04/P07 charge-energy proxy strata. Traditional: matched-stratum downstream and charge
  excess. ML: pile-up/current plus charge-residual scores. Metric: high-minus-low excess, median
  charge-proxy shift, score deltas, and stratum heterogeneity with stratified bootstrap CIs.
- **S14b — Range-energy calibration preflight from P04 closure.** Restart energy calibration as a
  minimal audit of table lookup, geometry assumptions, and charge-proxy uncertainty. Traditional:
  PSTAR/range interpolation with geometry variants. ML: monotonic gradient-boosted surrogate.
  Metric: depth-ordering violations, residual res68, geometry envelope, and ML delta CIs.
- **P04f — Baseline-excursion charge-bias closure.** Test whether P09a baseline-excursion and
  early-pretrigger taxa explain P04/P04c amplitude or charge bias. Traditional: frozen peak,
  integral, adaptive-template, and robust baseline-corrected estimators in matched strata. ML:
  leave-one-run-out charge residual model using waveform, P09a scores, and S16 summaries. Metric:
  bias, res68, full RMS, high-bias tail fraction, and paired delta CIs.
- **S10f — Anomaly-stratified pile-up excess closure.** Test whether the S10c current excess is
  concentrated in delayed-peak, broad-mismatch, baseline-excursion, or early-pretrigger waveform
  taxa. Traditional: matched Poisson/downstream excess by P09a stratum. ML: calibrated
  pile-up/current score with taxonomy and latent-distance terms under leakage guards. Metric:
  high-minus-low excess, topology odds ratio, score delta, and stratum heterogeneity with CIs.
- **P08a — Penetration-depth weak-label PID null test.** Before S14/S15 truth labels exist, test
  whether waveform shape adds stable PID-like information beyond charge, penetration depth, and
  run/stave proxies. Traditional: tail/total, area/peak, q_template, and DeltaE-like cuts. ML:
  P01/P01b latent and raw-waveform classifier with leakage sentinels. Metric: weak-label AUC/AP,
  calibration error, purity at fixed efficiency, leakage deltas, and paired CIs; no PID adoption
  claim is allowed.
- **P05b — Failure-aware two-pulse abstention calibration.** Turn S10d/S11a's ML time-RMS gain
  into an operational recovery rule by calibrating when to abstain. Traditional: bounded two-pulse
  fit quality cuts from chi2/ndf, covariance, separation, amplitude ratio, and residual shape. ML:
  conformal/isotonic failure probabilities for the same recovery outputs. Metric: accepted-event
  time RMS, charge bias/res68, abstention rate, bad-recovery rate, and risk-coverage AUC with
  paired run-block bootstrap CIs.
- **S16g — Quiet-run pseudo-pedestal calibration.** Since no true forced/random pedestal source is
  present, test whether quiet beam-event strata can serve as calibrated pseudo-pedestals.
  Traditional: frozen quiet-run/event thresholds from pre-trigger summaries, event maxima, and
  adaptive-lowering diagnostics. ML: pre-trigger-only quiet-probability weighting. Metric:
  pedestal bias/MAE, low-amplitude charge bias, timing-tail delta, and calibration ECE with
  leave-one-run-out bootstrap CIs.
- **S00d — Dynamic-selector pulse taxonomy audit.** Classify the dynamic-range-only population
  from S00b/S02c into pulse-shape, baseline, saturation, timing, pile-up, and dropout classes.
  Traditional: frozen cuts on peak sample, early/late fraction, q_template, baseline excursion,
  saturation count, and timing span. ML: P01/P01b embeddings as morphology summaries under
  leakage guards. Metric: class fractions, enrichment odds ratios, timing and charge deltas, and
  AUC/AP with run-block bootstrap CIs.
- **P09c — Delayed-peak dropout propagation audit.** Decide whether P09a delayed-peak and
  broad-mismatch taxa should be recovered, corrected, downweighted, or vetoed. Traditional:
  robust-template anomaly cuts propagated into S02/S03 timing, P04/P07 charge, and S16 baseline
  tables. ML: AE/PCA reconstruction and latent-distance scores under held-out-run sentinels.
  Metric: timing-tail enrichment, charge-bias delta, baseline-excursion rate, pile-up-score delta,
  and recover/veto AP with stratified bootstrap CIs.
- **S14c — Saturation-corrected charge proxy energy ordering.** Test whether P07/P07b saturation
  recovery improves P04/P04b charge-proxy ordering before GEANT4 truth. Traditional: peak,
  integral, adaptive-template charge and PSTAR geometry-order constraints with exclusion or
  rising-edge correction. ML: frozen P07/P07b saturation regressor plus P04 duplicate-readout
  charge model without depth/PID labels as features. Metric: depth-ordering violations,
  unsaturated-control charge res68/bias, saturated-minus-unsaturated ordering delta, and geometry
  envelope with run/stave bootstrap CIs.
