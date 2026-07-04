# mc02 MC pulse table — physical validation

Generated 2026-07-04T16:01:21+00:00 from `mc02_pulse_table_birks_1783180742`.
Card: `/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam/configs/mc_validation/digitizer_card.yaml` (sha256 `65e00bf47058…`, gain status **UNKNOWN_PLACEHOLDER_PENDING_PHASE2**). Mapping: `paired`.

- events scanned: **1,000,000** (tree entries 1,000,000)
- table rows (no selection): **518,247**; A>1000 companion: **415,416**
- Sample I events: 64,762; Sample II events: 237,098

## 1. Occupancy ordering (expect B2 >> B4 > B6 > B8)

| stave | MC rows (all deposits) | MC fraction | data selected rows (A>1000) | data fraction |
|---|---|---|---|---|
| B2 | 237,234 | 0.458 | 579,424 | 0.904 |
| B4 | 130,755 | 0.252 | 36,116 | 0.056 |
| B6 | 88,200 | 0.170 | 17,945 | 0.028 |
| B8 | 62,058 | 0.120 | 7,252 | 0.011 |

Ordering check (B2>2×B4 and B4>B6>B8): **FAIL**.
MC rows here are *unselected* (any deposit) while the data column is the A>1000 selected table — fractions are context, not a quantitative comparison. The MC occupancy weights are known to be geometry-poisoned (review P1/MV3: MC stopping fractions B2 47% vs data 90%+).

## 2. Per-stave amplitude spectra (shape only — gain is a placeholder)

| stave | n | median [ADC] | p10 | p90 | data net median [ADC] |
|---|---|---|---|---|---|
| B2 | 237,234 | 1715 | 866 | 2733 | 5752 |
| B4 | 130,755 | 1298 | 1010 | 2770 | 4132 |
| B6 | 88,200 | 1726 | 1219 | 2542 | 4178 |
| B8 | 62,058 | 1582 | 562 | 2071 | 3851 |

Absolute-scale agreement is NOT claimed: gain 297 ADC/MeV is the C2-resolution placeholder on a geometry-poisoned MC anchor. Only the ordering/shape is informative at Phase 1.

## 3. Pulse tail decay vs card (data-tuned tau_decay)

| stave | fitted tau [ns] (mean-waveform tail) | card tau [ns] (data) | ratio | n waveforms |
|---|---|---|---|---|
| B2 | 56.7 | 56.7 | 1.000 | 237,234 |
| B4 | 51.7 | 51.7 | 1.000 | 130,755 |
| B6 | 49.4 | 49.4 | 1.000 | 88,200 |
| B8 | 50.1 | 50.1 | 1.000 | 62,058 |

Fit: log-linear on the mean baseline-subtracted waveform tail between 90% and 10% of peak (10 ns sampling). Multi-hit pile-in within an event and the 2.5 ns rise bias the fitted tau slightly high relative to the pure kernel.

## 4. MV7 pedestal validation

NOT RUN (no mv7_pedestal_validation.json).

## Caveats (honest list)

1. **Gain placeholder**: gain 297 ADC/MeV = data B2 net median 5752 / (MC B2 edep median 26.44 MeV × peak_frac 0.733). The MC-side anchor is geometry-poisoned and peak_frac is phase-locked (review P1/P2). No ADC/MeV claim is made; re-anchor in Phase 2.
2. **Geometry-poisoned spectrum weights**: missing upstream material dilutes B2 with through-goers (MV3 chi2/ndf=68,269); per-stave occupancies and amplitude spectra inherit this defect. Shape ordering only.
3. **Mapping under review**: the paired {0,1}->B2 … {6,7}->B8 LayerID mapping is an unvalidated guess; the odd-layer alternative (odd bars unread) is a live hypothesis (review P4). Rebuild with `--mapping odd` to test.
4. **MV7 is MC-level only**: white-Gaussian noise + uniform pedestal jitter; no correlated noise/drift/signal contamination. Real data still has no true pedestal sample.
5. **Birks quenching ON** (Phase 4): per-hit light = edep/(1+kB*dE/dx), kB = 0.0126 g/(MeV cm^2)/1.06 g/cm^3; heavy-ion (alpha/C12) light is quenched. dE/dx from truth step lengths with a PSTAR/ASTAR-anchored species lookup fallback (digitizer/birks.py).
