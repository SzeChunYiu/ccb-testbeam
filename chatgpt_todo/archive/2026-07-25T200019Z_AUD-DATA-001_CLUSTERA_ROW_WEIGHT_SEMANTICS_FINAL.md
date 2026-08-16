# Final immutable handoff — AUD-DATA-001 Cluster A row and weight semantics

This record supersedes the preliminary same-stamp archive only for the final regression count
and validated blob identities. The earlier archive remains retained for provenance.

- Initial remote `main`: `39378e21c436344b43e9f659f5a76bce2bca1228`
- Concurrent non-overlapping merge: `c39aba2c55091aec501acbe402523e2d94be2c58`
- Policy: `DATA_ROWS_MUST_BE_FINITE_AND_ROW_LEVEL_RESULTS_MUST_NOT_POSE_AS_EVENTS`
- Focused result: `VALIDATED`
- Cumulative result: `PARTIAL`

## Final defects and remediation

The former Cluster A data-side path converted malformed numeric cells to zero, accepted
nonfinite values, loaded but ignored `PrimaryWeight`, and used event/stopping-distribution
language for a table with 632,939 rows and 385,984 composite keys.

The final script strictly validates UTF-8 and numeric inputs, rejects empty selected samples,
distinguishes row and event denominators, withholds event-level authorization, aligns and
sums finite nonnegative `PrimaryWeight`, rejects a selected all-zero weight vector, records
full source hashes, and writes result JSON atomically.

## Final validation

```text
python -m py_compile \
  scripts/studies/clusterA_data_side.py \
  tests/test_clusterA_data_side_contract.py \
  tools/audit/render_clusterA_data_side_semantics_evidence.py

pytest -q tests/test_clusterA_data_side_contract.py
7 passed in 0.36s
```

- Script blob: `8bda06c55dc00c1af3e025411fcc55df43f1487e`
- Test blob: `21d3c9ecdd2f9837cd8776adc69fccf5a9a11b63`
- Script SHA-256: `941adc78b9000cc7b117a1f12ab7e44a22135e4bfcc4ac873ea6e0e2d8a1314d`
- Test SHA-256: `c0b7eafbc4d954bf170a12dec6eeff99fce71a3eecdd30d552d72a98f65a64fa`
- JSON parse: PASS
- SVG XML parse: PASS
- Maximum Python line length: 96 characters

## Direct-main additions after the preliminary archive

- `22b0b5bf610bae8eab496d2b7b618d2884c28408` — empty-sample and positive-weight gate
- `6034f47a5acad6a3eacc278e3408e6c9abfb9e98` — final regression
- `e6c457bb322fe59013d13f3c073f036509d84849` — final validation JSON
- `ec1ca0827e2dfe4620f66b53c11411960caec832` — final audit report
- `a26a3cc257e2b34ab16684ee07c64acedfd40137` — final active-task record

No production CSV/ROOT execution, production plot regeneration, event-level composite merge,
correlation, stopping fraction, data/MC closure, PID transfer, calibration, or detector-
performance claim is made. The next scientific unit must use immutable content-addressed
production inputs and separate row-level diagnostics from a preregistered event-level merge.

`SESSION_LOG.md` and long aggregate ledgers were not replaced because complete current bytes
were only available through paged/truncated reads and the connector lacks byte-safe append.
The archives and latest handoff preserve the append-equivalent record without overwriting
concurrent provenance.
