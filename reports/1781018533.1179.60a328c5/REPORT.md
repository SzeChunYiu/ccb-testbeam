# S11e: residual-pool conditioning for two-pulse closure

- **Study ID:** S11e
- **Ticket:** `1781018533.1179.60a328c5`
- **Author:** `testbeam-laptop-2`
- **Date:** 2026-06-10
- **Input checksum(s):** see `input_sha256.csv` and `manifest.json`
- **Config:** `configs/s11e_1781018533_1179_60a328c5_residual_pool_conditioning.json`

## Question

Does conditioning injected-noise residual pools by run family, stave, amplitude bin, and late-tail class change the S11c ML-versus-traditional two-pulse closure gap when all templates and residual pools are learned only from train runs?

## Reproduction gate

The raw ROOT S00 selected-pulse gate was rerun first and passed exactly: `640737` selected B-stave pulses versus `640737` reported. The S10 injected-pileup AP handle was then rerun from raw ROOT with reproduced AP values `[0.982, 0.9719]`.

The S11a anchor was regenerated before S11e: traditional time RMS **13.30 ns** and ML **10.67 ns**, matching the configured tolerances. The S11c source closure was also rerun with the original run-local residual generator: traditional **18.65 ns** and ML **10.59 ns**.

## Methods

Train runs are `[58, 59, 60, 61, 62]` and held-out runs are `[63, 65]`. Templates are the S11c amplitude-binned asymmetric template library built only from train runs. S11e builds residuals as `clean waveform - train template model` from train runs only, bins them by `(run family, stave, amplitude tertile, late-tail class)`, and samples held-out injection noise through exact bins with amp-bin, tail-class, then stave-family fallback. Exact conditioned pools have minimum size `74` and median size `121.5`; full counts are in `residual_pool_summary.csv`.

The traditional method is the S11c bounded two-pulse template fit. The ML method is the same compact MLP classifier/regressor trained on the injected train runs. CIs are held-out run bootstraps.

## Head-to-head result

| Benchmark | Traditional RMS ns | ML RMS ns | gap trad-ML ns |
|---|---:|---:|---:|
| S11c source residuals | 18.65 | 10.59 | 8.06 |
| train-only residual control | 17.81 | 9.84 | 7.97 |
| conditioned train-only residuals | 17.36 [17.16, 17.55] | 9.07 [8.88, 9.26] | 8.28 [7.89, 8.68] |

Conditioning changes the gap versus the S11c source closure by **+0.22 ns**. The sign remains the same: ML has lower held-out constituent time RMS than the traditional fit in the conditioned closure.

## Held-out runs

| Run | Method | AP | time RMS ns | charge res68 | failure rate |
|---:|---|---:|---:|---:|---:|
| 63 | amp_binned_asymmetric_template_fit | 0.793 | 17.16 | 0.098 | 0.010 |
| 63 | compact_mlp_classifier_regressor | 0.847 | 9.26 | 0.065 | 0.243 |
| 65 | amp_binned_asymmetric_template_fit | 0.707 | 17.55 | 0.085 | 0.013 |
| 65 | compact_mlp_classifier_regressor | 0.820 | 8.88 | 0.069 | 0.260 |

## Leakage probes

Held-out source runs never enter template training or residual-pool construction. Event ids do not overlap. The shuffled-label sentinel AP is `0.521` and too-good sentinels did not pass silently; leakage flags: **0**. Full checks are in `leakage_checks.csv`.

## Limitations

This is still a data-driven synthetic injection closure. Conditioning makes the injected residuals more local in observed pulse shape, but it does not prove the same ranking on real unresolved beam pile-up.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s11e_1781018533_1179_60a328c5_residual_pool_conditioning.py --config configs/s11e_1781018533_1179_60a328c5_residual_pool_conditioning.json
```

Runtime in this run was `238.72` s.
