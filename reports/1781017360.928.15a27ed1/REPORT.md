# S10e: S10d high-stat validation

- **Ticket:** `1781017360.928.15a27ed1`
- **Worker:** `testbeam-laptop-1`
- **Inputs:** raw B-stack ROOT runs 44-57; no Monte Carlo.
- **Split:** leave-one-source-run-out templates/ML; CIs bootstrap held-out source runs within current group.

## Reproduction first

The S10d capped 140/event analysis was rerun from raw ROOT before the high-stat pass. Traditional high-minus-low secondary fraction reproduced as **0.03159** [0.01889, 0.04396], versus the S10d report value 0.03159.

| quantity                                 |   report_value |   reproduced |        delta |   tolerance | pass   |
|:-----------------------------------------|---------------:|-------------:|-------------:|------------:|:-------|
| low_2nA multi_stave_per_selected_event   |         0.0156 |    0.0155875 | -1.247e-05   |      0.0015 | True   |
| low_2nA three_stave_per_selected_event   |         0.0041 |    0.004111  |  1.09969e-05 |      0.0015 | True   |
| low_2nA downstream_per_selected_event    |         0.0231 |    0.0231244 |  2.43577e-05 |      0.0015 | True   |
| high_20nA multi_stave_per_selected_event |         0.0268 |    0.0268063 |  6.29596e-06 |      0.0015 | True   |
| high_20nA three_stave_per_selected_event |         0.0085 |    0.0085379 |  3.78959e-05 |      0.0015 | True   |
| high_20nA downstream_per_selected_event  |         0.0334 |    0.0334141 |  1.41048e-05 |      0.0015 | True   |

## Dominant high-stat strata

The high-stat rerun uses the top 3 matched strata by S10d match weight, covering 94.89% of the matched weight. The per-run/stratum waveform cap is 700, 5x the S10d cap of 140.

| amp_bin       | baseline_bin    | p02_topology   |   low_n |   high_n |   original_match_weight |   match_weight |
|:--------------|:----------------|:---------------|--------:|---------:|------------------------:|---------------:|
| amp_ge_4500   | s16_no_lowering | p02_broad_late |    2982 |   172450 |                0.519603 |       0.547558 |
| amp_2500_4500 | s16_no_lowering | p02_broad_late |    1685 |    32818 |                0.293605 |       0.309401 |
| amp_1000_2500 | s16_no_lowering | p02_broad_late |     779 |    12463 |                0.135738 |       0.143041 |

## Traditional method

The traditional method is the same constrained two-pulse template fit used in S10d: templates are median raw-pulse templates built without the held-out run, then a bounded one-pulse/two-pulse least-squares scan reports A2/(A1+A2).

Dominant-strata capped result: **0.03538** [0.02139, 0.05002]. High-stat result: **0.03301** [0.01919, 0.04876]. High-stat minus capped sensitivity on the identical dominant strata is **-0.00237**.

## ML method

The ML diagnostic is the S10d run-held-out random-forest classifier/regressor trained on synthetic two-pulse overlays made only from training-run raw pulses. Features exclude run, event number, current label, downstream label, and stratum labels.

High-stat ML secondary-fraction high-minus-low is **0.00668** [0.00438, 0.00938]. ML overlap-score high-minus-low is **0.02384** [0.01179, 0.03511].

## Leakage review

High-stat synthetic held-out AUC is 0.985; shuffled-label AUC is 0.520; actual-current AUC from ML secondary fraction is 0.503. Leakage flags: 0.

## Conclusion

The raw-ROOT capped reproduction matches S10d within +0.000000 on the traditional headline. On the top 3 strata covering 94.89% of the matched weight, increasing the per-run/stratum cap from 140 to 700 changes the traditional secondary-fraction high-minus-low by -0.00237. The high-stat traditional estimate is 0.03301 [0.01919, 0.04876], while the ML secondary-fraction diagnostic is 0.00668 [0.00438, 0.00938]. No leakage check flags, but the ML arm remains a synthetic-overlay diagnostic rather than a truth-labelled decomposition.

## Artifacts

`result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `stratum_table.csv`, dominant/capped/highstat method summaries, event scores, fold diagnostics, and leakage checks are in this folder.
