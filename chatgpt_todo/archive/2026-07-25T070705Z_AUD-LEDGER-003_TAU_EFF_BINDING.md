# Immutable session record — AUD-LEDGER-003

## Session identity

- UTC stamp: `2026-07-25T070705Z`
- Owner: scheduled scientific-review session
- Task: `AUD-LEDGER-003`
- Initial remote `main`: `53bf42c8d414c9d11bcc1f9d5ab2d088da5a7600`
- Focused validated head before archive: `3b3804ea2f1b94af932fa10e3aab8bff48f8ff2b`
- Destination: direct sequential commits to remote `main`; no force-push, branch transport, PR merge, or history rewrite
- Acceptance: `PARTIAL`; defect and fail-closed remediation contract validated, canonical claim/public text not yet changed

## Repository and coordination review

Inspected current `main`, recent history, open PR inventory, combined commit status,
repository permissions, the mandatory `chatgpt_todo/` records, the canonical claim
ledger, root WIKI, S10b measurement artifacts, the later MV5 pile-up report and
summary, and the exact primary producer implementation.

The initial main commit had no attached combined status checks. PR #868 remained
closed, unmerged, and non-mergeable and was not modified. No concurrent remote-main
commit appeared during the focused write sequence.

## Scientific question

Does canonical claim `CL-011` correctly identify, quantify, source, and classify
the tracked 124.8 ns effective-live-time result, including its estimand, sample
count, uncertainty method, and relation to the later MV5 simulation?

## Primary evidence and exact provenance

Primary S10b measurement bundle:

- report: `reports/1781000867.546870.5c124aaf/REPORT.md`, Git blob
  `dd33a29d2ccb62fd367a5b19a152fa36f669e69d`;
- result: `reports/1781000867.546870.5c124aaf/result.json`, Git blob
  `57d82d091b1f21d9d4c400cf92c9db2893aa7ffb`;
- manifest: `reports/1781000867.546870.5c124aaf/manifest.json`, Git blob
  `cc3713c2615bc5a5d2b5e493ef58a2b460e1aa92`;
- held-out summary: `reports/1781000867.546870.5c124aaf/heldout_run_summary.csv`,
  Git blob `71bc0cbe761c831c79efa5242191a9d2bd9ab78e`;
- producer: `reports/1781000867.546870.5c124aaf/s10b_tau_eff_template_fit.py`,
  Git blob `7805c39db6dab458f4ea40412454a770d0f944c7`;
- recorded source commit: `da9651c56ef6495ce9656d84b69b600daa6d8f86`;
- recorded environment: Python 3.7.6 on Linux;
- random seed: 10102;
- fourteen input ROOT SHA-256 values retained in the manifest.

Secondary MV5 bundle:

- report Git blob `96ede7778cdb30cfab420abeb69c23f0a98b6974`;
- summary Git blob `646d55e027f3ddc6def4ca43514c46ef9935e6d4`.

Canonical ledger Git blob reviewed:

`8135794d6f0b22da6b760bf6234bb8e1cae795fb`.

## Independent reconstruction

The tracked S10b held-out summary contains fourteen unique run rows and 252,266
selected pulses. The central result is the equal-weight arithmetic mean of the
fourteen run-level 10% template-crossing estimates relative to CFD20:

`124.79018394263471 ns`.

The source RNG stream was reconstructed exactly. The producer initializes
`numpy.default_rng(10102)`, consumes a 60,000-of-63,067 random choice and a
shuffle of 252,266 targets before drawing the bootstrap indices. Replaying those
operations followed by 5,000 fourteen-run bootstrap draws gives the exact tracked
percentile interval:

`[123.33094981246663, 126.35875117626817] ns`.

Both the central estimate and interval reproduce the tracked result exactly in
binary64 arithmetic.

## Confirmed defects

The current exact-width `CL-011` row returns 30 fail-closed findings:

1. The claim text hides the run-average, 10%-crossing, CFD20-relative estimand.
2. It records rounded value `124.79` and rounded interval `[123.5, 126.0]`
   rather than the exact tracked values.
3. It records unsupported `stat_unc=0.5`, `syst_unc=1.0`, and
   `total_unc=1.12`; no such decomposition exists in the primary result.
4. It omits `n_runs=14` and records `n_data=213843` rather than the tracked
   252,266 selected pulses.
5. It cites the later MV5 report/producer as primary evidence.
6. Its source-data path `reports/mv5_pileup_1782678353/results.json` does not
   exist.
7. MV5 hard-codes rounded `tau_eff_new_ns=124.8` and uses it as an input; it is
   not an independent validation of the S10b measurement.
8. `truth_type=data_mc_self_consistent`, `status=VALIDATED`, and
   `allowed_status_validated=YES` therefore overstate the evidence.
9. The row lacks the primary result, manifest, source commit, exact CI method,
   link validation, scientific caveats, and blocker.

## Required remediation contract

A corrected row must:

- identify the S10b run-average 10% template live-time relative to CFD20;
- record exact value and run-bootstrap percentile interval;
- record 14 runs and 252,266 selected pulses;
- leave statistical/systematic/total uncertainty decomposition empty;
- use `truth_type=data_measurement` and `status=DONE_DATA_ONLY`;
- bind the primary report, producer, result, manifest, and source commit;
- state that MV5 reuses the value rather than independently validating it;
- state that this is not a detector-wide universal dead time;
- remain blocked under `BLK-S10B-001` pending an accepted estimand decision,
  systematic studies, independent rerun, and non-circular closure.

Dependent WIKI, executive-summary, pile-up chapter, LaTeX, and figure metadata
must be synchronized in the remediation unit.

## Software and evidence delivered

Added:

- `tools/audit/audit_tau_eff_claim_binding.py`;
- `tests/test_audit_tau_eff_claim_binding.py`;
- `docs/validation/tau_eff_claim_binding_audit.md`;
- `docs/validation/tau_eff_claim_binding_validation.json`;
- `docs/validation/tau_eff_claim_binding.svg`.

Updated:

- `chatgpt_todo/ACTIVE_TASK.md`.

Policy:

`TAU_EFF_CLAIM_MUST_BIND_TO_PRIMARY_S10B_MEASUREMENT`.

The validator uses strict UTF-8 single-read snapshots, exact SHA-256 provenance,
exact 43-column row interpretation, manifest-output hash verification, independent
central-value and RNG-stream CI reconstruction, duplicate-row rejection, atomic
JSON/SVG publication, and destructive output-alias rejection.

## Validation

Executed on the locally reconstructed exact reviewed source bytes:

```text
python -m py_compile \
  tools/audit/audit_tau_eff_claim_binding.py \
  tests/test_audit_tau_eff_claim_binding.py

PYTHONPATH=. pytest -q tests/test_audit_tau_eff_claim_binding.py

6 passed in 1.22s
```

Additional checks:

- corrected-contract fixture: `VALIDATED`, zero findings;
- current-like exact-width row: `FLAWED`, 30 findings;
- manifest mutation: rejected;
- duplicate `CL-011`: rejected;
- invalid UTF-8: controlled status 2;
- destructive output alias: rejected and input preserved;
- validation JSON parse: passed;
- SVG XML parse: passed;
- changed Python line length: no line above 100 characters;
- local Git blob IDs matched committed validator, tests, report, JSON, and SVG.

Validation environment:

- Python 3.13.5;
- NumPy 2.3.5;
- pytest 9.0.2.

Validated SHA-256 values:

- validator: `091df1075683eb97d5fd0f278620a88374ef5a84692c9305e6d70dce3cb7439c`;
- tests: `0d8b5e906199878c0854d13208890dbb0449e24ff4be0456827303e9efc9fda2`;
- report: `327051dbc727f8b564f872e5741e65f78df176b9ecd1f206fda1217224917996`;
- JSON: `f64a7d38020788a65c59815e5965ba2575b7f1525d07164dbb62e4b113e4f17e`;
- SVG: `2126018b531bd6a161d72e9232b2661609043e4d357848469ff8eb056d33a9de`.

Committed Git blobs:

- validator: `7c9dde11905e56e60d49f3147a5e511cb7526948`;
- tests: `a602870b3c9fac806694b390c11526785cb61964`;
- report: `44e4150073f20f9da1a9088a9b91a0cf990e3f81`;
- JSON: `c8bc797782bda99be749d63ac02bf641df4717d5`;
- SVG: `354908c8717c29b1897fa245d837a5d98b145c86`.

## Direct-main commits before archive

- `877b1cb816f0c567ab8f346be9ab1994a1ccbe20` — audit implementation;
- `66cd6412fa65295cf79037493a2d60f2d7aa5852` — focused tests;
- `b15689de4beda4b3c015e51999f5a7a6999da0d1` — audit report;
- `775d306d97083ddfa23c9f85f19826c91aa939e5` — machine-readable evidence;
- `9838a5c50fedf6777194f2e70b6c249f9be16e09` — visual evidence;
- `3b3804ea2f1b94af932fa10e3aab8bff48f8ff2b` — active-task update.

GitHub contents writes returned successful commit SHAs. A post-write history read
confirmed the sequence above on remote `main`.

## Scientific and operational boundary

No raw ROOT file was opened in this run, no pulse selection or waveform fit was
rerun, no new uncertainty component was estimated, and no universal detector
live-time, Rmax, pile-up capability, calibration, or detector-performance claim
is accepted by this audit.

Full repository pytest, ruff, ROOT processing, broad link checking, and GitHub
Actions were not run. No combined status checks were attached to the initial
main commit.

Shared long-lived coordination files requiring complete whole-file replacement
(`SESSION_LOG.md`, `BACKLOG.md`, `BLOCKERS.md`, `MASTER_INDEX.md`, and aggregate
matrices) were reviewed but not overwritten from partial/paged reconstructions.
The active task, this immutable archive, and the latest handoff preserve the
complete append-equivalent record. This coordination limitation is explicit and
is not represented as completed synchronization.
