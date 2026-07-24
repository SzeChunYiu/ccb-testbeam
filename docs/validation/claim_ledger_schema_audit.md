# Claim-ledger exact-width audit

The canonical ledger contains 26 claim rows and 43 named fields. Field
interpretation is allowed only for rows with exactly 43 CSV columns.

After reconstructing `CL-025` and `CL-026`, the exact current state is:

- exact-width rows: **12/26**;
- withheld malformed rows: **14/26**;
- corrected current-ledger SHA-256:
  `d7231b66b477fffb3766bab68129ab8e4e56f37d3e84630d89bf5016023dfb79`;
- policy: `NO_FIELD_INTERPRETATION_FROM_WIDTH_MISMATCHED_ROWS`.

The cumulative validator intentionally remains `FLAWED` with status 1 until all
14 remaining malformed rows are reconstructed from source-backed evidence. A
`FLAWED` global schema state does not invalidate the 12 exact rows; it prevents
interpretation of the malformed rows.

This is repository schema/provenance evidence. It does not validate any detector
measurement, simulation, calibration, or physics conclusion by itself.
