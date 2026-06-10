# P01f: domain-residualized waveform latent benchmark

**Ticket:** `1781017209.1606.4c562bce`  
**Worker:** `testbeam-laptop-3`  
**No Monte Carlo:** raw B-stack ROOT and derived raw-data artifacts only.

## Reproduction first
The raw B-stack ROOT files were rescanned before modelling using the P01/S00 gate:
B2/B4/B6/B8, median baseline samples 0-3, and amplitude >1000 ADC.

| quantity | expected | reproduced | pass |
|---|---:|---:|---|
| selected B-stave pulses | 640737 | 640737 | True |
| P01b artifact rows | 640737 | 640737 | True |

The P01b artifact hash is `9dcffdb123a8c091781771ba9f1c6667a65af91cfabbfb64328427dfd7f865be` and its key hash is `605aa0fb0161573bf4afd95df232307823a4e7fd50a580455b0d53ee81121193`.
S01 `q_template` rows were verified row-aligned to the raw recount by run, stave,
and amplitude before target construction.

## Benchmark design
Held-out runs are `42, 57, 64, 65`.  The benchmark sample is capped at
`3000` pulses per `(run, stave)` cell, giving `133534` train and
`18187` held-out rows.  CIs are 95 percent run-block bootstraps over
the held-out runs.

Nuisance residualization regresses each representation against sample epoch,
run-family, selected-stave multiplicity, log amplitude, amplitude quartile, and
stave, using train runs only.  The physics-proxy probes are q_template top
quartile, peak group, timing-tail top quartile where timing residual labels are
available, and a P09-style anomaly proxy top 5 percent.

## Main results
| representation | physics mean balanced accuracy | nuisance mean balanced accuracy |
|---|---:|---:|
| frozen P01b latent | 0.687 | 0.504 |
| traditional hand+PCA residualized | 0.751 | 0.316 |
| ML P01b latent residualized | 0.705 | 0.326 |

Relative to the frozen P01b latent, residualization reduced mean nuisance
balanced accuracy by `0.178` for the ML latent and `0.188`
for the traditional representation.  The corresponding mean physics-proxy
retention fractions are `1.027` and `1.094`.  Values above 1.0 mean that the
held-out probe retained or recovered additional target signal after subtracting
the configured linear nuisance subspace.

## Leakage hunt
The full nuisance-probe table is in `nuisance_probe_metrics.csv`; the per-target
physics table is in `physics_probe_metrics.csv`.  Label shuffling and Gaussian
noise controls are included in `leakage_checks.csv`.

The timing-tail probe is smaller than the other physics probes because only
events present in the timing residual table carry that label.  The run-family
nuisance task is deliberately harsh: held-out run 64 is the only
`sample_ii_calib` run, so that class is unseen during supervised probe fitting.

| representation                            | task                             | family        |    value |   ci_low |   ci_high |    roc_auc |   heldout_rows |
|:------------------------------------------|:---------------------------------|:--------------|---------:|---------:|----------:|-----------:|---------------:|
| negative_control_gaussian_noise           | physics_q_template_top_quartile  | physics_proxy | 0.508553 | 0.498798 |  0.514432 |   0.506326 |          17995 |
| negative_control_gaussian_noise           | physics_peak_group               | physics_proxy | 0.334583 | 0.324518 |  0.343499 |   0.496439 |          18187 |
| negative_control_gaussian_noise           | physics_timing_tail_top_quartile | physics_proxy | 0.499712 | 0.489391 |  0.503306 |   0.49899  |           1318 |
| negative_control_gaussian_noise           | physics_anomaly_proxy_top5       | physics_proxy | 0.51659  | 0.506984 |  0.526826 |   0.518525 |          17995 |
| negative_control_gaussian_noise           | nuisance_sample_epoch            | nuisance      | 0.500547 | 0.491502 |  0.505248 |   0.502104 |          18187 |
| negative_control_gaussian_noise           | nuisance_run_family              | nuisance      | 0.243863 | 0.129977 |  0.357749 | nan        |          18187 |
| negative_control_gaussian_noise           | nuisance_topology_multiplicity   | nuisance      | 0.336909 | 0.331814 |  0.344779 |   0.505551 |          18187 |
| negative_control_gaussian_noise           | nuisance_amplitude_quartile      | nuisance      | 0.250559 | 0.246452 |  0.254727 |   0.497489 |          18187 |
| negative_control_gaussian_noise           | nuisance_stave                   | nuisance      | 0.251345 | 0.247527 |  0.255636 |   0.499503 |          18187 |
| ml_p01b_latent_residualized_label_shuffle | physics_q_template_top_quartile  | physics_proxy | 0.343389 | 0.304641 |  0.391194 |   0.286391 |          17995 |
| ml_p01b_latent_residualized_label_shuffle | physics_peak_group               | physics_proxy | 0.117822 | 0.084844 |  0.160987 |   0.282409 |          18187 |
| ml_p01b_latent_residualized_label_shuffle | physics_timing_tail_top_quartile | physics_proxy | 0.470146 | 0.431243 |  0.516838 |   0.433066 |           1318 |
| ml_p01b_latent_residualized_label_shuffle | physics_anomaly_proxy_top5       | physics_proxy | 0.555159 | 0.475053 |  0.646337 |   0.54316  |          17995 |
| ml_p01b_latent_residualized_label_shuffle | nuisance_sample_epoch            | nuisance      | 0.500002 | 0.457662 |  0.531698 |   0.487477 |          18187 |
| ml_p01b_latent_residualized_label_shuffle | nuisance_run_family              | nuisance      | 0.248118 | 0.108102 |  0.388135 | nan        |          18187 |
| ml_p01b_latent_residualized_label_shuffle | nuisance_topology_multiplicity   | nuisance      | 0.335324 | 0.3171   |  0.351493 |   0.494602 |          18187 |
| ml_p01b_latent_residualized_label_shuffle | nuisance_amplitude_quartile      | nuisance      | 0.260887 | 0.238994 |  0.268089 |   0.487814 |          18187 |
| ml_p01b_latent_residualized_label_shuffle | nuisance_stave                   | nuisance      | 0.2789   | 0.246311 |  0.301529 |   0.504997 |          18187 |

## Verdict
The frozen P01b latent retains both pulse-shape and acquisition-domain signals.
Linear orthogonalization removes a large fraction of nuisance probe performance
while keeping the averaged physics-proxy probes above the frozen-latent baseline.
The traditional hand+PCA residualized representation is still stronger than the
ML residualized P01b latent on these proxies, so the residualized ML latent is
best treated as a robustness-control representation rather than a replacement
for target-specific waveform features.

## Provenance
`manifest.json` records input sha256 values, the command, git commit, seeds, and
output hashes.  Runtime was `252.0` s on `billy`.
