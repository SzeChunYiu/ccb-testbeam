# Latest Scientific-Review Handoff

## Session identity

- **UTC stamp:** `2026-07-24T230723Z`
- **Task:** `AUD-WIKI-003`
- **Unit:** MV3 public-WIKI section-binding validation
- **Initial remote `main`:** `4480ca889250e1915d963e7c646cd5ebf923a201`
- **Validated implementation/evidence head:** `cf6b891550b1d50323fb0508ed3843f32d4cfa1b`
- **Destination:** direct sequential commits to remote `main`; no force-push, history rewrite, task branch, or PR transport
- **Acceptance:** **COMPLETE** for the validator/evidence unit; public WIKI remediation remains open

## Start-of-run review

Authenticated GitHub reads inspected recent `main` history, repository metadata,
open pull requests, current commit status, `chatgpt_todo/README.md`, the previous
active task and handoff, the complete root `WIKI.md`, exact-width canonical rows
`CL-019`/`CL-020`/`CL-021`, the tracked MV3 summary, the existing MV3 WIKI
validator and tests, and prior validation artifacts.

Initial exact inputs:

- root WIKI blob: `fee0e1a15243904dbeb46254878ade4650a8e1f6`;
- root WIKI bytes: `23355`;
- root WIKI SHA-256: `c0e8c8f7aa0c6b8f024ea9821dcb046b77376aecc95c81301afaf40248417680`;
- claim-ledger blob: `8135794d6f0b22da6b760bf6234bb8e1cae795fb`;
- MV3-summary blob: `2bb4b34e499642dfdf8ceb13e2f6351ff6e5cc6d`.

No status checks were attached to the initial head.

## Exact scientific source result

The tracked summary and canonical ledger bind:

- selected-data B8: `7051/306745 = 0.02298651974767315`;
- thresholded-MC B8: `55619/249484 = 0.22293614019335908`;
- Pearson chi-square: `204808.2179684494`;
- ndf: `3`;
- chi-square/ndf: `68269.40598948313`;
- claim status: `FLAWED` for the profile diagnostic under
  `BLK-MV3-LEGACY-001`.

These are reproducible fixed-source quantities, not an accepted stopping-profile
closure or calibrated goodness-of-fit result.

## Confirmed validator weakness

`tools/audit/validate_wiki_mv3_summary.py` checks that seven exact tokens occur
somewhere in the document. Its valid regression fixture is a single paragraph of
those tokens. Therefore, an unrelated appendix can satisfy the global predicate
while the canonical results table, PID narrative, validation matrix, blocker, and
gap row remain rounded or stale.

The new synthetic regression contains every globally required exact token but
retains a rounded canonical row. The global-token predicate is satisfied, while the
new section-binding gate correctly returns `FLAWED`.

## Work delivered

Added:

- `tools/audit/validate_wiki_mv3_section_binding.py`;
- `tools/audit/render_wiki_mv3_section_binding_evidence.py`;
- `tests/test_validate_wiki_mv3_section_binding.py`;
- `docs/validation/wiki_mv3_section_binding_audit.md`;
- `docs/validation/wiki_mv3_section_binding_validation.json`;
- `docs/validation/wiki_mv3_section_binding.svg`;
- `chatgpt_todo/archive/2026-07-24T230723Z_AUD-WIKI-003_SECTION_BINDING.md`.

Updated:

- `chatgpt_todo/ACTIVE_TASK.md`;
- this handoff.

Policy:

`WIKI_MV3_EXACT_VALUES_MUST_BE_BOUND_TO_CANONICAL_SECTIONS`

The validator requires unique, location-bound content in six public use sites:

1. canonical results table;
2. experimental-setup material-impact row;
3. PID MV3 section;
4. MC-validation matrix;
5. MC blocking-issue line;
6. GAP-01 row.

It records exact WIKI byte provenance, rejects missing or duplicate anchors, and
returns controlled status 0, 1, or 2.

## Current exact WIKI result

The current WIKI returns status 1, `FLAWED`, with seven location-bound findings:

- `CANONICAL_ROW_MISMATCH`;
- `CANONICAL_ROW_ROUNDED_ONLY`;
- `MATERIAL_IMPACT_MISMATCH`;
- `PID_SECTION_MISMATCH`;
- `VALIDATION_MATRIX_MISMATCH`;
- `BLOCKING_ISSUE_MISMATCH`;
- `GAP01_MISMATCH`.

The root WIKI was deliberately not replaced in this unit. The validated outcome is
a fail-closed gate and evidence package; the public correction must pass this gate
before being reported as delivered.

## Validation commands and results

```text
python -m py_compile \
  tools/audit/validate_wiki_mv3_section_binding.py \
  tools/audit/render_wiki_mv3_section_binding_evidence.py \
  tests/test_validate_wiki_mv3_section_binding.py

PYTHONPATH=. python -m pytest \
  tests/test_validate_wiki_mv3_section_binding.py -q

5 passed in 0.03s
```

Additional checks:

- exact current-WIKI audit: `FLAWED`, seven findings, exit status 1;
- corrected six-section fixture: `VALIDATED`, zero findings;
- global-token/rounded-row fixture: `FLAWED`, two findings;
- missing and duplicate section anchors: rejected;
- invalid UTF-8: controlled `ValidationError`;
- validation JSON parse: PASS;
- SVG XML parse: PASS;
- maximum changed Python line lengths: 96, 99, and 90 characters;
- environment: Python 3.13.5, pytest 9.0.2, Linux 6.12.13.

The SVG is explicitly software/documentation evidence, not detector data.

## Direct-main commit sequence

- `4441d7566a836eb120ed6541321f6ecfad0d0bf9` — section-binding validator;
- `628d450c2daf87ae49bbec878e2962a476181eab` — focused tests;
- `6ba41f6a13b1612f561907f419d58fd9d850875f` — deterministic evidence renderer;
- `34514fdb8c89191051eab3e03f54b68415ab233a` — machine-readable validation record;
- `fa42afc80fe603c15d8179bb6d9e0dc00691395b` — audit report;
- `6e63520af23ffa01585667570c10f90bfe9240d5` — visual evidence;
- `86d5fdfbbedf5860de196dbada412f8a1733396e` — immutable archive;
- `cf6b891550b1d50323fb0508ed3843f32d4cfa1b` — active-task completion.

The GitHub contents connector returned successful direct-main commit SHAs rather
than conventional textual `git push` stdout. A post-write history read must confirm
this handoff and the sequence on remote `main`; the resulting remote head is reported
to the user.

## Scientific boundary

No ROOT, Geant4, detector-data, or simulation rerun was performed. Exact counts and
Pearson arithmetic do not establish geometry closure, trigger/selection transfer,
gain response, covariance, p-value interpretation, detector/model systematics, or
a B8 acceptance correction. `BLK-MV3-LEGACY-001` remains open.

## Coordination limitation

`SESSION_LOG.md`, `BACKLOG.md`, `BLOCKERS.md`, and aggregate matrices were not
replaced. The connector exposes whole-file replacement rather than byte-safe append
or patch semantics for these long-lived shared records; replacing an incompletely
reconstructed or concurrently changed file could erase provenance. The immutable
archive and this handoff preserve the complete append-equivalent record. This is an
explicitly unmet aggregate-synchronization requirement.

## Next exact action

Patch all six root-WIKI MV3 use sites against a complete current snapshot. Then
require zero findings from both `validate_wiki_mv3_summary.py` and
`validate_wiki_mv3_section_binding.py`, run the current front-door claim gates and
internal-link checker, and only then mark the public WIKI remediation delivered.
