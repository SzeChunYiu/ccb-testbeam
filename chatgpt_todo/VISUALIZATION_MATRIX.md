# Visualization Coverage Matrix

This matrix links scientific or reproducibility claims to the visual evidence required to support them. A plot is not considered complete until its generating command, inputs, provenance, uncertainty meaning, output path, and acceptance interpretation are recorded.

| Viz ID | Claim / task | Status | Inputs | Version-controlled generator | Required views | Output / acceptance criteria |
|---|---|---|---|---|---|---|
| VIZ-G4-MT-001 | Same seed is reproducible across one and multiple worker threads | IMPLEMENTED_NOT_RUN | `mt_rng_t1.root`, `mt_rng_t4.root`, both metadata sidecars | `scripts/compare_single_stave_mt_reproducibility.py` | Summary page; distributions; candidate/reference ratios; event-keyed difference histograms for deposited energy, track length, generated photons, arrivals, detections, and saturated PE | `docs/figures/g4_mt_rng_t1_vs_t4.pdf`; exact-tolerance pass preferred. Any nonzero tolerance requires documented physical/numerical justification. |
| VIZ-G4-MT-002 | Merged MT event tree contains complete, unique events | IMPLEMENTED_NOT_RUN | Each ROOT `events` tree plus metadata `n_events` | Same validator JSON event-ID section | Tabular duplicate, missing, unexpected, total, and unique counts | JSON must show IDs exactly `0..N-1`, no duplicates, omissions, or unexpected IDs. |
| VIZ-G4-MT-003 | Requested, forced, and effective worker counts are faithfully recorded | SPECIFIED | One-thread, four-thread, and `G4FORCENUMBEROFTHREADS=2 --threads 4` metadata sidecars | Add a small provenance-table renderer or use a version-controlled Markdown/CSV generator | Requested / environment override / effective / observed event rows for each run | Forced run must record requested=4, effective=2, override=`2`; no hidden worker-count state. |
| VIZ-G4-PHOTON-001 | Per-photon output is complete and thread-reproducible | SPECIFIED | ROOT `photons` trees from one-thread and four-thread runs | Extend the MT validator or add a dedicated photon-tree validator | Photon rows per event/sensor; wavelength, arrival-time and path-length overlays/ratios; detected fraction; event foreign-key integrity | All photon event IDs must refer to valid event rows; same-seed distributions and event-keyed photon records must satisfy documented reproducibility criteria. |
| VIZ-G4-SEED-001 | Different random seeds form independent, statistically consistent ensembles | SPECIFIED | At least four seeds per thread configuration | New ensemble script linked from `AUD-G4-001` | Per-seed mean/variance with intervals; cross-seed correlation matrix; between-thread effect sizes; convergence versus event count | No duplicated streams; thread configuration effect consistent with zero within preregistered uncertainty; seed variation reported rather than hidden. |
| VIZ-G4-PE178-001 | Optical collection is approximately 178 PE/event | BLOCKED | Exact original commit/configuration, optical tables, geometry hash, seed ensemble, regenerated ROOT outputs | Locate original generator, then create a version-controlled yield-summary script | PE distribution; mean/median and robust interval; per-sensor breakdown; thread/seed stability; old-versus-corrected comparison | Reproduced value, uncertainty, event count, configuration, and any shift after RNG correction must be reported before the headline claim is retained. |

## Plot standards

- Axes, units, sample selection, normalization, binning, and uncertainty definitions are mandatory.
- Ratio panels must expose empty-reference bins rather than silently replacing them with zero.
- Event-keyed comparisons must sort or join by event ID; file row order is not physical evidence.
- Color cannot be the only distinction between samples.
- Generated figures must have a machine-readable companion summary whenever practical.
- Raw data and oversized generated binaries must follow repository artifact policy and must not be committed casually.
