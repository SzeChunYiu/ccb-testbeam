# MV6 PCA claim-row reconstruction audit

## Scope

This audit reconstructs claim-ledger records `CL-023` and `CL-024` from the
tracked MV6 synthetic-waveform producer and its fixed JSON summary. It does not
rerun ROOT processing, PCA, waveform simulation, or beam-data analysis.

Policy:

`MV6_PCA_CLAIMS_MUST_MATCH_TRACKED_SYNTHETIC_WAVEFORM_OUTPUT`

## Confirmed defect

The pre-change claim-ledger blob
`e489555f3a520c7cc64b8a7d858a0e93622b9de6` stored both PCA rows with only 37
CSV columns. Their late fields were therefore shifted and withheld by the
43-column schema gate. The same malformed rows published superseded values
`0.89` at three components and `0.997` at eight components while citing a
noncanonical `scripts/mv6_pca.py` / `results.json` source chain.

The tracked source is instead:

- producer: `scripts/mv6_representation_study.py`, blob
  `f965823518b22908f3e8974f280bff5c970368d0`;
- summary: `reports/mv6_representation_1782678362/`
  `mv6_representation_summary.json`, blob
  `26c187cbe05d8dadbe588c6ed9062d25658a80a9`;
- historical report: `reports/mv6_representation_1782678362/REPORT.md`, blob
  `2c531703755b28a0c576e978531b81374edf8ab4`.

The producer subtracts the 350 ADC pedestal, divides each synthetic waveform by
its positive peak, fits ten PCA components, and records cumulative variance at
four and eight components. It uses seed 42 on 87,555 charged B-arm MC tracks
from 220,000 scanned events. These are synthetic detector-response outputs, not
beam-data PCA measurements.

## Independent reconstruction

The summary records the first eight explained-variance ratios as:

```text
0.6397275304111596
0.05803144748933653
0.027701235443287935
0.02005735713674897
0.01943928056747368
0.01915966934733869
0.01891806012034366
0.018849346397427923
```

Using deterministic grouped summation:

```text
cumulative at 3 PCs = 0.7254602133437841
cumulative at 8 PCs = 0.821883926913117
```

The eight-component reconstruction exactly matches the source field
`pca_cumulative_at_8`. The source also records cumulative variance
`0.745517570480533` at four components.

## Delivered claim semantics

Both rows now have exactly 43 columns and are truth-labelled as
`synthetic_waveform_mc` / `TRUTH_LEVEL_MC_ONLY`.

- `CL-023`: three-PC cumulative fraction `0.7254602133437841`, superseding
  `0.89`;
- `CL-024`: eight-PC cumulative fraction `0.821883926913117`, superseding
  `0.997`.

The rows record the source report, producer, summary, producing commit, event
and track counts, and explicitly state that they are fixed synthetic-waveform
outputs rather than beam-data transfer or uncertainty claims. No confidence
interval is invented for a deterministic fixed artifact; scientific model and
transfer uncertainty remain unevaluated.

## Validation

Executed locally:

```text
PYTHONPATH=. python -m py_compile \
  tools/audit/validate_mv6_pca_claim_rows.py \
  tests/test_validate_mv6_pca_claim_rows.py

PYTHONPATH=. python -m pytest \
  tests/test_validate_mv6_pca_claim_rows.py -q

7 passed in 1.41s
```

The focused regression covers valid rows, the superseded values, a 42-column
row, a corrupted summary cumulative, a missing producer normalization contract,
machine-readable JSON/SVG generation, and invalid UTF-8 status-2 handling.

The exact pre-change ledger bytes were reconstructed locally and matched
SHA-256
`9a099f76609c51b7400c8615a46c5e873058ac00e0fa9e3a0e2877a1d5e5db5c`.
The corrected ledger was committed as `bf584eec7d64c6f78cd782b7b1ff84387d0f2bfe` with Git blob
`d33180f144cca10a6e310b3e89b5ab1d065d7e66` and SHA-256
`3a08d0d561de0ad11f2bbbf4a6cc1284af2315e30bbb3ded39be308b6d5125ff`.
The exact source summary reconstruction has SHA-256
`62c574fad724688e1fb9d455aec14ea273d089708c5593a2324e38e3eadc3be4`.

The complete producer was inspected through authenticated GitHub full-file and
ranged reads. Local executable validation used an exact excerpt of the current
PCA/GMM contract because the runtime could not resolve `github.com` for a clone.
This scope distinction is recorded in the machine-readable validation file.

## Visual evidence

`docs/validation/mv6_pca_claim_rows.svg` compares the two superseded fractions
with the source-reconstructed values. It is synthetic software/provenance
evidence, not detector data.

The cumulative schema evidence is refreshed separately: 10 of 26 rows are now
exact-width and 16 remain withheld.

## Scientific boundary

This repair does not validate Chapter 6's current full PCA spectrum, physical
interpretations of individual components, autoencoder comparisons, data/MC
transfer, or detector-response systematics. The academic chapter still contains
values and method claims that do not match the tracked MV6 producer and summary;
that public-document correction remains a separate required unit under
`AUD-ANOM-001` / `AUD-LEDGER-001`.
