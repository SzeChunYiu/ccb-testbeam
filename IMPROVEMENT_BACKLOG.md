# Improvement Backlog — consolidated from the nature-skills subskill pass (2026-07-05)

Sources: nature-reviewer (`reports/nature_reviewer_report.md`), nature-figure
(`docs/figures/FIGURE_MANIFEST.md`), nature-writing (`MANUSCRIPT.md`),
nature-data (`docs/DATA_AVAILABILITY.md`), nature-academic-search/citation
(`docs/RELATED_WORK.md`, `docs/references.bib`). This backlog is the running
list of what would raise the analysis from "honest and corrected" to
"publication-defensible". Status: PLANNED unless marked.

## Major (blocking for a submission-grade claim)

| ID | Item | Origin | Maps to existing gap | Effort |
|----|------|--------|----------------------|--------|
| ~~B-M1~~ | ✅ **DONE 2026-07-05** ([MV3 v5](reports/mv3_v5_realtrigger_1783242005/REPORT.md), LUNARC jobs 3348610/3348673). Scored `Trig_bar` as a real GEANT4 SD and ran a full 1M `Trig_bar`-scored production (`output_krakow_1M_trig.root`). The real two-arm coincidence **establishes the trigger as the mechanism** (untriggered B2 45.9% → triggered 99.7%) but **over-purifies** — MC B2 99.7% vs data Sample I 93.3%, profile NOT reproduced (χ²/ndf vs Sample I ~1.3×10⁵). Net: "root cause established" holds **for the mechanism** (real trigger, not proxy); "profile reproduced / χ²/ndf ≈ 625" is **retired** as over-optimistic. Residual is data-side (pile-up/accidentals, Sample-I purity) → STUDY_GAPS NEW-04. | reviewer M1 | STUDY_GAPS NEW-01 → NEW-04 | High (G4 + production) — done |
| B-M2 | **Systematic-aware CIs**: every headline CI gets a systematic component or an explicit "statistics-only, systematics dominate" flag; stop quoting sub-0.1 ns CIs on %-discrepant quantities; fold the √1.5 bootstrap under-coverage | reviewer M2 | review §4 | Medium |
| ~~B-M3~~ | ✅ **DONE 2026-07-05** (`reports/bm3_p04p07_fdr_20260705_203249/REPORT.md`; `scripts/stats02_p04p07_delta_ci.py` + refreshed census `reports/stats01_program_fdr_20260705_203905/`). Reproduced P04 (canonical) + P07 held-out per-pulse residuals from raw ROOT and computed **paired, event-clustered** (dependence unit = event `(run,eventno)`) delta-CIs; P04c/d/e registered from their own per-method CIs (conservative unpaired × measured design effect; P04e run-block). **Every P04/P07 win now has a machine-readable delta-CI and SURVIVES BH** at q=0.05 in the amplitude-charge family (z = 23–166; event-cluster design effect only ~1.05 — dependence barely moves these amplitude/charge closures, unlike timing pair-residuals). Census now: 14/15 bold wins survive, 0 fail, 1 prose-only (P05b, a pile-up study — not P04/P07). **S11a reconciled:** retired for circularity/rigging (review P8), not for failing BH; BH survival is necessary-not-sufficient (S03k). Certification = statistically distinguishable from zero, NOT absolute-energy truth (P04 = duplicate-readout closure; P07 natural-transfer unaudited). | reviewer M3 | STATS01 follow-up | Medium |
| B-M4 | **One validated timing σ₆₈** — **DONE (partial, honest) 2026-07-05** (LUNARC 3348546, `reports/s25_covariance_timing_1783241582/`): measured 3×3 inter-stave covariance on timewalk-corrected LORO residuals (B4/B6/B8, A>1000, 3,820 downstream triples), PSD-projected; combined σ₆₈ = **0.490 ns [0.470, 0.508]** (correlation-aware whole-event bootstrap), **replacing the withdrawn 0.54-0.56**; per-stave B4 1.52 / B6 0.68 / B8 0.80 ns. Independence-assumption test (off-diagonal equality) **not rejected**, bootstrap p=0.62; Cauchy-Schwarz bound [0, 0.81] ns. No sub-0.3 ns claim (combined 0.49, min per-stave 0.68). **Held-out confirmation — RESOLVED as definitively-blocked 2026-07-05** (Track A, `reports/trackA_heldout_confirmation/`): the reserved raw runs were located (`ccb_data/hrd/root/`, never staged) and inspected. They are **DAQ-incompatible** with the Sample-II analysis format — **16-sample** window (vs 18), signal on the **odd** channels rather than the analysis even-channel B-stave map (frozen selection reads near-empty downstream channels, median 13–17 ADC), and **truncated** pulses peaking at the last sample (ch7 ~99–100%). Holds for run 64 too. A frozen one-shot confirmation is therefore *physically invalid*, not merely deferred; exploration σ₆₈ = 0.490 ns reproduced **bit-exactly** (LUNARC job 3349014). `s25_covariance_timing.py` now guards on the waveform format (`daq_format_ok`, status `BLOCKED_DAQ_INCOMPATIBLE`). Net: **0.490 ns is a definitive single-partition (uncorroborated) number; a validated one needs a new Sample-II-configuration beam run.** Matched-MV4 not run (MC digitizer gain unanchored, B-M5). | reviewer M4 | STUDY_GAPS covariance + confirmation partition | High |
| B-M5 | **Quenched trigger-consistent gain re-scan** — **DONE 2026-07-05** (LUNARC 3348264, 1M events, `reports/mv3_gain_quenched_1783240619/`): with Birks ON the trigger-consistent optimum is **~65 ADC/MeV (band ~60-70)**, chi2/ndf 322 (vs unquenched 60→625; placeholder 297→7,751). B2 amplitude median at gain 65 = 2,917 ADC vs data 2,576 (+13%). The "0 rows at gain 60" was a full-digitizer/rescaled-native artifact; in the v4 threshold model gain 60 is viable. Residual band systematics-dominated (trigger proxy = B-M1). | reviewer M5 | STUDY_GAPS NEW-02 | Medium |
| ~~B-M6~~ | ✅ **DONE 2026-07-05** (`reports/bm6_runset_confound_20260705_202638/REPORT.md`; `scripts/bm6_runset_confound.py`, local nnbar_env). Quantified the run-set/beam-drift confound on the S23 B2 hardening (reproduces S23 exactly: pulse-pooled f_I/f_II = 3.452). Treating the **run as the dependence unit**: run-clustered ratio CI **[2.52, 4.64]** excludes 1; the cross-sample gap is **3.5× the within-sample run-to-run SD** (per-run Welch t≈6.5, Cohen d≈2.3 on B2 f(A>5000)); a smooth within-sample linear-drift model reproduces only **~3%** of the log-gap. **Confound bound: run-set/beam drift accounts for at most ~29% (conservative 1-SD coherent excursion; central ~3%) of the hardening.** Reframed docs from "confirmed/consistent in data (differences not separated)" → **"directionally confirmed in data, run-set/beam drift bounded ≤~29% (B-M6)"** (WIKI §8.5, FINDINGS). No external beam-current/HV metadata exists → drift proxy is the observable's own within-sample dispersion; a same-run control remains the only full break. | reviewer M6 | new | Medium |
| B-M7 | **Representative two-pulse benchmark** — **DONE 2026-07-05** (LUNARC 3348547, `reports/s26_overlay_realism_1783241582/`): re-ran the matched-coverage benchmark in three configs — pinned single-stave, +trigger-phase jitter (t1~U(45,55) ns, peak 40-60), +cross-stave overlays (donor kernel ≠ host). **Verdict STABLE: traditional wins matched 80% coverage in ALL three** (trad failure ≈0.000 vs ML 0.0005-0.0010); common-subset dt σ₆₈ trad 0.33-0.41 ns vs ML 1.07-1.47 ns. Phase jitter worsens ML dt (1.08→1.41 ns); cross-stave worsens trad slightly (0.34→0.41 ns) but trad still wins. The pinned single-stave result is NOT an artifact of the pinned phase. Kernel-family circularity partially broken by cross-stave (donor kernel differs). | reviewer M7 | MC03 follow-up | Medium |
| B-M8 | **Budget the 4.4% early-peak class** — **DONE 2026-07-05** (LUNARC 3348548, `reports/s27_earlypeak_budget_1783241582/`): early-peak := peak_sample≤3 (P02); 3.41% of the 640,737 canonical s00 A>1000 pulses (B4/B6/B8 4.7-6.0%). A>1000+valid-CFD does NOT remove them. Per-observable leakage bounds: **(i) timing** downstream pair σ₆₈ +0.058 ns [0.047, 0.068] when included; **(ii) τ_eff** live10 shifts −13.2 ns (all 131.6 → excluded 144.9 ns) — the largest leakage; **(iii) pile-up/current** 3.41% of counts but only −1.2% of integrated area (early-peak pulses have negative mean area, peak sits inside the baseline window) → negligible current/charge contribution. | reviewer M8 | STUDY_GAPS NEW-03 | Medium |
| ~~B-M9~~ | ✅ **DONE 2026-07-05** (`reports/bm9_layerid_stave_mapping_20260705_204303/REPORT.md`; LUNARC GEANT4 geometry + SD source investigation). **PARTIAL SIGN-OFF.** From the deployed geometry (`krakow_109_8-38deg_4-71deg.root`: B-stack = `Sci_stack1_1`, copyNo 1, **8 contiguous 2 cm PSci bars copyNo 0…7**) and `SamplingD.cc` (`LayerID = copyNo`, `LayerID1` = stack id 1=B/2=A): **SIGNED OFF** that `LayerID = bar depth index, 0 = upstream entrance → B2, monotonic to B8` (no interleaving) — so the depth **ordering, B2 fraction, B2-vs-rest and total occupancy are geometry-certain and mapping-invariant** (≲0.3% across variants; MC B2≈0.87 matches data ordering). **CARRIED MAPPING-CONDITIONAL:** the individual deep-stave **B4/B6/B8 MC fractions** (S21/S23/MV3), which move a few % between `paired` (adopted default: {0,1}→B2…{6,7}→B8) and `odd/even_read` — an energy-grouping/hardware question the sim cannot resolve (8 undifferentiated fully-active bars, no read/unread attribute). Data per-stave fractions unaffected. The prior "MV3 v4 closed the mapping" claim corrected to a marginal best-χ² preference (still χ²/ndf~554), not a geometry proof. | reviewer M9 | new | Low–Medium |

## Minor (presentation / consistency)

| ID | Item | Origin |
|----|------|--------|
| B-m1 | Quote R_max as one bound + estimator band; note MC excess tightens, not validates | reviewer m1 |
| B-m2 | Align "MC-closed" PID label with the weak-label-proxy caveat | reviewer m2 |
| B-m3 | Flag MV2 energy/containment as untriggered-MC (not trigger-representative) | reviewer m3 |
| B-m4 | Keep MV7 pedestal closure out of any "validated on data" column (MC-on-MC lower bound) | reviewer m4 |
| B-m5 | Actually use the reserved confirmation partition (runs 64, 12–30) for sub-0.3 ns claims | reviewer m5 |
| B-m6 | Note S22 reuses S02/S03 runs — measured, not independently confirmed | reviewer m6 |
| B-m7 | Add per-point uncertainties to PCA/AE/R_max/verdict numbers | reviewer m7 |
| B-m8 | Replace load-bearing emoji glyphs with a quantitative "status of each headline" table naming the single defensible primary result | reviewer m8 |
| B-m9 | Normalize strength language (confirmed/closed/ruled out/established) across WIKI/FINDINGS/PROJECT_REPORT | reviewer m9 |

## Citation gaps (from nature-citation pass, 2026-07-05; closed 2026-07-05)
- **CCB Kraków 190 MeV proton beam facility — CLOSED.** Added `Maj2024CCB` (Nuclear
  Physics News 34(2) 4–7, 2024, doi:10.1080/10619127.2024.2336422) as the canonical
  CCB facility paper (IBA Proteus C-235, 70–230 MeV research beam), plus `Swakon2010CCB`
  (Radiation Measurements 45(10) 1469–1471, 2010, doi:10.1016/j.radmeas.2010.06.020,
  IFJ PAN proton-therapy heritage) and `Briz2022ProtonRad` (IEEE TNS, 2022,
  doi:10.1109/TNS.2022.3142618, scintillator detector test beam at CCB).
- **HRD / scintillator-range-telescope method — CLOSED (with caveat).** No HIBEAM-NNBAR-
  specific HRD instrument paper exists in the literature; the established scintillator
  range-telescope *method* is now cited via `GranadoGonzalez2022ASTRA` (Phys. Med. Biol.
  67 035013, 2022, doi:10.1088/1361-6560/ac4b39) and `Briz2022ProtonRad`. Only an internal
  HIBEAM HRD design note (collaboration doc, not a citable paper) remains as optional.
- **6 quarantined refs — ALL VERIFIED and promoted** (authors+venue+DOI via Crossref):
  TC1→`Fu2018ANNpileup` (doi:10.1016/j.anucene.2018.05.054);
  TC2→`Du2017TimeWalk` (doi:10.1109/TRPMS.2017.2726534);
  TC3→`GranadoGonzalez2022ASTRA` (doi:10.1088/1361-6560/ac4b39);
  TC4→`Stoykov2021BC422` (doi:10.1109/TNS.2021.3089616);
  TC5→`Ortiz2019FPGApileup` (doi:10.1088/1748-0221/14/09/P09002);
  TC6→`Abele2023ESS` (doi:10.1016/j.physrep.2023.06.001). None dropped — all real.

## Assets to protect (do not regress)
C12 exclusion (MV6b); the retraction/leakage-control discipline; reproducibility
provenance (job IDs, md5s, reproduce commands).

## Application plan
- Immediate (docs-only, no new compute): **APPLIED 2026-07-05** (commit "calibrate
  claims across top-level docs") — B-M2 systematic-aware CIs, B-M3 S11a/P04/P07
  reconciliation, B-m1 R_max single bound, B-m2 PID caveat, B-m3 MV2 flag, B-m5
  confirmation-partition note, B-m8 G1–G5 grade + consolidated status table, B-m9
  strength-language normalization. Figures rebuilt so none asserts a retracted
  claim (commit "post-review figures"). Manuscript + Data Availability + verified
  references + this backlog committed.
- **B-M1 DONE 2026-07-05** (real `Trig_bar` SD production + MV3 re-fit, LUNARC jobs
  3348610/3348673; trigger established as mechanism, ideal trigger over-purifies,
  residual is data-side → STUDY_GAPS NEW-04). See `reports/mv3_v5_realtrigger_1783242005/`.
- **NEW-04 (B-M1 residual) DONE 2026-07-05** (`reports/new04_trigger_residual_1783275727/`,
  first-principles budget, no new compute). The 6.4-pt Sample-I non-B2 residual (MC ideal
  0.3% vs data 6.7%) budgets as **~2.0 pts accidental coincidences** (`f_acc≈R_B·Δt`,
  4.4–8.4%, UPPER-bounded by the corrected R_max ≤ 3.05 MHz, data-anchored by the S10
  +1.03-pt current excess) **+ ~1.5 pts paddle/selection fidelity** (deep-proton A-firing
  above the 0.06% truth; loose, 0.5–3.7 pts) **+ ~2.9 pts still-unexplained**. Accidentals
  are real but modest (cannot close alone); no forced closure. Uses the corrected R_max
  ≤3.05 MHz@124.8ns (the 4.22 MHz@90ns is retracted). Next: digitize `Trig_bar` SD hits to
  pin the paddle term; B-M6 for run-set/beam separation.
- Next compute round (still OPEN — require new jobs on LUNARC):
  B-M5 (quenched gain re-scan), B-M4 (measured inter-stave covariance +
  matched MV4 + confirmation-partition sign-off), B-M6 (separate data enrichment
  from run-set/beam differences), B-M7 (overlay realism: phase jitter + cross-stave),
  B-M8 (early-peak leakage budget), B-M9 (close layer→stave mapping). These are the
  STUDY_GAPS NEW-01/02/03 + covariance items; each is scoped and ready to run.
