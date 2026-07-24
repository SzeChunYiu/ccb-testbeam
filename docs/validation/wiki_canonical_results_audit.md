# WIKI canonical-results remediation audit

## Scope

The public canonical-results table was compared against 11 exact-width records in
`docs/claim_ledger.csv`. The pre-remediation WIKI continued to publish values and
status upgrades that the repaired ledger explicitly withholds or gates.

## Confirmed defects

The exact pre-remediation WIKI produced **31 findings**:

- source-absent B6, combined-stave, and covariance values were presented as accepted;
- MV0 was given an unsupported statistical uncertainty and `VALIDATED` status;
- legacy truth-MC PID was upgraded above its `GATED` leakage-risk state;
- the MV3 profile diagnostic was not represented by its canonical `FLAWED` record;
- MV4 toy pulls were presented as detector validation/tension;
- the analytic timing source was labelled as ML;
- the `REVIEW` status and fixed MV6 synthetic-MC PCA values were absent.

## Corrective state

The exact remote WIKI at commit `e215a4cd44ca6ed2eff3ec45921fcc72faa1e115`
now has zero findings under
`WIKI_CANONICAL_RESULTS_MUST_MATCH_EXACT_WIDTH_LEDGER_ROWS` for the bound claims.
It visibly withholds `CL-002`, `CL-004`, and `CL-006`; records MV0, PID, MV3,
and MV4 with their ledger states; identifies the timing verdict as analytic
`REVIEW`; and gives the tracked MV6 synthetic-waveform PCA values of 72.546%
(3 PCs) and 82.188% (8 PCs).

## Exact provenance

- WIKI Git blob: `fee0e1a15243904dbeb46254878ade4650a8e1f6`
- WIKI bytes: `23355`
- WIKI SHA-256: `c0e8c8f7aa0c6b8f024ea9821dcb046b77376aecc95c81301afaf40248417680`
- claim-ledger Git blob: `bb552aa5ed70e7d81dcda888c5aa61402c01e03c`
- claim-ledger bytes: `21486`
- claim-ledger SHA-256: `e7e560a66df43a9cacdf5041361aaffa0995927144adae3701b5c60e0433c26b`
- cumulative ledger schema: `26/26` rows at exactly `43` fields

## Reproducible checks

```text
python -m py_compile \
  tools/audit/validate_wiki_canonical_results.py \
  tests/test_validate_wiki_canonical_results.py \
  tests/test_wiki_claim_front_door_current.py

PYTHONPATH=. python -m pytest \
  tests/test_validate_wiki_canonical_results.py \
  tests/test_wiki_claim_front_door_current.py -q

8 passed in 1.14s
validator before: FLAWED, 31 findings, exit 1
validator after: VALIDATED, 0 findings, exit 0
```

Validation used the exact remote WIKI bytes and exact 43-field binding rows fetched
from current `main`; the repository's cumulative schema evidence separately records
all 26 ledger rows as exact-width.

## Scientific boundary

This is documentation and provenance validation, not detector data. It does not
create a B6 or combined timing resolution, covariance measurement, gain confidence
interval, data PID result, reconstructable MV3 goodness-of-fit statistic, or
beam-data anomaly identification. Claim-specific blockers remain authoritative.

One residual prose item remains: the GAP-01 shorthand still calls the legacy MV3
profile a geometry failure using the unreconstructable reported statistic. A later
focused documentation unit should replace that shorthand with the exact `CL-021`
boundary without changing the validated canonical table.
