# Latest Handoff

## Session

- **Task:** `AUD-MV3-SEL-001`
- **Stamp:** `2026-07-25T220218Z`
- **Initial remote main:** `701116061eb3346a3ae2b31e2946ca450d6120e2`
- **Remote main immediately before this handoff:**
  `63993988242b3d28affa8c8b106ebd72d143c8bc`
- **Acceptance:** focused audit gate `VALIDATED`; merged production follow-up `FLAWED`;
  cumulative task `PARTIAL`.

## Area reviewed

The newly merged MV3 selection-matched stopping-depth follow-up, exact summary/report/plots,
canonical `CL-021`, source-specific `PrimaryWeight` contract, canonical PDG charge helper,
trigger-split implementation, PR #932 history, PR #868 disposition, and required coordination
records.

## Exact repository facts

PR #932 merged as `701116061eb3346a3ae2b31e2946ca450d6120e2`. Its study reports
MC Sample-I B2 fraction `0.8669236675912432` versus data `0.9442769031852253`,
Pearson chi2/ndf `5590.089500522007`, and an advertised improvement factor
`16.602672795596263`. Canonical `CL-021` remains `FLAWED` under
`BLK-MV3-LEGACY-001`. PR #868 remained closed, unmerged, non-mergeable, and untouched.
No status checks were attached to the initial commit.

## Confirmed defects

1. The producer loads `PrimaryWeight`, defaults invalid/missing weight to `1.0`, and never
   applies the resulting event weight to the stopping profile or other advertised MC results.
2. The report rejects PrimaryWeight even though the repository weight contract states it is
   the generated-source cross-section factor and that unweighted truth distributions are not
   physical production distributions.
3. The charged mask uses `pdg_charge(int(p)) >= 1`, excluding negatively charged particles
   rather than using canonical `is_charged()`.
4. The advertised improvement changes the data target. Holding Sample-I data fixed gives
   `16.114635239581606x`, not `16.602672795596263x`.
5. Matched chi2/ndf remains `5590.089500522007`; B2 residual is
   `7.735323559398211` percentage points and total-variation distance is
   `0.07735323559398212`. “Gap gone” / “shape matches” is unsupported.
6. The summary lacks input hashes, source commit/command, weight sums/ESS,
   uncertainty/covariance, and gain/threshold/coincidence/weighting sensitivities.
7. The public verdict outruns the canonical ledger state.

## Work delivered

- `tools/audit/audit_mv3_selection_claim.py`
- `tests/test_audit_mv3_selection_claim.py`
- `tools/audit/render_mv3_selection_claim_evidence.py`
- `docs/validation/mv3_selection_claim_validation.json`
- `docs/validation/mv3_selection_claim.svg`
- `docs/validation/mv3_selection_claim_audit.md`
- `chatgpt_todo/archive/2026-07-25T220218Z_AUD-MV3-SEL-001_WEIGHTED_SELECTION_SEMANTICS.md`
- updated `chatgpt_todo/ACTIVE_TASK.md`

Policy:

`MV3_SELECTION_CLAIM_REQUIRES_WEIGHTED_SIGNED_CHARGE_AND_SAME_TARGET_VALIDATION`

The executable current-like contract returns `FLAWED` with 16 findings; a corrected contract
fixture returns `VALIDATED` with zero findings.

## Validation

```text
python -m py_compile \
  tools/audit/audit_mv3_selection_claim.py \
  tests/test_audit_mv3_selection_claim.py \
  tools/audit/render_mv3_selection_claim_evidence.py

pytest -q tests/test_audit_mv3_selection_claim.py
7 passed in 0.07s
```

JSON and SVG parsing passed. Changed Python lines are at most 99 characters. Regressions cover
the observed fail-open contract, corrected acceptance, count/fraction mutation, duplicate
`CL-021`, invalid UTF-8, destructive output aliasing, and atomic JSON publication.

A complete checkout could not be obtained because the runtime could not resolve `github.com`.
Exact GitHub blobs were inspected through the authenticated connector, and a byte-local
executable fixture reproduced the observed contracts. No exact-repository local CLI execution,
ROOT rerun, or broad CI result is claimed.

## Direct-main commits

- `b7ff8d887146cb1222eac318dc0afc0f4b943e61` — task claim
- `257e3eee09142f65de4e70aca0a9b1bfac76f668` — auditor
- `68390a96c4370b020fbeb44ba57076635ca85c30` — tests
- `332031fc0f98f3694933ca8a01b7df60056df41b` — renderer
- `1d561ba6b41a10d8eec37f175c32250f97f0b67e` — machine-readable evidence
- `c94f4135a8ec6b25e79170198fdbc348297494c4` — visual evidence
- `f7d89238557ce91eb55c56f857af3522c658c544` — audit report
- `bb0ae8fa92e78fe4e1c80895c122287296264d17` — active-task completion
- `63993988242b3d28affa8c8b106ebd72d143c8bc` — immutable archive

GitHub contents writes advanced `main` directly and returned commit SHAs rather than terminal
`git push` output. Remote history was re-read after the implementation/evidence sequence and
confirmed the commits on `main`.

## Scientific boundary and unresolved risks

No ROOT file was reprocessed. No weighted stopping profile, scattering-model correction,
material correction, calibration, PID result, or detector-performance result was produced.
The existing summary and PNGs remain diagnostic and non-authorizing. The report's residual
attribution is a hypothesis until weighted and controlled scattering/material ablations are
run.

## Required next action

Correct the producer and report together: validate/apply one finite nonnegative PrimaryWeight
per event, use canonical signed-charge selection, emit weighted primary and unweighted
sensitivity results with weight ESS and profile covariance, hold the data target fixed,
preregister gain/threshold/coincidence/aggregation/weighting scans, regenerate all artifacts
from immutable inputs with full hashes, and synchronize all public claims only after the
exact-repository audit returns zero findings.

## Coordination limitation

`SESSION_LOG.md`, `BACKLOG.md`, `BLOCKERS.md`, `MASTER_INDEX.md`, and aggregate matrices were
reviewed but not replaced because the connector exposes whole-file replacement while complete
shared bytes are available only in pages. Replacing a partial reconstruction could erase
append-only or concurrent provenance. The immutable archive and this handoff retain the full
append-equivalent record; aggregate synchronization remains explicitly unmet.
