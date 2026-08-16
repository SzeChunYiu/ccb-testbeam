# AUD-TIMING-001 — real-data CFD event identity

## Session

- Stamp: `2026-07-26T083435Z`
- Owner: scheduled scientific-review session
- Initial remote `main`: `a8c446732e9a73d6880b313939868162ec4e2d74`
- Concurrent advance observed before task claim: `bd0e9254f49f963da96fc0bbafd3c7620c743645` to `a8c446732e9a73d6880b313939868162ec4e2d74`
- Task ID: `AUD-TIMING-001`
- Policy: `REAL_DATA_CFD_EVENTS_MUST_USE_RUN_AND_EVENT_ID_TOGETHER`
- Focused acceptance: audit gate/evidence `VALIDATED / COMPLETE`
- Production acceptance: PR #939 timing contract `FLAWED / PARTIAL`

## Repository and concurrent-work review

The exact repository is `SzeChunYiu/ccb-testbeam`; authenticated permissions include direct push to
`main`. Current history, open pull requests, commit checks, repository coordination protocol, active
task, handoff, backlog, master index, blockers, study ledger, claim matrix, code-result map,
visualization records, and recent session history were inspected before selecting work.

The previous claim-ledger task was complete. `AUD-REPO-001` remained separately owned and was not
duplicated. The only open pull request returned by repository search was PR #939. PR #868 was not
reopened, changed, or merged.

PR #939 at inspection:

- state: open;
- head: `ce81f22ef57c5db0b658737c0d9ced4c7fc69949`;
- base: `main`;
- source path: `scripts/real_data_cfd_timing.py`;
- source Git blob: `ef13a859bb756dbf4b7ea6fa40f681d8858a7ac7`;
- attached combined commit statuses: none returned.

## Confirmed defect

The producer retains both `run` and `event_id` on every selected pulse, then drops `run` at all
multi-stave identity boundaries:

1. aligned peaks are pivoted by `event_id` alone in `select_in_time`;
2. accepted keys are reapplied through `df["event_id"].isin(keep)`;
3. corrected times are pivoted by `event_id` alone in `pair_analysis`;
4. the residual plotting path repeats the event-id-only pivot.

For input spanning multiple ROOT runs, `EVENTNO` must be treated as run-local unless immutable input
evidence establishes global uniqueness. The required event key is `(run, event_id)`.

### False cross-run pairing control

Synthetic rows `run=58,event_id=7,B6` and `run=59,event_id=7,B8` produce one apparent pair under the
current event-id-only contract. The composite contract produces zero pairs and selects zero rows.

### Duplicate run-local EVENTNO control

Two complete B6/B8 pairs in runs 58 and 59 with `event_id=9` make the event-id-only pivot raise
`ValueError`. The composite contract retains two valid pairs.

These controls prove the code-path failure modes. They do not prove that a collision occurred in the
reported production subset because the exact ROOT bytes and per-run event identifiers were not
available in this environment.

## Tooling and evidence

Added:

- `tools/audit/audit_real_data_cfd_event_identity.py`
- `tests/test_audit_real_data_cfd_event_identity.py`
- `tools/audit/render_real_data_cfd_event_identity_evidence.py`
- `docs/validation/real_data_cfd_event_identity_validation.json`
- `docs/validation/real_data_cfd_event_identity.svg`
- `docs/validation/real_data_cfd_event_identity_audit.md`

The audit performs strict-UTF8 single-read source snapshots, AST inspection, deterministic behavioral
controls, controlled status codes, input/output alias rejection, and atomic JSON publication through
a unique same-directory temporary file with flush, `fsync`, and `os.replace`.

The connector-inspected relevant source copy returns `FLAWED` with six findings. A corrected fixture
using `EVENT_KEY = ["run", "event_id"]` returns `VALIDATED` with zero findings.

## Validation

```text
python -m py_compile \
  tools/audit/audit_real_data_cfd_event_identity.py \
  tests/test_audit_real_data_cfd_event_identity.py \
  tools/audit/render_real_data_cfd_event_identity_evidence.py

PYTHONPATH=. pytest -q tests/test_audit_real_data_cfd_event_identity.py

6 passed in 0.06s
```

Additional validated outcomes:

- expected current-like audit status: `FLAWED`, exit 1;
- corrected composite-key fixture: `VALIDATED`, zero findings;
- false cross-run pair count: current 1, composite 0;
- duplicate-event control: current `ValueError`, composite 2 valid pairs;
- invalid UTF-8: controlled input error, exit 2;
- output alias: rejected without source modification;
- injected replacement failure: previous JSON preserved and temporary file removed;
- validation JSON parse: passed;
- SVG XML parse: passed;
- maximum changed Python line length: 99 characters.

Local environment: Python 3.13.5, pandas 2.2.3, pytest 9.0.2.

The local audited input is explicitly labelled
`CONNECTOR_INSPECTED_EXACT_RELEVANT_SOURCE_COPY`; the exact full PR source blob is retained above.
The execution container could not materialize a complete checkout or raw ROOT inputs.

## Direct-main commits through audit evidence

- `2c0165367f8567a03c629ff6926bac38442a9a5f` — task claim;
- `c6c74990ac3f2e031a7d17320b58970b4518a7c1` — fail-closed audit gate;
- `7bd52d0e293dc81f8383e1db4f0c964ffbabcb5f` — focused regressions;
- `934d4682969223e04d5a104398e2d80918d8754b` — evidence renderer;
- `ce73e8bc98f011b5eaaa20aeab463a010f208f3f` — machine-readable evidence;
- `d52123f052c8fb4291aa0e2ed0cae81455b25a9d` — visual evidence;
- `f9d26d018177bdf13f649edaa5338aca93c3e0eb` — audit report.

Every write was a direct sequential GitHub contents commit to `main`. No task branch, pull request,
force-push, or history rewrite was used. The connector returns commit SHAs rather than a terminal
`git push` transcript.

## Required remediation

Before PR #939 or equivalent results can be scientifically accepted:

1. use `(run,event_id)` in every pivot, filter, merge, residual, count, and plot;
2. reject duplicate `(run,event_id,stave)` rows;
3. retain every input ROOT path, bytes, SHA-256, tree name, entries, and per-run key cardinality;
4. report row and composite-key cut flow before and after each selection;
5. regenerate JSON, Markdown, and figures together from immutable ROOT bytes;
6. compare current and corrected selected event sets and timing widths;
7. treat `pair/sqrt(2)` as conditional on equal independent stave resolution and negligible
   correlated jitter.

## Scientific boundary

No raw ROOT file was processed. No channel map, pulse polarity, baseline method, timing calibration,
CFD bias, selection efficiency, bootstrap coverage, Gaussian-core model, waveform result, pair timing
resolution, single-stave resolution, or `CL-002` claim was validated or changed. The audit does not
assert that 0.899 ns is numerically false; it establishes that the current source cannot prove the
identity of the events used to derive it.

Repository-wide pytest/ruff, complete PR tests, ROOT processing, figure regeneration, link inventory,
and GitHub Actions were not run. No broad CI success is claimed.
