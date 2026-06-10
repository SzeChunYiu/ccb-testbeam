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
`open=11 claimed=0 done=0 failed=14`, which is below the 18-ready floor because the shim treats
`testbeam` as a positional default-queue argument. The required append path was still honoured
with `--project testbeam`: the project-aware testbeam queue remains deep, with this live
post-append audit observing `open=182 claimed=4 done=260 failed=7` while claimed counts moved
under concurrent worker activity, but the mission trigger still required a small set of
new ready studies. This steering pass appended four additional non-duplicate ready tickets:
S03s upstream q-template curvature leakage gate (`1781075115.415.5d145e93`),
P08c charge-residual waveform PID null (`1781075123.485.458a1740`),
S07m AppA definition-ensemble propagation (`1781075129.553.3f0644b1`), and
S10n baseline-excursion current-swap falsifier (`1781075136.621.29dd2751`). The previous pass
appended four additional non-duplicate ready tickets:
S03p HGB transfer feature-leakage null grid (`1781062439.500.63591f99`),
S05n pretrigger-atom covariance projection stress (`1781062443.571.1e7346af`),
P04t A-stack topology lower-bound charge transfer (`1781062449.642.488b2d5f`), and
P12e cross-consumer pulse-atom harm ledger (`1781062454.713.242b3d71`). The pass before that appended
four additional non-duplicate ready tickets:
S02f binned-timewalk shuffled-control atom ledger (`1781059683.845.5a6958ad`),
S13e residual CWoLa support-collapse atlas (`1781059683.869.4bca6f7e`),
P10i live-time surrogate negative-control support map (`1781059684.922.5d6d340d`), and
S06c charge-proxy timing pull-width calibration gate (`1781059684.1019.46485748`). The pass before
that appended four additional non-duplicate ready tickets:
S03o run-61 heavy-tail support exclusion gate (`1781058292.515.16756522`),
S14i material-budget PID label uncertainty bridge (`1781058292.529.4efe2d6e`),
P09i broad-width reviewer-disagreement propagation (`1781058292.535.650c13f1`), and
P05e baseline-overlap negative-control lattice (`1781058292.614.2d602ee2`). The earlier pass
appended four additional non-duplicate ready tickets: P01g latent
baseline-contamination atom map (`1781039488.1122.04bc6ecf`), S07l injected morphology
operating-point support audit (`1781039488.1142.659b28c4`), P09g injected-morphology
false-positive gallery (`1781039488.1166.6e40385a`), and S04f waveform timing pull-width
calibration map (`1781039488.1240.043427d8`). The previous pass appended three additional
non-duplicate ready tickets: P03i phase-local waveform architecture failure map
(`1781038014.1254.657842ac`), S16m pseudo-pedestal charge live-time bias closure
(`1781038019.1322.46921ff8`), and S18j A-stack ML transfer covariance gate
(`1781038027.1393.695b00c5`). The pass before that appended five additional non-duplicate ready
tickets: P05c real-current abstention transfer (`1781036493.3234.59a107e5`),
S01g q-template quality covariate map (`1781036493.3261.7a6c05c5`),
P04n B2 transfer saturation support frontier (`1781036493.3330.4f5f1b60`),
S13d CWoLa topology calibration bridge (`1781036493.3324.58306cd1`), and
S00g selector-edge waveform atom ledger (`1781036493.3495.3e8b1a02`). The previous pass appended
four additional non-duplicate ready tickets:
P03h stave-aware residual support map by pulse atoms (`1781035058.850.43a47da0`),
S16l target-excluded pedestal estimator timing-risk audit (`1781035063.930.38bd04a3`),
S18i A-stack residual-correction leakage-flag root cause audit (`1781035068.1008.20f6375e`),
and P13a ADC quantization noise floor across pulse phase (`1781035073.1085.4d0e5a1e`). The
pass before that appended four additional
non-duplicate ready tickets under `project:testbeam`: S00f dynamic-only baseline-excursion
pile-up support map (`1781033578.541.73575b7f`), P09f delayed-peak pile-up charge-bias
disentanglement (`1781033582.610.56930afd`), S14f saturation energy-ordering geometry stress map
(`1781033587.678.10103f5a`), and S18h A-stack late-pool ML degradation atom audit
(`1781033592.746.0bc755c5`). The previous pass appended S02i pretrigger-proxy timing transfer
atom map (`1781032083.463.2d9c6a45`), S16k pretrigger-veto support frontier
(`1781032083.478.14791743`), S10m overlap-secondary discordance audit
(`1781032084.526.56a43973`), and P04m pretrigger-mode charge-transfer abstention map
(`1781032084.548.4ccc082b`). The pass before that appended S10l asymmetric-template failure atom map
(`1781030650.532.4dd15543`), S03j selector-specific timewalk support map
(`1781030650.597.5d382001`), S16j pretrigger hidden-mode stability audit
(`1781030650.662.4bb162cb`), and P04l baseline-to-charge dropout coupling
(`1781030650.727.08857c2c`). The pass before that appended S03i q_template amplitude-matched
tail-label isolation (`1781029233.703.5ff5517d`), S10k operational Rmax failure-definition
frontier (`1781029239.771.51c16bca`), P04k selector-semantics charge-closure sensitivity
(`1781029246.839.554f50f7`), and S16i pretrigger-baseline live-time coupling audit
(`1781029251.907.5de90a17`). The earlier pass appended S07k raw-HRDv App.A label-definition
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

Newest steering update: S03e says q_template-only ML can beat a traditional q_template score on
all-three curvature tails, but downstream q_template features remain too close to the label
source, so an upstream-only leakage gate is now required. P08b upgrades the PID weak label with
duplicate-readout range-energy residuals and collapses the old perfect topology proxy, while P08c
shows topology-matched waveform separation survives only on a tiny support island and still ties
the hand-shape/q_template baseline within CIs; any PID waveform claim must therefore be a
charge-residual null test. S07k finds no raw-HRDv definition that reproduces the archived
App.A 12,147/10,636/1,511 tuple, so App.A conclusions now need definition-ensemble uncertainty.
S10h shows baseline_excursion does not by itself carry a clean downstream/two-pulse excess under
the current decomposition, motivating current-swap falsifiers. S14c and P08b together keep
energy/PID work in support-map mode: downstream charge-energy proxies remain broader than the
0.10 threshold, and calibrated labels are still proxy labels.

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
The freshest S02d/S16f/S10e/S10f results now split those atoms further: pretrigger proxy timing
transfer must be mapped feature-by-feature, tail vetoes need support-preserving thresholds,
ML overlap-score and secondary-fraction pile-up diagnostics must be reconciled, and pretrigger
hidden modes must be treated as charge-transfer abstention candidates before energy or PID reuse.
The newest S00d/P09c/S14c/S18e results split the next layer again: dynamic-only selector excess is
overwhelmingly baseline-excursion-like and must be matched before pile-up use; delayed-peak
anomalies combine a large pile-up-score shift with charge bias; saturation-corrected charge
improves internal energy ordering but remains geometry/support limited; and A-stack ML residual
correction can degrade under late/mixed Sample-III calibration pools, so independent timing
controls need a pool-specific failure atom audit.
The newest P03d/P03e/S16f/S16g/S18e/S18f layer adds four smaller atoms before broad adoption:
stave-aware waveform timing gains need pulse-atom support maps beyond detector labels; pedestal
estimators must be scored by induced timing tails, not only ADC RMSE; A-stack ML control transfers
need leakage-flag root-cause tests before they constrain B-stack covariance; and sample-level
ADC/electronics noise floors must be measured across pretrigger, rising edge, peak, and tail
regions before further denoising, dropout, saturation, or pile-up models are trusted. The newest
P05b/S01f/P04e/S13b/S00c layer adds five transfer atoms: injection-trained two-pulse abstention
must survive real high-current candidate windows; fold-local q_template should be treated as a
support covariate unless it improves pair residuals; P04e's B2 externalization needs a saturation
support frontier; S13b's CWoLa score needs calibration onto topology before pile-up interpretation;
and selector-edge waveform atoms must be ledgered before they leak into baseline, pile-up, charge,
PID, or energy claims.

Completed since last steering cycle:

- **S03e/P08b/S10h/S07k/S14c — Fresh q-template, PID, baseline, App.A, and energy-proxy reports.**
  Result: q_template ML gains are promising but source-separated leakage controls are mandatory;
  calibrated PID labels reduce topology leakage but leave no waveform win beyond charge-depth;
  baseline_excursion is not yet a clean pile-up excess mechanism; the historical App.A tuple
  should be propagated as definition uncertainty; and downstream charge-energy proxies remain
  support-limited rather than globally adoptable.
- **P05b/S01f/P04e/S13b/S00c — Fresh abstention, q_template, charge-transfer, current, and
  selector reports.** Result: P05b shows injected two-pulse abstention lowers risk only with
  support/coverage tradeoffs; S01f says fold-local q_template does not securely improve timing
  tails; P04e confirms duplicate-readout ML closure is strong while B2 transfer remains support
  limited; S13b makes CWoLa a modest current-shape discriminator but leaves topology as the
  physics-facing handle; and S00c reinforces that selector-edge morphology must be tracked before
  downstream pulse claims reuse it.
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
- **S00f — Dynamic-only baseline-excursion pile-up support map.** Decide whether the 65,636
  dynamic-selector-only pulses are usable pile-up/baseline support or a selector artifact.
  Traditional: frozen taxonomy cuts plus exact run/current/amplitude/topology matching. ML:
  leakage-guarded morphology classifier excluding selector amplitudes and event ids. Metric:
  secondary-fraction delta, timing-tail delta, and charge-bias delta with run-block bootstrap CIs.
- **P09f — Delayed-peak pile-up charge-bias disentanglement.** Split delayed peaks into
  overlap-like, charge-bias-like, and veto-only atoms before recovery decisions feed pile-up,
  charge, energy, or PID. Traditional: constrained two-pulse refit plus frozen charge estimators
  in matched controls. ML: compact latent/tail/pretrigger classifier-regressor with shuffled-target
  and run-family controls. Metric: recovered secondary fraction, charge-bias delta, and abstention
  precision/recall with run-block bootstrap CIs.
- **S14f — Saturation energy-ordering geometry stress map.** Stress S14c under 2 cm, 4 cm, and
  zero-offset geometry envelopes after support restrictions. Traditional: PSTAR/range lookup with
  observed, saturated-excluded, and rising-edge/template-corrected charge. ML: P07/P04 corrected
  charge with calibrated abstention from charge-transfer, saturation-knee, and anomaly scores.
  Metric: depth-order violation, energy-proxy res68, and saturated-minus-unsaturated log-charge
  delta with run-block bootstrap CIs.
- **S18h — A-stack late-pool ML degradation atom audit.** Isolate why S18e ML residual correction
  degrades for late or mixed Sample-III calibration pools before A-stack controls feed B-stack
  covariance. Traditional: robust pair-residual variance decomposition with pool swaps. ML:
  ridge/ExtraTrees residual correction under leave-one-run-family-out and leakage sentinels.
  Metric: ML-minus-traditional robust-width delta, tail-fraction delta, and pool-transfer delta
  with run-block bootstrap CIs.
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
- **S02i — Pretrigger-proxy timing transfer atom map.** Locate which S16e pretrigger proxy atoms
  improve S02b/S02d timing closure under leave-one-run-out transfer and where ML residual terms
  transfer worse than frozen traditional corrections. Traditional: freeze S02b analytic/template
  timewalk and add one pretrigger atom at a time in robust run-heldout regressions. ML:
  run-family-heldout ridge/ExtraTrees residual learners on the same atoms with shuffled-pretrigger
  and shuffled-target controls. Metric: per-run and per-stave sigma68, >5 ns tail fraction,
  ML-minus-traditional delta, and composition drift with paired bootstrap CIs.
- **S16k — Pretrigger-veto support frontier.** Find a pretrigger-contamination veto threshold
  that captures timing tails without deleting charge, current, topology, or saturation support.
  Traditional: hand-built pretrigger proxy thresholds plus q_template and baseline-excursion cuts
  under fixed support constraints. ML: calibrated logistic/ExtraTrees pretrigger veto scores with
  run-heldout folds and shuffled-pretrigger controls. Metric: tail-capture efficiency, precision,
  veto fraction, support drift, calibration ECE, and support-constrained utility with bootstrap CIs.
- **S10m — Overlap-secondary discordance audit.** Explain why the ML overlap score shows a
  positive high-current excess while ML secondary fraction is near zero and the traditional
  bounded two-pulse secondary fraction is positive. Traditional: frozen bounded two-pulse template
  maps of secondary fraction, residual bias, and failure by separation, amplitude ratio, lowering,
  and anomaly taxon. ML: separate run-heldout RF/MLP overlap and secondary-fraction regressors
  with synthetic-to-real calibration and shuffled controls. Metric: high-minus-low secondary
  fraction, overlap-score delta, discordance rate, charge bias, Brier/log-loss, and stratum-wise
  paired bootstrap CIs.
- **P04m — Pretrigger-mode charge-transfer abstention map.** Test whether S16 pretrigger hidden
  modes define support where duplicate-readout charge closure remains excellent but P04b-style
  external transfer or energy proxy fails. Traditional: peak, integral, adaptive-template, and
  strong-Huber charge estimators split by frozen pretrigger-mode bins and matched
  amplitude/saturation/run strata. ML: HGB/ExtraTrees charge-transfer models with and without
  pretrigger-mode covariates plus conformal abstention under run-family holdout and shuffled-mode
  controls. Metric: duplicate res68, external-proxy res68, bias, abstention coverage, support loss,
  and ML-minus-traditional deltas with paired bootstrap CIs.
- **P03h — Stave-aware residual support map by pulse atoms.** Decide whether the P03e
  stave-aware waveform timing gain lives in real pulse-shape support regions or in detector/run
  identity leakage. Traditional: freeze the S03/P03 analytic timewalk and make matched residual
  tables by stave, amplitude, peak-sample phase, q_template, saturation, anomaly, and run family.
  ML: rerun P03e waveform_amp_shape_stave residual models with feature-group knockouts,
  detector-label permutations, amplitude-only/stave-only controls, and shuffled-target sentinels.
  Metric: held-out sigma68, full RMS, >5 ns tail fraction, pull width, and ML-minus-traditional
  delta per support atom with event-paired run-block bootstrap CIs.
- **S16l — Target-excluded pedestal estimator timing-risk audit.** Explain why S16g
  target-excluded ML pedestal estimates reduce RMSE but can induce larger downstream timing tails
  than traditional mean3. Traditional: frozen mean3, median3, and run-stratified target-excluded
  estimators by target sample, stave, amplitude, pretrigger spectra, adaptive lowering, and
  anomaly taxon. ML: leakage-guarded ridge/HGB target-excluded estimators with feature-group
  ablations, timing-risk calibration, and shuffled-pretrigger/shuffled-target controls. Metric:
  pedestal MAE/RMSE/bias, induced timing sigma68/full RMS/tail fractions, charge-bias delta, and
  ML-minus-traditional risk delta with run-block bootstrap CIs.
- **S18i — A-stack residual-correction leakage-flag root cause audit.** Test whether S18e/S18f
  A-stack ML residual-correction gains and degradations are real pulse timing structure or
  leakage/control-definition failures in small pool transfers. Traditional: robust
  percentile68/MAD/IQR variance decomposition under fixed calibration-pool swaps,
  run-family holdout, and explicit exclusion of target-derived timing handles. ML:
  ridge/ExtraTrees residual corrections with leakage-feature knockouts, shuffled-pool labels,
  run-only controls, and waveform-only controls. Metric: ML-minus-traditional robust-width delta,
  full RMS, tail-fraction delta, leakage-control gap, and pool-transfer delta with pair/run-block
  bootstrap CIs.
- **P13a — ADC quantization noise floor across pulse phase.** Measure the per-sample
  ADC/electronics noise floor limiting timing, amplitude, baseline, dropout recovery, and pile-up
  separation across pretrigger, rising-edge, peak, and tail phases. Traditional: per-stave/run
  quantization and noise estimates from pretrigger samples, duplicate readouts, adjacent-sample
  differences, and unsaturated quiet tails. ML: denoising AE or probabilistic residual model with
  held-out-run noise calibration and shuffled-sample controls. Metric: per-phase noise sigma/MAD,
  induced timing and charge uncertainty floors, dropout false-positive rate, and
  ML-minus-traditional denoising delta with run-block bootstrap CIs.
- **P05c — Real-current abstention transfer.** Test whether P05b failure-aware abstention gates
  trained on injected two-pulse recoveries transfer to real high-current S10e/S11b candidate
  windows without deleting the high-amplitude, large-lowering, broad-late support where pile-up
  physics lives. Traditional: freeze the bounded two-pulse template-fit quality cuts and compare
  accepted real-candidate windows against matched low-current controls by separation, amplitude
  ratio, baseline lowering, saturation, and anomaly taxon. ML: freeze the P05b isotonic failure
  model, recalibrate only train-run intercepts, and include shuffled-current and amplitude-only
  sentinels. Metric: accepted secondary fraction, time-residual proxy RMS, charge-bias proxy,
  bad-recovery proxy rate, abstention rate, and risk-coverage delta with run-block bootstrap CIs.
- **S01g — Q-template quality covariate map.** After S01f found fold-local q_template vetoes do
  not securely improve S03b timing tails, decide whether q_template remains useful as an atomic
  support covariate for amplitude, saturation, pile-up, baseline, dropout, PID, and energy maps.
  Traditional: freeze fold-local templates and tabulate q_template distributions, residual slopes,
  and support counts by stave, amplitude, peak sample, saturation boundary, baseline excursion,
  delayed peak, and downstream topology. ML: run-heldout calibrated tree/monotone models using
  q_template plus hand-shape atoms with q_template-shuffled and amplitude-only controls. Metric:
  support count, timing sigma68 delta, charge-bias delta, pile-up-score delta, AP/Brier, and
  ML-minus-traditional deltas with event-paired run-block bootstrap CIs.
- **P04n — B2 transfer saturation support frontier.** Locate where P04e train-on-B4/B6/B8
  holdout-B2 charge transfer is trustworthy once saturation depth, q_template shift, baseline
  excursion, peak phase, and topology support are explicit. Traditional: freeze peak, integral,
  strong-Huber, and adaptive-template charge estimators and build B2 residual support-frontier
  tables with train-run quantile bands. ML: ExtraTrees/HGB charge-transfer models under
  run-family holdout with saturation-boundary, q_template, and pretrigger knockouts plus
  shuffled-target and B4/B6/B8-only sentinels. Metric: accepted B2 fraction, bias, res68, full RMS,
  within-10pct and within-25pct rates, calibration coverage, and ML-minus-traditional deltas with
  run-block bootstrap CIs.
- **S13d — CWoLa topology calibration bridge.** Decide whether the S13b CWoLa waveform current
  score calibrates onto the stronger downstream-topology current handle or is only a
  nuisance-sensitive shape discriminator. Traditional: train-run downstream-fraction and
  high-over-low topology ratios in matched amplitude, charge, saturation, baseline, anomaly, and
  run-family strata. ML: freeze the S13b CWoLa RF score and calibrate it to topology excess with
  isotonic/conformal maps, including shuffled-current, topology-only, and amplitude-only controls.
  Metric: calibration slope/intercept, Brier/ECE to topology excess, high-over-low score ratio,
  downstream excess delta, stratum heterogeneity, and ML-minus-traditional calibration error with
  run-block bootstrap CIs.
- **S00g — Selector-edge waveform atom ledger.** Explain the pulse atoms that produce S00c
  honest-summary selector mistakes and the median/dynamic selector-edge population, then test
  whether those atoms propagate into timing, amplitude, saturation, pile-up, baseline, dropout,
  PID, or energy support. Traditional: enumerate selector-edge strata using raw first-four medians,
  dynamic range, peak phase, baseline excursion, saturation count, q_template, and downstream
  topology with exact S00 count reproduction. ML: leakage-guarded morphology classifier excluding
  selector-rule amplitudes, with selector-feature, run-only, and shuffled-edge sentinels. Metric:
  edge class fractions, timing sigma68 delta, charge-bias delta, secondary-fraction delta,
  false-edge AUC/AP/Brier, and enrichment deltas with run-block bootstrap CIs.
- **P03i — Phase-local waveform architecture failure map.** Explain why the P03b/P03c waveform
  MLP/CNN timing models fail to beat the strong analytic timewalk baseline except in isolated
  runs. Traditional: freeze S03a analytic timewalk and P01d sample-window/OF-template ablations,
  then tabulate residuals by sample phase, stave, amplitude, saturation, q_template,
  baseline-excursion, delayed peak, and run family. ML: rerun frozen P03b/P03c learners with
  phase-local masks, sample-dropout knockouts, architecture swaps, amplitude-only/stave-only
  controls, and shuffled-target sentinels. Metric: ML-minus-traditional sigma68, full RMS,
  tail fraction, calibration pull width, and per-atom risk ratio with event-paired run-block
  bootstrap CIs.
- **S16m — Pseudo-pedestal charge live-time bias closure.** Test whether S16g quiet-run
  pseudo-pedestals introduce charge or live-time biases when reused by P04 charge transfer and
  S10 pile-up/live-time measurements. Traditional: freeze mean3, median3, quietest, quietish, and
  calibrated pretrigger pseudo-pedestal estimators, then propagate each into peak/integral/Huber
  charge closure, q_template, empirical last-above time, and bounded two-pulse summaries on matched
  run/stave/amplitude support. ML: train run-heldout pedestal-bias and downstream-risk models from
  pretrigger summaries with target-excluded features plus shuffled-pretrigger, amplitude-only, and
  run-only sentinels. Metric: pedestal bias/MAE, charge res68/bias, tau_eff shift,
  secondary-fraction shift, timing-tail fraction, and ML-minus-traditional risk delta with
  run-block bootstrap CIs.
- **S18j — A-stack ML transfer covariance gate.** Decide whether the newest S18d/S18e A-stack
  ML timing gains can be used as an external covariance gate for B-stack timing, or whether
  calibration-pool and leakage-control failures make the transfer unsafe. Traditional: freeze
  robust A1-A3 percentile/MAD/IQR width transfer, pair-residual variance decomposition, and
  calibration-pool swaps, then score B-stack residual covariance before and after A-stack gate
  strata. ML: freeze S18d/S18e ridge/ExtraTrees residual scores and build run-family-heldout gate
  calibrations with waveform-only, run-only, pool-label, and shuffled-pool controls. Metric:
  B-stack covariance component, pair sigma68/full RMS/tail fraction, A-gate ECE/Brier,
  leakage-control gap, and ML-minus-traditional covariance delta with pair/run-block bootstrap CIs.
- **P01g — Latent baseline-contamination atom map.** Decide whether loader-verified P01b latent
  coordinates encode pretrigger baseline, adaptive-lowering, dropout/delayed-peak, or
  saturation-boundary atoms after matching run, stave, amplitude, peak phase, and topology.
  Traditional: freeze hand-shape, PCA, and explicit pretrigger/baseline summaries, then build
  matched contingency and residual tables against S16, P09, P07, P04, and S03 outcomes. ML:
  train run-heldout latent-only and latent-plus-hand classifiers/regressors with amplitude-only,
  run-only, stave-only, and shuffled-atom sentinels. Metric: atom AUC/AP/Brier, timing sigma68
  delta, charge-bias delta, support drift, and ML-minus-traditional deltas with event-paired
  run-block bootstrap CIs.
- **S07l — Injected morphology operating-point support audit.** Test whether the S07h injected
  non-D_t morphology RF can be operated at fixed efficiency or fixed false-positive rate without
  distorting real timing, charge, baseline, saturation, pile-up, or topology support. Traditional:
  freeze S07h timing/template scores, transparent P02 morphology cuts, and q_template thresholds,
  then scan operating points on identical injected folds and real matched support strata. ML:
  calibrate the S07h RF score with isotonic/conformal maps plus amplitude-only, downstream-only,
  and shuffled-label sentinels under leave-one-run-out folds. Metric: injected detection AP/AUC,
  fixed-efficiency FPR, real-data support drift, timing sigma68/tail delta, charge-bias delta, and
  ML-minus-traditional utility with run-block bootstrap CIs.
- **P09g — Injected-morphology false-positive gallery.** Explain the waveform atoms behind S07h
  and P02e morphology-score false positives and false negatives on clean, injected, and D_t-tail
  samples. Traditional: rank failures with frozen robust-template residuals, q_template, P09
  anomaly taxa, S16 pretrigger summaries, and S10/S11 two-pulse scores, then curate a bounded
  waveform gallery by run/stave/atom. ML: compare RF explanation scores, latent nearest
  neighbors, isolation/AE residuals, and counterfactual sample masks with shuffled-score and
  run-heldout controls. Metric: curated precision by taxon, false-positive and false-negative
  taxon enrichment, inter-reviewer agreement, recovery/veto action accuracy, and
  ML-minus-traditional ranking precision with stratified bootstrap CIs.
- **S04f — Waveform timing pull-width calibration map.** Determine whether P03g waveform timing
  residual gains are accompanied by calibrated per-pulse uncertainty, or whether amplitude-only
  and phase-scrambled controls explain the apparent pull-width improvement in specific pulse
  atoms. Traditional: freeze S03 analytic timewalk residual quantile tables and S04 robust-width
  estimators by run, stave, amplitude, q_template, saturation, baseline, anomaly, and peak-phase
  strata. ML: train waveform MLP/CNN residual sigma and conformal uncertainty models with
  amplitude-only, phase-scrambled, sample-permuted, run-only, and shuffled-target controls under
  leave-one-run-out folds. Metric: pull sigma68/full RMS, ECE/coverage, interval width, tail
  calibration, stratum-wise sigma68, and ML-minus-traditional calibration deltas with
  event-paired run-block bootstrap CIs.
- **P01h — Time-local latent residualization gate.** Decide whether loader-verified P01/P01d
  latent waveform coordinates retain useful pulse-shape information after removing sample-epoch,
  run-family, stave, amplitude, peak-phase, topology, q_template, saturation, baseline-excursion,
  delayed-peak, and dropout atoms. Traditional: freeze hand-shape summaries, PCA, and matched
  residual tables after exact S00/P01 loader reproduction, then score each atom with
  run-family-held-out linear/logistic baselines and support counts. ML: latent-only and
  latent-plus-hand residualized ridge/ExtraTrees probes with nuisance residualization plus
  run-only, stave-only, amplitude-only, and shuffled-atom sentinels. Metric: atom AUC/AP/Brier,
  residual balanced accuracy, timing sigma68 delta, charge-bias delta, support drift, and
  ML-minus-traditional deltas with event-paired run-block bootstrap CIs.
- **S05h — Saturation-aware covariance support frontier.** Locate where S05d/S05e saturation-aware
  covariance gains remain valid after matching B2 saturation depth, q_template shift, amplitude,
  topology, baseline lowering, pile-up candidates, and run family. Traditional: freeze S05c
  pair-median hierarchical covariance and S05d static priors, then build support-frontier tables
  and bias envelopes by pulse atom. ML: freeze S05e ExtraTrees/dynamic-weight models, refit only
  calibration layers under leave-one-run-out folds, and run saturation-knockout, topology-only,
  amplitude-only, and shuffled-target sentinels. Metric: accepted support fraction, downstream
  projection sigma68/full RMS, median bias, covariance component error, tail fraction, calibration
  coverage, and ML-minus-traditional deltas with paired run-block bootstrap CIs.
- **S01h — Q-template run-stave leakage atom grid.** Explain which run, stave, amplitude,
  peak-phase, saturation, baseline, delayed-peak, dropout, and topology atoms drive the S01f
  q_template run-stave transfer leakage flags, and decide whether q_template is safe as a support
  covariate rather than a veto. Traditional: freeze S01 empirical templates and conditional
  q_external residual thresholds, then make atom-stratified residual/failure tables with exact
  S00/S01 reproduction and run-held-out support counts. ML: freeze or rerun the S01f RF
  q-structure model with feature-group knockouts, monotone/calibrated alternatives, and
  shuffled-q, run-only, stave-only, and amplitude-only controls. Metric: held-out AUC/AP,
  flagged-minus-all failure enrichment, q_template residual slope, support drift,
  timing/charge/pile-up deltas, leakage-control gap, and ML-minus-traditional deltas with
  run-block bootstrap CIs.
- **P12b — Pulse-support tensor for PID energy consumers.** Publish a compact support tensor that
  tells PID and energy consumers which combinations of shape, timing, amplitude, saturation,
  pile-up, baseline, dropout/anomaly, q_template, covariance, and charge-transfer atoms are
  populated and trustworthy now. Traditional: combine landed S00/S01/S03/S04/S05/S10/S16/P04/P07/
  P09/S14 support tables into deterministic multidimensional occupancy, bias, and closure
  summaries with minimum-count and exact-reproduction gates. ML: calibrated density/support and
  failure-risk models over the same atoms with leave-run-family-out validation, conformal support
  scores, and shuffled-axis controls. Metric: populated-cell count, minimum effective sample size,
  charge/energy proxy res68 and bias, timing-tail and pile-up enrichment, PID weak-label stability,
  support-score coverage/ECE, and ML-minus-traditional failure-risk deltas with stratified
  bootstrap CIs.
- **P06b — Amplitude-stratified timing bias ledger.** Determine which amplitude, charge-proxy,
  peak-phase, saturation, q_template, baseline, dropout/anomaly, and topology atoms carry signed
  timing bias or undercovered uncertainty after P06a showed traditional analytic timing still
  beats the ML residual model overall. Traditional: freeze S02/S03 analytic timewalk plus S04
  robust-width tables and build matched residual/bias strata with exact S00/S03 reproduction. ML:
  recalibrate the P06a ridge residual and absolute-residual uncertainty with amplitude-only,
  topology-only, run-only, and shuffled-target sentinels under leave-one-run-out folds. Metric:
  per-atom median bias, sigma68/full RMS, tail fraction, pull coverage/ECE, support count, and
  ML-minus-traditional deltas with event-paired run-block bootstrap CIs.
- **S05i — Covariance coverage calibration by B2 topology.** Test whether S05f B2-local covariance
  corrections provide calibrated interval coverage across B2-containing and downstream-only
  topology after saturation, amplitude, baseline, pile-up, and anomaly matching. Traditional:
  freeze S05c hierarchical pair-median covariance and S05h support-frontier strata, then compute
  topology-matched covariance components and prediction intervals. ML: freeze the S05f B2-local
  ExtraTrees residual model, refit only calibration/conformal layers, and compare B2-feature
  knockouts, topology-only, saturation-only, and shuffled-run controls. Metric: coverage error,
  interval width, signed off-diagonal covariance delta, inferred correlated fraction, sigma68/full
  RMS, accepted support fraction, and ML-minus-traditional deltas with pair/run-block bootstrap CIs.
- **P02g — Timing-tail label-source split for morphology RF.** Decompose the P02d morphology RF
  signal into upstream pulse-shape information versus downstream D_t label-source self-reference
  without losing early-peak and anomaly atoms. Traditional: freeze transparent P02 morphology,
  q_template, early-peak, amplitude, and topology cuts, then score upstream-only, downstream-only,
  and all-three matched strata against independent timing-tail definitions. ML: train shape
  RF/ExtraTrees variants on upstream-only, downstream-only, all-stave, amplitude-only, and
  phase-scrambled features with leave-one-run-out and shuffled-label controls. Metric: AUC/AP,
  fixed-efficiency tail rejection, source-split enrichment, support drift, timing sigma68/tail
  delta, and ML-minus-traditional deltas with stratified run-block bootstrap CIs.
- **P01i — Domain-score consumer leakage sentinel.** Decide whether residualized P01d/P03d
  epoch-domain scores still leak into downstream timing, charge, pile-up, PID, or energy consumers
  after removing amplitude, topology, run family, peak phase, q_template, saturation, baseline,
  dropout, and anomaly atoms. Traditional: freeze hand-shape/PCA and matched residual tables,
  residualize the domain score by explicit nuisances, and test consumer metrics with and without
  the residualized score. ML: compare latent-only, latent-plus-domain-score, and
  nuisance-residualized ExtraTrees/ridge probes with run-only, amplitude-only, topology-only, and
  shuffled-score controls. Metric: consumer sigma68/res68/AUC/AP changes, leakage-control gap,
  support drift, score calibration/ECE, and ML-minus-traditional deltas with event-paired
  run-block bootstrap CIs.
- **S16n — Large-lowering taxonomy propagation gate.** Propagate the S16f held-out
  large-lowering taxonomy into downstream pulse risks after that audit found pre-trigger
  contamination as the dominant source and pile-up as the next largest class. Traditional: freeze
  the S16f fixed morphology scorecard, then build class-matched residual, charge-bias, pile-up,
  q_template, and support tables with exact S00/S16 reproduction. ML: freeze the S16f run-split RF
  taxonomy transfer, recalibrate class probabilities with conformal/isotonic layers, and compare
  pretrigger-only, pile-up-only, amplitude-only, topology-only, and shuffled-label controls.
  Metric: per-class timing sigma68/full RMS/tail fraction, charge res68/bias, pile-up enrichment,
  support drift, calibration/ECE, and ML-minus-traditional deltas with held-out run-block
  bootstrap CIs.
- **S16o — No-proxy pedestal width tradeoff audit.** Decide whether the S16e no-proxy ML
  estimator's lower MAE is usable once its wider width68 and downstream timing/charge effects are
  counted. Traditional: freeze mean3, median3, stave-sample offset median3, and target-excluded
  summaries, then stratify pedestal bias, width68, RMSE, induced S02/S03 timing shifts, and P04
  charge shifts by target sample, stave, amplitude, peak phase, q_template, adaptive lowering,
  anomaly taxon, and run family. ML: rerun the S16e HGB with feature-group ablations,
  monotone/ridge alternatives, and shuffled-pretrigger, shuffled-target, amplitude-only, and
  run-only sentinels. Metric: pedestal MAE, width68, RMSE, induced timing sigma68/tail fraction,
  charge res68/bias, support drift, and ML-minus-traditional deltas with event-paired run-block
  bootstrap CIs.
- **P02h — Hand-latent morphology consensus failures.** Explain where P02e train-only AE
  latents, forbidden all-data latent diagnostics, and traditional hand+PCA morphology disagree on
  manual flags or peak-group pulse morphology. Traditional: freeze hand-shape variables, PCA
  clusters, robust-template residuals, q_template, P09 anomaly taxa, S16 pretrigger summaries, and
  P07 saturation flags, then build matched disagreement tables by run, stave, amplitude, peak
  sample, topology, baseline, delayed peak, and saturation atoms. ML: compare train-only AE latent
  probes, release-latent diagnostic probes, latent-plus-hand ensembles, and calibrated disagreement
  classifiers with run-only, amplitude-only, topology-only, and shuffled-label sentinels. Metric:
  disagreement rate, manual-flag and peak-group AMI/purity deltas, calibrated error probability,
  taxon enrichment, downstream timing/charge risk delta, and ML-minus-traditional deltas with
  stratified run-block bootstrap CIs.
- **S05j — Anomaly-tail covariance coverage stress.** Stress-test whether S05f covariance
  intervals remain calibrated outside the B2-topology support map, especially across anomaly taxa,
  timing-tail atoms, baseline contamination, saturation boundary, and two-pulse scores.
  Traditional: freeze raw pair-median, hierarchical covariance, downstream-only controls, and
  saturation ridge corrections, then tabulate signed off-diagonal covariance, sigma68, full RMS,
  and coverage by one frozen pathology axis at a time with matched downstream controls. ML: rerun
  the S05f `ml_with_b2_local` and `ml_no_b2_local` residual models with pathology-axis ablations,
  conformal interval calibration, and shuffled-axis/run-family sentinels. Metric: interval
  coverage, width, B2-containing minus downstream covariance, correlated-fraction shift, residual
  sigma68/full RMS, support loss, and ML-minus-traditional deltas with pair/event run-block
  bootstrap CIs.
- **P06c — Time-local pull coverage atlas.** Check whether per-pulse timing pull widths and
  uncertainty estimates are locally calibrated across the 18-sample pulse phase, especially around
  samples 3-6 where P01d found CFD and smoothing artifacts. Traditional: freeze S02/S03 analytic
  timing, OF/template sample-window ablations, and S04 robust-width estimates, then compute pull
  residuals by peak sample, leading-edge phase, sample-window mask, stave, amplitude, saturation,
  q_template, baseline, anomaly, and run family. ML: recalibrate the P06a residual-uncertainty
  model plus a constrained per-sample conformal/tail-risk model with sample-dropout ablations and
  shuffled-target, run-only, amplitude-only, and topology-only sentinels. Metric: pull width,
  nominal 68% and 95% coverage, sigma68/full RMS, >5 ns tail fraction, support count,
  calibration ECE, and ML-minus-traditional deltas with event-paired run-block bootstrap CIs.
- **S05k — Rate-residual covariance atom sieve.** Decide whether residual A/B acceptance and
  current-rate atoms still bias B-pair covariance intervals after S05e-rate showed run-level A/B
  coincidence rate does not explain the large B2-local covariance. Traditional: freeze S05c/S05f
  hierarchical pair-median covariance, match by run family, pair, topology, amplitude, saturation,
  anomaly taxon, and A/B rate-residual quantile, then tabulate signed off-diagonal covariance and
  downstream-only controls. ML: run-heldout ExtraTrees/GAM covariance predictors with and without
  rate-residual features plus shuffled-rate, run-only, and topology-only sentinels. Metric:
  interval coverage, interval width, B2-containing minus downstream covariance,
  correlated-fraction shift, sigma68/full RMS, and ML-minus-traditional deltas with pair/event
  run-block bootstrap CIs.
- **P01j — Control-stratum latent calibration map.** Test whether the P01e control-stratum latent
  lift for manual flags and peak groups is real pulse morphology beyond run, topology, amplitude,
  and stave controls, or residual domain leakage. Traditional: freeze hand-shape variables, PCA
  summaries, q_template, P09 taxa, and S16 baseline summaries within identical control strata and
  compare observed, controls-only, and label-shuffle probes. ML: run-heldout calibrated RF/linear
  probes on train-only latents with latent-only, latent-plus-domain-score, controls-only, and
  permuted-within-stratum ablations. Metric: balanced accuracy, macro-F1, lift over controls-only,
  ECE/Brier, downstream timing/charge risk delta, and ML-minus-traditional deltas with stratified
  run-block bootstrap CIs.
- **S10n — High-stat secondary support stability gate.** In the S10e high-stat dominant strata,
  test whether the traditional secondary-fraction high-minus-low excess is stable under template,
  threshold, and support choices, and why ML secondary-fraction and overlap-score diagnostics
  disagree. Traditional: freeze S10b/S10d templates, scan secondary thresholds and
  asymmetric-template variants inside the top high-amplitude, large-lowering, broad-late strata,
  and require matched current/topology support. ML: run-heldout RF/MLP overlap and
  secondary-fraction regressors with calibrated isotonic outputs, support-abstention rules, and
  shuffled-current, amplitude-only, and topology-only sentinels. Metric: secondary-fraction delta,
  overlap-score delta, threshold sensitivity slope, accepted-support fraction, timing-tail and
  charge-bias delta, and ML-minus-traditional deltas with run-block bootstrap CIs.
- **P04o — Rate-conditioned charge support veto.** Check whether sparse A/B coincidence-rate and
  current-acceptance atoms induce charge-transfer bias that should veto P04/S14 energy or PID
  consumers in low-support regions. Traditional: freeze P04/P04d duplicate-readout and P04b
  external charge closures, then stratify charge residuals by A/B rate residual, run family,
  topology, saturation depth, q_template, baseline taxon, and geometry support. ML: compare
  HGB/ExtraTrees charge regressors with and without rate-residual features plus conformal
  abstention, shuffled-rate, run-only, and topology-only controls. Metric: charge res68, signed
  bias, energy-ordering flip rate, support loss, conformal coverage, and ML-minus-traditional
  deltas with event/run-block bootstrap CIs.
- **S11f — Two-pulse method-disagreement taxonomy.** Split real high-current two-pulse candidates
  into traditional-only, ML-only, joint, and neither classes after S11e found partial agreement
  rather than redundancy. Traditional: freeze bounded-fit delta-SSE, secondary-fraction,
  support-count, and template-residual ranks from S11b/S11d/S11e, then match by run, amplitude,
  lowering, topology, saturation, and anomaly class. ML: freeze the low-current synthetic-overlay
  residual-shape score and recalibrate with leave-one-run-out isotonic/conformal layers plus
  shuffled-current sentinels. Metric: candidate-rate excess, recovered delay/area stability,
  topology-excess coverage, gallery precision/recall where available, and ML-minus-traditional
  deltas with source-run bootstrap CIs.
- **S05l — Saturation-covariance correction validity gate.** Re-test S05e's B2 covariance
  reduction using only saturation features that survive duplicate-readout validation, because P07e
  found the P07d ratio-transfer correction worsens high-amplitude B2 duplicate closure.
  Traditional: rerun S05c/S05e covariance tables with raw, template-only, duplicate-safe, and
  no-correction feature sets. ML: retrain the S05e ExtraTrees residual model only across those
  feature sets with correction-knockout, shuffled-target, and downstream-only sentinels. Metric:
  B2-minus-downstream covariance, correlated fraction, sigma68/full RMS, interval coverage,
  support loss, and ML-minus-traditional deltas with pair/event run-block bootstrap CIs.
- **P04p — Duplicate-readout charge harm labels.** Turn odd/even duplicate-readout closure into a
  harm-label audit for charge and saturation corrections before energy or PID consumers reuse
  them. Traditional: freeze raw peak/integral, Huber duplicate closure, adaptive-template, and
  template-only saturation corrections, then label excess charge bias, res68, timing abs68, and
  q_template shift on held-out odd duplicates. ML: train a leave-one-run-out harm
  classifier/calibrator using only even-channel waveform, saturation, baseline, anomaly, and
  support summaries with hash-overlap and shuffled-target sentinels. Metric: harm precision/recall,
  accepted coverage, charge res68/bias, timing abs68/tail rate, calibration error, and
  ML-minus-traditional deltas with run-block bootstrap CIs.
- **P12c — Pulse-action decision matrix.** Convert the growing set of pulse atoms into concrete
  downstream actions: correct, abstain, veto, or pass through for timing, amplitude, saturation,
  pile-up, baseline, dropout, PID, and energy consumers. Traditional: freeze rule-based atoms from
  S02/S03/S05/S10/S16/P04/P07/P09 and build matched raw/corrected/abstained/vetoed action tables.
  ML: train a calibrated multi-output decision model using predeclared waveform/support summaries
  with leave-one-run-out action-knockout, shuffled-target, and domain-sentinel controls. Metric:
  action support fraction, timing width/tails, charge bias/res68, pile-up coverage, baseline harm,
  covariance coverage, PID/energy proxy degradation, and ML-minus-traditional deltas with
  run-block bootstrap CIs.
- **S11g — Residual-pool two-pulse real-current transfer gate.** Test whether the S11e conditioned
  residual-pool gain on injected two-pulse recovery transfers to real high-current candidate
  windows without inflating failure, charge bias, or support drift; include the newest P05b
  threshold-utility result, where CNN thresholding lowers injected RMS and failure relative to a
  template threshold, as an injection-only anchor. Traditional: freeze the conditioned
  amplitude-binned asymmetric S01 template fit, residual-pool ranks, bounded-fit delta-SSE,
  secondary-fraction, and source-run holdout gates, then score high-minus-low candidate strata
  matched by run, amplitude, lowering, topology, saturation, anomaly, and q_template. ML:
  freeze the conditioned compact MLP classifier/regressor and recalibrate only isotonic/conformal
  abstention layers with shuffled-current, low-current overlay, amplitude-only, and topology-only
  sentinels. Metric: candidate-rate excess, accepted constituent time RMS proxy, charge fractional
  bias/res68, failure/abstention rate, support drift, topology-excess coverage, calibration ECE,
  and ML-minus-traditional deltas with source-run and matched-stratum bootstrap CIs.
- **P01k — Event-block timing leakage atomizer.** Locate which run, event-block, stave,
  amplitude, peak-phase, q_template, baseline, saturation, dropout, anomaly, and topology
  coordinates let event-block shuffled controls recover most of the P01f/P01e nominal timing gain.
  Traditional: freeze hand-shape/PCA residual timing probes and explicit nuisance-matched tables,
  then decompose nominal and event-block-shuffled sigma68 gains by one atom and paired atom
  interactions. ML: run-heldout latent ridge/ExtraTrees probes with per-atom residualization,
  adversarial domain-score removal, event-block/per-run-stave/per-run-stave-amplitude shuffles,
  and amplitude-only, run-only, topology-only controls. Metric: sigma68/full RMS/tail fraction,
  control-gain fraction, event-shuffle closeness, nuisance AUC, support count, leakage-control
  gap, and ML-minus-traditional deltas with event-paired run-block bootstrap CIs.
- **S03k — Analytic comparator reuse gate for waveform consumers.** Require downstream
  waveform-latent, timing-uncertainty, pile-up, charge, PID, and energy consumers to beat the
  exact-fold S03 analytic timewalk comparator, not just weaker CFD20 or S02 ridge baselines; carry
  forward the newest P01e quantization finding that samples 5/7/8 sign flips are CFD-only
  artifacts. Traditional: publish a frozen exact-fold S03 analytic residual registry and matched
  residual tables by run, stave, amplitude, peak phase, q_template, baseline, saturation,
  dropout/anomaly, topology, and pile-up score. ML: evaluate representative frozen
  P01/P03/P06/P05/P04 consumer models against the same folds with target-shuffle, event-shuffle,
  domain-score, amplitude-only, and topology-only sentinels. Metric: consumer sigma68/full
  RMS/tail fraction, pull coverage, charge/pile-up/PID proxy change after timing substitution,
  support loss, comparator margin, and ML-minus-S03 deltas with event-paired run-block bootstrap
  CIs.
- **P07h — Boundary-shrinkage leakage triage.** Explain the P07 natural B2 boundary-shrinkage
  leakage flags and decide whether they are harmless event-hash/support artifacts or real
  saturation-boundary bias that should veto charge, timing, PID, and energy consumers.
  Traditional: freeze linear boundary shrink, retained-window template/rising-edge estimators,
  odd/even duplicate checks, q_template and CFD20 shift tables, then isolate flagged boundary
  cells by saturation depth, observed amplitude, run, stave, peak sample, baseline, anomaly, and
  event-hash buckets. ML: rerun only calibration/diagnostic layers for boundary ML, isotonic
  alpha, and conformal risk models with hash-block exclusion, shuffled-target, shuffled-hash,
  amplitude-only, run-only, and saturation-only controls. Metric: leakage-flag rate,
  amplitude/charge lift, res68, signed bias, q_template shift, CFD20/timing-tail delta,
  calibration coverage/ECE, veto support loss, and ML-minus-traditional deltas with
  run/stave/hash-block bootstrap CIs.
- **S04g — Lowering-axis pull calibration adoption gate.** Turn the newest S04c finding that
  the S16 lowering axis dominates timing-tail strata into a calibrated uncertainty/veto gate
  rather than a silent timing-model replacement. Traditional: stratified CFD20/S03 analytic pull
  tables by lowering axis, amplitude, stave, and run with train-only isotonic bins. ML:
  run-held-out RF/GBM tail-probability and sigma predictors using the same pulse atoms with no
  event/run identifiers. Metric: pull width, tail-probability ECE, 95% acceptance tail coverage,
  sigma68 delta, and ML-minus-traditional deltas with run-block bootstrap CIs.
- **P01l — Sample-6 smoothing causality null atlas.** Test whether the P01d/P01e sample-6 timing
  gain is causal waveform information or a replacement/quantization artifact across CFD,
  template-phase, and OF pickoffs. Traditional: local-linear, amplitude-bin curvature, and
  control-stratum sample-6 replacements on train-selected timing methods. ML: no-sample-6 ridge
  and tree imputers plus waveform residual models with target, row, and event-block shuffles.
  Metric: delta sigma68/full RMS, imputation MAE/R2, control-gain fraction, and
  ML-minus-traditional deltas with held-out-run event-block bootstrap CIs.
- **P05d — Real-current overlap score calibration curve.** Decide whether the P05b/P05c CNN
  overlap score can become a calibrated real-current secondary-fraction estimator or must remain
  only a support-dependent ranking diagnostic. Traditional: frozen constrained two-pulse template
  fit and matched S10/S11 secondary-fraction estimator by amplitude, lowering, broad-late
  topology, and current/run strata. ML: isotonic/Platt-calibrated compact CNN overlap probability
  trained on injected overlays and low-current controls, applied leave-one-run-out to high-current
  windows. Metric: calibration slope/intercept, Brier score, high-minus-low secondary fraction,
  score/fraction discordance, accepted recovery RMS, and source-run bootstrap CIs.
- **P04q — Pathology-tail charge uncertainty propagation.** Propagate S04c/P09/S16 pathology-tail
  atoms into charge-closure uncertainty before energy and PID consumers reuse P04/P07 outputs.
  Traditional: duplicate-readout Huber/template charge closure stratified by lowering axis,
  anomaly taxon, saturation boundary, and run family with train-only abstention thresholds. ML:
  ExtraTrees or quantile-regression charge models with pathology features and conformal residual
  calibration, audited by shuffled-target and family-holdout sentinels. Metric: charge res68,
  signed bias, conformal coverage, abstention coverage, downstream range-energy proxy delta, and
  ML-minus-traditional deltas with run-family bootstrap CIs.
- **P07i — Run-family saturation knee acceptance gate.** Decide whether natural B2 saturation
  corrections can be accepted only inside duplicate-readout run-family knee support after P07f
  split the duplicate-ratio knees into incompatible low- and high-knee families. Traditional:
  per-run duplicate-ratio piecewise knees with odd-channel closure and transparent
  accept/abstain bands. ML: run-held-out waveform knee/acceptance classifier calibrated against
  duplicate labels with run/event IDs and duplicate targets excluded. Metric: accepted fraction,
  charge res68, timing-tail delta, q_template shift, and harm rate versus no-correction with
  run-block bootstrap CIs and shuffled-target sentinels.
- **P04r — Dropout recovery timing-harm support map.** Map where dropout-injected recovery helps
  amplitude/charge but harms timing phase, tail shape, or downstream support after P04g showed a
  strong injected ML charge closure. Traditional: calibrated interpolation and rising-edge Huber
  recovery stratified by dropout location, amplitude, stave, peak sample, and anomaly class. ML:
  ExtraTrees inpainting and HGB residual correction under run-held-out folds with no target or
  identifier leakage. Metric: amplitude/charge res68, time_abs68_samples, tail-bias median,
  catastrophic rate, and support-atom harm label rate with stratified event bootstrap CIs.
- **S14g — Veto-ladder energy acceptance calibration.** Treat P09/S10/S16/P07 veto ladders as
  energy/PID support acceptances rather than energy-ordering improvements after S14d found large
  acceptance loss and charge-scale shifts with little depth-ordering change. Traditional:
  sequential transparent veto ladders from anomaly, pile-up, baseline/lowering, and saturation
  thresholds with run-held-out charge-scale accounting. ML: calibrated support classifier using
  the same pulse atoms while excluding depth/PID/run/event identifiers. Metric: acceptance,
  charge-proxy log shift, energy-proxy res68, depth-order violation, and ML-minus-traditional
  deltas by geometry and veto family with run-block bootstrap CIs.
- **S04h — Saturation-nuisance timing-tail causal null.** Test whether retained-window saturation
  corrections causally change same-particle timing tails or merely track saturated support and
  unrelated pathology after S02d/P07e found non-adoptable recovery and only a small timing-tail
  nuisance span. Traditional: matched saturated-event timing residual tables for observed,
  template-retained-window, and duplicate-knee-abstained corrections with amplitude, lowering,
  q_template, and anomaly matching. ML: run-held-out nuisance model predicting tail risk from
  correction deltas and pulse atoms while excluding downstream timing labels from features.
  Metric: tail fraction above 5 ns, sigma68, q95_abs, q_template shift, and matched tail delta
  versus observed with paired event bootstrap CIs and composition-balance diagnostics.
- **S03l — Cross-sample timewalk residual atom ledger.** After the newest S03e blind
  Sample-I/Sample-II transfer and S03d shrinkage reports, explain which pulse atoms carry the
  remaining signed timewalk residual when the frozen S03 analytic comparator is applied without
  refitting. Traditional: freeze the S03 analytic and hierarchical-shrinkage coefficients, then
  tabulate residual bias, sigma68, full RMS, and >5 ns tails by sample family, run, stave,
  amplitude, peak phase, q_template, lowering, saturation, dropout/anomaly, and topology with
  matched downstream controls. ML: train only run-held-out calibration/diagnostic layers with
  amplitude-only, run-only, topology-only, and shuffled-target sentinels. Metric: signed residual
  bias, sigma68/full RMS, tail fraction, pull coverage, support count, and ML-minus-traditional
  deltas with event-paired run-block bootstrap CIs.
- **S10o — Anomaly-residual current excess truth split.** After S10f showed P09 anomaly taxa do
  not explain away the matched high-minus-low current excess, split the residual into beam
  pile-up, baseline pathology, charge support drift, and topology composition components.
  Traditional: freeze S10e/S10f matched current strata, P09 taxa, P04/P07 charge strata, and
  downstream topology controls, then decompose the residual excess one atom at a time under
  support-preserving matching. ML: run-held-out calibrated classifiers/regressors with
  taxon-knockout, charge-knockout, topology-only, amplitude-only, run-only, and shuffled-current
  sentinels. Metric: high-minus-low excess, secondary-fraction delta, charge log-shift, topology
  composition drift, accepted support fraction, and ML-minus-traditional deltas with matched
  run-block bootstrap CIs.
- **P07j — Saturation knee family action bands.** Convert the conflicting P07f natural B2 knee
  families and retained-window timing-tail nuisance into per-run-family pass, correct, abstain,
  or veto bands before saturation outputs feed timing, charge, PID, or energy. Traditional:
  freeze duplicate-ratio piecewise knees, retained-window/template estimators, odd/even duplicate
  closure, and S02/S04 timing-tail tables, then define transparent action bands by saturation
  depth, peak sample, amplitude, q_template, lowering, and anomaly support. ML: calibrate a
  run-held-out waveform knee/action classifier with duplicate targets, event IDs, and run IDs
  excluded, plus shuffled-target, saturation-only, amplitude-only, and run-family holdout
  sentinels. Metric: action support fraction, charge res68/bias, timing-tail delta, q_template
  shift, harm rate versus no correction, calibration ECE, and ML-minus-traditional deltas with
  run-block bootstrap CIs.
- **P04s — Dropout recovery phase-harm abstention gate.** Locate where P04g dropout-injected
  charge recovery creates timing-phase, tail-shape, q_template, or pile-up-score harm that should
  force abstention before recovered charge feeds P04/P07/S14/PID consumers. Traditional: freeze
  interpolation, rising-edge Huber, and template recovery baselines, then stratify injected and
  real dropout/anomaly candidates by missing-sample location, peak phase, amplitude, stave,
  q_template, lowering, saturation, and P09 taxon. ML: run-held-out ExtraTrees/HGB inpainting and
  harm calibrators with feature knockouts, dropout-location shuffles, amplitude-only, run-only,
  and topology-only sentinels. Metric: charge res68/bias, time_abs68_samples, q_template shift,
  tail-bias median, catastrophic harm rate, abstention support fraction, and ML-minus-traditional
  deltas with stratified event/run-block bootstrap CIs.
- **P12d — Consumer action conflict arbitration.** Decide what to do when existing pulse-action
  rules disagree across timing, charge, saturation, pile-up, baseline, dropout, PID, and energy
  consumers. Traditional: freeze the transparent S02/S03/S05/S10/S14/S16/P04/P07/P09/P12c action
  tables and build a deterministic precedence ladder by consumer, support count, and harm labels.
  ML: train a run-held-out calibrated multi-task conflict classifier from predeclared pulse atoms,
  with action-knockout, consumer-knockout, shuffled-target, and run-family sentinels. Metric:
  conflict rate, harmful-conflict precision/recall, accepted support fraction, timing-tail delta,
  charge res68/bias delta, PID weak-label drift, energy-proxy degradation, and ML-minus-traditional
  deltas with event-paired run-block bootstrap CIs.
- **P08d — PID weak-label action-band stability.** Test whether saturation, dropout, baseline,
  anomaly, and energy veto/action bands preserve PID-like waveform weak labels or manufacture
  apparent PID separation through support loss. Traditional: freeze penetration-depth, deltaE-E
  charge bands, topology matching, and transparent P07j/S14g/P04s action bands, then evaluate weak
  PID labels before and after each action band with matched charge/current/depth support. ML:
  run-held-out waveform/latent PID probes with charge-only, depth-only, action-only,
  shuffled-label, and run-family controls. Metric: weak-label AUC/AP, purity at fixed efficiency,
  calibration ECE, support loss, charge/depth composition drift, action-band induced label shift,
  and ML-minus-traditional deltas with stratified run-block bootstrap CIs; no PID adoption without
  truth.
- **P09h — Baseline-excursion temporal subtype ledger.** Split baseline-excursion anomaly taxa
  into temporal subtypes before using them to explain pile-up residuals, dropout recovery harm,
  charge bias, or timing tails. Traditional: split P09 baseline-excursion candidates by pretrigger
  slope, early-sample offset, rising-edge distortion, peak phase, tail recovery, and downstream
  topology using robust thresholds and matched support tables. ML: run-held-out calibrated subtype
  model from 18-sample waveform atoms and pretrigger summaries, with taxon-knockout,
  time-window-shuffle, amplitude-only, run-only, and topology-only sentinels. Metric: subtype
  prevalence, current high-minus-low excess share, timing >5 ns tail enrichment, charge bias/res68,
  dropout harm rate, pile-up secondary-fraction delta, and ML-minus-traditional deltas with matched
  run-block bootstrap CIs.
- **S06b — Amplitude-energy timing support closure.** After calibrated charge, saturation,
  dropout, anomaly, and baseline action bands, test whether timing resolution is monotonic in
  amplitude or energy proxy, or whether the apparent sigma(E) curve is support and veto
  composition. Traditional: freeze S03 analytic timing and S04 robust-width estimators, then
  tabulate sigma68, full RMS, pull width, and tail fractions in matched amplitude, P04/P07/S14
  charge-energy, saturation-knee, dropout, baseline, and anomaly strata. ML: run-held-out calibrated
  timing-uncertainty model with charge/support features, conformal intervals, and charge-only,
  amplitude-only, action-only, shuffled-target, and run-family controls. Metric: sigma68/full RMS
  versus amplitude and energy proxy, monotonicity violation rate, pull 68/95% coverage, support
  loss, timing-tail delta, and ML-minus-traditional deltas with event-paired run-block bootstrap
  CIs.
- **P07k — Q-template-preserving saturation acceptance calibration.** After P07g found that
  conformal-risk and traditional-envelope saturation acceptors have different coverage,
  q_template shifts, and accepted support, decide whether any acceptance rule preserves charge,
  q_template, and timing-tail safety simultaneously. Traditional: freeze retained-window/template
  envelopes and duplicate-ratio acceptance bands, then stratify accepted, abstained, and vetoed B2
  pulses by run family, saturation depth, q_template shift, amplitude, lowering,
  dropout/anomaly taxon, and topology. ML: freeze the P07g conformal-risk acceptor, recalibrate
  only isotonic/conformal layers under leave-one-run-family-out folds, and compare
  saturation-only, amplitude-only, run-family, and shuffled-target sentinels. Metric: accepted
  support fraction, charge res68/bias, q_template median shift, timing >5 ns tail delta,
  calibration coverage/ECE, catastrophic harm rate, and ML-minus-traditional deltas with paired
  event/run-block bootstrap CIs.
- **P08e — Conventional PID score decomposition null.** After P08b found the frozen conventional
  charge-current matched PID-like score far ahead of residualized waveform ML, decompose whether
  that apparent PID separation is physics-like pulse/DeltaE-E information or residual geometry,
  depth, current, and charge-support leakage. Traditional: freeze tail/total, area/peak,
  q_template, DeltaE-like amplitude vectors, PSTAR/depth-charge lookup, and
  charge/current/depth matching, then remove one nuisance axis at a time. ML: train waveform,
  hand-shape, PCA/latent, and adversarially residualized probes under leave-run-family-out folds
  with charge-only, depth-only, current-only, action-only, and shuffled-label sentinels. Metric:
  AUC/AP, purity at fixed efficiency, calibration ECE/Brier, nuisance-removal AUC loss, support
  drift, charge/depth composition shift, and ML-minus-traditional deltas with stratified
  run-block bootstrap CIs; no PID adoption without truth.
- **S05m — Correlated-floor projection coverage ledger.** Turn the S05d correlated timing-floor
  estimate into a coverage audit before it feeds two-ended timing, pile-up, PID, or energy
  projections. Traditional: freeze template-phase end-difference widths, hierarchical pair
  covariance, and transparent correlated-floor estimates, then ledger sigma68, full RMS, tail
  fraction, and interval coverage by pair, B2 topology, amplitude, saturation, q_template,
  lowering, anomaly, and run family. ML: freeze the S05d single-endpoint proxy and S05f/S05i
  covariance calibrators, refit only conformal/coverage layers, and run B2-feature knockout,
  topology-only, saturation-only, run-only, and shuffled-target controls. Metric:
  correlated-floor sigma, two-ended projection sigma68/full RMS, 68/95% interval coverage,
  interval width, tail coverage, support loss, and ML-minus-traditional deltas with pair/event
  run-block bootstrap CIs.
- **P13b — Rare-atom bootstrap promotion threshold.** Define minimum support, stability, and
  control-passing criteria before rare pulse atoms such as the S03f 54-event topology,
  saturation-boundary cells, delayed peaks, baseline excursions, or dropout subclasses can move
  from diagnostic observations to steering variables. Traditional: freeze transparent atom
  definitions from S03, S10, S16, P04, P07, P09, and P12, then compute effective sample size,
  bootstrap stability, exact-binomial tail bounds, and composition-balance diagnostics per atom.
  ML: calibrated density/support and harm-risk models over the same atoms with
  leave-run-family-out validation plus run-only, amplitude-only, topology-only, and
  shuffled-atom sentinels. Metric: promotion/pass/defer rate, effective sample size, CI width for
  timing sigma68/tail, charge res68/bias, pile-up excess, q_template shift, support-score
  coverage/ECE, false-promotion rate under controls, and ML-minus-traditional deltas with
  stratified run-block bootstrap CIs.

Current steering pass (2026-06-10): the exact requested `tn-ticket list testbeam` command still
reports `open=11 claimed=0 done=0 failed=14`, below the 18-ready trigger, while the correctly
addressed local `testbeam` project queue remains deep (`open=187 claimed=3 done=205 failed=7`)
after appending this batch. Four more ready, non-duplicate `project:testbeam` tickets were cut to
turn the newest S03/S14 reports into support gates rather than premature production corrections:
S03m (`1781056870.436.378a461c`), S03n (`1781056877.507.6c6921d4`), S14h
(`1781056885.578.73172123`), and S06c (`1781056892.649.4cbb3cd2`).

- **S03m — Run-64 timewalk transfer action bands.** Convert the S03g run-64 drift diagnostic
  into explicit pass, abstain, or recalibrate bands for S03 timing corrections before waveform,
  pile-up, PID, or energy consumers reuse corrected times. Traditional: freeze S03a analytic,
  monotone-binned, S03e population, and S03f run-level shared-bin corrections and score per-run
  and per-amplitude-bin sigma68, bias, bias-vs-amplitude slope, q_template shift, and tail
  movement with run 64 held out. ML: train guarded ridge/HGB residual correctors with train-only
  run-family summaries and calibrate action/support scores with run-family holdout, shuffled
  target, run-label permutation, and amplitude-only sentinels. Metric: action coverage, sigma68
  and tail deltas, run64-minus-analysis delta, bias slope, q_template shift, sentinel false-pass
  rate, and ML-minus-traditional deltas with run-block bootstrap CIs.
- **S03n — Hierarchical timewalk coefficient atom attribution.** Explain which stave, amplitude,
  topology, and pulse-shape atoms drive the S03e/S03f hierarchical gains and whether those atoms
  are physically plausible rather than support leakage. Traditional: frozen leave-one-atom and
  grouped-coefficient ablations across analytic, monotone-binned, population, and run-level
  shared-bin corrections with coefficient signs, monotonicity, support counts, and residual bias
  per atom. ML: leakage-guarded ridge/HGB residual attribution with permutation/SHAP-style
  rankings plus run-only, amplitude-only, topology-only, and shuffled-residual controls. Metric:
  per-atom sigma68/tail/bias contribution, coefficient stability, monotonicity violation rate,
  support-weighted attribution rank, control false-attribution rate, and ML-minus-traditional
  deltas with run-block bootstrap CIs.
- **S14h — Sparse A-stack energy-proxy support calibration.** Map where the S14c external energy
  proxy is supported enough for ordering or PID covariates and where sparse A-stack coincidences
  require abstention. Traditional: freeze observed, traditional, and ML energy proxies, tabulate
  A-stack match fraction, A-depth support, downstream multiplicity, current, saturation, dropout,
  and baseline-excursion strata, and derive transparent support thresholds from exact-binomial and
  run-block uncertainty. ML: calibrated support/proxy-error models with domain-residualized
  features, leave-run-family-out validation, and shuffled-target, charge-only, topology-only, and
  current-only sentinels. Metric: support coverage, abstention rate, proxy Spearman/RMSE, A-depth
  high-minus-low contrast, downstream contrast, PID-score stability, false-support rate, and
  ML-minus-traditional deltas with stratified run-block bootstrap CIs.
- **S06c — Timewalk-energy support closure after action bands.** Test whether sigma(A) or
  sigma(E) remains stable after current timing, saturation, dropout, baseline, and energy-support
  action bands. Traditional: combine frozen analytic/template timing corrections with transparent
  charge-energy bins and the current veto ladder, then measure sigma68, RMS, tail fraction, and
  bias-vs-amplitude/energy in run-held-out strata. ML: calibrated per-pulse timing-uncertainty
  and support models over waveform, charge, and action-band features with leave-run-family-out
  validation plus action-shuffle, energy-shuffle, and topology-only controls. Metric:
  sigma68(A/E), full RMS, tail fraction, pull width, coverage, accepted-support composition,
  bias slope, control false-closure rate, and ML-minus-traditional deltas with run-block and
  atom-stratified bootstrap CIs.

Current steering pass (2026-06-10): the exact requested `tn-ticket list testbeam` command still
reports `open=11 claimed=0 done=0 failed=14`, below the 18-ready trigger, while the correctly
addressed local `testbeam` project queue remains deep (`open=187 claimed=4 done=208 failed=7`)
after appending this batch. Four more ready, non-duplicate `project:testbeam` tickets were cut to
turn the newest timing, geometry/PID, anomaly, and overlap reports into atom-level support gates:
S03o (`1781058292.515.16756522`), S14i (`1781058292.529.4efe2d6e`), P09i
(`1781058292.535.650c13f1`), and P05e (`1781058292.614.2d602ee2`).

- **S03o — Run-61 heavy-tail support exclusion gate.** Decide whether the run-61-like
  heavy-tail timewalk gain survives when candidate support atoms are excluded from training and
  tested as a blinded transfer set. Traditional: freeze analytic amp-only timewalk plus
  run-level hierarchical shrinkage, then reuse coefficients under leave-support-family-out
  deployment with no waveform features. ML: leakage-audited HGB residual corrector with
  feature-family ablations trained without candidate heavy-tail atoms and calibrated on untouched
  runs. Metric: sigma68, full RMS, 95th-percentile absolute residual, coefficient drift, and
  tail-fraction delta on the excluded support with run-block bootstrap CIs.
- **S14i — Material-budget PID label uncertainty bridge.** Quantify how much S14d
  material-budget and geometry envelopes destabilize weak PID/action labels for P08 consumers.
  Traditional: PSTAR/range-energy lookup over geometry/material variants with conservative
  PID/action bands and abstention regions. ML: monotonic gradient-boosted or quantile surrogate
  using charge, depth, topology, and geometry nuisance draws while preserving held-out-run
  calibration. Metric: PID band purity/efficiency proxy, abstention fraction, action-band flip
  rate, and energy-ordering violation rate with material-budget plus run-block bootstrap CIs.
- **P09i — Broad-width reviewer-disagreement propagation.** Test whether broad-width anomaly
  cases where P09c/P09d reviewers or methods disagree produce measurable timing, charge,
  pile-up, or baseline biases downstream. Traditional: q_template/width/tail-fraction cuts
  stratified by held-out run, stave, amplitude, and reviewer agreement. ML: PCA/AE/isolation/RF
  broad-mismatch score calibrated on held-out runs with reviewer-disagreement as a nuisance label.
  Metric: curated broad precision, reviewer-disagreement rate, timing sigma68 shift, charge-res68
  shift, pile-up excess shift, and baseline-lowering enrichment at fixed coverage with stratified
  bootstrap CIs.
- **P05e — Baseline-overlap negative-control lattice.** Determine when baseline excursions and
  pretrigger contamination mimic two-pulse overlap in P05/S10/S11 candidates and whether recovery
  models reject those false positives without losing true injected overlap. Traditional:
  constrained two-pulse template fit plus matched pretrigger-lowering and baseline-excursion
  controls at fixed amplitude and topology. ML: calibrated overlap/CNN score with
  baseline-excursion nuisance calibration and residualized pretrigger controls. Metric:
  injected-overlap AP, real-candidate secondary-fraction delta, false-positive rate on baseline
  controls, recovered-time RMS, and charge-bias/res68 at fixed coverage with stratified run-block
  bootstrap CIs.

Current steering pass (2026-06-10): the exact requested `tn-ticket list testbeam` command still
reports `open=11 claimed=0 done=0 failed=14`, below the 18-ready trigger. The correctly addressed
local `testbeam` project queue remains deep after this pass (`open=184 claimed=4 done=219
failed=7`) while workers continue closing tickets. The trigger was satisfied by appending four
ready, non-duplicate `project:testbeam` tickets focused on the newest timing, pretrigger,
tail-shape, and charge-transfer gaps: S02j (`1781061044.485.7c697079`), S02k
(`1781061052.556.26992c81`), P11b (`1781061059.627.4bc647a3`), and P10j
(`1781061067.698.6c8a6921`).

- **S02j — ROOT-only rate-proxy falsification ledger.** After S02f/S02g found no external scaler
  files and no timing improvement from current/rate drift terms, decide which ROOT-only
  trigger-density or event-order proxies are legitimate nuisances versus shuffled-control
  artifacts for Sample-II timing closure. Traditional: freeze the S02b global/template and S02f
  binned timewalk branches, construct transparent pre-timing event-density, run-local event-order,
  selected-pulse-density, stave-occupancy, and topology-count proxies, then add one proxy family
  at a time under leave-one-run-out folds with shuffled-proxy and run-label-permutation controls.
  ML: guarded ridge/HGB residual correctors on the same proxy families with waveform, event id,
  downstream timing labels, and held-out-run rows excluded, plus proxy-knockout, topology-only,
  amplitude-only, run-only, and shuffled-target sentinels. Metric: per-run sigma68, full RMS,
  >5 ns tail fraction, bias-vs-amplitude slope, false-improvement rate under controls, and
  ML-minus-traditional deltas with run-block and pair bootstrap CIs.
- **S02k — High-risk timing atom handoff table.** Convert the S02e high-risk timing output into
  atom labels before S03/S04/S10 consumers reuse it. Traditional: freeze q_template RMSE/abs
  difference, charge-pair matching, amplitude/log-amp delta, width, late-fraction, stave, run,
  and topology tables, then build an auditable handoff table for delayed-peak, broad-late,
  low-charge-pair, and common-shape atoms. ML: run-held-out calibrated atom classifier using only
  18-sample shape summaries and P09 taxonomy features, with charge-only, topology-only, run-only,
  q_template-only, and shuffled-risk sentinels. Metric: atom prevalence, tail precision/enrichment,
  tail rate after exclusion, kept-pair fraction, max-pair-share concentration, downstream
  sigma68/tail delta, and ML-minus-traditional deltas with event-paired run-block bootstrap CIs.
- **P11b — Pretrigger atom charge-transfer gate.** Test whether P11a pretrigger atoms such as
  adaptive_lowering and spike predict charge-transfer harm after matching amplitude, saturation,
  dropout, and run family, or only label baseline excursions with no independent charge
  consequence. Traditional: freeze P11a atom definitions, P04 peak/integral/Huber/template charge
  estimators, P07 saturation flags, dropout/anomaly taxa, and run-family support bins, then compare
  matched charge res68, signed bias, tail-bias rate, and support loss per atom. ML: run-held-out
  calibrated charge-harm and support models from pretrigger summaries plus 18-sample waveform
  atoms, with pretrigger-knockout, saturation-only, dropout-only, amplitude-only, run-only, and
  shuffled-harm controls. Metric: charge res68/bias, charge-bias-tail rate, support coverage,
  abstention harm reduction, saturation-boundary residual delta, calibration ECE/coverage, and
  ML-minus-traditional deltas with stratified event/run-block bootstrap CIs.
- **P10j — Tail-surrogate live-time control atlas.** Locate where learned P10f tail surrogates
  improve q/tail reconstruction while failing live-time or pile-up transfer controls, and convert
  those regions into accept, diagnostic-only, or veto labels. Traditional: freeze empirical
  amplitude-binned templates, explicit timewalk terms, asymmetric tails, and measured
  live-time/secondary-fraction tables, then stratify tail MSE, q_template shift, live10/tau_eff
  shift, and secondary-fraction delta by amplitude, peak phase, q_template, saturation, baseline,
  dropout/anomaly, and run family. ML: freeze P10f learned tail surrogate scores and recalibrate
  only action/support layers under leave-run-family-out validation with tail-knockout,
  amplitude-only, run-only, shuffled-live-time, and shuffled-current sentinels. Metric: q MSE,
  tail MSE, timing sigma68, live10/tau_eff delta, high-minus-low secondary-fraction delta,
  accepted support fraction, control false-pass rate, and ML-minus-traditional deltas with
  event-paired run-block bootstrap CIs.

Current steering pass (2026-06-10): the exact requested `tn-ticket list testbeam` command still
reports `open=11 claimed=0 done=0 failed=14`, below the 18-ready trigger. The correctly addressed
local `testbeam` project queue remains deep after this pass (`open=185 claimed=4 done=222
failed=7`) under concurrent worker movement. The trigger was satisfied by appending four ready,
non-duplicate `project:testbeam` tickets focused on the newest timing-transfer, pretrigger,
covariance, A-stack charge, and consumer-harm gaps: S03p (`1781062439.500.63591f99`), S05n
(`1781062443.571.1e7346af`), P04t (`1781062449.642.488b2d5f`), and P12e
(`1781062454.713.242b3d71`). The newest S14d range-order preflight also reproduced the P04c A/B
table but left selected-A charge broad (traditional res68 0.3541, ML 0.3602), so P04t's
topology-specific lower bounds and S14i's material/PID uncertainty bridge remain the correct next
energy/PID atoms rather than a global range-energy calibration claim.

- **S03p — HGB transfer feature-leakage null grid.** Test whether the blind Sample-I to
  Sample-II HGB timewalk gain survives family-by-family feature removal, pretrigger exclusion,
  and run-family sentinels. Traditional: signed inverse-amplitude and S03a analytic comparators
  under identical exclusions. ML: HGB residual correction with feature-dropout, shuffled-target,
  run-only, and pretrigger-free nulls. Metric: held-out sigma68, full RMS, tail fraction, and
  ML-minus-traditional deltas with run-block bootstrap CIs.
- **S05n — Pretrigger-atom covariance projection stress.** Decide whether the B-stack correlated
  timing floor remains a common covariance term after P11a pretrigger atoms, saturation, topology,
  and anomalies are conditioned out. Traditional: hierarchical covariance decomposition with
  explicit atom strata. ML: calibrated ensemble variance model over waveform/pretrigger/topology
  atoms under held-out run families. Metric: common-covariance fraction, projected two-ended
  sigma68, pull width, and calibration deltas with run-block bootstrap CIs.
- **P04t — A-stack topology lower-bound charge transfer.** Quantify the best achievable
  A-charge transfer precision separately for A1-only, A3-only, and A1A3 topologies once support
  atoms are fixed. Traditional: topology medians, log-charge ridge, and robust Huber transfer.
  ML: topology-specific ExtraTrees/HGB waveform transfer with support abstention and shuffled
  targets. Metric: fractional res68, median bias, RMS, within-10% coverage, and topology/run-block
  bootstrap CIs.
- **P12e — Cross-consumer pulse-atom harm ledger.** For each pulse atom and action band, measure
  which downstream consumers are helped or harmed across timing, charge, saturation, pile-up,
  baseline, PID, and energy. Traditional: deterministic q_template, amplitude, pretrigger,
  saturation, dropout, and anomaly action rules. ML: calibrated multi-output harm predictor on
  held-out-run outcomes with shuffled-label controls. Metric: per-consumer harm rate, net utility
  at fixed coverage, conflict rate, and ML-minus-rule utility deltas with event/run-block
  bootstrap CIs.

Current steering pass (2026-06-10, S11e/S07g/S13d/P04h layer): the exact requested
`tn-ticket list testbeam` command still reports `open=11 claimed=0 done=0 failed=14`, below the
18-ready trigger. The correctly addressed local `testbeam` project queue remains deep after this
pass (`open=183 claimed=2 done=230 failed=7`) under concurrent worker movement. The trigger was
satisfied by appending four ready, non-duplicate `project:testbeam` tickets focused on the newest
all-three pile-up, shape-localization, current-support, and A-stack charge-identifiability gaps:
S11h all-three delay-scale recovery frontier (`1781063906.413.7e4c6b5c`), S07m
charge-preserved shape-cue localization (`1781063920.486.09951fba`), S13f exactly-two
current-family timing-tail null (`1781063920.513.7c742542`), and P04u A-stack shuffled-sentinel
root cause (`1781063920.599.196428b2`). The newest S11e full bounded fit confirms that
fit-output-only scoring remains interpretable but weak on the S07f all-three injected target
(AUC 0.608 versus shape RF 0.826), while S07g shows the RF survives both peak and positive-charge
preservation. S13d makes the all-three high-rate timing-tail contrast a null/support result after
matching, and P04h shows A-stack charge transfer is indistinguishable from shuffled target at the
global support level. The new tickets therefore split those reports into smaller pulse atoms:
delay/scale recovery thresholds, charge-preserved sample cues, exactly-two topology support, and
real-minus-shuffled A-stack charge identifiability.

- **S11h — All-three delay-scale recovery frontier.** Locate the delay-by-secondary-scale cells
  where S07f/S07g injected pile-up is actually recoverable, and where the shape RF beats the full
  bounded two-pulse fit after peak and charge preservation. Traditional: train-run-only constrained
  one-vs-two pulse template fits with fold-local secondary-fraction, fractional-SSE, delay, and
  chi2/ndf thresholds. ML: leakage-audited shape-only RF with isotonic calibration and amplitude,
  topology, shuffled-label, and pair-split sentinels. Metric: per-cell AUC, AP, fixed-95%-clean
  rejection, recovered delay bias/RMS, and failure rate with run-block bootstrap CIs.
- **S07m — Charge-preserved shape-cue localization.** Identify which normalized waveform samples
  and shape atoms carry the all-three RF signal after peak and charge preservation. Traditional:
  q_template residual windows, late/early charge ratios, derivative sign changes, and transparent
  peak/tail cuts. ML: shape-only RF with grouped sample-window dropout/permutation and sparse
  logistic probes, excluding timing, amplitudes, ids, topology, and injection parameters. Metric:
  AUC/AP loss, fixed-efficiency rejection loss, and fold-stability rank correlations with
  run-block bootstrap CIs and null-window controls.
- **S13f — Exactly-two current-family timing-tail null.** Test whether S13d's all-three current
  null is a topology-support artifact by repeating the matched high-rate versus low-edge contrast
  on exactly-two-downstream rows. Traditional: calibrated curvature and transparent
  timing/template tail scores. ML: amplitude-normalized waveform RF and residualized CWoLa probe
  with run, current, timing-label, amplitude, and topology leakage excluded. Metric: high-minus-low
  tail-score delta, current-family AUC, fixed-efficiency enrichment, and matched support with
  held-out run-pair bootstrap CIs.
- **P04u — A-stack shuffled-sentinel root cause.** Explain why P04h A-stack charge transfer tracks
  shuffled target and search for any raw-ROOT support atom with real-versus-shuffled separation.
  Traditional: B2 log-linear, peak/integral/topology ridge, and adaptive-template ridge baselines
  stratified by run, topology, A stave, event matching, saturation, and anomaly. ML: ExtraTrees/RF
  waveform regressors with target permutation, knockoff B-waveform controls, and conformal residual
  calibration. Metric: real-minus-shuffled res68 delta, within-25% coverage, coverage68, and bias
  by stratum with leave-one-run-out run-block bootstrap CIs.

Current steering pass (2026-06-10, P10c/P04f/S11e/S07g layer): the exact requested
`tn-ticket list testbeam` command still reports `open=11 claimed=0 done=0 failed=14`, below the
18-ready trigger. The correctly addressed local `testbeam` project queue remains deep after this
pass (`open=183 claimed=4 done=232 failed=7`) under concurrent worker movement. The trigger was
satisfied by appending four ready, non-duplicate `project:testbeam` tickets focused on the newest
calibration portability, duplicate-charge tail, bounded-fit calibration, and external-charge
abstention gaps: S03q run64-only calibration acceptance gate (`1781065299.451.065636a1`),
P04v duplicate-closure tail-risk ledger (`1781065299.478.126968ef`), S11i bounded-fit score
calibration audit (`1781065299.555.20535839`), and P04w external-charge abstention frontier
(`1781065299.620.6b5f516e`). P10c-followup shows mixed Sample-I plus run64 calibration worsens
Sample-II timing relative to run64-only for analytic, binned, and ML timewalk corrections.
P04f shows duplicate-readout ML closure is extremely sharp in res68 but still needs rare-tail
accounting before charge feeds saturation, PID, or energy. S11e/S07g show the bounded two-pulse
fit remains interpretable but weak compared with the charge-preserved shape RF, while external
charge transfer remains support-limited. The new tickets split these into acceptance, tail-risk,
calibration, and abstention atoms.

- **S03q — Run64-only calibration acceptance gate.** After P10c-followup showed Sample-I plus
  run64 calibration worsens Sample-II timing relative to run64-only, identify the exact
  run/stave/amplitude/shape atoms where run64-only timewalk calibration is acceptable versus
  diagnostic-only. Traditional: freeze S03a/S02b analytic amp-only and monotone-binned timewalk
  fits trained on run64-only calibration, then evaluate atom-stratified held-out sigma68, full
  RMS, bias-vs-amplitude, and tail fraction with no waveform features. ML: leakage-audited
  HGB/ridge residual correctors trained on the same run64-only rows with feature-family
  knockouts, shuffled-target, run-only, and mixed-calibration sentinels. Metric:
  ML-minus-traditional sigma68/full-RMS/tail deltas, accepted support fraction, false-accept rate
  under shuffled/mixed controls, and per-atom run-block bootstrap CIs.
- **P04v — Duplicate-closure tail-risk ledger.** Decide which pulse atoms drive the remaining
  full-RMS and rare charge failures in the otherwise strong P04f duplicate-readout closure before
  duplicate charge is reused by saturation, PID, or energy studies. Traditional: freeze peak,
  integral, adaptive-template, Huber, ridge, and residual-basis duplicate calibrators, then
  stratify high-error tails by run, stave, peak phase, saturation, q_template, dropout/anomaly,
  and pretrigger atoms. ML: ExtraTrees/HGB residual and conformal tail-risk models on the same
  even-waveform features with target permutation, atom knockouts, and run-family holdout. Metric:
  charge res68, full RMS, >10% and >25% tail rates, conformal coverage, accepted support
  fraction, and ML-minus-traditional tail-risk deltas with event/run-block bootstrap CIs.
- **S11i — Bounded-fit score calibration audit.** Test whether the interpretable bounded
  two-pulse fit outputs from S11e can be calibrated into reliable abstention or recovery scores
  even though their raw injected AUC is weaker than the shape RF. Traditional: use train-run-only
  constrained one-vs-two template fits and calibrate chi2/ndf, fractional SSE, recovered delay,
  secondary scale, and residual-tail scores against injected truth under peak-preserved and
  charge-preserved injections. ML: isotonic/logistic/ExtraTrees calibration layers over the same
  fit-output variables plus shape RF residuals, with fit-output-only, shape-only, shuffled-label,
  amplitude-only, and topology-only sentinels. Metric: calibrated AUC/AP, ECE, Brier score,
  fixed-95%-clean rejection, recovered delay/charge bias at accepted coverage, and
  ML-minus-traditional deltas with run-block bootstrap CIs.
- **P04w — External-charge abstention frontier.** After P04e/P04h/P04u show external A/B charge
  transfer is broad or shuffled-like, determine whether any abstention frontier lets B-stack
  waveform charge safely support downstream energy/PID labels. Traditional: robust log-charge
  ridge/Huber and topology medians with explicit support cuts on topology, saturation, peak
  phase, anomaly, q_template, and run family. ML: ExtraTrees/HGB waveform transfer plus conformal
  abstention and real-minus-shuffled sentinels, excluding target staves and event identifiers
  under leave-one-run-out validation. Metric: external-charge res68, median bias, full RMS,
  within-10/25% coverage, real-minus-shuffled separation, accepted support fraction, and
  topology/run-block bootstrap CIs.

Current steering pass (2026-06-10, P10e/P10g/P10f/S03h layer): the exact requested
`tn-ticket list testbeam` command still reports `open=11 claimed=0 done=0 failed=14`, below the
18-ready trigger. The correctly addressed local `testbeam` project queue remains deep after this
pass (`open=181 claimed=4 done=238 failed=7`) under concurrent worker movement. The trigger was
satisfied by appending four ready, non-duplicate `project:testbeam` tickets focused on the newest
template-drift, HGB-leakage, B2-inclusive timing, and peak-phase coupling gaps: S03r stave-only
HGB leakage dissection (`1781066704.631.13c7784e`), P10k minority-stave conditional-template
failure map (`1781066704.689.2f5f3d2a`), S04h B2-inclusive all-hit timing closure harm map
(`1781066704.724.5080332a`), and P06d peak-phase charge-timing coupling atlas
(`1781066704.794.27df492e`). P10e shows explicit handles still fail to rescue q-space under both
family holdouts while CFD and peak-sample distributions drift strongly between Sample-I and
run64. P10g shows no supported per-run or per-stave conditional-template ML win, with the worst
failures in minority B4/B6/B8 support. The newest P10f same-pulse leakage stress test separates
full CFD/shape/tail ExtraTrees from shuffled controls without hash or exact-nearest-neighbor
overlap, but the cross-family empirical-template gain is not CI-stable in every fold and the
amplitude-only ablation remains the conservative reference. The paired P10f run64-only external
closure still does not improve B2-inclusive all-hit timing closure. S03h finds HGB timewalk gains
in several support atoms, but the stave-only sentinel is nearly as strong as the full model and
the report raises a leakage flag. The new tickets split those reports into smaller atoms before
q_template, timing, charge, saturation, dropout, pile-up, PID, or energy consumers reuse the
outputs.

- **S03r — Stave-only HGB leakage dissection.** Decide whether the S03h HGB timewalk gain is a
  real pulse-shape/timing improvement or a stave/support confound. Traditional: freeze S03a
  amp-only, signed shared-shrinkage, and robust heavy-tail tables, then rerun leave-run-out atom
  tables with stave labels blinded, single-stave-only fits, and matched amplitude, q_template,
  pretrigger, and anomaly support. ML: HGB/ridge residual correction with feature-family
  knockouts for stave, peak phase, pretrigger, q_template, saturation, and anomaly atoms plus
  stave-only, run-only, shuffled-target, and support-excluded sentinels. Metric: sigma68, full
  RMS, |residual|>5 ns tail fraction, bias-vs-log-amplitude slope, false-gain rate under
  sentinels, and ML-minus-traditional deltas with held-out-run bootstrap CIs.
- **P10k — Minority-stave conditional-template failure map.** Explain why P10g conditional
  templates fail especially on B4/B6/B8 and whether the P10f same-pulse handle gains are support,
  peak phase, saturation boundary, dropout/anomaly, or q_template drift rather than a portable
  model class. Traditional: freeze S01 empirical templates and per-stave/peak-phase/q_template
  residual tables, then compare empirical, mean-template, and explicit-handle binned templates
  under family-heldout support.
  ML: conditional ridge/ExtraTrees templates with per-feature dropout, density/support
  calibration, and shuffled-template, run-family, stave-only, and amplitude-only sentinels.
  Metric: residual MSE, q_template shift, timing-fit sigma68 shift, minority-stave false-support
  rate, accepted support fraction, and ML-minus-empirical deltas with run-block bootstrap CIs.
- **S04h — B2-inclusive all-hit timing closure harm map.** Test whether adding B2-inclusive
  all-hit topology to external timing closure helps any supported atom or systematically harms
  closure. Traditional: freeze S02b/S03a analytic timewalk and P10c empirical explicit-handle
  corrections, then compare B2-excluded and B2-inclusive pairwise residuals by topology,
  amplitude, peak phase, saturation, baseline, dropout/anomaly, and run family. ML: ridge/HGB
  residual correction on train-run-only features with B2-blinded, topology-only, run-only,
  shuffled-target, and target-stave-excluded controls. Metric: all-six pairwise sigma68,
  downstream-only sigma68, full RMS, tail fraction, accepted topology support, B2-inclusion harm
  delta, and ML-minus-traditional deltas with held-out-run bootstrap CIs.
- **P06d — Peak-phase charge-timing coupling atlas.** Determine whether peak-sample and CFD-phase
  shifts are a common atomic cause of timing residuals, charge bias, saturation-boundary errors,
  and dropout/anomaly decisions. Traditional: freeze CFD/template timing, P04/P07 charge
  estimators, q_template, and anomaly/dropout flags, then tabulate matched peak-phase bins with
  amplitude, saturation, pretrigger, and run-family controls. ML: calibrated multi-output
  HGB/ExtraTrees models for timing residual, charge residual, saturation harm, and anomaly/dropout
  risk with peak-phase dropout and amplitude-only, run-only, topology-only, and shuffled-target
  sentinels. Metric: sigma68/full-RMS timing delta, charge res68/bias delta, saturation-boundary
  residual delta, dropout/anomaly enrichment, calibration ECE, and ML-minus-traditional deltas
  with event-paired run-block bootstrap CIs.

Current steering pass (2026-06-10, P10h/P05b/S11d/S07j/P12a layer): the exact requested
`tn-ticket list testbeam` command still reports `open=11 claimed=0 done=0 failed=14`, below the
18-ready trigger. The project-aware `testbeam` queue remains deep after this pass
(`open=179 claimed=3 done=247 failed=7`) under concurrent worker movement. The trigger was
satisfied by appending four ready, non-duplicate `project:testbeam` tickets focused on
tail-handle phase drift, two-pulse risk coverage, joint pulse-axis stability, and normalized
shape-cue nulls: P10l tail-handle phase-drift null (`1781068158.1584.4e8d411c`), P05f
two-pulse risk-coverage sideband map (`1781068159.1612.2426717d`), P12f joint pulse-axis
prevalence bootstrap (`1781068159.1620.18d0289d`), and S07n normalized shape-cue charge null
(`1781068159.1658.5f900b07`). P10h/P10e/P10f show explicit handles can separate from shuffled
controls while still failing portable cross-family claims; P05b/S11d/S11e keep pile-up recovery
coverage and charge bias method-dependent; P12a shows joint pulse axes are common enough to need
bootstrap promotion rules; and S07j/S07m require a stricter charge-normalization null before
shape RF cues are interpreted as pulse morphology.

- **P10l — Tail-handle phase-drift null.** Decide whether P10h/P10e explicit tail and CFD handle
  failures are caused by phase-distribution drift between run families or by intrinsic
  conditional-template instability after amplitude and q_template support are matched.
  Traditional: freeze S01 empirical templates plus explicit CFD/peak-phase/tail residual tables,
  then match by amplitude, stave, q_template, saturation, anomaly, and run family while scanning
  one handle family at a time. ML: ridge/ExtraTrees conditional template residual models with
  handle dropout, phase-shuffled, run-family-only, amplitude-only, and shuffled-target sentinels.
  Metric: q_template MSE, tail MSE, timing sigma68/full RMS, live10 shift, accepted support
  fraction, false-pass rate under sentinels, and ML-minus-traditional deltas with run-block
  bootstrap 95% CIs.
- **P05f — Two-pulse risk-coverage sideband map.** Locate where P05b/P05c/S11i two-pulse
  abstention scores trade coverage for recovery quality across secondary-amplitude sidebands,
  delay cells, baseline state, and saturation support. Traditional: frozen bounded template fit
  with chi2, fractional-SSE, recovered-delay, and secondary-scale thresholds, tabulated by
  injected and real high-current sidebands. ML: calibrated CNN/RF/isotonic failure scores using
  the same cells with amplitude-only, topology-only, baseline-only, shuffled-label, and
  real-current transfer controls. Metric: accepted coverage, bad-recovery rate, recovered-time
  RMS, charge fractional bias/res68, sideband calibration ECE, fixed-risk support fraction, and
  ML-minus-traditional deltas with run-block bootstrap 95% CIs.
- **P12f — Joint pulse-axis prevalence bootstrap.** Determine which joint combinations of P12a
  pulse axes are common and stable enough to steer downstream timing, charge, saturation,
  pile-up, baseline, dropout, PID, or energy decisions, rather than being rare coincidental
  overlaps. Traditional: freeze transparent P12a axes and compute joint prevalence, effective
  sample size, partial correlations, and atom-wise outcome deltas with exact-binomial and
  stratified bootstrap uncertainty. ML: calibrated density/support and multi-output harm models
  over the same joint axes with run-family holdout, axis-knockout, run-only, amplitude-only,
  topology-only, and shuffled-axis sentinels. Metric: joint prevalence, effective sample size,
  timing tail enrichment, charge error enrichment, pile-up score delta, support coverage/ECE,
  false-promotion rate, and ML-minus-traditional deltas with run-block bootstrap 95% CIs.
- **S07n — Normalized shape-cue charge null.** Test whether the S07j/S07m all-three injected
  pile-up shape cues remain after stricter residual charge normalization or vanish as
  amplitude-renormalization artifacts. Traditional: q_template-window, early/late ratio,
  derivative-sign, and peak-tail cuts evaluated under peak-preserved, positive-charge-preserved,
  area-preserved, and charge-pair-matched injections. ML: shape-only RF/logistic probes with
  grouped sample-window dropout and permutation, excluding timing, amplitude, topology, ids, and
  injection parameters, plus charge-null and shuffled-label controls. Metric: AUC/AP,
  fixed-95%-clean rejection, charge-null AUC loss, sample-window rank stability, support drift,
  and ML-minus-traditional deltas with run-block bootstrap 95% CIs.

Current steering pass (2026-06-10, S14d/S04d/P04j/P10h layer): the exact requested
`tn-ticket list testbeam` command still reports `open=11 claimed=0 done=0 failed=14`, below the
18-ready trigger. The project-aware `testbeam` queue remains deep after this pass
(`open=179 claimed=5 done=249 failed=7`) under concurrent worker movement. The trigger was
satisfied by appending four ready, non-duplicate `project:testbeam` tickets focused on raw-only
PID falsification, pathology-interaction veto calibration, retained charge-interval support, and
energy-claim red-team controls: S15b raw-HRD PID proxy falsification ledger
(`1781069565.648.74687e98`), S04j pathology-interaction calibrated veto transfer
(`1781069571.719.463e18dd`), P04x retained-support charge-interval calibration
(`1781069576.790.606924bd`), and S14j raw-only energy claim red-team ledger
(`1781069585.861.56193204`). S14d reproduces the S00/S14b gate and makes the missing external
requirements for proton energy explicit; S04d finds real pathology interactions but warns that
they are not a timing-correction shortcut; P04j shows conformal A-stack charge intervals are
calibrated only by being broad and support-limited; P10h keeps explicit-handle template gains
promotable only under sentinel-audited support. The new tickets keep the pulse programme atomic
before shape, timing, amplitude, saturation, pile-up, baseline, dropout, PID, or energy consumers
reuse any of those outputs.

- **S15b — Raw-HRD PID proxy falsification ledger.** Test whether any raw HRD pulse atoms carry
  PID-like information beyond penetration depth, charge, run family, saturation, and topology
  proxies. Traditional: transparent DeltaE-E, stopping-depth, charge-ratio, tail/total, and
  penetration-depth cuts matched by run, topology, saturation, anomaly, and external-charge
  support. ML: calibrated waveform/charge RF or HGB PID-proxy classifiers with run-only,
  topology-only, depth-only, shuffled-label, target-permutation, and feature-knockout sentinels.
  Metric: proxy AUC/AP, fixed-purity efficiency, real-minus-sentinel separation, calibration ECE,
  accepted support fraction, and ML-minus-traditional deltas with run-block and topology-block
  bootstrap 95% CIs.
- **S04j — Pathology-interaction calibrated veto transfer.** Convert the S04d interaction ledger
  into a support-preserving timing-tail veto/harm table, or prove it cannot transfer. Traditional:
  additive factorial interaction tables and transparent thresholds on pretrigger lowering,
  dropout/jagged, broad-late, saturation, q_template, and anomaly axes. ML: calibrated sparse-logit
  and shallow-tree tail-risk models with axis knockouts, run-only, amplitude-only, topology-only,
  and shuffled-axis sentinels. Metric: sigma68, full RMS, |residual|>5 ns tail fraction, veto
  coverage, composition drift, charge/pile-up proxy harm, calibration ECE, and ML-minus-traditional
  deltas with held-out-run bootstrap 95% CIs.
- **P04x — Retained-support charge-interval calibration.** Determine whether any P04j A-stack
  charge-transfer support cell has acceptable interval width, coverage, and real-minus-shuffled
  separation at the same time. Traditional: peak, integral, adaptive-template, topology-median,
  ridge, Huber, and support-cut charge predictors calibrated by run, topology, A-stave, B-stave,
  saturation, peak phase, dropout, and anomaly cells. ML: ExtraTrees/HGB waveform charge transfer
  with conformal residual calibration, width-ranked abstention, target permutation, run-family,
  topology-only, and shuffled-target sentinels. Metric: res68, full RMS, within-10/25% rates,
  coverage68/90, mean interval width, retained support fraction, real-minus-shuffled delta, and
  ML-minus-best-traditional deltas with run-block bootstrap 95% CIs.
- **S14j — Raw-only energy claim red-team ledger.** Stress the exact assumptions that could make
  an HRD-only range-energy or proton-energy claim appear valid despite missing material, geometry,
  Birks, PID, and stopping-depth truth. Traditional: S14b/S14d PSTAR depth-charge lookup,
  material/geometry envelope, duplicate-readout closure, and external-charge propagation with
  bounded nuisance scans and support cuts. ML: monotonic HGB/ridge energy-proxy models with
  ingredient-dropout, geometry-label, depth-only, run-family, topology-only, shuffled-target, and
  proxy-leakage sentinels. Metric: energy-proxy res68, median bias, geometry/material sensitivity
  span, support-abstention fraction, false-accept rate under missing-ingredient controls, and
  ML-minus-traditional deltas with run-block bootstrap 95% CIs.

Current steering pass (2026-06-10, S07j/S04d/S14d/P04j/P05b/P10h layer): the exact requested
`tn-ticket list testbeam` command reported `open=11 claimed=0 done=0 failed=14` before ticket
cutting and `open=12 claimed=0 done=0 failed=14` after, still below the 18-ready trigger. The
project-aware `testbeam` store remains deep after this pass (`open=183 claimed=4 done=250
failed=7`) under concurrent worker movement. The trigger was satisfied by appending four ready,
non-duplicate `project:testbeam` tickets: P06e dropout-phase timing irrecoverability frontier
(`1781070978.431.052370d7`), P11f overlapping-pulse baseline-reset confusion map
(`1781070978.435.149f11f5`), P07f saturation onset sample-window causal veto
(`1781070978.481.06412dbf`), and S15b pulse-shape PID null-label stability audit
(`1781070978.487.042a7300`). This S15b title is distinct from the earlier raw-HRD PID proxy
falsification ledger: the new ticket is specifically the null-label stability audit for
waveform/charge-shape PID weak labels.

Fresh synthesis: S07j retires the historical App.A 12,147-row weak label unless a byte source is
found; raw HRDv CFD20 gives 9,897 labelled events instead, while shape RFs remain strong only as
sentinel-audited diagnostics. S04d finds calibrated pathology interactions can predict timing
tails but still need support-preserving veto transfer before use. S14d reproduces S00/S14b exactly
and shows raw HRD can support internal depth/charge ordering, but per-event energy remains blocked
by external material, geometry, Birks/light-yield, PID truth, and stopping-depth validation. P04j
shows charge-transfer conformal intervals are broad and support-limited; P05b shows two-pulse
abstention trades coverage, timing RMS, and bad-recovery rate; P10h keeps explicit template
handles support-qualified rather than globally adopted. The new tickets therefore isolate four
next atoms before pulse-shape, timing, amplitude, saturation, pile-up, baseline, dropout, PID, or
energy consumers reuse these outputs.

- **P06e — Dropout-phase timing irrecoverability frontier.** Find the 18-sample phase locations
  where dropout or jagged corruptions cannot be repaired for timing after matching amplitude,
  stave, peak sample, saturation, and anomaly taxon. Traditional: injected dropout masks repaired
  with rule-based jagged masks, interpolation, and template refits. ML: existing P06/P04g-style
  inpainting or denoising models with sample-location shuffles and amplitude/run sentinels.
  Metric: timing sigma68/RMS delta, bad-tail fraction, abstention coverage, and
  ML-minus-traditional harm by dropout phase with event-block bootstrap 95% CIs.
- **P11f — Overlapping-pulse baseline-reset confusion map.** Decide whether high-current
  two-pulse candidates are separable from baseline-reset or pretrigger contamination after
  matching amplitude, lowering, broad-late anomaly, saturation, run family, and topology.
  Traditional: frozen S10/S11 two-pulse template fits plus S16 lowering/pretrigger diagnostics
  and P09 taxa in matched contingency tables. ML: calibrated RF/HGB overlap classifiers with
  baseline-reset features held out/included and shuffled-current, pretrigger-only, and
  topology-only controls. Metric: secondary-fraction excess, overlap-score delta,
  baseline-reset enrichment, calibration ECE, and template-vs-ML disagreement with matched-block
  bootstrap 95% CIs.
- **P07f — Saturation onset sample-window causal veto.** Identify which rising-edge, peak, and
  early-tail windows drive saturation-recovery gains and boundary timing harms near B2 saturation
  onset. Traditional: template/rising-edge extrapolation with sequential sample-window exclusion
  and boundary shrink rules. ML: frozen GBR/ExtraTrees saturation recovery with grouped
  sample-window dropout/permutation, monotone boundary calibration, and run/stave/amplitude-only
  sentinels. Metric: artificial-clip res68, natural-boundary q_template shift, timing-tail delta,
  charge-bias delta, coverage, and ML-minus-traditional deltas with run-block bootstrap 95% CIs.
- **S15b — Pulse-shape PID null-label stability audit.** Before external PID truth exists, test
  whether waveform or charge-shape PID weak labels survive null relabellings, geometry/depth-only
  baselines, and matched saturation, dropout, baseline, and anomaly support. Traditional:
  penetration-depth and DeltaE-E-style band cuts matched across pulse-support strata. ML:
  waveform/latent classifiers with geometry-label, depth-only, run-only, topology-only,
  amplitude-only, and shuffled-target sentinels. Metric: purity-efficiency envelope against weak
  labels, null-label AUC/AP, calibration ECE, support-collapse fraction, and
  ML-minus-traditional lift with stratified bootstrap 95% CIs.

Current steering pass (2026-06-10, S07j/S03f/P02d/S10g/S14d layer): the exact requested
`tn-ticket list testbeam` command still reports `open=11 claimed=0 done=0 failed=14`, below the
18-ready trigger. The project-aware `testbeam` store remains deep after this pass
(`open=185 claimed=4 done=253 failed=7`) under concurrent worker movement. The trigger was
satisfied by appending four ready, non-duplicate `project:testbeam` tickets: S07o raw AppA
ambiguous-event timing definition lattice (`1781072388.635.3a971559`), P02f latent-distance
nearest-neighbor leakage audit (`1781072388.645.34b21955`), S14k quenching-free depth-charge
monotonicity falsifier (`1781072388.662.19181f8a`), and P08d depth-matched pulse-shape PID null
(`1781072388.710.65f565af`).

Fresh synthesis: S07j/S03f now make the App.A 12,147-row label a boundary-definition and
provenance problem: current raw HRDv CFD20 gives 9,897 labelled events, there are 5,457 ambiguous
downstream-ge2 events, q_template-only is too weak, and shape RFs remain diagnostic unless the
timing-definition boundary is reproduced without leakage. P02d provides a useful run-heldout
latent-distance artifact, but consumers need a nearest-neighbor and event-key leakage audit before
PID, anomaly, timing, or pile-up analyses use it. S10g keeps the current excess positive after
P09 anomaly matching while showing taxonomy changes the downstream excess, and S14d says raw HRD
can support only depth/charge monotonic structure until material, geometry, quenching, PID, and
stopping-depth truth exist. The new tickets therefore deepen the pulse at App.A timing-definition,
latent-neighbor, raw depth-charge, and PID-null atoms.

- **S07o — Raw AppA ambiguous-event timing definition lattice.** Decide whether the 5,457
  ambiguous raw HRDv downstream-ge2 events contain a reproducible timing-definition boundary that
  explains the documented 12,147 App.A labelled-event tuple. Traditional: transparent CFD
  fraction/window, downstream span, q_template, and curvature definition scans. ML: run-heldout
  calibrated RF on waveform shape, q_template, amplitude, and topology summaries, excluding run,
  event id, and label-defining timing spans, with q/shape ablations and shuffled-label controls.
  Metric: labelled-count tuple recovery, clean/violating balance, external non-tail AUC/AP, and
  timing-tail enrichment with run-block bootstrap 95% CIs.
- **P02f — Latent-distance nearest-neighbor leakage audit.** Test whether P02d's keyed
  run-heldout latent-distance artifact stays honest when consumed through nearest-neighbor and
  exemplar joins. Traditional: hand/PCA distances with run-heldout centroids, exact-neighbor
  duplicate checks, event-key overlap checks, and amplitude/stave-stratified null joins. ML:
  train-run-only AE latent distances in a calibrated downstream consumer with forbidden all-data
  latent and event-shuffled controls. Metric: manual-flag AMI/purity, peak-group AMI/purity,
  downstream delta, neighbor duplicate rate, and leakage sentinel score with run-block bootstrap
  95% CIs.
- **S14k — Quenching-free depth-charge monotonicity falsifier.** Strip absolute-energy language
  away and test only raw depth-charge monotonicity across penetration depth, saturation, anomaly,
  and topology strata. Traditional: penetration-depth ordered charge/template/P04 duplicate
  summaries, isotonic trend tests, and veto-ladder support tables. ML: monotonic HGB or
  isotonic-calibrated ensemble under run-heldout splits, with shuffled-depth and topology-only
  sentinels. Metric: Kendall/Spearman monotonicity, pairwise order violation rate, abstention
  coverage, duplicate-proxy res68, and external-proxy failure rate with run-block bootstrap 95%
  CIs.
- **P08d — Depth-matched pulse-shape PID null.** Test whether waveform shape retains any
  PID-like separation after matching penetration depth, charge, current, run family, saturation,
  and anomaly taxa. Traditional: depth-matched DeltaE-E and tail/total PSD bands with propensity
  weights and balance tables. ML: run-heldout calibrated waveform/latent classifier with
  charge-only, topology-only, and phase-scrambled controls. Metric: matched pseudo-PID AUC/AP,
  fixed-efficiency purity proxy, balance residuals, Brier calibration, and null-control lift with
  run-block bootstrap 95% CIs.
