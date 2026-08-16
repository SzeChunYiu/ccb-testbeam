# Stopping-power simulation-input integration audit

## Scope

This audit reviews the CSV ingestion path used by
`scripts/single_stave/compare_stopping_power.py` before the deposited-energy
proxy is compared with the committed PSTAR table.

## Confirmed defect

Before this change the repository had a strict standalone preflight validator,
but the canonical comparison CLI still used a separate permissive reader. That
reader silently continued past rows with missing particle, energy, deposit, or
usable track length, and selected the first populated alias without rejecting
multiple populated aliases.

A synthetic three-row reproduction with a missing energy in the middle row
returned two rows and silently skipped one. This is parser regression evidence,
not detector data and not a Geant4/PSTAR agreement result.

## Validated implementation

The comparison now imports
`tools.audit.validate_stopping_power_sim_table.read_validated_simulation_table`.
The shared parser validates every noncomment row, normalizes particle labels and
track-length units, rejects ambiguous aliases and mixed deposit semantics, and
returns exact input provenance. The comparison output records:

- simulation input SHA-256 and byte size;
- number of validated rows;
- shared validator version;
- canonical energy-deposit basis.

Malformed simulation input returns status 2 before any numerical tolerance PASS
can be printed. Quenched proxy input remains labelled non-comparable and exits
nonzero.

## Reproducible validation

```text
python -m py_compile \
  scripts/single_stave/compare_stopping_power.py \
  tools/audit/validate_stopping_power_sim_table.py \
  tests/test_compare_stopping_power_reference_path.py \
  tests/test_compare_stopping_power_energy_range.py \
  tests/test_compare_stopping_power_reference_integrity.py \
  tests/test_validate_stopping_power_sim_table.py \
  tests/test_compare_stopping_power_sim_input_integration.py

python -m pytest \
  tests/test_compare_stopping_power_reference_path.py \
  tests/test_compare_stopping_power_energy_range.py \
  tests/test_compare_stopping_power_reference_integrity.py \
  tests/test_validate_stopping_power_sim_table.py \
  tests/test_compare_stopping_power_sim_input_integration.py -q

35 passed in 4.34s
```

The focused suite covers the existing reference path, interpolation-domain and
reference-integrity gates, the standalone parser contract, and canonical CLI
integration. The changed Python files have maximum line lengths of 91, 91, and
99 characters. Ruff was unavailable.

## Scientific boundary

This integration prevents malformed or ambiguous event rows from reaching the
PSTAR diagnostic. It does not establish agreement between Geant4 and PSTAR,
validate the external PSTAR transcription, prove that deposited energy equals
projectile energy loss, validate deuteron velocity scaling, or produce a
detector-performance result. Real exported simulation tables remain to be
validated by exact path, byte size, SHA-256, row count, basis, and code commit.
