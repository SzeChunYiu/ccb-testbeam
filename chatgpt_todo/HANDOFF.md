# Latest Scientific-Review Handoff

## Session identity

- **UTC stamp:** `2026-07-24T221537Z`
- **Task:** `AUD-WIKI-001`
- **Unit:** MV3 exact tracked-summary public-WIKI synchronization gate
- **Initial remote `main`:** `e844e779c9c431c6fcfe144b5cc5d856323c7bcf`
- **Validated evidence head:** `cfe88a6216bd069232e7693ed1e383f9a70bd864`
- **Coordination/archive head before handoff:** `7365f0167bbfaf5b4d8896f32882c85475bcdbf5`
- **Destination:** direct sequential commits to remote `main`; no force-push, history rewrite, task branch, or draft PR transport
- **Acceptance:** **PARTIAL** — the validator, regressions, exact candidate replacement contract, machine-readable evidence, visual evidence, and immutable archive are validated; the public root WIKI remains stale on remote `main` and the remediation is not delivered.

## Start-of-run review and concurrency

Authenticated GitHub reads inspected recent `main` history, repository metadata, current root WIKI, exact-width `CL-019`/`CL-020`/`CL-021`, the tracked MV3 summary, previous validator/evidence/handoff, backlog, blockers, active task, session log, and PR #868. No concurrent active task was duplicated. PR #868 remained closed, unmerged, non-mergeable, and untouched.

Initial WIKI/ledger/summary blobs:

- WIKI: `fee0e1a15243904dbeb46254878ade4650a8e1f6`
- claim ledger: `8135794d6f0b22da6b760bf6234bb8e1cae795fb`
- MV3 summary: `2bb4b34e499642dfdf8ceb13e2f6351ff6e5cc6d`

## Confirmed documentation flaw

The tracked summary and canonical ledger contain exact MV3 counts and Pearson arithmetic, but the public WIKI still publishes rounded-only `2.3%`, `22.3%`, and `68,269.4` summaries and says the exact counts/statistic are absent or not reconstructable.

Exact source-backed values:

- selected-data B8: `7051 / 306745 = 0.02298651974767315`;
- thresholded-MC B8: `55619 / 249484 = 0.22293614019335908`;
- Pearson chi-square: `204808.2179684494`;
- ndf: `3`;
- chi-square/ndf: `68269.40598948313`.

Independent reconstruction used MC fractions to form expected data counts and calculated `sum((observed-expected)^2/expected)` over B2/B4/B6/B8. The binary64 result exactly matches the tracked summary.

The exact remote/pre-change WIKI fails the new gate with 12 findings:

- seven `MISSING_EXACT_WIKI_TOKEN` findings;
- five `STALE_MV3_ABSENCE_NARRATIVE` findings.

## Work delivered

Added:

- `tools/audit/validate_wiki_mv3_summary.py` v1.0.0;
- `tools/audit/render_wiki_mv3_summary_evidence.py`;
- `tests/test_validate_wiki_mv3_summary.py`;
- `docs/validation/wiki_mv3_summary_audit.md`;
- `docs/validation/wiki_mv3_summary_validation.json`;
- `docs/validation/wiki_mv3_summary.svg`;
- `chatgpt_todo/archive/2026-07-24T221537Z_AUD-WIKI-001_MV3_PUBLIC_SYNC_GATE.md`.

Updated:

- `chatgpt_todo/ACTIVE_TASK.md`;
- this handoff.

Policy:

`WIKI_MV3_MUST_REPORT_EXACT_TRACKED_SUMMARY_WITH_FLAWED_BOUNDARY`

The validator requires exact-width canonical rows, exact counts/fractions/status/blocker, independently reconstructs Pearson arithmetic, checks exact public tokens, requires the non-acceptance boundary, rejects stale absence narratives, records byte provenance, and returns controlled status 0/1/2.

## Candidate public correction

A complete exact snapshot of `WIKI.md` was patched locally through six exact fail-closed replacements covering:

1. canonical result table;
2. material-budget impact;
3. MV3/PID narrative;
4. validation matrix action;
5. blocking issue wording;
6. GAP-01 wording.

Candidate provenance:

- bytes: `24,023`;
- SHA-256: `89537456afc070e2aa39cd15ac9c91d55526d35f719d85e5fe55b178a2d45fec`;
- validator: `VALIDATED`, zero issues;
- link target sequence: unchanged at 44 targets;
- scientific status retained: `FLAWED` under `BLK-MV3-LEGACY-001`.

The candidate was **not** published to remote `main` in this run.

## Validation commands and results

```text
python -m py_compile \
  tools/audit/validate_wiki_mv3_summary.py \
  tools/audit/render_wiki_mv3_summary_evidence.py \
  tests/test_validate_wiki_mv3_summary.py

PYTHONPATH=. python -m pytest \
  tests/test_validate_wiki_mv3_summary.py -q

5 passed in 0.04s
```

Additional checks:

- candidate direct validation: `VALIDATED`, zero issues;
- exact remote/pre-change negative control: `FLAWED`, 12 findings, exit status 1;
- validation JSON parse: PASS;
- SVG XML parse: PASS;
- link target sequence: unchanged, 44 targets;
- maximum changed Python line lengths: 93, 98, and 93 characters;
- environment: Python `3.13.5`, pytest `9.0.2`, Linux `6.12.13`.

## Transport result

A one-time GitHub Actions transport was staged at `b3d674a1d9b9cb22bac1072b4574e0be6cc6f59f` and retriggered through the contents API at `c9548f1abb8d8de465e618255f0c835987e8141f`. No workflow-generated follow-up commit was observed; a WIKI re-read still returned blob `fee0e1a15243904dbeb46254878ade4650a8e1f6`. The temporary workflow was removed at `d4aa241ac2f56834f4ad6638f8f4406f8edb72a2` rather than left as an unvalidated mutation path.

No claim is made that the public WIKI was synchronized.

## Direct-main commit sequence

- `b3d674a1d9b9cb22bac1072b4574e0be6cc6f59f` — stage validator, renderer, tests, and one-time transport;
- `c9548f1abb8d8de465e618255f0c835987e8141f` — retrigger one-time transport;
- `3e92d81d291daa7cb4f136ace591f54a81505b45` — validation audit;
- `fd18463c58e4479c08ed6713fde3a43cb7049618` — machine-readable validation record;
- `cfe88a6216bd069232e7693ed1e383f9a70bd864` — synthetic visual evidence;
- `d4aa241ac2f56834f4ad6638f8f4406f8edb72a2` — remove non-triggered transport workflow;
- `1963d30c2690d599509f6ecbd9d5538f45864f12` — active task;
- `7365f0167bbfaf5b4d8896f32882c85475bcdbf5` — immutable archive.

The connector returned direct-main commit SHAs rather than conventional textual `git push` stdout. Recent history reads confirmed the sequence on remote `main` before this handoff update.

## Coordination limitation

`SESSION_LOG.md` was not replaced. It is append-only, while the connector exposes whole-file replacement rather than a byte-safe append primitive. Reconstructing the long file manually under concurrent activity could destroy unrelated provenance. The immutable archive and this handoff retain the complete run. This is an unmet coordination requirement and is disclosed explicitly.

`BACKLOG.md`, `BLOCKERS.md`, and aggregate matrices were not replaced because no new task ID or scientific blocker was needed; `AUD-WIKI-001` and `BLK-MV3-LEGACY-001` already cover the open state.

## Scientific boundary

This is documentation/provenance validation. It does not establish:

- correct Geant4 geometry or material model;
- matched trigger or event-selection transfer;
- calibrated gain/response closure;
- covariance-aware inference;
- a meaningful p-value or goodness-of-fit acceptance rule;
- detector/model systematics;
- an accepted B8 correction;
- calibration or detector performance.

The MV3 diagnostic remains `FLAWED` under `BLK-MV3-LEGACY-001`.

## Next exact action

1. Publish the validated 24,023-byte candidate WIKI through a byte-safe complete-file operation.
2. Confirm the exact remote WIKI blob and SHA-256.
3. Run `validate_wiki_mv3_summary.py`, `validate_wiki_claim_front_door.py`, focused pytest, JSON/SVG parsing, and the WIKI internal-link checker against remote-equivalent bytes.
4. Require zero findings and retain `FLAWED`/`BLK-MV3-LEGACY-001` before marking the public synchronization unit validated.
