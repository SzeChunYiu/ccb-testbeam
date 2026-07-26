# Latest Handoff

## Session

- **Task ID:** `AUD-RMAX-001`
- **Stamp:** `2026-07-26T200250Z`
- **Owner:** scheduled scientific-review session
- **Initial remote main:** `9c576de392c4f81aaea369b4612e16841eeef730`
- **Validated implementation/evidence/archive/active-task head:** `1fb4f7e5cbcff6299485edc731cf50002044e133`
- **Destination:** authenticated sequential commits directly to `main`; no force-push, transport branch, pull-request merge, or history rewrite.
- **Push result:** every GitHub contents write returned a successful commit SHA; post-write history showed the complete focused sequence on remote `main`.
- **Acceptance:** checker software `VALIDATED / COMPLETE`; public WIKI claim state `FLAWED / BLOCKED`.

## Defect and policy

Policy: `RMAX_CHECK_MUST_VALIDATE_CLAIM_STATE_AND_NEVER_INFER_RATE_FROM_OCCUPANCY`.

The former Thesis QA checker printed `PASS` and then exited with status 1. It did not read `WIKI.md` or `docs/claim_ledger.csv`, and it called 3.05 MHz “measured (occupancy)” despite the unresolved exposure/rate-identifiability boundary.

Current WIKI blob `841222816dc60f5fb90ada51ee027a71e0994254` still contains `Rmax 2.92 MHz (data-derived, corroborates CL-010 3.05 MHz)`, while canonical `CL-010` is value-withheld, `BLOCKED`, and blocked by `S-STAT-003`.

## Remediation

Checker v2.0.0 now:

- reads WIKI and ledger exactly once as strict UTF-8 bytes;
- records byte counts, SHA-256, and snapshot method;
- enforces the exact 43-column ledger schema and unique `CL-010`/`CL-011` rows;
- verifies the blocked/withheld `CL-010` contract and exact `CL-011` live-time estimand;
- rejects stale public numerical Rmax endorsements;
- labels all calculated rates as arithmetic/model sensitivities;
- exits 0 only for a consistent blocked claim, 1 for scientific inconsistency, and 2 for malformed inputs;
- atomically publishes optional JSON and rejects destructive aliases.

## Independent calculations

Using `tau = 124.79018394263471 ns`:

- 5% Poisson arithmetic sensitivity: `0.4110362912128549 MHz`;
- legacy `mu=0.38` sensitivity: `3.045111305987686 MHz`;
- 3.05 MHz implies `mu=0.3806100610250359`;
- 3.05 MHz implies `P(N>=1)=0.31655566074793173`.

These calculations do not measure live exposure, event-arrival rate, `mu_max`, or an accepted absolute Rmax.

## Validation

```text
python -m py_compile \
  scripts/check_rmax_formula.py \
  tests/test_check_rmax_formula.py \
  tools/audit/render_rmax_checker_semantics_evidence.py

PYTHONPATH=. pytest -q tests/test_check_rmax_formula.py
7 passed in 0.04s
```

Current-like stale-WIKI fixture: `FLAWED`, one `WIKI_OVERAUTHORIZES_RMAX` finding, expected CLI status 1. Corrected fixture: `VALIDATED`, zero findings, expected CLI status 0. Duplicate claims, invalid UTF-8, and output aliasing fail closed. JSON and SVG parsing passed; maximum changed Python line length 93.

## Files and identities

- `scripts/check_rmax_formula.py` — blob `188716b5fb3982b32ba90dcb8364922caaf5ac21`, SHA-256 `3f824bfb12609b213b3898c2c3f83d43809580aaae9cb3ac06f06ce4831df721`
- `tests/test_check_rmax_formula.py` — blob `80418bf8f728a6aeba8f56bd9620b7e02f8b4d7d`, SHA-256 `edbbcfc42691496e08ebfba57dc873cbdf7b6a83bc8f23f747089ad4bc612323`
- `tools/audit/render_rmax_checker_semantics_evidence.py` — blob `30b7fea934b2381b162a98f155c3ee0dfc39bf23`, SHA-256 `9824f275e640bb393c1d69451536d2fe453a5753928fb9e296db51c8f20407ad`
- `docs/validation/rmax_checker_semantics_validation.json` — blob `ceff04cc85bde02a7384d90d3587b27dc1d996d5`
- `docs/validation/rmax_checker_semantics.svg` — blob `f3540a2cd81582f023ae55a62345c16b048025e3`
- immutable record: `chatgpt_todo/archive/2026-07-26T200250Z_AUD-RMAX-001_CHECKER_SEMANTICS.md`

## Direct-main sequence

- `e4729b1f8cc3c328c8a6d4abfbdde50b99f3e56a` — task claim
- `05b5fda18cfce54bd661e7f26ed18d82fc7156d3` — checker remediation
- `d46da566f62a93aec5c62e452a7132f32b4347f6` — focused regressions
- `21b8f6813468b1aa54095918b2b1033e8edefcc7` — evidence renderer
- `89ffcbc22d707adcfb45cf7bcfc8b1601e69073e` — JSON evidence
- `782e29e408a742045cb4fd9349c7cfaa2cff262e` — SVG evidence
- `98d7286fc2e0c2ca7105caf47654b207197729d4` — audit report
- `82ba886378f437f7fc53f0ca01f666eec4e046b9` — immutable archive
- `1fb4f7e5cbcff6299485edc731cf50002044e133` — active-task completion

## Scientific boundary and next action

No live exposure, absolute event rate, `mu_max`, recovery-failure ceiling, accepted Rmax, calibration, or detector-performance quantity was produced. Repository-wide pytest/ruff, the complete Thesis QA workflow, link inventory, and GitHub Actions were not run.

The remediated gate is expected to remain nonzero on current `main` because the WIKI sentence is still scientifically inconsistent. Correct that exact sentence, then require `python scripts/check_rmax_formula.py` to return 0 before treating Thesis QA as green.

PR #868 remains closed, unmerged, and non-mergeable. `SESSION_LOG.md`, `BACKLOG.md`, `MASTER_INDEX.md`, and long aggregate matrices were reviewed but not partially rewritten: connector reads are paged while updates replace complete files, and transcription could erase append-only provenance. The immutable archive retains the append-equivalent record.
