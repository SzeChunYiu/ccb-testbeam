# Current atomic findings — 2026-08-08

Base audited: `main@957c2fd6fa5b80233a283e88420631e93ee8cec7`.

This file separates direct repository evidence from the external B-stack timing note supplied to ChatGPT. The note itself is not stored here; page/table references below are handoff pointers and must be checked against the original 54-page PDF before implementation.

## P0 release blockers

### AF-001 — 16-sample real payload vs 18-sample S00 contract

Repository evidence:
- `reports/studies/data_side/REPORT.md` states the located raw data are `8 channels × 16 samples = 128 values/event`.
- `configs/s00_reproduction.yaml` still sets `samples_per_channel: 18`.
- `scripts/01_build_pulse_table_from_root.py::scan_raw` stacks a whole batch and then executes `.reshape(-1, 8, samples_per_channel)` instead of validating each event before reshaping.

Risk: a wrong configured width can mix words across event boundaries whenever the total batch element count happens to be divisible by the requested reshape size. This must be tested with a count-preserving synthetic corruption and real per-event length census.

### AF-002 — selected-count agreement is not raw-to-sorted closure

`sorted_crosscheck` counts only `hrdMax` above threshold in configured channels. It does not prove event-key equality, channel order, sample order, raw ADC-word identity, polarity, or last-channel survival. A release gate needs exact key-set accounting and per-word comparison (or an explicitly validated irreversible transform contract).

### AF-003 — no measured polarity contract in S00 pulse extraction

`pulse_quantities` subtracts a baseline and takes the positive maximum/argmax. The original project brief warns that some channels are inverted. A negative-going physical pulse can therefore be replaced by noise, recovery, undershoot or an ADC defect unless a measured polarity map is applied first.

### AF-004 — CL-001 evidence class is stronger than the current data-contract closure

`CL-001` is `VALIDATED` for 640,737 pulses, while its notes admit channel-mapping/provenance risk. The data-side report reports only 617,377 / 640,737 composite pulse-key overlap (96.4%) between one raw rebuild and the canonical selected table, not complete key-set/word-level closure. Treat exact selected-count reproduction as method/provenance closure, not detector-channel closure, until AF-001..003 pass.

### AF-005 — current data-side ΔE–E definition contradicts issue #618

`reports/studies/data_side/REPORT.md` defines the data view as `E = B2 amplitude, ΔE = B4 amplitude` and interprets a data/MC correlation sign reversal. Issue #618 explicitly says not to call B2-vs-B4 a ΔE–E analogue; it defines the data proxy as `ΔE = amplitude(B2)` and residual `E = amplitude(B4)+amplitude(B6)+amplitude(B8)`. The sign-reversal causal interpretation must be withdrawn/recomputed before being used as a material-budget or topology result.

### AF-006 — event-key validator checks cardinality, not closure

`tools/audit/validate_event_keys.py` can return `one_to_one=true` when both tables have unique keys even if the key sets are partially overlapping or disjoint, because it performs an inner join and gates only on duplicate-key fan-out. A closure validator must additionally require zero left-only keys, zero right-only keys, expected join cardinality, declared duplicate policy, and stable row identity.

## Statistical/ML defects

### AF-007 — class caps invalidate the stated inverse-probability weights

S00 first samples rows with class-dependent probabilities and assigns `1/p(class)`. It then independently caps each class by drawing at most `max_train_per_class + max_test_per_class` rows, but does not include this second inclusion probability in `sampling_weight`. If a cap binds, weighted evaluation no longer reconstructs the stated population prevalence.

### AF-008 — hyperparameter selection and calibration do not target the weighted grouped estimand

Regularisation is chosen with unweighted `StratifiedKFold`/`cross_val_score`; rows from the same DAQ event can enter different folds. `CalibratedClassifierCV(..., cv=3)` is likewise not run-group-aware. This can create within-event leakage and selects a model for the case-control sample rather than the weighted target population.

### AF-009 — weighted point estimate paired with unweighted bootstrap; failure collapses CI

The held-out accuracy point can be inverse-probability weighted, but its cluster bootstrap calls `np.mean` on unweighted correctness. If the bootstrap raises `ValueError`, the code sets `lo = hi = weighted_accuracy`. The interval therefore can target a different estimand or become spuriously zero-width on failure. Fail closed instead.

### AF-010 — silent unweighted model fallback

The calibrated fit catches `TypeError` for `sample_weight` and silently reruns an unweighted fit on older scikit-learn. This changes the estimand without an explicit failure state. Supported dependency versions should be pinned and lack of weighted support should abort the weighted analysis.

### AF-011 — canonical event identity is inconsistent across tools

The raw reader loads both `EVENTNO` and `EVT`. S00 bootstrap clusters use `(run, eventno)`. `tools/audit/validate_event_keys.py` documents `(run, evt)` as its default strict composite key. Establish the DAQ-level identity contract empirically (including wrap/reset behavior) before any join/bootstrap is declared event-safe.

## Timing-note reconciliation issues

### AF-012 — calibration-run drift

The supplied B-stack timing note declares Sample II run 61 as the only calibration run. `configs/s00_reproduction.yaml` declares `sample_ii_calib: [64]` and includes run 61 in analysis. No timing result should be described as held-out until a versioned run ledger fixes the split and reproduces all tables from that ledger.

### AF-013 — 16-vs-18 timing provenance conflict

The note interprets eight 18-sample blocks and reports sub-2 ns clean pair widths; the data-side report says the located raw product is 8×16 and calls real timing format-limited (~38 ns). These may be different processing products, but the repository lacks an immutable mapping proving how the two extra samples arise and whether event/channel/sample identity is preserved. Reconcile before interpreting either as detector performance.

### AF-014 — adaptive pedestal positivity is not an independent validation

The note lowers the first-four-sample seed pedestal until nearly every non-jagged sample is nonnegative within an amplitude-dependent tolerance. Its Table 6 reports ~98–100% adjusted, ~85–97% ambiguous, and zero below tolerance 'by construction'. This procedure can absorb early activity, inverted signals, undershoot, or dropouts into the baseline and must not be used as proof that the baseline is correct.

### AF-015 — pulse-description identifiability/overfit needs an executable rank audit

The note's v4 description model presents coefficients `c0` through `c12` on an 18-sample waveform, while jagged samples may be masked and first/final samples are reweighted. Before `qdesc` is treated as meaningful, the implementation must publish the exact free-parameter count, fixed time constants, design-matrix rank/condition number, effective degrees of freedom, and held-out residual performance. A visually good fit with a nearly saturated basis is not evidence of a predictive pulse model.

### AF-016 — qtemplate is a heuristic score, not a calibrated probability

The product of four hand-scaled exponential penalties (`0.08`, `0.08`, `0.25`, and chi-square scale `5`) is useful as a ranking score, but the note does not establish probability calibration, threshold operating characteristics, or robustness to amplitude/run/topology shift. Thresholds such as 0.20 or 0.50 require held-out sensitivity/specificity or clearly labelled heuristic status.

### AF-017 — narrow-window Gaussian σ is a conditional core width

The timing note fits only `-5 < Δt < 5 ns` with Gaussian+constant, especially after showing broad non-Gaussian Sample-I B2 tails. The resulting σ is conditional on entering the fit window and should not be treated as full pair resolution without a mixture/outlier model, fit-window sensitivity, and uncertainty that accounts for selection.

### AF-018 — independent-stave variance decomposition ignores common covariance

Using `σ²_ij ≈ σ²_i + σ²_j` assumes independent stave errors. Common trigger/clock jitter, shared event-reference corrections, common longitudinal-position effects, or calibration correlations can add covariance terms. Estimate the full covariance structure or explicitly quote an independence-conditional diagnostic.

### AF-019 — fixed 100 MeV proton TOF is not neutral for mixed p/d energy distributions

The note applies a 100 MeV proton reference for pairwise TOF. Its own physics-scale text describes much lower deuteron-like energies and different proton-like energies. Species/energy-dependent β can move inter-stave timing by O(ns) over multiple layers. Use event-level track/species hypotheses where justified, or propagate the physically allowed TOF range as a systematic; do not absorb it into timewalk.

### AF-020 — B2 broad residuals are not uniquely pile-up

The note appropriately lists secondary particles, cross-talk, afterpulse/recovery and overlapping pulses as alternatives, but downstream text still uses pile-up-like language. Required discriminants include raw-channel parity, sample-order/circular-buffer phase, polarity, low-word defects, SiPM recovery/afterpulse timing, event current/trigger dependence, downstream track/TPC association, and optical/electronic cross-talk controls.

## Public-status/documentation issues

### AF-021 — README says raw data are not staged although current report says they were found and analysed

The README headline still says beam ROOT is not staged on LUNARC, whereas `reports/studies/data_side/REPORT.md` says it was located on 2026-07-25 and analysed. Generate public status from one machine-readable authority or add a CI consistency gate.

### AF-022 — calibration terms need truth-type-qualified names

README advertises `119.17 ADC/MeV` as an MC digitizer gain, while CL-013 records `92 ADC/MeV` as a gated data/MC median-matching proxy with a heuristic ±30% envelope. These are not necessarily contradictory, but identical 'ADC calibration/gain' wording invites misuse. Names must encode truth type, estimator, domain and authorisation status.

## Next execution order

1. AF-001 / AF-002 / AF-003 / AF-006 (data contract and closure).
2. AF-004 / AF-005 (quarantine claims built on the unresolved contract).
3. AF-011 / AF-012 / AF-013 (event identity and run/product provenance).
4. AF-014..020 (timing and waveform inference after the byte contract is fixed).
5. AF-007..010 (ML/statistical estimand repair).
6. AF-021..022 (generate public claim surfaces from resolved machine-readable state).

Each finding should become one narrow GitHub issue unless an existing supervisor issue already owns the same scope; in that case add an evidence-bearing comment and create only the independently testable child tasks.