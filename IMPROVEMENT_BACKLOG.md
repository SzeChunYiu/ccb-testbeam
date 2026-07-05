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
| B-M1 | **Score `Trig_bar` volumes** in GEANT4 → real per-event Sample-I/II flag; re-fit MV3; soften "root cause established" → "strongly indicated" until then | reviewer M1 | STUDY_GAPS NEW-01 | High (G4 + production) |
| B-M2 | **Systematic-aware CIs**: every headline CI gets a systematic component or an explicit "statistics-only, systematics dominate" flag; stop quoting sub-0.1 ns CIs on %-discrepant quantities; fold the √1.5 bootstrap under-coverage | reviewer M2 | review §4 | Medium |
| B-M3 | **Certify P04/P07 ML wins**: emit machine-readable delta-CIs, run through STATS01 FDR, reconcile retired S11a; stop citing as certified until assessed | reviewer M3 | STATS01 follow-up | Medium |
| B-M4 | **One validated timing σ₆₈**: covariance-correct combination with *measured* inter-stave correlation + matched-MV4 validation + confirmation-partition sign-off for any sub-0.3 ns claim | reviewer M4 | STUDY_GAPS covariance + confirmation partition | High |
| B-M5 | **Quenched trigger-consistent gain re-scan** (gain ~60 was fit unquenched; quenched table has 0 rows at A>1000/gain 60) | reviewer M5 | STUDY_GAPS NEW-02 | Medium |
| B-M6 | **Disentangle data enrichment from run-set/beam differences** (disjoint Sample I/II runs); reframe "confirmed in data" → directional/consistent; quantify beam-condition contribution to DR | reviewer M6 | new | Medium |
| B-M7 | **Representative two-pulse benchmark**: add trigger-phase jitter (phase is the leading anomaly hypothesis), cross-stave overlays, address kernel-family circularity before recommending an operating point | reviewer M7 | MC03 follow-up | Medium |
| B-M8 | **Budget the 4.4% early-peak class**: bound its leakage into timing residuals, τ_eff, and pile-up excess, or show the headline selection removes it | reviewer M8 | STUDY_GAPS NEW-03 | Medium |
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

## Assets to protect (do not regress)
C12 exclusion (MV6b); the retraction/leakage-control discipline; reproducibility
provenance (job IDs, md5s, reproduce commands).

## Application plan
- Immediate (docs-only, no new compute): B-M2 flags, B-M3 reconciliation of S11a,
  B-m1–B-m9 — applied in a consistency pass across WIKI/FINDINGS/PROJECT_REPORT.
- Next compute round: B-M1 (Trig_bar), B-M5 (quenched gain), B-M4 (covariance +
  matched MV4), B-M7 (overlay realism), B-M8 (early-peak budget) — these are the
  NEW-01/02/03 + covariance items already queued in STUDY_GAPS §recommended.
