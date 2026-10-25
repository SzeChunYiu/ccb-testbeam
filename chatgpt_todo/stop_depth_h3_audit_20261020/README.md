# H3 stopping-depth validity / normalization review — 2026-10-20

**Scientific release: NOT_AUTHORIZED. Issue reporting: NOT_POSTED — GitHub safety checks rejected the attempted #1606 comment.** This is a bounded follow-up to prior closed #1047's H3 conditional-depth correction, not rediscovery of its old all-track denominator error.

Main source: `src/ccb_mc_validation/truth/stop_depth.py` at `a61427813344e29047ca9eb9b764182eb29e4c83`, complete Git blob `ca956eb7d07ea1e8044a61434d0c6bc273fb3736`. The source is included byte-for-byte in `stop_depth_original.py`. The `recheck.py` executable is the exact locally tested blob `0dc1d748e1b36265ad0e24d2d710ab12507c6431`; it intentionally exits 1 when the retained source defects reproduce and exits 2 on source drift/error. Requires NumPy.

**SD-01**: two stopping tracks at layers [1.9,7], weights [1,1], yield unweighted histogram count 2 but weighted histogram mass 0.5 (not 1); mean 4.45 is marked `ok`. A fractional physical layer index must fail closed.

**SD-02**: one stopped track at layer 8 with 8-layer geometry is excluded from histogram but weighted mean 8 and status `ok`; out-of-range depth cannot be accepted as an observed stopping location.

**SD-03**: stop+escape tracks with weights [0,0] return all-zero termination probabilities, sum 0 and no probability estimability status; the normalized measure is undefined. A NaN stop layer under zero weight also escapes validation.

**SD-04**: finite individual weights [1e308,1e308] overflow their total to Inf; termination probabilities become zero rather than 0.5/0.5. This is an arithmetic hostile fixture, not an asserted physical weight range.

Positive controls: well-formed finite integer layers with properly normalized weights follow the earlier H3 conditional-depth contract; negative/nonfinite individual weights, unknown termination and mismatched lengths already fail. Do not weaken the existing controls.

Execution locally on complete source (no stubs): 16 original-source tests passed, 12 separate review-only gate tests passed, both modes repeated under `python -O`; 585 bounded valid small synthetic configurations agreed with an independent `fractions.Fraction` oracle. Three initial harness/candidate expectation bugs were preserved and repaired in the fuller locally produced evidence archive. `recheck.py` and optimized replay generated identical result bytes. The review-only guard is **not** in production.

No real ROOT, Geant4 transport, true track-end/step data, authorizing generator weight law, full CLI/CI, installed hardware or independent human review was executed. All historical numerical impact remains NOT_EVALUATED.

An additional independent source lead: repository instructions point to GitHub `HIBEAM-NNBAR/hibeam_g4`, which currently returns 404; a public GitLab project landing page is at https://git.esss.dk/nnbar-sim/hibeam_g4/-/tree/main. Native `SD_Det` file contents and exact deployed commit could **not** be read here, so no writer schema or physical track chronology is verified.

**Owner action:** post SD-01–04 to #1606, retain #1047's prior fix, require finite integer in-geometry depth for every stopped track regardless of weight, explicit NOT_ESTIMABLE for empty/zero-weight populations, finite/stable aggregates and correctly matched generator-event grouping. Then run original ROOT/Geant4 and propagate actual changed outputs to canonical #1595 ledgers and manuscript figures. A commit alone is NOT a live issue report.
