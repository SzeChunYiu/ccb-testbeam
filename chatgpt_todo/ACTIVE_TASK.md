# Active Task

- **Task ID:** AUD-LEDGER-001 / CL-022 repair unit
- **Owner:** scheduled scientific-review session
- **Session stamp:** 2026-07-24T111232Z
- **Initial remote main SHA:** `5085866208586443d7ccdb9004e6d0898a2d20a0`
- **Scope completed in this unit:** reconstructed malformed claim `CL-022` from the tracked MV6 report and summary, separated the total early-peak rate from C12 class composition and the within-C12 rate, corrected README wording, and updated the exact-match public-claim synchronizer.
- **Source counts:** total early peak `283/87555`; C12 share of early peak `156/283`; early-peak rate within C12 `156/7302`; `low_area=0` in the tracked summary.
- **Independent calculation:** Wilson 95% intervals are `[0.002877452112691542, 0.003630645177388446]`, `[0.4929885941153212, 0.6081125511627331]`, and `[0.018290520583369645, 0.024940838952822255]`, respectively.
- **Implemented files:** repaired `docs/claim_ledger.csv` and `README.md`; updated `scripts/sync_c12_public_claims.py` plus regression; added `tools/audit/validate_claim_ledger_cl022.py`, focused tests, Markdown/JSON/SVG evidence; regenerated the repository-wide schema JSON/SVG.
- **Validation:** exact implementation and synchronizer candidates compiled; focused suites returned `19 passed`; direct validator returned `VALIDATED` with zero issues; former 39-column row failed closed; JSON and SVG artifacts parsed.
- **Evidence policy:** `SEPARATE_EARLY_PEAK_RATE_FROM_C12_COMPOSITION`.
- **Scientific boundary:** this is truth-labelled simulation evidence only. It does not identify the related real-data anomaly as C12 or validate a veto, efficiency, false-positive rate, or detector-performance result.
- **Remaining work:** repair the other 18 malformed ledger rows; execute `AUD-ANOM-001` matched data/MC closure; reconcile Chapter 9's K/PCA/method claims with the tracked MV6 producer and summary.
- **Status:** PARTIAL at ledger-wide scope; the CL-022 reconstruction unit is VALIDATED.
