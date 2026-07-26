# AUD-MV3-SEL-003 — Pearson producer remediation and CI blocker

- **Session:** `2026-07-26T002131Z`
- **Owner:** scheduled scientific-review session
- **Initial remote main:** `54a899d82c1991747218a5b3a5a0835c51991420`
- **Task:** `AUD-MV3-SEL-003`
- **Status:** `PARTIAL / BLOCKED`
- **Transport PR:** `#933`
- **Validated implementation head:** `c9b20d0707b675c134ce8e6b0e804a115b569ae4`
- **Remote-main delivery:** not completed

## Repository and coordination review

Fetched the current repository, latest `main` history, PR inventory, PR #868, CI workflow,
`chatgpt_todo/README.md`, `ACTIVE_TASK.md`, `HANDOFF.md`, `BACKLOG.md`, `BLOCKERS.md`, and available
`SESSION_LOG.md` ranges. No other open pull request existed when the task was selected. PR #868
remained closed, unmerged and non-mergeable and was not changed.

## Defect

The weighted MV3 producer used `expected > 0` to mask Pearson categories. It returned a finite
`chi2/ndf=1.0` after omitting ten observed B6 counts assigned zero model probability. It separately
accepted a model profile summing to `0.95` and returned `chi2/ndf=2.5`.

## Work performed

- Preserved the former weighted producer body as exact internal blob
  `cd787ab64408228d67536b88bcc617fe32d0ec5a`.
- Added canonical front-door blob `91dc6d21e6c5ffa83fada4210456157d3bbee322`.
- Added direct producer/audit tests, final blob
  `92c28df965d544d3c0b3ce5de36681e3a029f0e7`.
- Corrected the existing dynamic-module test loader after CI demonstrated a Python 3.11 dataclass
  collection failure; corrected blob `701d85489c7f1bda832103ce6c7b6e2d3f776da2`.
- Added path-scoped focused workflow blob `fcdbc661a91ef3d6c61011aafa8eb79211b05843`.
- Produced machine-readable, visual and narrative evidence.

Transport commits:

- `ba94808ebee8efe9fb5397c87ea24c07e2b6c379` — producer remediation
- `5d5ad343df0b02965f226996bb924c8d29cff8d3` — dynamic-module registration fix
- `e60b5c8d74a383c91df1b32536c3047e69f921bf` — nonzero summary fixture
- `c9b20d0707b675c134ce8e6b0e804a115b569ae4` — focused CI gate

## Validation

Focused run `30181818650`, job `89739575951`, conclusion `success`:

- compilation succeeded;
- focused Pearson/producer/audit regressions succeeded;
- exact-source audit returned zero findings;
- focused line-length gate succeeded.

Repository-wide run `30181818642`, job `89739575939`, conclusion `failure`:

- ruff: `All checks passed!`;
- pytest: `42 failed, 775 passed, 1 skipped, 6 warnings in 60.43s`;
- artifact `8625795443`;
- artifact digest
  `sha256:d16b0db6177e79fb30bcc682160d5460c30ea17f685b4a709c454f6c565adafa`;
- no candidate test appeared among the 42 failures.

Earlier diagnostic runs were retained:

- run `30181409691` exposed an existing dataclass dynamic-loader collection error;
- run `30181512678` gave `43 failed, 774 passed, 1 skipped`, including one candidate fixture error;
- both demonstrated defects were fixed before the final candidate head.

## Decision and blocker

The full repository validation gate remained failed. No merge was attempted, and no candidate code
was written to `main`. PR #933 remains transport only. Required resolution is to reconcile the
42 cross-area baseline failures or establish and approve a repository-level baseline policy without
weakening the scientific gate; then rerun both workflows on the exact updated candidate and merge
only after required checks pass.

## Scientific boundary

No ROOT or beam-data input was processed. No weighted profile, covariance, uncertainty, parameter
scan, material/scattering correction, calibration, PID, accepted closure or detector-performance
quantity was generated. `CL-021` remains `FLAWED` under `BLK-MV3-LEGACY-001`.

## Coordination limitation

`SESSION_LOG.md` was read through paged connector responses but was not replaced. The connector
requires whole-file replacement and did not expose a byte-safe append primitive; replacing a
partially reconstructed append-only log risked destroying provenance. This unmet requirement is
recorded explicitly rather than being fabricated.
