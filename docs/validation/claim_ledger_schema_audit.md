# Claim-ledger exact-width audit

The canonical ledger contains 26 claim rows and 43 named fields. Field
interpretation is allowed only for rows with exactly 43 CSV columns.

After reconstructing `CL-017` and `CL-018`, the exact current state is:

- exact-width rows: **16/26**;
- withheld malformed rows: **10/26**;
- corrected current-ledger SHA-256:
  `e607d042b7f6c6d1a62bf8fddb3c42e20e1e6429dc38a366696062330fb8eeb7`;
- width histogram: `36:1, 37:2, 38:5, 39:2, 43:16`;
- policy: `NO_FIELD_INTERPRETATION_FROM_WIDTH_MISMATCHED_ROWS`.

The cumulative validator intentionally remains `FLAWED` with status 1 until all
10 remaining malformed rows are reconstructed from source-backed evidence. A
`FLAWED` global schema state does not invalidate the 16 exact rows; it prevents
interpretation of the malformed rows.

This is repository schema/provenance evidence. It does not validate any detector
measurement, simulation, calibration, or physics conclusion by itself.
