# MC Production Forensic Report: output_krakow_1M.root

Issue: #1311
Date: 2026-08-14
Verdict: HISTORICAL_PROVENANCE_GATED

## Executive Summary

The historical MC file output_krakow_1M.root (SHA-256 2b62403f...42cc, 677 MB) CANNOT be bound to a complete production receipt. The file was created on 2026-07-09 11:29:48 and predates the current validated source-measure infrastructure. It contains non-unit PrimaryWeight values, confirming the legacy weighted source scheme (sigma(theta_lab)), which is defective per #1053.

## Recovered Evidence

File Identity:
- Path: geant4/data/output_krakow_1M.root
- SHA-256: 2b62403f0aa7ecc8c6fc8ffb5006b59d833ff1a31a95a8f389f88f45a18542cc
- Size: 677,221,620 bytes
- Created: 2026-07-09 11:29:48 +0200
- Events: 1,000,000 in hibeam TTree

Configuration (inferred):
- Macro: geant4/macros/run_krakow.mac (190 MeV, 1M events)
- Config: geant4/configs/krakow.config (Wasa geometry)
- Cross-section table: sigma_pd_cm_190.txt (SHA: 0ca33e76...)

## Missing Provenance

1. Exact Git commit: No ScatteringGenerator.cc history before 2026-07-10
2. Build receipt: No executable hash or build log
3. Random seed: Not recorded
4. Runtime host: No SLURM job ID found
5. Geometry digest: Geometry file has no recorded hash
6. Source-measure mode: Legacy weighted confirmed but exact formula unverified
7. Post-processing: No record of ROOT operations

## Search Scope

Searched: filesystem timestamps, slurm outputs, bash history, git logs, adjacent files, conda environments. No exact production receipt found.

## Physics Implications

Confirmed defects: #1053 (legacy weight), predates #1178 (direct-CDF), no #1179 (uncertainty). The file must NOT be used as primary publication MC.

## Verdict

HISTORICAL_PROVENANCE_GATED. This file is retained for historical diagnostics only. Regeneration from current validated stack is required.

## References

Issues #1311, #1053, #1178, #1179. PR #1329 (weight adapter).
