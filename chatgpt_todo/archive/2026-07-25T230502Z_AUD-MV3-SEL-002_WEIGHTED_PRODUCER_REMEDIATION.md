# AUD-MV3-SEL-002 — weighted producer remediation

- **Session stamp:** `2026-07-25T230502Z`
- **Initial remote main:** `feddba9e3cc488fd77e7bc015f80af9d78f6edd1`
- **Repository:** `SzeChunYiu/ccb-testbeam`
- **Owner:** scheduled scientific-review session
- **Focused acceptance:** prepared-byte software contract `VALIDATED`; source report quarantine
  `COMPLETE`; production weighted result `BLOCKED`; cumulative MV3 closure `PARTIAL`.

## Reviewed evidence

- former producer blob `32c2c9d480aa5bd02ecc6a73ddc4c0654dae21ca`;
- former report blob `7d0608e473bc85df7c1e5a8f2010ba01074d8ba8`;
- retained historical summary blob `bb659df56eacf6c7a9f0d3f56df3cf31043019ba`;
- canonical signed-charge helper blob `8c484b131ec07f3af2e2bd4726b83cd64601190c`;
- prior fail-closed audit and focused evidence;
- current claim ledger state `CL-021 = FLAWED`, blocked by `BLK-MV3-LEGACY-001`;
- PR #868 metadata: closed, unmerged, non-mergeable, untouched;
- current-main combined status: no attached status checks.

## Confirmed defects remediated

The former producer loaded `PrimaryWeight`, defaulted missing/nonfinite values to `1.0`, and never
used the weights in its profiles. It selected only positive charges and advertised an improvement
that changed the data target. The report then described a rejected residual as a shape match.

The corrected producer:

1. requires exactly one finite nonnegative event weight;
2. uses canonical `is_charged` for both signs;
3. publishes weighted primary and unweighted sensitivity profiles;
4. records `sum_w`, `sum_w2`, ESS, and zero-weight counts per selection;
5. computes weighted correlations and weighted entry-energy quantiles;
6. holds Sample-I data fixed for the selection ablation;
7. records full source/input SHA-256 and the generation command;
8. writes JSON atomically and rejects output/input aliases;
9. keeps the run non-authorizing unless strict residual/goodness-of-fit gates pass.

The report marks the old JSON/PNGs as `SUPERSEDED_UNWEIGHTED_OUTPUTS`. It preserves the former
values solely as diagnostics: MC/data Sample-I B2 `0.8669236675912432/0.9442769031852253`,
chi-square/ndf `5590.089500522007`, B2 residual `7.735323559398211` percentage points, TVD
`0.07735323559398212`, reported target-changing improvement `16.602672795596263x`, and controlled
same-target improvement `16.114635239581606x`.

## Validation

Prepared exact files were compiled and the focused tests executed:

```text
python -m py_compile \
  scripts/studies/mv3_selection_matched.py \
  tests/test_mv3_selection_weighted_contract.py \
  tools/audit/render_mv3_selection_weighted_remediation_evidence.py

pytest -q tests/test_mv3_selection_weighted_contract.py
6 passed in 0.04s
```

The exact committed test blob `4f81f85a387ae75ce81627fbb1da22de2fb6cc66` was reconstructed
from its GitHub base64 response and executed against the prepared producer: `6 passed in 0.04s`.
JSON and SVG parsing passed; prepared Python lines were at most 99 characters. The synthetic control
uses weights 1 and 9, giving weighted B2/B8 `0.1/0.9`, unweighted sensitivity `0.5/0.5`,
`sum_w=10`, `sum_w2=82`, and ESS `100/82 = 1.2195121951219512`.

The runtime could not establish a network checkout or retrieve the remote raw producer bytes.
Therefore exact committed producer-blob pytest is not claimed. Post-write connector inspection
confirmed the policy, weight gate, canonical charge helper, weighted sufficient statistics,
same-target metric, provenance, and atomic publication code in remote blob
`cd787ab64408228d67536b88bcc617fe32d0ec5a`.

## Direct-main commits through validation evidence

- `f4436a3d462a0dc533f0a4b70bfd7d2cf9b331ec` — active-task claim
- `6f8cb36633b4340499229e4029cd8fb6087dcf3c` — producer correction
- `e35c047d47308b4726b8a1da28a4dfc09a25514b` — focused tests
- `463fea2c516458bff516ed1de49a6d5e5a4d891a` — source-report quarantine
- `b0c1d0a386e4f717253e6c9ff0142a86c9a744e5` — evidence renderer
- `7db754a9f16f7243698fbfd665d550f863f8e966` — initial validation record
- `84e09864bf15faa9d39fed10e14be7695e40963f` — initial visual evidence
- `9b87af84ad33bc363d72d9b6313525c4ad9b2f2d` — audit report
- `3a78d88db5d7110d1c461695109f065ac9315cf8` — exact test-blob binding
- `59477eed02405c0391f24ecb930daa011006a657` — synchronized visual status

GitHub returned direct-main commit SHAs rather than terminal `git push` stdout. Remote history was
re-read after publication and showed the focused sequence consecutively on `main`; no force-push,
history rewrite, task branch, or PR transport was used.

## Scientific boundary and next action

No production ROOT, pulse-table, or event-table bytes were rerun. No weighted production profile,
covariance, gain/threshold/coincidence scan, material/scattering ablation, calibration, PID result,
or detector-performance result was produced. Canonical `CL-021` remains `FLAWED`.

Next: execute the corrected producer from an immutable commit against content-addressed production
inputs; require one validated weight per event, weighted/unweighted outputs, weight sums and ESS,
four-bin covariance, fixed-target metrics, preregistered scans, regenerated hashes/plots, and a
zero-finding claim audit before reviewing any canonical or public claim upgrade.

`SESSION_LOG.md` and the large aggregate ledgers were not replaced because the connector only
supports whole-file replacement while complete current bytes were available through paged/truncated
views. Reconstructing them partially could erase append-only or concurrent provenance. This archive
and the latest handoff preserve the append-equivalent record; the synchronization gap remains open.
