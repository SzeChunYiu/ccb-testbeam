# Rmax Checker Semantics Audit

- **Task:** `AUD-RMAX-001`
- **Policy:** `RMAX_CHECK_MUST_VALIDATE_CLAIM_STATE_AND_NEVER_INFER_RATE_FROM_OCCUPANCY`
- **Initial main:** `9c576de392c4f81aaea369b4612e16841eeef730`
- **Scientific acceptance:** `BLOCKED`

## Confirmed defects

The former `scripts/check_rmax_formula.py` printed `PASS` and then exited with status 1 whenever the 5% Poisson formula differed from 3.05 MHz. It did not read either `WIKI.md` or `docs/claim_ledger.csv`, so its message was not evidence-bound. It also described 3.05 MHz as “measured (occupancy),” contradicting the canonical `CL-010` exposure/rate-identifiability blocker.

The inspected WIKI blob `841222816dc60f5fb90ada51ee027a71e0994254` still contains the stale statement `Rmax 2.92 MHz (data-derived, corroborates CL-010 3.05 MHz)`, even though the same document and canonical ledger say the accepted value is withheld under `S-STAT-003`.

## Remediated gate

Checker v2.0.0 now reads WIKI and the claim ledger once as strict UTF-8 bytes, records SHA-256 and byte counts, requires the canonical 43-column ledger schema, requires exactly one `CL-010` and `CL-011`, verifies the blocked/withheld contract, rejects over-authorizing public wording, and publishes optional JSON atomically. It exits 0 only for a consistent blocked claim, 1 for scientific inconsistency, and 2 for malformed inputs.

## Independent arithmetic

Using the exact `CL-011` estimand `124.79018394263471 ns`:

- `-ln(0.95)/tau = 0.4110362912128549 MHz`;
- `0.38/tau = 3.045111305987686 MHz`, a legacy model sensitivity;
- `3.05 MHz` implies `mu = 0.3806100610250359` and `P(N>=1) = 0.31655566074793173`.

None of these arithmetic transformations measures live exposure, event-arrival rate, `mu_max`, or an accepted absolute Rmax.

## Validation

```text
python -m py_compile \
  scripts/check_rmax_formula.py \
  tests/test_check_rmax_formula.py \
  tools/audit/render_rmax_checker_semantics_evidence.py

PYTHONPATH=. pytest -q tests/test_check_rmax_formula.py
7 passed in 0.04s
```

The current-like stale-WIKI fixture returns `FLAWED` with `WIKI_OVERAUTHORIZES_RMAX` and expected CLI status 1. The corrected fixture returns `VALIDATED`, zero findings, and expected CLI status 0. Duplicate claims, invalid UTF-8, and destructive output aliases fail closed. JSON parsing and SVG XML parsing passed.

## Exact identities

- checker blob `188716b5fb3982b32ba90dcb8364922caaf5ac21`, SHA-256 `3f824bfb12609b213b3898c2c3f83d43809580aaae9cb3ac06f06ce4831df721`;
- tests blob `80418bf8f728a6aeba8f56bd9620b7e02f8b4d7d`, SHA-256 `edbbcfc42691496e08ebfba57dc873cbdf7b6a83bc8f23f747089ad4bc612323`;
- renderer blob `30b7fea934b2381b162a98f155c3ee0dfc39bf23`, SHA-256 `9824f275e640bb393c1d69451536d2fe453a5753928fb9e296db51c8f20407ad`.

## Acceptance boundary

The checker software remediation is validated. The repository public state remains flawed because WIKI still contains the stale numerical Rmax endorsement; the remediated Thesis QA gate should fail until that exact statement is corrected. No absolute rate or detector-performance quantity was accepted.
