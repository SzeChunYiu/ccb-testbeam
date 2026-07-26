# AUD-MV3-SEL-003 — Pearson producer remediation and CI blocker

- **Session:** `2026-07-26T002131Z`
- **Owner:** scheduled scientific-review session
- **Initial remote main:** `54a899d82c1991747218a5b3a5a0835c51991420`
- **Task:** `AUD-MV3-SEL-003`
- **Status:** `PARTIAL / BLOCKED`
- **Transport PR:** `#933` (draft, not merged)
- **Validated implementation head:** `c9b20d0707b675c134ce8e6b0e804a115b569ae4`
- **Main blocker-evidence commit:** `13ddd66f1b5280a960336d6f855631398d7db090`
- **Main handoff commit:** `fae320327fc157ffa362ad139df568b311201372`
- **Producer-code delivery:** not completed

## Review and defect

Fetched the current repository, `main` history, PR inventory, PR #868, CI workflow, mandatory
coordination records and the weighted MV3 producer. The producer used `expected > 0` to mask Pearson
categories. It returned finite `chi2/ndf=1.0` after omitting ten observed B6 counts assigned zero
model probability and accepted a profile summing to `0.95`, returning `chi2/ndf=2.5`.

## Candidate work

- Former weighted body retained as exact internal blob
  `cd787ab64408228d67536b88bcc617fe32d0ec5a`.
- Canonical strict front door blob `91dc6d21e6c5ffa83fada4210456157d3bbee322`.
- Producer-test blob `92c28df965d544d3c0b3ce5de36681e3a029f0e7`.
- Dynamic-loader correction blob `701d85489c7f1bda832103ce6c7b6e2d3f776da2`.
- Focused workflow blob `fcdbc661a91ef3d6c61011aafa8eb79211b05843`.

Transport commits:

- `ba94808ebee8efe9fb5397c87ea24c07e2b6c379` — producer remediation
- `5d5ad343df0b02965f226996bb924c8d29cff8d3` — dynamic-module registration
- `e60b5c8d74a383c91df1b32536c3047e69f921bf` — nonzero summary fixture
- `c9b20d0707b675c134ce8e6b0e804a115b569ae4` — focused CI gate

## Validation

Focused run `30181818650`, job `89739575951`, conclusion `success`: compilation, focused regressions,
exact-source zero-finding audit and line-length enforcement passed.

Repository-wide run `30181818642`, job `89739575939`, conclusion `failure`:

```text
ruff: All checks passed!
pytest: 42 failed, 775 passed, 1 skipped, 6 warnings in 60.43s
```

Artifact `8625795443`, digest
`sha256:d16b0db6177e79fb30bcc682160d5460c30ea17f685b4a709c454f6c565adafa`.
No candidate test appeared among the failures.

## Decision

The full gate was not bypassed. Producer code was not merged. PR #933 remains draft transport only.
Remote `main` advanced solely with accurate blocker evidence and handoff documentation. Required
resolution is to reconcile the 42 cross-area failures without weakening the gate, update the branch
onto current `main`, rerun both exact-head workflows, merge only after required success, and record
the resulting remote-main SHA.

## Scientific boundary

No ROOT or beam-data input was processed. No weighted profile, covariance, uncertainty, parameter
scan, material/scattering correction, calibration, PID, accepted closure or detector-performance
quantity was generated. `CL-021` remains `FLAWED` under `BLK-MV3-LEGACY-001`.

## Coordination limitation

`SESSION_LOG.md` was not replaced because a byte-safe append was unavailable and the complete
append-only file was exposed only through paged/truncated responses. The missing append is explicit
rather than fabricated.
