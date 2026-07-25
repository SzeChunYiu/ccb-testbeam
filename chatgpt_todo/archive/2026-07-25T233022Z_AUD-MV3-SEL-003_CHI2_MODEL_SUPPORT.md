# AUD-MV3-SEL-003 — Pearson chi-square model-support audit

- **Session stamp:** `2026-07-25T233022Z`
- **Initial remote main:** `0aa777457fff37a817bce29a7ea1656683210ddf`
- **Owner:** scheduled scientific-review session
- **Focused acceptance:** audit gate and evidence `VALIDATED`; current producer statistical
  contract `FLAWED`; production weighted result and canonical closure `BLOCKED/PARTIAL`.

## Repository and coordination review

Fetched current `main`, recent history, the weighted MV3 remediation, source report, focused tests,
`chatgpt_todo/` active task and handoff, open pull-request inventory, PR #868, and current commit
status. No open pull request was returned. PR #868 remains closed, unmerged, and non-mergeable. No
status checks were attached to the initial or current head.

A concurrent session completed `AUD-MV3-SEL-002` while this task was being selected. This run did not
repeat that correction. It reviewed the corrected producer's Pearson statistic boundary.

## Confirmed defect

The current `_chi2` implementation forms expected counts and then masks all categories with
`expected == 0` before computing Pearson chi-square. This is only valid when the corresponding
observed count is also zero. A positive observation in a zero-probability model category makes the
model unsupported and cannot be represented by a finite Pearson statistic.

Synthetic control:

```text
model fractions = [0.50, 0.50, 0, 0]
observed counts = [45, 45, 10, 0]
current result = chi2 1.0, ndf 1, chi2/ndf 1.0
```

The B6 count of ten is dropped because its expected count is zero.

The implementation also accepts model fractions summing to `0.95` and returns `chi2=5.0`, `ndf=2`,
`chi2/ndf=2.5`, even though the expected counts then sum to 95 rather than the observed total 100.

Policy:

`PEARSON_CHI2_MUST_REJECT_OUT_OF_SUPPORT_DATA_AND_NONUNIT_PROFILES`

## Work delivered

- `tools/audit/audit_mv3_chi2_support.py`
- `tests/test_audit_mv3_chi2_support.py`
- `tools/audit/render_mv3_chi2_support_evidence.py`
- `docs/validation/mv3_chi2_support_validation.json`
- `docs/validation/mv3_chi2_support.svg`
- `docs/validation/mv3_chi2_support_audit.md`
- this immutable archive, updated active task, latest handoff, and session-log append where safe.

The fail-closed replacement contract requires:

1. model fractions sum to one within a declared tolerance;
2. every `observed > 0` and `expected == 0` category is rejected as outside model support;
3. `observed == expected == 0` categories may be omitted;
4. ndf is derived only from supported categories;
5. the controls pass before any production weighted MV3 rerun.

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
returned `VALIDATED` with zero findings. Regressions cover valid four-bin input, zero-expected and
zero-observed categories, unsupported observed mass, nonunit profiles, invalid UTF-8, destructive
output aliases, and atomic JSON publication. JSON and SVG parsing passed. Changed Python lines are at
most 100 characters.

The full repository could not be cloned because the runtime could not resolve `github.com`. The exact
current `_chi2` lines were reconstructed from authenticated connector output. The validation record
retains current source blob `cd787ab64408228d67536b88bcc617fe32d0ec5a`, auditor blob
`0d17e06d281983ef767a26d8df0b49cb779ec7ac`, and test blob
`1eb60e1e6fa8169cbb15795e2b7eec52e228bafa`.

## Direct-main commits before archive

- `8004104c36c3edd1866e992bb98181bfc2ee82dc` — task claim
- `4cc9c71c68a66c4e297a4a36b260139f2c4933a6` — audit gate
- `f36fced405d2d17a69c863532781427b7e3cab8e` — focused tests
- `41bdb2793726ed190b75fed1553bc2b5151af082` — evidence renderer
- `3aec385642cf309b28f42cf20b35b4fb86c01d1f` — validation JSON
- `94690d21297cdd2bd6a7714dfc0e88900540f66e` — visual evidence
- `23c40d88ee572419f27b90d31fbd7b53bfc1887e` — audit report

All writes used direct GitHub contents-API commits to `main`; no force-push, history rewrite, task
branch, or pull-request transport was used. GitHub returned commit SHAs rather than terminal
`git push` stdout.

## Scientific boundary and next action

No production ROOT or beam-data file was rerun. No weighted stopping profile, covariance, parameter
scan, material/scattering correction, calibration, PID result, closure claim, or detector-performance
result was produced. Canonical `CL-021` remains `FLAWED` under `BLK-MV3-LEGACY-001`.

Next: correct `_chi2`, add the support and normalization regressions to the producer test suite, run
the exact source audit to zero findings, then execute the weighted producer only on immutable,
content-addressed inputs. Any claim review still requires covariance and preregistered sensitivity
scans.
