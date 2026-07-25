# Latest Handoff — AUD-DATA-001 Cluster A row and weight semantics

## Delivery identity

- **Session stamp:** `2026-07-25T200019Z`
- **Task ID:** `AUD-DATA-001`
- **Initial remote `main`:** `39378e21c436344b43e9f659f5a76bce2bca1228`
- **Concurrent change:** `c39aba2c55091aec501acbe402523e2d94be2c58` merged a
  separate single-stave documentation review during this run. It did not alter the Cluster A
  code, summary, tests, or validation evidence changed here.
- **Validated implementation/evidence/archive head:**
  `2a67f5e3bac9cd7e5bdb45574b489c0cf0389daa`
- **Validated delivery handoff / after-SHA:**
  `ec14003be6b789c5dc3b48bb3d65851cb25bc502`
- **Status checks on delivery handoff:** none attached; no broad CI success is claimed.
- **Destination:** direct GitHub contents-API commits to remote `main`; no force-push,
  history rewrite, task branch, or PR transport.
- **Push-output boundary:** successful commit SHAs were returned rather than conventional
  textual `git push` stdout.

## Reviewed state

Reviewed the new Cluster A data-side merge, its exact source blob, public study summary,
row/event-key semantics, MC comparison, recent history, open pull requests, PR #868, and the
repository-local coordination records. The original script blob was
`ccdc21dd967d0a25694261d488f959d89286a88d`.

The execution container could not access the production derived CSV or Krakow ROOT. Exact
GitHub source bytes were reconstructed locally for focused software tests. No production
result was regenerated.

## Confirmed defects

1. The data parser converted malformed numeric cells to `0.0`; NaN and infinity were not
   rejected.
2. The MC comparison loaded `PrimaryWeight` but plotted an unweighted hexbin. For two events
   with weights 1 and 100 in one bin, the former plot value was 2 instead of 101.
3. The data table contains 632,939 rows but 385,984 unique composite keys. Row-level stave
   counts and correlation were described with event and stopping-distribution language
   without a one-row-per-event composite merge.
4. Input bytes and SHA-256 were absent from the result contract; JSON publication was not
   atomic; importing the module executed the full analysis.

## Delivered remediation

`scripts/studies/clusterA_data_side.py` now follows policy
`DATA_ROWS_MUST_BE_FINITE_AND_ROW_LEVEL_RESULTS_MUST_NOT_POSE_AS_EVENTS`:

- strict UTF-8 single-read CSV input;
- required-column, integer, finite numeric, and nonnegative-weight validation;
- explicit row versus composite-event denominators;
- `event_level_claims_authorized=false` until canonical composite merge;
- exact data and MC byte count plus full SHA-256;
- exact event-index alignment of `PrimaryWeight`;
- `C=PrimaryWeight` and `reduce_C_function=np.sum` for MC hexbin density;
- row-labelled data plots and explicit different-statistical-unit comparison;
- atomic JSON, CLI options, and a main guard.

`reports/studies/clusterA/SUMMARY.md` now states that the published +0.18 correlation and
stave counts are row-level descriptive quantities, not event-level stopping fractions or
accepted data/MC closure. Existing data-side PNGs are marked stale until regenerated.

## Validation

```text
python -m py_compile \
  scripts/studies/clusterA_data_side.py \
  tests/test_clusterA_data_side_contract.py \
  tools/audit/render_clusterA_data_side_semantics_evidence.py

pytest -q tests/test_clusterA_data_side_contract.py
6 passed in 0.31s
```

Additional results:

- malformed numeric, NaN, infinity, invalid weight shape/range, and event-index mismatch
  failed closed;
- exact weight control changed one-bin value from former 2 to correct 101;
- JSON parsing: PASS;
- SVG XML parsing: PASS;
- maximum changed Python line lengths: script 95, tests 89, renderer 89 characters;
- corrected script Git blob: `897024e70ce57474606c3011d85c06310866a173`.

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

The SVG is synthetic software/provenance evidence, not detector data.

## Direct-main sequence

- `ae015d281a3791894a6098c4127b1dd5d5021a77` — implementation
- `64f20672ae9d9ceba6506b47ac7cd6eaa06a1919` — focused tests
- `37806271b196d0f78401690482612a6cb1841c61` — evidence renderer
- `fd1431a4d0ad2c36b852179d261f136588f8833f` — validation JSON
- `8417ee4eb4aed41b173f8653792f235cc8544409` — SVG evidence
- `ef9d748327c67a773205978cd875c3fd9bbc8c2b` — audit report
- `35fe7d8de23d333e285894678c608dfd4fd7d2c4` — summary correction
- `78b47bd7611277d7597acd71cdc53b297412adbf` — active task
- `2a67f5e3bac9cd7e5bdb45574b489c0cf0389daa` — immutable archive
- `ec14003be6b789c5dc3b48bb3d65851cb25bc502` — delivery handoff

## Acceptance boundary and next action

Focused software remediation is `VALIDATED`; cumulative `AUD-DATA-001` is `PARTIAL`.

No production CSV/ROOT execution, production figure, correlation, stopping distribution,
data/MC closure, beam-data PID, calibration, or detector-performance quantity was
regenerated or accepted. The next unit must bind immutable input hashes, rerun the corrected
row-level diagnostic, review regenerated source metadata and figures, then separately run the
canonical composite merge before making event-level statements.

Repository-wide pytest/ruff, broad link checking, and GitHub Actions were not run. PR #868
remains closed, unmerged, and untouched.

`SESSION_LOG.md`, `MASTER_INDEX.md`, `BACKLOG.md`, `BLOCKERS.md`, and aggregate matrices were
not replaced because their complete current bytes are returned through paged/truncated views
while the connector exposes whole-file replacement rather than byte-safe append. Replacing a
partial reconstruction could erase append-only or concurrent provenance. The immutable
archive and this handoff preserve the complete append-equivalent record.
