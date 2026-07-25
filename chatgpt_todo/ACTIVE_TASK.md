# Active Task

- **Task ID:** AUD-MV3-SEL-001
- **Owner:** scheduled scientific-review session
- **Session stamp:** 2026-07-25T220218Z
- **Initial remote main SHA:** `701116061eb3346a3ae2b31e2946ca450d6120e2`
- **Scope:** independently audit the merged MV3 selection-matched stopping-depth claim for
  MC weight semantics, signed-charge handling, comparison estimand, provenance, uncertainty,
  plots, and consistency with canonical `CL-021`.
- **Confirmed defects:** `PrimaryWeight` is read but not applied and invalid weight fails open
  to 1; the charged mask excludes negative particles; the advertised improvement changes the
  data target; the summary has no content-addressed provenance, weight sufficient statistics,
  uncertainty, or preregistered sensitivity; “shape matches” outruns chi2/ndf 5590.09 and
  total-variation distance 0.07735.
- **Independent calculation:** the reported improvement is 16.602672795596263x, whereas a
  same-Sample-I-data ablation gives 16.114635239581606x. The Sample-I B2 residual is
  7.735323559398211 percentage points.
- **Validated progress:** added a fail-closed auditor, seven regressions, machine-readable
  evidence, SVG evidence, and a detailed audit report under policy
  `MV3_SELECTION_CLAIM_REQUIRES_WEIGHTED_SIGNED_CHARGE_AND_SAME_TARGET_VALIDATION`.
- **Validation:** `python -m py_compile` passed; focused pytest returned
  `7 passed in 0.07s`; JSON and SVG parsing passed; changed Python lines are at most 99
  characters.
- **Focused status:** `VALIDATED` audit gate; merged production follow-up remains `FLAWED`
  pending a content-addressed weighted signed-charge rerun. Canonical `CL-021` remains
  `FLAWED` under `BLK-MV3-LEGACY-001`.
- **Next action:** correct the producer and report together, regenerate weighted and
  unweighted sensitivity outputs from immutable ROOT/data bytes, retain weight ESS and
  covariance, run parameter/aggregation scans, then synchronize every public claim only after
  the exact-repository audit returns zero findings.
- **Scientific boundary:** no ROOT file was reprocessed and no weighted profile, model
  correction, calibration, PID result, or detector-performance result was produced.
