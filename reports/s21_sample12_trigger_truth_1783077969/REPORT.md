# S21 — Sample I vs Sample II trigger-truth comparison (B arm)

- MC file: `/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam/geant4/data/output_krakow_1M.root` (tree `hibeam`)
- Events read: 1,000,000; coincidence window 15.0 ns
- Trigger counts: enter_B=237,098, enter_A=69,770, Sample I=64,762, Sample II=237,098 (inclusive; Sample I ⊂ Sample II)
- Generated: 2026-07-03T11:26:39Z by `scripts/s21_sample12_trigger_truth_comparison.py`

## Verdict

**Sample I deuteron-enriched in B2: YES (ratio 1.519, 95% CI [1.510, 1.528]; exclusive I vs II\I ratio 1.912, 95% CI [1.898, 1.925])**

## Key table — deuteron fraction per stave (charged B-arm tracks occupying the stave)

| Stave | f_d Sample I (95% CI) | n_I | f_d Sample II (95% CI) | n_II | ratio I/II (95% CI) | ratio I/(II\I) (95% CI) |
|---|---|---|---|---|---|---|
| B2 | 0.6748 [0.6717, 0.6778] | 91,012 | 0.4442 [0.4425, 0.4460] | 320,973 | 1.519 [1.510, 1.528] | 1.912 [1.898, 1.925] |
| B4 | 0.3037 [0.2956, 0.3119] | 12,232 | 0.2164 [0.2144, 0.2183] | 167,464 | 1.404 [1.365, 1.444] | 1.450 [1.409, 1.492] |
| B6 | 0.0108 [0.0086, 0.0135] | 6,927 | 0.0108 [0.0102, 0.0114] | 113,248 | 1.003 [0.795, 1.264] | 1.003 [0.795, 1.265] |
| B8 | 0.0022 [0.0012, 0.0040] | 4,595 | 0.0051 [0.0046, 0.0056] | 73,729 | 0.427 [0.228, 0.799] | 0.411 [0.219, 0.770] |

## Sample I (inclusive) — n_events = 64,762, charged B tracks = 97,500

### Per-stave occupancy by species

| Stave | n_p | n_d | n_other | f_p | f_d | f_other | d EDep med [MeV] | d σ68 | p EDep med [MeV] | p σ68 |
|---|---|---|---|---|---|---|---|---|---|---|
| B2 | 12,537 | 61,413 | 17,062 | 0.1378 | 0.6748 | 0.1875 | 70.5 | 16.4 | 24.6 | 11.9 |
| B4 | 6,199 | 3,715 | 2,318 | 0.5068 | 0.3037 | 0.1895 | 65.1 | 14.2 | 31.7 | 9.7 |
| B6 | 5,290 | 75 | 1,562 | 0.7637 | 0.0108 | 0.2255 | 7.2 | 15.1 | 50.9 | 13.2 |
| B8 | 4,130 | 10 | 455 | 0.8988 | 0.0022 | 0.0990 | 0.4 | 5.5 | 23.2 | 8.3 |

### Per-LayerID occupancy by species (mapping-independent)

| LayerID | n_p | n_d | n_other | f_p | f_d | f_other |
|---|---|---|---|---|---|---|
| 0 | 10,284 | 60,826 | 11,619 | 0.1243 | 0.7352 | 0.1404 |
| 1 | 8,087 | 41,039 | 5,480 | 0.1481 | 0.7515 | 0.1004 |
| 2 | 5,801 | 3,661 | 1,565 | 0.5261 | 0.3320 | 0.1419 |
| 3 | 5,275 | 1,672 | 765 | 0.6840 | 0.2168 | 0.0992 |
| 4 | 4,996 | 52 | 701 | 0.8690 | 0.0090 | 0.1219 |
| 5 | 4,778 | 28 | 867 | 0.8422 | 0.0049 | 0.1528 |
| 6 | 4,071 | 4 | 335 | 0.9231 | 0.0009 | 0.0760 |
| 7 | 64 | 7 | 123 | 0.3299 | 0.0361 | 0.6340 |

### Penetration depth (deepest LayerID with EDep>0), fraction of tracks

| Species | L0 | L1 | L2 | L3 | L4 | L5 | L6 | L7 |
|---|---|---|---|---|---|---|---|---|
| p | 0.3079 | 0.2073 | 0.0639 | 0.0405 | 0.0354 | 0.0592 | 0.2813 | 0.0044 |
| d | 0.3303 | 0.6083 | 0.0331 | 0.0270 | 0.0008 | 0.0005 | 0.0000 | 0.0001 |
| other | 0.5422 | 0.2556 | 0.0727 | 0.0354 | 0.0325 | 0.0403 | 0.0155 | 0.0058 |

### Truth PID entering each arm (first-layer charged entries)

- enter B: d: 60,826 (0.7352), p: 10,284 (0.1243), alpha: 6,114 (0.0739), pdg1000060120: 3,238 (0.0391), e-: 381 (0.0046), pdg1000030060: 349 (0.0042), pdg1000050110: 255 (0.0031), t: 217 (0.0026)
- enter A: p: 62,034 (0.8334), d: 5,505 (0.0740), pdg1000060120: 2,970 (0.0399), alpha: 2,923 (0.0393), pdg1000060110: 246 (0.0033), e-: 180 (0.0024), pdg1000030060: 100 (0.0013), pdg1000050110: 88 (0.0012)

### Entry-pair table (earliest entering species: B | A)

| B entry | A entry | n | fraction |
|---|---|---|---|
| d | p | 59,061 | 0.9120 |
| p | d | 5,181 | 0.0800 |
| p | p | 370 | 0.0057 |
| pdg1000060120 | p | 41 | 0.0006 |
| d | d | 22 | 0.0003 |
| e- | p | 21 | 0.0003 |
| d | e- | 16 | 0.0002 |
| t | p | 11 | 0.0002 |
| alpha | p | 10 | 0.0002 |
| d | pdg1000060120 | 9 | 0.0001 |

Containment (edep_tot ≥ 0.8·ekin): p: 0.8557, d: 0.8939, other: 0.5884

## Sample II (inclusive) — n_events = 237,098, charged B tracks = 399,664

### Per-stave occupancy by species

| Stave | n_p | n_d | n_other | f_p | f_d | f_other | d EDep med [MeV] | d σ68 | p EDep med [MeV] | p σ68 |
|---|---|---|---|---|---|---|---|---|---|---|
| B2 | 126,715 | 142,587 | 51,671 | 0.3948 | 0.4442 | 0.1610 | 61.9 | 17.3 | 24.5 | 6.8 |
| B4 | 107,011 | 36,231 | 24,222 | 0.6390 | 0.2164 | 0.1446 | 72.0 | 24.9 | 29.5 | 5.2 |
| B6 | 93,861 | 1,223 | 18,164 | 0.8288 | 0.0108 | 0.1604 | 8.5 | 15.8 | 40.5 | 17.2 |
| B8 | 64,200 | 376 | 9,153 | 0.8708 | 0.0051 | 0.1241 | 7.5 | 12.6 | 39.4 | 15.8 |

### Per-LayerID occupancy by species (mapping-independent)

| LayerID | n_p | n_d | n_other | f_p | f_d | f_other |
|---|---|---|---|---|---|---|
| 0 | 116,886 | 139,860 | 32,260 | 0.4044 | 0.4839 | 0.1116 |
| 1 | 110,041 | 104,566 | 19,563 | 0.4699 | 0.4465 | 0.0835 |
| 2 | 102,166 | 35,284 | 14,305 | 0.6732 | 0.2325 | 0.0943 |
| 3 | 95,723 | 27,221 | 9,999 | 0.7200 | 0.2048 | 0.0752 |
| 4 | 90,193 | 805 | 8,658 | 0.9050 | 0.0081 | 0.0869 |
| 5 | 84,905 | 502 | 9,559 | 0.8941 | 0.0053 | 0.1007 |
| 6 | 62,874 | 247 | 5,912 | 0.9108 | 0.0036 | 0.0856 |
| 7 | 30,626 | 143 | 3,279 | 0.8995 | 0.0042 | 0.0963 |

### Penetration depth (deepest LayerID with EDep>0), fraction of tracks

| Species | L0 | L1 | L2 | L3 | L4 | L5 | L6 | L7 |
|---|---|---|---|---|---|---|---|---|
| p | 0.1112 | 0.0991 | 0.0753 | 0.0637 | 0.0597 | 0.1626 | 0.2240 | 0.2043 |
| d | 0.2590 | 0.4845 | 0.0614 | 0.1845 | 0.0049 | 0.0032 | 0.0016 | 0.0010 |
| other | 0.3119 | 0.1886 | 0.1382 | 0.0965 | 0.0836 | 0.0923 | 0.0571 | 0.0319 |

### Truth PID entering each arm (first-layer charged entries)

- enter B: d: 139,860 (0.4839), p: 116,886 (0.4044), alpha: 15,583 (0.0539), pdg1000060120: 8,264 (0.0286), e-: 2,861 (0.0099), pdg1000030060: 856 (0.0030), pdg1000050110: 783 (0.0027), pdg1000060110: 693 (0.0024)
- enter A: p: 62,057 (0.8326), d: 5,576 (0.0748), pdg1000060120: 2,975 (0.0399), alpha: 2,926 (0.0393), pdg1000060110: 246 (0.0033), e-: 180 (0.0024), pdg1000030060: 101 (0.0014), pdg1000050110: 88 (0.0012)

### Entry-pair table (earliest entering species: B | A)

| B entry | A entry | n | fraction |
|---|---|---|---|
| p | none | 95,706 | 0.4037 |
| d | none | 76,478 | 0.3226 |
| d | p | 59,074 | 0.2492 |
| p | d | 5,252 | 0.0222 |
| p | p | 378 | 0.0016 |
| pdg1000060120 | p | 41 | 0.0002 |
| pdg1000060120 | none | 26 | 0.0001 |
| d | d | 22 | 0.0001 |
| e- | p | 21 | 0.0001 |
| e- | none | 18 | 0.0001 |

Containment (edep_tot ≥ 0.8·ekin): p: 0.6958, d: 0.8435, other: 0.5793

## Mechanism check (pd-pair tagging)

In Sample I, the fraction of events with a deuteron entering B and a proton entering A is 0.9120; proton-into-B with deuteron-into-A is 0.0800. A dominant d|p (or p|d) population is the direct signature of the kinematically correlated pd-elastic pair that the A·B coincidence tags.

## Caveats

- Truth-level only: EDep is used as the pulse-amplitude proxy; no digitizer, no threshold, no saturation, no Birks quenching. Data-facing amplitudes will differ.
- The LayerID->stave mapping ({0,1}->B2, {2,3}->B4, {4,5}->B6, {6,7}->B8) is a repo convention UNDER REVIEW; per-LayerID (0-7) tables are reported so conclusions can be re-derived under an alternative mapping (e.g. odd-layers-unread).
- Upstream beamline material is missing from the geometry (MV3/MV3b): absolute penetration depths and stave energies are biased toward deeper/through-going tracks. Enrichment RATIOS between Sample I and Sample II (same geometry, same bias) are more robust than any absolute fraction quoted here.
- Sample I is a subset of Sample II (inclusive definitions), so the inclusive enrichment ratio's binomial errors are positively correlated (CI conservative in the usual direction but not exact); the exclusive I vs II-minus-I comparison uses disjoint events and is reported alongside.
- Entry kinetic energy converts GeV/c momenta to MeV/c (C3 fix); containment is a heuristic flag (edep_tot >= 0.8*ekin) and punch-through tracks make 'deepest layer' an underestimate of true range.

## Artifacts

- `s21_summary.json` — all tables with counts
- `s21_overview.png` — multi-panel overview figure

Reproduce:
```
python3 scripts/s21_sample12_trigger_truth_comparison.py --mc /projects/hep/fs10/shared/nnbar/billy/ccb-testbeam/geant4/data/output_krakow_1M.root --max-events 0 --out /projects/hep/fs10/shared/nnbar/billy/ccb-testbeam/reports/s21_sample12_trigger_truth_1783077969
```
