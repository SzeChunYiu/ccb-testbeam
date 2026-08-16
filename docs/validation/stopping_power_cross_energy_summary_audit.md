# Stopping-power cross-energy summary audit

## Scope

This audit checks whether the diagnostic stopping-power reporter combines ratios from distinct configured energies into one arithmetic mean even though the report explicitly records `uncertainty_method=NOT_EVALUATED` and has no covariance or weighting model.

## Confirmed defect

The current canonical reporter prints `mean point-estimate ratio [species]` using `statistics.mean(ratios)` across distinct energy points. That number is not a defined combined measurement: each energy is a different comparison point, point uncertainties are absent, correlations are unknown, and equal weighting is not justified. The arithmetic mean can conceal energy-dependent bias and can change when the configured energy grid changes.

NIST Technical Note 1297 (DOI `10.6028/NIST.tn.1297`) requires uncertainty components and covariances, where appropriate, to be identified and combined using an established documented method. The present diagnostic has neither, so no cross-energy combined ratio should be reported.

## Reproducible audit

```bash
python tools/audit/audit_stopping_power_cross_energy_summary.py \
  scripts/single_stave/compare_stopping_power.py \
  --output docs/validation/stopping_power_cross_energy_summary_validation.json
```

Expected current result: exit status `1`, `status=FLAWED`, finding `UNWEIGHTED_CROSS_ENERGY_MEAN`.

Focused regression:

```bash
python -m py_compile \
  tools/audit/audit_stopping_power_cross_energy_summary.py \
  tests/test_audit_stopping_power_cross_energy_summary.py
python -m pytest tests/test_audit_stopping_power_cross_energy_summary.py -q
```

## Better method

Until a preregistered uncertainty and covariance model exists, report each energy point separately and optionally show descriptive minimum/maximum bounds. Do not compute a combined mean, weighted mean, fit normalization, or global closure score. A future combination must define the measurand, point uncertainties, correlations, weighting or likelihood, sensitivity to the energy grid, and coverage validation before inspecting the final result.

## Scientific boundary

This is source-level and synthetic regression evidence. It does not evaluate a real Geant4 export, quantify stopping-power uncertainty, or establish Geant4/PSTAR agreement.
