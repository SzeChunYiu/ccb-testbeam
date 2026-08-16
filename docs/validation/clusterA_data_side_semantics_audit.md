# Cluster A data-side row and PrimaryWeight semantics audit

Policy: `DATA_ROWS_MUST_BE_FINITE_AND_ROW_LEVEL_RESULTS_MUST_NOT_POSE_AS_EVENTS`

## Confirmed defects

The former data-side script silently converted nonnumeric cells to zero, did not reject
NaN or infinity, described a multi-row derived table using event-count language, and loaded
`PrimaryWeight` while drawing an unweighted MC hexbin. For two MC events with weights 1 and
100 in the same bin, the former plotted value is 2; the correct weighted value is 101.

The 632,939 rows and 385,984 unique `(source_file_id, run, evt)` keys are different
statistical units. Row-level stopping counts and correlations cannot be quoted as event-level
fractions or closure results without the canonical composite merge.

## Correction

`scripts/studies/clusterA_data_side.py` now:

- performs one strict UTF-8 input snapshot and records byte count and SHA-256;
- rejects missing columns, nonnumeric cells, NaN, infinity, and an empty selected sample;
- labels data outputs as row-level and withholds event-level authorization;
- aligns one finite nonnegative `PrimaryWeight` to each selected MC event;
- rejects a selected MC weight vector with no positive weight;
- plots MC density with `C=PrimaryWeight` and `reduce_C_function=np.sum`;
- publishes atomic machine-readable provenance and an explicit scientific boundary;
- exposes a CLI and main guard so the contract is independently testable.

Validated Git blobs:

- script: `8bda06c55dc00c1af3e025411fcc55df43f1487e`;
- tests: `21d3c9ecdd2f9837cd8776adc69fccf5a9a11b63`.

## Validation

```text
python -m py_compile \
  scripts/studies/clusterA_data_side.py \
  tests/test_clusterA_data_side_contract.py \
  tools/audit/render_clusterA_data_side_semantics_evidence.py

pytest -q tests/test_clusterA_data_side_contract.py
7 passed in 0.36s
```

Production beam CSV and Krakow ROOT bytes were unavailable, so no production plot,
correlation, stopping distribution, or data/MC result was regenerated. The next production
run must use immutable content-addressed inputs and review the resulting row-level plots
before any event-level composite-merge study.
