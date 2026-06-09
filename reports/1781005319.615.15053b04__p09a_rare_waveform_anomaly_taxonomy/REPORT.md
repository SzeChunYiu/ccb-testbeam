# P09a: rare waveform anomaly taxonomy and precision audit

**Ticket:** `1781005319.615.15053b04`

## Reproduction first
Raw B-stack ROOT files were read from `data/root/root` with the S00 gate: B2/B4/B6/B8 even channels, baseline median samples 0-3, and amplitude >1000 ADC. The selected-pulse count was reproduced before model fitting.

| quantity | expected | reproduced | pass |
|---|---:|---:|---|
| S00 selected B-stave pulses | 640737 | 640737 | True |

## Methods
Held-out runs were `42, 57, 64, 65`. The traditional ranker used train-run amplitude/stave median templates plus robust outlier scores over q_template, peak sample, late fraction, baseline residual, saturation count, duplicate-channel timing span, secondary peak, and undershoot. The ML ranker combined PCA reconstruction error, a small autoencoder reconstruction error, and IsolationForest density in PCA+AE latent space. No run id, event id, or stave label was used as a model feature; run/stave only balanced the held-out gallery selection.

## Held-out top-k audit
Top anomalies are selected as the top 8 per held-out run/stave stratum. CIs are 95% bootstrap intervals over held-out runs.

| method                      |   top_k |   curated_precision | curated_precision_ci   |   novel_precision | novel_precision_ci   |   physics_tail_only_rate | physics_tail_only_rate_ci   |   curated_enrichment | curated_enrichment_ci   |   duplicate_event_rate | duplicate_event_rate_ci   |
|:----------------------------|--------:|--------------------:|:-----------------------|------------------:|:---------------------|-------------------------:|:----------------------------|---------------------:|:------------------------|-----------------------:|:--------------------------|
| traditional_robust_template |     128 |            0.898438 | [0.852, 0.945]         |          0.554688 | [0.508, 0.625]       |                        0 | [0, 0]                      |             10.5952  | [9.2, 11.9]             |              0.015625  | [0, 0.0469]               |
| ml_pca_ae_isolation         |     128 |            0.882812 | [0.797, 0.969]         |          0.765625 | [0.703, 0.828]       |                        0 | [0, 0]                      |             10.4109  | [9.91, 11]              |              0.046875  | [0, 0.0938]               |
| balanced_random             |     128 |            0.17957  | [0.125, 0.242]         |          0.16375  | [0.109, 0.227]       |                        0 | [0, 0]                      |              2.11765 | [1.47, 2.86]            |              0.0165625 | [0, 0.0473]               |

## Taxonomy
| taxon                         |   heldout_count |   gallery_count |   heldout_rate |   gallery_rate |
|:------------------------------|----------------:|----------------:|---------------:|---------------:|
| unassigned_common             |           54558 |              28 |    0.915203    |     0.109375   |
| novel_early_pretrigger        |            2397 |             123 |    0.0402094   |     0.480469   |
| baseline_excursion            |             732 |              58 |    0.0122792   |     0.226562   |
| novel_delayed_peak            |            1581 |              41 |    0.0265211   |     0.160156   |
| novel_broad_template_mismatch |             162 |               1 |    0.00271753  |     0.00390625 |
| pileup_or_long_tail           |              93 |               1 |    0.00156006  |     0.00390625 |
| dropout                       |              88 |               4 |    0.00147619  |     0.015625   |
| saturation                    |               2 |               0 |    3.35497e-05 |     0          |

## Leakage checks
| check                                        |    value | pass   | note                                                         |
|:---------------------------------------------|---------:|:-------|:-------------------------------------------------------------|
| train_heldout_run_overlap                    | 0        | True   | must be zero                                                 |
| model_features_include_run_event_or_stave_id | 0        | True   | ids used only for split/balanced gallery, not score features |
| top_gallery_waveform_hash_seen_in_train      | 0        | True   | rounded normalized waveform hash overlap at 1e-3 precision   |
| ml_curated_precision_minus_random_mean       | 0.703242 | True   | positive indicates ranker beats balanced random triage       |

## Verdict
The ML ranker improves curated precision over balanced random selection and concentrates the gallery in novel early/delayed/template-mismatch rule classes more than the traditional ranker. This is useful for review triage, but it is not a standalone discovery claim because the curation is deterministic and still needs human waveform adjudication. The small gallery manifest is written to `gallery_manifest.csv` with waveform samples for manual audit.

## Provenance
Runtime was 127.0 s on `billy`. The AE ran on `cpu` with final training loss `0.0173705`. `manifest.json` records input and output hashes.
