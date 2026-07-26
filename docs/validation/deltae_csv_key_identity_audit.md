# DeltaE CSV composite-key identity audit

## Scope

Task `AUD-DELTAE-005` reviews the CSV input boundary in
`scripts/single_stave/deltaE_E.py`. The canonical event key is
`(source_file_id, run_id, event_id)`, so every key token must survive CSV parsing
without numeric inference before uniqueness checks, sample bookkeeping, or data/MC
joins.

Policy:

`DELTAE_CSV_COMPOSITE_KEYS_MUST_BE_READ_AS_LOSSLESS_TEXT`

Initial remote `main`: `f1a615d5b591b63c91b03124d243daf8372b61cd`.
Inspected source blob: `fe5dd5e4673f32fa5a4b94776531f2b392e12414`.

## Demonstrated defect

The current CSV branch is equivalent to:

```python
return pd.read_csv(path)
```

No dtype contract is applied to the three composite-key columns and the file is
not snapshotted as one strict-UTF-8 byte sequence before parsing.

A deterministic control used two exact source identifiers, `001` and `1`, with
the same run and event tokens. Under pandas 2.2.3 default inference:

- the parsed source identifiers became `1` and `1`;
- two exact composite keys collapsed to one parsed key;
- a data row from source `001` and an MC row from source `1` produced one false
  inner-join match.

With all three key columns loaded as text:

- two exact keys remained two keys;
- the false cross-file join count was zero.

This is not cosmetic provenance loss. It can change event cardinality, create false
duplicate-key rejection, or cross-contaminate data/MC rows before a stopping or
DeltaE-E result is calculated.

## Downstream review

The strict bundle consumer introduced by `AUD-DELTAE-004` applies an explicit
text contract to provenance columns. The Cluster A data-side reader uses a
single strict-UTF-8 byte snapshot and `csv.DictReader`, preserving
`source_file_id` as text. The vulnerable boundary identified in this unit is the
generic canonical `deltaE_E.py` CSV input path.

## Better-method comparison

1. **Post-read string casting** is rejected because it cannot restore leading
   zeros or undo an already-created false match.
2. **Text dtype for only `source_file_id`** reduces the demonstrated failure but
   leaves the other key tokens dependent on inference. The composite key should
   have one explicit lossless contract.
3. **Parquet-only input** supplies stronger typing but would remove the supported
   CSV workflow and does not repair existing CSV artifacts.
4. **Selected contract:** read CSV bytes once, decode strict UTF-8, and parse all
   three key columns as text. Numeric physics columns remain explicitly
   coercible and independently validated downstream.

## Audit implementation

Added:

- `tools/audit/audit_deltae_csv_key_identity.py`
- `tests/test_audit_deltae_csv_key_identity.py`
- `tools/audit/render_deltae_csv_key_identity_evidence.py`
- `docs/validation/deltae_csv_key_identity_validation.json`
- `docs/validation/deltae_csv_key_identity.svg`

The auditor snapshots source bytes once, parses the Python AST, checks the reader
contract, runs the lossy and lossless controls, rejects invalid UTF-8 and
input/output aliases, and publishes JSON atomically. CLI status is 0 for
`VALIDATED`, 1 for a demonstrated `FLAWED` contract, and 2 for controlled input
errors.

## Validation

Executed:

```text
python -m py_compile \
  tools/audit/audit_deltae_csv_key_identity.py \
  tests/test_audit_deltae_csv_key_identity.py \
  tools/audit/render_deltae_csv_key_identity_evidence.py

pytest -q tests/test_audit_deltae_csv_key_identity.py
6 passed in 0.09s
```

Environment:

- Python 3.13.5
- pandas 2.2.3

The JSON parsed successfully, the SVG parsed as XML, and changed Python lines are
at most 100 characters. The executable control used the exact behavioral excerpt
of the inspected current reader. The full repository source was not executed in
the networkless container; that limitation is explicit in the JSON rather than
concealed.

## Findings

Current status: `FLAWED`, five findings.

- `CSV_KEY_DTYPE_MISSING`
- `CSV_NOT_SINGLE_READ_STRICT_UTF8`
- `CSV_KEY_POLICY_MISSING`
- `DISTINCT_COMPOSITE_KEYS_COLLAPSE`
- `FALSE_CROSS_FILE_MATCH`

## Required remediation

Before a CSV-backed canonical DeltaE-E run is accepted:

1. `deltaE_E.py` must snapshot CSV bytes once and decode strict UTF-8.
2. `source_file_id`, `run_id`, and `event_id` must be parsed as lossless text.
3. Direct reader and CLI regressions must cover leading-zero distinctions,
   invalid UTF-8, duplicate detection, and false-join prevention.
4. Input byte size and SHA-256 must bind the parsed rows used by the analysis.
5. The exact-source audit must return `VALIDATED` with zero findings.

## Scientific boundary

This is software and event-identity validation. No exact A-002 pulse table was
processed and no amplitude convention, stopping fraction, DeltaE-E PID result,
uncertainty budget, calibration, or detector-performance result is established.
`AUD-DELTAE-001`, `AUD-DELTAE-002`, and `BLK-AMP-001` remain open.
