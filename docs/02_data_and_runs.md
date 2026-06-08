# 02 — Data and runs

## Inputs
- **Raw ROOT:** `data/extracted/root/root/{hrda,hrdb}_run_NNNN.root` (110 files).
- **Sorted ROOT:** `data/extracted/sorted-{a,b}/*-sorted.root` — the B-stack notes are built
  from `sorted-b`.
- **Pulse table:** a selected-pulse table of **640,737 B-stave pulse records** produced by
  `01_build_pulse_table_from_root.py`; figures by `02_make_report_plots.py`. Reproducing this
  is **Study S00**.

## Selection
- **Only hard cut:** baseline-subtracted amplitude **A = max_j(V_j − b) > 1000 ADC**.
- The **A = 7000 ADC** line is a *diagnostic* marker (large-pulse region), **not** a cut.

## Samples and run splits (newer 122-page report)

| Sample | Runs | Calibration runs | Analysis runs | Notes |
|---|---|---|---|---|
| I (B) | 31–57 | 31–42 (avail. 31–37, 39–42) | 44–57 | run 43 removed; run 38 absent (A) |
| II (B) | 58–65 | 64 | 58–63, 65 | p-enriched |
| III (A) | = Sample I runs | 31–42 | 44–57 | A-stack |
| IV (A) | = Sample II runs | 64 | 58–63, 65 | low stats |

> **Discrepancy with older v41 note** (resolve in S00): the v41 note used Sample II **run 61**
> as the single calibration run and a single Sample I calibration run; the newer report uses a
> **pooled** Sample I calibration (31–42) and run **64** for Sample II. `docs/` follows the
> newer report. Per-stave resolution numbers also differ between the two notes.

## Counts (newer report)
- Sample I: calib 239,559 ev / 248,745 pulses (mult 1.038); analysis 243,133 ev / 252,266
  pulses (mult 1.038).
- Sample II: calib (run 64) 12,103 ev / 14,630 pulses (mult 1.209); analysis 89,807 ev /
  125,096 pulses (mult 1.393).
- Per-stave (Sample I analysis, A>1000): B2 241,422 (median 6542, 41.7% >7000 ADC), B4 6451,
  B6 3094, B8 1299 — strongly **B2-dominated/terminal**.
- Per-stave (Sample II analysis): B2 88,213, B4 21,229, B6 11,148, B8 4506 — flatter, more
  penetrating.

## Topology, in one line
**Sample I** particles overwhelmingly **stop in B2** (terminal, D-like, high ionisation);
**Sample II** particles **penetrate** to B4/B6/B8 (cleaner same-particle timing). This split
drives every timing and pile-up conclusion downstream.
