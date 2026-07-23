# Stopping-power report reproducibility audit

## Scope

This audit checks whether a CSV emitted by `compare_stopping_power.py` contains the
sufficient statistics and numerical configuration needed to independently
reconstruct its deposited-energy proxy and tolerance classification. It is a
synthetic software regression, not detector data and not a stopping-power closure.

## Confirmed defect

The pre-change report contained `sim_total_MeV_cm2_g`, `ratio`, and the resulting
classification, but omitted the values that generated them:

- summed deposited energy;
- summed track length;
- material density;
- tolerance percentage;
- the estimator identity.

Two runs over identical event rows could therefore use different density or
tolerance settings and produce materially different numerical values or statuses
without those settings appearing in the machine-readable report.

The exact pre-change file was reconstructed from Git blob
`5081da0b77bcfeba07dca95e5087c4b2057c362f`. Running the new tests against those
exact bytes produced two expected failures because the report keys were absent.

## Correction

Each result dictionary and CSV row now records:

- `deposit_sum_MeV`;
- `track_length_sum_mm`;
- `material_density_g_cm3`;
- `mass_stopping_estimator=RATIO_OF_SUMS_TRACK_LENGTH_WEIGHTED`;
- `tolerance_percent`.

The deposited-energy proxy is therefore independently reconstructable as

```text
(deposit_sum_MeV / track_length_sum_mm) * 10 / material_density_g_cm3
```

and the point-estimate classification is reconstructable as

```text
abs(delta_percent) <= tolerance_percent
```

The terminal output also names the estimator. Round-trip float serialization from
`AUD-G4-016` is retained.

## Validation

```text
python -m py_compile \
  scripts/single_stave/compare_stopping_power.py \
  tests/test_compare_stopping_power_report_precision.py \
  tests/test_compare_stopping_power_report_reproducibility.py

python -m pytest \
  tests/test_compare_stopping_power_report_precision.py \
  tests/test_compare_stopping_power_report_reproducibility.py -q

5 passed in 0.07s
```

The exact pre-change blob produced `2 failed in 0.11s` under the new regression.
Changed Python lines are at most 93 characters. The validation JSON and SVG parse
successfully.

## Interpretation boundary

This makes the report numerically self-describing. It does not validate local
energy deposit as projectile total energy loss, quantify secondary escape or
energy evolution, establish an uncertainty budget, or demonstrate Geant4/PSTAR
agreement.
