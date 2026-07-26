# DeltaE CSV composite-key identity remediation

## Status

`VALIDATED` for the canonical CSV reader and same-snapshot provenance boundary.

Policy: `DELTAE_CSV_COMPOSITE_KEYS_MUST_BE_READ_AS_LOSSLESS_TEXT`.

## Confirmed former defect

The former canonical `read_table()` used default `pandas.read_csv(path)` inference. Exact
`source_file_id` tokens `001` and `1` became the same integer token, collapsed two exact composite
keys into one, and created one false data/MC inner-join match in the deterministic control.
Post-read string conversion cannot restore leading zeros or undo a match already created during
inference.

## Remediation

The canonical front door now reads each CSV-like input exactly once as bytes, decodes strict UTF-8,
and parses all three key columns as pandas strings:

- `source_file_id`
- `run_id`
- `event_id`

The exact byte count and SHA-256 from that same snapshot are retained and reused in `manifest.json`.
The reader policy and dtype map are also published in `result.json` and the manifest. The established
761-line numerical/plotting implementation is retained byte-for-byte as
`scripts/single_stave/_deltaE_E_core.py`; the front door patches only the reader, result metadata,
and input-provenance boundary.

## Reproducible controls

- Raw exact identifiers: `001`, `1`.
- Default inference: one distinct key and one false cross-file match.
- Corrected reader: two distinct keys and zero false matches.
- Invalid UTF-8: rejected before parsing.
- Same-snapshot mutation control: after the file path was replaced, the manifest retained the byte
  count and SHA-256 of the bytes actually parsed.

## Validation

Executed locally against the exact committed front-door bytes:

```text
python -m py_compile deltaE_E.py test_deltae_csv_key_remediation.py
PYTHONPATH=. pytest -q test_wrapper.py
4 passed in 0.03s
```

An AST-equivalent audit confirmed that `read_table()` itself contains the required `read_bytes`,
strict `decode`, `pandas.read_csv(..., dtype=...)`, policy token, and all composite-key names.
The committed repository regression additionally requires the exact current-source audit to return
zero findings and performs a direct CSV-backed CLI run. Those two full-repository tests were not
executed locally because the networkless container could not materialize the retained core, although
its exact original Git blob is preserved in the implementation commit.

## Better-method comparison

- Post-read string casting was rejected because it cannot recover lost leading zeros.
- Protecting only `source_file_id` was rejected because all three columns define identity.
- Reading the path again for provenance was rejected because the path can change after parsing.
- Removing CSV support was rejected because it remains a documented workflow.
- The selected front-door/core split preserves the reviewed numerical implementation byte-for-byte
  while making the input contract small, explicit, and directly auditable.

## Scientific boundary

No exact A-002 pulse table was processed. No amplitude convention, pulse polarity, stopping fraction,
DeltaE-E PID result, uncertainty budget, calibration, or detector-performance claim is established.
`AUD-DELTAE-001`, `AUD-DELTAE-002`, and `BLK-AMP-001` remain open.
