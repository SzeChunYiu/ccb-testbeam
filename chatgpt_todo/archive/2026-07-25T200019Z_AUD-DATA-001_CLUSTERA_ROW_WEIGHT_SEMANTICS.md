# Immutable handoff — AUD-DATA-001 Cluster A row and weight semantics

## Session identity

- Session stamp: `2026-07-25T200019Z`
- Owner: scheduled scientific-review session
- Initial remote `main`: `39378e21c436344b43e9f659f5a76bce2bca1228`
- Concurrent commit: `c39aba2c55091aec501acbe402523e2d94be2c58` merged a separate
  single-stave documentation review during this run. It did not modify the Cluster A files
  reviewed or changed here.
- Task: `AUD-DATA-001`
- Status: focused software remediation `VALIDATED`; cumulative scientific task `PARTIAL`.

## Reviewed area

Reviewed the newly merged Cluster A data-side commit, its script, generated-result summary,
row/event-key descriptions, MC comparison, recent repository history, open PRs, PR #868,
and the repository-local active task and handoff.

The reviewed production script blob was
`ccdc21dd967d0a25694261d488f959d89286a88d`.

## Confirmed defects

1. The numeric parser caught every exception and returned `0.0`, allowing malformed numeric
   cells to become measurements. NaN and infinity were not rejected.
2. The MC path loaded `PrimaryWeight` but plotted an unweighted hexbin. A bin containing
   events with weights 1 and 100 displayed 2 instead of the correct weighted sum 101.
3. The derived data table has 632,939 rows and 385,984 unique
   `(source_file_id, run, evt)` keys. Row-level stopping counts and correlation were described
   using event and stopping-distribution language even though no one-row-per-event composite
   merge had been performed.
4. The input CSV and ROOT identities were not content-addressed in the result metadata.
5. The module executed on import, had no independently testable CLI boundary, and wrote its
   JSON non-atomically.

## Delivered remediation

`scripts/studies/clusterA_data_side.py` now implements policy
`DATA_ROWS_MUST_BE_FINITE_AND_ROW_LEVEL_RESULTS_MUST_NOT_POSE_AS_EVENTS`:

- strict UTF-8 single-read CSV snapshot;
- required-column and strict integer/numeric validation;
- fail-closed NaN and infinity rejection;
- explicit row-level denominators and `event_level_claims_authorized=false`;
- exact CSV and ROOT byte count plus SHA-256 provenance;
- one finite nonnegative `PrimaryWeight` per selected MC event;
- MC hexbin values equal to the sum of `PrimaryWeight` in each bin;
- data figures labelled as row counts and not unique events;
- atomic JSON publication, CLI arguments, and main guard.

`reports/studies/clusterA/SUMMARY.md` now states that the +0.18 correlation and stave counts
are row-level descriptive quantities, not event-level stopping fractions or accepted data/MC
closure. Existing data-side PNGs are marked stale until regenerated with the corrected code.

## Validation

Executed on the exact reconstructed implementation, test, and renderer bytes:

```text
python -m py_compile \
  scripts/studies/clusterA_data_side.py \
  tests/test_clusterA_data_side_contract.py \
  tools/audit/render_clusterA_data_side_semantics_evidence.py

pytest -q tests/test_clusterA_data_side_contract.py
6 passed in 0.31s
```

Additional checks:

- validation JSON parse: PASS;
- SVG XML parse: PASS;
- maximum changed Python line lengths: script 95, tests 89, renderer 89 characters;
- synthetic weight control: former unweighted bin 2, corrected weighted bin 101;
- malformed numeric, NaN, infinity, invalid weight shape/range, and out-of-chunk event index
  fail closed.

## Evidence files

- `tests/test_clusterA_data_side_contract.py`
- `tools/audit/render_clusterA_data_side_semantics_evidence.py`
- `docs/validation/clusterA_data_side_semantics_validation.json`
- `docs/validation/clusterA_data_side_semantics.svg`
- `docs/validation/clusterA_data_side_semantics_audit.md`

The SVG is synthetic software/provenance evidence, not detector data.

## Direct-main sequence before this archive

- `ae015d281a3791894a6098c4127b1dd5d5021a77` — implementation
- `64f20672ae9d9ceba6506b47ac7cd6eaa06a1919` — focused tests
- `37806271b196d0f78401690482612a6cb1841c61` — evidence renderer
- `fd1431a4d0ad2c36b852179d261f136588f8833f` — validation JSON
- `8417ee4eb4aed41b173f8653792f235cc8544409` — SVG evidence
- `ef9d748327c67a773205978cd875c3fd9bbc8c2b` — audit report
- `35fe7d8de23d333e285894678c608dfd4fd7d2c4` — scientific summary correction
- `78b47bd7611277d7597acd71cdc53b297412adbf` — active-task update

GitHub contents writes returned successful direct-main commit SHAs rather than textual
`git push` output. No force-push, history rewrite, task branch, or pull request was used.

## Scientific boundary and blockers

The production derived CSV and Krakow ROOT were unavailable in this execution environment.
No production figure, correlation, stopping distribution, data/MC closure, beam-data PID,
calibration, or detector-performance quantity was regenerated or accepted.

Completion requires immutable input hashes, execution of the corrected row-level path,
review of regenerated outputs, and a separate canonical composite-merge analysis with one
accepted event record per key and preregistered denominators.

Repository-wide pytest/ruff, broad link checking, and GitHub Actions were not run.
`SESSION_LOG.md` and long aggregate ledgers were not replaced because the connector provides
whole-file replacement while complete current bytes are returned in paged/truncated views;
a partial replacement could erase append-only or concurrent provenance. This immutable file
and the latest `HANDOFF.md` preserve the append-equivalent record.
