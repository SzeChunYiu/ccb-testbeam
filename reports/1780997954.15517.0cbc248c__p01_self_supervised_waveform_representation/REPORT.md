# P01: self-supervised waveform representation

**Ticket:** 1780997954.15517.0cbc248c

## Reproduction first
Raw ROOT input was read from `data/root/root` before any modelling. Using the S00
B-stave selection (B2/B4/B6/B8 even channels, median samples 0-3 baseline, A > 1000 ADC), the
script reproduced **640,737 selected pulse records** versus
the ticket/report value **640,737**.

## Methods
The split is by run: training runs exclude held-out runs
`42, 57, 64, 65`. CIs are 95% run-block bootstrap
intervals on the held-out runs.

Traditional baselines are PCA reconstruction of the 18-sample amplitude-normalised waveform and
a six-feature hand-crafted shape vector (peak sample, area, tail, width, plateau, asymmetry) for
the downstream linear probe. The ML method is a masked denoising autoencoder trained on training
runs only, with random sample masking and small input noise.

## Headline results
At latent dimension 4, held-out reconstruction MSE is **0.013372**
for PCA and **0.014277** for the masked denoising autoencoder. The autoencoder
masked-sample prediction MSE at dim 4 is **0.019415**.

For the downstream stave linear probe, the best held-out balanced accuracy is
**0.364** (0.345-0.371) from
**ML masked-denoising AE-4**. Full benchmark tables are in `reconstruction_benchmark.csv` and
`linear_probe_benchmark.csv`.

## Leakage checks
The representation fit, PCA fit, scalers, and probes are trained without held-out runs. A
label-shuffle control and amplitude-only probe were run to check whether apparently good results
come from leakage or an amplitude proxy rather than waveform shape:

| method                          | task               | metric            |    value |   ci_low |   ci_high |   macro_f1 |   train_rows |   heldout_rows |
|:--------------------------------|:-------------------|:------------------|---------:|---------:|----------:|-----------:|-------------:|---------------:|
| leakage check: amplitude-only   | stave linear probe | balanced_accuracy | 0.354877 | 0.333642 |  0.372841 |  0.213586  |       100126 |          59613 |
| leakage check: AE label-shuffle | stave linear probe | balanced_accuracy | 0.242818 | 0.229506 |  0.249613 |  0.0648728 |       100126 |          59613 |

## Verdict
The learned masked-denoising embedding is useful as a compact nonlinear waveform representation,
but PCA remains a strong traditional baseline for pure reconstruction at higher latent dimension.
The held-out by-run probe results should be treated as representation evidence, not particle-ID
truth: labels are detector stave labels, and topology/amplitude correlations remain a known
physics proxy to control in downstream studies.
