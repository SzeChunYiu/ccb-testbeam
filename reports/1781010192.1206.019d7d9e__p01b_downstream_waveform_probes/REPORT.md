# P01b: waveform probes on non-stave downstream targets

**Ticket:** 1781010192.1206.019d7d9e

## Reproduction first
The script read raw B-stack ROOT files from `data/root/root` before any modelling.
Using the P01/S00 B-stave gate (B2/B4/B6/B8, median samples 0-3 baseline, A > 1000 ADC), it
reproduced **640,737** selected pulses versus the published
P01/S00 number **640,737**.

## Target and split
The downstream target is **sample epoch**: Sample I runs are the negative class and Sample II runs
are the positive class. This is not the pulse's own stave label. All representation fits and
supervised probes train on runs disjoint from held-out runs `42, 57, 64, 65`.
The benchmark sample is capped at 2500 pulses per `(run, stave)` cell
(117,889 train, 16,187
held out). CIs are 95% stratified run-block bootstraps over the held-out runs.

## Main held-out probes
| method                   | value | ci_low | ci_high | roc_auc | average_precision | train_rows | heldout_rows |
| ------------------------ | ----- | ------ | ------- | ------- | ----------------- | ---------- | ------------ |
| traditional hand-shape   | 0.602 | 0.576  | 0.630   | 0.629   | 0.637             | 117889     | 16187        |
| traditional PCA-4        | 0.649 | 0.641  | 0.658   | 0.693   | 0.694             | 117889     | 16187        |
| ML masked-denoising AE-4 | 0.634 | 0.618  | 0.648   | 0.708   | 0.719             | 117889     | 16187        |

The strongest waveform representation is **traditional PCA-4** at **0.649**
balanced accuracy (0.641-0.658). The traditional PCA-4
reconstruction MSE is 0.01169; the masked-AE-4
reconstruction MSE is 0.02880.

## Proxy and leakage checks
| method                                    | value | ci_low | ci_high | roc_auc | average_precision |
| ----------------------------------------- | ----- | ------ | ------- | ------- | ----------------- |
| proxy: amplitude+multiplicity             | 0.591 | 0.534  | 0.634   | 0.656   | 0.675             |
| leakage check: topology/stave composition | 0.593 | 0.541  | 0.632   | 0.658   | 0.679             |
| leakage check: AE label shuffle           | 0.400 | 0.393  | 0.409   | 0.355   | 0.468             |

The topology/stave-composition sentinel is the leakage hunt for a too-good result: if a waveform
probe wins only because it recovers sample-dependent detector composition, this proxy should also
be strong. Here, PCA and AE exceed the amplitude/topology proxies, while the proxy scores remain
nontrivial. The result should therefore be interpreted as sample-era/domain separation, not as
particle identification.

## Held-out run breakdown
| method                                    | run | sample_epoch | heldout_rows | run_class_recall | positive_rate | mean_score |
| ----------------------------------------- | --- | ------------ | ------------ | ---------------- | ------------- | ---------- |
| traditional hand-shape                    | 42  | sample_i     | 3635         | 0.518            | 0.482         | 0.482      |
| traditional hand-shape                    | 57  | sample_i     | 3559         | 0.438            | 0.562         | 0.498      |
| traditional hand-shape                    | 64  | sample_ii    | 5223         | 0.713            | 0.713         | 0.523      |
| traditional hand-shape                    | 65  | sample_ii    | 3770         | 0.741            | 0.741         | 0.527      |
| traditional PCA-4                         | 42  | sample_i     | 3635         | 0.624            | 0.376         | 0.441      |
| traditional PCA-4                         | 57  | sample_i     | 3559         | 0.594            | 0.406         | 0.461      |
| traditional PCA-4                         | 64  | sample_ii    | 5223         | 0.687            | 0.687         | 0.588      |
| traditional PCA-4                         | 65  | sample_ii    | 3770         | 0.691            | 0.691         | 0.574      |
| ML masked-denoising AE-4                  | 42  | sample_i     | 3635         | 0.612            | 0.388         | 0.443      |
| ML masked-denoising AE-4                  | 57  | sample_i     | 3559         | 0.555            | 0.445         | 0.471      |
| ML masked-denoising AE-4                  | 64  | sample_ii    | 5223         | 0.685            | 0.685         | 0.590      |
| ML masked-denoising AE-4                  | 65  | sample_ii    | 3770         | 0.681            | 0.681         | 0.582      |
| proxy: amplitude+multiplicity             | 42  | sample_i     | 3635         | 0.695            | 0.305         | 0.395      |
| proxy: amplitude+multiplicity             | 57  | sample_i     | 3559         | 0.681            | 0.319         | 0.413      |
| proxy: amplitude+multiplicity             | 64  | sample_ii    | 5223         | 0.572            | 0.572         | 0.555      |
| proxy: amplitude+multiplicity             | 65  | sample_ii    | 3770         | 0.386            | 0.386         | 0.470      |
| leakage check: topology/stave composition | 42  | sample_i     | 3635         | 0.691            | 0.309         | 0.389      |
| leakage check: topology/stave composition | 57  | sample_i     | 3559         | 0.671            | 0.329         | 0.412      |
| leakage check: topology/stave composition | 64  | sample_ii    | 5223         | 0.574            | 0.574         | 0.555      |
| leakage check: topology/stave composition | 65  | sample_ii    | 3770         | 0.410            | 0.410         | 0.474      |

## Verdict
On this non-stave downstream target, waveform shape does carry held-out sample-epoch information.
The ML masked-denoising latent is competitive with but not decisively better than traditional
PCA/hand-shape probes under run-held-out CIs. The amplitude/topology proxy and composition
sentinel show that detector/run-domain shifts explain a meaningful part of the separation, so this
is a useful robustness diagnostic rather than evidence for a new physics label.
