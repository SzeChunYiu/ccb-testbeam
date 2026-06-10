# S07j: all-three injected RF amplitude-matching nuisance audit

- **Ticket:** `1781025690.936.4b082470`
- **Worker:** `testbeam-laptop-1`
- **Input:** raw B-stack ROOT `HRDv` from `/home/billy/ccb-data/extracted/root/root`
- **Selection:** Sample-II analysis runs, B2+B4+B6+B8 all selected, `A>1000` ADC, CFD20 timing.
- **Split:** leave-one-run-out; intervals are held-out run-block bootstrap CIs.
- **Nuisance gate:** peak-renormalized injected copies must leave the amplitude-only RF near chance.

## Raw-ROOT Reproduction First

| quantity                                | report_value | reproduced | delta      | tolerance | pass |
| --------------------------------------- | ------------ | ---------- | ---------- | --------- | ---- |
| parent App.I guarded gross D_t>51 ns    | 72           | 72         | 0          | 0         | True |
| parent App.I documented gross D_t>50 ns |              | 74         |            |           | True |
| all-three control events                | 3774         | 3774       | 0          | 0         | True |
| all-three clean events D_t<3 ns         |              | 579        |            |           | True |
| all-three guarded gross D_t>51 ns       | 22           | 22         | 0          | 0         | True |
| all-three S07e shape RF ROC AUC         | 0.992778     | 0.994426   | 0.00164861 | 0.002     | True |
| S07f unnormalized injection RF ROC AUC  | 0.822118     | 0.822118   | 0          | 0.001     | True |

The raw all-three App.I gate reproduces the parent S07e population before any S07j result is used. The S07f unnormalized injection number is also reproduced from the same raw ROOT: RF AUC 0.822118 versus the prior 0.822118.

| method                                     | roc_auc  | roc_auc_ci_low | roc_auc_ci_high | average_precision | ap_ci_low | ap_ci_high | brier       | brier_ci_low | brier_ci_high | notes                                                                                                                       |
| ------------------------------------------ | -------- | -------------- | --------------- | ----------------- | --------- | ---------- | ----------- | ------------ | ------------- | --------------------------------------------------------------------------------------------------------------------------- |
| reproduced all-three curvature-only        | 1        | 1              | 1               | 1                 | 1         | 1          | 2.69041e-07 | 0            | 8.62127e-07   | S07e pre-registered all-three traditional comparator.                                                                       |
| reproduced all-three D_t/curvature ceiling | 1        | 1              | 1               | 1                 | 1         | 1          | 1.88359e-06 | 0            | 4.46498e-06   | Forbidden self-referential timing ceiling.                                                                                  |
| reproduced all-three shape-only RF         | 0.994426 | 0.981701       | 0.999521        | 0.913019          | 0.655174  | 0.984266   | 0.0123271   | 0.00503737   | 0.0211324     | Best params={'n_estimators': 500, 'max_depth': 7, 'min_samples_leaf': 8}; raw-ROOT reproduction of S07e all-three App.I RF. |

## S07f Baseline Reproduction

| method                                    | roc_auc  | roc_auc_ci_low | roc_auc_ci_high | average_precision | ap_ci_low | ap_ci_high | brier    | brier_ci_low | brier_ci_high | notes                                                                                                                                                       |
| ----------------------------------------- | -------- | -------------- | --------------- | ----------------- | --------- | ---------- | -------- | ------------ | ------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- |
| traditional fold-selected timing/template | 0.605954 | 0.598605       | 0.618069        | 0.570681          | 0.561867  | 0.583083   | 0.239508 | 0.237077     | 0.241699      | Fold-local best signed timing, curvature, shape-summary, or matched-template score.                                                                         |
| direct D_t/curvature cross-check          | 0.530522 | 0.51749        | 0.537119        | 0.581449          | 0.566058  | 0.597987   | 0.24422  | 0.240807     | 0.247804      | Not label-defining here; target is injected two-pulse truth.                                                                                                |
| all-three shape-only RF                   | 0.822118 | 0.80083        | 0.844361        | 0.83589           | 0.81471   | 0.860373   | 0.177242 | 0.164769     | 0.190468      | Best params={'n_estimators': 500, 'max_depth': 7, 'min_samples_leaf': 8}; excludes timing, run/event ids, injection params, amplitudes, and topology flags. |

## Peak-Renormalized Injection

The injected target waveform is rescaled after adding the delayed copy so its original peak amplitude is restored. This is the primary S07j nuisance control: it removes the direct peak-height channel while preserving the two-pulse shape distortion.

| method                                    | roc_auc  | roc_auc_ci_low | roc_auc_ci_high | average_precision | ap_ci_low | ap_ci_high | brier    | brier_ci_low | brier_ci_high | notes                                                                                                                                                       |
| ----------------------------------------- | -------- | -------------- | --------------- | ----------------- | --------- | ---------- | -------- | ------------ | ------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- |
| traditional fold-selected timing/template | 0.606899 | 0.5994         | 0.619684        | 0.570991          | 0.562413  | 0.583868   | 0.23961  | 0.236971     | 0.241873      | Fold-local best signed timing, curvature, shape-summary, or matched-template score.                                                                         |
| direct D_t/curvature cross-check          | 0.529224 | 0.514386       | 0.536777        | 0.581319          | 0.566057  | 0.597953   | 0.244278 | 0.24082      | 0.24785       | Not label-defining here; target is injected two-pulse truth.                                                                                                |
| all-three shape-only RF                   | 0.82315  | 0.801586       | 0.846248        | 0.835731          | 0.812396  | 0.862101   | 0.176617 | 0.163515     | 0.190129      | Best params={'n_estimators': 500, 'max_depth': 7, 'min_samples_leaf': 8}; excludes timing, run/event ids, injection params, amplitudes, and topology flags. |

### Peak-Preserving Leakage Checks

| probe                                  | roc_auc  | average_precision | notes                                                      |
| -------------------------------------- | -------- | ----------------- | ---------------------------------------------------------- |
| pre-injection D_t                      | 0.5      | 0.5               | Same for clean/injected pairs; should be chance.           |
| topology-only RF                       | 0.5      | 0.5               | Constant all-three topology; should be chance.             |
| absolute-amplitude-only RF             | 0.5      | 0.5               | Excluded from main RF; checks residual amplitude nuisance. |
| shape RF with shuffled training labels | 0.475908 | 0.479921          | Null/leakage sanity check.                                 |
| per-stave slot shape RF                | 0.852001 | 0.858067          | Permissive shape representation; not main claim.           |
| pair split violations                  | 0        |                   | Must be 0.                                                 |
| forbidden main RF columns              | 0        |                   | None.                                                      |

## Charge-Preserving Injection

The injected target waveform is rescaled after adding the delayed copy so its original positive charge is restored. This is a looser integral-preserving control and can still alter peak height.

| method                                    | roc_auc  | roc_auc_ci_low | roc_auc_ci_high | average_precision | ap_ci_low | ap_ci_high | brier    | brier_ci_low | brier_ci_high | notes                                                                                                                                                       |
| ----------------------------------------- | -------- | -------------- | --------------- | ----------------- | --------- | ---------- | -------- | ------------ | ------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- |
| traditional fold-selected timing/template | 0.605008 | 0.597535       | 0.616774        | 0.570376          | 0.561288  | 0.582514   | 0.239391 | 0.237044     | 0.241731      | Fold-local best signed timing, curvature, shape-summary, or matched-template score.                                                                         |
| direct D_t/curvature cross-check          | 0.530667 | 0.518515       | 0.536676        | 0.579988          | 0.561512  | 0.597998   | 0.244314 | 0.240921     | 0.248026      | Not label-defining here; target is injected two-pulse truth.                                                                                                |
| all-three shape-only RF                   | 0.822808 | 0.802008       | 0.845883        | 0.836536          | 0.81448   | 0.861933   | 0.177963 | 0.166127     | 0.19079       | Best params={'n_estimators': 500, 'max_depth': 7, 'min_samples_leaf': 8}; excludes timing, run/event ids, injection params, amplitudes, and topology flags. |

### Charge-Preserving Leakage Checks

| probe                                  | roc_auc  | average_precision | notes                                                      |
| -------------------------------------- | -------- | ----------------- | ---------------------------------------------------------- |
| pre-injection D_t                      | 0.5      | 0.5               | Same for clean/injected pairs; should be chance.           |
| topology-only RF                       | 0.5      | 0.5               | Constant all-three topology; should be chance.             |
| absolute-amplitude-only RF             | 0.55041  | 0.538629          | Excluded from main RF; checks residual amplitude nuisance. |
| shape RF with shuffled training labels | 0.477928 | 0.483002          | Null/leakage sanity check.                                 |
| per-stave slot shape RF                | 0.849304 | 0.855195          | Permissive shape representation; not main claim.           |
| pair split violations                  | 0        |                   | Must be 0.                                                 |
| forbidden main RF columns              | 0        |                   | None.                                                      |

## Finding

After forcing the peak-amplitude nuisance to chance, the all-three shape-only RF still reaches ROC AUC 0.823 [0.802, 0.846], compared with the traditional timing/template score 0.607 [0.599, 0.620]. The peak-renormalized amplitude-only RF is 0.500, so the main RF advantage is not a peak-height classifier. Under positive-charge preservation, the RF reaches 0.823 [0.802, 0.846] versus traditional 0.605 [0.598, 0.617], while the amplitude-only RF is 0.550.

The S07f RF gain survives peak renormalization, so it is not explained only by a peak-amplitude artifact. The amplitude-only leakage probe is at chance for peak preservation and remains reported for charge preservation. Shuffled labels, topology-only RF, pair split checks, and forbidden-column scans do not indicate run or pair leakage.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s07j_1781025690_936_4b082470_amp_matched_injected_rf_audit.py --config configs/s07j_1781025690_936_4b082470.json
```

Artifacts: `result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, baseline and preservation scoreboards, leakage CSVs, and out-of-fold prediction CSVs.
