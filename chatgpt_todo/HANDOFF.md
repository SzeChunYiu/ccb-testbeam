# Latest Handoff

## Completed predecessor in this session

PR `#1165` passed exact-head MC Validation on `930f08df435bd42532707f078501c396fb1da37d`; run `31391922666` reported `1337 passed, 1 skipped, 8 xfailed, 1 xpassed` and successful lint/enforcement. It was squash-merged to protected `main` as `a1d7afe17e526c0e90761e8d7da4924eea5862e5`. That work makes the #1164 event-cluster representation falsifier executable but does not authorise a CCB p-value.

## Selected atom: fitted-scale calibration topology (#1166)

Current `scripts/compare_data_mc.py` estimates

`shat = median(DATA_II) / weighted_median(MC_II, PrimaryWeight)`

then uses the same `shat` in both Sample-II and Sample-I weighted-ECDF discrepancies. The fit is therefore part of the statistic-generating chain.

Repository population identity is asymmetric:

- `configs/s00_reproduction.yaml`: DATA Sample-I analysis runs 44–57 and Sample-II analysis runs 58–63,65 are disjoint run families;
- `scripts/mc01_trigger_split_truth.py`: MC Sample II is every `ENTER B` event, while Sample I is the coincidence subset, so `MC_I subset MC_II` by construction.

A null replicate must preserve this fit/test membership graph or replace it with an explicitly held-out calibration design. Marginal distributions alone are insufficient.

## Executed research-only falsifiers

### Same-sample nuisance refitting

Equal-weight positive scale-family null, chosen specifically so PrimaryWeight cannot explain the effect:

- DATA = `90 * LogNormal(0,0.5)`; MC = `LogNormal(0,0.5)`;
- 200 trials; 80 DATA; 160 MC; 99 bootstrap replicates/trial;
- seed base `20260810`.

Results:

- alpha 0.05 rejection: fixed scale `0.000`, refit `0.060`;
- alpha 0.10 rejection: fixed scale `0.015`, refit `0.095`;
- mean p: fixed `0.67775`, refit `0.5378`;
- mean observed `D`: `0.0963125`;
- mean null `D`: fixed `0.1148734`, refit `0.0974836`.

The fixed-scale bootstrap is strongly conservative in this declared fixture. This falsifies nuisance freezing as a harmless default; it does not establish that refitting is sufficient for CCB.

### Fit/test overlap topology

2,000 trials, seed `20260811`; MC-II contains 160 events and MC-I is a Bernoulli-0.4 subset (mean 64.109). DATA-I and DATA-II are independent synthetic populations. Replacing the nested MC-I with an independent sample from the same marginal distribution gives:

- corr(`shat`, median(MC-I)): `-0.43589` preserved vs `0.00332` broken;
- mean Sample-I `D`: `0.14927` preserved vs `0.15842` broken;
- 95th-percentile Sample-I `D`: `0.24080` preserved vs `0.25758` broken.

Thus the membership graph materially changes the null law even with identical one-sample marginals.

## Four role-separated votes

- **Detector/calibration lead — REVISE.** The scale is not external: it is fit from Sample II. Its current ADC/MeV meaning is still a non-authorising hit-record proxy because #1052/#994 remain open.
- **Adversarial mechanism reviewer — BLOCK fixed/topology-blind nulls.** Fixed-nuisance and independently regenerated MC-I worlds are falsified by the two controlled studies.
- **Independent statistics/validation reviewer — ACCEPT the local falsifiers / BLOCK CCB inference.** Refitting and membership preservation survive locally, but nonuniform weights/ESS, clusters, ties/saturation, unequal populations and matched detector response remain untested.
- **Claims/provenance reviewer — BLOCK promotion.** Weighted `D` stays descriptive; legacy p-value stays `NONAUTHORISING_BLOCKED_ISSUE_1049`; CL-013 stays GATED.

## Repository artifacts on the branch

- `tools/audit/research_weighted_null_scale_contract.py`
- `tests/test_weighted_null_scale_research.py`
- `docs/validation/wks_null_scale_topology_research.json`
- `chatgpt_todo/archive/2026-08-10T132700Z_ARU-WKS-NULL-SCALE-001.md`
- this coordination update and `ACTIVE_TASK.md`

Issue #1166 contains the full atom definition, mechanisms, equations, literature mapping, exact synthetic results, acceptance/rejection criteria and handoff. The branch intentionally implements research falsifiers only; no production p-value or detector calibration is introduced.

## Literature boundary

Capasso et al. (2009), DOI `10.1142/S0219525909002131`, supports re-estimating fitted parameters in EDF goodness-of-fit Monte-Carlo calibration; Kojadinovic & Yan (2012), DOI `10.1002/cjs.11135`, treats estimated-parameter GOF as a distinct bootstrap problem. Neither source validates the CCB weighted, clustered, trigger-nested design.

## Next highest-value work

After exact-head CI/merge of this research branch, implement #1164/#1052 producer contracts: preserve immutable DAQ/generator event IDs plus Sample-I/Sample-II membership, declare statistical units/weight semantics, and construct a compatible event/stave detector-response product. Then repeat null-calibration studies with source-bound nonuniform weights, real cluster multiplicities, saturation/ties, and the Sample-II nuisance refit or a rigorously held-out calibration sample. Do not reinstate an authorising p-value until those cross-scale gates pass.
