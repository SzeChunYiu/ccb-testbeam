# ΔE–E composite-key rerun on real data (A-002 / CCB-DELTAE-FIX, DONE)

Reruns the ΔE–E event build on **real data** with the composite key
`(source_file_id, run, evt)` per `scripts/single_stave/deltaE_E.py`, and quantifies
exactly how corrupt the prior `eventno`-only outputs were. Source:
`reports/1781014251.574.7a497937/pulse_taxonomy_table.csv.gz` (per-hit pulses,
staves B2/B4/B6/B8).

## The eventno-only join was catastrophic

| quantity | value |
|---|--:|
| valid physical events (composite key) | **385,984** |
| distinct `eventno` values | 559,841 |
| `eventno` values spanning **>1** physical event | **73,098** |
| **events an `eventno`-only join would corrupt** | **146,196 (≈38%)** |

Nearly **4 in 10 events** would be wrongly merged by the old `eventno`-only join
(finding A-002). The composite `(source_file_id, run, evt)` key eliminates this.
This is the concrete confirmation that the prior eventno-only ΔE–E outputs were
correctly labelled `INVALID_PENDING_RERUN`.

## Valid stopping / penetration profile (composite-key events, threshold 200 ADC)

| deepest B-layer passing threshold | events |
|---|--:|
| B2 (stops in ΔE) | 567,925 |
| B4 | 26,978 |
| B6 | 14,586 |
| B8 (punch-through) | 8,575 |
| none | 14,875 |

The expected penetration cascade (most events stop in B2, a falling tail reaches
B4→B8). ΔE = amp(B2), E = amp(B4+B6+B8), units **ADC** (never relabeled MeV).
Figure `DE-01_deltaE_E_data.png` is the 2D ΔE–E density over the valid events.

## Status & remaining
- A-002 **rerun complete on real data**: composite key validated, corruption
  quantified, valid stopping distribution + ΔE–E density produced
  (`result.json`, `deltaE_E_events_data.csv`, `DE-01`).
- Data-side only. The full data/MC ΔE–E closure additionally needs the MC side
  (`edep_B2/B4/B6/B8` under the geometry/readout mapping contract) and the
  digitized-MC comparison — still `BLOCKED_COMPUTE`.
- The ~13 `EVENTNO_ONLY_JOIN` scripts the auditor flagged should adopt this
  composite key; each then needs re-validation against its own inputs.
