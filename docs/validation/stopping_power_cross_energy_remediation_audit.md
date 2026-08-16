# Stopping-power cross-energy reporting remediation

## Scope

This validation addresses one reporting-method defect in
`scripts/single_stave/compare_stopping_power.py`: the former arithmetic mean of
point-estimate simulation/PSTAR ratios across distinct configured energies.
It does not validate the Geant4 observable, the PSTAR transcription, or a physics
closure.

## Confirmed pre-change defect

The prior source imported `statistics` and printed
`statistics.mean(ratios)` as a `mean point-estimate ratio` for each particle
species. Every contributing point simultaneously declared
`uncertainty_method=NOT_EVALUATED`; no combined measurand, point uncertainty,
covariance, weighting rule, likelihood, or energy-grid sensitivity model was
defined. The number therefore had no accepted interpretation as a combined
stopping-power result.

Pre-change repository blob:

- path: `scripts/single_stave/compare_stopping_power.py`
- Git blob SHA-1: `4e45e55b48c1d51320b9e6d0959b0b8423d0b2fc`

## Corrected behavior

The reporter now:

1. keeps every exact configured energy point separate;
2. removes the `statistics` dependency and arithmetic mean;
3. prints only the descriptive minimum and maximum point-estimate ratio for each
   species, explicitly labelled `no combined estimate`;
4. prints and records
   `NO_CROSS_ENERGY_COMBINATION_WITHOUT_UNCERTAINTY_MODEL`;
5. writes that policy into every machine-readable CSV row.

Descriptive bounds are not used for acceptance and are not presented as an
estimate of a common parameter.

## Synthetic regression

Two proton points were evaluated with controlled validator stubs:

- 1 MeV: ratio 1.0;
- 2 MeV: ratio 0.8.

The reporter emitted the range `[0.8000, 1.0000]`, the explicit no-combination
policy, and no `mean point-estimate ratio`. Both result dictionaries and both CSV
rows retained the policy.

## Validation commands

```text
PYTHONPATH=. python -m py_compile \
  scripts/single_stave/compare_stopping_power.py \
  tools/audit/audit_stopping_power_cross_energy_summary.py \
  tests/test_audit_stopping_power_cross_energy_summary.py \
  tests/test_compare_stopping_power_cross_energy_policy.py

PYTHONPATH=. python -m pytest \
  tests/test_audit_stopping_power_cross_energy_summary.py \
  tests/test_compare_stopping_power_cross_energy_policy.py -q

6 passed in 0.04s

PYTHONPATH=. python tools/audit/audit_stopping_power_cross_energy_summary.py \
  scripts/single_stave/compare_stopping_power.py \
  --output docs/validation/stopping_power_cross_energy_remediation_validation.json

CROSS-ENERGY SUMMARY AUDIT: status=VALIDATED
```

Additional checks:

- committed source Git blob matched the locally validated file;
- committed test Git blob matched the locally validated file;
- maximum changed Python line length was 91 characters;
- validation JSON parsed successfully;
- SVG parsed successfully as XML.

## Evidence and interpretation boundary

This is synthetic software-method evidence, not detector data. It establishes that
the canonical reporter no longer emits an unsupported cross-energy average. It
does not provide uncertainties, covariance, total-energy-loss closure, or
Geant4/PSTAR agreement. A future combined quantity requires a preregistered
measurand, uncertainty model, covariance treatment, combination method,
energy-grid sensitivity study, and coverage validation.
