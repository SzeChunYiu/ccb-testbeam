# Claim-ledger exact-width audit

The canonical ledger contains 26 claim rows and 43 named fields. Field
interpretation is allowed only for rows with exactly 43 CSV columns.

After reconstructing `CL-019`, `CL-020`, and `CL-021`, the exact current state
is:

- exact-width rows: **19/26**;
- withheld malformed rows: **7/26**;
- corrected current-ledger SHA-256:
  `cfdfc8b38e53158fee5cb32a61165d2fc8c2e2370d81580e5f75fe369963fbcb`;
- width histogram: `37:2, 38:3, 39:2, 43:19`;
- remaining malformed rows: `CL-002` through `CL-006`, `CL-008`, and `CL-009`;
- policy: `NO_FIELD_INTERPRETATION_FROM_WIDTH_MISMATCHED_ROWS`.

The cumulative validator intentionally remains `FLAWED` with status 1 until all
seven remaining malformed rows are reconstructed from source-backed evidence.
A `FLAWED` global schema state does not invalidate the 19 exact rows; it
prevents interpretation of the malformed rows.

This is repository schema/provenance evidence. It does not validate any
detector measurement, simulation, calibration, or physics conclusion by itself.
