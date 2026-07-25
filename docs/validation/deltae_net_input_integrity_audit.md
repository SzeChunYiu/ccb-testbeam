# ΔE-E net-amplitude input-integrity audit

## Scope and evidence class

This is a software-integrity and provenance audit of
`scripts/single_stave/deltaE_E_data_bridge.py` at remote `main`
`67a7cdd6ef0dc64f00a9ebb43077d2acc1a7418e` (Git blob
`7f50ce667a6cde07e94717d0187831da4d8459ac`). It is not detector data,
a calibration, a stopping-profile measurement, or a particle-identification result.

Policy:

`DELTAE_NET_AMPLITUDE_ROWS_MUST_BE_FINITE_NUMERIC_BEFORE_AGGREGATION`

## Confirmed defect

The absolute-code path validates numeric finiteness before signed pedestal
conversion. The net-amplitude path instead assigns the selected source column
directly to the aggregation value. The subsequent `groupby(...).max()` and
`pivot_table(...)` can omit an all-NaN stave cell, and the layer-completion loop
then fills that omitted cell with `0.0`.

The exact current source operations are:

- net assignment at lines 183-184;
- event/stave aggregation and pivot at lines 200-215;
- missing-layer zero filling at lines 218-221.

A synthetic event with finite B4 amplitude and NaN B2 net amplitude is therefore
accepted as one physical event with `amp_B2 = 0.0`. A positive-infinity B2 value
is retained. Both cases violate fail-closed input semantics and can change
stopping-layer classification and the ΔE coordinate without an explicit
rejection.

## Audit gate

Added `tools/audit/audit_deltae_net_input_integrity.py`. It imports a candidate
bridge and executes controlled finite, NaN, and positive-infinity net-amplitude
cases. It records exact audited-source bytes and SHA-256, publishes JSON
atomically, rejects output/source aliases, and returns:

- `0` for `VALIDATED`;
- `1` for a demonstrated flaw;
- `2` for an unreadable or non-executable source.

The focused regression includes a vulnerable fixture preserving the current
assignment/groupby/pivot/zero-fill operations and a corrected fixture that
coerces the net source column with `pd.to_numeric` and rejects every nonfinite
value before aggregation.

## Validation

```text
python -m py_compile \
  tools/audit/audit_deltae_net_input_integrity.py \
  tests/test_audit_deltae_net_input_integrity.py \
  tools/audit/render_deltae_net_input_integrity_evidence.py

pytest -q tests/test_audit_deltae_net_input_integrity.py

5 passed in 0.12s
```

JSON parsing and SVG XML parsing passed. Maximum changed Python line length was
95 characters. The SVG is synthetic software evidence and explicitly does not
represent detector data.

## Required remediation

Before any evidence-authorized A-002 production rerun:

1. convert the selected net-amplitude column with `pd.to_numeric(errors="coerce")`;
2. reject every nonfinite source row before `groupby`, `pivot_table`, or zero filling;
3. distinguish a genuinely absent stave from an invalid measured stave row;
4. add exact bridge and strict-runner integration regressions for NaN, infinity,
   nonnumeric values, and mixed finite/nonfinite staves;
5. rerun the complete focused bridge/strict-runner suites and regenerate this
   audit against the corrected canonical source.

## Acceptance state

`AUD-DELTAE-003` is `PARTIAL`. The defect, audit gate, regression, machine-readable
record, and visual evidence are validated. The canonical bridge is not changed
in this unit, so `BLK-DELTAE-003` remains open and no A-002 output is authorized.
