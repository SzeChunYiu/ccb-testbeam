# Latest Scientific-Review Handoff

## Session identity

- **UTC stamp:** `2026-07-25T070705Z`
- **Task:** `AUD-LEDGER-003`
- **Unit:** fail-closed audit of canonical `CL-011` effective-live-time source binding, estimand, counts, uncertainty, and validation semantics
- **Initial remote `main`:** `53bf42c8d414c9d11bcc1f9d5ab2d088da5a7600`
- **Validated implementation/evidence head before this handoff:** `e323a268d889673757cd3b2b9f21b74e3e890113`
- **Destination:** direct sequential commits to remote `main`; no force-push, branch transport, PR, or history rewrite
- **Acceptance:** **PARTIAL** — defect, arithmetic reconstruction, audit gate, tests, and evidence validated; canonical claim/public remediation remains open
- **Immutable archive:** `chatgpt_todo/archive/2026-07-25T070705Z_AUD-LEDGER-003_TAU_EFF_BINDING.md`

## Start-of-run state

Remote `main` began at `53bf42c8d414c9d11bcc1f9d5ab2d088da5a7600`.
Repository metadata, recent history, open PRs, current status checks, mandatory
coordination records, the canonical claim ledger, root WIKI, primary S10b bundle,
and secondary MV5 bundle were inspected. The initial commit had no combined
status checks. PR #868 remained closed, unmerged, non-mergeable, and untouched.
No concurrent remote-main commit appeared during the focused write sequence.

## Primary scientific evidence

The effective-live-time measurement originates in the tracked S10b bundle at
source commit `da9651c56ef6495ce9656d84b69b600daa6d8f86`, not in the later MV5
pile-up study.

Primary tracked files:

- `reports/1781000867.546870.5c124aaf/REPORT.md`;
- `reports/1781000867.546870.5c124aaf/s10b_tau_eff_template_fit.py`;
- `reports/1781000867.546870.5c124aaf/result.json`;
- `reports/1781000867.546870.5c124aaf/manifest.json`;
- `reports/1781000867.546870.5c124aaf/heldout_run_summary.csv`.

The primary manifest records Python 3.7.6, random seed 10102, exact SHA-256 values
for fourteen ROOT inputs, and output hashes.

## Independent reconstruction

The held-out summary contains fourteen unique run rows and 252,266 selected
pulses. The reported central value is an equal-weight mean of fourteen run-level
10% template-crossing estimates relative to CFD20:

`124.79018394263471 ns`.

The exact RNG stream was reconstructed. Replaying the producer's pre-bootstrap
60,000-of-63,067 choice and 252,266-element shuffle, followed by 5,000 bootstrap
draws of fourteen run units, reproduces the tracked percentile interval exactly:

`[123.33094981246663, 126.35875117626817] ns`.

The result is therefore reproducible from tracked derived artifacts in binary64
arithmetic. This run did not reprocess the raw ROOT inputs.

## Confirmed `CL-011` defects

The current exact-width row returns 30 fail-closed findings. Material defects are:

1. It cites the later MV5 report/producer instead of primary S10b evidence.
2. Its cited source-data path `reports/mv5_pileup_1782678353/results.json` does
   not exist.
3. It rounds the estimate and interval to `124.79`, `[123.5, 126.0]`.
4. It publishes unsupported `stat_unc=0.5`, `syst_unc=1.0`, and
   `total_unc=1.12`; the primary source has no such decomposition.
5. It omits `n_runs=14` and gives `n_data=213843` instead of 252,266 selected
   pulses.
6. It obscures the equal-weight run-average, 10%-crossing, CFD20-relative
   estimand.
7. It labels the result `data_mc_self_consistent` and `VALIDATED`, even though
   MV5 hard-codes rounded 124.8 ns as an input rather than independently
   validating it.
8. It omits the primary manifest, source commit, exact CI method, caveats, and
   blocker.

## Required remediation contract

A corrected row must bind the S10b report, producer, result, manifest, and source
commit; record the exact value and interval; record 14 runs and 252,266 selected
pulses; leave statistical/systematic/total uncertainty components empty; use
`truth_type=data_measurement` and `status=DONE_DATA_ONLY`; explicitly state that
MV5 reuses the value; and state that the result is not a detector-wide universal
dead time.

The row remains blocked under `BLK-S10B-001` pending an accepted estimand decision,
waveform-threshold and run-weighting sensitivity, systematic uncertainty studies,
a clean independent rerun, and non-circular cross-method or external closure.
Dependent WIKI, executive-summary, pile-up chapter, LaTeX, and figure metadata
must be synchronized in the remediation unit.

## Audit gate, tests, and visual evidence

Added:

- `tools/audit/audit_tau_eff_claim_binding.py`;
- `tests/test_audit_tau_eff_claim_binding.py`;
- `docs/validation/tau_eff_claim_binding_audit.md`;
- `docs/validation/tau_eff_claim_binding_validation.json`;
- `docs/validation/tau_eff_claim_binding.svg`.

Policy:

`TAU_EFF_CLAIM_MUST_BIND_TO_PRIMARY_S10B_MEASUREMENT`.

The audit uses strict UTF-8 single-read snapshots, exact SHA-256 provenance,
exact 43-column claim interpretation, manifest-output hash verification,
independent central-value and RNG-stream CI reconstruction, duplicate-row
rejection, protected atomic JSON/SVG output, and input/output alias rejection.

Executed:

```text
python -m py_compile \
  tools/audit/audit_tau_eff_claim_binding.py \
  tests/test_audit_tau_eff_claim_binding.py

PYTHONPATH=. pytest -q tests/test_audit_tau_eff_claim_binding.py

6 passed in 1.22s
```

The corrected contract fixture returned `VALIDATED` with zero findings. Current-
like evidence returned `FLAWED` with 30 findings. Manifest mutation, duplicate
`CL-011`, invalid UTF-8, and destructive output aliases failed closed. JSON and
SVG XML parsing passed. Changed Python lines are at most 100 characters.

Environment: Python 3.13.5, NumPy 2.3.5, pytest 9.0.2.

Committed blob identities matched the locally validated files:

- validator `7c9dde11905e56e60d49f3147a5e511cb7526948`;
- tests `a602870b3c9fac806694b390c11526785cb61964`;
- report `44e4150073f20f9da1a9088a9b91a0cf990e3f81`;
- JSON `c8bc797782bda99be749d63ac02bf641df4717d5`;
- SVG `354908c8717c29b1897fa245d837a5d98b145c86`.

## Direct-main commit sequence before handoff

- `877b1cb816f0c567ab8f346be9ab1994a1ccbe20` — audit implementation;
- `66cd6412fa65295cf79037493a2d60f2d7aa5852` — focused tests;
- `b15689de4beda4b3c015e51999f5a7a6999da0d1` — audit report;
- `775d306d97083ddfa23c9f85f19826c91aa939e5` — machine-readable evidence;
- `9838a5c50fedf6777194f2e70b6c249f9be16e09` — visual evidence;
- `3b3804ea2f1b94af932fa10e3aab8bff48f8ff2b` — active-task update;
- `e323a268d889673757cd3b2b9f21b74e3e890113` — immutable archive.

GitHub contents writes returned successful direct-main commit SHAs rather than
conventional textual `git push` output. Post-write history confirmed this
sequence on remote `main`.

## Scientific boundary and unresolved risks

No raw ROOT file was opened, no pulse selection or waveform fit was rerun, no new
uncertainty component was estimated, and no detector-wide dead time, accepted
Rmax, pile-up capacity, calibration, or detector-performance claim is produced.
The audit validates tracked derived-artifact arithmetic and exposes claim binding
problems; it does not upgrade scientific acceptance.

Full repository pytest, ruff, ROOT processing, repository-wide link checking,
and GitHub Actions were not run. No broad CI success is claimed.

## Coordination limitation

`ACTIVE_TASK.md`, this immutable archive, and this handoff were updated. Shared
long-lived records requiring complete whole-file replacement (`SESSION_LOG.md`,
`BACKLOG.md`, `BLOCKERS.md`, `MASTER_INDEX.md`, and aggregate matrices) were
reviewed but not overwritten from partial or paged reconstructions because doing
so could erase unrelated or append-only provenance. This unmet synchronization
step is explicitly recorded rather than represented as completed.
