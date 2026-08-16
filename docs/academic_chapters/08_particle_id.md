# Chapter 8: Particle Identification — Source-Bound Proton/Deuteron Diagnostics

> **Claim-governance status:** The tracked MV1 result is a legacy truth-labelled
> Monte Carlo diagnostic. It is **GATED**, not a beam-data PID measurement and not
> a validated performance ceiling. Canonical claims: `CL-017` and `CL-018`.

## Abstract

The repository contains one tracked proton/deuteron classification producer,
`scripts/mv1_mv2_truth_pid_energy.py`, and one machine-readable summary,
`reports/mv1_mv2_truth_pid_energy_1782220258/mv1_mv2_truth_summary.json`.
The producer constructs per-track truth features from charged B-arm Monte Carlo
hits and restricts classification to 150,130 proton tracks and 146,842 deuteron
tracks, for 296,972 proton/deuteron tracks among 400,369 charged B-arm tracks.
It evaluates four truth-derived features: first-layer deposited energy,
second-layer deposited energy, total deposited energy, and the deepest hit layer.

The fixed summary records a logistic-regression ROC AUC of
`0.9628868703282414` and purity `0.9488978818667125` at nominal 90% deuteron
efficiency. The histogram-gradient-boosting output is ROC AUC
`0.9859658513538254` and purity `0.9644090769970706`. A traditional threshold
of `13.287866011130776 MeV` on first-layer deposited energy yields purity
`0.8909863556160177` and efficiency `0.900961577750235`; the producer does not report a traditional-cut AUC.

These values are not accepted detector-performance results. The train/test split
uses row-index parity rather than event-group separation, so correlated tracks
from one event can cross the split. The source does not retain event identifiers
in the classification table, does not specify an explicit random seed for the
histogram-gradient-boosting estimator, and provides no confidence interval,
systematic uncertainty, tracked report, or manifest. No beam-data PID performance metric is established. The claims remain **GATED** under `BLK-MV1-001` until a
content-addressed, event-group-disjoint rerun and data-transfer validation are
completed.

## 1. Scientific question and evidence class

The scientific question is whether B-stack energy-deposition and range-like
observables can separate proton and deuteron tracks. The tracked study answers a
narrower question: how strongly a legacy classifier separates truth-labelled
proton and deuteron Monte Carlo tracks under its own fixed feature construction
and row-index parity split.

This distinction matters because Monte Carlo truth labels remove the principal
ambiguity present in beam data. A truth-labelled result can demonstrate that the
simulated feature distributions differ; it cannot by itself establish species
purity, efficiency, calibration, or transfer in real data. Therefore:

- `CL-017` is a fixed legacy truth-MC HGB ROC AUC diagnostic;
- `CL-018` is the corresponding fixed purity at nominal 90% efficiency;
- both have `truth_type=mc_truth_only` and `status=GATED`;
- both are blocked by `BLK-MV1-001`;
- neither is an empirical beam-data result or a production classifier approval.

## 2. Producer and data path

The producer opens a ROOT tree and reads track ID, layer identifiers, PDG code,
deposited energy, track length, and momentum components. Within each event it
groups charged B-arm hits by track ID. For each retained track it stores:

1. PDG truth label;
2. a kinetic-energy quantity derived from the first-hit momentum;
3. deposited energy in layer 0;
4. deposited energy in layer 1;
5. total deposited energy;
6. deepest hit layer;
7. number of hit layers;
8. summed track length.

The classification mask retains PDG 2212 protons and PDG 1000010020 deuterons.
The summary records 400,369 charged B-arm tracks in total, of which 150,130 are
protons and 146,842 are deuterons. Their sum is 296,972, which is the sample size
recorded in `CL-017` and `CL-018`.

The stored `mc_file` is an absolute historical filesystem path. The ledger does
not bind a tracked manifest, exact ROOT digest, software environment, or model
version inventory. The tracked summary is sufficient to audit the fixed reported
numbers, but not to reproduce the study from raw input bytes.

## 3. Feature and estimator contract

The four classification features are taken directly from truth-level hit
aggregation:

- `edep_l0`: deposited energy in the first B-arm layer;
- `edep_l1`: deposited energy in the second B-arm layer;
- `edep_tot`: total deposited energy over retained B-arm hits;
- `stop_layer`: maximum layer identifier reached by the track.

The labels are exact PDG truth labels in simulation. The split is not run-held-out
or event-held-out. The producer creates a row index and assigns even rows to
training and odd rows to testing. This **row-index parity** contract is the central
validation limitation. Because the producer can retain multiple tracks from one
event and does not store an event ID in the classification table, event-group
independence cannot be verified from the tracked output.

The logistic regression and histogram-gradient-boosting classifier are fitted
without a repository-recorded hyperparameter scan. The HGB constructor is called
without an explicit `random_state`. Consequently the tracked numbers are fixed
source outputs, not a demonstrated deterministic rerun contract across supported
software versions.

## 4. Reconstructed fixed outputs

### 4.1 Traditional first-layer cut

The producer chooses the median of the pooled proton and deuteron first-layer
energy deposits as the threshold. It reports:

| Quantity | Fixed output |
|---|---:|
| Threshold | `13.287866011130776 MeV` |
| Purity | `0.8909863556160177` |
| Efficiency | `0.900961577750235` |

No ROC curve or AUC is computed for this cut. The former chapter mislabeled the rounded cut purity as an AUC. The producer does not report a traditional-cut AUC, so that interpretation is removed.

### 4.2 Logistic regression

| Quantity | Fixed output |
|---|---:|
| ROC AUC | `0.9628868703282414` |
| Purity at nominal 90% deuteron efficiency | `0.9488978818667125` |

These are truth-labelled MC outputs evaluated on the odd row-index subset. They
are not run-held-out beam-data metrics and do not use weak run-level labels.

### 4.3 Histogram-gradient boosting

| Quantity | Fixed output |
|---|---:|
| ROC AUC | `0.9859658513538254` |
| Purity at nominal 90% deuteron efficiency | `0.9644090769970706` |

The ROC AUC has its usual ranking interpretation within this fixed held-out row
subset. It must not be treated as a detector performance limit or an irreducible bound. The result is conditional on simulated physics,
feature construction, sample composition, split leakage, estimator defaults, and
unquantified systematic effects.

## 5. Uncertainty and validation state

The tracked summary contains point estimates only. It does not provide:

- bootstrap, repeated-split, or analytic uncertainty;
- confidence intervals for AUC, purity, or efficiency;
- event-group or run-group resampling;
- sensitivity to simulation physics, geometry, thresholds, or feature choices;
- cross-stave, cross-energy, or independent-seed closure;
- data/MC feature-distribution agreement;
- calibration or probability-calibration diagnostics;
- an immutable input manifest or tracked execution environment.

A point difference between the logistic-regression and HGB AUC values cannot be
partitioned into label noise, model nonlinearity, calibration, or any other cause
without controlled ablations and uncertainty. No such decomposition is
source-backed here.

## 6. Range-energy output quarantine

The same producer writes MV2 range-energy quantities. The summary's
`mean_ekin_MeV` entries are of order `1e-4 MeV`, which is incompatible with an
interpretation as a 190 MeV beam-scale kinetic energy. The producer combines a
rest-mass table labelled in MeV with momentum branches whose unit convention is
not explicitly converted or bound in the tracked manifest. Until the exact ROOT
branch units and conversion are established, MV2 kinetic-energy and range-energy
claims are **BLOCKED** and must not be used to justify stopping-depth performance,
combined decision rules, or PID efficiency/purity numbers.

The tracked MV1 summary also does not contain trigger-split “Sample I” and
“Sample II” stopping-depth tables or a validated combined decision-tree result.
Those former chapter claims are removed rather than inferred from unrelated
artifacts.

## 7. Required better method

A scientifically accepted PID study should preregister and retain:

1. exact input ROOT path, byte size, SHA-256, tree, branch schema, units, and event
   count;
2. exact producer commit, clean-worktree state, environment, package versions,
   command, configuration, and random seeds;
3. one row per declared analysis unit with stable event and track identifiers;
4. group-disjoint splitting by event and, where data are involved, by run;
5. a traditional physics baseline and at least one interpretable multivariate
   alternative;
6. confidence intervals from event/run-aware resampling and repeated-seed
   stability;
7. calibration, threshold, geometry, and simulation-model sensitivity;
8. an untouched validation sample or new simulated energies/runs;
9. matched data/MC closure for every deployed feature;
10. efficiency, purity, ROC, calibration, confusion matrices, and failure slices
    with explicit denominators.

Plausible alternatives include a two-dimensional binned likelihood in first-layer
versus total deposited energy, a monotonic generalized additive model, and a
calibrated gradient-boosting model. Model choice should compare bias, variance,
calibration, transfer robustness, interpretability, and computational cost. A
more flexible model is not preferred merely because its point AUC is larger.

## 8. Required visual evidence

Before a production claim, the repository should provide reproducible plots with
source hashes and generation commands:

- proton/deuteron feature distributions and data/MC overlays;
- event-group-disjoint ROC and purity-efficiency curves with uncertainty bands;
- score calibration and confusion matrices;
- performance by run, energy, stopping layer, multiplicity, and stave;
- split-overlap diagnostics proving event-group independence;
- repeated-seed and bootstrap distributions;
- feature ablations and traditional-baseline comparisons;
- MV2 unit and range-energy closure diagnostics before any stopping-depth use.

Every plot must state units, selections, denominators, normalization, uncertainty
meaning, source paths, hashes, and the interpretation of success or failure.

## 9. Conclusions

The repository supports two exact fixed legacy MV1 claims: HGB AUC
`0.9859658513538254` and purity `0.9644090769970706` at nominal 90% deuteron
efficiency on truth-labelled Monte Carlo tracks. It also supports the fixed
logistic-regression and traditional-cut outputs listed above. The evidence does
not support a data-only AUC, a Monte Carlo performance ceiling, an irreducible
information-loss interpretation, a validated stopping-depth classifier, a
combined decision-tree operating point, or a ±4% PID systematic uncertainty.

`CL-017` and `CL-018` remain **GATED** under `BLK-MV1-001`. No beam-data PID
performance metric is established. The next accepted step is a content-addressed,
event-group-disjoint, uncertainty-bearing rerun followed by matched data/MC
transfer validation.
