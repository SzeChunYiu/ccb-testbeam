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
- **Scientific assumptions:** NIST PSTAR total mass stopping power is converted
  to MeV/mm with the committed 1.060 g/cm3 density. The plotted Geant4 quantity
  remains a local raw-deposit/track-length proxy, not projectile total energy
  loss. No uncertainty model or acceptance statistic is authorized.
- **Files:** campaign `_common.py`; dedicated VIS-MC-002 renderer; Cluster D run
  script and summary; validator, tests, JSON/SVG/Markdown evidence; coordination
  records and immutable archive.
- **Validation plan:** strict UTF-8 snapshots; canonical parser and 141-row
  reference validation; exact former/current value comparison; py_compile;
  focused pytest; JSON and SVG parsing; line-length check; post-write blob and
  remote-main confirmation.
- **Progress:** implementation and local focused validation complete; direct-main
  publication and final handoff in progress.
- **Focused status:** ACTIVE.
- **Cumulative status:** PARTIAL until immutable external i885 ROOT inputs are
  content-addressed and the canonical plot is regenerated and reviewed.
