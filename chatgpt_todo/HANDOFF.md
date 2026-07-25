# Latest Scientific-Review Handoff

## Session identity

- **UTC stamp:** `2026-07-25T080448Z`
- **Task:** `AUD-LEDGER-003`
- **Unit:** canonical `CL-011` effective-live-time remediation
- **Initial remote `main`:** `563582a0d7b1d3b0fac3e33cc241b4981a21912e`
- **Validated implementation/evidence head before this handoff:**
  `c84c79cc9ae050f8a0a2528d28f93da9cb94048b`
- **Destination:** direct sequential commits to remote `main`; no force-push,
  branch transport, PR, or history rewrite
- **Acceptance:** **PARTIAL** — canonical ledger row and focused regression are
  validated; public WIKI/Chapter synchronization and scientific closure remain open
- **Immutable archive:**
  `chatgpt_todo/archive/2026-07-25T080448Z_AUD-LEDGER-003_TAU_EFF_REMEDIATION.md`

## Start-of-run state and concurrency

Remote `main` began at `563582a0d7b1d3b0fac3e33cc241b4981a21912e`.
Recent history, open PRs, closed PR #868, status checks, mandatory coordination files,
the canonical ledger, root WIKI, Chapters 1 and 5, the prior tau-eff audit, and the
primary S10b bundle were inspected. No concurrent `main` change appeared before or
during the focused sequence. The initial and delivery commits had no attached status
checks. PR #868 remained closed, unmerged, non-mergeable, and untouched.

## Reviewed scientific area

The unit reviewed the claim-to-result path for the effective-live-time quantity:

1. S10b producer and manifest;
2. held-out-run table and result JSON;
3. canonical `docs/claim_ledger.csv` row `CL-011`;
4. the later MV5 simulation reuse;
5. root WIKI and Chapters 1 and 5 as downstream public consumers;
6. the fail-closed audit and its prior focused tests.

## Confirmed former defects

The previous exact-width row:

- cited secondary MV5 files rather than the primary S10b measurement;
- cited nonexistent `reports/mv5_pileup_1782678353/results.json`;
- rounded the result and interval;
- supplied unsupported `0.5`, `1.0`, and `1.12 ns` uncertainty components;
- recorded `n_data=213843` rather than 252266 selected pulses;
- obscured the equal-weight 14-run estimand;
- classified MV5 reuse as independent `data_mc_self_consistent` / `VALIDATED`
  evidence.

## Corrected canonical claim

`CL-011` now records:

- claim: `S10b run-average 10% template live-time relative to CFD20`;
- value: `124.79018394263471 ns`;
- run-bootstrap 95% interval:
  `[123.33094981246663, 126.35875117626817] ns`;
- 14 runs and 252266 selected pulses;
- `truth_type=data_measurement`;
- `status=DONE_DATA_ONLY`;
- `allowed_status_validated=NO`;
- primary S10b report, producer, result, manifest, and source commit
  `da9651c56ef6495ce9656d84b69b600daa6d8f86`;
- `blocked_by=BLK-S10B-001`;
- empty statistical, systematic, and total uncertainty fields.

The notes state that this is a threshold-, selection-, and run-weighting-specific
estimand rather than a detector-wide universal dead time, and that MV5 uses rounded
124.8 ns as an input rather than independently validating it.

## Independent reconstruction and provenance

The tracked held-out table contains 14 unique run rows and 252266 pulses. The
unweighted mean of the fourteen run-level live10 values reproduces
`124.79018394263471 ns`. The recorded seed/RNG stream reproduces the exact percentile
interval in the tracked result.

Ledger provenance:

- pre-change blob: `8135794d6f0b22da6b760bf6234bb8e1cae795fb`;
- final blob: `254dc5b64945260193d6b1bd4146bd6400ad28cf`;
- final bytes: `21431`;
- final SHA-256:
  `e532f3af57c2d50d261bac6a0b40546decc45a4f780fd57f92afc279a4d71ea4`;
- all 27 rows, including the header, contain exactly 43 fields.

## Failed publication check and correction

The first direct ledger write
`aaa40edfc4e9f351e2c8f21460ef6e4d7419d287` transiently changed two unrelated
P04p/P07e script/config paths by using periods where the canonical rows used
underscores. The unexpected candidate Git blob exposed the mistake. Corrective commit
`ab03023366396caaa97abc4cb7ea9a81aeae0731` restored the unrelated paths and produced
the exact locally validated blob before tests and evidence were published. The failed
check and correction are retained in history and evidence.

## Validation commands and results

Executed on exact reconstructed candidate bytes:

```text
python -m py_compile tests/test_tau_eff_claim_current.py
pytest -q tests/test_tau_eff_claim_current.py

2 passed in 0.02s
```

The regression verifies unique exact-width `CL-011`, every required field and caveat,
14 unique runs, 252266 pulses, the central mean, interval, and source commit. JSON and
SVG evidence parsed successfully. The changed Python file has maximum line length 83.
The published test blob is
`5d2854cdd92a2a7caf209ecf482a0940a8d952f9`, matching the validated local file.

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

## Direct-main commit sequence before handoff

- `aaa40edfc4e9f351e2c8f21460ef6e4d7419d287` — initial ledger write;
- `ab03023366396caaa97abc4cb7ea9a81aeae0731` — restore unrelated source paths and
  publish exact validated ledger blob;
- `66e3ec992b01fdc59a0c256a92e9afb6a8683637` — current-ledger regression;
- `b3fac0f78c743ad4a2f89f6f95789412b09dbabb` — validation audit;
- `72d3dd4df910151f9027991dc628450a1f442357` — machine-readable evidence;
- `e13010075758981060f0f6d751258cdc4a9d3b3d` — visual evidence;
- `b9544dd7bb14b026495c6f9e6c504e4bcbdfbd95` — active-task update;
- `c84c79cc9ae050f8a0a2528d28f93da9cb94048b` — immutable archive.

GitHub contents writes returned successful direct-main commit SHAs rather than
conventional textual `git push` output. Post-write history confirmed the sequence on
remote `main`.

## Remaining public synchronization

The ledger is now authoritative, but these public surfaces remain stale and must be
corrected in a separate exact-content unit:

- `WIKI.md`;
- `docs/academic_chapters/01_executive_summary.md`;
- `docs/academic_chapters/05_pileup_analysis.md`.

They still contain some combination of `VALIDATED`, `data + MC self-consistent`,
rounded interval wording, unsupported uncertainty components, or an incorrect
confidence-level description.

## Scientific boundary and next task

No raw ROOT data were reprocessed, no waveform fit was rerun, and no new systematic
uncertainty was estimated. The measurement remains `DONE_DATA_ONLY` under
`BLK-S10B-001`. Threshold and run-weighting sensitivity, independent cross-method or
external closure, and an accepted systematic uncertainty model remain open. No
universal detector dead time, accepted Rmax, calibration, or detector-performance
claim follows.

Next: synchronize the three public surfaces to exact S10b semantics, add focused
location-bound regressions, run the link checker, and retain the `DONE_DATA_ONLY`
boundary.

## Append-only log limitation

`SESSION_LOG.md` was reviewed through complete ranged snapshots. This connector still
requires whole-file replacement rather than byte-safe append. Replacing a manually
reconstructed 282-line append-only history would create unnecessary provenance risk;
therefore it was not replaced. The immutable archive and this handoff contain the
complete append-equivalent record. This mandatory synchronization step remains
explicitly unmet rather than being falsely claimed.
