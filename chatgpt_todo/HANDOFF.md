# Latest Handoff

## Session

- **Task:** `AUD-MV3-SEL-003`
- **Stamp:** `2026-07-26T002131Z`
- **Initial remote main:** `54a899d82c1991747218a5b3a5a0835c51991420`
- **Remote main after run:** unchanged at the initial SHA when last checked
- **Transport PR:** `#933`
- **Transport branch:** `chatgpt/AUD-MV3-SEL-003-chi2-remediation-20260726T002131Z`
- **Validated implementation head:** `c9b20d0707b675c134ce8e6b0e804a115b569ae4`
- **Delivery:** `BLOCKED_NOT_ON_MAIN`
- **Acceptance:** focused producer/statistical contract `VALIDATED`; repository-wide integration gate
  `FAILED`; production result and canonical closure `BLOCKED/PARTIAL`.

## Start-of-run review

Fetched current `main`, recent history, open PRs, PR #868, workflow configuration, producer, audit,
focused tests, and mandatory coordination records. No open pull request existed at task selection.
PR #868 remained closed, unmerged and non-mergeable and was not changed.

## Confirmed defect

Former producer blob `cd787ab64408228d67536b88bcc617fe32d0ec5a` masked every zero-expected
category before summing Pearson terms. It therefore returned finite `chi2/ndf=1.0` after discarding
ten observed B6 counts assigned zero model probability. It also accepted model fractions summing to
`0.95` and returned `chi2/ndf=2.5`.

Policy:

`PEARSON_CHI2_MUST_REJECT_OUT_OF_SUPPORT_DATA_AND_NONUNIT_PROFILES`

## Candidate work

- Canonical front-door blob: `91dc6d21e6c5ffa83fada4210456157d3bbee322`
- Preserved implementation blob: `cd787ab64408228d67536b88bcc617fe32d0ec5a`
- Direct producer-test blob: `92c28df965d544d3c0b3ce5de36681e3a029f0e7`
- Focused workflow blob: `fcdbc661a91ef3d6c61011aafa8eb79211b05843`
- Existing dynamic-loader fix blob: `701d85489c7f1bda832103ce6c7b6e2d3f776da2`

Candidate commits:

- `ba94808ebee8efe9fb5397c87ea24c07e2b6c379` — strict producer front door and tests
- `5d5ad343df0b02965f226996bb924c8d29cff8d3` — dynamic-module registration fix
- `e60b5c8d74a383c91df1b32536c3047e69f921bf` — nonzero summary fixture
- `c9b20d0707b675c134ce8e6b0e804a115b569ae4` — focused Pearson CI gate

The corrected contract requires exact categories, finite nonnegative inputs, model normalization
within `1e-12`, positive observations, rejection of observed mass outside model support, supported-bin
ndf and `math.fsum`. Generated summaries record both executable source snapshots and full SHA-256.

## Validation

Focused workflow run `30181818650`, job `89739575951`, concluded `success`. Compilation, focused
producer/audit tests, exact-source zero-finding audit and the focused 100-character line gate all
passed.

Repository-wide workflow run `30181818642`, job `89739575939`, concluded `failure`:

```text
ruff: All checks passed!
pytest: 42 failed, 775 passed, 1 skipped, 6 warnings in 60.43s
```

Artifact: `8625795443`

Artifact digest:

`sha256:d16b0db6177e79fb30bcc682160d5460c30ea17f685b4a709c454f6c565adafa`

No candidate test was present in the failure list. The failures span pre-existing cross-area contracts,
including stopping-power parsing/reporting, figure registry, claim governance, PCA summaries and
public WIKI synchronization.

## Delivery decision

The failed repository-wide gate was not bypassed. PR #933 was not merged, no candidate commit was
pushed to `main`, and no delivery to remote `main` is claimed. The PR remains transport only until
the 42 failures are reconciled and both workflows pass on the exact updated candidate.

## Evidence

- `docs/validation/mv3_chi2_producer_remediation_validation.json`
- `docs/validation/mv3_chi2_producer_remediation.svg`
- `docs/validation/mv3_chi2_producer_remediation_audit.md`
- `chatgpt_todo/archive/2026-07-26T002131Z_AUD-MV3-SEL-003_CHI2_REMEDIATION_BLOCKED.md`

## Scientific boundary

No production ROOT or beam-data file was rerun. No weighted stopping profile, covariance,
preregistered sensitivity scan, material/scattering correction, calibration, PID result, closure
claim or detector-performance result was produced. Canonical `CL-021` remains `FLAWED` under
`BLK-MV3-LEGACY-001`.

## Coordination limitation

`SESSION_LOG.md` was not appended. The connector exposes whole-file replacement rather than a
byte-safe append, while the complete append-only file was available only through paged/truncated
responses. Replacing a partial reconstruction could erase provenance. This mandatory step remains
explicitly unmet rather than being fabricated.
