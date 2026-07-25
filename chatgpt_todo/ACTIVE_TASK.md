# Active Task

- **Task ID:** AUD-MV3-SEL-001
- **Owner:** scheduled scientific-review session
- **Session stamp:** 2026-07-25T220218Z
- **Initial remote main SHA:** `701116061eb3346a3ae2b31e2946ca450d6120e2`
- **Scope:** independently audit the newly merged MV3 selection-matched stopping-depth
  claim for MC weight semantics, signed-charge handling, comparison estimand, provenance,
  uncertainty, plots, and consistency with canonical `CL-021`.
- **Assumptions:** the repository-specific `PrimaryWeight` stores the generated-source
  cross-section factor; unweighted output may be retained only as a labelled sensitivity.
- **Files under review:** `scripts/studies/mv3_selection_matched.py`, its report/summary/
  figures, `docs/claim_ledger.csv`, `scripts/mc01_trigger_split_truth.py`, the MC-weight
  audit, and the canonical PDG charge helper.
- **Validation plan:** implement a strict UTF-8/content-addressed fail-closed auditor;
  independently reconstruct same-target Pearson comparisons and profile residuals; test
  current-like and corrected contracts, malformed fractions, duplicate claims, invalid
  UTF-8, destructive aliases, and atomic JSON publication; emit JSON/Markdown/SVG evidence.
- **Progress:** ACTIVE. Confirmed that the merged producer reads `PrimaryWeight` but does
  not apply it, defaults invalid weight to 1, uses a positive-charge-only mask, changes the
  data target in its advertised improvement factor, and declares shape agreement while
  Sample-I Pearson chi2/ndf remains about 5590.
- **Acceptance boundary:** this unit may validate an audit gate and blocker record. It may
  not authorize the production claim without a content-addressed weighted signed-charge
  rerun, uncertainty/sensitivity evaluation, regenerated figures, and zero audit findings.
