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
| B-M3 | **Certify P04/P07 ML wins**: emit machine-readable delta-CIs, run through STATS01 FDR, reconcile retired S11a; stop citing as certified until assessed | reviewer M3 | STATS01 follow-up | Medium |
| B-M4 | **One validated timing σ₆₈** — **DONE (partial, honest) 2026-07-05** (LUNARC 3348546, `reports/s25_covariance_timing_1783241582/`): measured 3×3 inter-stave covariance on timewalk-corrected LORO residuals (B4/B6/B8, A>1000, 3,820 downstream triples), PSD-projected; combined σ₆₈ = **0.490 ns [0.470, 0.508]** (correlation-aware whole-event bootstrap), **replacing the withdrawn 0.54-0.56**; per-stave B4 1.52 / B6 0.68 / B8 0.80 ns. Independence-assumption test (off-diagonal equality) **not rejected**, bootstrap p=0.62; Cauchy-Schwarz bound [0, 0.81] ns. No sub-0.3 ns claim (combined 0.49, min per-stave 0.68). **Held-out confirmation BLOCKED**: reserved runs {64, 12-30} raw files are not staged on LUNARC (only analysis runs 44-63,65) → the FIRST *validated* timing number is not achievable until they are staged. Matched-MV4 not run (MC digitizer gain unanchored, B-M5). | reviewer M4 | STUDY_GAPS covariance + confirmation partition | High |
| B-M5 | **Quenched trigger-consistent gain re-scan** — **DONE 2026-07-05** (LUNARC 3348264, 1M events, `reports/mv3_gain_quenched_1783240619/`): with Birks ON the trigger-consistent optimum is **~65 ADC/MeV (band ~60-70)**, chi2/ndf 322 (vs unquenched 60→625; placeholder 297→7,751). B2 amplitude median at gain 65 = 2,917 ADC vs data 2,576 (+13%). The "0 rows at gain 60" was a full-digitizer/rescaled-native artifact; in the v4 threshold model gain 60 is viable. Residual band systematics-dominated (trigger proxy = B-M1). | reviewer M5 | STUDY_GAPS NEW-02 | Medium |
| B-M6 | **Disentangle data enrichment from run-set/beam differences** (disjoint Sample I/II runs); reframe "confirmed in data" → directional/consistent; quantify beam-condition contribution to DR | reviewer M6 | new | Medium |
| B-M7 | **Representative two-pulse benchmark** — **DONE 2026-07-05** (LUNARC 3348547, `reports/s26_overlay_realism_1783241582/`): re-ran the matched-coverage benchmark in three configs — pinned single-stave, +trigger-phase jitter (t1~U(45,55) ns, peak 40-60), +cross-stave overlays (donor kernel ≠ host). **Verdict STABLE: traditional wins matched 80% coverage in ALL three** (trad failure ≈0.000 vs ML 0.0005-0.0010); common-subset dt σ₆₈ trad 0.33-0.41 ns vs ML 1.07-1.47 ns. Phase jitter worsens ML dt (1.08→1.41 ns); cross-stave worsens trad slightly (0.34→0.41 ns) but trad still wins. The pinned single-stave result is NOT an artifact of the pinned phase. Kernel-family circularity partially broken by cross-stave (donor kernel differs). | reviewer M7 | MC03 follow-up | Medium |
| B-M8 | **Budget the 4.4% early-peak class** — **DONE 2026-07-05** (LUNARC 3348548, `reports/s27_earlypeak_budget_1783241582/`): early-peak := peak_sample≤3 (P02); 3.41% of the 640,737 canonical s00 A>1000 pulses (B4/B6/B8 4.7-6.0%). A>1000+valid-CFD does NOT remove them. Per-observable leakage bounds: **(i) timing** downstream pair σ₆₈ +0.058 ns [0.047, 0.068] when included; **(ii) τ_eff** live10 shifts −13.2 ns (all 131.6 → excluded 144.9 ns) — the largest leakage; **(iii) pile-up/current** 3.41% of counts but only −1.2% of integrated area (early-peak pulses have negative mean area, peak sits inside the baseline window) → negligible current/charge contribution. | reviewer M8 | STUDY_GAPS NEW-03 | Medium |
| B-M9 | **Close the LayerID→stave mapping** + GEANT4 production sign-off, or carry all per-stave fractions as explicitly mapping-conditional | reviewer M9 | new | Low–Medium |

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

## Citation gaps (from nature-citation pass, 2026-07-05)
- **No verified HRD / scintillator-range-telescope method paper** — the methods
  section currently leans on general HIBEAM-NNBAR papers. Targeted search needed.
- **No citation for the CCB Kraków 190 MeV proton beam facility** — the beam claim
  is uncited. Targeted search needed before the methods section is final.
- 6 candidate refs are quarantined UNVERIFIED in `docs/references.bib` — verify or drop.

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
- Next compute round (still OPEN — require new jobs on LUNARC):
  B-M5 (quenched gain re-scan), B-M4 (measured inter-stave covariance +
  matched MV4 + confirmation-partition sign-off), B-M6 (separate data enrichment
  from run-set/beam differences), B-M7 (overlay realism: phase jitter + cross-stave),
  B-M8 (early-peak leakage budget), B-M9 (close layer→stave mapping). These are the
  STUDY_GAPS NEW-01/02/03 + covariance items; each is scoped and ready to run.
