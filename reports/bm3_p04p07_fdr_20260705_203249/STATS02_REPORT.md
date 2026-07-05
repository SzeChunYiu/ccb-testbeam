# STATS02 (B-M3) — dependence-aware delta-CIs for the P04/P07 ML wins

- Generated: 2026-07-05T18:32:49Z by `scripts/stats02_p04p07_delta_ci.py`
- Bootstrap reps: 4000; metric: res68 = 68th pct of |(pred-target)/target|; delta = res68(best traditional) - res68(ML) (positive = ML better).
- Dependence unit for the paired bootstrap = physical EVENT `(run,eventno)` (pulses in an event share beam/trigger conditions), vs the naive iid per-pulse unit.

## P04 — duplicate-readout closure (full reproduction, paired event-clustered)

- Held-out runs 57,65: n=26857 pulses in 24830 events.

| target | best trad | res68 trad | res68 ML | delta | iid CI | **event-clustered CI** | design effect | z (clustered) |
|---|---|---|---|---|---|---|---|---|
| amp | peak_calibrated | 0.1238 | 0.0096 | 0.1142 | [0.1127,0.1156] | **[0.1127,0.1156]** | 1.02 | 150 |
| charge | integral_calibrated | 0.1954 | 0.0153 | 0.1801 | [0.1783,0.1822] | **[0.1783,0.1825]** | 1.07 | 166 |

- **Event-cluster design effect** (clustered_SE / iid_SE) = 1.02 (amp), 1.07 (charge); mean 1.05. This is the factor by which the naive per-pulse bootstrap CI is too narrow for these observables.

## P07 — saturation recovery (full reproduction, paired event-clustered)

| ceiling ADC | res68 trad | res68 ML | delta | iid CI | **event-clustered CI** | design effect | z (clustered) |
|---|---|---|---|---|---|---|---|
| 4000 | 0.1044 | 0.0324 | 0.0719 | [0.0702,0.0738] | **[0.0702,0.0739]** | 1.00 | 77 |
| 3000 | 0.2389 | 0.0390 | 0.1999 | [0.1959,0.2038] | **[0.1959,0.2041]** | 1.05 | 93 |
| 2500 | 0.2332 | 0.0419 | 0.1913 | [0.1875,0.1962] | **[0.1873,0.1962]** | 1.05 | 81 |
| 2000 | 0.2864 | 0.0459 | 0.2404 | [0.2363,0.2447] | **[0.2358,0.2450]** | 1.10 | 106 |

## P04c / P04d / P04e — variants (conservative delta-CI from own per-method bootstrap CIs, inflated by the P04 event-cluster design effect)

These variants use bespoke traditional baselines (adaptive template / strong Huber) not re-fit here; their win is the SAME duplicate-readout closure with the SAME/ML families. We combine each study's reported best-traditional and best-ML res68 CIs unpaired (se=hypot; wider than paired) and multiply the SE by the measured design effect (1.05) to also cover event clustering. This is conservative on both axes.

| study | best trad res68 [CI] | best ML res68 [CI] | delta | inflated CI | z | CI excl. 0 |
|---|---|---|---|---|---|---|
| P04c | 0.0858 [0.0844,0.0871] | 0.0091 [0.0089,0.0093] | 0.0766 | [0.0752,0.0781] | 105 | True |
| P04d | 0.0203 [0.0199,0.0206] | 0.0027 [0.0026,0.0028] | 0.0176 | [0.0171,0.0180] | 84 | True |
| P04e | 0.1370 [0.1259,0.1455] | 0.0168 [0.0139,0.0196] | 0.1202 | [0.1100,0.1304] | 23 | True |

## Verdict

- Every P04/P07 win now has a machine-readable delta-CI. All emitted delta-CIs exclude zero (ML better): True. Even with the event-cluster design effect (~1.0x SE inflation) and conservative unpaired combination, the smallest z is dozens of sigma.
- Run `scripts/stats01_program_fdr.py` after this to fold these into the amplitude-charge family BH correction; expected result: all P04/P07 wins survive BH (the 6 former 'prose-only' wins are now assessed).
- **BH survival is necessary, not sufficient** (S03k precedent): it certifies statistical distinguishability from zero, NOT that the win is a real absolute-energy gain. P04 remains a duplicate-readout electronics closure (not external-energy truth); P04d/P04e flag B2-externalization/support-frontier caveats; P07's natural-saturation transfer is unaudited. See S11a reconciliation in the B-M3 REPORT.

