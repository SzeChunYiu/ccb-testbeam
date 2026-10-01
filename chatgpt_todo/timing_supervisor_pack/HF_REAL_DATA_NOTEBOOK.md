# Hugging Face real-data timing notebook contract

## Data source

Use the public Hugging Face dataset:

```text
billyyiu747/ccb-testbeam
```

The dataset card identifies:

- `parquet/` as ucesb RAW ADC tables, with sample entry point `parquet/sample/events_sample.parquet`;
- `sorted/` as hrdSorter waveform features, with sample entry point `sorted/sample/events_sample.parquet`;
- the source decode chain `.lmd -> ucesb-hibeam -> h101 ROOT -> hrdSorter`.

The interactive teaching notebook must call `HfApi(..., files_metadata=True)` and pin the dataset revision SHA before downloading any input with `hf_hub_download`. Every consumed file is recorded with the HF path, revision, local SHA-256, and loaded event count.

## Fail-closed frame rule

The physical timing lane requires a source `h101/HRDv` representation with exactly

```text
8 channels x 18 samples/channel = 144 words/event.
```

The notebook first inspects the real HF raw-Parquet schema. If it exposes 128 waveform-like scalar columns, the 128-word table is treated only as a staging/forensic representation. It is **not** silently reshaped as `8 x 16` for detector timing. The notebook instead inventories HF `.root`/archive files, resolves an explicitly run-bound h101 source, checks the `HRDv` vector-length distribution, and raises before any physical timing plot if the 144-word contract fails.

The historical `0.096--0.146 ns` B4--B6 result remains `RETRACTED / NON-PHYSICAL` and is shown only in a labelled forensic section.

## Student-facing plot sequence

The notebook teaches and diagnoses, in order:

1. HF revision / file inventory / SHA-256 provenance;
2. raw Parquet schema and 128-vs-144 contract;
3. source ROOT `HRDv` length audit;
4. raw waveform overlays for mapped staves;
5. polarity excursions and source-bound sign convention;
6. baseline RMS and pretrigger slope;
7. amplitude and peak-sample maps;
8. interactive single-event CFD threshold/bracket/interpolation;
9. unique-event cut flow;
10. per-stave timestamp and CFD-phase distributions;
11. `t_i` vs `t_j` and peak-sample lattice;
12. residual before/after constant TOF;
13. linear/log residual histograms and QQ diagnostics;
14. CFD-fraction scan with sigma68, core sigma, RMS and fit quality;
15. timewalk vs amplitude with train-only correction and held-out closure;
16. residual vs baseline-noise/crossing-slope jitter proxy;
17. residual vs interpolation phase;
18. run-by-run stability and run-block bootstrap;
19. leading-edge / CFD / template-phase comparison on the same held-out complete-event population;
20. historical 0.1-ns scan, explicitly retracted;
21. optional real 128-word staging-frame forensic overlays, disabled by default;
22. deterministic-boundary simulation explaining sub-sample artificial cores;
23. all three pair variances;
24. conditional B4/B6/B8 variance decomposition;
25. common-mode cancellation and `sigma68/sqrt(2)` counterexamples;
26. injection/recovery closure;
27. systematic variations;
28. final machine-readable inference gate.

## Inference boundary

A pair residual is not a stave resolution:

```text
Var(t_i - t_j) = sigma_i^2 + sigma_j^2 - 2 Cov(t_i,t_j).
```

The three-pair formula is presented only as a conditional zero-covariance variance model. `sigma68` is never assumed quadrature-additive. A single-stave headline remains blocked until pulse identity, held-out timewalk/phase/run stability, covariance/common-mode modelling, injection/recovery coverage, and the systematic budget are signed off.

## Notebook artifact

The generated notebook is named:

```text
ccb_timing_from_hf_raw_data.ipynb
```

It contains 90 cells / 49 Python code cells. All code cells were syntax-compiled after generation. The current ChatGPT execution environment could inspect the HF dataset card/metadata but could not execute the remote binary dataset download, so real-data numerical outputs must be produced by running the notebook in an environment with Hugging Face download access. The notebook deliberately has no silent synthetic fallback.
