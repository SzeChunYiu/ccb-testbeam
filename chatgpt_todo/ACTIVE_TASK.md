# Active Task

- **Task ID:** `AUD-RMAX-001`
- **Owner:** scheduled scientific-review session
- **Session stamp:** `2026-07-26T200250Z`
- **Initial remote main SHA:** `9c576de392c4f81aaea369b4612e16841eeef730`
- **Policy:** `RMAX_CHECK_MUST_VALIDATE_CLAIM_STATE_AND_NEVER_INFER_RATE_FROM_OCCUPANCY`.
- **Delivered:** evidence-aware checker v2.0.0; strict single-read WIKI/ledger provenance; canonical 43-column and unique-claim validation; blocked `CL-010` and exact `CL-011` binding; public overclaim rejection; consistent CLI status 0/1/2; atomic JSON publication; seven regressions; JSON/SVG evidence; detailed audit and immutable archive.
- **Confirmed current flaw:** WIKI blob `841222816dc60f5fb90ada51ee027a71e0994254` still says `Rmax 2.92 MHz (data-derived, corroborates CL-010 3.05 MHz)`. The remediated checker correctly returns nonzero until that public sentence is corrected.
- **Independent calculations:** 5% Poisson sensitivity `0.4110362912128549 MHz`; legacy `mu=0.38` sensitivity `3.045111305987686 MHz`; 3.05 MHz implies `mu=0.3806100610250359` and `P(N>=1)=0.31655566074793173`.
- **Validation:** `py_compile` passed; focused pytest `7 passed in 0.04s`; current-like fixture `FLAWED` with one `WIKI_OVERAUTHORIZES_RMAX`; corrected fixture `VALIDATED` with zero findings; JSON/SVG parsing passed; maximum changed Python line length 93.
- **Remote blobs:** checker `188716b5fb3982b32ba90dcb8364922caaf5ac21`; tests `80418bf8f728a6aeba8f56bd9620b7e02f8b4d7d`; renderer `30b7fea934b2381b162a98f155c3ee0dfc39bf23`; validation JSON `ceff04cc85bde02a7384d90d3587b27dc1d996d5`; SVG `f3540a2cd81582f023ae55a62345c16b048025e3`.
- **Scientific boundary:** no live exposure, event-arrival rate, `mu_max`, recovery-failure ceiling, accepted absolute Rmax, calibration, or detector-performance quantity was produced.
- **Unrun:** repository-wide pytest/ruff, complete Thesis QA workflow, link inventory, GitHub Actions.
- **Archive:** `chatgpt_todo/archive/2026-07-26T200250Z_AUD-RMAX-001_CHECKER_SEMANTICS.md`.
- **Acceptance:** checker software `VALIDATED / COMPLETE`; public WIKI claim state `FLAWED / BLOCKED`.
- **Next:** correct the exact stale WIKI sentence, run `python scripts/check_rmax_formula.py`, and require status 0 before treating Thesis QA as green.
- **Status:** `PARTIAL`
