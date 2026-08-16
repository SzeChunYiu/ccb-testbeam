# Identifiable baseline model audit (issue #963)

Status: **FIXED at estimator/contract level** for the positivity-forced
validation anti-pattern; historical S00 `v1` selector remains frozen.

## Change

`ccb_mc_validation.baseline_identifiable` provides:

- quiet-pretrigger robust median with explicit `BASELINE_UNIDENTIFIABLE`;
- joint baseline + signed template nuisance fit;
- rejection of "0% below tolerance by construction" as validation evidence;
- synthetic bias/coverage table by pathology.

The adaptive positivity-lowering path in study scripts remains available
as a *diagnostic covariate*, but cannot cite zero post-correction
violations as independent validation.
