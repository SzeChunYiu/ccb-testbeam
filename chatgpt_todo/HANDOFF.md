# Latest Handoff

## Session

- **Task:** `AUD-MV3-SEL-002`
- **Stamp:** `2026-07-25T230502Z`
- **Initial remote main:** `feddba9e3cc488fd77e7bc015f80af9d78f6edd1`
- **Validated delivery/handoff commit:** `35f8f6f12cc174be792c17ba56cdbe23e2ebad6b`
- **Remote-main confirmation:** post-write history confirmed the delivery commit as remote `main`
  before this confirmation update.
- **Destination:** direct contents-API commits to `main`; no force-push, history rewrite, task
  branch, or PR transport.
- **Push-output boundary:** GitHub returned successful commit SHAs rather than terminal `git push`
  stdout. Recent remote history was re-read after the focused sequence.
- **Acceptance:** producer contract and source-report quarantine `VALIDATED/PARTIAL`; production
  weighted result `BLOCKED`; canonical `CL-021` remains `FLAWED`.

## Review and finding

Reviewed the former producer, retained summary and report, prior MV3 audit/evidence, canonical PDG
charge helper, claim ledger state, recent main history, PR inventory, PR #868, and commit status.
The former producer read `PrimaryWeight` but did not apply it, silently substituted 1.0 for invalid
weights, selected only positive charge, and reported an improvement that changed the data target.
Its source report then called the residual shape matched despite chi-square/ndf
`5590.089500522007`, B2 residual `7.735323559398211` percentage points, and TVD
`0.07735323559398212`.

Holding Sample-I data fixed changes the former improvement from `16.602672795596263x` to
`16.114635239581606x`. These are retained diagnostic calculations, not weighted production results.

## Delivered correction

`scripts/studies/mv3_selection_matched.py` now:

1. requires exactly one finite nonnegative `PrimaryWeight` per event and never substitutes 1.0;
2. uses `ccb_mc_validation.truth.pdg.is_charged` for both charge signs;
3. publishes weighted primary and unweighted sensitivity profiles;
4. records `sum_w`, `sum_w2`, ESS, and zero-weight counts per selection;
5. calculates weighted correlations and weighted entry-energy quantiles;
6. holds Sample-I data fixed for the selection-ablation ratio;
7. records exact input/script SHA-256, full source commit, and generation command;
8. rejects input/output aliasing and publishes JSON atomically;
9. emits a non-authorizing diagnostic verdict with explicit missing covariance and scans.

`reports/studies/mv3_selection_matched/REPORT.md` now classifies the existing JSON/PNG files as
`SUPERSEDED_UNWEIGHTED_OUTPUTS`. They are preserved for provenance but are not accepted physical
closure evidence.

## Validation and visual evidence

Executed on prepared exact files:

```text
python -m py_compile \
  scripts/studies/mv3_selection_matched.py \
  tests/test_mv3_selection_weighted_contract.py \
  tools/audit/render_mv3_selection_weighted_remediation_evidence.py

pytest -q tests/test_mv3_selection_weighted_contract.py
6 passed in 0.04s
```

The exact committed test blob `4f81f85a387ae75ce81627fbb1da22de2fb6cc66` was reconstructed
from the GitHub base64 response and also returned `6 passed in 0.04s` against the prepared producer.
JSON and SVG parsing passed. Prepared Python lines were at most 99 characters.

The synthetic visual uses event weights 1 and 9 and demonstrates the contract distinction:
weighted B2/B8 `0.1/0.9`, unweighted sensitivity `0.5/0.5`, `sum_w=10`, `sum_w2=82`, ESS
`1.2195121951219512`. It is explicitly software/provenance evidence, not detector data.

Evidence paths:

- `docs/validation/mv3_selection_weighted_remediation_validation.json`
- `docs/validation/mv3_selection_weighted_remediation.svg`
- `docs/validation/mv3_selection_weighted_remediation_audit.md`
- `chatgpt_todo/archive/2026-07-25T230502Z_AUD-MV3-SEL-002_WEIGHTED_PRODUCER_REMEDIATION.md`

The runtime could not establish a network checkout or retrieve the remote raw producer bytes.
Exact committed producer-blob pytest is therefore not claimed. Post-write connector inspection
confirmed the delivered contract in Git blob `cd787ab64408228d67536b88bcc617fe32d0ec5a`.

## Direct-main commits before handoff

- `f4436a3d462a0dc533f0a4b70bfd7d2cf9b331ec` — task claim
- `6f8cb36633b4340499229e4029cd8fb6087dcf3c` — producer correction
- `e35c047d47308b4726b8a1da28a4dfc09a25514b` — tests
- `463fea2c516458bff516ed1de49a6d5e5a4d891a` — report quarantine
- `b0c1d0a386e4f717253e6c9ff0142a86c9a744e5` — evidence renderer
- `7db754a9f16f7243698fbfd665d550f863f8e966` — validation JSON
- `84e09864bf15faa9d39fed10e14be7695e40963f` — initial SVG
- `9b87af84ad33bc363d72d9b6313525c4ad9b2f2d` — audit report
- `3a78d88db5d7110d1c461695109f065ac9315cf8` — exact test-blob binding
- `59477eed02405c0391f24ecb930daa011006a657` — synchronized SVG status
- `2bbb2c26c1715bf6a6bfdf4b2822edba3d0394b1` — immutable archive
- `0aa777457fff37a817bce29a7ea1656683210ddf` — active-task completion
- `35f8f6f12cc174be792c17ba56cdbe23e2ebad6b` — validated delivery handoff

No status checks were attached to the initial or current head. PR #868 remains closed, unmerged,
non-mergeable, and untouched.

## Scientific boundary, blockers, and next task

No production ROOT, pulse-table, or event-table file was rerun. No weighted production profile,
covariance, sensitivity scan, material/scattering correction, calibration, PID result, or detector
performance is claimed. `BLK-MV3-LEGACY-001` remains open.

Next: execute the corrected producer from an immutable commit on content-addressed production inputs;
require one validated weight per event, weighted/unweighted outputs, weight sums and ESS, four-bin
covariance, fixed-target metrics, preregistered gain/threshold/coincidence/aggregation scans,
regenerated hashes and figures, then a zero-finding claim audit before any ledger or public upgrade.

`SESSION_LOG.md`, `BACKLOG.md`, `BLOCKERS.md`, `MASTER_INDEX.md`, and aggregate matrices were reviewed
but not replaced because only whole-file replacement was available while complete current contents
were paged or truncated. Partial reconstruction could erase append-only or concurrent provenance.
The immutable archive and this handoff preserve the complete append-equivalent record; mandatory
aggregate synchronization remains unresolved.
