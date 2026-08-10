# ARU-WKS-NULL-CLUSTER-001 — weighted-null source-cluster contract

- **Session:** 2026-08-10T130500Z
- **Base main:** `08edd7fa9acffe4ace1381a1fac9acc899084347`
- **Parent:** #1049 (`ARU-DATAMC-WKS-001`)
- **Child:** #1164 (`WKS-NULL-CLUSTER-001`)
- **Cross-scale dependencies:** #1052, #1041, #1046, #880/#1022, #994, #1027
- **Status:** `PARTIAL` — representation/unit falsifier validated synthetically; real CCB null calibration blocked.
- **Scientific boundary:** no beam/production-MC result, detector validation, or goodness-of-fit probability is produced.

## Expert group and sequential review contract

1. **Detector/DAQ and MC truth lead** — background in segmented scintillator response,
   Geant4 event/track/step semantics, trigger/DAQ event identity, and detector-response
   composition. Role: decide the physical statistical unit and whether exported rows preserve it.
2. **Adversarial mechanism reviewer** — background in software provenance, sampling-design
   failure modes, transport discretisation, and counterexample construction. Role: search for
   representation changes that preserve physics but change the inference.
3. **Independent statistics/validation reviewer** — background in weighted empirical processes,
   importance sampling, clustered resampling, effective sample size, and simulation calibration.
   Role: derive invariants and execute synthetic type-I / representation falsifiers.
4. **Claims/provenance reviewer** — background in claim ledgers, reproducible statistical
   reporting, source-to-claim mapping, and fail-closed publication gates. Role: constrain what can
   be promoted and preserve unresolved objections.

These are role-separated AI review passes, not independent human collaborators.

## Selected atomic universe

The local object is not yet a p-value formula. It is the input and resampling contract required
before a calibrated weighted DATA/MC null can exist.

For row `i`, require:

- observable `x_i` with units and measurand;
- analysis/generator weight `w_i >= 0`, source-bound to its semantics;
- immutable `cluster_id_i` identifying the DAQ/generator event that produced the row;
- declared `statistical_unit` and within-event aggregation rule;
- selection and artifact provenance;
- nuisance-calibration mode.

The weighted empirical measure is

`F_w(x) = sum_i w_i I(x_i <= x) / sum_i w_i`.

The representation transformation

`(x, w, c) -> {(x, w/k, c)}_{j=1..k}`

must not change either `F_w` or a design-consistent resampling law when the copies represent the
same physical source event.

## Repository evidence inspected

### Current comparison

`scripts/compare_data_mc.py` v5 computes the corrected right-continuous weighted ECDF distance
but retains a legacy non-authorising null that pools DATA/MC values, shuffles values, and assigns
unit weights. The MeV-to-ADC scale is estimated in the same comparison chain from the Sample-II
DATA median divided by the weighted Sample-II MC median.

### DATA producer

`scripts/data01_sample_split_staves.py` knows `(run,eventno)` and uses that composite key for
the event-level B2-vs-B4 product, but `first_B_layer_B2_amplitude.npz` serialises only
`sampleI`/`sampleII` amplitude arrays. The source-event cluster key is discarded from the
first-B comparison product.

### MC producer

`scripts/mc01_trigger_split_truth.py` exports `first_B_layer_edep.npz` from the layer
accumulator `edep`, which is a list of individual charged `Sci_bar_EDep` hit/step records.
`edep_w` repeats the event `PrimaryWeight` once per retained hit. The NPZ contains values and
weights but no generator-event identifier. #1052 already establishes that this is not the
detector-event measurand.

The same producer has `EDEP_CAP = 600_000` and retains an event-order prefix of hit/step rows
once the list reaches the cap. Historical tracked 1M Sample-I B0 output has only 82,729 hit rows,
so that particular retained Sample-I product does not demonstrate cap activation; production-scale
and Sample-II cap state must be checked separately. This is a child software/provenance concern,
not evidence of a historical numerical bias by itself.

### Weight lineage

`docs/contracts/MC_WEIGHT_POLICY.md` records the legacy Krakow world as uniform `theta_cm`
proposal sampling with nontrivial `PrimaryWeight`. `geant4/src_patch/patch_scatter.py` defines a
different, later generator world in which `theta_cm` is sampled directly from
`sigma(theta) sin(theta)` and the event weight is unity to avoid double counting. These generation
worlds are not interchangeable; null calibration must bind to the actual MC generation manifest.

## External source-to-claim mapping

- **LIT-WKS-001:** Hult & Nyquist, *Stochastic Processes and their Applications* 126 (2016)
  138–170, DOI `10.1016/j.spa.2015.08.002`. Supports the general statement that importance
  sampling output is represented as a weighted empirical measure with likelihood-ratio weights.
  It does **not** validate a CCB bootstrap method.
- **LIT-WKS-002:** Kojadinovic & Yan, *Canadian Journal of Statistics* 40 (2012) 480–500,
  DOI `10.1002/cjs.11135`. Supports the general statement that goodness-of-fit empirical
  processes with estimated parameters require dedicated bootstrap treatment; it does **not**
  establish the CCB cluster bootstrap or the Sample-II scale treatment.

No literature result is substituted for a CCB-specific design validation.

## Mechanism universe and collapse

| ID | description | disposition |
|---|---|---|
| H1 | unit-weight value permutation of pooled rows | **ELIMINATED** for nontrivial PrimaryWeight; changes the observed statistic/design |
| H2 | iid row bootstrap of `(x,w)` | **ELIMINATED** for exported hit/pulse rows; representation splitting changes its variance |
| H3 | source-event cluster bootstrap carrying all rows/weights | **SURVIVES local splitting test**; not yet a calibrated CCB p-value |
| H4 | parametric/simulator bootstrap through generator + detector + reconstruction | **SURVIVES in principle / BLOCKED** by full-chain and immutable-input dependencies |
| H5 | descriptive weighted `D` with no p-value | **SURVIVES fail-closed public state** |

All row-level shuffling/bootstrap variants that treat physical-event descendants as independent
collapse into H1/H2 for the dependency question: they discard source-event dependence.

## Equations and invariants

Observed discrepancy:

`D = sup_x |F_DATA(x) - F_MC,w(x)|`.

Kish-style positive-weight diagnostic:

`ESS = (sum w)^2 / sum(w^2)`.

Representation split:

`w -> (w/k,...,w/k)` at identical `x` and shared cluster `c`.

Then algebraically the weighted mass at `x` is unchanged. A cluster bootstrap that samples `c`
and carries every descendant row with the sampled cluster multiplicity therefore also has an
unchanged replicate empirical measure. A row bootstrap instead changes the number of independent
draws from one physical cluster and is not representation invariant.

## Executed experiments

### Experiment E1 — representation splitting

Implementation:
`tools/audit/research_weighted_null_cluster_contract.py`

Exact command executed in an isolated Python test environment using the same committed source:

```text
PYTHONPATH=. pytest -q tests/test_weighted_null_cluster_research.py
```

Result:

```text
7 passed in 0.11s
```

Exact research command:

```text
PYTHONPATH=. python tools/audit/research_weighted_null_cluster_contract.py --coverage
```

For the deterministic split fixture:

- DATA rows: 30; MC rows: 25;
- data seed: 7;
- split factor: 5;
- bootstrap replicates: 100;
- bootstrap seed: 99;
- observed `D`: `0.2892157294690688` unsplit,
  `0.2892157294690689` split;
- cluster-bootstrap maximum replicate difference:
  `3.3306690738754696e-16`;
- row-bootstrap maximum replicate difference:
  `0.36178488205380754`;
- cluster-bootstrap mean statistic:
  `0.2227850406275412` in both representations;
- row-bootstrap mean statistic:
  `0.2227850406275412` unsplit versus `0.15651673573442573` split.

**Falsifier conclusion:** row-level resampling is rejected as an authorising design whenever
multiple exported rows can descend from one event. Event-cluster identity is a required input.

### Experiment E2 — synthetic importance-sampling type-I probe

This is explicitly **toy method research, not detector validation**.

Known null:

- target DATA: `N(0,1)`;
- proposal MC: `N(1,1)`;
- exact target/proposal weight: `exp(-x + 0.5)`;
- 200 outer null trials;
- `n_DATA=80`, `n_MC=160`;
- 99 centered cluster-bootstrap replicates per trial;
- bootstrap seed = outer seed + 100000.

Results:

- rejection fraction at alpha 0.05: `0.045`;
- rejection fraction at alpha 0.10: `0.095`;
- mean p-value: `0.4759`;
- mean MC ESS: `63.67561764906291`;
- ESS p10/p50/p90:
  `49.05168174557246 / 64.1263315632699 / 78.50247380123736`.

This eliminates neither low-ESS failure nor nuisance/tie/cluster mechanisms. It only keeps H3
worth investigating under the known synthetic design.

Machine-readable values are stored in
`docs/validation/wks_null_cluster_research.json`.

## Sequential expert votes

### A. Detector/physics lead — REVISE

Evidence inspected: DATA and MC producers, #1052/#1041/#1046, weight-generation worlds.
Strongest counter-hypothesis: every exported first-B row is already an independent physical event.
Attempted falsifier: producer trace shows DATA can have multiple pulses per `(run,eventno)` and MC
can have multiple `Sci_bar` rows/TrackIDs per generator event. Residual uncertainty: real
multiplicity distributions and complete H5 detector-response construction require immutable data.
**Vote: REVISE.** Event IDs and compatible detector-event measurands must be produced first.

### B. Adversarial mechanism reviewer — BLOCK current NPZ inference

Evidence inspected: exact NPZ write sites and E1. Strongest counter-hypothesis: a row bootstrap is
a harmless computational approximation. Attempted falsifier: 5-way representation split leaves
`D` fixed but moves the row-bootstrap law by O(0.1). Residual uncertainty: filesystem/product
lineage and `EDEP_CAP` activation on real current artifacts. **Vote: BLOCK** any p-value from the
current NPZ pair.

### C. Independent statistics/validation reviewer — ACCEPT falsifier / BLOCK calibration

Evidence inspected: independent ECDF oracle, E1, E2, ESS diagnostics, LIT-WKS-001/002.
Strongest counter-hypothesis: passing one importance-sampling toy proves the cluster bootstrap.
Attempted falsifier: explicitly identify untested regimes—dominant weights, lower ESS,
quantisation/saturation, unequal populations, nuisance scale refit, and multi-row clusters.
**Vote: ACCEPT** the source-cluster requirement and E1; **BLOCK** a CCB p-value.

### D. Claims/provenance reviewer — BLOCK promotion

Evidence inspected: #1049 state, current `p_value_status`, Cluster-E CL-013 GATED status,
artifact schemas. Strongest counter-hypothesis: a visible blocked tag is enough governance.
Attempted falsifier: the current output still carries a numeric legacy p-value and current NPZs
carry no machine-readable statistical-unit/cluster contract. **Vote: BLOCK** GOF probability or
detector claim promotion.

## Cross-scale compatibility

The local survivor H3 cannot compose upward yet:

`MC step/hit -> event/stave deposit -> quenching -> optical/WLS -> SiPM -> electronics/DAQ
 -> data-like waveform -> identical reconstruction -> selected event/stave amplitude
 -> weighted empirical measure -> cluster-aware null + nuisance refit -> claim`.

#1052 blocks the step/hit-to-event measurand transition. #994 blocks unqualified ADC/MeV
nuisance semantics. #1027 owns saturation/tie physics. #1045 owns trigger/sample membership.
#880/#1022 own event-weight semantics. A locally sensible bootstrap cannot bypass any of them.

## Child atoms / concerns spawned

- **#1164 / WKS-NULL-CLUSTER-001:** preserve source-event cluster identity and fail inference
  closed when absent.
- **WKS-NULL-NUISANCE-002:** compare refitted-versus-held-out Sample-II scale calibration under
  the final null; remains under parent #1049 until a compatible event product exists.
- **MC01-RETENTION-CAP-001:** `EDEP_CAP=600_000` is silent prefix retention for hit diagnostics.
  Inspect real cap activation and replace with explicit complete/event-level products or declared
  diagnostic sampling; cross-link to #1052 rather than assuming historical activation.

## Claim/wiki implications

No public number is promoted. `D` remains descriptive; the legacy numerical p-value remains
`NONAUTHORISING_BLOCKED_ISSUE_1049`. CL-013 remains GATED. Any report/wiki sentence that treats
current first-B hit-EDep versus DATA-pulse shape agreement as detector closure remains blocked by
#1052 and #1049/#1164.

## Next highest-value atom

Implement #1164 at the producer/data-contract boundary: export immutable event-cluster identity and
explicit statistical-unit metadata, preferably while replacing the flawed MC hit-step comparison
with an event/stave detector-response product under #1052. Then rerun the representation and
cluster-multiplicity falsifiers, and only then compare null designs with the Sample-II scale refit
inside every replicate versus a held-out calibration design.
