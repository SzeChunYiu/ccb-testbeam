# Latest Handoff — AUD-DATA-001 Cluster A row and weight semantics

## Delivery identity

- **Session stamp:** `2026-07-25T200019Z`
- **Task ID:** `AUD-DATA-001`
- **Initial remote `main`:** `39378e21c436344b43e9f659f5a76bce2bca1228`
- **Concurrent non-overlapping merge:**
  `c39aba2c55091aec501acbe402523e2d94be2c58`
- **Later concurrent data-side merge:**
  `f283e61fd64b0826215251c92c9495428476a808` added a separate raw-beam event-level
  study while this remediation was being finalized. It did not modify the corrected Cluster A
  script. Its Rmax/claim-ledger upgrades were not accepted by this focused unit.
- **Validated code, tests, evidence, archive, and summary / after-SHA:**
  `34a2677132aec6bead99059b76c3e233b5d6aa9c`
- **Destination:** direct GitHub contents-API commits to remote `main`; no force-push,
  history rewrite, task branch, or PR transport.
- **Push-output boundary:** successful commit SHAs were returned rather than conventional
  textual `git push` stdout.

## Reviewed state

Reviewed the newly merged Cluster A data-side script, its source blob, study summary,
row/event-key semantics, MC plot weighting, repository history, open PRs, PR #868, and
coordination files. The reviewed former script blob was
`ccdc21dd967d0a25694261d488f959d89286a88d`.

The production derived CSV and Krakow ROOT were unavailable in this execution environment.
Exact source bytes were reconstructed for focused software validation. No production result
or figure was regenerated.

The later raw-beam study reports a distinct one-row-per-event B2/B4 sample and therefore does
not authorize reinterpreting the audited multi-row derived table as event-level. Its report
uses `Rmax = 0.38 / 130 ns` while describing the result as occupancy-grounded; the numerator
and live-time are still model/convention inputs. That adjacent claim needs a separate
source-bound estimand and uncertainty audit before acceptance.

## Confirmed defects

1. Malformed numeric cells were converted to zero, and NaN/infinity were not rejected.
2. `PrimaryWeight` was loaded but ignored in the MC hexbin. Two events with weights 1 and
   100 yielded a plotted bin value of 2 instead of the correct weighted sum 101.
3. The data table contains 632,939 rows and 385,984 composite keys. Row-level stave counts
   and correlation were presented with event/stopping-distribution language without the
   canonical one-row-per-event composite merge.
4. Input identities were not content-addressed; JSON publication was non-atomic; importing
   the module executed the analysis.
5. An empty positive-ΔE/E selection could emit undefined medians rather than fail closed.

## Delivered remediation

`scripts/studies/clusterA_data_side.py` now enforces policy
`DATA_ROWS_MUST_BE_FINITE_AND_ROW_LEVEL_RESULTS_MUST_NOT_POSE_AS_EVENTS`:

- strict UTF-8 single-read CSV snapshot;
- required-column, integer, finite-numeric, and selected-sample validation;
- explicit row and composite-key denominators;
- `event_level_claims_authorized=false` pending canonical composite merge;
- exact CSV/ROOT byte count and full SHA-256;
- finite nonnegative `PrimaryWeight` aligned by absolute event index;
- rejection of a selected MC weight vector with no positive weight;
- MC bins equal to summed `PrimaryWeight`;
- row-labelled data plots and explicit statistical-unit mismatch;
- atomic JSON, CLI options, and a main guard.

`reports/studies/clusterA/SUMMARY.md` now classifies the +0.18 correlation and stave counts as
row-level descriptive quantities, not event-level stopping fractions or accepted data/MC
closure. Existing Cluster A data-side PNGs are marked stale until regenerated. The summary
also distinguishes the later raw-beam event-level study and withholds acceptance of its Rmax
upgrade pending a separate estimand audit.

## Validation

```text
python -m py_compile \
  scripts/studies/clusterA_data_side.py \
  tests/test_clusterA_data_side_contract.py \
  tools/audit/render_clusterA_data_side_semantics_evidence.py

pytest -q tests/test_clusterA_data_side_contract.py
7 passed in 0.36s
```

Additional checks:

- malformed numeric, NaN, infinity, empty selected data, invalid weight shape/range, and
  event-index mismatch fail closed;
- synthetic weight control: former bin 2, corrected bin 101;
- JSON parse: PASS;
- SVG XML parse: PASS;
- maximum changed Python line length: 96 characters;
- validated script blob: `8bda06c55dc00c1af3e025411fcc55df43f1487e`;
- validated test blob: `21d3c9ecdd2f9837cd8776adc69fccf5a9a11b63`.

## Delivered files

Updated:

- `scripts/studies/clusterA_data_side.py`
- `reports/studies/clusterA/SUMMARY.md`
- `chatgpt_todo/ACTIVE_TASK.md`
- `chatgpt_todo/HANDOFF.md`

Added:

- `tests/test_clusterA_data_side_contract.py`
- `tools/audit/render_clusterA_data_side_semantics_evidence.py`
- `docs/validation/clusterA_data_side_semantics_validation.json`
- `docs/validation/clusterA_data_side_semantics.svg`
- `docs/validation/clusterA_data_side_semantics_audit.md`
- `chatgpt_todo/archive/2026-07-25T200019Z_AUD-DATA-001_CLUSTERA_ROW_WEIGHT_SEMANTICS.md`
- `chatgpt_todo/archive/2026-07-25T200019Z_AUD-DATA-001_CLUSTERA_ROW_WEIGHT_SEMANTICS_FINAL.md`

The SVG is synthetic software/provenance evidence, not detector data.

## Direct-main sequence

- `ae015d281a3791894a6098c4127b1dd5d5021a77` — initial implementation
- `64f20672ae9d9ceba6506b47ac7cd6eaa06a1919` — initial focused tests
- `37806271b196d0f78401690482612a6cb1841c61` — renderer
- `fd1431a4d0ad2c36b852179d261f136588f8833f` — initial JSON evidence
- `8417ee4eb4aed41b173f8653792f235cc8544409` — SVG evidence
- `ef9d748327c67a773205978cd875c3fd9bbc8c2b` — initial audit report
- `35fe7d8de23d333e285894678c608dfd4fd7d2c4` — initial summary correction
- `78b47bd7611277d7597acd71cdc53b297412adbf` — initial active task
- `2a67f5e3bac9cd7e5bdb45574b489c0cf0389daa` — preliminary archive
- `ec14003be6b789c5dc3b48bb3d65851cb25bc502` — preliminary handoff
- `ad8584fcd6479025a6eff96dc7cf2bc662dc5122` — preliminary confirmation
- `22b0b5bf610bae8eab496d2b7b618d2884c28408` — empty-sample/positive-weight gate
- `6034f47a5acad6a3eacc278e3408e6c9abfb9e98` — final regression
- `e6c457bb322fe59013d13f3c073f036509d84849` — final JSON evidence
- `ec1ca0827e2dfe4620f66b53c11411960caec832` — final audit report
- `a26a3cc257e2b34ab16684ee07c64acedfd40137` — final active task
- `6ce94adeb54c521f03a2b4f84b5a985e1ddff7f7` — final immutable archive
- `0db10040dc53bfc235233a03163a40ee74f5053c` — first final handoff
- `8094baa6e59aeac4787fff36cbf6d95d27c5793b` — concurrent-publication reconciliation
- `34a2677132aec6bead99059b76c3e233b5d6aa9c` — final summary synchronization

## Acceptance boundary and next action

Focused software remediation is `VALIDATED`; cumulative `AUD-DATA-001` is `PARTIAL`.

No production execution of the corrected Cluster A path, regenerated Cluster A figure,
correlation, stopping distribution, data/MC closure, beam-data PID, calibration, or detector-
performance quantity was accepted. The next unit must bind immutable input hashes, rerun the
corrected row-level path, review regenerated metadata and figures, and separately execute the
canonical composite merge before making event-level statements.

The concurrent raw-beam study should be audited separately before retaining its CL-010
upgrade: distinguish measured occupancy from the assumed `mu_max=0.38` and live-time model,
recompute with the exact CL-011 estimand where applicable, define uncertainty and correlation,
and do not label a derived convention as an absolute data measurement.

Repository-wide pytest/ruff, broad link checking, and GitHub Actions were not run. No status
checks were attached to the delivery commits. PR #868 remains closed, unmerged, and untouched.

`SESSION_LOG.md`, `MASTER_INDEX.md`, `BACKLOG.md`, `BLOCKERS.md`, and aggregate matrices were
not replaced because complete current bytes are returned through paged/truncated views while
the connector lacks byte-safe append. Replacing a partial reconstruction could erase
append-only or concurrent provenance. The immutable archives and this handoff preserve the
complete append-equivalent record.
