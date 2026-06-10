# P01a: amplitude/topology-controlled waveform representation probes

**Ticket:** 1781005204.1227.36547733

## Reproduction first
The script read raw B-stack ROOT files from `data/root/root` before any modelling.
Using the P01/S00 pulse selection (B2/B4/B6/B8, median samples 0-3 baseline, A > 1000 ADC),
it reproduced **640,737** selected pulses versus the
published gate value **640,737**.

## Controls and split
All classifiers were trained on runs disjoint from held-out runs `42, 57, 64, 65`.
The analysis sample is balanced by `(run, stave)` with at most 1500 pulses per cell
(82,118 train, 11,998 held out).
CIs are 95% run-block bootstraps on held-out runs.

Amplitude/topology proxies are represented by log10(amplitude) and selected-stave multiplicity.
Peer/topology-mask features are reported only as leakage sentinels because the mask is structurally
label-revealing for triple/quad stave probes. The controlled waveform methods first regress the
valid amplitude/multiplicity proxies out of the 18-sample normalized waveform using training runs only.

## Main held-out probes
| method                            | value | ci_low | ci_high | macro_f1 | train_rows | heldout_rows |
| --------------------------------- | ----- | ------ | ------- | -------- | ---------- | ------------ |
| traditional residual hand-shape   | 0.292 | 0.264  | 0.321   | 0.296    | 82118      | 11998        |
| traditional residual PCA-4        | 0.234 | 0.217  | 0.240   | 0.172    | 82118      | 11998        |
| ML residual masked-denoising AE-4 | 0.276 | 0.242  | 0.309   | 0.257    | 82118      | 11998        |

The best controlled waveform probe is **traditional residual hand-shape** at **0.292**
balanced accuracy (0.264-0.321).

## Proxy and leakage checks
| method                                   | value | ci_low | ci_high | macro_f1 |
| ---------------------------------------- | ----- | ------ | ------- | -------- |
| leakage check: AE label-shuffle          | 0.299 | 0.296  | 0.304   | 0.280    |
| proxy: amplitude only                    | 0.347 | 0.324  | 0.360   | 0.273    |
| proxy: topology only                     | 0.675 | 0.638  | 0.692   | 0.636    |
| proxy: amplitude+topology                | 0.669 | 0.637  | 0.683   | 0.623    |
| leakage check: peer topology mask        | 0.842 | 0.788  | 0.878   | 0.880    |
| leakage check: target-including topology | 0.828 | 0.804  | 0.848   | 0.732    |

The peer-mask and target-including topology sentinels are intentionally label-revealing for a
stave probe and land far above the multiplicity-only topology proxy; this was the leakage pattern
hunted after an initial too-good topology score. The AE label-shuffle sentinel is reported as an
additional guard against train/test leakage.

## Amplitude-stratified evaluation
| method                            | stratum    | value | ci_low | ci_high | heldout_rows |
| --------------------------------- | ---------- | ----- | ------ | ------- | ------------ |
| traditional residual PCA-4        | q1_low     | 0.225 | 0.205  | 0.256   | 3942         |
| traditional residual PCA-4        | q2_midlow  | 0.224 | 0.194  | 0.238   | 3341         |
| traditional residual PCA-4        | q3_midhigh | 0.202 | 0.192  | 0.208   | 3068         |
| traditional residual PCA-4        | q4_high    | 0.269 | 0.209  | 0.325   | 1647         |
| ML residual masked-denoising AE-4 | q1_low     | 0.200 | 0.183  | 0.215   | 3942         |
| ML residual masked-denoising AE-4 | q2_midlow  | 0.236 | 0.223  | 0.250   | 3341         |
| ML residual masked-denoising AE-4 | q3_midhigh | 0.249 | 0.213  | 0.274   | 3068         |
| ML residual masked-denoising AE-4 | q4_high    | 0.363 | 0.281  | 0.440   | 1647         |
| proxy: amplitude+topology         | q1_low     | 0.512 | 0.476  | 0.541   | 3942         |
| proxy: amplitude+topology         | q2_midlow  | 0.700 | 0.636  | 0.736   | 3341         |
| proxy: amplitude+topology         | q3_midhigh | 0.849 | 0.814  | 0.873   | 3068         |
| proxy: amplitude+topology         | q4_high    | 0.710 | 0.619  | 0.802   | 1647         |

## Topology-group probe holdouts
For this table the representation is fit on training runs, but the supervised linear probe is
trained excluding the named topology group and tested only on that group in held-out runs.

| method                                                          | heldout_topology | value | ci_low | ci_high | heldout_rows |
| --------------------------------------------------------------- | ---------------- | ----- | ------ | ------- | ------------ |
| traditional residual PCA-4 probe-holdout topology=single        | single           | 0.256 | 0.246  | 0.266   | 6085         |
| traditional residual PCA-4 probe-holdout topology=pair          | pair             | 0.308 | 0.283  | 0.352   | 2815         |
| traditional residual PCA-4 probe-holdout topology=triple        | triple           | 0.253 | 0.220  | 0.271   | 1895         |
| traditional residual PCA-4 probe-holdout topology=quad          | quad             | 0.316 | 0.251  | 0.344   | 1203         |
| ML residual masked-denoising AE-4 probe-holdout topology=single | single           | 0.240 | 0.233  | 0.249   | 6085         |
| ML residual masked-denoising AE-4 probe-holdout topology=pair   | pair             | 0.256 | 0.234  | 0.274   | 2815         |
| ML residual masked-denoising AE-4 probe-holdout topology=triple | triple           | 0.220 | 0.203  | 0.250   | 1895         |
| ML residual masked-denoising AE-4 probe-holdout topology=quad   | quad             | 0.300 | 0.255  | 0.317   | 1203         |

## Verdict
After per-run/per-stave balancing and explicit amplitude/topology controls, waveform shape carries
at most weak standalone stave information. The best controlled waveform score is below the
amplitude-only proxy and far below the topology-multiplicity proxy, while the mask-based sentinels
show how easily topology can become label leakage for this target. Future downstream claims should
quote proxy baselines and topology holdouts alongside any learned waveform representation score.
