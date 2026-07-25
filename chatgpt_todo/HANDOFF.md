# Latest Scientific-Review Handoff

## Session identity

- **UTC stamp:** `2026-07-25T080448Z`
- **Task:** `AUD-LEDGER-003`
- **Unit:** canonical `CL-011` effective-live-time remediation
- **Initial remote `main`:** `563582a0d7b1d3b0fac3e33cc241b4981a21912e`
- **Complete delivery handoff / recorded after-SHA:**
  `d7901b06ecdd45238744a88ec453821a89650f06`
- **Destination:** direct sequential commits to remote `main`; no force-push,
  branch transport, PR, or history rewrite
- **Push result:** GitHub contents writes returned successful direct-main commit SHAs;
  post-write history confirmed `d7901b06ecdd45238744a88ec453821a89650f06`
  on remote `main`
- **Acceptance:** **PARTIAL** — canonical ledger row and focused regression are
  validated; public WIKI/Chapter synchronization and scientific closure remain open
- **Immutable archive:**
  `chatgpt_todo/archive/2026-07-25T080448Z_AUD-LEDGER-003_TAU_EFF_REMEDIATION.md`

This confirmation records that the complete focused delivery is present on remote
`main`. It does not broaden the scientific acceptance boundary.

## Start-of-run review

Inspected current `main`, recent history, open PRs, closed PR #868, status checks,
mandatory coordination records, the canonical ledger, WIKI, Chapters 1 and 5, the
prior tau-eff audit, and primary S10b result/manifest/held-out table. No concurrent
`main` change appeared during the focused sequence. The initial and delivery commits
had no attached status checks. PR #868 remained closed, unmerged, non-mergeable, and
untouched.

## Confirmed former defects

The old exact-width `CL-011` row cited MV5 instead of primary S10b evidence, pointed
to nonexistent `reports/mv5_pileup_1782678353/results.json`, rounded the value and
interval, supplied unsupported `0.5/1.0/1.12 ns` components, recorded `n_data=213843`,
obscured the equal-weight 14-run estimand, and called MV5 reuse independent
`data_mc_self_consistent` / `VALIDATED` closure.

## Corrected canonical claim

`CL-011` now records:

- `S10b run-average 10% template live-time relative to CFD20`;
- `124.79018394263471 ns`;
- run-bootstrap 95% interval
  `[123.33094981246663, 126.35875117626817] ns`;
- 14 runs and 252266 selected pulses;
- `truth_type=data_measurement`;
- `status=DONE_DATA_ONLY`, `allowed_status_validated=NO`;
- primary S10b report, producer, result, manifest, and commit
  `da9651c56ef6495ce9656d84b69b600daa6d8f86`;
- `blocked_by=BLK-S10B-001`;
- no statistical/systematic/total uncertainty decomposition.

The notes explicitly state that this is a threshold-, selection-, and run-weighting-
specific estimand, not a detector-wide universal dead time, and that MV5 uses rounded
124.8 ns as an input rather than independently validating it.

## Independent reconstruction and exact provenance

The held-out table has 14 unique runs and 252266 pulses. The unweighted mean of the
14 run-level live10 estimates reproduces `124.79018394263471 ns`; the recorded RNG
stream reproduces the tracked percentile interval.

- Pre-change ledger blob:
  `8135794d6f0b22da6b760bf6234bb8e1cae795fb`
- Final ledger blob: `254dc5b64945260193d6b1bd4146bd6400ad28cf`
- Final ledger bytes: `21431`
- Final SHA-256:
  `e532f3af57c2d50d261bac6a0b40546decc45a4f780fd57f92afc279a4d71ea4`
- Schema check: all 27 rows, including the header, have exactly 43 fields

## Failed check retained in history

Initial contents write `aaa40edfc4e9f351e2c8f21460ef6e4d7419d287`
transiently mistranscribed two unrelated P04p/P07e script/config paths with periods
instead of underscores. The unexpected candidate blob exposed the error. Commit
`ab03023366396caaa97abc4cb7ea9a81aeae0731` restored those unrelated paths and
produced the exact validated ledger blob before tests/evidence publication. The failed
check is recorded rather than concealed.

## Validation

Executed on exact reconstructed candidate bytes:

```text
python -m py_compile tests/test_tau_eff_claim_current.py
pytest -q tests/test_tau_eff_claim_current.py

2 passed in 0.02s
```

The regression checks unique exact-width `CL-011`, required fields/caveats, 14 unique
runs, 252266 pulses, central mean, interval, and source commit. JSON and SVG parsed.
Maximum changed Python line length was 83. Published test blob
`5d2854cdd92a2a7caf209ecf482a0940a8d952f9` matches the validated local file.

No repository-wide pytest, ruff, broken-link inventory, ROOT processing, waveform-fit
execution, or GitHub Actions success is claimed.

## Files changed

- `docs/claim_ledger.csv`
- `tests/test_tau_eff_claim_current.py`
- `docs/validation/tau_eff_claim_remediation_audit.md`
- `docs/validation/tau_eff_claim_remediation_validation.json`
- `docs/validation/tau_eff_claim_remediation.svg`
- `chatgpt_todo/ACTIVE_TASK.md`
- `chatgpt_todo/archive/2026-07-25T080448Z_AUD-LEDGER-003_TAU_EFF_REMEDIATION.md`
- `chatgpt_todo/HANDOFF.md`

## Direct-main commit sequence

- `aaa40edfc4e9f351e2c8f21460ef6e4d7419d287` — initial ledger write;
- `ab03023366396caaa97abc4cb7ea9a81aeae0731` — restore unrelated paths and
  publish exact validated ledger;
- `66e3ec992b01fdc59a0c256a92e9afb6a8683637` — current-ledger regression;
- `b3fac0f78c743ad4a2f89f6f95789412b09dbabb` — audit report;
- `72d3dd4df910151f9027991dc628450a1f442357` — machine-readable evidence;
- `e13010075758981060f0f6d751258cdc4a9d3b3d` — visual evidence;
- `b9544dd7bb14b026495c6f9e6c504e4bcbdfbd95` — active-task update;
- `c84c79cc9ae050f8a0a2528d28f93da9cb94048b` — immutable archive;
- `d7901b06ecdd45238744a88ec453821a89650f06` — complete delivery handoff,
  confirmed on remote `main`.

## Remaining public synchronization and scientific boundary

`WIKI.md`, Chapter 1, and Chapter 5 remain stale and require an exact-content unit with
location-bound regressions and link checks. They still contain some combination of
`VALIDATED`, `data + MC self-consistent`, rounded interval wording, unsupported
uncertainty components, or an incorrect confidence-level description.

No raw ROOT data were reprocessed, no waveform fit was rerun, and no new systematic
uncertainty was estimated. The result remains `DONE_DATA_ONLY` under `BLK-S10B-001`.
Threshold/run-weighting sensitivity, independent cross-method or external closure, and
an accepted systematic model remain open. No universal dead time, accepted Rmax,
calibration, or detector-performance claim follows.

## Append-only log limitation

`SESSION_LOG.md` was reviewed through complete ranged snapshots. The connector
requires whole-file replacement rather than byte-safe append. Replacing a manually
reconstructed 282-line append-only history would create avoidable provenance risk, so
it was not replaced. The immutable archive and this handoff contain the complete
append-equivalent record. This mandatory synchronization step remains explicitly unmet.
