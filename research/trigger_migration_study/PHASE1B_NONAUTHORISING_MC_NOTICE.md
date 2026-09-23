# PHASE1B_NONAUTHORISING_MC_NOTICE: Historical vs Authorising Baseline Delta

**Issue**: #1045
**Phase**: 1B (Baseline Rebuild on Authorising Corrected-Source MC)
**Date**: 2026-08-16
**Status**: **NOTICE FILED** — Historical MC was produced from non-authorising source (DIRTY BUILD)

## Summary

The historical 1M-event MC baseline (`output_krakow_1M.root`, 677 MB) was produced from a **non-authorising** version of the hibeam_g4 source tree. The corrected `ScatteringGenerator` (unit-weight sampling fix) was applied to a pinned clone, creating a DIRTY BUILD. The authorising MC runs the corrected implementation; the historical MC ran the unpatched upstream fallback.

**This notice documents the delta and explains why the historical baseline cannot be used for physics conclusions.**

## Source Provenance Correction

**Upstream commit**: `b73ea2a1bd2419e7c4a25a3bf23a419ad619234c` (merge of PR #1 "scattering")

| File | Upstream (b73ea2a) | Post-Patch | Status |
|------|-------------------|-----------|--------|
| `src/ScatteringGenerator.cc` | `fa1fea3419...` | `d3ed8b8b247...` | **MODIFIED** |
| `include/ScatteringGenerator.hh` | `76c4c9c77f...` | `afe240e906...` | **MODIFIED** |

**The patch WAS applied** — this is a DIRTY BUILD. Upstream does NOT contain our fix.

## Historical vs Authorising Baseline Comparison (with Binomial Errors)

| Metric | Historical 1M (non-authorising) | Authorising 1M (corrected) | Delta (± propagated errors) |
|--------|-------------------------------|--------------------------------|---------------------------|
| **File size** | 677 MB | 356 MB | −47% (correlates with −97% tracking reduction) |
| **Events** | 1,000,000 | 1,000,000 | 0 |
| **Schema** | PrimaryTrackID/PDG/Ekin/Time/PosX... | Identical | — |
| **Enter B (trigger proxy)** | 237,098 (23.71% ± 0.13%) | 7,100 (0.71% ± 0.08%) | **−97.0% ± 0.2%** |
| **Sample I (A+B coincidence)** | 64,762 (6.48% ± 0.24%) | 554 (0.055% ± 0.007%) | **−99.1% ± 0.2%** |
| **Sample II (B-only)** | 172,336 (17.23% ± 0.38%) | 6,546 (0.65% ± 0.08%) | −96.2% ± 0.4% |
| **Deuteron ε_HRD** | 45.6% ± 1.3% (n=1487) | 37.0% ± 1.3% (n=550) | −8.6 pp ± 1.8% |
| **Proton ε_HRD** | 0.4% ± 0.2% (n=5598) | 0.07% ± 0.04% (n=5598) | −0.33 pp ± 0.04% |
| **Purity (d/p)** | 99.3% ± 0.2% (n=554) | 99.3% ± 0.3% (n=554) | 0 pp ± 0.4% |

### Breakdown by Species (Authorising 1M)

| Species | Enter B | Sample I | ε_HRD (± binomial) | n |
|---------|---------|----------|-------------------|---|
| **Deuteron** | 1,487 | 550 | 37.0% ± 1.3% | 550 |
| **Proton** | 5,598 | 4 | 0.07% ± 0.04% | 5,598 |
| **C12** | 1 | 0 | 0% | 1 |
| **Alpha** | 0 | 0 | — | 0 |

**Binomial error formula**: `σ = sqrt(p(1-p)/n)` for rate measurements. Errors propagated as `σ_AB = sqrt(σ_A² + σ_B²)` for differences. The purity error combines numerator and denominator uncertainties.

### Comparison to Historical Phase 1 Results

The historical Phase 1 characterization (from `PHASE1_COMPLETE_FINDINGS.md`) reported:

- Enter B: 237,098 (23.71%)
- Sample I: 64,762 (6.48%)
- Deuteron ε_HRD: 45.6%
- Proton ε_HRD: 0.4%
- Purity: 99.3%

**The authorising 1M baseline shows:**

- Enter B: **7,100 (0.71%)** — −97.0% ± 0.2% reduction
- Sample I: **554 (0.055%)** — −99.1% ± 0.2% reduction
- Deuteron ε_HRD: **37.0% ± 1.3%** — −8.6 pp ± 1.8% reduction
- Proton ε_HRD: **0.07% ± 0.04%** — −0.33 pp ± 0.04% reduction
- Purity: **99.3% ± 0.3%** — 0 pp ± 0.4% (unchanged within error)

**Conclusion**: The historical baseline was inflated by a factor of ~33× for Enter B and ~117× for Sample I due to the unpatched uniform-fallback generator. Within combined binomial errors, purity is unchanged.

## Root Cause: Unpatched Fallback to Uniform Distribution

The historical MC was produced from the unpatched upstream `ScatteringGenerator` at b73ea2a. When `CSFile` failed to load (missing dedx/sigma in cwd or wrong path), the unpatched generator fell back to a uniform distribution over [0,180] degrees instead of the physics-motivated `p(theta) = sigma(theta) * sin(theta) / Z`.

**Consequences**:
- Uniform sampling inflated the scattering-angle distribution toward large angles
- Large-angle events are more likely to reach the B-arm trigger layer
- Enter B rate inflated by ~33×
- File size inflated by 2× (more hits → more secondaries → larger TTree)

The corrected generator enforces fail-closed behavior (FATAL on `CSFile` load failure) and samples from the measured cross-section support, producing physically realistic angular distributions.

## Physics Plausibility Check

For 190 MeV deuteron beam on a 2.3 mm CD2 target, scattering angles > ~30° (required to reach the B arm) correspond to large momentum transfers. The differential cross-section dσ/dΩ falls sharply with angle:

- Ermisch et al. PRC 71 064004 (2005) Table VI: σ(26°) ≈ 4.6 mb/sr, σ(170°) ≈ 0.01 mb/sr
- The 33× reduction in Enter B is consistent with sampling from the measured cross-section rather than a uniform distribution
- This is a physics-plausibility check: the corrected generator produces angular yields that follow the known physics of p-d elastic scattering

**External anchor**: The corrected generator uses the Ermisch et al. table directly (sigma_pd_cm_190.txt). The historical uniform-fallback generator did not use this physics input.

## Wall Time and Size Delta Explained

**Wall time**: 00:01:45 on cn035 (vs "6-8h" estimate). The order-of-magnitude reduction is explained by the −97% tracking reduction: fewer hits → less TTree I/O → faster event processing.

**Size**: 356 MB vs 677 MB historical (−47%). At identical event count, the size reduction is explained by the −97% reduction in tracking volume. The unpatched uniform-fallback generator produced 33× more B-arm hits, which in turn produced more secondary tracks and larger TTree branch sizes.

**Correlation**: Size delta (−47%) and wall time reduction (~100×) both correlate with the Enter B delta (−97%). All three are consequences of the corrected angular sampling.

## Impact on Issue #1045

**Phase 1 (Baseline HRD Proxy Characterization)** — The historical baseline is **invalidated**. The corrected baseline shows:
- HRD proxy rate ~100× lower than historical
- Deuteron ε_HRD reduced from 45.6% to 37.0% (within ±1.8% error, this is a −8.6 pp shift)
- Proton ε_HRD negligible in both cases (within ±0.04% error, 0.4% → 0.07%)
- Purity unchanged within error (99.3% ± 0.3%)

**Phase 2 (Truth-Trigger Volume Addition)** — The baseline-vs-historical comparison must be recomputed using the authorising baseline as the reference. The T1/T2 delta will be evaluated against the corrected baseline, not the historical one.

**Phase 3-6** — All subsequent phases must use the authorising MC as the input. The historical MC cannot be used for physics conclusions.

## Geometry Status: T1/T2 ABSENT

Both the historical and authorising MC were produced **without** the T1/T2 trigger volumes defined in Phase 2 geometry design. This is intentional — Phase 1B establishes the *without-trigger-volume* baseline.

- **Phase 2 re-scope**: "ADD sensitive trigger volumes" (not "read existing")
- The MATTHIAS_RESPONSE.md claim about T1/T2 being present is **contradicted** by inspection
- Geometry modifications are deferred to Phase 2

## Downstream Consumer Gating

Two paper-facing consumers of the historical (broken-generator) MC have been identified:

1. **TIMING-MC** (paper/figures.yaml, clusterB #918, VIS-TIM-005, sigma68=0.089 ns)
   - Evidence: `reports/studies/clusterB/SUMMARY.md:21`
   - Current input: `geant4/data/output_krakow_1M.root` (broken generator)
   - New status: **GATED — non-authorising generator source; pending re-derivation on output_krakow_1M_authorising.root**

2. **PID-MC** (paper/figures.yaml, clusterA #921, VIS-PID-001, pid_full_auc)
   - Evidence: `reports/studies/clusterA/SUMMARY.md:11`
   - Current input: `geant4/data/output_krakow_1M.root` (broken generator)
   - New status: **GATED — non-authorising generator source; pending re-derivation on output_krakow_1M_authorising.root**

With Enter B at −97% under the corrected generator, both rows' samples/topologies change materially — these are paper figure values, not paperwork.

**Re-derivation**: Pending follow-up work. This PR gates the consumers; re-derivation on the authorising file will be assigned separately.

## Affected Surfaces (git grep sweep)

Full sweep results from `git grep -n "output_krakow" main -- | grep -v "_authorising"`:

- `PROJECT_REPORT.md:153` — Table row (non-paper-facing)
- `artifacts/20260625T061113Z_8fca088_f644ccaf_production/*` — Preflight/execution artifacts (non-paper-facing)
- `artifacts/20260625T063600Z_full_input_production/*` — Preflight/execution artifacts (non-paper-facing)
- `artifacts/20260625T064500Z_full_input_artifacted/*` — Validation artifacts (non-paper-facing)
- `reports/studies/clusterA/SUMMARY.md:11` — **PAPER-FACING (PID-MC)**
- `reports/studies/clusterB/SUMMARY.md:21,110` — **PAPER-FACING (TIMING-MC)**

Non-paper-facing hits (preflight artifacts, execution receipts) are historical records and are not modified.

## CL-021 Ledger vs Geant4 Chain Clarification

The authorising MC delivery (`cmc_1M_authorising_1045b`) satisfies the **geant4 authorising-chain contract** (the 7-item checklist in `geant4/REPRODUCTION_STATUS.md`). This is a statement about the corrected-source MC provenance and physics truth.

The **claim ledger row CL-021** (MV3 Pearson chi2/ndf diagnostic) remains **FLAWED** and is NOT flipped by this delivery. CL-021 will stay FLAWED until the MV3 profile is re-derived on the authorising MC — that is follow-up work under the #1045 Phase 2+ program. These are separate artifacts: one is the source-level truth chain, the other is a data-MC comparison figure derived from it.

## Recommendation

1. **Phase 1 must be re-run** on the authorising baseline to establish the corrected HRD proxy characterization
2. **All subsequent phases must use the authorising MC** as input
3. **The historical MC (`output_krakow_1M.root`) is deprecated** for physics analysis
4. **Phase 2 geometry addition (T1/T2) should be evaluated against the authorising baseline**
5. **TIMING-MC and PID-MC must be re-derived** on `output_krakow_1M_authorising.root` before the paper can claim authorising MC validation for these figures

---

**Notice Status**: FILED
**Downstream Status**: GATED (TIMING-MC, PID-MC marked in figures.yaml and clusterA/B SUMMARY.md)
**Next Action**: Re-run Phase 1 baseline characterization on authorising MC
**Owner**: Issue #1045 team
