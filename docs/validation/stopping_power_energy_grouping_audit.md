# Stopping-power configured-energy grouping audit

## Scope

This is a synthetic regression audit of `scripts/single_stave/compare_stopping_power.py`.
It is not detector data and does not establish Geant4/PSTAR agreement.

## Confirmed defect

The former aggregator keyed events by:

```python
(particle, round(energy_MeV, 1))
```

and then compared the pooled deposited-energy/path-length ratio with PSTAR at the
arithmetic mean of the original energies. Two distinct configured energies,
`1.01 MeV` and `1.04 MeV`, therefore became one output point at `1.025 MeV`.
Because stopping power is energy dependent and the interpolation is nonlinear,
implicit coalescence changes both the simulation statistic and the reference
energy without an explicit binning contract.

The exact pre-change reconstruction matched Git blob
`d525bf6b74a18d135b38434dd5085123b995132a`. Running the new regression against
that blob produced `2 failed, 1 passed`; both failures measured the silent
`[1.01, 1.04] -> [1.025]` merge.

## Correction

Aggregation now keys on the exact validated numeric energy:

```python
(particle, energy_MeV)
```

Numerically identical tokens such as `1.0` and `1.00` still group together after
canonical numeric parsing, while distinct values remain separate. Result rows
and output CSVs record:

```text
energy_grouping = EXACT_CONFIGURED_ENERGY
```

The CLI prints the same grouping mode before the reference-validation summary.

## Validation

```text
python -m py_compile \
  scripts/single_stave/compare_stopping_power.py \
  tests/test_compare_stopping_power_energy_grouping.py \
  tests/test_compare_stopping_power_energy_range.py \
  tests/test_compare_stopping_power_sim_input_integration.py \
  tests/test_compare_stopping_power_pstar_component_integration.py \
  tests/test_compare_stopping_power_quenched_proxy.py

python -m pytest \
  tests/test_compare_stopping_power_energy_grouping.py \
  tests/test_compare_stopping_power_energy_range.py \
  tests/test_compare_stopping_power_sim_input_integration.py \
  tests/test_compare_stopping_power_pstar_component_integration.py \
  tests/test_compare_stopping_power_quenched_proxy.py -q

19 passed in 3.22s
```

Additional checks:

- exact pre-change reconstruction matched the Git blob;
- changed Python files contain no line longer than 100 characters;
- validation JSON parsed;
- SVG parsed as XML.

## Acceptance boundary

This closes an implicit numerical-binning defect. It does not validate the
local-deposition observable, the deuteron `E/2` approximation, external PSTAR
transcription, or real Geant4 stopping-power closure.
