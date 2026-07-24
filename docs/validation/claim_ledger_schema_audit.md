# Claim-ledger exact-width audit

The canonical ledger contains 26 claim rows and 43 named fields. Field
interpretation is allowed only for rows with exactly 43 CSV columns.

After reconstructing `CL-013` and `CL-014`, the exact current state is:

- exact-width rows: **14/26**;
- withheld malformed rows: **12/26**;
- corrected current-ledger SHA-256:
  `30a1f5fd03d82366df3201a9d0d37be54572f13fd6c990d92b6bd5a9feab69a5`;
- policy: `NO_FIELD_INTERPRETATION_FROM_WIDTH_MISMATCHED_ROWS`.

The cumulative validator intentionally remains `FLAWED` with status 1 until all
12 remaining malformed rows are reconstructed from source-backed evidence. A
`FLAWED` global schema state does not invalidate the 14 exact rows; it prevents
interpretation of the malformed rows.

This is repository schema/provenance evidence. It does not validate any detector
measurement, simulation, calibration, or physics conclusion by itself.
