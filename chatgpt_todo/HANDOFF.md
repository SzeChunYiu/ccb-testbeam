# Latest Scientific-Review Handoff

## Session identity

- **UTC stamp:** `2026-07-25T121422Z`
- **Task:** `AUD-WIKI-004`
- **Unit:** close the evidence and coordination gap for the exact S10b live-time
  public-WIKI remediation
- **Initial remote `main`:** `0e32bf3f5956162d30259489d6d99295280e06fb`
- **Core remediation commit:**
  `0e32bf3f5956162d30259489d6d99295280e06fb`
- **Complete delivery handoff / recorded after-SHA:**
  `f28d04ec9742e3e42a78d054836309611384ce68`
- **Destination:** direct focused commits to remote `main`; no force-push,
  branch transport, PR, or history rewrite
- **Push result:** GitHub contents writes returned successful direct-main commit
  SHAs; post-write history confirmed
  `f28d04ec9742e3e42a78d054836309611384ce68` on remote `main`
- **Acceptance:** **COMPLETE** for `AUD-WIKI-004`; the cumulative repository-wide
  WIKI audit remains open for unrelated claims and links
- **Immutable archive:**
  `chatgpt_todo/archive/2026-07-25T121422Z_AUD-WIKI-004_PUBLIC_REMEDIATION.md`

## Start-of-run review

Inspected current `main`, recent history and concurrent changes, repository
permissions, open PRs, closed PR #868, the corrected root WIKI, exact-width
`CL-011`, Chapter 5, the integration regression, the prior location-bound
validator, and the mandatory coordination files.

No active task was duplicated. PR #868 remained closed, unmerged, and
non-mergeable and was not modified. The core remediation commit had no attached
status checks.

## Canonical scientific contract

The public claim is bound to the tracked S10b data-only estimand:

- S10b run-average 10% template live-time relative to CFD20;
- `124.79018394263471 ns`;
- run-bootstrap 95% interval
  `[123.33094981246663, 126.35875117626817] ns`;
- 14 runs and 252266 selected pulses;
- `truth_type=data_measurement`;
- `status=DONE_DATA_ONLY`;
- blocker `BLK-S10B-001`;
- no separate statistical, systematic, or total uncertainty components.

The pile-up narrative states that this is a threshold-, selection-, and
run-weighting-specific estimand rather than a detector-wide universal dead time,
and that MV5 reuses it as an input rather than independently validating it.
Numerical Rmax remains withheld under `S-STAT-003`.

## Exact remote identities

- corrected WIKI blob: `001e091f82756f45339fe5e48256a951b6331295`;
- canonical ledger blob: `254dc5b64945260193d6b1bd4146bd6400ad28cf`;
- integration-test blob: `fb049a100501d5091f85daab7d4cd715a9107586`;
- Chapter 5 blob: `02a9ba538b1627e1ef3cda78594a4f08446fbffe`.

## Independent validation

A full network checkout remained unavailable because the execution container
could not resolve `github.com`. The exact GitHub-fetched canonical-table section,
pile-up section, and ledger header plus `CL-011` were reconstructed locally and
checked independently.

```text
python -m py_compile \
  tests/test_wiki_tau_eff_public_remediation.py \
  tools/validate_remediation_snapshot.py

python tools/validate_remediation_snapshot.py

status: VALIDATED
issues: 0
```

The exact committed integration-test source compiled successfully. Its longest
line was 85 characters. The validation JSON records exact snapshot SHA-256
values. The SVG parsed successfully as XML, and the linked Chapter 5 target
exists and labels the result `DONE_DATA_ONLY` while withholding numerical Rmax.

## Evidence delivered

- `docs/validation/wiki_tau_eff_public_remediation_audit.md`
- `docs/validation/wiki_tau_eff_public_remediation_validation.json`
- `docs/validation/wiki_tau_eff_public_remediation.svg`
- `chatgpt_todo/ACTIVE_TASK.md`
- immutable archive listed above
- this handoff

## Direct-main commit sequence

- `0e32bf3f5956162d30259489d6d99295280e06fb` — corrected both public WIKI
  locations and added the integration regression;
- `0eb523905aecea718b752c5aba9959b068cadf2f` — audit report;
- `0105418655613486b7c74fe072847852f936986b` — machine-readable evidence;
- `cd535220b5eba5b805711413aea6d5a2a4dab342` — visual evidence;
- `e4ed90b2befad8a8b44d17014827f0dfc4c11674` — active-task completion;
- `852040143547d08db8c619d7469410652d69065c` — immutable archive;
- `f28d04ec9742e3e42a78d054836309611384ce68` — complete delivery handoff,
  confirmed on remote `main`.

## Checks not run

- repository-wide pytest and ruff;
- exact three-validator integration pytest in a complete checkout;
- repository-wide broken-link inventory;
- GitHub Actions;
- ROOT waveform reprocessing or an S10b fit rerun.

No broader CI or physics closure is claimed.

## Coordination boundary

`SESSION_LOG.md`, `BACKLOG.md`, `BLOCKERS.md`, `MASTER_INDEX.md`, and aggregate
matrices were reviewed but not replaced. The connector provides whole-file
replacement rather than a byte-safe append or patch, and the shared records are
long-lived and partly stale relative to many later immutable archives. Replacing
a partial reconstruction could erase unrelated provenance. This handoff and the
immutable archive provide the complete append-equivalent record; aggregate
synchronization remains an explicit repository-governance gap.

## Scientific boundary and next work

This unit validates public documentation and provenance only. It does not
establish a detector-wide universal dead time, accepted numerical Rmax, a new
uncertainty model, calibration, or detector performance. Independent S10b
closure/systematic studies remain under `BLK-S10B-001`; Rmax remains under
`S-STAT-003`.

The next non-duplicative WIKI unit should audit another still-unmapped public
claim or link rather than revisiting `CL-011`.
