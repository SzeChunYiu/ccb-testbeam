# Immutable handoff — AUD-CI-003

## Session

- **Stamp:** `2026-07-26T011234Z`
- **Initial remote main:** `b969c0cef71bebbab71728d0dc278cb7e284ce59`
- **Task:** content-address and classify the repository-wide CI blocker for MV3 transport PR #933
- **Policy:** `REPOSITORY_CI_BLOCKER_MUST_HAVE_CONTENT_ADDRESSED_FAILURE_LEDGER`
- **Status:** `VALIDATED / PARTIAL`
- **Owner:** scheduled scientific-review session

## Start-of-run review

Fetched current `main`, recent commits, PR #933, PR #868, the failed workflow/job metadata,
mandatory coordination records, the current stopping-power parser and comparison path, and the exact
workflow artifact. PR #933 remained draft and unmerged. PR #868 remained closed, unmerged,
non-mergeable, and untouched.

## Exact CI evidence

- Workflow run: `30181818642`
- Job: `89739575939`
- Artifact: `8625795443`
- Artifact SHA-256:
  `d16b0db6177e79fb30bcc682160d5460c30ea17f685b4a709c454f6c565adafa`
- Exact `pytest.log` bytes: `85803`
- Exact `pytest.log` SHA-256:
  `c48e98e20e5606b0d98a41f03f586dc8d012338fc7cc7f7cffb1847155d707ae`
- Ruff: `All checks passed!`
- Pytest: `42 failed, 775 passed, 1 skipped, 6 warnings in 60.43s`

## Confirmed governance defect

The prior handoff called all 42 failures “pre-existing cross-area failures.” The available evidence
contains only the candidate run. The absence of failures in the three named candidate test modules is
useful ownership evidence but does not establish that all other failures pre-date, or are causally
independent of, the candidate. Exact causal attribution requires a same-environment run of the exact
base SHA and paired-log comparison.

## Failure inventory

The 42 unique failing node IDs group as follows:

- stopping-power comparison: 23
- public WIKI claim binding: 6
- MV6 PCA claim rows: 4
- MV4 legacy claim rows: 2
- figure registry: 2
- Cluster D claim governance: 2
- DeltaE bridge: 1
- Chapter 8 claim validator: 1
- MV3 legacy claim rows: 1

No failure node ID begins with any of:

- `tests/test_mv3_chi2_producer_contract.py`
- `tests/test_mv3_selection_weighted_contract.py`
- `tests/test_audit_mv3_chi2_support.py`

This is recorded as `direct_candidate_test_failure_count=0`, not as proof that the remaining failures
are pre-existing.

## Work delivered

- `tools/audit/classify_ci_failure_log.py`
- `tests/test_classify_ci_failure_log.py`
- `tools/audit/render_ci_failure_ledger_evidence.py`
- `docs/validation/mv3_repository_ci_failure_ledger.json`
- `docs/validation/mv3_repository_ci_failure_ledger.svg`
- `docs/validation/mv3_repository_ci_failure_ledger_audit.md`

The classifier reads exact UTF-8 bytes once, verifies terminal failed-count closure against unique
`FAILED` node IDs, records complete SHA-256 provenance, groups families and signatures, rejects
malformed/duplicate diagnostics, publishes JSON atomically, and rejects destructive aliases. An
optional paired baseline log reports introduced, resolved, persistent, and changed-signature failures.
A single log explicitly returns `UNRESOLVED_SINGLE_RUN`.

## Validation

```text
python -m py_compile \
  tools/audit/classify_ci_failure_log.py \
  tests/test_classify_ci_failure_log.py \
  tools/audit/render_ci_failure_ledger_evidence.py

PYTHONPATH=. pytest -q tests/test_classify_ci_failure_log.py
7 passed in 2.26s
```

The exact artifact ledger returned:

- status: `VALIDATED`
- unique failures: `42`
- direct candidate-test failures: `0`
- causal-attribution mode: `UNRESOLVED_SINGLE_RUN`

JSON parsing and SVG XML parsing passed. Changed Python lines are at most 98 characters.

## Acceptance and scientific boundary

This work makes the integration blocker reproducible. It does not clear the repository-wide gate,
authorize merging PR #933, prove that the failures are pre-existing, or establish a physics result.
No production ROOT or beam-data file was rerun; no weighted profile, covariance, sensitivity scan,
material/scattering correction, calibration, PID, closure, or detector-performance result was
produced. Canonical `CL-021` remains `FLAWED` under `BLK-MV3-LEGACY-001`.

## Next action

Run the repository workflow in the same environment on the exact merge-base/base SHA and on the
updated candidate head, then classify the two exact logs together. Remediate demonstrated introduced
or persistent failures without weakening the validation gate. Keep PR #933 draft and unmerged until
the required repository-wide and focused checks pass on the exact integration head.

## Coordination limitation

`SESSION_LOG.md` was not replaced. The connector exposes whole-file replacement rather than a
byte-safe append, while the complete append-only file is available only through paged/truncated
responses. Replacing a partial reconstruction could erase provenance. This unmet requirement is
recorded explicitly rather than fabricated.
