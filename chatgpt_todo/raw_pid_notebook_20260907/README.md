# Raw-ADC PID notebook: executed findings and handoff

Date: 2026-09-07. Audited base: `cec9edc28257e0699c70c17fa9b2e8d806a3d42a`.

**EXECUTED RAW-ADC RECONSTRUCTION + MC DEPOSIT-TABLE REANALYSIS. BEAM SPECIES IDENTIFICATION IS NOT VALIDATED.**

## Deliverable and coordination

The delivered conversation bundle contains the executed `CCB_raw_PID_step_by_step.ipynb` (34 cells, 16 executed code cells, zero error outputs), HTML report, transparent percent-cell source, 35 diagnostic/data/MC plots, six equation PNGs, complete event features, out-of-fold predictions and source manifests. Eleven synthetic regression tests pass. This repository directory preserves the central numeric reproducer and handoff, not the multi-megabyte rendered notebook.

Our branch is `chatgpt/raw-pid-notebook-reproducible-20260907`. Leave the concurrent PR #1625 / `chatgpt/raw-pid-notebook-20260907` and the unrelated main `ACTIVE_TASK.md` unchanged. Production analysis and raw inputs were not edited. Full repository tests and independent human review were not performed. Detector physics, signal processing, statistics and provenance were separate review passes by the same assistant.

## Immutable inputs

HF: `billyyiu747/ccb-testbeam` at `0b25f28e0144a3d1597afcdd3446ad1abd3d2d74`. Read all rows of `parquet/events/hrdb_run_NNNN.parquet` for runs 44–63 and 65: **650,970 raw ADC events**. Sample I is runs 44–57; Sample II is 58–63,65. These are run populations, not species labels.

Read-only retrieval workflow `.github/workflows/raw-pid-notebook-inputs-20260907.yml`, commit `3c2c4a0382f17538037bee708a699ae61752080d`, run `34101549430`, job `101676903245`: SUCCESS. Artifact `10010695645` (`raw-pid-notebook-inputs`) contains `raw_adc.npz`, `mc_deposits.csv.gz`, and a manifest with every raw Parquet hash. Artifact retention ends 2026-09-14; the pinned original files remain the source of record.

| Object | SHA-256 |
|---|---|
| Input artifact ZIP | `c1b58eac8761754189400c477109d8298ab5bbfbebb77bc4bc826febe1f3120d` |
| Raw NPZ | `c64f00acf27e6f574ec4831581e2df172be3be71a822e94f71b463fba75ad41e` |
| Original MC Parquet | `d67b0bf47e1485877af9b9732b0139bbf5a2fd88733e6a7c2d4e2266184c5c40` |
| MC CSV-gzip transport | `f6d791339fd4348ff5451eadf76b2524ad0bb92d4d3eccfb2bb71d43f378637a` |

MC source is `reports/paper_618_species_penetration_2m_20260814T1449Z/deltaE_E_events_mc.parquet` at the audited Git revision: 14,112 unit-weight events. This work does not run new Geant4 production.

## Layout correction: do not use the old 8x16 interpretation

`configs/channel_polarity_v2.json` is **RETRACTED_20260816_TRUNCATED_STAGING_DESYNC**. Its retraction documents the 128-word product as the first 128 words of a channel-major **8x18=144-word frame**. Wrong 16-sample segmentation mixes adjacent pedestal levels into apparent pulses. Operative v1 uses positive-going even primary channels.

Primary readouts are fully retained: B2/channel0 = words 0:18; B4/channel2 = 36:54; B6/channel4 = 72:90; B8/channel6 = 108:126, all zero-based half-open slices. The incomplete last duplicate is excluded. Source-row identity is `(HF revision, file, event_idx)`, not a reused DAQ counter. The notebook plots raw pedestal boundaries under both interpretations. Per-run comparison to a full144 original remains a separate provenance gate.

On identical raw events and the same A>1000 cut:

| Readout | Correct 18-stride count | Wrong 16-stride count |
|---|---:|---:|
| B2 | 329635 | 328699 |
| B4 | 27680 | 55352 |
| B6 | 14242 | 22045 |
| B8 | 5805 | 13062 |

These are reconstruction effects, not species discoveries. This correction supersedes the earlier 8x16 narrative, including the earlier conversational review.

## Fresh raw-data calculations

`b=median(samples 0..3)`; `A=max(samples 0..17)-b`; `Delta_ADC=A(B2)`; `E_ADC=A(B4)+A(B6)+A(B8)`. Every channel is reconstructed before thresholding. Signed area over samples 4..17 stays ADC-samples. Neither quantity is calibrated MeV.

Below, the selection is explicitly **B2>1000 ADC**. It is not the historical union of selected pulse-table rows, so denominators differ from previous summaries.

| Quantity | Sample I | Sample II |
|---|---:|---:|
| Raw events | 388879 | 262091 |
| B2-anchor events | 241422 | 88213 |
| Median Delta [ADC] | 6542.5 | 3350.0 |
| Median uncensored downstream sum [ADC] | 77.5 | 97.0 |
| Pearson r | -0.05446549746028057 | -0.08443112404540734 |
| Any downstream A>1000, conditional on B2>1000 | 0.02631491744745715 | 0.238184848038271 |
| Whole-run bootstrap 95% interval | [0.021435663886391808, 0.03328539687035178] | [0.13254293277824286, 0.3489220355978942] |

Intervals use 2,000 whole-run resamples (14 and 7 runs). They describe statistical/run variability, not hardware systematics or species purity. In particular the Sample-II run variation is substantial.

A deliberate counterfactual zeroes downstream amplitudes <=1000 before summation. It creates exact E=0 for 97.3685% / 76.1815% of anchored Sample-I/II events and zero median E in both samples. Conversely, a quiet-channel maximum has positive noise bias: the uncensored small positive medians do not prove energy deposition or exclude a physical stop.

Threshold scans use 500/750/1000/1500 ADC, with local-hit and cumulative deepest-active probabilities separated. Early/end-window peaks, constant traces and repeated maxima are recorded; no hardware saturation level is invented. Baseline sensitivity and run-held-out, unlabelled mixture checks are included. Mixture components are never named p or d.

## MC sum repair and restricted-feature benchmark

Use `edep_layer_0..7`, not four `edep_B*` aliases. For mapping 1/3/5/7:

`Delta=D1; sparse E=D3+D5+D7; full E=D2+D3+D4+D5+D6+D7`.

The stored full column equals the sparse column everywhere, but differs from the correct physical sum in **10,796/14,112 events**. Median full-minus-sparse = **42.787803253470564 MeV**. D0 and D1 are not included in the downstream sum. The alternate 0/2/4/6 mapping changes the boundary and is only a nuisance scenario.

Labels remain the producer's **first-stored charged B-entrance-hit species**, not independently verified primary-track identity. Deposits include event secondaries. Sample I/II are disjoint first-stack-hit trigger proxies. Recalculating E does not repair these limitations.

Four comparisons use the same 14,075 p/d-labelled rows, five GroupKFold splits on generated `event_id//10000` blocks, and log(1+deposit/1 MeV) features. Entrance kinetic energy, PDG, event/run IDs, sample labels and termination truth are not predictors. Scaling is trained inside each fold. HGB: 100 iterations, 15 leaves, learning rate 0.07, minimum leaf support 30, no early stopping. Seed 20260907.

| Comparison | AUC | 95% interval | AP |
|---|---:|---|---:|
| Sparse two-variable logistic | 0.901095 | [0.895452, 0.906453] | 0.644045 |
| Sparse two-variable HGB | 0.975218 | [0.973258, 0.977222] | 0.885442 |
| Four-readout HGB | 0.975274 | [0.973338, 0.977228] | 0.885249 |
| Correct full-segmentation HGB diagnostic | 0.979444 | [0.977780, 0.981347] | 0.903103 |

These six-decimal values are transcribed from executed `results.json`. In particular exact full-model AUC is 0.9794438790800919, AP is 0.9031025668437734, and AUC interval is [0.977780104265695, 0.9813471006978084]; these replace the overprecise transcription in the preceding draft commit.

Intervals use 300 block resamples of fixed out-of-fold predictions, not refitting or source/label/detector uncertainty. Complete predictions, per-proxy-sample metrics, reliability and fixed-0.5 operating points are exported. These measure **stored-label agreement in deposit-level MC**, not detector/digitized performance or beam PID. They cannot be subtracted from the older 0.898 as a correction because campaign, selection, mapping and labels differ.

## Reproduce and verify

Delivered full bundle: `python build_notebook.py`, then `OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 CCB_OFFLINE=1 python execute_notebook.py`. Extract the input artifact into `inputs/` for offline execution. The notebook also supports pinned online retrieval. No paid HF compute subscription is needed; the attempted HF job was rejected with HTTP402 and did not start.

Independent core, without reading derived notebook tables:

```bash
OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 python chatgpt_todo/raw_pid_notebook_20260907/reproduce_core.py --inputs INPUT_DIRECTORY --out independent_check.json
```

It independently reconstructs amplitudes and refits all comparisons. Raw point estimates and all AUC/AP outputs matched the notebook with `rtol=atol=1e-10`. This is a computational cross-check by the same assistant, not independent human review. Numerical environment: Python3.13.5, numpy2.3.5, pandas2.2.3, scipy1.17.0, scikit-learn1.8.0; full environment and requirements are in the delivered bundle.

| Delivered object | SHA-256 |
|---|---|
| Executed notebook | `0a0d676652fec1099a74249d78c2333e7edc165b2d9b863bb214081af8f2de83` |
| Transparent notebook source | `b06eb3b4112db32ed2ba6d136f8c64086b94cb0fb20e83e043e051243a75af27` |
| Machine-readable results | `5f8b94f19ea4c0bab3eb54d7084fc5d1c9a63e01dc4cd314e5ccf2b7866b6067` |
| Independent check | `858aff7e8032458c61645b1ac39bbe69a1576f1fb40831015e750eb9e5243363` |

## Atomic backlog and next-session instructions

| ID | Priority/state | Acceptance condition |
|---|---|---|
| RN-001 | P0/PARTIAL | Bind every HF prefix to a full144 original by immutable event key and word-for-word comparison. Correct stale wiki layout text while preserving its history. |
| RN-002 | P0/CONFIRMED DEFECT | Repair production full sums from unique downstream physical layers; test both parities and missing layers; regenerate all dependent figures/claims. |
| RN-003 | P0/BLOCKED | Establish explicit track/parent species identity, mixed-deposit scope and label-order invariance; re-evaluate identical folds. |
| RN-004 | P0/BLOCKED | Source-bind channel mapping, actual B-only trigger logic (including any A veto), measured response and saturation. Disjoint run groups do not imply disjoint trigger acceptance. |
| RN-005 | P1/PARTIAL | Measure noise, baseline, finite-window and clip uncertainties; retain uncensored signals/missing states; propagate to observables. |
| RN-006 | P1/BLOCKED | Validate beam p/d candidate regions with independent tags or validated digitized detector/trigger response and held-out-run nuisance closure. |
| RN-007 | P1/PARTIAL | Archive the delivered full notebook/source/figures in a stable versioned repository artifact location before paper adoption; transient input retention is insufficient. |

Future sessions must first verify immutable input identity, run the core, and report whether each changed result is a raw measurement, simulation diagnostic, assumption or unresolved inference. Use detector-physics, waveform, statistics and provenance review passes, without presenting one analyst's passes as independent people. Append corrections rather than silently strengthening historical claims. No gate in the public claim ledger is promoted by this directory.
