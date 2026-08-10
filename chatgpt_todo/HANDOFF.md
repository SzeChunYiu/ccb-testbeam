# Latest Handoff

## Completed work in this session

The previous coordination PR `#1163` passed its exact-head required check and was squash-merged to protected `main` as `08edd7fa9acffe4ace1381a1fac9acc899084347`. Issue `#1049` was reopened because the merged #1051/#1162 work validates only the observed right-continuous weighted-ECDF distance `D`, not a p-value calibration.

The selected atom is now `WKS-NULL-CLUSTER-001`, child issue `#1164`. Current `compare_data_mc.py` cannot support a design-consistent clustered null because both of its first-B NPZ inputs discard source-event identity. DATA exports B2 pulse amplitudes without `(run,eventno)`; MC exports raw first-layer `Sci_bar_EDep` hit/step rows with repeated `PrimaryWeight` but no generator-event ID. This composes directly with the already-open measurand blocker #1052.

## Executable falsifier added on the research branch

`tools/audit/research_weighted_null_cluster_contract.py` implements an independent weighted-ECDF oracle plus research-only centered row/cluster bootstrap diagnostics. It is deliberately not an authorising p-value engine.

Exact local checks using the same source staged for the branch:

```text
PYTHONPATH=. pytest -q tests/test_weighted_null_cluster_research.py
7 passed in 0.11s

PYTHONPATH=. python tools/audit/research_weighted_null_cluster_contract.py --coverage
```

With 30 DATA rows, 25 weighted MC rows, seed 7, five-way representation splitting and 100 bootstrap replicates at seed 99:

- observed `D`: `0.2892157294690688` unsplit and `0.2892157294690689` split;
- cluster-bootstrap maximum replicate delta: `3.3306690738754696e-16`;
- row-bootstrap maximum replicate delta: `0.36178488205380754`;
- cluster-bootstrap mean is identical (`0.2227850406275412`);
- row-bootstrap mean shifts from `0.2227850406275412` to `0.15651673573442573`.

A separate known synthetic importance-sampling null, DATA ~ N(0,1), proposal MC ~ N(1,1), exact weight `exp(-x+0.5)`, 200 trials, 80 DATA, 160 MC and 99 bootstrap replicates per trial gave rejection fractions 0.045 at alpha 0.05 and 0.095 at alpha 0.10. Treat this only as a research-screening result; it does not include CCB clustering, Sample-II scale fitting, saturation, or detector response.

## Four role-separated votes

- **Detector/physics lead — REVISE.** Event IDs and an event/stave detector-response measurand are prerequisites; current hit/pulse rows are not a matched statistical unit.
- **Adversarial reviewer — BLOCK current NPZ inference.** Five-way row splitting changes iid-row bootstrap variance while preserving the weighted measure, so row-level resampling is representation-dependent.
- **Statistics/validation reviewer — ACCEPT the cluster-identity falsifier / BLOCK a CCB p-value.** The synthetic importance-weight study keeps cluster resampling worth testing, but low ESS, dominant weights, ties, unequal populations, multi-row clusters and nuisance refitting remain open.
- **Claims/provenance reviewer — BLOCK promotion.** `D` remains descriptive, legacy p-value remains non-authorising, and CL-013 remains GATED.

## Literature boundary

Hult & Nyquist (2016, DOI `10.1016/j.spa.2015.08.002`) supports the general interpretation of importance-sampling output as a weighted empirical measure. Kojadinovic & Yan (2012, DOI `10.1002/cjs.11135`) supports treating fitted-parameter goodness-of-fit as a separate bootstrap problem. Neither source validates the CCB cluster bootstrap or its MeV-to-ADC nuisance treatment.

## Next highest-value work

Implement #1164/#1052 at the producer contract: preserve immutable DAQ/generator event IDs, declare statistical units/weight semantics, and replace the first-B raw-hit MC product with a compatible event/stave detector-response hierarchy. Then repeat the representation-splitting and cluster-multiplicity tests, and compare refitting the Sample-II scale inside every null replicate against a held-out calibration design. Do not reinstate an authorising p-value until simulation type-I calibration and the full detector/statistical-unit chain pass.
