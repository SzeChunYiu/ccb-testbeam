# Follow-up for #1628 / #1609 and source PR #1554

Do not promote PID-MC figures or call source tests installed-detector validation. PR #1554 remains separate and unmerged. This audit adds only counterexamples and provenance, not a direct change to its clusterA producer.

1. Freeze actual MC ROOT SHA256 19cd97c1106632e9746dd76a683105186484aa34aa74be8617973072ebcf84ea and obtain eventwise 5,423 OOF truth/score/weight/fold/event records, seed identities and physical group provenance. Without these, corrected actual AUC/AP and uncertainties are NOT_EVALUATED.
2. Apply equal-score-threshold ROC and recall-from-zero AP in the owner branch. Compare exact weighted scores against sklearn ROC/AP and independent positive-negative pair ranking, including adversarial ties, invalid weights and two-class failures.
3. Correct bootstrap last-block omission. Choose physical independent resampling units and the interval target; arbitrary 500-event blocks are not run-level independence. Refit the trained model as needed for whole-procedure uncertainty.
4. Replace the misleading five-fold label with actual nonempty folds [2000,2000,1423]; record empty versus class-undefined folds. Check model calibration by fold and select on training only; conduct untouched independent evaluation.
5. Ablate MC truth entering kinetic energy from predictor features if seeking *detector-observable* PID. Keep energy-dominant secondary truth labels separate from incident beam species.
6. Regenerate ROC/PR, confidence bands, Brier/calibration, slice charts, source tables, strict result JSON, LaTeX, figure registry and #1595 canonical ledgers. Mark old values superseded; no relabeling as beam data.
7. Require separate human detector, transport, statistical and provenance reviews. A single assistant's four perspectives are not independent sign-offs.

Committed remote_smoke.py is a minimal tested source-contract reproducer (six assertions), not a full ROOT or ML run. Full local verification package has 19 passing methods and 1462 small reference cases; preserve first-failed tests. Expected smoke terminal: SCOPED_PASS, NOT SCIENTIFIC RELEASE.
