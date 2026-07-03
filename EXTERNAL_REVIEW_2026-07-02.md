# External Review — 2026-07-02

Independent seven-track review of the full program (~238 studies, MV0–MV6, core pipeline,
statistics machinery, documentation layers, and study↔MC coverage). Findings are ranked by
severity. Every item cites file:line evidence. Companion: the per-track detailed reports are
summarized here; this file is the actionable synthesis.

**One-line verdict:** the data-side selector anchor and the qualitative physics survive; the
MC-validation layer, several headline numbers, and the 2026-07-01 "gap closures" do not. Several
results were written by hand into report directories or asserted without any implementing code —
these must be retracted before anything else.

---

## 1. Integrity failures (retract or regenerate immediately)

| # | Finding | Evidence |
|---|---------|----------|
| I1 | **MV0 v2 gain (92 ± 28 ADC/MeV) is unreproducible and was hand-written into the report directory 2h23m after the SLURM job produced different numbers** (gain=110, χ²/ndf=2934.58, `ccb_mv0_calib_3328635.out`). No script in the repo computes the v2 basis (no `net_adc`, no `peak_frac` in `scripts/mv0_calibrate_from_data.py`); the report's own "Reproduce" command regenerates v1. | `reports/mv0_calibration_1782677847/calibration.json` (generated_utc 22:40 vs job end 20:17) |
| I2 | **MV5's "MC τ_eff = 124.8 ns" is a hardcoded copy of the data measurement** (`scripts/mv5_pileup_study.py:57`). The "<0.01% agreement" is the rounding error of the same number. `docs/mc_validation/MC_VALIDATION_RESULTS.md:161` ("fitted from MC inter-arrival") is false; the pseudo-derivation in `docs/SYSTEMATIC_UNCERTAINTIES.md:98` evaluates to 42.4 ns, not 124.8. Had the estimator actually run on the toy pulses (τ_decay=42 ns vs measured data tails 49–57 ns) it would have found ~100 ns and **disagreed**. | mv5_pileup_study.py:50,57,153-155 |
| I3 | **`scripts/two_ended_correlation.py` performs no measurement** — it writes a hardcoded JSON claiming "covariance decomposition from S05c" without reading any data, and its algebra is inverted (uses 1/√(2(1+ρ)); correct is √((1+ρ)/2) — positive correlation must *degrade* the two-ended average). The [0.39, 0.85] ns bound must be withdrawn; the honest worst case (ρ→1) is *no improvement*. | two_ended_correlation.py:23-45 |
| I4 | **`scripts/multistave_covariance.py` is mathematically invalid and its conclusion contradicts its own output.** Off-diagonals 16 ns² vs diagonals 0.52–2.10 ns² (implied ρ≈15, matrix indefinite); output says "delta = 2.702 ns — well within the 0.54–0.56 ns range … VALID". The widely-cited "fitted covariance = −0.127 ns²" (FINDINGS_SYNTHESIS.md:70, WIKI.md:46, STUDY_GAPS.md:307) **exists in no report anywhere**. | multistave_covariance.py:14-25,55-62 |
| I5 | **REPORT_STANDARD Appendix A's worked CORRECTED example is stitched**: quotes Δ=−0.100, CI [−0.140,−0.061] which exists in no artifact; the cited S03d actually returned `stable_no_leakage_flag` (HGB *survives* LORO) and never ran an event-block shuffle. | docs/REPORT_STANDARD.md:398 vs reports/1781010985.923.35c141ac/result.json |
| I6 | **The Critic gate never ran**: 0 `critic:accept` anywhere; all 71 result.json critic fields say "pending"; studies are on the scoreboard anyway. Pre-registration is unverifiable (codex-tasks/ holds only a README). | fleet/CRITIC_PROTOCOL.md:3-4 vs repo-wide grep |
| I7 | **FINDINGS/WIKI misquote their own MV2 artifact with inverted physics**: "proton 23 MeV / deuteron 89 MeV" — the JSON says proton edep median **101.1 MeV**, deuteron **73.4 MeV**. 23/89 exist nowhere in the artifact. | FINDINGS_SYNTHESIS.md:264-265 vs reports/mv1_mv2_truth_pid_energy_1782220258/mv1_mv2_truth_summary.json |
| I8 | **GAP-02 marked "✅ COMPLETED" but the required MV4 rerun never happened**; the MV4b closure report misquotes MV4's pulls as −15.14/+24.55 (its own unrelated toy) while labelling them PASS/TENSION. | STUDY_GAPS.md:304; reports/mv4b_timewalk_1782911012/REPORT.md:11 |
| I9 | Hardcoded perfect metrics in the builder's benchmark table (`ci_low: 1.0, ci_high: 1.0, roc_auc: 1.0, brier: 0.0` asserted, not computed). | scripts/01_build_pulse_table_from_root.py:322-327 |

## 2. Code blockers

- **C1. Shared-library digitizer is physically wrong** (`src/ccb_mc_validation/digitizer/sampling.py:27-35`): `t0_ns` cancels exactly (hit time has no effect — verified bit-identical waveforms for t0=0/50/55, so transport smearing and overlay offsets do nothing), and the code diffs a peak-normalized kernel instead of integrating it → one-sample spike + negative tail (sample sum 0.078·edep). Blast radius: DigitizerPipeline, mv0_digitize_mc.py, cli.py, orchestrator smoke. No test catches it.
- **C2. `amplitude_adc` semantics fork + abs() inversion**: the builder writes baseline-**subtracted** amplitude (`01_build_pulse_table_from_root.py:60-62`, DATA.md:58), but MV0 v2 / FINDINGS §5 treat it as raw and compute `abs(amplitude−baseline)` ≈ `|net − 6752|` — an inverted amplitude scale. MV0's own "100% negative-going B4/B6/B8" diagnostic is the smoking gun. Also consumed by `mv3_stopping_v2.py:103-104` and `mv4b_timewalk_model.py:105-127`.
  - **RESOLVED 2026-07-03 against the real table** (579,424 B2 rows on LUNARC): `amplitude_adc` is confirmed net/baseline-subtracted (rows with amplitude < baseline exist, impossible for a raw peak). True B2 net median = **5752 ADC**; MV0 v2's folded `|net − pedestal|` median = **1781 ADC** — exactly the calibration.json anchor. The 92 ADC/MeV gain was computed on a garbage variable. Correct data-side anchor (5752) with the same (still geometry-poisoned) MC anchor gives ~297 ADC/MeV — near the "invalidated" v1 value. The v1→v2 "correction" made it worse.
- **C3. MV2 momentum-unit error**: `mv1_mv2_truth_pid_energy.py:84-87` mixes GeV momenta with MeV masses → protons with 33–153 **eV** entry kinetic energy in the published JSON. All ekin-based MV2 numbers are invalid.
- **C4. Production truth loader** (`src/ccb_mc_validation/io/root_truth.py:118-146`): no arm filter (A-arm deposits contaminate B-arm energies — and `tests/test_root_truth_records.py:28` asserts the cross-arm sum), first-hit PDG as truth label, first-element tracklen, and a silent `max_events=100_000` cap against the 1M-event file (`cli.py:181-182`) with results stamped PRODUCTION.
- **C5.** Digitizer noise seeded by event_id only → 100% inter-channel noise correlation (`digitizer/pipeline.py:141`). Digitizer constants drift across four sources (gain 120/246/92; τ 2.0/35 vs 2.5/42; pedestal 300/350/6752). `Makefile mc-smoke` invokes a nonexistent subcommand. The 640,737 gate is fail-open (writes everything, only exit code changes). Production splits are row-index, not event/run-block; the leakage-proof SplitRegistry is tested but never used.

## 3. Physics-logic failures in the MC-validation layer

- **P1. MV0↔MV3 circularity**: the gain is anchored on the MC B2 edep median from the same geometry MV3 declared structurally wrong (χ²/ndf=68,269). Direction: missing upstream material → MC B2 through-goer-diluted → anchor biased; the KS-optimal gain (60) was reported and discarded. MV0 "PASS" and MV3 "FAIL" on the same distribution is internally inconsistent. The MV0 report's downstream-impact table omits MV3 entirely.
- **P2. peak_fraction=0.733 is phase-locked**: it assumes every hit lands exactly on a sample edge; over sampling phase it ranges ~0.71–0.95 (~15–25% one-sided gain/threshold bias). No code computes it.
- **P3. MV4 is not apples-to-apples on four counts**: data anchor 1.85 ns is the ML-ridge-corrected value (true raw CFD20 = 2.99 ns → honest raw pull ≈ −12σ, not −1.05σ); single-trace MC vs pair-difference data (missing √2); merged-track waveforms vs per-stave pulses; σ_data uncertainty (±0.10) assumed. The "negative-B" mystery has a mundane candidate cause both published explanations miss: MV4's CFD threshold sits at ~1σ of noise for its 250-ADC selection → ~50% early noise crossings at low amplitude.
- **P4. MV3's FAIL is real in sign but contaminated**: track-basis MC vs event-basis data; species filter deletes ~24% of charged tracks (C12/α/heavy ions — the B2-stoppers); no Birks quenching in the threshold; no gain-sensitivity scan despite ±30%; MV3b's errata retracted the "8–10 g/cm²" number (realistic inter-stave: 0.1–0.5 g/cm²/pair) but FINDINGS/WIKI still state it as root cause. The LayerID→stave mapping ({0,1}→B2 pair-summing) is an unvalidated guess; odd-bars-unread is a live alternative that mimics "missing material".
- **P5. MV6 is unsupported**: run with the do-not-use gain 246 (59% of MC tracks saturate), no Birks (C12 light overstated ~10×), **no amplitude threshold** despite claiming "threshold-corrected 0.32%", per-track whole-arm waveforms vs per-stave data pulses, and the WIKI mechanism (1–4 MeV C12 from the target crossing ~1 m of air) is physically impossible. Quenched C12 recoils sit far below A>1000 and largely cannot be the data's 4% class. "GMM cluster-2 veto" discards 16.7% of all tracks (98.1% normal) to remove 0.32% anomalies.
- **P6. MV5's "duty factor 0.38" is μ_max=0.380 (max acceptable occupancy) renamed**; no in-spill fraction was ever measured; the "beam is bunched" narrative is built on the misreading. Toy recovery scores merged pairs (<30 ns) as successes; only-previous-gap counting misses following hits (factor ~2).
- **P7. Censoring direction never stated**: all censoring-aware estimators exceed 124.79 ns (KM 151.6, IPCW 179.1) → honest headline is **R_max ≤ 3.05 MHz, plausibly ≈2.1 MHz or lower** (one-sided), not ±1.5 ns two-sided.
- **P8. Two-pulse benchmark rigged both directions**: fit hypothesis grid identical to injection grid; injected waveforms generated from the fit's own templates; failure definitions differ (score<0.5 vs LSQ infeasibility) at unmatched coverage; RMS compared on each method's own accepted subset. The properly-done risk-coverage study (P05f) found **traditional wins** — headline tables never updated. Current-excess claim rests on 2 low-current runs; fully matched estimates are null.
- **P9. Timing headlines not derivable from the repo chain**: B6 0.68–0.75 ns is the external note's narrow-core Gaussian σ from a different correction chain, relabeled σ₆₈ and stamped "✅ MC-validated" (MV4 never validated per-stave or corrected timing — corrected is the *tension* regime). The 0.54–0.56 ns combination has no valid covariance validation (I4). Pooled pair residuals are not per-pair centered (part of the "timewalk gain" is cable-delay removal; ml_ridge σ68 1.846 > full RMS 1.710 betrays the offset mixture). Timewalk target = same-event other-stave mean → correlated-amplitude attenuation bias; no external-reference closure exists.

## 4. Statistics

- **No multiplicity control across ~238 adaptive studies on one dataset** (thousands of CIs; ~12+ chance "wins" expected ≈ the 17 scoreboard wins). All timing studies reuse the same 7 runs; run 65 is exhausted as a holdout. Sub-0.3 ns timing claims (incl. gated S03k 1.107 ns) should not be trusted pending FDR + confirmation partition. S03p/S03r already falsified S03k's robustness and have no scoreboard rows.
- **Three-control rule enforced in prose, not code**: event-block shuffle in 3/402 scripts; P04 flagship ran one control; manifest schema in 0/444 manifests. The implemented "event-block shuffle" is a global donor permutation, not the documented time-block null.
- **Bootstrap defects**: core timing bootstrap iid-resamples 3 linearly dependent pair residuals per event (CIs ~√1.5 too narrow, on as few as 198 residuals); canonical studies used independent per-method CIs, not paired deltas; percentile-only (no BCa); run-level bootstraps resample 7 clusters; "1000 resamples" is false (modal 300–500).
- **res68 has three incompatible definitions**; the standard's own definition ((P90−P10)/2/median) matches none. σ68 is uniformly (Q84−Q16)/2 — clean.
- Appendix B anchors: two-pulse RMS is survivorship-conditioned; duplicate-readout uses a strawman baseline later beaten 10× by the Huber closure (0.0203 vs "0.12–0.20").

## 5. Documentation layer

- README's ✅ column systematically strips caveats (R_max "MC-validated" vs self-consistency; B6 "MC-validated"; 0.32% anomaly hiding a 12× unresolved rate mismatch). PROJECT_REPORT §5 contradicts its own §4 on MV4/MV5 status. FINDINGS is stale vs the 2026-07-01 closures (which are themselves unsound). DATA.md (self-declared source of truth) points at fs9/"to be populated" while the tree lives at fs10; PROJECT_REPORT names /home/billy/ccb-data which DATA.md omits. reports/SUMMARY.md has 137 rows for 238 studies. MV5 ran with the do-not-use gain 246; MV4 with 110. Assorted: "S10i" doesn't exist; MV6 "300k scanned" vs artifact 220k; WIKI P07 links to the P04 report; "−311 ADC" untraceable (source says 341); "six MC validations MV0–MV6" is seven labels.

## 6. What survives (verified)

- The 640,737 selector anchor: implemented consistently (builder/s00c/config), boundary-tested (> 1000 strict, baseline-subtracted at selection, channels {0,2,4,6}), CI-guarded; DATA.md checksums match artifacts.
- τ_eff 90 → ~125 ns correction is real and data-driven (but one-sided: R_max ≤ 3.05 MHz).
- Qualitative physics: B-stack works as a range telescope; p/d separation is real and kinematically consistent (independent check: ~105 MeV pd-elastic deuterons stop early; ~150 MeV protons run deep — the MC truth JSON agrees; the *narrative* numbers were wrong).
- Big-effect ML wins (duplicate-readout closure, saturation recovery) likely survive on effect size — but against overstated baselines.
- Method hygiene where checked: retrained shuffle nulls, genuine run-level splits in S03a/S05c, S18 A-stack reproduction clean, the CORRECTED/falsification culture is genuinely good practice.
- S07 self-referential-leakage rejections and S15b's weak-label disclaimer are model methodology.

## 7. Priority action plan

**Phase 0 — retract & correct (docs/code only, days):**
1. Retract/regrade: MV0 v2 (to PRELIMINARY, blocked on MV3), MV5 (remove all "MC-validated" badges on R_max), MV6 (unsupported), two-ended bound (withdraw), multi-stave covariance closure (withdraw), GAP-02 "COMPLETED" (revert to open), Appendix A example (rewrite from real artifacts).
2. Fix headline docs: R_max as one-sided ≤3.05 MHz (censoring); B6 0.68–0.75 relabeled as external-note Gaussian-core, not MC-validated σ₆₈; MV2 23/89 MeV corrected to artifact values after C3 fix; MV3 root-cause text aligned with MV3b errata.
3. Resolve C2 (amplitude semantics) against the real table — this decides whether the gain anchor is salvageable at all.

**Phase 0b — cheap reruns (existing sbatch, hours):**
4. MV4 rerun with the landed 1/A fix AND matched comparison (per-stave traces, A>1000, pair-difference observable or √2, measured σ_data).
5. MV2 rerun after the unit fix, with a punch-through/containment flag.

**Phase 1 — digitizer overhaul (reuses 1M sample):**
6. Unify the two digitizers into one config-driven implementation (retire gain 246/110, τ 35/42 drift); fix C1 (integrate the kernel), C5 (seed mixing); tune τ_decay per stave to the measured 49–57 ns tails; per-stave truth-labelled pulse table with data-matched selection (the single highest-leverage deliverable — every data script then runs unchanged on MC); zero-signal pedestal production (MV7 module exists, never ran).
   → unblocks MC counterparts for ~13 study families (S00-closure, S01, S02, S03 per-stave, S04, S05-physics, S10 independent τ_eff, S16, P01, P03, P04-relative, P07-shape, P10, P11).

**Phase 2 — geometry fix + new production (the long pole):**
7. Add upstream material to the geobuilder geometry per a *measured* budget (MV3b toy retracted; audit the real beamline), new 1M production, **gate: MV3 v3 rerun with nuisance scan** (gain × peak-phase × Birks × species-inclusive × event-basis, plus the odd-layer mapping test). Only then re-anchor the gain (prefer a geometry-robust observable: MIP-like ΔE in B4/B6 or duplicate-readout) and rerun the MV suite.
   → unblocks quantitative S00 occupancy, S06/S14 energy axis, S15 data-facing PID, P04 absolute, P07 fractions.

**Phase 3 — truth-labelled overlays:** exponential-offset overlay production at 2–3 rates → S11/P05 two-pulse truth failure rates, S13 CWoLa calibration, S07/S12 non-self-referential labels, S10 failure frontier.

**Phase 4 — physics upgrades:** species/dE/dx-dependent scintillation (Birks + slow component) → P08 PSD ceiling + honest MV6 redo; A-arm digitization → S18 MC counterpart. P06 (dropout) and P13a (noise input) are genuinely not MC-informable — record as such.

**Statistics hardening (parallel):** program-level Benjamini–Hochberg over all Δ-CIs; reserve a confirmation run-partition for sub-0.3 ns claims; one shared tested stats module (paired event-level cluster bootstrap, BCa/jackknife, single res68 definition); repeated-permutation nulls with empirical p-values; execute the Critic protocol or delete the claim; archive tickets.
