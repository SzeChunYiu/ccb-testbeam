# AUD-RMAX-001 — Rmax Checker Semantics

## Session

- Stamp: `2026-07-26T200250Z`
- Owner: scheduled scientific-review session
- Initial remote main: `9c576de392c4f81aaea369b4612e16841eeef730`
- Policy: `RMAX_CHECK_MUST_VALIDATE_CLAIM_STATE_AND_NEVER_INFER_RATE_FROM_OCCUPANCY`

## Repository facts inspected

- latest `main` history and concurrent stale-artifact remediation;
- `scripts/check_rmax_formula.py` blob `147a691d9c96aec1f527ad9eb4944b438f3fa0e9`;
- `.github/workflows/thesis_qa.yml` blob `1ff08332c29f095df87a4805658f30f8c373b1cf`;
- `WIKI.md` blob `841222816dc60f5fb90ada51ee027a71e0994254`;
- `docs/claim_ledger.csv` blob `d666d9db6e7026c8d4ba0d69cc1fb301adf5c306`;
- canonical Rmax semantic auditor and coordination files;
- PR #868, which remains closed, unmerged, and non-mergeable.

## Confirmed defects

1. The former gate printed `PASS` and exited 1.
2. It read no claim or public-document evidence.
3. It called 3.05 MHz “measured (occupancy)” despite unresolved rate exposure and `mu_max`.
4. Current WIKI still says `Rmax 2.92 MHz (data-derived, corroborates CL-010 3.05 MHz)` while canonical `CL-010` is value-withheld and `BLOCKED` by `S-STAT-003`.

## Delivered

- evidence-aware fail-closed checker v2.0.0;
- strict single-read UTF-8 snapshots and SHA-256 provenance;
- exact 43-column ledger and unique-claim validation;
- blocked/withheld `CL-010` and exact `CL-011` binding;
- public-WIKI overclaim rejection;
- consistent CLI statuses 0/1/2 and atomic JSON publication;
- seven focused regressions;
- deterministic JSON/SVG evidence and detailed audit report.

## Validation

```text
python -m py_compile \
  scripts/check_rmax_formula.py \
  tests/test_check_rmax_formula.py \
  tools/audit/render_rmax_checker_semantics_evidence.py

PYTHONPATH=. pytest -q tests/test_check_rmax_formula.py
7 passed in 0.04s
```

Current-like control: `FLAWED`, one `WIKI_OVERAUTHORIZES_RMAX` finding, expected CLI status 1. Corrected control: `VALIDATED`, zero findings, expected CLI status 0. JSON and SVG parsing passed; maximum changed Python line length 93.

## Independent calculations

- exact `CL-011` tau: `124.79018394263471 ns`;
- 5% Poisson arithmetic sensitivity: `0.4110362912128549 MHz`;
- legacy `mu=0.38` sensitivity: `3.045111305987686 MHz`;
- 3.05 MHz implied `mu`: `0.3806100610250359`;
- 3.05 MHz implied `P(N>=1)`: `0.31655566074793173`.

These are arithmetic/model sensitivities, not empirical absolute-rate measurements.

## Published identities

- checker blob `188716b5fb3982b32ba90dcb8364922caaf5ac21`;
- focused test blob `80418bf8f728a6aeba8f56bd9620b7e02f8b4d7d`;
- renderer blob `30b7fea934b2381b162a98f155c3ee0dfc39bf23`;
- validation JSON blob `ceff04cc85bde02a7384d90d3587b27dc1d996d5`;
- SVG blob `f3540a2cd81582f023ae55a62345c16b048025e3`.

## Acceptance and blockers

Checker software: `VALIDATED / COMPLETE`. Public claim state: `FLAWED / BLOCKED`. The remediated gate correctly remains nonzero until the stale WIKI sentence is corrected. No live exposure, arrival rate, accepted Rmax, calibration, or detector-performance quantity was produced.

Repository-wide pytest/ruff, the complete Thesis QA workflow, link inventory, and GitHub Actions were not run. `SESSION_LOG.md` and long aggregate ledgers were not partially reconstructed because paged reads plus whole-file replacement could erase append-only provenance.
