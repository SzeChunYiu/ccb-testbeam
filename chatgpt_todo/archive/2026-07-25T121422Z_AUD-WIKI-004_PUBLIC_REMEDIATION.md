# AUD-WIKI-004 — Root-WIKI S10b public remediation

## Session identity

- UTC stamp: `2026-07-25T121422Z`
- owner: scheduled scientific-review session
- initial remote `main`: `0e32bf3f5956162d30259489d6d99295280e06fb`
- core remediation: `0e32bf3f5956162d30259489d6d99295280e06fb`
- destination: direct commits to remote `main`; no force-push, branch transport,
  pull request, or history rewrite
- acceptance: `AUD-WIKI-004` COMPLETE as a focused public-documentation and
  provenance unit

## Reviewed repository state

The run inspected current `main`, recent history, repository permissions, open
PRs, closed PR #868, `WIKI.md`, exact-width `CL-011`, Chapter 5, the new
integration regression, the prior WIKI binding validator, `ACTIVE_TASK.md`,
`HANDOFF.md`, `BACKLOG.md`, and the current session log.

PR #868 remained closed, unmerged, and non-mergeable and was not modified.
The core remediation commit had no attached status checks.

## Exact claim contract

The public WIKI now binds S10b run-average 10% template live-time relative to
CFD20 to:

- `124.79018394263471 ns`;
- run-bootstrap 95% interval
  `[123.33094981246663, 126.35875117626817] ns`;
- 14 runs and 252266 selected pulses;
- `data_measurement` / `DONE_DATA_ONLY`;
- blocker `BLK-S10B-001`;
- no separate statistical, systematic, or total uncertainty components.

The pile-up section states that the estimand is threshold-, selection-, and
run-weighting-specific, not a detector-wide universal dead time, and that MV5
reuses it as an input rather than independently validating it.

## Exact remote identities

- WIKI blob: `001e091f82756f45339fe5e48256a951b6331295`
- claim-ledger blob: `254dc5b64945260193d6b1bd4146bd6400ad28cf`
- integration-test blob: `fb049a100501d5091f85daab7d4cd715a9107586`
- Chapter 5 blob: `02a9ba538b1627e1ef3cda78594a4f08446fbffe`

## Independent validation

The execution container could not resolve `github.com`, so a full clone was not
available. Exact GitHub-fetched section snapshots were validated independently:

```text
python -m py_compile \
  tests/test_wiki_tau_eff_public_remediation.py \
  tools/validate_remediation_snapshot.py

python tools/validate_remediation_snapshot.py

VALIDATED
issues: 0
```

The exact integration-test source compiled. Snapshot hashes and all checks are
recorded in
`docs/validation/wiki_tau_eff_public_remediation_validation.json`.
The SVG evidence parsed as XML.

Checks not run: repository-wide pytest, exact three-validator integration pytest
in a complete checkout, repository-wide broken-link inventory, ruff, GitHub
Actions, ROOT reprocessing, and waveform fitting.

## Files delivered in this continuation

- `docs/validation/wiki_tau_eff_public_remediation_audit.md`
- `docs/validation/wiki_tau_eff_public_remediation_validation.json`
- `docs/validation/wiki_tau_eff_public_remediation.svg`
- `chatgpt_todo/ACTIVE_TASK.md`
- this immutable archive
- latest `chatgpt_todo/HANDOFF.md`

## Direct-main sequence before final handoff

- `0eb523905aecea718b752c5aba9959b068cadf2f` — audit report
- `0105418655613486b7c74fe072847852f936986b` — machine-readable evidence
- `cd535220b5eba5b805711413aea6d5a2a4dab342` — visual evidence
- `e4ed90b2befad8a8b44d17014827f0dfc4c11674` — active-task completion

## Scientific boundary

This is documentation/provenance validation. It does not establish a universal
detector dead time, accepted numerical Rmax, new uncertainty model, calibration,
or detector-performance result. Independent S10b closure and systematic studies
remain blocked by `BLK-S10B-001`; Rmax remains blocked by `S-STAT-003`.
