# Immutable session record — AUD-WIKI-001 MV3 public synchronization gate

## Identity

- Session stamp: `2026-07-24T221537Z`
- Owner: scheduled scientific-review session
- Initial remote `main`: `e844e779c9c431c6fcfe144b5cc5d856323c7bcf`
- Task: `AUD-WIKI-001`
- Acceptance: **PARTIAL**

## Reviewed

- remote `main` history and divergence;
- root `WIKI.md`;
- `docs/claim_ledger.csv`, especially exact-width `CL-019`, `CL-020`, and `CL-021`;
- `reports/mv3_stopping_v3_1782679272/mv3_summary.json`;
- previous MV3 audit validator, evidence, active task, handoff, backlog, blockers, and session log;
- PR #868 status and current commit-status visibility.

## Confirmed documentation defect

The tracked summary and canonical ledger contain exact MV3 B8 counts and Pearson arithmetic, but the public root WIKI still publishes rounded-only fractions/statistic and says the exact counts/statistic are absent or not reconstructable.

Exact tracked values:

- selected-data B8: `7051/306745 = 0.02298651974767315`;
- thresholded-MC B8: `55619/249484 = 0.22293614019335908`;
- Pearson chi-square: `204808.2179684494`;
- ndf: `3`;
- chi-square/ndf: `68269.40598948313`.

The exact remote/pre-change WIKI snapshot fails the new gate with 12 findings: seven missing exact tokens and five stale absence narratives.

## Work delivered to remote main

Added:

- `tools/audit/validate_wiki_mv3_summary.py` v1.0.0;
- `tools/audit/render_wiki_mv3_summary_evidence.py`;
- `tests/test_validate_wiki_mv3_summary.py`;
- `docs/validation/wiki_mv3_summary_audit.md`;
- `docs/validation/wiki_mv3_summary_validation.json`;
- `docs/validation/wiki_mv3_summary.svg`.

Updated:

- `chatgpt_todo/ACTIVE_TASK.md`.

A temporary one-time workflow transport was staged and retriggered, but no workflow-generated follow-up commit was observed. It was removed from `main`; no persistent automated mutation path was left behind.

Policy:

`WIKI_MV3_MUST_REPORT_EXACT_TRACKED_SUMMARY_WITH_FLAWED_BOUNDARY`

## Candidate public correction

A complete exact WIKI snapshot was patched locally with six fail-closed exact replacements covering the canonical table, material-budget impact, MV3 narrative, validation matrix, blocking issue, and GAP-01. The candidate:

- is `24,023` bytes;
- has SHA-256 `89537456afc070e2aa39cd15ac9c91d55526d35f719d85e5fe55b178a2d45fec`;
- validates with zero issues;
- retains the `FLAWED` status and `BLK-MV3-LEGACY-001`;
- preserves the 44-link Markdown target sequence;
- is not present on remote `main` at the end of this run.

## Exact commands and results

```text
python -m py_compile \
  tools/audit/validate_wiki_mv3_summary.py \
  tools/audit/render_wiki_mv3_summary_evidence.py \
  tests/test_validate_wiki_mv3_summary.py

PYTHONPATH=. python -m pytest \
  tests/test_validate_wiki_mv3_summary.py -q

5 passed in 0.04s
```

Additional validation:

- patched candidate validator: `VALIDATED`, zero issues;
- exact remote/pre-change negative control: status 1, `FLAWED`, 12 findings;
- JSON parse: PASS;
- SVG XML parse: PASS;
- Markdown link-target sequence: unchanged, 44 targets;
- maximum changed Python line lengths: 93, 98, and 93 characters;
- environment: Python `3.13.5`, pytest `9.0.2`, Linux `6.12.13`.

## Direct-main commit sequence before archive

- `b3d674a1d9b9cb22bac1072b4574e0be6cc6f59f` — stage validator, renderer, tests, and transport gate;
- `c9548f1abb8d8de465e618255f0c835987e8141f` — retrigger transport through contents API;
- `3e92d81d291daa7cb4f136ace591f54a81505b45` — validation audit;
- `fd18463c58e4479c08ed6713fde3a43cb7049618` — machine-readable evidence;
- `cfe88a6216bd069232e7693ed1e383f9a70bd864` — visual evidence;
- `d4aa241ac2f56834f4ad6638f8f4406f8edb72a2` — remove non-triggered workflow transport;
- `1963d30c2690d599509f6ecbd9d5538f45864f12` — active-task update.

All writes were fast-forward direct commits to `main`; no force-push or history rewrite occurred.

## Coordination limitation

`SESSION_LOG.md` is append-only, but the connector exposes whole-file replacement rather than an append primitive. Although ranged reads were available, replacing a manually reconstructed long file under concurrent activity risked provenance loss. This archive and the latest handoff therefore retain the complete run. The missing append remains explicitly disclosed; no claim is made that `SESSION_LOG.md` was updated.

## Scientific boundary

No raw data, ROOT output, Geant4 run, detector simulation, uncertainty model, covariance, p-value interpretation, calibration, B8 correction, or detector-performance result was generated. Fixed-source arithmetic is reproducible; scientific stopping-profile closure remains unresolved under `BLK-MV3-LEGACY-001`.

PR #868 remained closed, unmerged, non-mergeable, and untouched. No broad CI success is claimed because no status checks were attached to the resulting commits.

## Next action

Publish the exact candidate WIKI through a byte-safe complete-file operation, rerun the new validator and the existing front-door/link gates against the exact remote bytes, require zero findings, record the final WIKI blob/SHA-256, and only then mark this public synchronization unit validated.
