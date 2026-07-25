# Latest Handoff

## Session

- **Task:** `AUD-MV3-SEL-003`
- **Stamp:** `2026-07-25T233022Z`
- **Initial remote main:** `0aa777457fff37a817bce29a7ea1656683210ddf`
- **Validated delivery/handoff commit:** `6be5f05a3f925329d7faac67f89a15fb624754f3`
- **Remote-main confirmation:** recent history confirmed the delivery commit and its complete focused
  ancestry on remote `main` before this confirmation update.
- **Destination:** direct GitHub contents-API commits to `main`; no force-push, history rewrite,
  task branch, or pull-request transport.
- **Push-output boundary:** GitHub returned successful commit SHAs rather than terminal `git push`
  stdout. Remote history was re-read during and after delivery.
- **Acceptance:** audit gate and evidence `VALIDATED`; current producer statistical contract
  `FLAWED`; weighted production result and canonical closure `BLOCKED/PARTIAL`.

## Area reviewed

The corrected weighted MV3 selection producer, its source report and tests, the exact `_chi2`
implementation, recent main history and concurrent `AUD-MV3-SEL-002` completion, open PR inventory,
PR #868, current commit status, and repository-local coordination records.

No open pull request was returned. PR #868 remains closed, unmerged, non-mergeable, and untouched.
No status checks were attached to the initial or delivery head.

## Confirmed statistical defects

The producer computes expected counts, masks all bins with `expected == 0`, and evaluates Pearson
chi-square only on the remaining bins. This silently omits observed mass in a category to which the
model assigns zero probability.

Synthetic exact-function control:

```text
model fractions = [0.50, 0.50, 0, 0]
observed counts = [45, 45, 10, 0]
current result = chi2 1.0, ndf 1, chi2/ndf 1.0
```

The B6 count of ten has expected count zero and is dropped. Under that model the observation is
outside support and the statistic must fail closed rather than return a finite goodness-of-fit value.

A second control uses model fractions `[0.45, 0.45, 0.05, 0]`, which sum to `0.95`. The current
implementation returns `chi2=5.0`, `ndf=2`, `chi2/ndf=2.5`, even though expected counts sum to 95
while observed counts sum to 100.

Policy:

`PEARSON_CHI2_MUST_REJECT_OUT_OF_SUPPORT_DATA_AND_NONUNIT_PROFILES`

## Work delivered

- `tools/audit/audit_mv3_chi2_support.py`
- `tests/test_audit_mv3_chi2_support.py`
- `tools/audit/render_mv3_chi2_support_evidence.py`
- `docs/validation/mv3_chi2_support_validation.json`
- `docs/validation/mv3_chi2_support.svg`
- `docs/validation/mv3_chi2_support_audit.md`
- `chatgpt_todo/archive/2026-07-25T233022Z_AUD-MV3-SEL-003_CHI2_MODEL_SUPPORT.md`
- updated `chatgpt_todo/ACTIVE_TASK.md`

The replacement contract requires normalized model fractions, rejection of every positive observed
count with zero expectation, omission only of categories where both values are zero, and ndf derived
from supported categories.

## Validation

```text
python -m py_compile \
  tools/audit/audit_mv3_chi2_support.py \
  tests/test_audit_mv3_chi2_support.py \
  tools/audit/render_mv3_chi2_support_evidence.py

pytest -q tests/test_audit_mv3_chi2_support.py
6 passed in 0.03s
```

The current exact-function reconstruction returned `FLAWED` with two findings. A corrected fixture
returned `VALIDATED` with zero findings. Regressions cover valid four-bin input, empty unsupported
categories, unsupported observed mass, nonunit profiles, invalid UTF-8, destructive output aliases,
and atomic JSON publication. JSON and SVG parsing passed; changed Python lines are at most 100
characters.

The full repository could not be cloned because the runtime could not resolve `github.com`. The exact
current function was reconstructed from authenticated connector-returned source lines. The evidence
retains producer blob `cd787ab64408228d67536b88bcc617fe32d0ec5a`, auditor blob
`0d17e06d281983ef767a26d8df0b49cb779ec7ac`, and test blob
`1eb60e1e6fa8169cbb15795e2b7eec52e228bafa`.

## Direct-main commits

- `8004104c36c3edd1866e992bb98181bfc2ee82dc` — task claim
- `4cc9c71c68a66c4e297a4a36b260139f2c4933a6` — audit gate
- `f36fced405d2d17a69c863532781427b7e3cab8e` — focused tests
- `41bdb2793726ed190b75fed1553bc2b5151af082` — evidence renderer
- `3aec385642cf309b28f42cf20b35b4fb86c01d1f` — validation JSON
- `94690d21297cdd2bd6a7714dfc0e88900540f66e` — visual evidence
- `23c40d88ee572419f27b90d31fbd7b53bfc1887e` — audit report
- `c186d363a6f0e9cd251a7d5ad2d23d79f531b300` — immutable archive
- `1b87f780e32c259ce9720578fe6d6be5f4e410f4` — active-task completion
- `6be5f05a3f925329d7faac67f89a15fb624754f3` — validated delivery handoff

## Scientific boundary and next action

No production ROOT or beam-data file was rerun. No weighted stopping profile, covariance, parameter
scan, material/scattering correction, calibration, PID result, closure claim, or detector-performance
result was produced. Canonical `CL-021` remains `FLAWED` under `BLK-MV3-LEGACY-001`.

Next: correct `_chi2`, add direct producer regressions for model normalization and support, require
the exact-source audit to return zero findings, then execute the corrected weighted producer only on
immutable content-addressed inputs. Canonical review still requires covariance and preregistered
sensitivity scans.

## Coordination limitation

`SESSION_LOG.md` was reviewed but not replaced. The connector exposes whole-file replacement rather
than byte-safe append, while the complete append-only bytes were returned only through paged or
truncated views. Reconstructing and replacing that shared log risked erasing provenance. The immutable
archive and this handoff preserve the complete append-equivalent session record. The requested
`SESSION_LOG.md` append remains explicitly unmet rather than being fabricated.
