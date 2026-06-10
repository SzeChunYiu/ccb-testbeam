# Study report: P02b - cluster topology stability across runs and staves

**Ticket:** 1781004956.538.5fc10cd7
**Command:** `/home/billy/anaconda3/bin/python reports/1781004956.538.5fc10cd7/p02b_cluster_topology_stability.py`

## Reproduction first
Raw B-stack ROOT was scanned from `data/root/root` before modeling. The S00 B-stave selected-pulse gate reproduced **640,737** records versus expected **640,737**.
For the original P02 run/sample recipe, the script sampled **60,000** pulses and reproduced the early-peak `peak<=3` class at **4.39%**, matching the reported approximately 4.4% anomalous class.

## Methods
All modeling used a run/stave-balanced subsample of **31,407** selected pulses from the reproduced raw population. The primary split is GroupKFold by run; a leave-one-stave-held-out stress test checks stave sampling artifacts. Hyperparameters (`n_clusters`) are selected by training-fold BIC only.

- **Traditional:** hand-crafted shape variables (peak sample, area/peak, tail/late/early fractions, widths, final sample, max negative step, asymmetry) plus PCA-4 and diagonal GMM.
- **ML:** P02-style fully connected autoencoder on the 18 normalized waveform samples, using the held-in fold only, then diagonal GMM in the learned latent.
- **Topology comparisons:** q-template residual bins from train-fold median templates, peak groups, event downstream topology, CFD20 downstream-span (`D_t`) class, and manual diagnostic flags.

## Held-out stability

| Split | Method | q_template AMI / purity | peak AMI / purity | downstream AMI / purity | D_t AMI / purity | manual flag AMI / purity |
|---|---|---:|---:|---:|---:|---:|
| run | traditional | 0.357 [0.342,0.371] / 0.554 [0.538,0.575] | 0.522 [0.502,0.540] / 0.848 [0.838,0.856] | 0.124 [0.102,0.151] / 0.677 [0.647,0.697] | 0.101 [0.091,0.112] / 0.684 [0.656,0.719] | 0.538 [0.516,0.554] / 0.945 [0.941,0.951] |
| run | ml_autoencoder | 0.377 [0.354,0.389] / 0.570 [0.555,0.586] | 0.524 [0.503,0.544] / 0.838 [0.828,0.847] | 0.121 [0.098,0.145] / 0.673 [0.645,0.695] | 0.100 [0.089,0.110] / 0.684 [0.655,0.716] | 0.490 [0.463,0.513] / 0.916 [0.909,0.926] |
| stave | traditional | 0.416 [0.347,0.458] / 0.709 [0.696,0.731] | 0.492 [0.315,0.612] / 0.852 [0.808,0.894] | 0.032 [0.019,0.043] / 0.851 [0.786,0.916] | 0.091 [0.044,0.139] / 0.737 [0.657,0.888] | 0.500 [0.435,0.541] / 0.932 [0.918,0.951] |
| stave | ml_autoencoder | 0.356 [0.288,0.425] / 0.673 [0.627,0.726] | 0.409 [0.368,0.450] / 0.777 [0.732,0.816] | 0.029 [0.017,0.046] / 0.851 [0.786,0.916] | 0.087 [0.033,0.142] / 0.733 [0.648,0.887] | 0.435 [0.321,0.522] / 0.892 [0.851,0.934] |

## Leakage checks

The run-held-out ML clusters have run-label AMI **0.104** and stave-label AMI **0.001**. Traditional clusters are similar: run AMI **0.108**, stave AMI **0.001**.
The paired run-bootstrap CI for ML minus traditional on manual-flag AMI is **[-0.069, -0.023]**. A large positive result would have triggered a run/stave leakage alarm; the observed deltas are treated as morphology diagnostics, not truth labels.

## Verdict

The P02 early-peak class is reproducible directly from ROOT and is not just an autoencoder artifact. The traditional and ML clusterings both recover peak/manual morphology more strongly than run identity, while q-template and downstream/D_t associations are weaker. That supports using P02 clusters as pulse-shape diagnostics, but not as standalone PID or timing-truth labels.

## Reproducibility

`manifest.json` records raw input SHA256 hashes, command, git commit, software versions, and output hashes. Supporting CSVs and figures are in `reports/1781004956.538.5fc10cd7/`.
