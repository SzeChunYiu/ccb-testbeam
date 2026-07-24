# Active Task

- **Task ID:** AUD-G4-021
- **Owner:** scheduled ChatGPT audit session
- **Session stamp:** 2026-07-24T030404Z
- **Initial remote main SHA:** `da94ca3f494b08209ed2d8f1d6d2cdc3ad85ac2c`
- **Validated code/test/evidence head:** `625c38af6380a4950de323779242293331df7972`
- **Scope:** prevent the canonical stopping-power report from overwriting validated simulation/reference inputs or leaving a partial final artifact.
- **Resolved defect:** source blob `360f3e46db664f4eead48021536f210e2f7a85c9` wrote directly through `out_path.open("w")`. Current source blob `043dbd8cae7362dede199b42b28aeb383bccde8d` rejects resolved/same-file aliases, writes a unique same-directory temporary file, flushes and fsyncs it, measures bytes/SHA-256, and publishes with `os.replace`.
- **Validated work:** direct CLI alias regressions; symlink alias regression; injected serialization and replacement failures preserve an existing report and remove temporary files; successful publication reports exact bytes/SHA-256; AST audit returns `VALIDATED`; Markdown/JSON/SVG evidence added.
- **Validation:** focused `py_compile`; `12 passed in 0.07s`; AST audit `VALIDATED`; JSON and SVG parsed; source/test Git blobs match the locally validated files; maximum Python line lengths 91 and 93 characters.
- **Boundary:** no real Geant4 export, accepted projectile-energy-loss closure, uncertainty budget, calibration, or detector-performance result was produced. Full repository pytest, ruff, Geant4/CTest, ROOT processing, and GitHub Actions were not run.
- **Status:** COMPLETE for report publication safety. Broader stopping-power physics remains open under `AUD-G4-005`, `AUD-G4-011`, and `BLK-G4-SP-001`.
