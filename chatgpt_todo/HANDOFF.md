# Latest Handoff

## Validated and merged in this session

Two bounded weighted-null research steps are now on protected `main`.

1. PR `#1165` exact head `930f08df435bd42532707f078501c396fb1da37d` passed MC Validation run `31391922666` (`1337 passed, 1 skipped, 8 xfailed, 1 xpassed`) and was squash-merged as `a1d7afe17e526c0e90761e8d7da4924eea5862e5`. It makes the #1164 event-cluster representation falsifier executable.
2. PR `#1167` exact head `90b1688a4f0f58f3d2bc23611b8854a9b9d9d21c` passed MC Validation run `31393379296` (`1347 passed, 1 skipped, 8 xfailed, 1 xpassed`) and was squash-merged as `4268175da2e282a755b7f59acc235cffee512ed4`. It makes the #1166 fitted-scale and fit/test-topology falsifiers executable.

Both are research-method closures only. Neither implements or authorises a production CCB p-value.

## Fitted-scale/topology result (#1166)

Current `scripts/compare_data_mc.py` estimates

`shat = median(DATA_II) / weighted_median(MC_II, PrimaryWeight)`

and reuses the result in Sample-II and Sample-I weighted-ECDF discrepancies. Canonical DATA Sample-I analysis runs 44–57 and Sample-II analysis runs 58–63,65 are disjoint, while `mc01_trigger_split_truth.py` defines Sample I as a coincidence subset of Sample II. Therefore the nuisance fit and source-membership graph are part of the null design.

The equal-weight LogNormal scale-family falsifier used 200 trials, 80 DATA, 160 MC and 99 bootstrap replicates/trial at seed base `20260810`. Fixed fitted scale rejected `0.000/0.015` at alpha `0.05/0.10`, while refitting inside each replicate gave `0.060/0.095`; mean p changed from `0.67775` to `0.5378`. The 95% Wilson intervals for the rejection estimates are approximately `[0,0.01885]` versus `[0.03465,0.10193]` at alpha 0.05 and `[0.00511,0.04317]` versus `[0.06166,0.14360]` at alpha 0.10. With 99 replicates, the Monte-Carlo p grid is 0.01. This supports only the narrow conclusion that nuisance freezing is not harmless in this declared fixture.

A separate 2,000-trial topology falsifier at seed `20260811` preserved MC-I as a Bernoulli-0.4 subset of MC-II, then replaced it with an independent same-marginal sample. corr(`shat`, median(MC-I)) changed from `-0.43589` to `0.00332`; mean Sample-I `D` changed from `0.14927` to `0.15842`; the 95th percentile changed from `0.24080` to `0.25758`. Marginal equality is therefore insufficient when source membership changes.

## Four role-separated disposition

- **Detector/calibration lead — REVISE.** Refitting/membership preservation are necessary design candidates, but the current ADC/MeV operand is still the wrong detector measurand under #1052/#994.
- **Adversarial reviewer — BLOCK fixed/topology-blind nulls.** Both rejected mechanisms have executable negative controls on main.
- **Statistics/validation reviewer — ACCEPT local falsifiers / BLOCK CCB inference.** The surviving method still needs nonuniform weights/ESS, event clusters, ties/saturation, unequal populations and substantially larger calibration studies with Monte-Carlo uncertainty.
- **Claims/provenance reviewer — BLOCK promotion.** Weighted `D` is descriptive; the legacy p-value remains `NONAUTHORISING_BLOCKED_ISSUE_1049`; CL-013 remains GATED.

Capasso et al. (2009), DOI `10.1142/S0219525909002131`, supports re-estimating unknown parameters in EDF Monte-Carlo GOF calibration; Kojadinovic & Yan (2012), DOI `10.1002/cjs.11135`, treats estimated-parameter GOF as a distinct bootstrap problem. These are method context, not validation of the CCB weighted/clustered trigger design.

## Next highest-value atom

Work at the #1164/#1052 producer boundary before adding more p-value machinery. Preserve immutable DAQ/generator event IDs and Sample-I/Sample-II membership; emit explicit `statistical_unit`, aggregation policy, source/config hashes and event-weight semantics; and replace the first-B raw hit-record MC product with an event/stave response hierarchy. The final DATA analogue still requires quenching → optical/WLS → SiPM → electronics/digitizer → identical reconstruction, but event/stave deposited-energy and visible-energy products can be retained as explicitly non-detector-closure mechanism diagnostics.

The strongest next negative controls are transport-step splitting at fixed event/stave total, multi-track same-event aggregation, duplicated rows with shared versus false-unique event IDs, nested-trigger membership preservation, one dominant PrimaryWeight/low ESS, and saturation/tie cases. No authorising p-value should return until these cross-scale contracts and a calibrated nuisance design pass together.
