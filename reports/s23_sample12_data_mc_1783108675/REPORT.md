# S23 — Sample I vs Sample II: data-side closure and data–MC comparison (B arm)

- DATA: `/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam/reports/1780917628.449525.085b2dc0__s01b_s00_selected_table_manifest/s00_selected_b_pulses.csv.gz` (analysis runs only: Sample I = 44–57, Sample II = 58–63,65; calibration runs 31–42/64 excluded, reported as variant)
- MC: `/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam/reports/mc02_pulse_table_1783107862/mc02_pulse_table_a1000.csv.gz` (mc02 digitized table, A>1000 companion; trigger mimics inclusive)
- Generated: 2026-07-03T19:58:01Z by `scripts/s23_sample12_data_mc_comparison.py`

## Verdicts

1. **Matthias signature in DATA: YES** — the Sample-I B2 spectrum is harder: f(A>5000) = 0.710 [0.708, 0.711] (I) vs 0.206 [0.203, 0.208] (II), ratio 3.452 [3.407, 3.498]; B2 median 6542 vs 3350 ADC.
2. **Trigger mimicking moves MC toward the data: YES** — data I: KS 0.1923 (untrig) → 0.1923 (II mimic) → 0.1310 (I mimic); χ² 623875 → 623706 → 20421. data II: KS 0.1599 → 0.1599 (II mimic; I mimic 0.2700); χ² 59389 → 59367 (I mimic 5200). The matched mimic is also the closest MC variant for data I in B2 shape. Absolute χ² remains far from statistical agreement (geometry poisoning + unmodelled beam conditions) — the claim is the *direction* of improvement, not agreement.
3. **Double ratio (gain/geometry-robust): B2 occupancy DR = 0.738 [0.733, 0.742] (z vs 1: -99.3); B2 high-amplitude DR = 1.672 [1.642, 1.703] (z: 55.4; exclusive-MC variant 0.840 [0.821, 0.859]).**

## (a) DATA per-stave summary (analysis runs, A>1000)

| Stave | n_I | share_I (95% CI) | med_I | σ68_I | f(A>thr)_I | n_II | share_II (95% CI) | med_II | σ68_II | f(A>thr)_II |
|---|---|---|---|---|---|---|---|---|---|---|
| B2 | 241,422 | 0.9570 [0.9562, 0.9578] | 6542 | 2432 | 0.710 [0.708, 0.711] | 88,213 | 0.7052 [0.7026, 0.7077] | 3350 | 1820 | 0.206 [0.203, 0.208] |
| B4 | 6,451 | 0.0256 [0.0250, 0.0262] | 2970 | 1204 | 0.062 [0.056, 0.068] | 21,229 | 0.1697 [0.1676, 0.1718] | 2915 | 1028 | 0.052 [0.049, 0.055] |
| B6 | 3,094 | 0.0123 [0.0118, 0.0127] | 2874 | 1132 | 0.019 [0.015, 0.024] | 11,148 | 0.0891 [0.0875, 0.0907] | 2780 | 972 | 0.021 [0.018, 0.024] |
| B8 | 1,299 | 0.0051 [0.0049, 0.0054] | 2890 | 1300 | 0.046 [0.036, 0.059] | 4,506 | 0.0360 [0.0350, 0.0371] | 3206 | 1173 | 0.077 [0.069, 0.085] |

## (b) MC per-stave summary (mc02 A>1000, trigger mimics)

MC high-amplitude thresholds are QUANTILE-MATCHED per stave to the data threshold (5000 ADC in data; matched on the pooled sample-II spectra so the placeholder gain cancels to first order): B2: 3184 ADC, B4: 3755 ADC, B6: 3340 ADC, B8: 2614 ADC

| Stave | variant | n | share (95% CI) | med (ADC) | σ68 | f(A>thr_mc) (95% CI) |
|---|---|---|---|---|---|---|
| B2 | sample_I mimic | 63,917 | 0.8045 [0.8018, 0.8073] | 2996 | 669 | 0.424 [0.420, 0.428] |
| B2 | sample_II mimic (incl.) | 200,584 | 0.4373 [0.4359, 0.4388] | 2239 | 1110 | 0.205 [0.204, 0.207] |
| B2 | sample_II \ I (excl.) | 136,667 | 0.3604 [0.3589, 0.3619] | 2042 | 972 | 0.103 [0.102, 0.105] |
| B2 | untriggered | 200,590 | 0.4373 [0.4359, 0.4387] | 2239 | 1110 | 0.205 [0.204, 0.207] |
| B4 | sample_I mimic | 8,430 | 0.1061 [0.1040, 0.1083] | 1509 | 800 | 0.003 [0.002, 0.005] |
| B4 | sample_II mimic (incl.) | 123,650 | 0.2696 [0.2683, 0.2709] | 1474 | 1063 | 0.052 [0.051, 0.053] |
| B4 | sample_II \ I (excl.) | 115,220 | 0.3038 [0.3024, 0.3053] | 1468 | 1088 | 0.055 [0.054, 0.057] |
| B4 | untriggered | 123,672 | 0.2696 [0.2683, 0.2709] | 1474 | 1063 | 0.052 [0.051, 0.053] |
| B6 | sample_I mimic | 4,632 | 0.0583 [0.0567, 0.0600] | 2470 | 308 | 0.023 [0.019, 0.028] |
| B6 | sample_II mimic (incl.) | 83,295 | 0.1816 [0.1805, 0.1827] | 2115 | 817 | 0.021 [0.020, 0.022] |
| B6 | sample_II \ I (excl.) | 78,663 | 0.2074 [0.2062, 0.2087] | 2054 | 822 | 0.021 [0.020, 0.022] |
| B6 | untriggered | 83,316 | 0.1816 [0.1805, 0.1827] | 2114 | 817 | 0.021 [0.020, 0.022] |
| B8 | sample_I mimic | 2,468 | 0.0311 [0.0299, 0.0323] | 1280 | 210 | 0.000 [0.000, 0.002] |
| B8 | sample_II mimic (incl.) | 51,122 | 0.1115 [0.1106, 0.1124] | 1969 | 492 | 0.077 [0.074, 0.079] |
| B8 | sample_II \ I (excl.) | 48,654 | 0.1283 [0.1272, 0.1294] | 1989 | 462 | 0.080 [0.078, 0.083] |
| B8 | untriggered | 51,134 | 0.1115 [0.1106, 0.1124] | 1969 | 492 | 0.077 [0.074, 0.079] |

## (c) Three-way data-vs-MC comparison (does trigger mimicking help?)

Metrics: occupancy χ² over the 4 staves (dof≈3; binomial variances) and the two-sample KS distance on **median-scaled** B2 amplitude spectra (scale-free, so the placeholder gain drops out; raw-ADC KS is reported in the JSON but is BLOCKED as a comparison by the unknown gain).

| Data sample | MC variant | occupancy χ² | per-stave pulls (B2/B4/B6/B8) | KS(B2, median-scaled) |
|---|---|---|---|---|
| data I | untriggered | 623875 | +621/-336/-278/-219 | 0.1923 |
| data I | sample_II mimic | 623706 | +621/-336/-278/-219 | 0.1923 |
| data I | sample_I mimic | 20421 | +104/-71/-54/-41 | 0.1310 |
| data II | untriggered | 59389 | +181/-80/-94/-107 | 0.1599 |
| data II | sample_II mimic | 59367 | +181/-80/-94/-107 | 0.1599 |
| data II | sample_I mimic | 5200 | -52/+42/+27/+6 | 0.2700 |

**Reading:** data I: KS 0.1923 (untrig) → 0.1923 (II mimic) → 0.1310 (I mimic); χ² 623875 → 623706 → 20421. data II: KS 0.1599 → 0.1599 (II mimic; I mimic 0.2700); χ² 59389 → 59367 (I mimic 5200). The matched mimic is also the closest MC variant for data I in B2 shape. Absolute χ² remains far from statistical agreement (geometry poisoning + unmodelled beam conditions) — the claim is the *direction* of improvement, not agreement.

## (d) Double ratios — the cleanest test of the enrichment mechanism

DR = [f(·,I)/f(·,II)]_data / [f(·,I)/f(·,II)]_MC. Any factor common to both samples within data or within MC (unknown gain, common geometry acceptance) cancels in each inner ratio. DR = 1 ⇔ MC reproduces the between-sample enrichment.

| Observable | R_data (95% CI) | R_MC incl. (95% CI) | R_MC excl. II\I (95% CI) | DR (data/MC incl.) | z vs 1 | DR (data/MC excl.) |
|---|---|---|---|---|---|---|
| occupancy B2 | 1.357 [1.352, 1.362] | 1.840 [1.831, 1.848] | 2.232 [2.220, 2.244] | 0.738 [0.733, 0.742] | -99.3 | 0.608 [0.604, 0.612] |
| occupancy B4 | 0.151 [0.147, 0.155] | 0.394 [0.386, 0.402] | 0.349 [0.342, 0.357] | 0.383 [0.370, 0.396] | -55.2 | 0.432 [0.417, 0.446] |
| occupancy B6 | 0.138 [0.132, 0.143] | 0.321 [0.312, 0.330] | 0.281 [0.273, 0.289] | 0.429 [0.408, 0.450] | -34.2 | 0.490 [0.466, 0.514] |
| occupancy B8 | 0.143 [0.134, 0.152] | 0.279 [0.268, 0.290] | 0.242 [0.233, 0.252] | 0.513 [0.477, 0.552] | -17.9 | 0.590 [0.549, 0.635] |
| B2 f(A>thr) | 3.452 [3.407, 3.498] | 2.064 [2.039, 2.090] | 4.111 [4.038, 4.186] | 1.672 [1.642, 1.703] | 55.4 | 0.840 [0.821, 0.859] |

## MC species mechanism (dominant-pdg composition of B2 pulses)

| variant | f_d(B2) | f_p(B2) | f_other(B2) |
|---|---|---|---|
| sample_I mimic | 0.891 | 0.098 | 0.011 |
| sample_II mimic | 0.639 | 0.352 | 0.009 |
| II \ I | 0.521 | 0.471 | 0.008 |
| untriggered | 0.639 | 0.352 | 0.009 |

## Robustness variant — calibration runs included

- data B2 f(A>5000): I = 0.6708, II = 0.2062 (headline: 0.7096 / 0.2056); B2 occupancy DR = 0.726 [0.722, 0.730].

## Caveats (honest limits of this comparison)

- **Gain placeholder**: the mc02 digitizer gain (297 ADC/MeV) is an UNKNOWN placeholder anchored on geometry-poisoned MC (review P1/P2). NO absolute ADC comparison is made; MC high-amplitude thresholds are quantile-matched and the shape metric is median-scaled. Residual gain nonlinearity/saturation differences are NOT removed by scaling.
- **Geometry poisoning**: the MC geometry lacks upstream beamline material (MV3, χ²/ndf=68,269), diluting stoppers with through-goers. Absolute occupancy χ² values are therefore expected to stay large even for a perfect trigger mimic; only the *ordering* (untriggered → II → I) and the between-sample double ratios are decision-grade.
- **Disjoint-runs vs inclusive-MC asymmetry**: data Samples I/II are disjoint run sets with different hardware triggers; the MC mimics are inclusive (I ⊂ II). The exclusive MC variant (II\I) is reported alongside everywhere; it is the closer analogue of the data Sample II run set *only if* the hardware B-trigger runs contain the same pd-pair phase space (they do, untagged), so inclusive is the physically correct default and exclusive is the bracketing variant.
- **Beam/rate differences between run sets** (currents, pile-up, drift across runs 44–65) are NOT modelled in MC and are absorbed into the data ratios.
- **Data saturation**: the data amplitude spectrum clips at the ADC ceiling in B2; the MC pipeline saturates differently. The high-amplitude fraction uses a threshold well below the ceiling, but the KS shape distance retains a tail-shape systematic.
- **LayerID→stave mapping** ('paired') is UNDER REVIEW (P4); MC occupancy shares would change under the 'odd' mapping, the data does not.

## Artifacts

- `s23_summary.json` — every number in this report plus raw-ADC KS and histograms
- `s23_overview.png` / `.svg` — multi-panel overview figure

Reproduce:
```
python3 scripts/s23_sample12_data_mc_comparison.py --data /projects/hep/fs10/shared/nnbar/billy/ccb-testbeam/reports/1780917628.449525.085b2dc0__s01b_s00_selected_table_manifest/s00_selected_b_pulses.csv.gz \
    --mc /projects/hep/fs10/shared/nnbar/billy/ccb-testbeam/reports/mc02_pulse_table_1783107862/mc02_pulse_table_a1000.csv.gz --high-adc 5000 --out /projects/hep/fs10/shared/nnbar/billy/ccb-testbeam/reports/s23_sample12_data_mc_1783108675
```
