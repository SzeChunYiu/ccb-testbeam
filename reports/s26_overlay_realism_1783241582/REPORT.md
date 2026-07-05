# S26 — Two-pulse overlay realism: phase jitter + cross-stave (B-M7)

- Generated: 2026-07-05 08:54:57 UTC
- Git commit: `b85f11bc75f4d95e48a7037aad5c7939135262c3`
- Records/rate/config: 30000; rates [0.5, 1.5, 3.0] MHz; overlap fraction 0.7.
- Phase jitter: t1 ~ Uniform(45, 55) ns (peak lands ~40-60 ns). Cross-stave: pulse 2 donor stave != host, digitized with the donor kernel.

## Verdict at matched 80% coverage (mean over rates)

| config | trad failure | ML failure | winner | margin |
|---|---|---|---|---|
| pinned_same | 0.0000 | 0.0007 | **trad** | 0.0007 |
| jitter_same | 0.0000 | 0.0010 | **trad** | 0.0010 |
| jitter_cross | 0.0000 | 0.0005 | **trad** | 0.0005 |

## Failure @ 80% coverage and common-subset sigma68, per rate

### pinned_same
| rate (MHz) | trad fail [CI] | ML fail [CI] | sigma68 trad | sigma68 ML | n common |
|---|---|---|---|---|---|
| 0.5 | 0.0000 [0.0000, 0.0000] | 0.0010 [0.0004, 0.0017] | 0.338 | 1.083 | 7237 |
| 1.5 | 0.0000 [0.0000, 0.0000] | 0.0004 [0.0000, 0.0010] | 0.340 | 1.071 | 7218 |
| 3 | 0.0000 [0.0000, 0.0000] | 0.0007 [0.0002, 0.0014] | 0.334 | 1.111 | 7339 |

### jitter_same
| rate (MHz) | trad fail [CI] | ML fail [CI] | sigma68 trad | sigma68 ML | n common |
|---|---|---|---|---|---|
| 0.5 | 0.0000 [0.0000, 0.0000] | 0.0014 [0.0007, 0.0023] | 0.351 | 1.409 | 7397 |
| 1.5 | 0.0000 [0.0000, 0.0000] | 0.0008 [0.0002, 0.0014] | 0.354 | 1.417 | 7460 |
| 3 | 0.0000 [0.0000, 0.0000] | 0.0008 [0.0004, 0.0014] | 0.342 | 1.404 | 7452 |

### jitter_cross
| rate (MHz) | trad fail [CI] | ML fail [CI] | sigma68 trad | sigma68 ML | n common |
|---|---|---|---|---|---|
| 0.5 | 0.0000 [0.0000, 0.0000] | 0.0010 [0.0004, 0.0017] | 0.410 | 1.428 | 7494 |
| 1.5 | 0.0000 [0.0000, 0.0000] | 0.0002 [0.0000, 0.0006] | 0.402 | 1.442 | 7489 |
| 3 | 0.0000 [0.0000, 0.0000] | 0.0004 [0.0000, 0.0007] | 0.409 | 1.466 | 7632 |

## How the verdict moved vs the pinned single-stave result

Pinned single-stave: winner **trad** (trad 0.0000 vs ML 0.0007). Adding phase jitter: winner **trad** (trad 0.0000 vs ML 0.0010). Adding cross-stave overlays too: winner **trad** (trad 0.0000 vs ML 0.0005). The matched-coverage verdict is STABLE across the realism axes.

## Caveats
- Digitization sums per-constituent card-kernel analog waveforms + pedestal (6752) + 8 ADC RMS
  noise; identical across configs so the comparison is internal and apples-to-apples. It omits
  the pipeline's per-hit transport smear (0.5 ns << 10 ns), so absolute numbers differ slightly
  from s24; only the config-to-config movement is interpreted.
- Gain is the card placeholder (297 ADC/MeV, arbitrary scale); the A>1000-equivalent boundary is
  not a physical energy. Kernel-family circularity (fit template shares the card kernel) persists
  for the traditional method; the cross-stave config partially breaks it (donor kernel != host).
- Stave/amplitude weights inherit the un-triggered MC truth population (MV3 spectrum discrepancy).
