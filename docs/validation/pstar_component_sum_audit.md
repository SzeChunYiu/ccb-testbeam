# PSTAR component-sum integrity audit

**Task:** `AUD-G4-012`  
**Scope:** local reference-table integrity only  
**Scientific status:** validation of a deterministic table identity; not a Geant4/PSTAR closure

## Question

Does every row of the committed proton PSTAR table satisfy the NIST column identity

\[
S_{\mathrm{total}} = S_{\mathrm{electronic}} + S_{\mathrm{nuclear}}
\]

within the decimal rounding precision actually written in the CSV?

NIST documents total proton stopping power as the sum of the electronic and nuclear stopping powers. The current comparison parser validates that each field is finite and physical, but it does not test this cross-column identity. A transcription error confined to `total_MeV_cm2_g` could therefore directly bias every reported simulation/reference ratio while passing all existing structural checks.

## Method

Added `tools/audit/validate_pstar_component_sum.py` version 1.0.0.

For each noncomment row, the validator:

1. parses the four required fields as exact decimal tokens;
2. rejects missing, nonnumeric, nonfinite, nonphysical, duplicate-energy, or out-of-order input;
3. assigns each written value a rounding interval equal to one half-unit in its last written decimal place;
4. forms the interval for `electronic + nuclear` by adding the component intervals;
5. requires that interval to overlap the declared-total interval;
6. records exact input bytes, SHA-256, row count, rounding model, and overlap-width extrema.

This interval method avoids an arbitrary floating-point tolerance. For example, the committed row

```text
0.001,186,40.73,226.8
```

represents component-sum interval `[226.225, 227.235]` and total interval `[226.75, 226.85]`; the intervals overlap, so the rounded values are mutually consistent.

## Exact committed-table validation

The GitHub contents API reported blob SHA:

```text
7e953dd346caedcee6da54180fb636b890a64040
```

The reconstructed exact bytes produced the same Git blob SHA, establishing byte identity before execution.

Command:

```bash
python tools/audit/validate_pstar_component_sum.py \
  data/reference/stopping_power/pstar_polystyrene.csv \
  --output docs/validation/pstar_component_sum_validation_payload.json
```

Measured result:

- file bytes: `7413`;
- SHA-256: `bc4d8b018115fd0892fe4ea22b6ec3da7be8ab65afa7595337c491ae6ed869dd`;
- validated rows: `141`;
- component identity: all rows consistent under declared decimal rounding;
- minimum overlap width: `0.0002615 MeV cm^2/g`;
- maximum overlap width: `0.110 MeV cm^2/g`.

## Regression validation

Commands:

```bash
python -m py_compile \
  tools/audit/validate_pstar_component_sum.py \
  tests/test_validate_pstar_component_sum.py

python -m pytest tests/test_validate_pstar_component_sum.py -q
```

Result:

```text
8 passed in 1.21s
```

The tests cover NIST-style rounded rows, scientific notation, exact provenance, inconsistent totals, malformed/nonfinite/nonphysical fields, fail-closed CLI behavior, and machine-readable output.

## Acceptance and limitation

The new standalone validator is validated and the exact committed PSTAR table passes it. However, `compare_stopping_power.py` does not yet invoke this cross-column validator, so a caller can still bypass the new check by invoking the comparison CLI directly on a modified reference table. This task is therefore `PARTIAL` until the canonical comparison path shares the same validated parser.

This audit does not independently re-query NIST, establish that every committed number was transcribed from the correct material, validate the deuteron velocity-scaling approximation, or establish agreement between Geant4 local deposited energy and projectile total stopping power.
