# CL-001 source-backed claim-ledger reconstruction audit

## Scope

This unit reconstructs only `CL-001`, the S00 selected B-stack pulse count, into the
canonical 43-column claim-ledger schema. It does not repair or interpret the other 23
width-mismatched rows and does not rerun raw ROOT processing.

Policy:

`SOURCE_BACKED_EXACT_COUNT_LEDGER_ROW`

## Evidence chain

The corrected row is bound to the repository-supported S00 chain:

- configuration: `configs/s00_reproduction.yaml`;
- implementation: `scripts/01_build_pulse_table_from_root.py`;
- report: `reports/S00_data_integrity_pipeline_reproduction/REPORT.md`;
- machine-readable gate: `reports/S00_data_integrity_pipeline_reproduction/count_match_table.csv`;
- manifest: `reports/S00_data_integrity_pipeline_reproduction/manifest.json`;
- diagnostic figure: `reports/S00_data_integrity_pipeline_reproduction/fig_counts_by_group_stave.png`;
- producing source commit recorded by the report: `dcde28d37b9adee4f56ee0348d090006c53d2fa1`.

The report, configuration, count table, and manifest were reconstructed byte-for-byte
from authenticated GitHub reads. Their local Git blob hashes matched the repository
content blobs before validation.

## Confirmed defects corrected

The former 40-column row placed late values three columns early under ordinary CSV
parsing. It also referenced paths not present in the repository:

- `reports/s00_pulse_table/REPORT.md`;
- `data/pulse_table.parquet`.

`FIG-GL-001` likewise pointed to stale/nonexistent paths:

- `scripts/s00_selector.py`;
- `data/s00_counts.csv`;
- `docs/figures/s00_gate.png`.

The reconstructed row now has exactly 43 fields and records the actual report,
implementation, generated data path, configuration, manifest, source commit, run
count, fixed-input exact-count scope, and intentionally untracked selected-pulse table.
The figure registry now points to the canonical S00 script, count table, and committed
S00 group/stave figure.

## Source-backed numerical checks

The validator independently checked:

- configured total selected pulses: `640737`;
- claim `current_value`: `640737`;
- claim `n_data`: `640737` pulses;
- configured unique runs: `33`;
- count-table report value: `640737`;
- count-table reproduced value: `640737`;
- delta: `0`;
- tolerance: `0`;
- gate state: `True`;
- manifest gate: `count_match_passed=true`;
- report source-commit prefix: `dcde28d`;
- full ledger source commit: `dcde28d37b9adee4f56ee0348d090006c53d2fa1`.

The selected pulse table is generated at
`data/processed/s00_selected_b_pulses.csv.gz` and is intentionally ignored by Git. The
row therefore records an exact deterministic count for fixed raw inputs and algorithm;
it does not imply a population confidence interval or quantify every provenance risk.

## Added validation gate

`tools/audit/validate_claim_ledger_cl001.py` version `1.0.0`:

- reads ledger/config/report/count-table/manifest/figure-registry bytes once;
- requires the canonical 43-field ledger header and exactly one `CL-001` row;
- checks the count and run cardinality against the S00 configuration;
- checks exact count-table closure and report wording;
- checks manifest/config/data-path agreement;
- checks the report commit prefix against the ledger source commit;
- checks the figure registry and tracked source paths;
- returns 0 for `VALIDATED`, 1 for measured inconsistencies, and 2 for controlled
  input/encoding/schema failures;
- writes deterministic JSON and an accessible SVG provenance-chain diagnostic.

## Validation

```text
python -m py_compile \
  tools/audit/validate_claim_ledger_cl001.py \
  tests/test_validate_claim_ledger_cl001.py

PYTHONPATH=. python -m pytest tests/test_validate_claim_ledger_cl001.py -q

5 passed in 0.65s

PYTHONPATH=. python tools/audit/validate_claim_ledger_cl001.py \
  --output docs/validation/claim_ledger_cl001_validation.json \
  --svg docs/validation/claim_ledger_cl001.svg

status: VALIDATED
issues: 0
configured runs: 33
count: 640737
```

Additional checks passed:

- validation JSON parsed successfully;
- SVG parsed as XML and contains `role="img"`, title, and description;
- maximum implementation line length: `96` characters;
- maximum test line length: `95` characters;
- source-backed count mismatch, short-row, stale-figure-registry, and CLI-output
  failures are covered.

## Updated cumulative schema state

The full claim ledger remains deliberately fail-closed:

- data rows: `26`;
- exact-width rows: `3` (`CL-001`, `CL-007`, `CL-011`);
- width-mismatched rows: `23`;
- schema status: `FLAWED` until every remaining row is reconstructed.

The updated row-width JSON and SVG are authoritative for the cumulative state.

## Scientific boundary

No raw ROOT file, generated pulse table, count, uncertainty, figure, calibration,
simulation, or detector-performance result was regenerated. This unit validates
repository provenance and fixes one malformed ledger row plus its stale figure-registry
links. The other malformed rows remain uninterpretable until source-backed repair.
