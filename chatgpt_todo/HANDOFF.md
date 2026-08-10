# Latest Handoff

## Active atom

- **Task:** `ARU-DATAMC-ECDF-001` / issue #1051
- **Branch / PR:** `fix/data-mc-right-continuous-ecdf` / #1162
- **Base main:** `4c8cebefe077f081f182eafd34d6b20e8d4ac067`
- **State:** implementation + adversarial tests complete on branch; exact-head MC Validation CI still required after the final handoff commits.

## Local scientific/software result

The observed DATA<->MC EDF discrepancy now implements the declared weighted empirical distribution

`F_w(x) = sum_i w_i I(X_i <= x) / sum_i w_i`

as a right-continuous step function. Equal-valued rows are collapsed into one support point carrying their total weight, arbitrary evaluation uses `searchsorted(..., side="right")`, and `D` is evaluated exactly on the union of DATA and MC support points. No `np.interp` path remains in the ECDF/KS-D implementation.

The regression suite covers the original two-point midpoint falsifier, exact tie aggregation, an all-tied 7000-ADC saturation spike, direct indicator-sum equality, weighted-row splitting/merging invariance, tie permutation invariance, equal-weight agreement with `scipy.stats.ks_2samp(...).statistic`, quantized/saturated support, and invalid empirical-measure inputs.

## Four role-separated votes

- **Statistical-method lead — ACCEPT local observed-statistic repair / pending exact-head CI.** The implemented measure has the required right-continuous step semantics and dimensional/unit contract is unchanged: input observable values retain their source units, weights are nonnegative dimensionless measure masses, and output `D` is dimensionless.
- **Adversarial mechanism reviewer — ACCEPT local D contract / BLOCK p-value inference.** H3 piecewise-linear interpolation is eliminated; row representation and tie order no longer define independent hypotheses. The existing unit-weight permutation null remains scientifically invalid for weighted MC.
- **Independent statistics/validation reviewer — ACCEPT deterministic/oracle tests / pending CI.** Direct indicator sums and SciPy's ordinary equal-weight KS statistic are independent checks of `D`; they do not validate a weighted null or p-value.
- **Claims/provenance reviewer — REVISE downstream products / no claim promotion.** Output schema is advanced to v5 and tags the legacy numerical p-value `NONAUTHORISING_BLOCKED_ISSUE_1049`; plots label it blocked. Existing real-data comparison artifacts must be regenerated before any new D is quoted.

## Surviving dependencies / child atoms

- #1049 remains the P0 owner for the weighted null hypothesis, resampling/calibration law, nuisance-scale treatment and type-I validation.
- #880/#1022 remain the source-of-truth atoms for generator/analysis weight semantics.
- #1027 remains the detector/DAQ atom for the physical meaning of ADC saturation/ties; this branch only proves the statistical estimator handles exact ties correctly.
- No beam ROOT bytes or campaign MC artifacts are available in this runtime, so real DATA<->MC D values are not regenerated and no detector-performance result changes.

## Merge gate / next action

Inspect exact-head MC Validation for the final #1162 head. If it passes on current base, merge #1162 and close only #1051. Do **not** close #1049 or treat the retained legacy p-value as a goodness-of-fit probability. After merge, the next highest-value code-ready atom is #1049 if weight semantics are sufficiently resolved; otherwise return to the highest-ready dependency among #880/#1022 rather than inventing a calibration law.
