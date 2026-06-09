# Study report: P02c - full-S01 q_template cluster stability

**Ticket:** 1781009575.1631.563755ca
**Command:** `/home/billy/anaconda3/bin/python reports/1781009575.1631.563755ca/p02c_full_s01_q_template_cluster_stability.py`

## Reproduction first
Raw B-stack ROOT was scanned from `data/root/root` before modeling. The S00 B-stave selected-pulse gate reproduced **640,737** records versus expected **640,737**.
For the original P02 run/sample recipe, the script sampled **60,000** pulses and reproduced the early-peak `peak<=3` class at **4.39%**, matching the reported approximately 4.4% anomalous class.
The committed S01 `q_template_per_pulse.csv.gz` was then aligned row-for-row by run, event number, EVT, stave, channel, amplitude, peak sample, and area. Alignment passed for **640,737** rows; median full-S01 q-template RMSE is **0.0364**.

## Methods
All modeling used a run/stave-balanced subsample of **31,407** selected pulses from the reproduced raw population with exact S01 q-template rows attached. The primary split is GroupKFold by run; a leave-one-stave-held-out stress test checks stave sampling artifacts. Hyperparameters (`n_clusters`) are selected by training-fold BIC only.

- **Traditional:** hand-crafted shape variables (peak sample, area/peak, tail/late/early fractions, widths, final sample, max negative step, asymmetry) plus PCA-4 and diagonal GMM.
- **ML:** P02-style fully connected autoencoder on the 18 normalized waveform samples, using the held-in fold only, then diagonal GMM in the learned latent.
- **Topology comparisons:** full-S01 q-template residual bins, peak groups, event downstream topology, CFD20 downstream-span (`D_t`) class, and manual diagnostic flags. q-template values are labels for evaluation only; they are not model inputs.

## Held-out stability

| Split | Method | S01 q_template AMI / purity | peak AMI / purity | downstream AMI / purity | D_t AMI / purity | manual flag AMI / purity |
|---|---|---:|---:|---:|---:|---:|
| run | traditional | 0.154 [0.145,0.162] / 0.396 [0.384,0.408] | 0.490 [0.466,0.509] / 0.800 [0.786,0.813] | 0.108 [0.088,0.124] / 0.641 [0.609,0.678] | 0.090 [0.078,0.104] / 0.677 [0.643,0.710] | 0.674 [0.646,0.711] / 0.938 [0.932,0.944] |
| run | ml_autoencoder | 0.134 [0.125,0.142] / 0.398 [0.392,0.405] | 0.441 [0.417,0.467] / 0.799 [0.781,0.815] | 0.105 [0.083,0.129] / 0.671 [0.645,0.699] | 0.098 [0.087,0.109] / 0.677 [0.644,0.712] | 0.470 [0.451,0.499] / 0.898 [0.883,0.914] |
| stave | traditional | 0.171 [0.166,0.177] / 0.408 [0.404,0.411] | 0.508 [0.344,0.613] / 0.824 [0.800,0.845] | 0.028 [0.013,0.045] / 0.849 [0.784,0.913] | 0.076 [0.037,0.115] / 0.724 [0.638,0.884] | 0.606 [0.465,0.694] / 0.930 [0.911,0.953] |
| stave | ml_autoencoder | 0.154 [0.132,0.180] / 0.424 [0.400,0.455] | 0.456 [0.402,0.511] / 0.788 [0.755,0.817] | 0.035 [0.016,0.061] / 0.849 [0.786,0.912] | 0.079 [0.024,0.135] / 0.735 [0.652,0.886] | 0.411 [0.341,0.473] / 0.892 [0.834,0.942] |

## Leakage checks

The run-held-out ML clusters have run-label AMI **0.191** and stave-label AMI **0.010**. Traditional clusters are similar: run AMI **0.187**, stave AMI **0.025**.
The target itself has run AMI **0.003** and stave AMI **0.003**, so q-template bins are not acting as a direct run or stave code.
The paired run-bootstrap CI for ML minus traditional on S01 q-template AMI is **[-0.026, -0.012]**; for manual-flag AMI it is **[-0.235, -0.175]**. Leakage alarm status: **not triggered** under the pre-set `AMI > 0.80` too-good threshold.

## Verdict

Using the exact full-S01 q_template table does not overturn P02b: clusters associate most strongly with peak/manual pulse morphology, while S01 q-template, downstream topology, and D_t are weaker held-out associations. The q-template signal is stable enough to be a pulse-shape diagnostic, but neither method produces a suspiciously perfect q-template classifier.

## Reproducibility

`manifest.json` records raw input SHA256 hashes, command, git commit, software versions, and output hashes. Supporting CSVs and figures are in `reports/1781009575.1631.563755ca/`.
