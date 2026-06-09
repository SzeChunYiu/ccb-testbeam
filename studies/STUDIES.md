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
`open=11 claimed=0 done=0 failed=8`, which is below the 18-ready floor because the shim treats
`testbeam` as a positional default-queue argument. The required append path was still honoured
with `--project testbeam`: the project-aware testbeam queue remains deep, with live post-append
audits at 165 open and concurrent workers moving tickets, but the mission trigger still required a
small set of new ready studies. This pass appended four additional non-duplicate ready tickets
under `project:testbeam`: S10l asymmetric-template failure atom map
(`1781030650.532.4dd15543`), S03j selector-specific timewalk support map
(`1781030650.597.5d382001`), S16j pretrigger hidden-mode stability audit
(`1781030650.662.4bb162cb`), and P04l baseline-to-charge dropout coupling
(`1781030650.727.08857c2c`). The previous pass appended S03i q_template amplitude-matched
tail-label isolation (`1781029233.703.5ff5517d`), S10k operational Rmax failure-definition
frontier (`1781029239.771.51c16bca`), P04k selector-semantics charge-closure sensitivity
(`1781029246.839.554f50f7`), and S16i pretrigger-baseline live-time coupling audit
(`1781029251.907.5de90a17`). The pass before that appended S07k raw-HRDv App.A label-definition
sensitivity grid (`1781027683.937.4b432fbc`), S10h baseline-excursion pile-up excess
decomposition (`1781027683.951.7bcc2f09`), and S14e range-energy abstention support envelope
(`1781027683.1000.24e0133d`). The earlier pass appended P10h explicit-handle q-template
support map (`1781026226.557.2d8e79db`), P04j charge-transfer conformal uncertainty calibration
(`1781026226.572.6e7c10a0`), and S04d timing-tail pathology interaction audit
(`1781026226.608.7a105c91`). The prior pass appended S07i S07f score transfer from injected
corruption to real high-current strata (`1781024786.1471.167d1f38`), P04i duplicate-readout charge
closure sample-causality map (`1781024791.1539.3ba15c1d`), and S03h HGB timewalk gain support map
by amplitude and shape atoms (`1781024797.1607.4a1b6480`). The earlier pass appended P04h
A-stack charge-transfer support map by B-stack topology (`1781023326.470.61534f82`), S02h
binned-timewalk shuffled-target failure autopsy (`1781023333.541.66a8325e`), and P12a pulse-axis
covariance atom table across pathology flags (`1781023340.632.43377364`). The discrepancy is a
shim/argument parsing issue, not a scientific queue shortage.

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
tiny heteroskedastic MLP was 1.927 ns. P03b now shows the waveform MLP beats the weaker S02 ridge
baseline on 6/7 held-out Sample-II runs but not the analytic baseline, and P03c shows a tiny MLP
residual gain while the CNN matches the analytic result; P03f/P03g should therefore test
sample-window causality and negative controls before any waveform timing adoption. S18b found the
leave-one-run-out traditional A-stack width at 1.471 ns and the ridge residual correction worse at
1.935 ns; S18c/S18d now show the broadening is calibration-pool and core-estimator sensitive, so
S18g should transfer only robust widths into B-stack covariance. S16c found RF nuisance correction
reduces tails diagnostically but high adaptive-lowering events do not explain the held-out S02
timing tails; the newest Sample-I S16d result finds high-lowering events are tail-enriched
(0.130 vs 0.012) while lowering corrections barely move sigma68, motivating S16h's matched
pile-up/topology confound audit.
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
The newest P01b/P02c/P02d representation reports are a warning sign: P01b-downstream finds
sample-epoch separability in waveform probes, P02c says train-only AE embeddings do not beat
hand+PCA morphology on the guarded manual-flag target, and P02d's near-perfect RF timing-tail
score is largely downstream D_t label-source self-reference. P01f therefore asks whether waveform
latents can be domain-residualized before PID, timing, pile-up, or energy tasks consume them.
S05c reduces held-out B-stack residual width with ExtraTrees, but the covariance decomposition
remains B2/topology dominated; S05f now separates true common covariance from B2-local saturation,
topology, and anomaly confounds. The missing atomic bridge from pulse amplitude to timing is also
now explicit: P06a will tabulate timing resolution by amplitude, charge proxy, saturation,
peak-sample, and anomaly strata with both traditional and ML uncertainty estimates.
The latest S10d amplitude-stratified result replaces the binary downstream pile-up excess with a
matched two-pulse secondary-fraction diagnostic: the largest positive stratum is high-amplitude,
large-lowering, broad-late waveform topology. The latest S16d strata validation still finds zero
true forced/random entries and shows large adaptive lowering is predictable from pre-trigger
contamination/pathology rather than a clean pedestal-bias truth label. These two reports tighten
the P06a/S05f/S16h boundary: amplitude, pile-up, baseline lowering, and anomaly topology must be
matched together before timing, covariance, PID, or energy claims are adopted.
The newest P01c/P01e strict latent audits make the representation warning more concrete:
residual AE latents do not beat hand-shape/PCA under repeated leakage sentinels, and strict AE
timing sigma68 (1.965 ns) is indistinguishable from hand-shape (1.962 ns) while shuffled-target
controls remain too strong. P01d separates the sample-importance story into a CFD interpolation
artifact at sample 5 and a more robust sample-6 smoothing effect visible in template/OF timing.
P07c/P07d keep saturation correction promising on artificial and pseudo-saturation closures, but
boundary q_template shifts and a run-65 tail envelope make saturation-corrected timing and energy
claims veto-sensitive. P05a/S11b/S11c show that injected and real high-current two-pulse
candidates still concentrate the next pile-up question in high-amplitude, large-lowering,
broad-late strata; the ML methods improve time RMS, but only with explicit failure/abstention
accounting.
The newest S03d report moves timewalk from "analytic closure is stable" to a sharper question:
HGB improves LORO sigma68 to 1.394 ns versus 1.551 ns for amp-only and 1.645 ns for monotone
binned, with no immediate leakage flag, but the gain is not yet physically explained. S10e shows
the high-current downstream excess remains after P04/P07 charge-energy stratification
(0.00676/event with CIs excluding zero), while charge-residual ML is diagnostic rather than
physics-facing. P07e finds the best retained-window saturation recovery is still non-adoptable
(res68 0.0812, median bias 0.0292), so saturation use now needs calibrated accept/veto rules.
The freshest P04c A/B charge-transfer report makes the energy/PID risk more concrete: external
A-stack charge prediction stays broad and topology-limited, with B-charge ridge res68 0.519 and
waveform ExtraTrees res68 0.521, essentially at the shuffled-target sentinel. S02d/S02e now also
make the timing-template risk concrete: global no-drift timewalk is stable, current/rate drift
does not rescue binned branches, and binned selected branches can fail shuffled-target controls.
The latest anomaly-tail closure finds the ML high-risk cut can reduce timing tails only by removing
about 24% of pairs and shifting amplitude/pair composition, so pathology vetoes must be matched
and composition-stable.
The latest S07f/S07g reports refine the App.I story: the all-three shape RF is no longer only a
D_t-label mirror because it reaches AUC 0.822 on injected two-pulse truth versus 0.606 for the
traditional timing/template score, but curvature remains the ceiling on the original D_t label and
amplitude nuisance is visible. That pushes the next question to calibrated transfer from injected
truth into real high-current strata, not another D_t classifier. The latest P04d report repairs the
duplicate-readout direct-template pathology with a strong Huber traditional closure (res68 0.0203)
and an even stronger waveform ExtraTrees closure (res68 0.00270), but external A/B transfer remains
broad, so the charge programme now needs sample-causal ablations and support maps before feeding
PID or energy. The freshest P10c/P10d/P10e reports split template steering into support-limited
pieces: run-64-only Sample-II explicit calibration transfers better than pooled calibration,
external B2-B8 timing closure favors a traditional ridge explicit correction over waveform
ExtraTrees, and simple conditional templates still fail the q-space negative-control registry under
both family holdouts. Learned or handle-based templates should therefore be mapped by support
region and feature family before their q_template, live-time, saturation, PID, or energy outputs
are trusted.
The latest App.A archive provenance search finds no byte-identifiable 12,147-row source table:
raw HRDv CFD20 produces 9,897 labelled events, so the historical App.A weak label should be
retired unless a source table is recovered or bounded through a raw-HRDv definition grid. The
latest S10f anomaly-stratified closure shows the high-current downstream excess remains positive
after P09a taxonomy matching, but the largest rare-class excess is baseline_excursion; pile-up and
baseline contamination must now be decomposed in the same matched support. The P04b-propagated
S14b range-energy preflight reproduces S00 exactly but fails the 0.10 per-event energy threshold
once external charge uncertainty is included, so energy/PID work should use support and abstention
maps rather than global energy claims. The newest S00c selector-regression, S03d q_template-tail,
S03d pair-veto, and S10d/S10e live-time reports now define the next atomic bridge: isolate
q_template from amplitude nuisance, translate threshold-dependent live-time into failure-definition
frontiers, propagate selector semantics into charge closure, and test whether pretrigger baseline
spectra bias pile-up live-time handles. This pass extends that bridge to four smaller atoms:
asymmetric-template two-pulse failures, selector-specific timewalk support, pretrigger hidden-mode
stability, and baseline/dropout coupling into charge failure before energy or PID reuse.

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
- **S07f/S07g — Independent all-three App.I validation and stratification.** Result: the shape RF
  survives an injected non-D_t waveform-corruption target, but the original App.I label is still
  curvature-defined and amplitude/current strata must be calibrated before real pile-up claims.
- **P04d — Adaptive-template scale pathology.** Result: direct shifted-template scale variants
  remain poor, strong Huber calibration closes duplicate readout to res68 0.0203, and waveform ML
  reaches res68 0.00270; the result is duplicate-readout closure, not external energy truth.
- **S02c/S03b/S10c/S10d/S16d/S16e — Newest selector, timing-tail, pile-up, and pedestal reports.**
  Result: dynamic-selector semantics shift timing closure; q_template weak labels improve with ML
  but need pair-residual proof; live-time thresholds remain above 90 ns; ML two-pulse recovery
  needs abstention because failures rise; no true forced/random pedestal source is present; and
  pre-trigger proxies improve timing closure without settling tail causality.
- **P03b/P03c — Waveform timing residual stability and CNN-vs-MLP targets.** Result: waveform ML
  often improves over the S02 ridge comparator but does not beat the strong analytic timewalk
  baseline; CNN structure adds no clear advantage, so the next timing work is sample-window
  ablation and negative-control falsification.
- **S18c/S18d — A-stack calibration-pool and robust core-fit stability.** Result: Sample-IV
  broadening is highly estimator and calibration-pool sensitive; binned Gaussian core fits should
  not drive B-stack covariance conclusions without robust transfer checks.
- **S16e tagged-random and S16d Sample-I lowering.** Result: no true tagged random/forced B-stack
  pedestal entries are present, and Sample-I high-lowering events are tail-enriched despite weak
  correction gains; baseline studies must separate true pedestal bias from pile-up/topology and
  anomaly confounders.
- **P01b/P02c/P02d — Downstream waveform probes and guarded embedding consumers.** Result:
  waveform representations still carry sample-epoch, topology, and label-source signals; train-only
  AE embeddings do not beat hand+PCA morphology on the guarded manual-flag target, and D_t-tail
  RF gains remain self-referential unless independent timing labels are used.
- **S05c — Hierarchical B-stack run/stave covariance model.** Result: waveform ExtraTrees reduce
  held-out residual width relative to pair-median/hierarchical baselines, but the covariance
  decomposition remains B2/topology dominated; covariance work now needs matched B2-local confound
  separation before two-ended projections.
- **S10d amplitude and S16d strata — Pile-up amplitude meets adaptive lowering.** Result: the
  two-pulse secondary-fraction excess is concentrated in high-amplitude, large-lowering,
  broad-late strata, while large lowering is a pre-trigger contamination/pathology diagnostic and
  not a true forced/random pedestal validation. Future pile-up, baseline, and timing studies must
  match these axes jointly.
- **P01c/P01e/P07c/P07d/S11b/S11c — Latest strict latent, saturation, and two-pulse closures.**
  Result: waveform latents fail stricter timing/null controls; saturation recovery has useful
  artificial closure but boundary-dependent q_template and timing-tail shifts; and real
  high-current two-pulse diagnostics point to high-amplitude, large-lowering, broad-late strata
  where ML still needs failure-aware operation.
- **P01d/P05a — Post-rebase sample-importance and CNN two-pulse reports.** Result: sample 5's
  negative CFD delta is a pickoff artifact while sample 6 remains a robust smoothing point, and
  the compact CNN improves injected two-pulse RMS (10.01 ns vs 13.90 ns) but fails adoption
  because failure rate increases from 0.168 to 0.228.
- **S03d/S10e/P07e — Fresh timewalk, charge-stratified pile-up, and saturation-ablation reports.**
  Result: HGB timewalk residual correction now beats the analytic and monotone-binned LORO
  baselines but needs monotonicity/feature-causality and transfer falsification; the current
  excess survives charge-energy matching; and retained-window saturation recovery still needs an
  acceptance rule before timing, PID, or energy consumers can use it.

Active ready queue highlights:

- **P03d — Leave-one-heldout-run analytic-residual CNN versus MLP.** Repeat P03c across all
  Sample-II held-out runs to determine whether the small MLP residual gain is stable. Traditional:
  analytic amp-only/timewalk closure in each fold. ML: matched MLP and tiny CNN residual
  correctors. Metric: residual sigma68, full RMS, calibration pull width, and paired run-block
  bootstrap CIs.
- **P03e — Stave-blind versus stave-aware waveform residual ablation.** Test whether residual
  timing gains come from waveform shape or stave/run-family identity. Traditional: analytic
  timewalk with no residual learner. ML: waveform residual models with and without stave features
  and matched negative controls. Metric: held-out sigma68, full RMS, pull width, and feature-ablation
  deltas with bootstrap CIs.
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
- **P03f — Early-peak sample-window timing residual ablation.** Test whether samples 3-6 carry
  stable post-analytic timing information or only run-specific artifacts. Traditional: fixed
  early-peak template/CFD ablations after analytic timewalk. ML: matched MLP/CNN residual
  correctors under identical sample masks. Metric: held-out pairwise sigma68, full RMS, tail
  fraction, and ML-minus-traditional delta with event-paired run-block bootstrap CIs.
- **P03g — Waveform timing residual negative-control registry.** Falsify waveform timing gains
  against amplitude-only, phase-scrambled, sample-permuted, run-only, and shuffled-target controls.
  Traditional: frozen analytic timewalk. ML: P03c residual learners under true and negative-control
  features. Metric: per-run sigma68, full RMS, pull width, and true-control performance gap with
  paired bootstrap and leave-one-run CIs.
- **S16h — Matched lowering pile-up confound audit.** Separate adaptive-lowering pedestal effects
  from pile-up, topology, saturation, and anomaly confounders. Traditional: matched residual tables
  by run, pair, amplitude, peak sample, S10 proxies, P09 taxa, and saturation flags. ML:
  leakage-audited tail/residual predictor using lowering plus pile-up/anomaly/saturation summaries.
  Metric: tail odds ratio, sigma68/full-RMS deltas, pile-up-score enrichment, and calibration ECE
  with stratified run-block bootstrap CIs.
- **S18g — A-stack robust-width transfer to B-stack covariance.** Test whether robust A-stack
  timing widths can constrain B-stack correlated covariance without binned Gaussian low-stat
  artifacts. Traditional: hierarchical variance decomposition using Student-t, MAD/IQR, and
  trimmed-likelihood A-stack priors. ML: ridge/ExtraTrees covariance predictor using A-stack robust
  summaries under run-heldout guards. Metric: B-stack robust width, inferred correlated fraction,
  covariance-interval coverage, and ML-minus-traditional delta with paired bootstrap CIs.
- **P06a — Amplitude-binned timing resolution atom table.** Quantify timing resolution by
  amplitude, charge proxy, peak sample, saturation flag, and anomaly class after the strongest
  analytic timewalk closure. Traditional: frozen S02/S03 pickoff/timewalk with matched
  stratum-wise pair residual tables. ML: leakage-audited per-pulse uncertainty/residual model using
  waveform, latent, charge, and saturation summaries. Metric: sigma68, full RMS, pull width, tail
  fraction, and ML-minus-traditional deltas with event-paired run-block bootstrap CIs.
- **S05f — B2-local covariance confound matched audit.** Decide whether S05c's large B2 covariance
  component is a true common timing mode or a local confound from B2 saturation, amplitude,
  topology, and anomalies. Traditional: matched robust covariance tables within run, pair,
  amplitude, saturation, topology, and P09 strata. ML: residual/covariance predictor with and
  without B2-local features plus shuffled-run and downstream-only controls. Metric: B2-containing
  minus downstream covariance, correlated fraction, held-out width delta, and interval coverage
  with stratified run-block bootstrap CIs.
- **P01f — Domain-residualized waveform latent benchmark.** Test whether P01/P01b latents retain
  pulse-shape information after removing sample-epoch, run-family, topology, amplitude, and stave
  domain signals. Traditional: hand-shape/PCA residual features after nuisance regression. ML:
  adversarial or orthogonal nuisance-residualized AE latent compared with the frozen P01b latent and
  shuffled controls. Metric: nuisance AUC reduction at fixed physics-proxy retention, reconstruction
  MSE, and downstream target deltas with run-block bootstrap CIs.
- **S04c — Pathology-stratified timing-resolution tail table.** Freeze the strongest S02/S03
  analytic baseline and ask which atomic pathology axis explains the non-core timing tails:
  anomaly taxon, saturation boundary, lowering/pretrigger contamination, two-pulse score, dropout,
  or peak-sample phase. Traditional: matched same-particle residual tables and variance components.
  ML: calibrated per-event sigma/tail model using only waveform/pathology summaries. Metric:
  sigma68, full RMS, >5 ns tail fraction, pull width, and ML-minus-traditional deltas with
  event-paired run-block bootstrap CIs.
- **P04g — Dropout-injected amplitude charge recovery closure.** Inject controlled leading-edge,
  peak, and trailing-sample dropouts into clean pulses to test whether amplitude and charge
  estimates remain usable for P04/P07/S14. Traditional: peak, integral, adaptive-template,
  rising-edge, and interpolation estimators. ML: denoising/inpainting and direct charge residual
  models with held-out-run guards. Metric: amplitude/charge bias, res68, full RMS, catastrophic
  error rate, timing-tail propagation, and paired bootstrap CIs.
- **S14d — Anomaly-veto energy-ordering sensitivity.** Test whether P09 anomaly, S10 pile-up,
  S16 baseline-lowering, and P07 saturation-correction vetoes change S14/S15 pre-GEANT
  depth-ordering conclusions. Traditional: PSTAR/range-order preflight under a frozen veto ladder.
  ML: monotonic charge-energy surrogate using P04/P07 charge plus calibrated anomaly, pile-up, and
  baseline scores under leakage sentinels. Metric: depth-ordering violations, median charge-proxy
  shift, unsaturated-control res68, veto acceptance, and run/stave bootstrap CIs.
- **S03g — HGB timewalk feature monotonicity audit.** Explain whether the S03d HGB gain is
  physically meaningful residual structure or non-monotone/local overfit. Traditional: S03a
  amp-only analytic closure plus physically signed shared-stave shrinkage and monotone residual
  tables. ML: HGB residual corrector with amplitude-only, shape-only, stave-only, monotonic, and
  shuffled-target controls. Metric: sigma68, full RMS, >5 ns tail fraction, bias-vs-amplitude
  slope, and paired ML-minus-traditional bootstrap CIs.
- **P07g — Saturation recovery acceptance rule from bias envelope.** Convert P07e's non-adoptable
  retained-window recovery into a calibrated accept/veto rule. Traditional: rising-edge/template
  retained-window estimators with fixed bias-envelope cuts on saturation depth, peak sample,
  q_template shift, and odd-channel duplicate consistency. ML: conformal/isotonic error and
  tail-risk predictor for frozen P07/P07e regressors. Metric: accepted-event res68, bias,
  catastrophic error, q_template shift, timing-tail delta, calibration coverage, and acceptance
  rate with run-block bootstrap CIs.
- **P08b — Charge-current matched waveform PID leakage null.** Test whether PID-like waveform
  signals survive after matching charge, current, depth proxy, run, saturation, pile-up, topology,
  and stave. Traditional: tail/total, area/peak, q_template, penetration-depth, and DeltaE-like
  cuts within matched P04/P07/S10 strata. ML: raw waveform and P01/P01b latent classifiers with
  nuisance residualization and run-family sentinels. Metric: weak-label AUC/AP, purity at fixed
  efficiency, calibration ECE, nuisance AUC after residualization, and ML-minus-traditional
  bootstrap CIs; no PID adoption without S17 truth.
- **S06a — Charge-proxy timing-resolution monotonicity after S14b.** Test whether timing
  resolution is monotonic with charge/energy proxy once saturation, anomaly, peak-sample phase,
  pile-up, and baseline strata are matched. Traditional: frozen S02/S03 analytic timing residual
  tables binned by P04/P07 charge proxy and S14b depth-order proxy with matched controls. ML:
  leakage-audited per-pulse uncertainty/residual model using waveform, charge, saturation, and
  anomaly summaries. Metric: sigma68, full RMS, >5 ns tail fraction, pull width, charge-proxy
  monotonic slope, and ML-minus-traditional deltas with event-paired run-block bootstrap CIs.
- **P10f — Template tail-shape saturation and current transfer.** Decide whether post-peak tail
  constants and live-time handles transfer across amplitude, saturation boundary, and current
  strata. Traditional: train-run S01/P10 amplitude-binned template tail descriptors and live10
  tables. ML: conditional or monotonic tail-shape surrogate over log amplitude, stave, current,
  and saturation flags with shuffled/family-holdout controls. Metric: tail residual MSE, live10,
  q_template delta, two-pulse resolvability threshold, and ML-minus-traditional bootstrap CIs.
- **S13c — Charge-matched current weak-supervision null.** Establish whether CWoLa/current
  classifiers retain information after matching charge, topology, anomaly, baseline lowering,
  run family, and stave. Traditional: frozen matched-stratum current-excess and Poisson/downstream
  occupancy tables. ML: waveform/latent current classifier with nuisance residualization and
  run-family sentinels. Metric: high-minus-low excess, AUC/AP, calibration ECE, nuisance AUC after
  residualization, and stratified run-block bootstrap CIs.
- **P11a — Pretrigger baseline spectrum atom table.** Decompose pretrigger baseline spectra
  before baseline, dropout, pile-up, PID, or energy consumers use them. Traditional: frozen
  pretrigger mean, slope, RMS, max-excursion, asymmetry, and adaptive-lowering tables against
  timing, charge, anomaly, and pile-up outcomes. ML: pretrigger-only autoencoder or calibrated
  classifier/regressor under run-heldout folds. Metric: baseline-class fractions, timing-tail odds
  ratio, charge-bias delta, dropout/anomaly enrichment, calibration ECE, and bootstrap CIs.
- **P04h — A-stack charge-transfer support map by B-stack topology.** Decide where the P04c
  external A-stack charge proxy is identifiable rather than topology-limited. Traditional: frozen
  B2 log-linear, peak, integral, adaptive-template, and matched topology/support tables with
  leave-one-run-out rows. ML: calibrated ExtraTrees or quantile residual model using B-stack
  waveform and charge summaries only, with shuffled-target and topology-only sentinels. Metric:
  per-stratum bias, res68, full RMS, within-25pct rate, calibration coverage, and
  ML-minus-traditional delta using run-block bootstrap CIs.
- **S02h — Binned-timewalk shuffled-target failure autopsy.** Explain why selected
  amplitude-binned template timewalk branches fail shuffled-target controls while global timewalk
  stays stable and current/rate drift adds no gain. Traditional: frozen S02b global no-drift
  timewalk plus binned-template decomposition by bin occupancy, amplitude range, stave, run, and
  pair composition. ML: regularized residual learner with bin-dropout, shuffled-bin,
  shuffled-target, and current-covariate sentinels under identical leave-one-run-out folds. Metric:
  sigma68, full RMS, >5 ns tail fraction, bias-vs-amplitude slope, occupancy-weighted instability
  score, and ML-minus-traditional deltas with run-block bootstrap CIs.
- **P12a — Pulse-axis covariance atom table across pathology flags.** Measure which completed
  pulse-pathology axes move together before downstream timing, amplitude, saturation, pile-up,
  baseline, dropout, PID, or energy studies consume them. Traditional: matched contingency,
  odds-ratio, robust covariance, and partial-correlation tables using frozen
  S00/S02/S03/P04/P07/P09/S10/S16 outputs. ML: sparse graphical model or calibrated multi-label
  classifier with leave-one-run-out nuisance residualization and shuffled-axis sentinels. Metric:
  conditional odds ratios, partial correlations, mutual-information deltas, downstream sigma68 or
  charge-bias deltas, calibration ECE, and stratified run-block bootstrap CIs.
- **S07i — S07f score transfer from injected corruption to real high-current strata.** Calibrate
  the S07f shape-only waveform-corruption score, learned on injected two-pulse truth, against real
  high-current candidate strata matched on amplitude, baseline lowering, saturation, anomaly, and
  run family. Traditional: S10/S11 one-pulse-vs-two-pulse template scores, curvature/timing
  residuals, and matched high-minus-low excess tables. ML: frozen S07f RF with isotonic or
  conformal calibration plus shuffled-current and amplitude-only sentinels. Metric: calibration
  slope/intercept, score shift, candidate excess rate, template-fit agreement, Brier/ECE, and
  ML-minus-traditional deltas with run-block bootstrap CIs.
- **P04i — Duplicate-readout charge closure sample-causality map.** Identify which waveform
  samples drive P04/P04d duplicate-readout charge closure and whether the ML gain survives ablation
  of early-peak, post-peak tail, baseline, and saturation-boundary samples. Traditional: peak,
  integral, adaptive-template scale, and strong Huber charge calibrator under frozen sample-window
  ablations. ML: frozen ExtraTrees/HGB charge regressor with occlusion, permutation, grouped-window
  retraining, and shuffled-target/stave-only sentinels. Metric: fractional bias, res68, full RMS,
  within-10pct rate, sample-window performance delta, and paired run-block bootstrap CIs.
- **S03h — HGB timewalk gain support map by amplitude and shape atoms.** Locate where the S03d
  HGB residual gain over the signed analytic prior appears or fails across amplitude, stave,
  peak-sample, q_template, saturation-boundary, pretrigger, and anomaly strata. Traditional:
  frozen S03a amp-only, S03d signed inverse-amplitude prior, and heavy-tail analytic residual
  tables in matched strata. ML: S03d HGB residual corrector with feature-group ablations,
  stratum-specific calibration, monotonicity probes, and shuffled-target/run-family sentinels.
  Metric: support count, sigma68, full RMS, >5 ns tail fraction, bias-vs-amplitude slope,
  calibration coverage, and stratified run-block bootstrap CIs.
- **P10h — Explicit-handle q-template support map.** Decide where explicit same-pulse handles
  improve q_template or timing-transfer error beyond S01 empirical templates, and where they fail
  the family-holdout negative-control registry. Traditional: frozen S01 amplitude-bin templates
  plus train-only handle-binned median/residual tables with occupancy and fallback diagnostics.
  ML: frozen ridge/ExtraTrees explicit-handle template predictors with grouped feature knockouts,
  monotonic controls, shuffled-target sentinels, and family-label sentinels. Metric: per-stratum
  q_template MSE, live10/tail residual, timing-fit sigma68/full RMS, fallback rate, and
  ML-minus-traditional deltas with family-heldout run-block bootstrap CIs.
- **P04j — Charge-transfer conformal uncertainty calibration.** Turn broad external A/B
  charge-transfer point estimates into calibrated uncertainty and abstention regions before PID or
  energy consumers reuse them. Traditional: frozen peak, integral, adaptive-template, strong-Huber,
  and topology/support-stratified residual bands with train-run quantile intervals. ML: quantile
  ExtraTrees/HGB or conformal residual calibration using B-stack waveform/charge summaries only,
  with topology-only, shuffled-target, and run-family sentinels. Metric: interval coverage,
  interval width, bias, res68, full RMS, within-25pct rate, abstention rate, and
  ML-minus-traditional deltas with leave-one-run/family run-block bootstrap CIs.
- **S04d — Timing-tail pathology interaction audit.** Test whether non-core timing tails are
  additive in single pathology axes or driven by interactions among saturation boundary, pile-up
  score, baseline/pretrigger contamination, dropout/delayed peak, anomaly taxon, peak-sample phase,
  and charge proxy. Traditional: frozen S02/S03 analytic timing residuals with matched factorial
  residual tables, robust variance components, and pair/run composition preservation. ML:
  calibrated sparse interaction model or constrained tree tail-risk model using only frozen
  pathology summaries, with shuffled-axis, additive-only, and run-family sentinels. Metric:
  sigma68, full RMS, >5 ns tail fraction, interaction odds ratios, composition shift, calibration
  ECE, and ML-minus-traditional/additive deltas with stratified event-paired run-block bootstrap
  CIs.
- **S07k — Raw-HRDv App.A label-definition sensitivity grid.** Bound whether any reproducible
  raw-HRDv definition variant can explain the documented 12,147 App.A labelled events, or whether
  all downstream clean-timing consumers must retire that count. Traditional: deterministic grid
  over CFD fraction, downstream multiplicity, D_t/gross-tail thresholds, q_template quality, and
  ambiguity handling with forbidden timing-span overlap recorded. ML: run-heldout shape RF for
  each reproducible label definition, excluding run/event/timing-span features and including leaky
  plus shuffled-label controls. Metric: labelled-count delta to 12,147, clean/violating
  composition, q_template-only and RF ROC-AUC/AP/Brier, fixed-efficiency tail rejection, and
  run-block bootstrap CIs.
- **S10h — Baseline-excursion pile-up excess decomposition.** Decide whether S10f's
  baseline_excursion downstream excess is true two-pulse pile-up or pretrigger/baseline
  contamination. Traditional: matched high-low current strata within baseline_excursion split by
  pretrigger level, adaptive lowering, peak sample, late fraction, saturation proxy, and
  constrained two-pulse residual. ML: run-heldout classifier/regressor using P09a scores,
  P01/P02 latent-distance atoms, and waveform summaries with run/current/event excluded, calibrated
  against the same downstream topology target and shuffled controls. Metric: downstream
  high-minus-low excess, topology odds ratio, two-pulse residual enrichment, Brier/log-loss
  improvement over stratum rates, and run-block bootstrap CIs.
- **S14e — Range-energy abstention support envelope.** Find whether any depth, charge,
  saturation, or topology support clears the 10 percent res68 threshold after S14b propagates P04b
  external charge uncertainty. Traditional: PSTAR depth plus per-depth monotonic charge lookup
  under S14b geometry variants and ticket-local P04b uncertainty propagation, binned by support
  strata. ML: monotonic HGB energy proxy with train-run calibration and uncertainty-ranked
  abstention using existing S14b/P04b artifacts plus shuffled-target sentinels. Metric: accepted
  fraction, combined energy-proxy res68, bias, depth-order violation rate, ML-minus-traditional
  delta, and held-out-run bootstrap CIs.
- **S03i — q_template amplitude-matched tail-label isolation.** Test whether the S03d q_template
  clean-tail signal survives matching on amplitude, stave, downstream topology, peak-sample phase,
  saturation boundary, and run family, or whether it is mostly amplitude nuisance on downstream
  waveforms. Traditional: frozen q_template and hand-shape threshold tables within matched
  amplitude/topology strata, using S03a/S03d analytic residual tails as the target and preserving
  run-heldout folds. ML: run-heldout q_template/shape RF with amplitude-residualized features,
  topology-only, amplitude-only, shuffled-label, and downstream-only sentinels. Metric: tail
  ROC-AUC/AP, fixed-efficiency tail rejection, pair-level sigma68/full-RMS delta, >5 ns tail
  fraction delta, Brier/ECE, and ML-minus-traditional deltas with event-paired run-block bootstrap
  CIs.
- **S10k — Operational Rmax failure-definition frontier.** Decide which timing, amplitude, charge,
  and combined failure definitions make the S10e operational Rmax stable enough for run planning,
  and where threshold/live-time choices dominate. Traditional: recompute Poisson/downstream Rmax
  using frozen S10e 5%, 10%, 20%, and noise-floor tau_eff definitions crossed with bounded
  two-pulse timing and charge failure criteria. ML: calibrated compact MLP/Ridge operational score
  from S10e under the same failure definitions, with run/current/event excluded and
  shuffled-source controls. Metric: Rmax MHz, accepted-event timing RMS, charge bias/res68,
  failure rate, definition sensitivity slope, and ML-minus-traditional deltas with held-out-run
  bootstrap CIs.
- **P04k — Selector-semantics charge-closure sensitivity.** Test whether median-first-four versus
  dynamic-range selector semantics change P04/P04d duplicate-readout charge closure, especially
  near saturation and baseline-excursion boundaries. Traditional: frozen peak, integral,
  adaptive-template, and strong-Huber duplicate-readout charge estimators compared on S00c
  median-selected, dynamic-only, and matched-control strata. ML: frozen ExtraTrees/HGB charge
  regressor retrained only on train runs under each selector with selector-blind, selector-aware,
  and shuffled-target sentinels. Metric: fractional bias, res68, full RMS, within-10pct and
  within-25pct rates, saturation-boundary q_template shift, and selector delta with event-paired
  run-block bootstrap CIs.
- **S16i — Pretrigger-baseline live-time coupling audit.** Test whether S10 live-time tails and
  two-pulse separability thresholds are shifted by pretrigger baseline spectra or adaptive-lowering
  contamination before the main pulse. Traditional: stratify S10e threshold tau_eff,
  empirical last-above times, and bounded two-pulse residuals by frozen S16 pretrigger mean, slope,
  RMS, max-excursion, and adaptive-lowering bins. ML: run-heldout pretrigger-only
  live-time/tail-risk regressor plus calibrated classifier, excluding post-trigger samples, run
  IDs, current labels, and event IDs, with shuffled-pretrigger controls. Metric: tau_eff shift,
  empirical-last-above shift, two-pulse time RMS, charge bias, downstream excess, calibration ECE,
  and ML-minus-traditional deltas with run-block bootstrap CIs.
- **S10l — Asymmetric-template failure atom map.** Explain why S10f amplitude-binned/asymmetric
  templates do not reduce the operational resolvable delay below 60 ns. Traditional: frozen S10f
  asymmetric S01 template fit with chi2/ndf, residual-tail, charge-bias, and timing-bias failures
  tabulated by separation, amplitude ratio, saturation boundary, baseline excursion, peak-sample
  phase, and tail-shape strata. ML: run-heldout calibrated failure classifier/regressor using
  waveform residual atoms plus P09/S16/P07 summaries, with amplitude-only, run-family, and
  shuffled-source sentinels. Metric: per-stratum failure rate, time RMS, charge res68/bias,
  bad-recovery odds ratio, and risk-coverage AUC with held-out-source-run bootstrap CIs.
- **S03j — Selector-specific timewalk support map.** Test whether median-first-four and
  dynamic-range selector semantics change the physical support of S03 analytic/HGB timewalk gains,
  or only the selected amplitude/topology mixture. Traditional: freeze S03a amp-only and S03d
  signed-prior coefficients, refit only on train runs for median-selected, dynamic-only, and
  matched-control strata, and compare bias-vs-amplitude plus pair residual tables. ML:
  run-heldout HGB residual corrector with selector-blind, selector-aware, amplitude-only,
  topology-only, and shuffled-target sentinels. Metric: sigma68, full RMS, >5 ns tail fraction,
  bias-vs-amplitude slope, support count, and ML-minus-traditional delta with event-paired
  run-block bootstrap CIs.
- **S16j — Pretrigger hidden-mode stability audit.** Decide whether the S16e pretrigger-only
  hidden-mode signal is stable across runs and staves or is a quiet-proxy sampling artifact.
  Traditional: frozen pretrigger mean/RMS/range/slope and adaptive-lowering tables across
  run-family, stave, amplitude, and quiet-proxy strata with calibration-only thresholds. ML:
  run-family-held-out calibrated logistic/ExtraTrees hidden-mode probe using only pretrigger
  summaries, compared with shuffled-quiet labels, run-only, and amplitude-only sentinels. Metric:
  held-out AUC/AP, calibration ECE, mean quiet-probability shift, timing-tail odds ratio,
  charge-bias delta, and run-family bootstrap CIs.
- **P04l — Baseline-to-charge dropout coupling.** Determine whether baseline excursion and
  delayed/dropout waveform taxa cause charge-estimator failures directly or only through
  saturation, amplitude, and peak-sample confounding. Traditional: frozen peak, integral,
  adaptive-template, strong-Huber, and dropout-injected estimators compared in matched
  baseline-excursion/delayed-peak/dropout strata with saturation, amplitude, peak-sample, run, and
  topology controls. ML: run-heldout charge residual model using waveform atoms, P09 anomaly
  scores, S16 pretrigger summaries, and P07 saturation summaries, with baseline-only,
  saturation-only, topology-only, and shuffled-target sentinels. Metric: charge fractional bias,
  res68, full RMS, catastrophic-error rate, timing-tail propagation, and ML-minus-traditional delta
  with stratified run-block bootstrap CIs.
