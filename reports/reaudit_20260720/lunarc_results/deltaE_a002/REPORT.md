# ΔE–E composite-key rerun on real data (A-002 / CCB-DELTAE-FIX, FLAWED)

> **Audit correction (2026-07-22):** the approximately 38% `eventno`-collision
> diagnostic remains internally consistent, but the committed stopping profile,
> event CSV row count, and ΔE–E density are invalid. The bridge retained
> `eventno` in the pivot index, so one physical `(run, evt)` could become multiple
> rows. The report declares 385,984 physical events while its stopping bins sum
> to 632,939. See `AUDIT_INVALIDATION.md`; corrected real-table outputs require a
> rerun with the fixed bridge on current `main`.

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

## Quarantined stopping / penetration profile

The following historical counts are retained only to document the invalidated
artifact. They are **not** a valid event-level stopping distribution because they
sum to 632,939 rather than 385,984 physical events.

| deepest B-layer passing threshold | historical rows (invalid) |
|---|--:|
| B2 | 567,925 |
| B4 | 26,978 |
| B6 | 14,586 |
| B8 | 8,575 |
| none | 14,875 |

The previously described penetration cascade and `DE-01_deltaE_E_data.png` must
not be interpreted until regenerated with one row per physical composite key.
ΔE remains defined as amp(B2), E as amp(B4+B6+B8), in **ADC**.

## Status & remaining

- A-002 eventno-collision diagnosis: **retained**.
- Stopping distribution, event CSV cardinality, and ΔE–E density: **FLAWED**.
- Corrected bridge and synthetic regression test are on `main`.
- Required rerun: regenerate `result.json`, `deltaE_E_events_data.csv`, and
  `DE-01_deltaE_E_data.png`; verify composite-key uniqueness and exact cardinality
  closure; record source hash, code SHA, environment, and exact command.
- Data-side only. Full data/MC ΔE–E closure additionally needs the MC side
  (`edep_B2/B4/B6/B8` under the geometry/readout mapping contract) and digitized
  MC comparison.
- The approximately 13 `EVENTNO_ONLY_JOIN` scripts flagged by the auditor should
  adopt the composite key and be revalidated against their own inputs.
