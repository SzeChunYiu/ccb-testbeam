# PHASE1B_NONAUTHORISING_MC_NOTICE: Historical vs Authorising Baseline Delta

**Issue**: #1045
**Phase**: 1B (Baseline Rebuild on Authorising Corrected-Source MC)
**Date**: 2026-08-16
**Status**: **NOTICE FILED** — Historical MC was produced from non-authorising source

## Summary

The historical 1M-event MC baseline (`output_krakow_1M.root`, 677 MB) was produced from a **non-authorising** version of the hibeam_g4 source tree. The corrected `ScatteringGenerator` (unit-weight sampling fix, merged in hibeam_g4 PR #1) produces a dramatically different HRD proxy baseline.

**This notice documents the delta and explains why the historical baseline cannot be used for physics conclusions.**

## Historical vs Authorising Baseline Comparison

| Metric | Historical 1M (non-authorising) | Authorising 1M (corrected source) | Delta | Interpretation |
|--------|-------------------------------|----------------------------------|-------|----------------|
| **File size** | 677 MB | 356 MB | -47% | Fewer stored secondaries in corrected output |
| **Events** | 1,000,000 | 1,000,000 | 0 | Event count exact |
| **Schema** | PrimaryTrackID/PDG/Ekin/Time/PosX... | Identical | — | Schema matches |
| **Enter B (trigger proxy)** | 237,098 (23.71%) | 7,100 (0.71%) | **-97%** | Corrected sampling dramatically reduces HRD proxy rate |
| **Sample I (A+B coincidence)** | 64,762 (6.48%) | 554 (0.06%) | **-99%** | Coincidence rate nearly eliminated |
| **Sample II (B-only)** | 172,336 (17.23%) | 6,546 (0.65%) | -96% | Consistent with Enter B reduction |
| **Deuteron ε_HRD** | 45.6% | 37.0% | -8.6 pp | Deuteron trigger efficiency reduced but still positive |
| **Proton ε_HRD** | 0.4% | 0.1% | -0.3 pp | Proton trigger efficiency negligible in both |
| **Purity (deuteron/proton)** | 99.3% | 99.3% | 0 pp | Purity unchanged — surviving events well-separated |

### Breakdown by Species (Authorising 1M)

| Species | Enter B | Sample I | ε_HRD | Interpretation |
|---------|---------|----------|-------|----------------|
| **Deuteron** | 1,487 | 550 | 37.0% | Primary signal, reduced but still positive |
| **Proton** | 5,598 | 4 | 0.1% | Background, negligible efficiency |
| **C12** | 1 | 0 | 0% | Heavy ion, no HRD signal |
| **Alpha** | 0 | 0 | — | Not observed in sample |

### Comparison to Historical Phase 1 Results

The historical Phase 1 characterization (from `PHASE1_COMPLETE_FINDINGS.md`) reported:

- Enter B: 237,098 (23.71%)
- Sample I: 64,762 (6.48%)
- Deuteron ε_HRD: 45.6%
- Proton ε_HRD: 0.4%
- Purity: 99.3%

**The authorising 1M baseline shows:**

- Enter B: **7,100 (0.71%)** — -97% reduction
- Sample I: **554 (0.06%)** — -99% reduction
- Deuteron ε_HRD: **37.0%** — -8.6 pp reduction
- Proton ε_HRD: **0.1%** — -0.3 pp reduction
- Purity: **99.3%** — unchanged

**Conclusion**: The historical baseline was inflated by a factor of ~33× for Enter B and ~117× for Sample I due to the unit-weight sampling bug in the uncorrected `ScatteringGenerator`.

## Root Cause: Non-Authorising Source

The historical MC was produced from a version of hibeam_g4 **before** the corrected `ScatteringGenerator` was merged. The authorising MC is built from commit `b73ea2a` (merge of PR #1), which contains the fix.

**Evidence**:
- `sha256(src/ScatteringGenerator.cc)` at pinned commit = `d3ed8b8b...` (matches patch payload)
- The patch application was verification-only — upstream already contains the corrected implementation
- The non-authorising historical source lacked the unit-weight sampling correction

## Impact on Issue #1045

**Phase 1 (Baseline HRD Proxy Characterization)** — The historical baseline is **invalidated**. The corrected baseline shows:
- HRD proxy rate ~100× lower than historical
- Deuteron ε_HRD reduced from 45.6% to 37.0%
- Proton ε_HRD negligible in both cases

**Phase 2 (Truth-Trigger Volume Addition)** — The baseline-vs-historical comparison must be recomputed using the authorising baseline as the reference. The T1/T2 delta will be evaluated against the corrected baseline, not the historical one.

**Phase 3-6** — All subsequent phases must use the authorising MC as the input. The historical MC cannot be used for physics conclusions.

## Geometry Status: T1/T2 ABSENT

Both the historical and authorising MC were produced **without** the T1/T2 trigger volumes defined in Phase 2 geometry design. This is intentional — Phase 1B establishes the *without-trigger-volume* baseline.

- **Phase 2 re-scope**: "ADD sensitive trigger volumes" (not "read existing")
- The MATTHIAS_RESPONSE.md claim about T1/T2 being present is **contradicted** by inspection
- Geometry modifications are deferred to Phase 2

## Size Delta Explanation

The authorising output (356 MB) is 47% smaller than the historical output (677 MB) despite having the same event count. This is consistent with the corrected `ScatteringGenerator` producing fewer stored secondaries. The branch-by-entry content comparison is pending but not a blocker for authorising status.

## Recommendation

1. **Phase 1 must be re-run** on the authorising baseline to establish the corrected HRD proxy characterization
2. **All subsequent phases must use the authorising MC** as input
3. **The historical MC (`output_krakow_1M.root`) is deprecated** for physics analysis
4. **Phase 2 geometry addition (T1/T2) should be evaluated against the authorising baseline**

---

**Notice Status**: FILED
**Next Action**: Re-run Phase 1 baseline characterization on authorising MC
**Owner**: Issue #1045 team
