# PSTAR Reference-Integrity Audit

## Scope

This synthetic regression audit covers the CSV parser in `scripts/single_stave/compare_stopping_power.py`. It does not validate Geant4, PSTAR physics, deuteron scaling, or detector performance.

## Confirmed failure mode

The former parser silently skipped rows with missing or nonnumeric required values and sorted the surviving rows. It also accepted duplicate or out-of-order energies, IEEE nonfinite values, negative stopping components, and nonpositive totals.

A three-row reference with a malformed middle row therefore became a two-row reference without an error. The exact pre-change blob was `0436fb390476697cfc83f88208322a99d7792a1c`. The new regression produced six expected failures against that blob, including a CLI case that returned success and printed `NUMERICAL TOLERANCE: PASS`.

## Corrected behavior

The parser now requires all four columns, parseable values in every data row, finite physical values, strictly increasing energy in declared file order, and at least two validated rows. Malformed input raises `StoppingPowerInputError`; the CLI returns input-error status 2 and prints no numerical PASS.

## Validation

```text
python -m py_compile scripts/single_stave/compare_stopping_power.py tests/test_compare_stopping_power_reference_path.py tests/test_compare_stopping_power_energy_range.py tests/test_compare_stopping_power_reference_integrity.py
python -m pytest tests/test_compare_stopping_power_reference_path.py tests/test_compare_stopping_power_energy_range.py tests/test_compare_stopping_power_reference_integrity.py -q
14 passed in 2.94s
```

The reference-path test used a synthetic local table covering the self-test energies. The committed PSTAR file was inspected through GitHub but was not materialized in the execution container, so its complete byte-for-byte parser run was not performed here.

## Evidence classification

The parser defect was independently reproduced with synthetic inputs. The correction is validated by focused regression. The visual is a synthetic failure-mode schematic. Scientific status remains `DIAGNOSTIC_ONLY`; accepted stopping-power closure is not established.
