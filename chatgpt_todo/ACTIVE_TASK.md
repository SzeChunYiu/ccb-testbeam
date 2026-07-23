# Active Task

- **Task ID:** AUD-I885-001
- **Owner:** scheduled ChatGPT audit session
- **Session stamp:** 2026-07-23T13:21:12Z
- **Initial main SHA:** `2986da32c6b01d6f3f1b6ec90231ab5eeee436b1`
- **Implementation/evidence head:** `467c007cd3526a762258a7f1d3f00563a37db8a8`
- **Scope:** independently review the merged issue #885 proton/deuteron calibration campaign, its manifest, partial outputs, coverage wording, fit statistics, plots, and acceptance claims.
- **Confirmed defects:** the summary used 72 total campaign files as the main-grid denominator; it collapsed unequal proton/deuteron energy coverage; the plotter displayed seed-averaged points but fitted per-seed rows; fit `n` counted files rather than independent energies; the deuteron line used only two independent energies and therefore has zero residual degrees of freedom after seed averaging.
- **Validated change:** added a strict campaign-result validator with input hashes and focused tests; corrected the committed summary; quarantined P5/P5b and fit claims; added Markdown/JSON/SVG evidence.
- **Files:** `tools/audit/validate_i885_campaign_results.py`, `tests/test_validate_i885_campaign_results.py`, `geant4/single_stave/results/i885_v1/{SUMMARY.md,AUDIT_INVALIDATION.md}`, and `docs/validation/i885_campaign_acceptance_*`.
- **Commands:** `python -m py_compile`; focused `pytest`; validator runs against exact reconstructed manifest/CSV/fits/summary; JSON and SVG parse checks; Git blob hash comparisons.
- **Validation:** focused tests returned `4 passed`; exact pre-correction bundle returned `FLAWED`, 20 issues and one partial-coverage warning; corrected-summary bundle returned `FLAWED`, 18 fit issues and one warning; measured coverage is 14/72 total files, 14/40 main-grid files, and 7/20 independent main-grid energy points.
- **Boundary:** no Geant4 job or ROOT file was rerun. Per-file means remain partial simulation outputs. Calibration slopes, R² values, and P5/P5b remain quarantined until the generator seed-averages before fitting, records independent counts, requires at least three energies, and regenerates the bundle.
- **Status:** COMPLETE for independent validation, coverage correction, quarantine, evidence, and direct-to-main delivery; PARTIAL for corrected campaign generation and scientific calibration acceptance.
