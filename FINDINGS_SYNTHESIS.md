# CCB Test-Beam — Synthesis of findings (what we understand about the pulse)

**A distilled, physics-organized synthesis of the autonomous study program, written to
publication standard.** As of 2026-06-28 (corrected 2026-07-03 following external review — see
`EXTERNAL_REVIEW_2026-07-02.md`; post-review program completed 2026-07-04 — see the
"Post-review program" section below) the fleet has completed ~230 data-driven studies plus all
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
| **MV0 v2** | Digitizer gain calibration (corrected) | ⛔ RETRACTED (2026-07-03) | v2 gain 92±28 was computed on a folded variable \|net−pedestal\| (amplitude_adc is already baseline-subtracted; true B2 net median = 5752 ADC, not 1781) and is unreproducible from any committed script; v1 (~246) also invalid. **Current best statement (2026-07-04): gain ≈ 60–70 ADC/MeV, dominated by trigger/quenching modelling — no precision value yet.** The Phase-2 trigger-consistent scan prefers ~60 (unquenched threshold model); with Birks quenching on, the quenched re-scan DONE (2026-07-05, LUNARC 3348264): optimum ~65 ADC/MeV (`reports/mv3_gain_quenched_1783240619/`). The 297 ADC/MeV in the mc02 card is the C2-corrected data-side anchor over trigger-unselected MC and is carried as an explicit placeholder only. |
| **MV1** | Particle ID (proton vs deuteron) | ✅ PASS (MC truth ceiling; data = weak-label proxy) | MC AUC = 0.986 (MC truth ceiling); data within 0.5% via weak-label proxies, not species truth; p/d separation at B2 (where deuterons stop) may be less affected by MV3 stopping-depth error |
| **MV2** | Range-energy calibration | ✅ rerun 2026-07-03 (geometry/trigger caveat) | Momentum-unit fix landed: MeV-scale ekin (mean p 99.4 / d 79.7 MeV); edep medians p 101.1 / d 73.4 MeV; containment p 0.70 / d 0.84 (`reports/mv1_mv2_truth_pid_energy_1783077795/`) |
| **MV3 v5** | Stopping-depth profile | 🔶 TENSION (re-graded from FAIL, Phase 2; mechanism ESTABLISHED 2026-07-05) | The published χ²/ndf = 68,269 is **ESTABLISHED by a real `Trig_bar` sensitive-detector simulation** (full 1M, job 3348610) to be dominated by the **unsimulated two-arm coincidence trigger**, not geometry: untriggered MC B2 45.9% (χ²/ndf 68,705, reproduces the FAIL) → real triggered 99.7%, toward data 93.3%. Missing-material narrative **falsified**: only ~0.13 g/cm² of air is absent vs ≥10.5 g/cm² a material explanation would need. **Quantitative closure NOT achieved:** the ideal truth trigger **over-purifies** (B2 99.7% vs data Sample I 93.3%), so the profile is not reproduced; the earlier proxy headline **χ²/ndf 68,269 → 625 (109×) is RETIRED as over-optimistic** (coincidence MC vs mixed all-data, fortuitously loose A-HRD threshold). Residual (~7–12% deep-stave data population) is now **data-side** — STUDY_GAPS NEW-04. (`reports/mv3_v5_realtrigger_1783242005/`, `reports/phase2_geometry_1783108797/`) |
| **MV4** | Single-stave timing | ⚠️ REVIEW (honest rerun 2026-07-03) | Rising-edge CFD + physical timewalk sign (B = +39.6 ns·ADC) landed; MC pair-equivalent σ₆₈ = 2.087 ± 0.009 ns sits between the data raw (2.993 ns) and corrected (1.50 ns) anchors. Matched per-stave rerun awaits the Phase-1 digitizer (`reports/mv4_timing_1783077795/`) |
| **MV5** | Pile-up / R_max | ⛔ RETRACTED as validation → slot refilled (2026-07-04) | The 2026-06 "MC τ_eff" was a hardcoded copy of the data value. The validation slot now points to the **first honest MC live-time (MC03): τ_eff = 134.99 ns [134.96, 135.01]** (statistics only; the +8% / +10.2 ns offset from data 124.79 ns is the dominant, systematic, difference) **vs data 124.79 ns (+8%, B2-driven)** — an honest disagreement, measured independently by the S10b estimator on digitized MC single pulses. (`reports/mc03_overlay_1783180480/`) |
| **MV6** | Representation & anomaly ID | ⛔ RETRACTED → **MV6b: C12 RULED OUT** (2026-07-04) | Honest redo with physical Birks quenching: **0 of 1,656 quenched C12-dominant records pass A>1000 at any gain (60–297)**; MC early-peak fraction is 0.000% in every configuration vs data 4.4%. The early-peak class cannot be a species/scintillation effect — it must be instrumental or trigger-phase-related, and is reopened as a **data-side** question (P02/P09 leads). (`reports/mv6b_anomaly_quenching_1783180742/`) |

**Correction 2026-07-03:** following the external review, most of the "closed by MC" claims are
withdrawn. **Still closed:** PID ceiling (MV1), timing raw resolution (MV4 — under review pending
matched rerun). **Reopened:** anomaly species identity (MV6 retracted), pile-up R_max validation
(MV5 retracted as validation — R_max is now a data-driven one-sided bound), digitizer gain model
(MV0 retracted), MV2 range-energy mechanism (retracted pending rerun).

**Update 2026-07-04:** the post-review program closed or re-scoped most of the reopened items —
MV3's root-cause mechanism is ESTABLISHED by a real `Trig_bar` sensitive-detector simulation (the unsimulated trigger, not missing material; re-graded TENSION, quantitative closure still open), the C12 attribution is ruled out
(MV6b), the two-pulse failure-rate question is closed by the honest truth-labelled benchmark
(MC03/S24), the zero-signal pedestal validation ran (MV7), and an independent MC live-time now
exists (an honest +8% disagreement). Details in the section below.

---

## Post-review program (2026-07-03/04) — what changed after the external review

The seven-track external review (`EXTERNAL_REVIEW_2026-07-02.md`) triggered a correction program
(Phase 0 retractions through Phase 4 physics upgrades, plus a statistics-hardening pass). All
phases are complete. The seven results below supersede the corresponding 2026-06 claims wherever
the two disagree.

1. **MV3 root-cause mechanism ESTABLISHED by a real `Trig_bar` sensitive-detector simulation: the
   unsimulated trigger, not missing material (Phase 2 diagnosis; MV3 v5 real simulation 2026-07-05).**
   A real GEANT4 production with `Trig_bar` scored as a sensitive detector (full 1M, job 3348610)
   now supersedes the Phase-2 truth proxy. It **validates against the original** (untriggered MC
   B2 = 45.9%, χ²/ndf 68,705 — reproduces the published FAIL) and shows the real two-arm coincidence
   drives B2 to **99.7%**, toward the data (Sample I 93.3%); the coincidence vetoes 99.94% of
   deep-proton events (the conjugate 37 MeV deuteron never reaches the A-paddle) and keeps B2
   deuterons, giving a ~98%-pure B2 deuteron sample. The missing-material narrative is **falsified**:
   a direct volume dump shows every named upstream component present except ~0.13 g/cm² of air, vs
   ≥10.5 g/cm² a material explanation would need. **BUT quantitative closure is NOT achieved:** the
   *ideal* truth trigger **over-purifies** (B2 99.7% overshoots data Sample I 93.3%); the data keeps
   a 6.7% (Sample I) / 12.4% (all) deep-stave coincidence population the ideal trigger does not
   produce. The earlier proxy headline **χ²/ndf 68,269 → 625 (109×) is RETIRED as over-optimistic**
   — it compared a coincidence MC against *mixed* all-data with a fortuitously loose A-HRD threshold.
   MV3 is re-graded **FAIL → TENSION** (mechanism established, quantitative match not). The residual
   is now **data-side** (accidental/pile-up coincidences absent in truth MC, Sample-I purity,
   paddle threshold/resolution fidelity, LayerID→stave mapping) — STUDY_GAPS NEW-04; no new GEANT4
   production is needed. (`reports/mv3_v5_realtrigger_1783242005/REPORT.md`,
   `reports/phase2_geometry_1783108797/REPORT.md`)
2. **Gain: no precision value yet — the honest statement is "≈60–70 ADC/MeV, dominated by
   trigger/quenching modelling".** v1 (246) and v2 (92 ± 28) are both retracted; 297 ADC/MeV is
   the C2-corrected data-side anchor (true B2 net median 5752 ADC) over trigger-unselected MC and
   is carried only as an explicit placeholder. The trigger-consistent Phase-2 scan prefers ~60
   (unquenched threshold model; monotonic in the *proxy* χ²/ndf: 60 → 625, 92 → 3,613, 300 → 7,017 —
   proxy-scan diagnostics whose absolute values are retired as over-optimistic with the MV3 proxy
   headline, but the monotonic gain *trend* still informs the band); with Birks
   quenching on, the quenched re-scan (2026-07-05, LUNARC 3348264) measured the optimum at ~65 (band ~60–70).
3. **Sample-I deuteron enrichment is confirmed at truth level and directionally confirmed in data,
   with the run-set/beam-drift confound now bounded (S21 + S23 + B-M6).** Truth
   (S21): B2 deuteron-fraction ratio I/II = 1.519 [1.510, 1.528] (exclusive I vs II\I: 1.912
   [1.898, 1.925]); 91.2% of Sample-I events are d-into-B / p-into-A pd-elastic pairs. Data
   (S23): the Sample-I B2 spectrum is harder — high-amplitude fraction ratio f(A>5000)_I/II =
   3.45 [3.41, 3.50]. Samples I/II are disjoint run sets, so **B-M6 (2026-07-05,
   `reports/bm6_runset_confound_20260705_202638/`) bounds the run-set/beam confound**: treating the
   run as the dependence unit, the run-clustered ratio CI is **[2.52, 4.64]** (excludes 1), the gap
   is **3.5× the within-sample run-to-run SD** (Welch t≈6.5, d≈2.3), and a smooth-drift model
   reproduces only ~3% — so run-set/beam drift accounts for **at most ~29% (conservative 1-SD;
   central ~3%)** of the hardening, which is therefore trigger-dominated but not a clean same-run
   confirmation. Mimicking the trigger moves MC toward the
   data (B2 KS 0.192 → 0.131; occupancy χ² 624k → 20k), and the residual double-ratio deficit
   (B2 occupancy DR = 0.738 [0.733, 0.742], z = −99 — statistics-only significance; systematics
   from disjoint run-sets/beam conditions not included) shows MC under-predicts the between-sample
   contrast — consistent with the Phase-2 trigger finding. (`reports/s21_sample12_trigger_truth_1783077969/`,
   `reports/s23_sample12_data_mc_1783108675/`)
4. **Per-stave timing resolution vs amplitude is measured (S22).** σ68 vs min-pair amplitude per
   pair and per sample, per-(pair, run) centered; the raw curves follow a 1/A scaling better than
   1/√A in the high-lever pairs (B4–B6 χ²/ndf 0.32–0.87 vs 1.25–3.71) and tie where the constant
   floor dominates; downstream per-stave resolution reaches **≈0.85–1.1 ns at high amplitude**
   (σ_pair/√2, cross-checked by a triangle decomposition); B2 curves are saturation-flagged
   (30–40% of selected B2 pulses above ~7000 ADC) and excluded from headline per-stave claims.
   (`reports/s22_timing_vs_amplitude_1783108999/REPORT.md`)
5. **Honest two-pulse benchmark and the first real MC live-time (Phase 3, MC03/S24).** The
   truth-labelled overlay benchmark (continuous injected dt, digitized real truth-hit pairs, one
   failure definition for both methods, matched coverage) replaces the rigged S11a comparison —
   its failure rates 0.295 vs 0.168 are retired everywhere. Result: at matched 80% coverage the
   **traditional fit wins** (failure ≤0.0001 vs ML 0.0001–0.0002); at full coverage **ML wins**
   (0.011 vs 0.048); common-subset dt σ68 is trad 0.64 ns vs ML 0.89 ns. Independently, the S10b
   estimator on digitized MC single pulses gives **MC τ_eff = 134.99 ns [134.96, 135.01]**
   (statistics only; the +8% / +10.2 ns offset from data 124.79 ns is the dominant, systematic,
   difference) **vs data 124.79 ns (+8%, B2-driven)** — the first honest MC live-time, an honest disagreement, and the
   measurement that now fills the validation slot left by the retracted MV5.
   (`reports/mc03_overlay_1783180480/REPORT.md`)
6. **Physical Birks quenching lands; C12 ruled out; MV7 pedestal closure (Phase 4).** With the
   rewritten per-hit Birks law (kB = 0.0126 g/(MeV cm²), PSTAR/ASTAR-anchored dE/dx), **0 of
   1,656 quenched C12-dominant records pass A>1000 at any gain hypothesis (60–297)** — C12
   recoils are **ruled out** as the data's 4.4% early-peak class, which must be instrumental or
   trigger-phase-related and is reopened as a **data-side** question (P02/P09 leads). MV7:
   pedestal estimators validated on zero-signal MC (adaptive MAE 3.48 ADC, learned 1.50 ADC;
   MC-level lower bounds — data still has no true-pedestal sample). An A-arm digitized baseline
   table (S18 counterpart; only A1/A3 usable in data) now exists.
   (`reports/phase4_1783180742/REPORT.md`, `reports/mv6b_anomaly_quenching_1783180742/`,
   `reports/mc02_pulse_table_1783107862/`)
7. **Statistics hardening.** A program-level Benjamini–Hochberg FDR census over the delta-CI
   claims: after B-M3 emitted machine-readable, dependence-aware delta-CIs for the P04/P07 wins
   (`scripts/stats02_p04p07_delta_ci.py`), the refreshed census
   (`reports/stats01_program_fdr_20260705_203905/`, 1,957 claims) finds **14 of 15 scoreboard bold
   wins survive BH, 0 fail, 1 prose-only**. **The flagship P04 (duplicate-readout) and P07
   (saturation) ML wins are now FDR-certified** — all five (P04/P04c/P04d/P04e/P07) pass BH at
   q=0.05 in the amplitude-charge family with paired **event-clustered** delta-CIs (event-cluster
   design effect only ~1.05, so the dependence unit barely moves these amplitude/charge closures;
   z = 23–166). Certification means *statistically distinguishable from zero*, not absolute-energy
   truth: P04 stays a duplicate-readout electronics closure, P07's natural-saturation transfer is
   unaudited (`reports/bm3_p04p07_fdr_20260705_203249/REPORT.md`). The one remaining prose-only win
   is **P05b** (a pile-up two-pulse study). The retired, rigged S11a (0.295/0.168) is not a BH
   survivor — it was killed for circularity, not multiplicity, the reminder that S03k survives BH
   yet was falsified by the
   S03p/S03r leakage nulls — BH survival is necessary, not sufficient. A confirmation partition
   (runs 64 and 12–30) is reserved for sub-0.3 ns claims (`docs/CONFIRMATION_PARTITION.md`) but is
   **defined and not yet used**, so any sub-0.3 ns timing claim is not yet confirmed on held-out
   data; a
   shared, tested estimators module (`src/ccb_mc_validation/statistics/estimators.py`) replaces
   per-study bootstrap code; and the Critic gate's honest status (specified, never executed) is
   recorded in `fleet/CRITIC_PROTOCOL.md`.
   (`reports/stats01_program_fdr_20260703_220116/REPORT.md`)

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
   this MC ceiling — but **only via weak-label proxies, not species truth**: AUC 0.986 is an MC
   truth ceiling and the data side is a leakage-safe stress test, not a species-truth PID
   validation. ✅ (MV1/MV2; MC ceiling + weak-label data proxy)
4. **Analytic amplitude timewalk is the timing champion; a timewalk correction tension with MC is
   identified.** The analytic correction reaches **sigma68 ~ 1.49-1.55 ns** (LORO). The per-stave resolution decomposition assumes independent stave errors (covariance validation withdrawn 2026-07-03 — the closure script was numerically invalid; residual inter-stave covariance is unmeasured). MC raw timing
   resolution agrees within 1.05σ (PASS); MC timewalk-corrected resolution is discrepant at 2.68σ
   (TENSION — see Section 1). ✅/🔶 (MV4 completed)
5. **The pile-up headline number was wrong by ~30%; the corrected value is a data-driven upper
   bound.** The note's R_max ~ 4.2 MHz assumed tau_eff = 90 ns; the measured waveform live-time
   (124.79 ns) implies **R_max ≤ 3.05 MHz** (one bound plus estimator band; censoring-aware
   estimators — KM 151.6 ns, IPCW 179.1 ns — suggest ≈2.1 MHz or lower). MV5 retracted as
   validation 2026-07-03 — its "MC τ_eff" was a hardcoded copy of the data value; the independent
   MC live-time (MC03, +8%) would, if real, **tighten the bound rather than validate it**. ⚠️
6. **ML genuinely wins where the truth is independent of the input and lives in waveform shape:**
   duplicate-readout amplitude/charge closure and artificial saturation recovery — each with a CI
   excluding zero and surviving leakage controls. (Two-pulse recovery, once claimed here, is now a
   split verdict on the honest truth-labelled benchmark: traditional wins at matched coverage, ML
   wins at full coverage — MC03/S24.) ⚠️
7. **Absolute per-event energy is not reachable from data alone** to the 10% target; this is a
   structural limitation, confirmed by the GEANT4 finding that the physics-anchored Birks lookup is
   the best held-out energy method. ✅ (the *limitation* is MC-confirmed)
8. **The C12-recoil identification of the 4.4% early-peak anomaly class is RULED OUT (MV6b,
   2026-07-04).** The retracted MV6 attribution was tested honestly with physical Birks
   quenching: 0 of 1,656 quenched C12-dominant records pass A>1000 at any gain (60–297), and the
   MC early-peak fraction is 0.000% in every configuration vs data 4.4%. The class cannot be a
   species/scintillation effect; it must be instrumental or trigger-phase-related and is now a
   **data-side** open question (P02/P09 leads). ✅ (the *exclusion* is MC-confirmed)

---

## The one-paragraph answer

The CCB B-stack pulse is **low-dimensional in shape** and **well-described by analytic models** for
timing and pile-up rate, so **ML helps most where the signal lives in waveform shape and the truth is
independent of the inputs** — saturation recovery, duplicate-readout amplitude/charge closure, and
two-pulse detection at full coverage (though the traditional fit wins two-pulse recovery at a
matched abstaining operating point — MC03/S24). It **ties or loses** where an analytic physics
model is already optimal
(timewalk correction, Poisson pile-up rate) or where an apparent win rests on a label that is a
disguised function of the input (D_t / curvature classifiers). The most consequential physics results
are: (1) the pile-up R_max is **≤3.05 MHz, not ~4.2 MHz** — a data-driven one-sided bound; the
first honest MC live-time (MC03, 2026-07-04) disagrees by +8% (134.99 vs 124.79 ns, B2-driven;
statistics-only CI, the +8% offset is the dominant systematic difference); (2) proton/deuteron PID
is **MC-closed** at AUC = 0.986 (MV1) — an MC truth ceiling reached in data only via weak-label
proxies, not species truth; (3) the stopping-depth discrepancy
(MV3: χ²/ndf = 68,269) has its **mechanism ESTABLISHED by a real `Trig_bar` sensitive-detector simulation
(2026-07-05) as the unsimulated two-arm coincidence trigger, not missing material** (untriggered
B2 45.9% → real triggered 99.7%, toward data 93.3%); quantitative closure is NOT achieved (the
ideal trigger over-purifies, so the proxy χ²/ndf ≈ 625 is retired as over-optimistic; residual is
data-side, NEW-04), and MV3 stays TENSION (Phase 2, 2026-07-03); (4) the early-peak anomaly class is **not C12 recoils**
(MV6b, 2026-07-04: 0 quenched C12 records pass A>1000 at any gain) — it must be
instrumental/trigger-phase and is a data-side open question; and (5) the digitizer gain has **no
precision value yet** — the honest statement is ≈60–70 ADC/MeV, dominated by trigger/quenching
modelling (v1 246 and v2 92 ± 28 both retracted; 297 is an explicit placeholder).

---

## 1. Timing  (S02, S03, S04, S05, S18, S22, P01, P03)

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
- **Resolution vs amplitude (S22, 2026-07-03):** per-pair sigma68 vs min-pair amplitude, per
  sample, per-(pair, run) centered (cable-delay offsets removed before pooling). The raw curves
  follow a **1/A** scaling better than 1/sqrt(A) in the high-lever pairs (B4-B6 chi2/ndf
  0.32-0.87 vs 1.25-3.71); downstream per-stave resolution reaches **~0.85-1.1 ns at high
  amplitude** (sigma_pair/sqrt(2), triangle-decomposition cross-checked). B2 curves are
  saturation-flagged and excluded from headline per-stave claims.
  (`reports/s22_timing_vs_amplitude_1783108999/`)
- **A-stack independent-arm check (S18):** A1-A3 robust width **1.389 ns** reproduces the note
  (1.43 ns). (Corrected 2026-07-03, experiment-owner setup facts: the A-stack is an independent
  detector arm at the conjugate angle measuring **different particles** — pd-elastic sends the
  proton into one arm, the correlated deuteron into the other — so S18 is a methodology
  reproduction on an independent detector, not a same-particle cross-check.)
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

**Update (2026-07-03, honest rerun):** MV4 was rerun with a rising-edge-constrained CFD and the
MV4b functional-form fix; the fitted timewalk coefficient is now physical (B = +39.6 ns·ADC) and
the MC pair-equivalent σ₆₈ = 2.087 ± 0.009 ns sits between the data raw (2.993 ns) and corrected
(1.50 ns) anchors. Verdict **REVIEW** — the comparison is still merged-track MC vs per-stave data
with unmatched selection; a matched per-stave rerun awaits the Phase-1 digitizer.
(`reports/mv4_timing_1783077795/`)

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

## 2. Pile-up  (S10, S11→S24, S13)  — the headline physics revision

**Section verdict: R_max ≤ 3.05 MHz is a data-driven one-sided bound (MV5 retracted as validation
2026-07-03; independent MC live-time disagrees by +8%, MC03 2026-07-04); the honest truth-labelled
two-pulse benchmark (MC03/S24) gives a split verdict — traditional at matched coverage, ML at full
coverage. ⚠️/🔶**

- **R_max is lower than the note claims — as a data-driven upper bound.** The note's R_max =
  **4.222 MHz** assumes tau_eff = 90 ns. Direct measurement of the waveform live-time window finds
  **all thresholds imply > 90 ns**: the 10% tail-crossing live-time is **124.79 ns** (bootstrap CI
  **[123.33, 126.36] ns**). MV5 used the data-measured τ_eff as an input; no independent MC
  live-time measurement exists. R_max = 0.380/τ_eff is a data-driven one-sided bound:
  censoring-aware estimators (KM 151.6 ns, IPCW 179.1 ns) imply **R_max ≤ 3.05 MHz, plausibly
  ≈2.1 MHz or lower**. The analysis note's τ_eff = 90 ns → 4.22 MHz correction stands — but as an
  upper bound. ⚠️
- **Two-pulse recovery — settled by the honest truth-labelled benchmark (MC03/S24, 2026-07-04):**
  the S11a comparison (and its failure rates 0.295 vs 0.168) is **retired** — its injection grid
  coincided with the fit's hypothesis grid, its injected waveforms came from the fit's own
  templates, and its failure definitions differed between methods (review P8). The replacement
  benchmark (continuous injected dt, digitized real truth-hit pairs, one failure definition,
  matched coverage) finds: at matched **80% coverage the traditional fit wins** (failure ≤0.0001
  vs ML 0.0001–0.0002); at **full coverage ML wins** (0.011 vs 0.048); common-subset dt σ68 is
  trad 0.64 ns vs ML 0.89 ns. (`reports/mc03_overlay_1783180480/`)
- **Current-dependent excess is real but heterogeneous.** CIs exclude zero, but after matching on
  amplitude/baseline/topology it concentrates in high-amplitude / large-baseline-lowering /
  broad-late pulses (S10c-f, S11b-d). The honest beam-pile-up statement is the **high-current
  excess** (matched: ~0.0048-0.0203 per event depending on stratum), not the raw "pile-up score",
  which is mostly a current-independent baseline (ratio 1.29, not 10). Topology stays the
  physics-facing rate handle; ML/CWoLa is **monitoring/diagnostic only** (S13b-c).
- **Censoring caveat (S10h, S10i):** the final-sample window is heavily censored (72.6% of pulses
  show positive inflation at live20); tau/R_max adoption requires acquisition-window bounds.

**MC verdict (pile-up) — MV5 retracted; slot refilled by MC03 (2026-07-04).** The 2026-06 MV5
used the data-measured τ_eff as an input and was retracted as a validation. The validation slot
now points to the **independent MC live-time (MC03)**: the S10b 10% tail-crossing estimator on
digitized MC single pulses gives **τ_eff = 134.99 ns [134.96, 135.01]** (statistics only; the
+8% / +10.2 ns offset from data 124.79 ns is the dominant, systematic, difference) **vs data
124.79 ns (Δ = +10.2 ns, +8%, driven by B2: 141.35 ns)** — an honest disagreement, not a pass; MC
pulses are clean by construction while the data value includes real pathologies. R_max = 0.380/τ_eff
remains **one data-driven one-sided bound plus an estimator band: R_max ≤ 3.05 MHz (censoring-aware
estimators — KM 151.6 ns, IPCW 179.1 ns — suggest ≈2.1 MHz or lower)**; the +8% MC excess, if real,
would tighten this bound rather than validate it. The note's 90 ns assumption is still
corrected (4.22 → ≤3.05 MHz), as an upper bound. The two-pulse failure-rate sub-item is closed by
the honest benchmark above. ⚠️/🔶

---

## 3. Pulse shape and learned representation  (P01, P02, P09)

**Section verdict: shapes are low-dimensional; a compact autoencoder wins only at very low latent
dim; the representation-superiority claim for downstream tasks is CORRECTED (leakage); the C12
anomaly-species identification is RULED OUT (MV6b, 2026-07-04) — the early-peak class is now a
data-side question. ⚠️/❌/⛔**

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

**MC verdict (representation/anomaly) — MV6 ⛔ RETRACTED (2026-07-03); MV6b redo: C12 RULED OUT
(2026-07-04).** MV6 ran with the invalidated gain (246), no Birks quenching, no amplitude
threshold (despite claiming "threshold-corrected"), and per-track whole-arm waveforms vs per-stave
data pulses; the C12 attribution was unsupported. The honest redo (MV6b) compared a quenched
digitized table against its unquenched twin under the data taxonomy (A>1000, early-peak
`peak_sample ≤ 3`): **0 of 1,656 quenched C12-dominant records pass A>1000 at any gain hypothesis
(60–297)** (unquenched, only 3 pass at gain 297), and the MC early-peak fraction is 0.000% in
every configuration vs data 4.4%. The early-peak class **cannot be a species/scintillation
effect**; it must be instrumental (baseline/noise/bipolar artifacts, per P02/P09 leads) or
trigger-phase-related — neither of which the MC models — and is reopened as a **data-side**
question. (`reports/mv6b_anomaly_quenching_1783180742/`) The retracted MV6 numbers below are
retained for the record only. (External Review 2026-07-02)

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
the MV6 retraction; MV6b (2026-07-04) rules the C12 hypothesis out, so the open question is now
data-side: which instrumental or trigger-phase mechanism produces the 4.4% early-peak class? ⛔→🔶

---

## 4. Amplitude, charge and energy  (P04, S01, S14, P07, P10)

**Section verdict: ML wins duplicate-readout amplitude/charge decisively; absolute energy is
structurally unreachable from data, MC-confirmed. ⚠️ closure / ✅ limitation**

- **Amplitude/charge duplicate-readout closure (P04, P04c-e):** ML (HGB / ExtraTrees) is a
  **decisive win** — res68 = **0.003-0.009** vs **0.12-0.20** for peak/integral. The traditional
  direct template-scale has a pathology that needs diagnosis. (S01: full-dataset amplitude-bin
  template MSE 0.0444 vs AE/PCA basis 0.00208, Delta = -0.0423, CI [-0.0524, -0.0324].)
  **FDR status:** P04/P04c–e have **no machine-readable delta-CI in the STATS01 FDR census** (they
  are among the 6 prose-only bold wins outside the BH census); they are **reported, not yet
  FDR-certified**.
- **Absolute energy is not reachable (S14b-c):** propagated per-event energy res68 ~ 0.19-0.25 fails
  the 10% threshold. This is an honest structural limitation: there is no per-event energy truth in
  the data.
- **Saturation recovery (P07):** ML recovers true amplitude to **res68 ~ 0.032-0.046** vs template
  **0.104-0.286** on artificial constant-ceiling clips (3-7x win), degrading gracefully as
  saturation worsens. Natural-saturation transfer carries a run-dependent timing-tail envelope and
  needs boundary/systematic audits before production (P07b-e). (~30-40% of Sample-I B2 pulses exceed
  7000 ADC and saturate.) **FDR status:** like P04, P07 has **no machine-readable delta-CI in the
  STATS01 FDR census** (a prose-only bold win) — **reported, not yet FDR-certified**.
- **Conditional templates (P10):** an explicit analytic timewalk **beats** a learned conditional
  template on the primary q-template metric; ML only helps a secondary timing metric (P10a-b).

**MC verdict (energy) — MV2, rerun 2026-07-03 after the momentum-unit fix.** MV2 supports the
limitation: absolute energy reconstruction is unreachable without inter-stave absorber calibration.
Per-species medians at truth level: proton edep_tot median = **101.1 MeV**, deuteron = **73.4 MeV**
(the previously quoted 23/89 MeV were untraceable). The eV-scale ekin corruption (review C3) is
fixed: entry kinetic energies are MeV-scale (mean proton 99.4 MeV, deuteron 79.7 MeV); containment
proton 0.70 / deuteron 0.84 (**untriggered MC — not trigger-representative**; the containment
fractions inherit the MV3 selection bias). Deuterons stop early because pd-elastic kinematics gives them
~105 MeV with roughly half a proton's range; forward protons (~150 MeV) penetrate deep or punch
through. Relative range ordering (p/d separation by stopping depth) is supported; the GEANT4
Birks lookup remains the best held-out energy method; neural/tree models do not supersede the
physics prior. ⚠️ (geometry/trigger caveat: MV2 runs on the untriggered MC population) ✅/⚠️

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
(92 ± 28 ADC/MeV) is valid. **Current best statement (2026-07-04): gain ≈ 60–70 ADC/MeV,
dominated by trigger/quenching modelling — no precision value yet.** The Phase-2
trigger-consistent scan prefers ~60 (unquenched); the quenched re-scan (2026-07-05, LUNARC 3348264) measured ~65 and is
pending; 297 ADC/MeV is the C2-corrected data-side placeholder in the mc02 card. The hardware
pedestal ~6752 ADC statement stands (it is the `baseline_adc` column).

**MV7 (zero-signal pedestal validation) ran 2026-07-03** on a 100,000-record zero-signal MC
sample: adaptive estimator (median of samples 0–3) MAE **3.48 ADC**, learned (ridge on 18
samples) MAE **1.50 ADC**. This is an MC-level closure and a lower bound — correlated noise,
drift, and signal contamination are not modelled, and real data still has no true-pedestal
sample. (`reports/mc02_pulse_table_1783107862/`)

---

## 6. Particle identification and stopping depth  (MV1, MV2, MV3, S07, S15)

**Section verdict: ✅ PID MC truth ceiling (MV1/MV2 complete; data side is weak-label proxy, not
species truth); 🔶 stopping-depth profile re-graded FAIL → TENSION (Phase 2, 2026-07-03): the
discrepancy has its mechanism ESTABLISHED by a real `Trig_bar` sensitive-detector simulation
(2026-07-05) as the unsimulated two-arm coincidence trigger, not geometry — but quantitative
closure is NOT achieved (ideal trigger over-purifies; residual data-side, NEW-04).**

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

The HGB AUC (0.986) is the MC truth ceiling; data methods reach within 0.5% of this ceiling **only
via weak-label proxies, not species truth** — a leakage-safe stress test showing the separating
information is present in the data, not a species-truth PID validation. ✅ (MC ceiling; weak-label
data proxy)

**MV2 (energy/range, rerun 2026-07-03 after the momentum-unit fix):** deuterons deposit and stop
early (layers 0-1), protons penetrate (layers 4-7, p-fraction ~0.89-0.90). edep_tot medians at
truth level: proton **101.1 MeV**, deuteron **73.4 MeV** (the previously quoted 23/89 MeV were
untraceable). Entry kinetic energies are now MeV-scale (mean proton 99.4 MeV, deuteron 79.7 MeV);
containment (edep_tot ≥ 0.8·ekin): proton 0.70, deuteron 0.84 (**untriggered MC — not
trigger-representative**). Deuterons stop early because
pd-elastic kinematics gives them ~105 MeV with roughly half a proton's range; forward protons
(~150 MeV) penetrate deep or punch through.

**Data vs MC comparison (PID/range, MV1 + MV2):**

| Observable | Data result | MC (GEANT4) result | Agreement |
|---|---|---|---|
| p/d separability (AUC) | ~0.985 (near-ceiling, leakage-safe proxy) | 0.9860 (HGB truth) | within ~0.1% |
| Deuteron stopping depth | inferred early (B2-enriched Sample I) | layers 0-1, d-frac 0.36-0.39 | consistent |
| Proton stopping depth | inferred penetrating (Sample II) | layers 4-7, p-frac 0.89-0.90 | consistent |
| Depth occupancy ordering | B2 >> B4 > B6 > B8 | Sci_bar hits fall layer 0->7 | qualitative match |
| Sample I/II trigger split | deuteron-enriched — consistent in data (S23: B2 f(A>5000) ratio 3.45 [3.41, 3.50]; run-set/beam drift bounded ≤~29% by B-M6) | confirmed at truth level (S21: B2 f_d ratio 1.519 [1.510, 1.528], exclusive 1.912) | confirmed at truth level, consistent in data (2026-07-03); MC under-predicts the contrast (S23 DR 0.738, z = −99 statistics-only; systematics from disjoint run-sets/beam conditions not included) |

> **Sample definitions (corrected 2026-07-03, experiment-owner setup facts):** Sample I = A AND B
> trigger coincidence (MC mimic: charged particle entering the first A and first B layer within
> 15 ns); Sample II = B trigger only (A ignored). In MC, Sample I is a **subset** of Sample II
> (inclusive flags in `src/ccb_mc_validation/io/root_truth.py`); in data, Samples I and II are
> **disjoint run sets** with different trigger configurations — the MC-vs-data sample rows above
> inherit this subset-vs-disjoint asymmetry. The enrichment mechanism — the coincidence tags
> kinematically-correlated pd-elastic pairs — is confirmed by S21 (91.2% of Sample-I events are
> d-into-B / p-into-A pairs) and, on the data side, by S23.

### 6.2 Stopping-depth profile — FAIL re-graded TENSION (MV3, root cause: the trigger)

MV3 v3 (threshold-corrected) compared the MC and data stave-occupancy profiles quantitatively and
published **χ²/ndf = 68,269 (4 stave bins, ndf = 3)**. Phase 2 (2026-07-03) diagnosed, and a real
`Trig_bar` sensitive-detector simulation (2026-07-05) then ESTABLISHED, the mechanism: the
comparison (trigger selection), not the geometry — see below.

| Stave | MC fraction | Data fraction | Ratio (Data/MC) |
|---|---|---|---|
| B2 | 47.0% | 87.6% | 1.86× |
| B4 | 18.2% | 6.3% | 0.35× |
| B6 | 12.5% | 3.9% | 0.31× |
| B8 | 22.3% | 2.3% | 0.10× |

The untriggered MC overestimates B8 penetration by a factor of ~10 relative to data. The
qualitative depth ordering (B2 > B4 > B6 > B8 in data) is reproduced.

**Root-cause mechanism ESTABLISHED by a real `Trig_bar` sensitive-detector simulation (2026-07-05,
full 1M production, job 3348610; superseding the Phase-2 truth proxy): the unsimulated two-arm
coincidence trigger.** The real production reproduces the published FAIL untriggered (B2 45.9%,
χ²/ndf 68,705) and, with the real A-paddle AND B-paddle coincidence (EDep > 0.5 MeV, 20 ns window),
drives B2 to **99.7%**, toward the data (Sample I 93.3%): the coincidence vetoes 99.94% of
deep-proton events (their conjugate 37 MeV deuteron never reaches the A-paddle) and keeps B2
deuterons, leaving a ~98%-pure B2 deuteron sample.
The geometry audit (direct `TGeoManager` dump of the production file) independently **falsified** the
missing-material narrative: every named upstream component (vacuum window, trigger scintillators,
TPC) is already in the production geometry; only ~0.13 g/cm² of air is genuinely missing, while a
material explanation of the B2 deficit would require ≥10.5 g/cm² — a factor ≥13 more than
physically exists.
**BUT quantitative closure is NOT achieved.** The *ideal* truth trigger **over-purifies**: B2 =
99.7% overshoots even the data's own coincidence sample (Sample I 93.3%), so the profile is not
reproduced (χ²/ndf vs Sample I ~1.3×10⁵). The data keeps a 6.7% (Sample I) / 12.4% (all) deep-stave
coincidence population that the ideal trigger does not produce. The earlier proxy headline
**χ²/ndf 68,269 → 625 (109×) is RETIRED as over-optimistic** — it compared a coincidence MC against
*mixed* all-data with a fortuitously loose, gain-dependent A-HRD threshold that fortuitously
retained ~13% non-B2 events. The physics of the mechanism is transparent: the coincidence keeps
deuteron-into-B events (conjugate ~85 MeV proton reaches Stack A) and vetoes deep-proton events
(conjugate ~37 MeV deuteron dies before the A-paddle). The odd-layer mapping hypothesis (review P4)
is the marginal best-χ² loser (both unread-bar variants are worse); `paired` is adopted as default.
B-M9 (2026-07-05) signs off the LayerID *semantics* from the geometry/SD source (`LayerID=copyNo=bar
depth index`, 0=upstream→B2, monotonic to B8; B2/total/ordering mapping-invariant) but carries the
deep-stave B4/B6/B8 MC fractions as **mapping-conditional** (paired↔odd/even is an unresolved
energy-grouping/hardware question, not derivable from the sim). The residual
deep-stave data population is now a **data-side** question (accidental/pile-up coincidences absent
in the truth MC, Sample-I purity, paddle threshold/resolution fidelity, LayerID→stave mapping) —
STUDY_GAPS NEW-04; it is not a geometry/SD production.
(`reports/mv3_v5_realtrigger_1783242005/REPORT.md`, `reports/phase2_geometry_1783108797/REPORT.md`)

**Impact:** MV3 is re-graded **FAIL → TENSION**; no new GEANT4 production is needed, and PR #8
(inter-stave Al proxy in the geobuilder) should be closed or reworked, not merged. The PID
qualitative conclusion (p/d range separation) stands. Quantitative stopping-depth and acceptance
work should proceed via the next MC-side work item: **score the `Trig_bar` volumes as sensitive
detectors and emit a real per-event Sample-I/Sample-II trigger flag**, replacing the truth proxy. 🔶

---

## 7. Cross-cutting methodology (why to trust the above)

- **Leakage is hunted, not assumed away.** D_t / curvature classifiers hit AUC ~ 1.0 because the
  label is a disguised function of the input — flagged as **self-referential**, not wins (S07b, S07e,
  S07g, P02d). On injected-corruption truth (label independent of input), shape-only ML legitimately
  wins (S07f, S07h) — but that is *not* a measured beam pile-up rate.
- **The pattern.** ML wins when truth is independent and the signal is in shape (saturation,
  duplicate-amplitude; two-pulse only at full coverage per the honest MC03/S24 benchmark); ML
  ties/loses when an analytic model is already optimal (timewalk, Poisson rate) or when the
  apparent win is leakage.
- **Reproduce-first is enforced.** Every study above carries an exact count gate; the 640,737 /
  706,373 selector distinction (S00b/c) is the model of how a one-line selection change is tracked
  rather than silently absorbed.
- **MC validation is adversarial.** MV0 v1 was rejected when its χ²/ndf = 2934 was traced to a
  wrong baseline definition; MV3 v3 was reported as FAIL rather than papered over — and the
  Phase-2 diagnosis then falsified its own "missing material" story and re-graded it TENSION
  (unsimulated trigger). The MV program distinguishes comparison-level failures (what is being
  compared — trigger selection, event basis, species) from model failures (geometry, code bugs),
  and requires the distinction to be tested, not asserted.

---

## Open questions: closed vs. still open

### Closed by MC validation

_(Corrected 2026-07-03: R_max, digitizer gain, anomaly species, and the MV2 range-energy mechanism
were moved back to "Still open" following the external review. Updated 2026-07-04: the post-review
program closed the rows added below.)_

| Question | Closed by | Finding |
|---|---|---|
| Is p/d PID at AUC 0.986 real? | MV1 (rerun 2026-07-03) | Yes as an MC truth ceiling; data within 0.5% via weak-label proxies, not species truth |
| What caused the MV3 stopping-depth FAIL? | Phase 2 (2026-07-03) + real `Trig_bar` SD sim (2026-07-05) | **Mechanism ESTABLISHED** by a real `Trig_bar` sensitive-detector simulation: the unsimulated two-arm coincidence trigger, not missing material (falsified: ~0.13 g/cm² air missing vs ≥10.5 needed). Untriggered B2 45.9% (χ²/ndf 68,705) → real triggered 99.7%, toward data 93.3%. **Quantitative closure NOT achieved** — the ideal trigger over-purifies (99.7% vs data 93.3%); the proxy χ²/ndf ≈ 625 is retired as over-optimistic; residual ~7–12% deep-stave data population is data-side (NEW-04). MV3 stays TENSION |
| Is Sample I deuteron-enriched? | S21 + S23 (2026-07-03) | Confirmed at truth level (B2 f_d ratio 1.519 [1.510, 1.528]; exclusive 1.912); consistent in data (B2 f(A>5000) ratio 3.45 [3.41, 3.50]; run-set/beam drift bounded ≤~29% by B-M6); MC under-predicts the contrast (DR 0.738, z = −99 statistics-only; disjoint run-set/beam systematics not included) |
| Is the early-peak anomaly class C12 recoils? | MV6b (2026-07-04) | **No — ruled out.** 0/1,656 quenched C12 records pass A>1000 at any gain (60–297); the class must be instrumental/trigger-phase (data-side question, P02/P09) |
| Does ML two-pulse recovery maintain failure rate on true overlaps? | MC03/S24 (2026-07-04) | Truth-labelled honest benchmark: traditional wins at matched 80% coverage (≤0.0001 vs 0.0001–0.0002); ML wins at full coverage (0.011 vs 0.048); common-subset dt σ68 trad 0.64 vs ML 0.89 ns |
| What is the p/d range-energy mechanism (quantitative)? | MV2 rerun (2026-07-03) | MeV-scale ekin after the momentum-unit fix; containment p 0.70 / d 0.84; Birks lookup remains best (geometry/trigger caveat) |
| Is the zero-signal pedestal model validated? | MV7 (2026-07-03, MC-level) | Adaptive MAE 3.48 ADC, learned 1.50 ADC on zero-signal MC — lower bounds; data still has no true-pedestal sample |

### Still open

| Question | Blocker | Path to close |
|---|---|---|
| Does MC timing match data in a matched comparison? | MV4 honest rerun (2026-07-03) is REVIEW: MC pair-equivalent 2.087 ns sits between the data raw (2.993) and corrected (1.50) anchors, but merged-track MC vs per-stave data and unmatched selection remain | Matched per-stave MV4 rerun on the Phase-1 digitizer (data selection applied, measured σ_data) |
| Can the residual MV3 tension be closed? (mechanism established; ideal trigger over-purifies, B2 99.7% vs data 93.3%) | The real `Trig_bar` SD sim is DONE; the residual is now **data-side** — accidental/pile-up coincidences absent in the truth MC, Sample-I purity, paddle threshold/resolution fidelity, LayerID→stave mapping | **Model the data-side deep-stave coincidence population** (accidental/pile-up rate model, Sample-I purity, paddle fidelity) — STUDY_GAPS NEW-04; no new GEANT4 production needed |
| Why does the MC live-time exceed data by +8%? | MC03 τ_eff 134.99 vs data 124.79 ns is B2-driven; MC pulses are clean by construction, data includes real pathologies | Data-matched selection/pathology model on the MC side; per-stave comparison |
| What is the precision digitizer gain? | Quenched re-scan DONE 2026-07-05 (LUNARC 3348264): the trigger-consistent optimum is **~65 ADC/MeV (band ~60–70)**, up from the unquenched ~60, far below the 297 placeholder; B2 amplitude median 2,917 ADC brackets data 2,576 | Still a **band, not precision** — residual set by the trigger proxy (B-M1); re-anchor on a geometry-robust observable next (`reports/mv3_gain_quenched_1783240619/`) |
| What instrumental mechanism produces the 4.4% early-peak class? | Species/scintillation origin ruled out (MV6b); MC has no trigger-phase or DAQ-artifact model | **Data-side investigation of the early-peak class** (P02 cluster morphology, P09 taxonomy; baseline/noise/bipolar and trigger-phase hypotheses) |
| Is the forced-pedestal model validated on data? | No forced-trigger sample in data (MV7 closes the MC side only) | Add forced-trigger capability to the acquisition in a future beam run |

---

## Provenance and uncertainty conventions

- All sigma values are robust **sigma68** unless explicitly stated as Gaussian core. Timing CIs are
  bootstrap (1000 resamples) or LORO SEM as noted in each source report.
- AUC values are quoted to 4 decimals from the MV1 truth summary
  (`reports/mv1_mv2_truth_pid_energy_1782220258/mv1_mv2_truth_summary.json`).
- MC truth from GEANT4 (`hibeam_g4`, official HIBEAM-NNBAR source, conda env `nnbar_env`, GEANT4
  11.2.2 / ROOT 6.32), 1M primary events; `geant4/results/sim_summary.json` and SLURM job 3310358.
- MV0 v2 gain (92 ± 28 ADC/MeV) and MV0 v1 (~246 ADC/MeV) are both retracted (2026-07-03). Do not
  use either value for any energy-scale reference. The current best statement (2026-07-04) is
  gain ≈ 60–70 ADC/MeV, dominated by trigger/quenching modelling — no precision value yet; 297
  ADC/MeV in the mc02 card is an explicit placeholder.
- Every per-section number above is traceable to a `reports/<id>/REPORT.md`; see `reports/SUMMARY.md`
  for the live scoreboard and `docs/REPORT_STANDARD.md` for the rules each report obeys.

_This synthesis is regenerated as the program advances. When a study or MV closes an open question,
follow `docs/REPORT_STANDARD.md` section 10 to update this file, `reports/SUMMARY.md`, and
`PROJECT_REPORT.md` in one pass._
