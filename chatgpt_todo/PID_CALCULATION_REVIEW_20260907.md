# E–ΔE PID calculation review — 2026-09-07

## Scope and evidence status

Reviewed base: `cec9edc28257e0699c70c17fa9b2e8d806a3d42a`.
Interactive review, not ownership of the scheduled session's ACTIVE_TASK. Production code, existing results and claim gates are unchanged. Direct main write was refused by branch protection; this record is PR transport, NOT main acceptance or scientific closure.

Reviewed: source functions, tracked JSON/manifests, publication chapter, wiki and Hugging Face metadata. Executed locally: small synthetic source-excerpt regressions. NOT executed: raw waveform/Parquet inspection, full repository tests, full producer, Geant4 or production AUC/correlation reruns. The HF viewer/download failures do not prove corruption of a particular raw file.

Dataset `billyyiu747/ccb-testbeam` distinguishes ucesb raw ADC `parquet/` from hrdSorter features `sorted/`. The example paths are `parquet/sample/events_sample.parquet` and `sorted/sample/events_sample.parquet`. Freeze actual dataset revision and downloaded SHA-256; the card does not establish channel/sample flattening or measured hardware mapping.

## Step-by-step calculation trace

1. Decode LMD → ucesb/h101 ROOT → hrdSorter features. Wiki S00 uses baseline=median(samples0–3), positive amplitude=max(sample)−baseline, then A>1000 ADC. Verify product schema/polarity rather than assuming a 128-column table is a specified8×16 waveform.
2. Reconstruct all channels BEFORE analysis cuts, retaining values, presence/corruption/clipping flags, source/run/event identity and polarity. ADC peak height is not integrated charge or calibrated MeV.
3. Form one event per `(source_file_id,run_id,event_id)`. The bridge repairs the earlier eventno pivot split. The saved bundle has332940 eventno values but216448 physical events;90260 physical events contain multiple eventno values. Do not equate the640737 S00 pulse inventory with unique PID events.
4. Data axes: ΔE_ADC=A(B2); E_ADC=A(B4)+A(B6)+A(B8). B2 versus B4 alone is a different diagnostic, often also selected on both channels being positive.
5. MC: let D_i be a physical-layer deposit and r the readout map. ΔE=D[r(B2)], E_sparse=D[r(B4)]+D[r(B6)]+D[r(B8)]. E_full must sum each physical layer downstream of r(B2) exactly once. Under the bundle1/3/5/7 map, full=D2+D3+D4+D5+D6+D7 and sparse=D3+D5+D7. Under0/2/4/6, the boundary changes.
6. Energy deposits require quenching, optical/sensor/electronics response and the same waveform estimator before comparison to amplitudes. A deposit sum is not residual kinetic energy if energy escapes or is lost in uninstrumented material. A simulation gain closure is not a measured beam calibration.
7. Pearson r is global linear association, not PID efficiency/purity. Historical Cluster A uses dominant-deposit-track labels and event-summed deposits, requires both ΔE and Eres positive, pair-merges layers(0,1),(2,3),(4,5),(6,7), and uses five folds of2000 selected-row blocks sorted by event ID—not independent beam runs.

## Saved results: descriptive, not freshly reconstructed

Bundle: `reports/paper_618_species_penetration_2m_20260814T1449Z/`.

| Beam-data quantity | Sample I | Sample II |
|---|---:|---:|
| Runs |44–57|58–63,65|
| Physical events |147274|69174|
| Median ΔE [ADC] |7101.0|3566.5|
| ΔE event16–84% [ADC] |3855.5–8609.5|2018.5–5820|
| Median E [ADC] |0|0|
| E event16–84% [ADC] |0–0|0–4405|
| Pearson r |-0.0418976936|-0.0697173506|
| Run-bootstrap16–84% r interval |-0.0514093692 to -0.0304741052|-0.0984078947 to -0.0303058776|
| Deepest-active B2 fraction |0.946080|0.698369|
| Deepest-active B8 fraction |0.008780|0.064041|

Event quantiles are not uncertainty on medians; bootstrap16–84% intervals are not95% intervals. Zero downstream amplitude under selected-pulse/zero-fill semantics does not establish a physical stop. Gated amplitude-domain summaries only.

2M MC:2000000 generated events,14112 B-entrance rows,1106 Sample I,13006 Sample II. Saved labels: I313p/790d/3other; II11102p/1870d/34other. Nonzero sparse-axis summaries reduce I to859 and II to11893. Keep those denominators separate; species counts are not measured beam composition.

Different Krakow1M Cluster A:131198 selected events; weighted medians ΔE24.13MeV,E101.03MeV; r−0.533; AUC≈0.898. Its aggregation, selection and truth-assisted features differ from the2M bundle, so these are not successive measurements of an unchanged benchmark.

## Atomic findings and handoff queue

### PID-20260907-01 | P0 | CONFIRMED_DEFECT, NOT_FIXED

**Full MC E collapses to sparse E.** `_deltaE_E_core.py::mc_layer_columns` recognizes only `edep_B<number>`. `derive_mc_columns` sums these except B2; producer physical `edep_layer_0..7` fields are ignored because only four edep_B aliases exist. `paper_618_species_penetration.py::load_mc` consumes that full column unchanged. Saved mc4_I/mcfull_I and mc4_II/mcfull_II summaries are exactly identical, consistent with source and unit fixture.

Fixture physical deposits[1,2,3,4,5,6,7,8]MeV/map1/3/5/7: sparse18; physical downstream full33; implementation full18. This15MeV discrepancy is not an estimate of production bias. The legacy path also includes upstream edep_B1 because !=B2 is not a downstream predicate. The manifest's `sum(edep_layer_1..7)` would include ΔE when B2 maps to1; resolve the boundary rather than copying this string into a fix.

Acceptance/owner: detector geometry + implementation. Explicit map and physical-layer schema; both phases, unsampled-only deposits, upstream exclusion, unique-layer counting and incomplete-schema tests. Recompute real2M per-event E_full differences and figures. Preserve old artifacts and claim quarantine.

### PID-20260907-02 | P0 | CONFIRMED_DOMAIN_GAP, NOT_REBENCHMARKED

**AUC≈0.898 is not E–ΔE-only.** `clusterA_dE_PID_stopping.py::vis_pid_001` uses `[log(dE+.001),log(Eres+.001),dE/(dE+Eres),log(ekin_entry+.001)]`. The fourth input is dominant-track MC-truth entrance kinetic energy. The axes are deposited-energy truth, not digitized beam readout. This is a truth-assisted MC diagnostic, not detector-readout-only PID. The numerical effect of removing truth energy has not been measured.

Acceptance/owner: PID/statistics. On identical held-out events, distinguish readout-only, deposit-truth-only and truth-energy-assisted benchmarks. Record feature availability and prevent truth-only columns entering detector-performance models.

### PID-20260907-03 | P1 | CONFIRMED_METRIC_DEFECTS, NOT_FIXED

`roc_pr` does not group tied thresholds: one p and one d with equal score0.5 return AUC1 or0 by input order, instead of0.5. AP omits the first recall increment: a perfect two-event ranking returns0 rather than1. Reproduced on source excerpts; production metric impact unknown.

Other visible statistical issues: trailing partial bootstrap block omitted by ne//blk when ne>=blk is not divisible by blk; operating threshold maximizes F1 on pooled OOF scores and reports confusion on those same scores; some robustness y-ranges start at0.5 despite sub0.5 slices.

Acceptance/owner: statistics. Independent ROC/AP reference with ties, permutations, unit/nonunit/zero weights and class imbalance; bootstrap includes all eligible blocks; operating-threshold selection stays inside training/calibration folds; failure slices visible.

### PID-20260907-04 | P0 | CONFIRMED_INPUT_LINEAGE_GAP, RAW_EFFECT_UNKNOWN

Manifest input is `reports/1780917628.449525.085b2dc0__s01b_s00_selected_table_manifest/s00_selected_b_pulses.csv.gz`, declared SHA256 `648c32d0109fb05cdf04b2a0d2817044067e8741c70a53f540308a1c038a8b2f`. Producer reads selected pulses, not raw waveforms. ADC500/750/1000 scans are identical. It does not demonstrate uncensored reconstruction despite metadata `no_pre_threshold_censoring`; equality alone is not proof, input lineage is essential.

Illustration, not data: amplitudes(2000,800,600,400)ADC imply E1800. Per-pulse >1000 selection plus absent→zero produces E0. Acceptance/owner: waveform reconstruction. Hash raw HF files, validate schema/polarity/map/identity, retain all signals/states before cuts, rebuild threshold scans and selected inventory separately.

### PID-20260907-05 | P0 | CONFIRMED_SEMANTIC_GAP

Bridge absent channels become0 before outer producer labels zero MISSING; measured zero and absence are indistinguishable. Missing saturation columns defaultFalse. Reported zero saturation flags do not prove no waveform clipping. Acceptance: preserve nullable measurements, presence/status and source-bound clipping information before aggregation; test missing versus measured0 explicitly.

### PID-20260907-06 | P0 | CONFIRMED_LABEL_RULE_GAP, MISLABEL_RATE_UNKNOWN

`build_mc_wide_table` loads no TrackID/ParentID and assigns `b_enter_indices[0]`, the first stored charged entrance hit, while claiming entrance-primary identity. Permuting p/d entrance hits can change labels at unchanged deposits; per-layer energy sums all tracks. Acceptance/owner: MC truth. Bind entrance tracks, separate dominant species/event mixture, test hit-order invariance, retain ambiguous events explicitly. Do not invent a mislabel rate without a rerun.

### PID-20260907-07 | P0 | BLOCKED_HARDWARE_TRANSFER

I=coincidence and II=B entrance AND NOT coincidence is not automatically faithful to a B-only trigger, which need not veto A. Disjoint real run cohorts do not require exclusive MC acceptance. Existing#1045 tracks hardware-trigger/proxy closure. Wiki0/2/4/6 versus bundle1/3/5/7 also needs hardware mapping evidence. Acceptance: separately model inclusive B-trigger and explicit-veto hypotheses; compare both readout phases on identical events without declaring either measured.

### PID-20260907-08 | P1 | CONFIRMED_CONTRACT_DRIFT

Core reach=P(deepest>=layer), but618 local reach=hit in that readout. Data overlay inherits bridge threshold0 whereas core scans500–1500ADC; species MC uses0.02MeV versus core primary0.05MeV. CLI bootstrap-replicates is parsed but not forwarded to the helper, which defaults1000; this did not alter the tracked default1000 run.

Acceptance/owner: provenance. Bind observables/thresholds/denominators/actual replicate counts in tables, figures and manifests. Update wiki, publication chapter and claim ledger together; structural PASS is not calibrated beam PID.

## Execution and coordination

Companion: `chatgpt_todo/reviews/20260907_pid/reproduce_defects.py`. Excerpt run: six checks, five failed scientific invariants and one passing sparse-sum control; intentional exit1. Not a full-repository run or physics MC.

```bash
python chatgpt_todo/reviews/20260907_pid/reproduce_defects.py \
  --repo . --out /tmp/ccb_pid_regressions.json
```

Repository mode AST-extracts actual functions without executing the study's top-level ROOT load. Pin checkout and record source hashes. Recommended first implementation atom:01; keep unrelated calibration changes separate. Follow existing coordination README, preserve scheduled task ownership, link#618/#956/#1045 and affected claim rows, and leave old evidence quarantined until real regenerated outputs pass the declared scientific gates. No production fix or closure is claimed here.

## Source index (reviewed base unless specified)

- `publication/chapters/07_deltae_e.tex`: intended observables/gates.
- `scripts/single_stave/{_deltaE_E_core.py,paper_956_deltaE_E_publication.py,deltaE_E_data_bridge.py,paper_618_species_penetration.py}`: sums, conventions, flags, labels, maps and figures.
- `scripts/studies/clusterA_dE_PID_stopping.py`: truth feature, folds, ROC/AP/bootstrap.
- `reports/studies/clusterA/SUMMARY.md`: historical MC and row/event scope.
- `reports/paper_618_species_penetration_2m_20260814T1449Z/{result.json,618_summary.json,manifest.json}`: saved results, declared production commit `6b57771e3c872ff3ee1b503f84f732c454acca6d`. Raw hashes were not recomputed here.
- `WIKI.md`: S00 and map narrative; conflicting/stale prose is not hardware calibration evidence.
- HF card: https://huggingface.co/datasets/billyyiu747/ccb-testbeam
- NIST proton stopping powers: https://physics.nist.gov/PhysRefData/Star/Text/PSTAR.html
- Geant4 quenching: https://geant4.web.cern.ch/documentation/pipelines/master/bfad_html/ForApplicationDevelopers/Detector/birks.html
- AP reference: https://scikit-learn.org/stable/modules/generated/sklearn.metrics.average_precision_score.html
