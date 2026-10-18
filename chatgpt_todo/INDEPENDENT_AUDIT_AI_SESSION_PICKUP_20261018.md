# Independent scientific audit — persistent AI/human pickup protocol

**Start here:** https://github.com/SzeChunYiu/ccb-testbeam/issues/1628  
**Legacy master, never supersede silently:** #1594  
**Repository baseline surveyed:** main@a61427813344e29047ca9eb9b764182eb29e4c83 on 2026-10-18  
**Immediate documents:** OPEN_ISSUE_SCIENTIFIC_CLOSURE_MATRIX_20261018.csv and INDEPENDENT_PHYSICS_REVIEW_FINDINGS_20261018.md  
**Shared audit implementation already under construction:** PR #1595 on audit/global-number-census-20260817 (not main at snapshot)

## Initial state and safety

- This is a *handoff and test plan*, not a claim that the full codebase, raw archive, Geant4 campaign or published physics is verified. All 25 original issue rows remain OPEN pending their respective evidence-based criteria. Supervisor issue #1628 is additional.
- Do not overwrite or fork competing numerical/physics/figure ledgers: #1595 introduces NUMBER_AUDIT_LEDGER.csv, PHYSICS_JUSTIFICATION_LEDGER.csv, FIGURE_AUDIT_LEDGER.csv, ML_VALIDATION_LEDGER.csv, REDO_QUEUE.csv, SCIENTIFIC_REVIEW_PROTOCOL.md and governance workflow. First reconcile and extend them on a conflict-free integration branch.
- Before taking a task, inspect exact main SHA, open issue/PR status, dependent branches, active task ownership and last authorizing evidence. Never rely on the older 2026-08-17 timestamp to infer merge state.
- Failed data inputs, missing hardware measurements, absent untouched validation, or uncompiled MC => BLOCKED or DIAGNOSTIC; do not invent a physics constant, event count, error bar, proof, bench result, or simulation output.
- Preserve audit findings separately from *published detector measurements*. The scientific acceptance class is separate from software-test pass/fail.

## Resume loop — repeat for every finding until closure

1. **Reconcile work queue.** Refresh #1628 and 25 linked issues; enumerate actual current PRs plus local experiment task owner. Take the highest-priority unblocked physical atom with no conflicting in-progress owner. Add new issues to matrix with unique ID and parent if the original 25 have grown.
2. **Define one falsifiable assertion.** Name measurable quantity and mathematical definition, units/reference frame/sign, expected domain and source, data/MC/truth class, exact previously published claim/consumer, and a *physical counterexample* that would make the conclusion invalid. Link all parent/descendant atoms.
3. **Separate reviewing roles.** A detector/DAQ, B nuclear/Geant4/optical, C statistics/ML, D code/provenance. Record explicit skeptical findings from each relevant role. If using one AI session as several roles, do NOT falsely call that independent empirical replication.
4. **Freeze configuration before validation.** Snapshot git superproject/submodules, executable binary and build receipt, raw ROOT source hashes/event schema/channel length, scripts/configs/env, complete selection and run IDs, physical constants, random seeds, simulation physics list/cuts, energy/angle/source measure and result directory. Create a failing negative fixture before implementing a fix.
5. **Run RED→GREEN and independent recomputation.** Test wrong frame width, inverted pulses, join duplicates, trigger migration, bad event weights, energy nonconservation, malformed model covariance, time-cut mismatch, ML truth leakage, incorrect sampling unit and stale public claim, as applicable. Check exact negative exit and appropriate quarantining. Then rerun actual physics on a data- and compute-capable host, not just synthetic fixtures.
6. **Quantify real coverage.** Give denominator, independent unit (run/event/source seed), point estimate and interval, correlated nuisance terms, sensitivity envelope, domain of applicability, held-out validation and physical baseline. Failure to measure is NOT_EVALUATED rather than a made-up 0 or ± estimate.
7. **Write a source-bound receipt.** Versioned atom+claim IDs, objective, raw+config+producer+runtime SHA, full command, exact N/selection and event key, physics equation/reference, observed code/test result, uncertainty/negative controls, reviewer verdict and vetoes, outputs and source artifact hash; include all affected results, figures, WIKI and PR/issue links.
8. **Propagate invalidation.** If an upstream atom is FLAWED, UNJUSTIFIED or materially changed, mechanically quarantine every transitive descendant until it is redone or source-demonstrated independent. Preserve old headlines as SUPERSEDED/HISTORICAL, never overwrite silently.
9. **Only then mark done.** Link concrete committed evidence and exact executed CI/test/simulation receipts in the owning original issue **and** #1628. A status word in an issue or prior PR body alone does not justify a green box. Require independent reviewers and unmet-external-data disclosure.
10. **Re-scan and repeat.** Audit all directories and wiki/publication after each update. Keep pending backlog and reviewer disagreements, not just successes.

## Short highest-priority queue, executable where data availability permits

| Rank | Issue(s) | First actionable test | Success evidence or blocker |
| --- | --- | --- | --- |
| 1 | #1607/#1594/#1616 | Exercise a contradictory Rmax ledger through main v2 checker: currently emits PASS on FLAWED; review PR #1595 fixed implementation and ensure hostile nonzero test after merge | CI run and fixture prove fail closed; published Rmax remains BLOCKED |
| 2 | #1603/#1617 | Verify exact 144-word 8x18 per-event ROOT and source-bound polarity; reject known-bad 128-word staging | Signed amplitude and run/stave count independent reproduction; external raw/hardware evidence required |
| 3 | #1045/#1608 | Reproduce claimed 554/1M proxy vs 0/1M modeled T1&T2 scenario, then survey-bound geometry counterfactuals, trigger thresholds and migration | Raw simulation/runtime provenance and matched data trigger; external hardware geometry |
| 4 | #1608/#1602/#1091 | Source theta/phi/weights and G4 kinetic-energy conservation; proton stopping-vs-edep; optical response and neutron time cut | Physics fixtures, executable receipts and nuisance scans |
| 5 | #1609/#1605/#1606 | Validate sample-group/clock/reference, data waveform semantics, truth-free ML targets, untouched run split | No selected model refit on final holdout; uncertainty and covariance coverage |
| 6 | #1592/#1597/#1611/#1598 | Fail A09 placeholder yerr; rewrite source-bound figure and strict WIKI claim checks | Real uncertainty per plotted point, ledger-to-caption binding, complete no-overclaim release gate |

## Physical and logical invariants for hostile controls

- **DAQ:** each event's raw word count and ordering exact (8x18=144 when source-bound); no reshape of truncated 128. Same run-event ID cannot multiply unexpectedly on event joins. Selection counts by independent decoder, not by hardcoded expected cardinality.
- **Pulse amplitude:** corrected voltage/ADC y_c,s = signed_polarity[c]*(raw_c,s - baseline_c); authorizing polarity is external measurement, not the outcome of the same analysis. Unknown => reject physical use. An isolated single-sample glitch filter must have pulse-preservation sensitivity tests, not assumed perfection.
- **Timing:** res=t_rec−t_ref (or explicitly opposite); E[res] bias and sigma68/RMS/tails; Var(t1−t2)=Var(t1)+Var(t2)−2Cov(t1,t2); covariance from independent run/clock anchors. A 10-ns sampled waveform does not by itself define an absolute timing resolution.
- **Energy:** E_kin(projectile) != E_lost(projectile) != E_dep(scintillator) != E_vis(Birks) != digitized ADC. Reject proton PSTAR evaluated at E_d/2 as *direct deuteron* standard. Check total energy budget, escaping secondaries, geometry and step sensitivity.
- **Source:** if generating directly with PDF proportional to (dσ/dΩ)*sin(theta_CM), event weight must not repeat the same density. Measured angular table support is not physical zero outside support; publish boundary policy and model sensitivity. Four-momentum conservation and angle Jacobian are adversarial fixtures.
- **Trigger:** true hardware logic, threshold, coincidence time and material != first-HRD-layer charged hit proxy without quantitative demonstrated equivalence; record migration by species/energy/angle/multiplicity and historical run conditions.
- **Rate:** stationary Poisson window P>=1=1−e^(−r tau) is conditional; occupancy cannot establish absolute beam rate without known exposure/deadtime and window definition. No unique Rmax without preregistered quality criterion.
- **Statistics:** if N pulses share a run/clock calibration, N pulses may not represent N independent observations. Keep physical cluster/seed/run level, model-selection multiplicity, label independence and final never-used test set.
- **MC:** expected numerical agreement under shared simulated assumptions is method closure, not hardware validation. Geant4 runtime cut/physics list, source/model bytes, optical physics and digitizer parameters must be captured at execution.
- **Publication:** any unclassified, blocked or superseded upstream dependency prevents a claim from being promoted; missing uncertainty is not zero error.

## Planned in-repository deliverables and issue linkage

Use the existing #1595 audit schemas for atom, numerical, physics, figure, ML and redo ledgers. Add fields only with schema migrations and validator tests. Link generated scientific graphs and WIKI text to canonical claim IDs. Add an issue-checkbox-to-evidence-commit synchronization regression (#1616), a dependency invalidation test, and a publication figure zero-error rejection test.

**Expected evidence classes:** DATA_MEASUREMENT (real, calibrated), TRUTH_LEVEL_MC_ONLY, MC_METHOD_CLOSURE, DETECTOR_MODEL_PREDICTION, VALIDATED_TRANSFER only after independent experiment transfer; plus CONDITIONAL, GATED, BLOCKED, FLAWED, SUPERSEDED/DIAGNOSTIC as lifecycle states. An issue being closed in GitHub does not convert MC evidence into measured performance.

**Close #1628 only when:** every original and newly discovered scientific atom has a disposition; all physically promoted claims are independently reproduced, reference/condition/covariance-verified, and fully traceable to authorized inputs; no contradictory hardware or trigger model remains under an accepted result; all relevant reruns and figures regenerated; wiki publication gate tested fail-closed; and an independent reviewer signs the release manifest. External evidence may leave some claims permanently BLOCKED; then publish no corresponding detector-performance claim.
