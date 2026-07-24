# Active Task

- **Task ID:** AUD-G4-021
- **Owner:** scheduled ChatGPT audit session
- **Session stamp:** 2026-07-24T020230Z
- **Initial remote main SHA:** `cdaf032c13f9967ad2a02c420987058b8a57a61b`
- **Validated audit/test/evidence head:** `ef388f3fc90e8d81804d277dbbe7840ae4ae4a27`
- **Latest coordination head before archive:** `6e10c2e0f3364fada18a3bf4ea939ad9a7b6fa29`
- **Scope:** determine whether the canonical stopping-power report can overwrite its validated simulation/reference inputs or leave a partial final artifact.
- **Confirmed defect:** source blob `360f3e46db664f4eead48021536f210e2f7a85c9` writes directly through `out_path.open("w")`, with no explicit output/input alias rejection and no atomic replacement.
- **Validated work:** AST audit v1.0.0; five focused synthetic regressions; Markdown/JSON/SVG evidence; master index, backlog, code-result map, study ledger, claim matrix, visualization matrix, and blocker register updated.
- **Validation:** focused `py_compile`; `5 passed in 1.63s`; JSON and SVG parsed; maximum Python line lengths were 91 and 92 characters.
- **Boundary:** exact repository source was inspected through complete authenticated GitHub ranges, but the exact full source was not executed locally. No real Geant4 export, stopping-power closure, uncertainty budget, calibration, or detector-performance result was produced.
- **Status:** PARTIAL. The flaw and remediation contract are validated; the canonical reporter remains unchanged under `BLK-G4-SP-004`.
