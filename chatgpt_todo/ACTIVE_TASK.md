# Active Task

- **Task ID:** AUD-ANOM-001 / Chapter 9 source-consistency unit
- **Owner:** scheduled scientific-review session
- **Session stamp:** 2026-07-24T132532Z
- **Initial remote main SHA:** `a4420ed5ecb51074bff68d9e0d2265e6b6bee978`
- **Scope completed in this unit:** reconciled the academic anomaly chapter with the tracked MV6 producer, exact summary, historical report, and exact-width `CL-022` claim.
- **Confirmed defect:** the former chapter described an unsupported 8-PC, 99.7%-variance, K=7 BIC-selected model plus untracked convergence, PC-meaning, alternative-method, manual-review, physical-rate, detector-response, and veto-performance results. The tracked producer uses K=4 on the first four PCs, performs no BIC scan, and records cumulative PCA variance 0.745517570480533 at four PCs and 0.821883926913117 at eight PCs.
- **Source counts:** early peak `283/87555`; C12 share of early peak `156/283`; early-peak rate within C12 `156/7302`; `low_area=0`.
- **Independent calculation:** Wilson 95% intervals are `[0.002877452112691542, 0.003630645177388446]`, `[0.4929885941153212, 0.6081125511627331]`, and `[0.018290520583369645, 0.024940838952822255]`.
- **Implemented files:** corrected `docs/academic_chapters/09_anomaly_id.md`; added `tools/audit/validate_chapter9_mv6_claims.py`, focused tests, and Markdown/JSON/SVG validation evidence.
- **Validation:** changed Python files compiled; focused suite returned `6 passed in 1.15s`; JSON and SVG parsed; exact repository producer/summary/report/ledger blobs were inspected through authenticated GitHub reads.
- **Evidence policy:** `CHAPTER9_MUST_MATCH_TRACKED_MV6_PRODUCER_AND_SUMMARY`.
- **Scientific boundary:** the fixed truth-labelled MC counts and representation contract are source-backed. Beam-data identity, matched transfer, efficiency, false-positive rate, veto impact, and model-systematic uncertainty remain unvalidated.
- **Remaining work:** execute `AUD-ANOM-001` matched data/MC closure; repair malformed `CL-023` and `CL-024` ledger rows from exact PCA source values; inspect Chapter 6 and other public summaries for the superseded 0.89/0.997 representation claims.
- **Status:** VALIDATED for this Chapter 9 correction unit; `AUD-ANOM-001` and ledger-wide `AUD-LEDGER-001` remain PARTIAL.
