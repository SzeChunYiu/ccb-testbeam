# MV4 -- Timing-Resolution Toy Diagnostic

- status: **TOY_DIAGNOSTIC** (was MV4/PRODUCTION)
- calibration source: **loaded** (`/projects/hep/fs10/shared/nnbar/billy/ccb-wt-clD/reports/studies/clusterD/mv_runs/mv0/calibration.json`)
- data anchors source: **fallback**
- mode: synthetic  seed: 20260720
- generated: 2026-07-25T16:34:46.282262+00:00
- tracks used: 4011 (proton 2587, deuteron 1424)
- digitizer: gain=110 ADC/MeV, noise=50 ADC, ped=350, tau_rise=2.5, tau_decay=42.0 ns

> WARNING: this run used HARD-CODED FALLBACK values (gain and/or data anchors). It is a diagnostic only. Re-run with --calibration and --data-anchors (and --strict) for a production result.

## Reproduce
```
mv4_timing_study.py --mc <root> --out <dir> --calibration <mv0 calibration.json> --data-anchors <anchors.json> --strict --slice-by species,amplitude
```

## Global metrics (raw / timewalk-corrected test-half)
| metric | raw | corrected |
|---|---|---|
| sigma68 [ns] | 4.75 | 4.592 |
| RMS [ns] | 11.71 | 11.09 |
| Gaussian-core sigma [ns] | 1.873 | 2.436 |
| tail frac (>3.0sig) | 0.1381 | 0.1287 |
| chi2/ndf | 7.511e+10 | 1.219e+09 |
| sigma68 unc [ns] | 0.5981 | 0.9233 |

- improvement factor (raw/corr sigma68): 1.0342813143796887
- timewalk fit: A=1.316 ns, B=-2489.51 ns*ADC (1/A form)

## LORO / per-run spread (raw sigma68)
- runs: 5  full sigma68=4.750 ns
- leave-one-run-out sigma68: mean=4.720, std=0.232, min=4.371, max=5.095 ns
- per-run sigma68 spread (std): 0.986 ns

## Slices
| dim | value | n | raw sig68 | corr sig68 | raw tail | corr tail |
|---|---|---|---|---|---|---|
| species | deuteron | 1424 | 2.469 | 2.522 | 0.111 | 0.107 |
| species | proton | 2587 | 8.656 | 7.271 | 0.106 | 0.111 |
| amplitude | amp_q1 | 1003 | 18.351 | 18.084 | 0.000 | 0.000 |
| amplitude | amp_q2 | 1002 | 8.227 | 8.238 | 0.104 | 0.101 |
| amplitude | amp_q3 | 1003 | 1.993 | 2.052 | 0.035 | 0.034 |
| amplitude | amp_q4 | 1003 | 1.442 | 1.545 | 0.007 | 0.003 |

(full per-slice metrics incl. RMS, core-sigma, chi2/ndf in `mv4_slice_metrics.csv`)

## Comparison to data anchors
| stage | MC sigma68 [ns] | data sigma68 [ns] | pull | verdict |
|---|---|---|---|---|
| raw CFD20 | 4.75+/-0.60 | 1.85 | +4.78 | FAIL |
| timewalk-corr | 4.59+/-0.92 | 1.50 | +3.33 | FAIL |

## Open questions / caveats
- STATUS is TOY_DIAGNOSTIC until re-run on LUNARC with the v2 calibration and measured anchors.
- Absolute residual offset is set by the (arbitrary) window placement; only the spread (sigma68) is physical.
- Noise/tau taken from the digitizer card; an MV0-style data-driven pulse-shape fit would remove the remaining modeling freedom.
