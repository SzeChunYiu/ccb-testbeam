# Stopping-power report precision audit

## Scope

This is synthetic regression evidence for the CSV and terminal serialization in
`scripts/single_stave/compare_stopping_power.py`. It is not detector data and does
not establish Geant4/PSTAR agreement.

## Confirmed defect

The comparison grouped events by exact parsed floating-point energy but serialized
every float with six significant digits. Two distinct configured energies,
`1.0000001 MeV` and `1.0000002 MeV`, therefore became the same CSV token, `1`.
The terminal table also printed both as `1.00`. A downstream reader could no longer
reconstruct which result belonged to which exact configured energy, despite the
row claiming `EXACT_CONFIGURED_ENERGY` grouping.

The exact pre-change script was reconstructed from Git blob
`c3884d953a38b0dad69f50e3a9dc787bc1f29fd0`. Running the new regression against
those bytes produced `2 failed, 1 passed`; the CSV assertion measured tokens
`["1", "1"]` for the two distinct energies.

## Correction

Floating-point CSV fields now use Python's shortest round-trip representation.
Parsing a written token with `float()` therefore reproduces the exact binary float
used by the calculation. The result and CSV record
`report_float_serialization=PYTHON_REPR_ROUND_TRIP`. Nonfinite floats are rejected
at serialization even though upstream validators should already exclude them.
The terminal table uses the same round-trip representation for configured energy.

## Validation

```text
python -m py_compile \
  scripts/single_stave/compare_stopping_power.py \
  tests/test_compare_stopping_power_report_precision.py

python -m pytest tests/test_compare_stopping_power_report_precision.py -q
3 passed in 0.03s
```

The tests verify the historical six-significant-digit collision, exact round-trip
preservation for every float field in the CSV, distinct terminal energy labels,
and fail-closed nonfinite serialization. Changed Python lines are at most 93
characters.

## Scientific boundary

This fixes serialized numerical identity only. It does not implement an uncertainty
budget, validate a real Geant4 export, replace the local-deposition proxy with an
accepted projectile-energy-loss observable, or establish a detector result.
