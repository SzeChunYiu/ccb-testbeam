# Scientific Figure Standard

Parent issues: #1597, #1601, #1613. A figure is scientific evidence only when its underlying numerical atom/claim is itself auditable. Visual quality never upgrades evidence class.

## Required context for claim-authorizing figures

Every evidence figure must expose, in the panel/caption or bound sidecar:

- figure ID and bound claim ID(s);
- evidence class: `DATA_MEASUREMENT`, `MC_METHOD_CLOSURE`, `TRUTH_LEVEL_MC_ONLY`, `DETECTOR_MODEL_PREDICTION`, `VALIDATED_TRANSFER`, `EXTERNAL_REFERENCE`, or `DIAGNOSTIC`;
- exact source artifact(s) and SHA-256;
- generator script, config and commit;
- x/y physical quantities and units;
- selection/cuts and sample definition;
- `N` or denominator for efficiencies/fractions/rates;
- uncertainty model and confidence/credible interval definition;
- normalization definition for histograms/densities;
- fit model/domain and goodness-of-fit when a fit supports interpretation;
- data/MC/truth distinction;
- status (`SUPPORTED`, `CONDITIONAL`, `GATED`, `BLOCKED`, `DIAGNOSTIC`, etc.).

## Plot-type requirements

### Data versus MC

Show the two samples with their uncertainties and, where meaningful, a ratio or residual/pull panel. State normalization and matched-selection definition. A shape comparison without matched trigger/selection/acceptance cannot authorize a closure claim.

### Fits/calibrations

Show the fit domain, uncertainty, residuals and a quantitative goodness-of-fit diagnostic. High `R²` alone is not an acceptance test. Report rejected fits rather than hiding them.

### Timing

State the residual definition and reference clock/truth. Show robust width plus tails/RMS or distributional diagnostics. For combined channels, expose covariance assumptions or the measured covariance matrix.

### Efficiencies/fractions/rates

Show numerator/denominator, interval method and operational criterion. Never label a nearest scan point as an exact threshold crossing. Distinguish beam duty factor, Poisson overlap probability, quality gate and detector throughput.

### ROC/PID/ML

Identify truth/label source, split unit and final validation set. Include uncertainty/slice behavior where relevant. A truth-level ROC must be visibly labeled as simulation truth.

### Energy/stopping/DeltaE-E

State ADC versus energy units explicitly. Never relabel an uncalibrated ADC quantity as MeV. For data/MC depth comparisons, show selection matching and systematic-model limitations.

## Visual integrity rules

- Do not truncate axes in a way that exaggerates effects without explicit visual notice.
- Do not smooth or interpolate in a way that creates apparent resolution not present in source data.
- Use bin widths appropriate to detector/sample resolution and include binning sensitivity when conclusions depend on it.
- Distinguish counts from probability density; label normalization.
- Keep error bars/bands visible and interpretable.
- Avoid categorical points connected by lines when no continuous ordering exists.
- Captions must state what would falsify the interpretation, not only the preferred story.

## Provenance sidecar

Claim-authorizing figures should carry a JSON sidecar conforming to `docs/contracts/SCIENTIFIC_FIGURE_SIDECAR.schema.json`. The figure ledger may remain `REVIEW/GATED/BLOCKED` without complete sidecar fields, but `SUPPORTED/VALIDATED` promotion is fail-closed in `scripts/check_scientific_promotion_rules.py`.

## Regeneration order

Do not regenerate a polished publication figure before the underlying numerical atom is resolved. First fix/recompute the analysis, then machine-readable result, then figure, then WIKI/paper caption. If the analysis is blocked, produce only clearly labeled `DIAGNOSTIC` visualizations.
