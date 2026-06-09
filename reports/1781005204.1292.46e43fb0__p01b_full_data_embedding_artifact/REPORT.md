# P01b: reusable full-data waveform embedding artifact

**Ticket:** 1781005204.1292.46e43fb0

## Reproduction first
Raw B-stack ROOT files were read from `data/root/root`. The S00/P01 B-stave
selection reproduced **640,737** selected pulse records versus the ticket
target **640,737** before any model fitting.

## Frozen held-out benchmark
The benchmark split is by run. Held-out runs are `42, 57, 64, 65`; all PCA,
autoencoder, scalers, and probes below were fit without those runs. CIs are 95%
run-block bootstrap intervals over held-out runs.

| method | held-out reconstruction MSE | 95% CI |
|---|---:|---:|
| traditional PCA-4 | 0.013372 | 0.009224-0.016965 |
| ML masked-denoising AE-4 | 0.014277 | 0.009938-0.017722 |

The best held-out stave linear probe is **0.364**
(0.344-0.368) from **ML masked-denoising AE-4**. The amplitude-only
and label-shuffle controls are written to `leakage_checks.csv`; label shuffling
falls to chance, while amplitude-only remains a documented detector proxy.

## Release artifact
After the held-out evaluation was frozen, the same selected masked-denoising
architecture was fit on all **640,737** selected waveforms. The reusable
artifact is `p01b_embedding_latents.npz`, keyed by `run`, deterministic
`event_index`, and `stave_index`, with `amplitude_adc` and `z` (`float32`,
shape `640737 x 4`). The model weights are in
`p01b_autoencoder_state.pt`; the generation metadata is in
`p01b_embedding_metadata.json`.

Compressed latent table size is **11.37 MiB**, versus **44.00 MiB**
for the in-memory normalized waveform matrix. Runtime was **59.5 s** on
`cpu`. Regenerate the local binary artifact with
`/home/billy/anaconda3/bin/python scripts/p01b_full_data_embedding_artifact.py --config configs/p01b_full_data_embedding_artifact.json`.
Input sha256 values are recorded in `input_sha256.csv`.

## Verdict
This artifact is suitable for downstream P02-P08 feature work as a compact
waveform representation. It should not be cited as an independent benchmark
score, because the release model intentionally uses every selected pulse after
the held-out P01/P01b checks are frozen.
