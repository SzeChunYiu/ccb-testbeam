# Immutable handoff — AUD-WIKI-003 public remediation

## Session identity

- UTC stamp: `2026-07-25T000907Z`
- Owner: scheduled scientific-review session
- Initial remote `main`: `94eb6705c5db6d10793532b6b2607b855806298b`
- Destination: direct sequential commits to remote `main`
- Acceptance: `COMPLETE` for root-WIKI MV3 public remediation

## Start-of-run state

The immediately preceding audit had delivered a fail-closed section-binding validator but left the exact root WIKI intentionally unmodified. The former WIKI blob was `fee0e1a15243904dbeb46254878ade4650a8e1f6` and had seven location-bound findings.

The run inspected repository metadata, recent main history, open pull requests, the coordination protocol, active task, latest handoff, backlog, exact WIKI, exact-width `CL-019`/`CL-020`/`CL-021`, tracked MV3 summary, both MV3 WIKI validators, and prior evidence. PR #868 was not modified.

## Exact scientific inputs

Tracked fixed-source evidence:

- selected-data B8: `7051/306745 = 0.02298651974767315`;
- thresholded-MC B8: `55619/249484 = 0.22293614019335908`;
- Pearson chi-square: `204808.2179684494`;
- degrees of freedom: `3`;
- chi-square/ndf: `68269.40598948313`;
- status: `FLAWED`;
- blocker: `BLK-MV3-LEGACY-001`.

The values are reproducible from tracked counts. They are not an accepted stopping-profile closure or calibrated goodness-of-fit result.

## Public correction

The corrected WIKI blob is `91e82c59a2b59b285c6a529c0637ed665be2c4fd`, created by commit `a38f8cf5b2abb6f363a7bd2c0c6bed6828229720`.

Exact evidence and the non-authorizing boundary are now bound to:

1. canonical results table;
2. material-budget impact row;
3. particle-identification MV3 section;
4. MC-validation matrix;
5. MC blocking-issue statement;
6. GAP-01 row.

The WIKI explicitly retains unresolved geometry, trigger and selection transfer, gain response, covariance, p-value interpretation, detector/model systematics, and B8 acceptance correction.

## Regression and evidence

Added:

- `tests/test_wiki_mv3_public_remediation.py`;
- `tools/audit/render_wiki_mv3_public_remediation.py`;
- `docs/validation/wiki_mv3_public_remediation_validation.json`;
- `docs/validation/wiki_mv3_public_remediation.svg`;
- `docs/validation/wiki_mv3_public_remediation_audit.md`.

Focused reconstructed validation:

```text
python -m py_compile \
  tools/audit/validate_wiki_mv3_section_binding.py \
  tools/audit/validate_wiki_mv3_summary.py \
  tests/test_wiki_mv3_public_remediation.py

PYTHONPATH=. python -m pytest \
  tests/test_wiki_mv3_public_remediation.py -q

2 passed in 0.02s
```

The validation fixture matched the six committed public-use sites and used exact ledger/summary arithmetic. Both validator contracts returned `VALIDATED` with zero issues. A rounded canonical-row mutation failed closed. JSON and SVG parsing passed locally.

The GitHub connector does not expose a repository command runner. No full-checkout execution, repository-wide pytest/ruff, broken-link run, ROOT/Geant4 processing, or GitHub Actions success is claimed. No status checks or workflow runs were attached to the focused test commit when inspected.

## Commit sequence before final handoff

- `a38f8cf5b2abb6f363a7bd2c0c6bed6828229720` — bind exact MV3 evidence to root-WIKI sections;
- `eb030003d96ed1e6a589ec03e4e2fdaa6c57d718` — exact-current integration and fail-closed regression;
- `44345931360fe8a1d21693a334e6058249608dd0` — deterministic SVG renderer;
- `251e59462dfcb2af18d8a2b518ac1f8442d90768` — machine-readable validation record;
- `115e2e4745050cd28a12892a5bfc0dcbfb4d7b23` — visual evidence;
- `96f43cff4636837a8df92349467d2eec6aa6a996` — audit report;
- `84d0bc52a66b10f115c4956e0db499a4fc060bc0` — active-task completion.

## Coordination limitation

`SESSION_LOG.md`, `BACKLOG.md`, `BLOCKERS.md`, and aggregate matrices were not replaced. The connector provides complete-file replacement rather than byte-safe append/patch semantics for these shared records. Replacing a partially reconstructed or concurrently updated file could erase unrelated provenance. This immutable archive and `HANDOFF.md` preserve the complete append-equivalent record.

## Next scientific action

Do not infer B8 acceptance closure from the exact legacy statistic. A strict MV3 rerun must establish geometry/material configuration, trigger and event-selection transfer, gain/threshold response, covariance and uncertainty treatment, detector/model systematic scans, and a preregistered goodness-of-fit interpretation.
