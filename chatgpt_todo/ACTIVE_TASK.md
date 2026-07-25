# Active Task

- **Task ID:** AUD-CLD-002
- **Owner:** scheduled scientific-review session
- **Session stamp:** 2026-07-25T173220Z
- **Initial remote main SHA:** `64c3841ccb522589e6866d835889e797ea342e24`
- **Scope:** migrate Cluster D VIS-MC-002 from a second embedded coarse PSTAR
  table to the repository's canonical exact-decimal PSTAR parser and committed
  reference bytes; quarantine the historical plot; add a dedicated diagnostic
  renderer, fail-closed regression gate, machine-readable evidence, visual
  evidence, and repository-local handoff.
- **Confirmed defect:** `_common.py` carried a conflicting 20-row reference and
  the historical plot stated that the canonical CSV did not exist. Relative to
  the committed total stopping-power column, the embedded values were high by
  12.22% at 10 MeV, 62.16% at 50 MeV, 80.67% at 100 MeV, and 82.70% at 150 MeV.
- **Validated changes:** removed the embedded table; reused the canonical parser
  and 141-row reference; added fail-closed range checks and provenance; added a
  dedicated ratio-of-sums renderer with sufficient statistics, compensated sums,
  plot hash, no uncertainty evaluation, and no acceptance statistic; migrated
  the reproducer; quarantined the legacy plot; added tests and Markdown/JSON/SVG
  evidence.
- **Validation:** exact canonical reference returned `VALIDATED`; binding audit
  returned zero findings; focused pytest returned `5 passed in 2.08s`;
  py_compile, JSON parse, SVG XML parse, and line-length checks passed; embedded
  table, out-of-range lookup, invalid UTF-8, and destructive alias controls failed
  closed.
- **Unrun checks:** external i885 ROOT regeneration, repository-wide pytest/ruff,
  Geant4 build/CTest, ROOT processing, broad link inventory, and GitHub Actions.
- **Scientific boundary:** local raw deposit per scored track length remains a
  diagnostic proxy, not projectile total energy loss. No uncertainty budget,
  deuteron validation, calibration, or detector-performance result was produced.
- **Immutable record:**
  `chatgpt_todo/archive/2026-07-25T173220Z_AUD-CLD-002_PSTAR_BINDING.md`.
- **Focused status:** VALIDATED.
- **Cumulative status:** PARTIAL until immutable external i885 ROOT inputs are
  content-addressed, the canonical plot is regenerated and reviewed, and
  `BLK-G4-SP-001` is resolved with an accepted observable and uncertainty model.
