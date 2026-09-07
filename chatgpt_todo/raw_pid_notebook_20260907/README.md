# Raw-ADC E–DeltaE / proton–deuteron notebook reanalysis

Date: 2026-09-07. Audited base: `cec9edc28257e0699c70c17fa9b2e8d806a3d42a`.

## Scope and evidence state

**EXECUTED RAW-ADC RECONSTRUCTION + MC DEPOSIT-TABLE REANALYSIS; NOT VALIDATED BEAM PID.**

The user requested a step-by-step Jupyter notebook rebuilt from the Hugging Face raw data. The completed notebook contains 34 cells, 16 executed code cells, 35 diagnostic/data/MC plots and six equation images; no error outputs. Eleven synthetic software tests pass. The full executed notebook, HTML, transparent percent-cell source, figures, event features, predictions, input manifest and numerical receipts are delivered in the conversation artifact bundle. This directory preserves the central numerical reproducer and the repository handoff, not a copy of the multi-megabyte rendered notebook.

Do not overwrite the unrelated main `ACTIVE_TASK.md` or concurrent `chatgpt/raw-pid-notebook-20260907` / PR #1625. This work uses `chatgpt/raw-pid-notebook-reproducible-20260907` and the isolated input workflow. Raw files and production analysis scripts are unchanged.

## Input provenance

- HF dataset: `billyyiu747/ccb-testbeam`; revision `0b25f28e0144a3d1597afcdd3446ad1abd3d2d74`.
- All rows of `parquet/events/hrdb_run_0044.parquet` through runs 44–63, plus run 65: **650,970 events**.
- Sample I: runs 44–57, 388,879 raw events. Sample II: runs 58–63 and 65, 262,091 raw events.
- Public read-only retrieval workflow: `.github/workflows/raw-pid-notebook-inputs-20260907.yml`; commit `3c2c4a0382f17538037bee708a699ae61752080d`; run `34101549430`; job `101676903245`, SUCCESS.
- Artifact `10010695645`, `raw-pid-notebook-inputs`; ZIP SHA-256 `c1b58eac8761754189400c477109d8298ab5bbfbebb77bc4bc826febe1f3120d`. Retention ends 2026-09-14; pinned originals remain the source of record.
- Raw NPZ SHA-256 `c64f00acf27e6f574ec4831581e2df172be3be71a822e94f71b463fba75ad41e`. All per-file Parquet hashes, row counts and the resolved HF revision are recorded in the artifact's `manifest.json`.
- MC source: `reports/paper_618_species_penetration_2m_20260814T1449Z/deltaE_E_events_mc.parquet` at the audited Git revision; SHA-256 `d67b0bf47e1485877af9b9732b0139bbf5a2fd88733e6a7c2d4e2266184c5c40`.
- MC transport CSV-gzip SHA-256 `f6d791339fd4348ff5451eadf76b2524ad0bb92d4d3eccfb2bb71d43f378637a`; 14,112 rows, all unit weights. No new Geant4 production was performed.

## Critical layout correction: supersedes the earlier 8x16 narrative

Read `configs/channel_polarity_v2.json` at the audited revision. It is explicitly **RETRACTED_20260816_TRUNCATED_STAGING_DESYNC**. Its retraction documents the staged 128 words as the first 128 words of a true channel-major **8x18=144-word** frame. The apparent v2 polarity reversal came from reading adjacent pedestal levels as pulses under the wrong stride. Operative v1 has even primary channels positive-going and odd duplicates inverted.

The four primary readouts are fully inside the prefix:

| Readout | Physical ADC channel | Zero-based raw slice |
|---|---:|---|
| B2 | 0 | 0:18 |
| B4 | 2 | 36:54 |
| B6 | 4 | 72:90 |
| B8 | 6 | 108:126 |

The last duplicate channel lacks samples and is not used. Each source row is preserved; no global cross-event reshape occurs. Event identity is `(HF revision, source file, event_idx)`, not a reused DAQ counter. The notebook shows the median raw-word pedestal profile under both candidate grids. This supports the documented interpretation, but does not replace an independent full144/prefix128 comparison for every run.

On identical raw events, positive peak heights above 1000 ADC change as follows:

| Readout | Correct 18-stride | Wrong 16-stride |
|---|---:|---:|
| B2 | 329635 | 328699 |
| B4 | 27680 | 55352 |
| B6 | 14242 | 22045 |
| B8 | 5805 | 13062 |

These differences are reconstruction effects, not new particle species.

## Fresh beam-data calculations

For each primary channel: `baseline = median(samples 0..3)`, `A = max(samples 0..17) - baseline`. Preserve every channel measurement before thresholding. Define `Delta_ADC=A(B2)` and `E_ADC=A(B4)+A(B6)+A(B8)`. Signed finite-window area uses samples 4..17 and remains ADC-samples, not calibrated charge or MeV.

The E–DeltaE headline selection below is the explicit **B2 > 1000 ADC anchor**, not an arbitrary union of selected pulse rows. This differs from historical table populations.

| Quantity | Sample I | Sample II |
|---|---:|---:|
| Raw events | 388879 | 262091 |
| B2-anchor events | 241422 | 88213 |
| Median Delta [ADC] | 6542.5 | 3350.0 |
| Median uncensored downstream sum [ADC] | 77.5 | 97.0 |
| Pearson r | -0.05446549746028057 | -0.08443112404540734 |
| P(any downstream A>1000 given B2>1000) | 0.02631491744745715 | 0.238184848038271 |
| Whole-run bootstrap 95% interval | [0.021435663886391808, 0.03328539687035178] | [0.13254293277824286, 0.3489220355978942] |

Run intervals use 2,000 replicates, 14 and 7 runs respectively. They are statistical/run-variability intervals, not hardware-systematic or species-purity intervals. The wide Sample-II interval must not be hidden behind a binomial event error.

An intentionally censored counterfactual zeroes downstream amplitudes <=1000 before summation. It makes 97.3685% / 76.1815% of anchored Sample-I/II events have exactly zero E and gives zero median E in both samples. Quiet-channel maxima have positive noise bias: the uncensored 77.5/97-ADC medians are NOT proof of genuine deposited energy or of non-stopping particles.

Threshold scans use 500/750/1000/1500 ADC on reconstructed signals. Local hit probability and cumulative deepest-active-readout probability are tabulated separately. Early/end-window peaks, constant traces and repeated-maximum plateaus are recorded as diagnostics. No numerical hardware saturation level is invented. Unlabelled mixture fits use held-out runs and never name components p or d.

## MC full-sum repair and feature-restricted evaluation

Use physical `edep_layer_0..7`, not the four `edep_B*` aliases. For the stored 1/3/5/7 map:

`Delta=D1; E_sparse=D3+D5+D7; E_full=D2+D3+D4+D5+D6+D7`.

The stored full column equals the sparse column everywhere; it differs from the correct physical full sum in **10,796 / 14,112 events**. The median full-minus-sparse deposit is **42.787803253470564 MeV**. Upstream D0 and the Delta layer D1 are not added to the downstream sum. An alternative 0/2/4/6 map changes the boundary and is only a nuisance scenario.

The labels remain the producer's first-stored charged B-entrance-hit species, NOT independently verified primary-track identity. Deposits are event-level sums. The trigger split is a disjoint first-stack-hit proxy. These problems are not repaired by recalculating E.

Four models use the same 14,075 p/d-labelled rows, five GroupKFold splits on `event_id//10000`, and only log(1+deposit/1 MeV) features. No entrance kinetic energy, PDG, sample, event ID, run ID or termination is a predictor. Logistic scaling is trained inside each fold. HGB uses 100 iterations, 15 leaves, learning rate 0.07, minimum leaf support 30, no early stopping. Seed 20260907.

| Comparison | AUC | 95% block-bootstrap interval | AP |
|---|---:|---|---:|
| Sparse two-variable logistic | 0.9010949845 | [0.8954524310, 0.9064531203] | 0.6440454657 |
| Sparse two-variable HGB | 0.9752178245 | [0.9732581798, 0.9772220779] | 0.8854418073 |
| Four-readout HGB | 0.9752744542 | [0.9733382818, 0.9772279854] | 0.8852490091 |
| Correct full-segmentation HGB diagnostic | 0.9794444738 | [0.9777796533, 0.9813467730] | 0.9031025762 |

The last row's display is rounded; exact values belong to the delivered machine-readable `results.json`. ROC/AP intervals use 300 generated-event-block resamples of fixed out-of-fold predictions, not refitting/bootstrap of the whole modelling process. Per-proxy-sample metrics, reliability, fixed-0.5 operating points and complete predictions are exported. These are **stored-label agreement in deposited-energy MC**, not detector-only/digitized performance or beam PID. Do not call the high AUC a measured proton/deuteron identification result. Do not subtract it from the older 0.898 as a correction: campaign, selection, mapping and label definitions differ.

## Validation and reproducibility

In the delivered bundle: `python build_notebook.py`; then `OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 CCB_OFFLINE=1 python execute_notebook.py`. Offline execution requires the retrieved input artifact extracted into `inputs/`. The notebook also implements pinned online retrieval for connected machines. A HF paid compute job is not required; the attempted HF CPU job was blocked with HTTP402 and never started.

The separate checked core in this directory runs as:

```bash
OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 python chatgpt_todo/raw_pid_notebook_20260907/reproduce_core.py --inputs INPUT_DIRECTORY --out independent_check.json
```

It reconstructs from raw words and refits all four comparisons without consuming notebook-derived tables. Raw point estimates and all AUC/AP outputs matched the notebook at `rtol=atol=1e-10`. This is computational cross-checking by the same assistant, not independent human review. Full repository tests were not run and no publication gate is promoted.

Executed notebook SHA-256: `0a0d676652fec1099a74249d78c2333e7edc165b2d9b863bb214081af8f2de83`.
Transparent full source SHA-256: `b06eb3b4112db32ed2ba6d136f8c64086b94cb0fb20e83e043e051243a75af27`.
Machine-readable result SHA-256: `5f8b94f19ea4c0bab3eb54d7084fc5d1c9a63e01dc4cd314e5ccf2b7866b6067`.
Independent check SHA-256: `858aff7e8032458c61645b1ac39bbe69a1576f1fb40831015e750eb9e5243363`.

## Next-session atomic backlog

| ID | Priority / state | Acceptance condition |
|---|---|---|
| RN-001 | P0 / PARTIAL | Bind each HF 128-word prefix to a full144 original by immutable event key and word-for-word comparison; quarantine any mismatch. Correct the stale 8x16 wiki narrative without removing its provenance. |
| RN-002 | P0 / CONFIRMED DEFECT | Repair production full-sum discovery to consume unique downstream physical layers; test both parities and reject missing layers; regenerate every dependent figure and claim. |
| RN-003 | P0 / BLOCKED | Replace first-stored-hit species labels with an explicit track/parent identity and quantify mixed-species deposits and label-order invariance. Re-evaluate the same folds. |
| RN-004 | P0 / BLOCKED | Source-bind channel mapping, actual B-only trigger logic (including whether an A veto exists), readout response and saturation calibration. Do not confuse disjoint run sets with disjoint trigger acceptance. |
| RN-005 | P1 / PARTIAL | Establish noise and baseline/finite-window/clip uncertainties with measured calibration; retain uncensored signals and missing states; propagate to PID-sensitive observables. |
| RN-006 | P1 / BLOCKED | Validate candidate beam p/d regions with independent tags or a validated digitized detector-response and trigger model, using held-out runs and full nuisance propagation. |
| RN-007 | P1 / PARTIAL | Archive the delivered rendered notebook/full source and figure hashes in a stable versioned repository artifact location before paper adoption; transient input artifact retention is not permanent provenance. |

Required review passes for any closure: detector physics, waveform reconstruction, statistics and provenance. State whether these are role-separated passes by one analyst or genuinely independent reviewers. Future sessions must preserve the immutable input identity, rerun the core before interpreting changed results, and append corrections rather than silently overwriting historical claims.
