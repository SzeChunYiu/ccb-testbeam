# Latest Handoff

## Session

- **Task ID:** `AUD-TIMING-001`
- **Stamp:** `2026-07-26T083435Z`
- **Owner:** scheduled scientific-review session
- **Initial remote main:** `a8c446732e9a73d6880b313939868162ec4e2d74`
- **Reviewed PR:** #939, head `ce81f22ef57c5db0b658737c0d9ced4c7fc69949`
- **Reviewed source blob:** `ef13a859bb756dbf4b7ea6fa40f681d8858a7ac7`
- **Destination:** direct sequential commits to `main`; no task branch, pull-request transport, force-push, or history rewrite.
- **Focused acceptance:** event-identity audit tooling/evidence `VALIDATED / COMPLETE`.
- **Production acceptance:** PR #939 event-pairing contract `FLAWED / PARTIAL`; no merge is authorized by this handoff.

## Finding

Policy:

`REAL_DATA_CFD_EVENTS_MUST_USE_RUN_AND_EVENT_ID_TOGETHER`

The PR producer retains `run`, `event_id`, and `stave` on each selected pulse, but subsequently:

- pivots aligned peak samples on `event_id` alone in `select_in_time`;
- reapplies selected keys with `df["event_id"].isin(keep)`;
- pivots corrected pair times on `event_id` alone in `pair_analysis`;
- repeats the event-id-only pivot in residual plotting.

For multi-run input, `EVENTNO` must be treated as run-local unless immutable input evidence proves
global uniqueness. Dropping `run` permits cross-run stave pairing and duplicate-index failure.

## Independent controls

### False cross-run pair

`run58/event7/B6` plus `run59/event7/B8` yields:

- current event-id-only pair count: `1`;
- composite `(run,event_id)` pair count: `0`.

### Duplicate run-local EVENTNO

Two complete B6/B8 pairs in runs 58 and 59 sharing `event_id=9` yield:

- current event-id-only pivot: `ValueError`;
- composite-key pair count: `2`.

These controls demonstrate the code-path failure modes. They do not establish that the retained
production sample actually collided, because exact ROOT/event-ID bytes were unavailable.

## Work delivered

Added:

- `tools/audit/audit_real_data_cfd_event_identity.py`
- `tests/test_audit_real_data_cfd_event_identity.py`
- `tools/audit/render_real_data_cfd_event_identity_evidence.py`
- `docs/validation/real_data_cfd_event_identity_validation.json`
- `docs/validation/real_data_cfd_event_identity.svg`
- `docs/validation/real_data_cfd_event_identity_audit.md`
- `chatgpt_todo/archive/2026-07-26T083435Z_AUD-TIMING-001_EVENT_IDENTITY.md`

Updated:

- `chatgpt_todo/ACTIVE_TASK.md`
- `chatgpt_todo/HANDOFF.md`

A review comment was posted on PR #939 with the exact defect, evidence paths, remediation conditions,
and scientific boundary.

## Validation

```text
python -m py_compile \
  tools/audit/audit_real_data_cfd_event_identity.py \
  tests/test_audit_real_data_cfd_event_identity.py \
  tools/audit/render_real_data_cfd_event_identity_evidence.py

PYTHONPATH=. pytest -q tests/test_audit_real_data_cfd_event_identity.py

6 passed in 0.06s
```

Additional outcomes:

- current-like source contract: `FLAWED`, six findings, expected exit `1`;
- corrected composite-key fixture: `VALIDATED`, zero findings;
- invalid UTF-8: controlled exit `2`;
- source/output alias: rejected with source unchanged;
- injected `os.replace` failure: previous output preserved, zero temporary files remain;
- JSON parse: passed;
- SVG XML parse: passed;
- maximum changed Python line length: 99 characters.

Local validation environment: Python 3.13.5, pandas 2.2.3, pytest 9.0.2.

The complete PR checkout could not be materialized because the execution container could not resolve
`github.com`. The audit input is explicitly labelled
`CONNECTOR_INSPECTED_EXACT_RELEVANT_SOURCE_COPY`; exact PR head and full source Git blob are recorded.

## Direct-main sequence through this handoff

- `2c0165367f8567a03c629ff6926bac38442a9a5f` — task claim;
- `c6c74990ac3f2e031a7d17320b58970b4518a7c1` — audit gate;
- `7bd52d0e293dc81f8383e1db4f0c964ffbabcb5f` — focused regressions;
- `934d4682969223e04d5a104398e2d80918d8754b` — evidence renderer;
- `ce73e8bc98f011b5eaaa20aeab463a010f208f3f` — machine-readable evidence;
- `d52123f052c8fb4291aa0e2ed0cae81455b25a9d` — visual evidence;
- `f9d26d018177bdf13f649edaa5338aca93c3e0eb` — audit report;
- `60566b36f2fb931bdc47663d480142c1f837e420` — immutable archive;
- `15bf294136c19d4b9fb0ac4a6c2ea0fa424c965e` — active-task completion.

GitHub contents writes returned a successful direct-main commit SHA for each file. The connector does
not return a conventional terminal `git push` transcript; none is claimed.

## Required remediation

Before accepting or merging the timing study:

1. define `EVENT_KEY = ["run", "event_id"]` and use it in every pivot, selection, merge, residual,
   count, and plot;
2. reject duplicate `(run,event_id,stave)` rows;
3. content-address every ROOT input with path, bytes, SHA-256, tree, entries, and per-run key counts;
4. report row and composite-key cut flow at each selection stage;
5. regenerate JSON, Markdown, and figures as one reproducible bundle;
6. compare current and corrected event membership and timing widths;
7. keep `pair/sqrt(2)` conditional on equal independent stave resolutions and negligible correlated
   jitter.

## Scientific boundary

No raw ROOT file was processed. No channel mapping, waveform calibration, pulse polarity, baseline,
CFD estimator bias, selection efficiency, bootstrap coverage, core-fit model, pair resolution,
single-stave resolution, or canonical `CL-002` claim was validated or changed. The audit does not
assert that the reported 0.899 ns value is false; it establishes that current source cannot prove the
multi-run identity of its contributing events.

Repository-wide pytest/ruff, full PR tests, ROOT processing, result/figure regeneration, complete link
inventory, and GitHub Actions were not run. PR #939 had no attached combined commit statuses at
inspection time. PR #868 was not changed or merged.

`SESSION_LOG.md` and aggregate ledgers still require a safe append/synchronization commit. Their
complete append-only bytes are exposed through paged connector responses; partial whole-file
replacement is prohibited. The immutable archive above preserves the complete session record until
that synchronization is safely performed.
