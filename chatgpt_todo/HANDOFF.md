# Latest Scientific-Review Handoff

## Session identity

- **UTC stamp:** `2026-07-25T000907Z`
- **Task:** `AUD-WIKI-003`
- **Unit:** root-WIKI MV3 public remediation
- **Initial remote `main`:** `94eb6705c5db6d10793532b6b2607b855806298b`
- **Validated implementation/evidence head:** `7887d03bb1913cb05e493b9046cb0fc47f5f7fca`
- **Complete delivery handoff:** `046f5588677a877d7e129b18a9776031af3819c4` was confirmed as remote `main` head; this update records confirmation metadata only
- **Destination:** direct sequential commits to remote `main`; no force-push, history rewrite, task branch, or PR transport
- **Acceptance:** **COMPLETE** for the public-WIKI remediation unit; MV3 physics closure remains open

## Start-of-run review

Authenticated GitHub reads inspected repository metadata, recent `main` history, open pull requests, repository permissions, the coordination protocol, previous active task and handoff, backlog, the exact root `WIKI.md`, exact-width canonical rows `CL-019`/`CL-020`/`CL-021`, the tracked MV3 summary, both existing MV3 WIKI validators, and prior validation artifacts.

Initial source state:

- remote `main`: `94eb6705c5db6d10793532b6b2607b855806298b`;
- former WIKI blob: `fee0e1a15243904dbeb46254878ade4650a8e1f6`;
- claim-ledger blob: `8135794d6f0b22da6b760bf6234bb8e1cae795fb`;
- MV3-summary blob: `2bb4b34e499642dfdf8ceb13e2f6351ff6e5cc6d`.

PR #868 was not modified. The concurrent G4-02 benchmark commit at the initial head was preserved.

## Exact scientific source result

The tracked summary and canonical ledger bind:

- selected-data B8: `7051/306745 = 0.02298651974767315`;
- thresholded-MC B8: `55619/249484 = 0.22293614019335908`;
- Pearson chi-square: `204808.2179684494`;
- ndf: `3`;
- chi-square/ndf: `68269.40598948313`;
- claim status: `FLAWED` under `BLK-MV3-LEGACY-001`.

These are reproducible fixed-source quantities. They are not an accepted stopping-profile closure, calibrated p-value, or B8 acceptance correction.

## Former public defect

The former root WIKI had seven location-bound findings:

- `CANONICAL_ROW_MISMATCH`;
- `CANONICAL_ROW_ROUNDED_ONLY`;
- `MATERIAL_IMPACT_MISMATCH`;
- `PID_SECTION_MISMATCH`;
- `VALIDATION_MATRIX_MISMATCH`;
- `BLOCKING_ISSUE_MISMATCH`;
- `GAP01_MISMATCH`.

It published rounded `2.3%`, `22.3%`, and `68269.4` values and stale absence wording even though the tracked summary contains the exact counts and statistic components.

## Work delivered

Commit `a38f8cf5b2abb6f363a7bd2c0c6bed6828229720` updated `WIKI.md` and produced blob `91e82c59a2b59b285c6a529c0637ed665be2c4fd`.

Exact evidence and the non-authorizing boundary are now bound to:

1. canonical results table;
2. experimental-setup material-impact row;
3. particle-identification MV3 section;
4. MC-validation matrix;
5. MC blocking-issue statement;
6. GAP-01 row.

Added:

- `tests/test_wiki_mv3_public_remediation.py`;
- `tools/audit/render_wiki_mv3_public_remediation.py`;
- `docs/validation/wiki_mv3_public_remediation_validation.json`;
- `docs/validation/wiki_mv3_public_remediation.svg`;
- `docs/validation/wiki_mv3_public_remediation_audit.md`;
- `chatgpt_todo/archive/2026-07-25T000907Z_AUD-WIKI-003_PUBLIC_REMEDIATION.md`.

Updated `chatgpt_todo/ACTIVE_TASK.md` and this handoff.

Policy:

`WIKI_MV3_EXACT_VALUES_MUST_BE_BOUND_TO_CANONICAL_SECTIONS`

## Validation

Focused reconstructed validation command:

```text
python -m py_compile \
  tools/audit/validate_wiki_mv3_section_binding.py \
  tools/audit/validate_wiki_mv3_summary.py \
  tests/test_wiki_mv3_public_remediation.py

PYTHONPATH=. python -m pytest \
  tests/test_wiki_mv3_public_remediation.py -q

2 passed in 0.02s
```

Validated contract results:

- section-binding validator: `VALIDATED`, zero findings;
- exact-summary/ledger validator: `VALIDATED`, zero findings;
- rounded canonical-row mutation: `FLAWED` with the two expected canonical-row findings;
- validation JSON parse: PASS;
- SVG XML parse: PASS;
- visual evidence explicitly labelled documentation/provenance evidence, not detector data.

The fixture matched the six committed public-use sites and exact ledger/summary arithmetic. The GitHub connector does not provide a repository checkout or command runner, so no claim is made that the command executed against a full post-publication clone.

No status checks or workflow runs were attached to the focused test commit when inspected. No repository-wide pytest, ruff, broken-link run, ROOT processing, Geant4 execution, detector-data regeneration, or simulation regeneration is claimed.

## Direct-main commit sequence

- `a38f8cf5b2abb6f363a7bd2c0c6bed6828229720` — exact public WIKI correction;
- `eb030003d96ed1e6a589ec03e4e2fdaa6c57d718` — integration and fail-closed mutation regression;
- `44345931360fe8a1d21693a334e6058249608dd0` — deterministic evidence renderer;
- `251e59462dfcb2af18d8a2b518ac1f8442d90768` — machine-readable validation record;
- `115e2e4745050cd28a12892a5bfc0dcbfb4d7b23` — visual evidence;
- `96f43cff4636837a8df92349467d2eec6aa6a996` — validation audit;
- `84d0bc52a66b10f115c4956e0db499a4fc060bc0` — active-task completion;
- `7887d03bb1913cb05e493b9046cb0fc47f5f7fca` — immutable archive;
- `046f5588677a877d7e129b18a9776031af3819c4` — complete delivery handoff, confirmed on remote `main`.

The GitHub contents connector returned successful commit SHAs instead of conventional textual `git push` stdout. Post-write history confirmed the complete sequence on remote `main`.

## Scientific boundary

The exact legacy statistic remains non-authorizing. No geometry/material closure, trigger and selection transfer, gain/threshold response, covariance or accepted uncertainty model, p-value calibration, detector/model systematic scan, or B8 acceptance correction was established. `BLK-MV3-LEGACY-001` remains open.

## Coordination limitation

`SESSION_LOG.md`, `BACKLOG.md`, `BLOCKERS.md`, and aggregate matrices were not replaced. The connector exposes complete-file replacement rather than byte-safe append/patch semantics for these shared long-lived records. Replacing a partially reconstructed or concurrently changed file could erase unrelated provenance. The immutable archive and this handoff preserve the complete append-equivalent record. This remains an explicitly unmet aggregate-synchronization requirement.

## Next scientific action

Run a strict MV3 closure study with immutable producer/config/input provenance, fixed geometry and material configuration, trigger/selection-transfer validation, gain and threshold scans, covariance-aware uncertainty, detector/model systematic ensembles, and a preregistered goodness-of-fit interpretation. Do not use the exact legacy statistic as an acceptance correction.
