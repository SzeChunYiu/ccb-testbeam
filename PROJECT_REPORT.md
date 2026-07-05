# CCB Test-Beam — Project Report & Status

**One document with everything a human needs to know about this project: the science, what has been
done, the results, the current state, what is blocking us, and what comes next.**

- **Last updated:** 2026-07-04 — post-review program complete (Phases 0–4 + statistics hardening; see `FINDINGS_SYNTHESIS.md` "Post-review program (2026-07-03/04)"). Corrected 2026-07-03 following External Review 2026-07-02 (`EXTERNAL_REVIEW_2026-07-02.md`)
- **Repository:** `SzeChunYiu/ccb-testbeam` (branch `main`); canonical tree on LUNARC at
  `/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam/`
- **Status:** research in progress — all numbers **preliminary, not peer-reviewed**
- **This file is the status entry point.** The science is distilled in `FINDINGS_SYNTHESIS.md`; the
  reporting rules are in `docs/REPORT_STANDARD.md`; a newcomer should start at
  `docs/ANALYSIS_GUIDE.md`. Per-study detail is in `reports/<id>/REPORT.md`; the live scoreboard is
  `reports/SUMMARY.md`.

---

## 1. TL;DR (read this first)

| | |
|---|---|
| **What** | Data-driven analysis of CCB test-beam data (190 MeV protons on a CD2 target, HRD scintillator range stacks), now cross-validated against a GEANT4 Monte-Carlo truth bridge. |
| **Physics goals** | (1) same-particle **timing resolution** of the staves; (2) **pile-up** characterisation; (3+) energy/PID, now reachable via MC. |
| **Data** | 640,737 selected B-stack pulses (median selector) / 706,373 (dynamic selector), 18-sample waveforms @ 10 ns. ~6.4 GB, stored **outside git**, immutable. |
| **Method discipline** | Reproduce-first, traditional **and** ML head-to-head, atomic decomposition, three leakage controls, explicit MC verdict per study. See `docs/REPORT_STANDARD.md`. |
| **Done so far** | ~230 data-driven studies + the full 2026-07-03/04 **post-review program** (External Review corrections, Phases 0–4, statistics hardening): MV3 mechanism ESTABLISHED by a real `Trig_bar` sensitive-detector simulation (unsimulated two-arm coincidence trigger, not missing material: untriggered B2 45.9% → triggered 99.7%; re-graded TENSION, quantitative closure still open), Sample-I D-enrichment confirmed at truth level (S21) and **consistent in data** (S23; run-set differences not yet separated), per-stave timing vs amplitude measured (S22), honest two-pulse benchmark + first independent MC live-time (MC03/S24), physical Birks + MV6b (C12 ruled out) + MV7 pedestal closure, program-level FDR census (STATS01). |
| **Headline science** | Analytic timewalk wins timing (sigma68 ~1.49-1.55 ns; per-stave ~0.85-1.1 ns at high amplitude, S22); pile-up R_max revised down 4.2 -> ≤3.05 MHz (one-sided bound + estimator band ≈2.1 MHz; independent MC live-time +8%, MC03 — tightens the bound if real, does not validate); ML wins shape-closure tasks; **p/d PID MC-closed at AUC 0.986** (MC truth ceiling; data via weak-label proxies, not species truth); Sample-I D-enrichment confirmed at truth level (S21 ratio 1.519) and consistent in data (S23 ratio 3.45; run-set differences not yet separated). |
| **Biggest open item** | Gain has **no precision value** (honest statement: ≈60–70 ADC/MeV, dominated by trigger/quenching modelling; quenched re-scan DONE 2026-07-05 (~65 measured)). The `Trig_bar` sensitive-detector simulation is now DONE (2026-07-05, real 1M production): it establishes the trigger as the MV3 mechanism but does NOT achieve quantitative closure (ideal trigger over-purifies, B2 99.7% vs data 93.3%); the residual deep-stave population is now a **data-side** question (accidental/pile-up coincidences, Sample-I purity, paddle fidelity, mapping) — STUDY_GAPS NEW-04. Early-peak 4.4% class is a **data-side** question (C12 ruled out by MV6b). |

---

## 2. The measurement (science in brief)

At the Cyclotron Centre Bronowice (CCB, Krakow) a **190 MeV proton beam** strikes a **deuterated
polyethylene (CD2)** target. Charged particles leaving the target are recorded by **two independent
HRD scintillator range stacks** (A and B) at **conjugate angles**, each ~1 m from the target and
each behind its **own trigger scintillators**, with a **TPC in front of stack A** (experiment-owner
setup facts, 2026-07-03). Each stack acts as a data-driven **ΔE-E / range telescope**; the two arms
measure **different particles** — pd-elastic sends the proton into one arm and the kinematically-
correlated deuteron into the other.

For each stave we record an **18-sample waveform at 10 ns spacing**, read out at one end via a
wavelength-shifting (WLS) fibre, and reconstruct an amplitude (ADC), a time (ns), and shape
variables. The main analysis uses **B-stack staves B2, B4, B6, B8**; the **A-stack (A1, A3)** is an
independent arm measuring **different particles** — an independent methodology check, not a
same-particle cross-check (corrected 2026-07-03, experiment-owner setup facts).

**The two original goals, plus the MC-enabled third:**
1. **Timing resolution** — how precisely a stave (and a multi-stave event) timestamps a particle,
   from same-particle inter-stave time residuals.
2. **Pile-up** — how often overlapping pulses corrupt time/charge, and at what beam rate it becomes
   limiting.
3. **Energy / PID** — truth-limited in data; now addressed via the GEANT4 bridge (MV1/MV2 done).

**The samples**

| Sample | Stack | Enrichment | Role |
|---|---|---|---|
| Sample I (runs 31-57) | B | terminal-B2-like; D-enrichment **confirmed at truth level** (S21: B2 f_d ratio 1.519), **consistent in data** (S23: B2 f(A>5000) ratio 3.45; run-set differences not yet separated) | topology-heavy |
| Sample II (runs 58-65) | B | p-enriched, penetrating | clean timing reference |
| Sample III / IV | A | = Sample I / II runs | A-arm data (different particles) |

**Trigger definitions (experiment-owner setup facts, 2026-07-03):** Sample I = **A AND B trigger
coincidence** (MC mimic: a charged particle entering the first A and the first B layer within
15 ns); Sample II = **B trigger only** (A ignored). In MC, Sample I is a **subset** of Sample II
(inclusive flags in `src/ccb_mc_validation/io/root_truth.py`); in data, Samples I and II are
**disjoint run sets** taken with different trigger configurations — MC-vs-data sample comparisons
must state this asymmetry. Matthias's deuteron enrichment of Sample I in the first B layer is
**confirmed at truth level and consistent in data** (2026-07-03): at truth level by S21 (B2 f_d
ratio I/II = 1.519 [1.510, 1.528]; exclusive 1.912; 91.2% of Sample-I events are d-into-B / p-into-A
pairs) and, on the data side, by S23 (Sample-I B2 high-amplitude fraction ratio 3.45 [3.41, 3.50]) —
but in data Samples I and II are disjoint run sets, so run-set/beam differences are not yet separated
from the trigger. The mechanism is the coincidence tagging kinematically-correlated pd-elastic pairs;
MC under-predicts the between-sample contrast (S23 double ratio 0.738, z = −99 — statistics-only
significance; systematics from disjoint run-sets/beam conditions not included), consistent with the
Phase-2 finding that the trigger is not simulated.

---

## 3. Status dashboard (study families)

Each row is a study family; per-row detail in `reports/SUMMARY.md`. "ML verdict" uses the
`docs/REPORT_STANDARD.md` taxonomy (wins / ties / loses / CORRECTED / gated).

| Family | Studies | Status | Headline | ML verdict |
|---|---|---|---|---|
| **S00** data gate | S00, S00a-d | ✅ done | 640,737 exact (median); 706,373 (dynamic) | n/a (deterministic) |
| **S01** templates | S01 | ✅ done | AE/PCA basis MSE 0.00208 vs template 0.0444 | ML wins (Delta=-0.0423, CI excl. 0) |
| **S02** pickoff | S02, S02b-d | ✅ done | analytic timewalk 1.49-1.55 ns; CFD20 1.846 ns | trad wins (analytic) |
| **S03** timewalk | S03a-e, S03k | ✅ done | analytic 1.494-1.551 ns champion; S03k 1.107 ns gated | CORRECTED (LORO) / S03k gated |
| **S05** covariance | S05c-e | ✅ done | B2/topology-dominated; ExtraTrees 1.352 ns | small ML gain, support-bounded |
| **S07** ML rigour | S07, S07b-k | ✅ done | D_t/curvature AUC~1.0 self-referential | CORRECTED (leakage) |
| **S10** pile-up | S10, S10b-m | ✅ done | R_max 4.22 -> 3.05 MHz; live10 124.79 ns | trad physics-facing; ML diagnostic |
| **S11** two-pulse | S11a-b | ⛔ superseded by S24 | S11a benchmark was rigged (review P8); its 0.295/0.168 failure rates are retired. Honest benchmark: MC03/S24 | see S24 row |
| **S13** CWoLa | S13b-c | ✅ done | topology ratio 1.445 vs CWoLa 1.220 | ML monitoring only |
| **S16** pedestal | S16, S16b-g | ✅ done | learned MAE 48.9 vs 341 ADC; no true pedestal | ML win, proxy-only |
| **S18** A-stack | S18, S18b | ✅ done | A1-A3 1.389 ns reproduces note | trad (CIs overlap) |
| **P02** representation | P02, P02b-e | ✅ done | AE +40-51% @ dim<=4; PCA wins dim 8 | ML wins (compact only) |
| **P01** downstream rep | P01a-f | ✅ done | latent does not beat hand-crafted | CORRECTED (leakage) |
| **P03** deep timing | P03a-c | ✅ done | MLP/CNN lose to analytic | trad wins |
| **P04** amplitude | P04, P04c-e | ✅ done | res68 0.003-0.009 vs 0.12-0.20 | ML wins (decisive) |
| **P07** saturation | P07, P07b-e | ✅ done | ML res68 0.032-0.046 vs 0.104-0.286 | ML wins (3-7x) |
| **P09** anomaly | P09a, P09c | ✅ done | ~4.4% early-peak class; C12 ruled out (MV6b 2026-07-04) — instrumental/trigger-phase, data-side question | ML for novelty; cuts for precision |
| **P10** cond. template | P10a-b | ✅ done | analytic timewalk beats learned template | trad wins |
| **S21** trigger truth | S21 | ✅ done (2026-07-03) | Sample-I D-enrichment confirmed at truth level: B2 f_d ratio 1.519 [1.510, 1.528] (excl. 1.912); 91.2% d\|p pairs | n/a (truth study) |
| **S22** timing vs amplitude | S22 | ✅ done (2026-07-03) | per-stave σ68 vs amplitude; 1/A beats 1/√A raw; ~0.85-1.1 ns/stave at high amplitude; B2 saturation-excluded | n/a (traditional measurement) |
| **S23** data I/II + MC | S23 | ✅ done (2026-07-03) | D-enrichment consistent in data (B2 f(A>5000) ratio 3.45; run-set differences not yet separated); trigger mimic moves MC toward data (KS 0.192→0.131, χ² 624k→20k); DR 0.738 (z=−99, statistics-only) | n/a (data–MC comparison) |
| **S24** honest two-pulse (MC03) | S24 | ✅ done (2026-07-04) | truth-labelled: trad wins at matched 80% coverage; ML wins at full coverage (0.011 vs 0.048); σ68 trad 0.64 vs ML 0.89 ns | split verdict (coverage-dependent) |

---

## 4. MC validation status (MV0-MV9)

All six MV studies ran to completion. Following External Review 2026-07-02, MV0/MV5/MV6 were
retracted; the 2026-07-03/04 post-review program then reran MV2 and MV4, and established MV3's
root-cause mechanism with a real `Trig_bar` sensitive-detector simulation (2026-07-05: the unsimulated two-arm trigger, not missing material; re-graded TENSION, quantitative closure still open), ruled the
MV6 C12 attribution out (MV6b), and ran MV7 (see rows below).

| MV | What it validates | Status | Result |
|---|---|---|---|
| **MV0** | Digitizer gain calibration | ⛔ **RETRACTED** (2026-07-03) | v2 gain 92 ± 28 ADC/MeV retracted: anchor was \|net−pedestal\| of an already baseline-subtracted amplitude (true B2 net median 5752 ADC, not 1781), unreproducible from any committed script; v1 (~246) also invalid. **Current best statement: gain ≈ 60–70 ADC/MeV, dominated by trigger/quenching modelling — no precision value yet** (Phase-2 trigger-consistent scan optimum ~60, unquenched; quenched re-scan DONE 2026-07-05: ~65 measured; 297 is the placeholder card value). |
| **MV1** | p/d PID (truth ceiling) | ✅ PASS (MC truth ceiling; data = weak-label proxy) | HGB AUC **0.9860**, logreg 0.9629, cut purity 0.8910; purity@90%eff 0.9644 (400,369 truth tracks). AUC 0.986 is the **MC truth ceiling**; data reaches within 0.5% only via **weak-label proxies, not species truth** |
| **MV2** | Energy / range / stopping | ✅ rerun 2026-07-03 (untriggered-MC caveat) | momentum-unit fix landed: MeV-scale ekin (mean p 99.4 / d 79.7 MeV); edep medians p 101.1 / d 73.4 MeV; containment p 0.70 / d 0.84 (**untriggered MC — not trigger-representative**). Depth ordering (deuterons stop layers 0-1, protons penetrate 4-7) supported |
| **MV3** | Stopping-depth profile (Layer↔stave) | 🔶 **TENSION** (re-graded from FAIL, Phase 2, 2026-07-03; mechanism ESTABLISHED 2026-07-05) | Mechanism **ESTABLISHED by a real `Trig_bar` sensitive-detector simulation** (full 1M, job 3348610): the **unsimulated two-arm coincidence trigger**, not geometry, drives the discrepancy — untriggered MC B2 45.9% (χ²/ndf 68,705, reproduces the published FAIL) → real triggered 99.7%, toward data 93.3%. Missing-material narrative **falsified** (only ~0.13 g/cm² air missing vs ≥10.5 g/cm² needed). **Quantitative closure NOT achieved:** the ideal truth trigger **over-purifies** (B2 99.7% vs data Sample I 93.3%; profile not reproduced). The earlier proxy headline **χ²/ndf 68,269 → 625 (109×) is RETIRED as over-optimistic** (coincidence MC vs mixed all-data with a fortuitously loose A-HRD threshold). Residual (data keeps a ~7–12% deep-stave coincidence population the ideal trigger lacks) is now **data-side** — STUDY_GAPS NEW-04. (`reports/mv3_v5_realtrigger_1783242005/`, `reports/phase2_geometry_1783108797/`) |
| **MV4** | Timing σ₆₈ reproduction in MC | ⚠️ **REVIEW** (honest rerun 2026-07-03) | rising-edge CFD + physical timewalk sign (B = +39.6 ns·ADC); MC pair-equivalent σ₆₈ 2.087 ± 0.009 ns sits between data raw (2.993) and corrected (1.50) anchors; matched per-stave rerun awaits Phase-1 digitizer (`reports/mv4_timing_1783077795/`) |
| **MV5** | Pile-up R_max from live-time model | ⛔ RETRACTED as validation → slot refilled (MC03, 2026-07-04) | The 2026-06 "MC τ_eff" was a hardcoded copy of the data value. **First honest MC live-time: τ_eff = 134.99 ns [134.96, 135.01]** (statistics only; the +8% / +10.2 ns offset from data 124.79 ns is the dominant, systematic, difference) **vs data 124.79 ns (+8%, B2-driven) — an honest disagreement.** The 4.22 → ≤3.05 MHz correction stands as **one data-driven one-sided upper bound plus estimator band (censoring-aware estimators suggest ≈2.1 MHz or lower)**; the +8% MC excess, if real, tightens the bound rather than validating it (`reports/mc03_overlay_1783180480/`) |
| **MV6** | Anomaly species ID (early-peak class) | ⛔ RETRACTED → **MV6b: C12 RULED OUT** (2026-07-04) | Honest redo with physical Birks quenching: 0/1,656 quenched C12 records pass A>1000 at any gain (60–297); MC early-peak fraction 0.000% everywhere vs data 4.4%. Class must be instrumental/trigger-phase — reopened as a **data-side** question (P02/P09 leads) (`reports/mv6b_anomaly_quenching_1783180742/`) |
| **MV3b** | Upstream material budget estimation (MV3 FAIL diagnosis) | ⛔ superseded by Phase 2 | The toy 8–10 g/cm² estimate was retracted in MV3b's own errata; Phase 2 then **falsified** the material hypothesis outright (available missing material ≲0.8 g/cm² vs ≥10.5 needed) and identified the trigger as the cause. See `reports/phase2_geometry_1783108797/` |
| **MV4b** | Physical timewalk model diagnosis (MV4 TENSION diagnosis) | ✅ done, confirmed by the MV4 rerun | Toy 1/√ADC with B=−23 ns·√ADC was **unphysical** (B<0). Correct form: 1/A = τ_rise·V_th/A; the MV4 honest rerun with rising-edge CFD fits B = +39.6 ns·ADC (physical). See `reports/mv4b_timewalk_model/` |
| **MV7** | Zero-signal pedestal validation | ✅ done (2026-07-03, MC-level) | adaptive pedestal MAE **3.48 ADC**, learned **1.50 ADC** on 100k zero-signal MC records — lower bounds (no correlated noise/drift modelled); data still has no true-pedestal sample (`reports/mc02_pulse_table_1783107862/`) |
| **MV9** | MC synthesis | ⚠️ pre-review artifact | the 2026-06 "6/6 PRODUCTION" registry predates the external review and the post-review re-grades; superseded by `FINDINGS_SYNTHESIS.md` "Post-review program (2026-07-03/04)" |
| **MV8** | Two-ended readout | reserved | — |


## 5. Key findings, ranked by physics impact

The **Grade** column is the load-bearing verdict (words + number); any emoji is a mnemonic only.
Grade key: **G1 Validated** (truth + data, no dominant unquantified systematic) · **G2
Confirmatory/negative** (clean exclusion or truth ceiling) · **G3 Indicated / consistent**
(directional; a dominant systematic or confound unseparated) · **G4 Under review / bound**
(provisional or one-sided) · **G5 Corrected/retracted**.

| # | Finding | Number (with uncertainty) | Grade | Source |
|---|---|---|---|---|
| 1 | Pile-up R_max revised down ~30% | 4.222 -> ≤3.05 MHz one-sided bound + estimator band ≈2.1 MHz (live10 124.79 ns, CI [123.33,126.36]); first independent MC live-time 134.99 ns (+8%, statistics-only CI; the +8% offset is the dominant systematic — tightens the bound if real, does not validate) | **G4 Under review / bound** (data-driven; MC +8%) | S10b/c, MC03 |
| 2 | p/d PID is MC-closed (truth ceiling) | AUC 0.9860 (HGB) MC truth ceiling; data ~0.985 via weak-label proxies, not species truth | **G2 Confirmatory** (MC truth ceiling; data = weak-label proxy, not species truth) | MV1 |
| 3 | Sample-I deuteron enrichment | truth: B2 f_d ratio 1.519 [1.510,1.528] (excl. 1.912); data: B2 f(A>5000) ratio 3.45 [3.41,3.50]; MC under-predicts contrast (DR 0.738, z=−99, statistics-only) | **G2/G3** confirmed at truth level; **consistent in data** (run-set differences not yet separated) | S21/S23 |
| 4 | MV3 stopping-depth root cause = unsimulated trigger | Mechanism established by a real `Trig_bar` SD simulation: untriggered B2 45.9% (χ²/ndf 68,705) → triggered 99.7% (toward data 93.3%); material narrative falsified. Quantitative closure NOT achieved (ideal trigger over-purifies; proxy χ²/ndf ≈ 625 retired as over-optimistic); residual ~7–12% deep-stave data population is data-side (NEW-04) | **G3 Indicated** — mechanism ESTABLISHED (real trigger); quantitative closure OPEN; TENSION (re-graded from FAIL) | Phase 2 / MV3 v5 |
| 5 | Analytic timewalk wins timing | sigma68 1.494-1.551 ns (LORO); best trad 1.343 ns; per-stave ~0.85-1.1 ns at high amplitude (S22) | **G4 Under review** (data-only; MV4 REVIEW after honest rerun) | S03/S02d+S16e/S22 |
| 6 | Duplicate-readout amplitude closure | res68 0.003-0.009 vs 0.12-0.20 | **G4 Data-only** — reported, not yet FDR-certified (no machine-readable delta-CI in STATS01) | P04 |
| 7 | Saturation recovery by ML | res68 0.032-0.046 vs template 0.104-0.286 | **G4 Data-only** — reported, not yet FDR-certified (no machine-readable delta-CI in STATS01) | P07 |
| 8 | Absolute energy unreachable from data | res68 0.19-0.25 (fails 10%) | **G2 Confirmatory limitation** (data-side; MV2 rerun supports) | S14/MV2 |
| 9 | Two-pulse recovery, honest truth-labelled benchmark | trad wins at matched 80% coverage (fail ≤0.0001 vs 0.0001-0.0002); ML wins at full coverage (0.011 vs 0.048); σ68 trad 0.64 vs ML 0.89 ns. Replaces the rigged S11a table (0.295/0.168 retired) | **G2 Truth-labelled** (MC03/S24, 2026-07-04; fixed trigger phase / single-stave caveats) | MC03/S24 |
| 10 | Representation-superiority claim is leakage | latent does not beat hand-crafted under controls | **G5 Corrected** | P01a-f |
| 11 | Early-peak anomaly class is NOT C12 | 0/1,656 quenched C12 records pass A>1000 at any gain; MC early-peak 0.000% vs data 4.4% — instrumental/trigger-phase, data-side question | **G2 Confirmatory/negative** (clean exclusion, MC-confirmed, MV6b 2026-07-04) | P02/P09/MV6b |

### 5.1 Status of each headline result (consolidated)

This is the single honest status table for the whole program. It uses the words+number grade key
above (G1–G5); the emoji elsewhere in this repo are mnemonics, not the verdict.

**Bottom line: there is no single fully-validated (G1) primary physics result yet.** The cleanest
results are the **negative / confirmatory** ones — the C12 exclusion (MV6b) and the p/d PID truth
ceiling (MV1) — not a novel positive measurement. Every would-be positive headline is either a
one-sided bound (R_max), under review (timing σ₆₈), reported-but-not-FDR-certified (P04/P07),
directionally indicated with an unseparated systematic (MV3 trigger, data-side enrichment), or
carries a statistics-only CI dominated by a %-level systematic.

| Headline | Grade | Truth-validated? | Data-validated? | Dominant caveat |
|---|---|---|---|---|
| C12 exclusion (early-peak class) | **G2** | Yes (MV6b) | n/a (exclusion) | Positive identity of the 4.4% class still open |
| p/d PID AUC 0.986 | **G2** | Yes (MC ceiling) | Weak-label proxy only | Data side is not species truth |
| Absolute-energy limitation | **G2** | Yes (MV2) | Yes (data) | — (a confirmed *limitation*, not a measurement) |
| Pile-up R_max ≤ 3.05 MHz | **G4** | No | One-sided bound | MC +8% live-time; band to ≈2.1 MHz; statistics-only CI |
| Sample-I d-enrichment | **G2 truth / G3 data** | Yes (S21) | Consistent only (S23) | Data run-sets disjoint; beam differences unseparated |
| MV3 root cause = trigger | **G3** | Mechanism established (real `Trig_bar` SD) | Not reproduced | Ideal trigger over-purifies (B2 99.7% vs data 93.3%); proxy χ²/ndf ≈ 625 retired; residual data-side (NEW-04) |
| Analytic timewalk timing σ₆₈ | **G4** | MV4 REVIEW | Data-only | Mixed metric; covariance withdrawn; partition unused |
| Duplicate-readout / saturation ML wins (P04/P07) | **G4** | n/a | Data-only | No machine-readable delta-CI; not in STATS01 FDR census |
| Two-pulse split verdict (MC03/S24) | **G2** | Truth-labelled | n/a | Fixed trigger phase; single-stave overlays |
| Representation-superiority claim | **G5** | — | Corrected | Failed run-family / event-block leakage controls |

---

## 6. Data and where everything lives

| What | Path | Notes |
|---|---|---|
| **Canonical tree (LUNARC)** | `/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam/` | this report, docs, reports, geant4 |
| **Canonical data store** | `/home/billy/ccb-data` (outside repo, immutable) | survived the 2026-06-08 data-loss incident |
| → raw | `…/ccb-data/raw/` | `sorted-a/b.zip`, `root.zip` — sha256-verified vs S00 |
| → extracted | `…/ccb-data/extracted/` | 110 ROOT files (57 hrda + 53 hrdb + sorted), 6.1 GB |
| GEANT4 truth | `geant4/data/output_krakow_1M.root` | 1M-event `hibeam` tree (PDG, Ekin, per-stave EDep/time) |
| Processed S00 table | `data/processed/s00_selected_b_pulses.csv.gz` | git-ignored; regenerate from raw (S01b) |
| Study plan | `studies/STUDIES.md` | S00-S18 + P01-P11, prioritised |
| Per-study results | `reports/<study>/REPORT.md` | one dir per study + `manifest.json` + figures |
| Scoreboard | `reports/SUMMARY.md` | rolling one-row-per-study table |
| Reporting standard | `docs/REPORT_STANDARD.md` | the rules every report obeys |

**Data-safety rules (from the 2026-06-08 incident):** data is read-only, external, immutable, backed
up; never store the only data copy in an agent's working tree. Full post-mortem in `fleet/LESSONS.md`.

---

## 7. Infrastructure status

- **Compute:** LUNARC (fs10 mounted on compute nodes; interactive via `ssh cosmos2`). GEANT4 jobs run
  under SLURM (`geant4/jobs/*.sbatch`). MV1/MV2 ran on cn039.
- **Analysis env:** Python 3.11, `uv`-managed, scikit-learn 1.4.x, numpy/scipy, matplotlib (dpi=130
  figures). GEANT4/ROOT via conda env `nnbar_env` (GEANT4 11.2.2, ROOT 6.32, VGM 5.4.0).
- **Fleet (legacy local):** sandboxed codex workers + keeper; codex pinned at 0.129.0-alpha.15
  (never upgrade). The 0.129 sandbox `.git`/queue write bug is worked around with an external
  bubblewrap jail (`~/.tb-bwrap-codex.sh`). On LUNARC the work is now driven via SLURM rather than the
  local fleet.
- **Code review graph:** `.code-review-graph/` present; use graph tools before grep/read.

---

## 8. Open actions for humans (operator-only)

These cannot be done by an agent and block specific next steps:

1. ✓ MV4/MV5/MV6 SLURM jobs **done**; ✓ post-review program (Phases 0–4 + statistics hardening)
   **done** (2026-07-03/04).
2. ✓ **MV3 mechanism ESTABLISHED by a real `Trig_bar` sensitive-detector simulation** (2026-07-05,
   full 1M production; superseding the Phase-2 truth proxy): the discrepancy is driven by the
   unsimulated two-arm coincidence trigger, not geometry (untriggered B2 45.9% → triggered 99.7%,
   toward data 93.3%); re-graded TENSION. **Quantitative closure is NOT achieved** — the ideal
   trigger over-purifies (B2 99.7% vs data 93.3%), so the residual ~7–12% deep-stave data population
   is now a **data-side** question (STUDY_GAPS NEW-04), not a new production. Remaining decision:
   close or rework geobuilder PR #8 (its 2.51 g/cm²/pair default injects ~10× the realistic
   wrapping budget).
3. **Provide or confirm there is no forced-trigger/random pedestal sample** in the original DAQ; if
   one exists off-tree, it closes the S16 pedestal validation directly (MV7 closes the MC side
   only).
4. **Sign off on the GEANT4 production macro / event-to-HRD alignment** before MV results are quoted
   as a production calibration (currently a layer-level prior + smoke-tested truth tree).
5. **Adoption policies now decidable on honest evidence:** S03k is withdrawn (falsified by
   S03p/S03r; any sub-0.3 ns claim needs the confirmation partition, `docs/CONFIRMATION_PARTITION.md`,
   which is **defined but not yet used** — so sub-0.3 ns timing claims are not yet confirmed on
   held-out data);
   two-pulse recovery has a split truth-labelled verdict (MC03/S24: traditional at matched 80%
   coverage, ML at full coverage) — choose the operating point.

---

## 9. Next steps (queued analyses)

| Priority | Item | Closes | Blocker |
|---|---|---|---|
| ~~P0~~ **DONE** | ~~Score `Trig_bar` volumes as sensitive detectors → real per-event trigger flag~~ **completed 2026-07-05** (real 1M SD production, LUNARC 3348610/3348673) | MV3 mechanism established (untriggered B2 45.9% → triggered 99.7%); **but** ideal trigger over-purifies (99.7% vs data 93.3%), quantitative closure NOT achieved | `reports/mv3_v5_realtrigger_1783242005/`; residual now data-side → STUDY_GAPS NEW-04 |
| P0 | **Data-side residual: model accidental/pile-up coincidences + Sample-I purity + paddle fidelity + LayerID→stave mapping** | residual MV3 deep-stave data population (~7–12%) the ideal trigger lacks; S23 double-ratio deficit | STUDY_GAPS NEW-04 (data-side/digitizer, no new GEANT4 production) |
| ~~P0~~ **DONE** | ~~Quenched trigger-consistent gain re-scan~~ **completed 2026-07-05** (LUNARC 3348264) | optimum **~65 ADC/MeV** (band ~60–70), chi2/ndf 322 vs unquenched-60 625 / placeholder-297 7,751 | `reports/mv3_gain_quenched_1783240619/`; residual band = trigger-proxy systematic (see B-M1) |
| P1 | **Early-peak 4.4% class: data-side instrumental investigation** (P02 morphology, P09 taxonomy; baseline/noise/bipolar and trigger-phase hypotheses) | anomaly mechanism (species origin ruled out by MV6b) | data-side study; no MC blocker |
| P1 | MV4 matched per-stave rerun (data selection applied, measured σ_data) | MC-vs-data timing verdict (currently REVIEW) | Phase-1 per-stave digitizer table (exists: mc02) + comparison script |
| P1 | Reconcile MC live-time +8% excess (134.99 vs 124.79 ns, B2-driven) | honest MC-vs-data live-time statement | data-matched selection/pathology model on MC side |
| P2 | Validate P07 saturation on real B2>7000 pulses | production saturation use | strengthen S01 template baseline |
| P2 | Two-ended-readout √2 projection with correlated terms | timing projection bias | MV8 (reserved) |

---

## 10. Map of the documentation

| You want… | Read |
|---|---|
| New to the project? Start here | **`docs/ANALYSIS_GUIDE.md`** |
| Status + results overview | **`PROJECT_REPORT.md`** (here) |
| The distilled science | **`FINDINGS_SYNTHESIS.md`** |
| The rules every report obeys | **`docs/REPORT_STANDARD.md`** |
| Master index of all docs | `docs/INDEX.md` |
| Physics background, detail | `docs/00_overview.md` … `docs/09_open_questions.md`, `docs/glossary.md` |
| The full prioritised study plan | `studies/STUDIES.md` |
| A single study's full write-up | `reports/<study>/REPORT.md` + its `manifest.json`/figures |
| The rolling scoreboard | `reports/SUMMARY.md` |
| MC validation architecture | `docs/mc_validation/` (ADR-0001, TASK_LEDGER.md) |
| Data location & manifest | `DATA.md`, section 6 above |
| Standing mistakes to avoid (leakage, etc.) | `fleet/LESSONS.md` |
