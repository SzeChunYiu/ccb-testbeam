# MV0 gain and KS claim-row reconstruction audit

## Scope

This unit reconstructs `CL-013` and `CL-014` in `docs/claim_ledger.csv` from the
tracked MV0 report and calibration JSON. It repairs field alignment and records
scientific limitations; it does not rerun the calibration.

Policy:

`MV0_CLAIMS_REQUIRE_EXACT_WIDTH_AND_SOURCE_BACKED_LIMITATIONS`

## Confirmed defects

The claim ledger has a canonical 43-column header, but the previous records were
malformed:

- `CL-013` had 38 columns;
- `CL-014` had 37 columns.

Their truth type, status, source paths, confidence-interval state, blocker,
supersession, and notes were therefore withheld by the fail-closed schema policy.
The previous rows also cited non-existent or non-canonical producer/result paths and
presented the gain uncertainty as though it were a statistical-plus-systematic
measurement.

## Exact source evidence

Tracked source files:

- `reports/mv0_calibration_1782677847/REPORT.md`;
- `reports/mv0_calibration_1782677847/calibration.json`;
- `scripts/mv0_calibrate_from_data.py`;
- introducing source commit
  `3c5ff5cf587c8ca9cefda20cb220ba29effd2170`.

The source values are:

| Quantity | Source value |
|---|---:|
| B2 median-matched gain | 92 ADC/MeV |
| Heuristic gain systematic | 30% (rounded to 28 ADC/MeV) |
| B2 data pulses | 579,424 |
| MC tracks with a B2 hit | 321,130 |
| KS statistic at 92 ADC/MeV | 0.1577 |
| KS-optimal scan point | 60 ADC/MeV, D = 0.1188 |
| Previous erroneous v1 gain | 110 ADC/MeV |

The report calls the 30% term a systematic range. It supplies no statistical
uncertainty and no confidence interval. The KS output is a fixed two-sample statistic;
its p-value is not reported, and the report documents unresolved selection and shape
mismatch. The tracked script path also differs from the former ledger path, while no
content-addressed producer/data manifest binds the historical result to exact code and
input bytes.

## Reconstructed records

`CL-013` is now a 43-column `data_mc_calibration_proxy` record. It is `GATED`, not
`VALIDATED`, and records only the source-supported 28 ADC/MeV heuristic systematic
envelope. Statistical, total-uncertainty, and confidence-interval fields are blank. It
is blocked by `BLK-MV0-001` pending exact producer/input provenance, selection closure,
model alternatives, and an accepted uncertainty treatment.

`CL-014` is now a 43-column `data_mc_calibration_proxy` diagnostic with status
`TENSION`. It records D = 0.1577 at the median-matched gain, the KS-optimal D = 0.1188
as a comparator, and their descriptive difference 0.0389. It does not manufacture a
p-value or confidence interval and is not represented as a calibrated goodness-of-fit
probability.

## Validation

Executed against exact local reconstructions of the committed source files:

```text
python -m py_compile \
  tools/audit/validate_mv0_claim_rows.py \
  tests/test_validate_mv0_claim_rows.py

PYTHONPATH=. python -m pytest \
  tests/test_validate_mv0_claim_rows.py -q

5 passed in 0.03s
```

The direct validator returned `VALIDATED` with zero issues. Regression coverage includes
valid exact-width rows, wrong-gain rejection, required-caveat enforcement, 42-column
fail-closed handling, and controlled invalid-UTF-8 input. JSON parsing, SVG XML parsing,
and the repository 100-character Python line convention passed.

After this repair, 14 of 26 claim rows have the exact 43-column contract and 12 remain
malformed and withheld.

## Scientific boundary

This is a source-governance and schema repair. It does not establish a precision gain
calibration, reproduce the historical ROOT/data inputs, validate pulse-selection
transfer, provide a confidence interval, resolve the data/MC shape disagreement, or
produce a detector-performance result. The value 92 ADC/MeV remains a gated
median-matching calibration proxy until `BLK-MV0-001` is resolved.
