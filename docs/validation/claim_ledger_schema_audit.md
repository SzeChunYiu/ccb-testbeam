# Claim-ledger exact-width audit

The canonical ledger contains 26 claim rows and 43 named fields. Field
interpretation is allowed only for rows with exactly 43 CSV columns.

After reconstructing `CL-002` through `CL-009`, the exact current state is:

- exact-width rows: **26/26**;
- withheld malformed rows: **0/26**;
- corrected current-ledger SHA-256:
  `e7e560a66df43a9cacdf5041361aaffa0995927144adae3701b5c60e0433c26b`;
- width histogram: `43:26`;
- remaining malformed rows: none;
- policy: `NO_FIELD_INTERPRETATION_FROM_WIDTH_MISMATCHED_ROWS`.

The cumulative validator returns `VALIDATED` with zero issues. This schema
result permits field interpretation; it does not convert `BLOCKED`, `GATED`,
`REVIEW`, `TENSION`, `FLAWED`, or truth-level records into validated physics
claims.

This is repository schema/provenance evidence. It does not validate any
detector measurement, simulation, calibration, or physics conclusion by itself.
