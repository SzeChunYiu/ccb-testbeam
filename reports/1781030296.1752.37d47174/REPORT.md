# S10f: blinded waveform gallery scan

- **Ticket:** `1781030296.1752.37d47174`
- **Worker:** `testbeam-laptop-4`
- **Inputs:** raw B-stack ROOT runs 44-57 plus S10e run-held-out score table; no Monte Carlo.
- **Split:** candidate scores are source-run held out from S10e; morphology CIs bootstrap held-out source runs.

## Reproduction first

The raw ROOT S10 topology gate was rerun before any gallery classification. All documented topology rows pass: True. The S10d real-candidate thresholds used here are traditional score > 0.015 with delay >= 60 ns, and ML score > 0.5 with delay >= 20 ns.

| quantity                                 |   report_value |   reproduced |        delta |   tolerance | pass   |
|:-----------------------------------------|---------------:|-------------:|-------------:|------------:|:-------|
| low_2nA multi_stave_per_selected_event   |         0.0156 |    0.0155875 | -1.247e-05   |      0.0015 | True   |
| low_2nA three_stave_per_selected_event   |         0.0041 |    0.004111  |  1.09969e-05 |      0.0015 | True   |
| low_2nA downstream_per_selected_event    |         0.0231 |    0.0231244 |  2.43577e-05 |      0.0015 | True   |
| high_20nA multi_stave_per_selected_event |         0.0268 |    0.0268063 |  6.29596e-06 |      0.0015 | True   |
| high_20nA three_stave_per_selected_event |         0.0085 |    0.0085379 |  3.78959e-05 |      0.0015 | True   |
| high_20nA downstream_per_selected_event  |         0.0334 |    0.0334141 |  1.41048e-05 |      0.0015 | True   |

## Candidate gallery

The high-current set contains 70 traditional candidates and 261 ML candidates above the reproduced S10d real-candidate thresholds. Rows were assigned blinded IDs before morphology labeling; the rubric used only normalized waveform shape features, not current group, run, event number, or model scores. A compact audit image is in `waveform_gallery_blinded.png`.

| group     | morphology         |   n |
|:----------|:-------------------|----:|
| high_20nA | broad_late_shape   | 226 |
| high_20nA | pathology_or_noisy |  75 |
| high_20nA | two_pulse_like     |  27 |
| low_2nA   | broad_late_shape   | 829 |
| low_2nA   | pathology_or_noisy | 182 |
| low_2nA   | two_pulse_like     |  81 |

## Traditional method

Traditional candidates are the bounded template-fit events with nontrivial SSE improvement and recovered delay above 60 ns. Their two-pulse-like morphology fraction is **0.043** versus **0.088** in matched low-current controls, delta **-0.045** [-0.096, 0.022].

## ML method

ML candidates are the random-forest residual-score events with overlap score and recovered delay above the S10d ML thresholds. Their two-pulse-like morphology fraction is **0.092** versus **0.074** in matched low-current controls, delta **0.018** [-0.032, 0.060].

## Leakage review

Leakage flags: 0. Candidate scoring is inherited from S10e's run-held-out fits/ML; this script verifies score rows against freshly loaded raw ROOT events. The morphology classifier uses only blinded waveform features. Current AUC from morphology two-pulse-like labels is 0.504; current AUC from the blinded morphology feature score is 0.488.

## Conclusion

Above-threshold high-current S10e candidates are mostly not clean visually separated double pulses: traditional two-pulse-like fraction 0.043 versus matched low-control 0.088, and ML two-pulse-like fraction 0.092 versus 0.074. The excess is therefore better described as broad/late detector-shape support with a small genuine-two-pulse-like subset, not a pure beam pile-up gallery.

## Artifacts

`result.json`, `manifest.json`, `input_sha256.csv`, `morphology_scores.csv`, `morphology_summary.csv`, `morphology_counts.csv`, `gallery_manifest.csv`, and `waveform_gallery_blinded.png` are in this folder.
