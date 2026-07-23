# PSTAR component-sum integration audit

## Scope

This audit checks whether the canonical stopping-power comparison can bypass the
repository's exact-decimal PSTAR identity gate. The identity is

\[
S_{\mathrm{total}} = S_{\mathrm{electronic}} + S_{\mathrm{nuclear}}.
\]

The result is a software/numerical validation. It is not detector data and does
not establish Geant4 agreement with PSTAR.

## Confirmed defect

Before this change, `compare_stopping_power.py` maintained an independent float
parser. It rejected malformed, nonfinite, nonphysical, duplicate-energy, and
out-of-order rows, but it did not test the cross-column identity. A reference
row such as `1,9,1,8` was therefore structurally valid and could enter a
numerical ratio.

## Method

`tools/audit/validate_pstar_component_sum.py` now exposes
`read_validated_pstar_table()`, which returns both canonical float rows and the
exact-decimal provenance summary. The comparison imports this parser directly.
No second PSTAR parser remains in the canonical comparison path.

Each row is accepted only when the half-unit-in-last-written-place interval for
the declared total overlaps the interval obtained by adding the electronic and
nuclear component intervals.

## Regression fixtures

- Valid reference: `1,9,1,10` and `2,4,1,5`.
- Invalid reference: `1,9,1,8` and `2,4,1,5`.
- Simulation: one raw proton event at 1 MeV with 1 MeV deposited over 1 mm.

The invalid direct CLI invocation must return status 2, must not write an output
CSV, and must not print `NUMERICAL TOLERANCE: PASS`.

## Commands

```text
python -m py_compile \
  scripts/single_stave/compare_stopping_power.py \
  tools/audit/validate_pstar_component_sum.py \
  tests/test_validate_pstar_component_sum.py \
  tests/test_compare_stopping_power_pstar_component_integration.py

python -m pytest \
  tests/test_validate_pstar_component_sum.py \
  tests/test_compare_stopping_power_pstar_component_integration.py \
  tests/test_compare_stopping_power_reference_integrity.py \
  tests/test_compare_stopping_power_energy_range.py \
  tests/test_compare_stopping_power_quenched_proxy.py \
  tests/test_compare_stopping_power_sim_input_integration.py \
  tests/test_validate_stopping_power_sim_table.py -q
```

Result: `42 passed in 4.22s`.

## Output provenance added

Every comparison row now records:

- reference input SHA-256 and byte size;
- validated reference-row count;
- PSTAR validator version;
- component identity;
- component-consistency state.

The CLI also prints one `PSTAR REFERENCE VALIDATION` line before any numerical
acceptance statement.

## Acceptance

The integration is accepted when:

1. all reference rows are returned by one shared validated parser;
2. a component-inconsistent reference exits with status 2;
3. no numerical PASS or result CSV is produced for invalid input;
4. valid output carries immutable reference provenance;
5. all focused reference and simulation-input regressions pass.

All five criteria passed.

## Scientific boundary

This closes the parser-integration blocker only. It does not independently
verify the external NIST transcription or material selection. It also does not
show that local deposited energy equals projectile total energy loss, and it
does not validate the approximate deuteron velocity-scaling relation.
