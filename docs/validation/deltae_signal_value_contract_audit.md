# DeltaE present-signal value contract audit

## Status

`VALIDATED` for the focused software-integrity remediation under
`DELTAE_PRESENT_SIGNAL_CELLS_MUST_BE_FINITE_NUMERIC`.

This does not authorize an A-002 physics result.

## Confirmed defect

The former canonical path distinguished an absent downstream column only at the schema level, but
it did not preserve that distinction at the cell level. The retained numerical core used
`pd.to_numeric(..., errors="coerce").fillna(0.0)` for supported present B-layer columns. Therefore:

- malformed text or a missing-value cell could become zero and be interpreted as no deposit;
- positive or negative infinity remained present and could enter energy sums, stopping categories,
  density plots, conditional profiles, and result tables;
- any extra MC `edep_B*` column discovered by `mc_layer_columns()` could participate in the full
  downstream energy and stopping-layer calculation without an all-column finite-value gate.

Exact former front-door blob: `a5c255a971a7cf672f011f84b91a3c7b64d1f209`.
Exact retained-core blob inspected: `fe5dd5e4673f32fa5a4b94776531f2b392e12414`.

The scientific distinction is material: a wholly absent supported detector layer and a present but
invalid measured cell are not equivalent missing-data states. Only the former is eligible for the
existing documented zero-fill convention.

## Remediation

Commit `63348699fe3a507fb9008ee582b193c28c7a7b20` updates the canonical front door to:

1. coerce every present data `amp_B2`, `amp_B4`, `amp_B6`, and `amp_B8` cell to numeric;
2. require every converted value to be finite before absent-layer filling;
3. discover and validate every present MC `edep_B*` column, including deeper optional layers;
4. retain zero fill only for a wholly absent supported downstream column;
5. raise `SignalValueError` with the affected column, count, and first row indices;
6. install the strict functions into the retained core's production hooks;
7. publish the signal-value and missing-layer policies in both `result.json` and `manifest.json`.

Corrected source blob: `be00a58dbbc3c2b9de424c80bea3b5a4be6fe119`.
Corrected source bytes: `10349`.
Corrected source SHA-256:
`ef51bec47aa15eada369a4e46f4036dfe4ba54409030aa18adf1a3d951165548`.

## Synthetic controls

The focused validation reproduced the former behavior and the corrected boundary:

| Control | Former behavior | Corrected behavior |
|---|---|---|
| present `amp_B4="bad"` | coerced to missing, then zero | `SignalValueError` |
| present `amp_B4=+inf` | infinity retained | `SignalValueError` |
| present optional `edep_B10=+inf` | retained and used by full-energy/stopping code | `SignalValueError` |
| absent `amp_B8` or `edep_B8` column | zero-filled | zero-filled |
| finite numeric string | coerced | coerced with value preserved |

## Validation

Executed against the exact proposed source, focused tests, audit gate, and renderer:

```text
python -m py_compile \
  scripts/single_stave/deltaE_E.py \
  tools/audit/audit_deltae_signal_value_contract.py \
  tests/test_deltae_signal_value_contract.py \
  tests/test_audit_deltae_signal_value_contract.py \
  tools/audit/render_deltae_signal_value_evidence.py

PYTHONPATH=. pytest -q \
  tests/test_deltae_signal_value_contract.py \
  tests/test_audit_deltae_signal_value_contract.py

19 passed in 3.06s
```

Additional checks:

- exact-source audit: `VALIDATED`, zero findings;
- malformed-contract mutation: fail closed;
- invalid UTF-8 audit input: controlled status 2;
- audit input/output alias: rejected;
- atomic JSON replacement: passed;
- JSON parsing: passed;
- SVG XML parsing: passed;
- changed Python maximum line length: at most 100 characters.

Environment: Python `3.13.5`, pandas `2.2.3`, NumPy `2.3.5`.

## Visual evidence

`docs/validation/deltae_signal_value_contract.svg` is synthetic software/provenance evidence. It
shows whether malformed and infinite present cells remain accepted before and after the correction.
It is not detector data and is not a physics acceptance plot.

## Better-method comparison

Three approaches were considered:

1. **Continue cell-level zero filling.** Rejected because it erases the distinction between invalid
   measurement and absent detector layer, biases stopping fractions toward shallower/no-reach
   categories, and conceals schema/data-quality failures.
2. **Drop invalid rows.** Rejected as a default because it silently changes event cardinality and can
   introduce selection bias unless a preregistered exclusion and uncertainty treatment exists.
3. **Fail closed on every present invalid signal; fill only absent supported columns.** Selected. It
   preserves cardinality, exposes the exact failure, retains the established missing-layer policy,
   and allows an explicit later decision about repair or exclusion.

## Boundaries and unrun checks

No exact A-002 pulse table, ROOT file, amplitude convention, pulse polarity, stopping fraction,
DeltaE-E PID result, uncertainty budget, calibration, or detector-performance result was produced.
`AUD-DELTAE-001`, `AUD-DELTAE-002`, `AUD-AMP-009`, `AUD-AMP-010`, and `BLK-AMP-001` remain open.

Repository-wide pytest, ruff, ROOT processing, real Parquet-engine execution, GitHub Actions, and the
repository-wide link inventory were not run in the local validation environment and are not claimed.
